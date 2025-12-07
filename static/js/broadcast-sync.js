/**
 * CROWN⁴ BroadcastChannel Multi-Tab Synchronization
 * 
 * Enables real-time cache invalidation and synchronization across multiple browser tabs.
 * When a user makes a change in one tab (archive, task update, etc.), all other tabs
 * receive and apply the change immediately via BroadcastChannel API.
 * 
 * Architecture:
 * - Channel: mina_sync_{workspaceId}
 * - Events: CACHE_INVALIDATE, MEETING_UPDATE, TASK_UPDATE, ARCHIVE_UPDATE
 * - Message Format: { type, payload, timestamp, tabId }
 * 
 * CROWN⁴ Phase 4 Task #12: Multi-tab sync with zero-desync architecture
 */

// Prevent redeclaration using window check
(function() {
    if (window.BroadcastSync) {
        console.log('📡 BroadcastSync already loaded, skipping redeclaration');
        return;
    }
    
window.BroadcastSync = class BroadcastSync {
    constructor(workspaceId = 'default') {
        this.workspaceId = workspaceId;
        this.channelName = `mina_sync_${workspaceId}`;
        this.channel = null;
        this.tabId = this._generateTabId();
        this.listeners = new Map();
        this.messageQueue = [];
        this.isInitialized = false;
        
        // CROWN⁴.14: Message deduplication to prevent echo loops
        this._processedMessageIds = new Set();
        this._messageIdCleanupInterval = null;
        this._maxProcessedMessages = 100;
        this._messageSeq = 0;
        
        // CROWN⁴.14: Handler guard - prevents rebroadcasts while handling incoming message
        this._isHandlingBroadcast = false;
        
        // Event types - Complete CROWN⁴ 15-event pipeline
        this.EVENTS = {
            // Existing events
            CACHE_INVALIDATE: 'cache_invalidate',
            MEETING_UPDATE: 'meeting_update',
            MEETING_ARCHIVE: 'meeting_archive',
            MEETING_RESTORE: 'meeting_restore',
            TASK_UPDATE: 'task_update',
            STATS_UPDATE: 'stats_update',
            FULL_SYNC: 'full_sync',
            
            // CROWN⁴ Complete Event Set
            DASHBOARD_BOOTSTRAP: 'dashboard_bootstrap',
            SESSION_UPDATE_CREATED: 'session_update:created',
            SESSION_PREFETCH: 'session_prefetch',
            SESSION_CARD_CLICK: 'session_card_click',
            SESSION_REFINED_LOAD: 'session_refined_load',
            ANALYTICS_REFRESH: 'analytics_refresh',
            DASHBOARD_REFRESH: 'dashboard_refresh',
            FILTER_APPLY: 'filter_apply',
            SEARCH_QUERY: 'search_query',
            SESSION_ARCHIVE: 'session_archive',
            ARCHIVE_REVEAL: 'archive_reveal',
            DASHBOARD_IDLE_SYNC: 'dashboard_idle_sync',
            UI_STATE_SYNC: 'ui_state_sync',
            INSIGHT_REMINDER: 'insight_reminder'
        };
    }
    
    /**
     * Initialize BroadcastChannel and set up listeners
     */
    init() {
        if (this.isInitialized) {
            console.warn('[BroadcastSync] Already initialized');
            return;
        }
        
        // Check if BroadcastChannel is supported
        if (typeof BroadcastChannel === 'undefined') {
            console.warn('[BroadcastSync] BroadcastChannel not supported in this browser');
            return;
        }
        
        try {
            // Create channel
            this.channel = new BroadcastChannel(this.channelName);
            
            // Set up message listener
            this.channel.onmessage = (event) => {
                this._handleMessage(event.data);
            };
            
            // Handle errors
            this.channel.onerror = (error) => {
                console.error('[BroadcastSync] Channel error:', error);
            };
            
            this.isInitialized = true;
            console.log(`✅ BroadcastSync initialized: ${this.channelName} (tab=${this.tabId})`);
            
            // Announce tab presence
            this.broadcast(this.EVENTS.FULL_SYNC, {
                action: 'tab_connected',
                tabId: this.tabId,
                timestamp: Date.now()
            });
            
        } catch (error) {
            console.error('[BroadcastSync] Failed to initialize:', error);
        }
    }
    
    /**
     * CROWN⁴.14: Generate unique message ID for deduplication
     * @private
     */
    _generateMessageId() {
        this._messageSeq++;
        return `${this.tabId}_${Date.now()}_${this._messageSeq}`;
    }
    
    /**
     * Broadcast message to all other tabs
     * @param {string} type - Event type
     * @param {Object} payload - Message payload
     * @param {Object} options - Broadcast options
     */
    broadcast(type, payload, options = {}) {
        if (!this.channel) {
            console.warn('[BroadcastSync] Channel not initialized, queueing message');
            this.messageQueue.push({ type, payload });
            return;
        }
        
        // CROWN⁴.14: Block broadcasts while handling incoming message (prevents echo loops)
        if (this._isHandlingBroadcast && !options.allowDuringHandler) {
            console.log(`📡 [BroadcastSync] Skipping broadcast during handler: ${type}`);
            return;
        }
        
        // CROWN⁴.14: Generate unique messageId for deduplication
        const messageId = this._generateMessageId();
        
        const message = {
            type,
            payload,
            timestamp: Date.now(),
            tabId: this.tabId,
            workspaceId: this.workspaceId,
            messageId: messageId,
            isRebroadcast: options.isRebroadcast || false
        };
        
        // CROWN⁴.14: Track our own messages to prevent self-echo
        this._processedMessageIds.add(messageId);
        this._cleanupProcessedMessages();
        
        try {
            this.channel.postMessage(message);
            console.log(`📡 Broadcast sent: ${type} (id=${messageId.substring(0, 20)}...)`, payload);
        } catch (error) {
            console.error('[BroadcastSync] Failed to broadcast:', error);
        }
    }
    
    /**
     * CROWN⁴.14: Cleanup old processed message IDs to prevent memory leak
     * @private
     */
    _cleanupProcessedMessages() {
        if (this._processedMessageIds.size > this._maxProcessedMessages) {
            const toDelete = this._processedMessageIds.size - this._maxProcessedMessages;
            const ids = Array.from(this._processedMessageIds);
            for (let i = 0; i < toDelete; i++) {
                this._processedMessageIds.delete(ids[i]);
            }
        }
    }
    
    /**
     * Register listener for specific event type
     * @param {string} type - Event type
     * @param {Function} callback - Callback function (payload, message) => void
     */
    on(type, callback) {
        if (!this.listeners.has(type)) {
            this.listeners.set(type, []);
        }
        
        this.listeners.get(type).push(callback);
        console.log(`🎧 Listener registered: ${type} (total=${this.listeners.get(type).length})`);
    }
    
    /**
     * Unregister listener
     * @param {string} type - Event type
     * @param {Function} callback - Callback to remove
     */
    off(type, callback) {
        if (!this.listeners.has(type)) {
            return;
        }
        
        const callbacks = this.listeners.get(type);
        const index = callbacks.indexOf(callback);
        
        if (index > -1) {
            callbacks.splice(index, 1);
            console.log(`🔇 Listener removed: ${type}`);
        }
    }
    
    /**
     * Invalidate cache across all tabs
     * @param {string} cacheKey - Cache key to invalidate (e.g., 'meetings', 'tasks')
     * @param {Object} [options] - Additional options
     */
    invalidateCache(cacheKey, options = {}) {
        this.broadcast(this.EVENTS.CACHE_INVALIDATE, {
            cacheKey,
            ...options
        });
    }
    
    /**
     * Broadcast meeting update (archive, restore, delete)
     * @param {number} meetingId - Meeting ID
     * @param {Object} changes - Changes applied
     */
    broadcastMeetingUpdate(meetingId, changes) {
        this.broadcast(this.EVENTS.MEETING_UPDATE, {
            meetingId,
            changes,
            timestamp: Date.now()
        });
    }
    
    /**
     * Broadcast meeting archive
     * @param {number} meetingId - Meeting ID
     */
    broadcastMeetingArchive(meetingId) {
        this.broadcast(this.EVENTS.MEETING_ARCHIVE, {
            meetingId,
            archived: true,
            timestamp: Date.now()
        });
    }
    
    /**
     * Broadcast meeting restore
     * @param {number} meetingId - Meeting ID
     */
    broadcastMeetingRestore(meetingId) {
        this.broadcast(this.EVENTS.MEETING_RESTORE, {
            meetingId,
            archived: false,
            timestamp: Date.now()
        });
    }
    
    /**
     * Broadcast task update
     * @param {number} taskId - Task ID
     * @param {Object} changes - Changes applied
     */
    broadcastTaskUpdate(taskId, changes) {
        this.broadcast(this.EVENTS.TASK_UPDATE, {
            taskId,
            changes,
            timestamp: Date.now()
        });
    }
    
    /**
     * Broadcast stats update
     */
    broadcastStatsUpdate() {
        this.broadcast(this.EVENTS.STATS_UPDATE, {
            timestamp: Date.now()
        });
    }
    
    /**
     * Handle incoming broadcast message
     * @private
     */
    _handleMessage(message) {
        // Ignore messages from self
        if (message.tabId === this.tabId) {
            return;
        }
        
        // Ignore messages from different workspace
        if (message.workspaceId !== this.workspaceId) {
            return;
        }
        
        // CROWN⁴.14: Message deduplication - skip if already processed
        if (message.messageId && this._processedMessageIds.has(message.messageId)) {
            console.log(`📨 [BroadcastSync] Skipping duplicate message: ${message.type} (id=${message.messageId.substring(0, 20)}...)`);
            return;
        }
        
        // CROWN⁴.14: Track this message to prevent re-processing
        if (message.messageId) {
            this._processedMessageIds.add(message.messageId);
            this._cleanupProcessedMessages();
        }
        
        // CROWN⁴.14: Skip rebroadcasts to prevent infinite loops
        if (message.isRebroadcast) {
            console.log(`📨 [BroadcastSync] Skipping rebroadcast: ${message.type}`);
            return;
        }
        
        // CROWN⁴.14: Set handler guard to prevent rebroadcasts from within handlers
        this._isHandlingBroadcast = true;
        
        try {
            console.log(`📨 Broadcast received: ${message.type}`, message.payload);
            
            // Call registered listeners
            const listeners = this.listeners.get(message.type) || [];
            listeners.forEach(callback => {
                try {
                    callback(message.payload, message);
                } catch (error) {
                    console.error(`[BroadcastSync] Listener error for ${message.type}:`, error);
                }
            });
            
            // Default handlers
            this._applyDefaultHandlers(message);
        } finally {
            // CROWN⁴.14: Always clear handler guard
            this._isHandlingBroadcast = false;
        }
    }
    
    /**
     * Apply default handlers for common events
     * @private
     */
    async _applyDefaultHandlers(message) {
        const { type, payload } = message;
        
        try {
            switch (type) {
                case this.EVENTS.CACHE_INVALIDATE:
                    await this._handleCacheInvalidate(payload);
                    break;
                    
                case this.EVENTS.MEETING_UPDATE:
                    await this._handleMeetingUpdate(payload);
                    break;
                    
                case this.EVENTS.MEETING_ARCHIVE:
                case this.EVENTS.MEETING_RESTORE:
                    await this._handleMeetingArchiveRestore(payload);
                    break;
                    
                case this.EVENTS.TASK_UPDATE:
                    await this._handleTaskUpdate(payload);
                    break;
                    
                case this.EVENTS.STATS_UPDATE:
                    await this._handleStatsUpdate();
                    break;
                    
                case this.EVENTS.FULL_SYNC:
                    console.log(`👋 Tab connected: ${payload.tabId}`);
                    break;
                
                // CROWN⁴ Complete Event Handlers
                case this.EVENTS.SESSION_UPDATE_CREATED:
                    await this._handleSessionCreated(payload);
                    break;
                    
                case this.EVENTS.ANALYTICS_REFRESH:
                case this.EVENTS.DASHBOARD_REFRESH:
                    await this._handleDashboardRefresh(payload);
                    break;
                    
                case this.EVENTS.FILTER_APPLY:
                    await this._handleFilterApply(payload);
                    break;
                    
                case this.EVENTS.SEARCH_QUERY:
                    await this._handleSearchQuery(payload);
                    break;
                    
                case this.EVENTS.ARCHIVE_REVEAL:
                    await this._handleArchiveReveal(payload);
                    break;
                    
                case this.EVENTS.DASHBOARD_IDLE_SYNC:
                    await this._handleIdleSync(payload);
                    break;
                    
                case this.EVENTS.UI_STATE_SYNC:
                    await this._handleUIStateSync(payload);
                    break;
                    
                case this.EVENTS.INSIGHT_REMINDER:
                    console.log('💡 Insight reminder received:', payload);
                    break;
            }
        } catch (error) {
            console.error(`[BroadcastSync] Handler error for ${type}:`, error);
        }
    }
    
    /**
     * Handle cache invalidation
     * @private
     */
    async _handleCacheInvalidate(payload) {
        const { cacheKey } = payload;
        
        console.log(`🗑️ Cache invalidated: ${cacheKey}`);
        
        // Clear cache in IndexedDB if available
        if (window.cacheManager) {
            try {
                // Trigger refresh based on cache key
                if (cacheKey === 'meetings' && window.dashboard) {
                    await window.dashboard.loadMeetings();
                } else if (cacheKey === 'tasks' && window.dashboard) {
                    await window.dashboard.loadMyTasks();
                } else if (cacheKey === 'stats' && window.dashboard) {
                    await window.dashboard.loadStats();
                }
            } catch (error) {
                console.error('[BroadcastSync] Failed to refresh after cache invalidation:', error);
            }
        }
    }
    
    /**
     * Handle meeting update
     * @private
     */
    async _handleMeetingUpdate(payload) {
        const { meetingId, changes } = payload;
        
        console.log(`📝 Meeting updated: ${meetingId}`, changes);
        
        // Update UI if dashboard is available
        if (window.dashboard) {
            await window.dashboard.loadMeetings();
            await window.dashboard.loadStats();
        }
    }
    
    /**
     * Handle meeting archive/restore
     * @private
     */
    async _handleMeetingArchiveRestore(payload) {
        const { meetingId, archived } = payload;
        
        console.log(`${archived ? '📦' : '📂'} Meeting ${archived ? 'archived' : 'restored'}: ${meetingId}`);
        
        // Find meeting card and update UI
        const meetingCard = document.querySelector(`.meeting-card[data-meeting-id="${meetingId}"]`);
        if (meetingCard) {
            if (archived) {
                // Apply archived styling
                meetingCard.style.opacity = '0.6';
                meetingCard.style.filter = 'grayscale(30%)';
                
                // Add archived badge if not exists
                if (!meetingCard.querySelector('.badge-archived')) {
                    const titleEl = meetingCard.querySelector('.meeting-title');
                    if (titleEl) {
                        const badge = document.createElement('span');
                        badge.className = 'badge badge-secondary badge-archived ms-2';
                        badge.textContent = 'Archived';
                        titleEl.appendChild(badge);
                    }
                }
            } else {
                // Remove archived styling
                meetingCard.style.opacity = '1';
                meetingCard.style.filter = 'none';
                
                // Remove archived badge
                const badge = meetingCard.querySelector('.badge-archived');
                if (badge) {
                    badge.remove();
                }
            }
        }
        
        // Refresh data
        if (window.dashboard) {
            await window.dashboard.loadMeetings();
            await window.dashboard.loadStats();
        }
    }
    
    /**
     * Handle task update
     * @private
     */
    async _handleTaskUpdate(payload) {
        const { taskId, changes } = payload;
        
        console.log(`✅ Task updated: ${taskId}`, changes);
        
        // Update UI if dashboard is available
        if (window.dashboard) {
            await window.dashboard.loadMyTasks();
            await window.dashboard.loadStats();
        }
    }
    
    /**
     * Handle stats update
     * @private
     */
    async _handleStatsUpdate() {
        console.log('📊 Stats update requested');
        
        // Refresh stats
        if (window.dashboard) {
            await window.dashboard.loadStats();
        }
    }
    
    /**
     * Handle new session created (CROWN⁴)
     * @private
     */
    async _handleSessionCreated(payload) {
        console.log('📝 New session created:', payload);
        
        if (window.dashboard) {
            await window.dashboard.loadRecentMeetings();
            await window.dashboard.loadStats();
        }
    }
    
    /**
     * Handle dashboard refresh (CROWN⁴)
     * @private
     */
    async _handleDashboardRefresh(payload) {
        console.log('🔄 Dashboard refresh triggered');
        
        if (window.dashboard) {
            await window.dashboard.loadDashboardData();
        }
    }
    
    /**
     * Handle filter apply (CROWN⁴)
     * @private
     */
    async _handleFilterApply(payload) {
        const { filters } = payload;
        console.log('🔍 Filter applied:', filters);
        
        // Apply filters to dashboard view
        if (window.dashboard && window.dashboard.applyFilters) {
            window.dashboard.applyFilters(filters);
        }
    }
    
    /**
     * Handle search query (CROWN⁴)
     * @private
     */
    async _handleSearchQuery(payload) {
        const { query } = payload;
        console.log('🔎 Search query:', query);
        
        // Apply search to dashboard
        if (window.dashboard && window.dashboard.performSearch) {
            window.dashboard.performSearch(query);
        }
    }
    
    /**
     * Handle archive reveal (CROWN⁴)
     * @private
     */
    async _handleArchiveReveal(payload) {
        const { showArchived } = payload;
        console.log(`📂 Archive reveal: ${showArchived ? 'shown' : 'hidden'}`);
        
        // Toggle archived meetings visibility
        if (window.dashboard && window.dashboard.toggleArchived) {
            window.dashboard.toggleArchived(showArchived);
        }
    }
    
    /**
     * Handle idle sync (CROWN⁴)
     * @private
     */
    async _handleIdleSync(payload) {
        const { checksums } = payload;
        console.log('⏱️  Idle sync - validating checksums');
        
        // Validate cache checksums and re-sync if needed
        if (window.cache && checksums) {
            const localChecksums = await window.cache.getMetadata('meetings_checksum');
            if (localChecksums?.value !== checksums.meetings) {
                console.log('🔄 Cache drift detected, refreshing...');
                if (window.dashboard) {
                    await window.dashboard.loadDashboardData();
                }
            }
        }
    }
    
    /**
     * Handle UI state sync (CROWN⁴)
     * @private
     */
    async _handleUIStateSync(payload) {
        const { state } = payload;
        console.log('🎨 UI state sync:', state);
        
        // Sync UI state (filters, sorting, view mode, etc.)
        if (state) {
            // Apply scroll position
            if (state.scrollPosition && window.scrollTo) {
                window.scrollTo({ top: state.scrollPosition, behavior: 'smooth' });
            }
            
            // Apply view mode
            if (state.viewMode && window.dashboard && window.dashboard.setViewMode) {
                window.dashboard.setViewMode(state.viewMode);
            }
            
            // Apply sort order
            if (state.sortBy && window.dashboard && window.dashboard.setSortOrder) {
                window.dashboard.setSortOrder(state.sortBy);
            }
        }
    }
    
    /**
     * Generate unique tab ID
     * @private
     */
    _generateTabId() {
        return `tab_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    /**
     * Flush queued messages
     */
    flushQueue() {
        if (this.messageQueue.length === 0) {
            return;
        }
        
        console.log(`📤 Flushing ${this.messageQueue.length} queued messages`);
        
        const queue = [...this.messageQueue];
        this.messageQueue = [];
        
        queue.forEach(({ type, payload }) => {
            this.broadcast(type, payload);
        });
    }
    
    /**
     * Close channel and cleanup
     */
    destroy() {
        if (this.channel) {
            this.broadcast(this.EVENTS.FULL_SYNC, {
                action: 'tab_disconnected',
                tabId: this.tabId,
                timestamp: Date.now()
            });
            
            this.channel.close();
            this.channel = null;
        }
        
        this.listeners.clear();
        this.messageQueue = [];
        this.isInitialized = false;
        
        console.log('🔌 BroadcastSync destroyed');
    }
};

// Export singleton instance  
window.broadcastSync = new window.BroadcastSync();

// Auto-initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.broadcastSync.init();
    });
} else {
    window.broadcastSync.init();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.broadcastSync) {
        window.broadcastSync.destroy();
    }
});
})(); // End IIFE
