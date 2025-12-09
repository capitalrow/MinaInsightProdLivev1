/**
 * CROWN⁴.5 Multi-Tab Sync via BroadcastChannel
 * Synchronizes task state changes across browser tabs in real-time.
 */

class MultiTabSync {
    constructor() {
        this.channel = null;
        this.tabId = this._generateTabId();
        this.isLeader = false;
        
        // CROWN⁴.14: Message deduplication and echo loop prevention
        this._processedMessageIds = new Set();
        this._maxProcessedMessages = 100;
        this._messageSeq = 0;
        
        // CROWN⁴.14: Initial load guard - block filter operations during initial load
        this._isInitialLoad = true;
        this._isApplyingRemoteState = false;
        this._settlingPeriodMs = 1000; // 1 second settling period after hydration
        this._hydrationCompleteTime = 0;
        
        // Listen for hydration complete to clear initial load flag
        document.addEventListener('tasks:hydrated', () => {
            this._isInitialLoad = false;
            this._hydrationCompleteTime = Date.now();
            console.log('[MultiTabSync] Hydration complete - filter operations enabled after settling');
        });
        
        this._init();
    }

    /**
     * Generate unique tab ID
     * @returns {string}
     */
    _generateTabId() {
        return `tab_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Initialize BroadcastChannel
     */
    _init() {
        if (!('BroadcastChannel' in window)) {
            console.warn('⚠️ BroadcastChannel not supported');
            return;
        }

        this.channel = new BroadcastChannel('mina_tasks_sync');
        
        this.channel.onmessage = (event) => {
            this._handleMessage(event.data);
        };

        // Announce this tab
        this._broadcast({
            type: 'tab_connected',
            tab_id: this.tabId,
            timestamp: Date.now()
        });

        // Listen for tab visibility changes
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this._requestSync();
            }
        });

        console.log(`📡 Multi-tab sync initialized (Tab: ${this.tabId})`);
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
     * CROWN⁴.14: Cleanup old processed message IDs
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
     * CROWN⁴.14: Check if still in settling period after hydration
     * @private
     */
    _isInSettlingPeriod() {
        if (this._hydrationCompleteTime === 0) return false;
        const elapsed = Date.now() - this._hydrationCompleteTime;
        return elapsed < this._settlingPeriodMs;
    }
    
    /**
     * Broadcast message to other tabs
     * @param {Object} message
     */
    _broadcast(message) {
        if (!this.channel) return;
        
        // CROWN⁴.14: Don't broadcast if applying remote state (prevents echo loop)
        if (this._isApplyingRemoteState) {
            console.log(`[MultiTabSync] Skipping broadcast during remote state application: ${message.type}`);
            return;
        }
        
        // CROWN⁴.14: Generate unique message ID
        const messageId = this._generateMessageId();
        
        // Track our own message to prevent self-echo
        this._processedMessageIds.add(messageId);
        this._cleanupProcessedMessages();
        
        this.channel.postMessage({
            ...message,
            from_tab: this.tabId,
            timestamp: Date.now(),
            messageId: messageId
        });
    }

    /**
     * Handle incoming messages from other tabs
     * @param {Object} data
     */
    _handleMessage(data) {
        // Ignore own messages
        if (data.from_tab === this.tabId) return;
        
        // CROWN⁴.14: Message deduplication - skip if already processed
        if (data.messageId && this._processedMessageIds.has(data.messageId)) {
            console.log(`[MultiTabSync] Skipping duplicate message: ${data.type}`);
            return;
        }
        
        // CROWN⁴.14: Track this message to prevent re-processing
        if (data.messageId) {
            this._processedMessageIds.add(data.messageId);
            this._cleanupProcessedMessages();
        }

        console.log('📨 Multi-tab message received:', data.type);

        switch (data.type) {
            case 'tab_connected':
                console.log(`👋 Tab connected: ${data.from_tab}`);
                // Send current state to new tab
                if (this.isLeader) {
                    this._sendState();
                }
                break;

            case 'task_created':
                // TASK 5: Pass event_id for deduplication
                this._handleTaskCreated(data.task, data.event_id);
                break;

            case 'task_updated':
                // TASK 5: Pass event_id for deduplication
                this._handleTaskUpdated(data.task, data.event_id);
                break;

            case 'task_deleted':
                // TASK 5: Pass event_id for deduplication
                this._handleTaskDeleted(data.task_id, data.event_id);
                break;

            case 'filter_changed':
                this._handleFilterChanged(data.filter);
                break;

            case 'sync_request':
                if (this.isLeader) {
                    this._sendState();
                }
                break;

            case 'state_sync':
                this._handleStateSync(data.state);
                break;

            case 'cache_invalidated':
                this._handleCacheInvalidation();
                break;
        }
    }

    /**
     * Broadcast task creation
     * @param {Object} task
     * @param {Object} metadata - Optional CROWN metadata for deduplication
     */
    broadcastTaskCreated(task, metadata = {}) {
        this._broadcast({
            type: 'task_created',
            task: task,
            event_id: metadata.event_id || task._crown_event_id
        });
    }

    /**
     * Broadcast task update
     * @param {Object} task
     * @param {Object} metadata - Optional CROWN metadata for deduplication
     */
    broadcastTaskUpdated(task, metadata = {}) {
        this._broadcast({
            type: 'task_updated',
            task: task,
            event_id: metadata.event_id || task._crown_event_id
        });
    }

    /**
     * Broadcast task deletion
     * @param {number} taskId
     * @param {Object} metadata - Optional CROWN metadata for deduplication
     */
    broadcastTaskDeleted(taskId, metadata = {}) {
        this._broadcast({
            type: 'task_deleted',
            task_id: taskId,
            event_id: metadata.event_id
        });
    }

    /**
     * Broadcast filter change
     * @param {Object} filter
     */
    broadcastFilterChanged(filter) {
        this._broadcast({
            type: 'filter_changed',
            filter: filter
        });
    }

    /**
     * Broadcast cache invalidation
     */
    broadcastCacheInvalidation() {
        this._broadcast({
            type: 'cache_invalidated'
        });
    }

    /**
     * Handle task created in another tab
     * @param {Object} task
     * @param {string} eventId - Optional CROWN event_id for deduplication
     */
    async _handleTaskCreated(task, eventId) {
        // TASK 5: Event deduplication - use passed event_id for consistent dedup
        if (window.taskEventDeduplicator) {
            const dedupData = eventId ? { event_id: eventId, task } : { task };
            const { isNew } = window.taskEventDeduplicator.checkAndMark('task_created', dedupData, 'broadcast');
            if (!isNew) {
                console.log('⏭️ [BroadcastChannel] Skipping duplicate task_created event');
                return;
            }
        }
        
        // Save to cache
        await window.taskCache.saveTask(task);

        // Add to DOM if visible
        if (this._shouldRenderTask(task)) {
            if (window.optimisticUI) {
                window.optimisticUI._addTaskToDOM(task);
            }
        }
        
        // Dispatch event for filter reapplication
        window.dispatchEvent(new CustomEvent('task:created', {
            detail: { task, fromMultiTab: true }
        }));

        // Show notification
        this._showNotification(`Task created in another tab: ${task.title}`);
    }

    /**
     * Handle task updated in another tab
     * @param {Object} task
     * @param {string} eventId - Optional CROWN event_id for deduplication
     */
    async _handleTaskUpdated(task, eventId) {
        // TASK 5: Event deduplication - use passed event_id for consistent dedup
        if (window.taskEventDeduplicator) {
            const dedupData = eventId ? { event_id: eventId, task } : { task };
            const { isNew } = window.taskEventDeduplicator.checkAndMark('task_updated', dedupData, 'broadcast');
            if (!isNew) {
                console.log('⏭️ [BroadcastChannel] Skipping duplicate task_updated event');
                return;
            }
        }
        
        // Update cache
        await window.taskCache.saveTask(task);

        // Update DOM
        if (window.optimisticUI) {
            window.optimisticUI._updateTaskInDOM(task.id, task);
        }
        
        // CRITICAL: Dispatch event for filter reapplication (since _updateTaskInDOM is private and doesn't emit events)
        window.dispatchEvent(new CustomEvent('task:updated', {
            detail: { taskId: task.id, task, fromMultiTab: true }
        }));
    }

    /**
     * Handle task deleted in another tab
     * @param {number} taskId
     * @param {string} eventId - Optional CROWN event_id for deduplication
     */
    async _handleTaskDeleted(taskId, eventId) {
        // TASK 5: Event deduplication - use passed event_id for consistent dedup
        if (window.taskEventDeduplicator) {
            const dedupData = eventId ? { event_id: eventId, task_id: taskId } : { task_id: taskId };
            const { isNew } = window.taskEventDeduplicator.checkAndMark('task_deleted', dedupData, 'broadcast');
            if (!isNew) {
                console.log('⏭️ [BroadcastChannel] Skipping duplicate task_deleted event');
                return;
            }
        }
        
        // Remove from cache
        await window.taskCache.deleteTask(taskId);

        // Remove from DOM
        if (window.optimisticUI) {
            window.optimisticUI._removeTaskFromDOM(taskId);
        }
        
        // Dispatch event for filter reapplication
        window.dispatchEvent(new CustomEvent('task:deleted', {
            detail: { taskId, fromMultiTab: true }
        }));
    }

    /**
     * CROWN⁴.9: Check if hydration is ready
     * @returns {boolean}
     */
    _isHydrationReady() {
        return window.taskHydrationReady || 
               (window.taskBootstrap?.isHydrationReady?.() ?? false);
    }
    
    /**
     * Handle filter changed in another tab
     * @param {Object} filter
     */
    async _handleFilterChanged(filter) {
        // CROWN⁴.14: Block filter operations during initial page load
        if (this._isInitialLoad) {
            console.log('[MultiTabSync] _handleFilterChanged blocked - initial load in progress');
            return;
        }
        
        // CROWN⁴.14: Block during settling period after hydration
        if (this._isInSettlingPeriod()) {
            console.log('[MultiTabSync] _handleFilterChanged blocked - in settling period');
            return;
        }
        
        // CROWN⁴.9: Block filter operations until hydration is complete
        if (!this._isHydrationReady()) {
            console.log('[MultiTabSync] _handleFilterChanged blocked - hydration not ready');
            return;
        }
        
        // CROWN⁴.15: Check user action lock from TaskSearchSort to prevent echo loops
        if (window.taskSearchSort?._isUserActionLocked?.()) {
            console.log('[MultiTabSync] _handleFilterChanged blocked - user action lock active');
            return;
        }
        
        // CROWN⁴.14: Set flag to prevent re-broadcast during remote state application
        this._isApplyingRemoteState = true;
        
        try {
            // Save view state
            await window.taskCache.setViewState('tasks_page', {
                ...await window.taskCache.getViewState('tasks_page'),
                ...filter
            });

            // Refresh if on tasks page
            if (window.location.pathname.includes('/tasks')) {
                if (window.taskBootstrap) {
                    const tasks = await window.taskCache.getFilteredTasks(filter);
                    
                    // CROWN⁴.9 FIX: Prevent render loop during initial bootstrap
                    // Skip render if cache is empty but server already rendered tasks
                    const container = document.getElementById('tasks-list-container');
                    const serverRenderedCards = container?.querySelectorAll('.task-card')?.length || 0;
                    if ((!tasks || tasks.length === 0) && serverRenderedCards > 0) {
                        console.log(`[MultiTabSync] Skipping filter render - cache empty but ${serverRenderedCards} server cards exist`);
                        return;
                    }
                    
                    // CROWN⁴.12: Pass sync metadata - lower priority than user actions
                    const sortConfig = window.taskBootstrap._getCurrentViewContext?.()?.sort || { field: 'created_at', direction: 'desc' };
                    await window.taskBootstrap.renderTasks(tasks, { 
                        isFilterChange: false,
                        source: 'websocket', // Cross-tab sync has same priority as WebSocket
                        filterContext: filter.filter || filter.status || 'active',
                        searchQuery: filter.search || '',
                        sortConfig: sortConfig,
                        fromMultiTab: true
                    });
                }
            }
        } finally {
            // CROWN⁴.14: Always clear flag, even on error
            this._isApplyingRemoteState = false;
        }
    }

    /**
     * Request state sync from leader tab
     */
    _requestSync() {
        this._broadcast({
            type: 'sync_request'
        });
    }

    /**
     * Send current state to other tabs
     */
    async _sendState() {
        const tasks = await window.taskCache.getAllTasks();
        const viewState = await window.taskCache.getViewState('tasks_page');

        this._broadcast({
            type: 'state_sync',
            state: {
                tasks: tasks,
                view_state: viewState
            }
        });
    }

    /**
     * Handle state sync from another tab
     * @param {Object} state
     */
    async _handleStateSync(state) {
        // CROWN⁴.14: Block during initial load to prevent race conditions
        if (this._isInitialLoad) {
            console.log('[MultiTabSync] _handleStateSync blocked - initial load in progress');
            return;
        }
        
        // CROWN⁴.14: Block during settling period
        if (this._isInSettlingPeriod()) {
            console.log('[MultiTabSync] _handleStateSync blocked - in settling period');
            return;
        }
        
        // CROWN⁴.15: Check user action lock from TaskSearchSort to prevent echo loops
        if (window.taskSearchSort?._isUserActionLocked?.()) {
            console.log('[MultiTabSync] _handleStateSync blocked - user action lock active');
            return;
        }
        
        this._isApplyingRemoteState = true;
        
        try {
            if (state.tasks) {
                await window.taskCache.saveTasks(state.tasks);
            }

            if (state.view_state) {
                await window.taskCache.setViewState('tasks_page', state.view_state);
            }

            // Refresh UI only if hydration is ready
            if (window.taskBootstrap && this._isHydrationReady()) {
                await window.taskBootstrap.syncInBackground();
            }
        } finally {
            this._isApplyingRemoteState = false;
        }
    }

    /**
     * Handle cache invalidation
     */
    async _handleCacheInvalidation() {
        console.log('🔄 Cache invalidated by another tab - reloading...');
        
        if (window.taskBootstrap) {
            await window.taskBootstrap.syncInBackground();
        }
    }

    /**
     * Check if task should be rendered based on current filters
     * @param {Object} task
     * @returns {boolean}
     */
    _shouldRenderTask(task) {
        // Simplified - in production would check against active filters
        return true;
    }

    /**
     * Show notification
     * @param {string} message
     */
    _showNotification(message) {
        if (window.showToast) {
            window.showToast(message, 'info');
        }
    }

    /**
     * Close channel (cleanup)
     */
    close() {
        if (this.channel) {
            this.channel.close();
        }
    }
}

// Export class for orchestrator
window.MultiTabSync = MultiTabSync;

// CROWN⁴.10 SINGLETON GUARD: Prevent double instantiation
if (!window.__minaMultiTabSyncInstantiated && !window.multiTabSync) {
    window.__minaMultiTabSyncInstantiated = true;
    window.multiTabSync = new MultiTabSync();
    console.log('🔗 CROWN⁴.5 MultiTabSync loaded (singleton)');
} else if (window.multiTabSync) {
    console.log('🔗 CROWN⁴.5 MultiTabSync already exists');
} else {
    console.warn('⚠️ [MultiTabSync] BLOCKED duplicate instantiation attempt');
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.multiTabSync) {
        window.multiTabSync.close();
    }
});
