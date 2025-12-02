"""
Admin Dashboard WebSocket Namespace - Real-time updates for Cognitive Mission Control

Provides real-time streaming of:
- System health metrics
- Pipeline performance
- AI oversight data
- Incident alerts
- Business metrics updates
"""

import logging
import threading
import time
from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user

logger = logging.getLogger(__name__)

_socketio = None
_broadcast_thread = None
_broadcast_active = False


def register_admin_namespace(socketio):
    """
    Register Admin WebSocket namespace handlers.
    
    Namespace: /admin
    Events:
    - connect: Admin client connects
    - disconnect: Admin client disconnects  
    - subscribe: Subscribe to specific metric streams
    """
    global _socketio
    _socketio = socketio
    
    @socketio.on('connect', namespace='/admin')
    def handle_admin_connect():
        """Handle admin client connection."""
        try:
            client_id = request.sid
            logger.info(f"Admin client connected: {client_id}")
            
            join_room('admin_dashboard')
            
            emit('connected', {
                'message': 'Connected to admin namespace',
                'client_id': client_id,
                'namespace': '/admin',
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Admin connect error: {e}", exc_info=True)
    
    @socketio.on('disconnect', namespace='/admin')
    def handle_admin_disconnect():
        """Handle admin client disconnection."""
        try:
            client_id = request.sid
            logger.info(f"Admin client disconnected: {client_id}")
            leave_room('admin_dashboard')
            
        except Exception as e:
            logger.error(f"Admin disconnect error: {e}", exc_info=True)
    
    @socketio.on('subscribe', namespace='/admin')
    def handle_subscribe(data):
        """
        Subscribe to specific metric streams.
        
        Args:
            data: {'streams': ['system', 'pipeline', 'ai', 'incidents', 'business']}
        """
        try:
            streams = data.get('streams', ['all'])
            client_id = request.sid
            
            for stream in streams:
                room = f"admin_{stream}"
                join_room(room)
                logger.debug(f"Client {client_id} subscribed to {room}")
            
            emit('subscribed', {
                'streams': streams,
                'message': 'Subscribed to metric streams'
            })
            
        except Exception as e:
            logger.error(f"Subscribe error: {e}", exc_info=True)
            emit('error', {'message': 'Failed to subscribe'})
    
    @socketio.on('unsubscribe', namespace='/admin')
    def handle_unsubscribe(data):
        """Unsubscribe from metric streams."""
        try:
            streams = data.get('streams', [])
            client_id = request.sid
            
            for stream in streams:
                room = f"admin_{stream}"
                leave_room(room)
                logger.debug(f"Client {client_id} unsubscribed from {room}")
            
            emit('unsubscribed', {
                'streams': streams
            })
            
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}", exc_info=True)
    
    @socketio.on('request_metrics', namespace='/admin')
    def handle_request_metrics(data):
        """Handle explicit request for current metrics."""
        try:
            from services.admin_metrics_service import get_admin_metrics_service
            
            metrics_service = get_admin_metrics_service()
            metric_type = data.get('type', 'all')
            
            response = {
                'timestamp': datetime.utcnow().isoformat(),
                'type': metric_type
            }
            
            if metric_type in ['all', 'system']:
                response['system'] = metrics_service.get_system_health()
            
            if metric_type in ['all', 'pipeline']:
                response['pipeline'] = metrics_service.get_pipeline_health()
            
            if metric_type in ['all', 'ai']:
                response['ai'] = metrics_service.get_copilot_metrics()
            
            if metric_type in ['all', 'timeline']:
                response['timeline'] = metrics_service.get_system_timeline_data(hours=24)
            
            if metric_type in ['all', 'confidence']:
                response['confidence'] = metrics_service.get_confidence_distribution()
            
            emit('metrics_update', response)
            
        except Exception as e:
            logger.error(f"Request metrics error: {e}", exc_info=True)
            emit('error', {'message': 'Failed to fetch metrics'})
    
    @socketio.on('ping_latency', namespace='/admin')
    def handle_ping_latency(data):
        """Handle latency ping for WS connection monitoring."""
        try:
            client_timestamp = data.get('timestamp', 0)
            server_timestamp = time.time() * 1000
            
            emit('pong_latency', {
                'client_timestamp': client_timestamp,
                'server_timestamp': server_timestamp
            })
            
        except Exception as e:
            logger.error(f"Ping latency error: {e}")
    
    logger.info("✅ Admin WebSocket namespace registered (/admin)")


def start_admin_broadcast(interval: int = 5):
    """
    Start background thread for broadcasting admin metrics.
    
    Args:
        interval: Broadcast interval in seconds
    """
    global _broadcast_thread, _broadcast_active
    
    if _broadcast_active:
        return
    
    _broadcast_active = True
    _broadcast_thread = threading.Thread(
        target=_broadcast_loop,
        args=(interval,),
        daemon=True
    )
    _broadcast_thread.start()
    logger.info(f"✅ Admin broadcast started (interval: {interval}s)")


def stop_admin_broadcast():
    """Stop the admin broadcast thread."""
    global _broadcast_active
    _broadcast_active = False
    if _broadcast_thread:
        _broadcast_thread.join(timeout=5)
    logger.info("Admin broadcast stopped")


def _broadcast_loop(interval: int):
    """Main broadcast loop for pushing real-time updates."""
    global _socketio, _broadcast_active
    
    time.sleep(2)
    
    while _broadcast_active:
        try:
            if _socketio and hasattr(_socketio, 'server') and _socketio.server:
                _broadcast_metrics()
        except Exception as e:
            logger.error(f"Broadcast error: {e}", exc_info=True)
        
        time.sleep(interval)


def _broadcast_metrics():
    """Broadcast current metrics to all subscribed admin clients."""
    global _socketio
    
    if not _socketio:
        return
    
    try:
        from services.admin_metrics_service import get_admin_metrics_service
        
        metrics_service = get_admin_metrics_service()
        
        system_health = metrics_service.get_system_health()
        _socketio.emit('system_metrics', {
            'timestamp': datetime.utcnow().isoformat(),
            'data': system_health
        }, namespace='/admin', room='admin_dashboard')
        
        pipeline_health = metrics_service.get_pipeline_health()
        _socketio.emit('pipeline_metrics', {
            'timestamp': datetime.utcnow().isoformat(),
            'data': pipeline_health
        }, namespace='/admin', room='admin_dashboard')
        
        copilot_metrics = metrics_service.get_copilot_metrics()
        _socketio.emit('ai_metrics', {
            'timestamp': datetime.utcnow().isoformat(),
            'data': copilot_metrics
        }, namespace='/admin', room='admin_dashboard')
        
    except Exception as e:
        logger.error(f"Error broadcasting metrics: {e}", exc_info=True)


def broadcast_incident(incident_data: dict):
    """
    Broadcast a new incident to all admin clients.
    
    Args:
        incident_data: Incident dictionary with id, severity, title, description
    """
    global _socketio
    
    if not _socketio:
        return
    
    try:
        _socketio.emit('incident', {
            'timestamp': datetime.utcnow().isoformat(),
            'data': incident_data
        }, namespace='/admin', room='admin_dashboard')
        
        logger.info(f"Broadcasted incident: {incident_data.get('id')}")
        
    except Exception as e:
        logger.error(f"Error broadcasting incident: {e}", exc_info=True)


def broadcast_audit_log(audit_data: dict):
    """
    Broadcast a new audit log entry to admin clients.
    
    Args:
        audit_data: Audit log dictionary
    """
    global _socketio
    
    if not _socketio:
        return
    
    try:
        _socketio.emit('audit_log', {
            'timestamp': datetime.utcnow().isoformat(),
            'data': audit_data
        }, namespace='/admin', room='admin_dashboard')
        
    except Exception as e:
        logger.error(f"Error broadcasting audit log: {e}", exc_info=True)
