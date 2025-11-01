"""
Analytics WebSocket Namespace - CROWN⁴ Real-time Analytics Updates

Handles real-time updates for:
- Analytics data refresh after meeting completion
- Participant metrics updates
- Speaking time distribution changes
- Sentiment analysis results
"""

import logging
from flask import request
from flask_socketio import emit, join_room, leave_room
from services.event_broadcaster import event_broadcaster

logger = logging.getLogger(__name__)


def register_analytics_namespace(socketio):
    """
    Register Analytics WebSocket namespace handlers.
    
    Namespace: /analytics
    Events:
    - connect: Client connects
    - disconnect: Client disconnects
    - join_workspace: Join workspace room
    - subscribe_meeting: Subscribe to analytics for specific meeting
    """
    
    @socketio.on('connect', namespace='/analytics')
    def handle_analytics_connect():
        """Handle client connection to analytics namespace."""
        try:
            client_id = request.sid
            logger.info(f"Analytics client connected: {client_id}")
            
            emit('connected', {
                'message': 'Connected to analytics namespace',
                'client_id': client_id,
                'namespace': '/analytics'
            })
            
        except Exception as e:
            logger.error(f"Analytics connect error: {e}", exc_info=True)
    
    @socketio.on('disconnect', namespace='/analytics')
    def handle_analytics_disconnect():
        """Handle client disconnection from analytics namespace."""
        try:
            client_id = request.sid
            logger.info(f"Analytics client disconnected: {client_id}")
            
        except Exception as e:
            logger.error(f"Analytics disconnect error: {e}", exc_info=True)
    
    @socketio.on('join_workspace', namespace='/analytics')
    def handle_join_workspace(data):
        """
        Join workspace room for analytics updates.
        
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
            
            logger.info(f"Client {request.sid} joined analytics room: {room}")
            
            emit('joined_workspace', {
                'workspace_id': workspace_id,
                'room': room
            })
            
        except Exception as e:
            logger.error(f"Join workspace error: {e}", exc_info=True)
            emit('error', {'message': 'Failed to join workspace'})
    
    @socketio.on('subscribe_meeting', namespace='/analytics')
    def handle_subscribe_meeting(data):
        """
        Subscribe to analytics updates for specific meeting.
        
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
            
            logger.info(f"Client {request.sid} subscribed to meeting {meeting_id} analytics")
            
            emit('subscribed_meeting', {
                'meeting_id': meeting_id,
                'room': room
            })
            
        except Exception as e:
            logger.error(f"Subscribe meeting error: {e}", exc_info=True)
            emit('error', {'message': 'Failed to subscribe to meeting'})
    
    logger.info("✅ Analytics WebSocket namespace registered (/analytics)")
