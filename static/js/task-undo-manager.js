/**
 * CROWN⁴.8 Task Undo Manager
 * Centralized undo system for all destructive task actions
 * 
 * Features:
 * - Toast notifications with undo buttons for delete/archive/complete
 * - Auto-dismiss after configurable timeout (default 8s)
 * - Queue system for multiple actions
 * - Keyboard shortcut support (Ctrl/Cmd+Z)
 * - Visual feedback during undo operation
 */

class TaskUndoManager {
    constructor() {
        this.container = null;
        this.undoStack = [];
        this.maxStackSize = 10;
        this.defaultTimeout = 8000;
        this.toasts = new Map();
        
        this.init();
    }
    
    init() {
        this.createContainer();
        this.attachKeyboardListener();
        this.attachEventListeners();
        
        console.log('[UndoManager] Initialized with undo stack support');
    }
    
    createContainer() {
        if (document.getElementById('undo-toast-container')) {
            this.container = document.getElementById('undo-toast-container');
            return;
        }
        
        this.container = document.createElement('div');
        this.container.id = 'undo-toast-container';
        this.container.className = 'undo-toast-container';
        this.container.setAttribute('role', 'region');
        this.container.setAttribute('aria-label', 'Undo notifications');
        document.body.appendChild(this.container);
    }
    
