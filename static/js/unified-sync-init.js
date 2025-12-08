/**
 * CROWN⁴ Unified Sync Initialization
 * 
 * Ensures consistent background synchronization across all dashboard pages.
 * Initializes ReconciliationCycle (30-second ETag checks) and WebSocket connections
 * for any authenticated page that needs real-time data updates.
 * 
 * Included in base.html to provide consistent sync behavior across:
 * - Dashboard
 * - Meetings
 * - Tasks  
 * - Analytics
 * - Calendar
 * - Copilot
 * - Settings
 */

(function() {
    'use strict';
    
    if (window.__unifiedSyncInitialized) {
        console.log('[UnifiedSync] Already initialized, skipping');
        return;
    }
    window.__unifiedSyncInitialized = true;
    
    const SYNC_CONFIG = {
        reconciliationInterval: 30000,
        wsReconnectDelay: 1000,
        maxReconnectAttempts: 10
    };
    
    let reconciliationCycle = null;
    let workspaceId = null;
    
    function getWorkspaceId() {
        if (workspaceId) return workspaceId;
        
        const metaTag = document.querySelector('meta[name="workspace-id"]');
        if (metaTag) {
            workspaceId = parseInt(metaTag.content, 10);
            return workspaceId;
        }
        
        const wsIdElement = document.querySelector('[data-workspace-id]');
        if (wsIdElement) {
            workspaceId = parseInt(wsIdElement.dataset.workspaceId, 10);
            return workspaceId;
        }
        
        if (window.WORKSPACE_ID) {
            workspaceId = window.WORKSPACE_ID;
            return workspaceId;
        }
        
        return null;
    }
    
    function initReconciliationCycle() {
        const wsId = getWorkspaceId();
        if (!wsId) {
            console.log('[UnifiedSync] No workspace ID found, skipping reconciliation');
            return;
        }
        
        if (typeof window.ReconciliationCycle === 'undefined') {
            console.log('[UnifiedSync] ReconciliationCycle not loaded, skipping');
            return;
        }
        
        if (reconciliationCycle && reconciliationCycle.isRunning) {
            console.log('[UnifiedSync] ReconciliationCycle already running');
            return;
        }
        
        reconciliationCycle = new window.ReconciliationCycle(wsId);
        reconciliationCycle.start();
        
        console.log(`[UnifiedSync] ReconciliationCycle started for workspace ${wsId}`);
    }
    
    function initWebSocketConnections() {
        const wsId = getWorkspaceId();
        if (!wsId) {
            console.log('[UnifiedSync] No workspace ID, skipping WebSocket init');
            return;
        }
        
        if (!window.wsManager) {
            console.log('[UnifiedSync] WebSocketManager not available');
            return;
        }
        
        const currentPath = window.location.pathname;
        let namespaces = ['dashboard'];
        
        if (currentPath.includes('/tasks')) {
            namespaces.push('tasks');
        } else if (currentPath.includes('/analytics')) {
            namespaces.push('analytics');
        } else if (currentPath.includes('/meetings')) {
            namespaces.push('meetings');
        } else if (currentPath.includes('/copilot')) {
            namespaces.push('copilot');
        }
        
        window.wsManager.init(wsId, namespaces);
        
        console.log(`[UnifiedSync] WebSocket connected to namespaces: ${namespaces.join(', ')}`);
    }
    
    function initBroadcastSync() {
        if (window.broadcastSync && window.broadcastSync.isInitialized) {
            console.log('[UnifiedSync] BroadcastSync already initialized');
            return;
        }
        
        console.log('[UnifiedSync] BroadcastSync handled by broadcast-sync.js auto-init');
    }
    
    function handleVisibilityChange() {
        if (document.hidden) {
            console.log('[UnifiedSync] Tab hidden, sync continues in background');
        } else {
            console.log('[UnifiedSync] Tab visible, triggering immediate sync');
            if (reconciliationCycle && reconciliationCycle.isRunning) {
                reconciliationCycle.runCycle();
            }
        }
    }
    
    function initialize() {
        const wsId = getWorkspaceId();
        if (!wsId) {
            console.log('[UnifiedSync] Not on authenticated page, sync disabled');
            return;
        }
        
        console.log('[UnifiedSync] Initializing unified sync system...');
        
        initBroadcastSync();
        initWebSocketConnections();
        
        if (typeof window.ReconciliationCycle !== 'undefined') {
            initReconciliationCycle();
        } else {
            const checkReconciliation = setInterval(() => {
                if (typeof window.ReconciliationCycle !== 'undefined') {
                    clearInterval(checkReconciliation);
                    initReconciliationCycle();
                }
            }, 100);
            
            setTimeout(() => clearInterval(checkReconciliation), 5000);
        }
        
        document.addEventListener('visibilitychange', handleVisibilityChange);
        
        window.addEventListener('beforeunload', () => {
            if (reconciliationCycle) {
                reconciliationCycle.stop();
            }
        });
        
        console.log('[UnifiedSync] Initialization complete');
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        setTimeout(initialize, 100);
    }
    
    window.unifiedSync = {
        getStatus: function() {
            return {
                workspaceId: getWorkspaceId(),
                reconciliationRunning: reconciliationCycle?.isRunning || false,
                reconciliationStats: reconciliationCycle?.getStats() || null,
                broadcastSyncActive: window.broadcastSync?.isInitialized || false,
                wsManagerConnected: window.wsManager?.isConnected || false
            };
        },
        
        forceSync: function() {
            if (reconciliationCycle) {
                reconciliationCycle.runCycle();
            }
            if (window.broadcastSync) {
                window.broadcastSync.broadcast('FULL_SYNC', { 
                    action: 'force_sync',
                    timestamp: Date.now()
                });
            }
        },
        
        restart: function() {
            if (reconciliationCycle) {
                reconciliationCycle.stop();
            }
            initialize();
        }
    };
    
})();
