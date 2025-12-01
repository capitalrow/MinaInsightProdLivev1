/**
 * CROWN⁴.5 Idle Sync Service
 * Silently syncs with server every 30 seconds to maintain "Always true" state.
 * Uses exponential backoff on failures and pauses when user is actively editing.
 */

class IdleSyncService {
    constructor() {
        this.baseIntervalMs = 30000; // 30 seconds
        this.currentIntervalMs = 30000; // Current interval (grows with failures)
        this.maxIntervalMs = 300000; // Max 5 minutes
        this.intervalId = null;
        this.running = false;
        this.lastSyncTimestamp = null;
        this.consecutiveFailures = 0;
        this.userActivityDetected = false;
        this.activityTimeout = null;
        this.paused = false;
        
        this._registerActivityListeners();
    }

    /**
     * Start idle sync
     */
    start() {
        if (this.running) {
            console.log('⚠️ Idle sync already running');
            return;
        }

        console.log(`🔄 Starting idle sync (every ${this.currentIntervalMs / 1000}s)`);
        this.running = true;
        this.paused = false;

        // Run first sync immediately
        this._performSync();

        // Schedule periodic syncs
        this._scheduleNextSync();
    }

    /**
     * Schedule next sync with current interval
     */
    _scheduleNextSync() {
        if (this.intervalId) {
            clearTimeout(this.intervalId);
        }

        if (this.running) {
            this.intervalId = setTimeout(() => {
                this._performSync();
                this._scheduleNextSync();
            }, this.currentIntervalMs);
        }
    }

    /**
     * Stop idle sync
     */
    stop() {
        if (!this.running) {
            return;
        }

        console.log('⏸️ Stopping idle sync');
        this.running = false;

        if (this.intervalId) {
            clearTimeout(this.intervalId);
            this.intervalId = null;
        }
    }

    /**
     * Pause idle sync (e.g., when user is actively editing)
     */
    pause() {
        console.log('⏸️ Pausing idle sync (user active)');
        this.paused = true;
    }

    /**
     * Resume idle sync
     */
    resume() {
        console.log('▶️ Resuming idle sync');
        this.paused = false;
    }

