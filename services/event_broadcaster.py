"""
Event Broadcaster Service - CROWN⁴ Real-time WebSocket Broadcasting

Broadcasts events to connected clients via WebSocket namespaces for
real-time dashboard updates, task synchronization, and analytics refresh.

Integrates with EventSequencer to ensure ordered, reliable event delivery.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from flask_socketio import emit, join_room, leave_room
from models.event_ledger import EventLedger, EventType, EventStatus
from services.event_sequencer import event_sequencer

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """
    Service for broadcasting events to WebSocket clients in real-time.
    
    Responsibilities:
    - Emit events to appropriate WebSocket namespaces
    - Track broadcast status (pending/sent/failed)
    - Support room-based broadcasting for workspace isolation
    - Integrate with EventSequencer for event ordering
    """
    
    def __init__(self, socketio=None):
        """
        Initialize EventBroadcaster.
        
        Args:
            socketio: Flask-SocketIO instance (injected at runtime)
        """
        self.socketio = socketio
        
    def set_socketio(self, socketio):
        """Set SocketIO instance after initialization."""
        self.socketio = socketio
    
    def emit_event(
        self,
        event: EventLedger,
        namespace: str = "/dashboard",
        room: Optional[str] = None,
        broadcast: bool = True
    ) -> bool:
        """
        Emit an event to WebSocket clients.
        
        Args:
            event: EventLedger instance to broadcast
            namespace: WebSocket namespace (e.g., /dashboard, /analytics)
            room: Optional room for workspace isolation
            broadcast: Whether to broadcast to all clients in room
            
        Returns:
            True if successfully emitted, False otherwise
        """
        if not self.socketio:
            logger.warning("SocketIO not initialized, cannot broadcast event")
            return False
        
        try:
            # Prepare event payload with CROWN⁴.5 sequencing tokens
            payload = {
                'event_id': event.id,
                'event_type': event.event_type.value,
                'event_name': event.event_name,
                'sequence_num': event.sequence_num,
                'last_applied': event.last_applied_id,  # CROWN⁴: Idempotency token
                'vector_clock': event.vector_clock,  # CROWN⁴.5: Distributed ordering
                'timestamp': event.created_at.isoformat() if event.created_at else None,
                'data': event.payload or {},
                'checksum': event.checksum
            }
            
            # Emit to specific room or broadcast to all
            if room:
                self.socketio.emit(
                    event.event_type.value,
                    payload,
                    namespace=namespace,
                    room=room
                )
            else:
                self.socketio.emit(
                    event.event_type.value,
                    payload,
                    namespace=namespace,
                    broadcast=broadcast
                )
            
            # Mark event as broadcast successfully
            event_sequencer.mark_event_completed(
                event.id,
                result={'broadcast': 'sent', 'namespace': namespace, 'room': room},
                broadcast_status='sent'
            )
            
            logger.debug(
                f"Broadcast event {event.id} ({event.event_type.value}) to {namespace}"
                f"{' room=' + room if room else ''}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to broadcast event {event.id}: {e}", exc_info=True)
            
            # Mark event as failed
            event_sequencer.mark_event_failed(
                event.id,
                error_message=str(e),
                broadcast_status='failed'
            )
            
            return False
    
    def broadcast_session_created(
        self,
        session_id: int,
        meeting_data: Dict[str, Any],
        workspace_id: int
    ) -> Optional[EventLedger]:
        """
        Broadcast session_update:created event when new meeting created.
        
        Args:
            session_id: Session ID
            meeting_data: Meeting information
            workspace_id: Workspace ID for room isolation
            
        Returns:
            Created EventLedger instance or None
        """
        try:
            # Create event
            event = event_sequencer.create_event(
                event_type=EventType.SESSION_UPDATE_CREATED,
                event_name="New Meeting Created",
                payload={
                    'session_id': session_id,
                    'meeting': meeting_data,
                    'workspace_id': workspace_id
                },
                session_id=session_id,
                trace_id=str(session_id)
            )
            
            # Broadcast to dashboard namespace with workspace room
            self.emit_event(
                event,
                namespace="/dashboard",
                room=f"workspace_{workspace_id}"
            )
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to broadcast session_created: {e}")
            return None
    
    def broadcast_task_update(
        self,
        task_id: int,
        task_data: Dict[str, Any],
        meeting_id: Optional[int],
        workspace_id: int,
        user_id: Optional[int] = None,
        previous_clock: Optional[Dict[str, int]] = None
    ) -> Optional[EventLedger]:
        """
        Broadcast task_update event when task status changes (CROWN⁴.5).
        
        Args:
            task_id: Task ID
            task_data: Task information
            meeting_id: Associated meeting ID (None if no meeting)
            workspace_id: Workspace ID
            user_id: Client user ID for vector clock generation (enables distributed ordering)
            previous_clock: Previous vector clock from client (enables causality tracking)
            
        Returns:
            Created EventLedger instance or None
        """
        try:
            # If no previous_clock provided, retrieve from last event by this user in this workspace (CROWN⁴.5)
            if user_id and not previous_clock:
                from sqlalchemy import select, desc
                from models import db
                last_event = db.session.scalar(
                    select(EventLedger)
                    .where(EventLedger.payload['user_id'].astext == str(user_id))
                    .where(EventLedger.payload['workspace_id'].astext == str(workspace_id))
                    .where(EventLedger.vector_clock.isnot(None))
                    .order_by(desc(EventLedger.created_at))
                    .limit(1)
                )
                previous_clock = last_event.vector_clock if last_event else None
            
            event = event_sequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Task Updated",
                payload={
                    'task_id': task_id,
                    'task': task_data,
                    'meeting_id': meeting_id,
                    'workspace_id': workspace_id,
                    'user_id': user_id
                },
                trace_id=f"task_{task_id}",
                client_id=f"user_{user_id}" if user_id else f"server_{workspace_id}",  # CROWN⁴.5: Real client ID
                previous_clock=previous_clock
            )
            
            # Broadcast to both dashboard and tasks namespaces
            self.emit_event(event, namespace="/dashboard", room=f"workspace_{workspace_id}")
            self.emit_event(event, namespace="/tasks", room=f"workspace_{workspace_id}")
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to broadcast task_update: {e}")
            return None
    
    def broadcast_analytics_refresh(
        self,
        meeting_id: int,
        analytics_data: Dict[str, Any],
        workspace_id: int
    ) -> Optional[EventLedger]:
        """
        Broadcast analytics_refresh event when analytics updated.
        
        Args:
            meeting_id: Meeting ID
            analytics_data: Analytics information
            workspace_id: Workspace ID
            
        Returns:
            Created EventLedger instance or None
        """
        try:
            event = event_sequencer.create_event(
                event_type=EventType.ANALYTICS_REFRESH,
                event_name="Analytics Refreshed",
                payload={
                    'meeting_id': meeting_id,
                    'analytics': analytics_data,
                    'workspace_id': workspace_id
                },
                trace_id=f"analytics_{meeting_id}"
            )
            
            # Broadcast to analytics and dashboard namespaces
            self.emit_event(event, namespace="/analytics", room=f"workspace_{workspace_id}")
            self.emit_event(event, namespace="/dashboard", room=f"workspace_{workspace_id}")
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to broadcast analytics_refresh: {e}")
            return None
    
    def broadcast_dashboard_idle_sync(
        self,
        workspace_id: int,
        checksum_data: Dict[str, str]
    ) -> Optional[EventLedger]:
        """
        Broadcast dashboard_idle_sync for background cache validation.
        
        Args:
            workspace_id: Workspace ID
            checksum_data: Checksums for data validation
            
        Returns:
            Created EventLedger instance or None
        """
        try:
            event = event_sequencer.create_event(
                event_type=EventType.DASHBOARD_IDLE_SYNC,
                event_name="Dashboard Background Sync",
                payload={
                    'workspace_id': workspace_id,
                    'checksums': checksum_data,
                    'timestamp': datetime.utcnow().isoformat()
                },
                trace_id=f"sync_{workspace_id}_{int(datetime.utcnow().timestamp())}"
            )
            
            # Broadcast to dashboard namespace
            self.emit_event(event, namespace="/dashboard", room=f"workspace_{workspace_id}")
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to broadcast dashboard_idle_sync: {e}")
            return None
    
    def broadcast_meeting_update(
        self,
        meeting_id: int,
        meeting_data: Dict[str, Any],
        workspace_id: int
    ) -> Optional[EventLedger]:
        """
        Broadcast meeting_update event when meeting data changes.
        
        Args:
            meeting_id: Meeting ID
            meeting_data: Updated meeting information
            workspace_id: Workspace ID
            
        Returns:
            Created EventLedger instance or None
        """
        try:
            event = event_sequencer.create_event(
                event_type=EventType.MEETING_UPDATE,
                event_name="Meeting Updated",
                payload={
                    'meeting_id': meeting_id,
                    'meeting': meeting_data,
                    'workspace_id': workspace_id
                },
                trace_id=f"meeting_{meeting_id}"
            )
            
            # Broadcast to meetings and dashboard namespaces
            self.emit_event(event, namespace="/meetings", room=f"workspace_{workspace_id}")
            self.emit_event(event, namespace="/dashboard", room=f"workspace_{workspace_id}")
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to broadcast meeting_update: {e}")
            return None
    
    def broadcast_meeting_archived(
        self,
        workspace_id: int,
        meeting_id: int
    ) -> Optional[EventLedger]:
        """
        Broadcast meeting_archived event (CROWN⁴ Phase 4).
        
        Args:
            workspace_id: Workspace ID
            meeting_id: Meeting ID that was archived
            
        Returns:
            Created EventLedger instance or None
        """
        try:
            event = event_sequencer.create_event(
                event_type=EventType.SESSION_ARCHIVE,
                event_name="Meeting Archived",
                payload={
                    'workspace_id': workspace_id,
                    'meeting_id': meeting_id,
                    'timestamp': datetime.utcnow().isoformat()
                },
                trace_id=f"archived_{meeting_id}_{int(datetime.utcnow().timestamp())}"
            )
            
            # Broadcast to meetings and dashboard namespaces
            self.emit_event(event, namespace="/meetings", room=f"workspace_{workspace_id}")
            self.emit_event(event, namespace="/dashboard", room=f"workspace_{workspace_id}")
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to broadcast meeting_archived: {e}")
            return None
    
    def broadcast_meeting_restored(
        self,
        workspace_id: int,
        meeting_id: int
    ) -> Optional[EventLedger]:
        """
        Broadcast meeting_restored event (CROWN⁴ Phase 4).
        
        Args:
            workspace_id: Workspace ID
            meeting_id: Meeting ID that was restored
            
        Returns:
            Created EventLedger instance or None
        """
        try:
            event = event_sequencer.create_event(
                event_type=EventType.MEETING_UPDATE,
                event_name="Meeting Restored",
                payload={
                    'workspace_id': workspace_id,
                    'meeting_id': meeting_id,
                    'restored': True,
                    'timestamp': datetime.utcnow().isoformat()
                },
                trace_id=f"restored_{meeting_id}_{int(datetime.utcnow().timestamp())}"
            )
            
            # Broadcast to meetings and dashboard namespaces
            self.emit_event(event, namespace="/meetings", room=f"workspace_{workspace_id}")
            self.emit_event(event, namespace="/dashboard", room=f"workspace_{workspace_id}")
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to broadcast meeting_restored: {e}")
            return None
    
    def broadcast_dashboard_refresh(
        self,
        workspace_id: int,
        stats: Dict[str, Any]
    ) -> Optional[EventLedger]:
        """
        Broadcast dashboard_refresh event with updated statistics.
        
        Args:
            workspace_id: Workspace ID
            stats: Dashboard statistics (total_meetings, total_tasks, hours_saved, etc.)
            
        Returns:
            Created EventLedger instance or None
        """
        try:
            event = event_sequencer.create_event(
                event_type=EventType.DASHBOARD_REFRESH,
                event_name="Dashboard Statistics Refreshed",
                payload={
                    'workspace_id': workspace_id,
                    'stats': stats,
                    'timestamp': datetime.utcnow().isoformat()
                },
                trace_id=f"dashboard_{workspace_id}_{int(datetime.utcnow().timestamp())}"
            )
            
            # Broadcast to dashboard namespace
            self.emit_event(event, namespace="/dashboard", room=f"workspace_{workspace_id}")
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to broadcast dashboard_refresh: {e}")
            return None
    
    def broadcast_insight_reminder(
        self,
        user_id: int,
        workspace_id: int,
        reminder_data: Dict[str, Any]
    ) -> Optional[EventLedger]:
        """
        Broadcast insight_reminder event with AI-generated reminder (CROWN⁴ Phase 5).
        Uses predictive AI with 24-hour throttling to provide intelligent reminders.
        
        Args:
            user_id: User ID receiving the reminder
            workspace_id: Workspace ID
            reminder_data: Reminder information (title, message, action_url, type, confidence)
            
        Returns:
            Created EventLedger instance or None
        """
        try:
            event = event_sequencer.create_event(
                event_type=EventType.INSIGHT_REMINDER,
                event_name="AI Insight Reminder",
                payload={
                    'user_id': user_id,
                    'workspace_id': workspace_id,
                    'reminder': reminder_data,
                    'timestamp': datetime.utcnow().isoformat()
                },
                trace_id=f"insight_reminder_{user_id}_{int(datetime.utcnow().timestamp())}"
            )
            
            # Broadcast to dashboard namespace for this workspace
            self.emit_event(event, namespace="/dashboard", room=f"workspace_{workspace_id}")
            
            logger.info(f"Broadcast insight reminder for user {user_id}: {reminder_data.get('title', 'N/A')}")
            return event
            
        except Exception as e:
            logger.error(f"Failed to broadcast insight_reminder: {e}")
            return None
    
    def join_workspace_room(self, workspace_id: int, namespace: str = "/dashboard"):
        """
        Have client join workspace room for isolated broadcasts.
        
        Args:
            workspace_id: Workspace ID
            namespace: WebSocket namespace
        """
        if self.socketio:
            room = f"workspace_{workspace_id}"
            join_room(room, namespace=namespace)
            logger.debug(f"Client joined {namespace} room: {room}")
    
    def leave_workspace_room(self, workspace_id: int, namespace: str = "/dashboard"):
        """
        Have client leave workspace room.
        
        Args:
            workspace_id: Workspace ID
            namespace: WebSocket namespace
        """
        if self.socketio:
            room = f"workspace_{workspace_id}"
            leave_room(room, namespace=namespace)
            logger.debug(f"Client left {namespace} room: {room}")
    
    def process_pending_events(self, limit: int = 50):
        """
        Process pending events that need to be broadcast.
        This can be called periodically to ensure all events are broadcast.
        
        Args:
            limit: Maximum number of events to process
        """
        try:
            pending_events = event_sequencer.get_pending_events(limit=limit)
            
            if not pending_events:
                return
            
            logger.info(f"Processing {len(pending_events)} pending events for broadcast")
            
            for event in pending_events:
                # Determine namespace based on event type
                namespace = self._get_namespace_for_event(event.event_type)
                
                # Extract workspace_id from payload if available
                workspace_id = None
                if event.payload and isinstance(event.payload, dict):
                    workspace_id = event.payload.get('workspace_id')
                
                # Broadcast event
                room = f"workspace_{workspace_id}" if workspace_id else None
                self.emit_event(event, namespace=namespace, room=room)
                
        except Exception as e:
            logger.error(f"Failed to process pending events: {e}", exc_info=True)
    
    def _get_namespace_for_event(self, event_type: EventType) -> str:
        """
        Determine WebSocket namespace for event type.
        
        Args:
            event_type: EventType enum value
            
        Returns:
            Namespace string
        """
        # Map event types to namespaces
        namespace_map = {
            EventType.SESSION_UPDATE_CREATED: "/dashboard",
            EventType.SESSION_PREFETCH: "/dashboard",
            EventType.TASK_UPDATE: "/tasks",
            EventType.ANALYTICS_REFRESH: "/analytics",
            EventType.DASHBOARD_IDLE_SYNC: "/dashboard",
            EventType.MEETING_UPDATE: "/meetings",
            EventType.DASHBOARD_REFRESH: "/dashboard",
            EventType.FILTER_APPLY: "/dashboard",
            EventType.SESSION_ARCHIVE: "/dashboard",
            EventType.ARCHIVE_REVEAL: "/dashboard",
            EventType.WORKSPACE_SWITCH: "/dashboard",
            EventType.CACHE_INVALIDATE: "/dashboard",
        }
        
        return namespace_map.get(event_type, "/dashboard")


# Singleton instance (will be initialized with socketio in app.py)
event_broadcaster = EventBroadcaster()
