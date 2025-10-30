"""
CognitiveSynchronizer Service - CROWN⁴.5 Self-Improving NLP

Learns from user corrections to task suggestions and improves extraction accuracy over time.

Core Features:
- Tracks user edits to AI-proposed tasks
- Analyzes rejection patterns
- Refines extraction prompts based on feedback
- Adapts confidence scoring
- Maintains user-specific preference profiles
"""

import logging
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, asdict
from sqlalchemy import select, func
from models import db, Task, User

logger = logging.getLogger(__name__)


@dataclass
class UserFeedback:
    """User correction or feedback on AI extraction"""
    task_id: int
    user_id: int
    action: str  # 'edited', 'rejected', 'accepted_unchanged'
    original_title: str
    corrected_title: Optional[str]
    original_priority: str
    corrected_priority: Optional[str]
    original_category: Optional[str]
    corrected_category: Optional[str]
    context: Dict[str, Any]
    timestamp: datetime
    correction_type: List[str]  # ['title', 'priority', 'category', 'assignee']


@dataclass
class LearningProfile:
    """User-specific learning profile"""
    user_id: int
    total_suggestions: int = 0
    acceptance_rate: float = 0.0
    common_corrections: Dict[str, int] = None
    priority_preferences: Dict[str, float] = None
    category_mapping: Dict[str, str] = None
    confidence_adjustment: float = 0.0
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.common_corrections is None:
            self.common_corrections = {}
        if self.priority_preferences is None:
            self.priority_preferences = {}
        if self.category_mapping is None:
            self.category_mapping = {}
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()


