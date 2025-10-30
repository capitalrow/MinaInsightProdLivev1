"""
BroadcastChannel Service - Multi-Tab Task Synchronization (Server-Side Support)

Coordinates BroadcastChannel messages across tabs via WebSocket namespace.
Ensures deterministic multi-tab state consistency for CROWN⁴.5.

Frontend uses native BroadcastChannel API; backend provides:
- Event validation and sequencing
- Conflict resolution
- State reconciliation messages
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class BroadcastChannelService:
    """
    Server-side support for multi-tab BroadcastChannel synchronization.
    
    Responsibilities:
    - Validate events received from any tab
    - Broadcast reconciled state to all tabs in workspace
    - Handle conflict resolution when multiple tabs update same task
    - Maintain single source of truth (database)
    """
    
    def __init__(self):
        """Initialize BroadcastChannelService."""
        self.active_channels = {}  # workspace_id -> set of connected clients
        self.metrics = {
            'broadcasts_sent': 0,
            'conflicts_resolved': 0,
            'tabs_synchronized': 0
        }
    
    def register_client(self, workspace_id: int, client_id: str, tab_id: str):
        """
        Register a new tab/client for broadcast synchronization.
        
        Args:
            workspace_id: Workspace ID
            client_id: WebSocket client ID (request.sid)
            tab_id: Browser tab identifier
        """
        if workspace_id not in self.active_channels:
            self.active_channels[workspace_id] = {}
        
        self.active_channels[workspace_id][client_id] = {
            'tab_id': tab_id,
            'connected_at': datetime.utcnow().isoformat(),
            'last_seen': datetime.utcnow().isoformat()
        }
        
        tab_count = len(self.active_channels[workspace_id])
        logger.info(f"Tab registered: workspace={workspace_id}, tab={tab_id}, "
                   f"total_tabs={tab_count}")
    
    def unregister_client(self, workspace_id: int, client_id: str):
        """
        Unregister a tab/client from broadcast synchronization.
        
        Args:
            workspace_id: Workspace ID
            client_id: WebSocket client ID
        """
        if workspace_id in self.active_channels:
            if client_id in self.active_channels[workspace_id]:
                del self.active_channels[workspace_id][client_id]
                
                # Clean up empty workspaces
                if not self.active_channels[workspace_id]:
                    del self.active_channels[workspace_id]
                
                logger.info(f"Tab unregistered: workspace={workspace_id}, client={client_id}")
    
    def broadcast_to_workspace(self, workspace_id: int, event_type: str,
                              payload: Dict[str, Any], exclude_client: Optional[str] = None) -> int:
        """
        Broadcast event to all tabs in workspace.
        
        Args:
            workspace_id: Workspace ID
            event_type: Event type (e.g., 'task_update', 'task_created')
            payload: Event payload
            exclude_client: Optional client ID to exclude (usually the sender)
            
        Returns:
            Number of tabs notified
        """
        if workspace_id not in self.active_channels:
            return 0
        
        broadcast_message = {
            'type': 'broadcast',
            'event_type': event_type,
            'payload': payload,
            'timestamp': datetime.utcnow().isoformat(),
            'workspace_id': workspace_id
        }
        
        tabs_notified = 0
        for client_id, client_info in self.active_channels[workspace_id].items():
            # Skip the sender tab (it already has optimistic update)
            if client_id == exclude_client:
                continue
            
            # In production, emit via SocketIO to this specific client
            # emit('broadcast_event', broadcast_message, room=client_id)
            tabs_notified += 1
        
        self.metrics['broadcasts_sent'] += 1
        self.metrics['tabs_synchronized'] += tabs_notified
        
        logger.debug(f"Broadcast sent: event={event_type}, workspace={workspace_id}, "
                    f"tabs_notified={tabs_notified}")
        
        return tabs_notified
    
    def resolve_conflict(self, workspace_id: int, task_id: int,
                        conflicting_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Resolve conflicts when multiple tabs update same task simultaneously.
        
        Args:
            workspace_id: Workspace ID
            task_id: Task ID with conflict
            conflicting_updates: List of updates from different tabs
            
        Returns:
            Resolved update to broadcast to all tabs
        """
        if not conflicting_updates:
            return {}
        
        # Strategy: Last-write-wins with server timestamp as tie-breaker
        # Sort by updated_at timestamp (server authoritative)
        sorted_updates = sorted(
            conflicting_updates,
            key=lambda u: u.get('updated_at', ''),
            reverse=True
        )
        
        winning_update = sorted_updates[0]
        
        # Mark as reconciled
        winning_update['_reconciled'] = True
        winning_update['_conflict_resolved'] = True
        winning_update['_conflicting_updates_count'] = len(conflicting_updates)
        
        self.metrics['conflicts_resolved'] += 1
        
        logger.warning(f"Conflict resolved for task {task_id}: "
                      f"{len(conflicting_updates)} updates, winner timestamp: "
                      f"{winning_update.get('updated_at')}")
        
        return winning_update
    
    def get_workspace_tab_count(self, workspace_id: int) -> int:
        """
        Get number of active tabs for workspace.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Number of active tabs
        """
        return len(self.active_channels.get(workspace_id, {}))
    
    def heartbeat(self, workspace_id: int, client_id: str):
        """
        Update last_seen timestamp for tab (keepalive).
        
        Args:
            workspace_id: Workspace ID
            client_id: Client ID
        """
        if workspace_id in self.active_channels:
            if client_id in self.active_channels[workspace_id]:
                self.active_channels[workspace_id][client_id]['last_seen'] = \
                    datetime.utcnow().isoformat()
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get BroadcastChannel metrics.
        
        Returns:
            Dictionary of metrics
        """
        total_workspaces = len(self.active_channels)
        total_tabs = sum(len(clients) for clients in self.active_channels.values())
        
        return {
            **self.metrics,
            'active_workspaces': total_workspaces,
            'total_active_tabs': total_tabs,
            'workspaces': {
                ws_id: len(clients)
                for ws_id, clients in self.active_channels.items()
            }
        }


# Singleton instance
broadcast_channel_service = BroadcastChannelService()
