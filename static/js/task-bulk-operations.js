/**
 * CROWN⁴.5 Task Bulk Operations
 * Handles multi-select, bulk actions (complete, archive, delete, label), and visual feedback
 * Uses existing HTML toolbar from tasks.html template
 */

class TaskBulkOperations {
    constructor(optimisticUI) {
        this.optimisticUI = optimisticUI;
        this.selectedTasks = new Set();
        this.isSelectAllMode = false;
        this.isBulkMode = false;
        this.init();
    }

    init() {
        this.toolbar = document.getElementById('bulk-action-toolbar');
        this.countDisplay = document.getElementById('bulk-selected-count');
        
        this.setupEventListeners();
        
        window.addEventListener('tasks:rendered', () => {
            this.syncCheckboxStates();
        });

        console.log('[BulkOps] ✅ TaskBulkOperations initialized');
    }

    setupEventListeners() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('#bulk-complete-btn')) {
                e.preventDefault();
                this.bulkComplete();
            } else if (e.target.closest('#bulk-delete-btn')) {
                e.preventDefault();
                this.bulkDelete();
            } else if (e.target.closest('#bulk-label-btn')) {
                e.preventDefault();
                this.bulkAddLabel();
            } else if (e.target.closest('#bulk-cancel-btn')) {
                e.preventDefault();
                this.clearSelection();
            }
        });

        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('task-bulk-checkbox')) {
                const taskId = e.target.dataset.taskId;
                if (e.target.checked) {
                    this.selectTask(taskId);
                } else {
                    this.deselectTask(taskId);
                }
            }
        });

        document.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'a' && this.isTasksPageActive()) {
                e.preventDefault();
                this.toggleBulkMode();
            }
            if (e.key === 'Escape' && this.selectedTasks.size > 0) {
                this.clearSelection();
            }
        });

        document.addEventListener('click', (e) => {
            const card = e.target.closest('.task-card');
            if (!card) return;
            
            if (e.shiftKey && !e.target.closest('.task-checkbox')) {
                e.preventDefault();
                const taskId = card.dataset.taskId;
                this.toggleTaskSelection(taskId);
                return;
            }
            
            if (this.isBulkMode && !e.target.closest('.task-checkbox') && 
                !e.target.closest('.task-menu-trigger') && 
                !e.target.closest('.task-actions')) {
                e.preventDefault();
                e.stopPropagation();
                const taskId = card.dataset.taskId;
                this.toggleTaskSelection(taskId);
            }
        });

        this.setupLongPressHandler();
    }

    setupLongPressHandler() {
        let longPressTimer = null;
        let longPressTarget = null;
        const LONG_PRESS_DURATION = 500;

        const startLongPress = (e) => {
            const card = e.target.closest('.task-card');
            if (!card) return;
            
            if (e.target.closest('.task-checkbox') || 
                e.target.closest('.task-menu-trigger') ||
                e.target.closest('.task-actions')) return;

            longPressTarget = card;
            longPressTimer = setTimeout(() => {
                const taskId = card.dataset.taskId;
                
                if ('vibrate' in navigator) {
                    navigator.vibrate(50);
                }
                
                this.selectTask(taskId);
                card.classList.add('long-press-active');
                
                setTimeout(() => {
                    card.classList.remove('long-press-active');
                }, 300);
            }, LONG_PRESS_DURATION);
        };

        const cancelLongPress = () => {
            if (longPressTimer) {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            }
            longPressTarget = null;
        };

        document.addEventListener('touchstart', startLongPress, { passive: true });
        document.addEventListener('touchend', cancelLongPress);
        document.addEventListener('touchmove', cancelLongPress);
        document.addEventListener('touchcancel', cancelLongPress);
    }

    toggleBulkMode() {
        this.isBulkMode = !this.isBulkMode;
        
        if (this.isBulkMode) {
            this.selectAllVisible();
        } else {
            this.clearSelection();
        }
    }

    toggleTaskSelection(taskId) {
        if (this.selectedTasks.has(taskId)) {
            this.deselectTask(taskId);
        } else {
            this.selectTask(taskId);
        }
    }

    syncCheckboxStates() {
        document.querySelectorAll('.task-card').forEach(card => {
            const taskId = card.dataset.taskId;
            const isSelected = this.selectedTasks.has(taskId);
            const checkbox = card.querySelector('.task-bulk-checkbox');
            
            if (isSelected) {
                card.classList.add('task-selected');
            } else {
                card.classList.remove('task-selected');
            }
            
            if (checkbox) {
                checkbox.checked = isSelected;
            }
        });
    }

    selectTask(taskId) {
        this.selectedTasks.add(taskId);
        this.isBulkMode = true;
        this.updateUI();
        this.updateTaskCardSelection(taskId, true);
        
        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('bulk_task_selected', 1, { taskId });
        }
    }

    deselectTask(taskId) {
        this.selectedTasks.delete(taskId);
        this.updateUI();
        this.updateTaskCardSelection(taskId, false);
        
        if (this.selectedTasks.size === 0) {
            this.isBulkMode = false;
        }
    }

    selectAllVisible() {
        const taskCards = document.querySelectorAll('.task-card:not(.is-hidden):not([data-status="completed"]):not([data-status="cancelled"])');
        taskCards.forEach(card => {
            const taskId = card.dataset.taskId;
            this.selectedTasks.add(taskId);
            card.classList.add('task-selected');
            
            const checkbox = card.querySelector('.task-bulk-checkbox');
            if (checkbox) {
                checkbox.checked = true;
            }
        });
        
        this.isSelectAllMode = true;
        this.updateUI();

        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('bulk_select_all', 1, { count: this.selectedTasks.size });
        }
    }

    clearSelection() {
        document.querySelectorAll('.task-card.task-selected').forEach(card => {
            card.classList.remove('task-selected');
            
            const checkbox = card.querySelector('.task-bulk-checkbox');
            if (checkbox) {
                checkbox.checked = false;
            }
        });
        
        this.selectedTasks.clear();
        this.isSelectAllMode = false;
        this.isBulkMode = false;
        
        this.updateUI();
    }

    updateTaskCardSelection(taskId, selected) {
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (!card) return;

        if (selected) {
            card.classList.add('task-selected');
        } else {
            card.classList.remove('task-selected');
        }
        
        const checkbox = card.querySelector('.task-bulk-checkbox');
        if (checkbox) {
            checkbox.checked = selected;
        }
    }

    updateUI() {
        const count = this.selectedTasks.size;
        
        if (this.countDisplay) {
            this.countDisplay.textContent = count;
        }

        if (this.toolbar) {
            if (count > 0) {
                this.toolbar.classList.remove('hidden');
            } else {
                this.toolbar.classList.add('hidden');
            }
        }
    }

    async bulkComplete() {
        if (this.selectedTasks.size === 0) return;

        const taskIds = Array.from(this.selectedTasks);
        const count = taskIds.length;

        try {
            this.setLoadingState(true);

            let completedCount = 0;
            for (const taskId of taskIds) {
                try {
                    if (this.optimisticUI?.completeTask) {
                        await this.optimisticUI.completeTask(taskId);
                    } else if (this.optimisticUI?.updateTask) {
                        await this.optimisticUI.updateTask(taskId, { 
                            status: 'completed',
                            completed_at: new Date().toISOString()
                        });
                    }
                    completedCount++;
                    
                    const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
                    if (card) {
                        card.classList.add('completed');
                        card.dataset.status = 'completed';
                    }
                } catch (err) {
                    console.error(`[BulkOps] Failed to complete task ${taskId}:`, err);
                }
            }

            if (window.toastManager && completedCount > 0) {
                window.toastManager.show(`Completed ${completedCount} task${completedCount > 1 ? 's' : ''}`, 'success', 3000);
            }

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('bulk_complete', 1, { count: completedCount });
            }

            this.clearSelection();

        } catch (error) {
            console.error('[BulkOps] Bulk complete failed:', error);
            if (window.toastManager) {
                window.toastManager.show('Failed to complete tasks', 'error', 4000);
            }
        } finally {
            this.setLoadingState(false);
        }
    }

    async bulkDelete() {
        if (this.selectedTasks.size === 0) return;

        const count = this.selectedTasks.size;

        const confirmed = await this.showConfirmModal(
            'Delete Tasks',
            `Are you sure you want to delete ${count} task${count > 1 ? 's' : ''}?`,
            'Delete',
            'danger'
        );

        if (!confirmed) return;

        const taskIds = Array.from(this.selectedTasks);

        try {
            this.setLoadingState(true);

            for (const taskId of taskIds) {
                try {
                    if (this.optimisticUI?.deleteTask) {
                        await this.optimisticUI.deleteTask(taskId);
                    } else {
                        const response = await fetch(`/api/tasks/${taskId}`, {
                            method: 'DELETE',
                            credentials: 'same-origin'
                        });
                        if (response.ok) {
                            const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
                            if (card) card.remove();
                        }
                    }
                } catch (err) {
                    console.error(`[BulkOps] Failed to delete task ${taskId}:`, err);
                }
            }

            if (window.toastManager) {
                window.toastManager.show(`Deleted ${count} task${count > 1 ? 's' : ''}`, 'success', 3000);
            }

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('bulk_delete', 1, { count });
            }

            this.clearSelection();

        } catch (error) {
            console.error('[BulkOps] Bulk delete failed:', error);
            if (window.toastManager) {
                window.toastManager.show('Failed to delete tasks', 'error', 4000);
            }
        } finally {
            this.setLoadingState(false);
        }
    }

    async bulkAddLabel() {
        if (this.selectedTasks.size === 0) return;

        const label = await this.showLabelInputModal();
        if (!label) return;

        const taskIds = Array.from(this.selectedTasks);
        const count = taskIds.length;

        try {
            this.setLoadingState(true);

            for (const taskId of taskIds) {
                try {
                    const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
                    let existingLabels = [];
                    try {
                        existingLabels = JSON.parse(card?.dataset.labels || '[]');
                    } catch (e) {}
                    
                    if (!existingLabels.includes(label)) {
                        const newLabels = [...existingLabels, label];
                        
                        if (this.optimisticUI?.updateTask) {
                            await this.optimisticUI.updateTask(taskId, { labels: newLabels });
                        } else {
                            await fetch(`/api/tasks/${taskId}`, {
                                method: 'PATCH',
                                headers: { 'Content-Type': 'application/json' },
                                credentials: 'same-origin',
                                body: JSON.stringify({ labels: newLabels })
                            });
                        }
                        
                        if (card) {
                            card.dataset.labels = JSON.stringify(newLabels);
                        }
                    }
                } catch (err) {
                    console.error(`[BulkOps] Failed to add label to task ${taskId}:`, err);
                }
            }

            if (window.toastManager) {
                window.toastManager.show(`Added label "${label}" to ${count} task${count > 1 ? 's' : ''}`, 'success', 3000);
            }

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('bulk_add_label', 1, { count, label });
            }

            this.clearSelection();

        } catch (error) {
            console.error('[BulkOps] Bulk add label failed:', error);
            if (window.toastManager) {
                window.toastManager.show('Failed to add labels', 'error', 4000);
            }
        } finally {
            this.setLoadingState(false);
        }
    }

    showLabelInputModal() {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'task-modal-overlay';
            
            overlay.innerHTML = `
                <div class="task-modal bulk-label-modal">
                    <div class="modal-header">
                        <h3 class="modal-title">Add Label</h3>
                        <button class="modal-close" aria-label="Close">
                            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                            </svg>
                        </button>
                    </div>
                    <div class="modal-body">
                        <input type="text" class="form-input label-input" placeholder="Enter label name..." maxlength="30" autofocus>
                        <div class="quick-labels">
                            <button class="quick-label-btn" data-label="urgent">Urgent</button>
                            <button class="quick-label-btn" data-label="follow-up">Follow-up</button>
                            <button class="quick-label-btn" data-label="blocked">Blocked</button>
                            <button class="quick-label-btn" data-label="review">Review</button>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary modal-cancel">Cancel</button>
                        <button class="btn-primary modal-confirm">Add Label</button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);

            requestAnimationFrame(() => overlay.classList.add('visible'));

            const input = overlay.querySelector('.label-input');
            const closeModal = (label) => {
                overlay.classList.remove('visible');
                setTimeout(() => {
                    overlay.remove();
                    resolve(label);
                }, 200);
            };

            input.focus();
            
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && input.value.trim()) {
                    closeModal(input.value.trim());
                }
            });

            overlay.querySelectorAll('.quick-label-btn').forEach(btn => {
                btn.addEventListener('click', () => closeModal(btn.dataset.label));
            });

            overlay.querySelector('.modal-cancel').addEventListener('click', () => closeModal(null));
            overlay.querySelector('.modal-close').addEventListener('click', () => closeModal(null));
            overlay.querySelector('.modal-confirm').addEventListener('click', () => {
                if (input.value.trim()) closeModal(input.value.trim());
            });
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) closeModal(null);
            });

            const escapeHandler = (e) => {
                if (e.key === 'Escape') {
                    closeModal(null);
                    document.removeEventListener('keydown', escapeHandler);
                }
            };
            document.addEventListener('keydown', escapeHandler);
        });
    }

    showConfirmModal(title, message, confirmText, variant = 'primary') {
        return new Promise((resolve) => {
            // Create modal overlay
            const overlay = document.createElement('div');
            overlay.className = 'task-modal-overlay';
            
            // Escape HTML to prevent XSS
            const escapeHtml = (str) => {
                const div = document.createElement('div');
                div.textContent = str;
                return div.innerHTML;
            };

            overlay.innerHTML = `
                <div class="task-modal">
                    <div class="modal-header">
                        <h3 class="modal-title">${escapeHtml(title)}</h3>
                        <button class="modal-close" aria-label="Close">
                            <i data-feather="x"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <p>${escapeHtml(message)}</p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary modal-cancel">Cancel</button>
                        <button class="btn-${variant} modal-confirm">${escapeHtml(confirmText)}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);

            // Render feather icons
            if (window.feather) {
                feather.replace();
            }

            // Animate in
            requestAnimationFrame(() => {
                overlay.classList.add('visible');
            });

            const closeModal = (confirmed) => {
                overlay.classList.remove('visible');
                setTimeout(() => {
                    overlay.remove();
                    resolve(confirmed);
                }, 200);
            };

            // Event listeners
            overlay.querySelector('.modal-cancel').addEventListener('click', () => closeModal(false));
            overlay.querySelector('.modal-close').addEventListener('click', () => closeModal(false));
            overlay.querySelector('.modal-confirm').addEventListener('click', () => closeModal(true));
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) closeModal(false);
            });

            // Escape key
            const escapeHandler = (e) => {
                if (e.key === 'Escape') {
                    closeModal(false);
                    document.removeEventListener('keydown', escapeHandler);
                }
            };
            document.addEventListener('keydown', escapeHandler);
        });
    }

    setLoadingState(loading) {
        const buttons = document.querySelectorAll('.bulk-action-btn');
        buttons.forEach(btn => {
            btn.disabled = loading;
            if (loading) {
                btn.classList.add('loading');
            } else {
                btn.classList.remove('loading');
            }
        });
    }

    isTasksPageActive() {
        const tasksContainer = document.getElementById('tasks-list-container');
        return tasksContainer && tasksContainer.offsetParent !== null;
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TaskBulkOperations;
}
