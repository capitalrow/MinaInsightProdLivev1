"""
Analytics Delta Service - CROWN⁵+ Real-time Delta Broadcasting

Listens for meeting and task updates, computes analytics deltas,
and broadcasts them to connected clients for instant KPI updates.

Features:
- Event-driven delta computation
- Idempotent delta broadcasting
- Efficient field-level changes only
- Vector clock support for ordering
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from models import db, Meeting, Task
from services.analytics_cache_service import analytics_cache_service
from services.event_broadcaster import event_broadcaster
from services.event_sequencer import event_sequencer
from models.event_ledger import EventType
from sqlalchemy import func

logger = logging.getLogger(__name__)


class AnalyticsDeltaService:
    """
    Service for computing and broadcasting analytics deltas.
    
    Triggered by:
    - Meeting completion (analytics computed)
    - Task status changes
    - Meeting data updates
    """
    
    @staticmethod
    def broadcast_kpi_delta_on_meeting_completion(meeting_id: int, workspace_id: int, user_id: Optional[int] = None):
        """
        Broadcast analytics delta when meeting is completed.
        
        Args:
            meeting_id: Meeting ID
            workspace_id: Workspace ID
            user_id: User ID (for vector clock)
        """
        try:
            # Get current snapshot (last 30 days)
            current_snapshot = analytics_cache_service.get_analytics_snapshot(workspace_id, days=30)
            
            # Compute delta (just the changed KPIs)
            delta = {
                'changes': {
                    'kpis': {
                        'total_meetings': current_snapshot.get('kpis', {}).get('total_meetings', 0),
                        'avg_duration': current_snapshot.get('kpis', {}).get('avg_duration', 0),
                        'hours_saved': current_snapshot.get('kpis', {}).get('hours_saved', 0)
                    }
                },
                'checksums': current_snapshot.get('checksums', {})
            }
            
            # Use event_broadcaster which will use event_sequencer internally
            event = event_broadcaster.broadcast_analytics_delta(
                workspace_id=workspace_id,
                delta_data=delta,
                event_id=None,  # event_broadcaster creates the event with proper ID
                user_id=user_id
            )
            
            if event:
                logger.info(f"Analytics delta broadcast for meeting {meeting_id} (event_id: {event.id})")
            
        except Exception as e:
            logger.error(f"Failed to broadcast KPI delta: {e}")
    
    @staticmethod
    def broadcast_task_delta_on_status_change(
        task_id: int,
        workspace_id: int,
        old_status: str,
        new_status: str,
        user_id: Optional[int] = None
    ):
        """
        Broadcast analytics delta when task status changes.
        
        Args:
            task_id: Task ID
            workspace_id: Workspace ID
            old_status: Previous status
            new_status: New status
            user_id: User ID (for vector clock)
        """
        try:
            # Only broadcast if completion status changed
            if (old_status != 'completed' and new_status == 'completed') or \
               (old_status == 'completed' and new_status != 'completed'):
                
                # Get current snapshot
                current_snapshot = analytics_cache_service.get_analytics_snapshot(workspace_id, days=30)
                
                # Compute delta (just the changed KPIs)
                delta = {
                    'changes': {
                        'kpis': {
                            'total_tasks': current_snapshot.get('kpis', {}).get('total_tasks', 0),
                            'task_completion_rate': current_snapshot.get('kpis', {}).get('task_completion_rate', 0)
                        }
                    },
                    'checksums': current_snapshot.get('checksums', {})
                }
                
                # Broadcast delta event
                event_broadcaster.broadcast_analytics_delta(
                    workspace_id=workspace_id,
                    delta_data=delta,
                    event_id=None,
                    user_id=user_id
                )
                
                logger.info(f"Task completion delta broadcast for task {task_id}")
                
        except Exception as e:
            logger.error(f"Failed to broadcast task delta: {e}")
    
    @staticmethod
    def broadcast_full_refresh_on_bulk_update(workspace_id: int, user_id: Optional[int] = None):
        """
        Broadcast full snapshot refresh for bulk updates.
        
        Args:
            workspace_id: Workspace ID
            user_id: User ID (for vector clock)
        """
        try:
            # Get current snapshot
            snapshot = analytics_cache_service.get_analytics_snapshot(workspace_id, days=30)
            
            # Broadcast as delta (full refresh)
            delta = {
                'changes': {
                    'kpis': snapshot.get('kpis', {}),
                    'charts': snapshot.get('charts', {})
                },
                'checksums': snapshot.get('checksums', {})
            }
            
            # Broadcast delta event
            event_broadcaster.broadcast_analytics_delta(
                workspace_id=workspace_id,
                delta_data=delta,
                event_id=None,
                user_id=user_id
            )
            
            logger.info(f"Full refresh delta broadcast for workspace {workspace_id}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast full refresh: {e}")


# Singleton instance
analytics_delta_service = AnalyticsDeltaService()
