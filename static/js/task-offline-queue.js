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
                // Conflict detected
                const conflict = await response.json();
                return { success: false, conflict: true, data: conflict };
            }

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }

            const result = await response.json();

            // Update cache with server data
            if (type === 'task_create' && temp_id) {
                const realTask = result.task || result;
                await this.cache.deleteTask(temp_id);
                await this.cache.saveTask(realTask);
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
