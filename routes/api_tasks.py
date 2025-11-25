"""
Tasks API Routes
REST API endpoints for task management, CRUD operations, and status updates.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Task, Meeting, User, Session, Workspace, TaskComment, EventLedger, EventType, Segment
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_, or_, select, text
from sqlalchemy.orm import joinedload, selectinload
from utils.etag_helper import with_etag, compute_collection_etag
from utils.auth import admin_required
# server/routes/api_tasks.py
import logging
from app import db
from models.summary import Summary
from services.event_broadcaster import EventBroadcaster
from services.event_sequencer import event_sequencer
from services.deduper import deduper
from services.task_embedding_service import get_embedding_service

logger = logging.getLogger(__name__)
event_broadcaster = EventBroadcaster()

api_tasks_bp = Blueprint('api_tasks', __name__, url_prefix='/api/tasks')


@api_tasks_bp.route('/', methods=['GET'])
@with_etag
@login_required
def list_tasks():
    """Get tasks for current user's workspace with filtering and pagination."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        status = request.args.get('status', None)
        priority = request.args.get('priority', None)
        assigned_to = request.args.get('assigned_to', None)
        meeting_id = request.args.get('meeting_id', None, type=int)
        search = request.args.get('search', None)
        due_date_filter = request.args.get('due_date', None)  # today, overdue, this_week
        
        # Base query - tasks from meetings in user's workspace (exclude soft-deleted by default)
        include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
        
        # CROWN⁴.6 OPTIMIZATION: Eager load ALL relationships to prevent N+1 queries
        # Performance target: <500ms for full sync with 15+ tasks
        # - assignees: selectinload for many-to-many (more efficient than joinedload)
        # - meeting: joinedload since we're already joining on Meeting table
        # - assigned_to, created_by, deleted_by: joinedload for single FK relationships
        stmt = select(Task).join(Meeting).options(
            selectinload(Task.assignees),
            joinedload(Task.meeting),
            joinedload(Task.assigned_to),
            joinedload(Task.created_by),
            joinedload(Task.deleted_by)
        ).where(
            Meeting.workspace_id == current_user.workspace_id
        )
        
        # CROWN⁴.5 Phase 1: Filter out soft-deleted tasks by default
        if not include_deleted:
            stmt = stmt.where(Task.deleted_at.is_(None))
        
        # Apply filters
        if status:
            stmt = stmt.where(Task.status == status)
        
        if priority:
            stmt = stmt.where(Task.priority == priority)
        
        if assigned_to:
            if assigned_to == 'me':
                stmt = stmt.where(Task.assigned_to_id == current_user.id)
            elif assigned_to == 'unassigned':
                stmt = stmt.where(Task.assigned_to_id.is_(None))
            else:
                stmt = stmt.where(Task.assigned_to_id == int(assigned_to))
        
        if meeting_id:
            stmt = stmt.where(Task.meeting_id == meeting_id)
        
        # CROWN⁴.6: Semantic search support
        semantic = request.args.get('semantic', 'false').lower() == 'true'
        semantic_mode_active = False  # Track if semantic ordering was applied
        
        if search:
            if semantic:
                # Try semantic search with pgvector cosine similarity
                embedding_service = get_embedding_service()
                if embedding_service.is_available():
                    try:
                        # Generate embedding for search query
                        query_embedding = embedding_service.generate_embedding(search)
                        
                        if query_embedding:
                            # Use pgvector.sqlalchemy cosine_distance for similarity search
                            # Scoped to workspace via existing Meeting join
                            from sqlalchemy import func
                            
                            # Filter tasks with embeddings
                            stmt = stmt.where(Task.embedding.isnot(None))
                            
                            # Order by cosine similarity (distance) - lower distance = more similar
                            stmt = stmt.order_by(Task.embedding.cosine_distance(query_embedding))
                            
                            # Limit to top 50 most similar tasks
                            stmt = stmt.limit(50)
                            
                            semantic_mode_active = True  # Flag to skip default ordering
                            logger.info(f"Semantic search active for query: '{search[:50]}...'")
                        else:
                            # Fall back to keyword search
                            logger.warning("Failed to generate query embedding, falling back to keyword search")
                            stmt = stmt.where(
                                or_(
                                    Task.title.contains(search),
                                    Task.description.contains(search)
                                )
                            )
                    except Exception as e:
                        logger.error(f"Semantic search failed: {e}, falling back to keyword search")
                        # Fall back to keyword search
                        stmt = stmt.where(
                            or_(
                                Task.title.contains(search),
                                Task.description.contains(search)
                            )
                        )
                else:
                    # Embedding service not available, fall back to keyword search
                    stmt = stmt.where(
                        or_(
                            Task.title.contains(search),
                            Task.description.contains(search)
                        )
                    )
            else:
                # Regular keyword search
                stmt = stmt.where(
                    or_(
                        Task.title.contains(search),
                        Task.description.contains(search)
                    )
                )
        
        # Due date filters
        if due_date_filter:
            today = date.today()
            if due_date_filter == 'today':
                stmt = stmt.where(Task.due_date == today)
            elif due_date_filter == 'overdue':
                stmt = stmt.where(
                    and_(
                        Task.due_date < today,
                        Task.status.in_(['todo', 'in_progress'])
                    )
                )
            elif due_date_filter == 'this_week':
                week_end = today + timedelta(days=7-today.weekday())
                stmt = stmt.where(
                    and_(
                        Task.due_date >= today,
                        Task.due_date <= week_end
                    )
                )
        
        # Order by position (drag-drop), then priority and due date
        # CROWN⁴.5 Phase 3: Position-based ordering for drag-drop reordering
        # CROWN⁴.6: Skip default ordering if semantic search is active (preserve cosine similarity ordering)
        if not semantic_mode_active:
            stmt = stmt.order_by(
                Task.position.asc(),
                Task.priority.desc(),
                Task.due_date.asc().nullslast(),
                Task.created_at.desc()
            )
        
        # Paginate
        tasks = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'tasks': [task.to_dict() for task in tasks.items],
            'pagination': {
                'page': tasks.page,
                'pages': tasks.pages,
                'per_page': tasks.per_page,
                'total': tasks.total,
                'has_next': tasks.has_next,
                'has_prev': tasks.has_prev
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    """Get detailed task information.
    
    Query Parameters:
        detail (str): Response detail level ('mini' for prefetching, default: full)
    """
    try:
        # Use outerjoin to support tasks without meetings
        # Filter by workspace_id from task OR meeting (for tasks without meeting_id)
        workspace_id_str = str(current_user.workspace_id)
        task = db.session.query(Task).outerjoin(Meeting).filter(
            Task.id == task_id,
            or_(
                Task.workspace_id == workspace_id_str,
                Meeting.workspace_id == current_user.workspace_id
            )
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        # CROWN⁴.5 Phase 1.7: Support mini detail for prefetching
        detail_level = request.args.get('detail', 'full')
        
        if detail_level == 'mini':
            # Minimal payload optimized for prefetch cache warming
            # Defensive assignees loading to prevent 500 errors
            assignees_data = []
            try:
                if hasattr(task, 'assignees') and task.assignees:
                    assignees_data = [
                        {
                            'id': assignee.id,
                            'username': assignee.username,
                            'email': assignee.email
                        }
                        for assignee in task.assignees
                    ]
            except Exception as assignee_err:
                logger.warning(f"Failed to load assignees for task {task_id}: {assignee_err}")
                assignees_data = []
            
            response = {
                'success': True,
                'task': task.to_dict(),
                'meeting': {
                    'id': task.meeting.id,
                    'title': task.meeting.title,
                    'date': task.meeting.created_at.isoformat() if task.meeting.created_at else None
                } if task.meeting else None,
                'assignees': assignees_data
            }
        else:
            # Full detail (default) - include meeting info for CROWN⁴.6
            response = {
                'success': True,
                'task': task.to_dict(include_relationships=True)
            }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>/html', methods=['GET'])
@login_required
def get_task_html(task_id):
    """Get server-rendered HTML fragment for a task card (CROWN⁴.6 feature).
    
    Returns the complete HTML for a task card to enable fragment-based hydration
    for optimistic inserts without page reloads. Preserves all data attributes
    needed for emotional UI and spoken provenance features.
    """
    try:
        from flask import render_template_string
        
        # Fetch task with all relationships eager loaded
        task = db.session.query(Task).options(
            joinedload(Task.meeting),
            joinedload(Task.assigned_to),
            selectinload(Task.assignees)
        ).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        # Render task card using macro
        html = render_template_string(
            "{% from 'dashboard/_task_card_macro.html' import task_card %}{{ task_card(task) }}",
            task=task
        )
        
        return jsonify({
            'success': True,
            'html': html.strip(),
            'task': task.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error rendering task {task_id} HTML fragment: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>/transcript-context', methods=['GET'])
@login_required
def get_task_transcript_context(task_id):
    """Get transcript context for a task (CROWN⁴.6 feature).
    
    Returns the spoken context, speaker, and transcript snippet where this task was mentioned.
    Used for preview tooltips and spoken provenance UI.
    """
    try:
        # Fetch task and verify workspace access
        task = db.session.query(Task).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        # Check if task has transcript context
        if not task.transcript_span or not task.extraction_context:
            return jsonify({
                'success': True,
                'context': None,
                'message': 'No transcript context available'
            })
        
        # Build context response
        transcript_span = task.transcript_span
        extraction_context = task.extraction_context
        
        # Fetch the actual segment text if segment_ids are available
        segment_texts = []
        if transcript_span.get('segment_ids'):
            from sqlalchemy import select
            stmt = select(Segment).filter(Segment.id.in_(transcript_span['segment_ids']))
            segments = db.session.execute(stmt).scalars().all()
            segment_texts = [seg.text for seg in segments]
        
        context_response = {
            'task_id': task.id,
            'task_title': task.title,
            'meeting_id': task.meeting_id,
            'meeting_title': task.meeting.title if task.meeting else None,
            'speaker': extraction_context.get('speaker'),
            'quote': extraction_context.get('quote', ''),
            'full_segments': segment_texts,
            'confidence': task.confidence_score,
            'start_ms': transcript_span.get('start_ms'),
            'end_ms': transcript_span.get('end_ms'),
            'start_time_formatted': format_ms_to_time(transcript_span.get('start_ms')) if transcript_span.get('start_ms') else None
        }
        
        return jsonify({
            'success': True,
            'context': context_response
        })
        
    except Exception as e:
        logger.error(f"Error fetching transcript context for task {task_id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


def format_ms_to_time(milliseconds):
    """Format milliseconds to MM:SS format."""
    if not milliseconds:
        return "00:00"
    total_seconds = milliseconds // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


@api_tasks_bp.route('/meeting-heatmap', methods=['GET'])
@login_required
def get_meeting_heatmap():
    """Get meeting heatmap data for CROWN⁴.6 Meeting Intelligence visualization.
    
    Returns meetings with active task counts, sorted by task count (descending).
    Used for the Meeting Heatmap component to show which meetings have actionable items.
    """
    try:
        # Query meetings with task counts
        from sqlalchemy import case
        
        # Subquery to count tasks per meeting
        task_counts = db.session.query(
            Task.meeting_id,
            func.count(Task.id).label('total_tasks'),
            func.sum(case((Task.status == 'todo', 1), else_=0)).label('todo_count'),
            func.sum(case((Task.status == 'in_progress', 1), else_=0)).label('in_progress_count'),
            func.sum(case((Task.status == 'completed', 1), else_=0)).label('completed_count')
        ).filter(
            Task.deleted_at.is_(None)
        ).group_by(Task.meeting_id).subquery()
        
        # Join with meetings
        meetings = db.session.query(
            Meeting,
            func.coalesce(task_counts.c.total_tasks, 0).label('total_tasks'),
            func.coalesce(task_counts.c.todo_count, 0).label('todo_count'),
            func.coalesce(task_counts.c.in_progress_count, 0).label('in_progress_count'),
            func.coalesce(task_counts.c.completed_count, 0).label('completed_count')
        ).outerjoin(
            task_counts, Meeting.id == task_counts.c.meeting_id
        ).filter(
            Meeting.workspace_id == current_user.workspace_id,
            Meeting.archived == False
        ).order_by(
            func.coalesce(task_counts.c.total_tasks, 0).desc(),
            Meeting.created_at.desc()
        ).limit(20).all()  # Limit to top 20 meetings
        
        # Build response
        heatmap_data = []
        for meeting, total, todo, in_progress, completed in meetings:
            # Calculate active tasks (todo + in_progress)
            active_count = todo + in_progress
            
            # Skip meetings with no tasks
            if total == 0:
                continue
            
            # Calculate heat intensity (0-100 scale)
            # Primarily based on active tasks, with recency bonus
            days_ago = (datetime.utcnow() - meeting.created_at).days if meeting.created_at else 999
            recency_bonus = max(0, 10 - days_ago) * 2  # Up to +20 for recent meetings
            heat_intensity = min(100, (active_count * 10) + recency_bonus)
            
            heatmap_data.append({
                'meeting_id': meeting.id,
                'meeting_title': meeting.title,
                'created_at': meeting.created_at.isoformat() if meeting.created_at else None,
                'total_tasks': total,
                'active_tasks': active_count,
                'todo_count': todo,
                'in_progress_count': in_progress,
                'completed_count': completed,
                'heat_intensity': heat_intensity,
                'days_ago': days_ago
            })
        
        return jsonify({
            'success': True,
            'meetings': heatmap_data,
            'total_meetings': len(heatmap_data)
        })
        
    except Exception as e:
        logger.error(f"Error fetching meeting heatmap: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/', methods=['POST'])
@login_required
def create_task():
    """Create a new task."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({'success': False, 'message': 'Title is required'}), 400
        
        if not data.get('meeting_id'):
            return jsonify({'success': False, 'message': 'Meeting ID is required'}), 400
        
        # Verify meeting exists and belongs to user's workspace
        meeting = db.session.query(Meeting).filter_by(
            id=data['meeting_id'],
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Invalid meeting ID'}), 400
        
        # Parse due date if provided
        due_date = None
        if data.get('due_date'):
            try:
                due_date = date.fromisoformat(data['due_date'])
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid due date format. Use YYYY-MM-DD'}), 400
        
        # Validate assigned_to_id if provided
        assigned_to_id = data.get('assigned_to_id')
        if assigned_to_id:
            assignee = db.session.query(User).filter_by(
                id=assigned_to_id,
                workspace_id=current_user.workspace_id
            ).first()
            if not assignee:
                return jsonify({'success': False, 'message': 'Invalid assignee'}), 400
        
        # CROWN⁴.5 Phase 3: Calculate next position for drag-drop ordering
        # Assign position = max(existing positions) + 1 to append new tasks at end
        max_position = db.session.query(func.max(Task.position)).join(Meeting).filter(
            Meeting.workspace_id == current_user.workspace_id,
            Task.deleted_at.is_(None)
        ).scalar() or -1
        
        task = Task(
            title=data['title'].strip(),
            description=data.get('description', '').strip() or None,
            meeting_id=data['meeting_id'],
            priority=data.get('priority', 'medium'),
            category=data.get('category', '').strip() or None,
            due_date=due_date,
            assigned_to_id=assigned_to_id,
            status='todo',
            created_by_id=current_user.id,
            extracted_by_ai=False,
            position=max_position + 1
        )
        
        db.session.add(task)
        db.session.flush()  # Flush to get task.id before commit
        
        # CROWN⁴.5: Multi-assignee support via assignee_ids array
        if 'assignee_ids' in data:
            from models.task import TaskAssignee
            
            assignee_ids = data['assignee_ids']
            if isinstance(assignee_ids, list) and assignee_ids:
                # Validate all assignees are in workspace
                valid_users = db.session.query(User).filter(
                    User.id.in_(assignee_ids),
                    User.workspace_id == current_user.workspace_id,
                    User.active == True
                ).all()
                
                if len(valid_users) != len(set(assignee_ids)):
                    db.session.rollback()
                    return jsonify({'success': False, 'message': 'One or more invalid assignee IDs'}), 400
                
                # Create assignments
                for user_id in assignee_ids:
                    assignment = TaskAssignee(
                        task_id=task.id,
                        user_id=user_id,
                        assigned_by_user_id=current_user.id,
                        role='assignee'
                    )
                    db.session.add(assignment)
                
                # Update assigned_to_id for backward compatibility (first assignee)
                task.assigned_to_id = assignee_ids[0]
        
        db.session.commit()
        
        # CROWN⁴.5 Phase 2 Batch 1: Emit TASK_CREATE_MANUAL event
        try:
            task_data = task.to_dict()
            task_data['action'] = 'created'
            task_data['meeting_title'] = meeting.title
            
            event = event_sequencer.create_event(
                event_type=EventType.TASK_CREATE_MANUAL,
                event_name=f"Task created manually: {task.title}",
                payload={
                    'task_id': task.id,
                    'task': task_data,
                    'meeting_id': meeting.id,
                    'workspace_id': str(current_user.workspace_id),
                    'action': 'created'
                },
                workspace_id=str(current_user.workspace_id),
                client_id=f"user_{current_user.id}"
            )
            # Broadcast event immediately
            event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
        except Exception as e:
            logger.error(f"Failed to emit TASK_CREATE_MANUAL event: {e}")
        
        # Broadcast task_update event (legacy broadcast for backward compatibility)
        task_dict = task.to_dict()
        task_dict['action'] = 'created'
        task_dict['meeting_title'] = meeting.title
        event_broadcaster.broadcast_task_update(
            task_id=task.id,
            task_data=task_dict,
            meeting_id=meeting.id,
            workspace_id=current_user.workspace_id,
            user_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': 'Task created successfully',
            'task': task.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/check-duplicate', methods=['POST'])
@login_required
def check_duplicate():
    """
    Check if a task is a duplicate before creation.
    CROWN⁴.5 Phase 1.3: Deduper active workflows with origin_hash matching.
    Security: Only returns duplicates within user's workspace, no cross-tenant leakage.
    """
    try:
        data = request.get_json()
        
        if not data.get('title'):
            return jsonify({'success': False, 'message': 'Title is required'}), 400
        
        title = data['title'].strip()
        description = data.get('description', '').strip() or None
        assigned_to_id = data.get('assigned_to_id')
        meeting_id = data.get('meeting_id')
        session_id = data.get('session_id')
        
        if meeting_id:
            meeting = db.session.query(Meeting).filter_by(
                id=meeting_id,
                workspace_id=current_user.workspace_id
            ).first()
            
            if not meeting:
                return jsonify({'success': False, 'message': 'Invalid meeting ID'}), 403
        
        duplicate_check = deduper.check_duplicate(
            title=title,
            description=description,
            assigned_to_id=assigned_to_id,
            meeting_id=meeting_id,
            session_id=session_id,
            use_fuzzy_matching=True
        )
        
        has_workspace_duplicate = False
        workspace_existing_task = None
        workspace_similar_tasks = []
        
        if duplicate_check['existing_task']:
            existing_task = duplicate_check['existing_task']
            if existing_task.meeting and existing_task.meeting.workspace_id == current_user.workspace_id:
                has_workspace_duplicate = True
                workspace_existing_task = existing_task.to_dict()
        
        if duplicate_check['similar_tasks']:
            for task, similarity in duplicate_check['similar_tasks']:
                if task.meeting and task.meeting.workspace_id == current_user.workspace_id:
                    task_dict = task.to_dict()
                    task_dict['similarity'] = similarity
                    workspace_similar_tasks.append(task_dict)
                    has_workspace_duplicate = True
        
        if has_workspace_duplicate:
            response_data = {
                'success': True,
                'is_duplicate': True,
                'duplicate_type': duplicate_check['duplicate_type'],
                'confidence': duplicate_check['confidence'],
                'origin_hash': duplicate_check['origin_hash'],
                'recommendation': duplicate_check['recommendation']
            }
            
            if workspace_existing_task:
                response_data['existing_task'] = workspace_existing_task
            
            if workspace_similar_tasks:
                response_data['similar_tasks'] = workspace_similar_tasks
        else:
            response_data = {
                'success': True,
                'is_duplicate': False,
                'duplicate_type': 'none',
                'confidence': 0.0,
                'origin_hash': duplicate_check['origin_hash'],
                'recommendation': 'OK to create - no duplicates detected in workspace'
            }
        
        logger.info(
            f"Duplicate check (workspace {current_user.workspace_id}): "
            f"{response_data['duplicate_type']} (confidence: {response_data['confidence']:.2f})"
        )
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Failed to check duplicate: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>', methods=['PUT', 'PATCH'])
@login_required
def update_task(task_id):
    """Update task information (field-level updates)."""
    try:
        task = db.session.query(Task).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        data = request.get_json()
        old_status = task.status
        old_labels = task.labels
        old_snoozed_until = task.snoozed_until
        
        # CROWN⁴.5 Phase 2 Batch 2: Track old values for lifecycle event emission
        old_priority = task.priority
        old_due_date = task.due_date
        old_assigned_to_id = task.assigned_to_id
        
        # Update fields
        if 'title' in data:
            task.title = data['title'].strip()
        
        if 'description' in data:
            task.description = data['description'].strip() or None
        
        if 'priority' in data:
            task.priority = data['priority']
        
        if 'category' in data:
            task.category = data['category'].strip() or None
        
        if 'status' in data:
            new_status = data['status']
            if new_status != old_status:
                task.status = new_status
                
                # Update completion timestamp
                if new_status == 'completed' and old_status != 'completed':
                    task.completed_at = datetime.now()
                elif new_status != 'completed' and old_status == 'completed':
                    task.completed_at = None
        
        if 'due_date' in data:
            if data['due_date']:
                try:
                    task.due_date = date.fromisoformat(data['due_date'])
                except ValueError:
                    return jsonify({'success': False, 'message': 'Invalid due date format'}), 400
            else:
                task.due_date = None
        
        if 'assigned_to_id' in data:
            assigned_to_id = data['assigned_to_id']
            if assigned_to_id:
                assignee = db.session.query(User).filter_by(
                    id=assigned_to_id,
                    workspace_id=current_user.workspace_id
                ).first()
                if not assignee:
                    return jsonify({'success': False, 'message': 'Invalid assignee'}), 400
            task.assigned_to_id = assigned_to_id
        
        # CROWN⁴.5: Multi-assignee support via assignee_ids array
        if 'assignee_ids' in data:
            from models.task import TaskAssignee  # Import here to avoid circular dependency
            
            assignee_ids = data['assignee_ids']
            if not isinstance(assignee_ids, list):
                return jsonify({'success': False, 'message': 'assignee_ids must be an array'}), 400
            
            # CROWN⁴.5 Phase 2 Batch 2: Capture old assignee list before mutation
            old_assignee_ids = [a.user_id for a in db.session.query(TaskAssignee).filter_by(task_id=task.id).all()]
            
            # Validate all assignees are in workspace
            if assignee_ids:
                valid_users = db.session.query(User).filter(
                    User.id.in_(assignee_ids),
                    User.workspace_id == current_user.workspace_id,
                    User.active == True
                ).all()
                
                if len(valid_users) != len(set(assignee_ids)):
                    return jsonify({'success': False, 'message': 'One or more invalid assignee IDs'}), 400
            
            # Update junction table transactionally
            # 1. Delete existing assignments
            db.session.query(TaskAssignee).filter_by(task_id=task.id).delete()
            
            # 2. Add new assignments
            for user_id in assignee_ids:
                assignment = TaskAssignee(
                    task_id=task.id,
                    user_id=user_id,
                    assigned_by_user_id=current_user.id,
                    role='assignee'
                )
                db.session.add(assignment)
            
            # 3. Update assigned_to_id for backward compatibility (first assignee)
            task.assigned_to_id = assignee_ids[0] if assignee_ids else None
        else:
            # Track old assignee list even if not updating (for single assigned_to_id changes)
            from models.task import TaskAssignee
            old_assignee_ids = [a.user_id for a in db.session.query(TaskAssignee).filter_by(task_id=task.id).all()]
        
        if 'labels' in data:
            labels = data['labels']
            if isinstance(labels, list):
                task.labels = labels
            else:
                task.labels = []
        
        if 'snoozed_until' in data:
            if data['snoozed_until']:
                try:
                    # Parse and convert to naive UTC datetime
                    dt = datetime.fromisoformat(data['snoozed_until'].replace('Z', '+00:00'))
                    task.snoozed_until = dt.replace(tzinfo=None)
                except (ValueError, AttributeError):
                    return jsonify({'success': False, 'message': 'Invalid snoozed_until format'}), 400
            else:
                task.snoozed_until = None
        
        # CROWN⁴.5: Soft delete support (archive/restore via deleted_at timestamp)
        if 'deleted_at' in data:
            if data['deleted_at']:
                try:
                    # Parse and convert to naive UTC datetime
                    dt = datetime.fromisoformat(data['deleted_at'].replace('Z', '+00:00'))
                    task.deleted_at = dt.replace(tzinfo=None)
                    task.deleted_by_user_id = current_user.id
                except (ValueError, AttributeError):
                    return jsonify({'success': False, 'message': 'Invalid deleted_at format'}), 400
            else:
                # Restore from archive (undo)
                task.deleted_at = None
                task.deleted_by_user_id = None
        
        task.updated_at = datetime.now()
        db.session.commit()
        
        # CROWN⁴.5 Phase 2 Batch 1: Emit TASK_UPDATE_CORE event
        try:
            meeting = task.meeting
            task_data = task.to_dict()
            task_data['action'] = 'updated'
            task_data['meeting_title'] = meeting.title if meeting else 'Unknown'
            task_data['changes'] = {
                'status_changed': old_status != task.status,
                'old_status': old_status,
                'new_status': task.status
            }
            
            event = event_sequencer.create_event(
                event_type=EventType.TASK_UPDATE_CORE,
                event_name=f"Task updated: {task.title}",
                payload={
                    'task_id': task.id,
                    'task': task_data,
                    'meeting_id': meeting.id if meeting else None,
                    'workspace_id': str(current_user.workspace_id),
                    'action': 'updated'
                },
                workspace_id=str(current_user.workspace_id),
                client_id=f"user_{current_user.id}"
            )
            # Broadcast event immediately
            event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
        except Exception as e:
            logger.error(f"Failed to emit TASK_UPDATE_CORE event: {e}")
        
        # CROWN⁴.5 Phase 2 Batch 2: Emit granular lifecycle events
        meeting = task.meeting
        workspace_id_str = str(current_user.workspace_id)
        client_id = f"user_{current_user.id}"
        
        # 1. TASK_PRIORITY_CHANGED
        if 'priority' in data and old_priority != task.priority:
            try:
                event = event_sequencer.create_event(
                    event_type=EventType.TASK_PRIORITY_CHANGED,
                    event_name=f"Task priority changed: {task.title}",
                    payload={
                        'task_id': task.id,
                        'task': task.to_dict(),
                        'old_value': old_priority,
                        'new_value': task.priority,
                        'changed_by': current_user.id,
                        'meeting_id': meeting.id if meeting else None,
                        'workspace_id': workspace_id_str
                    },
                    workspace_id=workspace_id_str,
                    client_id=client_id
                )
                event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
            except Exception as e:
                logger.error(f"Failed to emit TASK_PRIORITY_CHANGED event: {e}")
        
        # 2. TASK_STATUS_CHANGED
        if 'status' in data and old_status != task.status:
            try:
                event = event_sequencer.create_event(
                    event_type=EventType.TASK_STATUS_CHANGED,
                    event_name=f"Task status changed: {task.title}",
                    payload={
                        'task_id': task.id,
                        'task': task.to_dict(),
                        'old_value': old_status,
                        'new_value': task.status,
                        'changed_by': current_user.id,
                        'meeting_id': meeting.id if meeting else None,
                        'workspace_id': workspace_id_str
                    },
                    workspace_id=workspace_id_str,
                    client_id=client_id
                )
                event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
            except Exception as e:
                logger.error(f"Failed to emit TASK_STATUS_CHANGED event: {e}")
        
        # 3. TASK_DUE_DATE_CHANGED
        if 'due_date' in data and old_due_date != task.due_date:
            try:
                event = event_sequencer.create_event(
                    event_type=EventType.TASK_DUE_DATE_CHANGED,
                    event_name=f"Task due date changed: {task.title}",
                    payload={
                        'task_id': task.id,
                        'task': task.to_dict(),
                        'old_value': old_due_date.isoformat() if old_due_date else None,
                        'new_value': task.due_date.isoformat() if task.due_date else None,
                        'changed_by': current_user.id,
                        'meeting_id': meeting.id if meeting else None,
                        'workspace_id': workspace_id_str
                    },
                    workspace_id=workspace_id_str,
                    client_id=client_id
                )
                event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
            except Exception as e:
                logger.error(f"Failed to emit TASK_DUE_DATE_CHANGED event: {e}")
        
        # 4. TASK_ASSIGNED / TASK_UNASSIGNED (assignment delta logic)
        if 'assigned_to_id' in data or 'assignee_ids' in data:
            try:
                # Get current assignee list
                new_assignee_ids = [a.user_id for a in db.session.query(TaskAssignee).filter_by(task_id=task.id).all()]
                
                # Handle legacy single-assignee path (assigned_to_id only, no junction table)
                if 'assigned_to_id' in data and 'assignee_ids' not in data:
                    # Use old_assigned_to_id and task.assigned_to_id for diff
                    removed_users = set([old_assigned_to_id]) if old_assigned_to_id and old_assigned_to_id != task.assigned_to_id else set()
                    added_users = set([task.assigned_to_id]) if task.assigned_to_id and old_assigned_to_id != task.assigned_to_id else set()
                else:
                    # Use junction table diff for multi-assignee path
                    removed_users = set(old_assignee_ids) - set(new_assignee_ids)
                    added_users = set(new_assignee_ids) - set(old_assignee_ids)
                
                # Emit TASK_UNASSIGNED for removed users
                for user_id in removed_users:
                    event = event_sequencer.create_event(
                        event_type=EventType.TASK_UNASSIGNED,
                        event_name=f"Task unassigned: {task.title}",
                        payload={
                            'task_id': task.id,
                            'task': task.to_dict(),
                            'unassigned_user_id': user_id,
                            'changed_by': current_user.id,
                            'meeting_id': meeting.id if meeting else None,
                            'workspace_id': workspace_id_str
                        },
                        workspace_id=workspace_id_str,
                        client_id=client_id
                    )
                    event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
                
                # Emit TASK_ASSIGNED for added users
                for user_id in added_users:
                    event = event_sequencer.create_event(
                        event_type=EventType.TASK_ASSIGNED,
                        event_name=f"Task assigned: {task.title}",
                        payload={
                            'task_id': task.id,
                            'task': task.to_dict(),
                            'assigned_user_id': user_id,
                            'changed_by': current_user.id,
                            'meeting_id': meeting.id if meeting else None,
                            'workspace_id': workspace_id_str
                        },
                        workspace_id=workspace_id_str,
                        client_id=client_id
                    )
                    event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
            except Exception as e:
                logger.error(f"Failed to emit TASK_ASSIGNED/UNASSIGNED events: {e}")
        
        # Broadcast task_update event with specific event type (legacy for backward compatibility)
        meeting = task.meeting
        
        # Determine event type based on what changed
        if task.status == 'completed' and old_status != 'completed':
            action = 'completed'
            event_type = 'task_update:completed'
        elif 'snoozed_until' in data and task.snoozed_until != old_snoozed_until:
            action = 'updated'
            event_type = 'task_snooze'
        elif 'labels' in data and task.labels != old_labels:
            action = 'updated'
            event_type = 'task_update:labels'
        else:
            action = 'updated'
            event_type = 'task_update'
        
        task_dict = task.to_dict()
        task_dict['action'] = action
        task_dict['event_type'] = event_type
        task_dict['meeting_title'] = meeting.title if meeting else 'Unknown'
        
        # Add diff metadata for specific events
        if event_type == 'task_update:labels':
            task_dict['label_diff'] = {
                'old': old_labels or [],
                'new': task.labels or []
            }
        
        if event_type == 'task_snooze':
            task_dict['snooze_diff'] = {
                'old': old_snoozed_until.isoformat() if old_snoozed_until else None,
                'new': task.snoozed_until.isoformat() if task.snoozed_until else None
            }
        
        event_broadcaster.broadcast_task_update(
            task_id=task.id,
            task_data=task_dict,
            meeting_id=meeting.id if meeting else None,
            workspace_id=current_user.workspace_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Task updated successfully',
            'task': task.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    """Soft delete a task (CROWN⁴.5 Phase 1: 15s undo window)."""
    try:
        task = db.session.query(Task).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        # Check if already deleted
        if task.deleted_at is not None:
            return jsonify({'success': False, 'message': 'Task already deleted'}), 400
        
        # CROWN⁴.5 Phase 1: Soft delete instead of hard delete
        task.deleted_at = datetime.now()
        task.deleted_by_user_id = current_user.id
        task.updated_at = datetime.now()
        
        # Store task info for broadcast
        task_dict = task.to_dict()
        task_dict['action'] = 'deleted'
        task_dict['event_type'] = 'task_delete'
        task_dict['undo_window_seconds'] = 15  # 15-second undo window
        meeting = task.meeting
        meeting_title = meeting.title if meeting else 'Unknown'
        meeting_id = meeting.id if meeting else None
        task_dict['meeting_title'] = meeting_title
        workspace_id = current_user.workspace_id
        
        db.session.commit()
        
        # CROWN⁴.5 Phase 2 Batch 1: Emit TASK_DELETE_SOFT event
        try:
            task_data_for_event = task.to_dict()
            task_data_for_event['action'] = 'deleted'
            task_data_for_event['undo_window_seconds'] = 15
            
            event = event_sequencer.create_event(
                event_type=EventType.TASK_DELETE_SOFT,
                event_name=f"Task soft deleted: {task.title}",
                payload={
                    'task_id': task.id,
                    'task': task_data_for_event,
                    'meeting_id': meeting_id,
                    'workspace_id': str(workspace_id),
                    'action': 'deleted'
                },
                workspace_id=str(workspace_id),
                client_id=f"user_{current_user.id}"
            )
            # Broadcast event immediately
            event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{workspace_id}")
        except Exception as e:
            logger.error(f"Failed to emit TASK_DELETE_SOFT event: {e}")
        
        # Broadcast task_delete event (legacy for backward compatibility)
        event_broadcaster.broadcast_task_update(
            task_id=task.id,
            task_data=task_dict,
            meeting_id=meeting_id,
            workspace_id=workspace_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Task deleted successfully (15s undo window)',
            'task_id': task.id,
            'undo_window_seconds': 15
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>/undo-delete', methods=['POST'])
@login_required
def undo_delete_task(task_id):
    """Restore a soft-deleted task (CROWN⁴.5 Phase 1: undo within 15s window)."""
    try:
        task = db.session.query(Task).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        # Check if task is deleted
        if task.deleted_at is None:
            return jsonify({'success': False, 'message': 'Task is not deleted'}), 400
        
        # Check if undo window (15 seconds) has expired
        undo_deadline = task.deleted_at + timedelta(seconds=15)
        if datetime.now() > undo_deadline:
            return jsonify({
                'success': False, 
                'message': 'Undo window expired (15s limit)'
            }), 410  # 410 Gone
        
        # Restore task
        task.deleted_at = None
        task.deleted_by_user_id = None
        task.updated_at = datetime.now()
        
        task_dict = task.to_dict()
        task_dict['action'] = 'restored'
        task_dict['event_type'] = 'task_restore'
        meeting = task.meeting
        task_dict['meeting_title'] = meeting.title if meeting else 'Unknown'
        
        db.session.commit()
        
        # CROWN⁴.5 Phase 2 Batch 1: Emit TASK_RESTORE event
        try:
            task_data_restore = task.to_dict()
            task_data_restore['action'] = 'restored'
            task_data_restore['meeting_title'] = meeting.title if meeting else 'Unknown'
            
            event = event_sequencer.create_event(
                event_type=EventType.TASK_RESTORE,
                event_name=f"Task restored: {task.title}",
                payload={
                    'task_id': task.id,
                    'task': task_data_restore,
                    'meeting_id': meeting.id if meeting else None,
                    'workspace_id': str(current_user.workspace_id),
                    'action': 'restored'
                },
                workspace_id=str(current_user.workspace_id),
                client_id=f"user_{current_user.id}"
            )
            # Broadcast event immediately
            event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
        except Exception as e:
            logger.error(f"Failed to emit TASK_RESTORE event: {e}")
        
        # Broadcast task_restore event (legacy for backward compatibility)
        event_broadcaster.broadcast_task_update(
            task_id=task.id,
            task_data=task_dict,
            meeting_id=meeting.id if meeting else None,
            workspace_id=current_user.workspace_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Task restored successfully',
            'task': task.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>/accept', methods=['POST'])
@login_required
def accept_task_proposal(task_id):
    """Accept an AI-proposed task (change emotional_state from pending_suggest to accepted)."""
    try:
        task = db.session.query(Task).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        if task.emotional_state != 'pending_suggest':
            return jsonify({'success': False, 'message': 'Task is not in pending_suggest state'}), 400
        
        task.emotional_state = 'accepted'
        task.status = 'todo'
        task.updated_at = datetime.now()
        db.session.commit()
        
        meeting = task.meeting
        task_dict = task.to_dict()
        task_dict['action'] = 'accepted'
        task_dict['event_type'] = 'task_proposal:accepted'
        task_dict['meeting_title'] = meeting.title if meeting else 'Unknown'
        
        event_broadcaster.broadcast_task_update(
            task_id=task.id,
            task_data=task_dict,
            meeting_id=meeting.id if meeting else None,
            workspace_id=current_user.workspace_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Task accepted successfully',
            'task': task.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>/reject', methods=['POST'])
@login_required
def reject_task_proposal(task_id):
    """Reject an AI-proposed task (delete it)."""
    try:
        task = db.session.query(Task).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        if task.emotional_state != 'pending_suggest':
            return jsonify({'success': False, 'message': 'Task is not in pending_suggest state'}), 400
        
        task_dict = task.to_dict()
        task_dict['action'] = 'rejected'
        task_dict['event_type'] = 'task_proposal:rejected'
        meeting = task.meeting
        task_dict['meeting_title'] = meeting.title if meeting else 'Unknown'
        meeting_id = meeting.id if meeting else None
        workspace_id = current_user.workspace_id
        
        db.session.delete(task)
        db.session.commit()
        
        event_broadcaster.broadcast_task_update(
            task_id=task_id,
            task_data=task_dict,
            meeting_id=meeting_id,
            workspace_id=workspace_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Task rejected successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>/merge', methods=['POST'])
@login_required
def merge_tasks(task_id):
    """Merge source task into target task."""
    try:
        # Get target task (the one being merged into)
        target_task = db.session.query(Task).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not target_task:
            return jsonify({'success': False, 'message': 'Target task not found'}), 404
        
        # Guard against malformed/empty JSON - silent=True returns None instead of raising BadRequest
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Request body must be a JSON object'}), 400
        
        source_task_id = data.get('source_task_id')
        
        if not source_task_id:
            return jsonify({'success': False, 'message': 'source_task_id is required'}), 400
        
        # Convert source_task_id to int for comparison
        try:
            source_task_id = int(source_task_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid source_task_id format'}), 400
        
        # Prevent merging a task into itself
        if source_task_id == task_id:
            return jsonify({'success': False, 'message': 'Cannot merge a task into itself'}), 400
        
        # Get source task (the one being merged from and deleted) - BEFORE any mutations
        source_task = db.session.query(Task).join(Meeting).filter(
            Task.id == source_task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not source_task:
            return jsonify({'success': False, 'message': 'Source task not found'}), 404
        
        # ALL VALIDATION PASSED - Now perform merge data operations
        # Combine labels (unique)
        target_labels = set(target_task.labels or [])
        source_labels = set(source_task.labels or [])
        merged_labels = list(target_labels | source_labels)
        
        # Keep higher priority
        priority_rank = {'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}
        target_priority_rank = priority_rank.get(target_task.priority, 2)
        source_priority_rank = priority_rank.get(source_task.priority, 2)
        merged_priority = target_task.priority if target_priority_rank >= source_priority_rank else source_task.priority
        
        # Combine descriptions
        merged_description = target_task.description or ''
        if source_task.description and source_task.description not in merged_description:
            if merged_description:
                merged_description = f"{merged_description}\n\n[Merged from another task]\n{source_task.description}"
            else:
                merged_description = source_task.description
        
        # Store old values for merge_diff
        old_labels = target_task.labels
        old_priority = target_task.priority
        old_description = target_task.description
        
        # Update target task
        target_task.labels = merged_labels
        target_task.priority = merged_priority
        target_task.description = merged_description
        target_task.updated_at = datetime.now()
        
        # Store source task info before deletion
        source_task_dict = source_task.to_dict()
        
        # Delete source task
        db.session.delete(source_task)
        db.session.commit()
        
        # Broadcast task_merge event
        meeting = target_task.meeting
        task_dict = target_task.to_dict()
        task_dict['action'] = 'updated'
        task_dict['event_type'] = 'task_merge'
        task_dict['meeting_title'] = meeting.title if meeting else 'Unknown'
        task_dict['merge_diff'] = {
            'source_task_id': source_task_id,
            'source_task_title': source_task_dict.get('title'),
            'old_labels': old_labels or [],
            'new_labels': merged_labels,
            'old_priority': old_priority,
            'new_priority': merged_priority
        }
        
        event_broadcaster.broadcast_task_update(
            task_id=target_task.id,
            task_data=task_dict,
            meeting_id=meeting.id if meeting else None,
            workspace_id=current_user.workspace_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Tasks merged successfully',
            'task': target_task.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/bulk/complete', methods=['POST'])
@login_required
def bulk_complete_tasks():
    """Bulk complete multiple tasks."""
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Invalid request format'}), 400
        
        task_ids = data.get('task_ids', [])
        if not isinstance(task_ids, list) or len(task_ids) == 0:
            return jsonify({'success': False, 'message': 'task_ids is required'}), 400
        
        # Convert to integers
        try:
            task_ids = [int(tid) for tid in task_ids]
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid task IDs'}), 400
        
        print(f"📋 [BULK COMPLETE] Requested task IDs: {task_ids}")
        print(f"🔑 [BULK COMPLETE] User workspace: {current_user.workspace_id}")
        
        # Fetch all tasks and verify ownership
        tasks = db.session.query(Task).join(Meeting).filter(
            Task.id.in_(task_ids),
            Meeting.workspace_id == current_user.workspace_id
        ).all()
        
        found_ids = [t.id for t in tasks]
        print(f"✅ [BULK COMPLETE] Found {len(tasks)} tasks: {found_ids}")
        
        if len(tasks) != len(task_ids):
            missing_ids = set(task_ids) - set(found_ids)
            print(f"❌ [BULK COMPLETE] Missing {len(missing_ids)} tasks: {missing_ids}")
            return jsonify({'success': False, 'message': 'Some tasks not found'}), 404
        
        # Mark all as completed
        from datetime import datetime
        for task in tasks:
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Broadcast bulk operation event
        event_broadcaster.broadcast_task_update(
            task_id=None,
            task_data={
                'event_type': 'task_multiselect:bulk',
                'action': 'bulk_complete',
                'task_ids': task_ids,
                'count': len(task_ids)
            },
            meeting_id=None,
            workspace_id=current_user.workspace_id,
            user_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': f'{len(tasks)} tasks completed',
            'count': len(tasks)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/bulk/delete', methods=['POST'])
@login_required
def bulk_delete_tasks():
    """Bulk delete multiple tasks."""
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Invalid request format'}), 400
        
        task_ids = data.get('task_ids', [])
        if not isinstance(task_ids, list) or len(task_ids) == 0:
            return jsonify({'success': False, 'message': 'task_ids is required'}), 400
        
        # Convert to integers
        try:
            task_ids = [int(tid) for tid in task_ids]
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid task IDs'}), 400
        
        # Fetch all tasks and verify ownership
        tasks = db.session.query(Task).join(Meeting).filter(
            Task.id.in_(task_ids),
            Meeting.workspace_id == current_user.workspace_id,
            Task.deleted_at.is_(None)  # Only non-deleted tasks
        ).all()
        
        if len(tasks) != len(task_ids):
            return jsonify({'success': False, 'message': 'Some tasks not found or already deleted'}), 404
        
        # CROWN⁴.5: Soft delete all tasks (consistent with single delete)
        deleted_timestamp = datetime.now()
        for task in tasks:
            task.deleted_at = deleted_timestamp
            task.deleted_by_user_id = current_user.id
            task.updated_at = deleted_timestamp
        
        db.session.commit()
        
        # Broadcast bulk operation event
        event_broadcaster.broadcast_task_update(
            task_id=None,
            task_data={
                'event_type': 'task_multiselect:bulk',
                'action': 'bulk_delete',
                'task_ids': task_ids,
                'count': len(task_ids),
                'undo_window_seconds': 15  # CROWN⁴.5: 15-second undo window
            },
            meeting_id=None,
            workspace_id=current_user.workspace_id,
            user_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': f'{len(tasks)} tasks deleted (15s undo window)',
            'count': len(tasks),
            'undo_window_seconds': 15
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/bulk/label', methods=['POST'])
@login_required
def bulk_add_label():
    """Bulk add label to multiple tasks."""
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Invalid request format'}), 400
        
        task_ids = data.get('task_ids', [])
        label = data.get('label', '').strip()
        
        if not isinstance(task_ids, list) or len(task_ids) == 0:
            return jsonify({'success': False, 'message': 'task_ids is required'}), 400
        
        if not label:
            return jsonify({'success': False, 'message': 'label is required'}), 400
        
        # Convert to integers
        try:
            task_ids = [int(tid) for tid in task_ids]
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid task IDs'}), 400
        
        # Fetch all tasks and verify ownership
        tasks = db.session.query(Task).join(Meeting).filter(
            Task.id.in_(task_ids),
            Meeting.workspace_id == current_user.workspace_id
        ).all()
        
        if len(tasks) != len(task_ids):
            return jsonify({'success': False, 'message': 'Some tasks not found'}), 404
        
        # Add label to all tasks
        for task in tasks:
            if task.labels is None:
                task.labels = []
            if label not in task.labels:
                task.labels.append(label)
        
        db.session.commit()
        
        # Broadcast bulk operation event
        event_broadcaster.broadcast_task_update(
            task_id=None,
            task_data={
                'event_type': 'task_multiselect:bulk',
                'action': 'bulk_label',
                'task_ids': task_ids,
                'label': label,
                'count': len(task_ids)
            },
            meeting_id=None,
            workspace_id=current_user.workspace_id,
            user_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': f'Label "{label}" added to {len(tasks)} tasks',
            'count': len(tasks),
            'label': label
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>/track-transcript-jump', methods=['POST'])
@login_required
def track_transcript_jump(task_id):
    """Track when user jumps to transcript from task."""
    try:
        task = db.session.query(Task).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        # Broadcast task_link:jump_to_span event
        meeting = task.meeting
        task_dict = task.to_dict()
        task_dict['action'] = 'transcript_jump'
        task_dict['event_type'] = 'task_link:jump_to_span'
        task_dict['meeting_title'] = meeting.title if meeting else 'Unknown'
        
        event_broadcaster.broadcast_task_update(
            task_id=task.id,
            task_data=task_dict,
            meeting_id=meeting.id if meeting else None,
            workspace_id=current_user.workspace_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Transcript jump tracked'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>/status', methods=['PUT'])
@login_required
def update_task_status(task_id):
    """Update only the status of a task (for quick status changes)."""
    try:
        task = db.session.query(Task).join(Meeting).filter(
            Task.id == task_id,
            Meeting.workspace_id == current_user.workspace_id
        ).first()
        
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'success': False, 'message': 'Status is required'}), 400
        
        if new_status not in ['todo', 'in_progress', 'completed', 'cancelled']:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400
        
        old_status = task.status
        old_completed_at = task.completed_at  # Capture for completion timestamp diff
        
        # Early return if status unchanged (prevent spurious events and unnecessary commits)
        if old_status == new_status:
            return jsonify({
                'success': True,
                'message': 'Task status unchanged',
                'task': task.to_dict()
            })
        
        task.status = new_status
        
        # Update completion fields
        if new_status == 'completed' and old_status != 'completed':
            task.completed_at = datetime.now()
        elif new_status != 'completed' and old_status == 'completed':
            task.completed_at = None
        
        task.updated_at = datetime.now()
        db.session.commit()
        
        # CROWN⁴.5 Phase 2 Batch 2: Emit TASK_STATUS_CHANGED event with completion metadata
        try:
            meeting = task.meeting
            event = event_sequencer.create_event(
                event_type=EventType.TASK_STATUS_CHANGED,
                event_name=f"Task status changed: {task.title}",
                payload={
                    'task_id': task.id,
                    'task': task.to_dict(),
                    'old_value': old_status,
                    'new_value': task.status,
                    'old_completed_at': old_completed_at.isoformat() if old_completed_at else None,
                    'new_completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'changed_by': current_user.id,
                    'meeting_id': meeting.id if meeting else None,
                    'workspace_id': str(current_user.workspace_id)
                },
                workspace_id=str(current_user.workspace_id),
                client_id=f"user_{current_user.id}"
            )
            event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
        except Exception as e:
            logger.error(f"Failed to emit TASK_STATUS_CHANGED event: {e}")
        
        # Broadcast task_update event
        meeting = task.meeting
        action = 'completed' if new_status == 'completed' and old_status != 'completed' else 'updated'
        task_dict = task.to_dict()
        task_dict['action'] = action
        task_dict['meeting_title'] = meeting.title if meeting else 'Unknown'
        event_broadcaster.broadcast_task_update(
            task_id=task.id,
            task_data=task_dict,
            meeting_id=meeting.id if meeting else None,
            workspace_id=current_user.workspace_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Task status updated successfully',
            'task': task.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@api_tasks_bp.route('/bulk-update', methods=['PUT'])
@login_required
def bulk_update_tasks():
    """Update multiple tasks at once."""
    try:
        data = request.get_json()
        task_ids = data.get('task_ids', [])
        updates = data.get('updates', {})
        
        if not task_ids:
            return jsonify({'success': False, 'message': 'Task IDs are required'}), 400
        
        # Get tasks that belong to user's workspace
        tasks = db.session.query(Task).join(Meeting).filter(
            Task.id.in_(task_ids),
            Meeting.workspace_id == current_user.workspace_id
        ).all()
        
        updated_count = 0
        for task in tasks:
            if 'status' in updates:
                new_status = updates['status']
                old_status = task.status
                task.status = new_status
                
                # Handle completion logic
                if new_status == 'completed' and old_status != 'completed':
                    task.completed_at = datetime.now()
                elif new_status != 'completed' and old_status == 'completed':
                    task.completed_at = None
            
            if 'priority' in updates:
                task.priority = updates['priority']
            
            if 'assigned_to_id' in updates:
                task.assigned_to_id = updates['assigned_to_id']
            
            task.updated_at = datetime.now()
            updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} tasks successfully',
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@api_tasks_bp.route('/my-tasks', methods=['GET'])
@login_required
def get_my_tasks():
    """Get tasks assigned to current user."""
    try:
        status = request.args.get('status', None)
        
        query = db.session.query(Task).join(Meeting).filter(
            Task.assigned_to_id == current_user.id,
            Meeting.workspace_id == current_user.workspace_id
        )
        
        if status:
            query = query.filter(Task.status == status)
        
        tasks = query.order_by(
            Task.priority.desc(),
            Task.due_date.asc().nullslast(),
            Task.created_at.desc()
        ).all()
        
        # Group by status for dashboard
        task_groups = {
            'todo': [],
            'in_progress': [],
            'completed': []
        }
        
        for task in tasks:
            if task.status in task_groups:
                task_groups[task.status].append(task.to_dict())
        
        return jsonify({
            'success': True,
            'tasks': task_groups,
            'total_assigned': len(tasks)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@api_tasks_bp.route('/stats', methods=['GET'])
@with_etag
@login_required
def get_task_stats():
    """Get task statistics for current workspace."""
    try:
        workspace_id = current_user.workspace_id
        
        # Basic counts
        total_tasks = db.session.query(Task).join(Meeting).filter(
            Meeting.workspace_id == workspace_id
        ).count()
        
        completed_tasks = db.session.query(Task).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Task.status == 'completed'
        ).count()
        
        overdue_tasks = db.session.query(Task).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Task.due_date < date.today(),
            Task.status.in_(['todo', 'in_progress'])
        ).count()
        
        my_tasks = db.session.query(Task).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Task.assigned_to_id == current_user.id,
            Task.status.in_(['todo', 'in_progress'])
        ).count()
        
        # Tasks by status
        status_counts = db.session.query(
            Task.status,
            func.count(Task.id).label('count')
        ).join(Meeting).filter(
            Meeting.workspace_id == workspace_id
        ).group_by(Task.status).all()
        
        status_distribution = {status: count for status, count in status_counts}
        
        # Tasks by priority
        priority_counts = db.session.query(
            Task.priority,
            func.count(Task.id).label('count')
        ).join(Meeting).filter(
            Meeting.workspace_id == workspace_id
        ).group_by(Task.priority).all()
        
        priority_distribution = {priority: count for priority, count in priority_counts}
        
        return jsonify({
            'success': True,
            'stats': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'overdue_tasks': overdue_tasks,
                'my_active_tasks': my_tasks,
                'completion_rate': round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0,
                'status_distribution': status_distribution,
                'priority_distribution': priority_distribution
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@api_tasks_bp.route('/overdue', methods=['GET'])
@login_required
def get_overdue_tasks():
    """Get overdue tasks for current workspace."""
    try:
        overdue_tasks = db.session.query(Task).join(Meeting).filter(
            Meeting.workspace_id == current_user.workspace_id,
            Task.due_date < date.today(),
            Task.status.in_(['todo', 'in_progress'])
        ).order_by(Task.due_date.asc()).all()
        
        return jsonify({
            'success': True,
            'overdue_tasks': [task.to_dict() for task in overdue_tasks],
            'count': len(overdue_tasks)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@api_tasks_bp.route('/create', methods=['POST'])
def create_live_task():
    """Create a task from highlighted text in live transcription (no authentication required for live sessions)."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({'success': False, 'message': 'Title is required'}), 400
        
        if not data.get('session_id'):
            return jsonify({'success': False, 'message': 'Session ID is required'}), 400
        
        # Find or create a session record
        session_external_id = data['session_id']
        session = db.session.query(Session).filter_by(external_id=session_external_id).first()
        
        if not session:
            # Create a new session record for this live transcription
            # Note: No user_id/workspace_id for anonymous live sessions
            session = Session(
                external_id=session_external_id,
                title=f"Live Transcription - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                status="active",
                started_at=datetime.utcnow()
            )
            db.session.add(session)
            db.session.flush()  # Get the session ID
        
        # Create or find a meeting record linked to this session
        meeting = db.session.query(Meeting).filter(Meeting.session.has(id=session.id)).first()
        
        if not meeting:
            # Get default workspace for anonymous sessions
            default_workspace = db.session.query(Workspace).first()
            workspace_id = default_workspace.id if default_workspace else 1
            
            # Get default user for anonymous sessions  
            default_user = db.session.query(User).first()
            user_id = default_user.id if default_user else None
            
            # Create a meeting record
            meeting = Meeting(
                title=f"Live Meeting - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                status="in_progress",
                workspace_id=workspace_id,
                organizer_id=user_id if user_id else 1,  # Required field
                created_at=datetime.utcnow()
            )
            db.session.add(meeting)
            db.session.flush()  # Get the meeting ID
            
            # Link session to meeting (correct direction)
            session.meeting_id = meeting.id
            db.session.flush()
        
        # Parse due date from natural language if provided
        due_date = None
        due_date_text = data.get('due_date_text', '').strip()
        if due_date_text:
            due_date = parse_natural_due_date(due_date_text)
        
        # Create the task
        # Store context and assignee in extraction_context for live sessions
        extraction_ctx = {}
        if data.get('context'):
            extraction_ctx['source_text'] = data.get('context', '')
        if data.get('assignee'):
            extraction_ctx['assignee_name'] = data.get('assignee', '').strip()
        
        task = Task(
            title=data['title'].strip(),
            description=data.get('description', '').strip() or None,
            meeting_id=meeting.id,
            priority=data.get('priority', 'medium'),
            category='live_transcription',
            due_date=due_date,
            status='todo',
            created_by_id=None,  # No user authentication for live sessions
            extracted_by_ai=False,
            extraction_context=extraction_ctx if extraction_ctx else None
        )
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Task created successfully',
            'task': {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'priority': task.priority,
                'status': task.status,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'extraction_context': task.extraction_context,
                'created_at': task.created_at.isoformat()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

def parse_natural_due_date(due_date_text):
    """Parse natural language due dates like 'tomorrow', 'next week', 'friday'."""
    try:
        text = due_date_text.lower().strip()
        today = date.today()
        
        if text in ['today']:
            return today
        elif text in ['tomorrow']:
            return today + timedelta(days=1)
        elif text in ['next week']:
            days_ahead = 7 - today.weekday()
            return today + timedelta(days=days_ahead)
        elif text in ['end of week', 'friday']:
            days_ahead = 4 - today.weekday()  # Friday is day 4
            if days_ahead < 0:  # If Friday has passed, get next Friday
                days_ahead += 7
            return today + timedelta(days=days_ahead)
        elif text in ['monday']:
            days_ahead = 0 - today.weekday()
            if days_ahead <= 0:  # If Monday has passed, get next Monday
                days_ahead += 7
            return today + timedelta(days=days_ahead)
        elif text in ['next month']:
            if today.month == 12:
                return date(today.year + 1, 1, today.day)
            else:
                return date(today.year, today.month + 1, today.day)
        
        # Try to parse as ISO date
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
            
        # Default to one week from now if we can't parse
        return today + timedelta(days=7)
        
    except Exception:
        # If all parsing fails, default to one week from now
        return date.today() + timedelta(days=7)

@api_tasks_bp.route('', methods=['GET'])
def get_all_tasks():
    """
    List all action items across sessions.
    Query params:
      - session_id: (optional) filter by session
      - completed: (optional) "true"/"false" to filter by completion status
    """
    session_filter = request.args.get('session_id', type=int)
    completed_filter = request.args.get('completed')
    try:
        stmt = select(Summary).filter(Summary.actions != None)
        if session_filter:
            stmt = stmt.filter(Summary.session_id == session_filter)
        summaries = db.session.execute(stmt).scalars().all()
        tasks = []
        for summary in summaries:
            if not summary.actions: 
                continue
            for idx, task in enumerate(summary.actions):
                # Apply completion filter if provided
                if completed_filter is not None:
                    want_completed = completed_filter.lower() in ['1', 'true', 'yes']
                    if task.get('completed', False) != want_completed:
                        continue
                tasks.append({
                    "session_id": summary.session_id,
                    "task_index": idx,
                    "text": task.get("text"),
                    "owner": task.get("owner"),
                    "due": task.get("due"),
                    "completed": task.get("completed", False)
                })
        return jsonify({"success": True, "tasks": tasks}), 200
    except Exception as e:
        logger.error(f"Error retrieving tasks: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve tasks"}), 500

@api_tasks_bp.route('/users', methods=['GET'])
@login_required
def list_assignable_users():
    """
    Get list of users in workspace for assignee autocomplete.
    CROWN⁴.5 Event #7: Assignee selection support.
    """
    try:
        # Get users in current workspace
        stmt = select(User).where(User.workspace_id == current_user.workspace_id)
        users = db.session.execute(stmt).scalars().all()
        
        return jsonify({
            "success": True,
            "users": [{
                "id": user.id,
                "name": user.display_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                "username": user.username,
                "email": user.email
            } for user in users]
        }), 200
    except Exception as e:
        logger.error(f"Error fetching assignable users: {e}")
        return jsonify({"success": False, "error": "Failed to fetch users"}), 500


@api_tasks_bp.route('/ai-proposals/<int:meeting_id>', methods=['GET'])
@login_required
def get_ai_task_proposals(meeting_id):
    """
    Get AI-proposed tasks for a meeting.
    CROWN⁴.5 Event #10: AI task proposals from transcript.
    """
    try:
        import asyncio
        from services.task_extraction_service import TaskExtractionService
        
        # Check if meeting belongs to user's workspace
        meeting = db.session.get(Meeting, meeting_id)
        if not meeting or meeting.workspace_id != current_user.workspace_id:
            return jsonify({"success": False, "error": "Meeting not found"}), 404
        
        # Extract tasks using AI (run async service in sync context)
        extraction_service = TaskExtractionService()
        proposed_tasks = asyncio.run(extraction_service.extract_tasks_from_meeting(meeting_id))
        
        return jsonify({
            "success": True,
            "proposals": [{
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "confidence": task.confidence,
                "assigned_to": task.assigned_to,
                "category": task.category,
                "context": task.context
            } for task in proposed_tasks]
        }), 200
    except Exception as e:
        logger.error(f"Error fetching AI task proposals: {e}")
        return jsonify({"success": False, "error": "Failed to fetch AI proposals"}), 500


@api_tasks_bp.route('/create-from-proposal', methods=['POST'])
@login_required
def create_task_from_proposal():
    """
    Create a task from an AI proposal.
    CROWN⁴.5 Event #10: Click-to-create from AI proposal.
    """
    try:
        data = request.get_json()
        
        # Create task from proposal
        task = Task(
            title=data.get('title'),
            description=data.get('description'),
            priority=data.get('priority', 'medium'),
            meeting_id=data.get('meeting_id'),
            created_by_id=current_user.id,
            extracted_by_ai=True,
            confidence_score=data.get('confidence', 0.0),
            extraction_context=data.get('context', {}),
            source='ai_extraction'
        )
        
        db.session.add(task)
        db.session.commit()
        
        # CROWN⁴.5 Phase 2 Batch 1: Emit TASK_CREATE_AI_ACCEPT event
        try:
            meeting = task.meeting
            task_data = task.to_dict()
            task_data['action'] = 'ai_accepted'
            
            event = event_sequencer.create_event(
                event_type=EventType.TASK_CREATE_AI_ACCEPT,
                event_name=f"AI task accepted: {task.title}",
                payload={
                    'task_id': task.id,
                    'task': task_data,
                    'meeting_id': task.meeting_id,
                    'workspace_id': str(current_user.workspace_id),
                    'action': 'ai_accepted'
                },
                workspace_id=str(current_user.workspace_id) if meeting and current_user.workspace_id else None,
                client_id=f"user_{current_user.id}"
            )
            # Broadcast event immediately
            event_broadcaster.emit_event(event, namespace="/tasks", room=f"workspace_{current_user.workspace_id}")
        except Exception as e:
            logger.error(f"Failed to emit TASK_CREATE_AI_ACCEPT event: {e}")
        
        # Broadcast via WebSocket (legacy for backward compatibility)
        event_broadcaster.broadcast_task_update(
            task_id=task.id,
            task_data={"title": task.title, "priority": task.priority},
            meeting_id=task.meeting_id,
            workspace_id=current_user.workspace_id
        )
        
        logger.info(f"✅ Task created from AI proposal: {task.title}")
        
        return jsonify({
            "success": True,
            "task": {
                "id": task.id,
                "title": task.title,
                "priority": task.priority
            }
        }), 201
    except Exception as e:
        logger.error(f"Error creating task from proposal: {e}")
        db.session.rollback()
        return jsonify({"success": False, "error": "Failed to create task"}), 500


@api_tasks_bp.route('/<int:session_id>/<int:task_index>', methods=['PUT'])
def update_summary_task(session_id, task_index):
    """
    Update a specific task identified by session ID and index.
    Allows marking complete or editing fields (same JSON format as summary route).
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"success": False, "error": "No update data provided"}), 400
    try:
        stmt = select(Summary).filter(Summary.session_id == session_id).order_by(Summary.created_at.desc())
        summary = db.session.execute(stmt).scalar_one_or_none()
        if not summary or not summary.actions or task_index >= len(summary.actions):
            return jsonify({"success": False, "error": "Task not found"}), 404
        task = summary.actions[task_index]
        if 'text' in data: task['text'] = data['text']
        if 'owner' in data: task['owner'] = data['owner']
        if 'due' in data: task['due'] = data['due']
        if 'completed' in data: task['completed'] = bool(data['completed'])
        summary.actions = summary.actions
        db.session.commit()
        logger.info(f"Task updated for session {session_id}, index {task_index}: {data}")
        return jsonify({"success": True, "task": task}), 200
    except Exception as e:
        logger.error(f"Error updating task {task_index} in session {session_id}: {e}")
        db.session.rollback()
        return jsonify({"success": False, "error": "Failed to update task"}), 500


@api_tasks_bp.route('/workspace-users', methods=['GET'])
@login_required
def get_workspace_users():
    """
    Get list of users in current workspace for assignee selector.
    Returns user id, name, avatar_url for display in UI.
    """
    try:
        if not current_user.workspace_id:
            return jsonify({
                'success': False,
                'message': 'User not in a workspace'
            }), 400
        
        # Fetch all active users in the workspace
        stmt = select(User).where(
            User.workspace_id == current_user.workspace_id,
            User.active == True
        ).order_by(User.display_name.asc().nullslast(), User.username.asc())
        
        users = db.session.execute(stmt).scalars().all()
        
        # Format user data for frontend
        user_list = []
        for user in users:
            user_list.append({
                'id': user.id,
                'username': user.username,
                'display_name': user.display_name,
                'full_name': user.full_name,
                'avatar_url': user.avatar_url,
                'is_current_user': user.id == current_user.id
            })
        
        return jsonify({
            'success': True,
            'users': user_list,
            'current_user_id': current_user.id
        })
        
    except Exception as e:
        logger.error(f"Error fetching workspace users: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# CROWN⁴.5 Phase 3: Reorder tasks via drag-and-drop
@api_tasks_bp.route('/reorder', methods=['POST'])
@login_required
def reorder_tasks():
    """
    Update task positions after drag-and-drop reordering.
    Accepts an array of {task_id, position} updates.
    """
    try:
        data = request.get_json()
        updates = data.get('updates', [])
        
        if not updates:
            return jsonify({'success': False, 'message': 'No updates provided'}), 400
        
        # Validate that all task IDs belong to user's workspace
        task_ids = [update['task_id'] for update in updates]
        
        stmt = select(Task).join(Meeting).where(
            and_(
                Task.id.in_(task_ids),
                Meeting.workspace_id == current_user.workspace_id,
                Task.deleted_at.is_(None)  # Cannot reorder deleted tasks
            )
        )
        
        tasks = db.session.execute(stmt).scalars().all()
        
        if len(tasks) != len(task_ids):
            return jsonify({'success': False, 'message': 'One or more tasks not found'}), 404
        
        # Update task positions
        updated_task_ids = []
        for update in updates:
            task_id = update['task_id']
            new_position = update['position']
            
            task = next((t for t in tasks if t.id == task_id), None)
            if task:
                task.position = new_position
                updated_task_ids.append(task_id)
        
        db.session.commit()
        
        logger.info(f"[REORDER] Updated positions for {len(updated_task_ids)} tasks by user {current_user.id}")
        
        # TODO: Broadcast reorder event to WebSocket clients
        # EventBroadcaster.broadcast_task_reorder needs to be implemented
        # For now, reordering works without real-time sync across tabs
        
        return jsonify({
            'success': True,
            'message': f'Updated positions for {len(updated_task_ids)} tasks',
            'updated_task_ids': updated_task_ids
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[REORDER] Error reordering tasks: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


# CROWN⁴.5 Phase 1: Admin endpoint for purge job
@api_tasks_bp.route('/admin/purge', methods=['POST'])
@login_required
def admin_purge_deleted_tasks():
    """
    Admin endpoint to manually trigger purge of soft-deleted tasks (T+7d).
    Useful for testing and manual cleanup.
    SECURITY: Admin-only access required.
    """
    from services.task_purge_job import purge_deleted_tasks, get_purgeable_task_count
    
    # SECURITY FIX: Check if user is admin/superuser
    # For now, we'll comment this out and remove the endpoint from production
    # In production, this should be a cron job, not an API endpoint
    return jsonify({
        'success': False,
        'error': 'This endpoint is disabled. Use scheduled background job instead.'
    }), 403
    
    # Uncomment below for development testing only (with proper admin check)
    # try:
    #     # Check purgeable count first
    #     purgeable_count = get_purgeable_task_count()
    #     
    #     if purgeable_count == 0:
    #         return jsonify({
    #             'success': True,
    #             'message': 'No tasks to purge',
    #             'purgeable_count': 0,
    #             'purged_count': 0
    #         })
    #     
    #     # Trigger purge job
    #     result = purge_deleted_tasks()
    #     
    #     return jsonify(result)
    #     
    # except Exception as e:
    #     logger.error(f"[ADMIN_PURGE] Error: {str(e)}", exc_info=True)
    #     return jsonify({
    #         'success': False,
    #         'error': str(e)
    #     }), 500


# CROWN⁴.5 Phase 3 Task 10: AI Task Proposals with Streaming
@api_tasks_bp.route('/ai-proposals/stream', methods=['POST'])
@login_required
def stream_ai_task_proposals():
    """
    Stream AI-generated task proposals based on meeting context.
    Uses Server-Sent Events (SSE) for real-time streaming.
    
    Request Body:
        {
            "meeting_id": int,
            "context": str (optional),
            "max_proposals": int (default: 3)
        }
    
    Returns:
        Stream of JSON objects:
        - data: {"type": "proposal", "task": {...}}
        - data: {"type": "done"}
        - data: {"type": "error", "message": str}
    """
    from flask import Response, stream_with_context
    from services.openai_client_manager import get_openai_client
    import json
    
    try:
        data = request.get_json()
        meeting_id = data.get('meeting_id')
        custom_context = data.get('context', '')
        max_proposals = data.get('max_proposals', 3)
        
        # Meeting ID is now optional - use workspace context if not provided
        meeting = None
        if meeting_id:
            # Verify meeting access
            meeting = db.session.query(Meeting).filter_by(
                id=meeting_id,
                workspace_id=current_user.workspace_id
            ).first()
            
            if not meeting:
                return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        def generate_proposals():
            """Generator function for SSE streaming."""
            try:
                # Build context from meeting OR workspace
                context_parts = []
                
                if meeting:
                    # Single meeting context
                    context_parts.append(f"Meeting: {meeting.title}")
                    
                    # Try to get summary from session
                    if meeting.session:
                        summary_obj = db.session.query(Summary).filter_by(session_id=meeting.session.id).first()
                        if summary_obj and summary_obj.summary_md:
                            context_parts.append(f"Summary: {summary_obj.summary_md[:500]}")
                        elif meeting.description:
                            context_parts.append(f"Description: {meeting.description[:300]}")
                    elif meeting.description:
                        context_parts.append(f"Description: {meeting.description[:300]}")
                else:
                    # Workspace-wide context - use recent meetings
                    recent_meetings = db.session.query(Meeting).filter_by(
                        workspace_id=current_user.workspace_id
                    ).order_by(Meeting.created_at.desc()).limit(3).all()
                    
                    if recent_meetings:
                        meeting_summaries = []
                        for m in recent_meetings:
                            summary_text = None
                            if m.session:
                                summary_obj = db.session.query(Summary).filter_by(session_id=m.session.id).first()
                                if summary_obj and summary_obj.summary_md:
                                    summary_text = summary_obj.summary_md[:200]
                                elif m.description:
                                    summary_text = m.description[:200]
                            elif m.description:
                                summary_text = m.description[:200]
                            
                            if summary_text:
                                meeting_summaries.append(f"- {m.title}: {summary_text}")
                        
                        if meeting_summaries:
                            context_parts.append("Recent meetings:\n" + "\n".join(meeting_summaries))
                
                if custom_context:
                    context_parts.append(f"Additional context: {custom_context}")
                
                # Get existing tasks to avoid duplicates
                if meeting_id:
                    existing_tasks = db.session.query(Task).filter_by(
                        meeting_id=meeting_id,
                        deleted_at=None
                    ).all()
                else:
                    # Get all workspace tasks via Meeting join
                    existing_tasks = db.session.query(Task).join(Meeting).filter(
                        Meeting.workspace_id == current_user.workspace_id,
                        Task.deleted_at.is_(None)
                    ).order_by(Task.created_at.desc()).limit(20).all()
                
                existing_titles = [t.title for t in existing_tasks]
                
                if existing_titles:
                    context_parts.append(f"Existing tasks (avoid duplicates): {', '.join(existing_titles[:10])}")
                
                context = "\n\n".join(context_parts)
                
                # Build OpenAI prompt
                system_prompt = """You are an AI assistant that suggests actionable tasks from meeting content.
Generate practical, specific tasks that can be assigned and tracked.
Return tasks as JSON array with: title, description, priority (low/medium/high), category.
Avoid duplicating existing tasks. Focus on concrete next steps."""
                
                context_source = "meeting content" if meeting else "recent workspace meetings"
                user_prompt = f"""{context}

Based on this {context_source}, suggest {max_proposals} actionable tasks.
Format as JSON array: [{{"title": "...", "description": "...", "priority": "medium", "category": "..."}}]"""
                
                # Stream from OpenAI
                client = get_openai_client()
                if not client:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'OpenAI client not available'})}\n\n"
                    return
                
                stream = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    stream=True,
                    temperature=0.7,
                    max_tokens=800
                )
                
                full_response = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"
                
                # Parse complete response
                try:
                    # Extract JSON from response (handle markdown code blocks)
                    response_text = full_response.strip()
                    if '```json' in response_text:
                        response_text = response_text.split('```json')[1].split('```')[0].strip()
                    elif '```' in response_text:
                        response_text = response_text.split('```')[1].split('```')[0].strip()
                    
                    proposals = json.loads(response_text)
                    
                    # Send each proposal as separate event
                    for proposal in proposals[:max_proposals]:
                        yield f"data: {json.dumps({'type': 'proposal', 'task': proposal})}\n\n"
                    
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to parse AI response'})}\n\n"
                
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                
            except Exception as e:
                logger.error(f"Stream error: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate_proposals()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        logger.error(f"AI proposals error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@api_tasks_bp.route('/<int:task_id>/comments', methods=['GET'])
@login_required
def get_task_comments(task_id):
    """Get comments for a specific task (CROWN⁴.5 Task 7)."""
    try:
        # Verify task exists and user has access
        task = db.session.get(Task, task_id)
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        # Verify workspace access
        meeting = db.session.get(Meeting, task.meeting_id)
        if not meeting or meeting.workspace_id != current_user.workspace_id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        # Query comments (exclude soft-deleted)
        stmt = select(TaskComment).where(
            and_(
                TaskComment.task_id == task_id,
                TaskComment.deleted_at.is_(None)
            )
        ).order_by(TaskComment.created_at.asc())
        
        comment_records = db.session.execute(stmt).scalars().all()
        
        # Build response with user info
        comments = []
        for comment in comment_records:
            user = db.session.get(User, comment.user_id)
            comments.append({
                'id': comment.id,
                'text': comment.text,
                'author': user.username if user else 'Unknown',
                'created_at': comment.created_at.isoformat() if comment.created_at else None,
                'updated_at': comment.updated_at.isoformat() if comment.updated_at else None
            })
        
        return jsonify({
            'success': True,
            'comments': comments
        })
        
    except Exception as e:
        logger.error(f"Error loading comments for task {task_id}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@api_tasks_bp.route('/<int:task_id>/comments', methods=['POST'])
@login_required
def add_task_comment(task_id):
    """Add a comment to a task (CROWN⁴.5 Task 7)."""
    try:
        # Verify task exists and user has access
        task = db.session.get(Task, task_id)
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        # Verify workspace access
        meeting = db.session.get(Meeting, task.meeting_id)
        if not meeting or meeting.workspace_id != current_user.workspace_id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        data = request.get_json()
        comment_text = data.get('text', '').strip()
        
        if not comment_text:
            return jsonify({'success': False, 'message': 'Comment text required'}), 400
        
        # Create new comment
        comment = TaskComment(
            task_id=task_id,
            user_id=current_user.id,
            text=comment_text
        )
        
        db.session.add(comment)
        db.session.commit()
        
        logger.info(f"Comment {comment.id} added to task {task_id} by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Comment added successfully',
            'comment': {
                'id': comment.id,
                'text': comment.text,
                'author': current_user.username,
                'created_at': comment.created_at.isoformat() if comment.created_at else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding comment to task {task_id}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@api_tasks_bp.route('/predict', methods=['POST'])
@login_required
def predict_task_attributes():
    """
    Get AI predictions for task attributes (CROWN⁴.5 PredictiveEngine).
    
    Provides smart defaults for:
    - Due date (based on task type, priority, urgency indicators)
    - Priority (based on text analysis)
    - Assignee (based on historical patterns)
    """
    try:
        from services.predictive_engine import predictive_engine
        
        data = request.get_json()
        
        if not data.get('title'):
            return jsonify({'success': False, 'message': 'Title is required'}), 400
        
        # Get predictions
        predictions = predictive_engine.get_prediction_suggestions(
            title=data.get('title'),
            description=data.get('description'),
            task_type=data.get('task_type', 'action_item'),
            user_id=current_user.id,
            workspace_id=current_user.workspace_id,
            meeting_id=data.get('meeting_id')
        )
        
        return jsonify({
            'success': True,
            'predictions': predictions
        })
        
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Prediction service error'}), 500


@api_tasks_bp.route('/predict/learn', methods=['POST'])
@login_required
def learn_from_correction():
    """
    Learn from user corrections to improve predictions (CROWN⁴.5 CognitiveSynchronizer).
    
    Called when user changes a predicted value to track accuracy and improve future predictions.
    """
    try:
        from services.predictive_engine import predictive_engine
        
        data = request.get_json()
        
        if not all(k in data for k in ['task_id', 'field', 'predicted_value', 'actual_value']):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        # Learn from correction
        predictive_engine.learn_from_correction(
            task_id=data['task_id'],
            predicted_field=data['field'],
            predicted_value=data['predicted_value'],
            actual_value=data['actual_value'],
            user_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': 'Correction recorded for learning'
        })
        
    except Exception as e:
        logger.error(f"Learning failed: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Learning service error'}), 500


@api_tasks_bp.route('/events/recover', methods=['POST'])
@login_required
def recover_event_sequence():
    """
    Recover from event sequence drift (CROWN⁴.5 TemporalRecoveryEngine).
    
    Detects and re-orders drifted events using vector clocks, ensuring causal consistency.
    """
    try:
        from services.temporal_recovery_engine import temporal_recovery_engine
        
        data = request.get_json()
        
        # Get time window for recovery (default 1 hour)
        time_window_hours = data.get('time_window_hours', 1)
        dry_run = data.get('dry_run', False)
        
        # Detect sequence drift
        drift_pairs = temporal_recovery_engine.detect_sequence_drift(
            session_id=None,  # Check all sessions in workspace
            time_window_hours=time_window_hours
        )
        
        if not drift_pairs:
            return jsonify({
                'success': True,
                'message': 'No sequence drift detected',
                'drift_detected': False,
                'metrics': temporal_recovery_engine.get_metrics()
            })
        
        # Get all events in window for reordering
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        stmt = select(EventLedger).where(
            and_(
                EventLedger.created_at >= cutoff_time,
                EventLedger.workspace_id == str(current_user.workspace_id)
            )
        ).order_by(EventLedger.created_at.asc())
        
        events = list(db.session.execute(stmt).scalars().all())
        
        # Replay events in correct order
        replay_result = temporal_recovery_engine.replay_events(events, dry_run=dry_run)
        
        return jsonify({
            'success': True,
            'drift_detected': True,
            'drift_pairs_count': len(drift_pairs),
            'replay_result': replay_result,
            'metrics': temporal_recovery_engine.get_metrics()
        })
        
    except Exception as e:
        logger.error(f"Event recovery failed: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Recovery service error'}), 500


@api_tasks_bp.route('/events/validate', methods=['GET'])
@login_required
def validate_event_sequence():
    """
    Validate event sequence integrity (CROWN⁴.5 TemporalRecoveryEngine).
    
    Checks for gaps, duplicates, and drift in event sequences.
    """
    try:
        from services.temporal_recovery_engine import temporal_recovery_engine
        
        # Validate sequence for user's workspace
        validation_result = temporal_recovery_engine.validate_event_sequence(
            session_id=None  # Validate all sessions in workspace
        )
        
        return jsonify({
            'success': True,
            'validation': validation_result,
            'metrics': temporal_recovery_engine.get_metrics()
        })
        
    except Exception as e:
        logger.error(f"Event validation failed: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Validation service error'}), 500


@api_tasks_bp.route('/ledger/compact', methods=['POST'])
@admin_required
def compact_event_ledger():
    """
    Compact event ledger by compressing old events (CROWN⁴.5 LedgerCompactor).
    
    **ADMIN ONLY** - Creates summaries and deletes old events to reduce database size
    while maintaining audit trail. Scoped to admin's workspace for multi-tenant isolation.
    """
    try:
        from services.ledger_compactor import ledger_compactor
        
        # Verify user has workspace
        if not current_user.workspace_id:
            return jsonify({'success': False, 'message': 'No workspace assigned'}), 400
        
        data = request.get_json() or {}
        
        # Get parameters
        dry_run = data.get('dry_run', False)
        batch_size = data.get('batch_size', 1000)
        
        # Run compaction (WORKSPACE-SCOPED)
        result = ledger_compactor.compact_events(
            workspace_id=current_user.workspace_id,
            dry_run=dry_run,
            batch_size=batch_size
        )
        
        # Get workspace-scoped metrics (CRITICAL: prevents cross-tenant leakage)
        workspace_metrics = ledger_compactor.get_metrics(workspace_id=current_user.workspace_id)
        
        return jsonify({
            'success': result.get('success', False),
            'result': result,
            'metrics': workspace_metrics
        })
        
    except Exception as e:
        logger.error(f"Ledger compaction failed: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Compaction service error'}), 500


@api_tasks_bp.route('/ledger/status', methods=['GET'])
@admin_required
def get_ledger_status():
    """
    Get event ledger status and metrics (CROWN⁴.5 LedgerCompactor).
    
    **ADMIN ONLY** - Returns compaction metrics and pending event counts
    scoped to admin's workspace for multi-tenant isolation.
    """
    try:
        from services.ledger_compactor import ledger_compactor
        
        # Verify user has workspace
        if not current_user.workspace_id:
            return jsonify({'success': False, 'message': 'No workspace assigned'}), 400
        
        # Get count of events ready for compaction (WORKSPACE-SCOPED)
        events_ready_count = ledger_compactor.get_events_ready_count(
            workspace_id=current_user.workspace_id
        )
        
        # Count total events in ledger (WORKSPACE-SCOPED)
        total_events = db.session.query(func.count(EventLedger.id)).filter(
            EventLedger.workspace_id == str(current_user.workspace_id)
        ).scalar()
        
        # Get workspace-scoped metrics (CRITICAL: prevents cross-tenant leakage)
        workspace_metrics = ledger_compactor.get_metrics(workspace_id=current_user.workspace_id)
        
        return jsonify({
            'success': True,
            'status': {
                'total_events': total_events,
                'events_ready_for_compaction': events_ready_count,
                'metrics': workspace_metrics
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get ledger status: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Status service error'}), 500


@api_tasks_bp.route('/<int:task_id>/history', methods=['GET'])
@login_required
def get_task_history(task_id):
    """Get history/audit trail for a specific task (CROWN⁴.5 Task 7)."""
    try:
        # Verify task exists and user has access
        task = db.session.get(Task, task_id)
        if not task:
            return jsonify({'success': False, 'message': 'Task not found'}), 404
        
        # Verify workspace access
        meeting = db.session.get(Meeting, task.meeting_id)
        if not meeting or meeting.workspace_id != current_user.workspace_id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        # Build history from task data and EventLedger
        history = []
        
        # Add creation event
        history.append({
            'id': 'created',
            'action': 'created',
            'timestamp': task.created_at.isoformat() if task.created_at else datetime.utcnow().isoformat(),
            'details': f'Task created from {task.source or "manual entry"}'
        })
        
        # Query EventLedger for task-related events
        # Look for TASK_UPDATE events in the task's payload
        stmt = select(EventLedger).where(
            and_(
                EventLedger.event_type == EventType.TASK_UPDATE,
                EventLedger.workspace_id == str(current_user.workspace_id)
            )
        ).order_by(EventLedger.created_at.asc())
        
        events = db.session.execute(stmt).scalars().all()
        
        # Filter events related to this specific task
        for event in events:
            if event.payload and event.payload.get('task_id') == task_id:
                action = event.payload.get('action', 'updated')
                details = event.payload.get('details', '')
                
                # Add event details if available
                if event.payload.get('old_value') and event.payload.get('new_value'):
                    old_val = event.payload.get('old_value')
                    new_val = event.payload.get('new_value')
                    history.append({
                        'id': f'event-{event.id}',
                        'action': action,
                        'timestamp': event.created_at.isoformat(),
                        'details': details or f'Updated',
                        'old_value': old_val,
                        'new_value': new_val
                    })
                else:
                    history.append({
                        'id': f'event-{event.id}',
                        'action': action,
                        'timestamp': event.created_at.isoformat(),
                        'details': details or event.event_name
                    })
        
        # Add status-based events from task data
        if task.status == 'completed':
            history.append({
                'id': 'completed',
                'action': 'completed',
                'timestamp': task.updated_at.isoformat() if task.updated_at else datetime.utcnow().isoformat(),
                'details': 'Task marked as completed'
            })
        
        # Sort by timestamp
        history.sort(key=lambda x: x['timestamp'])
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        logger.error(f"Error loading history for task {task_id}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
        