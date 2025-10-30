/**
 * CROWN⁴.5 Idle Sync Timer
 * Background checksum reconciliation every 30 seconds.
 * Invisible operation that maintains continuous trust.
 * 
 * Features:
 * - 30s idle timer for automatic sync
 * - Checksum validation
 * - Delta pull for changes since last_event_id
 * - Silent operation (no UI disruption)
 */

class IdleSyncTimer {
    constructor(options = {}) {
        this.interval = options.interval || 30000; // 30 seconds
        this.enabled = options.enabled !== false;
        this.timer = null;
        this.lastSyncTime = null;
        this.lastEventId = null;
        this.isSyncing = false;
        
        // Metrics
        this.metrics = {
            totalSyncs: 0,
            checksumMismatches: 0,
            deltasPulled: 0,
            errors: 0
        };
        
        if (this.enabled) {
            this._start();
        }
        
        console.log('[IdleSyncTimer] Initialized (interval: 30s)');
    }

    /**
     * Start idle sync timer
     */
    _start() {
        if (this.timer) {
            clearInterval(this.timer);
        }

        this.timer = setInterval(() => {
            this._performSync();
        }, this.interval);

        console.log('[IdleSyncTimer] Started');
    }

    /**
     * Stop idle sync timer
     */
    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        console.log('[IdleSyncTimer] Stopped');
    }

    /**
     * Restart timer
     */
    restart() {
        this.stop();
        this._start();
    }

    /**
     * Perform background sync
     * @returns {Promise<Object>} Sync result
     */
    async _performSync() {
        if (this.isSyncing) {
            console.log('[IdleSyncTimer] Sync already in progress, skipping');
            return;
        }

        if (!navigator.onLine) {
            console.log('[IdleSyncTimer] Offline, skipping sync');
            return;
        }

        this.isSyncing = true;
        const startTime = Date.now();

        try {
            console.log('[IdleSyncTimer] Starting idle sync...');

            // Step 1: Get current cache checksum
            const cacheChecksum = await this._getCacheChecksum();
            
            // Step 2: Fetch server checksum
            const serverData = await this._fetchServerChecksum();
            const serverChecksum = serverData.checksum;
            
            // Step 3: Compare checksums
            if (cacheChecksum === serverChecksum) {
                console.log('[IdleSyncTimer] Checksums match - no drift detected ✓');
                this.metrics.totalSyncs++;
                this.lastSyncTime = Date.now();
                return {
                    success: true,
                    drift: false,
                    duration: Date.now() - startTime
                };
            }

            // Checksum mismatch - pull delta
            console.warn('[IdleSyncTimer] Checksum mismatch detected - pulling deltas');
            this.metrics.checksumMismatches++;

            // Step 4: Pull changes since last_event_id
            const delta = await this._pullDelta(this.lastEventId || serverData.last_event_id);
            
            // Step 5: Apply delta to cache
            if (delta.tasks && delta.tasks.length > 0) {
                await this._applyDelta(delta);
                this.metrics.deltasPulled += delta.tasks.length;
                
                console.log(`[IdleSyncTimer] Applied ${delta.tasks.length} delta changes`);
                
                // Trigger UI refresh
                this._triggerUIRefresh(delta);
            }

            // Update last event ID
            if (serverData.last_event_id) {
                this.lastEventId = serverData.last_event_id;
            }

            this.metrics.totalSyncs++;
            this.lastSyncTime = Date.now();

            return {
                success: true,
                drift: true,
                deltaCount: delta.tasks.length,
                duration: Date.now() - startTime
            };

        } catch (error) {
            console.error('[IdleSyncTimer] Sync failed:', error);
            this.metrics.errors++;
            
            return {
                success: false,
                error: error.message,
                duration: Date.now() - startTime
            };
        } finally {
            this.isSyncing = false;
        }
    }

    /**
     * Get cache checksum
     * @returns {Promise<string>} Checksum
     */
    async _getCacheChecksum() {
        if (window.taskCache && typeof window.taskCache.calculateChecksum === 'function') {
            return await window.taskCache.calculateChecksum();
        }
        
        // Fallback: return null if cache not available
        return null;
    }

    /**
     * Fetch server checksum and metadata
     * @returns {Promise<Object>} Server data
     */
    async _fetchServerChecksum() {
        const response = await fetch('/api/tasks/checksum', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`Checksum fetch failed: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * Pull delta changes since last_event_id
     * @param {number} sinceEventId - Last event ID
     * @returns {Promise<Object>} Delta data
     */
    async _pullDelta(sinceEventId) {
        const params = new URLSearchParams();
        if (sinceEventId) {
            params.append('since_event_id', sinceEventId);
        }

        const response = await fetch(`/api/tasks/delta?${params.toString()}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`Delta fetch failed: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * Apply delta to cache
     * @param {Object} delta - Delta changes
     * @returns {Promise<void>}
     */
    async _applyDelta(delta) {
        if (!window.taskCache) {
            console.warn('[IdleSyncTimer] Task cache not available');
            return;
        }

        // Apply task changes
        if (delta.tasks) {
            for (const task of delta.tasks) {
                if (task.deleted) {
                    await window.taskCache.deleteTask(task.id);
                } else {
                    await window.taskCache.updateTask(task);
                }
            }
        }

        // Recalculate cache checksum
        if (typeof window.taskCache.recalculateChecksum === 'function') {
            await window.taskCache.recalculateChecksum();
        }
    }

    /**
     * Trigger UI refresh after delta sync
     * @param {Object} delta - Delta changes
     */
    _triggerUIRefresh(delta) {
        // Dispatch custom event for UI to handle
        window.dispatchEvent(new CustomEvent('idle_sync_completed', {
            detail: {
                taskCount: delta.tasks.length,
                timestamp: Date.now()
            }
        }));

        // If task list renderer exists, trigger refresh
        if (window.taskListRenderer && typeof window.taskListRenderer.refresh === 'function') {
            window.taskListRenderer.refresh({ silent: true });
        }
    }

    /**
     * Get sync metrics
     * @returns {Object} Metrics
     */
    getMetrics() {
        return {
            ...this.metrics,
            lastSyncTime: this.lastSyncTime,
            lastEventId: this.lastEventId,
            enabled: this.enabled,
            interval: this.interval,
            avgSyncInterval: this.lastSyncTime ? (Date.now() - this.lastSyncTime) / 1000 : null
        };
    }

    /**
     * Force immediate sync
     * @returns {Promise<Object>} Sync result
     */
    async forceSync() {
        console.log('[IdleSyncTimer] Force sync requested');
        return await this._performSync();
    }

    /**
     * Enable idle sync
     */
    enable() {
        if (!this.enabled) {
            this.enabled = true;
            this._start();
            console.log('[IdleSyncTimer] Enabled');
        }
    }

    /**
     * Disable idle sync
     */
    disable() {
        if (this.enabled) {
            this.enabled = false;
            this.stop();
            console.log('[IdleSyncTimer] Disabled');
        }
    }
}

// Initialize global instance
window.IdleSyncTimer = IdleSyncTimer;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.idleSyncTimer) {
            window.idleSyncTimer = new IdleSyncTimer({
                interval: 30000, // 30 seconds
                enabled: true
            });
            console.log('[IdleSyncTimer] Global instance created');
        }
    });
}
