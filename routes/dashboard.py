"""
Dashboard Routes for Mina Productivity Platform
Main dashboard with meetings, tasks, analytics overview.
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, Meeting, Task, Analytics, Session, Marker
from sqlalchemy import desc, func, and_
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta, date
from services.event_broadcaster import event_broadcaster

try:
    from services.uptime_monitoring import uptime_monitor
    from services.performance_monitoring import performance_monitor
    monitoring_available = True
except ImportError:
    monitoring_available = False
    uptime_monitor = None
    performance_monitor = None


dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard page with overview of meetings, tasks, and analytics."""
    # Check if user has a workspace, if not create one
    if not current_user.workspace_id:
        from models import Workspace
        try:
            workspace_name = f"{current_user.first_name}'s Workspace" if current_user.first_name else f"{current_user.username}'s Workspace"
            workspace = Workspace(
                name=workspace_name,
                slug=Workspace.generate_slug(workspace_name),
                owner_id=current_user.id
            )
            db.session.add(workspace)
            db.session.flush()
            current_user.workspace_id = workspace.id
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            import logging
            logging.error(f"Failed to create workspace for user {current_user.id}: {e}")
            # Continue with None workspace - show empty dashboard
    
    # Get recent meetings (handle None workspace)
    # ✨ CROWN⁴: Eager load session relationship for card navigation
    # ✨ CROWN⁴ Phase 4: Exclude archived meetings from main view
    if current_user.workspace_id:
        recent_meetings = db.session.query(Meeting).options(
            joinedload(Meeting.session)
        ).filter_by(
            workspace_id=current_user.workspace_id,
            archived=False
        ).order_by(desc(Meeting.created_at)).limit(5).all()
    else:
        recent_meetings = []
    
    # Get user's tasks
    user_tasks = db.session.query(Task).filter_by(
        assigned_to_id=current_user.id
    ).filter(Task.status.in_(['todo', 'in_progress'])).limit(10).all()
    
    # Get workspace statistics using new meeting lifecycle service
    if current_user.workspace_id:
        from services.meeting_lifecycle_service import MeetingLifecycleService
        stats = MeetingLifecycleService.get_meeting_statistics(current_user.workspace_id, days=365)
        total_meetings = stats['total_meetings']
        total_tasks = stats['total_tasks']
        completed_tasks = stats['completed_tasks']
    else:
        total_meetings = 0
        total_tasks = 0
        completed_tasks = 0
    
    # Calculate task completion rate
    task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Get this week's meetings
    week_start = datetime.now() - timedelta(days=datetime.now().weekday())
    if current_user.workspace_id:
        this_week_meetings = db.session.query(Meeting).filter_by(
            workspace_id=current_user.workspace_id
        ).filter(Meeting.created_at >= week_start).count()
    else:
        this_week_meetings = 0
    
    # Get today's meetings (meetings created today or scheduled for today)
    # ✨ CROWN⁴: Eager load session relationship for card navigation
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    if current_user.workspace_id:
        todays_meetings = db.session.query(Meeting).options(
            joinedload(Meeting.session)
        ).filter_by(
            workspace_id=current_user.workspace_id,
            archived=False
        ).filter(
            and_(
                Meeting.created_at >= today_start,
                Meeting.created_at < today_end
            )
        ).order_by(desc(Meeting.created_at)).all()
    else:
        todays_meetings = []
    
    # Get follow-up items from recent meetings (last 7 days)
    recent_cutoff = datetime.now() - timedelta(days=7)
    
    # Get recent markers (decisions, todos, risks)
    recent_markers = db.session.query(Marker).filter_by(
        user_id=current_user.id
    ).filter(Marker.created_at >= recent_cutoff).order_by(desc(Marker.created_at)).limit(5).all()
    
    # Get urgent tasks (high priority or due soon)
    urgent_tasks = db.session.query(Task).filter_by(
        assigned_to_id=current_user.id
    ).filter(
        Task.status.in_(['todo', 'in_progress'])
    ).order_by(desc(Task.priority), Task.due_date).limit(5).all()
    
    # Create follow-up items combining markers and urgent tasks
    follow_up_items = []
    
    # Add markers as follow-up items
    for marker in recent_markers:
        content_preview = str(marker.content)[:50] + ('...' if len(str(marker.content)) > 50 else '')
        follow_up_items.append({
            'type': 'marker',
            'subtype': marker.type,
            'title': f"{marker.type.title()}: {content_preview}",
            'content': marker.content,
            'timestamp': marker.created_at,
            'speaker': marker.speaker,
            'session_id': marker.session_id,
            'id': marker.id
        })
    
    # Add urgent tasks as follow-up items
    for task in urgent_tasks:
        follow_up_items.append({
            'type': 'task',
            'subtype': task.priority,
            'title': task.title,
            'content': task.description or '',
            'timestamp': task.created_at,
            'due_date': task.due_date,
            'status': task.status,
            'id': task.id
        })
    
    # Sort follow-up items by timestamp (newest first)
    follow_up_items.sort(key=lambda x: x['timestamp'], reverse=True)
    follow_up_items = follow_up_items[:8]  # Limit to 8 items
    
    return render_template('dashboard/index.html',
                         recent_meetings=recent_meetings,
                         user_tasks=user_tasks,
                         todays_meetings=todays_meetings,
                         follow_up_items=follow_up_items,
                         stats={
                             'total_meetings': total_meetings,
                             'total_tasks': total_tasks,
                             'completed_tasks': completed_tasks,
                             'task_completion_rate': round(task_completion_rate, 1),
                             'this_week_meetings': this_week_meetings,
                             'todays_meetings': len(todays_meetings)
                         })


