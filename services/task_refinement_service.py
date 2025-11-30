"""
TaskRefinementService - Semantic transformation of raw task extractions into professional action items

This service uses GPT-4o-mini to transform conversational task fragments into
crisp, executive-ready action items with proper grammar, punctuation, and professional phrasing.

Transformation Examples:
- "I will take from here is then check the replit agent" → "Check Replit agent test progress."
- "to check the post-transcription pipeline to make sure that all the tabs are relevantly and correctly" → "Verify post-transcription pipeline tab accuracy."
- "go ahead with these two actions for now" → "Execute two pending action items."
"""

import logging
import os
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RefinementResult:
    """Result of task refinement with metadata"""
    success: bool
    refined_text: str
    original_text: str
    transformation_applied: bool
    confidence: float
    error: Optional[str] = None


class TaskRefinementService:
    """
    Service for refining AI-extracted tasks into professional, executive-ready action items.
    Uses GPT-4o-mini for intelligent semantic transformation.
    """
    
    # Prompt template for task refinement
    REFINEMENT_PROMPT = """You are a professional executive assistant. Transform this raw task fragment into a crisp, professional action item.

CRITICAL RULES:
1. **Action Verb Start**: Begin with a strong action verb (Review, Update, Check, Schedule, Send, Create, Analyze, etc.)
2. **Grammar**: Perfect grammar, proper capitalization, end with period
3. **Remove First-Person**: NEVER use "I", "I'll", "I'm", "we", "we'll", "let me", "let's" - convert to imperative form
4. **Remove Fillers**: Delete conversational words ("just", "quickly", "probably", "basically", "kind of")
5. **Complete Sentences**: Ensure sentence is complete and grammatically sound, not cut off mid-thought
6. **Preserve Details**: Keep important context, deadlines, and specifics
7. **Professional Tone**: Executive-ready, third-person imperative language
8. **Concise**: 3-12 words ideal, maximum 15 words

TRANSFORMATION EXAMPLES:

Raw: "I will take from here is then check the replit agent"
Refined: "Check Replit agent functionality."

Raw: "I need to check the post-transcription pipeline to make sure that all the tabs are relevantly and correctly"
Refined: "Verify post-transcription pipeline displays all tabs correctly."

Raw: "I think we should probably update the budget proposal sometime this week"
Refined: "Update budget proposal by end of week."

Raw: "go ahead with these two actions for now"
Refined: "Execute two pending action items."

Raw: "I will go ahead and send the report to Sarah"
Refined: "Send report to Sarah."

Raw: "we need to quickly fix the login bug before launch"
Refined: "Fix login bug before launch."

Raw: "let me schedule a meeting with the design team"
Refined: "Schedule meeting with design team."

Raw: "I'm going to review the code changes tomorrow"
Refined: "Review code changes tomorrow."

Now refine this task (remember: NO first-person pronouns, start with action verb):
Raw: "{raw_task}"
Refined:"""

    def __init__(self):
        """Initialize the refinement service"""
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            logger.warning("OpenAI API key not found - task refinement will use fallback mode")
    
    def refine_task(self, raw_task: str, context: Optional[Dict] = None) -> RefinementResult:
        """
        Refine a raw task extraction into a professional action item.
        
        Args:
            raw_task: Raw task text from AI extraction
            context: Optional context dict with evidence_quote, speaker, etc.
            
        Returns:
            RefinementResult with refined text and metadata
        """
        if not raw_task or not raw_task.strip():
            return RefinementResult(
                success=False,
                refined_text="",
                original_text=raw_task,
                transformation_applied=False,
                confidence=0.0,
                error="Empty task text"
            )
        
        # Check if task is already well-formatted (avoid unnecessary API calls)
        if self._is_already_refined(raw_task):
            logger.debug(f"Task already well-formatted: {raw_task[:50]}...")
            return RefinementResult(
                success=True,
                refined_text=raw_task,
                original_text=raw_task,
                transformation_applied=False,
                confidence=0.95
            )
        
        # Check for feature flag
        enable_refinement = os.environ.get('ENABLE_TASK_REFINEMENT', 'true').lower() == 'true'
        if not enable_refinement:
            logger.debug("Task refinement disabled via feature flag")
            return RefinementResult(
                success=True,
                refined_text=self._apply_basic_formatting(raw_task),
                original_text=raw_task,
                transformation_applied=False,
                confidence=0.7
            )
        
        # Try LLM-based refinement
        if self.api_key:
            try:
                refined = self._refine_with_llm(raw_task, context)
                return RefinementResult(
                    success=True,
                    refined_text=refined,
                    original_text=raw_task,
                    transformation_applied=True,
                    confidence=0.85
                )
            except Exception as e:
                logger.warning(f"LLM refinement failed: {e}, falling back to rule-based")
                # Fall through to rule-based fallback
        
        # Fallback: Rule-based formatting
        refined = self._apply_basic_formatting(raw_task)
        return RefinementResult(
            success=True,
            refined_text=refined,
            original_text=raw_task,
            transformation_applied=True,
            confidence=0.6
        )
    
    def refine_batch(self, tasks: List[str], context: Optional[List[Dict]] = None) -> List[RefinementResult]:
        """
        Refine multiple tasks in batch (more efficient).
        
        Args:
            tasks: List of raw task texts
            context: Optional list of context dicts (same length as tasks)
            
        Returns:
            List of RefinementResult objects
        """
        if not context:
            context = [None] * len(tasks)
        
        results = []
        for task, ctx in zip(tasks, context):
            results.append(self.refine_task(task, ctx))
        
        return results
    
    def _is_already_refined(self, task: str) -> bool:
        """
        Check if task is already well-formatted and doesn't need refinement.
        
        Criteria:
        - Starts with capital letter
        - Ends with period
        - Starts with action verb
        - No conversational fillers
        - Appropriate length
        """
        task = task.strip()
        
        # Must start with capital letter
        if not task or not task[0].isupper():
            return False
        
        # Must end with period
        if not task.endswith('.'):
            return False
        
        # Check for conversational fillers
        conversational_prefixes = [
            'i will', 'i\'ll', 'we will', 'we\'ll', 'let me', 'let\'s',
            'i think', 'we should', 'to check', 'to update', 'going to'
        ]
        task_lower = task.lower()
        if any(task_lower.startswith(prefix) for prefix in conversational_prefixes):
            return False
        
        # Check for action verbs at start
        action_verbs = [
            'review', 'update', 'check', 'verify', 'schedule', 'prepare', 'send',
            'create', 'build', 'implement', 'analyze', 'research', 'test', 'deploy',
            'fix', 'resolve', 'complete', 'finish', 'discuss', 'present', 'share'
        ]
        first_word = task.split()[0].lower()
        if first_word not in action_verbs:
            return False
        
        # Appropriate length (not too short or too long)
        word_count = len(task.split())
        if word_count < 2 or word_count > 15:
            return False
        
        return True
    
    def _apply_basic_formatting(self, task: str) -> str:
        """
        Apply basic rule-based formatting when LLM is unavailable.
        
        - Remove conversational prefixes
        - Capitalize first letter
        - Add period if missing
        - Fix basic grammar issues
        """
        task = task.strip()
        
        if not task:
            return ""
        
        # Remove common conversational prefixes
        prefixes_to_remove = [
            r'^i will\s+', r'^i\'ll\s+', r'^we will\s+', r'^we\'ll\s+',
            r'^let me\s+', r'^let\'s\s+', r'^i think\s+', r'^we should\s+',
            r'^to\s+', r'^going to\s+', r'^i am\s+', r'^i\'m\s+'
        ]
        
        import re
        for prefix in prefixes_to_remove:
            task = re.sub(prefix, '', task, flags=re.IGNORECASE)
        
        # Remove "is then" pattern (common in broken sentences)
        task = re.sub(r'\s+is\s+then\s+', ' ', task, flags=re.IGNORECASE)
        
        # Fix "take an action to X" → "X"
        task = re.sub(r'^take an action to\s+', '', task, flags=re.IGNORECASE)
        
        # Capitalize first letter
        if task:
            task = task[0].upper() + task[1:]
        
        # Add period if missing
        if task and task[-1] not in '.!?':
            task += '.'
        
        # Fix double periods
        task = re.sub(r'\.+', '.', task)
        
        # Fix "relevantly and correctly" → "relevant and correct"
        task = task.replace('relevantly and correctly', 'relevant and correct')
        task = task.replace('relevantly', 'relevant')
        
        return task.strip()
    
    def _refine_with_llm(self, raw_task: str, context: Optional[Dict] = None) -> str:
        """
        Use GPT-4o-mini to semantically refine the task.
        
        Args:
            raw_task: Raw task text
            context: Optional context with evidence_quote, etc.
            
        Returns:
            Refined task text
        """
        from openai import OpenAI
        
        client = OpenAI(api_key=self.api_key)
        
        # Build prompt
        prompt = self.REFINEMENT_PROMPT.format(raw_task=raw_task)
        
        # Call GPT-4o-mini (fast and cheap for simple transformations)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional executive assistant. Transform task fragments into crisp action items. Respond with ONLY the refined task text, nothing else."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Low temperature for consistent formatting
            max_tokens=100  # Tasks should be concise
        )
        
        refined_text = response.choices[0].message.content.strip()
        
        # Validation: Ensure it's actually refined
        if not refined_text:
            raise ValueError("Empty response from LLM")
        
        # Remove any extra quotes or formatting
        refined_text = refined_text.strip('"\'')
        
        # Ensure it ends with period
        if refined_text and refined_text[-1] not in '.!?':
            refined_text += '.'
        
        logger.debug(f"LLM refinement: '{raw_task[:40]}...' → '{refined_text}'")
        
        return refined_text


# Singleton instance
_refinement_service = None

def get_task_refinement_service() -> TaskRefinementService:
    """Get singleton task refinement service instance"""
    global _refinement_service
    if _refinement_service is None:
        _refinement_service = TaskRefinementService()
    return _refinement_service
