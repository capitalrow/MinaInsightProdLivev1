/**
 * CROWN⁴.13 Task Action Lock - Global Sync Protection
 * 
 * Prevents background sync systems (IdleSync, ReconciliationCycle, BroadcastSync)
 * from overwriting optimistic UI updates during active user interactions.
 * 
 * Pattern: All task mutations acquire a lock before making changes.
 * Sync systems check the lock before reconciling DOM.
 */

class TaskActionLock {
    constructor() {
        this._locks = new Map();
        this._globalLockTimestamp = 0;
        this._globalLockDuration = 3000;
        this._pendingOperations = new Set();
        this._listeners = new Set();
        
        console.log('[TaskActionLock] Initialized');
    }
    
    /**
     * Acquire a lock for a specific task
     * @param {string|number} taskId - Task ID to lock
     * @param {string} reason - Reason for lock (for debugging)
     * @returns {string} Lock ID for release
     */
    acquire(taskId, reason = 'unknown') {
        const lockId = `lock_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        const lockData = {
            taskId,
            reason,
            timestamp: Date.now(),
            lockId
        };
        
        this._locks.set(lockId, lockData);
        this._pendingOperations.add(taskId.toString());
        this._globalLockTimestamp = Date.now();
        
        console.log(`[TaskActionLock] Acquired lock ${lockId} for task ${taskId} (${reason})`);
        this._notifyListeners('acquired', lockData);
        
        return lockId;
    }
    
    /**
     * Release a lock
     * @param {string} lockId - Lock ID to release
     */
    release(lockId) {
        const lockData = this._locks.get(lockId);
        if (!lockData) {
            console.warn(`[TaskActionLock] Lock ${lockId} not found`);
            return;
        }
        
        this._locks.delete(lockId);
        
        const taskId = lockData.taskId.toString();
        const hasOtherLocks = Array.from(this._locks.values())
            .some(l => l.taskId.toString() === taskId);
        
        if (!hasOtherLocks) {
            this._pendingOperations.delete(taskId);
        }
        
        console.log(`[TaskActionLock] Released lock ${lockId} for task ${lockData.taskId}`);
        this._notifyListeners('released', lockData);
    }
    
    /**
     * Check if a specific task is locked
     * @param {string|number} taskId - Task ID to check
     * @returns {boolean}
     */
    isTaskLocked(taskId) {
        return this._pendingOperations.has(taskId.toString());
    }
    
    /**
     * Check if any locks are active (global lock check)
     * @returns {boolean}
     */
    isAnyLockActive() {
        if (this._locks.size > 0) {
            return true;
        }
        
        const elapsed = Date.now() - this._globalLockTimestamp;
        return elapsed < this._globalLockDuration;
    }
    
    /**
     * Check if sync should be blocked
     * Used by IdleSync, ReconciliationCycle, etc.
     * @returns {boolean}
     */
    shouldBlockSync() {
        const blocked = this.isAnyLockActive();
        const elapsed = Date.now() - this._globalLockTimestamp;
        const activeLocks = this._locks.size;
        
        if (blocked) {
            console.log(`[TaskActionLock] 🔒 Sync BLOCKED - ${activeLocks} active locks, ${elapsed}ms since last action`);
            if (activeLocks > 0) {
                const lockDetails = Array.from(this._locks.values())
                    .map(l => `Task ${l.taskId}: ${l.reason}`)
                    .join(', ');
                console.log(`[TaskActionLock] 📋 Active locks: ${lockDetails}`);
            }
        } else {
            console.log(`[TaskActionLock] ✅ Sync ALLOWED - ${elapsed}ms since last action (threshold: ${this._globalLockDuration}ms)`);
        }
        return blocked;
    }
    
    /**
     * Get list of pending task IDs (tasks with active operations)
     * @returns {Set<string>}
     */
    getPendingTaskIds() {
        return new Set(this._pendingOperations);
    }
    
    /**
     * Set global lock without specific task (for bulk operations)
     * @param {number} durationMs - Lock duration in milliseconds
     */
    setGlobalLock(durationMs = 3000) {
        this._globalLockTimestamp = Date.now();
        this._globalLockDuration = durationMs;
        console.log(`[TaskActionLock] Global lock set for ${durationMs}ms`);
    }
    
    /**
     * Add listener for lock events
     * @param {Function} callback - (event, lockData) => void
     */
    addListener(callback) {
        this._listeners.add(callback);
    }
    
    /**
     * Remove listener
     * @param {Function} callback
     */
    removeListener(callback) {
        this._listeners.delete(callback);
    }
    
    _notifyListeners(event, lockData) {
        for (const listener of this._listeners) {
            try {
                listener(event, lockData);
            } catch (e) {
                console.error('[TaskActionLock] Listener error:', e);
            }
        }
    }
    
    /**
     * Clear all locks (for cleanup/reset)
     */
    clearAll() {
        this._locks.clear();
        this._pendingOperations.clear();
        this._globalLockTimestamp = 0;
        console.log('[TaskActionLock] All locks cleared');
    }
    
    /**
     * Get debug info
     */
    getDebugInfo() {
        return {
            activeLocks: this._locks.size,
            pendingTasks: Array.from(this._pendingOperations),
            globalLockAge: Date.now() - this._globalLockTimestamp,
            isBlocking: this.shouldBlockSync()
        };
    }
}

window.taskActionLock = new TaskActionLock();
console.log('[TaskActionLock] Global instance created');
