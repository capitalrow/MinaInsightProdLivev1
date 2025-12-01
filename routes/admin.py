"""
Admin Dashboard Routes for Mina - Cognitive Mission Control
Provides founders/admins with comprehensive system analytics, 
AI oversight, and business intelligence panels.
"""

from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Meeting, Task, Session
from sqlalchemy import func, and_, desc
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """
    Decorator to require admin or owner role for access.
    Returns 403 Forbidden if user lacks proper permissions.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin:
            logger.warning(f"Access denied to admin route for user {current_user.id} (role: {current_user.role})")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/analytics')
@admin_required
def analytics_dashboard():
    """
    Main Admin Analytics Dashboard - Cognitive Mission Control
    Displays comprehensive system health, AI oversight, and business metrics.
    """
    try:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # KPI Metrics
        active_meetings = db.session.query(Session).filter(
            Session.status == 'active'
        ).count()
        
        total_meetings_today = db.session.query(Meeting).filter(
            Meeting.created_at >= today_start
        ).count()
        
        total_meetings_week = db.session.query(Meeting).filter(
            Meeting.created_at >= week_ago
        ).count()
        
        # User metrics
        total_users = db.session.query(User).filter(User.active == True).count()
        
        # Daily Active Users (users who logged in today)
        dau = db.session.query(User).filter(
            and_(
                User.last_login >= today_start,
                User.active == True
            )
        ).count()
        
        # Weekly Active Users
        wau = db.session.query(User).filter(
            and_(
                User.last_login >= week_ago,
                User.active == True
            )
        ).count()
        
        # Monthly Active Users
        mau = db.session.query(User).filter(
            and_(
                User.last_login >= month_ago,
                User.active == True
            )
        ).count()
        
        # Task metrics
        total_tasks = db.session.query(Task).count()
        completed_tasks = db.session.query(Task).filter(Task.status == 'completed').count()
        pending_tasks = db.session.query(Task).filter(Task.status.in_(['todo', 'in_progress'])).count()
        task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Calculate cognitive health score (0-100)
        # Based on: task completion, user engagement, system stability
        engagement_score = min(100, (dau / max(total_users, 1)) * 200)  # Up to 100 if 50%+ DAU
        task_score = task_completion_rate
        stability_score = 95  # Placeholder - would come from real metrics
        cognitive_health = int((engagement_score + task_score + stability_score) / 3)
        
        # Meeting statistics by day (last 7 days)
        meeting_trend = []
        for i in range(7):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            count = db.session.query(Meeting).filter(
                and_(
                    Meeting.created_at >= day_start,
                    Meeting.created_at < day_end
                )
            ).count()
            meeting_trend.insert(0, {
                'date': day_start.strftime('%Y-%m-%d'),
                'label': day_start.strftime('%a'),
                'count': count
            })
        
        # User growth trend (last 30 days)
        user_trend = []
        for i in range(30):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            new_users = db.session.query(User).filter(
                and_(
                    User.created_at >= day_start,
                    User.created_at < day_end
                )
            ).count()
            user_trend.insert(0, {
                'date': day_start.strftime('%Y-%m-%d'),
                'count': new_users
            })
        
        # System health metrics (mock data - would come from real monitoring)
        system_health = {
            'ws_latency': 45,  # ms
            'api_throughput': 150,  # req/s
            'queue_depth': 3,
            'error_rate': 0.2,  # %
            'sync_drift': 80,  # ms
            'status': 'healthy'
        }
        
        # Pipeline health (mock data - would come from real transcription pipeline)
        pipeline_health = {
            'ingest': {'status': 'healthy', 'latency_ms': 12, 'error_rate': 0.1},
            'chunking': {'status': 'healthy', 'latency_ms': 45, 'error_rate': 0.0},
            'whisper': {'status': 'healthy', 'latency_ms': 320, 'error_rate': 0.5},
            'ai_summary': {'status': 'healthy', 'latency_ms': 850, 'error_rate': 0.3},
            'task_extract': {'status': 'healthy', 'latency_ms': 220, 'error_rate': 0.2},
            'sync': {'status': 'healthy', 'latency_ms': 55, 'error_rate': 0.1}
        }
        
        # AI oversight metrics (mock data)
        ai_metrics = {
            'confidence_median': 0.87,
            'misfire_rate': 2.3,  # %
            'semantic_drift': 0.12,
            'override_rate': 4.5,  # %
            'copilot_actions_today': 156,
            'retry_rate': 1.8  # %
        }
        
        # Recent incidents (mock data)
        recent_incidents = [
            {
                'id': 'INC-001',
                'timestamp': (now - timedelta(hours=2)).isoformat(),
                'severity': 'warning',
                'title': 'Elevated API Latency',
                'description': 'API response times increased by 15% due to database connection pooling.',
                'status': 'resolved'
            },
            {
                'id': 'INC-002', 
                'timestamp': (now - timedelta(hours=8)).isoformat(),
                'severity': 'info',
                'title': 'Whisper Model Switch',
                'description': 'Automatic failover to backup transcription model completed successfully.',
                'status': 'resolved'
            }
        ]
        
        return render_template('admin/analytics.html',
            # KPIs
            active_meetings=active_meetings,
            total_meetings_today=total_meetings_today,
            total_meetings_week=total_meetings_week,
            total_users=total_users,
            dau=dau,
            wau=wau,
            mau=mau,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            pending_tasks=pending_tasks,
            task_completion_rate=round(task_completion_rate, 1),
            cognitive_health=cognitive_health,
            
            # Trends
            meeting_trend=meeting_trend,
            user_trend=user_trend,
            
            # System health
            system_health=system_health,
            pipeline_health=pipeline_health,
            ai_metrics=ai_metrics,
            recent_incidents=recent_incidents,
            
            # Meta
            last_updated=now.isoformat(),
            current_admin=current_user
        )
        
    except Exception as e:
        logger.error(f"Error loading admin analytics: {e}", exc_info=True)
        return render_template('admin/analytics.html',
            error=str(e),
            active_meetings=0,
            total_meetings_today=0,
            total_meetings_week=0,
            total_users=0,
            dau=0,
            wau=0,
            mau=0,
            total_tasks=0,
            completed_tasks=0,
            pending_tasks=0,
            task_completion_rate=0,
            cognitive_health=0,
            meeting_trend=[],
            user_trend=[],
            system_health={},
            pipeline_health={},
            ai_metrics={},
            recent_incidents=[],
            last_updated=datetime.utcnow().isoformat(),
            current_admin=current_user
        )


@admin_bp.route('/api/metrics/realtime')
@admin_required
def get_realtime_metrics():
    """
    API endpoint for real-time metrics updates via WebSocket polling.
    Returns current system state for dashboard updates.
    """
    try:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        active_meetings = db.session.query(Session).filter(
            Session.status == 'active'
        ).count()
        
        dau = db.session.query(User).filter(
            and_(
                User.last_login >= today_start,
                User.active == True
            )
        ).count()
        
        return jsonify({
            'timestamp': now.isoformat(),
            'active_meetings': active_meetings,
            'dau': dau,
            'system_latency': 45,  # Mock - would come from real monitoring
            'queue_depth': 3,
            'ws_status': 'connected',
            'cognitive_health': 87
        })
        
    except Exception as e:
        logger.error(f"Error fetching realtime metrics: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/pipeline/health')
@admin_required
def get_pipeline_health():
    """
    API endpoint for meeting pipeline health status.
    Returns latency and error rates for each pipeline stage.
    """
    return jsonify({
        'timestamp': datetime.utcnow().isoformat(),
        'stages': {
            'ingest': {'status': 'healthy', 'latency_ms': 12, 'error_rate': 0.1},
            'chunking': {'status': 'healthy', 'latency_ms': 45, 'error_rate': 0.0},
            'whisper': {'status': 'healthy', 'latency_ms': 320, 'error_rate': 0.5},
            'ai_summary': {'status': 'healthy', 'latency_ms': 850, 'error_rate': 0.3},
            'task_extract': {'status': 'healthy', 'latency_ms': 220, 'error_rate': 0.2},
            'sync': {'status': 'healthy', 'latency_ms': 55, 'error_rate': 0.1}
        }
    })


@admin_bp.route('/api/incidents')
@admin_required
def get_incidents():
    """
    API endpoint for recent incidents and anomalies.
    Returns paginated list of system incidents with narrative explanations.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Mock incidents - would come from incident tracking system
    incidents = [
        {
            'id': 'INC-001',
            'timestamp': datetime.utcnow().isoformat(),
            'severity': 'warning',
            'title': 'Elevated API Latency',
            'description': 'API response times increased by 15% due to database connection pooling.',
            'narrative': 'The system detected elevated latency in API responses. Root cause analysis indicates database connection pool saturation during peak usage. Auto-scaling has been triggered.',
            'status': 'resolved',
            'resolution_time': '12 minutes'
        }
    ]
    
    return jsonify({
        'incidents': incidents,
        'total': len(incidents),
        'page': page,
        'per_page': per_page
    })


