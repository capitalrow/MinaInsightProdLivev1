/**
 * TaskErrorHandler - Unified Error Handling & Retry System
 * CROWN⁴.9 Phase 9: Error States & Retry
 * 
 * Features:
 * - Inline error messages with retry buttons on task cards
 * - Network error detection and recovery
 * - Graceful degradation when operations fail
 * - User-friendly error messaging
 * - Automatic retry with exponential backoff
 */

class TaskErrorHandler {
    constructor() {
        this.activeErrors = new Map();
        this.retryQueue = new Map();
        this.maxRetries = 3;
        this.baseDelay = 1000;
        this.isOnline = navigator.onLine;
        this.connectionBanner = null;
        this.init();
    }

    init() {
        console.log('[TaskErrorHandler] Initializing error handling system...');
        
        this.connectionBanner = document.getElementById('connection-banner');
        
        window.addEventListener('online', () => this.handleOnline());
        window.addEventListener('offline', () => this.handleOffline());
        
        window.addEventListener('task:operation-failed', (e) => {
            this.handleOperationError(e.detail);
        });
        
        if (!navigator.onLine) {
            this.handleOffline();
        }
        
        console.log('[TaskErrorHandler] Initialized successfully');
    }

    handleOnline() {
        console.log('[TaskErrorHandler] Network restored');
        this.isOnline = true;
        this.updateConnectionBanner('online', 'Back online');
        
        setTimeout(() => {
            this.hideConnectionBanner();
        }, 3000);
        
        this.retryPendingOperations();
    }

    handleOffline() {
        console.log('[TaskErrorHandler] Network lost');
        this.isOnline = false;
        this.updateConnectionBanner('offline', 'You\'re offline. Changes will sync when you reconnect.');
    }

    updateConnectionBanner(status, message) {
        if (!this.connectionBanner) {
            this.connectionBanner = document.getElementById('connection-banner');
        }
        
        if (!this.connectionBanner) return;
        
        this.connectionBanner.classList.remove('hidden', 'online', 'offline', 'reconnecting');
        this.connectionBanner.classList.add(status);
        
        const messageEl = this.connectionBanner.querySelector('.connection-message');
        if (messageEl) {
            messageEl.textContent = message;
        }
        
        const pendingCount = this.connectionBanner.querySelector('.pending-count');
        if (pendingCount) {
            const count = this.retryQueue.size;
            pendingCount.textContent = count > 0 ? `(${count} pending)` : '';
        }
    }

    hideConnectionBanner() {
        if (this.connectionBanner) {
            this.connectionBanner.classList.add('hidden');
        }
    }

    async retryPendingOperations() {
        if (this.retryQueue.size === 0) return;
        
        console.log(`[TaskErrorHandler] Retrying ${this.retryQueue.size} pending operations`);
        this.updateConnectionBanner('reconnecting', 'Syncing changes...');
        
        const operations = Array.from(this.retryQueue.entries());
        for (const [id, operation] of operations) {
            try {
                await operation.retryFn();
                this.retryQueue.delete(id);
                this.clearInlineError(operation.taskId);
                console.log(`[TaskErrorHandler] Retry succeeded for ${id}`);
            } catch (error) {
                console.error(`[TaskErrorHandler] Retry failed for ${id}:`, error);
            }
        }
        
        if (this.retryQueue.size === 0) {
            this.updateConnectionBanner('online', 'All changes synced');
            setTimeout(() => this.hideConnectionBanner(), 2000);
        }
    }

    handleOperationError({ taskId, action, error, retryFn, originalData }) {
        console.error(`[TaskErrorHandler] Operation failed:`, { taskId, action, error: error?.message });
        
        const errorType = this.classifyError(error);
        const userMessage = this.getUserFriendlyMessage(errorType, action);
        
        if (taskId) {
            this.showInlineError(taskId, userMessage, action, retryFn);
        } else {
            this.showNetworkError(userMessage, retryFn);
        }
        
        if (errorType === 'network' && retryFn) {
            const operationId = `${taskId || 'global'}-${action}-${Date.now()}`;
            this.retryQueue.set(operationId, { taskId, action, retryFn, originalData });
        }
        
        this.activeErrors.set(taskId || 'global', {
            action,
            error,
            timestamp: Date.now(),
            userMessage
        });
    }

    classifyError(error) {
        if (!navigator.onLine) return 'network';
        
        if (error instanceof TypeError && error.message.includes('fetch')) {
            return 'network';
        }
        
        const message = error?.message?.toLowerCase() || '';
        const status = error?.status || error?.response?.status;
        
        if (status === 401 || status === 403) return 'auth';
        if (status === 404) return 'not_found';
        if (status === 409) return 'conflict';
        if (status === 422) return 'validation';
        if (status >= 500) return 'server';
        if (message.includes('network') || message.includes('failed to fetch')) return 'network';
        if (message.includes('timeout')) return 'timeout';
        
        return 'unknown';
    }

