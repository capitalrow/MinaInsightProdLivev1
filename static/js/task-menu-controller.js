/**
 * TaskMenuController - Unified Action Handler
 * Modern event delegation pattern for all 13 task menu actions
 * Follows Linear/Notion/Asana best practices
 */

class TaskMenuController {
    constructor() {
        this.menu = null;
        this.currentTaskId = null;
        this.isLoading = false;
        this.init();
    }

    init() {
        console.log('[TaskMenuController] Initializing unified controller...');
        // No global listener needed - TaskActionsMenu calls executeAction() directly
        console.log('[TaskMenuController] Initialized successfully - ready to handle actions');
    }

    /**
     * Action dispatcher - routes to appropriate handler
     */
    async executeAction(action, taskId) {
        // Prevent duplicate execution while loading
        if (this.isLoading) {
            console.warn('[TaskMenuController] Action already in progress');
            return;
        }

        try {
            this.setLoading(true, taskId);

            // Map action to handler method
            switch (action) {
                case 'view-details':
                    await this.handleViewDetails(taskId);
                    break;
                case 'edit':
                case 'edit-title':
                    await this.handleEdit(taskId);
                    break;
                case 'toggle-status':
                case 'toggle-complete':
                    await this.handleToggleStatus(taskId);
                    break;
                case 'priority':
                    await this.handlePriority(taskId);
                    break;
                case 'due-date':
                case 'set-due-date':
                    await this.handleDueDate(taskId);
                    break;
                case 'assign':
                    await this.handleAssign(taskId);
                    break;
                case 'labels':
                    await this.handleLabels(taskId);
                    break;
                case 'duplicate':
                    await this.handleDuplicate(taskId);
                    break;
                case 'snooze':
                    await this.handleSnooze(taskId);
                    break;
                case 'merge':
                    await this.handleMerge(taskId);
                    break;
                case 'jump-to-transcript':
                case 'jump':
                    await this.handleJumpToTranscript(taskId);
                    break;
                case 'archive':
                    await this.handleArchive(taskId);
                    break;
                case 'delete':
                    await this.handleDelete(taskId);
                    break;
                default:
                    console.warn('[TaskMenuController] Unknown action:', action);
                    window.toast?.error(`Unknown action: ${action}`);
            }
        } catch (error) {
            console.error('[TaskMenuController] Action execution failed:', error);
            window.toast?.error('Action failed. Please try again.');
        } finally {
            this.setLoading(false, taskId);
        }
    }

    /**
     * 1. VIEW DETAILS - Open task detail page
     */
    async handleViewDetails(taskId) {
        console.log(`[TaskMenuController] Opening details for task ${taskId}`);
        window.open(`/tasks/${taskId}`, '_blank');
    }

    /**
     * 2. EDIT TITLE - Inline title editing with optimistic UI
     */
    async handleEdit(taskId) {
        console.log(`[TaskMenuController] Editing title for task ${taskId}`);
        
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!taskCard) {
            window.toast?.error('Task not found');
            return;
        }

        const titleEl = taskCard.querySelector('.task-title-text');
        if (!titleEl) {
            window.toast?.error('Cannot find task title');
            return;
        }

        const currentTitle = titleEl.textContent.trim();
        
        // Create inline input
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentTitle;
        input.className = 'task-title-edit-input';
        input.style.cssText = `
            width: 100%;
            padding: 4px 8px;
            border: 1px solid var(--color-border-focus, #4a9eff);
            border-radius: 4px;
            font-size: inherit;
            font-family: inherit;
            background: var(--color-bg-input, #fff);
            color: var(--color-text-primary, #000);
        `;

        // Replace title with input
        titleEl.style.display = 'none';
        titleEl.parentNode.insertBefore(input, titleEl);
        input.focus();
        input.select();

        // Save on blur or Enter
        const save = async () => {
            const newTitle = input.value.trim();
            
            if (!newTitle || newTitle === currentTitle) {
                // Cancel - restore original
                input.remove();
                titleEl.style.display = '';
                return;
            }

            try {
                // Optimistic UI
                titleEl.textContent = newTitle;
                input.remove();
                titleEl.style.display = '';

                // API call
                await this.updateTask(taskId, { title: newTitle });
                
                window.toast?.success('Title updated');
            } catch (error) {
                // Rollback on error
                titleEl.textContent = currentTitle;
                window.toast?.error('Failed to update title');
            }
        };

