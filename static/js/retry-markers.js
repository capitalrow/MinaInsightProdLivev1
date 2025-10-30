/**
 * CROWN⁴.5 Retry Markers
 * Visual indicators for failed task saves with retry functionality.
 * 
 * Features:
 * - "Needs attention" badge for failed saves
 * - Auto-retry with exponential backoff
 * - Manual retry button
 * - Error detail tooltips
 */

class RetryMarkers {
    constructor() {
        this.failedTasks = new Map();
        this.retryAttempts = new Map();
        this.maxRetries = 3;
        this.baseDelay = 1000; // 1 second
        
        this._setupListeners();
        console.log('[RetryMarkers] Initialized');
    }

    /**
     * Setup event listeners
     */
    _setupListeners() {
        // Listen for task save failures
        window.addEventListener('task_save_failed', (e) => {
            this.markTaskForRetry(e.detail);
        });

        // Listen for successful retries
        window.addEventListener('task_save_success', (e) => {
            this.clearRetryMarker(e.detail.task_id);
        });
    }

    /**
     * Mark task for retry
     * @param {Object} failureData - Failure data
     */
    markTaskForRetry(failureData) {
        const {
            task_id,
            error,
            operation,
            timestamp = Date.now()
        } = failureData;

        console.log(`[RetryMarkers] Task ${task_id} failed: ${error}`);

        // Store failure
        this.failedTasks.set(task_id, {
            error,
            operation,
            timestamp,
            retryCount: this.retryAttempts.get(task_id) || 0
        });

        // Show retry marker on task card
        this._showRetryMarker(task_id, error);

        // Attempt auto-retry
        this._scheduleRetry(task_id);
    }

