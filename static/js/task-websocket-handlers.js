/**
 * CROWN⁴.5 WebSocket Event Handlers
 * Registers 20+ event handlers with WebSocketManager for /tasks namespace.
 * 
 * ARCHITECTURE (refactored for single-connection ownership):
 * - WebSocketManager owns the Socket.IO connection to /tasks
 * - This module exports handler functions that register via wsManager.registerHandlers()
 * - All events flow through wsManager.handleSequencedEvent() for CROWN⁴ guarantees
 */

class TaskWebSocketHandlers {
    constructor() {
        this.connected = false;
        this.namespace = 'tasks'; // No leading slash - wsManager adds it
        this.handlers = new Map();
    }

    /**
     * CROWN⁴.8: Rehydrate tasks with user data from users map (Linear pattern)
     * This ensures assignee names persist through background syncs and WebSocket updates
     * @param {Array} tasks - Array of task objects
     * @param {Object} usersMap - Map of user IDs to user objects
     * @returns {Array} Tasks with rehydrated assigned_to and assignees
     */
    _rehydrateTasksWithUsers(tasks, usersMap) {
        if (!usersMap || Object.keys(usersMap).length === 0) {
            return tasks;
        }
        
        for (const task of tasks) {
            // Rehydrate primary assigned_to
            if (task.assigned_to_id && usersMap[task.assigned_to_id]) {
                task.assigned_to = usersMap[task.assigned_to_id];
            }
            // Rehydrate assignees array for multi-assignee support
            if (task.assignee_ids && task.assignee_ids.length > 0) {
                task.assignees = task.assignee_ids
                    .map(id => usersMap[id])
                    .filter(Boolean);
            }
        }
        
        return tasks;
    }

    /**
     * Initialize by registering handlers with WebSocketManager
     * Call this AFTER wsManager.init() completes
     * @returns {void}
     */
    init() {
        if (!window.wsManager) {
            console.error('❌ WebSocketManager not available - cannot register task handlers');
            return;
        }

        // Build handler map for all CROWN⁴.5 events
        const handlers = this._buildHandlerMap();
        
        // Register with WebSocketManager (routes through handleSequencedEvent)
        window.wsManager.registerHandlers(this.namespace, handlers);
        
        // Listen for connection events from wsManager
        window.wsManager.on('connection_status', (data) => {
            if (data.namespace === this.namespace) {
                this.connected = data.connected;
                if (data.connected) {
                    console.log('✅ Tasks WebSocket connected');
                    this._emitBootstrap();
                } else {
                    console.log('📵 Tasks WebSocket disconnected');
                }
            }
        });
        
        console.log('✅ Task handlers registered with WebSocketManager');
    }

