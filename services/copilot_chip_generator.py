"""
CROWN⁹ Copilot Smart Chip Generation

Generates predictive action chips based on context, user behavior, and workspace state.

Chip Types:
- Quick actions (create task, schedule meeting, view analytics)
- Context-aware suggestions (based on current page, time, history)
- Predictive queries (based on patterns and embeddings)
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ChipType(str, Enum):
    """Types of action chips."""
    QUICK_ACTION = "quick_action"
    SUGGESTION = "suggestion"
    PREDICTIVE_QUERY = "predictive_query"
    SHORTCUT = "shortcut"


class ActionChip:
    """Smart action chip with metadata."""
    def __init__(
        self,
        chip_id: str,
        label: str,
        chip_type: ChipType,
        action: str,
        icon: Optional[str] = None,
        confidence: float = 1.0,
        context: Optional[Dict[str, Any]] = None
    ):
        self.chip_id = chip_id
        self.label = label
        self.chip_type = chip_type
        self.action = action
        self.icon = icon
        self.confidence = confidence
        self.context = context or {}
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'chip_id': self.chip_id,
            'label': self.label,
            'type': self.chip_type.value,
            'action': self.action,
            'icon': self.icon,
            'confidence': self.confidence,
            'context': self.context,
            'created_at': self.created_at.isoformat()
        }


class CopilotChipGenerator:
    """
    Smart chip generator for Copilot interface.
    
    Features:
    - Context-aware suggestions based on current page
    - Time-based suggestions (morning: "Review today's schedule")
    - Pattern-based predictions from user history
    - Quick action shortcuts for common tasks
    """
    
    def __init__(self):
        """Initialize chip generator."""
        self.chip_cache = {}
        self.user_patterns = {}
    
    def generate_chips(
        self,
        user_id: int,
        workspace_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ActionChip]:
        """
        Generate contextual action chips.
        
        Args:
            user_id: Current user ID
            workspace_id: Current workspace ID
            context: Additional context (current page, time, recent actions)
            
        Returns:
            List of ActionChip objects
        """
        context = context or {}
        chips = []
        
        # Add quick action chips
        chips.extend(self._generate_quick_actions(user_id, workspace_id))
        
        # Add context-aware suggestions
        chips.extend(self._generate_contextual_suggestions(context))
        
        # Add time-based suggestions
        chips.extend(self._generate_time_based_chips())
        
        # Add predictive query chips
        chips.extend(self._generate_predictive_chips(user_id))
        
        # Sort by confidence and limit to top 6
        chips.sort(key=lambda c: c.confidence, reverse=True)
        return chips[:6]
    
    def _generate_quick_actions(
        self,
        user_id: int,
        workspace_id: Optional[int]
    ) -> List[ActionChip]:
        """Generate quick action chips."""
        return [
            ActionChip(
                chip_id="qa_create_task",
                label="Create Task",
                chip_type=ChipType.QUICK_ACTION,
                action="create_task",
                icon="plus-circle",
                confidence=0.95
            ),
            ActionChip(
                chip_id="qa_schedule_meeting",
                label="Schedule Meeting",
                chip_type=ChipType.QUICK_ACTION,
                action="schedule_meeting",
                icon="calendar",
                confidence=0.90
            ),
            ActionChip(
                chip_id="qa_view_analytics",
                label="View Analytics",
                chip_type=ChipType.QUICK_ACTION,
                action="view_analytics",
                icon="bar-chart",
                confidence=0.85
            ),
        ]
    
    def _generate_contextual_suggestions(
        self,
        context: Dict[str, Any]
    ) -> List[ActionChip]:
        """Generate context-aware suggestion chips."""
        chips = []
        current_page = context.get('page', 'dashboard')
        
        # Page-specific suggestions
        if current_page == 'tasks':
            chips.append(ActionChip(
                chip_id="ctx_overdue_tasks",
                label="Show overdue tasks",
                chip_type=ChipType.SUGGESTION,
                action="query",
                icon="alert-circle",
                confidence=0.88,
                context={'query': 'Show me my overdue tasks'}
            ))
        elif current_page == 'calendar':
            chips.append(ActionChip(
                chip_id="ctx_next_meeting",
                label="What's my next meeting?",
                chip_type=ChipType.SUGGESTION,
                action="query",
                icon="clock",
                confidence=0.90,
                context={'query': "What's my next meeting?"}
            ))
        elif current_page == 'analytics':
            chips.append(ActionChip(
                chip_id="ctx_weekly_progress",
                label="Show weekly progress",
                chip_type=ChipType.SUGGESTION,
                action="query",
                icon="trending-up",
                confidence=0.87,
                context={'query': 'Show my weekly progress'}
            ))
        
        return chips
    
    def _generate_time_based_chips(self) -> List[ActionChip]:
        """Generate time-based suggestion chips."""
        chips = []
        now = datetime.now()
        hour = now.hour
        
        # Morning suggestions (6 AM - 12 PM)
        if 6 <= hour < 12:
            chips.append(ActionChip(
                chip_id="time_morning_schedule",
                label="Review today's schedule",
                chip_type=ChipType.SUGGESTION,
                action="query",
                icon="sunrise",
                confidence=0.92,
                context={'query': "What's on my schedule today?"}
            ))
        
        # Afternoon suggestions (12 PM - 5 PM)
        elif 12 <= hour < 17:
            chips.append(ActionChip(
                chip_id="time_afternoon_tasks",
                label="Check remaining tasks",
                chip_type=ChipType.SUGGESTION,
                action="query",
                icon="check-square",
                confidence=0.88,
                context={'query': 'Show my remaining tasks for today'}
            ))
        
        # Evening suggestions (5 PM - 10 PM)
        elif 17 <= hour < 22:
            chips.append(ActionChip(
                chip_id="time_evening_summary",
                label="Daily summary",
                chip_type=ChipType.SUGGESTION,
                action="query",
                icon="sunset",
                confidence=0.90,
                context={'query': 'Give me a summary of today'}
            ))
        
        # Friday-specific suggestions
        if now.weekday() == 4:  # Friday
            chips.append(ActionChip(
                chip_id="time_friday_nextweek",
                label="Plan next week",
                chip_type=ChipType.SUGGESTION,
                action="query",
                icon="calendar",
                confidence=0.85,
                context={'query': 'What do I have scheduled for next week?'}
            ))
        
        return chips
    
    def _generate_predictive_chips(self, user_id: int) -> List[ActionChip]:
        """Generate predictive chips based on user patterns."""
        chips = []
        
        # Check user patterns (in production, load from database/memory)
        patterns = self.user_patterns.get(user_id, {})
        
        # Example: If user frequently asks about tasks on Monday morning
        if datetime.now().weekday() == 0 and datetime.now().hour < 12:
            chips.append(ActionChip(
                chip_id="pred_monday_tasks",
                label="This week's priorities",
                chip_type=ChipType.PREDICTIVE_QUERY,
                action="query",
                icon="target",
                confidence=0.82,
                context={'query': 'What are my priorities this week?'}
            ))
        
        return chips
    
    def track_chip_usage(
        self,
        user_id: int,
        chip_id: str,
        action_taken: bool
    ):
        """Track chip usage for pattern learning."""
        if user_id not in self.user_patterns:
            self.user_patterns[user_id] = {}
        
        if chip_id not in self.user_patterns[user_id]:
            self.user_patterns[user_id][chip_id] = {
                'shown': 0,
                'clicked': 0,
                'last_shown': None
            }
        
        self.user_patterns[user_id][chip_id]['shown'] += 1
        self.user_patterns[user_id][chip_id]['last_shown'] = datetime.now()
        
        if action_taken:
            self.user_patterns[user_id][chip_id]['clicked'] += 1
        
        logger.debug(f"Chip usage tracked: user={user_id}, chip={chip_id}, action={action_taken}")


# Global singleton instance
copilot_chip_generator = CopilotChipGenerator()
