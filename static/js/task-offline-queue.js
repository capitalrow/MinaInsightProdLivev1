/**
 * CROWN⁴.5 Offline Queue Manager
 * Manages offline operations with vector clock ordering and replay on reconnect.
 */

class OfflineQueueManager {
    constructor() {
        this.cache = window.taskCache;
        this.isOnline = navigator.onLine;
        this.replayInProgress = false;
        this.sessionId = this._generateSessionId();
        
        this._setupNetworkListeners();
    }

    /**
     * Generate unique session ID
     * @returns {string}
     */
    _generateSessionId() {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Setup online/offline event listeners
     */
    _setupNetworkListeners() {
        window.addEventListener('online', () => {
            console.log('🌐 Network online - triggering queue replay');
            this.isOnline = true;
            this.replayQueue();
        });

        window.addEventListener('offline', () => {
            console.log('📵 Network offline - queueing operations');
            this.isOnline = false;
        });
    }

    /**
     * Queue operation when offline
     * @param {Object} operation
     * @returns {Promise<number>} Queue ID
     */
    async queueOperation(operation) {
        const queueId = await this.cache.queueOfflineOperation({
            ...operation,
            session_id: this.sessionId,
            queued_at: Date.now()
        });

        console.log(`📥 Operation queued (ID: ${queueId}):`, operation.type);

        // Save queue to server for backup
        await this._backupQueueToServer();

        return queueId;
    }

    /**
     * Replay queued operations when back online
     * @returns {Promise<Object>} Replay results
     */
    async replayQueue() {
        if (this.replayInProgress) {
            console.log('⏳ Replay already in progress');
            return { skipped: true };
        }

        this.replayInProgress = true;
        const startTime = performance.now();

        try {
            // Get queue ordered by CROWN⁴.5 rules
            const queue = await this.cache.getOfflineQueue();

            if (queue.length === 0) {
                console.log('✅ Offline queue is empty');
                this.replayInProgress = false;
                return { success: true, replayed: 0 };
            }

            console.log(`🔄 Replaying ${queue.length} queued operations...`);

            const results = {
                success: 0,
                failed: 0,
                conflicts: 0,
                operations: []
            };

            // Replay operations in order
            for (const item of queue) {
                try {
                    const result = await this._replayOperation(item);
                    
                    if (result.success) {
                        results.success++;
                        await this.cache.removeFromQueue(item.id);
                    } else if (result.conflict) {
                        results.conflicts++;
                        // Keep in queue for manual resolution
                    } else {
                        results.failed++;
                    }

                    results.operations.push({
                        id: item.id,
                        type: item.type,
                        ...result
                    });

                } catch (error) {
                    console.error(`❌ Replay failed for operation ${item.id}:`, error);
                    results.failed++;
                }
            }

            const replayTime = performance.now() - startTime;
            console.log(`✅ Queue replay completed in ${replayTime.toFixed(2)}ms:`, results);

            // Clear queue backup on server
            await this._clearServerBackup();

            // Emit telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('queue_replay_ms', replayTime);
                window.CROWNTelemetry.recordMetric('queue_replay_count', results.success);
            }

            // Emit event
            window.dispatchEvent(new CustomEvent('tasks:queue:replayed', {
                detail: results
            }));

            return results;

        } finally {
            this.replayInProgress = false;
        }
    }

