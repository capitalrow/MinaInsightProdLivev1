/**
 * CROWN⁴.5 Optimistic UI Update System
 * Applies changes instantly to DOM, queues to IndexedDB, syncs to server.
 * Provides <150ms reconciliation on success, rollback on failure.
 */

class OptimisticUI {
    constructor() {
        this.cache = window.taskCache;
        this.pendingOperations = new Map();
        this.operationCounter = 0;
        this.rehydrationComplete = false;
        this._setupReconnectHandler();
    }
    
    /**
     * ENTERPRISE-GRADE: Rehydrate pending operations from IndexedDB on page load
     * Restores ALL operation types (create/update/delete) from offline_queue
     * CRITICAL FIX: Filters out stale operations older than 2 minutes
     * This ensures retry mechanism works after page refresh
     */
    async rehydratePendingOperations() {
        if (this.rehydrationComplete) {
            console.log('✅ [Offline-First] Rehydration already complete');
            return;
        }
        
        try {
            console.log('🔄 [Offline-First] Rehydrating pending operations from IndexedDB offline_queue...');
            
            // Get all pending operations from offline_queue (supports create/update/delete)
            const operations = await this.cache.getAllPendingOperations();
            
            // CRITICAL FIX: Filter out stale operations before adding to memory
            // Stale operations (older than 2 minutes) likely already succeeded on server
            const now = Date.now();
            const STALE_THRESHOLD_MS = 2 * 60 * 1000; // 2 minutes
            const freshOperations = new Map();
            const staleOpIds = [];
            
            for (const [opId, op] of operations.entries()) {
                const opTime = op.timestamp ? new Date(op.timestamp).getTime() : 0;
                const opAge = now - opTime;
                
                // Filter out stale create operations (likely already succeeded)
                if (op.type === 'create' && opAge > STALE_THRESHOLD_MS) {
                    console.log(`🧹 [Rehydrate] Skipping stale operation: ${opId} (age: ${Math.round(opAge/1000)}s)`);
                    staleOpIds.push(opId);
                } else {
                    freshOperations.set(opId, op);
                }
            }
            
            // Restore only fresh operations to in-memory map
            this.pendingOperations = freshOperations;
            
            console.log(`✅ [Offline-First] Rehydration complete: ${freshOperations.size} fresh operations (${staleOpIds.length} stale filtered)`);
            
            // Log breakdown by type
            const breakdown = { create: 0, update: 0, delete: 0, failed: 0, skipped: staleOpIds.length };
            for (const [opId, op] of freshOperations.entries()) {
                breakdown[op.type] = (breakdown[op.type] || 0) + 1;
                if (op.failed) breakdown.failed++;
                
                console.log(`  → ${opId}: ${op.type} (${op.failed ? 'FAILED' : 'pending'}, retries: ${op.retryCount || 0})`);
            }
            console.log(`📊 [Offline-First] Operations by type:`, breakdown);
            
            this.rehydrationComplete = true;
            
            // Auto-retry pending (non-failed) operations if online
            if (window.wsManager && window.wsManager.getConnectionStatus('/tasks')) {
                const pendingOps = Array.from(this.pendingOperations.entries())
                    .filter(([_, op]) => !op.failed);
                
                if (pendingOps.length > 0) {
                    console.log(`🔄 [Offline-First] Auto-retrying ${pendingOps.length} pending operations...`);
                    for (const [opId, _] of pendingOps) {
                        await this._retryOperation(opId);
                    }
                }
            }
            
        } catch (error) {
            console.error('❌ [Offline-First] Failed to rehydrate pending operations:', error);
        }
    }

    /**
     * Setup WebSocket reconnect handler to retry pending operations
     */
    _setupReconnectHandler() {
        if (!window.wsManager) {
            console.warn('⚠️ WebSocketManager not available for reconnect handling');
            return;
        }

        // Listen for connection status changes
        window.wsManager.on('connection_status', (data) => {
            if (data.namespace === '/tasks') {
                if (data.connected) {
                    console.log('🔄 WebSocket reconnected, retrying pending operations...');
                    this._showConnectionBanner('online', 'Connected', 2000);
                    this._retryPendingOperations();
                } else {
                    this._showConnectionBanner('offline', 'Offline - changes will sync when reconnected');
                }
            }
        });
        
        window.wsManager.on('reconnecting', (data) => {
            if (data.namespace === '/tasks') {
                this._showConnectionBanner('reconnecting', 'Reconnecting...');
            }
        });
    }
    
    _showConnectionBanner(status, message, autohideDuration = 0) {
        const banner = document.getElementById('connection-banner');
        if (!banner) return;
        
        banner.className = `connection-banner ${status}`;
        banner.querySelector('.connection-message').textContent = message;
        
        const pendingCount = this.pendingOperations.size;
        const pendingEl = banner.querySelector('.pending-count');
        if (pendingCount > 0) {
            pendingEl.textContent = `(${pendingCount} pending)`;
            pendingEl.style.display = 'inline';
        } else {
            pendingEl.style.display = 'none';
        }
        
        banner.style.display = 'flex';
        
        if (autohideDuration > 0) {
            setTimeout(() => {
                banner.style.display = 'none';
            }, autohideDuration);
        }
    }

    /**
     * Retry pending operations after WebSocket reconnect
     */
    async _retryPendingOperations() {
        if (this.pendingOperations.size === 0) {
            console.log('✅ No pending operations to retry');
            return;
        }

        console.log(`🔄 Retrying ${this.pendingOperations.size} pending operations...`);
        const operations = Array.from(this.pendingOperations.entries());

        for (const [opId, operation] of operations) {
            try {
                console.log(`🔄 Retrying operation ${opId} (${operation.type})`);
                
                if (operation.type === 'create') {
                    // Use clean original data, not optimistic version
                    await this._syncToServer(opId, 'create', operation.data, operation.tempId);
                } else if (operation.type === 'update') {
                    // Use clean updates data
                    await this._syncToServer(opId, 'update', operation.data, operation.taskId);
                } else if (operation.type === 'delete') {
                    await this._syncToServer(opId, 'delete', {}, operation.taskId);
                }
            } catch (error) {
                console.error(`❌ Retry failed for operation ${opId}:`, error);
            }
        }
    }

    /**
     * Retry a single operation
     * ENTERPRISE-GRADE: Clears failed flag and re-attempts sync
     */
    async _retryOperation(opId) {
        const operation = this.pendingOperations.get(opId);
        if (!operation) {
            console.warn(`⚠️ Operation ${opId} not found for retry`);
            return;
        }

        console.log(`🔄 [Offline-First] Retrying operation ${opId} (${operation.type}, attempt #${(operation.retryCount || 0) + 1})`);
        
        // Clear failed flag for retry
        operation.failed = false;
        
        try {
            if (operation.type === 'create') {
                // Update temp task status back to pending before retry
                if (this.cache && operation.tempId) {
                    await this.cache.updateTempTaskStatus(operation.tempId, 'pending');
                    
                    // Refresh UI to show "Syncing" badge instead of "Failed"
                    const taskCard = document.querySelector(`[data-task-id="${operation.tempId}"]`);
                    if (taskCard) {
                        const syncBadge = taskCard.querySelector('.sync-status-badge');
                        if (syncBadge) {
                            syncBadge.className = 'sync-status-badge syncing';
                            syncBadge.innerHTML = '<span class="badge-icon spin-animation">⟳</span> Syncing';
                        }
                    }
                }
                await this._syncToServer(opId, 'create', operation.data, operation.tempId);
            } else if (operation.type === 'update') {
                await this._syncToServer(opId, 'update', operation.data, operation.taskId);
            } else if (operation.type === 'delete') {
                await this._syncToServer(opId, 'delete', {}, operation.taskId);
            }
            
            if (window.toast) {
                window.toast.success('Changes saved successfully');
            }
        } catch (error) {
            console.error(`❌ [Offline-First] Retry failed for operation ${opId}:`, error);
            // Operation will be marked as failed again by _reconcileFailure
        }
    }

