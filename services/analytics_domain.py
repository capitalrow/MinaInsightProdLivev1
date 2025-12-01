"""
CROWN⁵+ Analytics Domain Service
================================
Centralized KPI and metrics calculation service.
Ensures consistent formulas across Dashboard, Analytics, and Tasks pages.

This is the single source of truth for all analytics calculations.
All routes should use this service to avoid formula divergence.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from app import db
from models import Meeting, Task, Analytics

logger = logging.getLogger(__name__)


@dataclass
class KPIResult:
    """Standardized KPI result with trend metadata."""
    value: float
    previous: float
    change: float
    trend: str  # 'up', 'down', 'stable'
    
    def to_dict(self) -> Dict:
        return {
            'value': self.value,
            'previous': self.previous,
            'change': self.change,
            'trend': self.trend
        }


@dataclass
class HealthScoreBreakdown:
    """Meeting Health Score component breakdown."""
    effectiveness: float
    engagement: float
    follow_through: float
    decision_velocity: float
    
    def to_dict(self) -> Dict:
        return {
            'effectiveness': self.effectiveness,
            'engagement': self.engagement,
            'follow_through': self.follow_through,
            'decision_velocity': self.decision_velocity
        }


class AnalyticsDomainService:
    """
    Centralized analytics calculation service.
    
    All analytics computations should go through this service to ensure
    consistency across Dashboard, Analytics page, Tasks page, and WebSocket updates.
    """
    
    # Default weights for health score calculation
    HEALTH_WEIGHTS = {
        'effectiveness': 0.30,
        'engagement': 0.25,
        'follow_through': 0.30,
        'decision_velocity': 0.15
    }
    
    # Hours saved formula constants
    EFFICIENCY_MULTIPLIER = 0.30  # 30% time saved via AI
    TASK_MINUTES_SAVED = 2  # 2 minutes saved per task via automation
    
    @staticmethod
    def calculate_hours_saved(total_duration_minutes: float, total_tasks: int) -> float:
        """
        Calculate hours saved using consistent formula.
        
        Formula: (duration * 0.3) + (tasks * 2 minutes) converted to hours
        This represents:
        - 30% efficiency gain from AI-powered meeting insights
        - 2 minutes saved per task via automated extraction
        
        Args:
            total_duration_minutes: Total meeting duration in minutes
            total_tasks: Total number of tasks extracted
            
        Returns:
            Hours saved as a float
        """
        minutes_saved = (
            total_duration_minutes * AnalyticsDomainService.EFFICIENCY_MULTIPLIER + 
            total_tasks * AnalyticsDomainService.TASK_MINUTES_SAVED
        )
        return minutes_saved / 60
    
    @staticmethod
    def calculate_completion_rate(completed: int, total: int) -> float:
        """Calculate task completion rate as percentage."""
        if total == 0:
            return 0.0
        return round((completed / total) * 100, 1)
    
    @staticmethod
    def calculate_change(current: float, previous: float) -> float:
        """Calculate percentage change between periods."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)
    
    @staticmethod
    def determine_trend(current: float, previous: float) -> str:
        """Determine trend direction."""
        if current > previous:
            return 'up'
        elif current < previous:
            return 'down'
        return 'stable'
    
    @staticmethod
    def get_meeting_duration(meeting: Meeting) -> float:
        """
        Extract meeting duration in minutes from various sources.
        
        Checks (in order):
        1. meeting.duration_minutes if set
        2. Calculate from actual_start/actual_end times
        3. Default to 0
        """
        if hasattr(meeting, 'duration_minutes') and meeting.duration_minutes:
            return float(meeting.duration_minutes)
        
        # Use actual_end and actual_start (correct field names)
        actual_end = getattr(meeting, 'actual_end', None)
        actual_start = getattr(meeting, 'actual_start', None) or getattr(meeting, 'created_at', None)
        
        if actual_end and actual_start and actual_end > actual_start:
            duration = (actual_end - actual_start).total_seconds() / 60
            return min(duration, 480)  # Cap at 8 hours
        
        return 0.0
    
    @classmethod
    def calculate_health_score(
        cls,
        meetings: List[Meeting],
        tasks: List[Task],
        analytics_list: Optional[List[Analytics]] = None,
        weights: Optional[Dict[str, float]] = None
    ) -> Tuple[float, HealthScoreBreakdown]:
        """
        Calculate composite Meeting Health Score (0-100).
        
        Works even when AI analysis isn't complete by falling back to
        task-based metrics for follow-through scoring.
        
        Args:
            meetings: List of meetings in the period
            tasks: List of tasks from those meetings
            analytics_list: Optional list of completed Analytics records
            weights: Optional custom weights (defaults to HEALTH_WEIGHTS)
            
        Returns:
            Tuple of (total_score, breakdown)
        """
        if weights is None:
            weights = cls.HEALTH_WEIGHTS
        
        if not meetings:
            return 0.0, HealthScoreBreakdown(0, 0, 0, 0)
        
        # Calculate component scores
        effectiveness = cls._calculate_effectiveness(meetings, analytics_list)
        engagement = cls._calculate_engagement(meetings, analytics_list)
        follow_through = cls._calculate_follow_through(tasks)
        decision_velocity = cls._calculate_decision_velocity(meetings, analytics_list)
        
        # Weighted average
        total_score = (
            effectiveness * weights['effectiveness'] +
            engagement * weights['engagement'] +
            follow_through * weights['follow_through'] +
            decision_velocity * weights['decision_velocity']
        )
        
        breakdown = HealthScoreBreakdown(
            effectiveness=round(effectiveness, 1),
            engagement=round(engagement, 1),
            follow_through=round(follow_through, 1),
            decision_velocity=round(decision_velocity, 1)
        )
        
        return round(total_score, 1), breakdown
    
    @classmethod
    def _calculate_effectiveness(
        cls,
        meetings: List[Meeting],
        analytics_list: Optional[List[Analytics]]
    ) -> float:
        """
        Calculate meeting effectiveness score.
        
        Uses AI analysis if available, otherwise estimates from meeting metadata.
        """
        if analytics_list and len(analytics_list) > 0:
            # Use AI-derived effectiveness scores (meeting_effectiveness_score in model)
            scores = []
            for a in analytics_list:
                eff_score = getattr(a, 'meeting_effectiveness_score', None)
                if eff_score is not None:
                    scores.append(eff_score * 100)  # Convert 0-1 to 0-100
            if scores:
                return sum(scores) / len(scores)
        
        # Fallback: Estimate from meeting duration (shorter = more efficient)
        if not meetings:
            return 50.0
        
        total_duration = sum(cls.get_meeting_duration(m) for m in meetings)
        avg_duration = total_duration / len(meetings) if meetings else 30
        
        # Optimal duration is 30 minutes
        if avg_duration <= 30:
            return min(90, 70 + (30 - avg_duration))
        else:
            return max(40, 70 - (avg_duration - 30) * 0.5)
    
    @classmethod
    def _calculate_engagement(
        cls,
        meetings: List[Meeting],
        analytics_list: Optional[List[Analytics]]
    ) -> float:
        """
        Calculate participant engagement score.
        
        Uses AI sentiment/participation data if available.
        """
        if analytics_list and len(analytics_list) > 0:
            scores = []
            for a in analytics_list:
                # Use overall_engagement_score (correct field name)
                eng_score = getattr(a, 'overall_engagement_score', None)
                if eng_score is not None:
                    scores.append(eng_score * 100)  # Convert 0-1 to 0-100
                else:
                    # Convert sentiment to engagement proxy
                    sent_score = getattr(a, 'overall_sentiment_score', None)
                    if sent_score is not None:
                        scores.append(50 + sent_score * 50)  # -1 to 1 → 0 to 100
            if scores:
                return sum(scores) / len(scores)
        
        # Fallback: Base score for having meetings
        return 65.0 if meetings else 0.0
    
    @classmethod
    def _calculate_follow_through(cls, tasks: List[Task]) -> float:
        """
        Calculate follow-through score based on task completion.
        
        This is the most reliable metric as it uses real task data.
        """
        if not tasks:
            return 50.0  # Neutral if no tasks
        
        completed = sum(1 for t in tasks if t.status == 'completed')
        total = len(tasks)
        
        completion_rate = (completed / total) * 100
        
        # Scale completion rate to score
        # 80%+ completion = 85-100 score
        # 50-80% = 60-85 score
        # Below 50% = 30-60 score
        if completion_rate >= 80:
            return 85 + (completion_rate - 80) * 0.75
        elif completion_rate >= 50:
            return 60 + (completion_rate - 50) * 0.83
        else:
            return 30 + completion_rate * 0.6
    
    @classmethod
    def _calculate_decision_velocity(
        cls,
        meetings: List[Meeting],
        analytics_list: Optional[List[Analytics]]
    ) -> float:
        """
        Calculate how quickly decisions are made and acted upon.
        """
        if analytics_list and len(analytics_list) > 0:
            scores = []
            for a in analytics_list:
                # Use decisions_made_count (correct field name)
                decisions = getattr(a, 'decisions_made_count', None)
                if decisions is not None and decisions > 0:
                    # More decisions per meeting = higher velocity
                    scores.append(min(100, 50 + decisions * 10))
            if scores:
                return sum(scores) / len(scores)
        
        # Fallback: Base score
        return 60.0 if meetings else 0.0
    
    @classmethod
    def get_task_status_breakdown(
        cls,
        workspace_id: int,
        meeting_ids: Optional[List[int]] = None
    ) -> Dict[str, int]:
        """
        Get accurate task status breakdown from the Task table.
        
        Args:
            workspace_id: Workspace to filter by
            meeting_ids: Optional list of specific meeting IDs
            
        Returns:
            Dict with completed, in_progress, pending counts
        """
        from sqlalchemy import func, case
        
        query = db.session.query(
            func.sum(case((Task.status == 'completed', 1), else_=0)).label('completed'),
            func.sum(case((Task.status == 'in_progress', 1), else_=0)).label('in_progress'),
            func.sum(case((Task.status.in_(['pending', 'todo']), 1), else_=0)).label('pending')
        )
        
        if meeting_ids:
            query = query.filter(Task.meeting_id.in_(meeting_ids))
        else:
            query = query.filter(Task.workspace_id == workspace_id)
        
        result = query.first()
        
        if result is None:
            return {'completed': 0, 'in_progress': 0, 'pending': 0}
        
        return {
            'completed': int(result.completed or 0),
            'in_progress': int(result.in_progress or 0),
            'pending': int(result.pending or 0)
        }
    
    @classmethod
    def get_workspace_kpis(
        cls,
        workspace_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get all KPIs for a workspace in one call.
        
        Returns consistent metrics for use across Dashboard, Analytics, etc.
        """
        from sqlalchemy import func
        
        current_end = datetime.now()
        current_start = current_end - timedelta(days=days)
        previous_end = current_start
        previous_start = previous_end - timedelta(days=days)
        
        # Current period meetings
        current_meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= current_start
        ).all()
        
        current_meeting_ids = [m.id for m in current_meetings]
        
        # Previous period meetings
        previous_meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= previous_start,
            Meeting.created_at < previous_end
        ).all()
        
        previous_meeting_ids = [m.id for m in previous_meetings]
        
        # Get tasks
        current_tasks = []
        previous_tasks = []
        
        if current_meeting_ids:
            current_tasks = db.session.query(Task).filter(
                Task.meeting_id.in_(current_meeting_ids)
            ).all()
        
        if previous_meeting_ids:
            previous_tasks = db.session.query(Task).filter(
                Task.meeting_id.in_(previous_meeting_ids)
            ).all()
        
        # Calculate durations
        current_duration = sum(cls.get_meeting_duration(m) for m in current_meetings)
        previous_duration = sum(cls.get_meeting_duration(m) for m in previous_meetings)
        
        # Calculate all KPIs
        current_task_count = len(current_tasks)
        previous_task_count = len(previous_tasks)
        
        current_completed = sum(1 for t in current_tasks if t.status == 'completed')
        previous_completed = sum(1 for t in previous_tasks if t.status == 'completed')
        
        current_hours_saved = cls.calculate_hours_saved(current_duration, current_task_count)
        previous_hours_saved = cls.calculate_hours_saved(previous_duration, previous_task_count)
        
        current_avg_duration = current_duration / len(current_meetings) if current_meetings else 0
        previous_avg_duration = previous_duration / len(previous_meetings) if previous_meetings else 0
        
        return {
            'total_meetings': KPIResult(
                value=len(current_meetings),
                previous=len(previous_meetings),
                change=cls.calculate_change(len(current_meetings), len(previous_meetings)),
                trend=cls.determine_trend(len(current_meetings), len(previous_meetings))
            ),
            'action_items': KPIResult(
                value=current_task_count,
                previous=previous_task_count,
                change=cls.calculate_change(current_task_count, previous_task_count),
                trend=cls.determine_trend(current_task_count, previous_task_count)
            ),
            'hours_saved': KPIResult(
                value=round(current_hours_saved, 1),
                previous=round(previous_hours_saved, 1),
                change=cls.calculate_change(current_hours_saved, previous_hours_saved),
                trend=cls.determine_trend(current_hours_saved, previous_hours_saved)
            ),
            'avg_duration': KPIResult(
                value=round(current_avg_duration, 0),
                previous=round(previous_avg_duration, 0),
                change=cls.calculate_change(current_avg_duration, previous_avg_duration),
                trend='down' if current_avg_duration < previous_avg_duration else (
                    'up' if current_avg_duration > previous_avg_duration else 'stable'
                )
            ),
            'completion_rate': cls.calculate_completion_rate(current_completed, current_task_count),
            'task_status': cls.get_task_status_breakdown(workspace_id, current_meeting_ids),
            'period': {
                'current': {'start': current_start.isoformat(), 'end': current_end.isoformat()},
                'previous': {'start': previous_start.isoformat(), 'end': previous_end.isoformat()},
                'days': days
            },
            '_metadata': {
                'current_meetings': len(current_meetings),
                'current_tasks': current_task_count,
                'current_duration_minutes': current_duration
            }
        }


# Singleton instance for easy importing
analytics_service = AnalyticsDomainService()
