/**
 * CROWN⁴.5 Task Bulk Operations
 * Handles multi-select, bulk actions (complete, archive, delete), and visual feedback
 * Part of Phase 3 Task 8
 */

class TaskBulkOperations {
    constructor(optimisticUI) {
        this.optimisticUI = optimisticUI;
        this.selectedTasks = new Set();
        this.isSelectAllMode = false;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.renderBulkToolbar();
        
        // Listen for task renders to add checkboxes
        window.addEventListener('tasks:rendered', () => {
            this.addCheckboxesToTasks();
        });

        console.log('✅ TaskBulkOperations initialized');
    }

    setupEventListeners() {
        // Select all checkbox
        document.addEventListener('change', (e) => {
            if (e.target.id === 'bulk-select-all') {
                this.handleSelectAll(e.target.checked);
            }
        });

        // Individual task checkboxes
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('task-bulk-checkbox')) {
                const taskId = parseInt(e.target.dataset.taskId);
                if (e.target.checked) {
                    this.selectTask(taskId);
                } else {
                    this.deselectTask(taskId);
                }
            }
        });

        // Bulk action buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('#bulk-complete-btn')) {
                e.preventDefault();
                this.bulkComplete();
            } else if (e.target.closest('#bulk-archive-btn')) {
                e.preventDefault();
                this.bulkArchive();
            } else if (e.target.closest('#bulk-delete-btn')) {
                e.preventDefault();
                this.bulkDelete();
            } else if (e.target.closest('#bulk-cancel-btn')) {
                e.preventDefault();
                this.clearSelection();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Cmd/Ctrl+A: Select all
            if ((e.metaKey || e.ctrlKey) && e.key === 'a' && this.isTasksPageActive()) {
                e.preventDefault();
                this.selectAll();
            }
            // Escape: Clear selection
            if (e.key === 'Escape' && this.selectedTasks.size > 0) {
                this.clearSelection();
            }
        });
    }

    renderBulkToolbar() {
        const container = document.querySelector('.tasks-header') || document.querySelector('.tasks-page-header');
        if (!container) return;

        // Add bulk toolbar after the header
        const existingToolbar = document.getElementById('bulk-actions-toolbar');
        if (existingToolbar) return; // Already rendered

        const toolbar = document.createElement('div');
        toolbar.id = 'bulk-actions-toolbar';
        toolbar.className = 'bulk-actions-toolbar';
        toolbar.innerHTML = `
            <div class="bulk-toolbar-inner">
                <div class="bulk-select-section">
                    <label class="bulk-select-all-wrapper">
                        <input type="checkbox" id="bulk-select-all" class="bulk-checkbox">
                        <span class="bulk-select-label">Select All</span>
                    </label>
                    <span class="bulk-selected-count">0 selected</span>
                </div>
                <div class="bulk-actions-section" style="display: none;">
                    <button id="bulk-complete-btn" class="bulk-action-btn bulk-btn-success" title="Mark as completed">
                        <i data-feather="check-circle"></i>
                        Complete
                    </button>
                    <button id="bulk-archive-btn" class="bulk-action-btn bulk-btn-warning" title="Archive selected tasks">
                        <i data-feather="archive"></i>
                        Archive
                    </button>
                    <button id="bulk-delete-btn" class="bulk-action-btn bulk-btn-danger" title="Delete selected tasks">
                        <i data-feather="trash-2"></i>
                        Delete
                    </button>
                    <button id="bulk-cancel-btn" class="bulk-action-btn bulk-btn-secondary" title="Clear selection">
                        <i data-feather="x"></i>
                        Cancel
                    </button>
                </div>
            </div>
        `;

        container.after(toolbar);

        // Render feather icons
        if (window.feather) {
            feather.replace();
        }
    }

    addCheckboxesToTasks() {
        const taskCards = document.querySelectorAll('.task-card');
        taskCards.forEach(card => {
            const taskId = parseInt(card.dataset.taskId);
            
            // Skip if checkbox already exists
            if (card.querySelector('.task-bulk-checkbox')) return;

            // Create checkbox
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'task-bulk-checkbox';
            checkbox.dataset.taskId = taskId;
            checkbox.checked = this.selectedTasks.has(taskId);

            // Create wrapper
            const wrapper = document.createElement('div');
            wrapper.className = 'task-bulk-select';
            wrapper.appendChild(checkbox);

            // Insert at the beginning of the card
            card.insertBefore(wrapper, card.firstChild);

            // Update card styling if selected
            if (this.selectedTasks.has(taskId)) {
                card.classList.add('task-selected');
            }
        });
    }

    selectTask(taskId) {
        this.selectedTasks.add(taskId);
        this.updateUI();
        this.updateTaskCardSelection(taskId, true);
        
        // Track telemetry
        if (window.telemetry) {
            window.telemetry.track('task_selected', { task_id: taskId });
        }
    }

    deselectTask(taskId) {
        this.selectedTasks.delete(taskId);
        this.updateUI();
        this.updateTaskCardSelection(taskId, false);
    }

    selectAll() {
        const taskCards = document.querySelectorAll('.task-card:not([data-archived]):not([data-deleted])');
        taskCards.forEach(card => {
            const taskId = parseInt(card.dataset.taskId);
            this.selectedTasks.add(taskId);
            const checkbox = card.querySelector('.task-bulk-checkbox');
            if (checkbox) checkbox.checked = true;
            card.classList.add('task-selected');
        });
        
        this.isSelectAllMode = true;
        this.updateUI();

        // Track telemetry
        if (window.telemetry) {
            window.telemetry.track('bulk_select_all', { count: this.selectedTasks.size });
        }
    }

    handleSelectAll(checked) {
        if (checked) {
            this.selectAll();
        } else {
            this.clearSelection();
        }
    }

    clearSelection() {
        this.selectedTasks.clear();
        this.isSelectAllMode = false;
        
        // Uncheck all checkboxes
        document.querySelectorAll('.task-bulk-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        
        // Remove selected styling
        document.querySelectorAll('.task-card.task-selected').forEach(card => {
            card.classList.remove('task-selected');
        });
        
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
    }

    updateUI() {
        const count = this.selectedTasks.size;
        const countElement = document.querySelector('.bulk-selected-count');
        const actionsSection = document.querySelector('.bulk-actions-section');
        const selectAllCheckbox = document.getElementById('bulk-select-all');

        // Update count
        if (countElement) {
            countElement.textContent = count === 1 ? '1 selected' : `${count} selected`;
        }

        // Show/hide actions
        if (actionsSection) {
            actionsSection.style.display = count > 0 ? 'flex' : 'none';
        }

        // Update select all checkbox state
        if (selectAllCheckbox) {
            const taskCards = document.querySelectorAll('.task-card:not([data-archived]):not([data-deleted])');
            const allSelected = taskCards.length > 0 && count === taskCards.length;
            selectAllCheckbox.checked = allSelected;
            selectAllCheckbox.indeterminate = count > 0 && !allSelected;
        }
    }

    async bulkComplete() {
        if (this.selectedTasks.size === 0) return;

        const taskIds = Array.from(this.selectedTasks);

        try {
            // Show loading state
            this.setLoadingState(true);

            // Complete all selected tasks using completeTask helper
            // This ensures proper WebSocket/offline queue event propagation
            let completedCount = 0;
            for (const taskId of taskIds) {
                const taskBefore = await this.optimisticUI.cache.getTask(taskId);
                const wasCompleted = taskBefore && taskBefore.status === 'completed';
                
                await this.optimisticUI.completeTask(taskId);
                
                // Only count if it wasn't already completed
                if (!wasCompleted) {
                    completedCount++;
                }
            }

            // Show success toast
            if (window.toastManager && completedCount > 0) {
                window.toastManager.show({
                    message: `Completed ${completedCount} task${completedCount > 1 ? 's' : ''}`,
                    type: 'success',
                    duration: 3000
                });
            }

            // Track telemetry
            if (window.telemetry) {
                window.telemetry.track('bulk_complete', { 
                    total: taskIds.length,
                    completed: completedCount,
                    already_completed: taskIds.length - completedCount
                });
            }

            // Clear selection
            this.clearSelection();

        } catch (error) {
            console.error('Bulk complete failed:', error);
            if (window.toastManager) {
                window.toastManager.show({
                    message: 'Failed to complete tasks',
                    type: 'error',
                    duration: 4000
                });
            }
        } finally {
            this.setLoadingState(false);
        }
    }

    async bulkArchive() {
        if (this.selectedTasks.size === 0) return;

        const count = this.selectedTasks.size;

        // Show confirmation modal
        const confirmed = await this.showConfirmModal(
            'Archive Tasks',
            `Are you sure you want to archive ${count} task${count > 1 ? 's' : ''}?`,
            'Archive',
            'warning'
        );

        if (!confirmed) return;

        const taskIds = Array.from(this.selectedTasks);

        try {
            // Show loading state
            this.setLoadingState(true);

            // Optimistically archive all tasks
            for (const taskId of taskIds) {
                await this.optimisticUI.archiveTask(taskId);
            }

            // Show success toast with undo
            if (window.toastManager) {
                window.toastManager.show({
                    message: `Archived ${count} task${count > 1 ? 's' : ''}`,
                    type: 'success',
                    duration: 5000,
                    action: {
                        label: 'Undo',
                        callback: async () => {
                            for (const taskId of taskIds) {
                                await this.optimisticUI.unarchiveTask(taskId);
                            }
                        }
                    }
                });
            }

            // Track telemetry
            if (window.telemetry) {
                window.telemetry.track('bulk_archive', { count });
            }

            // Clear selection
            this.clearSelection();

        } catch (error) {
            console.error('Bulk archive failed:', error);
            if (window.toastManager) {
                window.toastManager.show({
                    message: 'Failed to archive tasks',
                    type: 'error',
                    duration: 4000
                });
            }
        } finally {
            this.setLoadingState(false);
        }
    }

    async bulkDelete() {
        if (this.selectedTasks.size === 0) return;

        const count = this.selectedTasks.size;

        // Show confirmation modal
        const confirmed = await this.showConfirmModal(
            'Delete Tasks',
            `Are you sure you want to delete ${count} task${count > 1 ? 's' : ''}? You can undo within 15 seconds.`,
            'Delete',
            'danger'
        );

        if (!confirmed) return;

        const taskIds = Array.from(this.selectedTasks);

        try {
            // Show loading state
            this.setLoadingState(true);

            // Optimistically delete all tasks
            for (const taskId of taskIds) {
                await this.optimisticUI.deleteTask(taskId);
            }

            // Show success toast with undo
            if (window.toastManager) {
                window.toastManager.show({
                    message: `Deleted ${count} task${count > 1 ? 's' : ''}`,
                    type: 'warning',
                    duration: 15000,
                    action: {
                        label: 'Undo',
                        callback: async () => {
                            for (const taskId of taskIds) {
                                await this.optimisticUI.restoreTask(taskId);
                            }
                        }
                    }
                });
            }

            // Track telemetry
            if (window.telemetry) {
                window.telemetry.track('bulk_delete', { count });
            }

            // Clear selection
            this.clearSelection();

        } catch (error) {
            console.error('Bulk delete failed:', error);
            if (window.toastManager) {
                window.toastManager.show({
                    message: 'Failed to delete tasks',
                    type: 'error',
                    duration: 4000
                });
            }
        } finally {
            this.setLoadingState(false);
        }
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
