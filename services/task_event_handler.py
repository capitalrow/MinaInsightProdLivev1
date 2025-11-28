"""
TaskEventHandler Service - CROWN⁴.5 Event Matrix Implementation

Implements all 20 event handlers from the CROWN⁴.5 specification for the Tasks system.

Event Matrix:
1. tasks_bootstrap - Initial load with cache-first
2. tasks_ws_subscribe - Subscribe to real-time updates
3. task_nlp:proposed - AI-proposed task from transcript
4. task_create:manual - Manual task creation
5. task_create:nlp_accept - Accept NLP proposal
6. task_update:title - Update task title
7. task_update:status_toggle - Toggle completion status
8. task_update:priority - Update priority
9. task_update:due - Update due date (with PredictiveEngine)
10. task_update:assign - Assign to participant
11. task_update:labels - Update labels
12. task_snooze - Snooze task
13. task_merge - Merge duplicate tasks
14. task_link:jump_to_span - Jump to transcript span
15. filter_apply - Apply filters
16. tasks_refresh - Manual refresh
17. tasks_idle_sync - Background sync
18. tasks_offline_queue:replay - Replay offline queue
19. task_delete - Delete task
20. tasks_multiselect:bulk - Bulk operations
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from models import db
from models.task import Task
from models.task_view_state import TaskViewState
from models.task_counters import TaskCounters
from models.event_ledger import EventLedger, EventType, EventStatus
from services.event_sequencer import event_sequencer
from services.cache_validator import cache_validator
from services.deduper import deduper
from services.prefetch_controller import prefetch_controller
from services.quiet_state_manager import quiet_state_manager, AnimationPriority
from services.temporal_recovery_engine import temporal_recovery_engine

logger = logging.getLogger(__name__)

# Task status constants (strings, not enums)
TASK_STATUS_TODO = "todo"
TASK_STATUS_IN_PROGRESS = "in_progress"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_BLOCKED = "blocked"
TASK_STATUS_CANCELLED = "cancelled"

# Task priority constants
TASK_PRIORITY_LOW = "low"
TASK_PRIORITY_MEDIUM = "medium"
TASK_PRIORITY_HIGH = "high"
TASK_PRIORITY_URGENT = "urgent"


class TaskEventHandler:
    """
    Service for handling all 20 CROWN⁴.5 task events.
    
    Responsibilities:
    - Process incoming events from WebSocket
    - Update database with event changes
    - Log events to EventLedger
    - Broadcast updates to connected clients
    - Handle deduplication and conflict resolution
    - Coordinate animations via QuietStateManager
    """
    
    def __init__(self):
        """Initialize TaskEventHandler."""
        self.metrics = {
            'total_events': 0,
            'events_by_type': {},
            'errors': 0,
            'conflicts_resolved': 0
        }
    
    def _enhance_response_with_crown_metadata(
        self,
        response: Dict[str, Any],
        user_id: int,
        event_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Enhance event response with CROWN⁴.5 metadata (event_id, checksum).
        
        Args:
            response: Original event response
            user_id: User ID
            event_id: Event ID from sequencer (optional, will be included if provided)
            
        Returns:
            Enhanced response with event_id (if provided) and checksum
        """
        try:
            # Compute checksum of affected data
            # For tasks: checksum includes all tasks + counters for this user
            tasks = list(db.session.scalars(
                select(Task).where(Task.created_by_id == user_id)
            ).all())
            
            counters = db.session.scalar(
                select(TaskCounters).where(TaskCounters.user_id == user_id)
            )
            
            # Convert to list of dicts for checksum computation
            task_dicts = [t.to_dict() for t in tasks]
            
            # Compute checksum on tasks list
            checksum = cache_validator.compute_cache_checksum(
                task_dicts,
                id_field='id'
            )
            
            # Enhance response with CROWN⁴.5 metadata
            if event_id is not None:
                response['event_id'] = event_id
            response['checksum'] = checksum
            response['timestamp'] = datetime.utcnow().isoformat()
            
            # Include counter data for frontend validation
            if counters:
                response['counters_checksum'] = cache_validator.compute_cache_checksum(
                    [counters.to_dict()],
                    id_field='user_id'
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to enhance response with CROWN metadata: {e}", exc_info=True)
            # Return original response if enhancement fails (graceful degradation)
            return response
    
    @staticmethod
    def validate_task_id(task_id: Any) -> Dict[str, Any]:
        """
        ENTERPRISE-GRADE: Validate task ID before database operations.
        Prevents temp_ IDs from causing psycopg2.errors.InvalidTextRepresentation
        
        Args:
            task_id: Task ID to validate
            
        Returns:
            Validation result with success flag and error message
        """
        # Null/undefined IDs are invalid for updates
        if task_id is None or task_id == '':
            return {
                'valid': False,
                'error': 'Task ID is required',
                'error_code': 'MISSING_TASK_ID'
            }
        
        # Temp IDs indicate unreconciled optimistic operations
        if isinstance(task_id, str) and task_id.startswith('temp_'):
            logger.warning(f"⚠️ Rejecting operation on temp ID: {task_id}")
            return {
                'valid': False,
                'error': f'Cannot update task with temporary ID: {task_id}. This task was created offline and has not been synchronized with the server yet. Please wait for sync to complete.',
                'error_code': 'TEMP_ID_NOT_RECONCILED',
                'needs_reconciliation': True
            }
        
        # Valid integer IDs
        if isinstance(task_id, int) and task_id > 0:
            return {'valid': True}
        
        # String representation of integers
        if isinstance(task_id, str) and task_id.isdigit() and int(task_id) > 0:
            return {'valid': True, 'normalized_id': int(task_id)}
        
        # Invalid format
        return {
            'valid': False,
            'error': f'Invalid task ID format: {task_id}. Expected integer, got {type(task_id).__name__}',
            'error_code': 'INVALID_TASK_ID_FORMAT'
        }
    
    @staticmethod
    def check_workspace_access(task: Task, user_id: int) -> bool:
        """
        CRITICAL FIX: Validate workspace membership with fallback to ownership.
        
        This allows:
        - AI-extracted tasks (created_by_id=NULL) to be updated by workspace members
        - Tasks created by other users in the same workspace to be updated
        - Team collaboration on shared workspace tasks
        - Legacy tasks (workspace_id=NULL) to be accessed by original creator
        
        Authorization hierarchy:
        1. Owner access: User created the task (created_by_id == user_id)
        2. Workspace access: Task belongs to user's workspace (workspace_id match)
        3. Legacy/NULL workspace: Allow if user is the creator
        
        Args:
            task: Task instance to check access for
            user_id: User ID requesting access
            
        Returns:
            True if user has access, False otherwise
        """
        from models.user import User
        
        try:
            # PRIORITY 1: Owner always has access (handles legacy tasks)
            if task.created_by_id == user_id:
                return True
            
            # Get the user's workspace for workspace-based authorization
            user = db.session.get(User, user_id)
            if not user:
                logger.warning(f"User {user_id} not found during workspace access check")
                return False
            
            # PRIORITY 2: Workspace membership access
            # Handle NULL workspace_id gracefully (legacy tasks, AI backfills)
            if task.workspace_id is None:
                # Legacy task without workspace: only creator has access (already checked above)
                logger.info(f"Task {task.id} has NULL workspace_id, access denied for non-owner")
                return False
            
            # Normalize types to handle int vs string comparisons
            task_ws_id = int(task.workspace_id) if task.workspace_id is not None else None
            user_ws_id = int(user.workspace_id) if user.workspace_id is not None else None
            
            # Allow access if task belongs to same workspace as user
            if task_ws_id == user_ws_id:
                logger.debug(f"Workspace access granted: User {user_id} (ws={user_ws_id}) can access task {task.id} (ws={task_ws_id})")
                return True
            
            # DENY: Different workspace and not the creator
            logger.warning(f"Access denied: User {user_id} (workspace {user_ws_id}, type={type(user.workspace_id)}) "
                         f"cannot access task {task.id} (workspace {task_ws_id}, type={type(task.workspace_id)}, "
                         f"created_by {task.created_by_id})")
            return False
            
        except Exception as e:
            logger.error(f"Workspace access check failed: {e}", exc_info=True)
            return False
    
    async def handle_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Route event to appropriate handler based on event type.
        
        Args:
            event_type: Event type (e.g., 'task_create:manual')
            payload: Event payload data
            user_id: User ID
            session_id: Session ID (optional)
            
        Returns:
            Event processing result
        """
        try:
            # Update metrics
            self.metrics['total_events'] += 1
            self.metrics['events_by_type'][event_type] = \
                self.metrics['events_by_type'].get(event_type, 0) + 1
            
            # Route to handler
            handler_map = {
                'tasks_bootstrap': self._handle_tasks_bootstrap,
                'tasks_ws_subscribe': self._handle_tasks_ws_subscribe,
                'task_nlp:proposed': self._handle_task_nlp_proposed,
                'task_create:manual': self._handle_task_create_manual,
                'task_create:nlp_accept': self._handle_task_create_nlp_accept,
                'task_update:title': self._handle_task_update_title,
                'task_update:status_toggle': self._handle_task_update_status_toggle,
                'task_update:priority': self._handle_task_update_priority,
                'task_update:due': self._handle_task_update_due,
                'task_update:assign': self._handle_task_update_assign,
                'task_update:labels': self._handle_task_update_labels,
                'task_snooze': self._handle_task_snooze,
                'task_merge': self._handle_task_merge,
                'task_link:jump_to_span': self._handle_task_link_jump_to_span,
                'filter_apply': self._handle_filter_apply,
                'tasks_refresh': self._handle_tasks_refresh,
                'tasks_idle_sync': self._handle_tasks_idle_sync,
                'tasks_offline_queue:replay': self._handle_tasks_offline_queue_replay,
                'task_delete': self._handle_task_delete,
                'tasks_multiselect:bulk': self._handle_tasks_multiselect_bulk
            }
            
            handler = handler_map.get(event_type)
            if not handler:
                return {
                    'success': False,
                    'error': f'Unknown event type: {event_type}'
                }
            
            # Call handler
            result = await handler(payload, user_id, session_id)
            
            # Log event to ledger
            self._log_event(event_type, payload, user_id, session_id, result.get('success', False))
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to handle event {event_type}: {e}", exc_info=True)
            self.metrics['errors'] += 1
            return {
                'success': False,
                'error': str(e)
            }
    
    def _log_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int],
        success: bool
    ):
        """
        Log event to EventLedger.
        
        Args:
            event_type: Event type
            payload: Event payload
            user_id: User ID
            session_id: Session ID
            success: Whether event succeeded
        """
        try:
            # Map event type string to EventType enum
            event_type_map = {
                'task_create:manual': EventType.TASK_UPDATE,
                'task_create:nlp_accept': EventType.TASK_UPDATE,
                'task_update:title': EventType.TASK_UPDATE,
                'task_update:status_toggle': EventType.TASK_COMPLETE,
                'task_update:priority': EventType.TASK_UPDATE,
                'task_update:due': EventType.TASK_UPDATE,
                'task_update:assign': EventType.TASK_UPDATE,
                'task_update:labels': EventType.TASK_UPDATE,
                'task_delete': EventType.TASK_UPDATE,
            }
            
            ledger_event_type = event_type_map.get(event_type, EventType.TASK_UPDATE)
            
            # Create event ledger entry with sequence number
            # Unpack tuple: get_next_sequence_num returns (global_seq, workspace_seq)
            workspace_id = payload.get('workspace_id')
            global_seq, workspace_seq = event_sequencer.get_next_sequence_num(workspace_id)
            
            event = EventLedger(
                event_type=ledger_event_type,
                event_name=event_type,
                payload=payload,
                session_id=session_id,
                status=EventStatus.COMPLETED if success else EventStatus.FAILED,
                sequence_num=global_seq,
                workspace_id=workspace_id,
                workspace_sequence_num=workspace_seq,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow() if success else None
            )
            
            # Add vector clock if in payload
            if 'vector_clock' in payload:
                event.vector_clock = payload['vector_clock']
            
            db.session.add(event)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
            db.session.rollback()
    
    # Event Handlers Implementation
    
    async def _handle_tasks_bootstrap(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #1: tasks_bootstrap
        Initial load with cache-first strategy.
        """
        try:
            page = payload.get('page', 1)
            page_size = payload.get('page_size', 50)
            filters = payload.get('filters', {})
            
            # Build query
            query = select(Task).where(Task.created_by_id == user_id)
            
            # Apply filters
            if filters.get('status'):
                query = query.where(Task.status == filters['status'])
            if filters.get('priority'):
                query = query.where(Task.priority == filters['priority'])
            if filters.get('session_id'):
                query = query.where(Task.session_id == filters['session_id'])
            
            # Order and paginate
            query = query.order_by(Task.created_at.desc())
            query = query.offset((page - 1) * page_size).limit(page_size)
            
            tasks = list(db.session.scalars(query).all())
            
            # Get counters
            counters = db.session.scalar(
                select(TaskCounters).where(TaskCounters.user_id == user_id)
            )
            
            return {
                'success': True,
                'tasks': [task.to_dict() for task in tasks],
                'counters': counters.to_dict() if counters else {
                    'total': 0,
                    'pending': 0,
                    'completed': 0,
                    'overdue': 0,
                    'today': 0
                },
                'page': page,
                'page_size': page_size,
                'has_more': len(tasks) == page_size
            }
            
        except Exception as e:
            logger.error(f"Bootstrap failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _handle_tasks_ws_subscribe(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #2: tasks_ws_subscribe
        Subscribe to real-time task updates.
        """
        try:
            # Create or update view state
            view_state = db.session.scalar(
                select(TaskViewState).where(TaskViewState.user_id == user_id)
            )
            
            if not view_state:
                view_state = TaskViewState(
                    user_id=user_id,
                    active_filter="all",
                    scroll_position=0,
                    selected_task_ids=[]
                )
                db.session.add(view_state)
            
            db.session.commit()
            
            return {
                'success': True,
                'subscribed': True,
                'user_id': user_id,
                'view_state': view_state.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Subscribe failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_nlp_proposed(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #3: task_nlp:proposed
        AI-proposed task from transcript analysis.
        """
        try:
            # Queue animation
            quiet_state_manager.queue_animation(
                animation_type='soft_glow',
                target_element='#nlp-proposal',
                duration_ms=500,
                priority=AnimationPriority.HIGH
            )
            
            return {
                'success': True,
                'proposed_task': payload.get('proposed_task'),
                'confidence': payload.get('confidence', 0.0),
                'animation': 'soft_glow'
            }
            
        except Exception as e:
            logger.error(f"NLP propose failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_create_manual(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #4: task_create:manual
        Manual task creation by user.
        """
        try:
            # Generate origin hash for deduplication
            title = payload.get('title', '')
            description = payload.get('description')
            origin_hash = deduper.generate_origin_hash(title, description, user_id)
            
            # Check for exact duplicates
            duplicate = deduper.find_exact_duplicate(origin_hash, session_id=session_id)
            
            if duplicate:
                return {
                    'success': False,
                    'duplicate': True,
                    'existing_task': duplicate.to_dict()
                }
            
            # Parse due_date if provided
            due_date_str = payload.get('due_date')
            due_date = None
            if due_date_str:
                try:
                    # Try parsing ISO format date (YYYY-MM-DD)
                    due_date = datetime.fromisoformat(due_date_str).date()
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid due_date format: {due_date_str}")
            
            # Create task
            task = Task(
                title=title,
                description=description,
                created_by_id=user_id,
                workspace_id=payload.get('workspace_id', 1),  # Default to workspace 1 if not provided
                session_id=session_id,
                status=payload.get('status', TASK_STATUS_TODO),
                priority=payload.get('priority', TASK_PRIORITY_MEDIUM),
                due_date=due_date,
                origin_hash=origin_hash,
                source='manual',
                created_at=datetime.utcnow()
            )
            
            # Set assignee if provided (can be string name for now, will be converted to user_id later)
            assignee = payload.get('assignee')
            if assignee:
                # Store assignee as string in extraction_context for now
                # In production, this would be resolved to a user_id
                task.extraction_context = {'assignee_name': assignee}
            
            db.session.add(task)
            db.session.flush()
            
            # Update counters
            self._update_counters(user_id)
            
            db.session.commit()
            
            # Queue animation
            quiet_state_manager.queue_animation(
                animation_type='pop_in',
                target_element=f'#task-{task.id}',
                duration_ms=300,
                priority=AnimationPriority.CRITICAL
            )
            
            return {
                'success': True,
                'task': task.to_dict(),
                'animation': 'pop_in'
            }
            
        except Exception as e:
            logger.error(f"Task create failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_create_nlp_accept(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #5: task_create:nlp_accept
        Accept NLP-proposed task.
        """
        # Reuse manual creation logic
        return await self._handle_task_create_manual(payload, user_id, session_id)
    
    async def _handle_task_update_title(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #6: task_update:title
        Update task title.
        """
        try:
            task_id = payload.get('task_id')
            new_title = payload.get('title')
            
            task = db.session.get(Task, task_id)
            if not task:
                return {'success': False, 'error': 'Task not found'}
            
            # FIXED: Check workspace membership instead of ownership
            if not self.check_workspace_access(task, user_id):
                return {'success': False, 'error': 'Access denied - task not in your workspace'}
            
            if new_title:
                task.title = new_title
            task.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'success': True,
                'task': task.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Title update failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_update_status_toggle(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #7: task_update:status_toggle
        Toggle task completion status.
        ENTERPRISE-GRADE: Validates task ID before database operations.
        """
        try:
            task_id = payload.get('task_id')
            
            # ENTERPRISE-GRADE: Validate task ID before database operation
            validation = self.validate_task_id(task_id)
            if not validation.get('valid'):
                logger.warning(f"❌ Invalid task ID in status toggle: {task_id}")
                return {
                    'success': False,
                    'error': validation.get('error'),
                    'error_code': validation.get('error_code'),
                    'needs_reconciliation': validation.get('needs_reconciliation', False)
                }
            
            # Normalize ID if needed (string -> int)
            if 'normalized_id' in validation:
                task_id = validation['normalized_id']
            
            task = db.session.get(Task, task_id)
            if not task:
                return {'success': False, 'error': 'Task not found'}
            
            # FIXED: Check workspace membership instead of ownership
            if not self.check_workspace_access(task, user_id):
                return {'success': False, 'error': 'Access denied - task not in your workspace'}
            
            # Toggle status
            task.status = TASK_STATUS_COMPLETED if task.status == TASK_STATUS_TODO else TASK_STATUS_TODO
            task.updated_at = datetime.utcnow()
            
            if task.status == TASK_STATUS_COMPLETED:
                task.completed_at = datetime.utcnow()
            
            # Update counters
            self._update_counters(user_id)
            
            db.session.commit()
            
            # Queue animation
            if task.status == TASK_STATUS_COMPLETED:
                quiet_state_manager.queue_animation(
                    animation_type='checkmark_burst',
                    target_element=f'#task-{task.id}',
                    duration_ms=400,
                    priority=AnimationPriority.CRITICAL
                )
            
            return {
                'success': True,
                'task': task.to_dict(),
                'animation': 'checkmark_burst' if task.status == TASK_STATUS_COMPLETED else None
            }
            
        except Exception as e:
            logger.error(f"Status toggle failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_update_priority(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #8: task_update:priority
        Update task priority.
        """
        try:
            task_id = payload.get('task_id')
            new_priority = payload.get('priority')
            
            task = db.session.get(Task, task_id)
            if not task:
                return {'success': False, 'error': 'Task not found'}
            
            # FIXED: Check workspace membership instead of ownership
            if not self.check_workspace_access(task, user_id):
                return {'success': False, 'error': 'Access denied - task not in your workspace'}
            
            if new_priority:
                task.priority = new_priority
            task.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'success': True,
                'task': task.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Priority update failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_update_due(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #9: task_update:due
        Update task due date (with PredictiveEngine suggestions).
        """
        try:
            task_id = payload.get('task_id')
            new_due_date = payload.get('due_date')
            
            task = db.session.get(Task, task_id)
            if not task:
                return {'success': False, 'error': 'Task not found'}
            
            # FIXED: Check workspace membership instead of ownership
            if not self.check_workspace_access(task, user_id):
                return {'success': False, 'error': 'Access denied - task not in your workspace'}
            
            task.due_date = datetime.fromisoformat(new_due_date) if new_due_date else None
            task.updated_at = datetime.utcnow()
            
            # Update counters (affects overdue count)
            self._update_counters(user_id)
            
            db.session.commit()
            
            return {
                'success': True,
                'task': task.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Due date update failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_update_assign(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #10: task_update:assign
        Assign task to participant.
        """
        try:
            task_id = payload.get('task_id')
            assigned_to_id = payload.get('assigned_to_id')
            
            task = db.session.get(Task, task_id)
            if not task:
                return {'success': False, 'error': 'Task not found'}
            
            # FIXED: Check workspace membership instead of ownership
            if not self.check_workspace_access(task, user_id):
                return {'success': False, 'error': 'Access denied - task not in your workspace'}
            
            task.assigned_to_id = assigned_to_id
            task.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'success': True,
                'task': task.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Assign update failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_update_labels(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #11: task_update:labels
        Update task labels.
        """
        try:
            task_id = payload.get('task_id')
            new_labels = payload.get('labels', [])
            
            task = db.session.get(Task, task_id)
            if not task:
                return {'success': False, 'error': 'Task not found'}
            
            # FIXED: Check workspace membership instead of ownership
            if not self.check_workspace_access(task, user_id):
                return {'success': False, 'error': 'Access denied - task not in your workspace'}
            
            task.labels = new_labels
            task.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'success': True,
                'task': task.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Labels update failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_snooze(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #12: task_snooze
        Snooze task until specified time.
        """
        try:
            task_id = payload.get('task_id')
            snooze_until = payload.get('snooze_until')
            
            task = db.session.get(Task, task_id)
            if not task:
                return {'success': False, 'error': 'Task not found'}
            
            # FIXED: Check workspace membership instead of ownership
            if not self.check_workspace_access(task, user_id):
                return {'success': False, 'error': 'Access denied - task not in your workspace'}
            
            # Persist snooze time to database
            task.snoozed_until = datetime.fromisoformat(snooze_until) if snooze_until else None
            task.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # Queue animation
            quiet_state_manager.queue_animation(
                animation_type='slide_fade',
                target_element=f'#task-{task.id}',
                duration_ms=350,
                priority=AnimationPriority.MEDIUM
            )
            
            return {
                'success': True,
                'task': task.to_dict(),
                'animation': 'slide_fade'
            }
            
        except Exception as e:
            logger.error(f"Snooze failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_merge(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #13: task_merge
        Merge duplicate tasks.
        """
        try:
            source_task_id = payload.get('source_task_id')
            target_task_id = payload.get('target_task_id')
            
            source_task = db.session.get(Task, source_task_id)
            target_task = db.session.get(Task, target_task_id)
            
            if not source_task or not target_task:
                return {'success': False, 'error': 'Tasks not found'}
            
            # FIXED: Check workspace membership for BOTH tasks instead of ownership
            if not self.check_workspace_access(source_task, user_id):
                return {'success': False, 'error': 'Access denied - source task not in your workspace'}
            if not self.check_workspace_access(target_task, user_id):
                return {'success': False, 'error': 'Access denied - target task not in your workspace'}
            
            # Merge descriptions
            if source_task.description:
                target_task.description = f"{target_task.description}\n\n{source_task.description}" if target_task.description else source_task.description
            
            # Merge labels
            if source_task.labels:
                target_labels = set(target_task.labels or [])
                target_labels.update(source_task.labels)
                target_task.labels = list(target_labels)
            
            target_task.updated_at = datetime.utcnow()
            
            # Delete source task
            db.session.delete(source_task)
            
            # Update counters
            self._update_counters(user_id)
            
            db.session.commit()
            
            return {
                'success': True,
                'merged_task': target_task.to_dict(),
                'deleted_task_id': source_task_id
            }
            
        except Exception as e:
            logger.error(f"Task merge failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_task_link_jump_to_span(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #14: task_link:jump_to_span
        Jump to transcript span where task was mentioned.
        """
        try:
            task_id = payload.get('task_id')
            
            task = db.session.get(Task, task_id)
            if not task:
                return {'success': False, 'error': 'Task not found'}
            
            # FIXED: Check workspace membership instead of ownership
            if not self.check_workspace_access(task, user_id):
                return {'success': False, 'error': 'Access denied - task not in your workspace'}
            
            # Queue animation
            quiet_state_manager.queue_animation(
                animation_type='morph_transition',
                target_element='#transcript-viewer',
                duration_ms=500,
                priority=AnimationPriority.HIGH
            )
            
            return {
                'success': True,
                'task_id': task_id,
                'session_id': task.session_id,
                'transcript_span': task.transcript_span,
                'animation': 'morph_transition'
            }
            
        except Exception as e:
            logger.error(f"Jump to span failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _handle_filter_apply(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #15: filter_apply
        Apply filters to task list.
        """
        try:
            filters = payload.get('filters', {})
            
            # Update view state
            view_state = db.session.scalar(
                select(TaskViewState).where(TaskViewState.user_id == user_id)
            )
            
            if view_state:
                # Note: active_filter is a single string, not a dict
                # For complex filtering, update individual filter fields
                if 'active_filter' in filters:
                    view_state.active_filter = filters['active_filter']
                if 'status_filter' in filters:
                    view_state.status_filter = filters['status_filter']
                if 'priority_filter' in filters:
                    view_state.priority_filter = filters['priority_filter']
                view_state.updated_at = datetime.utcnow()
                db.session.commit()
            
            # Return filtered tasks (delegate to bootstrap)
            return await self._handle_tasks_bootstrap(
                {'page': 1, 'page_size': 50, 'filters': filters},
                user_id,
                session_id
            )
            
        except Exception as e:
            logger.error(f"Filter apply failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_tasks_refresh(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #16: tasks_refresh
        Manual refresh request.
        """
        # Delegate to bootstrap
        return await self._handle_tasks_bootstrap(payload, user_id, session_id)
    
    async def _handle_tasks_idle_sync(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #17: tasks_idle_sync
        Background sync during idle time.
        """
        try:
            # Update view state timestamp
            view_state = db.session.scalar(
                select(TaskViewState).where(TaskViewState.user_id == user_id)
            )
            
            if view_state:
                view_state.updated_at = datetime.utcnow()
                db.session.commit()
            
            # Queue subtle animation
            quiet_state_manager.queue_animation(
                animation_type='shimmer',
                target_element='#sync-icon',
                duration_ms=200,
                priority=AnimationPriority.LOW
            )
            
            return {
                'success': True,
                'synced': True,
                'timestamp': datetime.utcnow().isoformat(),
                'animation': 'shimmer'
            }
            
        except Exception as e:
            logger.error(f"Idle sync failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_tasks_offline_queue_replay(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #18: tasks_offline_queue:replay
        Replay offline queue with vector clock ordering and conflict resolution.
        
        CROWN⁴.5 Compliance:
        - Reorders events using vector clock causality
        - Detects and resolves conflicts
        - Applies deduplication
        - Guarantees zero event loss
        """
        try:
            queued_events = payload.get('queued_events', [])
            
            if not queued_events:
                return {
                    'success': True,
                    'total_queued': 0,
                    'processed': 0,
                    'conflicts': 0,
                    'duplicates': 0
                }
            
            # Convert queued events to pseudo-EventLedger objects for ordering
            event_objects = []
            for queued_event in queued_events:
                # Create temporary event object with vector clock
                event_obj = type('EventLedger', (), {
                    'id': None,
                    'event_type': queued_event.get('event_type'),
                    'payload': queued_event.get('payload', {}),
                    'vector_clock': queued_event.get('vector_clock'),
                    'sequence_num': queued_event.get('sequence_num'),
                    'created_at': datetime.fromisoformat(queued_event['timestamp']) if queued_event.get('timestamp') else datetime.utcnow()
                })()
                event_objects.append(event_obj)
            
            # Reorder events using TemporalRecoveryEngine
            ordered_events = temporal_recovery_engine.reorder_events(event_objects)
            
            # Detect conflicts using vector clocks
            conflicts = event_sequencer.detect_conflicts(ordered_events) if len(ordered_events) > 1 else []
            
            # Replay events in order
            processed_count = 0
            failed_count = 0
            duplicate_count = 0
            conflict_count = len(conflicts)
            results = []
            
            for event in ordered_events:
                try:
                    # Check for duplicates using deduplication
                    if hasattr(event, 'payload') and event.payload and event.payload.get('task_id'):
                        # For updates, check if task exists and has newer vector clock
                        task_id = event.payload['task_id']
                        existing_task = db.session.get(Task, task_id)
                        
                        if existing_task and existing_task.vector_clock_token:
                            # Compare vector clocks
                            if event.vector_clock:
                                relation = event_sequencer.compare_vector_clocks(
                                    existing_task.vector_clock_token,
                                    event.vector_clock
                                )
                                
                                if relation == "after":
                                    # Existing task is newer - skip this event
                                    duplicate_count += 1
                                    logger.info(f"Skipping outdated event for task {task_id}")
                                    continue
                    
                    # Process event
                    result = await self.handle_event(
                        event_type=str(event.event_type) if hasattr(event, 'event_type') else 'unknown',
                        payload=event.payload if hasattr(event, 'payload') and event.payload else {},
                        user_id=user_id,
                        session_id=session_id
                    )
                    
                    if result.get('success'):
                        processed_count += 1
                    else:
                        failed_count += 1
                    
                    results.append({
                        'event_type': event.event_type,
                        'success': result.get('success', False),
                        'error': result.get('error')
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to replay event: {e}")
                    failed_count += 1
                    results.append({
                        'event_type': event.event_type if hasattr(event, 'event_type') else 'unknown',
                        'success': False,
                        'error': str(e)
                    })
            
            return {
                'success': True,
                'total_queued': len(queued_events),
                'processed': processed_count,
                'failed': failed_count,
                'duplicates': duplicate_count,
                'conflicts': conflict_count,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Offline queue replay failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'total_queued': len(payload.get('queued_events', []))
            }
    
    async def _handle_task_delete(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #19: task_delete
        Delete task.
        """
        try:
            task_id = payload.get('task_id')
            
            task = db.session.get(Task, task_id)
            if not task:
                return {'success': False, 'error': 'Task not found'}
            
            # FIXED: Check workspace membership instead of ownership
            if not self.check_workspace_access(task, user_id):
                return {'success': False, 'error': 'Access denied - task not in your workspace'}
            
            db.session.delete(task)
            
            # Update counters
            self._update_counters(user_id)
            
            db.session.commit()
            
            return {
                'success': True,
                'deleted_task_id': task_id
            }
            
        except Exception as e:
            logger.error(f"Task delete failed: {e}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    async def _handle_tasks_multiselect_bulk(
        self,
        payload: Dict[str, Any],
        user_id: int,
        session_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Event #20: tasks_multiselect:bulk
        Bulk operations on multiple tasks.
        """
        try:
            task_ids = payload.get('task_ids', [])
            operation = payload.get('operation')  # 'complete', 'delete', 'priority', etc.
            operation_data = payload.get('operation_data', {})
            
            results = []
            for task_id in task_ids:
                # Dispatch to appropriate handler
                if operation == 'complete':
                    result = await self._handle_task_update_status_toggle(
                        {'task_id': task_id},
                        user_id,
                        session_id
                    )
                elif operation == 'delete':
                    result = await self._handle_task_delete(
                        {'task_id': task_id},
                        user_id,
                        session_id
                    )
                elif operation == 'priority':
                    result = await self._handle_task_update_priority(
                        {'task_id': task_id, 'priority': operation_data.get('priority')},
                        user_id,
                        session_id
                    )
                else:
                    result = {'success': False, 'error': f'Unknown operation: {operation}'}
                
                results.append(result)
            
            return {
                'success': True,
                'operation': operation,
                'total_tasks': len(task_ids),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Bulk operation failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _update_counters(self, user_id: int):
        """
        Update TaskCounters for user.
        
        Args:
            user_id: User ID
        """
        try:
            # Count tasks by status
            total = db.session.scalar(
                select(func.count()).where(Task.created_by_id == user_id)
            ) or 0
            
            pending = db.session.scalar(
                select(func.count()).where(
                    and_(Task.created_by_id == user_id, Task.status == TASK_STATUS_TODO)
                )
            ) or 0
            
            completed = db.session.scalar(
                select(func.count()).where(
                    and_(Task.created_by_id == user_id, Task.status == TASK_STATUS_COMPLETED)
                )
            ) or 0
            
            # Count overdue
            overdue = db.session.scalar(
                select(func.count()).where(
                    and_(
                        Task.created_by_id == user_id,
                        Task.status == TASK_STATUS_TODO,
                        Task.due_date < datetime.utcnow()
                    )
                )
            ) or 0
            
            # Count due today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            today = db.session.scalar(
                select(func.count()).where(
                    and_(
                        Task.created_by_id == user_id,
                        Task.status == TASK_STATUS_TODO,
                        Task.due_date >= today_start,
                        Task.due_date < today_end
                    )
                )
            ) or 0
            
            # Update or create counters
            counters = db.session.scalar(
                select(TaskCounters).where(TaskCounters.user_id == user_id)
            )
            
            if counters:
                counters.total_count = total
                counters.pending_count = pending
                counters.completed_count = completed
                counters.overdue_count = overdue
                counters.due_today_count = today
                counters.updated_at = datetime.utcnow()
            else:
                counters = TaskCounters(
                    user_id=user_id,
                    total_count=total,
                    pending_count=pending,
                    completed_count=completed,
                    overdue_count=overdue,
                    due_today_count=today
                )
                db.session.add(counters)
            
            # Queue counter pulse animation
            quiet_state_manager.queue_animation(
                animation_type='counter_pulse',
                target_element='#task-counters',
                duration_ms=250,
                priority=AnimationPriority.MEDIUM
            )
            
        except Exception as e:
            logger.error(f"Failed to update counters: {e}")


# Singleton instance
task_event_handler = TaskEventHandler()