    /**
     * Create task optimistically
     * ENTERPRISE-GRADE: Waits for cache initialization to prevent race conditions
     * @param {Object} taskData
     * @returns {Promise<Object>} Created task
     */
    async createTask(taskData) {
        console.log('🔥 [OptimisticUI] createTask called with:', taskData);
        // ENTERPRISE-GRADE: Wait for cache to be ready (prevents init race conditions)
        if (window.cacheManagerReady) {
            console.log('⏳ [Offline-First] Waiting for cacheManager to initialize...');
            try {
                await window.cacheManagerReady;
                console.log('✅ [Offline-First] cacheManager ready, proceeding with task creation');
            } catch (error) {
                console.error('❌ [Offline-First] cacheManager initialization failed:', error);
                throw new Error('Cache not available - please refresh the page');
            }
        }
        
        const opId = this._generateOperationId();
        const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        const optimisticTask = {
            id: tempId,
            ...taskData,
            status: taskData.status || 'todo',
            priority: taskData.priority || 'medium',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            _optimistic: true,
            operation_id: opId  // Store for retry after refresh
        };

        try {
            // Step 1: Update DOM immediately (<50ms)
            this._addTaskToDOM(optimisticTask);
            
            // Step 2: Save to IndexedDB (now guaranteed to be initialized)
            await this.cache.saveTask(optimisticTask);
            console.log(`✅ [Offline-First] Temp task ${tempId} saved to IndexedDB`);
            
            // Dispatch creation event for haptics/animations
            window.dispatchEvent(new CustomEvent('task:created', {
                detail: { taskId: tempId, task: optimisticTask }
            }));
            
            // CROWN⁴.15: Update TaskStateStore for counter synchronization
            // Temp tasks tracked separately - pass isTemp=true
            window.taskStateStore?.upsertTask(optimisticTask, true);
            
            // Step 3: Queue event and offline operation via OfflineQueueManager
            await this.cache.addEvent({
                event_type: 'task_create',
                task_id: tempId,
                data: taskData,
                timestamp: Date.now()
            });

            // Use OfflineQueueManager for proper session tracking and replay
            let queueId = null;
            if (window.offlineQueue) {
                queueId = await window.offlineQueue.queueOperation({
                    type: 'task_create',
                    temp_id: tempId,
                    data: taskData,
                    priority: 10,
                    operation_id: opId  // Link queue entry to operation
                });
            }

            // Step 4: Sync to server
            // Store ORIGINAL clean data (not optimistic version) for retry
            const operation = { 
                type: 'create', 
                tempId, 
                task: optimisticTask,  // Keep for rollback
                data: taskData,  // Original clean data for retry
                queueId,  // Store queue ID to remove on success
                timestamp: Date.now()
            };
            this.pendingOperations.set(opId, operation);
            
            // ENTERPRISE-GRADE: Persist to IndexedDB for rehydration after refresh
            await this.cache.savePendingOperation(opId, operation).catch(err => {
                console.error('❌ Failed to persist pending operation:', err);
            });
            
            console.log('🔥 [OptimisticUI] About to call _syncToServer for create operation');
            this._syncToServer(opId, 'create', taskData, tempId);

            return optimisticTask;
        } catch (error) {
            console.error('❌ [Offline-First] Optimistic create failed:', error);
            this._rollbackCreate(tempId, error);
            throw error;
        }
    }

    /**
     * Update task optimistically
     * CROWN⁴.13: Acquires action lock to prevent sync overwrites
     * @param {number|string} taskId
     * @param {Object} updates
     * @returns {Promise<Object>} Updated task
     */
    async updateTask(taskId, updates) {
        console.log(`\n📥 [UpdateTask] START - Task ${taskId}`, updates);
        const opId = this._generateOperationId();
        console.log(`🔑 [UpdateTask] Generated operation ID: ${opId}`);
        
        // CROWN⁴.13: Acquire action lock to prevent sync overwrites
        let lockId = null;
        if (window.taskActionLock) {
            lockId = window.taskActionLock.acquire(taskId, `update:${Object.keys(updates).join(',')}`);
            console.log(`🔒 [UpdateTask] Lock acquired: ${lockId}`);
        } else {
            console.warn(`⚠️ [UpdateTask] taskActionLock not available - sync protection disabled!`);
        }
        
        try {
            // Get current task
            const currentTask = await this.cache.getTask(taskId);
            if (!currentTask) {
                console.error(`❌ [UpdateTask] Task ${taskId} not found in cache`);
                if (lockId) window.taskActionLock.release(lockId);
                throw new Error('Task not found');
            }
            console.log(`📋 [UpdateTask] Current task state:`, { id: currentTask.id, status: currentTask.status });

            // Create optimistic version
            const optimisticTask = {
                ...currentTask,
                ...updates,
                updated_at: new Date().toISOString(),
                _optimistic: true,
                _operation_id: opId
            };

            // Step 1: Update DOM immediately
            this._updateTaskInDOM(taskId, optimisticTask);
            console.log(`✅ [UpdateTask] Step 1 complete: DOM updated`);
            
            // Step 2: Update IndexedDB
            try {
                await this.cache.saveTask(optimisticTask);
                console.log(`✅ [UpdateTask] Step 2 complete: Task saved to IndexedDB`);
            } catch (cacheError) {
                console.error(`❌ [UpdateTask] Step 2 FAILED (saveTask):`, cacheError?.name, cacheError?.message, cacheError);
                throw cacheError;
            }
            
            // Dispatch update event for haptics/animations
            window.dispatchEvent(new CustomEvent('task:updated', {
                detail: { taskId, updates, task: optimisticTask }
            }));
            
            // CROWN⁴.15: Update TaskStateStore for counter synchronization
            // This handles status changes (active<->archived) and completion
            window.taskStateStore?.upsertTask(optimisticTask);
            
            // Step 3: Queue event via OfflineQueueManager
            try {
                await this.cache.addEvent({
                    event_type: 'task_update',
                    task_id: taskId,
                    data: updates,
                    timestamp: Date.now()
                });
                console.log(`✅ [UpdateTask] Step 3 complete: Event added to ledger`);
            } catch (eventError) {
                console.error(`❌ [UpdateTask] Step 3 FAILED (addEvent):`, eventError?.name, eventError?.message, eventError);
                throw eventError;
            }

            // Use OfflineQueueManager for proper session tracking and replay
            let queueId = null;
            if (window.offlineQueue) {
                try {
                    queueId = await window.offlineQueue.queueOperation({
                        type: 'task_update',
                        task_id: taskId,
                        data: updates,
                        priority: 5,
                        operation_id: opId  // Link queue entry to operation
                    });
                    console.log(`✅ [UpdateTask] Step 3b complete: Operation queued (queueId: ${queueId})`);
                } catch (queueError) {
                    console.error(`❌ [UpdateTask] Step 3b FAILED (queueOperation):`, queueError?.name, queueError?.message, queueError);
                    throw queueError;
                }
            }

            // Step 4: Sync to server
            // Store clean updates data for retry
            const operation = { 
                type: 'update', 
                taskId, 
                previous: currentTask,  // Keep for rollback
                updates,  // Clean updates data for retry
                data: updates,  // Explicit clean data reference
                queueId,  // Store queue ID to remove on success
                timestamp: Date.now(),
                lockId  // CROWN⁴.13: Store lock ID for release on completion
            };
            this.pendingOperations.set(opId, operation);
            
            // ENTERPRISE-GRADE: Persist to IndexedDB for rehydration after refresh
            await this.cache.savePendingOperation(opId, operation).catch(err => {
                console.error('❌ Failed to persist pending operation:', err?.name, err?.message, err);
            });
            console.log(`✅ [UpdateTask] Step 4 complete: Pending operation saved`);
            
            console.log(`📤 [UpdateTask] Calling _syncToServer() for task ${taskId}...`);
            this._syncToServer(opId, 'update', updates, taskId);
            console.log(`📨 [UpdateTask] _syncToServer() initiated (async) - returning optimistic task`);

            return optimisticTask;
        } catch (error) {
            // Properly serialize error for debugging (IndexedDB errors don't stringify well)
            const errorInfo = {
                name: error?.name || 'Unknown',
                message: error?.message || String(error),
                stack: error?.stack?.split('\n').slice(0, 3).join('\n')
            };
            console.error('❌ [UpdateTask] FAILED:', errorInfo.name, '-', errorInfo.message);
            console.error('❌ [UpdateTask] Stack:', errorInfo.stack);
            // CROWN⁴.13: Release lock on error
            if (lockId && window.taskActionLock) {
                window.taskActionLock.release(lockId);
                console.log(`🔓 [UpdateTask] Lock ${lockId} released after error`);
            }
            throw error;
        }
    }