@dashboard_bp.route('/api/meetings')
@login_required
def api_meetings():
    """
    Get meetings in JSON format with checksum for cache validation.
    CROWN⁴ cache bootstrap endpoint.
    Supports ?archived=true to filter archived meetings.
    """
    import hashlib
    import json
    
    # Get archived filter parameter (CROWN⁴ Phase 4)
    archived_filter = request.args.get('archived', 'false').lower() == 'true'
    
    # Build query - use impossible condition if no workspace
    if current_user.workspace_id:
        query = db.select(Meeting).options(
            joinedload(Meeting.session)
        ).where(
            Meeting.workspace_id == current_user.workspace_id,
            Meeting.archived == archived_filter
        )
    else:
        query = db.select(Meeting).where(Meeting.id == -1)
    
    # Order by created_at descending
    query = query.order_by(desc(Meeting.created_at))
    
    # Get all meetings (limit to 100 for performance)
    meetings = db.session.execute(query.limit(100)).scalars().all()
    
    # Serialize meetings to dict
    meetings_data = []
    for meeting in meetings:
        meeting_dict = {
            'id': meeting.id,
            'title': meeting.title,
            'created_at': meeting.created_at.isoformat() if meeting.created_at else None,
            'status': meeting.status,
            'duration': meeting.duration,
            'word_count': meeting.word_count,
            'speaker_count': meeting.speaker_count,
            'summary': meeting.summary,
            'archived': getattr(meeting, 'archived', False),
            'session_id': meeting.session.external_session_id if meeting.session else None,
            'meeting_id': meeting.id
        }
        meetings_data.append(meeting_dict)
    
    # Generate checksum for cache validation
    serialized = json.dumps(meetings_data, sort_keys=True, default=str)
    checksum = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
    
    return jsonify({
        'meetings': meetings_data,
        'checksum': checksum,
        'count': len(meetings_data),
        'timestamp': datetime.utcnow().isoformat()
    })


@dashboard_bp.route('/meetings')
@login_required
def meetings():
    """Meetings overview page."""
    # Filter and pagination
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    
    # Build query - use impossible condition if no workspace
    # ✨ CROWN⁴: Eager load session relationship for card navigation
    # ✨ CROWN⁴ Phase 4: Exclude archived meetings from active view
    if current_user.workspace_id:
        query = db.select(Meeting).options(
            joinedload(Meeting.session)
        ).where(
            Meeting.workspace_id == current_user.workspace_id,
            Meeting.archived == False
        )
    else:
        query = db.select(Meeting).where(Meeting.id == -1)
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search_query:
        query = query.filter(Meeting.title.contains(search_query))
    
    # Order by created_at descending
    query = query.order_by(desc(Meeting.created_at))
    
    # Paginate results
    meetings_paginated = db.paginate(query, page=page, per_page=20, error_out=False)
    
    return render_template('dashboard/meetings.html',
                         meetings=meetings_paginated.items,
                         has_more=meetings_paginated.has_next,
                         page=page,
                         total=meetings_paginated.total,
                         status_filter=status_filter,
                         search_query=search_query)