@admin_bp.route('/api/audit-trail')
@admin_required
def get_audit_trail():
    """
    API endpoint for audit trail logs.
    Returns paginated, filterable list of admin and AI actions.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    actor = request.args.get('actor')
    action_type = request.args.get('action_type')
    
    # Mock audit trail - would come from audit log table
    audit_logs = [
        {
            'trace_id': 'TRC-8a7b6c5d',
            'timestamp': datetime.utcnow().isoformat(),
            'actor': 'system:copilot',
            'action': 'task_created',
            'entity_type': 'task',
            'entity_id': 'TSK-123',
            'before': None,
            'after': {'title': 'Follow up with client', 'priority': 'high'},
            'ai_lineage': {
                'session_id': 'SES-456',
                'transcript_span': '2:15-2:45',
                'confidence': 0.92
            },
            'region': 'us-east-1'
        }
    ]
    
    return jsonify({
        'logs': audit_logs,
        'total': len(audit_logs),
        'page': page,
        'per_page': per_page
    })


@admin_bp.route('/users')
@admin_required
def user_management():
    """
    User management page for admins.
    Lists all users with ability to modify roles and status.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    
    # Use offset/limit for pagination instead of .paginate()
    offset = (page - 1) * per_page
    users_query = db.session.query(User).order_by(desc(User.created_at))
    total_users = users_query.count()
    users = users_query.offset(offset).limit(per_page).all()
    
    return render_template('admin/users.html',
        users=users,
        total_users=total_users,
        page=page,
        per_page=per_page,
        total_pages=(total_users + per_page - 1) // per_page,
        current_admin=current_user
    )


@admin_bp.route('/api/users/<int:user_id>/role', methods=['POST'])
@admin_required
def update_user_role(user_id):
    """
    Update a user's role. Only owners can promote to admin.
    """
    if current_user.role != 'owner':
        return jsonify({'error': 'Only owners can modify user roles'}), 403
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    new_role = data.get('role') if data else None
    if new_role not in ['user', 'admin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    old_role = user.role
    user.role = new_role
    db.session.commit()
    
    logger.info(f"User {user_id} role changed from {old_role} to {new_role} by admin {current_user.id}")
    
    return jsonify({
        'success': True,
        'user_id': user_id,
        'new_role': new_role
    })