    /**
     * Build map of all event handlers (CROWN⁴.5: 20+ events)
     * @returns {Object} Map of event names to handler functions
     */
    _buildHandlerMap() {
        const handlers = {};
        
        // Phase 2 Batch 1: Core CRUD Events
        handlers['task.create.manual'] = this._handleTaskCreated.bind(this);
        handlers['task.create.ai_accept'] = this._handleTaskCreated.bind(this);
        handlers['task.update.core'] = this._handleTaskUpdated.bind(this);
        handlers['task.delete.soft'] = this._handleTaskDeleted.bind(this);
        handlers['task.restore'] = this._handleTaskRestored.bind(this);
        
        // Phase 2 Batch 2: Task Lifecycle Events
        handlers['task.priority.changed'] = this._handleBatch2PriorityChanged.bind(this);
        handlers['task.status.changed'] = this._handleBatch2StatusChanged.bind(this);
        handlers['task.assigned'] = this._handleBatch2TaskAssigned.bind(this);
        handlers['task.unassigned'] = this._handleBatch2TaskUnassigned.bind(this);
        handlers['task.due_date.changed'] = this._handleBatch2DueDateChanged.bind(this);
        handlers['task.archived'] = this._handleBatch2TaskArchived.bind(this);
        
        // 1. Bootstrap (initial data load)
        handlers['bootstrap_response'] = this._handleBootstrap.bind(this);
        
        // 2. Task Create (legacy)
        handlers['task_created'] = this._handleTaskCreated.bind(this);
        
        // 3-9. Task Update (7 variants - legacy)
        handlers['task_updated'] = this._handleTaskUpdated.bind(this);
        handlers['task_title_updated'] = this._handleTaskUpdated.bind(this);
        handlers['task_description_updated'] = this._handleTaskUpdated.bind(this);
        handlers['task_due_date_updated'] = this._handleTaskUpdated.bind(this);
        handlers['task_assignee_updated'] = this._handleTaskUpdated.bind(this);
        handlers['task_category_updated'] = this._handleTaskUpdated.bind(this);
        handlers['task_progress_updated'] = this._handleTaskUpdated.bind(this);
        
        // 10. Task Status Toggle
        handlers['task_status_toggled'] = this._handleTaskStatusToggled.bind(this);
        
        // 11. Task Priority Change
        handlers['task_priority_changed'] = this._handleTaskPriorityChanged.bind(this);
        
        // 12. Task Labels Update
        handlers['task_labels_updated'] = this._handleTaskLabelsUpdated.bind(this);
        
        // 13. Task Snooze
        handlers['task_snoozed'] = this._handleTaskSnoozed.bind(this);
        
        // 14. Task Merge
        handlers['tasks_merged'] = this._handleTasksMerged.bind(this);
        
        // 15. Transcript Jump
        handlers['transcript_jump'] = this._handleTranscriptJump.bind(this);
        
        // 16. Task Filter
        handlers['filter_changed'] = this._handleFilterChanged.bind(this);
        
        // 17. Task Refresh
        handlers['tasks_refreshed'] = this._handleTasksRefreshed.bind(this);
        
        // 18. Idle Sync
        handlers['idle_sync_complete'] = this._handleIdleSyncComplete.bind(this);
        
        // 19. Offline Queue Replay
        handlers['offline_queue_replayed'] = this._handleOfflineQueueReplayed.bind(this);
        
        // 20. Task Delete (legacy)
        handlers['task_deleted'] = this._handleTaskDeleted.bind(this);
        
        // Bulk operations
        handlers['tasks_bulk_updated'] = this._handleTasksBulkUpdated.bind(this);
        
        // Error handling
        handlers['error'] = this._handleError.bind(this);
        
        return handlers;
    }

