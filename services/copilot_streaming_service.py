"""
CROWN⁹ Copilot Streaming Service

Handles token-level streaming from OpenAI with intelligent response structuring,
performance tracking, and emotional coherence.

Target: ≤600ms response start latency
"""

import os
import logging
import time
import json
import asyncio
import threading
import queue
import eventlet
from typing import AsyncGenerator, Dict, Any, Optional, List, Callable
from datetime import datetime
from openai import OpenAI, AsyncOpenAI
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Model configuration with fallback hierarchy (Direct OpenAI API)
# Primary: gpt-4o-mini (fast, cost-effective)
# Fallback 1: gpt-4o (reliable, high capability)
# Fallback 2: gpt-4-turbo (proven stable)
COPILOT_MODEL_HIERARCHY = [
    "gpt-4o-mini",        # Fast, cost-effective
    "gpt-4o",             # Reliable high-capability fallback
    "gpt-4-turbo",        # Proven stable fallback
]

def get_copilot_model() -> str:
    """Get the OpenAI model to use for copilot, respecting env override."""
    env_model = os.getenv("COPILOT_MODEL")
    if env_model:
        return env_model
    return COPILOT_MODEL_HIERARCHY[0]

# Import metrics collector (lazy to avoid circular import)
_metrics_collector = None
def get_metrics_collector():
    global _metrics_collector
    if _metrics_collector is None:
        from services.copilot_metrics_collector import copilot_metrics_collector
        _metrics_collector = copilot_metrics_collector
    return _metrics_collector


@dataclass
class StreamMetrics:
    """Performance metrics for streaming responses."""
    query_received_at: float
    first_token_at: Optional[float] = None
    stream_complete_at: Optional[float] = None
    total_tokens: int = 0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    
    @property
    def first_token_latency_ms(self) -> Optional[float]:
        """Time to first token in milliseconds."""
        if self.first_token_at:
            return (self.first_token_at - self.query_received_at) * 1000
        return None
    
    @property
    def total_latency_ms(self) -> Optional[float]:
        """Total streaming time in milliseconds."""
        if self.stream_complete_at:
            return (self.stream_complete_at - self.query_received_at) * 1000
        return None
    
    @property
    def calm_score(self) -> float:
        """
        Calculate calm score based on performance metrics.
        Target: ≥0.95
        
        Factors:
        - First token latency ≤600ms: +0.5
        - Consistent token delivery: +0.3
        - No errors during stream: +0.2
        """
        score = 0.0
        
        # First token latency check
        if self.first_token_latency_ms and self.first_token_latency_ms <= 600:
            score += 0.5
        elif self.first_token_latency_ms and self.first_token_latency_ms <= 1000:
            score += 0.3
        
        # Completion check
        if self.stream_complete_at:
            score += 0.2
        
        # Token throughput (consistent delivery)
        if self.total_latency_ms and self.total_tokens > 0:
            tokens_per_sec = (self.total_tokens / self.total_latency_ms) * 1000
            if tokens_per_sec >= 20:  # Good throughput
                score += 0.3
            elif tokens_per_sec >= 10:
                score += 0.15
        
        return min(score, 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            **asdict(self),
            'first_token_latency_ms': self.first_token_latency_ms,
            'total_latency_ms': self.total_latency_ms,
            'calm_score': self.calm_score
        }