@dashboard_bp.route('/tasks')
@login_required
def tasks():
    """Tasks overview page with kanban board."""
    # Get all tasks for workspace
    all_tasks = db.session.query(Task).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id
    ).order_by(Task.due_date.asc().nullslast(), Task.priority.desc(), Task.created_at.desc()).all()
    
    # Get tasks by status
    todo_tasks = [t for t in all_tasks if t.status == 'todo']
    in_progress_tasks = [t for t in all_tasks if t.status == 'in_progress']
    completed_tasks = [t for t in all_tasks if t.status == 'completed'][:10]
    
    return render_template('dashboard/tasks.html',
                         tasks=all_tasks,
                         todo_tasks=todo_tasks,
                         in_progress_tasks=in_progress_tasks,
                         completed_tasks=completed_tasks)


@dashboard_bp.route('/analytics')
@login_required
def analytics():
    """Analytics and insights page."""
    from sqlalchemy import select, cast, Date
    from datetime import datetime, timedelta
    from models import Participant
    
    if not current_user.workspace_id:
        return render_template('dashboard/analytics.html',
                             total_meetings=0,
                             total_tasks=0,
                             hours_saved=0,
                             avg_duration=0,
                             task_completion_rate=0,
                             workspace_averages={'effectiveness': 0, 'engagement': 0, 'sentiment': 0})
    
    # Get date range (last 30 days by default)
    days = 30
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # Total meetings in period
    total_meetings = db.session.query(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Meeting.created_at >= cutoff_date
    ).count()
    
    # Total tasks
    meeting_ids_query = select(Meeting.id).where(
        Meeting.workspace_id == current_user.workspace_id,
        Meeting.created_at >= cutoff_date
    )
    meeting_ids = [row[0] for row in db.session.execute(meeting_ids_query)]
    
    total_tasks = db.session.query(Task).filter(Task.meeting_id.in_(meeting_ids)).count() if meeting_ids else 0
    completed_tasks = db.session.query(Task).filter(
        Task.meeting_id.in_(meeting_ids),
        Task.status == 'completed'
    ).count() if meeting_ids else 0
    
    task_completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0
    
    # Average meeting duration
    avg_duration_query = db.session.query(func.avg(Analytics.total_duration_minutes)).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Meeting.created_at >= cutoff_date,
        Analytics.total_duration_minutes.isnot(None)
    ).scalar()
    avg_duration = round(avg_duration_query) if avg_duration_query else 45
    
    # Hours saved (estimate based on meeting efficiency)
    total_meeting_hours = db.session.query(func.sum(Analytics.total_duration_minutes)).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Meeting.created_at >= cutoff_date,
        Analytics.total_duration_minutes.isnot(None)
    ).scalar() or 0
    
    avg_efficiency = db.session.query(func.avg(Analytics.meeting_efficiency_score)).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Meeting.created_at >= cutoff_date,
        Analytics.meeting_efficiency_score.isnot(None)
    ).scalar() or 0.5
    
    hours_saved = round((total_meeting_hours / 60) * (avg_efficiency * 0.3))  # Estimate savings
    
    # Calculate workspace averages
    avg_effectiveness = db.session.query(func.avg(Analytics.meeting_effectiveness_score)).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Meeting.created_at >= cutoff_date,
        Analytics.meeting_effectiveness_score.isnot(None)
    ).scalar() or 0
    
    avg_engagement = db.session.query(func.avg(Analytics.overall_engagement_score)).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Meeting.created_at >= cutoff_date,
        Analytics.overall_engagement_score.isnot(None)
    ).scalar() or 0
    
    avg_sentiment = db.session.query(func.avg(Analytics.overall_sentiment_score)).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Meeting.created_at >= cutoff_date,
        Analytics.overall_sentiment_score.isnot(None)
    ).scalar() or 0
    
    return render_template('dashboard/analytics.html',
                         total_meetings=total_meetings,
                         total_tasks=total_tasks,
                         hours_saved=hours_saved,
                         avg_duration=avg_duration,
                         task_completion_rate=task_completion_rate,
                         workspace_averages={
                             'effectiveness': round(avg_effectiveness * 100, 1) if avg_effectiveness else 0,
                             'engagement': round(avg_engagement * 100, 1) if avg_engagement else 0,
                             'sentiment': round(avg_sentiment * 100, 1) if avg_sentiment else 0
                         })


