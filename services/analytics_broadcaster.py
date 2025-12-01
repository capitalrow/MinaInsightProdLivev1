"""
CROWN⁵+ Analytics Event Broadcaster
====================================
Handles WebSocket event emission for analytics updates.
Broadcasts structured deltas with sequence IDs for idempotent client updates.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsDelta:
    """Structured analytics delta for WebSocket broadcast."""
    event_type: str  # 'task_created', 'task_updated', 'task_completed', 'meeting_ended', etc.
    workspace_id: int
    sequence_id: str
    timestamp: str
    entity_type: str  # 'task', 'meeting', 'analytics'
    entity_id: int
    changes: Dict[str, Any]
    affected_kpis: List[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class AnalyticsBroadcaster:
    """
    Broadcasts analytics updates via WebSocket with structured deltas.
    
    Features:
    - Sequence IDs for idempotent updates
    - Delta metadata for incremental UI updates
    - Workspace isolation
    - Event deduplication
    """
    
    _instance = None
    _socketio = None
    _sequence_counter = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def init_app(cls, socketio) -> None:
        """Initialize with Flask-SocketIO instance."""
        cls._socketio = socketio
        logger.info("✅ AnalyticsBroadcaster initialized")
    
    @classmethod
    def _generate_sequence_id(cls) -> str:
        """Generate unique sequence ID for event ordering."""
        cls._sequence_counter += 1
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        return f"seq_{timestamp}_{cls._sequence_counter}"
    
    @classmethod
    def _get_checksum(cls, data: Dict) -> str:
        """Generate checksum for delta verification."""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    
    @classmethod
    def broadcast_task_event(
        cls,
        workspace_id: int,
        task_id: int,
        event_type: str,
        changes: Dict[str, Any],
        meeting_id: Optional[int] = None
    ) -> None:
        """
        Broadcast task-related analytics update.
        
        Args:
            workspace_id: Target workspace
            task_id: The task that changed
            event_type: 'task_created', 'task_updated', 'task_completed', 'task_deleted'
            changes: Dict of changed fields and their new values
            meeting_id: Optional associated meeting
        """
        if not cls._socketio:
            logger.warning("SocketIO not initialized, skipping broadcast")
            return
        
        # Determine which KPIs are affected
        affected_kpis = ['action_items', 'completion_rate']
        if event_type in ['task_created', 'task_completed']:
            affected_kpis.extend(['hours_saved', 'follow_through'])
        
        delta = AnalyticsDelta(
            event_type=event_type,
            workspace_id=workspace_id,
            sequence_id=cls._generate_sequence_id(),
            timestamp=datetime.now().isoformat(),
            entity_type='task',
            entity_id=task_id,
            changes=changes,
            affected_kpis=affected_kpis
        )
        
        payload = delta.to_dict()
        payload['checksum'] = cls._get_checksum(payload)
        
        room = f"workspace_{workspace_id}"
        
        try:
            cls._socketio.emit(
                'analytics_delta',
                payload,
                room=room,
                namespace='/analytics'
            )
            
            # Also emit to general analytics_update for backward compatibility
            cls._socketio.emit(
                'analytics_update',
                {
                    'type': event_type,
                    'workspace_id': workspace_id,
                    'sequence_id': delta.sequence_id,
                    'timestamp': delta.timestamp,
                    'refresh_kpis': affected_kpis
                },
                room=room,
                namespace='/analytics'
            )
            
            logger.debug(f"📡 Analytics delta broadcast: {event_type} for task {task_id} in workspace {workspace_id}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast analytics delta: {e}")
    
    @classmethod
    def broadcast_meeting_event(
        cls,
        workspace_id: int,
        meeting_id: int,
        event_type: str,
        changes: Dict[str, Any]
    ) -> None:
        """
        Broadcast meeting-related analytics update.
        
        Args:
            workspace_id: Target workspace
            meeting_id: The meeting that changed
            event_type: 'meeting_started', 'meeting_ended', 'meeting_analyzed'
            changes: Dict of changed fields
        """
        if not cls._socketio:
            logger.warning("SocketIO not initialized, skipping broadcast")
            return
        
        affected_kpis = ['total_meetings', 'avg_duration']
        if event_type == 'meeting_analyzed':
            affected_kpis.extend(['health_score', 'effectiveness', 'engagement'])
        if event_type == 'meeting_ended':
            affected_kpis.append('hours_saved')
        
        delta = AnalyticsDelta(
            event_type=event_type,
            workspace_id=workspace_id,
            sequence_id=cls._generate_sequence_id(),
            timestamp=datetime.now().isoformat(),
            entity_type='meeting',
            entity_id=meeting_id,
            changes=changes,
            affected_kpis=affected_kpis
        )
        
        payload = delta.to_dict()
        payload['checksum'] = cls._get_checksum(payload)
        
        room = f"workspace_{workspace_id}"
        
        try:
            cls._socketio.emit(
                'analytics_delta',
                payload,
                room=room,
                namespace='/analytics'
            )
            
            cls._socketio.emit(
                'analytics_update',
                {
                    'type': event_type,
                    'workspace_id': workspace_id,
                    'meeting_id': meeting_id,
                    'sequence_id': delta.sequence_id,
                    'timestamp': delta.timestamp,
                    'refresh_kpis': affected_kpis
                },
                room=room,
                namespace='/analytics'
            )
            
            logger.debug(f"📡 Analytics delta broadcast: {event_type} for meeting {meeting_id}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast meeting analytics delta: {e}")
    
    @classmethod
    def broadcast_full_refresh(
        cls,
        workspace_id: int,
        reason: str = 'sync'
    ) -> None:
        """
        Request clients to perform a full analytics refresh.
        
        Used when incremental updates aren't sufficient.
        """
        if not cls._socketio:
            return
        
        room = f"workspace_{workspace_id}"
        
        try:
            cls._socketio.emit(
                'analytics_refresh',
                {
                    'type': 'full_refresh',
                    'workspace_id': workspace_id,
                    'sequence_id': cls._generate_sequence_id(),
                    'timestamp': datetime.now().isoformat(),
                    'reason': reason
                },
                room=room,
                namespace='/analytics'
            )
            
            logger.debug(f"📡 Full analytics refresh broadcast for workspace {workspace_id}: {reason}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast full refresh: {e}")


# Singleton instance
analytics_broadcaster = AnalyticsBroadcaster()
