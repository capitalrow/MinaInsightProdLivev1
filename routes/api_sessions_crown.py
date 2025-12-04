"""
CROWN 4.6 Sessions API - Delta Synchronization Endpoints
REST API for meetings page with incremental updates via event sourcing.
"""

import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, func, and_, or_, desc, cast, String
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import hashlib
import json

from models import db, Session, Meeting, EventLedger
from models.event_ledger import EventType
from services.event_broadcaster import event_broadcaster

logger = logging.getLogger(__name__)

api_sessions_crown_bp = Blueprint('api_sessions_crown', __name__, url_prefix='/api/sessions')


def _get_range_filter(range_param: str):
    """Convert range parameter to date filter."""
    now = datetime.utcnow()
    if range_param == 'last30':
        return now - timedelta(days=30)
    elif range_param == 'last90':
        return now - timedelta(days=90)
    else:  # 'all'
        return None


def _session_to_meeting_card(session: Session, meeting: Optional[Meeting]) -> Dict[str, Any]:
    """Convert Session to MeetingCard format for frontend."""
    # Determine status based on session and post-transcription status
    if session.status == 'active':
        status = 'recording'
    elif session.post_transcription_status == 'processing':
        status = 'processing'
    elif meeting and getattr(meeting, 'archived', False):
        status = 'archived'
    else:
        status = 'ready'
    
    # Get task and highlight counts (safely handle lazy load failures)
    try:
        task_count = meeting.task_count if meeting else 0
    except Exception:
        task_count = 0
    
    highlight_count = 0  # TODO: Implement highlights tracking
    
    # Calculate session etag
    try:
        updated_at = meeting.updated_at if meeting else session.started_at
    except Exception:
        updated_at = session.started_at
    
    etag_source = f"{session.id}:{updated_at.isoformat()}"
    etag = hashlib.md5(etag_source.encode()).hexdigest()[:16]
    
    return {
        'session_id': session.external_id,
        'title': session.title,
        'started_at': session.started_at.isoformat(),
        'ended_at': session.completed_at.isoformat() if session.completed_at else None,
        'status': status,
        'tasks': task_count,
        'highlights': highlight_count,
        'duration_s': int(session.total_duration) if session.total_duration else None,
        'etag': etag,
        'updated_at': updated_at.isoformat()
    }


def _compute_global_etag(workspace_id: int, range_filter: Optional[datetime], show_archived: bool) -> str:
    """Compute ETag for entire meetings list based on latest event."""
    # Get latest event for this workspace
    latest_event = db.session.scalar(
        select(EventLedger)
        .where(EventLedger.event_type.in_([
            EventType.SESSION_UPDATE_CREATED,
            EventType.MEETING_UPDATE,
            EventType.SESSION_ARCHIVE,
            EventType.SESSION_FINALIZED
        ]))
        .where(cast(EventLedger.payload['workspace_id'], String) == str(workspace_id))
        .order_by(desc(EventLedger.id))
        .limit(1)
    )
    
    if latest_event:
        return f"w{workspace_id}:e{latest_event.id}"
    
    # Fallback: hash of current state
    count = db.session.scalar(
        select(func.count(Session.id))
        .join(Session.workspace)
        .where(Session.workspace_id == workspace_id)
    ) or 0
    
    return f"w{workspace_id}:c{count}"