    /**
     * Replay single operation
     * @param {Object} item
     * @returns {Promise<Object>} Result
     */
    async _replayOperation(item) {
        const { type, data, task_id, temp_id } = item;

        try {
            // Sanitize data to remove cache-internal fields before server sync (CROWN⁴.5)
            const sanitizedData = window.TaskCache?.sanitizeForSync(data) || data;
            
            let response;

            switch (type) {
                case 'task_create':
                    response = await fetch('/api/tasks/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify(sanitizedData)
                    });
                    break;

                case 'task_update':
                    response = await fetch(`/api/tasks/${task_id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify(sanitizedData)
                    });
                    break;

                case 'task_delete':
                    response = await fetch(`/api/tasks/${task_id}`, {
                        method: 'DELETE',
                        credentials: 'same-origin'
                    });
                    break;

                case 'task_status_toggle':
                case 'task_priority_change':
                case 'task_snooze':
                case 'task_label_add':
                    response = await fetch(`/api/tasks/${task_id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify(sanitizedData)
                    });
                    break;

                default:
                    console.warn(`Unknown operation type: ${type}`);
                    return { success: false, error: 'Unknown operation type' };
            }

            if (response.status === 409) {
                // CROWN⁴.5: Deterministic conflict resolution using vector clocks
                const conflict = await response.json();
                console.warn(`⚠️ Conflict detected for ${type} on task ${task_id}`);
                
                const resolution = await this._resolveConflict(item, conflict);
                
                if (resolution.resolved) {
                    console.log(`✅ Conflict resolved: ${resolution.strategy}`);
                    return { success: true, conflict: true, resolution: resolution.strategy, data: resolution.data };
                } else {
                    console.error(`❌ Conflict unresolved - keeping in queue for manual resolution`);
                    return { success: false, conflict: true, data: conflict };
                }
            }

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }

            const result = await response.json();

            // CROWN⁴.5: Update cache with server data + temp ID reconciliation
            if (type === 'task_create' && temp_id) {
                const realTask = result.task || result;
                const realId = realTask.id;
                
                // 1. Reconcile temp ID to real ID
                if (this.cache.reconcileTempID) {
                    await this.cache.reconcileTempID(temp_id, realId);
                    console.log(`🔄 Offline replay: Reconciled ${temp_id} → ${realId}`);
                } else {
                    // Fallback if reconcileTempID not available
                    await this.cache.deleteTask(temp_id);
                    await this.cache.saveTask(realTask);
                }
                
                // 2. Broadcast reconciliation to other tabs via multi-tab sync
                if (window.multiTabSync) {
                    window.multiTabSync.broadcastIDReconciliation(temp_id, realId);
                }
                
                // 3. Update DOM if task card exists
                if (window.optimisticUI) {
                    const card = document.querySelector(`[data-task-id="${temp_id}"]`);
                    if (card) {
                        card.dataset.taskId = realId;
                        card.classList.remove('optimistic-create');
                        card.classList.add('reconciled');
                    }
                }
                
            } else if (type !== 'task_delete') {
                const task = result.task || result;
                await this.cache.saveTask(task);
            }

