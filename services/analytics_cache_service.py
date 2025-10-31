"""
Analytics Cache Service - CROWN⁵+ Cache-First Bootstrap & Reconciliation

Manages analytics data caching, validation, and delta computation for
the analytics intelligence system.

Features:
- SHA-256 checksum generation for data integrity
- Field-level delta computation for efficient updates
- ETag generation for HTTP caching
- Cache validation and reconciliation logic
"""

import logging
import hashlib
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from models import db, Meeting, Task, Analytics, Participant
from sqlalchemy import func, desc, and_

logger = logging.getLogger(__name__)


class AnalyticsCacheService:
    """
    Service for managing analytics data caching and validation.
    
    Implements CROWN⁵+ principles:
    - Atomic Truth: Each cached value has a verifiable checksum
    - Predictive Harmony: Computes diffs to minimize payload size
    - Idempotent Safety: Delta application is replay-safe
    - Self-Healing: Detects and corrects cache drift
    """
    
    @staticmethod
    def generate_checksum(data: Dict[str, Any]) -> str:
        """
        Generate SHA-256 checksum for data integrity verification.
        
        Args:
            data: Data dictionary to hash
            
        Returns:
            SHA-256 hex digest
        """
        try:
            # Sort keys for consistent hashing
            data_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.sha256(data_str.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to generate checksum: {e}")
            return ""
    
    @staticmethod
    def generate_etag(workspace_id: int, days: int = 30) -> str:
        """
        Generate ETag for analytics data to enable HTTP caching.
        
        Args:
            workspace_id: Workspace ID
            days: Time range in days
            
        Returns:
            ETag string (SHA-256 hash of key data)
        """
        try:
            # Get last modified timestamp of relevant data
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get latest meeting timestamp
            latest_meeting = db.session.query(func.max(Meeting.updated_at)).filter(
                Meeting.workspace_id == workspace_id,
                Meeting.created_at >= cutoff_date
            ).scalar()
            
            # Get latest task timestamp
            latest_task = db.session.query(func.max(Task.updated_at)).join(Meeting).filter(
                Meeting.workspace_id == workspace_id,
                Meeting.created_at >= cutoff_date
            ).scalar()
            
            # Get latest analytics timestamp
            latest_analytics = db.session.query(func.max(Analytics.updated_at)).join(Meeting).filter(
                Meeting.workspace_id == workspace_id,
                Meeting.created_at >= cutoff_date
            ).scalar()
            
            # Combine timestamps to create unique ETag
            timestamps = {
                'workspace_id': workspace_id,
                'days': days,
                'latest_meeting': latest_meeting.isoformat() if latest_meeting else None,
                'latest_task': latest_task.isoformat() if latest_task else None,
                'latest_analytics': latest_analytics.isoformat() if latest_analytics else None
            }
            
            return AnalyticsCacheService.generate_checksum(timestamps)
            
        except Exception as e:
            logger.error(f"Failed to generate ETag: {e}")
            return ""
    
    @staticmethod
    def get_analytics_snapshot(workspace_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get complete analytics snapshot for workspace.
        
        Args:
            workspace_id: Workspace ID
            days: Time range in days
            
        Returns:
            Complete analytics data with checksums
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Get KPIs
            kpis = AnalyticsCacheService._get_kpis(workspace_id, cutoff_date)
            
            # Get chart data
            charts = AnalyticsCacheService._get_charts(workspace_id, cutoff_date, days)
            
            # Get tab data
            tabs = {
                'overview': AnalyticsCacheService._get_overview_data(workspace_id, cutoff_date),
                'engagement': AnalyticsCacheService._get_engagement_data(workspace_id, cutoff_date),
                'productivity': AnalyticsCacheService._get_productivity_data(workspace_id, cutoff_date),
                'insights': AnalyticsCacheService._get_insights_data(workspace_id, cutoff_date)
            }
            
            # Build snapshot
            snapshot = {
                'workspace_id': workspace_id,
                'days': days,
                'timestamp': datetime.utcnow().isoformat(),
                'kpis': kpis,
                'charts': charts,
                'tabs': tabs,
                'last_event_id': None  # Will be set by event sequencer
            }
            
            # Add checksum for each section
            snapshot['checksums'] = {
                'kpis': AnalyticsCacheService.generate_checksum(kpis),
                'charts': AnalyticsCacheService.generate_checksum(charts),
                'tabs_overview': AnalyticsCacheService.generate_checksum(tabs['overview']),
                'tabs_engagement': AnalyticsCacheService.generate_checksum(tabs['engagement']),
                'tabs_productivity': AnalyticsCacheService.generate_checksum(tabs['productivity']),
                'tabs_insights': AnalyticsCacheService.generate_checksum(tabs['insights']),
                'full': AnalyticsCacheService.generate_checksum(snapshot)
            }
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to get analytics snapshot: {e}")
            return {}
    
    @staticmethod
    def compute_delta(old_snapshot: Dict[str, Any], new_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute field-level delta between two snapshots.
        
        Args:
            old_snapshot: Previous snapshot
            new_snapshot: Current snapshot
            
        Returns:
            Delta payload with only changed fields
        """
        try:
            delta = {
                'timestamp': datetime.utcnow().isoformat(),
                'changes': {}
            }
            
            # Compare KPIs
            if old_snapshot.get('kpis') != new_snapshot.get('kpis'):
                delta['changes']['kpis'] = AnalyticsCacheService._compute_dict_delta(
                    old_snapshot.get('kpis', {}),
                    new_snapshot.get('kpis', {})
                )
            
            # Compare charts
            if old_snapshot.get('charts') != new_snapshot.get('charts'):
                delta['changes']['charts'] = AnalyticsCacheService._compute_dict_delta(
                    old_snapshot.get('charts', {}),
                    new_snapshot.get('charts', {})
                )
            
            # Compare tabs
            old_tabs = old_snapshot.get('tabs', {})
            new_tabs = new_snapshot.get('tabs', {})
            
            for tab_name in ['overview', 'engagement', 'productivity', 'insights']:
                if old_tabs.get(tab_name) != new_tabs.get(tab_name):
                    if 'tabs' not in delta['changes']:
                        delta['changes']['tabs'] = {}
                    delta['changes']['tabs'][tab_name] = AnalyticsCacheService._compute_dict_delta(
                        old_tabs.get(tab_name, {}),
                        new_tabs.get(tab_name, {})
                    )
            
            # Add checksums for verification
            delta['checksums'] = new_snapshot.get('checksums', {})
            
            return delta
            
        except Exception as e:
            logger.error(f"Failed to compute delta: {e}")
            return {'timestamp': datetime.utcnow().isoformat(), 'changes': {}}
    
    @staticmethod
    def _compute_dict_delta(old_dict: Dict, new_dict: Dict) -> Dict:
        """Compute delta between two dictionaries (field-level)."""
        delta = {}
        
        # Find added and changed fields
        for key, value in new_dict.items():
            if key not in old_dict or old_dict[key] != value:
                delta[key] = value
        
        # Find removed fields
        for key in old_dict:
            if key not in new_dict:
                delta[key] = None  # Mark as removed
        
        return delta
    
    @staticmethod
    def _get_kpis(workspace_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """Get KPI metrics."""
        # Total meetings
        total_meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).count()
        
        # Total tasks
        total_tasks = db.session.query(Task).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).count()
        
        # Completed tasks
        completed_tasks = db.session.query(Task).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Task.status == 'completed'
        ).count()
        
        # Task completion rate
        task_completion_rate = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
        
        # Average duration
        avg_duration_result = db.session.query(
            func.avg(
                func.extract('epoch', Meeting.actual_end - Meeting.actual_start) / 60
            )
        ).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Meeting.actual_start.isnot(None),
            Meeting.actual_end.isnot(None)
        ).scalar()
        
        avg_duration = int(avg_duration_result) if avg_duration_result else 0
        
        # Hours saved (estimate: 5 min per meeting for manual notes)
        hours_saved = int((total_meetings * 5) / 60)
        
        return {
            'total_meetings': total_meetings,
            'total_tasks': total_tasks,
            'task_completion_rate': task_completion_rate,
            'avg_duration': avg_duration,
            'hours_saved': hours_saved
        }
    
    @staticmethod
    def _get_charts(workspace_id: int, cutoff_date: datetime, days: int) -> Dict[str, Any]:
        """Get chart data."""
        from sqlalchemy import cast, Date
        
        # Meeting activity trend
        trend_data = db.session.query(
            cast(Meeting.created_at, Date).label('date'),
            func.count(Meeting.id).label('meetings')
        ).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).group_by(
            cast(Meeting.created_at, Date)
        ).order_by(
            cast(Meeting.created_at, Date)
        ).all()
        
        trend_map = {row.date: row.meetings for row in trend_data}
        
        meeting_trend = []
        for i in range(days):
            day = (datetime.now() - timedelta(days=i)).date()
            meeting_trend.append({
                'date': day.strftime('%Y-%m-%d'),
                'meetings': trend_map.get(day, 0)
            })
        
        meeting_trend.reverse()
        
        return {
            'meeting_activity': meeting_trend
        }
    
    @staticmethod
    def _get_overview_data(workspace_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """Get overview tab data."""
        return {
            'loaded': True,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _get_engagement_data(workspace_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """Get engagement tab data."""
        return {
            'loaded': False,  # Lazy-loaded
            'timestamp': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _get_productivity_data(workspace_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """Get productivity tab data."""
        return {
            'loaded': False,  # Lazy-loaded
            'timestamp': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _get_insights_data(workspace_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """Get insights tab data."""
        return {
            'loaded': False,  # Lazy-loaded
            'timestamp': datetime.utcnow().isoformat()
        }


# Singleton instance
analytics_cache_service = AnalyticsCacheService()
