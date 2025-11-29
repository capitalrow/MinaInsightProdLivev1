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
from services.copilot_intent_classifier import copilot_intent_classifier
from services.copilot_chip_generator import copilot_chip_generator
from services.copilot_security import copilot_security, AuditAction
from services.copilot_error_handler import copilot_error_handler, CopilotError, ErrorCategory
from services.copilot_metrics_collector import copilot_metrics_collector

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
                
                # Mark session inactive in metrics collector
                copilot_metrics_collector.track_session(session_id, active=False)
                
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
                copilot_security.audit_log_event(
                    action=AuditAction.AUTH,
                    user_id=None,
                    details={'event': 'copilot_bootstrap', 'result': 'unauthorized'},
                    success=False
                )
                return
            
            workspace_id = data.get('workspace_id') or current_user.workspace_id
            load_context = data.get('load_context', True)
            session_id = data.get('session_id') or f"copilot_{current_user.id}_{get_socket_sid()}"
            
            logger.info(f"Copilot bootstrap: user={current_user.id}, workspace={workspace_id}, session={session_id}")
            
            # Track session in metrics
            copilot_metrics_collector.track_session(session_id, active=True)
            
            # Audit successful bootstrap
            copilot_security.audit_log_event(
                action=AuditAction.AUTH,
                user_id=current_user.id,
                details={'event': 'copilot_bootstrap', 'session_id': session_id, 'workspace_id': workspace_id},
                success=True
            )
            
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
            
            # Event #3: Generate smart chips
            chips = copilot_chip_generator.generate_chips(
                user_id=current_user.id,
                workspace_id=workspace_id,
                context={'page': 'dashboard'}
            )
            
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.CHIPS_GENERATE,
                data={'chips': [chip.to_dict() for chip in chips]}
            )
            
            # Broadcast chips to client
            emit('copilot_chips_generated', {
                'chips': [chip.to_dict() for chip in chips],
                'session_id': session_id
            })
            
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
            
            # Sanitize user input for security
            user_message = copilot_security.sanitize_input(user_message)
            
            # Audit query
            copilot_security.audit_log_event(
                action=AuditAction.QUERY,
                user_id=current_user.id,
                details={'session_id': session_id, 'message_preview': user_message[:100]},
                success=True
            )
            
            # Classify intent (Task 5: Intent Classification)
            classification = copilot_intent_classifier.classify(user_message)
            logger.debug(f"Intent classified: {classification.intent.value}, confidence={classification.confidence:.2f}")
            
            # Event #5: query_detect
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.QUERY_DETECT,
                data={
                    'message': user_message,
                    'intent': classification.intent.value,
                    'confidence': classification.confidence,
                    'entities': [e.to_dict() for e in classification.entities]
                }
            )
            
            # Event #6: context_merge - Build context from workspace data
            context = _build_query_context(current_user.id, workspace_id, context_data)
            
            # Add intent classification to context for response generation
            context['intent'] = classification.to_dict()
            
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.CONTEXT_MERGE,
                data={
                    'context_keys': list(context.keys()),
                    'intent': classification.intent.value,
                    'has_entities': len(classification.entities) > 0
                }
            )
            
            # Event #7: reasoning_stream - Stream response using background task (eventlet-safe)
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.REASONING_STREAM,
                data={'started': True}
            )
            
            # Capture user_id before background task (Flask-Login context not available in background tasks)
            captured_user_id = current_user.id
            
            def stream_task():
                """Background task for streaming response (uses dedicated async thread)."""
                try:
                    complete_message = ""
                    
                    # Use eventlet-safe streaming (async in dedicated thread, queue-based communication)
                    for event in copilot_streaming_service.stream_response_eventlet_safe(
                        user_message=user_message,
                        context=context,
                        workspace_id=workspace_id,
                        user_id=captured_user_id
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
                        user_id=captured_user_id,
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
            
            # Handle error with graceful degradation
            error_session_id = data.get('session_id', 'unknown') if data else 'unknown'
            error_user_message = data.get('message', '')[:100] if data else ''
            error_user_id = current_user.id if current_user and current_user.is_authenticated else None
            error_response = copilot_error_handler.handle_error(
                error=e,
                context={'session_id': error_session_id, 'user_message': error_user_message},
                user_id=error_user_id
            )
            
            # Record error in metrics
            copilot_metrics_collector.record_error(
                error_type=type(e).__name__,
                severity='high'
            )
            
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
                    workspace_id=workspace_id,
                    user_id=current_user.id
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
    Build initial context for copilot bootstrap with comprehensive data and proactive insights.
    
    CROWN⁹ Enhanced Context Building:
    - Recent tasks (last 10) with overdue detection
    - Recent meetings (last 5) with insights
    - Proactive blockers and alerts
    - User preferences and patterns
    - Activity summary with trends
    """
    from models import db, Task, Meeting, User
    from datetime import datetime, timedelta, date
    
    context = {
        'loaded_at': datetime.utcnow().isoformat(),
        'user_id': user_id,
        'workspace_id': workspace_id,
        'recent_tasks': [],
        'recent_meetings': [],
        'proactive_insights': [],
        'blockers': [],
        'activity': {}
    }
    
    try:
        # Defensive null guard for user_id
        if not user_id:
            logger.warning("No user_id provided for context building")
            return context
        
        # Get user with null guard
        user = db.session.get(User, user_id)
        if not user:
            logger.warning(f"User {user_id} not found")
            return context
        
        context['user_name'] = getattr(user, 'display_name', None) or getattr(user, 'username', 'User')
        
        # Recent tasks with comprehensive data
        if workspace_id:
            try:
                recent_tasks = db.session.query(Task)\
                    .filter(Task.workspace_id == workspace_id)\
                    .filter(Task.deleted_at.is_(None))\
                    .order_by(Task.created_at.desc())\
                    .limit(10)\
                    .all()
                
                today = date.today()
                overdue_tasks = []
                due_soon_tasks = []
                blocked_tasks = []
                
                for t in recent_tasks:
                    if t is None:
                        continue
                    
                    due_date_val = getattr(t, 'due_date', None)
                    task_data = {
                        'id': getattr(t, 'id', None),
                        'title': getattr(t, 'title', 'Untitled'),
                        'status': getattr(t, 'status', 'todo'),
                        'priority': getattr(t, 'priority', 'medium'),
                        'due_date': due_date_val.isoformat() if due_date_val else None,
                        'is_overdue': False,
                        'is_due_soon': False
                    }
                    
                    # Detect overdue tasks
                    if t.due_date and t.status not in ['completed', 'cancelled']:
                        if t.due_date < today:
                            task_data['is_overdue'] = True
                            overdue_tasks.append(task_data)
                        elif (t.due_date - today).days <= 3:
                            task_data['is_due_soon'] = True
                            due_soon_tasks.append(task_data)
                    
                    # Detect blocked tasks
                    if t.status == 'blocked':
                        blocked_tasks.append(task_data)
                    
                    context['recent_tasks'].append(task_data)
                
                # Add proactive insights
                if overdue_tasks:
                    context['proactive_insights'].append({
                        'type': 'overdue_alert',
                        'severity': 'high',
                        'message': f"You have {len(overdue_tasks)} overdue task{'s' if len(overdue_tasks) > 1 else ''}",
                        'count': len(overdue_tasks),
                        'tasks': overdue_tasks[:3]  # Top 3
                    })
                
                if due_soon_tasks:
                    context['proactive_insights'].append({
                        'type': 'due_soon_alert',
                        'severity': 'medium',
                        'message': f"{len(due_soon_tasks)} task{'s' if len(due_soon_tasks) > 1 else ''} due in the next 3 days",
                        'count': len(due_soon_tasks),
                        'tasks': due_soon_tasks[:3]
                    })
                
                if blocked_tasks:
                    context['blockers'] = blocked_tasks
                    context['proactive_insights'].append({
                        'type': 'blocker_alert',
                        'severity': 'high',
                        'message': f"{len(blocked_tasks)} task{'s' if len(blocked_tasks) > 1 else ''} blocked",
                        'count': len(blocked_tasks)
                    })
                    
            except Exception as task_error:
                logger.error(f"Error loading tasks: {task_error}", exc_info=True)
        
        # Recent meetings with null guards
        if workspace_id:
            try:
                recent_meetings = db.session.query(Meeting)\
                    .filter(Meeting.workspace_id == workspace_id)\
                    .order_by(Meeting.created_at.desc())\
                    .limit(5)\
                    .all()
                
                for m in recent_meetings:
                    if m is None:
                        continue
                    
                    meeting_data = {
                        'id': getattr(m, 'id', None),
                        'title': getattr(m, 'title', 'Untitled Meeting'),
                        'created_at': m.created_at.isoformat() if getattr(m, 'created_at', None) else None,
                        'has_transcript': bool(getattr(m, 'transcript', None)),
                        'has_summary': bool(getattr(m, 'summary', None))
                    }
                    context['recent_meetings'].append(meeting_data)
                    
            except Exception as meeting_error:
                logger.error(f"Error loading meetings: {meeting_error}", exc_info=True)
        
        # Activity summary with trends
        today = datetime.utcnow().date()
        tasks_today = len([t for t in context.get('recent_tasks', []) 
                          if t.get('due_date') and t['due_date'].startswith(today.isoformat())])
        
        completed_recently = len([t for t in context.get('recent_tasks', []) 
                                 if t.get('status') == 'completed'])
        
        context['activity'] = {
            'tasks_today': tasks_today,
            'tasks_completed_recently': completed_recently,
            'meetings_this_week': len(context.get('recent_meetings', [])),
            'productivity_score': min(100, completed_recently * 10 + 50) if completed_recently else 50
        }
        
        # Add productivity insight
        if completed_recently >= 3:
            context['proactive_insights'].append({
                'type': 'productivity_positive',
                'severity': 'low',
                'message': f"Great progress! You've completed {completed_recently} tasks recently."
            })
        
    except Exception as e:
        logger.error(f"Error building context: {e}", exc_info=True)
    
    return context


def _build_query_context(
    user_id: int,
    workspace_id: Optional[int],
    context_filter: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build context for specific query with semantic RAG retrieval.
    
    CROWN⁹ Enhanced Query Context:
    - Base workspace context (tasks, meetings)
    - Semantic context from embeddings (RAG)
    - Conversation history for continuity
    - Intent-specific context filtering
    """
    # Start with base context
    context = _build_user_context(user_id, workspace_id)
    
    try:
        # Retrieve semantic context using RAG (embeddings-based similarity)
        query_text = context_filter.get('query', '') or context_filter.get('message', '')
        
        if query_text and user_id:
            semantic_contexts = copilot_memory_service.get_semantic_context(
                query=query_text,
                user_id=user_id,
                workspace_id=workspace_id,
                limit=5
            )
            
            if semantic_contexts:
                context['semantic_context'] = semantic_contexts
                context['rag_enabled'] = True
                logger.debug(f"RAG retrieved {len(semantic_contexts)} relevant contexts")
        
        # Get recent conversation history for continuity
        recent_conversations = copilot_memory_service.get_recent_conversations(
            user_id=user_id,
            workspace_id=workspace_id,
            limit=5
        )
        
        if recent_conversations:
            context['conversation_history'] = recent_conversations
        
        # Apply intent-specific filters
        intent_type = context_filter.get('intent_type')
        if intent_type:
            context = _apply_intent_filter(context, intent_type, context_filter)
        
    except Exception as e:
        logger.error(f"Error building query context with RAG: {e}", exc_info=True)
    
    return context


def _apply_intent_filter(
    context: Dict[str, Any],
    intent_type: str,
    context_filter: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply intent-specific filtering to context.
    
    Optimizes context for different query types:
    - task_query: Focus on tasks
    - meeting_summary: Focus on meetings
    - calendar_query: Focus on calendar
    - analytics_query: Focus on metrics
    """
    if intent_type == 'task_query':
        # For task queries, prioritize task data
        context['focus'] = 'tasks'
        # Filter to relevant tasks only
        status_filter = context_filter.get('status')
        if status_filter and context.get('recent_tasks'):
            context['recent_tasks'] = [
                t for t in context['recent_tasks'] 
                if t.get('status') == status_filter
            ]
    
    elif intent_type == 'meeting_summary':
        # For meeting queries, prioritize meeting data
        context['focus'] = 'meetings'
        # Add meeting details if available
        meeting_id = context_filter.get('meeting_id')
        if meeting_id:
            context['target_meeting_id'] = meeting_id
    
    elif intent_type == 'analytics_query':
        context['focus'] = 'analytics'
        # Include productivity metrics
        context['include_metrics'] = True
    
    elif intent_type == 'calendar_query':
        context['focus'] = 'calendar'
    
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
    Execute copilot action with action chaining support.
    
    CROWN⁹ Enhanced Actions:
    - Single actions: create_task, mark_done, add_to_calendar, schedule_meeting
    - Action chains: create_and_assign, complete_and_create_followup
    - Bulk actions: mark_all_done, prioritize_batch
    
    Supports multi-step workflows for agentic capability.
    """
    from models import db, Task, Meeting
    from datetime import datetime, timedelta
    from dateutil.parser import parse as parse_date
    
    results = {
        'success': False,
        'action': action,
        'steps': [],
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        # Single action: create_task
        if action == 'create_task':
            task = Task(
                title=parameters.get('title', 'Untitled Task'),
                description=parameters.get('description'),
                workspace_id=workspace_id,
                created_by_id=user_id,
                assigned_to_id=parameters.get('assigned_to_id') or user_id,
                status='todo',
                priority=parameters.get('priority', 'medium'),
                due_date=_parse_date_safe(parameters.get('due_date')),
                source='copilot'
            )
            db.session.add(task)
            db.session.commit()
            
            results['success'] = True
            results['task_id'] = task.id
            results['task'] = task.to_dict() if hasattr(task, 'to_dict') else {'id': task.id, 'title': task.title}
            results['steps'].append({'action': 'create_task', 'success': True, 'task_id': task.id})
        
        # Single action: mark_done
        elif action == 'mark_done':
            task_id = parameters.get('task_id')
            if not task_id:
                return {'success': False, 'error': 'task_id is required'}
            
            task = db.session.get(Task, task_id)
            
            if task and (task.workspace_id == workspace_id or workspace_id is None):
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                db.session.commit()
                
                results['success'] = True
                results['task_id'] = task.id
                results['steps'].append({'action': 'mark_done', 'success': True, 'task_id': task.id})
            else:
                results['error'] = 'Task not found or access denied'
        
        # Action chain: create_and_assign (multi-step)
        elif action == 'create_and_assign':
            # Step 1: Create the task
            task = Task(
                title=parameters.get('title', 'Untitled Task'),
                description=parameters.get('description'),
                workspace_id=workspace_id,
                created_by_id=user_id,
                status='todo',
                priority=parameters.get('priority', 'medium'),
                due_date=_parse_date_safe(parameters.get('due_date')),
                source='copilot'
            )
            db.session.add(task)
            db.session.flush()  # Get ID without committing
            
            results['steps'].append({'action': 'create_task', 'success': True, 'task_id': task.id})
            
            # Step 2: Assign to user
            assignee_id = parameters.get('assignee_id') or parameters.get('assigned_to_id')
            if assignee_id:
                task.assigned_to_id = assignee_id
                results['steps'].append({'action': 'assign_task', 'success': True, 'assignee_id': assignee_id})
            
            # Step 3: Set reminder if specified
            if parameters.get('set_reminder'):
                reminder_date = _parse_date_safe(parameters.get('reminder_date'))
                if reminder_date:
                    task.reminder_date = reminder_date
                    results['steps'].append({'action': 'set_reminder', 'success': True})
            
            db.session.commit()
            
            results['success'] = True
            results['task_id'] = task.id
            results['task'] = task.to_dict() if hasattr(task, 'to_dict') else {'id': task.id, 'title': task.title}
        
        # Action chain: complete_and_followup (multi-step)
        elif action == 'complete_and_followup':
            task_id = parameters.get('task_id')
            if not task_id:
                return {'success': False, 'error': 'task_id is required'}
            
            original_task = db.session.get(Task, task_id)
            
            if original_task and (original_task.workspace_id == workspace_id or workspace_id is None):
                # Step 1: Complete original task
                original_task.status = 'completed'
                original_task.completed_at = datetime.utcnow()
                results['steps'].append({'action': 'complete_task', 'success': True, 'task_id': task_id})
                
                # Step 2: Create follow-up task
                followup_title = parameters.get('followup_title') or f"Follow-up: {original_task.title}"
                followup_task = Task(
                    title=followup_title,
                    description=parameters.get('followup_description'),
                    workspace_id=workspace_id,
                    created_by_id=user_id,
                    assigned_to_id=original_task.assigned_to_id,
                    status='todo',
                    priority=parameters.get('priority', original_task.priority),
                    due_date=_parse_date_safe(parameters.get('followup_due_date')),
                    depends_on_task_id=original_task.id,
                    source='copilot'
                )
                db.session.add(followup_task)
                db.session.commit()
                
                results['steps'].append({'action': 'create_followup', 'success': True, 'task_id': followup_task.id})
                results['success'] = True
                results['original_task_id'] = task_id
                results['followup_task_id'] = followup_task.id
            else:
                results['error'] = 'Original task not found or access denied'
        
        # Bulk action: mark_all_done
        elif action == 'mark_all_done':
            task_ids = parameters.get('task_ids', [])
            if not task_ids:
                return {'success': False, 'error': 'task_ids is required'}
            
            completed_count = 0
            for tid in task_ids:
                task = db.session.get(Task, tid)
                if task and (task.workspace_id == workspace_id or workspace_id is None):
                    task.status = 'completed'
                    task.completed_at = datetime.utcnow()
                    completed_count += 1
            
            db.session.commit()
            results['success'] = completed_count > 0
            results['completed_count'] = completed_count
            results['steps'].append({'action': 'bulk_complete', 'success': True, 'count': completed_count})
        
        # Action: schedule_meeting
        elif action == 'schedule_meeting':
            title = parameters.get('title', 'New Meeting')
            scheduled_start = _parse_date_safe(parameters.get('scheduled_start'))
            
            if not scheduled_start:
                scheduled_start = datetime.utcnow() + timedelta(days=1)  # Default to tomorrow
            
            meeting = Meeting(
                title=title,
                workspace_id=workspace_id,
                created_by_id=user_id,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_start + timedelta(hours=1),
                status='scheduled'
            )
            db.session.add(meeting)
            db.session.commit()
            
            results['success'] = True
            results['meeting_id'] = meeting.id
            results['meeting'] = {'id': meeting.id, 'title': meeting.title}
            results['steps'].append({'action': 'schedule_meeting', 'success': True, 'meeting_id': meeting.id})
        
        # Action: prioritize_task
        elif action == 'prioritize_task':
            task_id = parameters.get('task_id')
            priority = parameters.get('priority', 'high')
            
            if not task_id:
                return {'success': False, 'error': 'task_id is required'}
            
            task = db.session.get(Task, task_id)
            if task and (task.workspace_id == workspace_id or workspace_id is None):
                task.priority = priority
                db.session.commit()
                results['success'] = True
                results['task_id'] = task_id
                results['steps'].append({'action': 'prioritize_task', 'success': True, 'priority': priority})
            else:
                results['error'] = 'Task not found or access denied'
        
        # Action: snooze_task
        elif action == 'snooze_task':
            task_id = parameters.get('task_id')
            snooze_until = _parse_date_safe(parameters.get('snooze_until'))
            
            if not task_id:
                return {'success': False, 'error': 'task_id is required'}
            
            if not snooze_until:
                snooze_until = datetime.utcnow() + timedelta(days=1)  # Default to tomorrow
            
            task = db.session.get(Task, task_id)
            if task and (task.workspace_id == workspace_id or workspace_id is None):
                task.snoozed_until = snooze_until
                db.session.commit()
                results['success'] = True
                results['task_id'] = task_id
                results['steps'].append({'action': 'snooze_task', 'success': True, 'snoozed_until': snooze_until.isoformat()})
            else:
                results['error'] = 'Task not found or access denied'
        
        else:
            results['error'] = f'Unknown action: {action}'
        
        return results
        
    except Exception as e:
        logger.error(f"Action execution error: {e}", exc_info=True)
        db.session.rollback()
        return {'success': False, 'error': str(e), 'action': action}


def _parse_date_safe(date_input):
    """Safely parse date string to datetime object."""
    from datetime import datetime as dt
    
    if not date_input:
        return None
    
    if isinstance(date_input, dt):
        return date_input
    
    if isinstance(date_input, str):
        try:
            from dateutil.parser import parse as parse_date
            return parse_date(date_input)
        except Exception:
            pass
    
    return None


def _broadcast_action_result(
    action: str,
    result: Dict[str, Any],
    workspace_id: Optional[int],
    user_id: Optional[int] = None
):
    """
    Broadcast action result to other surfaces for cross-surface sync (CROWN⁹ Event #10).
    
    Uses enhanced event_broadcaster.broadcast_copilot_action for:
    - ≤400ms sync latency SLA
    - Multi-surface broadcast (Dashboard, Tasks, Calendar, Analytics)
    - Metrics tracking for SLA compliance
    
    Channels:
    - /tasks - Task namespace
    - /calendar - Calendar namespace
    - /dashboard - Dashboard namespace
    - /analytics - Analytics namespace
    - /copilot - Copilot namespace
    """
    from app import socketio
    
    try:
        if not workspace_id:
            logger.warning("No workspace_id for cross-surface sync")
            return
        
        # Use enhanced event broadcaster for SLA-tracked broadcast
        event_broadcaster.broadcast_copilot_action(
            action=action,
            result=result,
            workspace_id=workspace_id,
            user_id=user_id
        )
        
        # Also emit legacy events for backward compatibility
        room_name = f"workspace_{workspace_id}"
        
        if action in ['create_task', 'mark_done', 'update_task', 'delete_task']:
            socketio.emit(
                'task_updated',
                result,
                namespace='/tasks',
                to=room_name
            )
        
        elif action in ['add_to_calendar', 'schedule_meeting']:
            socketio.emit(
                'calendar_updated',
                result,
                namespace='/calendar',
                to=room_name
            )
        
        # Dashboard notification
        socketio.emit(
            'copilot_action_completed',
            {
                'action': action,
                'result': result,
                'source': 'copilot'
            },
            namespace='/dashboard',
            to=room_name
        )
        
        logger.debug(f"Cross-surface sync: {action} broadcast to workspace {workspace_id}")
        
    except Exception as e:
        logger.error(f"Cross-surface sync error: {e}", exc_info=True)