    /**
     * Show retry marker on task card
     * @param {string} task_id
     * @param {string} error
     */
    _showRetryMarker(task_id, error) {
        const taskCard = document.querySelector(`[data-task-id="${task_id}"]`);
        if (!taskCard) return;

        // Remove existing marker
        const existing = taskCard.querySelector('.retry-marker');
        if (existing) existing.remove();

        // Create retry marker
        const marker = document.createElement('div');
        marker.className = 'retry-marker';
        marker.style.cssText = `
            position: absolute;
            top: 8px;
            right: 8px;
            background: #ef4444;
            color: white;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            z-index: 10;
            box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
            transition: all 200ms ease-out;
        `;

        const retryCount = this.retryAttempts.get(task_id) || 0;
        const isRetrying = retryCount > 0;

        marker.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                 ${isRetrying ? 'class="retry-spinner" style="animation: spin 1s linear infinite;"' : ''}>
                ${isRetrying ? `
                    <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
                ` : `
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                `}
            </svg>
            <span>${isRetrying ? `Retrying (${retryCount}/${this.maxRetries})` : 'Needs attention'}</span>
        `;

        // Add error tooltip
        marker.title = error || 'Save failed - click to retry';

        // Click to manually retry
        marker.addEventListener('click', (e) => {
            e.stopPropagation();
            this._manualRetry(task_id);
        });

        // Make task card position relative
        if (getComputedStyle(taskCard).position === 'static') {
            taskCard.style.position = 'relative';
        }

        taskCard.appendChild(marker);

        // Add visual indicator to task card
        taskCard.classList.add('has-retry-marker');
        taskCard.style.borderColor = '#ef4444';
        taskCard.style.boxShadow = '0 0 0 2px rgba(239, 68, 68, 0.2)';
    }

    /**
     * Clear retry marker
     * @param {string} task_id
     */
    clearRetryMarker(task_id) {
        const taskCard = document.querySelector(`[data-task-id="${task_id}"]`);
        if (!taskCard) return;

        // Remove marker
        const marker = taskCard.querySelector('.retry-marker');
        if (marker) {
            marker.style.opacity = '0';
            marker.style.transform = 'scale(0.8)';
            setTimeout(() => marker.remove(), 200);
        }

        // Remove visual indicators
        taskCard.classList.remove('has-retry-marker');
        taskCard.style.borderColor = '';
        taskCard.style.boxShadow = '';

        // Clear from maps
        this.failedTasks.delete(task_id);
        this.retryAttempts.delete(task_id);

        console.log(`[RetryMarkers] Cleared retry marker for task ${task_id}`);
    }

    /**
     * Schedule automatic retry with exponential backoff
     * @param {string} task_id
     */
    _scheduleRetry(task_id) {
        const retryCount = this.retryAttempts.get(task_id) || 0;

        if (retryCount >= this.maxRetries) {
            console.warn(`[RetryMarkers] Max retries reached for task ${task_id}`);
            this._showMaxRetriesError(task_id);
            return;
        }

        // Exponential backoff: 1s, 2s, 4s
        const delay = this.baseDelay * Math.pow(2, retryCount);

        console.log(`[RetryMarkers] Scheduling retry ${retryCount + 1}/${this.maxRetries} for task ${task_id} in ${delay}ms`);

        setTimeout(async () => {
            await this._executeRetry(task_id);
        }, delay);
    }

    /**
     * Execute retry attempt
     * @param {string} task_id
     * @returns {Promise<boolean>} Success
     */
    async _executeRetry(task_id) {
        const failureData = this.failedTasks.get(task_id);
        if (!failureData) return false;

        // Increment retry count
        const retryCount = (this.retryAttempts.get(task_id) || 0) + 1;
        this.retryAttempts.set(task_id, retryCount);

        // Update marker to show retrying state
        this._showRetryMarker(task_id, failureData.error);

        try {
            console.log(`[RetryMarkers] Attempting retry ${retryCount}/${this.maxRetries} for task ${task_id}`);

            // Attempt to replay the failed operation
            const success = await this._replayOperation(task_id, failureData.operation);

            if (success) {
                console.log(`[RetryMarkers] Retry successful for task ${task_id}`);
                this.clearRetryMarker(task_id);
                
                // Show success toast
                this._showToast('Changes saved successfully', 'success');
                
                return true;
            } else {
                console.warn(`[RetryMarkers] Retry ${retryCount} failed for task ${task_id}`);
                
                // Schedule next retry if not at max
                if (retryCount < this.maxRetries) {
                    this._scheduleRetry(task_id);
                } else {
                    this._showMaxRetriesError(task_id);
                }
                
                return false;
            }
        } catch (error) {
            console.error(`[RetryMarkers] Retry error for task ${task_id}:`, error);
            
            // Update failure data
            this.failedTasks.set(task_id, {
                ...failureData,
                error: error.message,
                retryCount
            });

            // Schedule next retry if not at max
            if (retryCount < this.maxRetries) {
                this._scheduleRetry(task_id);
            } else {
                this._showMaxRetriesError(task_id);
            }
            
            return false;
        }
    }

    /**
     * Replay failed operation
     * @param {string} task_id
     * @param {Object} operation
     * @returns {Promise<boolean>} Success
     */
    async _replayOperation(task_id, operation) {
        if (!operation) return false;

        // Get offline queue if available
        if (window.offlineQueue && typeof window.offlineQueue.replayItem === 'function') {
            return await window.offlineQueue.replayItem(operation);
        }

        // Fallback: Use optimistic UI if available
        if (window.optimisticUI && typeof window.optimisticUI.replayOperation === 'function') {
            return await window.optimisticUI.replayOperation(task_id, operation);
        }

        return false;
    }

    /**
     * Manual retry triggered by user
     * @param {string} task_id
     */
    async _manualRetry(task_id) {
        console.log(`[RetryMarkers] Manual retry requested for task ${task_id}`);
        
        // Reset retry count for manual retry
        this.retryAttempts.set(task_id, 0);
        
        await this._executeRetry(task_id);
    }

    /**
     * Show max retries error
     * @param {string} task_id
     */
    _showMaxRetriesError(task_id) {
        const failureData = this.failedTasks.get(task_id);
        
        this._showToast(
            `Failed to save task after ${this.maxRetries} attempts. Click "Needs attention" to retry.`,
            'error',
            5000
        );

        // Update marker to show manual retry needed
        this._showRetryMarker(task_id, failureData?.error || 'Max retries exceeded');
    }

    /**
     * Show toast notification
     * @param {string} message
     * @param {string} type
     * @param {number} duration
     */
    _showToast(message, type = 'info', duration = 3000) {
        if (window.showToast) {
            window.showToast(message, type, duration);
            return;
        }

        // Fallback toast
        console.log(`[RetryMarkers] Toast: ${message} (${type})`);
    }

    /**
     * Get retry statistics
     * @returns {Object} Stats
     */
    getStats() {
        return {
            failedTasks: this.failedTasks.size,
            totalRetryAttempts: Array.from(this.retryAttempts.values()).reduce((a, b) => a + b, 0),
            averageRetries: this.retryAttempts.size > 0
                ? Array.from(this.retryAttempts.values()).reduce((a, b) => a + b, 0) / this.retryAttempts.size
                : 0
        };
    }

    /**
     * Retry all failed tasks
     */
    async retryAll() {
        console.log(`[RetryMarkers] Retrying all ${this.failedTasks.size} failed tasks`);
        
        const promises = Array.from(this.failedTasks.keys()).map(task_id =>
            this._manualRetry(task_id)
        );

        await Promise.all(promises);
    }
}

// Add spinner animation styles
if (!document.getElementById('retry-markers-styles')) {
    const style = document.createElement('style');
    style.id = 'retry-markers-styles';
    style.textContent = `
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .retry-marker:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
        }
    `;
    document.head.appendChild(style);
}

// Initialize global instance
window.RetryMarkers = RetryMarkers;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.retryMarkers) {
            window.retryMarkers = new RetryMarkers();
            console.log('[RetryMarkers] Global instance created');
        }
    });
}