class CopilotStreamingService:
    """
    Service for streaming AI responses with CROWN⁹ standards.
    
    Capabilities:
    - Token-level streaming with ≤600ms first token latency
    - Multi-layered response structure (Summary, Actions, Insights, Next Steps)
    - Performance tracking and calm score calculation
    - Context-aware response generation
    """
    
    def __init__(self):
        """Initialize OpenAI client with dedicated asyncio thread for eventlet compatibility."""
        # Use user's own OPENAI_API_KEY - connect directly to OpenAI (no Replit proxy)
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            logger.warning("No OPENAI_API_KEY configured - AI Copilot streaming will be disabled")
            self.client = None
            self.async_client = None
            self.async_loop = None
            self.async_thread = None
        else:
            # Initialize clients - connect directly to api.openai.com (no base_url override)
            self.client = OpenAI(api_key=self.api_key)
            self.async_client = AsyncOpenAI(api_key=self.api_key)
            logger.info("✅ OpenAI client initialized - connecting directly to api.openai.com")
            
            # Create dedicated asyncio event loop in background thread for true async streaming
            self.async_loop = None
            self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
            self.async_thread.start()
            
            # Wait for loop to be ready
            timeout = 5
            start = time.time()
            while self.async_loop is None and (time.time() - start) < timeout:
                time.sleep(0.01)
            
            if self.async_loop is None:
                logger.error("Failed to start async event loop")
            else:
                logger.info("OpenAI streaming client initialized with dedicated async thread")
    
    def _run_async_loop(self):
        """Run asyncio event loop in dedicated thread (eventlet-safe)."""
        try:
            self.async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.async_loop)
            self.async_loop.run_forever()
        except Exception as e:
            logger.error(f"Async loop error: {e}", exc_info=True)
        finally:
            if self.async_loop:
                self.async_loop.close()
    
    def stream_response_eventlet_safe(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        workspace_id: Optional[int] = None,
        user_id: Optional[int] = None
    ):
        """
        Stream AI response with TRUE async in dedicated thread (eventlet-safe, non-blocking).
        
        Uses asyncio.run_coroutine_threadsafe to execute async OpenAI streaming in
        dedicated thread, communicating back via queue for full concurrent streaming.
        
        Args:
            user_message: User's query
            context: Optional context (meetings, tasks, embeddings)
            workspace_id: Current workspace ID
            user_id: Current user ID
        
        Yields:
            Dict with streaming events (token-level)
        """
        if not self.async_client or not self.async_loop:
            yield {
                'type': 'error',
                'content': 'AI streaming not configured',
                'error': 'missing_api_key'
            }
            return
        
        # Use thread-safe queue for cross-thread communication
        event_queue = queue.Queue()
        
        async def async_stream_worker():
            """Async worker that streams from OpenAI and pushes to thread-safe queue."""
            try:
                async for event in self.stream_response(
                    user_message=user_message,
                    context=context,
                    workspace_id=workspace_id,
                    user_id=user_id
                ):
                    # Put in thread-safe queue
                    event_queue.put(event)
                
                # Signal completion
                event_queue.put(None)
                
            except Exception as e:
                logger.error(f"Async stream worker error: {e}", exc_info=True)
                event_queue.put({
                    'type': 'error',
                    'content': 'Streaming failed',
                    'error': str(e)
                })
                event_queue.put(None)
        
        # Submit to dedicated asyncio thread
        future = asyncio.run_coroutine_threadsafe(async_stream_worker(), self.async_loop)
        
        # Consume events from queue using non-blocking polling (eventlet-safe)
        while True:
            try:
                # Non-blocking get - raises queue.Empty if no events
                event = event_queue.get_nowait()
                if event is None:
                    break
                yield event
            except queue.Empty:
                # No event ready - yield to eventlet hub and try again
                eventlet.sleep(0)
                # Check if async worker finished
                if future.done():
                    # Get any remaining events
                    try:
                        while True:
                            event = event_queue.get_nowait()
                            if event is None:
                                break
                            yield event
                    except queue.Empty:
                        break
                    break
    
    def stream_response_sync(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        workspace_id: Optional[int] = None,
        user_id: Optional[int] = None
    ):
        """
        Stream AI response (blocking sync - only use for non-concurrent scenarios).
        
        Args:
            user_message: User's query
            context: Optional context (meetings, tasks, embeddings)
            workspace_id: Current workspace ID
            user_id: Current user ID
        
        Yields:
            Dict with streaming events:
            - type: 'token' | 'section' | 'metrics' | 'complete'
            - content: Token text or structured data
            - section: Optional section indicator (summary, actions, insights, next_steps)
        """
        if not self.client:
            yield {
                'type': 'error',
                'content': 'AI streaming not configured',
                'error': 'missing_api_key'
            }
            return
        
        # Initialize metrics
        metrics = StreamMetrics(query_received_at=time.time())
        
        try:
            # Build messages with system prompt and context
            messages = self._build_messages(user_message, context)
            
            # Start streaming (SYNC) with model fallback
            model_to_use = get_copilot_model()
            stream = None
            last_error = None
            
            for model in [model_to_use] + [m for m in COPILOT_MODEL_HIERARCHY if m != model_to_use]:
                try:
                    stream = self.client.chat.completions.create(
                        model=model,
                        messages=messages,  # type: ignore[arg-type]
                        temperature=0.7,
                        max_tokens=1500,
                        stream=True,
                        stream_options={"include_usage": True}
                    )
                    logger.info(f"Copilot streaming using model: {model}")
                    break
                except Exception as model_error:
                    last_error = model_error
                    logger.warning(f"Model {model} unavailable: {model_error}, trying fallback...")
                    continue
            
            if stream is None:
                raise last_error or Exception("No available models")
            
            current_section = None
            buffer = ""
            chunk_count = 0
            
            for chunk in stream:
                chunk_count += 1
                
                # Record first token timing (handle non-content deltas)
                if metrics.first_token_at is None:
                    # Check for any delta (content, role, tool_calls, etc.)
                    has_delta = (chunk.choices and len(chunk.choices) > 0 and 
                                chunk.choices[0].delta)
                    if has_delta:
                        metrics.first_token_at = time.time()
                        
                        # Emit first token metrics
                        yield {
                            'type': 'metrics',
                            'event': 'first_token',
                            'latency_ms': metrics.first_token_latency_ms
                        }
                
                # Extract delta content
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    if delta.content:
                        content = delta.content
                        buffer += content
                        
                        # Detect section markers and structured content
                        section = self._detect_section(buffer)
                        if section and section != current_section:
                            current_section = section
                            yield {
                                'type': 'section',
                                'section': section,
                                'content': f"\n## {section.title()}\n"
                            }
                        
                        # Stream token
                        yield {
                            'type': 'token',
                            'content': content,
                            'section': current_section
                        }
                
                # Capture usage data when available (usually at stream end)
                if hasattr(chunk, 'usage') and chunk.usage:
                    if chunk.usage.prompt_tokens is not None:
                        metrics.prompt_tokens = chunk.usage.prompt_tokens
                    if chunk.usage.completion_tokens is not None:
                        metrics.completion_tokens = chunk.usage.completion_tokens
                        metrics.total_tokens = chunk.usage.completion_tokens
            
            # Mark completion
            metrics.stream_complete_at = time.time()
            
            # Emit final metrics
            yield {
                'type': 'metrics',
                'event': 'complete',
                **metrics.to_dict()
            }
            
            # Log performance
            logger.info(
                f"Copilot stream complete: {metrics.first_token_latency_ms:.0f}ms first token, "
                f"{metrics.total_latency_ms:.0f}ms total, calm_score={metrics.calm_score:.2f}"
            )
            
            # Record metrics in collector for SLA monitoring
            metrics_collector = get_metrics_collector()
            if metrics_collector and metrics.first_token_latency_ms:
                metrics_collector.record_response_latency(
                    latency_ms=metrics.first_token_latency_ms,
                    calm_score=metrics.calm_score
                )
            
            # Emit completion event
            yield {
                'type': 'complete',
                'message': buffer,
                'metrics': metrics.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Copilot streaming error: {e}", exc_info=True)
            yield {
                'type': 'error',
                'content': 'Failed to generate response',
                'error': str(e)
            }
    
    async def stream_response(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        workspace_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream AI response with token-level granularity.
        
        Args:
            user_message: User's query
            context: Optional context (meetings, tasks, embeddings)
            workspace_id: Current workspace ID
            user_id: Current user ID
        
        Yields:
            Dict with streaming events:
            - type: 'token' | 'section' | 'metrics' | 'complete'
            - content: Token text or structured data
            - section: Optional section indicator (summary, actions, insights, next_steps)
        """
        if not self.async_client:
            yield {
                'type': 'error',
                'content': 'AI streaming not configured',
                'error': 'missing_api_key'
            }
            return
        
        # Initialize metrics
        metrics = StreamMetrics(query_received_at=time.time())
        
        try:
            # Build messages with system prompt and context
            messages = self._build_messages(user_message, context)
            
            # Start streaming with model fallback
            model_to_use = get_copilot_model()
            stream = None
            last_error = None
            
            for model in [model_to_use] + [m for m in COPILOT_MODEL_HIERARCHY if m != model_to_use]:
                try:
                    stream = await self.async_client.chat.completions.create(
                        model=model,
                        messages=messages,  # type: ignore[arg-type]
                        temperature=0.7,
                        max_tokens=1500,
                        stream=True,
                        stream_options={"include_usage": True}
                    )
                    logger.info(f"Copilot async streaming using model: {model}")
                    break
                except Exception as model_error:
                    last_error = model_error
                    logger.warning(f"Model {model} unavailable: {model_error}, trying fallback...")
                    continue
            
            if stream is None:
                raise last_error or Exception("No available models")
            
            current_section = None
            buffer = ""
            chunk_count = 0
            
            async for chunk in stream:
                chunk_count += 1
                
                # Record first token timing (handle non-content deltas)
                if metrics.first_token_at is None:
                    # Check for any delta (content, role, tool_calls, etc.)
                    has_delta = (chunk.choices and len(chunk.choices) > 0 and 
                                chunk.choices[0].delta)
                    if has_delta:
                        metrics.first_token_at = time.time()
                        
                        # Emit first token metrics
                        yield {
                            'type': 'metrics',
                            'event': 'first_token',
                            'latency_ms': metrics.first_token_latency_ms
                        }
                
                # Extract delta content
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    if delta.content:
                        content = delta.content
                        buffer += content
                        
                        # Detect section markers and structured content
                        section = self._detect_section(buffer)
                        if section and section != current_section:
                            current_section = section
                            yield {
                                'type': 'section',
                                'section': section,
                                'content': f"\n## {section.title()}\n"
                            }
                        
                        # Stream token
                        yield {
                            'type': 'token',
                            'content': content,
                            'section': current_section
                        }
                
                # Capture usage data when available (usually at stream end)
                if hasattr(chunk, 'usage') and chunk.usage:
                    if chunk.usage.prompt_tokens is not None:
                        metrics.prompt_tokens = chunk.usage.prompt_tokens
                    if chunk.usage.completion_tokens is not None:
                        metrics.completion_tokens = chunk.usage.completion_tokens
                        # Use actual completion tokens for total
                        metrics.total_tokens = chunk.usage.completion_tokens
            
            # Mark completion
            metrics.stream_complete_at = time.time()
            
            # Emit final metrics
            yield {
                'type': 'metrics',
                'event': 'complete',
                **metrics.to_dict()
            }
            
            # Log performance
            logger.info(
                f"Copilot stream complete: {metrics.first_token_latency_ms:.0f}ms first token, "
                f"{metrics.total_latency_ms:.0f}ms total, calm_score={metrics.calm_score:.2f}"
            )
            
            # Record metrics in collector for SLA monitoring
            metrics_collector = get_metrics_collector()
            if metrics_collector and metrics.first_token_latency_ms:
                metrics_collector.record_response_latency(
                    latency_ms=metrics.first_token_latency_ms,
                    calm_score=metrics.calm_score
                )
            
            # Emit completion event
            yield {
                'type': 'complete',
                'message': buffer,
                'metrics': metrics.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield {
                'type': 'error',
                'content': 'Failed to generate response',
                'error': str(e)
            }
    
    def _build_messages(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """
        Build message array with system prompt and CROWN⁹ enhanced context.
        
        CROWN⁹ Enhanced Context Building:
        - User workspace context (tasks, meetings)
        - Proactive insights (overdue, blockers, due soon)
        - Semantic context from RAG retrieval
        - Conversation history for continuity
        
        Args:
            user_message: User's query
            context: Optional context data
        
        Returns:
            List of message dictionaries for OpenAI API
        """
        # System prompt defining Copilot's role (Industry-leading)
        system_prompt = """You are Mina Copilot, the cognitive thread that connects every thought, task, and moment of work.

Your purpose is to perceive, interpret, and synchronize — bridging meetings, tasks, calendar, and analytics through natural dialogue.

CAPABILITIES:
- Understand user's workspace: meetings, tasks, calendar, analytics
- Provide actionable insights with clear next steps
- Execute actions: create tasks, schedule meetings, prioritize work
- Surface blockers and overdue items proactively
- Learn from interactions to improve over time

RESPONSE STRUCTURE (use markdown headers):
Start with a direct answer to the query, then use these section headers:

### Actions
Specific, actionable next steps. Format action buttons as: [Button Text](#)

### Insights  
Relevant patterns, blockers, or observations from the data.

### Next Steps
Forward-looking recommendations.

FORMATTING RULES:
- Use ### for section headers (NOT ** bold **)
- Use bullet points with - for lists
- Use [text](#) for action buttons
- Keep responses concise and well-structured

CRITICAL GUIDELINES:
- ALWAYS use the ACTUAL data from the context provided (real task names, real meeting titles, real dates)
- NEVER output placeholders like [Task Name], [Date], [Meeting Title], or similar bracket text
- If no relevant data exists in context, say so clearly instead of using placeholder text
- Be concise but thorough
- Prioritize actionable responses
- Reference specific data with exact names and dates from the context
- Maintain calm, professional, intelligent tone
- Never say "I don't have access" — use the context provided
- When listing tasks, use the exact titles: "Schedule a follow-up with client" NOT "[Task Name]"
- When mentioning dates, use the actual date: "December 1, 2024" NOT "[Date]" """
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Build comprehensive context
        if context:
            context_parts = []
            
            # Proactive insights (HIGH PRIORITY - surface first)
            if context.get('proactive_insights'):
                insights = context['proactive_insights']
                insight_lines = []
                for insight in insights:
                    severity = insight.get('severity', 'medium')
                    emoji = '🔴' if severity == 'high' else '🟡' if severity == 'medium' else '🟢'
                    insight_lines.append(f"{emoji} {insight.get('message', '')}")
                if insight_lines:
                    context_parts.append("⚠️ PROACTIVE ALERTS:\n" + "\n".join(insight_lines))
            
            # Blockers (HIGH PRIORITY)
            if context.get('blockers'):
                blockers = context['blockers']
                blocker_lines = [f"- {b.get('title', 'Untitled')} (blocked)" for b in blockers[:3]]
                context_parts.append(f"🚫 BLOCKERS ({len(blockers)}):\n" + "\n".join(blocker_lines))
            
            # Query-relevant tasks (HIGH PRIORITY - matches user's question)
            if context.get('query_relevant_tasks'):
                relevant = context['query_relevant_tasks']
                relevant_lines = []
                for t in relevant[:5]:
                    status = t.get('status', 'todo')
                    status_label = status.upper() if status else 'TODO'
                    status_emoji = '✅' if status == 'completed' else '🔴' if t.get('is_overdue') else '📋'
                    priority = t.get('priority', 'medium')
                    priority_tag = f"[{priority.upper()}]" if priority in ['high', 'urgent'] else ""
                    due = f" (due: {t.get('due_date')})" if t.get('due_date') else ""
                    # Include explicit status text for AI accuracy
                    relevant_lines.append(f"{status_emoji} {t.get('title', 'Untitled')} - STATUS: {status_label} {priority_tag}{due}")
                context_parts.append(f"🎯 MATCHING TASKS (found {len(relevant)} matching your query):\n" + "\n".join(relevant_lines))
            
            # Recent tasks
            if context.get('recent_tasks'):
                tasks = context['recent_tasks']
                task_lines = []
                for t in tasks[:10]:  # Increased from 7 to 10 for better coverage
                    status = t.get('status', 'todo')
                    status_label = status.upper() if status else 'TODO'
                    status_emoji = '✅' if status == 'completed' else '🔴' if t.get('is_overdue') else '📋'
                    priority = t.get('priority', 'medium')
                    priority_tag = f"[{priority.upper()}]" if priority in ['high', 'urgent'] else ""
                    due = f" (due: {t.get('due_date')})" if t.get('due_date') else ""
                    # Include explicit status text for AI accuracy
                    task_lines.append(f"{status_emoji} {t.get('title', 'Untitled')} [{status_label}] {priority_tag}{due}")
                context_parts.append(f"📋 RECENT TASKS ({len(tasks)}):\n" + "\n".join(task_lines))
            
            # Recent meetings
            if context.get('recent_meetings'):
                meetings = context['recent_meetings']
                meeting_lines = []
                for m in meetings[:5]:
                    has_summary = "📝" if m.get('has_summary') else ""
                    meeting_lines.append(f"- {m.get('title', 'Untitled')} {has_summary}")
                context_parts.append(f"📅 RECENT MEETINGS ({len(meetings)}):\n" + "\n".join(meeting_lines))
            
            # Semantic context from RAG (HIGH VALUE)
            if context.get('semantic_context'):
                semantic = context['semantic_context']
                if semantic:
                    semantic_lines = []
                    for s in semantic[:3]:
                        text = s.get('text', '')[:100]
                        similarity = s.get('similarity', 0)
                        if similarity > 0.7:
                            semantic_lines.append(f"- {text}...")
                    if semantic_lines:
                        context_parts.append("🧠 RELATED CONTEXT:\n" + "\n".join(semantic_lines))
            
            # Conversation history for continuity
            if context.get('conversation_history'):
                history = context['conversation_history']
                if history:
                    recent_messages = [f"User: {h.get('message', '')[:50]}..." for h in history[:2]]
                    if recent_messages:
                        context_parts.append("💬 RECENT CONVERSATION:\n" + "\n".join(recent_messages))
            
            # Activity summary
            if context.get('activity'):
                activity = context['activity']
                tasks_today = activity.get('tasks_today', 0)
                completed = activity.get('tasks_completed_recently', 0)
                productivity = activity.get('productivity_score', 50)
                context_parts.append(f"📊 ACTIVITY: {tasks_today} tasks due today, {completed} completed recently, productivity score: {productivity}%")
            
            # User name for personalization
            if context.get('user_name'):
                context_parts.insert(0, f"👤 User: {context['user_name']}")
            
            # Add summary if provided
            if context.get('summary'):
                context_parts.append(f"📌 Context: {context['summary']}")
            
            if context_parts:
                messages.append({
                    "role": "system",
                    "content": "WORKSPACE CONTEXT:\n\n" + "\n\n".join(context_parts)
                })
        
        # Add user message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _detect_section(self, text: str) -> Optional[str]:
        """
        Detect section type from response text.
        
        Sections:
        - summary: Context overview
        - actions: Interactive elements
        - insights: Trends or blockers
        - next_steps: Future guidance
        """
        text_lower = text.lower()
        
        # Look for section markers (supporting ### header format)
        if any(marker in text_lower for marker in ['### summary', '## summary', '**summary**', 'summary:']):
            return 'summary'
        elif any(marker in text_lower for marker in ['### actions', '## actions', '**actions**', 'actions:', 'you can:']):
            return 'actions'
        elif any(marker in text_lower for marker in ['### insights', '## insights', '**insights**', 'insights:', 'trends:']):
            return 'insights'
        elif any(marker in text_lower for marker in ['### next steps', '### next', '## next', '**next steps**', 'next steps:', 'recommend:']):
            return 'next_steps'
        
        return None


# Singleton instance
copilot_streaming_service = CopilotStreamingService()