class CognitiveSynchronizer:
    """
    Self-improving NLP system that learns from user task corrections.
    
    Capabilities:
    1. Capture user edits to AI-proposed tasks
    2. Analyze patterns in corrections
    3. Adjust extraction confidence based on success rate
    4. Refine prompt templates with learned preferences
    5. Build user-specific extraction profiles
    """
    
    def __init__(self):
        """Initialize CognitiveSynchronizer"""
        self.feedback_buffer = []
        self.learning_profiles = {}  # user_id -> LearningProfile
        self.correction_patterns = defaultdict(int)
        self.min_feedback_threshold = 5  # Minimum feedback before adapting
        
        logger.info("✅ CognitiveSynchronizer initialized - Ready to learn from user feedback")
    
    def capture_task_acceptance(self, task_id: int, user_id: int, 
                               was_edited: bool = False, 
                               changes: Optional[Dict[str, Any]] = None) -> None:
        """
        Capture user acceptance/editing of AI-proposed task.
        
        Args:
            task_id: Task ID
            user_id: User who accepted/edited
            was_edited: Whether user modified the suggestion
            changes: Dict of field changes {field: {'old': x, 'new': y}}
        """
        try:
            task = db.session.get(Task, task_id)
            if not task or not task.extracted_by_ai:
                return
            
            action = 'edited' if was_edited else 'accepted_unchanged'
            correction_types = []
            
            # Extract original values from extraction_context
            context = task.extraction_context or {}
            original_title = context.get('original_title', task.title)
            original_priority = context.get('original_priority', task.priority)
            original_category = context.get('original_category', task.category)
            
            corrected_title = None
            corrected_priority = None
            corrected_category = None
            
            if changes:
                if 'title' in changes:
                    correction_types.append('title')
                    corrected_title = changes['title']['new']
                if 'priority' in changes:
                    correction_types.append('priority')
                    corrected_priority = changes['priority']['new']
                if 'category' in changes:
                    correction_types.append('category')
                    corrected_category = changes['category']['new']
            
            feedback = UserFeedback(
                task_id=task_id,
                user_id=user_id,
                action=action,
                original_title=original_title,
                corrected_title=corrected_title,
                original_priority=original_priority,
                corrected_priority=corrected_priority,
                original_category=original_category,
                corrected_category=corrected_category,
                context=context,
                timestamp=datetime.utcnow(),
                correction_type=correction_types
            )
            
            self.feedback_buffer.append(feedback)
            self._update_learning_profile(user_id, feedback)
            
            logger.debug(f"Captured feedback: task={task_id}, action={action}, corrections={correction_types}")
            
        except Exception as e:
            logger.error(f"Failed to capture task acceptance: {e}")
    
    def capture_task_rejection(self, task_id: int, user_id: int, 
                              reason: Optional[str] = None) -> None:
        """
        Capture user rejection of AI-proposed task.
        
        Args:
            task_id: Task ID
            user_id: User who rejected
            reason: Optional rejection reason
        """
        try:
            task = db.session.get(Task, task_id)
            if not task or not task.extracted_by_ai:
                return
            
            context = task.extraction_context or {}
            context['rejection_reason'] = reason
            
            feedback = UserFeedback(
                task_id=task_id,
                user_id=user_id,
                action='rejected',
                original_title=task.title,
                corrected_title=None,
                original_priority=task.priority,
                corrected_priority=None,
                original_category=task.category,
                corrected_category=None,
                context=context,
                timestamp=datetime.utcnow(),
                correction_type=['full_rejection']
            )
            
            self.feedback_buffer.append(feedback)
            self._update_learning_profile(user_id, feedback)
            
            logger.debug(f"Captured rejection: task={task_id}, reason={reason}")
            
        except Exception as e:
            logger.error(f"Failed to capture task rejection: {e}")
    
    def _update_learning_profile(self, user_id: int, feedback: UserFeedback) -> None:
        """Update user's learning profile with new feedback"""
        if user_id not in self.learning_profiles:
            self.learning_profiles[user_id] = LearningProfile(user_id=user_id)
        
        profile = self.learning_profiles[user_id]
        profile.total_suggestions += 1
        
        # Update acceptance rate
        if feedback.action == 'accepted_unchanged':
            accepted = 1
        elif feedback.action == 'edited':
            accepted = 0.5  # Partial credit for edited acceptances
        else:
            accepted = 0
        
        profile.acceptance_rate = (
            (profile.acceptance_rate * (profile.total_suggestions - 1) + accepted) 
            / profile.total_suggestions
        )
        
        # Track priority corrections
        if feedback.corrected_priority and feedback.corrected_priority != feedback.original_priority:
            key = f"{feedback.original_priority} -> {feedback.corrected_priority}"
            profile.common_corrections[key] = profile.common_corrections.get(key, 0) + 1
            profile.priority_preferences[feedback.corrected_priority] = (
                profile.priority_preferences.get(feedback.corrected_priority, 0) + 1
            )
        
        # Track category corrections
        if feedback.corrected_category and feedback.corrected_category != feedback.original_category:
            profile.category_mapping[feedback.original_category or 'unknown'] = feedback.corrected_category
        
        # Adjust confidence based on acceptance rate
        if profile.total_suggestions >= self.min_feedback_threshold:
            # Range: -0.2 to +0.2 based on acceptance rate
            profile.confidence_adjustment = (profile.acceptance_rate - 0.5) * 0.4
        
        profile.last_updated = datetime.utcnow()
        
        logger.debug(f"Updated profile for user {user_id}: acceptance={profile.acceptance_rate:.2f}, "
                    f"confidence_adj={profile.confidence_adjustment:.2f}")
    
    def get_adjusted_confidence(self, user_id: int, base_confidence: float) -> float:
        """
        Get confidence score adjusted for user-specific learning.
        
        Args:
            user_id: User ID
            base_confidence: Base confidence from extraction
            
        Returns:
            Adjusted confidence score (0.0-1.0)
        """
        if user_id not in self.learning_profiles:
            return base_confidence
        
        profile = self.learning_profiles[user_id]
        
        if profile.total_suggestions < self.min_feedback_threshold:
            return base_confidence
        
        # Adjust confidence based on user's historical acceptance rate
        adjusted = base_confidence + profile.confidence_adjustment
        return max(0.0, min(1.0, adjusted))
    
    def get_priority_suggestion(self, user_id: int, base_priority: str, 
                              task_context: Dict[str, Any]) -> str:
        """
        Get priority suggestion adjusted for user preferences.
        
        Args:
            user_id: User ID
            base_priority: Base priority from extraction
            task_context: Task context for analysis
            
        Returns:
            Adjusted priority suggestion
        """
        if user_id not in self.learning_profiles:
            return base_priority
        
        profile = self.learning_profiles[user_id]
        
        # Check if user frequently corrects this priority
        correction_key = f"{base_priority} -> "
        common_correction = None
        max_count = 0
        
        for key, count in profile.common_corrections.items():
            if key.startswith(correction_key) and count > max_count:
                max_count = count
                common_correction = key.split(' -> ')[1]
        
        # Use common correction if it appears frequently enough
        if common_correction and max_count >= 3:
            logger.debug(f"Adjusted priority from {base_priority} to {common_correction} "
                        f"based on user preference (count={max_count})")
            return common_correction
        
        return base_priority
    
    def get_category_suggestion(self, user_id: int, base_category: Optional[str], 
                               task_context: Dict[str, Any]) -> Optional[str]:
        """
        Get category suggestion adjusted for user mapping.
        
        Args:
            user_id: User ID
            base_category: Base category from extraction
            task_context: Task context for analysis
            
        Returns:
            Adjusted category suggestion
        """
        if user_id not in self.learning_profiles:
            return base_category
        
        profile = self.learning_profiles[user_id]
        
        # Check for learned category mapping
        if base_category and base_category in profile.category_mapping:
            mapped_category = profile.category_mapping[base_category]
            logger.debug(f"Mapped category from {base_category} to {mapped_category}")
            return mapped_category
        
        return base_category
    
    def get_learning_insights(self, user_id: int) -> Dict[str, Any]:
        """
        Get learning insights for user (for telemetry/analytics).
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with learning metrics
        """
        if user_id not in self.learning_profiles:
            return {
                'has_profile': False,
                'total_suggestions': 0,
                'acceptance_rate': 0.0
            }
        
        profile = self.learning_profiles[user_id]
        
        return {
            'has_profile': True,
            'total_suggestions': profile.total_suggestions,
            'acceptance_rate': profile.acceptance_rate,
            'confidence_adjustment': profile.confidence_adjustment,
            'common_corrections': dict(list(profile.common_corrections.items())[:5]),
            'top_priority': max(profile.priority_preferences.items(), 
                              key=lambda x: x[1])[0] if profile.priority_preferences else None,
            'last_updated': profile.last_updated.isoformat() if profile.last_updated else None
        }
    
    def refine_extraction_prompt(self, user_id: int, base_prompt: str) -> str:
        """
        Refine extraction prompt with user-specific learned preferences.
        
        Args:
            user_id: User ID
            base_prompt: Base extraction prompt
            
        Returns:
            Refined prompt with user preferences
        """
        if user_id not in self.learning_profiles:
            return base_prompt
        
        profile = self.learning_profiles[user_id]
        
        if profile.total_suggestions < self.min_feedback_threshold:
            return base_prompt
        
        # Add user preference hints to prompt
        refinements = []
        
        if profile.priority_preferences:
            top_priority = max(profile.priority_preferences.items(), key=lambda x: x[1])[0]
            refinements.append(f"User typically prefers '{top_priority}' priority tasks.")
        
        if profile.category_mapping:
            category_examples = list(profile.category_mapping.items())[:3]
            mapping_str = ', '.join([f"'{k}' as '{v}'" for k, v in category_examples])
            refinements.append(f"User categorizes: {mapping_str}.")
        
        if refinements:
            refined_prompt = base_prompt + "\n\nUser Preferences:\n" + "\n".join(refinements)
            logger.debug(f"Refined prompt for user {user_id} with {len(refinements)} preferences")
            return refined_prompt
        
        return base_prompt
    
    def analyze_feedback_patterns(self) -> Dict[str, Any]:
        """
        Analyze global feedback patterns across all users.
        
        Returns:
            Dict with pattern analysis
        """
        if not self.feedback_buffer:
            return {'patterns': [], 'insights': 'Insufficient data'}
        
        # Analyze by action type
        action_counts = defaultdict(int)
        correction_counts = defaultdict(int)
        
        for feedback in self.feedback_buffer:
            action_counts[feedback.action] += 1
            for correction in feedback.correction_type:
                correction_counts[correction] += 1
        
        total = len(self.feedback_buffer)
        acceptance_rate = action_counts['accepted_unchanged'] / total if total > 0 else 0
        edit_rate = action_counts['edited'] / total if total > 0 else 0
        rejection_rate = action_counts['rejected'] / total if total > 0 else 0
        
        return {
            'total_feedback': total,
            'acceptance_rate': acceptance_rate,
            'edit_rate': edit_rate,
            'rejection_rate': rejection_rate,
            'common_corrections': dict(correction_counts),
            'insights': self._generate_insights(acceptance_rate, edit_rate, correction_counts)
        }
    
    def _generate_insights(self, acceptance_rate: float, edit_rate: float, 
                          corrections: Dict[str, int]) -> str:
        """Generate natural language insights from patterns"""
        insights = []
        
        if acceptance_rate > 0.7:
            insights.append("AI extraction is performing well.")
        elif acceptance_rate < 0.3:
            insights.append("AI extraction needs improvement.")
        
        if edit_rate > 0.5:
            insights.append("Users frequently edit suggestions.")
        
        if corrections:
            top_correction = max(corrections.items(), key=lambda x: x[1])
            insights.append(f"Most common correction: {top_correction[0]}")
        
        return " ".join(insights) if insights else "Gathering learning data..."
    
    def persist_profiles(self) -> None:
        """Persist learning profiles to database (for future enhancement)"""
        # TODO: Store profiles in database for persistence across restarts
        logger.debug(f"Profiles to persist: {len(self.learning_profiles)}")
    
    def load_profiles(self) -> None:
        """Load learning profiles from database (for future enhancement)"""
        # TODO: Load profiles from database
        logger.debug("Profile loading not yet implemented")


# Global instance
_cognitive_sync = None


def get_cognitive_synchronizer() -> CognitiveSynchronizer:
    """Get or create global CognitiveSynchronizer instance"""
    global _cognitive_sync
    if _cognitive_sync is None:
        _cognitive_sync = CognitiveSynchronizer()
    return _cognitive_sync
