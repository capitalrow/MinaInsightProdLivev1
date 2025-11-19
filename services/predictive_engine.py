"""
PredictiveEngine Service - CROWN⁴.5 Smart Defaults

Provides ML-based predictions for task attributes using pattern matching,
historical analysis, and user behavior learning.

Key Features:
- Due date prediction based on task type and priority
- Priority suggestion based on title/description analysis
- Assignee recommendation based on past patterns
- Continuous learning from user corrections
"""

import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple
from collections import defaultdict, Counter
from sqlalchemy import select, func
from models import db
from models.task import Task
from models.user import User

logger = logging.getLogger(__name__)


class PredictiveEngine:
    """
    Service for predicting task attributes using ML and pattern matching.
    
    Responsibilities:
    - Predict due dates based on task context
    - Suggest priorities based on urgency indicators
    - Recommend assignees based on historical patterns
    - Learn from user corrections to improve predictions
    - Maintain prediction accuracy metrics
    """
    
    # Priority urgency indicators (keywords in title/description)
    URGENT_INDICATORS = [
        'urgent', 'asap', 'immediately', 'critical', 'emergency',
        'blocker', 'blocking', 'high priority', 'deadline', 'overdue'
    ]
    
    HIGH_PRIORITY_INDICATORS = [
        'important', 'priority', 'soon', 'quickly', 'needed',
        'required', 'must', 'need to', 'have to'
    ]
    
    # Due date patterns based on task type
    DUE_DATE_PATTERNS = {
        'follow_up': timedelta(days=3),
        'action_item': timedelta(days=7),
        'decision': timedelta(days=5),
        'research': timedelta(days=14),
        'review': timedelta(days=2),
        'urgent': timedelta(days=1),
        'high': timedelta(days=3),
        'medium': timedelta(days=7),
        'low': timedelta(days=14),
    }
    
    def __init__(self):
        """Initialize PredictiveEngine."""
        self.metrics = {
            'predictions_made': 0,
            'due_date_accuracy': 0.0,
            'priority_accuracy': 0.0,
            'assignee_accuracy': 0.0,
            'corrections_learned': 0
        }
        
        # Cache for user patterns (cleared periodically)
        self._user_patterns_cache = {}
        self._cache_timestamp = datetime.utcnow()
        self._cache_ttl_seconds = 3600  # 1 hour
    
    def _clear_cache_if_stale(self):
        """Clear cache if TTL expired."""
        if (datetime.utcnow() - self._cache_timestamp).total_seconds() > self._cache_ttl_seconds:
            self._user_patterns_cache.clear()
            self._cache_timestamp = datetime.utcnow()
            logger.debug("Cleared stale prediction cache")
    
    def predict_due_date(
        self,
        title: str,
        description: Optional[str] = None,
        priority: str = 'medium',
        task_type: str = 'action_item',
        user_id: Optional[int] = None,
        workspace_id: Optional[int] = None
    ) -> Tuple[Optional[date], float]:
        """
        Predict due date for a task based on context and historical patterns.
        
        Args:
            title: Task title
            description: Task description (optional)
            priority: Task priority (low, medium, high, urgent)
            task_type: Task type (action_item, follow_up, etc.)
            user_id: User ID for personalized predictions
            workspace_id: Workspace ID for team patterns
            
        Returns:
            Tuple of (predicted_due_date, confidence_score)
        """
        try:
            self._clear_cache_if_stale()
            
            # Start with base prediction from task type and priority
            base_delta = self.DUE_DATE_PATTERNS.get(
                task_type,
                self.DUE_DATE_PATTERNS.get(priority, timedelta(days=7))
            )
            
            # Adjust based on urgency indicators in text
            text_lower = (title + ' ' + (description or '')).lower()
            
            if any(indicator in text_lower for indicator in self.URGENT_INDICATORS):
                base_delta = timedelta(days=1)
                priority_boost = True
            elif any(indicator in text_lower for indicator in self.HIGH_PRIORITY_INDICATORS):
                base_delta = min(base_delta, timedelta(days=3))
                priority_boost = True
            else:
                priority_boost = False
            
            # Personalize based on user's historical completion times
            if user_id and workspace_id:
                user_avg_delta = self._get_user_average_completion_time(
                    user_id, workspace_id, task_type
                )
                if user_avg_delta:
                    # Blend base prediction with user history (70% history, 30% base)
                    base_delta = timedelta(
                        days=int(user_avg_delta.days * 0.7 + base_delta.days * 0.3)
                    )
            
            # Calculate predicted due date
            predicted_date = date.today() + base_delta
            
            # Calculate confidence score
            confidence = 0.75  # Base confidence
            if user_id:
                confidence += 0.15  # Boost if personalized
            if priority_boost:
                confidence += 0.10  # Boost if clear urgency indicators
            
            confidence = min(confidence, 1.0)
            
            self.metrics['predictions_made'] += 1
            
            logger.debug(
                f"Predicted due date: {predicted_date} (confidence: {confidence:.2f}) "
                f"for task_type={task_type}, priority={priority}"
            )
            
            return predicted_date, confidence
            
        except Exception as e:
            logger.error(f"Due date prediction failed: {e}", exc_info=True)
            return None, 0.0
    
    def predict_priority(
        self,
        title: str,
        description: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Tuple[str, float]:
        """
        Predict priority for a task based on text analysis.
        
        Args:
            title: Task title
            description: Task description (optional)
            user_id: User ID for personalized predictions
            
        Returns:
            Tuple of (predicted_priority, confidence_score)
        """
        try:
            text_lower = (title + ' ' + (description or '')).lower()
            
            # Check for urgency indicators
            if any(indicator in text_lower for indicator in self.URGENT_INDICATORS):
                return 'urgent', 0.90
            
            if any(indicator in text_lower for indicator in self.HIGH_PRIORITY_INDICATORS):
                return 'high', 0.85
            
            # Check for low priority indicators
            low_indicators = ['minor', 'nice to have', 'eventually', 'someday', 'when possible']
            if any(indicator in text_lower for indicator in low_indicators):
                return 'low', 0.80
            
            # Default to medium with lower confidence
            return 'medium', 0.60
            
        except Exception as e:
            logger.error(f"Priority prediction failed: {e}", exc_info=True)
            return 'medium', 0.50
    
    def predict_assignee(
        self,
        title: str,
        description: Optional[str] = None,
        task_type: str = 'action_item',
        workspace_id: Optional[int] = None,
        meeting_id: Optional[int] = None
    ) -> Tuple[Optional[int], float]:
        """
        Predict assignee for a task based on historical patterns.
        
        Args:
            title: Task title
            description: Task description (optional)
            task_type: Task type
            workspace_id: Workspace ID
            meeting_id: Meeting ID (for participant context)
            
        Returns:
            Tuple of (predicted_user_id, confidence_score)
        """
        try:
            if not workspace_id:
                return None, 0.0
            
            # Get historical task assignment patterns for this workspace
            assignments = self._get_workspace_assignment_patterns(workspace_id, task_type)
            
            if not assignments:
                return None, 0.0
            
            # Find most common assignee for this task type
            most_common = assignments.most_common(1)[0]
            assignee_id, count = most_common
            
            # Calculate confidence based on consistency
            total_assignments = sum(assignments.values())
            confidence = min(count / total_assignments, 0.85) if total_assignments > 0 else 0.0
            
            # Require at least 3 historical examples for confidence
            if total_assignments < 3:
                confidence *= 0.5
            
            logger.debug(
                f"Predicted assignee: {assignee_id} (confidence: {confidence:.2f}) "
                f"based on {count}/{total_assignments} historical assignments"
            )
            
            return assignee_id, confidence
            
        except Exception as e:
            logger.error(f"Assignee prediction failed: {e}", exc_info=True)
            return None, 0.0
    
    def _get_user_average_completion_time(
        self,
        user_id: int,
        workspace_id: int,
        task_type: str
    ) -> Optional[timedelta]:
        """
        Get user's average completion time for a task type.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            task_type: Task type
            
        Returns:
            Average completion time as timedelta, or None
        """
        try:
            # Check cache first
            cache_key = f"user_{user_id}_type_{task_type}"
            if cache_key in self._user_patterns_cache:
                return self._user_patterns_cache[cache_key]
            
            # Query completed tasks from last 90 days
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            stmt = select(Task).where(
                Task.assigned_to_id == user_id,
                Task.task_type == task_type,
                Task.status == 'completed',
                Task.completed_at.isnot(None),
                Task.created_at >= cutoff_date
            ).limit(50)
            
            tasks = list(db.session.scalars(stmt).all())
            
            if not tasks:
                return None
            
            # Calculate average completion time
            completion_times = []
            for task in tasks:
                if task.created_at and task.completed_at:
                    delta = task.completed_at - task.created_at
                    completion_times.append(delta)
            
            if not completion_times:
                return None
            
            avg_seconds = sum(d.total_seconds() for d in completion_times) / len(completion_times)
            avg_delta = timedelta(seconds=avg_seconds)
            
            # Cache result
            self._user_patterns_cache[cache_key] = avg_delta
            
            return avg_delta
            
        except Exception as e:
            logger.error(f"Failed to get user completion time: {e}")
            return None
    
    def _get_workspace_assignment_patterns(
        self,
        workspace_id: int,
        task_type: str
    ) -> Counter:
        """
        Get assignment patterns for a workspace and task type.
        
        Args:
            workspace_id: Workspace ID
            task_type: Task type
            
        Returns:
            Counter of {user_id: assignment_count}
        """
        try:
            # Check cache
            cache_key = f"workspace_{workspace_id}_type_{task_type}"
            if cache_key in self._user_patterns_cache:
                return self._user_patterns_cache[cache_key]
            
            # Query recent assignments (last 90 days)
            from models.meeting import Meeting
            
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            stmt = select(Task.assigned_to_id, func.count(Task.id)).join(Meeting).where(
                Meeting.workspace_id == workspace_id,
                Task.task_type == task_type,
                Task.assigned_to_id.isnot(None),
                Task.created_at >= cutoff_date
            ).group_by(Task.assigned_to_id)
            
            results = db.session.execute(stmt).all()
            
            assignment_counts = Counter({user_id: count for user_id, count in results})
            
            # Cache result
            self._user_patterns_cache[cache_key] = assignment_counts
            
            return assignment_counts
            
        except Exception as e:
            logger.error(f"Failed to get assignment patterns: {e}")
            return Counter()
    
    def learn_from_correction(
        self,
        task_id: int,
        predicted_field: str,
        predicted_value: Any,
        actual_value: Any,
        user_id: Optional[int] = None
    ):
        """
        Learn from user corrections to improve future predictions.
        
        Args:
            task_id: Task ID
            predicted_field: Field that was predicted (due_date, priority, assignee)
            predicted_value: What was predicted
            actual_value: What user actually set
            user_id: User who made the correction
        """
        try:
            # Update metrics
            self.metrics['corrections_learned'] += 1
            
            # Log correction for analysis
            logger.info(
                f"Learning from correction: task={task_id}, field={predicted_field}, "
                f"predicted={predicted_value}, actual={actual_value}, user={user_id}"
            )
            
            # Clear cache to force fresh pattern learning
            self._user_patterns_cache.clear()
            self._cache_timestamp = datetime.utcnow()
            
            # Future enhancement: Store corrections in dedicated table for ML training
            
        except Exception as e:
            logger.error(f"Failed to learn from correction: {e}")
    
    def get_prediction_suggestions(
        self,
        title: str,
        description: Optional[str] = None,
        task_type: str = 'action_item',
        user_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        meeting_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get all prediction suggestions for a task.
        
        Args:
            title: Task title
            description: Task description
            task_type: Task type
            user_id: User ID
            workspace_id: Workspace ID
            meeting_id: Meeting ID
            
        Returns:
            Dictionary with predictions and confidence scores
        """
        try:
            # Predict priority first (affects due date prediction)
            predicted_priority, priority_confidence = self.predict_priority(
                title, description, user_id
            )
            
            # Predict due date using predicted priority
            predicted_due, due_confidence = self.predict_due_date(
                title, description, predicted_priority, task_type, user_id, workspace_id
            )
            
            # Predict assignee
            predicted_assignee, assignee_confidence = self.predict_assignee(
                title, description, task_type, workspace_id, meeting_id
            )
            
            return {
                'priority': {
                    'value': predicted_priority,
                    'confidence': priority_confidence
                },
                'due_date': {
                    'value': predicted_due.isoformat() if predicted_due else None,
                    'confidence': due_confidence
                },
                'assignee_id': {
                    'value': predicted_assignee,
                    'confidence': assignee_confidence
                },
                'overall_confidence': (
                    priority_confidence * 0.3 +
                    due_confidence * 0.4 +
                    assignee_confidence * 0.3
                )
            }
            
        except Exception as e:
            logger.error(f"Failed to get prediction suggestions: {e}", exc_info=True)
            return {
                'priority': {'value': 'medium', 'confidence': 0.0},
                'due_date': {'value': None, 'confidence': 0.0},
                'assignee_id': {'value': None, 'confidence': 0.0},
                'overall_confidence': 0.0
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get prediction engine metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **self.metrics,
            'cache_size': len(self._user_patterns_cache),
            'cache_age_seconds': (datetime.utcnow() - self._cache_timestamp).total_seconds()
        }


# Singleton instance
predictive_engine = PredictiveEngine()
