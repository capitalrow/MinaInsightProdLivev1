"""
Analytics WebSocket Namespace - CROWN⁵+ Real-time Analytics Updates

Handles real-time updates for:
- Analytics data refresh after meeting completion
- Participant metrics updates
- Speaking time distribution changes
- Sentiment analysis results
- KPI updates and period comparisons
- Meeting health score changes
"""

import logging
from flask import request
from flask_socketio import emit, join_room, leave_room

logger = logging.getLogger(__name__)

# Global reference to socketio for broadcasting
_socketio = None


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
    
    # Store socketio reference for broadcasting
    global _socketio
    _socketio = socketio
    
    logger.info("✅ Analytics WebSocket namespace registered (/analytics)")


def broadcast_analytics_update(workspace_id, event_type, data):
    """
    Broadcast analytics update to workspace room.
    
    Args:
        workspace_id: Workspace ID to broadcast to
        event_type: Type of update ('kpi_update', 'health_score', 'productivity', etc.)
        data: Update data payload
    
    Usage from API endpoints:
        from routes.analytics_websocket import broadcast_analytics_update
        broadcast_analytics_update(workspace_id, 'kpi_update', kpi_data)
    """
    global _socketio
    if _socketio is None:
        logger.warning("Analytics WebSocket not initialized, skipping broadcast")
        return False
    
    try:
        room = f"workspace_{workspace_id}"
        _socketio.emit(
            'analytics_update',
            {
                'type': event_type,
                'data': data,
                'timestamp': __import__('datetime').datetime.now().isoformat()
            },
            room=room,
            namespace='/analytics'
        )
        logger.debug(f"Broadcast {event_type} to {room}")
        return True
    except Exception as e:
        logger.error(f"Failed to broadcast analytics update: {e}")
        return False


def broadcast_meeting_analytics(meeting_id, event_type, data):
    """
    Broadcast analytics update for a specific meeting.
    
    Args:
        meeting_id: Meeting ID to broadcast to
        event_type: Type of update
        data: Update data payload
    """
    global _socketio
    if _socketio is None:
        logger.warning("Analytics WebSocket not initialized, skipping broadcast")
        return False
    
    try:
        room = f"meeting_{meeting_id}"
        _socketio.emit(
            'meeting_analytics_update',
            {
                'type': event_type,
                'meeting_id': meeting_id,
                'data': data,
                'timestamp': __import__('datetime').datetime.now().isoformat()
            },
            room=room,
            namespace='/analytics'
        )
        logger.debug(f"Broadcast {event_type} to meeting {meeting_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to broadcast meeting analytics: {e}")
        return False
