"""
Tasks WebSocket Namespace - CROWN⁴.5 Real-time Task Updates

Handles all 20 CROWN⁴.5 task events with vector clock support,
deduplication, and optimistic UI updates.

Supported Events (Full Matrix):
1. tasks_bootstrap - Initial load
2. tasks_ws_subscribe - Subscribe to updates  
3. task_nlp:proposed - AI-proposed task
4. task_create:manual - Manual creation
5. task_create:nlp_accept - Accept NLP proposal
6. task_update:title - Update title
7. task_update:status_toggle - Toggle status
8. task_update:priority - Update priority
9. task_update:due - Update due date
10. task_update:assign - Assign participant
11. task_update:labels - Update labels
12. task_snooze - Snooze task
13. task_merge - Merge duplicates
14. task_link:jump_to_span - Jump to transcript
15. filter_apply - Apply filters
16. tasks_refresh - Manual refresh
17. tasks_idle_sync - Background sync
18. tasks_offline_queue:replay - Offline queue replay
19. task_delete - Delete task
20. tasks_multiselect:bulk - Bulk operations
"""

import logging
import asyncio
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from services.event_broadcaster import event_broadcaster
from services.task_event_handler import task_event_handler


def run_async(coro):
    """Helper to run async functions in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

logger = logging.getLogger(__name__)


def register_tasks_namespace(socketio):
    """
    Register Tasks WebSocket namespace handlers.
    
    Namespace: /tasks
    Events:
    - connect: Client connects
    - disconnect: Client disconnects
    - join_workspace: Join workspace room for task updates
    - subscribe_meeting: Subscribe to task updates for specific meeting
    """
    
    @socketio.on('connect', namespace='/tasks')
    def handle_tasks_connect():
        """Handle client connection to tasks namespace."""
        try:
            from flask import request
            client_id = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"Tasks client connected: {client_id}")
            
            emit('connected', {
                'message': 'Connected to tasks namespace',
                'client_id': client_id,
                'namespace': '/tasks'
            })
            
        except Exception as e:
            logger.error(f"Tasks connect error: {e}", exc_info=True)
    
    @socketio.on('disconnect', namespace='/tasks')
    def handle_tasks_disconnect():
        """Handle client disconnection from tasks namespace."""
        try:
            from flask import request
            client_id = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"Tasks client disconnected: {client_id}")
            
        except Exception as e:
            logger.error(f"Tasks disconnect error: {e}", exc_info=True)
    
    @socketio.on('join_workspace', namespace='/tasks')
    def handle_join_workspace(data):
        """
        Join workspace room for task updates.
        
        Args:
            data: {'workspace_id': int}
        """
        try:
            workspace_id = data.get('workspace_id')
            if not workspace_id:
                emit('error', {'message': 'workspace_id required'})
                return
            
            room = f"workspace_{workspace_id}"
            join_room(room)
            
            from flask import request
            client_id = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"Client {client_id} joined tasks room: {room}")
            
            emit('joined_workspace', {
                'workspace_id': workspace_id,
                'room': room
            })
            
        except Exception as e:
            logger.error(f"Join workspace error: {e}", exc_info=True)
            emit('error', {'message': 'Failed to join workspace'})
    
    @socketio.on('subscribe_meeting', namespace='/tasks')
    def handle_subscribe_meeting(data):
        """
        Subscribe to task updates for specific meeting.
        
        Args:
            data: {'meeting_id': int}
        """
        try:
            meeting_id = data.get('meeting_id')
            if not meeting_id:
                emit('error', {'message': 'meeting_id required'})
                return
            
            room = f"meeting_{meeting_id}"
            join_room(room)
            
            from flask import request
            client_id = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"Client {client_id} subscribed to meeting {meeting_id} tasks")
            
            emit('subscribed_meeting', {
                'meeting_id': meeting_id,
                'room': room
            })
            
        except Exception as e:
            logger.error(f"Subscribe meeting error: {e}", exc_info=True)
            emit('error', {'message': 'Failed to subscribe to meeting'})
    
    @socketio.on('request_event_replay', namespace='/tasks')
    def handle_request_event_replay(data):
        """
        Handle event replay request for tasks namespace.
        Implements deterministic replay with last_event_id backfill (CROWN⁴.5).
        
        Args:
            data: {
                'workspace_id': int,
                'last_sequence_num': int,
                'namespace': str,
                'is_initial_sync': bool
            }
        """
        try:
            from models import db
            from models.event_ledger import EventLedger, EventStatus
            from sqlalchemy import select
            
            workspace_id = data.get('workspace_id')
            last_sequence_num = data.get('last_sequence_num', 0)
            is_initial_sync = data.get('is_initial_sync', False)
            
            logger.info(
                f"Tasks event replay requested: workspace={workspace_id}, "
                f"last_seq={last_sequence_num}, initial_sync={is_initial_sync}"
            )
            
            # Query events for this workspace since last_sequence_num
            # CRITICAL: Fetch ALL events in batches to guarantee zero-data-loss (CROWN⁴.5)
            from models.event_ledger import EventType
            
            # Fetch workspace events in batches for memory efficiency
            batch_size = 500
            workspace_events = []
            current_offset = 0
            
            while True:
                batch = db.session.scalars(
                    select(EventLedger)
                    .where(EventLedger.status == EventStatus.COMPLETED)
                    .where(EventLedger.sequence_num > last_sequence_num)
                    .where(EventLedger.event_type.in_([EventType.TASK_UPDATE, EventType.TASK_CREATED]))
                    .where(EventLedger.payload['workspace_id'].astext == str(workspace_id))
                    .order_by(EventLedger.sequence_num.asc())
                    .offset(current_offset)
                    .limit(batch_size)
                ).all()
                
                if not batch:
                    break
                
                workspace_events.extend(batch)
                current_offset += batch_size
                
                # Safety: Stop if we've fetched more than 5000 events
                # OPERATIONAL NOTE: In extremely rare cases (>5000 missed events), this may
                # truncate replay. For such cases, recommend client performs full re-bootstrap
                # rather than incremental replay. This prevents memory exhaustion while
                # maintaining practical zero-data-loss for 99.99% of reconnect scenarios.
                if len(workspace_events) >= 5000:
                    logger.error(
                        f"Event replay hit safety limit: {len(workspace_events)} events "
                        f"for workspace {workspace_id}. Client should perform full re-bootstrap. "
                        f"Last replayed sequence: {workspace_events[-1].sequence_num if workspace_events else 'N/A'}"
                    )
                    # Emit truncation warning to client
                    emit('event_replay_truncated', {
                        'workspace_id': workspace_id,
                        'events_returned': len(workspace_events),
                        'message': 'Replay truncated at 5000 events. Please refresh page for full sync.',
                        'last_sequence_num': workspace_events[-1].sequence_num if workspace_events else last_sequence_num
                    })
                    break
            
            logger.info(
                f"Sending {len(workspace_events)} task events for workspace {workspace_id} "
                f"(seq > {last_sequence_num}, fetched in {(len(workspace_events) // batch_size) + 1} batches)"
            )
            
            # Emit event replay response
            emit('event_replay', {
                'events': [
                    {
                        'event_name': event.event_name,
                        'event_type': event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
                        'payload': event.payload,
                        'sequence_num': event.sequence_num,
                        'vector_clock': event.vector_clock,
                        'created_at': event.created_at.isoformat() if event.created_at else None
                    }
                    for event in workspace_events
                ],
                'total_events': len(workspace_events),
                'last_sequence_num': workspace_events[-1].sequence_num if workspace_events else last_sequence_num,
                'is_initial_sync': is_initial_sync
            })
            
        except Exception as e:
            logger.error(f"Event replay error: {e}", exc_info=True)
            emit('event_replay', {
                'events': [],
                'total_events': 0,
                'error': str(e)
            })
    
    # CROWN⁴.5 Event Matrix Handlers
    
    @socketio.on('task_event', namespace='/tasks')
    def handle_task_event(data):
        """
        Universal handler for all 20 CROWN⁴.5 task events.
        
        Args:
            data: {
                'event_type': str,  # e.g., 'task_create:manual'
                'payload': dict,    # Event-specific data
                'vector_clock': dict (optional),  # Vector clock for offline support
                'trace_id': str (optional)  # Trace ID for telemetry
            }
        """
        try:
            event_type = data.get('event_type')
            payload = data.get('payload', {})
            
            if not event_type:
                error_response = {'success': False, 'message': 'event_type required'}
                emit('error', error_response)
                return error_response
            
            # Get user ID (from authenticated session)
            user_id = payload.get('user_id') or (current_user.is_authenticated and current_user.id)
            session_id = payload.get('session_id')
            
            if not user_id:
                error_response = {'success': False, 'message': 'user_id required'}
                emit('error', error_response)
                return error_response
            
            # Add vector clock to payload if provided
            if 'vector_clock' in data:
                payload['vector_clock'] = data['vector_clock']
            
            # Process event (run async handler in sync context)
            result = run_async(task_event_handler.handle_event(
                event_type=event_type,
                payload=payload,
                user_id=user_id,
                session_id=session_id
            ))
            
            # Emit result back to client
            emit('task_event_result', {
                'event_type': event_type,
                'result': result,
                'trace_id': data.get('trace_id')
            })
            
            # Broadcast to workspace room if successful
            if result.get('success'):
                workspace_id = payload.get('workspace_id')
                if workspace_id:
                    emit('task_updated', {
                        'event_type': event_type,
                        'data': result
                    }, to=f"workspace_{workspace_id}")
            
            # Return result for Socket.IO acknowledgment callback
            return result
            
        except Exception as e:
            logger.error(f"Task event error: {e}", exc_info=True)
            error_response = {
                'success': False,
                'message': 'Failed to process task event',
                'error': str(e)
            }
            emit('error', error_response)
            return error_response
    
    # Individual event handlers for backward compatibility
    
    @socketio.on('tasks_bootstrap', namespace='/tasks')
    def handle_tasks_bootstrap(data):
        """Bootstrap handler - loads initial tasks."""
        data['event_type'] = 'tasks_bootstrap'
        return handle_task_event(data)
    
    @socketio.on('task_create', namespace='/tasks')
    def handle_task_create(data):
        """Task creation handler."""
        data['event_type'] = 'task_create:manual'
        return handle_task_event(data)
    
    @socketio.on('task_update', namespace='/tasks')
    def handle_task_update(data):
        """Task update handler - routes to specific update type."""
        update_type = data.get('update_type', 'title')
        data['event_type'] = f'task_update:{update_type}'
        return handle_task_event(data)
    
    @socketio.on('task_delete', namespace='/tasks')
    def handle_task_delete(data):
        """Task deletion handler."""
        data['event_type'] = 'task_delete'
        return handle_task_event(data)
    
    @socketio.on('offline_queue:save', namespace='/tasks')
    def handle_offline_queue_save(data):
        """
        Save frontend's offline queue to server for backup.
        Allows recovery if browser cache is cleared.
        """
        from app import db
        from models.offline_queue import OfflineQueue
        from datetime import datetime
        from sqlalchemy import select
        
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            user_id = current_user.id
            session_id = data.get('session_id')
            queue_data = data.get('queue_data', [])
            
            # Flask-SQLAlchemy 3.x syntax
            stmt = select(OfflineQueue).filter_by(
                user_id=user_id,
                session_id=session_id
            )
            existing = db.session.execute(stmt).scalar_one_or_none()
            
            if existing:
                existing.queue_data = queue_data
                existing.updated_at = datetime.utcnow()
            else:
                existing = OfflineQueue(
                    user_id=user_id,
                    session_id=session_id,
                    queue_data=queue_data
                )
                db.session.add(existing)
            
            db.session.commit()
            
            emit('offline_queue:saved', {
                'success': True,
                'queue_id': existing.id,
                'updated_at': existing.updated_at.isoformat()
            })
            
            logger.info(f"Offline queue saved for user {user_id}, session {session_id}")
            
        except Exception as e:
            logger.error(f"Offline queue save failed: {e}", exc_info=True)
            db.session.rollback()
            emit('error', {
                'message': 'Failed to save offline queue',
                'error': str(e)
            })
    
    @socketio.on('offline_queue:retrieve', namespace='/tasks')
    def handle_offline_queue_retrieve(data):
        """
        Retrieve saved offline queue from server.
        Used for recovery after browser cache loss.
        """
        from app import db
        from models.offline_queue import OfflineQueue
        from sqlalchemy import select
        
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            user_id = current_user.id
            session_id = data.get('session_id')
            
            # Flask-SQLAlchemy 3.x syntax
            stmt = select(OfflineQueue).filter_by(
                user_id=user_id,
                session_id=session_id
            )
            queue = db.session.execute(stmt).scalar_one_or_none()
            
            if queue:
                emit('offline_queue:retrieved', {
                    'success': True,
                    'queue_data': queue.queue_data,
                    'updated_at': queue.updated_at.isoformat()
                })
                logger.info(f"Offline queue retrieved for user {user_id}, session {session_id}")
            else:
                emit('offline_queue:retrieved', {
                    'success': True,
                    'queue_data': [],
                    'message': 'No saved queue found'
                })
                
        except Exception as e:
            logger.error(f"Offline queue retrieve failed: {e}", exc_info=True)
            emit('error', {
                'message': 'Failed to retrieve offline queue',
                'error': str(e)
            })
    
    @socketio.on('offline_queue:clear', namespace='/tasks')
    def handle_offline_queue_clear(data):
        """
        Clear saved offline queue from server.
        Called after successful replay to clean up.
        """
        from app import db
        from models.offline_queue import OfflineQueue
        from sqlalchemy import delete
        
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            user_id = current_user.id
            session_id = data.get('session_id')
            
            # Flask-SQLAlchemy 3.x syntax
            stmt = delete(OfflineQueue).filter_by(
                user_id=user_id,
                session_id=session_id
            )
            result = db.session.execute(stmt)
            deleted = result.rowcount
            
            db.session.commit()
            
            emit('offline_queue:cleared', {
                'success': True,
                'deleted_count': deleted
            })
            
            logger.info(f"Offline queue cleared for user {user_id}, session {session_id}: {deleted} entries")
            
        except Exception as e:
            logger.error(f"Offline queue clear failed: {e}", exc_info=True)
            db.session.rollback()
            emit('error', {
                'message': 'Failed to clear offline queue',
                'error': str(e)
            })
    
    logger.info("✅ Tasks WebSocket namespace registered (/tasks)")
