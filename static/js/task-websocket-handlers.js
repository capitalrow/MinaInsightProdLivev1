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
        
        // Phase 2 Batch 1: Core CRUD Events (use event_type.value literal strings)
        this.on('task.create.manual', this._handleTaskCreated.bind(this));
        this.on('task.create.ai_accept', this._handleTaskCreated.bind(this));
        this.on('task.update.core', this._handleTaskUpdated.bind(this));
        this.on('task.delete.soft', this._handleTaskDeleted.bind(this));
        this.on('task.restore', this._handleTaskRestored.bind(this));
        
        // 1. Bootstrap (initial data load)
        this.on('bootstrap_response', this._handleBootstrap.bind(this));
        
        // 2. Task Create (legacy)
        this.on('task_created', this._handleTaskCreated.bind(this));
        
        // 3-9. Task Update (7 variants - legacy)
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
        
        // 20. Task Delete (legacy)
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
     * CROWN⁴.5: Process event metadata (event_id, checksum, timestamp)
     * Tracks sequence numbers and stores checksum for drift detection
     * Automatically triggers reconciliation on forward gaps to maintain ordering guarantees
     * BLOCKS stale events (regressions) from being applied to cache
     * @param {Object} data - Event data with CROWN metadata
     * @returns {Promise<{shouldProcess: boolean, reason: string}>} Whether handler should proceed
     */
    async _processCROWNMetadata(data) {
        if (!data) return { shouldProcess: true, reason: 'no_metadata' };

        // Extract CROWN⁴.5 metadata
        const { event_id, checksum, timestamp, counters_checksum } = data;

        // Track event sequence and detect gaps/regressions
        if (event_id !== undefined && event_id !== null) {
            const sequenceResult = await window.taskCache.trackEventSequence(event_id);
            
            // BLOCK stale events (regressions) from being applied
            if (sequenceResult.gap_type === 'regression') {
                console.warn(`🚫 BLOCKING stale event: event_id=${event_id} < last_event_id=${sequenceResult.expected} (regression ignored)`);
                return { shouldProcess: false, reason: 'regression_blocked' };
            }
            
            // ALLOW duplicates (idempotent replay is safe)
            if (sequenceResult.gap_type === 'duplicate') {
                console.log(`✅ Allowing duplicate event_id=${event_id} (idempotent)`);
                return { shouldProcess: true, reason: 'duplicate_allowed' };
            }
            
            // FORWARD GAP: Trigger reconciliation but allow event to proceed
            if (sequenceResult.gap_detected && sequenceResult.gap_type === 'forward') {
                const gap_size = sequenceResult.gap_size || 0;
                console.warn(`⚠️ Forward gap detected (${gap_size} missing events) - triggering reconciliation`);
                
                // Trigger reconciliation for forward gaps to maintain ordering guarantees
                // For small gaps (1-5 events), trigger immediate bootstrap
                // For large gaps (>5 events), trigger full reconciliation
                if (gap_size <= 5) {
                    console.log('🔄 Small gap detected - requesting bootstrap');
                    this._emitBootstrap();
                } else {
                    console.warn('🚨 Large gap detected - requesting full reconciliation');
                    // Trigger full reconciliation via TaskBootstrap
                    if (window.taskBootstrap) {
                        await window.taskBootstrap.reconcile();
                    } else {
                        // Fallback to bootstrap if reconcile not available
                        this._emitBootstrap();
                    }
                }
                
                // Record reconciliation trigger
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordEvent('reconciliation_triggered', {
                        reason: 'forward_gap',
                        gap_size
                    });
                }
            }
        }

        // Store latest checksum for drift detection
        if (checksum) {
            await window.taskCache.setMetadata('last_checksum', checksum);
        }

        if (counters_checksum) {
            await window.taskCache.setMetadata('last_counters_checksum', counters_checksum);
        }

        if (timestamp) {
            await window.taskCache.setMetadata('last_event_timestamp', timestamp);
        }
        
        return { shouldProcess: true, reason: 'sequential' };
    }

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
        
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale bootstrap event');
            return;
        }
        
        if (data.tasks) {
            await window.taskCache.saveTasks(data.tasks);
        }
        
        if (data.view_state) {
            await window.taskCache.setViewState('tasks_page', data.view_state);
        }
        
        if (data.counters) {
            this._updateCountersFromServer(data.counters);
        }
    }

    /**
     * Handle task created
     * @param {Object} data
     */
    async _handleTaskCreated(data) {
        // CROWN⁴.5 Phase 2.1 Batch 1: Telemetry tracking
        const eventType = data.event_type || (data.data?.action === 'ai_accepted' ? 'task.create.ai_accept' : 'task.create.manual');
        if (window.crownTelemetry && eventType.startsWith('task.create')) {
            window.crownTelemetry.recordBatch1Event(eventType, 'received');
        }
        
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task_created event');
            return;
        }
        
        // CROWN⁴.5 Batch 1: Support both new events (data.data.task) and legacy (data.task)
        const task = data.data?.task || data.task || data;
        
        // Preserve CROWN⁴.5 metadata for deduplication and reconciliation
        if (data.event_id) {
            task._crown_event_id = data.event_id;
            task._crown_checksum = data.checksum;
            task._crown_sequence_num = data.sequence_num;
            task._crown_action = data.data?.action || data.action;
        }
        
        console.log('✨ Task created:', task.id, task._crown_event_id ? `(event: ${task._crown_event_id})` : '');
        
        try {
            await window.taskCache.saveTask(task);
            if (window.crownTelemetry && eventType.startsWith('task.create')) {
                window.crownTelemetry.recordBatch1Event(eventType, 'processed');
            }
        } catch (error) {
            if (window.crownTelemetry && eventType.startsWith('task.create')) {
                window.crownTelemetry.recordBatch1Event(eventType, 'error');
            }
            throw error;
        }
        
        if (window.optimisticUI) {
            window.optimisticUI._addTaskToDOM(task);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskCreated(task);
        }
    }

    /**
     * Handle task updated
     * @param {Object} data
     */
    async _handleTaskUpdated(data) {
        // CROWN⁴.5 Phase 2.1 Batch 1: Telemetry tracking
        const eventType = data.event_type || 'task.update.core';
        if (window.crownTelemetry && eventType === 'task.update.core') {
            window.crownTelemetry.recordBatch1Event(eventType, 'received');
        }
        
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task_updated event');
            return;
        }
        
        // CROWN⁴.5 Batch 1: Support both new events (data.data.task) and legacy (data.task)
        const task = data.data?.task || data.task || data;
        
        // Preserve CROWN⁴.5 metadata for deduplication and reconciliation
        if (data.event_id) {
            task._crown_event_id = data.event_id;
            task._crown_checksum = data.checksum;
            task._crown_sequence_num = data.sequence_num;
            task._crown_action = data.data?.action || data.action;
        }
        
        console.log('📝 Task updated:', task.id, task._crown_event_id ? `(event: ${task._crown_event_id})` : '');
        
        try {
            await window.taskCache.saveTask(task);
            if (window.crownTelemetry && eventType === 'task.update.core') {
                window.crownTelemetry.recordBatch1Event(eventType, 'processed');
            }
        } catch (error) {
            if (window.crownTelemetry && eventType === 'task.update.core') {
                window.crownTelemetry.recordBatch1Event(eventType, 'error');
            }
            throw error;
        }
        
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
        // Process CROWN⁴.5 metadata (check shouldProcess before any mutations)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task_status_toggled event');
            return;
        }
        
        const task = data.task || data;
        console.log(`✅ Task status toggled: ${task.id} → ${task.status}`);
        
        // Save to cache
        await window.taskCache.saveTask(task);
        
        // Update DOM
        if (window.optimisticUI) {
            window.optimisticUI._updateTaskInDOM(task.id, task);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskUpdated(task);
        }
        
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
        // Process CROWN⁴.5 metadata (check shouldProcess before any mutations)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task_priority_changed event');
            return;
        }
        
        const task = data.task || data;
        console.log(`🎯 Task priority changed: ${task.id} → ${task.priority}`);
        
        // Save to cache
        await window.taskCache.saveTask(task);
        
        // Update DOM
        if (window.optimisticUI) {
            window.optimisticUI._updateTaskInDOM(task.id, task);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskUpdated(task);
        }
    }

    /**
     * Handle task labels updated
     * @param {Object} data
     */
    async _handleTaskLabelsUpdated(data) {
        // Process CROWN⁴.5 metadata (check shouldProcess before any mutations)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task_labels_updated event');
            return;
        }
        
        const task = data.task || data;
        console.log('🏷️ Task labels updated:', task.id);
        
        // Save to cache
        await window.taskCache.saveTask(task);
        
        // Update DOM
        if (window.optimisticUI) {
            window.optimisticUI._updateTaskInDOM(task.id, task);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskUpdated(task);
        }
    }

    /**
     * Handle task snoozed
     * @param {Object} data
     */
    async _handleTaskSnoozed(data) {
        // Process CROWN⁴.5 metadata (check shouldProcess before any mutations)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task_snoozed event');
            return;
        }
        
        const task = data.task || data;
        console.log(`⏰ Task snoozed: ${task.id} until ${task.snoozed_until}`);
        
        // Save to cache
        await window.taskCache.saveTask(task);
        
        // Update DOM
        if (window.optimisticUI) {
            window.optimisticUI._updateTaskInDOM(task.id, task);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskUpdated(task);
        }
        
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
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale tasks_merged event');
            return;
        }
        
        console.log('🔀 Tasks merged:', data);
        
        const { primary_task, merged_task_ids } = data;
        
        // CROWN⁴.5 Event #13: task_merge animation (duplicate collapse + badge)
        const primaryTaskCard = document.querySelector(`[data-task-id="${primary_task.id}"]`);
        
        if (primaryTaskCard && merged_task_ids && merged_task_ids.length > 0 && window.quietStateManager) {
            // Animate merged tasks collapsing into primary task
            for (const mergedTaskId of merged_task_ids) {
                const mergedCard = document.querySelector(`[data-task-id="${mergedTaskId}"]`);
                if (mergedCard) {
                    try {
                        await window.quietStateManager.queueAnimation((setCancelHandler) => {
                            return new Promise((resolve) => {
                                const rect1 = mergedCard.getBoundingClientRect();
                                const rect2 = primaryTaskCard.getBoundingClientRect();
                                
                                const deltaX = rect2.left - rect1.left;
                                const deltaY = rect2.top - rect1.top;
                                
                                // Collapse animation: shrink and move to primary task
                                mergedCard.style.transition = 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)';
                                mergedCard.style.transform = `translate(${deltaX}px, ${deltaY}px) scale(0)`;
                                mergedCard.style.opacity = '0';
                                
                                setTimeout(() => {
                                    if (mergedCard.parentNode) {
                                        mergedCard.remove();
                                    }
                                    resolve();
                                }, 500);
                                
                                setCancelHandler(() => {
                                    if (mergedCard.parentNode) {
                                        mergedCard.remove();
                                    }
                                    resolve();
                                });
                            });
                        }, { priority: 8, type: 'task_merge', entityId: mergedTaskId });
                    } catch (error) {
                        console.error('Failed to animate merge collapse:', error);
                        if (mergedCard.parentNode) {
                            mergedCard.remove();
                        }
                    }
                }
            }
            
            // Add merge badge to primary task (awaited to respect queue)
            try {
                await window.quietStateManager.queueAnimation((setCancelHandler) => {
                    return new Promise((resolve) => {
                        const badge = document.createElement('div');
                        badge.className = 'task-merge-badge';
                        badge.textContent = `+${merged_task_ids.length} merged`;
                        badge.style.cssText = `
                            position: absolute;
                            top: 0.5rem;
                            right: 0.5rem;
                            padding: 0.25rem 0.5rem;
                            background: var(--color-primary);
                            color: white;
                            border-radius: var(--radius-full);
                            font-size: 0.75rem;
                            font-weight: 600;
                            z-index: 10;
                            opacity: 0;
                            transform: scale(0.5);
                            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                        `;
                        
                        primaryTaskCard.style.position = 'relative';
                        primaryTaskCard.appendChild(badge);
                        
                        // Animate badge in
                        setTimeout(() => {
                            badge.style.opacity = '1';
                            badge.style.transform = 'scale(1)';
                        }, 50);
                        
                        // Auto-remove badge after 3 seconds
                        setTimeout(() => {
                            badge.style.opacity = '0';
                            badge.style.transform = 'scale(0.5)';
                            setTimeout(() => {
                                if (badge.parentNode) {
                                    badge.remove();
                                }
                                resolve();
                            }, 300);
                        }, 3000);
                        
                        setCancelHandler(() => {
                            if (badge.parentNode) {
                                badge.remove();
                            }
                            resolve();
                        });
                    });
                }, { priority: 7, type: 'merge_badge', entityId: primary_task.id });
            } catch (error) {
                console.error('Failed to animate merge badge:', error);
            }
        } else if (merged_task_ids && merged_task_ids.length > 0) {
            // Fallback: Remove merged cards without animation if QuietStateManager unavailable
            for (const mergedTaskId of merged_task_ids) {
                const mergedCard = document.querySelector(`[data-task-id="${mergedTaskId}"]`);
                if (mergedCard && mergedCard.parentNode) {
                    mergedCard.remove();
                }
            }
        }
        
        // Update cache and DOM
        await window.taskCache.saveTask(primary_task);
        
        // Remove merged tasks from cache
        for (const taskId of merged_task_ids) {
            await window.taskCache.deleteTask(taskId);
        }
        
        // Update primary task in DOM
        if (window.optimisticUI) {
            window.optimisticUI._updateTaskInDOM(primary_task.id, primary_task);
        }
        
        // Record telemetry
        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('task_merge_event', 1);
            window.CROWNTelemetry.recordMetric('tasks_merged_count', merged_task_ids.length);
        }
    }

    /**
     * Handle transcript jump
     * @param {Object} data
     */
    async _handleTranscriptJump(data) {
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale transcript_jump event');
            return;
        }
        
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
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale filter_changed event');
            return;
        }
        
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
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale tasks_refreshed event');
            return;
        }
        
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
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale idle_sync_complete event');
            return;
        }
        
        console.log('💤 Idle sync complete:', data);
        
        await window.taskCache.setMetadata('last_idle_sync', Date.now());
    }

    /**
     * Handle offline queue replayed
     * @param {Object} data
     */
    async _handleOfflineQueueReplayed(data) {
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale offline_queue_replayed event');
            return;
        }
        
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
        // CROWN⁴.5 Phase 2.1 Batch 1: Telemetry tracking
        const eventType = data.event_type || 'task.delete.soft';
        if (window.crownTelemetry && eventType === 'task.delete.soft') {
            window.crownTelemetry.recordBatch1Event(eventType, 'received');
        }
        
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task_deleted event');
            return;
        }
        
        // CROWN⁴.5 Batch 1: Support both new events (data.data.task_id) and legacy (data.task_id)
        const taskId = data.data?.task_id || data.task_id || data.id;
        console.log('🗑️ Task deleted:', taskId);
        
        try {
            await window.taskCache.deleteTask(taskId);
            if (window.crownTelemetry && eventType === 'task.delete.soft') {
                window.crownTelemetry.recordBatch1Event(eventType, 'processed');
            }
        } catch (error) {
            if (window.crownTelemetry && eventType === 'task.delete.soft') {
                window.crownTelemetry.recordBatch1Event(eventType, 'error');
            }
            throw error;
        }
        
        if (window.optimisticUI) {
            window.optimisticUI._removeTaskFromDOM(taskId);
        }
        
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskDeleted(taskId);
        }
    }

    /**
     * CROWN⁴.5 Phase 2 Batch 1: Handle task restored event
     * Restores soft-deleted task (undo delete within 15s window)
     * @param {Object} data
     */
    async _handleTaskRestored(data) {
        // CROWN⁴.5 Phase 2.1 Batch 1: Telemetry tracking
        if (window.crownTelemetry) {
            window.crownTelemetry.recordBatch1Event('task.restore', 'received');
        }
        
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task.restore event');
            return;
        }
        
        const task = data.data?.task || data.task || data;
        const taskId = task.id || task.task_id;
        
        // Preserve CROWN⁴.5 metadata for deduplication and reconciliation
        if (data.event_id) {
            task._crown_event_id = data.event_id;
            task._crown_checksum = data.checksum;
            task._crown_sequence_num = data.sequence_num;
            task._crown_action = 'restored';
        }
        
        console.log('♻️ Task restored:', taskId, task._crown_event_id ? `(event: ${task._crown_event_id})` : '');
        
        try {
            // Save restored task to cache
            await window.taskCache.saveTask(task);
            if (window.crownTelemetry) {
                window.crownTelemetry.recordBatch1Event('task.restore', 'processed');
            }
        } catch (error) {
            if (window.crownTelemetry) {
                window.crownTelemetry.recordBatch1Event('task.restore', 'error');
            }
            throw error;
        }
        
        // Re-add to DOM (similar to task created)
        if (window.optimisticUI) {
            window.optimisticUI._addTaskToDOM(task);
        }
        
        // CROWN⁴.5 Multi-tab sync: Broadcast restored task to other tabs
        // Restore is equivalent to create for UI purposes
        if (window.multiTabSync) {
            window.multiTabSync.broadcastTaskCreated(task);
        }
    }

    /**
     * Handle tasks bulk updated
     * @param {Object} data
     */
    async _handleTasksBulkUpdated(data) {
        // Process CROWN⁴.5 metadata (event_id, checksum, timestamp)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale tasks_bulk_updated event');
            return;
        }
        
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