        input.addEventListener('blur', save);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                save();
            } else if (e.key === 'Escape') {
                input.remove();
                titleEl.style.display = '';
            }
        });
    }

    /**
     * 3. TOGGLE STATUS - Mark complete/incomplete with checkbox animation
     */
    async handleToggleStatus(taskId) {
        console.log(`[TaskMenuController] Toggling status for task ${taskId}`);
        
        const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!taskCard) {
            window.toast?.error('Task not found');
            return;
        }

        const checkbox = taskCard.querySelector('.task-checkbox input[type="checkbox"]');
        if (!checkbox) {
            window.toast?.error('Cannot find task checkbox');
            return;
        }

        const currentStatus = checkbox.checked;
        const newStatus = !currentStatus;

        try {
            // Optimistic UI
            checkbox.checked = newStatus;
            
            if (newStatus) {
                taskCard.classList.add('task-completed');
            } else {
                taskCard.classList.remove('task-completed');
            }

            // API call
            await this.updateTask(taskId, { status: newStatus ? 'completed' : 'todo' });
            
            window.toast?.success(newStatus ? 'Task completed' : 'Task reopened');
        } catch (error) {
            // Rollback
            checkbox.checked = currentStatus;
            if (currentStatus) {
                taskCard.classList.add('task-completed');
            } else {
                taskCard.classList.remove('task-completed');
            }
            window.toast?.error('Failed to update status');
        }
    }

    /**
     * 4. PRIORITY - Change priority with visual selector
     */
    async handlePriority(taskId) {
        console.log(`[TaskMenuController] Changing priority for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            // Find the task card to use as trigger for positioning
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            const trigger = taskCard || document.body;

            // Use existing TaskPrioritySelector modal
            const newPriority = await window.taskPrioritySelector?.show(trigger);
            
            if (!newPriority || newPriority === undefined) {
                console.log('[TaskMenuController] Priority selection cancelled');
                return;
            }

            await this.updateTask(taskId, { priority: newPriority });
            
            // Update badge
            const priorityBadge = taskCard?.querySelector('.task-priority-badge');
            if (priorityBadge) {
                const priorityLabels = { high: 'High', medium: 'Medium', low: 'Low', urgent: 'Urgent' };
                priorityBadge.textContent = priorityLabels[newPriority] || newPriority;
                priorityBadge.className = `task-priority-badge priority-${newPriority}`;
            }

            window.toast?.success(`Priority updated to ${newPriority.charAt(0).toUpperCase() + newPriority.slice(1)}`);
        } catch (error) {
            window.toast?.error('Failed to update priority');
        }
    }

    /**
     * 5. DUE DATE - Set due date with date picker
     */
    async handleDueDate(taskId) {
        console.log(`[TaskMenuController] Setting due date for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            // Find the task card to use as trigger for positioning
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            const trigger = taskCard || document.body;

            // Use existing TaskDatePicker modal
            const newDate = await window.taskDatePicker?.show(trigger);
            
            if (newDate === undefined) {
                console.log('[TaskMenuController] Date selection cancelled');
                return;
            }

            await this.updateTask(taskId, { due_date: newDate || null });
            
            if (newDate) {
                const formattedDate = new Date(newDate).toLocaleDateString();
                window.toast?.success(`Due date set to ${formattedDate}`);
            } else {
                window.toast?.success('Due date cleared');
            }
        } catch (error) {
            window.toast?.error('Failed to update due date');
        }
    }

    /**
     * 6. ASSIGN - Open assignee selector modal
     */
    async handleAssign(taskId) {
        console.log(`[TaskMenuController] Opening assignee selector for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            // Use existing TaskAssigneeSelector modal
            const result = await window.taskAssigneeSelector?.show(task.assignee_ids || []);
            
            if (result === null || result === undefined) {
                console.log('[TaskMenuController] Assignee selection cancelled');
                return;
            }

            await this.updateTask(taskId, { assignee_ids: result });
            window.toast?.success('Assignees updated successfully');
        } catch (error) {
            window.toast?.error('Failed to update assignees');
        }
    }

    /**
     * 7. LABELS - Open labels editor modal
     */
    async handleLabels(taskId) {
        console.log(`[TaskMenuController] Opening labels editor for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            // Use existing TaskLabelsEditor modal
            const result = await window.taskLabelsEditor?.show(task.labels || []);
            
            if (result === null || result === undefined) {
                console.log('[TaskMenuController] Labels edit cancelled');
                return;
            }

            await this.updateTask(taskId, { labels: result });
            window.toast?.success('Labels updated successfully');
        } catch (error) {
            window.toast?.error('Failed to update labels');
        }
    }

    /**
     * 8. DUPLICATE - Duplicate task with confirmation
     */
    async handleDuplicate(taskId) {
        console.log(`[TaskMenuController] Duplicating task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            // Use existing TaskDuplicateConfirmation modal
            const confirmed = await window.taskDuplicateConfirmation?.show(task);
            
            if (!confirmed) {
                console.log('[TaskMenuController] Duplication cancelled');
                return;
            }

            // Create duplicate
            const duplicateData = {
                title: task.title ? `${task.title} [Copy]` : 'Untitled Task [Copy]',
                description: task.description,
                priority: task.priority,
                due_date: task.due_date,
                assignee_ids: task.assignee_ids,
                labels: task.labels,
                meeting_id: task.meeting_id,
                workspace_id: task.workspace_id
            };

            const response = await fetch('/api/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(duplicateData)
            });

            if (!response.ok) {
                throw new Error('Failed to duplicate task');
            }

            const data = await response.json();
            
            if (data.success) {
                window.toast?.success('Task duplicated successfully');
                
                // Refresh task list
                if (window.taskBootstrap) {
                    await window.taskBootstrap.bootstrap();
                }
            } else {
                throw new Error(data.error || 'Failed to duplicate task');
            }
        } catch (error) {
            window.toast?.error('Failed to duplicate task');
        }
    }

    /**
     * 9. SNOOZE - Snooze task with time picker
     */
    async handleSnooze(taskId) {
        console.log(`[TaskMenuController] Snoozing task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            // Use existing TaskSnoozeModal
            const snoozeUntil = await window.taskSnoozeModal?.show(task.snoozed_until);
            
            if (snoozeUntil === null || snoozeUntil === undefined) {
                console.log('[TaskMenuController] Snooze cancelled');
                return;
            }

            await this.updateTask(taskId, { snoozed_until: snoozeUntil });
            
            const snoozeDate = new Date(snoozeUntil).toLocaleString();
            window.toast?.success(`Task snoozed until ${snoozeDate}`);
        } catch (error) {
            window.toast?.error('Failed to snooze task');
        }
    }

    /**
     * 10. MERGE - Merge with another task
     */
    async handleMerge(taskId) {
        console.log(`[TaskMenuController] Merging task ${taskId}`);
        
        const sourceTask = await this.fetchTask(taskId);
        if (!sourceTask) return;

        try {
            // Use existing TaskMergeModal
            const targetTaskId = await window.taskMergeModal?.show(sourceTask);
            
            if (targetTaskId === null || targetTaskId === undefined) {
                console.log('[TaskMenuController] Merge cancelled');
                return;
            }

            // Try API endpoint first
            const response = await fetch('/api/tasks/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_task_id: taskId,
                    target_task_id: targetTaskId
                })
            });

            if (!response.ok) {
                // If merge endpoint doesn't exist, perform client-side merge
                if (response.status === 404) {
                    console.warn('[TaskMenuController] /api/tasks/merge not found, using client-side merge');
                    await this.performClientSideMerge(taskId, targetTaskId);
                    return;
                }
                throw new Error('Failed to merge tasks');
            }

            const data = await response.json();
            
            if (data.success) {
                window.toast?.success('Tasks merged successfully');
                
                // Refresh task list
                if (window.taskBootstrap) {
                    await window.taskBootstrap.bootstrap();
                }
            } else {
                throw new Error(data.error || 'Failed to merge tasks');
            }
        } catch (error) {
            window.toast?.error('Failed to merge tasks');
        }
    }

    /**
     * 11. JUMP TO TRANSCRIPT - Navigate to transcript section
     */
    async handleJumpToTranscript(taskId) {
        console.log(`[TaskMenuController] Jumping to transcript for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task || !task.meeting_id) {
            window.toast?.error('No transcript available for this task');
            return;
        }

        // Navigate to session transcript (sessions route uses meeting_id)
        window.location.href = `/sessions/${task.meeting_id}#transcript`;
    }

    /**
     * 12. ARCHIVE - Archive task with confirmation
     */
    async handleArchive(taskId) {
        console.log(`[TaskMenuController] Archiving task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            // Use existing confirmation modal
            const confirmed = await window.taskConfirmModal?.confirmArchive(task.title);
            
            if (!confirmed) {
                console.log('[TaskMenuController] Archive cancelled');
                return;
            }

            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);

            // Optimistic UI - fade out
            if (taskCard) {
                taskCard.style.opacity = '0.5';
                taskCard.style.pointerEvents = 'none';
            }

            try {
                await this.updateTask(taskId, { archived: true });

                // Remove from DOM
                if (taskCard) {
                    taskCard.style.transition = 'opacity 0.3s ease';
                    taskCard.style.opacity = '0';
                    setTimeout(() => taskCard.remove(), 300);
                }

                // Show toast with undo
                window.toast?.success('Task archived', 15000, {
                    undoCallback: async () => {
                        await this.updateTask(taskId, { archived: false });
                        if (window.taskBootstrap) {
                            await window.taskBootstrap.bootstrap();
                        }
                    }
                });
            } catch (error) {
                // Rollback
                if (taskCard) {
                    taskCard.style.opacity = '';
                    taskCard.style.pointerEvents = '';
                }
                throw error;
            }
        } catch (error) {
            window.toast?.error('Failed to archive task');
        }
    }

    /**
     * 13. DELETE - Permanently delete task with confirmation
     */
    async handleDelete(taskId) {
        console.log(`[TaskMenuController] Deleting task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            // Use existing confirmation modal
            const confirmed = await window.taskConfirmModal?.confirmDelete(task.title);
            
            if (!confirmed) {
                console.log('[TaskMenuController] Delete cancelled');
                return;
            }

            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);

            // Optimistic UI - fade out
            if (taskCard) {
                taskCard.style.opacity = '0.5';
                taskCard.style.pointerEvents = 'none';
            }

            try {
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    throw new Error('Failed to delete task');
                }

                // Remove from DOM
                if (taskCard) {
                    taskCard.style.transition = 'opacity 0.3s ease';
                    taskCard.style.opacity = '0';
                    setTimeout(() => taskCard.remove(), 300);
                }

                window.toast?.success('Task deleted');
            } catch (error) {
                // Rollback
                if (taskCard) {
                    taskCard.style.opacity = '';
                    taskCard.style.pointerEvents = '';
                }
                throw error;
            }
        } catch (error) {
            window.toast?.error('Failed to delete task');
        }
    }

    /**
     * Helper: Fetch task details from API
     */
    async fetchTask(taskId) {
        try {
            const response = await fetch(`/api/tasks/${taskId}`);
            if (!response.ok) {
                throw new Error('Failed to fetch task');
            }
            const data = await response.json();
            return data.task;
        } catch (error) {
            console.error('[TaskMenuController] Error fetching task:', error);
            window.toast?.error('Failed to fetch task details');
            return null;
        }
    }

    /**
     * Helper: Update task via PATCH API
     */
    async updateTask(taskId, updates) {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        if (!response.ok) {
            throw new Error('Failed to update task');
        }

        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Failed to update task');
        }

        return data.task;
    }

    /**
     * Helper: Client-side merge fallback
     */
    async performClientSideMerge(sourceTaskId, targetTaskId) {
        const [sourceTask, targetTask] = await Promise.all([
            this.fetchTask(sourceTaskId),
            this.fetchTask(targetTaskId)
        ]);

        if (!sourceTask || !targetTask) {
            throw new Error('Failed to fetch tasks for merge');
        }

        // Merge labels (unique union)
        const mergedLabels = [...new Set([
            ...(sourceTask.labels || []),
            ...(targetTask.labels || [])
        ])];

        // Use higher priority
        const priorities = { high: 3, medium: 2, low: 1 };
        const sourcePriority = priorities[(sourceTask.priority || 'medium').toLowerCase()] || 2;
        const targetPriority = priorities[(targetTask.priority || 'medium').toLowerCase()] || 2;
        const mergedPriority = sourcePriority >= targetPriority 
            ? sourceTask.priority 
            : targetTask.priority;

        // Update target task
        await this.updateTask(targetTaskId, {
            labels: mergedLabels,
            priority: mergedPriority
        });

        // Delete source task
        await fetch(`/api/tasks/${sourceTaskId}`, {
            method: 'DELETE'
        });

        window.toast?.success('Tasks merged successfully');

        // Refresh task list
        if (window.taskBootstrap) {
            await window.taskBootstrap.bootstrap();
        }
    }

    /**
     * Helper: Set loading state
     */
    setLoading(isLoading, taskId) {
        this.isLoading = isLoading;
        
        if (taskId) {
            const trigger = document.querySelector(`[data-task-id="${taskId}"] .task-menu-trigger`);
            if (trigger) {
                if (isLoading) {
                    trigger.classList.add('loading');
                    trigger.style.opacity = '0.6';
                    trigger.style.pointerEvents = 'none';
                } else {
                    trigger.classList.remove('loading');
                    trigger.style.opacity = '';
                    trigger.style.pointerEvents = '';
                }
            }
        }
    }

    /**
     * Helper: Close menu (no-op since TaskActionsMenu handles this)
     */
    closeMenu() {
        // Menu is already closed by TaskActionsMenu before actions execute
        // This method is kept for compatibility but does nothing
    }
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.taskMenuController = new TaskMenuController();
    });
} else {
    window.taskMenuController = new TaskMenuController();
}
