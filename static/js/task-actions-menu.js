/**
 * CROWN⁴.5 Task Actions Menu
 * Provides edit, archive, and delete actions with confirmation modals
 */

class TaskActionsMenu {
    constructor(taskOptimisticUI) {
        this.taskUI = taskOptimisticUI;
        this.activeMenu = null;
        this.activeModal = null;
        this.init();
        console.log('[TaskActionsMenu] Initialized');
    }

    init() {
        // Click handler for menu trigger
        document.addEventListener('click', (e) => {
            const trigger = e.target.closest('.task-menu-trigger');
            if (trigger) {
                e.stopPropagation();
                this.toggleMenu(trigger);
                return;
            }

            // Close menu if clicking outside
            if (this.activeMenu && !e.target.closest('.task-menu')) {
                this.closeMenu();
            }

            // Handle menu item clicks
            const menuItem = e.target.closest('.task-menu-item');
            if (menuItem && !menuItem.classList.contains('disabled')) {
                e.preventDefault();
                const action = menuItem.dataset.action;
                const taskId = menuItem.dataset.taskId;
                this.handleMenuAction(action, taskId);
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Escape to close menu
            if (e.key === 'Escape') {
                if (this.activeModal) {
                    this.closeModal();
                } else if (this.activeMenu) {
                    this.closeMenu();
                }
            }

            // Delete key to delete focused task
            if (e.key === 'Delete' && !e.target.matches('input, textarea')) {
                const focusedCard = document.querySelector('.task-card:focus-within');
                if (focusedCard) {
                    const taskId = focusedCard.dataset.taskId;
                    if (taskId) {
                        e.preventDefault();
                        this.showDeleteConfirmation(taskId);
                    }
                }
            }

            // Ctrl/Cmd + E to edit (placeholder for Task 18)
            if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
                const focusedCard = document.querySelector('.task-card:focus-within');
                if (focusedCard && !e.target.matches('input, textarea')) {
                    e.preventDefault();
                    const taskId = focusedCard.dataset.taskId;
                    if (taskId) {
                        this.handleEdit(taskId);
                    }
                }
            }
        });

        // Close menu when scrolling
        document.addEventListener('scroll', () => {
            if (this.activeMenu) {
                this.closeMenu();
            }
        }, true);
    }

    /**
     * Toggle menu dropdown
     * @param {HTMLElement} trigger - Menu trigger button
     */
    toggleMenu(trigger) {
        console.log('[TaskActionsMenu] toggleMenu called');
        const taskId = trigger.dataset.taskId;
        console.log('[TaskActionsMenu] taskId:', taskId);
        console.log('[TaskActionsMenu] window.taskStore exists:', !!window.taskStore);
        
        const taskCard = trigger.closest('.task-card');
        if (!taskCard) {
            console.warn('[TaskActionsMenu] No task card found for trigger');
            return;
        }

        // Close existing menu if open
        if (this.activeMenu) {
            this.closeMenu();
            // If clicking same trigger, just close (don't reopen)
            if (this.activeMenu.dataset.taskId === taskId) {
                console.log('[TaskActionsMenu] Toggling same menu - closing only');
                return;
            }
        }

        // Get task data - but don't fail silently
        const task = window.taskStore?.getTask(taskId);
        console.log('[TaskActionsMenu] task data:', task);
        
        if (!task) {
            console.error('[TaskActionsMenu] Task not found in taskStore. TaskId:', taskId, 'TaskStore:', window.taskStore);
            // Continue anyway for debugging - create menu without task data
        }

        // Create menu
        const menu = document.createElement('div');
        menu.className = 'task-menu';
        menu.dataset.taskId = taskId;
        menu.innerHTML = `
            <div class="task-menu-item" data-action="edit" data-task-id="${taskId}">
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                </svg>
                <span>Edit details</span>
            </div>

            <div class="task-menu-item" data-action="duplicate" data-task-id="${taskId}">
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                </svg>
                <span>Duplicate</span>
            </div>

            <div class="task-menu-divider"></div>

            ${task?.status === 'completed' ? `
                <div class="task-menu-item" data-action="archive" data-task-id="${taskId}">
                    <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/>
                    </svg>
                    <span>Archive</span>
                </div>
            ` : ''}

            <div class="task-menu-item task-menu-item-danger" data-action="delete" data-task-id="${taskId}">
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
                <span>Delete</span>
            </div>
        `;

        // Position menu - append to body to avoid CSS clipping (Golden Standard)
        document.body.appendChild(menu);
        
        // Smart positioning with edge detection
        const triggerRect = trigger.getBoundingClientRect();
        const menuRect = menu.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const PADDING = 8; // Safe margin from viewport edges
        
        menu.style.position = 'fixed';
        menu.style.zIndex = '1000';
        
        // Vertical positioning: prefer below, flip to above if no space
        let top;
        const spaceBelow = viewportHeight - triggerRect.bottom;
        const spaceAbove = triggerRect.top;
        
        if (spaceBelow >= menuRect.height + PADDING) {
            // Enough space below
            top = triggerRect.bottom + 4;
        } else if (spaceAbove >= menuRect.height + PADDING) {
            // Not enough space below, flip to above
            top = triggerRect.top - menuRect.height - 4;
        } else {
            // Not enough space either way, center vertically with scrolling
            top = Math.max(PADDING, Math.min(triggerRect.bottom + 4, viewportHeight - menuRect.height - PADDING));
        }
        
        // Horizontal positioning: prefer right-aligned, flip to left if no space
        let left, right;
        const spaceRight = viewportWidth - triggerRect.right;
        const spaceLeft = triggerRect.left;
        
        if (spaceRight >= menuRect.width + PADDING) {
            // Enough space on right, align menu's right edge with trigger's right edge
            right = window.innerWidth - triggerRect.right;
            menu.style.right = right + 'px';
        } else if (spaceLeft >= menuRect.width + PADDING) {
            // Not enough space on right, align to left edge
            left = triggerRect.left;
            menu.style.left = left + 'px';
        } else {
            // Not enough space either way, align to right edge with padding
            right = PADDING;
            menu.style.right = right + 'px';
        }
        
        menu.style.top = top + 'px';
        
        console.log('[TaskActionsMenu] Menu positioned at:', {
            top: menu.style.top,
            left: menu.style.left || 'auto',
            right: menu.style.right || 'auto',
            spaceBelow,
            spaceAbove,
            menuHeight: menuRect.height
        });

        // Show menu with animation
        requestAnimationFrame(() => {
            menu.classList.add('visible');
            console.log('[TaskActionsMenu] Menu should be visible now');
        });

        // Update trigger state
        trigger.setAttribute('aria-expanded', 'true');

        this.activeMenu = menu;
    }