@dashboard_bp.route('/api/recent-activity')
@login_required
def api_recent_activity():
    """API endpoint for recent activity feed."""
    # Get recent meetings
    # ✨ CROWN⁴: Eager load session relationship
    recent_meetings = db.session.query(Meeting).options(
        joinedload(Meeting.session)
    ).filter_by(
        workspace_id=current_user.workspace_id
    ).order_by(desc(Meeting.created_at)).limit(5).all()
    
    # Get recent tasks
    recent_tasks = db.session.query(Task).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id
    ).order_by(desc(Task.created_at)).limit(5).all()
    
    # Combine and sort activities
    activities = []
    
    for meeting in recent_meetings:
        activities.append({
            'type': 'meeting',
            'id': meeting.id,
            'title': meeting.title,
            'timestamp': meeting.created_at,
            'status': meeting.status
        })
    
    for task in recent_tasks:
        activities.append({
            'type': 'task',
            'id': task.id,
            'title': task.title,
            'timestamp': task.created_at,
            'status': task.status,
            'priority': task.priority
        })
    
    # Sort by timestamp
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({'activities': activities[:10]})


@dashboard_bp.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for dashboard statistics."""
    # Meeting stats
    total_meetings = db.session.query(Meeting).filter_by(workspace_id=current_user.workspace_id).count()
    active_meetings = db.session.query(Meeting).filter_by(
        workspace_id=current_user.workspace_id,
        status='live'
    ).count()
    
    # Task stats
    total_tasks = db.session.query(Task).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id
    ).count()
    completed_tasks = db.session.query(Task).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Task.status == 'completed'
    ).count()
    overdue_tasks = db.session.query(Task).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Task.due_date < datetime.now().date(),
        Task.status.in_(['todo', 'in_progress'])
    ).count()
    
    # This week's activity
    week_start = datetime.now() - timedelta(days=datetime.now().weekday())
    this_week_meetings = db.session.query(Meeting).filter_by(
        workspace_id=current_user.workspace_id
    ).filter(Meeting.created_at >= week_start).count()
    
    this_week_tasks = db.session.query(Task).join(Meeting).filter(
        Meeting.workspace_id == current_user.workspace_id,
        Task.created_at >= week_start
    ).count()
    
    return jsonify({
        'meetings': {
            'total': total_meetings,
            'active': active_meetings,
            'this_week': this_week_meetings
        },
        'tasks': {
            'total': total_tasks,
            'completed': completed_tasks,
            'overdue': overdue_tasks,
            'this_week': this_week_tasks,
            'completion_rate': round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0
        }
    })


@dashboard_bp.route('/api/events/bootstrap', methods=['POST'])
@login_required
def log_dashboard_bootstrap():
    """
    Log dashboard_bootstrap event to EventLedger.
    CROWN⁴ Event #1: Tracks dashboard initialization with cache performance.
    """
    from services.event_ledger_service import EventLedgerService
    from models.event_ledger import EventType
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        data = request.get_json() or {}
        
        # Extract performance metrics from request
        cache_load_time = data.get('cache_load_time', 0)
        server_load_time = data.get('server_load_time', 0)
        total_time = data.get('total_time', 0)
        cache_hit = data.get('cache_hit', False)
        
        # Log event to EventLedger
        event = EventLedgerService.log_event(
            event_type=EventType.DASHBOARD_BOOTSTRAP,
            session_id=None,
            external_session_id=None,
            payload={
                'user_id': current_user.id,
                'workspace_id': current_user.workspace_id,
                'cache_load_time_ms': cache_load_time,
                'server_load_time_ms': server_load_time,
                'total_bootstrap_time_ms': total_time,
                'cache_hit': cache_hit,
                'timestamp': datetime.utcnow().isoformat()
            },
            trace_id=f"dashboard_bootstrap_{current_user.id}_{datetime.utcnow().timestamp()}"
        )
        
        # Mark event as completed immediately
        EventLedgerService.complete_event(event, result={
            'status': 'success',
            'sub_200ms': total_time < 200
        }, duration_ms=total_time)
        
        logger.info(f"📊 Dashboard bootstrap event logged for user {current_user.id} ({total_time}ms)")
        
        return jsonify({
            'success': True,
            'event_id': event.id,
            'total_time': total_time,
            'sub_200ms': total_time < 200
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to log dashboard_bootstrap event: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/api/events/filter-apply', methods=['POST'])
@login_required
def log_filter_apply():
    """
    Log filter_apply event to EventLedger.
    CROWN⁴ Event #8: Tracks dashboard search and filter usage.
    """
    from services.event_ledger_service import EventLedgerService
    from models.event_ledger import EventType
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        data = request.get_json() or {}
        
        # Extract filter data
        filter_type = data.get('filter_type')  # 'search', 'time', 'status', etc.
        filter_value = data.get('filter_value')
        
        if not filter_type:
            return jsonify({
                'success': False,
                'error': 'filter_type required'
            }), 400
        
        # Log event to EventLedger
        event = EventLedgerService.log_event(
            event_type=EventType.FILTER_APPLY,
            session_id=None,
            external_session_id=None,
            payload={
                'user_id': current_user.id,
                'workspace_id': current_user.workspace_id,
                'filter_type': filter_type,
                'filter_value': filter_value,
                'timestamp': datetime.utcnow().isoformat()
            },
            trace_id=f"filter_apply_{current_user.id}_{datetime.utcnow().timestamp()}"
        )
        
        # Mark event as completed immediately
        EventLedgerService.complete_event(event, result={
            'status': 'success',
            'filter_applied': True
        }, duration_ms=0)
        
        logger.info(f"🔍 Filter event logged for user {current_user.id}: {filter_type}={filter_value}")
        
        return jsonify({
            'success': True,
            'event_id': event.id
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to log filter_apply event: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/api/events/prefetch', methods=['POST'])
@login_required
def log_session_prefetch():
    """
    Log session_prefetch event to EventLedger.
    CROWN⁴ Event #6: Tracks when hover triggers session prefetch.
    """
    from services.event_ledger_service import EventLedgerService
    from models.event_ledger import EventType
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        data = request.get_json() or {}
        
        # Extract event data
        session_id = data.get('session_id')
        external_session_id = data.get('external_session_id')
        meeting_id = data.get('meeting_id')
        
        if not session_id and not external_session_id and not meeting_id:
            return jsonify({
                'success': False,
                'error': 'session_id, external_session_id, or meeting_id required'
            }), 400
        
        # Log event to EventLedger
        event = EventLedgerService.log_event(
            event_type=EventType.SESSION_PREFETCH,
            session_id=session_id,
            external_session_id=external_session_id,
            payload={
                'user_id': current_user.id,
                'workspace_id': current_user.workspace_id,
                'meeting_id': meeting_id,
                'timestamp': datetime.utcnow().isoformat()
            },
            trace_id=f"prefetch_{meeting_id or session_id or external_session_id}_{datetime.utcnow().timestamp()}"
        )
        
        # Mark event as completed immediately (prefetch is instant)
        EventLedgerService.complete_event(event, result={
            'status': 'success',
            'prefetch_initiated': True
        }, duration_ms=0)
        
        logger.info(f"🔮 Prefetch event logged for meeting {meeting_id or session_id or external_session_id}")
        
        return jsonify({
            'success': True,
            'event_id': event.id
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to log session_prefetch event: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/api/events/card-click', methods=['POST'])
@login_required
def log_session_card_click():
    """
    Log session_card_click event to EventLedger.
    CROWN⁴ Event #7: Tracks when user clicks meeting card to navigate.
    """
    from services.event_ledger_service import EventLedgerService
    from models.event_ledger import EventType
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        data = request.get_json() or {}
        
        # Extract event data
        session_id = data.get('session_id')
        external_session_id = data.get('external_session_id')
        meeting_id = data.get('meeting_id')
        
        if not session_id and not external_session_id and not meeting_id:
            return jsonify({
                'success': False,
                'error': 'session_id, external_session_id, or meeting_id required'
            }), 400
        
        # Log event to EventLedger
        event = EventLedgerService.log_event(
            event_type=EventType.SESSION_CARD_CLICK,
            session_id=session_id,
            external_session_id=external_session_id,
            payload={
                'user_id': current_user.id,
                'workspace_id': current_user.workspace_id,
                'meeting_id': meeting_id,
                'timestamp': datetime.utcnow().isoformat()
            },
            trace_id=f"card_click_{meeting_id or session_id or external_session_id}_{datetime.utcnow().timestamp()}"
        )
        
        # Mark event as completed immediately (click is instant)
        EventLedgerService.complete_event(event, result={
            'status': 'success',
            'navigation_initiated': True
        }, duration_ms=0)
        
        logger.info(f"🖱️ Card click event logged for meeting {meeting_id or session_id or external_session_id}")
        
        return jsonify({
            'success': True,
            'event_id': event.id
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to log session_card_click event: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/api/meetings/<int:meeting_id>/archive', methods=['POST'])
@login_required
def archive_meeting(meeting_id):
    """
    Archive a meeting (CROWN⁴ Phase 4).
    Logs SESSION_ARCHIVE event to EventLedger.
    """
    from services.event_ledger_service import EventLedgerService
    from models.event_ledger import EventType
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get the meeting
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'error': 'Meeting not found'}), 404
        
        if meeting.archived:
            return jsonify({'success': False, 'error': 'Meeting already archived'}), 400
        
        # Archive the meeting (don't commit yet - transactional safety)
        meeting.archive(current_user.id)
        
        # Log SESSION_ARCHIVE event to EventLedger
        event = EventLedgerService.log_event(
            event_type=EventType.SESSION_ARCHIVE,
            session_id=meeting.session.id if meeting.session else None,
            external_session_id=meeting.session.external_id if meeting.session else None,
            payload={
                'user_id': current_user.id,
                'workspace_id': current_user.workspace_id,
                'meeting_id': meeting_id,
                'meeting_title': meeting.title,
                'timestamp': datetime.utcnow().isoformat()
            },
            trace_id=f"archive_{meeting_id}_{datetime.utcnow().timestamp()}"
        )
        
        # Mark event as completed
        EventLedgerService.complete_event(event, result={
            'status': 'success',
            'archived': True
        }, duration_ms=0)
        
        # Commit all changes together (meeting + event) - transactional safety
        db.session.commit()
        
        # Broadcast to WebSocket clients (after successful commit)
        event_broadcaster.broadcast_meeting_archived(
            workspace_id=current_user.workspace_id,
            meeting_id=meeting_id
        )
        
        logger.info(f"📦 Meeting {meeting_id} archived by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'event_id': event.id,
            'meeting': meeting.to_dict()
        }), 200
        
    except Exception as e:
        # Ensure rollback on any error (transactional safety)
        db.session.rollback()
        logger.error(f"Failed to archive meeting {meeting_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/meetings/<int:meeting_id>/restore', methods=['POST'])
@login_required
def restore_meeting(meeting_id):
    """
    Restore an archived meeting (CROWN⁴ Phase 4).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Get the meeting
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'error': 'Meeting not found'}), 404
        
        if not meeting.archived:
            return jsonify({'success': False, 'error': 'Meeting is not archived'}), 400
        
        # Restore the meeting (don't commit yet - transactional safety)
        meeting.restore()
        
        # Commit the restore
        db.session.commit()
        
        # Broadcast to WebSocket clients (after successful commit)
        event_broadcaster.broadcast_meeting_restored(
            workspace_id=current_user.workspace_id,
            meeting_id=meeting_id
        )
        
        logger.info(f"📥 Meeting {meeting_id} restored by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'meeting': meeting.to_dict()
        }), 200
        
    except Exception as e:
        # Ensure rollback on any error (transactional safety)
        db.session.rollback()
        logger.error(f"Failed to restore meeting {meeting_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/events/archive-reveal', methods=['POST'])
@login_required
def log_archive_reveal():
    """
    Log ARCHIVE_REVEAL event to EventLedger.
    CROWN⁴ Event #9: Tracks when user accesses the archive tab.
    """
    from services.event_ledger_service import EventLedgerService
    from models.event_ledger import EventType
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Log event to EventLedger
        event = EventLedgerService.log_event(
            event_type=EventType.ARCHIVE_REVEAL,
            session_id=None,
            payload={
                'user_id': current_user.id,
                'workspace_id': current_user.workspace_id,
                'timestamp': datetime.utcnow().isoformat()
            },
            trace_id=f"archive_reveal_{current_user.id}_{datetime.utcnow().timestamp()}"
        )
        
        # Mark event as completed immediately
        EventLedgerService.complete_event(event, result={
            'status': 'success',
            'archive_revealed': True
        }, duration_ms=0)
        
        logger.info(f"🗂️ Archive reveal event logged for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'event_id': event.id
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to log archive_reveal event: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/ops/metrics')
def ops_metrics():
    """Operational metrics dashboard endpoint."""
    if not monitoring_available or uptime_monitor is None or performance_monitor is None:
        return jsonify({'error': 'Monitoring services not available'}), 503
    
    try:
        health = uptime_monitor.get_health_status()
        perf_stats = performance_monitor.get_stats()
        
        return jsonify({
            'health': health,
            'performance': perf_stats,
            'timestamp': health['timestamp']
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500