/**
 * CROWN⁴.5 WebSocket Event Handlers
 * Connects to /tasks namespace and handles all 20 CROWN⁴.5 events.
 */

class TaskWebSocketHandlers {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.namespace = '/tasks';
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.handlers = new Map();
    }

    /**
     * Connect to tasks WebSocket namespace
     * @returns {Promise<void>}
     */
    async connect() {
        if (this.connected) {
            console.log('✅ Already connected to tasks namespace');
            return;
        }

        try {
            // Use existing socket.io connection
            if (!window.io) {
                console.error('❌ Socket.IO not available');
                return;
            }

            this.socket = window.io(this.namespace, {
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionAttempts: this.maxReconnectAttempts,
                reconnectionDelay: 1000
            });

            this._registerEventHandlers();
            console.log('📡 Connected to tasks WebSocket namespace');

        } catch (error) {
            console.error('❌ Failed to connect to tasks namespace:', error);
        }
    }

    /**
     * Register all CROWN⁴.5 event handlers
     */
    _registerEventHandlers() {
        // Connection events
        this.socket.on('connect', () => {
            this.connected = true;
            this.reconnectAttempts = 0;
            console.log('✅ Tasks WebSocket connected');
            
            // Trigger bootstrap
            this._emitBootstrap();
        });

        this.socket.on('disconnect', () => {
            this.connected = false;
            console.log('📵 Tasks WebSocket disconnected');
        });

        this.socket.on('reconnect', (attemptNumber) => {
            console.log(`🔄 Reconnected after ${attemptNumber} attempts`);
            this._emitBootstrap();
        });

        // CROWN⁴.5 Event Handlers (20 events)
        
        // 1. Bootstrap (initial data load)
        this.on('bootstrap_response', this._handleBootstrap.bind(this));
        
        // 2. Task Create
        this.on('task_created', this._handleTaskCreated.bind(this));
        
        // 2b. ID Reconciliation (temp→real ID mapping for offline task creation)
        this.on('id_reconciled', this._handleIDReconciled.bind(this));
        
        // 3-9. Task Update (7 variants)
        this.on('task_updated', this._handleTaskUpdated.bind(this));
        this.on('task_title_updated', this._handleTaskUpdated.bind(this));
        this.on('task_description_updated', this._handleTaskUpdated.bind(this));
        this.on('task_due_date_updated', this._handleTaskUpdated.bind(this));
        this.on('task_assignee_updated', this._handleTaskUpdated.bind(this));
        this.on('task_category_updated', this._handleTaskUpdated.bind(this));
        this.on('task_progress_updated', this._handleTaskUpdated.bind(this));
        
        // 10. Task Status Toggle
        this.on('task_status_toggled', this._handleTaskStatusToggled.bind(this));
        
        // 11. Task Priority Change
        this.on('task_priority_changed', this._handleTaskPriorityChanged.bind(this));
        
        // 12. Task Labels Update
        this.on('task_labels_updated', this._handleTaskLabelsUpdated.bind(this));
        
        // 13. Task Snooze
        this.on('task_snoozed', this._handleTaskSnoozed.bind(this));
        
        // 14. Task Merge
        this.on('tasks_merged', this._handleTasksMerged.bind(this));
        
        // 15. Transcript Jump
        this.on('transcript_jump', this._handleTranscriptJump.bind(this));
        
        // 16. Task Filter
        this.on('filter_changed', this._handleFilterChanged.bind(this));
        
        // 17. Task Refresh
        this.on('tasks_refreshed', this._handleTasksRefreshed.bind(this));
        
        // 18. Idle Sync
        this.on('idle_sync_complete', this._handleIdleSyncComplete.bind(this));
        
        // 19. Offline Queue Replay
        this.on('offline_queue_replayed', this._handleOfflineQueueReplayed.bind(this));
        
        // 20. Task Delete
        this.on('task_deleted', this._handleTaskDeleted.bind(this));
        
        // Bulk operations
        this.on('tasks_bulk_updated', this._handleTasksBulkUpdated.bind(this));
        
        // Error handling
        this.on('error', this._handleError.bind(this));
    }

    /**
     * Register event handler
     * @param {string} event
     * @param {Function} handler
     */
    on(event, handler) {
        if (!this.socket) return;
        
        this.socket.on(event, handler);
        this.handlers.set(event, handler);
    }

    /**
     * Emit event to server
     * @param {string} event
     * @param {Object} data
     */
    emit(event, data) {
        if (!this.socket || !this.connected) {
            console.warn(`⚠️ Cannot emit ${event} - not connected`);
            return;
        }
        
        this.socket.emit(event, data);
    }

    // Event Handlers

    /**
     * Emit bootstrap request
     */
    _emitBootstrap() {
        this.emit('task_event', {
            event_type: 'bootstrap'
        });
    }

    /**
     * Handle bootstrap response
     * @param {Object} data
     */
    async _handleBootstrap(data) {
        console.log('📦 Bootstrap data received:', data);
        
        if (data.tasks) {
            await window.taskCache.saveTasks(data.tasks);
        }
        
        if (data.view_state) {
            await window.taskCache.setViewState('tasks_page', data.view_state);
        }
        
        if (data.counters) {
            this._updateCountersFromServer(data.counters);
        }
        
        // CROWN⁴.5: Request pending reconciliations to catch up on missed broadcasts
        this._requestPendingReconciliations();
    }
    
    /**
     * Request pending reconciliations for bootstrap recovery (CROWN⁴.5)
     * Catches up on temp→real ID mappings that may have been missed
     */
    _requestPendingReconciliations() {
        if (!this.socket || !this.socket.connected) {
            console.warn('⚠️ Cannot request reconciliations - WebSocket not connected');
            return;
        }
        
        const workspace_id = window.WORKSPACE_ID || null;
        
        // Request pending reconciliations from server
        this.socket.emit('reconciliations:get_pending', { workspace_id }, (response) => {
            if (response && response.success && response.reconciliations) {
                console.log(`🔄 Received ${response.count} pending reconciliations for bootstrap recovery`);
                
                // Process each reconciliation like a live broadcast
                response.reconciliations.forEach(async (recon) => {
                    if (recon.real_id && recon.temp_id) {
                        // Trigger the same handler as live broadcasts
                        await this._handleIDReconciled({
                            temp_id: recon.temp_id,
                            real_id: recon.real_id,
                            user_id: recon.user_id,
                            workspace_id: recon.workspace_id,
                            timestamp: recon.reconciled_at || recon.created_at
                        });
                    }
                });
            }
        });
    }

    /**
     * Handle task created
     * @param {Object} data
     */
    async _handleTaskCreated(data) {
        const task = data.task || data;
        console.log('✨ Task created:', task.id);
        
        await window.taskCache.saveTask(task);
        
        if (window.optimisticUI) {
            window.optimisticUI._addTaskToDOM(task);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskCreated(task);
        }
    }

    /**
     * Handle ID reconciliation - temp→real ID mapping for offline task creation
     * @param {Object} data - Contains temp_id, real_id, user_id, workspace_id
     */
    async _handleIDReconciled(data) {
        const { temp_id, real_id, user_id, workspace_id, timestamp } = data;
        console.log(`🔄 ID Reconciled: ${temp_id} → ${real_id}`);
        
        if (!temp_id || !real_id) {
            console.error('⚠️ Invalid reconciliation data:', data);
            return;
        }
        
        try {
            // 1. Update IndexedDB cache - reconcile temp ID to real ID
            if (window.taskCache && window.taskCache.reconcileTempID) {
                await window.taskCache.reconcileTempID(temp_id, real_id);
                console.log(`✅ Cache reconciled: ${temp_id} → ${real_id}`);
            }
            
            // 2. Update DOM elements that reference the temp ID
            const tempCard = document.querySelector(`[data-task-id="${temp_id}"]`);
            if (tempCard) {
                // Update data attribute
                tempCard.setAttribute('data-task-id', real_id);
                
                // Update checkbox ID
                const checkbox = tempCard.querySelector(`#task-${temp_id}`);
                if (checkbox) {
                    checkbox.id = `task-${real_id}`;
                    checkbox.setAttribute('data-task-id', real_id);
                }
                
                // Remove syncing indicator
                const syncBadge = tempCard.querySelector('.temp-id-badge');
                if (syncBadge) {
                    syncBadge.remove();
                }
                
                // Remove shimmer animation
                tempCard.classList.remove('syncing');
                
                // Add reconciled animation
                tempCard.classList.add('reconciled');
                setTimeout(() => tempCard.classList.remove('reconciled'), 500);
                
                console.log(`✅ DOM updated: ${temp_id} → ${real_id}`);
            }
            
            // 3. Broadcast to other tabs
            if (window.multiTabSync && window.multiTabSync.broadcastIDReconciled) {
                window.multiTabSync.broadcastIDReconciled(temp_id, real_id);
            }
            
            // 4. Update optimistic UI mapping
            if (window.optimisticUI && window.optimisticUI.reconcileTempID) {
                window.optimisticUI.reconcileTempID(temp_id, real_id);
            }
            
            // 5. Show success toast (subtle, not intrusive)
            if (window.showToast) {
                window.showToast(`Task synced successfully`, 'success', 2000);
            }
            
        } catch (error) {
            console.error(`❌ Failed to reconcile ${temp_id} → ${real_id}:`, error);
        }
    }

    /**
     * Handle task updated
     * @param {Object} data
     */
    async _handleTaskUpdated(data) {
        const task = data.task || data;
        console.log('📝 Task updated:', task.id);
        
        await window.taskCache.saveTask(task);
        
        if (window.optimisticUI) {
            window.optimisticUI._updateTaskInDOM(task.id, task);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskUpdated(task);
        }
    }

    /**
     * Handle task status toggled
     * @param {Object} data
     */
    async _handleTaskStatusToggled(data) {
        const task = data.task || data;
        console.log(`✅ Task status toggled: ${task.id} → ${task.status}`);
        
        await this._handleTaskUpdated(data);
        
        // Animate status change
        const card = document.querySelector(`[data-task-id="${task.id}"]`);
        if (card) {
            card.classList.add('status-changed');
            setTimeout(() => card.classList.remove('status-changed'), 500);
        }
    }

    /**
     * Handle task priority changed
     * @param {Object} data
     */
    async _handleTaskPriorityChanged(data) {
        const task = data.task || data;
        console.log(`🎯 Task priority changed: ${task.id} → ${task.priority}`);
        
        await this._handleTaskUpdated(data);
    }

    /**
     * Handle task labels updated
     * @param {Object} data
     */
    async _handleTaskLabelsUpdated(data) {
        const task = data.task || data;
        console.log('🏷️ Task labels updated:', task.id);
        
        await this._handleTaskUpdated(data);
    }

    /**
     * Handle task snoozed
     * @param {Object} data
     */
    async _handleTaskSnoozed(data) {
        const task = data.task || data;
        console.log(`⏰ Task snoozed: ${task.id} until ${task.snoozed_until}`);
        
        await this._handleTaskUpdated(data);
        
        // Optionally hide snoozed task
        const card = document.querySelector(`[data-task-id="${task.id}"]`);
        if (card) {
            card.classList.add('snoozed');
        }
    }

    /**
     * Handle tasks merged
     * @param {Object} data
     */
    async _handleTasksMerged(data) {
        console.log('🔀 Tasks merged:', data);
        
        const { primary_task, merged_task_ids } = data;
        
        // Update primary task
        await window.taskCache.saveTask(primary_task);
        
        // Remove merged tasks
        for (const taskId of merged_task_ids) {
            await window.taskCache.deleteTask(taskId);
            if (window.optimisticUI) {
                window.optimisticUI._removeTaskFromDOM(taskId);
            }
        }
        
        // Update primary task in DOM
        if (window.optimisticUI) {
            window.optimisticUI._updateTaskInDOM(primary_task.id, primary_task);
        }
    }

    /**
     * Handle transcript jump
     * @param {Object} data
     */
    _handleTranscriptJump(data) {
        console.log('🎯 Transcript jump:', data);
        
        const { task_id, transcript_span } = data;
        
        // Navigate to transcript if available
        if (transcript_span && transcript_span.start_ms !== undefined) {
            window.dispatchEvent(new CustomEvent('transcript:jump', {
                detail: {
                    task_id,
                    timestamp: transcript_span.start_ms
                }
            }));
        }
    }

    /**
     * Handle filter changed
     * @param {Object} data
     */
    async _handleFilterChanged(data) {
        console.log('🔍 Filter changed:', data.filter);
        
        await window.taskCache.setViewState('tasks_page', data.filter);
        
        if (window.taskBootstrap) {
            const tasks = await window.taskCache.getFilteredTasks(data.filter);
            await window.taskBootstrap.renderTasks(tasks);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastFilterChanged(data.filter);
        }
    }

    /**
     * Handle tasks refreshed
     * @param {Object} data
     */
    async _handleTasksRefreshed(data) {
        console.log('🔄 Tasks refreshed');
        
        if (data.tasks) {
            await window.taskCache.saveTasks(data.tasks);
            
            if (window.taskBootstrap) {
                await window.taskBootstrap.renderTasks(data.tasks);
            }
        }
    }

    /**
     * Handle idle sync complete
     * @param {Object} data
     */
    async _handleIdleSyncComplete(data) {
        console.log('💤 Idle sync complete:', data);
        
        await window.taskCache.setMetadata('last_idle_sync', Date.now());
    }

    /**
     * Handle offline queue replayed
     * @param {Object} data
     */
    async _handleOfflineQueueReplayed(data) {
        console.log('📥 Offline queue replayed:', data);
        
        const { success_count, failed_count, conflicts } = data;
        
        if (conflicts && conflicts.length > 0) {
            // Show conflict resolution UI
            this._showConflictResolution(conflicts);
        }
        
        // Refresh tasks
        if (window.taskBootstrap) {
            await window.taskBootstrap.syncInBackground();
        }
    }

    /**
     * Handle task deleted
     * @param {Object} data
     */
    async _handleTaskDeleted(data) {
        const taskId = data.task_id || data.id;
        console.log('🗑️ Task deleted:', taskId);
        
        await window.taskCache.deleteTask(taskId);
        
        if (window.optimisticUI) {
            window.optimisticUI._removeTaskFromDOM(taskId);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskDeleted(taskId);
        }
    }

    /**
     * Handle tasks bulk updated
     * @param {Object} data
     */
    async _handleTasksBulkUpdated(data) {
        console.log('📦 Tasks bulk updated:', data.task_ids.length);
        
        if (data.tasks) {
            await window.taskCache.saveTasks(data.tasks);
            
            for (const task of data.tasks) {
                if (window.optimisticUI) {
                    window.optimisticUI._updateTaskInDOM(task.id, task);
                }
            }
        }
    }

    /**
     * Handle error
     * @param {Object} data
     */
    _handleError(data) {
        console.error('❌ WebSocket error:', data);
        
        if (window.showToast) {
            window.showToast(data.message || 'An error occurred', 'error');
        }
    }

    /**
     * Update counters from server
     * @param {Object} counters
     */
    _updateCountersFromServer(counters) {
        Object.entries(counters).forEach(([key, value]) => {
            const badge = document.querySelector(`[data-counter="${key}"]`);
            if (badge) {
                badge.textContent = value;
            }
        });
    }

    /**
     * Show conflict resolution UI
     * @param {Array} conflicts
     */
    _showConflictResolution(conflicts) {
        console.log('⚠️ Conflicts detected:', conflicts);
        
        // Emit event for conflict resolution UI
        window.dispatchEvent(new CustomEvent('tasks:conflicts', {
            detail: { conflicts }
        }));
    }

    /**
     * Disconnect
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.connected = false;
        }
    }
}

// Export singleton
window.tasksWS = new TaskWebSocketHandlers();

// Auto-connect on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.tasksWS.connect();
    });
} else {
    window.tasksWS.connect();
}

console.log('🔌 CROWN⁴.5 WebSocket Handlers loaded');