    /**
     * Close active menu
     */
    closeMenu() {
        if (!this.activeMenu) return;

        // Remove visible class for exit animation
        this.activeMenu.classList.remove('visible');

        // Update trigger state
        const trigger = document.querySelector('.task-menu-trigger[aria-expanded="true"]');
        if (trigger) {
            trigger.setAttribute('aria-expanded', 'false');
        }

        // Remove menu after animation
        setTimeout(() => {
            if (this.activeMenu && this.activeMenu.parentNode) {
                this.activeMenu.remove();
            }
            this.activeMenu = null;
        }, 200);
    }

    /**
     * Handle menu action
     * @param {string} action - Action type (edit, archive, delete, duplicate)
     * @param {string|number} taskId - Task ID
     */
    async handleMenuAction(action, taskId) {
        this.closeMenu();

        switch (action) {
            case 'view-details':
                this.handleViewDetails(taskId);
                break;
            case 'edit':
                this.handleEdit(taskId);
                break;
            case 'archive':
                this.handleArchive(taskId);
                break;
            case 'delete':
                this.showDeleteConfirmation(taskId);
                break;
            case 'duplicate':
                this.handleDuplicate(taskId);
                break;
            default:
                console.warn('[TaskActionsMenu] Unknown action:', action);
        }
    }

    /**
     * Handle view details action - opens task detail modal (CROWN⁴.5 Task 7)
     * @param {string|number} taskId - Task ID
     */
    handleViewDetails(taskId) {
        console.log('[TaskActionsMenu] Opening task detail modal for:', taskId);
        
        if (window.openTaskDetail) {
            window.openTaskDetail(taskId);
        } else {
            console.error('[TaskActionsMenu] Task detail modal not available');
            if (window.showToast) {
                window.showToast('Task detail modal not loaded', 'error');
            }
        }
    }

    /**
     * Handle edit action (inline title editing)
     * @param {string|number} taskId - Task ID
     */
    handleEdit(taskId) {
        console.log('[TaskActionsMenu] Edit task title:', taskId);
        
        // Trigger inline editing for the task title
        const taskCard = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (taskCard) {
            const titleEl = taskCard.querySelector('.task-title');
            if (titleEl) {
                if (window.taskInlineEditing) {
                    window.taskInlineEditing.editTitle(titleEl);
                } else {
                    titleEl.contentEditable = true;
                    titleEl.focus();
                    const range = document.createRange();
                    range.selectNodeContents(titleEl);
                    const selection = window.getSelection();
                    selection.removeAllRanges();
                    selection.addRange(range);
                }
            }
        }
    }

