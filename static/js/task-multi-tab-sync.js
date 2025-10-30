/**
 * CROWN⁴.5 Multi-Tab Sync via BroadcastChannel
 * Synchronizes task state changes across browser tabs in real-time.
 */

class MultiTabSync {
    constructor() {
        this.channel = null;
        this.tabId = this._generateTabId();
        this.isLeader = false;
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
     * Broadcast message to other tabs
     * @param {Object} message
     */
    _broadcast(message) {
        if (!this.channel) return;
        
        this.channel.postMessage({
            ...message,
            from_tab: this.tabId,
            timestamp: Date.now()
        });
    }

    /**
     * Handle incoming messages from other tabs
     * @param {Object} data
     */
    _handleMessage(data) {
        // Ignore own messages
        if (data.from_tab === this.tabId) return;

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
                this._handleTaskCreated(data.task);
                break;

            case 'task_updated':
                this._handleTaskUpdated(data.task);
                break;

            case 'task_deleted':
                this._handleTaskDeleted(data.task_id);
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
     */
    broadcastTaskCreated(task) {
        this._broadcast({
            type: 'task_created',
            task: task
        });
    }

    /**
     * Broadcast task update
     * @param {Object} task
     */
    broadcastTaskUpdated(task) {
        this._broadcast({
            type: 'task_updated',
            task: task
        });
    }

    /**
     * Broadcast task deletion
     * @param {number} taskId
     */
    broadcastTaskDeleted(taskId) {
        this._broadcast({
            type: 'task_deleted',
            task_id: taskId
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
     */
    async _handleTaskCreated(task) {
        // Save to cache
        await window.taskCache.saveTask(task);

        // Add to DOM if visible
        if (this._shouldRenderTask(task)) {
            if (window.optimisticUI) {
                window.optimisticUI._addTaskToDOM(task);
            }
        }

        // Show notification
        this._showNotification(`Task created in another tab: ${task.title}`);
    }

    /**
     * Handle task updated in another tab
     * @param {Object} task
     */
    async _handleTaskUpdated(task) {
        // Update cache
        await window.taskCache.saveTask(task);

        // Update DOM
        if (window.optimisticUI) {
            window.optimisticUI._updateTaskInDOM(task.id, task);
        }
    }

    /**
     * Handle task deleted in another tab
     * @param {number} taskId
     */
    async _handleTaskDeleted(taskId) {
        // Remove from cache
        await window.taskCache.deleteTask(taskId);

        // Remove from DOM
        if (window.optimisticUI) {
            window.optimisticUI._removeTaskFromDOM(taskId);
        }
    }

    /**
     * Handle filter changed in another tab
     * @param {Object} filter
     */
    async _handleFilterChanged(filter) {
        // Save view state
        await window.taskCache.setViewState('tasks_page', {
            ...await window.taskCache.getViewState('tasks_page'),
            ...filter
        });

        // Refresh if on tasks page
        if (window.location.pathname.includes('/tasks')) {
            if (window.taskBootstrap) {
                const tasks = await window.taskCache.getFilteredTasks(filter);
                await window.taskBootstrap.renderTasks(tasks);
            }
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
        if (state.tasks) {
            await window.taskCache.saveTasks(state.tasks);
        }

        if (state.view_state) {
            await window.taskCache.setViewState('tasks_page', state.view_state);
        }

        // Refresh UI
        if (window.taskBootstrap) {
            await window.taskBootstrap.bootstrap();
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

// Export singleton
window.multiTabSync = new MultiTabSync();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.multiTabSync) {
        window.multiTabSync.close();
    }
});

console.log('🔗 CROWN⁴.5 MultiTabSync loaded');
