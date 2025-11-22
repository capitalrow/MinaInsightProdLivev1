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
        self.api_key = os.getenv("AI_INTEGRATIONS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("AI_INTEGRATIONS_OPENAI_BASE_URL")
        
        if not self.api_key:
            logger.warning("No OpenAI API key configured - streaming will be disabled")
            self.client = None
            self.async_client = None
            self.async_loop = None
            self.async_thread = None
        else:
            # Initialize clients
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
                
            self.client = OpenAI(**client_kwargs)
            self.async_client = AsyncOpenAI(**client_kwargs)
            
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
            
            # Start streaming (SYNC)
            stream = self.client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
                stream=True,
                stream_options={"include_usage": True}
            )
            
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
            
            # Start streaming
            stream = await self.async_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
                stream=True,
                stream_options={"include_usage": True}
            )
            
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
        Build message array with system prompt and context.
        
        Args:
            user_message: User's query
            context: Optional context data
        
        Returns:
            List of message dictionaries for OpenAI API
        """
        # System prompt defining Copilot's role
        system_prompt = """You are Mina Copilot, the cognitive thread that connects every thought, task, and moment of work.

Your purpose is to perceive, interpret, and synchronize — bridging meetings, tasks, calendar, and analytics through natural dialogue.

When responding:
1. **Summary** - Provide context overview first
2. **Actions** - Suggest interactive next steps
3. **Insights** - Surface trends or blockers
4. **Next Steps** - Recommend future guidance

Be concise, intelligent, and emotionally calm. Every query is both reflection and action."""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add context if provided
        if context:
            context_parts = []
            
            if context.get('recent_tasks'):
                tasks = context['recent_tasks']
                context_parts.append(f"Recent Tasks ({len(tasks)} items):\n" + 
                                   "\n".join([f"- {t.get('title', 'Untitled')}" for t in tasks[:5]]))
            
            if context.get('recent_meetings'):
                meetings = context['recent_meetings']
                context_parts.append(f"Recent Meetings ({len(meetings)} items):\n" +
                                   "\n".join([f"- {m.get('title', 'Untitled')}" for m in meetings[:3]]))
            
            if context.get('summary'):
                context_parts.append(f"Context: {context['summary']}")
            
            if context_parts:
                messages.append({
                    "role": "system",
                    "content": "Context from your workspace:\n\n" + "\n\n".join(context_parts)
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
        
        # Look for section markers
        if any(marker in text_lower for marker in ['## summary', '**summary**', 'summary:']):
            return 'summary'
        elif any(marker in text_lower for marker in ['## actions', '**actions**', 'actions:', 'you can:']):
            return 'actions'
        elif any(marker in text_lower for marker in ['## insights', '**insights**', 'insights:', 'trends:']):
            return 'insights'
        elif any(marker in text_lower for marker in ['## next', '**next steps**', 'next steps:', 'recommend:']):
            return 'next_steps'
        
        return None


# Singleton instance
copilot_streaming_service = CopilotStreamingService()