    /**
     * Handle archive action
     * @param {string|number} taskId - Task ID
     */
    async handleArchive(taskId) {
        const task = window.taskStore?.getTask(taskId);
        if (!task) return;

        try {
            await this.taskUI.archiveTask(taskId);
            
            if (window.toast) {
                window.toast.success('Task archived', 5000, {
                    undoCallback: async () => {
                        await this.taskUI.unarchiveTask(taskId);
                    },
                    undoText: 'Undo'
                });
            }

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_archived', 1);
            }
        } catch (error) {
            console.error('Failed to archive task:', error);
            if (window.toast) {
                window.toast.error('Failed to archive task');
            }
        }
    }

    /**
     * Show delete confirmation modal
     * @param {string|number} taskId - Task ID
     */
    showDeleteConfirmation(taskId) {
        const task = window.taskStore?.getTask(taskId);
        if (!task) return;

        this.showModal({
            title: 'Delete Task',
            message: `Delete "${task.title}"? This will move the task to trash. You'll have 15 seconds to undo.`,
            confirmText: 'Delete',
            confirmClass: 'btn-danger',
            onConfirm: async () => {
                try {
                    await this.taskUI.deleteTask(taskId);
                    
                    if (window.toast) {
                        window.toast.info('Task deleted', 15000, {
                            undoCallback: async () => {
                                await this.taskUI.restoreTask(taskId);
                            },
                            undoText: 'Undo'
                        });
                    }

                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('task_deleted', 1);
                    }
                } catch (error) {
                    console.error('Failed to delete task:', error);
                    if (window.toast) {
                        window.toast.error('Failed to delete task');
                    }
                }
            }
        });
    }

    /**
     * Handle duplicate action
     * @param {string|number} taskId - Task ID
     */
    async handleDuplicate(taskId) {
        const task = window.taskStore?.getTask(taskId);
        if (!task) return;

        try {
            const duplicateData = {
                title: `${task.title} (Copy)`,
                description: task.description,
                meeting_id: task.meeting_id,
                priority: task.priority,
                category: task.category,
                due_date: task.due_date,
                assigned_to_id: task.assigned_to_id,
                assignee_ids: task.assignee_ids,
                status: 'todo'
            };

            await this.taskUI.createTask(duplicateData);

            if (window.toast) {
                window.toast.success('Task duplicated');
            }

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_duplicated', 1);
            }
        } catch (error) {
            console.error('Failed to duplicate task:', error);
            if (window.toast) {
                window.toast.error('Failed to duplicate task');
            }
        }
    }

    /**
     * Show confirmation modal
     * @param {Object} options - Modal options
     */
    showModal({ title, message, confirmText, confirmClass = 'btn-primary', onConfirm }) {
        // Close existing modal
        if (this.activeModal) {
            this.closeModal();
        }

        const modal = document.createElement('div');
        modal.className = 'task-modal-overlay';
        modal.innerHTML = `
            <div class="task-modal">
                <div class="modal-header">
                    <h3>${this.escapeHtml(title)}</h3>
                    <button class="modal-close" aria-label="Close">
                        <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
                <div class="modal-body">
                    <p>${this.escapeHtml(message)}</p>
                </div>
                <div class="modal-footer">
                    <button class="modal-btn btn-secondary modal-cancel">Cancel</button>
                    <button class="modal-btn ${confirmClass} modal-confirm">${this.escapeHtml(confirmText)}</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Show with animation
        requestAnimationFrame(() => {
            modal.classList.add('visible');
        });

        // Event listeners
        const confirmBtn = modal.querySelector('.modal-confirm');
        const cancelBtn = modal.querySelector('.modal-cancel');
        const closeBtn = modal.querySelector('.modal-close');

        const confirm = async () => {
            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Processing...';
            await onConfirm();
            this.closeModal();
        };

        const cancel = () => {
            this.closeModal();
        };

        confirmBtn.addEventListener('click', confirm);
        cancelBtn.addEventListener('click', cancel);
        closeBtn.addEventListener('click', cancel);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) cancel();
        });

        this.activeModal = modal;
    }

    /**
     * Close active modal
     */
    closeModal() {
        if (!this.activeModal) return;

        this.activeModal.classList.remove('visible');
        setTimeout(() => {
            if (this.activeModal && this.activeModal.parentNode) {
                this.activeModal.remove();
            }
            this.activeModal = null;
        }, 200);
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

window.TaskActionsMenu = TaskActionsMenu;
