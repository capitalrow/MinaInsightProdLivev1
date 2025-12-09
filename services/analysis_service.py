"""
Analysis Service (M3) - AI-powered meeting insights generation.

This service handles the generation of Actions, Decisions, and Risks
from meeting transcripts using configurable AI engines.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from flask import current_app
from sqlalchemy.orm import Session as DbSession

from app import db
from models.session import Session
from models.segment import Segment
from models.summary import Summary, SummaryLevel, SummaryStyle
from services.text_matcher import TextMatcher
import os
import inspect

# Lazy-load MemoryStore to avoid PostgreSQL connection at import time in test environments
_memory = None

def get_memory_store():
    """Lazy load MemoryStore to avoid connection at import time in tests."""
    global _memory
    if _memory is None:
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url.startswith("postgresql"):
            from server.models.memory_store import MemoryStore
            _memory = MemoryStore()
    return _memory

logger = logging.getLogger(__name__)
text_matcher = TextMatcher()


class AnalysisService:
    """Service for generating AI-powered meeting insights with multi-level and multi-style support."""
    
    # Multi-level, multi-style prompt templates
    PROMPT_TEMPLATES = {
        # Brief Level Prompts
        "brief_executive": """
        You are a C-level executive assistant. Create a brief executive summary (2-3 sentences max) of this meeting.
        Focus on strategic decisions, financial impact, and high-level outcomes only.
        
        Return ONLY valid JSON:
        {{
            "brief_summary": "2-3 sentence executive summary",
            "executive_insights": [{{"insight": "Key strategic point", "impact": "Business impact"}}]
        }}
        
        Meeting transcript:
        {transcript}
        """,
        
        "brief_action": """
        You are a STRICT evidence-based task extraction specialist. Extract ONLY action items that are EXPLICITLY stated in the transcript.
        
        CORE PHILOSOPHY: ZERO HALLUCINATION
        If you cannot find the EXACT words in the transcript, DO NOT extract it.
        It is better to miss a task than to invent one.
        
        STRICT EXTRACTION RULES:
        1. ONLY extract tasks where the speaker EXPLICITLY commits to an action
        2. The evidence_quote MUST be a VERBATIM quote that appears word-for-word in the transcript
        3. If the transcript is about "testing" something, do NOT invent related tasks like "check pages" or "update settings"
        4. When in doubt, DO NOT extract
        
        VALID PATTERNS (extract these):
        ✓ "I will work on X" → Extract "Work on X"
        ✓ "I need to do Y today" → Extract "Do Y"
        ✓ "The action item is Z" → Extract "Z"
        
        INVALID PATTERNS (DO NOT extract):
        ✗ Implied tasks not explicitly stated
        ✗ Tasks the AI thinks "should" happen based on context
        ✗ Recommendations you would make to the speaker
        ✗ Any task where you cannot provide a VERBATIM quote from the transcript
        
        FEW-SHOT EXAMPLES:
        
        Example 1 - Explicit Task:
        Transcript: "The critical action I will take is to work on the AI Copilot page and make sure it's fully functioning. That's due today."
        Output: {{
            "brief_summary": "Speaker stated one critical action item regarding the AI Copilot page.",
            "action_plan": [
                {{"action": "Work on the AI Copilot page and make sure it's fully functioning", "evidence_quote": "The critical action I will take is to work on the AI Copilot page and make sure it's fully functioning", "owner": "Not specified", "priority": "high", "due": "today"}}
            ]
        }}
        
        Example 2 - Testing Session (NO extra tasks):
        Transcript: "Just testing the live transcription as well as checking the insights."
        Output: {{
            "brief_summary": "Testing session for transcription and insights functionality.",
            "action_plan": []
        }}
        NOTE: Do NOT invent tasks like "check the session page" or "update the meetings page" - these were never stated.
        
        Example 3 - Multiple Explicit Tasks:
        Transcript: "I need to clean my bedroom today, get 30 pounds from the ATM, and buy a train ticket for tomorrow."
        Output: {{
            "brief_summary": "Personal task planning for household chores, finances, and travel.",
            "action_plan": [
                {{"action": "Clean bedroom", "evidence_quote": "I need to clean my bedroom today", "owner": "Not specified", "priority": "medium", "due": "today"}},
                {{"action": "Get 30 pounds from the ATM", "evidence_quote": "get 30 pounds from the ATM", "owner": "Not specified", "priority": "medium", "due": "Not specified"}},
                {{"action": "Buy a train ticket for tomorrow", "evidence_quote": "buy a train ticket for tomorrow", "owner": "Not specified", "priority": "medium", "due": "tomorrow"}}
            ]
        }}
        
        Return ONLY valid JSON:
        {{
            "brief_summary": "2-3 sentence FACTUAL summary of what was discussed",
            "action_plan": [
                {{
                    "action": "Task description from transcript", 
                    "evidence_quote": "VERBATIM quote from transcript (MUST appear word-for-word)",
                    "owner": "Person mentioned or 'Not specified'", 
                    "priority": "high/medium/low",
                    "due": "Date/time mentioned or 'Not specified'"
                }}
            ]
        }}
        
        Meeting transcript:
        {transcript}
        """,
        
        # Standard Level Prompts
        "standard_executive": """
        You are a STRICT evidence-based meeting analyst. Extract ONLY action items, decisions, and risks that are EXPLICITLY stated in the transcript.
        
        CORE PHILOSOPHY: ZERO HALLUCINATION
        If you cannot find the EXACT words in the transcript, DO NOT extract it.
        It is better to miss an item than to invent one that wasn't said.
        
        STRICT EXTRACTION RULES:
        1. ONLY extract items where the speaker EXPLICITLY states them
        2. The evidence_quote MUST be a VERBATIM quote that appears word-for-word in the transcript
        3. If the transcript is about "testing" something, do NOT invent related tasks
        4. Do NOT add tasks you think "should" happen - only what was ACTUALLY said
        5. When in doubt, DO NOT extract
        
        For ACTIONS:
        ✓ ONLY extract explicit commitments: "I will...", "I need to...", "The action is..."
        ✗ Do NOT extract implied tasks, suggestions you would make, or contextual inferences
        
        For DECISIONS:
        ✓ ONLY extract explicit decisions: "We decided...", "We're going with...", "Approved..."
        ✗ Do NOT extract implied decisions or assumptions
        
        For RISKS:
        ✓ ONLY extract explicitly stated concerns: "I'm worried about...", "The risk is..."
        ✗ Do NOT extract risks you think exist but weren't mentioned
        
        FEW-SHOT EXAMPLES:
        
        Example 1 - Explicit Content:
        Transcript: "We decided to proceed with cloud migration. John will lead the team. There's risk around downtime."
        Output: {{
            "summary_md": "Team decided on cloud migration with John as lead. Downtime risk noted.",
            "actions": [
                {{"text": "Lead the team for cloud migration", "evidence_quote": "John will lead the team", "owner": "John", "due": "Not specified"}}
            ],
            "decisions": [
                {{"text": "Proceed with cloud migration", "evidence_quote": "We decided to proceed with cloud migration", "impact": "Not specified"}}
            ],
            "risks": [
                {{"text": "Downtime risk", "evidence_quote": "There's risk around downtime", "mitigation": "Not specified"}}
            ]
        }}
        
        Example 2 - Testing Session with ONE Real Task:
        Transcript: "Just testing the transcription. The critical action I will take that is due today is to work on the AI Copilot page."
        Output: {{
            "summary_md": "Testing session with one explicit action item regarding the AI Copilot page.",
            "actions": [
                {{"text": "Work on the AI Copilot page", "evidence_quote": "The critical action I will take that is due today is to work on the AI Copilot page", "owner": "Not specified", "due": "today"}}
            ],
            "decisions": [],
            "risks": []
        }}
        NOTE: Do NOT add extra tasks like "check session page" or "update meetings" - these were never stated!
        
        Example 3 - Pure Conversation (NO extraction):
        Transcript: "How was your weekend? I went hiking."
        Output: {{
            "summary_md": "Casual conversation about weekend activities.",
            "actions": [],
            "decisions": [],
            "risks": []
        }}
        
        Return ONLY valid JSON with VERBATIM evidence quotes:
        {{
            "summary_md": "FACTUAL summary of what was ACTUALLY said (no embellishment or inference)",
            "actions": [
                {{
                    "text": "Task exactly as stated", 
                    "evidence_quote": "VERBATIM quote from transcript (MUST appear word-for-word)",
                    "owner": "Person name or 'Not specified'", 
                    "due": "Date/time mentioned or 'Not specified'"
                }}
            ],
            "decisions": [
                {{
                    "text": "Decision exactly as stated",
                    "evidence_quote": "VERBATIM quote from transcript",
                    "impact": "Impact mentioned or 'Not specified'"
                }}
            ],
            "risks": [
                {{
                    "text": "Risk exactly as stated",
                    "evidence_quote": "VERBATIM quote from transcript",
                    "mitigation": "Mitigation mentioned or 'Not specified'"
                }}
            ]
        }}
        
        Meeting transcript:
        {transcript}
        """,
        
        "standard_technical": """
        You are a technical lead. Create a standard technical summary (1-2 paragraphs) focusing on implementation details.
        Include technical decisions, architecture choices, and development tasks.
        
        Return ONLY valid JSON:
        {{
            "summary_md": "Standard technical summary in markdown format",
            "actions": [{{"text": "Technical task", "owner": "Person or unknown", "due": "Date or unknown", "complexity": "high/medium/low"}}],
            "decisions": [{{"text": "Technical decision", "rationale": "Why this was chosen"}}],
            "risks": [{{"text": "Technical risk", "mitigation": "Technical solution"}}],
            "technical_details": [{{"area": "Technology/Architecture", "details": "Technical specifics", "impact": "Development impact"}}]
        }}
        
        Meeting transcript:
        {transcript}
        """,
        
        "standard_narrative": """
        You are a storytelling analyst. Create a standard narrative summary (1-2 paragraphs) that tells the story of this meeting.
        Focus on the chronological flow of discussions and how decisions evolved.
        
        Return ONLY valid JSON:
        {{
            "summary_md": "Standard narrative summary in markdown format",
            "actions": [{{"text": "Action description", "owner": "Person or unknown", "due": "Date or unknown"}}],
            "decisions": [{{"text": "Decision description", "context": "How this decision came about"}}],
            "risks": [{{"text": "Risk description", "mitigation": "Suggested mitigation or unknown"}}]
        }}
        
        Meeting transcript:
        {transcript}
        """,
        
        "standard_bullet": """
        You are a structured analyst. Create a standard bullet-point summary (1-2 paragraphs) using clear bullet points and lists.
        Focus on organized, scannable information.
        
        Return ONLY valid JSON:
        {{
            "summary_md": "Standard bullet-point summary in markdown format with bullet points",
            "actions": [{{"text": "Action description", "owner": "Person or unknown", "due": "Date or unknown"}}],
            "decisions": [{{"text": "Decision description"}}],
            "risks": [{{"text": "Risk description", "mitigation": "Suggested mitigation or unknown"}}]
        }}
        
        Meeting transcript:
        {transcript}
        """,
        
        "brief_narrative": """
        You are a concise storyteller. Create a brief narrative summary (2-3 sentences max) that tells the key story of this meeting.
        Focus on the main flow and outcome.
        
        Return ONLY valid JSON:
        {{
            "brief_summary": "2-3 sentence narrative summary"
        }}
        
        Meeting transcript:
        {transcript}
        """,
        
        "brief_bullet": """
        You are a structured summarizer. Create a brief bullet-point summary (2-3 key points max).
        Focus on the most important outcomes in bullet format.
        
        Return ONLY valid JSON:
        {{
            "brief_summary": "2-3 key bullet points summary"
        }}
        
        Meeting transcript:
        {transcript}
        """,
        
        # Detailed Level Prompts
        "detailed_comprehensive": """
        You are a comprehensive meeting analyst. Create a detailed, multi-section analysis of this meeting.
        Include all aspects: strategic, operational, technical, and actionable items.
        
        Return ONLY valid JSON:
        {{
            "detailed_summary": "Comprehensive multi-section analysis in markdown format",
            "summary_md": "Overview paragraph",
            "brief_summary": "2-3 sentence executive summary",
            "actions": [{{"text": "Action item", "owner": "Person or unknown", "due": "Date or unknown", "priority": "high/medium/low", "category": "strategic/operational/technical"}}],
            "decisions": [{{"text": "Decision made", "rationale": "Why this was decided", "impact": "Expected impact", "stakeholders": "Who is affected"}}],
            "risks": [{{"text": "Risk identified", "mitigation": "Mitigation strategy", "severity": "high/medium/low", "timeline": "When this might occur"}}],
            "executive_insights": [{{"insight": "Strategic insight", "impact": "Business impact", "timeline": "When this matters", "stakeholders": "Who should know"}}],
            "technical_details": [{{"area": "Technical area", "details": "Specific details", "decisions": "Technical choices made", "next_steps": "What needs to happen"}}],
            "action_plan": [{{"phase": "Implementation phase", "tasks": "What needs to be done", "owner": "Who leads this", "timeline": "When this happens"}}]
        }}
        
        Meeting transcript:
        {transcript}
        """
    }
    
    @classmethod
    def validate_prompt_templates(cls) -> Dict[str, bool]:
        """
        Validate all prompt templates can be formatted correctly.
        This should be called on service initialization to catch template errors early.
        
        Returns:
            Dict mapping template keys to validation status (True = valid, False = invalid)
        """
        validation_results = {}
        test_transcript = "This is a test meeting transcript to validate template formatting."
        
        for key, template in cls.PROMPT_TEMPLATES.items():
            try:
                # Test if template can be formatted with transcript placeholder
                formatted = template.format(transcript=test_transcript)
                validation_results[key] = True
                logger.debug(f"✅ Template '{key}' validation passed")
            except KeyError as e:
                validation_results[key] = False
                logger.error(f"❌ Template '{key}' validation failed: KeyError {e}")
            except Exception as e:
                validation_results[key] = False
                logger.error(f"❌ Template '{key}' validation failed: {e}")
        
        # Log summary
        total = len(validation_results)
        valid = sum(validation_results.values())
        if valid == total:
            logger.info(f"✅ All {total} prompt templates validated successfully")
        else:
            invalid = total - valid
            invalid_keys = [k for k, v in validation_results.items() if not v]
            logger.error(f"❌ {invalid}/{total} prompt templates failed validation: {invalid_keys}")
        
        return validation_results
    
    @staticmethod
    def generate_summary(session_id: int, level: SummaryLevel = SummaryLevel.STANDARD, style: SummaryStyle = SummaryStyle.EXECUTIVE) -> Dict:
        """
        Generate AI-powered summary for a session with specified level and style.
        
        Args:
            session_id: ID of the session to analyse
            level: Summary detail level (brief, standard, detailed)
            style: Summary style (executive, action, technical, narrative, bullet)
            
        Returns:
            Dict containing the generated summary data
            
        Raises:
            ValueError: If session not found or no segments available
        """
        logger.info(f"Generating summary for session {session_id}")
        
        # Load session once (used for both validation and progress broadcasting)
        session = db.session.get(Session, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Get external session ID for WebSocket progress broadcasting (optional, for chunked processing)
        external_session_id = getattr(session, 'external_id', None)
        if not external_session_id:
            logger.info(f"Session {session_id} has no external_id - progress events will be skipped")

        # --- Memory-aware context (NEW) ---
        memory_context = ""
        try:
            memory = get_memory_store()
            if memory:
                related_memories = memory.search_memory(f"session_{session_id}", top_k=10)
                if related_memories:
                    joined = "\n".join([m["content"] for m in related_memories])
                    memory_context = f"\n\nPreviously recalled notes:\n{joined}\n\n"
                    logger.info(f"Added {len(related_memories)} related memories to context.")
                else:
                    logger.info("No related memories found for this session.")
            else:
                logger.info("Memory store not available, skipping memory retrieval.")
        except Exception as e:
            logger.warning(f"Memory retrieval skipped: {e}")
        
        # Load final segments ordered by timestamp
        from sqlalchemy import select
        stmt = select(Segment).filter(
            Segment.session_id == session_id, 
            Segment.kind == 'final'
        ).order_by(Segment.start_ms)
        final_segments = db.session.execute(stmt).scalars().all()
        
        # Determine analysis engine from configuration
        # Default to 'openai_gpt' to use real AI analysis (not mock)
        try:
            engine = current_app.config.get('ANALYSIS_ENGINE', 'openai_gpt')
        except RuntimeError:
            # If running outside Flask context, check if API key is available
            import os
            api_key = os.environ.get('OPENAI_API_KEY')
            engine = 'openai_gpt' if api_key else 'mock'
            logger.warning(f"Running outside Flask context, using engine: {engine}")
        
        # Initialize context variable for all code paths
        context = ""
        
        if not final_segments:
            logger.warning(f"No final segments found for session {session_id}")
            # Create empty summary for sessions without transcript
            summary_data = {
                'summary_md': 'No transcript available for analysis.',
                'actions': [],
                'decisions': [],
                'risks': []
            }
        else:
            # Build context string from segments
            context = AnalysisService._build_context(list(final_segments))
            
            # Log what we're analyzing for debugging
            word_count = len(context.split())
            logger.info(f"[AI Analysis] Session {session_id}: {len(final_segments)} final segments, {word_count} words, {len(context)} chars")
            logger.debug(f"[AI Analysis] Transcript preview: {context[:500]}...")
            
            # Combine transcript with any recalled memory context
            context_with_memory = f"{memory_context}{context}"
            
            # Validate transcript quality before processing
            validation_result = AnalysisService._validate_transcript_quality(context)
            
            if not validation_result['is_valid']:
                logger.warning(f"Transcript quality issue for session {session_id}: {validation_result['reason']}")
                # Return informative message for low-quality transcripts
                summary_data = {
                    'summary_md': validation_result['message'],
                    'actions': [],
                    'decisions': [],
                    'risks': [],
                    'validation_warning': validation_result['reason']
                }
            else:
                # Generate insights using OpenAI engine only - no mock fallbacks in production
                if engine == 'openai_gpt':
                    summary_data = AnalysisService._analyse_with_openai(context_with_memory, level, style, external_session_id=external_session_id)
                else:
                    # AI service unavailable - return informative error instead of fake data
                    logger.error("AI analysis unavailable: OpenAI API key not configured")
                    summary_data = {
                        'summary_md': '## AI Analysis Unavailable\n\nThe AI-powered meeting analysis service is currently unavailable. Please ensure your OpenAI API key is properly configured to enable meeting summaries and insights.',
                        'actions': [],
                        'decisions': [],
                        'risks': [],
                        'error': 'AI service unavailable - OpenAI API key not configured'
                    }
                
                # Attach any validation warnings to summary data for UI display
                if validation_result.get('warning'):
                    summary_data['quality_warning'] = validation_result['warning']
                    logger.info(f"Quality warning for session {session_id}: {validation_result['warning']}")
        
        # Persist summary to database
        summary = AnalysisService._persist_summary(session_id, summary_data, engine, level, style)

        logger.info(f"Generated summary {summary.id} for session {session_id} using {engine}")

        # --- Store summary + key insights back into memory (NEW) ---
        try:
            memory = get_memory_store()
            if memory:
                def _safe(text):
                    return text.strip() if isinstance(text, str) else ""

                # store main summary
                if summary_data.get("summary_md"):
                    memory.add_memory(session_id, "summary_bot", _safe(summary_data["summary_md"]), source_type="summary")

                # store highlights / actions / decisions for semantic recall
                for item in summary_data.get("actions", []) or []:
                    memory.add_memory(session_id, "summary_bot", _safe(item.get("text")), source_type="action_item")

                for item in summary_data.get("decisions", []) or []:
                    memory.add_memory(session_id, "summary_bot", _safe(item.get("text")), source_type="decision")

                for item in summary_data.get("risks", []) or []:
                    memory.add_memory(session_id, "summary_bot", _safe(item.get("text")), source_type="risk")

                logger.info("Summary data stored back into MemoryStore successfully.")
            else:
                logger.info("Memory store not available, skipping summary persistence to memory.")
        except Exception as e:
            logger.warning(f"Could not persist summary to MemoryStore: {e}")
        
        # 🔄 Trigger analytics sync if relevant meeting exists
        try:
            from services.analytics_service import AnalyticsService
            import threading

            session_obj = db.session.get(Session, session_id)
            meeting = getattr(session_obj, "meeting", None)

            if meeting:
                analytics_service = AnalyticsService()
                # Capture real Flask app object (not LocalProxy) for thread safety
                from flask import current_app as app_proxy
                app = app_proxy._get_current_object()  # type: ignore
                meeting_id = meeting.id
                
                # Run analytics in background thread with app context
                def run_analytics():
                    try:
                        import asyncio
                        with app.app_context():
                            asyncio.run(analytics_service.analyze_meeting(meeting_id))
                            logger.info(f"Analytics sync completed for meeting {meeting_id}")
                    except Exception as e:
                        logger.warning(f"Analytics sync failed for meeting {meeting_id}: {e}")
                
                thread = threading.Thread(target=run_analytics, daemon=True)
                thread.start()
                logger.info(f"Triggered analytics sync for meeting {meeting_id} (session {session_id})")
            else:
                logger.info(f"No linked meeting found for session {session_id}, skipping analytics sync.")
        except Exception as e:
            logger.warning(f"Failed to trigger analytics after summary: {e}")

        return summary.to_dict()
    
    @staticmethod
    def get_session_summary(session_id: int) -> Optional[Dict]:
        """
        Get the latest summary for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Summary dictionary or None if not found
        """
        from sqlalchemy import select
        stmt = select(Summary).filter(
            Summary.session_id == session_id
        ).order_by(Summary.created_at.desc())
        summary = db.session.execute(stmt).scalar_one_or_none()
        
        return summary.to_dict() if summary else None
    
    @staticmethod
    def _validate_transcript_quality(context: str) -> Dict[str, Any]:
        """
        Validate transcript quality before AI processing.
        
        Args:
            context: Transcript text to validate
            
        Returns:
            Dictionary with validation results:
            - is_valid: bool indicating if transcript is suitable for analysis
            - reason: str explaining validation failure (if any)
            - message: str user-friendly message for invalid transcripts
        """
        # Calculate basic metrics
        word_count = len(context.split())
        char_count = len(context.strip())
        
        # Check for completely empty transcript
        if char_count == 0:
            return {
                'is_valid': False,
                'reason': 'empty_transcript',
                'message': 'No transcript content available for analysis.'
            }
        
        # Check for very short transcripts (< 30 words)
        if word_count < 30:
            return {
                'is_valid': False,
                'reason': 'transcript_too_short',
                'message': f'This recording is too short to analyze ({word_count} words). Please record at least 30 words for meaningful insights.'
            }
        
        # Check for minimal content (30-50 words - warning zone)
        if word_count < 50:
            logger.info(f"Transcript has minimal content ({word_count} words), insights may be limited")
            # Allow processing but flag as limited
            return {
                'is_valid': True,
                'reason': 'limited_content',
                'message': None,
                'warning': f'Short transcript ({word_count} words). Insights may be limited.'
            }
        
        # Check for nonsensical/repetitive content (simple heuristic)
        words = context.lower().split()
        unique_words = set(words)
        uniqueness_ratio = len(unique_words) / len(words) if words else 0
        
        # If less than 20% unique words, likely gibberish or highly repetitive
        if uniqueness_ratio < 0.2 and word_count > 50:
            return {
                'is_valid': False,
                'reason': 'low_content_quality',
                'message': 'This transcript appears to contain mostly repetitive content. Please ensure clear audio for better results.'
            }
        
        # All validation checks passed
        return {
            'is_valid': True,
            'reason': None,
            'message': None
        }
    
    # Chunking configuration for long transcripts
    CHUNK_SIZE = 6000  # ~6k chars per chunk (leaves room for prompt overhead)
    CHUNK_OVERLAP = 500  # 500 char overlap for context continuity
    CHUNKING_THRESHOLD = 10000  # Use chunking for transcripts > 10k chars
    
    @staticmethod
    def _build_context(segments: List[Segment]) -> str:
        """
        Build FULL context string from final segments without truncation.
        Chunking is handled separately in _analyse_with_openai for long transcripts.
        
        Args:
            segments: List of final segments ordered by time
            
        Returns:
            Full context string (no truncation - chunking handles long transcripts)
        """
        # Build full transcript without truncation
        transcript_parts = []
        for segment in segments:
            # Format with timestamp for context
            if hasattr(segment, 'start_time_formatted'):
                time_str = f"[{segment.start_time_formatted}]"
            elif segment.start_ms is not None:
                time_str = f"[{segment.start_ms//1000}s]"
            else:
                time_str = "[0s]"
            transcript_parts.append(f"{time_str} {segment.text}")
        
        full_transcript = " ".join(transcript_parts)
        
        # Log transcript size for debugging
        logger.info(f"[Build Context] Full transcript: {len(full_transcript)} chars, {len(full_transcript.split())} words")
        
        return full_transcript
    
    @staticmethod
    def _chunk_transcript(transcript: str, chunk_size: int = None, overlap: int = None) -> List[Dict[str, Any]]:
        """
        Split long transcript into overlapping chunks for processing.
        Maintains sentence boundaries for better context.
        
        Args:
            transcript: Full transcript text
            chunk_size: Target chunk size in chars (default: CHUNK_SIZE)
            overlap: Overlap between chunks in chars (default: CHUNK_OVERLAP)
            
        Returns:
            List of chunk dicts with keys: text, chunk_index, total_chunks, start_char, end_char
        """
        if chunk_size is None:
            chunk_size = AnalysisService.CHUNK_SIZE
        if overlap is None:
            overlap = AnalysisService.CHUNK_OVERLAP
        
        # If transcript fits in one chunk, return as single chunk
        if len(transcript) <= chunk_size:
            return [{
                'text': transcript,
                'chunk_index': 0,
                'total_chunks': 1,
                'start_char': 0,
                'end_char': len(transcript)
            }]
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(transcript):
            # Calculate end position
            end = min(start + chunk_size, len(transcript))
            
            # If not at the end, try to break at sentence boundary
            if end < len(transcript):
                # Look for sentence endings (. ! ?) within last 500 chars of chunk
                search_start = max(end - 500, start)
                last_sentence_end = -1
                
                for i in range(end - 1, search_start - 1, -1):
                    if transcript[i] in '.!?' and (i + 1 >= len(transcript) or transcript[i + 1] in ' \n'):
                        last_sentence_end = i + 1
                        break
                
                # Use sentence boundary if found, otherwise use chunk_size
                if last_sentence_end > start:
                    end = last_sentence_end
            
            chunk_text = transcript[start:end].strip()
            
            if chunk_text:  # Only add non-empty chunks
                chunks.append({
                    'text': chunk_text,
                    'chunk_index': chunk_index,
                    'total_chunks': -1,  # Will be updated after all chunks created
                    'start_char': start,
                    'end_char': end
                })
                chunk_index += 1
            
            # Break if we've reached the end of the transcript
            if end >= len(transcript):
                break
            
            # Move start position forward with overlap for context continuity
            # The new start should be (end - overlap) to maintain overlap
            # But ensure we always advance by at least (chunk_size - overlap) to prevent micro-chunks
            min_advance = chunk_size - overlap  # Normal step size when not at sentence boundary
            new_start = end - overlap
            
            # If we'd advance less than expected (due to short sentence boundary chunk), 
            # ensure we still make meaningful progress
            if new_start <= start:
                new_start = start + min_advance
            
            start = new_start
        
        # Update total_chunks in all chunks
        total = len(chunks)
        for chunk in chunks:
            chunk['total_chunks'] = total
        
        logger.info(f"[Chunking] Split {len(transcript)} chars into {total} chunks (size={chunk_size}, overlap={overlap})")
        
        return chunks
    
    @staticmethod
    def _merge_insights(chunk_results: List[Dict], level: SummaryLevel, style: SummaryStyle) -> Dict:
        """
        Merge insights from multiple chunk analyses into unified result.
        Handles deduplication, summary combination, and metadata aggregation.
        
        Args:
            chunk_results: List of analysis results from individual chunks
            level: Summary detail level
            style: Summary style type
            
        Returns:
            Merged analysis results dictionary
        """
        if not chunk_results:
            return {
                'summary_md': 'No content to analyze.',
                'actions': [],
                'decisions': [],
                'risks': []
            }
        
        if len(chunk_results) == 1:
            return chunk_results[0]
        
        logger.info(f"[Merge] Merging insights from {len(chunk_results)} chunks")
        
        # Initialize merged result
        merged = {
            'summary_md': '',
            'brief_summary': '',
            'actions': [],
            'decisions': [],
            'risks': [],
            'executive_insights': [],
            'technical_details': [],
            'action_plan': [],
            '_chunked_processing': {
                'chunk_count': len(chunk_results),
                'merge_timestamp': datetime.utcnow().isoformat()
            }
        }
        
        # Collect all items from all chunks
        all_summaries = []
        all_brief_summaries = []
        
        for i, result in enumerate(chunk_results):
            # Collect summaries
            if result.get('summary_md'):
                all_summaries.append(f"**Part {i+1}:** {result['summary_md']}")
            if result.get('brief_summary'):
                all_brief_summaries.append(result['brief_summary'])
            
            # Collect actions with chunk source
            for action in result.get('actions', []) or []:
                action['_source_chunk'] = i
                merged['actions'].append(action)
            
            # Collect decisions with chunk source
            for decision in result.get('decisions', []) or []:
                decision['_source_chunk'] = i
                merged['decisions'].append(decision)
            
            # Collect risks with chunk source
            for risk in result.get('risks', []) or []:
                risk['_source_chunk'] = i
                merged['risks'].append(risk)
            
            # Collect other insights
            for insight in result.get('executive_insights', []) or []:
                merged['executive_insights'].append(insight)
            for detail in result.get('technical_details', []) or []:
                merged['technical_details'].append(detail)
            for plan_item in result.get('action_plan', []) or []:
                merged['action_plan'].append(plan_item)
        
        # Combine summaries
        if all_summaries:
            merged['summary_md'] = '\n\n'.join(all_summaries)
        if all_brief_summaries:
            # Use first and last for brief summary to capture beginning and end
            if len(all_brief_summaries) >= 2:
                merged['brief_summary'] = f"{all_brief_summaries[0]} [...] {all_brief_summaries[-1]}"
            else:
                merged['brief_summary'] = all_brief_summaries[0]
        
        # Deduplicate actions by text similarity
        merged['actions'] = AnalysisService._deduplicate_items(merged['actions'], 'text')
        merged['decisions'] = AnalysisService._deduplicate_items(merged['decisions'], 'text')
        merged['risks'] = AnalysisService._deduplicate_items(merged['risks'], 'text')
        
        logger.info(f"[Merge] Final counts - Actions: {len(merged['actions'])}, Decisions: {len(merged['decisions'])}, Risks: {len(merged['risks'])}")
        
        return merged
    
    @staticmethod
    def _deduplicate_items(items: List[Dict], text_key: str, similarity_threshold: float = 0.8) -> List[Dict]:
        """
        Deduplicate items based on text similarity.
        
        Args:
            items: List of item dicts
            text_key: Key containing the text to compare
            similarity_threshold: Threshold for considering items duplicates (0-1)
            
        Returns:
            Deduplicated list of items
        """
        if not items:
            return []
        
        unique_items = []
        
        for item in items:
            item_text = item.get(text_key, '').lower().strip()
            if not item_text:
                continue
            
            is_duplicate = False
            for existing in unique_items:
                existing_text = existing.get(text_key, '').lower().strip()
                
                # Simple similarity check: normalized word overlap
                item_words = set(item_text.split())
                existing_words = set(existing_text.split())
                
                if not item_words or not existing_words:
                    continue
                
                intersection = len(item_words & existing_words)
                union = len(item_words | existing_words)
                similarity = intersection / union if union > 0 else 0
                
                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_items.append(item)
        
        if len(items) != len(unique_items):
            logger.debug(f"[Dedupe] Removed {len(items) - len(unique_items)} duplicates (from {len(items)} to {len(unique_items)})")
        
        return unique_items
    
    @staticmethod
    def _analyse_with_openai(context: str, level: SummaryLevel, style: SummaryStyle, external_session_id: Optional[str] = None) -> Dict:
        """
        Analyse context using OpenAI GPT with specified level and style.
        For long transcripts (>10k chars), uses chunked processing to capture full content.
        Implements exponential backoff retry (3 attempts: 0s, 2s, 5s).
        
        Args:
            context: Meeting transcript context
            level: Summary detail level
            style: Summary style type
            external_session_id: Optional session ID for WebSocket progress broadcasting
            
        Returns:
            Analysis results dictionary
        """
        import time
        
        # Check if we need chunked processing for long transcripts
        if len(context) > AnalysisService.CHUNKING_THRESHOLD:
            logger.info(f"[Chunked Analysis] Transcript is {len(context)} chars (>{AnalysisService.CHUNKING_THRESHOLD}), using chunked processing")
            return AnalysisService._analyse_with_chunking(context, level, style, external_session_id=external_session_id)
        
        # Standard single-call processing for shorter transcripts
        logger.info(f"[Single Analysis] Transcript is {len(context)} chars, using single-call processing")
        
        # Retry configuration
        MAX_RETRIES = 3
        BACKOFF_DELAYS = [0, 2, 5]  # delay in seconds: attempt 0=0s, attempt 1=2s, attempt 2=5s
        
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            try:
                if attempt > 0:
                    delay = BACKOFF_DELAYS[attempt]  # Fixed: use attempt directly as index
                    logger.info(f"[Retry {attempt}/{MAX_RETRIES-1}] Waiting {delay}s before retry...")
                    time.sleep(delay)
                    logger.info(f"[Retry {attempt}/{MAX_RETRIES-1}] Attempting OpenAI analysis again...")
                
                # Perform the actual OpenAI call
                result = AnalysisService._perform_openai_analysis(context, level, style, attempt)
                
                # Success! Return immediately
                if attempt > 0:
                    logger.info(f"[Retry Success] Analysis succeeded on attempt {attempt + 1}")
                return result
                
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                logger.warning(f"[Attempt {attempt + 1}/{MAX_RETRIES}] Failed: {e}")
                
                # If this was the last attempt, raise
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"[Retry Exhausted] All {MAX_RETRIES} attempts failed")
                    raise ValueError(f"OpenAI analysis failed after {MAX_RETRIES} attempts: {e}") from e
                
                # Otherwise, continue to next retry
                continue
                
            except Exception as e:
                # For non-retryable errors (API key missing, etc), fail immediately
                logger.error(f"Non-retryable error: {e}")
                raise
        
        # Should never reach here, but just in case
        raise ValueError(f"OpenAI analysis failed: {last_error}")
    
    @staticmethod
    def _analyse_with_chunking(context: str, level: SummaryLevel, style: SummaryStyle, external_session_id: Optional[str] = None) -> Dict:
        """
        Process long transcripts using chunked analysis.
        Splits transcript into chunks, processes each, then merges results.
        Emits WebSocket progress events for real-time UI updates.
        
        Args:
            context: Full meeting transcript (>10k chars)
            level: Summary detail level
            style: Summary style type
            external_session_id: Optional session ID for WebSocket progress broadcasting
            
        Returns:
            Merged analysis results from all chunks
        """
        import time
        
        # Import socketio for progress broadcasting
        try:
            from app import socketio
            can_broadcast = socketio is not None and external_session_id is not None
            if not can_broadcast:
                logger.debug(f"[Chunked Analysis] Progress broadcasting disabled (socketio={socketio is not None}, session_id={external_session_id})")
        except ImportError:
            can_broadcast = False
            socketio = None
            logger.debug("[Chunked Analysis] Progress broadcasting disabled (socketio import failed)")
        
        # Helper to emit progress events
        def emit_progress(current_chunk: int, total: int, status: str = 'processing', message: str = None):
            if not can_broadcast:
                return
            try:
                progress_pct = int((current_chunk / total) * 100) if total > 0 else 0
                socketio.emit('insights_progress', {
                    'session_id': external_session_id,
                    'current_chunk': current_chunk,
                    'total_chunks': total,
                    'progress_percent': progress_pct,
                    'status': status,
                    'message': message or f'Processing chunk {current_chunk} of {total}...'
                })
                logger.debug(f"[Progress] Emitted insights_progress: {progress_pct}% ({current_chunk}/{total})")
            except Exception as e:
                logger.warning(f"[Progress] Failed to emit progress event: {e}")
        
        # Split transcript into chunks
        chunks = AnalysisService._chunk_transcript(context)
        total_chunks = len(chunks)
        
        logger.info(f"[Chunked Analysis] Processing {total_chunks} chunks for {len(context)} char transcript")
        
        # Emit initial progress event
        emit_progress(0, total_chunks, 'started', f'Analyzing long transcript ({total_chunks} sections)...')
        
        chunk_results = []
        failed_chunks = []
        
        for chunk in chunks:
            chunk_idx = chunk['chunk_index']
            chunk_text = chunk['text']
            
            logger.info(f"[Chunk {chunk_idx + 1}/{total_chunks}] Processing {len(chunk_text)} chars...")
            
            # Emit progress for this chunk
            emit_progress(chunk_idx + 1, total_chunks, 'processing', f'Analyzing section {chunk_idx + 1} of {total_chunks}...')
            
            # Add chunk context to the prompt
            chunk_context = f"[CHUNK {chunk_idx + 1} OF {total_chunks}]\n{chunk_text}"
            
            # Retry configuration for each chunk
            MAX_RETRIES = 3
            BACKOFF_DELAYS = [0, 2, 5]
            
            chunk_success = False
            last_error = None
            
            for attempt in range(MAX_RETRIES):
                try:
                    if attempt > 0:
                        delay = BACKOFF_DELAYS[attempt]
                        logger.info(f"[Chunk {chunk_idx + 1}] Retry {attempt}, waiting {delay}s...")
                        time.sleep(delay)
                    
                    result = AnalysisService._perform_openai_analysis(chunk_context, level, style, attempt)
                    result['_chunk_index'] = chunk_idx
                    chunk_results.append(result)
                    chunk_success = True
                    
                    logger.info(f"[Chunk {chunk_idx + 1}/{total_chunks}] ✓ Processed successfully")
                    break
                    
                except (json.JSONDecodeError, ValueError) as e:
                    last_error = e
                    logger.warning(f"[Chunk {chunk_idx + 1}] Attempt {attempt + 1} failed: {e}")
                    continue
                    
                except Exception as e:
                    last_error = e
                    logger.error(f"[Chunk {chunk_idx + 1}] Non-retryable error: {e}")
                    break
            
            if not chunk_success:
                failed_chunks.append({
                    'chunk_index': chunk_idx,
                    'error': str(last_error)
                })
                logger.error(f"[Chunk {chunk_idx + 1}/{total_chunks}] ✗ Failed after all retries: {last_error}")
        
        # Log summary
        success_count = len(chunk_results)
        fail_count = len(failed_chunks)
        logger.info(f"[Chunked Analysis] Completed: {success_count}/{total_chunks} chunks succeeded, {fail_count} failed")
        
        if not chunk_results:
            emit_progress(total_chunks, total_chunks, 'failed', 'Analysis failed - all sections had errors')
            raise ValueError(f"All {total_chunks} chunks failed to process")
        
        # Emit merging progress
        emit_progress(total_chunks, total_chunks, 'merging', 'Combining insights from all sections...')
        
        # Merge results from all successful chunks
        merged_result = AnalysisService._merge_insights(chunk_results, level, style)
        
        # Add chunking metadata
        merged_result['_chunked_processing'] = {
            'total_chunks': total_chunks,
            'successful_chunks': success_count,
            'failed_chunks': failed_chunks,
            'original_length': len(context)
        }
        
        # Emit completion progress
        emit_progress(total_chunks, total_chunks, 'completed', 'Analysis complete!')
        
        return merged_result
    
    @staticmethod
    def _perform_openai_analysis(context: str, level: SummaryLevel, style: SummaryStyle, attempt: int = 0) -> Dict:
        """
        Perform a single OpenAI analysis attempt.
        
        Args:
            context: Meeting transcript context
            level: Summary detail level
            style: Summary style type
            attempt: Current retry attempt number (0-indexed)
            
        Returns:
            Analysis results dictionary
        """
        # Initialize variables before try block to avoid unbound errors
        result_text = None
        client = None
        prompt = ""
        expected_keys: List[str] = []
        
        try:
            from openai import OpenAI
            
            import os
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                logger.error("OpenAI API key not found - CANNOT GENERATE INSIGHTS")
                raise ValueError("OpenAI API key not configured")
            
            client = OpenAI(api_key=api_key)
            
            # Select appropriate prompt template based on level and style
            prompt_key = AnalysisService._get_prompt_key(level, style)
            prompt_template = AnalysisService.PROMPT_TEMPLATES.get(prompt_key, AnalysisService.PROMPT_TEMPLATES["standard_executive"])
            prompt = prompt_template.format(transcript=context)
            
            # Get expected keys for this level/style combination
            expected_keys = AnalysisService._get_expected_keys(level, style)
            
            # Use unified AI model manager with GPT-4.1 fallback chain
            from services.ai_model_manager import AIModelManager
            
            def make_api_call(model: str):
                """API call wrapper for model manager."""
                return client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a professional meeting analyst. Respond with valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2  # Lower temperature for consistency and reduced hallucination
                )
            
            # Call with intelligent fallback and retry
            result_obj = AIModelManager.call_with_fallback(
                make_api_call,
                operation_name="insights generation"
            )
            
            if not result_obj.success:
                raise Exception(f"All AI models failed after {len(result_obj.attempts)} attempts")
            
            response = result_obj.response
            
            # Track degradation metadata for orchestrator
            degradation_metadata = {}
            if result_obj.degraded:
                logger.warning(f"⚠️ Insights generation degraded: {result_obj.degradation_reason}")
                degradation_metadata = {
                    'model_degraded': True,
                    'model_used': result_obj.model_used,
                    'degradation_reason': result_obj.degradation_reason
                }
            else:
                degradation_metadata = {
                    'model_degraded': False,
                    'model_used': result_obj.model_used
                }
            
            result_text = response.choices[0].message.content
            if result_text is None:
                raise ValueError("OpenAI returned empty response")
            
            # Log the FULL raw response for debugging
            logger.debug(f"[OpenAI Raw Response] Length: {len(result_text)} chars")
            logger.debug(f"[OpenAI Raw Response] FULL CONTENT:\n{result_text}")
            
            # Robust JSON extraction: handle markdown, whitespace, extra text
            cleaned_json = AnalysisService._extract_json_from_response(result_text)
            logger.debug(f"[JSON Extraction] Cleaned JSON: {cleaned_json[:500]}...")
            
            result = json.loads(cleaned_json)
            
            # Log what the AI extracted (before validation)
            action_count_raw = len(result.get('actions', []))
            decision_count_raw = len(result.get('decisions', []))
            risk_count_raw = len(result.get('risks', []))
            logger.info(f"[AI Extraction RAW] Actions: {action_count_raw}, Decisions: {decision_count_raw}, Risks: {risk_count_raw}")
            
            if action_count_raw > 0:
                logger.debug(f"[AI Extraction RAW] Actions before validation: {result.get('actions')}")
            
            # CRITICAL: Validate extracted actions against transcript to prevent hallucination
            if result.get('actions'):
                logger.info(f"[Validation] Validating {len(result['actions'])} extracted actions against transcript...")
                validated_actions = text_matcher.validate_task_list(result['actions'], context)
                
                # Replace with validated actions only
                original_count = len(result['actions'])
                result['actions'] = validated_actions
                validated_count = len(validated_actions)
                
                logger.info(f"[Validation] Actions: {validated_count}/{original_count} passed validation")
                
                if validated_count < original_count:
                    rejected_count = original_count - validated_count
                    logger.warning(f"[Validation] ⚠️ REJECTED {rejected_count} hallucinated tasks that had no evidence in transcript")
            
            # Validate decisions (if present)
            if result.get('decisions'):
                logger.info(f"[Validation] Validating {len(result['decisions'])} extracted decisions...")
                validated_decisions = []
                for decision in result['decisions']:
                    decision_text = decision.get('text', '')
                    if decision_text:
                        validation = text_matcher.validate_extraction(decision_text, context, 'decision')
                        if validation['is_valid']:
                            decision['validation'] = {
                                'confidence_score': validation['confidence_score'],
                                'evidence_quote': validation['evidence_quote']
                            }
                            validated_decisions.append(decision)
                        else:
                            logger.warning(f"[Validation] ❌ Rejected decision: {decision_text[:60]}...")
                
                original_count = len(result['decisions'])
                result['decisions'] = validated_decisions
                logger.info(f"[Validation] Decisions: {len(validated_decisions)}/{original_count} passed validation")
            
            # Validate risks (if present)
            if result.get('risks'):
                logger.info(f"[Validation] Validating {len(result['risks'])} extracted risks...")
                validated_risks = []
                for risk in result['risks']:
                    risk_text = risk.get('text', '')
                    if risk_text:
                        validation = text_matcher.validate_extraction(risk_text, context, 'risk')
                        if validation['is_valid']:
                            risk['validation'] = {
                                'confidence_score': validation['confidence_score'],
                                'evidence_quote': validation['evidence_quote']
                            }
                            validated_risks.append(risk)
                        else:
                            logger.warning(f"[Validation] ❌ Rejected risk: {risk_text[:60]}...")
                
                original_count = len(result['risks'])
                result['risks'] = validated_risks
                logger.info(f"[Validation] Risks: {len(validated_risks)}/{original_count} passed validation")
            
            # Log final validated counts
            action_count = len(result.get('actions', []))
            decision_count = len(result.get('decisions', []))
            risk_count = len(result.get('risks', []))
            logger.info(f"[AI Extraction FINAL] Actions: {action_count}, Decisions: {decision_count}, Risks: {risk_count} (after validation)")
            
            # Validate required keys based on level/style
            missing_keys = [key for key in expected_keys if key not in result]
            if missing_keys:
                logger.warning(f"Missing expected keys for {level.value} {style.value}: {missing_keys}")
                # Don't fail for missing keys, just log the warning
            
            # Include degradation metadata in result
            result['_metadata'] = degradation_metadata
            
            return result
            
        except json.JSONDecodeError as e:
            # Log detailed JSON parsing error
            result_text_snippet = result_text[max(0, e.pos-50):e.pos+50] if result_text else 'N/A'
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"[OpenAI JSON Error] Failed to parse at position {e.pos}")
            logger.error(f"[OpenAI JSON Error] Problem text: {result_text_snippet}")
            # Re-raise to trigger retry at higher level
            raise
            
        except Exception as e:
            logger.error(f"OpenAI analysis failed: {e}")
            logger.error(f"[CRITICAL] OpenAI analysis failed - CANNOT GENERATE INSIGHTS WITHOUT VALID API RESPONSE")
            # Re-raise to trigger retry or fail
            raise
    
    @staticmethod
    def _extract_json_from_response(response_text: str) -> str:
        """
        Extract clean JSON from OpenAI response, handling:
        - Markdown code blocks (```json ... ```)
        - Extra whitespace/newlines
        - Text before/after JSON
        
        Args:
            response_text: Raw response from OpenAI
            
        Returns:
            Clean JSON string ready for parsing
        """
        if not response_text:
            raise ValueError("Empty response text")
        
        # Remove leading/trailing whitespace
        cleaned = response_text.strip()
        
        # Handle markdown code blocks (```json ... ``` or ``` ... ```)
        if cleaned.startswith('```'):
            # Extract content between code fences
            lines = cleaned.split('\n')
            # Skip first line (```json or ```)
            start_idx = 1
            # Find end fence
            end_idx = len(lines)
            for i in range(1, len(lines)):
                if lines[i].strip() == '```':
                    end_idx = i
                    break
            cleaned = '\n'.join(lines[start_idx:end_idx])
        
        # Strip again after removing code blocks
        cleaned = cleaned.strip()
        
        # Find JSON object boundaries
        # Look for first { and last }
        start_brace = cleaned.find('{')
        end_brace = cleaned.rfind('}')
        
        if start_brace == -1 or end_brace == -1:
            raise ValueError(f"No JSON object found in response: {cleaned[:200]}")
        
        # Extract just the JSON object
        json_str = cleaned[start_brace:end_brace+1]
        
        return json_str
    
    @staticmethod
    def _get_expected_keys(level: SummaryLevel, style: SummaryStyle) -> List[str]:
        """
        Get the expected JSON keys for a given level and style combination.
        
        Args:
            level: Summary detail level
            style: Summary style type
            
        Returns:
            List of expected JSON keys
        """
        if level == SummaryLevel.BRIEF:
            return ["brief_summary"]  # Brief always requires brief_summary
        elif level == SummaryLevel.DETAILED:
            return ["detailed_summary", "summary_md", "brief_summary", "actions", "decisions", "risks", 
                   "executive_insights", "technical_details", "action_plan"]
        else:  # STANDARD level
            return ["summary_md", "actions", "decisions", "risks"]
    
    @staticmethod
    def _get_prompt_key(level: SummaryLevel, style: SummaryStyle) -> str:
        """
        Get the appropriate prompt key based on level and style.
        
        Args:
            level: Summary detail level
            style: Summary style type
            
        Returns:
            Prompt template key
        """
        # Map level and style combinations to prompt keys
        if level == SummaryLevel.BRIEF:
            if style == SummaryStyle.ACTION:
                return "brief_action"
            elif style == SummaryStyle.NARRATIVE:
                return "brief_narrative"
            elif style == SummaryStyle.BULLET:
                return "brief_bullet"
            else:  # EXECUTIVE, TECHNICAL default to executive for brief
                return "brief_executive"
        elif level == SummaryLevel.DETAILED:
            return "detailed_comprehensive"
        else:  # STANDARD level
            if style == SummaryStyle.TECHNICAL:
                return "standard_technical"
            elif style == SummaryStyle.NARRATIVE:
                return "standard_narrative"
            elif style == SummaryStyle.BULLET:
                return "standard_bullet"
            else:  # EXECUTIVE, ACTION default to executive for standard
                return "standard_executive"
    
    @staticmethod
    def _persist_summary(session_id: int, summary_data: Dict, engine: str, level: SummaryLevel, style: SummaryStyle) -> Summary:
        """
        Persist analysis results to database with level and style information.
        
        Args:
            session_id: ID of the session
            summary_data: Analysis results
            engine: Analysis engine used
            level: Summary detail level
            style: Summary style type
            
        Returns:
            Persisted Summary object
        """
        # Create new summary (replace existing if any for one-to-one relationship)
        from sqlalchemy import select
        stmt = select(Summary).filter(Summary.session_id == session_id)
        existing_summary = db.session.execute(stmt).scalar_one_or_none()
        if existing_summary:
            db.session.delete(existing_summary)
            db.session.flush()  # Ensure deletion is processed
        
        summary = Summary(  # type: ignore[call-arg]
            session_id=session_id,
            level=level,
            style=style,
            summary_md=summary_data.get('summary_md'),
            brief_summary=summary_data.get('brief_summary'),
            detailed_summary=summary_data.get('detailed_summary'),
            actions=summary_data.get('actions', []),
            decisions=summary_data.get('decisions', []),
            risks=summary_data.get('risks', []),
            executive_insights=summary_data.get('executive_insights', []),
            technical_details=summary_data.get('technical_details', []),
            action_plan=summary_data.get('action_plan', []),
            engine=engine,
            created_at=datetime.utcnow()
        )
        
        db.session.add(summary)
        db.session.commit()
        
        return summary


# Validate prompt templates at module import time to catch errors early
try:
    _validation_results = AnalysisService.validate_prompt_templates()
    if not all(_validation_results.values()):
        logger.warning("⚠️ Some prompt templates failed validation - check logs for details")
except Exception as e:
    logger.error(f"Failed to validate prompt templates at import: {e}")