    attachKeyboardListener() {
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
                if (this.undoStack.length > 0 && !e.target.matches('input, textarea, [contenteditable]')) {
                    e.preventDefault();
                    this.undoLast();
                }
            }
        });
    }
    
    attachEventListeners() {
        window.addEventListener('task:deleted', (e) => {
            if (e.detail?.showUndo !== false) {
                this.recordAction('delete', e.detail.taskId, e.detail.task);
            }
        });
        
        window.addEventListener('task:archived', (e) => {
            if (e.detail?.showUndo !== false) {
                this.recordAction('archive', e.detail.taskId, e.detail.task);
            }
        });
        
        window.addEventListener('task:completed', (e) => {
            if (e.detail?.showUndo !== false) {
                this.recordAction('complete', e.detail.taskId, e.detail.task);
            }
        });
    }
    
    getIcon(type) {
        const icons = {
            delete: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>`,
            archive: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="21 8 21 21 3 21 3 8"></polyline>
                <rect x="1" y="3" width="22" height="5"></rect>
                <line x1="10" y1="12" x2="14" y2="12"></line>
            </svg>`,
            complete: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>`
        };
        return icons[type] || icons.archive;
    }
    
    getActionLabel(type) {
        const labels = {
            delete: 'deleted',
            archive: 'archived',
            complete: 'completed'
        };
        return labels[type] || 'updated';
    }
    
    recordAction(type, taskId, task, options = {}) {
        const id = `undo_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        const action = {
            id,
            type,
            taskId,
            task: { ...task },
            timestamp: Date.now(),
            timeout: options.timeout || this.defaultTimeout
        };
        
        this.undoStack.push(action);
        
        if (this.undoStack.length > this.maxStackSize) {
            this.undoStack.shift();
        }
        
        this.showToast(action);
        
        return id;
    }
    
    showToast(action) {
        const { id, type, task, timeout } = action;
        const taskTitle = task?.title || 'Task';
        const truncatedTitle = taskTitle.length > 40 ? taskTitle.substring(0, 40) + '...' : taskTitle;
        
        const toast = document.createElement('div');
        toast.className = 'undo-toast';
        toast.id = `toast-${id}`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'polite');
        toast.style.position = 'relative';
        
        toast.innerHTML = `
            <div class="undo-toast-icon ${type}">
                ${this.getIcon(type)}
            </div>
            <div class="undo-toast-content">
                <div class="undo-toast-title">Task ${this.getActionLabel(type)}</div>
                <div class="undo-toast-subtitle" title="${this.escapeHtml(taskTitle)}">${this.escapeHtml(truncatedTitle)}</div>
            </div>
            <div class="undo-toast-actions">
                <button class="undo-toast-btn" data-action-id="${id}" aria-label="Undo action">
                    Undo
                </button>
                <span class="undo-keyboard-hint">
                    <kbd>${navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}</kbd>+<kbd>Z</kbd>
                </span>
            </div>
            <button class="undo-toast-dismiss" aria-label="Dismiss notification">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
            <div class="undo-toast-progress" style="width: 100%"></div>
        `;
        
        this.container.appendChild(toast);
        
        const undoBtn = toast.querySelector('.undo-toast-btn');
        const dismissBtn = toast.querySelector('.undo-toast-dismiss');
        const progressBar = toast.querySelector('.undo-toast-progress');
        
        undoBtn.addEventListener('click', () => this.handleUndo(id, toast, undoBtn));
        dismissBtn.addEventListener('click', () => this.dismissToast(id));
        
        requestAnimationFrame(() => {
            toast.classList.add('visible');
        });
        
        progressBar.style.transition = `width ${timeout}ms linear`;
        requestAnimationFrame(() => {
            progressBar.style.width = '0%';
        });
        
        const timeoutId = setTimeout(() => {
            this.dismissToast(id);
        }, timeout);
        
        this.toasts.set(id, {
            element: toast,
            timeoutId,
            action
        });
    }
    
    async handleUndo(actionId, toast, button) {
        const toastData = this.toasts.get(actionId);
        if (!toastData) return;
        
        clearTimeout(toastData.timeoutId);
        
        button.classList.add('loading');
        button.disabled = true;
        
        try {
            await this.performUndo(toastData.action);
            
            toast.classList.add('undo-success');
            toast.querySelector('.undo-toast-title').textContent = 'Restored';
            button.style.display = 'none';
            
            setTimeout(() => {
                this.dismissToast(actionId);
            }, 1500);
            
        } catch (error) {
            console.error('[UndoManager] Undo failed:', error);
            button.classList.remove('loading');
            button.disabled = false;
            button.textContent = 'Retry';
            
            window.toast?.error('Failed to undo. Please try again.');
        }
    }
    
    async performUndo(action) {
        const { type, taskId, task } = action;
        
        console.log(`[UndoManager] Performing undo: ${type} for task ${taskId}`);
        
        switch (type) {
            case 'delete':
                await this.undoDelete(taskId, task);
                break;
            case 'archive':
                await this.undoArchive(taskId, task);
                break;
            case 'complete':
                await this.undoComplete(taskId, task);
                break;
            default:
                throw new Error(`Unknown action type: ${type}`);
        }
        
        const stackIndex = this.undoStack.findIndex(a => a.id === action.id);
        if (stackIndex > -1) {
            this.undoStack.splice(stackIndex, 1);
        }
        
        window.dispatchEvent(new CustomEvent('task:undone', {
            detail: { type, taskId, task }
        }));
    }
    
    async undoDelete(taskId, task) {
        if (window.optimisticUI?.restoreTask) {
            await window.optimisticUI.restoreTask(taskId);
        } else {
            const response = await fetch(`/api/tasks/${taskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    deleted_at: null,
                    deleted_by_user_id: null
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            if (window.taskBootstrap?.bootstrap) {
                await window.taskBootstrap.bootstrap();
            }
        }
    }
    
    async undoArchive(taskId, task) {
        const previousStatus = task?.previousStatus || 'todo';
        
        if (window.optimisticUI?.updateTask) {
            await window.optimisticUI.updateTask(taskId, {
                status: previousStatus,
                completed_at: null
            });
        } else {
            const response = await fetch(`/api/tasks/${taskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    status: previousStatus,
                    completed_at: null
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
        }
        
        if (window.taskBootstrap?.bootstrap) {
            await window.taskBootstrap.bootstrap();
        }
    }
    
    async undoComplete(taskId, task) {
        const previousStatus = task?.previousStatus || 'todo';
        
        if (window.optimisticUI?.updateTask) {
            await window.optimisticUI.updateTask(taskId, {
                status: previousStatus,
                completed_at: null
            });
        } else {
            const response = await fetch(`/api/tasks/${taskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    status: previousStatus,
                    completed_at: null
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
        }
        
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (taskCard) {
            taskCard.classList.remove('completed');
            taskCard.dataset.status = previousStatus;
            const checkbox = taskCard.querySelector('.task-checkbox');
            if (checkbox) checkbox.checked = false;
        }
    }
    
    dismissToast(actionId) {
        const toastData = this.toasts.get(actionId);
        if (!toastData) return;
        
        clearTimeout(toastData.timeoutId);
        
        const { element } = toastData;
        element.classList.remove('visible');
        element.classList.add('hiding');
        
        setTimeout(() => {
            if (element.parentNode) {
                element.remove();
            }
            this.toasts.delete(actionId);
        }, 300);
    }
    
    undoLast() {
        if (this.undoStack.length === 0) {
            console.log('[UndoManager] No actions to undo');
            return;
        }
        
        const lastAction = this.undoStack[this.undoStack.length - 1];
        const toastData = this.toasts.get(lastAction.id);
        
        if (toastData) {
            const undoBtn = toastData.element.querySelector('.undo-toast-btn');
            if (undoBtn) {
                this.handleUndo(lastAction.id, toastData.element, undoBtn);
            }
        } else {
            this.performUndo(lastAction).catch(err => {
                console.error('[UndoManager] Keyboard undo failed:', err);
                window.toast?.error('Failed to undo');
            });
        }
    }
    
    showUndoToast(type, taskId, task, options = {}) {
        return this.recordAction(type, taskId, task, options);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
    
    clearAll() {
        for (const [id] of this.toasts) {
            this.dismissToast(id);
        }
        this.undoStack = [];
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.undoManager = new TaskUndoManager();
    });
} else {
    window.undoManager = new TaskUndoManager();
}

window.TaskUndoManager = TaskUndoManager;