    /**
     * Delete task optimistically (soft delete with 15s undo window)
     * CROWN⁴.5: Soft delete to support undo functionality
     * @param {number|string} taskId
     * @returns {Promise<void>}
     */
    async deleteTask(taskId) {
        const opId = this._generateOperationId();
        
        try {
            // Get task for rollback
            const task = await this.cache.getTask(taskId);
            if (!task) {
                throw new Error('Task not found');
            }

            // IDEMPOTENT: Early return if already deleted (prevents error on stale cache)
            if (task.deleted_at) {
                console.log(`⚠️ Task ${taskId} already deleted, skipping (idempotent operation)`);
                return { success: true, action: 'noop', message: 'Task already deleted' };
            }

            // Step 1: Soft delete - mark as deleted but keep in cache for undo
            const updates = {
                deleted_at: new Date().toISOString(),
                deleted_by_user_id: window.CURRENT_USER_ID || null
            };

            // Update task in cache with deleted_at
            const updatedTask = { ...task, ...updates };
            await this.cache.updateTask(taskId, updatedTask);
            
            // Step 2: Dispatch deletion event for animations FIRST
            // TaskAnimationController will handle DOM removal in animation's onComplete
            window.dispatchEvent(new CustomEvent('task:deleted', {
                detail: { taskId, task: updatedTask }
            }));
            
            // CROWN⁴.15: Update TaskStateStore for counter synchronization
            // Remove from store so counters update immediately
            window.taskStateStore?.removeTask(taskId);
            
            // Step 3: Queue event via OfflineQueueManager
            await this.cache.addEvent({
                event_type: 'task_delete',
                task_id: taskId,
                timestamp: Date.now(),
                data: updates
            });

            // Use OfflineQueueManager for proper session tracking and replay
            let queueId = null;
            if (window.offlineQueue) {
                queueId = await window.offlineQueue.queueOperation({
                    type: 'task_update',  // Use update, not delete
                    task_id: taskId,
                    data: updates,
                    priority: 8,
                    operation_id: opId
                });
            }

            // Step 4: Sync to server (as update with deleted_at, not hard delete)
            const operation = { 
                type: 'update',  // Changed from 'delete' 
                taskId, 
                previous: task,  // Keep for rollback
                updates,
                data: updates,
                queueId,
                timestamp: Date.now()
            };
            this.pendingOperations.set(opId, operation);
            
            // ENTERPRISE-GRADE: Persist to IndexedDB for rehydration after refresh
            await this.cache.savePendingOperation(opId, operation).catch(err => {
                console.error('❌ Failed to persist pending operation:', err);
            });
            
            this._syncToServer(opId, 'update', updates, taskId);

            // CACHE HYGIENE: Task already marked with deleted_at in cache (line 307)
            // Prevention filters will hide it on page refresh while preserving undo capability
            console.log(`✅ Task ${taskId} soft-deleted in cache (preserved for 15s undo window)`);

            // CROWN⁴.6: Show undo toast for single task deletion
            if (window.toastManager) {
                window.toastManager.show({
                    message: `Deleted "${task.title}"`,
                    type: 'warning',
                    duration: 15000,
                    action: {
                        label: 'Undo',
                        callback: async () => {
                            await this.restoreTask(taskId);
                        }
                    }
                });
            }

        } catch (error) {
            console.error('❌ Optimistic delete failed:', error);
            throw error;
        }
    }

    /**
     * Archive task (mark as completed - Task model has no archived_at column)
     * @param {number|string} taskId
     * @returns {Promise<Object>}
     */
    async archiveTask(taskId) {
        return this.updateTask(taskId, {
            status: 'completed',
            completed_at: new Date().toISOString()
        });
    }

    /**
     * Unarchive task (restore to todo status)
     * @param {number|string} taskId
     * @returns {Promise<Object>}
     */
    async unarchiveTask(taskId) {
        return this.updateTask(taskId, {
            status: 'todo',
            completed_at: null
        });
    }

    /**
     * Restore deleted task (undo soft delete within 15s window)
     * @param {number|string} taskId
     * @returns {Promise<Object>}
     */
    async restoreTask(taskId) {
        // Clear deleted_at to restore
        const result = await this.updateTask(taskId, {
            deleted_at: null,
            deleted_by_user_id: null
        });

        // Re-render the task in the UI (it was removed from DOM during delete)
        const task = await this.cache.getTask(taskId);
        if (task && window.taskBootstrap) {
            // Trigger a re-render by dispatching custom event
            window.dispatchEvent(new CustomEvent('task:restored', {
                detail: { taskId, task }
            }));

            // Or directly call bootstrap to re-render tasks
            const container = document.getElementById('tasks-list-container');
            if (container) {
                const tasks = await this.cache.getTasks();
                // Filter out deleted tasks and archived (completed/cancelled) tasks
                const activeTasks = tasks.filter(t => {
                    if (t.deleted_at) return false;
                    const status = (t.status || '').toLowerCase();
                    return status !== 'completed' && status !== 'cancelled';
                });
                const ctx = window.taskBootstrap._getCurrentViewContext?.() || { filter: 'active', search: '', sort: { field: 'created_at', direction: 'desc' } };
                await window.taskBootstrap.renderTasks(activeTasks, { 
                    fromCache: true, 
                    source: 'optimistic',
                    isUserAction: true,
                    filterContext: ctx.filter,
                    searchQuery: ctx.search,
                    sortConfig: ctx.sort
                });
            }
        }

        return result;
    }

    /**
     * Complete task (set status to completed, never uncomplete)
     * Used for bulk operations to ensure proper event propagation
     * @param {number|string} taskId
     * @returns {Promise<Object>}
     */
    async completeTask(taskId) {
        const task = await this.cache.getTask(taskId);
        if (!task) return;

        // Skip if already completed
        if (task.status === 'completed') {
            return task;
        }

        const updates = {
            status: 'completed',
            completed_at: new Date().toISOString()
        };

        const result = await this.updateTask(taskId, updates);

        // Trigger celebration animation
        if (window.emotionalAnimations) {
            const card = document.querySelector(`[data-task-id="${taskId}"]`);
            if (card) {
                window.emotionalAnimations.celebrate(card, ['burst', 'shimmer']);
            }
        }
        
        // Dispatch completion event for other listeners
        window.dispatchEvent(new CustomEvent('task:completed', {
            detail: { taskId, task: result }
        }));

        return result;
    }

    /**
     * Toggle task status optimistically
     * CROWN⁴.13: Complete flow logging for debugging persistence issues
     * @param {number|string} taskId
     * @returns {Promise<Object>}
     */
    async toggleTaskStatus(taskId) {
        console.log(`🔄 [ToggleStatus] START - Task ${taskId}`);
        
        const task = await this.cache.getTask(taskId);
        if (!task) {
            console.warn(`⚠️ [ToggleStatus] Task ${taskId} not found in cache`);
            return;
        }

        const oldStatus = task.status;
        const newStatus = oldStatus === 'completed' ? 'todo' : 'completed';
        console.log(`📝 [ToggleStatus] Task ${taskId}: ${oldStatus} → ${newStatus}`);
        
        const updates = {
            status: newStatus,
            completed_at: newStatus === 'completed' ? new Date().toISOString() : null
        };
        console.log(`📦 [ToggleStatus] Update payload:`, updates);

        const result = await this.updateTask(taskId, updates);
        console.log(`✅ [ToggleStatus] updateTask() returned for task ${taskId}`);
        console.log(`📊 [ToggleStatus] Result:`, { id: result?.id, status: result?.status });

        if (newStatus === 'completed') {
            if (window.emotionalAnimations) {
                const card = document.querySelector(`[data-task-id="${taskId}"]`);
                if (card) {
                    window.emotionalAnimations.celebrate(card, ['burst', 'shimmer']);
                }
            }
            
            window.dispatchEvent(new CustomEvent('task:completed', {
                detail: { taskId, task }
            }));
        }

        return result;
    }

    /**
     * Snooze task optimistically
     * @param {number|string} taskId
     * @param {Date} snoozeUntil
     * @returns {Promise<Object>}
     */
    async snoozeTask(taskId, snoozeUntil) {
        return this.updateTask(taskId, {
            snoozed_until: snoozeUntil.toISOString()
        });
    }

    /**
     * Update task priority optimistically
     * @param {number|string} taskId
     * @param {string} priority
     * @returns {Promise<Object>}
     */
    async updatePriority(taskId, priority) {
        const result = await this.updateTask(taskId, { priority });

        if (window.emotionalAnimations) {
            const card = document.querySelector(`[data-task-id="${taskId}"]`);
            if (card) {
                window.emotionalAnimations.shimmer(card, {
                    emotion_cue: 'priority_change'
                });
            }
        }

        return result;
    }

    /**
     * Add label to task optimistically
     * @param {number|string} taskId
     * @param {string} label
     * @returns {Promise<Object>}
     */
    async addLabel(taskId, label) {
        const task = await this.cache.getTask(taskId);
        if (!task) return;

        const labels = task.labels || [];
        if (!labels.includes(label)) {
            labels.push(label);
        }

        return this.updateTask(taskId, { labels });
    }

    /**
     * Remove label from task optimistically
     * @param {number|string} taskId
     * @param {string} label
     * @returns {Promise<Object>}
     */
    async removeLabel(taskId, label) {
        const task = await this.cache.getTask(taskId);
        if (!task) return;

        const labels = task.labels || [];
        const updatedLabels = labels.filter(l => l !== label);

        return this.updateTask(taskId, { labels: updatedLabels });
    }

