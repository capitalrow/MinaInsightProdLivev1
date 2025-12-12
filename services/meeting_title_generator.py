"""
Meeting Title Generator Service
Generates meaningful, contextual meeting titles from transcript content using AI.
Fixes the "Live Transcription Session" placeholder issue.
"""

import logging
import re
from typing import Optional
from services.ai_model_manager import AIModelManager
from services.openai_client_manager import get_openai_client

logger = logging.getLogger(__name__)


class MeetingTitleGenerator:
    """
    Generates contextual meeting titles from transcript content.
    Uses AI to analyze content and produce meaningful names.
    """
    
    PLACEHOLDER_TITLES = [
        "live transcription session",
        "live transcription",
        "untitled meeting",
        "new meeting",
        ""
    ]
    
    def __init__(self):
        pass
    
    def is_placeholder_title(self, title: str) -> bool:
        """Check if a title is a generic placeholder that should be replaced."""
        if not title:
            return True
        return title.strip().lower() in self.PLACEHOLDER_TITLES
    
    async def generate_title(self, transcript: str, max_length: int = 60) -> Optional[str]:
        """
        Generate a meaningful meeting title from transcript content.
        
        Args:
            transcript: Full or partial meeting transcript text
            max_length: Maximum length of generated title
            
        Returns:
            Generated title or None if generation fails
        """
        if not transcript or len(transcript.strip()) < 20:
            logger.warning("Transcript too short to generate meaningful title")
            return None
        
        transcript_sample = transcript[:3000]
        
        system_prompt = """You are a meeting title generator. Your job is to create concise, meaningful meeting titles that capture the main topic or purpose.

RULES:
1. Title should be 3-8 words
2. Use title case (capitalize main words)
3. Focus on the primary topic discussed
4. Be specific, not generic
5. Do NOT include dates, times, or "Meeting" unless essential
6. Return ONLY the title, no quotes or explanation

GOOD EXAMPLES:
- "Q4 Product Roadmap Planning"
- "Customer Support Process Review"
- "API Redesign Discussion"
- "Marketing Campaign Strategy"
- "Sprint Retrospective and Planning"

BAD EXAMPLES:
- "Meeting Notes" (too generic)
- "Live Transcription Session" (placeholder)
- "Discussion About Various Topics" (too vague)
- "January 15 2024 Call" (date-based)"""

        user_prompt = f"""Based on this meeting transcript, generate a concise, descriptive title:

{transcript_sample}

Respond with ONLY the meeting title (3-8 words, title case):"""

        async def make_api_call(model: str):
            client = get_openai_client()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=50,
                temperature=0.3
            )
            return response
        
        try:
            result = await AIModelManager.call_with_fallback_async(
                api_call=make_api_call,
                operation_name="meeting title generation"
            )
            
            if result.success and result.response:
                content = result.response.choices[0].message.content
                if content:
                    title = content.strip().strip('"\'')
                    title = re.sub(r'^(Title:|Meeting:|Topic:)\s*', '', title, flags=re.IGNORECASE)
                    
                    if len(title) > max_length:
                        title = title[:max_length-3].rsplit(' ', 1)[0] + "..."
                    
                    if len(title) < 5 or self.is_placeholder_title(title):
                        logger.warning(f"AI generated invalid title: {title}")
                        return self._fallback_title_extraction(transcript)
                    
                    logger.info(f"✅ Generated meeting title: {title}")
                    return title
                
        except Exception as e:
            logger.error(f"AI title generation failed: {e}")
            return self._fallback_title_extraction(transcript)
        
        return None
    
    def _fallback_title_extraction(self, transcript: str) -> Optional[str]:
        """
        Rule-based fallback to extract a title from transcript keywords.
        Used when AI fails or is unavailable.
        """
        first_segment = transcript[:500].lower()
        
        topic_patterns = [
            r"(?:let's discuss|discussing|talk about|meeting about|here to discuss)\s+(.{10,50})",
            r"(?:agenda|topic|focus|purpose)(?:\s+is|\s+today)?\s*:?\s*(.{10,50})",
            r"(?:working on|reviewing|planning|updates on)\s+(.{10,40})",
        ]
        
        for pattern in topic_patterns:
            match = re.search(pattern, first_segment, re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
                topic = re.sub(r'[.!?,].*$', '', topic)
                title = topic.title()[:50]
                logger.info(f"Fallback title extracted: {title}")
                return title
        
        words = re.findall(r'\b[A-Za-z]{4,}\b', transcript[:1000])
        if words:
            from collections import Counter
            common = Counter(words).most_common(3)
            if common:
                title_words = [word.capitalize() for word, _ in common if word.lower() not in 
                              ['that', 'this', 'with', 'have', 'will', 'they', 'them', 'their', 
                               'what', 'when', 'where', 'which', 'about', 'from', 'just', 'like',
                               'were', 'been', 'would', 'could', 'should', 'going', 'being']]
                if title_words:
                    return f"{' '.join(title_words[:2])} Discussion"
        
        return None


_generator_instance = None

def get_title_generator() -> MeetingTitleGenerator:
    """Get singleton instance of MeetingTitleGenerator."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = MeetingTitleGenerator()
    return _generator_instance


async def generate_meeting_title(transcript: str) -> Optional[str]:
    """Convenience function to generate a meeting title."""
    generator = get_title_generator()
    return await generator.generate_title(transcript)