            return { success: true, data: result };

        } catch (error) {
            console.error(`Replay error for ${type}:`, error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Resolve conflicts deterministically using vector clocks (CROWN⁴.5)
     * @param {Object} localOp - Local operation from queue
     * @param {Object} serverConflict - Server conflict data
     * @returns {Promise<Object>} Resolution result
     */
    async _resolveConflict(localOp, serverConflict) {
        const { type, data, task_id, vector_clock } = localOp;
        const serverData = serverConflict.server_state || serverConflict;
        
        // Strategy 1: Vector clock comparison (deterministic ordering)
        if (vector_clock && serverConflict.vector_clock) {
            const localClock = new VectorClock(
                Array.isArray(vector_clock) 
                    ? Object.fromEntries(vector_clock) 
                    : vector_clock
            );
            const serverClock = new VectorClock(
                Array.isArray(serverConflict.vector_clock) 
                    ? Object.fromEntries(serverConflict.vector_clock) 
                    : serverConflict.vector_clock
            );
            
            const comparison = localClock.compare(serverClock);
            
            if (comparison === 1) {
                // Local change dominates - retry with force flag
                console.log('🔵 Local change dominates (vector clock)');
                try {
                    const response = await fetch(`/api/tasks/${task_id}`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Force-Update': 'true',
                            'X-Vector-Clock': JSON.stringify(localClock.toTuple())
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify(data)
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        await this.cache.saveTask(result.task || result);
                        return { resolved: true, strategy: 'vector_clock_local_wins', data: result };
                    }
                } catch (error) {
                    console.error('❌ Force update failed:', error);
                }
            } else if (comparison === -1) {
                // Server change dominates - accept server version
                console.log('🔴 Server change dominates (vector clock)');
                await this.cache.saveTask(serverData);
                return { resolved: true, strategy: 'vector_clock_server_wins', data: serverData };
            } else {
                // Concurrent changes - need merge strategy
                console.log('🟡 Concurrent changes detected - attempting merge');
            }
        }
        
        // Strategy 2: Last-write-wins based on timestamp (fallback)
        const localTimestamp = new Date(localOp.queued_at || 0).getTime();
        const serverTimestamp = new Date(serverData.updated_at || 0).getTime();
        
        if (localTimestamp > serverTimestamp) {
            console.log('🔵 Local change wins (timestamp)');
            try {
                const response = await fetch(`/api/tasks/${task_id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Conflict-Resolution': 'last-write-wins'
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    const result = await response.json();
                    await this.cache.saveTask(result.task || result);
                    return { resolved: true, strategy: 'timestamp_local_wins', data: result };
                }
            } catch (error) {
                console.error('❌ Timestamp resolution failed:', error);
            }
        } else {
            console.log('🔴 Server change wins (timestamp)');
            await this.cache.saveTask(serverData);
            return { resolved: true, strategy: 'timestamp_server_wins', data: serverData };
        }
        
        // Strategy 3: Field-level merge (for safe concurrent edits)
        if (type === 'task_update') {
            console.log('🟢 Attempting field-level merge');
            const merged = { ...serverData, ...data };
            
            try {
                const response = await fetch(`/api/tasks/${task_id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Conflict-Resolution': 'field-merge'
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(merged)
                });
                
                if (response.ok) {
                    const result = await response.json();
                    await this.cache.saveTask(result.task || result);
                    return { resolved: true, strategy: 'field_merge', data: result };
                }
            } catch (error) {
                console.error('❌ Field merge failed:', error);
            }
        }
        
        // Unresolved - keep in queue for manual intervention
        return { resolved: false, strategy: 'unresolved' };
    }

    /**
     * Backup queue to server for recovery
     * @returns {Promise<void>}
     */
    async _backupQueueToServer() {
        if (!this.isOnline) return;

        try {
            const queue = await this.cache.getOfflineQueue();
            
            // Use WebSocket to save queue
            if (window.tasksWS && window.tasksWS.connected) {
                window.tasksWS.emit('offline_queue:save', {
                    session_id: this.sessionId,
                    queue_data: queue
                });
            }
        } catch (error) {
            console.warn('⚠️ Failed to backup queue to server:', error);
        }
    }

    /**
     * Clear queue backup on server
     * @returns {Promise<void>}
     */
    async _clearServerBackup() {
        try {
            if (window.tasksWS && window.tasksWS.connected) {
                window.tasksWS.emit('offline_queue:clear', {
                    session_id: this.sessionId
                });
            }
        } catch (error) {
            console.warn('⚠️ Failed to clear server backup:', error);
        }
    }

    /**
     * Get queue status
     * @returns {Promise<Object>}
     */
    async getStatus() {
        const queue = await this.cache.getOfflineQueue();
        const pendingEvents = await this.cache.getPendingEvents();

        return {
            is_online: this.isOnline,
            queued_operations: queue.length,
            pending_events: pendingEvents.length,
            replay_in_progress: this.replayInProgress,
            session_id: this.sessionId
        };
    }

    /**
     * Clear entire queue (admin/debug only)
     * @returns {Promise<void>}
     */
    async clearQueue() {
        await this.cache.clearOfflineQueue();
        console.log('✅ Offline queue cleared');
    }
}

// Export singleton
window.offlineQueue = new OfflineQueueManager();

console.log('📱 CROWN⁴.5 OfflineQueue loaded');
