"""
Analytics WebSocket Namespace - CROWN⁵+ Real-time Analytics Intelligence

Handles real-time analytics updates with event sequencing for:
- Cache-first bootstrap with validation
- Real-time delta updates
- Background sync and reconciliation
- Tab switching and prefetching
- Filter changes with optimistic updates

Implements CROWN⁵+ event lifecycle:
1. analytics_bootstrap - Initial page load with cache paint
2. analytics_ws_subscribe - Socket handshake with checkpoint
3. analytics_header_reconcile - ETag + checksum validation
4. analytics_overview_hydrate - Default tab data load
5. analytics_prefetch_tabs - Intelligent prefetching
6. analytics_delta_apply - Real-time KPI updates
7. analytics_filter_change - Date range changes
8. analytics_tab_switch - Tab navigation
9. analytics_export_initiated - Export requests
10. analytics_idle_sync - Background validation
"""

import logging
from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from services.event_broadcaster import event_broadcaster
from services.event_sequencer import event_sequencer
from services.analytics_cache_service import analytics_cache_service
from models.event_ledger import EventType
from datetime import datetime

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
    
    @socketio.on('analytics_bootstrap_request', namespace='/analytics')
    def handle_analytics_bootstrap(data):
        """
        Handle analytics_bootstrap request - cache-first load (CROWN⁵+).
        
        Client sends cached checksums to validate cache freshness.
        Server responds with 'valid' or full snapshot if cache is stale.
        
        Args:
            data: {
                'workspace_id': int,
                'days': int,
                'cached_checksums': dict,
                'last_event_id': int (optional)
            }
        """
        workspace_id = None
        days = 30
        try:
            logger.info(f"📨 Analytics bootstrap request received from client {request.sid}")
            logger.info(f"   Request data: {data}")
            
            workspace_id = data.get('workspace_id')
            days = data.get('days', 30)
            cached_checksums = data.get('cached_checksums', {})
            last_event_id = data.get('last_event_id')
            
            logger.info(f"   workspace_id={workspace_id}, days={days}, has_cache={bool(cached_checksums)}")
            
            if not workspace_id:
                logger.error("❌ Bootstrap rejected: missing workspace_id")
                emit('error', {'message': 'workspace_id required'})
                return
            
            # Create bootstrap event
            event = event_sequencer.create_event(
                event_type=EventType.ANALYTICS_BOOTSTRAP,
                event_name="Analytics Bootstrap",
                payload={
                    'workspace_id': workspace_id,
                    'days': days,
                    'client_id': request.sid
                },
                trace_id=f"analytics_bootstrap_{workspace_id}_{request.sid}"
            )
            
            # Get current snapshot
            snapshot = analytics_cache_service.get_analytics_snapshot(workspace_id, days)
            
            # Compare checksums
            server_checksums = snapshot.get('checksums', {})
            cache_valid = (
                cached_checksums.get('full') == server_checksums.get('full')
                if cached_checksums.get('full') else False
            )
            
            if cache_valid:
                # Cache is valid, send confirmation
                logger.info(f"✅ Cache valid - sending confirmation to client {request.sid}")
                emit('analytics_bootstrap_response', {
                    'status': 'valid',
                    'checksums': server_checksums,
                    'last_event_id': event.id,
                    'timestamp': datetime.utcnow().isoformat()
                })
                logger.info(f"   Response emitted: status=valid")
            else:
                # Cache is stale, send full snapshot
                logger.info(f"📦 Generating snapshot for workspace {workspace_id}")
                logger.info(f"   Snapshot contains: {len(snapshot.get('kpis', {}))} KPIs, {len(snapshot.get('charts', {}))} charts")
                emit('analytics_bootstrap_response', {
                    'status': 'snapshot',
                    'snapshot': snapshot,
                    'last_event_id': event.id,
                    'timestamp': datetime.utcnow().isoformat()
                })
                logger.info(f"   Response emitted: status=snapshot, size={len(str(snapshot))} bytes")
            
            # Mark event completed
            event_sequencer.mark_event_completed(
                event.id,
                result={'cache_valid': cache_valid},
                duration_ms=0,
                broadcast_status='sent'
            )
            
        except Exception as e:
            logger.error(f"Analytics bootstrap error: {e}", exc_info=True)
            logger.error(f"Bootstrap data received: workspace_id={workspace_id}, days={days}")
            emit('error', {
                'message': 'Bootstrap failed',
                'error': str(e),
                'workspace_id': workspace_id
            })
    
    @socketio.on('analytics_filter_change_request', namespace='/analytics')
    def handle_filter_change(data):
        """
        Handle analytics_filter_change - date range or segment change (CROWN⁵+).
        
        Args:
            data: {
                'workspace_id': int,
                'filters': {'days': int, 'segment': str, ...},
                'user_id': int
            }
        """
        try:
            workspace_id = data.get('workspace_id')
            filters = data.get('filters', {})
            user_id = data.get('user_id')
            
            if not workspace_id:
                emit('error', {'message': 'workspace_id required'})
                return
            
            # Broadcast filter change event
            event_broadcaster.broadcast_analytics_filter_change(
                workspace_id=workspace_id,
                filter_params=filters,
                user_id=user_id
            )
            
            # Get new snapshot with filters
            days = filters.get('days', 30)
            snapshot = analytics_cache_service.get_analytics_snapshot(workspace_id, days)
            
            emit('analytics_filter_response', {
                'snapshot': snapshot,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Filter change error: {e}", exc_info=True)
            emit('error', {'message': 'Filter change failed'})
    
    @socketio.on('analytics_tab_switch_request', namespace='/analytics')
    def handle_tab_switch(data):
        """
        Handle analytics_tab_switch - lazy-load tab data (CROWN⁵+).
        
        Args:
            data: {
                'workspace_id': int,
                'from_tab': str,
                'to_tab': str,
                'user_id': int,
                'days': int
            }
        """
        try:
            workspace_id = data.get('workspace_id')
            from_tab = data.get('from_tab')
            to_tab = data.get('to_tab')
            user_id = data.get('user_id')
            days = data.get('days', 30)
            
            if not workspace_id or not to_tab:
                emit('error', {'message': 'workspace_id and to_tab required'})
                return
            
            # Broadcast tab switch event
            event_broadcaster.broadcast_analytics_tab_switch(
                workspace_id=workspace_id,
                from_tab=from_tab or 'none',
                to_tab=to_tab,
                user_id=user_id
            )
            
            # Get tab-specific data (lazy load)
            snapshot = analytics_cache_service.get_analytics_snapshot(workspace_id, days)
            tab_data = snapshot.get('tabs', {}).get(to_tab, {})
            
            emit('analytics_tab_data', {
                'tab': to_tab,
                'data': tab_data,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Tab switch error: {e}", exc_info=True)
            emit('error', {'message': 'Tab switch failed'})
    
    @socketio.on('analytics_idle_sync_request', namespace='/analytics')
    def handle_idle_sync(data):
        """
        Handle analytics_idle_sync - background validation (CROWN⁵+).
        
        Args:
            data: {
                'workspace_id': int,
                'cached_checksums': dict,
                'days': int
            }
        """
        try:
            workspace_id = data.get('workspace_id')
            cached_checksums = data.get('cached_checksums', {})
            days = data.get('days', 30)
            
            if not workspace_id:
                emit('error', {'message': 'workspace_id required'})
                return
            
            # Get current snapshot
            snapshot = analytics_cache_service.get_analytics_snapshot(workspace_id, days)
            server_checksums = snapshot.get('checksums', {})
            
            # Detect drift
            drift_detected = (
                cached_checksums.get('full') != server_checksums.get('full')
                if cached_checksums.get('full') else True
            )
            
            if drift_detected:
                # Compute delta for efficient sync
                old_snapshot = {'checksums': cached_checksums}
                delta = analytics_cache_service.compute_delta(old_snapshot, snapshot)
                
                emit('analytics_drift_detected', {
                    'delta': delta,
                    'checksums': server_checksums,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                logger.info(f"Cache drift detected for workspace {workspace_id}")
            else:
                emit('analytics_sync_ok', {
                    'checksums': server_checksums,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Idle sync error: {e}", exc_info=True)
            emit('error', {'message': 'Idle sync failed'})
    
    logger.info("✅ Analytics WebSocket namespace registered (/analytics) with CROWN⁵+ events")