    /**
     * Snooze task optimistically
     * @param {number|string} taskId
     * @param {Date} snoozedUntil - When to unsnooze the task
     * @returns {Promise<Object>}
     */
    async snoozeTask(taskId, snoozedUntil) {
        const task = await this.cache.getTask(taskId);
        if (!task) return;

        // Update task with snooze timestamp
        const result = await this.updateTask(taskId, { 
            snoozed_until: snoozedUntil.toISOString()
        });

        // Hide snoozed task from view with animation (CROWN⁴.5 QuietStateManager)
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (card && window.quietStateManager) {
            window.quietStateManager.queueAnimation((setCancelHandler) => {
                card.style.animation = 'fadeOut 0.3s ease-out';
                const timeoutId = setTimeout(() => {
                    card.style.display = 'none';
                    this._updateCounters();
                }, 300);
                
                setCancelHandler(() => {
                    clearTimeout(timeoutId);
                    card.style.animation = '';
                });
            }, { duration: 300, priority: 6, metadata: { type: 'task_snooze', task_id: taskId } });
        } else if (card) {
            card.style.animation = 'fadeOut 0.3s ease-out';
            setTimeout(() => {
                card.style.display = 'none';
                this._updateCounters();
            }, 300);
        }

        return result;
    }

    /**
     * Merge two tasks optimistically
     * @param {number|string} sourceTaskId - Task to merge from (will be deleted)
     * @param {number|string} targetTaskId - Task to merge into (will be kept)
     * @returns {Promise<Object>}
     */
    async mergeTasks(sourceTaskId, targetTaskId) {
        const sourceTask = await this.cache.getTask(sourceTaskId);
        const targetTask = await this.cache.getTask(targetTaskId);
        
        if (!sourceTask || !targetTask) return;

        const opId = this._generateOperationId();
        
        // Save original target task state for rollback
        const originalTargetTask = { ...targetTask };

        try {
            // Step 1: Hide source task with animation (CROWN⁴.5 QuietStateManager)
            const sourceCard = document.querySelector(`[data-task-id="${sourceTaskId}"]`);
            if (sourceCard && window.quietStateManager) {
                window.quietStateManager.queueAnimation((setCancelHandler) => {
                    sourceCard.style.animation = 'fadeOut 0.3s ease-out';
                    const timeoutId = setTimeout(() => sourceCard.style.display = 'none', 300);
                    
                    setCancelHandler(() => {
                        clearTimeout(timeoutId);
                        sourceCard.style.animation = '';
                    });
                }, { duration: 300, priority: 8, metadata: { type: 'task_merge', task_id: sourceTaskId } });
            } else if (sourceCard) {
                sourceCard.style.animation = 'fadeOut 0.3s ease-out';
                setTimeout(() => sourceCard.style.display = 'none', 300);
            }

            // Step 2: Merge data - combine labels, keep higher priority, combine descriptions
            const mergedLabels = [...new Set([...(targetTask.labels || []), ...(sourceTask.labels || [])])];
            const priorityRank = { urgent: 4, high: 3, medium: 2, low: 1 };
            const mergedPriority = (priorityRank[sourceTask.priority] > priorityRank[targetTask.priority]) 
                ? sourceTask.priority : targetTask.priority;
            
            let mergedDescription = targetTask.description || '';
            if (sourceTask.description && !mergedDescription.includes(sourceTask.description)) {
                mergedDescription = mergedDescription 
                    ? `${mergedDescription}\n\n[Merged from another task]\n${sourceTask.description}`
                    : sourceTask.description;
            }

            // Step 3: Update cache
            const updatedTask = {
                ...targetTask,
                labels: mergedLabels,
                priority: mergedPriority,
                description: mergedDescription,
                updated_at: new Date().toISOString(),
                _optimistic: true,
                _operation_id: opId
            };
            await this.cache.setTask(targetTaskId, updatedTask);

            // Step 4: Update target task DOM
            this._updateTaskInDOM(targetTaskId, updatedTask);

            // Step 5: Sync to server
            const response = await fetch(`/api/tasks/${targetTaskId}/merge`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ source_task_id: sourceTaskId })
            });

            if (!response.ok) {
                throw new Error(`Merge failed: ${response.statusText}`);
            }

            const data = await response.json();
            
            // Step 6: Reconcile with server truth
            await this.cache.setTask(targetTaskId, data.task);
            this._updateTaskInDOM(targetTaskId, data.task);
            
            // Remove source task from cache
            await this.cache.deleteTask(sourceTaskId);
            
            this._updateCounters();
            this.pendingOperations.delete(opId);
            
            return data.task;
        } catch (error) {
            console.error('❌ Merge failed - rolling back:', error);
            
            // Rollback: restore source task card (CROWN⁴.5 QuietStateManager)
            const sourceCard = document.querySelector(`[data-task-id="${sourceTaskId}"]`);
            if (sourceCard && window.quietStateManager) {
                window.quietStateManager.queueAnimation((setCancelHandler) => {
                    sourceCard.style.display = '';
                    sourceCard.style.animation = 'slideInFromTop 0.3s ease-out';
                    
                    setCancelHandler(() => {
                        sourceCard.style.animation = '';
                    });
                }, { duration: 300, priority: 9, metadata: { type: 'task_merge_rollback', task_id: sourceTaskId } });
            } else if (sourceCard) {
                sourceCard.style.display = '';
                sourceCard.style.animation = 'slideInFromTop 0.3s ease-out';
            }
            
            // Rollback: restore original target task in cache and DOM
            await this.cache.setTask(targetTaskId, originalTargetTask);
            this._updateTaskInDOM(targetTaskId, originalTargetTask);
            
            this.pendingOperations.delete(opId);
            throw error;
        }
    }

    /**
     * Generate unique operation ID
     * @returns {string}
     */
    _generateOperationId() {
        return `op_${Date.now()}_${++this.operationCounter}`;
    }

    /**
     * Add task to DOM
     * @param {Object} task
     */
    _addTaskToDOM(task) {
        const container = document.getElementById('tasks-list-container');
        if (!container) return;

        const taskHTML = window.taskBootstrap.renderTaskCard(task, 0);
        container.insertAdjacentHTML('afterbegin', taskHTML);

        // Add CROWN⁴.5 emotional pop-in animation
        const card = container.querySelector(`[data-task-id="${task.id}"]`);
        if (card && window.emotionalAnimations) {
            window.emotionalAnimations.popIn(card, {
                emotion_cue: 'task_created'
            });
        } else if (card && window.quietStateManager) {
            // Fallback to QuietStateManager
            window.quietStateManager.queueAnimation((setCancelHandler) => {
                card.classList.add('optimistic-create');
                card.style.animation = 'slideInFromTop 0.3s ease-out';
                
                setCancelHandler(() => {
                    card.classList.remove('optimistic-create');
                    card.style.animation = '';
                });
            }, { duration: 300, priority: 7, metadata: { type: 'task_create', task_id: task.id } });
        } else if (card) {
            // Final fallback
            card.classList.add('optimistic-create');
            card.style.animation = 'slideInFromTop 0.3s ease-out';
        }

        // Hide empty state
        const emptyState = document.getElementById('tasks-empty-state');
        if (emptyState) {
            emptyState.style.display = 'none';
        }

        // Update counters
        this._updateCounters();
    }

    /**
     * Update task in DOM
     * @param {number|string} taskId
     * @param {Object} task
     */
    _updateTaskInDOM(taskId, task) {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!card) return;

        // CROWN⁴.8: Diff check for assignee_ids to prevent redundant re-renders (flicker prevention)
        // Skip assignee badge update if IDs are unchanged (optimistic already applied)
        const incomingIds = (task.assignee_ids || []).slice().sort((a, b) => a - b);
        const currentIds = (card.dataset.assigneeIds || '').split(',').filter(Boolean).map(Number).sort((a, b) => a - b);
        const assigneesUnchanged = incomingIds.length === currentIds.length && 
            incomingIds.every((id, i) => id === currentIds[i]);
        
        if (assigneesUnchanged && incomingIds.length > 0) {
            console.log('[_updateTaskInDOM] Skipping assignee render - IDs unchanged:', incomingIds.join(','));
        }
        
        // Always update the stored IDs for next comparison
        card.dataset.assigneeIds = incomingIds.join(',');

        // Update title
        const titleEl = card.querySelector('.task-title');
        if (titleEl && task.title) {
            titleEl.textContent = task.title;
        }

        // Update description
        const descEl = card.querySelector('.task-description');
        if (task.description) {
            if (descEl) {
                descEl.textContent = task.description;
            } else {
                const contentEl = card.querySelector('.task-content');
                if (contentEl) {
                    const descHTML = `<p class="task-description">${this._escapeHtml(task.description)}</p>`;
                    contentEl.insertAdjacentHTML('afterbegin', descHTML);
                }
            }
        }

        // Update status
        if (task.status) {
            card.dataset.status = task.status;
            const checkbox = card.querySelector('.task-checkbox');
            if (checkbox) {
                checkbox.checked = task.status === 'completed';
            }
            if (task.status === 'completed') {
                console.log(`✅ Adding 'completed' class to task card ${taskId}`);
                card.classList.add('completed');
            } else {
                console.log(`❌ Removing 'completed' class from task card ${taskId}`);
                card.classList.remove('completed');
            }
        }

        // Update priority
        if (task.priority) {
            card.dataset.priority = task.priority;
            const priorityBadge = card.querySelector('.priority-badge');
            if (priorityBadge) {
                priorityBadge.className = `priority-badge priority-${task.priority.toLowerCase()}`;
                priorityBadge.textContent = task.priority;
            }
        }

        // Update assignee badge (CRITICAL FIX: Instant UI update for assignments)
        // Handles both existing badges and re-rendering when badge structure needs updating
        // INDUSTRY-STANDARD: Follows Linear/Notion/Asana pattern for instant optimistic updates
        // CROWN⁴.7: Handle BOTH server-rendered (.task-assignee) and JS-rendered (.task-assignees) structures
        // CROWN⁴.8: Skip badge update if assignee_ids unchanged (flicker prevention)
        if (!assigneesUnchanged) {
            const taskMeta = card.querySelector('.task-metadata') || card.querySelector('.task-content');
            let assigneeBadge = card.querySelector('.task-assignee') || card.querySelector('.task-assignees');
            
            // CROWN⁴.8: Multi-assignee support - first try using payload's assignees array (optimistic path)
            // This ensures instant display without waiting for user resolution
            const allUsers = window.taskAssigneeSelector?.allUsers || [];
            const assigneeIds = (task.assignee_ids || []).slice().sort((a, b) => a - b);
            const maxVisibleAssignees = 2;
            
            // Resolve assignees: prefer task.assignees (full objects), fallback to resolving from IDs
            let resolvedAssignees = [];
            if (task.assignees && task.assignees.length > 0) {
                // Use optimistic payload's full assignees array (sorted by ID)
                resolvedAssignees = task.assignees.slice().sort((a, b) => a.id - b.id);
                console.log('[_updateTaskInDOM] Using payload assignees:', resolvedAssignees.length);
            } else if (assigneeIds.length > 0) {
                // Fallback: resolve from IDs
                resolvedAssignees = assigneeIds.map(id => allUsers.find(u => u.id === id)).filter(Boolean);
                console.log('[_updateTaskInDOM] Resolved', resolvedAssignees.length, 'assignees from', assigneeIds.length, 'IDs');
            }
            
            // Fallback to single assigned_to if no IDs resolved
            if (resolvedAssignees.length === 0 && task.assigned_to && task.assigned_to.id) {
                resolvedAssignees = [task.assigned_to];
            }
            
            // Handle explicit unassign case
            const isExplicitUnassign = task.hasOwnProperty('assigned_to') && task.assigned_to === null;
            const hasEmptyAssigneeIds = task.assignee_ids && task.assignee_ids.length === 0;
            
            // SVG icon (matches task-bootstrap.js)
            const svgIcon = `<svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
            </svg>`;
            const addUserSvg = `<svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/>
            </svg>`;
            
            let newBadgeHTML;
            
            if (resolvedAssignees.length > 0) {
                // ASSIGN: Show assignee names with overflow handling (Linear/Notion style)
                const visibleAssignees = resolvedAssignees.slice(0, maxVisibleAssignees);
                const overflowCount = resolvedAssignees.length - maxVisibleAssignees;
                
                const assigneeNames = visibleAssignees
                    .map(a => a.display_name || a.username || a.email)
                    .filter(Boolean)
                    .join(', ');
                
                const fullList = resolvedAssignees
                    .map(a => a.display_name || a.username || a.email)
                    .filter(Boolean)
                    .join(', ');
                
                const overflowSpan = overflowCount > 0 ? ` <span class="assignee-overflow">+${overflowCount}</span>` : '';
                
                newBadgeHTML = `<div class="task-assignees" data-task-id="${task.id}" title="${this._escapeHtml(fullList || 'Click to change assignees')}">
                    ${svgIcon}
                    <span class="assignee-names">${this._escapeHtml(assigneeNames || 'Assigned')}${overflowSpan}</span>
                </div>`;
                console.log('[_updateTaskInDOM] Rendering multi-assignee badge:', assigneeNames, overflowCount > 0 ? `+${overflowCount}` : '');
                
            } else if (isExplicitUnassign || hasEmptyAssigneeIds) {
                // UNASSIGN: Show "Assign" placeholder with add-user icon
                newBadgeHTML = `<div class="task-assignees task-assignees-empty" data-task-id="${task.id}" title="Click to assign">
                    ${addUserSvg}
                    <span class="assignee-names">Assign</span>
                </div>`;
                console.log('[_updateTaskInDOM] Clearing assignee (unassign)');
                
            } else if (assigneeIds.length > 0) {
                // Fallback: Has IDs but couldn't resolve users - show generic placeholder
                newBadgeHTML = `<div class="task-assignees" data-task-id="${task.id}" title="Click to change assignees">
                    ${svgIcon}
                    <span class="assignee-names">Assigned</span>
                </div>`;
                console.log('[_updateTaskInDOM] Fallback: showing generic Assigned badge');
            }
            
            // Apply the badge update
            if (newBadgeHTML) {
                if (assigneeBadge) {
                    assigneeBadge.outerHTML = newBadgeHTML;
                } else if (taskMeta) {
                    taskMeta.insertAdjacentHTML('afterbegin', newBadgeHTML);
                }
            }
        }

        // Update labels (CROWN⁴.7: Instant labels update with empty-state CTA)
        if (task.hasOwnProperty('labels')) {
            const labelsContainer = card.querySelector('.task-labels');
            const labelsEmpty = card.querySelector('.task-labels-empty');
            
            if (task.labels && task.labels.length > 0) {
                // Has labels: show container, hide empty CTA
                if (labelsContainer) {
                    labelsContainer.innerHTML = '';
                    task.labels.forEach(label => {
                        const labelSpan = document.createElement('span');
                        labelSpan.className = 'task-label';
                        labelSpan.textContent = label;
                        labelsContainer.appendChild(labelSpan);
                    });
                    labelsContainer.style.display = '';
                } else if (taskMeta) {
                    const labelsHTML = `<div class="task-labels">${task.labels.map(l => `<span class="task-label">${this._escapeHtml(l)}</span>`).join('')}</div>`;
                    taskMeta.insertAdjacentHTML('afterend', labelsHTML);
                }
                if (labelsEmpty) labelsEmpty.style.display = 'none';
                console.log('[_updateTaskInDOM] Updated labels:', task.labels);
            } else {
                // No labels: hide container, show empty CTA
                if (labelsContainer) {
                    labelsContainer.innerHTML = '';
                    labelsContainer.style.display = 'none';
                }
                if (labelsEmpty) {
                    labelsEmpty.style.display = '';
                } else if (taskMeta) {
                    // Create empty CTA if missing
                    const emptyCTA = document.createElement('span');
                    emptyCTA.className = 'task-labels-empty';
                    emptyCTA.textContent = '+ Add label';
                    taskMeta.appendChild(emptyCTA);
                }
                console.log('[_updateTaskInDOM] Cleared labels, showing CTA');
            }
        }

        // Update due date (CROWN⁴.7: Instant due date update with empty-state CTA)
        // Architecture: Either badge (with date) OR empty CTA (no date) is visible, never both
        if (task.hasOwnProperty('due_date')) {
            let dueDateBadge = card.querySelector('.task-due-date, .due-date-badge:not(.due-date-badge--empty)');
            let dueDateEmpty = card.querySelector('.due-date-badge--empty, [data-inline-action="add-due-date"]');
            
            if (task.due_date) {
                // HAS DUE DATE: Show badge, hide empty CTA
                const date = new Date(task.due_date);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const diff = Math.floor((date - today) / (1000 * 60 * 60 * 24));
                
                let displayText;
                if (diff === 0) displayText = 'Today';
                else if (diff === 1) displayText = 'Tomorrow';
                else if (diff < 0) displayText = 'Overdue';
                else if (diff <= 7) displayText = `In ${diff}d`;
                else displayText = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                
                // Step 1: Ensure badge exists (create if missing)
                if (!dueDateBadge) {
                    if (taskMeta) {
                        dueDateBadge = document.createElement('span');
                        dueDateBadge.className = 'due-date-badge';
                        taskMeta.appendChild(dueDateBadge);
                    }
                }
                
                // Step 2: Update badge content and show it
                if (dueDateBadge) {
                    dueDateBadge.textContent = displayText;
                    dueDateBadge.style.display = '';
                    dueDateBadge.classList.remove('due-date-badge--empty');
                    if (diff < 0) {
                        dueDateBadge.classList.add('overdue');
                    } else {
                        dueDateBadge.classList.remove('overdue');
                    }
                }
                
                // Step 3: Hide empty CTA
                if (dueDateEmpty) {
                    dueDateEmpty.style.display = 'none';
                }
                
                console.log('[_updateTaskInDOM] Set due date:', displayText);
            } else {
                // NO DUE DATE: Hide badge, show empty CTA
                
                // Step 1: Hide badge if it exists
                if (dueDateBadge) {
                    dueDateBadge.style.display = 'none';
                }
                
                // Step 2: Ensure empty CTA exists (create if missing)
                if (!dueDateEmpty) {
                    if (taskMeta) {
                        dueDateEmpty = document.createElement('span');
                        dueDateEmpty.className = 'due-date-badge--empty';
                        dueDateEmpty.setAttribute('data-inline-action', 'add-due-date');
                        dueDateEmpty.textContent = '+ Add due date';
                        taskMeta.appendChild(dueDateEmpty);
                    }
                }
                
                // Step 3: Show empty CTA
                if (dueDateEmpty) {
                    dueDateEmpty.style.display = '';
                }
                
                console.log('[_updateTaskInDOM] Cleared due date, showing CTA');
            }
        }

        // Update snoozed state (CROWN⁴.7: Visual feedback for snooze)
        if (task.hasOwnProperty('snoozed_until')) {
            let snoozeIndicator = card.querySelector('.snooze-indicator');
            
            if (task.snoozed_until) {
                card.classList.add('snoozed');
                card.dataset.snoozedUntil = task.snoozed_until;
                
                // Add or update snooze indicator
                if (!snoozeIndicator && taskMeta) {
                    snoozeIndicator = document.createElement('span');
                    snoozeIndicator.className = 'snooze-indicator';
                    taskMeta.appendChild(snoozeIndicator);
                }
                if (snoozeIndicator) {
                    const snoozeDate = new Date(task.snoozed_until);
                    snoozeIndicator.textContent = `💤 Until ${snoozeDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
                    snoozeIndicator.style.display = '';
                }
                console.log('[_updateTaskInDOM] Task snoozed until:', task.snoozed_until);
            } else {
                // Unsnooze: fully remove indicator and class
                card.classList.remove('snoozed');
                delete card.dataset.snoozedUntil;
                if (snoozeIndicator) {
                    snoozeIndicator.remove();
                }
                console.log('[_updateTaskInDOM] Cleared snooze, removed indicator');
            }
        }

        // Add optimistic indicator (CROWN⁴.5 QuietStateManager)
        if (window.quietStateManager) {
            window.quietStateManager.queueAnimation((setCancelHandler) => {
                card.classList.add('optimistic-update');
                const timeoutId = setTimeout(() => card.classList.remove('optimistic-update'), 300);
                
                setCancelHandler(() => {
                    clearTimeout(timeoutId);
                    card.classList.remove('optimistic-update');
                });
            }, { duration: 300, priority: 6, metadata: { type: 'task_update', task_id: taskId } });
        } else {
            card.classList.add('optimistic-update');
            setTimeout(() => card.classList.remove('optimistic-update'), 300);
        }

        this._updateCounters();
    }

    /**
     * Remove task from DOM
     * @param {number|string} taskId
     */
    _removeTaskFromDOM(taskId) {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!card) return;

        // Use QuietStateManager for fade-out animation (CROWN⁴.5)
        if (window.quietStateManager) {
            window.quietStateManager.queueAnimation((setCancelHandler) => {
                card.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                card.style.opacity = '0';
                card.style.transform = 'translateX(-20px)';
                
                const timeoutId = setTimeout(() => {
                    card.remove();
                    this._updateCounters();
                    
                    const remaining = document.querySelectorAll('.task-card').length;
                    if (remaining === 0) {
                        const emptyState = document.getElementById('tasks-empty-state');
                        if (emptyState) emptyState.style.display = 'block';
                    }
                }, 300);
                
                setCancelHandler(() => {
                    clearTimeout(timeoutId);
                    card.style.transition = '';
                    card.style.opacity = '';
                    card.style.transform = '';
                });
            }, { duration: 300, priority: 5, metadata: { type: 'task_remove', task_id: taskId } });
        } else {
            card.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
            card.style.opacity = '0';
            card.style.transform = 'translateX(-20px)';
            
            setTimeout(() => {
                card.remove();
                this._updateCounters();
                
                const remaining = document.querySelectorAll('.task-card').length;
                if (remaining === 0) {
                    const emptyState = document.getElementById('tasks-empty-state');
                    if (emptyState) emptyState.style.display = 'block';
                }
            }, 300);
        }
    }

    /**
     * Update task counters
     * CROWN⁴.6: Delegates to TaskStateStore for single source of truth
     * All counter updates MUST go through TaskStateStore
     */
    _updateCounters() {
        // PRIMARY: Use TaskStateStore (single source of truth)
        if (window.taskStateStore && window.taskStateStore._initialized) {
            window.taskStateStore.forceRefresh();
            return;
        }
        
        // FALLBACK: Delegate to TaskBootstrap if TaskStateStore not ready
        if (window.taskBootstrap && typeof window.taskBootstrap._updateCountersFromDOM === 'function') {
            window.taskBootstrap._updateCountersFromDOM();
        }
    }

    /**
     * Sync operation to server via WebSocket
     * Gracefully defers to OfflineQueueManager if socket is disconnected/reconnecting
     * @param {string} opId
     * @param {string} type
     * @param {Object} data
     * @param {number|string} taskId
     */
    async _syncToServer(opId, type, data, taskId) {
        const startTime = performance.now();

        try {
            // Check WebSocket connection (wsManager.sockets.tasks is the socket object)
            const isConnected = window.wsManager && 
                               window.wsManager.sockets.tasks && 
                               window.wsManager.sockets.tasks.connected;
            
            if (!isConnected) {
                // ENTERPRISE-GRADE: HTTP fallback when WebSocket is unavailable
                console.log(`⏸️ WebSocket not connected, attempting HTTP fallback (${type})`);
                
                // Emit telemetry for HTTP fallback
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordEvent('task_sync_http_fallback', {
                        type,
                        reason: 'socket_disconnected'
                    });
                }
                
                try {
                    const result = await this._syncViaHTTP(opId, type, data, taskId);
                    await this._reconcileSuccess(opId, type, result, taskId);
                    console.log(`✅ [HTTP Fallback] ${type} operation succeeded`);
                    return;
                } catch (httpError) {
                    console.error(`❌ [HTTP Fallback] Failed:`, httpError);
                    
                    // CRITICAL FIX: Trigger rollback so UI reflects actual server state
                    await this._reconcileFailure(opId, type, taskId, httpError);
                    
                    // Show user-friendly error
                    if (window.toast) {
                        window.toast.error(`Failed to save changes: ${httpError.message || 'Network error'}`);
                    }
                    return;
                }
            }

            // Get user and session context
            const userId = window.CURRENT_USER_ID || null;
            const sessionId = window.CURRENT_SESSION_ID || null;
            const workspaceId = window.WORKSPACE_ID || null;

            if (!userId) {
                console.error('❌ User ID not found in page context');
                throw new Error('User not authenticated');
            }

            // Map operation types to WebSocket event names (server expects simple event names)
            let eventName, payload;

            if (type === 'create') {
                // Server listens for 'task_create' (not 'task_create:manual')
                eventName = 'task_create';
                payload = {
                    payload: {
                        ...data,
                        temp_id: taskId,
                        operation_id: opId,
                        user_id: userId,
                        session_id: sessionId,
                        workspace_id: workspaceId
                    }
                };
            } else if (type === 'update') {
                // Server expects 'update_type' field for routing
                // Map to exact server event names (from routes/tasks_websocket.py:6-18)
                eventName = 'task_update';
                let updateType = 'title'; // default
                
                // CRITICAL FIX: deleted_at (archive/soft-delete) uses HTTP fallback
                // WebSocket doesn't have dedicated archive event, but HTTP PUT supports deleted_at
                if (data.deleted_at !== undefined) {
                    console.log(`🔄 [Archive] Using HTTP fallback for deleted_at update`);
                    try {
                        const result = await this._syncViaHTTP(opId, type, data, taskId);
                        await this._reconcileSuccess(opId, type, result, taskId);
                        console.log(`✅ [Archive] HTTP update succeeded`);
                        return;
                    } catch (httpError) {
                        console.error(`❌ [Archive] HTTP fallback failed:`, httpError);
                        await this._reconcileFailure(opId, type, taskId, httpError);
                        if (window.toast) {
                            window.toast.error(`Failed to archive: ${httpError.message || 'Network error'}`);
                        }
                        return;
                    }
                } else if (data.status !== undefined) {
                    updateType = 'status_toggle';
                } else if (data.priority !== undefined) {
                    updateType = 'priority';
                } else if (data.due_date !== undefined || data.due !== undefined) {
                    updateType = 'due';
                } else if (data.assignee !== undefined || data.assigned_to !== undefined || data.assignee_ids !== undefined) {
                    updateType = 'assign';
                } else if (data.labels !== undefined) {
                    updateType = 'labels';
                } else if (data.title !== undefined) {
                    updateType = 'title';
                }
                
                payload = {
                    payload: {
                        task_id: taskId,
                        ...data,
                        operation_id: opId,
                        user_id: userId,
                        session_id: sessionId,
                        workspace_id: workspaceId
                    },
                    update_type: updateType
                };
            } else if (type === 'delete') {
                eventName = 'task_delete';
                payload = {
                    payload: {
                        task_id: taskId,
                        operation_id: opId,
                        user_id: userId,
                        session_id: sessionId,
                        workspace_id: workspaceId
                    }
                };
            }

            console.log(`📤 Sending ${eventName} event:`, payload);

            // Emit via WebSocket and wait for server acknowledgment
            const result = await window.wsManager.emitWithAck(eventName, payload, '/tasks');

            const reconcileTime = performance.now() - startTime;
            console.log(`✅ Server acknowledged ${type} in ${reconcileTime.toFixed(2)}ms, response:`, result);

            // CROWN⁴.13 FIX: Check if server returned success=false and trigger rollback
            // This handles cases where WebSocket ACK is received but the operation failed server-side
            if (result?.success === false || result?.result?.success === false) {
                const errorMessage = result?.error || result?.result?.error || 'Server rejected operation';
                console.error(`❌ [_syncToServer] Server returned failure:`, errorMessage);
                throw new Error(errorMessage);
            }

            // Reconcile with server data
            await this._reconcileSuccess(opId, type, result, taskId);

            // Emit telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('optimistic_reconcile_ms', reconcileTime);
            }

            // Emit event for performance validator
            window.dispatchEvent(new CustomEvent('reconcile:complete', {
                detail: { type, reconcileTime, taskId }
            }));

        } catch (error) {
            const syncTime = performance.now() - startTime;
            console.error(`❌ Server sync failed for ${type} after ${syncTime.toFixed(2)}ms:`, {
                error: error.message,
                opId,
                taskId,
                type,
                stack: error.stack
            });
            
            const is409Conflict = error.message && (
                error.message.includes('409') || 
                error.message.includes('conflict') ||
                error.message.includes('version mismatch')
            );
            
            // ENTERPRISE-GRADE: Special handling for temp ID validation errors
            const isTempIdError = error.message && (
                error.message.includes('temporary ID') ||
                error.message.includes('TEMP_ID_NOT_RECONCILED') ||
                error.message.includes('temp_')
            );
            
            if (isTempIdError) {
                // Temp ID error - this task needs reconciliation with server
                if (window.toast) {
                    window.toast.warning('This task is still syncing with the server. Please wait a moment and try again.', 5000, {
                        undoText: 'Refresh',
                        undoCallback: () => window.location.reload()
                    });
                }
            } else if (is409Conflict) {
                if (window.toast) {
                    window.toast.warning('Changes conflict detected - reloading latest version', 5000, {
                        undoText: 'Retry',
                        undoCallback: () => this._retryOperation(opId)
                    });
                }
            } else {
                if (window.toast) {
                    window.toast.error(`Save failed - ${error.message}`, 6000, {
                        undoText: 'Retry',
                        undoCallback: () => this._retryOperation(opId)
                    });
                }
            }
            
            // Emit telemetry for failures
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('optimistic_failure_ms', syncTime);
                window.CROWNTelemetry.recordEvent('task_sync_failure', {
                    type,
                    error: error.message,
                    duration_ms: syncTime,
                    is_conflict: is409Conflict,
                    is_temp_id_error: isTempIdError
                });
            }
            
            await this._reconcileFailure(opId, type, taskId, error);
        }
    }

    /**
     * ENTERPRISE-GRADE: HTTP fallback when WebSocket is unavailable
     * Provides resilient sync path for offline-first behavior
     * @param {string} opId
     * @param {string} type
     * @param {Object} data
     * @param {number|string} taskId
     * @returns {Promise<Object>} Server response
     */
    async _syncViaHTTP(opId, type, data, taskId) {
        console.log(`🌐 [HTTP Fallback] Syncing ${type} operation via REST API`);
        
        let url, method, body;
        
        if (type === 'create') {
            url = '/api/tasks/';
            method = 'POST';
            body = {
                ...data,
                temp_id: taskId,
                operation_id: opId
            };
        } else if (type === 'update') {
            url = `/api/tasks/${taskId}`;
            method = 'PUT';
            body = {
                ...data,
                operation_id: opId
            };
        } else if (type === 'delete') {
            url = `/api/tasks/${taskId}`;
            method = 'DELETE';
            body = {
                operation_id: opId
            };
        }
        
        const response = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify(body)
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: response.statusText }));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const result = await response.json();
        console.log(`✅ [HTTP Fallback] ${type} operation completed:`, result);
        
        return result;
    }

    /**
     * Reconcile successful server response
     * CRITICAL FIX: Properly finalizes creates for all transport paths (WebSocket, HTTP, duplicate)
     * @param {string} opId
     * @param {string} type
     * @param {Object} serverData
     * @param {number|string} taskId
     */
    async _reconcileSuccess(opId, type, serverData, taskId) {
        const operation = this.pendingOperations.get(opId);
        if (!operation) return;

        // ENTERPRISE-GRADE: Remove from both offline_queue and event queue since sync succeeded
        if (this.cache) {
            try {
                // Remove from pending operations store
                await this.cache.removePendingOperation(opId);
                console.log(`✅ [Offline-First] Removed pending operation ${opId} from IndexedDB`);
                
                // Also remove from offline queue if present
                if (operation.queueId) {
                    await this.cache.removeFromQueue(operation.queueId);
                    console.log(`🗑️ Removed queue entry ${operation.queueId} after successful sync`);
                }
            } catch (error) {
                console.warn(`⚠️ Failed to remove operation from IndexedDB:`, error);
            }
        }

        if (type === 'create') {
            // Replace temp ID with real ID
            // Handle various response formats:
            // - serverData.result.task (WebSocket ack with result wrapper)
            // - serverData.result.existing_task (WebSocket duplicate detection)
            // - serverData.existing_task (HTTP API duplicate detection)
            // - serverData.task (direct task wrapper from HTTP API)
            // - serverData (task object directly)
            const realTask = serverData?.result?.task || 
                           serverData?.result?.existing_task || 
                           serverData?.existing_task ||
                           serverData?.task || 
                           serverData;
            const tempId = operation.tempId;
            const isDuplicate = serverData?.result?.duplicate === true || 
                               serverData?.is_duplicate === true;
            
            // CRITICAL: Verify we have a valid task ID before proceeding
            if (!realTask?.id) {
                console.error('❌ [Reconcile] No task ID in server response:', serverData);
                throw new Error('Server response missing task ID');
            }
            
            // Log duplicate detection for debugging
            if (isDuplicate) {
                console.log(`ℹ️ [Reconcile] Duplicate detected, using existing task ID ${realTask.id}`);
            }
            
            console.log(`✅ [Reconcile] Got real task ID ${realTask.id} for temp ${tempId}`);

            // CRITICAL FIX: Finalize create by updating DOM and clearing syncing badge
            await this._finalizeCreate(tempId, realTask);

        } else if (type === 'update') {
            // Update with server truth
            // Handle various response formats
            const realTask = serverData?.result?.task || serverData?.task || serverData;
            
            if (realTask?.id) {
                await this.cache.saveTask(realTask);
                this._updateTaskInDOM(taskId, realTask);
            } else {
                console.warn('⚠️ [Reconcile] Update response missing task ID, using taskId:', taskId);
            }
        }

        // CROWN⁴.13: Release action lock on successful sync
        if (operation.lockId && window.taskActionLock) {
            window.taskActionLock.release(operation.lockId);
            console.log(`🔓 [Reconcile] Released action lock ${operation.lockId}`);
        }

        // Remove operation from in-memory map
        this.pendingOperations.delete(opId);

        // Mark event as synced
        try {
            const events = await this.cache.getPendingEvents();
            const relatedEvent = events.find(e => e.task_id === taskId || e.task_id === operation.tempId);
            if (relatedEvent) {
                await this.cache.markEventSynced(relatedEvent.id);
            }
        } catch (eventError) {
            console.warn('⚠️ Failed to mark event as synced:', eventError);
        }
        
        // CROWN⁴.6: Refresh related widgets after successful sync
        // This ensures Meeting Heatmap, counters, and other widgets reflect the updated data
        this._refreshRelatedWidgets(type, taskId, serverData);
    }
    
    /**
     * CRITICAL FIX: Finalize task creation - replaces temp task with real task in DOM and cache
     * Called by _reconcileSuccess for all create paths (WebSocket, HTTP, duplicate)
     * @param {string} tempId - Temporary task ID
     * @param {Object} realTask - Server-confirmed task with real ID
     */
    async _finalizeCreate(tempId, realTask) {
        console.log(`🔧 [Finalize] Replacing temp ${tempId} with real task ${realTask.id}`);
        
        // Step 1: Update DOM - replace temp ID with real ID and clear syncing badge
        const card = document.querySelector(`[data-task-id="${tempId}"]`);
        if (card) {
            card.dataset.taskId = realTask.id;
            card.classList.remove('optimistic-create');
            
            // CRITICAL: Clear syncing badge
            const syncBadge = card.querySelector('.sync-status-badge');
            if (syncBadge) {
                syncBadge.remove();
                console.log(`✅ [Finalize] Cleared syncing badge for task ${realTask.id}`);
            }
            
            // Update any other temp-specific UI elements
            card.classList.remove('syncing');
            card.removeAttribute('data-temp-id');
        } else {
            console.warn(`⚠️ [Finalize] No card found for temp ID ${tempId}`);
        }

        // Step 2: Reconcile in cache - remove from temp_tasks, add to tasks
        try {
            await this.cache.reconcileTempTask(realTask.id, tempId);
            console.log(`✅ [Finalize] Cache reconciled for task ${realTask.id}`);
        } catch (cacheError) {
            console.error('❌ [Finalize] Cache reconciliation failed:', cacheError);
        }
        
        // Step 3: CROWN⁴.6 - Reconcile TaskStateStore (single source of truth)
        if (window.taskStateStore) {
            window.taskStateStore.reconcileTempTask(tempId, realTask.id, realTask);
            console.log(`✅ [Finalize] TaskStateStore reconciled: ${tempId} → ${realTask.id}`);
        }
        
        // Step 4: Update counters after successful finalization
        this._updateCounters();
    }
    
    /**
     * Refresh related widgets after successful task sync
     * CROWN⁴.6: Ensures cross-widget consistency after task changes
     * @param {string} type - Operation type (create, update, delete)
     * @param {number|string} taskId
     * @param {Object} serverData
     */
    _refreshRelatedWidgets(type, taskId, serverData) {
        // Debounce to prevent multiple rapid refreshes
        if (this._widgetRefreshTimeout) {
            clearTimeout(this._widgetRefreshTimeout);
        }
        
        this._widgetRefreshTimeout = setTimeout(() => {
            console.log(`🔄 [CROWN⁴.6] Refreshing related widgets after ${type} sync`);
            
            // 1. Refresh Meeting Heatmap (task counts per meeting)
            if (window.meetingHeatmap?.refresh) {
                window.meetingHeatmap.refresh().catch(err => {
                    console.warn('⚠️ Failed to refresh meeting heatmap:', err);
                });
            }
            
            // 2. Update tab counters (All/Active/Archived)
            this._updateCounters();
            
            // 3. Dispatch event for other widgets to react
            window.dispatchEvent(new CustomEvent('task:synced', {
                detail: { type, taskId, task: serverData?.task }
            }));
            
            // 4. Invalidate IndexedDB cache for meeting metrics
            if (this.cache?.invalidate) {
                this.cache.invalidate('meeting_metrics').catch(() => {});
            }
        }, 100); // 100ms debounce
    }

    /**
     * Reconcile failed server sync (rollback)
     * ENTERPRISE-GRADE: Marks temp tasks as 'failed' instead of deleting (prevents data loss)
     * CRITICAL: Keeps operation in pendingOperations for retry capability
     * @param {string} opId
     * @param {string} type
     * @param {number|string} taskId
     * @param {Error} error
     */
    async _reconcileFailure(opId, type, taskId, error) {
        const operation = this.pendingOperations.get(opId);
        if (!operation) {
            console.warn(`⚠️ No pending operation found for ${opId}`);
            return;
        }

        console.log(`🔄 [Offline-First] Handling ${type} failure:`, { opId, taskId, error: error.message });

        if (type === 'create') {
            // ENTERPRISE-GRADE: Mark temp task as 'failed' instead of deleting
            // This preserves user data across page refreshes and enables retry
            await this._rollbackCreate(operation.tempId, error);
        } else if (type === 'update') {
            // Rollback to previous state
            await this.cache.saveTask(operation.previous);
            this._updateTaskInDOM(taskId, operation.previous);
        } else if (type === 'delete') {
            // Restore deleted task
            await this.cache.saveTask(operation.task);
            this._addTaskToDOM(operation.task);
        }

        // CROWN⁴.13: Release action lock on failure (don't block future syncs)
        if (operation.lockId && window.taskActionLock) {
            window.taskActionLock.release(operation.lockId);
            console.log(`🔓 [Reconcile] Released action lock ${operation.lockId} after failure`);
        }

        // CRITICAL FIX: DO NOT delete operation from pendingOperations
        // Keep it so _retryOperation() can work after failure
        // Mark it as failed for tracking
        operation.failed = true;
        operation.lastError = error.message;
        operation.retryCount = (operation.retryCount || 0) + 1;
        
        console.log(`✅ [Offline-First] Operation ${opId} marked as failed (retry count: ${operation.retryCount})`);
        
        // ENTERPRISE-GRADE: Persist failed state to IndexedDB for post-refresh retry
        if (this.cache) {
            await this.cache.savePendingOperation(opId, operation).catch(err => {
                console.error('❌ Failed to persist failed operation state:', err);
            });
        }

        // Show detailed error notification
        const errorMsg = error.message || 'Unknown error';
        this._showErrorNotification(`Failed to ${type} task. You can retry when online.`, errorMsg);
        
        console.log(`✅ [Offline-First] Failure handling complete for operation ${opId}`);
    }

    /**
     * Rollback task creation - ENTERPRISE-GRADE offline-first pattern
     * Marks temp task as 'failed' instead of deleting (preserves data for retry)
     * @param {string} tempId
     * @param {Error} error
     */
    async _rollbackCreate(tempId, error) {
        console.log(`🔄 [Offline-First] Marking temp task ${tempId} as FAILED (not deleting)`);
        
        // Update task sync_status to 'failed' in IndexedDB
        await this.cache.updateTempTaskStatus(tempId, 'failed', error.message);
        
        // Update DOM to show failed state (add badge/indicator)
        const card = document.querySelector(`[data-task-id="${tempId}"]`);
        if (card) {
            card.classList.remove('optimistic-create');
            card.classList.add('sync-failed');
            
            // Add failed badge to card
            const existingBadge = card.querySelector('.sync-status-badge');
            if (existingBadge) {
                existingBadge.remove();
            }
            
            const badge = document.createElement('div');
            badge.className = 'sync-status-badge failed';
            badge.innerHTML = `
                <span class="badge-icon">⚠️</span>
                <span class="badge-text">Sync Failed</span>
                <button class="retry-btn" onclick="window.optimisticUI._retryOperation('${card.dataset.operationId}')">
                    Retry
                </button>
            `;
            
            const cardHeader = card.querySelector('.task-card-header') || card;
            cardHeader.appendChild(badge);
        }
        
        console.log(`✅ [Offline-First] Temp task ${tempId} marked as failed (preserved in IndexedDB)`);
    }

    /**
     * Show error notification
     * @param {string} message
     * @param {string} detail - Optional detailed error message
     */
    _showErrorNotification(message, detail = null) {
        console.error(`🚨 Error notification: ${message}`, detail ? `(${detail})` : '');
        
        if (window.showToast) {
            window.showToast(message, 'error');
        } else {
            console.error(message);
        }
    }

    /**
     * Escape HTML
     * @param {string} text
     * @returns {string}
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export class for orchestrator
window.OptimisticUI = OptimisticUI;

// CROWN⁴.10 SINGLETON GUARD: Prevent double instantiation
if (!window.__minaOptimisticUIInstantiated) {
    // Auto-instantiate if taskCache is ready
    if (window.taskCache && window.taskCache.ready) {
        window.__minaOptimisticUIInstantiated = true;
        window.optimisticUI = new OptimisticUI();
        console.log('⚡ CROWN⁴.5 OptimisticUI loaded (auto-instantiated, singleton)');
    } else {
        console.log('⚡ CROWN⁴.5 OptimisticUI class loaded (orchestrator will instantiate)');
    }
} else {
    console.warn('⚠️ [OptimisticUI] BLOCKED duplicate instantiation attempt');
}
