"""
Session Routes (M2)
REST API endpoints for session management, list, detail, and finalization.
"""

import logging
from flask import Blueprint, request, jsonify, render_template, abort, Response
from flask_login import current_user, login_required
from app import db
from services.session_service import SessionService
from services.export_service import ExportService
from services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

sessions_bp = Blueprint('sessions', __name__, url_prefix='/sessions')


@sessions_bp.route('/', methods=['GET'])
def list_sessions():
    """
    GET /sessions - List sessions with optional filtering
    
    Query parameters:
    - q: Search query for title
    - status: Status filter (active, completed, error)  
    - limit: Maximum results (default: 50)
    - offset: Results offset (default: 0)
    - format: Response format ('json' or 'html', default: 'html')
    """
    # Get query parameters
    q = request.args.get('q', None)
    status = request.args.get('status', None)
    limit = min(int(request.args.get('limit', 50)), 100)  # Cap at 100
    offset = int(request.args.get('offset', 0))
    response_format = request.args.get('format', 'html')
    
    # Get sessions from service with error handling
    try:
        sessions_result = SessionService.list_sessions(q=q, status=status, limit=limit, offset=offset)
        
        # Handle pagination object vs list
        if hasattr(sessions_result, 'items') and hasattr(sessions_result, 'total'):
            sessions = sessions_result.items  # type: ignore
            total_count = sessions_result.total  # type: ignore
        elif isinstance(sessions_result, list):
            sessions = sessions_result
            total_count = len(sessions)
        else:
            sessions = []
            total_count = 0
            
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return jsonify({'error': 'Failed to load sessions'}), 500
    
    # Return JSON for API requests
    if response_format == 'json':
        return jsonify({
            'sessions': [session.to_dict() for session in sessions] if sessions else [],
            'total': total_count,
            'query': {
                'q': q,
                'status': status,
                'limit': limit,
                'offset': offset
            }
        })
    
    # Return HTML template for browser requests
    # Pass pagination object or create simple wrapper for template compatibility
    if hasattr(sessions_result, 'items'):
        # Already a pagination object from SQLAlchemy
        meetings_obj = sessions_result
    else:
        # Create simple pagination wrapper with proper method signatures
        class SimplePagination:
            def __init__(self, items, total):
                self.items = items if items else []
                self.total = total
                self.pages = 1
                self.page = 1
                self.per_page = len(self.items)
                self.has_prev = False
                self.has_next = False
                self.prev_num = None
                self.next_num = None
            
            def __len__(self):
                return len(self.items)
            
            def __iter__(self):
                return iter(self.items)
            
            def iter_pages(self, left_edge=0, right_edge=0, left_current=0, right_current=0):
                """Generator for page numbers"""
                yield 1
        
        meetings_obj = SimplePagination(sessions, total_count)
    
    return render_template('dashboard/meetings.html', 
                         meetings=meetings_obj,
                         search_query=q, 
                         status_filter=status,
                         limit=limit,
                         offset=offset)


@sessions_bp.route('/<session_identifier>', methods=['GET'])
def get_session_detail(session_identifier):
    """
    GET /sessions/<id_or_external_id> - Get session detail with segments
    
    Query parameters:
    - format: Response format ('json' or 'html', default: 'html')
    """
    response_format = request.args.get('format', 'html')
    
    # Try external_id first (since most lookups use external_id), then database ID as fallback
    session_detail = SessionService.get_session_detail_by_external(session_identifier)
    
    # If not found by external_id and identifier is numeric, try database ID
    if not session_detail and session_identifier.isdigit():
        session_detail = SessionService.get_session_detail(int(session_identifier))
    
    if not session_detail:
        if response_format == 'json':
            return jsonify({'error': 'Session not found'}), 404
        else:
            abort(404)
    
    # Return JSON for API requests
    if response_format == 'json':
        return jsonify(session_detail)
    
    # Return HTML template for browser requests  
    return render_template('session_refined.html',
                         meeting=session_detail['session'],
                         segments=session_detail['segments'])


