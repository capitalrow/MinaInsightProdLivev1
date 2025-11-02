"""
Meetings WebSocket Namespace - CROWN⁴ Real-time Meeting Updates

Handles real-time updates for:
- Meeting metadata changes (title, description, status)
- Participant join/leave events
- Recording status changes
- Meeting archive/unarchive
"""

import logging
from flask import request
from flask_socketio import emit, join_room, leave_room
from services.event_broadcaster import event_broadcaster

logger = logging.getLogger(__name__)


def register_meetings_namespace(socketio):
    """
    Register Meetings WebSocket namespace handlers.
    
    Namespace: /meetings
    Events:
    - connect: Client connects
    - disconnect: Client disconnects
    - join_workspace: Join workspace room
    - subscribe_meeting: Subscribe to updates for specific meeting
    """
    
    @socketio.on('connect', namespace='/meetings')
    def handle_meetings_connect():
        """Handle client connection to meetings namespace."""
        try:
            # Get client ID from Flask request (patched by Flask-SocketIO)
            client_id = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"Meetings client connected: {client_id}")
            
            emit('connected', {
                'message': 'Connected to meetings namespace',
                'client_id': client_id,
                'namespace': '/meetings'
            })
            
        except Exception as e:
            logger.error(f"Meetings connect error: {e}", exc_info=True)
    
    @socketio.on('disconnect', namespace='/meetings')
    def handle_meetings_disconnect():
        """Handle client disconnection from meetings namespace."""
        try:
            client_id = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"Meetings client disconnected: {client_id}")
            
        except Exception as e:
            logger.error(f"Meetings disconnect error: {e}", exc_info=True)
    
    @socketio.on('join_workspace', namespace='/meetings')
    def handle_join_workspace(data):
        """
        Join workspace room for meeting updates.
        
        Args:
            data: {'workspace_id': int}
        """
        try:
            workspace_id = data.get('workspace_id')
            if not workspace_id:
                emit('error', {'message': 'workspace_id required'})
                return
            
            room = f"workspace_{workspace_id}"
            join_room(room)
            
            client_id = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"Client {client_id} joined meetings room: {room}")
            
            emit('joined_workspace', {
                'workspace_id': workspace_id,
                'room': room
            })
            
        except Exception as e:
            logger.error(f"Join workspace error: {e}", exc_info=True)
            emit('error', {'message': 'Failed to join workspace'})
    
    @socketio.on('subscribe_meeting', namespace='/meetings')
    def handle_subscribe_meeting(data):
        """
        Subscribe to updates for specific meeting.
        
        Args:
            data: {'meeting_id': int}
        """
        try:
            meeting_id = data.get('meeting_id')
            if not meeting_id:
                emit('error', {'message': 'meeting_id required'})
                return
            
            room = f"meeting_{meeting_id}"
            join_room(room)
            
            client_id = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"Client {client_id} subscribed to meeting {meeting_id} updates")
            
            emit('subscribed_meeting', {
                'meeting_id': meeting_id,
                'room': room
            })
            
        except Exception as e:
            logger.error(f"Subscribe meeting error: {e}", exc_info=True)
            emit('error', {'message': 'Failed to subscribe to meeting'})
    
    logger.info("✅ Meetings WebSocket namespace registered (/meetings)")