@api_sessions_crown_bp.route('/header', methods=['GET'])
@login_required
def get_sessions_header():
    """
    GET /api/sessions/header?range&archived
    
    Returns summary statistics and etag for cache reconciliation.
    CROWN 4.6 Step 3: meetings_header_reconcile
    """
    try:
        workspace_id = current_user.workspace_id
        
        # Handle case where user has no workspace
        if workspace_id is None:
            return jsonify({
                'total': 0,
                'live': 0,
                'archived': 0,
                'last_event_id': 0,
                'etag': 'w0:c0'
            })
        
        range_param = request.args.get('range', 'last30')
        show_archived = request.args.get('archived', 'false').lower() == 'true'
        
        range_filter = _get_range_filter(range_param)
        
        # Build base query
        query = select(Session).where(Session.workspace_id == workspace_id)
        
        if range_filter:
            query = query.where(Session.started_at >= range_filter)
        
        # Count total (non-archived)
        total_query = query.outerjoin(Session.meeting).where(
            or_(Meeting.archived == False, Meeting.id.is_(None))
        )
        total = db.session.scalar(select(func.count()).select_from(total_query.subquery())) or 0
        
        # Count live (status=recording)
        live_query = query.where(Session.status == 'active')
        live = db.session.scalar(select(func.count()).select_from(live_query.subquery())) or 0
        
        # Count archived
        archived_query = query.join(Session.meeting).where(Meeting.archived == True)
        archived = db.session.scalar(select(func.count()).select_from(archived_query.subquery())) or 0
        
        # Get latest event_id for this workspace
        last_event = db.session.scalar(
            select(EventLedger.id)
            .where(cast(EventLedger.payload['workspace_id'], String) == str(workspace_id))
            .order_by(desc(EventLedger.id))
            .limit(1)
        )
        last_event_id = last_event if last_event else 0
        
        # Compute global etag
        etag = _compute_global_etag(workspace_id, range_filter, show_archived)
        
        return jsonify({
            'total': total,
            'live': live,
            'archived': archived,
            'last_event_id': last_event_id,
            'etag': etag
        })
        
    except Exception as e:
        logger.error(f"Error in get_sessions_header: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@api_sessions_crown_bp.route('/<session_id>/status', methods=['GET'])
@login_required
def get_session_status(session_id: str):
    """
    GET /api/sessions/<session_id>/status
    
    Lightweight endpoint for polling session processing status.
    Used by session view page to detect when insights become ready.
    """
    try:
        session = db.session.scalar(
            select(Session)
            .where(Session.external_id == session_id)
            .where(Session.workspace_id == current_user.workspace_id)
        )
        
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        return jsonify({
            'session_id': session.external_id,
            'status': session.status,
            'post_transcription_status': session.post_transcription_status,
            'has_meeting': session.meeting is not None
        })
        
    except Exception as e:
        logger.error(f"Error in get_session_status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@api_sessions_crown_bp.route('', methods=['GET'])
@api_sessions_crown_bp.route('/', methods=['GET'])
@login_required
def get_sessions_diff():
    """
    GET /api/sessions?range&sort&cursor&since_event_id
    
    Returns incremental diff (upserts, deletes) since last sync.
    CROWN 4.6 Step 4: meetings_diff_fetch
    """
    try:
        logger.info(f"GET /api/sessions called - user_id={current_user.id}, workspace_id={getattr(current_user, 'workspace_id', None)}")
        workspace_id = current_user.workspace_id
        
        # Handle case where user has no workspace
        if workspace_id is None:
            return jsonify({
                'upserts': [],
                'deletes': [],
                'cursor': None,
                'last_event_id': 0
            })
        
        range_param = request.args.get('range', 'last30')
        sort_order = request.args.get('sort', 'newest')
        cursor = request.args.get('cursor')
        since_event_id = request.args.get('since_event_id', type=int, default=0)
        
        range_filter = _get_range_filter(range_param)
        
        # Build base query with eager loading
        query = (
            select(Session)
            .options(joinedload(Session.meeting))
            .where(Session.workspace_id == workspace_id)
        )
        
        if range_filter:
            query = query.where(Session.started_at >= range_filter)
        
        # Apply sorting
        if sort_order == 'oldest':
            query = query.order_by(Session.started_at.asc())
        else:  # newest
            query = query.order_by(Session.started_at.desc())
        
        # Execute query
        sessions = db.session.scalars(query).unique().all()
        
        # Convert to MeetingCard format
        upserts = []
        for session in sessions:
            card = _session_to_meeting_card(session, session.meeting)
            upserts.append(card)
        
        # Get latest event_id for response
        last_event = db.session.scalar(
            select(EventLedger.id)
            .where(cast(EventLedger.payload['workspace_id'], String) == str(workspace_id))
            .order_by(desc(EventLedger.id))
            .limit(1)
        )
        last_event_id = last_event if last_event else 0
        
        # For now, no pagination cursor (implement if needed)
        response_cursor = None
        
        return jsonify({
            'upserts': upserts,
            'deletes': [],  # TODO: Track deleted sessions
            'cursor': response_cursor,
            'last_event_id': last_event_id
        })
        
    except Exception as e:
        logger.error(f"Error in get_sessions_diff: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@api_sessions_crown_bp.route('/<session_id>', methods=['PATCH'])
@login_required
def patch_session(session_id: str):
    """
    PATCH /api/sessions/:id
    
    Idempotent operations: archive, rename, restore
    Uses client_ulid for deduplication.
    CROWN 4.6 Step 5: Archive/Rename operations
    """
    try:
        data = request.get_json() or {}
        operation = data.get('op')
        client_ulid = data.get('client_ulid')
        
        if not operation:
            return jsonify({'error': 'op field required'}), 400
        
        if not client_ulid:
            return jsonify({'error': 'client_ulid required for idempotency'}), 400
        
        # Check if operation already processed (idempotency)
        existing_event = db.session.scalar(
            select(EventLedger)
            .where(EventLedger.idempotency_key == client_ulid)
            .limit(1)
        )
        
        if existing_event:
            logger.info(f"Duplicate operation detected, client_ulid={client_ulid}")
            return jsonify({'success': True, 'duplicate': True})
        
        # Find session
        session = db.session.scalar(
            select(Session)
            .where(Session.external_id == session_id)
            .where(Session.workspace_id == current_user.workspace_id)
        )
        
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Ensure meeting exists
        if not session.meeting:
            # Create meeting if doesn't exist
            from services.meeting_lifecycle_service import MeetingLifecycleService
            meeting = MeetingLifecycleService.create_meeting_from_session(session.id)
            if not meeting:
                return jsonify({'error': 'Failed to create meeting'}), 500
        else:
            meeting = session.meeting
        
        # Perform operation
        if operation == 'archive':
            meeting.archive(current_user.id)
            event_name = "Meeting Archived"
            
        elif operation == 'restore':
            meeting.restore()
            event_name = "Meeting Restored"
            
        elif operation == 'rename':
            title = data.get('title')
            if not title:
                return jsonify({'error': 'title required for rename'}), 400
            session.title = title
            meeting.title = title
            event_name = "Meeting Renamed"
            
        else:
            return jsonify({'error': f'Unknown operation: {operation}'}), 400
        
        # Commit changes
        db.session.commit()
        
        # Create event with idempotency key
        from services.event_sequencer import event_sequencer
        event = event_sequencer.create_event(
            event_type=EventType.MEETING_UPDATE if operation != 'archive' else EventType.SESSION_ARCHIVE,
            event_name=event_name,
            payload={
                'session_id': session.id,
                'external_session_id': session.external_id,
                'meeting_id': meeting.id,
                'workspace_id': current_user.workspace_id,
                'operation': operation,
                'user_id': current_user.id
            },
            session_id=session.id,
            idempotency_key=client_ulid
        )
        
        # Broadcast update via WebSocket
        card = _session_to_meeting_card(session, meeting)
        event_broadcaster.broadcast_meeting_update(
            meeting_id=meeting.id,
            meeting_data=card,
            workspace_id=current_user.workspace_id
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in patch_session: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