@sessions_bp.route('/', methods=['POST'])
@login_required
def create_session():
    """
    POST /sessions - Create a new session (authenticated endpoint)
    
    Request body (JSON):
    - title: Optional session title
    - external_id: Optional external ID (auto-generated if not provided)
    - locale: Optional language/locale code
    - device_info: Optional device information dictionary
    
    Note: workspace_id and user_id are automatically obtained from current_user
    """
    data = request.get_json() or {}
    
    # 🔒 CROWN¹⁰ Fix: Get workspace_id and user_id from authenticated user
    workspace_id = current_user.workspace_id if current_user.is_authenticated else None
    user_id = current_user.id if current_user.is_authenticated else None
    
    if not workspace_id:
        return jsonify({'error': 'Workspace not found. Please ensure you are logged in.'}), 403
    
    try:
        session_id = SessionService.create_session(
            title=data.get('title'),
            external_id=data.get('external_id'),
            locale=data.get('locale'),
            device_info=data.get('device_info'),
            workspace_id=workspace_id,
            user_id=user_id
        )
        
        # Get created session for response
        session = SessionService.get_session_by_id(session_id)
        if session:
            return jsonify({
                'id': session.id,
                'external_id': session.external_id,
                'title': session.title,
                'status': session.status,
                'started_at': session.started_at.isoformat()
            }), 201
        else:
            return jsonify({'error': 'Failed to create session'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Failed to create session: {str(e)}'}), 500


@sessions_bp.route('/<int:session_id>/finalize', methods=['POST'])
def finalize_session(session_id):
    """
    POST /sessions/<id>/finalize - Mark session as completed and create meeting (idempotent)
    
    Request body (JSON, optional):
    - final_text: Optional final transcript text to add
    """
    data = request.get_json() or {}
    final_text = data.get('final_text')
    
    try:
        # Check if session exists
        session = SessionService.get_session_by_id(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Finalize segments if final text provided
        if final_text:
            finalized_count = SessionService.finalize_session_segments(session_id, final_text)
        else:
            finalized_count = 0
        
        # Use new meeting lifecycle service to complete session + create meeting
        from services.meeting_lifecycle_service import MeetingLifecycleService
        result = MeetingLifecycleService.finalize_session_with_meeting(session_id)
        
        if result.get('success'):
            return jsonify({
                'message': f'Session {session_id} completed and meeting created',
                'session_id': session_id,
                'meeting_id': result.get('meeting_id'),
                'finalized_segments': finalized_count,
                'status': 'completed'
            })
        else:
            # Fallback to just completing session
            SessionService.complete_session(session_id, create_meeting=False)
            return jsonify({
                'message': f'Session {session_id} completed (meeting creation failed)',
                'status': 'completed',
                'error': result.get('error')
            })
            
    except Exception as e:
        logger.error(f"Error finalizing session {session_id}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to finalize session: {str(e)}'}), 500


@sessions_bp.route('/stats', methods=['GET'])
def get_session_stats():
    """
    GET /sessions/stats - Get session statistics
    """
    try:
        stats = SessionService.get_session_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Failed to get stats: {str(e)}'}), 500


@sessions_bp.route('/<session_identifier>/refined', methods=['GET'])
def get_session_refined(session_identifier):
    """
    GET /sessions/<id_or_external_id>/refined - Refined session view with tabs
    
    This is the post-transcription view with:
    - Transcript tab
    - Highlights tab (summary, insights)
    - Analytics tab (metrics, sentiment)
    - Tasks tab (action items)
    - Replay tab (audio sync)
    
    Query parameters:
    - t: Timestamp in milliseconds to scroll to (for Jump to Transcript feature)
    
    Automatically navigated to after post_transcription_reveal event.
    
    PROGRESSIVE LOADING STRATEGY:
    1. First try to load 'final' segments (post-processing complete)
    2. If no final segments, fall back to 'live' segments (immediate display)
    3. Template will show loading indicator if insights still processing
    This ensures users see their transcript immediately after redirect.
    """
    # Get optional timestamp parameter for Jump to Transcript feature
    jump_to_timestamp = request.args.get('t', type=int)
    
    # Try external_id first (since redirect uses external_id), then database ID as fallback
    # First try 'final' segments (processed transcript)
    session_detail = SessionService.get_session_detail_by_external(session_identifier, kind='final')
    segments_source = 'final'
    
    # If not found by external_id and identifier is numeric, try database ID
    if not session_detail and session_identifier.isdigit():
        session_detail = SessionService.get_session_detail(int(session_identifier), kind='final')
    
    # PROGRESSIVE FALLBACK: If no final segments, try live segments for immediate display
    if not session_detail or len(session_detail.get('segments', [])) == 0:
        # Try to get session with live segments
        live_detail = SessionService.get_session_detail_by_external(session_identifier, kind='live')
        if not live_detail and session_identifier.isdigit():
            live_detail = SessionService.get_session_detail(int(session_identifier), kind='live')
        
        if live_detail and len(live_detail.get('segments', [])) > 0:
            session_detail = live_detail
            segments_source = 'live'
            logger.info(f"[Refined View] Using live segments for immediate display (finalization pending)")
    
    # Final fallback: try loading any segments if both final and live are empty
    if not session_detail or len(session_detail.get('segments', [])) == 0:
        all_detail = SessionService.get_session_detail_by_external(session_identifier, kind=None)
        if not all_detail and session_identifier.isdigit():
            all_detail = SessionService.get_session_detail(int(session_identifier), kind=None)
        
        if all_detail:
            session_detail = all_detail
            segments_source = 'all'
            logger.info(f"[Refined View] Loaded all segments ({len(all_detail.get('segments', []))} total)")
    
    if not session_detail:
        abort(404)
    
    # Get additional data for tabs
    session_data = session_detail['session']
    segments = session_detail['segments']
    
    # Determine if insights are still processing (used by template for loading states)
    insights_pending = segments_source != 'final'
    
    # Log what we're working with for debugging
    logger.info(f"[Refined View] Session {session_identifier}: {len(segments)} {segments_source} segments loaded (insights_pending={insights_pending})")
    
    # Get summary/insights data
    summary_data = None
    try:
        from services.analysis_service import AnalysisService
        summary_data = AnalysisService.get_session_summary(session_data['id'])
    except Exception as e:
        logger.warning(f"Failed to get summary for session {session_identifier}: {e}")
    
    # Get analytics data
    analytics_data = None
    try:
        # Calculate basic analytics from segments
        word_count = sum(len((s.get('text') or '').split()) for s in segments)
        total_duration = sum((s.get('end_ms', 0) - s.get('start_ms', 0)) for s in segments) / 1000.0
        avg_confidence = sum(s.get('avg_confidence', 0) for s in segments) / len(segments) if segments else 0
        
        analytics_data = {
            'word_count': word_count,
            'total_duration': total_duration,
            'average_confidence': avg_confidence,
            'segment_count': len(segments),
            'words_per_minute': (word_count / (total_duration / 60)) if total_duration > 0 else 0
        }
    except Exception as e:
        logger.warning(f"Failed to calculate analytics for session {session_identifier}: {e}")
    
    # Get tasks/action items
    tasks_data = []
    try:
        from models.task import Task
        from sqlalchemy import select
        stmt = select(Task).filter(Task.session_id == session_data['id']).order_by(Task.created_at)
        tasks = db.session.execute(stmt).scalars().all()
        tasks_data = [task.to_dict(include_relationships=True) for task in tasks] if tasks else []
    except Exception as e:
        logger.warning(f"Failed to get tasks for session {session_identifier}: {e}")
    
    # Get event timeline for debugging/status
    event_timeline = []
    try:
        from services.event_ledger_service import EventLedgerService
        event_timeline = EventLedgerService.get_event_timeline(
            session_data.get('external_id') or session_identifier
        )
    except Exception as e:
        logger.warning(f"Failed to get event timeline: {e}")
    
    # Check if user has live transcription (Business tier) for timestamp display
    has_live_transcription = False
    if current_user.is_authenticated:
        has_live_transcription = SubscriptionService.has_live_transcription(current_user.id)
    
    # Render refined template with all data
    return render_template(
        'session_refined.html',
        session=session_data,
        segments=segments,
        summary=summary_data,
        analytics=analytics_data,
        tasks=tasks_data,
        event_timeline=event_timeline,
        insights_pending=insights_pending,
        segments_source=segments_source,
        jump_to_timestamp=jump_to_timestamp,
        has_live_transcription=has_live_transcription
    )


@sessions_bp.route('/api/events/refined-load', methods=['POST'])
def log_session_refined_load():
    """
    Log session_refined_load event to EventLedger.
    CROWN⁴ Event #5: Tracks detailed session page access with performance metrics.
    """
    from services.event_ledger_service import EventLedgerService
    from models.event_ledger import EventType
    from datetime import datetime
    
    try:
        data = request.get_json() or {}
        
        # Extract metrics from request
        session_id = data.get('session_id')
        external_session_id = data.get('external_session_id')
        total_load_time = data.get('total_load_time', 0)
        cache_hit = data.get('cache_hit', False)
        
        if not session_id and not external_session_id:
            return jsonify({
                'success': False,
                'error': 'session_id or external_session_id required'
            }), 400
        
        # Log event to EventLedger
        event = EventLedgerService.log_event(
            event_type=EventType.SESSION_REFINED_LOAD,
            session_id=session_id,
            external_session_id=external_session_id,
            payload={
                'total_load_time_ms': total_load_time,
                'cache_hit': cache_hit,
                'timestamp': datetime.utcnow().isoformat()
            },
            trace_id=f"session_refined_load_{session_id or external_session_id}_{datetime.utcnow().timestamp()}"
        )
        
        # Mark event as completed
        EventLedgerService.complete_event(event, result={
            'status': 'success',
            'sub_300ms': total_load_time < 300
        }, duration_ms=total_load_time)
        
        logger.info(f"📄 Session refined load event logged for session {session_id or external_session_id} ({total_load_time}ms)")
        
        return jsonify({
            'success': True,
            'event_id': event.id,
            'total_time': total_load_time,
            'sub_300ms': total_load_time < 300
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to log session_refined_load event: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@sessions_bp.route('/<int:session_id>/export.md', methods=['GET'])
def export_session_markdown(session_id):
    """
    GET /sessions/<id>/export.md - Export session to Markdown
    
    Returns:
        Markdown file download with Content-Disposition header
    """
    try:
        # Generate markdown content
        markdown_content = ExportService.session_to_markdown(session_id)
        if not markdown_content:
            abort(404)
        
        # Generate filename
        filename = ExportService.get_export_filename(session_id, 'md')
        
        # Return as downloadable file
        return Response(
            markdown_content,
            mimetype='text/markdown',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        return jsonify({'error': f'Failed to export session: {str(e)}'}), 500