    /**
     * Emit event to server via WebSocketManager
     * @param {string} event - Event name
     * @param {Object} data - Event data
     */
    emit(event, data) {
        if (!window.wsManager) {
            console.warn(`⚠️ Cannot emit ${event} - WebSocketManager not available`);
            return;
        }
        
        window.wsManager.send(this.namespace, event, data);
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
            // CROWN⁴.8: Rehydrate assignees from users map before caching
            const rehydratedTasks = this._rehydrateTasksWithUsers(data.tasks, data.users || {});
            await window.taskCache.saveTasks(rehydratedTasks);
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
        
        // TASK 5: Event deduplication - check before processing
        if (window.taskEventDeduplicator) {
            const { isNew } = window.taskEventDeduplicator.checkAndMark('task_created', data, 'websocket');
            if (!isNew) {
                console.log('⏭️ [WebSocket] Skipping duplicate task_created event');
                return;
            }
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
            // TASK 5: Pass event metadata for deduplication
            window.multiTabSync.broadcastTaskCreated(task, { event_id: data.event_id });
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
        
        // TASK 5: Event deduplication - check before processing
        if (window.taskEventDeduplicator) {
            const { isNew } = window.taskEventDeduplicator.checkAndMark('task_updated', data, 'websocket');
            if (!isNew) {
                console.log('⏭️ [WebSocket] Skipping duplicate task_updated event');
                return;
            }
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
            // TASK 5: Pass event metadata for deduplication
            window.multiTabSync.broadcastTaskUpdated(task, { event_id: data.event_id });
        }
    }

    /**
     * Handle task status toggled
     * @param {Object} data
     */
    async _handleTaskStatusToggled(data) {
        // TASK 5: Event deduplication - check before processing
        if (window.taskEventDeduplicator) {
            const { isNew } = window.taskEventDeduplicator.checkAndMark('task_status_toggled', data, 'websocket');
            if (!isNew) {
                console.log('⏭️ [WebSocket] Skipping duplicate task_status_toggled event');
                return;
            }
        }
        
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
            // TASK 5: Pass event metadata for deduplication
            window.multiTabSync.broadcastTaskUpdated(task, { event_id: data.event_id });
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
        // TASK 5: Event deduplication - check before processing
        if (window.taskEventDeduplicator) {
            const { isNew } = window.taskEventDeduplicator.checkAndMark('task_priority_changed', data, 'websocket');
            if (!isNew) {
                console.log('⏭️ [WebSocket] Skipping duplicate task_priority_changed event');
                return;
            }
        }
        
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
            // TASK 5: Pass event metadata for deduplication
            window.multiTabSync.broadcastTaskUpdated(task, { event_id: data.event_id });
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
     * CROWN⁴.9: Check if hydration is ready
     * @returns {boolean}
     */
    _isHydrationReady() {
        return window.taskHydrationReady || 
               (window.taskBootstrap?.isHydrationReady?.() ?? false);
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
        
        // CROWN⁴.9: Block filter operations until hydration is complete
        if (!this._isHydrationReady()) {
            console.log('[WebSocketHandlers] _handleFilterChanged blocked - hydration not ready');
            return;
        }
        
        console.log('🔍 Filter changed:', data.filter);
        
        await window.taskCache.setViewState('tasks_page', data.filter);
        
        if (window.taskBootstrap) {
            const tasks = await window.taskCache.getFilteredTasks(data.filter);
            
            // CROWN⁴.9 FIX: Prevent render loop during initial bootstrap
            // Skip render if cache is empty but server already rendered tasks
            const container = document.getElementById('tasks-list-container');
            const serverRenderedCards = container?.querySelectorAll('.task-card')?.length || 0;
            if ((!tasks || tasks.length === 0) && serverRenderedCards > 0) {
                console.log(`[WebSocketHandlers] Skipping filter render - cache empty but ${serverRenderedCards} server cards exist`);
            } else {
                // CROWN⁴.12: Pass WebSocket metadata - lowest priority
                const sortConfig = window.taskBootstrap._getCurrentViewContext?.()?.sort || { field: 'created_at', direction: 'desc' };
                await window.taskBootstrap.renderTasks(tasks, {
                    source: 'websocket',
                    filterContext: data.filter?.filter || data.filter?.status || 'active',
                    searchQuery: data.filter?.search || '',
                    sortConfig: sortConfig
                });
            }
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
            // CROWN⁴.8: Rehydrate assignees from users map before caching
            const rehydratedTasks = this._rehydrateTasksWithUsers(data.tasks, data.users || {});
            await window.taskCache.saveTasks(rehydratedTasks);
            
            if (window.taskBootstrap) {
                // CROWN⁴.12: Pass WebSocket metadata - lowest priority with full context
                const ctx = window.taskBootstrap._getCurrentViewContext?.() || { filter: 'active', search: '', sort: { field: 'created_at', direction: 'desc' } };
                await window.taskBootstrap.renderTasks(rehydratedTasks, {
                    source: 'websocket',
                    fromCache: false,
                    filterContext: ctx.filter,
                    searchQuery: ctx.search,
                    sortConfig: ctx.sort
                });
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
        
        // TASK 5: Event deduplication - check before processing
        if (window.taskEventDeduplicator) {
            const { isNew } = window.taskEventDeduplicator.checkAndMark('task_deleted', data, 'websocket');
            if (!isNew) {
                console.log('⏭️ [WebSocket] Skipping duplicate task_deleted event');
                return;
            }
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
            // TASK 5: Pass event metadata for deduplication
            window.multiTabSync.broadcastTaskDeleted(taskId, { event_id: data.event_id });
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
     * CROWN⁴.5 Phase 2.2 Batch 2: Shared lifecycle update helper
     * Unified logic for applying lifecycle changes (priority, status, assignment, due date, archive)
     * Used by both new Batch 2 events and legacy events for consistency
     * 
     * @param {Object} task - Updated task object (single source of truth)
     * @param {string} eventType - Event type (e.g., 'task.priority.changed')
     * @param {any} oldValue - Previous value (for logging/diagnostics)
     * @param {any} newValue - New value (for logging/diagnostics)
     * @param {Object} crownMetadata - CROWN event metadata (event_id, checksum, etc.)
     */
    async _applyLifecycleUpdate(task, eventType, oldValue, newValue, crownMetadata = {}) {
        // Preserve CROWN⁴.5 metadata for deduplication and reconciliation
        if (crownMetadata.event_id) {
            task._crown_event_id = crownMetadata.event_id;
            task._crown_checksum = crownMetadata.checksum;
            task._crown_sequence_num = crownMetadata.sequence_num;
            task._crown_action = crownMetadata.action;
        }
        
        // Log lifecycle change with old/new values for diagnostics
        const changeLog = oldValue !== undefined && newValue !== undefined 
            ? `${oldValue} → ${newValue}` 
            : '';
        console.log(`🔄 ${eventType}: task ${task.id} ${changeLog}`);
        
        try {
            // Save to IndexedDB cache (single source of truth)
            await window.taskCache.saveTask(task);
            
            // Update DOM (full card update, optimized internally)
            if (window.optimisticUI) {
                window.optimisticUI._updateTaskInDOM(task.id, task);
            }
            
            // Multi-tab sync
            if (window.multiTabSync) {
                window.multiTabSync.broadcastTaskUpdated(task);
            }
            
            return { success: true };
        } catch (error) {
            console.error(`❌ Failed to apply lifecycle update for ${eventType}:`, error);
            return { success: false, error };
        }
    }

    /**
     * CROWN⁴.5 Phase 2.2 Batch 2: Handle task.priority.changed event
     * @param {Object} data - Event payload {event_id, data: {task, old_value, new_value, ...}}
     */
    async _handleBatch2PriorityChanged(data) {
        // Record telemetry (received)
        if (window.crownTelemetry) {
            window.crownTelemetry.recordBatch2Event('task.priority.changed', 'received');
        }
        
        // Process CROWN⁴.5 metadata (regression check)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task.priority.changed event');
            return;
        }
        
        // Extract task and old/new values from dual payload
        const task = data.data?.task || data.task || data;
        const oldValue = data.data?.old_value;
        const newValue = data.data?.new_value;
        
        try {
            // Apply lifecycle update via shared helper
            const result = await this._applyLifecycleUpdate(task, 'task.priority.changed', oldValue, newValue, {
                event_id: data.event_id,
                checksum: data.checksum,
                sequence_num: data.sequence_num,
                action: 'priority_changed'
            });
            
            // Record telemetry (processed or error)
            if (window.crownTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.priority.changed', result.success ? 'processed' : 'error');
            }
        } catch (error) {
            if (window.crownTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.priority.changed', 'error');
            }
            throw error;
        }
    }

    /**
     * CROWN⁴.5 Phase 2.2 Batch 2: Handle task.status.changed event
     * @param {Object} data - Event payload {event_id, data: {task, old_value, new_value, old_completed_at, new_completed_at, ...}}
     */
    async _handleBatch2StatusChanged(data) {
        // Record telemetry (received)
        if (window.crownTelemetry) {
            window.crownTelemetry.recordBatch2Event('task.status.changed', 'received');
        }
        
        // Process CROWN⁴.5 metadata (regression check)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task.status.changed event');
            return;
        }
        
        // Extract task and old/new values
        const task = data.data?.task || data.task || data;
        const oldValue = data.data?.old_value;
        const newValue = data.data?.new_value;
        
        try {
            // Apply lifecycle update
            const result = await this._applyLifecycleUpdate(task, 'task.status.changed', oldValue, newValue, {
                event_id: data.event_id,
                checksum: data.checksum,
                sequence_num: data.sequence_num,
                action: 'status_changed'
            });
            
            // Animate status change (visual feedback)
            const card = document.querySelector(`[data-task-id="${task.id}"]`);
            if (card) {
                card.classList.add('status-changed');
                setTimeout(() => card.classList.remove('status-changed'), 500);
            }
            
            // Record telemetry
            if (window.crownTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.status.changed', result.success ? 'processed' : 'error');
            }
        } catch (error) {
            if (window.crownTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.status.changed', 'error');
            }
            throw error;
        }
    }

    /**
     * CROWN⁴.5 Phase 2.2 Batch 2: Handle task.assigned event
     * @param {Object} data - Event payload {event_id, data: {task, new_value (user_id), ...}}
     */
    async _handleBatch2TaskAssigned(data) {
        // Record telemetry (received)
        if (window.crownTelemetry) {
            window.crownTelemetry.recordBatch2Event('task.assigned', 'received');
        }
        
        // Process CROWN⁴.5 metadata (regression check)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task.assigned event');
            return;
        }
        
        // Extract task and assigned user
        const task = data.data?.task || data.task || data;
        const assignedUserId = data.data?.new_value;
        
        try {
            // Apply lifecycle update
            const result = await this._applyLifecycleUpdate(task, 'task.assigned', null, assignedUserId, {
                event_id: data.event_id,
                checksum: data.checksum,
                sequence_num: data.sequence_num,
                action: 'assigned'
            });
            
            // Record telemetry
            if (window.crownTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.assigned', result.success ? 'processed' : 'error');
            }
        } catch (error) {
            if (window.crownTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.assigned', 'error');
            }
            throw error;
        }
    }

    /**
     * CROWN⁴.5 Phase 2.2 Batch 2: Handle task.unassigned event
     * @param {Object} data - Event payload {event_id, data: {task, old_value (user_id), ...}}
     */
    async _handleBatch2TaskUnassigned(data) {
        // Record telemetry (received)
        if (window.CROWNTelemetry) {
            window.crownTelemetry.recordBatch2Event('task.unassigned', 'received');
        }
        
        // Process CROWN⁴.5 metadata (regression check)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task.unassigned event');
            return;
        }
        
        // Extract task and unassigned user
        const task = data.data?.task || data.task || data;
        const unassignedUserId = data.data?.old_value;
        
        try {
            // Apply lifecycle update
            const result = await this._applyLifecycleUpdate(task, 'task.unassigned', unassignedUserId, null, {
                event_id: data.event_id,
                checksum: data.checksum,
                sequence_num: data.sequence_num,
                action: 'unassigned'
            });
            
            // Record telemetry
            if (window.CROWNTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.unassigned', result.success ? 'processed' : 'error');
            }
        } catch (error) {
            if (window.CROWNTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.unassigned', 'error');
            }
            throw error;
        }
    }

    /**
     * CROWN⁴.5 Phase 2.2 Batch 2: Handle task.due_date.changed event
     * @param {Object} data - Event payload {event_id, data: {task, old_value, new_value, ...}}
     */
    async _handleBatch2DueDateChanged(data) {
        // Record telemetry (received)
        if (window.CROWNTelemetry) {
            window.crownTelemetry.recordBatch2Event('task.due_date.changed', 'received');
        }
        
        // Process CROWN⁴.5 metadata (regression check)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task.due_date.changed event');
            return;
        }
        
        // Extract task and old/new due dates
        const task = data.data?.task || data.task || data;
        const oldValue = data.data?.old_value;
        const newValue = data.data?.new_value;
        
        try {
            // Apply lifecycle update
            const result = await this._applyLifecycleUpdate(task, 'task.due_date.changed', oldValue, newValue, {
                event_id: data.event_id,
                checksum: data.checksum,
                sequence_num: data.sequence_num,
                action: 'due_date_changed'
            });
            
            // Record telemetry
            if (window.CROWNTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.due_date.changed', result.success ? 'processed' : 'error');
            }
        } catch (error) {
            if (window.CROWNTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.due_date.changed', 'error');
            }
            throw error;
        }
    }

    /**
     * CROWN⁴.5 Phase 2.2 Batch 2: Handle task.archived event
     * @param {Object} data - Event payload {event_id, data: {task, ...}}
     */
    async _handleBatch2TaskArchived(data) {
        // Record telemetry (received)
        if (window.CROWNTelemetry) {
            window.crownTelemetry.recordBatch2Event('task.archived', 'received');
        }
        
        // Process CROWN⁴.5 metadata (regression check)
        const { shouldProcess } = await this._processCROWNMetadata(data);
        if (!shouldProcess) {
            console.log('⏭️ Skipping stale task.archived event');
            return;
        }
        
        // Extract task
        const task = data.data?.task || data.task || data;
        const taskId = task.id || task.task_id;
        
        try {
            // Archive is like soft delete but preserves metadata
            // Remove from active cache but trigger bootstrap for fresh state
            await window.taskCache.deleteTask(taskId);
            
            // Remove from DOM
            if (window.optimisticUI) {
                window.optimisticUI._removeTaskFromDOM(taskId);
            }
            
            // Multi-tab sync
            if (window.multiTabSync) {
                window.multiTabSync.broadcastTaskDeleted(taskId);
            }
            
            // Trigger bootstrap to refresh active task list
            if (window.taskBootstrap) {
                await window.taskBootstrap.syncInBackground();
            }
            
            console.log(`🗃️ Task archived: ${taskId}`);
            
            // Record telemetry (processed)
            if (window.CROWNTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.archived', 'processed');
            }
        } catch (error) {
            if (window.CROWNTelemetry) {
                window.crownTelemetry.recordBatch2Event('task.archived', 'error');
            }
            throw error;
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
            // CROWN⁴.8: Rehydrate assignees from users map before caching
            const rehydratedTasks = this._rehydrateTasksWithUsers(data.tasks, data.users || {});
            await window.taskCache.saveTasks(rehydratedTasks);
            
            for (const task of rehydratedTasks) {
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
     * CROWN⁴.6 FIX: Respect TaskStateStore's initial load state to prevent flickering
     * @param {Object} counters
     */
    _updateCountersFromServer(counters) {
        // CRITICAL: Delegate to TaskStateStore if available - single source of truth pattern
        // This respects the _initialLoadComplete guard to prevent counter flickering
        if (window.taskStateStore && !window.taskStateStore._initialLoadComplete) {
            console.log('[WebSocket] Skipping counter update during initial load stabilization');
            return;
        }
        
        Object.entries(counters).forEach(([key, value]) => {
            const badge = document.querySelector(`[data-counter="${key}"]`);
            if (badge) {
                const currentValue = parseInt(badge.textContent) || 0;
                if (currentValue !== value) {
                    badge.textContent = value;
                    
                    // Subtle animation on change (emotional UX)
                    badge.classList.remove('counter-updated');
                    void badge.offsetWidth; // Force reflow
                    badge.classList.add('counter-updated');
                }
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
     * Disconnect (no-op since wsManager owns the connection)
     */
    disconnect() {
        console.log('ℹ️ Disconnect called - WebSocketManager owns connection lifecycle');
        this.connected = false;
    }
}

// Export singleton (initialization happens in tasks.html after wsManager.init)
window.tasksWS = new TaskWebSocketHandlers();

console.log('🔌 CROWN⁴.5 WebSocket Handlers loaded (awaiting init() call)');
