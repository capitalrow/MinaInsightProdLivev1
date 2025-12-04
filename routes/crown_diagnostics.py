"""
CROWN¹⁰ Diagnostics Routes
Pre-flight checks and verification endpoints for database persistence
"""
import logging
from flask import Blueprint, jsonify, render_template_string
from flask_login import current_user, login_required
from app import db
from models.session import Session
from models.meeting import Meeting
from models.task import Task
from models.user import User
from models.workspace import Workspace

logger = logging.getLogger(__name__)

crown_diagnostics_bp = Blueprint('crown_diagnostics', __name__, url_prefix='/crown-diagnostics')

@crown_diagnostics_bp.route('/pre-flight-check')
@login_required
def pre_flight_check():
    """
    Pre-flight check to verify user authentication and workspace configuration
    Shows if the user is ready to create recordings that will save to database
    """
    try:
        # Gather user information
        user_info = {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'workspace_id': current_user.workspace_id,
            'authenticated': current_user.is_authenticated
        }
        
        # Get workspace information
        workspace_info = None
        if current_user.workspace_id:
            workspace = db.session.get(Workspace, current_user.workspace_id)
            if workspace:
                workspace_info = {
                    'id': workspace.id,
                    'name': workspace.name,
                    'slug': workspace.slug,
                    'is_active': workspace.is_active,
                    'plan': workspace.plan
                }
        
        # Check recent sessions for this user
        recent_sessions = db.session.query(Session).filter_by(user_id=current_user.id).order_by(Session.started_at.desc()).limit(5).all()
        session_data = []
        for session in recent_sessions:
            session_data.append({
                'id': session.id,
                'external_id': session.external_id,
                'title': session.title,
                'user_id': session.user_id,
                'workspace_id': session.workspace_id,
                'meeting_id': session.meeting_id,
                'status': session.status,
                'has_workspace': session.workspace_id is not None,
                'has_meeting': session.meeting_id is not None,
                'started_at': session.started_at.isoformat() if session.started_at else None
            })
        
        # Check meetings for this user
        recent_meetings = db.session.query(Meeting).filter_by(organizer_id=current_user.id).order_by(Meeting.created_at.desc()).limit(5).all()
        meeting_data = []
        for meeting in recent_meetings:
            task_count = db.session.query(Task).filter_by(meeting_id=meeting.id).count()
            meeting_data.append({
                'id': meeting.id,
                'title': meeting.title,
                'workspace_id': meeting.workspace_id,
                'status': meeting.status,
                'task_count': task_count,
                'created_at': meeting.created_at.isoformat() if meeting.created_at else None
            })
        
        # Check orphaned tasks (session but no meeting)
        orphaned_tasks = db.session.query(Task).join(
            Session, Task.session_id == Session.id
        ).filter(
            Task.meeting_id.is_(None),
            Session.user_id == current_user.id
        ).count()
        
        # Determine readiness status
        readiness_status = {
            'ready': current_user.workspace_id is not None,
            'checks': {
                'user_authenticated': current_user.is_authenticated,
                'has_workspace_id': current_user.workspace_id is not None,
                'workspace_active': workspace_info.get('is_active', False) if workspace_info else False
            }
        }
        
        # Calculate stats
        stats = {
            'total_sessions': db.session.query(Session).filter_by(user_id=current_user.id).count(),
            'total_meetings': db.session.query(Meeting).filter_by(organizer_id=current_user.id).count(),
            'total_tasks': db.session.query(Task).filter_by(created_by_id=current_user.id).count(),
            'orphaned_tasks': orphaned_tasks,
            'sessions_with_workspace': db.session.query(Session).filter_by(user_id=current_user.id).filter(Session.workspace_id.isnot(None)).count(),
            'sessions_with_meeting': db.session.query(Session).filter_by(user_id=current_user.id).filter(Session.meeting_id.isnot(None)).count()
        }
        
        # Jinja2 template with proper escaping
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>CROWN¹⁰ Pre-Flight Check</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    max-width: 900px;
                    margin: 40px auto;
                    padding: 20px;
                    background: #f5f5f5;
                }
                .status-card {
                    background: white;
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                .status-header {
                    font-size: 24px;
                    font-weight: 600;
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                .status-ready { color: #10b981; }
                .status-error { color: #ef4444; }
                .check-item {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    margin: 10px 0;
                    padding: 10px;
                    background: #f9fafb;
                    border-radius: 4px;
                }
                .check-pass { color: #10b981; font-size: 20px; }
                .check-fail { color: #ef4444; font-size: 20px; }
                .info-grid {
                    display: grid;
                    grid-template-columns: 150px 1fr;
                    gap: 10px;
                    margin: 10px 0;
                }
                .info-label {
                    font-weight: 600;
                    color: #6b7280;
                }
                .info-value { color: #1f2937; }
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    gap: 15px;
                    margin-top: 20px;
                }
                .stat-box {
                    background: #f9fafb;
                    padding: 15px;
                    border-radius: 6px;
                    text-align: center;
                }
                .stat-value {
                    font-size: 32px;
                    font-weight: 700;
                    color: #6366f1;
                }
                .stat-label {
                    font-size: 12px;
                    color: #6b7280;
                    margin-top: 5px;
                }
                .session-list { margin-top: 15px; }
                .session-item {
                    padding: 12px;
                    background: #f9fafb;
                    border-left: 4px solid #6366f1;
                    margin: 8px 0;
                    border-radius: 4px;
                }
                .badge {
                    display: inline-block;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 600;
                    margin-left: 8px;
                }
                .badge-success { background: #d1fae5; color: #065f46; }
                .badge-error { background: #fee2e2; color: #991b1b; }
                .badge-warning { background: #fef3c7; color: #92400e; }
            </style>
        </head>
        <body>
            <div class="status-card">
                <div class="status-header {% if readiness.ready %}status-ready{% else %}status-error{% endif %}">
                    {% if readiness.ready %}✅{% else %}❌{% endif %} CROWN¹⁰ Persistence Status
                </div>
                
                <div class="check-item">
                    <span class="{% if readiness.checks.user_authenticated %}check-pass{% else %}check-fail{% endif %}">
                        {% if readiness.checks.user_authenticated %}✓{% else %}✗{% endif %}
                    </span>
                    <span>User Authenticated</span>
                </div>
                
                <div class="check-item">
                    <span class="{% if readiness.checks.has_workspace_id %}check-pass{% else %}check-fail{% endif %}">
                        {% if readiness.checks.has_workspace_id %}✓{% else %}✗{% endif %}
                    </span>
                    <span>Workspace ID Configured</span>
                </div>
                
                <div class="check-item">
                    <span class="{% if readiness.checks.workspace_active %}check-pass{% else %}check-fail{% endif %}">
                        {% if readiness.checks.workspace_active %}✓{% else %}✗{% endif %}
                    </span>
                    <span>Workspace Active</span>
                </div>
                
                {% if readiness.ready %}
                <div style="margin-top: 20px; padding: 15px; background: #d1fae5; border-radius: 6px; color: #065f46;">
                    <strong>✅ Ready to Record!</strong><br>Your next recording will automatically save Session → Meeting → Tasks with proper workspace linkage.
                </div>
                {% else %}
                <div style="margin-top: 20px; padding: 15px; background: #fee2e2; border-radius: 6px; color: #991b1b;">
                    <strong>❌ Not Ready</strong><br>Please ensure you have a workspace assigned to your account.
                </div>
                {% endif %}
            </div>
            
            <div class="status-card">
                <h3>Current User Info</h3>
                <div class="info-grid">
                    <div class="info-label">User ID:</div>
                    <div class="info-value">{{ user.id }}</div>
                    
                    <div class="info-label">Username:</div>
                    <div class="info-value">{{ user.username }}</div>
                    
                    <div class="info-label">Email:</div>
                    <div class="info-value">{{ user.email }}</div>
                    
                    <div class="info-label">Workspace ID:</div>
                    <div class="info-value">
                        {% if user.workspace_id %}{{ user.workspace_id }}{% else %}<span class="badge badge-error">NULL</span>{% endif %}
                    </div>
                </div>
            </div>
            
            {% if workspace %}
            <div class="status-card">
                <h3>Workspace Info</h3>
                <div class="info-grid">
                    <div class="info-label">Workspace ID:</div>
                    <div class="info-value">{{ workspace.id }}</div>
                    
                    <div class="info-label">Name:</div>
                    <div class="info-value">{{ workspace.name }}</div>
                    
                    <div class="info-label">Slug:</div>
                    <div class="info-value">{{ workspace.slug }}</div>
                    
                    <div class="info-label">Status:</div>
                    <div class="info-value">{% if workspace.is_active %}Active{% else %}Inactive{% endif %}</div>
                    
                    <div class="info-label">Plan:</div>
                    <div class="info-value">{{ workspace.plan }}</div>
                </div>
            </div>
            {% endif %}
            
            <div class="status-card">
                <h3>Statistics</h3>
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-value">{{ stats.total_sessions }}</div>
                        <div class="stat-label">Total Sessions</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{{ stats.total_meetings }}</div>
                        <div class="stat-label">Total Meetings</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{{ stats.total_tasks }}</div>
                        <div class="stat-label">Total Tasks</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" style="color: {% if stats.orphaned_tasks > 0 %}#ef4444{% else %}#6366f1{% endif %};">{{ stats.orphaned_tasks }}</div>
                        <div class="stat-label">Orphaned Tasks</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{{ stats.sessions_with_workspace }}</div>
                        <div class="stat-label">Sessions w/ Workspace</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{{ stats.sessions_with_meeting }}</div>
                        <div class="stat-label">Sessions w/ Meeting</div>
                    </div>
                </div>
            </div>
            
            <div class="status-card">
                <h3>Recent Sessions</h3>
                <div class="session-list">
                    {% if sessions %}
                        {% for s in sessions %}
                        <div class="session-item">
                            <strong>{{ s.title }}</strong> 
                            <span class="badge {% if s.has_workspace %}badge-success{% else %}badge-error{% endif %}">
                                {% if s.has_workspace %}Workspace ✓{% else %}No Workspace{% endif %}
                            </span>
                            <span class="badge {% if s.has_meeting %}badge-success{% else %}badge-warning{% endif %}">
                                {% if s.has_meeting %}Meeting ✓{% else %}No Meeting{% endif %}
                            </span>
                            <div style="font-size: 12px; color: #6b7280; margin-top: 5px;">
                                ID: {{ s.id }} | External: {{ s.external_id[:8] }}... | Status: {{ s.status }} | {{ s.started_at[:19] if s.started_at else 'N/A' }}
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <p style="color: #6b7280;">No recent sessions found</p>
                    {% endif %}
                </div>
            </div>
            
            <div class="status-card">
                <h3>Recent Meetings</h3>
                <div class="session-list">
                    {% if meetings %}
                        {% for m in meetings %}
                        <div class="session-item">
                            <strong>{{ m.title }}</strong>
                            <span class="badge badge-success">{{ m.task_count }} tasks</span>
                            <div style="font-size: 12px; color: #6b7280; margin-top: 5px;">
                                ID: {{ m.id }} | Workspace: {{ m.workspace_id }} | Status: {{ m.status }} | {{ m.created_at[:19] if m.created_at else 'N/A' }}
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <p style="color: #6b7280;">No recent meetings found</p>
                    {% endif %}
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #6b7280;">
                <p>🚀 CROWN¹⁰ Architecture: One Mind, Many Surfaces — Every Moment in Harmony</p>
                <p style="font-size: 12px;">Last checked: {{ timestamp }}</p>
            </div>
        </body>
        </html>
        """
        
        import datetime
        return render_template_string(
            html_template,
            user=user_info,
            workspace=workspace_info,
            readiness=readiness_status,
            stats=stats,
            sessions=session_data,
            meetings=meeting_data,
            timestamp=datetime.datetime.utcnow().isoformat() + 'Z'
        )
        
    except Exception as e:
        logger.error(f"Pre-flight check error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@crown_diagnostics_bp.route('/api/status')
@login_required
def api_status():
    """JSON version of pre-flight check for programmatic access"""
    try:
        workspace = None
        if current_user.workspace_id:
            workspace = db.session.get(Workspace, current_user.workspace_id)
        
        return jsonify({
            'ready': current_user.workspace_id is not None,
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'workspace_id': current_user.workspace_id
            },
            'workspace': {
                'id': workspace.id,
                'name': workspace.name,
                'is_active': workspace.is_active
            } if workspace else None,
            'stats': {
                'total_sessions': db.session.query(Session).filter_by(user_id=current_user.id).count(),
                'total_meetings': db.session.query(Meeting).filter_by(organizer_id=current_user.id).count(),
                'total_tasks': db.session.query(Task).filter_by(created_by_id=current_user.id).count()
            }
        })
    except Exception as e:
        logger.error(f"API status error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
