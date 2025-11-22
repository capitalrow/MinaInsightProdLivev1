"""
CROWN⁹ Copilot WebSocket Namespace

Handles real-time streaming for AI Copilot with event lifecycle management.

Events:
1. connect - Client connects to copilot namespace
2. copilot_bootstrap - Initialize context hydration
3. copilot_query - Stream AI response
4. copilot_action - Execute action (task, meeting, calendar)
5. disconnect - Client disconnects
"""

import logging
import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from services.copilot_streaming_service import copilot_streaming_service
from services.event_broadcaster import event_broadcaster
from services.copilot_lifecycle_service import (
    copilot_lifecycle_service,
    LifecycleEvent
)
from services.copilot_memory_service import copilot_memory_service

logger = logging.getLogger(__name__)


def get_socket_sid() -> str:
    """Get Socket.IO session ID from request context."""
    return request.sid  # type: ignore[attr-defined]


def register_copilot_namespace(socketio):
    """
    Register Copilot WebSocket namespace handlers.
    
    Namespace: /copilot
    Handles: streaming responses, context hydration, action execution
    """
    
    @socketio.on('connect', namespace='/copilot')
    def handle_copilot_connect():
        """Handle client connection to copilot namespace."""
        try:
            client_id = get_socket_sid()
            user_id = current_user.id if current_user.is_authenticated else None
            
            logger.info(f"Copilot client connected: {client_id}, user={user_id}")
            
            emit('connected', {
                'message': 'Connected to Mina Copilot',
                'client_id': client_id,
                'namespace': '/copilot',
                'timestamp': str(asyncio.get_event_loop().time()) if hasattr(asyncio, 'get_event_loop') else None
            })
            
        except Exception as e:
            logger.error(f"Copilot connect error: {e}", exc_info=True)
            emit('error', {'message': 'Connection failed', 'error': str(e)})
    
    @socketio.on('disconnect', namespace='/copilot')
    def handle_copilot_disconnect():
        """Handle client disconnection from copilot namespace."""
        try:
            client_id = get_socket_sid()
            logger.info(f"Copilot client disconnected: {client_id}")
            
            # Cleanup lifecycle session for this client
            if current_user.is_authenticated:
                session_id = f"copilot_{current_user.id}_{client_id}"
                copilot_lifecycle_service.destroy_session(session_id)
                logger.debug(f"Destroyed lifecycle session: {session_id}")
            
            # Leave workspace room on disconnect
            if current_user.is_authenticated and current_user.workspace_id:
                room_name = f"copilot_workspace_{current_user.workspace_id}"
                leave_room(room_name)
                logger.debug(f"Left copilot room: {room_name}")
            
        except Exception as e:
            logger.error(f"Copilot disconnect error: {e}", exc_info=True)
    
    @socketio.on('copilot_bootstrap', namespace='/copilot')
    def handle_copilot_bootstrap(data: Dict[str, Any]):
        """
        Handle copilot bootstrap event (Event #1 in CROWN⁹ lifecycle).
        
        Loads user memory, embeddings, and recent events for context hydration.
        
        Args:
            data: {
                'workspace_id': int,
                'load_context': bool (default True),
                'session_id': str (optional)
            }
        """
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            workspace_id = data.get('workspace_id') or current_user.workspace_id
            load_context = data.get('load_context', True)
            session_id = data.get('session_id') or f"copilot_{current_user.id}_{get_socket_sid()}"
            
            logger.info(f"Copilot bootstrap: user={current_user.id}, workspace={workspace_id}, session={session_id}")
            
            # Create lifecycle session (Event #1)
            lifecycle_state = copilot_lifecycle_service.create_session(
                session_id=session_id,
                user_id=current_user.id,
                workspace_id=workspace_id
            )
            
            # Join workspace room for cross-surface sync
            if workspace_id:
                room_name = f"copilot_workspace_{workspace_id}"
                join_room(room_name)
                logger.debug(f"Joined copilot room: {room_name}")
            
            # Build initial context
            context = {}
            if load_context:
                context = _build_user_context(current_user.id, workspace_id)
            
            # Emit Event #1: copilot_bootstrap
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.COPILOT_BOOTSTRAP,
                data={'context': context}
            )
            
            # Emit Event #2: context_rehydrate
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.CONTEXT_REHYDRATE,
                data={'active_sessions': True}
            )
            
            # Emit bootstrap complete with context
            emit('copilot_bootstrap_complete', {
                'event': 'copilot_bootstrap',
                'context': context,
                'workspace_id': workspace_id,
                'user_id': current_user.id,
                'session_id': session_id,
                'timestamp': time.time()
            })
            
            # Generate adaptive chips (Event #3)
            chips = _generate_contextual_chips(context, current_user.id, workspace_id)
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.CHIPS_GENERATE,
                data={'chips': chips}
            )
            
            # Emit chips to client
            emit('copilot_chips_generated', {
                'chips': chips,
                'session_id': session_id
            })
            
        except Exception as e:
            logger.error(f"Copilot bootstrap error: {e}", exc_info=True)
            emit('error', {'message': 'Bootstrap failed', 'error': str(e)})
    
    @socketio.on('copilot_query', namespace='/copilot')
    def handle_copilot_query(data: Dict[str, Any]):
        """
        Handle copilot query with streaming response.
        
        Args:
            data: {
                'message': str,  # User query
                'context': dict,  # Optional context filter
                'session_id': str  # Optional conversation session
            }
        """
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            user_message = data.get('message', '').strip()
            if not user_message:
                emit('error', {'message': 'Message is required'})
                return
            
            workspace_id = current_user.workspace_id
            context_data = data.get('context', {})
            session_id = data.get('session_id') or f"copilot_{current_user.id}_{get_socket_sid()}"
            client_sid = get_socket_sid()
            
            logger.info(f"Copilot query: user={current_user.id}, message='{user_message[:50]}...', session={session_id}")
            
            # Event #5: query_detect
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.QUERY_DETECT,
                data={'message': user_message}
            )
            
            # Event #6: context_merge - Build context from workspace data
            context = _build_query_context(current_user.id, workspace_id, context_data)
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.CONTEXT_MERGE,
                data={'context_keys': list(context.keys())}
            )
            
            # Event #7: reasoning_stream - Stream response using background task (eventlet-safe)
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.REASONING_STREAM,
                data={'started': True}
            )
            
            def stream_task():
                """Background task for streaming response (uses dedicated async thread)."""
                try:
                    complete_message = ""
                    
                    # Use eventlet-safe streaming (async in dedicated thread, queue-based communication)
                    for event in copilot_streaming_service.stream_response_eventlet_safe(
                        user_message=user_message,
                        context=context,
                        workspace_id=workspace_id,
                        user_id=current_user.id
                    ):
                        # Emit streaming event to specific client
                        socketio.emit('copilot_stream', event, namespace='/copilot', to=client_sid)
                        
                        # Capture complete message
                        if event.get('type') == 'complete':
                            complete_message = event.get('message', '')
                    
                    # Event #8: response_commit - Persist reply
                    copilot_lifecycle_service.emit_event(
                        session_id=session_id,
                        event=LifecycleEvent.RESPONSE_COMMIT,
                        data={'message_length': len(complete_message)}
                    )
                    
                    # Event #11: context_retrain - Learn from interaction
                    copilot_lifecycle_service.emit_event(
                        session_id=session_id,
                        event=LifecycleEvent.CONTEXT_RETRAIN,
                        data={'started': True}
                    )
                    
                    # Store conversation and update embeddings
                    copilot_memory_service.retrain_context(
                        user_id=current_user.id,
                        workspace_id=workspace_id,
                        interaction_data={
                            'message': user_message,
                            'response': complete_message,
                            'success': True
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Stream task error: {e}", exc_info=True)
                    socketio.emit('copilot_stream', {
                        'type': 'error',
                        'content': 'Streaming failed',
                        'error': str(e)
                    }, namespace='/copilot', to=client_sid)
            
            # Start background task (eventlet-safe)
            socketio.start_background_task(stream_task)
            
        except Exception as e:
            logger.error(f"Copilot query error: {e}", exc_info=True)
            emit('copilot_stream', {
                'type': 'error',
                'content': 'Failed to process query',
                'error': str(e)
            })
    
    @socketio.on('copilot_action', namespace='/copilot')
    def handle_copilot_action(data: Dict[str, Any]):
        """
        Execute action from copilot (Event #9 in CROWN⁹ lifecycle).
        
        Triggers cross-surface broadcast to update Dashboard, Tasks, Calendar, Analytics.
        
        Args:
            data: {
                'action': str,  # create_task, mark_done, add_to_calendar, etc.
                'parameters': dict,
                'workspace_id': int
            }
        """
        try:
            if not current_user.is_authenticated:
                emit('error', {'message': 'Authentication required'})
                return
            
            action = data.get('action')
            if not action:
                emit('copilot_action_result', {'success': False, 'error': 'Action is required'})
                return
                
            parameters = data.get('parameters', {})
            workspace_id = data.get('workspace_id') or current_user.workspace_id
            session_id = data.get('session_id') or f"copilot_{current_user.id}_{get_socket_sid()}"
            
            logger.info(f"Copilot action: user={current_user.id}, action={action}, session={session_id}")
            
            # Event #9: action_trigger - Execute mutation
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.ACTION_TRIGGER,
                data={'action': action, 'parameters': parameters}
            )
            
            # Execute action and get result
            result = _execute_copilot_action(
                action=action,
                parameters=parameters,
                user_id=current_user.id,
                workspace_id=workspace_id
            )
            
            # Event #10: cross_surface_sync - Broadcast to other pages
            if result.get('success'):
                copilot_lifecycle_service.emit_event(
                    session_id=session_id,
                    event=LifecycleEvent.CROSS_SURFACE_SYNC,
                    data={'action': action, 'broadcast': True}
                )
                _broadcast_action_result(
                    action=action,
                    result=result,
                    workspace_id=workspace_id
                )
            
            # Emit action result
            emit('copilot_action_result', {
                'action': action,
                'success': result.get('success', False),
                'result': result,
                'session_id': session_id,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Copilot action error: {e}", exc_info=True)
            emit('copilot_action_result', {
                'success': False,
                'error': str(e)
            })


def _build_user_context(user_id: int, workspace_id: Optional[int]) -> Dict[str, Any]:
    """
    Build initial context for copilot bootstrap.
    
    Loads:
    - Recent tasks (last 10)
    - Recent meetings (last 5)
    - User preferences
    - Activity summary
    """
    from models import db, Task, Meeting, User
    from datetime import datetime, timedelta
    
    context = {
        'loaded_at': datetime.utcnow().isoformat(),
        'user_id': user_id,
        'workspace_id': workspace_id
    }
    
    try:
        # Get user
        user = db.session.get(User, user_id)
        if not user:
            return context
        
        # Recent tasks
        if workspace_id:
            recent_tasks = db.session.query(Task)\
                .filter(Task.workspace_id == workspace_id)\
                .filter(Task.deleted_at.is_(None))\
                .order_by(Task.created_at.desc())\
                .limit(10)\
                .all()
            
            context['recent_tasks'] = [
                {
                    'id': t.id,
                    'title': t.title,
                    'status': t.status,
                    'priority': t.priority,
                    'due_date': t.due_date.isoformat() if t.due_date else None
                }
                for t in recent_tasks
            ]
        
        # Recent meetings
        if workspace_id:
            recent_meetings = db.session.query(Meeting)\
                .filter(Meeting.workspace_id == workspace_id)\
                .order_by(Meeting.created_at.desc())\
                .limit(5)\
                .all()
            
            context['recent_meetings'] = [
                {
                    'id': m.id,
                    'title': m.title,
                    'created_at': m.created_at.isoformat()
                }
                for m in recent_meetings
            ]
        
        # Activity summary
        today = datetime.utcnow().date()
        context['activity'] = {
            'tasks_today': len([t for t in context.get('recent_tasks', []) 
                              if t.get('due_date') and t['due_date'].startswith(today.isoformat())]),
            'meetings_today': 0  # TODO: Filter by meeting date
        }
        
    except Exception as e:
        logger.error(f"Error building context: {e}", exc_info=True)
    
    return context


def _build_query_context(
    user_id: int,
    workspace_id: Optional[int],
    context_filter: Dict[str, Any]
) -> Dict[str, Any]:
    """Build context for specific query based on context filter."""
    # Start with base context
    context = _build_user_context(user_id, workspace_id)
    
    # Apply additional filters if provided
    # TODO: Implement context filtering based on user preferences
    
    return context


def _generate_contextual_chips(
    context: Dict[str, Any],
    user_id: int,
    workspace_id: Optional[int]
) -> List[Dict[str, str]]:
    """
    Generate adaptive quick-action chips based on workspace context (Event #3).
    
    Chips adapt dynamically based on:
    - Overdue tasks
    - Upcoming deadlines
    - Recent meetings
    - Activity patterns
    
    Args:
        context: Workspace context from bootstrap
        user_id: Current user ID
        workspace_id: Current workspace ID
    
    Returns:
        List of chip objects with text and action
    """
    from datetime import datetime
    
    chips = []
    
    # Always include base chips
    chips.append({'text': "What's due today?", 'action': 'query'})
    
    # Check for overdue tasks
    recent_tasks = context.get('recent_tasks', [])
    overdue_count = sum(
        1 for t in recent_tasks 
        if t.get('status') != 'completed' and 
           t.get('due_date') and 
           t['due_date'] < datetime.utcnow().isoformat()
    )
    
    if overdue_count > 0:
        chips.insert(0, {
            'text': f"Show {overdue_count} overdue tasks",
            'action': 'query',
            'priority': 'high'
        })
    
    # Recent meetings chip
    recent_meetings = context.get('recent_meetings', [])
    if recent_meetings:
        chips.append({
            'text': "Summarize yesterday's meetings",
            'action': 'query'
        })
    
    # Tasks due today
    tasks_today = context.get('activity', {}).get('tasks_today', 0)
    if tasks_today > 0:
        chips.append({
            'text': f"Review {tasks_today} tasks due today",
            'action': 'query'
        })
    
    # General insights
    chips.extend([
        {'text': "Show blockers", 'action': 'query'},
        {'text': "What decisions were made?", 'action': 'query'}
    ])
    
    # Limit to 6 chips
    return chips[:6]


def _execute_copilot_action(
    action: str,
    parameters: Dict[str, Any],
    user_id: int,
    workspace_id: Optional[int]
) -> Dict[str, Any]:
    """
    Execute copilot action.
    
    Supported actions:
    - create_task
    - mark_done
    - add_to_calendar
    - schedule_meeting
    """
    from models import db, Task
    from datetime import datetime
    
    try:
        if action == 'create_task':
            # Create new task
            task = Task(
                title=parameters.get('title', 'Untitled Task'),
                workspace_id=workspace_id,
                created_by_id=user_id,
                status='pending',
                priority=parameters.get('priority', 'medium'),
                due_date=parameters.get('due_date')
            )
            db.session.add(task)
            db.session.commit()
            
            return {
                'success': True,
                'task_id': task.id,
                'task': {
                    'id': task.id,
                    'title': task.title,
                    'status': task.status
                }
            }
        
        elif action == 'mark_done':
            # Mark task as complete
            task_id = parameters.get('task_id')
            task = db.session.get(Task, task_id)
            
            if task and task.workspace_id == workspace_id:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                db.session.commit()
                
                return {
                    'success': True,
                    'task_id': task.id
                }
        
        # Add more actions as needed
        
        return {'success': False, 'error': f'Unknown action: {action}'}
        
    except Exception as e:
        logger.error(f"Action execution error: {e}", exc_info=True)
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def _broadcast_action_result(
    action: str,
    result: Dict[str, Any],
    workspace_id: Optional[int]
):
    """
    Broadcast action result to other surfaces for cross-surface sync.
    
    Channels:
    - /tasks - Task namespace
    - /calendar - Calendar namespace
    - /dashboard - Dashboard namespace
    """
    from app import socketio
    
    try:
        # Determine broadcast namespace and event based on action
        if action in ['create_task', 'mark_done', 'update_task']:
            # Broadcast to tasks namespace
            if workspace_id:
                room_name = f"workspace_{workspace_id}"
                socketio.emit(
                    'task_updated',
                    result,
                    namespace='/tasks',
                    to=room_name
                )
        
        elif action in ['add_to_calendar', 'schedule_meeting']:
            # Broadcast to calendar namespace
            if workspace_id:
                room_name = f"workspace_{workspace_id}"
                socketio.emit(
                    'calendar_updated',
                    result,
                    namespace='/calendar',
                    to=room_name
                )
        
        # Also broadcast to dashboard for unified updates
        if workspace_id:
            room_name = f"workspace_{workspace_id}"
            socketio.emit(
                'copilot_action_completed',
                {
                    'action': action,
                    'result': result
                },
                namespace='/dashboard',
                to=room_name
            )
        
        logger.debug(f"Broadcast {action} to workspace {workspace_id}")
        
    except Exception as e:
        logger.error(f"Broadcast error: {e}", exc_info=True)
