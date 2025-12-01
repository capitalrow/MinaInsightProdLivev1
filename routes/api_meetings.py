"""
Meetings API Routes
REST API endpoints for meeting management, processing, and data retrieval.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Meeting, Session, Task, Participant, Analytics, Workspace, Segment
from services.task_extraction_service import task_extraction_service
from services.meeting_metadata_service import meeting_metadata_service
from services.analytics_service import analytics_service
from middleware.cache_decorator import cache_response, invalidate_cache, invalidate_meeting_cache
from utils.etag_helper import with_etag, compute_collection_etag
from datetime import datetime
import asyncio
import json
from typing import Optional


api_meetings_bp = Blueprint('api_meetings', __name__, url_prefix='/api/meetings')


@api_meetings_bp.route('/', methods=['GET'])
@with_etag
@cache_response(ttl=300, prefix='session')  # 5 min cache for meeting lists
@login_required
def list_meetings():
    """Get list of meetings for current user's workspace."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status_filter = request.args.get('status', None)
        search_query = request.args.get('search', None)
        
        # Paginate results (Flask-SQLAlchemy 3.x compatible) with eager loading to prevent N+1 queries
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload, joinedload
        
        stmt = select(Meeting).where(Meeting.workspace_id == current_user.workspace_id)
        
        # Apply filters to statement
        if status_filter:
            stmt = stmt.where(Meeting.status == status_filter)
        if search_query:
            stmt = stmt.where(Meeting.title.contains(search_query))
        
        # Eager load relationships to prevent N+1 queries
        # Use selectinload for *-to-many, joinedload for *-to-one
        # IMPORTANT: Must include joinedload(Meeting.session) for to_dict() to access session.external_id
        stmt = stmt.options(
            joinedload(Meeting.session),  # Required for session_id in to_dict()
            selectinload(Meeting.tasks).selectinload(Task.assigned_to),
            selectinload(Meeting.participants),
            joinedload(Meeting.analytics),
            joinedload(Meeting.organizer)
        ).order_by(Meeting.created_at.desc())
        
        meetings = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'meetings': [meeting.to_dict() for meeting in meetings.items],
            'pagination': {
                'page': meetings.page,
                'pages': meetings.pages,
                'per_page': meetings.per_page,
                'total': meetings.total,
                'has_next': meetings.has_next,
                'has_prev': meetings.has_prev
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/<int:meeting_id>', methods=['GET'])
@cache_response(ttl=600, prefix='session')  # 10 min cache for meeting details
@login_required
def get_meeting(meeting_id):
    """Get detailed meeting information."""
    try:
        from sqlalchemy.orm import selectinload, joinedload
        
        # Single query with eager loading to prevent N+1 queries (was 4 queries, now 1)
        # IMPORTANT: Must include joinedload(Meeting.session) for to_dict() to access session.external_id
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).options(
            joinedload(Meeting.session),  # Required for session_id in to_dict()
            selectinload(Meeting.tasks).joinedload(Task.assigned_to),
            selectinload(Meeting.participants).joinedload(Participant.user),
            joinedload(Meeting.analytics),
            joinedload(Meeting.organizer)
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # All data already loaded via eager loading - no additional queries
        meeting_data = meeting.to_dict()
        meeting_data.update({
            'tasks': [task.to_dict() for task in meeting.tasks],
            'participants': [participant.to_dict() for participant in meeting.participants],
            'analytics': meeting.analytics.to_dict() if meeting.analytics else None
        })
        
        return jsonify({
            'success': True,
            'meeting': meeting_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/', methods=['POST'])
@invalidate_cache(prefix='session')  # Invalidate meeting list cache
@invalidate_cache(prefix='analytics')  # Invalidate analytics cache
@login_required
def create_meeting():
    """Create a new meeting."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({'success': False, 'message': 'Title is required'}), 400
        
        meeting = Meeting(
            title=data['title'],
            description=data.get('description'),
            workspace_id=current_user.workspace_id,
            status='scheduled',
            scheduled_start=_parse_datetime(data.get('scheduled_start')),
            scheduled_end=_parse_datetime(data.get('scheduled_end')),
            agenda=data.get('agenda', {}),
            meeting_type=data.get('meeting_type', 'internal'),
            organizer_id=current_user.id
        )
        
        db.session.add(meeting)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Meeting created successfully',
            'meeting': meeting.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/<int:meeting_id>', methods=['PUT'])
@login_required
def update_meeting(meeting_id):
    """Update meeting information."""
    try:
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        data = request.get_json()
        
        # Update fields
        if 'title' in data:
            meeting.title = data['title']
        if 'description' in data:
            meeting.description = data['description']
        if 'status' in data:
            meeting.status = data['status']
        if 'scheduled_start' in data:
            meeting.scheduled_start = _parse_datetime(data['scheduled_start'])
        if 'scheduled_end' in data:
            meeting.scheduled_end = _parse_datetime(data['scheduled_end'])
        if 'agenda' in data:
            meeting.agenda = data['agenda']
        if 'meeting_type' in data:
            meeting.meeting_type = data['meeting_type']
        
        meeting.updated_at = datetime.now()
        db.session.commit()
        
        # Invalidate cache for this meeting
        invalidate_meeting_cache(meeting_id)
        
        return jsonify({
            'success': True,
            'message': 'Meeting updated successfully',
            'meeting': meeting.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/<int:meeting_id>', methods=['DELETE'])
@login_required
def delete_meeting(meeting_id):
    """Delete a meeting and all associated data."""
    try:
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # Delete associated data
        db.session.query(Task).filter_by(meeting_id=meeting_id).delete()
        db.session.query(Participant).filter_by(meeting_id=meeting_id).delete()
        db.session.query(Analytics).filter_by(meeting_id=meeting_id).delete()
        
        # Delete meeting
        db.session.delete(meeting)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Meeting deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/<int:meeting_id>/start', methods=['POST'])
@login_required
def start_meeting(meeting_id):
    """Start a live meeting."""
    try:
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # Update meeting status
        meeting.status = 'live'
        meeting.actual_start = datetime.now()
        
        # Create session if doesn't exist
        if not meeting.session:
            session = Session(
                title=f"Session for {meeting.title}",
                status='active',
                user_id=current_user.id,
                workspace_id=current_user.workspace_id,
                meeting_id=meeting.id  # Link session to meeting
            )
            db.session.add(session)
            db.session.flush()  # Ensure session is saved
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Meeting started successfully',
            'meeting': meeting.to_dict(),
            'session_id': meeting.session.id if meeting.session else None
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/<int:meeting_id>/end', methods=['POST'])
@login_required
def end_meeting(meeting_id):
    """End a live meeting and trigger processing."""
    try:
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # Update meeting status
        meeting.status = 'completed'
        meeting.actual_end = datetime.now()
        
        # Update session if exists
        if meeting.session:
            meeting.session.status = 'completed'
            meeting.session.completed_at = datetime.now()
        
        db.session.commit()
        
        # Trigger async processing in background (WSGI-safe)
        import threading
        thread = threading.Thread(target=lambda: asyncio.run(process_meeting_async(meeting_id)))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Meeting ended successfully. Processing started.',
            'meeting': meeting.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/<int:meeting_id>/process', methods=['POST'])
@login_required
def process_meeting(meeting_id):
    """Manually trigger meeting processing (task extraction, analytics, etc.)."""
    try:
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # Start processing
        processing_results = {}
        
        # Process participants and metadata
        metadata_result = asyncio.run(meeting_metadata_service.process_meeting_metadata(meeting_id))
        processing_results['metadata'] = metadata_result
        
        # Extract tasks
        task_result = asyncio.run(task_extraction_service.process_meeting_for_tasks(meeting_id))
        processing_results['tasks'] = task_result
        
        # Analyze meeting
        analytics_result = asyncio.run(analytics_service.analyze_meeting(meeting_id))
        processing_results['analytics'] = analytics_result
        
        # Meeting processing completed
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Meeting processing completed',
            'results': processing_results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/<int:meeting_id>/participants', methods=['GET'])
@login_required
def get_meeting_participants(meeting_id):
    """Get meeting participants with detailed metrics."""
    try:
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # Get participant summary
        summary = meeting_metadata_service.get_meeting_participant_summary(meeting_id)
        
        return jsonify({
            'success': True,
            'participants': summary['participants'],
            'summary': summary['summary']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/<int:meeting_id>/tasks', methods=['GET'])
@login_required
def get_meeting_tasks(meeting_id):
    """Get all tasks created from this meeting."""
    try:
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        tasks = db.session.query(Task).filter_by(meeting_id=meeting_id).all()
        
        # Group tasks by status
        task_groups = {
            'todo': [],
            'in_progress': [],
            'completed': [],
            'cancelled': []
        }
        
        for task in tasks:
            task_groups[task.status].append(task.to_dict())
        
        return jsonify({
            'success': True,
            'tasks': task_groups,
            'total_tasks': len(tasks)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/<int:meeting_id>/analytics', methods=['GET'])
@login_required
def get_meeting_analytics(meeting_id):
    """Get detailed analytics for a meeting."""
    try:
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        analytics = db.session.query(Analytics).filter_by(meeting_id=meeting_id).first()
        
        if not analytics:
            return jsonify({'success': False, 'message': 'Analytics not available. Please process the meeting first.'}), 404
        
        return jsonify({
            'success': True,
            'analytics': analytics.to_dict(include_detailed_data=True)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/recent', methods=['GET'])
@with_etag
@login_required
def get_recent_meetings():
    """Get recent meetings for dashboard."""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        meetings = db.session.query(Meeting).filter_by(
            workspace_id=current_user.workspace_id
        ).order_by(Meeting.created_at.desc()).limit(limit).all()
        
        meetings_data = [meeting.to_dict() for meeting in meetings]
        checksum = compute_collection_etag(meetings_data)
        
        return jsonify({
            'success': True,
            'meetings': meetings_data,
            'checksum': checksum
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_meetings_bp.route('/stats', methods=['GET'])
@with_etag
@login_required
def get_meeting_stats():
    """Get meeting statistics for current workspace."""
    try:
        workspace_id = current_user.workspace_id
        
        # Basic counts
        total_meetings = db.session.query(Meeting).filter_by(workspace_id=workspace_id).count()
        live_meetings = db.session.query(Meeting).filter_by(workspace_id=workspace_id, status='live').count()
        completed_meetings = db.session.query(Meeting).filter_by(workspace_id=workspace_id, status='completed').count()
        
        # This week's meetings
        from datetime import datetime, timedelta
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        this_week_meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= week_start
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_meetings': total_meetings,
                'live_meetings': live_meetings,
                'completed_meetings': completed_meetings,
                'this_week_meetings': this_week_meetings,
                'completion_rate': round((completed_meetings / total_meetings * 100), 1) if total_meetings > 0 else 0
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


def _parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Safely parse ISO datetime string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


async def process_meeting_async(meeting_id: int):
    """Async background processing for meeting after it ends."""
    try:
        # Process metadata and participants
        await meeting_metadata_service.process_meeting_metadata(meeting_id)
        
        # Extract tasks
        await task_extraction_service.process_meeting_for_tasks(meeting_id)
        
        # Generate analytics
        await analytics_service.analyze_meeting(meeting_id)
        
        # Update meeting status
        meeting = db.session.query(Meeting).get(meeting_id)
        if meeting:
            db.session.commit()
        
    except Exception as e:
        print(f"Background processing failed for meeting {meeting_id}: {e}")
        # Update meeting with error status
        meeting = db.session.query(Meeting).get(meeting_id)
        if meeting:
            db.session.commit()