    /**
     * Register activity listeners to detect user edits
     */
    _registerActivityListeners() {
        // Detect typing in inputs/textareas
        document.addEventListener('input', (event) => {
            if (event.target.matches('input, textarea')) {
                this._handleUserActivity();
            }
        });

        // Detect clicks (but not on read-only elements)
        document.addEventListener('click', (event) => {
            if (event.target.closest('.task-card, button, a')) {
                this._handleUserActivity();
            }
        });

        // Detect visibility changes
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                // Tab became visible - trigger immediate sync
                console.log('👁️ Tab visible - triggering sync');
                this._performSync({ force: true });
            }
        });

        // Detect online/offline
        window.addEventListener('online', () => {
            console.log('🌐 Connection restored - triggering sync');
            this.consecutiveFailures = 0;
            this._resetInterval();
            this._performSync({ force: true });
        });
    }

    /**
     * Handle user activity
     */
    _handleUserActivity() {
        this.userActivityDetected = true;
        this.pause();

        // Clear existing timeout
        if (this.activityTimeout) {
            clearTimeout(this.activityTimeout);
        }

        // Resume after 2 seconds of inactivity
        this.activityTimeout = setTimeout(() => {
            this.userActivityDetected = false;
            this.resume();
        }, 2000);
    }

    /**
     * Perform sync with server
     * @param {Object} options - { force: boolean }
     */
    async _performSync(options = {}) {
        const { force = false } = options;

        // Skip if paused (unless forced)
        if (this.paused && !force) {
            console.log('⏸️ Skipping sync - user active');
            return;
        }

        // Skip if offline
        if (!navigator.onLine) {
            console.log('📵 Skipping sync - offline');
            return;
        }

        const startTime = performance.now();
        console.log('🔄 [Idle Sync] Starting background sync...');

        try {
            // Step 1: Fetch tasks from server
            const response = await fetch('/api/tasks/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin',
                signal: AbortSignal.timeout(10000) // 10s timeout
            });

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }

            const data = await response.json();
            const serverTasks = data.tasks || [];
            const usersMap = data.users || {};  // CROWN⁴.8: Users map for rehydration

            // CROWN⁴.8: Rehydrate assigned_to from users map (Linear pattern)
            // This ensures assignee names persist through background syncs
            for (const task of serverTasks) {
                if (task.assigned_to_id && usersMap[task.assigned_to_id]) {
                    task.assigned_to = usersMap[task.assigned_to_id];
                }
                // Also rehydrate assignees array for multi-assignee support
                if (task.assignee_ids && task.assignee_ids.length > 0) {
                    task.assignees = task.assignee_ids
                        .map(id => usersMap[id])
                        .filter(Boolean);
                }
            }

            // Step 2: Update cache with server data (now with rehydrated user objects)
            if (window.taskCache) {
                await window.taskCache.saveTasks(serverTasks);
            }

            // Step 3: Reconcile DOM (only if visible and not actively editing)
            if (!document.hidden && !this.userActivityDetected) {
                await this._reconcileDOM(serverTasks);
            }

            // Update metadata
            this.lastSyncTimestamp = Date.now();
            this.consecutiveFailures = 0;
            this._resetInterval(); // Reset to base interval on success

            if (window.taskCache) {
                await window.taskCache.setMetadata('last_idle_sync', this.lastSyncTimestamp);
            }

            const syncTime = performance.now() - startTime;
            console.log(`✅ [Idle Sync] Completed in ${syncTime.toFixed(2)}ms (${serverTasks.length} tasks)`);

            // Telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('idle_sync_ms', syncTime);
                window.CROWNTelemetry.recordMetric('idle_sync_task_count', serverTasks.length);
                window.CROWNTelemetry.recordMetric('idle_sync_interval_ms', this.currentIntervalMs);
            }

            // Emit success event
            window.dispatchEvent(new CustomEvent('tasks:idle_sync:success', {
                detail: {
                    tasks: serverTasks,
                    sync_time_ms: syncTime,
                    timestamp: this.lastSyncTimestamp
                }
            }));

        } catch (error) {
            this.consecutiveFailures++;
            console.error(`❌ [Idle Sync] Failed (attempt ${this.consecutiveFailures}):`, error);

            // Apply exponential backoff: 30s → 60s → 120s → 240s → 300s (max)
            this._applyBackoff();

            // Emit error event
            window.dispatchEvent(new CustomEvent('tasks:idle_sync:error', {
                detail: {
                    error: error.message,
                    attempts: this.consecutiveFailures,
                    next_retry_ms: this.currentIntervalMs
                }
            }));

            console.log(`⏰ Next retry in ${this.currentIntervalMs / 1000}s (attempt ${this.consecutiveFailures})`);
        }
    }

    /**
     * Apply exponential backoff to interval
     * Progression: 30s → 60s → 120s → 240s → 300s (max)
     */
    _applyBackoff() {
        this.currentIntervalMs = Math.min(
            this.baseIntervalMs * Math.pow(2, this.consecutiveFailures),
            this.maxIntervalMs
        );
    }

    /**
     * Reset interval to base value
     */
    _resetInterval() {
        this.currentIntervalMs = this.baseIntervalMs;
        console.log(`✅ Sync interval reset to ${this.currentIntervalMs / 1000}s`);
    }

    /**
     * Reconcile DOM with server state
     * Only updates tasks that have changed (checksum comparison)
     * @param {Array} serverTasks
     */
    async _reconcileDOM(serverTasks) {
        if (!window.taskCache) {
            return;
        }

        const localTasks = await window.taskCache.getAllTasks();
        const serverTasksById = new Map(serverTasks.map(t => [t.id, t]));
        const localTasksById = new Map(localTasks.map(t => [t.id, t]));

        let updatedCount = 0;
        let addedCount = 0;
        let removedCount = 0;

        // CRITICAL FIX: If server returns 0 tasks but cache has tasks, force clear cache
        if (serverTasks.length === 0 && localTasks.length > 0) {
            console.log(`🧹 [Idle Sync] Force-clearing stale cache (${localTasks.length} orphaned tasks)`);
            
            // Clear all cached tasks
            await window.taskCache.clearAllTasks();
            
            // Clear all task cards from DOM
            const allCards = document.querySelectorAll('.task-card');
            allCards.forEach(card => {
                card.remove();
            });
            
            // Show empty state
            const emptyState = document.getElementById('tasks-empty-state');
            if (emptyState) {
                emptyState.style.display = 'block';
            }
            
            // Reset counters from DOM (after cards removed)
            if (window.taskBootstrap && typeof window.taskBootstrap._updateCountersFromDOM === 'function') {
                window.taskBootstrap._updateCountersFromDOM();
            }
            
            removedCount = localTasks.length;
            console.log(`✅ [Idle Sync] Cache cleared, ${removedCount} stale tasks removed`);
            
            // Telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordEvent('cache_force_clear', {
                    stale_task_count: removedCount
                });
            }
            
            return;
        }

        // Check for updates and additions
        for (const [taskId, serverTask] of serverTasksById) {
            const localTask = localTasksById.get(taskId);

            if (!localTask) {
                // New task from server
                if (window.optimisticUI && this._shouldShowTask(serverTask)) {
                    window.optimisticUI._addTaskToDOM(serverTask);
                    addedCount++;
                }
            } else {
                // Check if task changed (compare updated_at timestamp)
                const serverUpdated = new Date(serverTask.updated_at).getTime();
                const localUpdated = new Date(localTask.updated_at).getTime();

                if (serverUpdated > localUpdated) {
                    // Server has newer version
                    if (window.optimisticUI) {
                        window.optimisticUI._updateTaskInDOM(taskId, serverTask);
                        updatedCount++;
                    }
                }
            }
        }

        // Check for deletions
        for (const [taskId, localTask] of localTasksById) {
            if (!serverTasksById.has(taskId)) {
                // Task deleted on server - remove from cache AND DOM
                // Only remove if it's not a pending local creation (temp ID)
                if (!taskId.toString().startsWith('temp_')) {
                    // Remove from cache
                    await window.taskCache.deleteTask(taskId);
                    
                    // Remove from DOM
                    if (window.optimisticUI) {
                        window.optimisticUI._removeTaskFromDOM(taskId);
                    }
                    removedCount++;
                }
            }
        }

        // Update counters if any changes
        if (updatedCount > 0 || addedCount > 0 || removedCount > 0) {
            console.log(`🔄 [Idle Sync] DOM reconciled: ${addedCount} added, ${updatedCount} updated, ${removedCount} removed`);
            
            // CROWN⁴.6 FIX: Use DOM-based counter for single source of truth
            if (window.taskBootstrap && typeof window.taskBootstrap._updateCountersFromDOM === 'function') {
                window.taskBootstrap._updateCountersFromDOM();
            }

            // Telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('idle_sync_dom_changes', addedCount + updatedCount + removedCount);
            }
        }
    }

    /**
     * Check if task should be shown in current view
     * @param {Object} task
     * @returns {boolean}
     */
    _shouldShowTask(task) {
        // TODO: Implement filter logic
        return true;
    }

    /**
     * Force immediate sync
     * @returns {Promise<void>}
     */
    async forceSync() {
        console.log('⚡ Force sync requested');
        await this._performSync({ force: true });
    }

    /**
     * Get sync status
     * @returns {Object}
     */
    getStatus() {
        return {
            running: this.running,
            paused: this.paused,
            last_sync: this.lastSyncTimestamp,
            consecutive_failures: this.consecutiveFailures,
            interval_ms: this.intervalMs
        };
    }
}

// Export singleton
window.idleSyncService = new IdleSyncService();

// Auto-start on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.idleSyncService.start();
    });
} else {
    window.idleSyncService.start();
}

// Stop on unload
window.addEventListener('beforeunload', () => {
    if (window.idleSyncService) {
        window.idleSyncService.stop();
    }
});

console.log('⏰ CROWN⁴.5 Idle Sync Service loaded');