    getUserFriendlyMessage(errorType, action) {
        const actionLabels = {
            'toggle-status': 'update status',
            'edit-title': 'save title',
            'priority': 'change priority',
            'due-date': 'set due date',
            'archive': 'archive task',
            'delete': 'delete task',
            'assign': 'assign task',
            'labels': 'update labels',
            'duplicate': 'duplicate task',
            'snooze': 'snooze task'
        };
        
        const actionLabel = actionLabels[action] || action || 'complete action';
        
        const messages = {
            network: `Could not ${actionLabel}. Check your connection.`,
            timeout: `Request timed out. Try again.`,
            auth: `Session expired. Please refresh.`,
            not_found: `Task not found. It may have been deleted.`,
            conflict: `Conflict detected. Please refresh.`,
            validation: `Invalid data. Please check and try again.`,
            server: `Server error. We're looking into it.`,
            unknown: `Could not ${actionLabel}. Please try again.`
        };
        
        return messages[errorType] || messages.unknown;
    }

    showInlineError(taskId, message, action, retryFn) {
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!taskCard) return;
        
        this.clearInlineError(taskId);
        
        taskCard.classList.add('has-error');
        
        const errorEl = document.createElement('div');
        errorEl.className = 'task-error-inline';
        errorEl.dataset.errorFor = taskId;
        
        errorEl.innerHTML = `
            <span class="task-error-icon">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
            </span>
            <span class="task-error-text">${message}</span>
            ${retryFn ? '<button class="task-error-retry-btn" aria-label="Retry">Retry</button>' : ''}
            <button class="task-error-dismiss-btn" aria-label="Dismiss error">
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        `;
        
        const taskContent = taskCard.querySelector('.task-content');
        if (taskContent) {
            taskContent.appendChild(errorEl);
        } else {
            taskCard.appendChild(errorEl);
        }
        
        const retryBtn = errorEl.querySelector('.task-error-retry-btn');
        if (retryBtn && retryFn) {
            retryBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await this.handleRetryClick(taskId, retryBtn, retryFn);
            });
        }
        
        const dismissBtn = errorEl.querySelector('.task-error-dismiss-btn');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.clearInlineError(taskId);
            });
        }
        
        const liveRegion = document.getElementById('task-list-live-region');
        if (liveRegion) {
            liveRegion.textContent = `Error: ${message}`;
        }
    }

    async handleRetryClick(taskId, button, retryFn) {
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        
        button.classList.add('loading');
        button.disabled = true;
        taskCard?.classList.add('retrying');
        
        try {
            await retryFn();
            this.clearInlineError(taskId);
            window.toast?.success('Action completed');
        } catch (error) {
            console.error('[TaskErrorHandler] Retry failed:', error);
            button.classList.remove('loading');
            button.disabled = false;
            window.toast?.error('Retry failed. Please try again.');
        } finally {
            taskCard?.classList.remove('retrying');
        }
    }

    clearInlineError(taskId) {
        const errorEl = document.querySelector(`.task-error-inline[data-error-for="${taskId}"]`);
        if (errorEl) {
            errorEl.remove();
        }
        
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (taskCard) {
            taskCard.classList.remove('has-error');
        }
        
        this.activeErrors.delete(taskId);
    }

    showNetworkError(message, retryFn) {
        let toast = document.querySelector('.network-error-toast');
        
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'network-error-toast';
            toast.innerHTML = `
                <div class="network-error-icon">
                    <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                </div>
                <div class="network-error-content">
                    <div class="network-error-title">Connection Issue</div>
                    <div class="network-error-message"></div>
                </div>
                <div class="network-error-actions">
                    <button class="network-error-retry">Retry</button>
                    <button class="network-error-dismiss">
                        <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
            `;
            document.body.appendChild(toast);
            
            toast.querySelector('.network-error-dismiss').addEventListener('click', () => {
                this.hideNetworkError();
            });
        }
        
        toast.querySelector('.network-error-message').textContent = message;
        
        const retryBtn = toast.querySelector('.network-error-retry');
        if (retryFn) {
            retryBtn.style.display = '';
            retryBtn.onclick = async () => {
                retryBtn.disabled = true;
                retryBtn.textContent = 'Retrying...';
                try {
                    await retryFn();
                    this.hideNetworkError();
                    window.toast?.success('Action completed');
                } catch (error) {
                    retryBtn.disabled = false;
                    retryBtn.textContent = 'Retry';
                }
            };
        } else {
            retryBtn.style.display = 'none';
        }
        
        requestAnimationFrame(() => {
            toast.classList.add('visible');
        });
    }

    hideNetworkError() {
        const toast = document.querySelector('.network-error-toast');
        if (toast) {
            toast.classList.remove('visible');
            toast.classList.add('hiding');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }
    }

    async withRetry(fn, options = {}) {
        const { maxRetries = this.maxRetries, taskId, action } = options;
        let lastError;
        
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                return await fn();
            } catch (error) {
                lastError = error;
                console.warn(`[TaskErrorHandler] Attempt ${attempt}/${maxRetries} failed:`, error.message);
                
                if (attempt < maxRetries) {
                    const delay = this.baseDelay * Math.pow(2, attempt - 1);
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
            }
        }
        
        window.dispatchEvent(new CustomEvent('task:operation-failed', {
            detail: { taskId, action, error: lastError, retryFn: fn }
        }));
        
        throw lastError;
    }

    clearAllErrors() {
        for (const [taskId] of this.activeErrors) {
            if (taskId !== 'global') {
                this.clearInlineError(taskId);
            }
        }
        this.hideNetworkError();
        this.activeErrors.clear();
    }
}

window.taskErrorHandler = new TaskErrorHandler();
console.log('[TaskErrorHandler] Global instance created');
