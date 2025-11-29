/**
 * TaskMenuController - Unified Action Handler
 * Modern event delegation pattern for all 13 task menu actions
 * Follows Linear/Notion/Asana best practices
 * 
 * ROBUST FALLBACK SYSTEM:
 * - Each modal has browser-native fallback (prompt/confirm)
 * - Toast always available with fallback to alert
 * - Retry mechanism for failed operations
 */

class TaskMenuController {
    constructor() {
        this.menu = null;
        this.currentTaskId = null;
        this.isLoading = false;
        this.dependenciesReady = false;
        this.init();
    }

    init() {
        console.log('[TaskMenuController] Initializing unified controller...');
        
        // Listen for dependencies ready event
        document.addEventListener('tasks:dependencies-ready', (e) => {
            this.dependenciesReady = true;
            console.log('[TaskMenuController] Dependencies ready:', e.detail?.status);
        });
        
        // Check if already initialized
        if (window.tasksOrchestrator?.initialized) {
            this.dependenciesReady = true;
        }
        
        console.log('[TaskMenuController] Initialized successfully - ready to handle actions');
    }
    
    /**
     * ROBUST TOAST - Always works, even without toast module
     */
    showToast(message, type = 'info') {
        if (window.toast && typeof window.toast[type] === 'function') {
            window.toast[type](message);
        } else if (window.toast && typeof window.toast.show === 'function') {
            window.toast.show(message, type);
        } else {
            console.log(`[Toast ${type}] ${message}`);
            if (type === 'error') {
                alert(message);
            }
        }
    }
    
    /**
     * ROBUST CONFIRMATION - Falls back to browser confirm()
     */
    async confirm(message, title = 'Confirm') {
        if (window.taskConfirmModal?.confirm) {
            try {
                return await window.taskConfirmModal.confirm(message, title);
            } catch (e) {
                console.warn('[TaskMenuController] Modal confirm failed, using browser fallback');
            }
        }
        return window.confirm(message);
    }
    
    /**
     * ROBUST PROMPT - Falls back to browser prompt()
     */
    async prompt(message, defaultValue = '') {
        const result = window.prompt(message, defaultValue);
        return result;
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
        window.location.href = `/dashboard/tasks/${taskId}`;
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

                // Use OptimisticUI system (not raw fetch!)
                await window.optimisticUI.updateTask(taskId, { title: newTitle });
                
                // Toast handled by OptimisticUI system
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
     * Uses the same toggleTaskStatus() method as direct checkbox clicks for consistent animations
     */
    async handleToggleStatus(taskId) {
        console.log(`[TaskMenuController] Toggling status for task ${taskId}`);
        
        // Use the same optimistic UI toggle method as checkbox clicks
        // This ensures consistent animation (confetti) and visual feedback
        if (window.optimisticUI?.toggleTaskStatus) {
            try {
                await window.optimisticUI.toggleTaskStatus(taskId);
            } catch (error) {
                console.error('[TaskMenuController] Failed to toggle status:', error);
                window.toast?.error('Failed to update status');
            }
        } else {
            // Fallback if optimisticUI not available
            window.toast?.error('Task system not ready');
        }
    }

    /**
     * 4. PRIORITY - Change priority with visual selector (with browser fallback)
     */
    async handlePriority(taskId) {
        console.log(`[TaskMenuController] Changing priority for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            const trigger = taskCard || document.body;

            let newPriority;
            
            // Try custom modal first, fallback to browser prompt
            if (window.taskPrioritySelector?.show) {
                try {
                    newPriority = await window.taskPrioritySelector.show(trigger);
                } catch (e) {
                    console.warn('[TaskMenuController] Priority selector failed, using fallback');
                    newPriority = null;
                }
            }
            
            // Fallback: use browser prompt with options
            if (newPriority === undefined || newPriority === null) {
                if (!window.taskPrioritySelector) {
                    const currentPriority = task.priority || 'medium';
                    const choice = window.prompt(
                        `Set priority for "${task.title || 'Task'}":\n\nOptions: urgent, high, medium, low\n\nCurrent: ${currentPriority}`,
                        currentPriority
                    );
                    
                    if (choice && ['urgent', 'high', 'medium', 'low'].includes(choice.toLowerCase())) {
                        newPriority = choice.toLowerCase();
                    } else if (choice) {
                        this.showToast('Invalid priority. Choose: urgent, high, medium, or low', 'error');
                        return;
                    } else {
                        console.log('[TaskMenuController] Priority selection cancelled');
                        return;
                    }
                } else {
                    console.log('[TaskMenuController] Priority selection cancelled');
                    return;
                }
            }

            // Use OptimisticUI system
            if (window.optimisticUI?.updateTask) {
                await window.optimisticUI.updateTask(taskId, { priority: newPriority });
            } else {
                // Direct API fallback
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ priority: newPriority })
                });
                if (!response.ok) throw new Error('API call failed');
                this.showToast('Priority updated', 'success');
            }
            
            // Update DOM immediately for visual feedback
            const priorityBadge = taskCard?.querySelector('.task-priority-badge');
            if (priorityBadge) {
                const priorityLabels = { high: 'High', medium: 'Medium', low: 'Low', urgent: 'Urgent' };
                priorityBadge.textContent = priorityLabels[newPriority] || newPriority;
                priorityBadge.className = `task-priority-badge priority-${newPriority}`;
            }
        } catch (error) {
            console.error('[TaskMenuController] Priority update failed:', error);
            this.showToast('Failed to update priority', 'error');
        }
    }

    /**
     * 5. DUE DATE - Set due date with date picker (with browser fallback)
     */
    async handleDueDate(taskId) {
        console.log(`[TaskMenuController] Setting due date for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            const trigger = taskCard || document.body;

            let newDate;
            
            // Try custom date picker first
            if (window.taskDatePicker?.show) {
                try {
                    newDate = await window.taskDatePicker.show(trigger);
                } catch (e) {
                    console.warn('[TaskMenuController] Date picker failed, using fallback');
                    newDate = undefined;
                }
            }
            
            // Fallback: use browser input type=date via prompt
            if (newDate === undefined && !window.taskDatePicker) {
                const currentDate = task.due_date ? new Date(task.due_date).toISOString().split('T')[0] : '';
                const choice = window.prompt(
                    `Set due date for "${task.title || 'Task'}":\n\nFormat: YYYY-MM-DD (e.g., 2024-12-31)\nLeave empty to clear due date`,
                    currentDate
                );
                
                if (choice === null) {
                    console.log('[TaskMenuController] Date selection cancelled');
                    return;
                }
                
                if (choice === '') {
                    newDate = null; // Clear due date
                } else if (/^\d{4}-\d{2}-\d{2}$/.test(choice)) {
                    newDate = choice;
                } else {
                    this.showToast('Invalid date format. Use YYYY-MM-DD', 'error');
                    return;
                }
            } else if (newDate === undefined) {
                console.log('[TaskMenuController] Date selection cancelled');
                return;
            }

            // Use OptimisticUI system
            if (window.optimisticUI?.updateTask) {
                await window.optimisticUI.updateTask(taskId, { due_date: newDate || null });
            } else {
                // Direct API fallback
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ due_date: newDate || null })
                });
                if (!response.ok) throw new Error('API call failed');
                this.showToast('Due date updated', 'success');
            }
        } catch (error) {
            console.error('[TaskMenuController] Due date update failed:', error);
            this.showToast('Failed to update due date', 'error');
        }
    }

    /**
     * 6. ASSIGN - Open assignee selector modal (with fallback notification)
     */
    async handleAssign(taskId) {
        console.log(`[TaskMenuController] Opening assignee selector for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            let result;
            
            // Try custom assignee selector
            if (window.taskAssigneeSelector?.show) {
                try {
                    result = await window.taskAssigneeSelector.show(task.assignee_ids || []);
                } catch (e) {
                    console.warn('[TaskMenuController] Assignee selector failed:', e);
                    result = undefined;
                }
            }
            
            // Fallback message if selector not available
            if (result === undefined && !window.taskAssigneeSelector) {
                this.showToast('Assignee selector is loading. Please try again.', 'info');
                return;
            }
            
            if (result === null || result === undefined) {
                console.log('[TaskMenuController] Assignee selection cancelled');
                return;
            }

            // Use OptimisticUI system
            if (window.optimisticUI?.updateTask) {
                await window.optimisticUI.updateTask(taskId, { assignee_ids: result });
            } else {
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ assignee_ids: result })
                });
                if (!response.ok) throw new Error('API call failed');
                this.showToast('Assignees updated', 'success');
            }
        } catch (error) {
            console.error('[TaskMenuController] Assign failed:', error);
            this.showToast('Failed to update assignees', 'error');
        }
    }

    /**
     * 7. LABELS - Open labels editor modal (with browser fallback)
     */
    async handleLabels(taskId) {
        console.log(`[TaskMenuController] Opening labels editor for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            let result;
            
            // Try custom labels editor
            if (window.taskLabelsEditor?.show) {
                try {
                    result = await window.taskLabelsEditor.show(task.labels || []);
                } catch (e) {
                    console.warn('[TaskMenuController] Labels editor failed:', e);
                    result = undefined;
                }
            }
            
            // Fallback: use browser prompt
            if (result === undefined && !window.taskLabelsEditor) {
                const currentLabels = (task.labels || []).join(', ');
                const input = window.prompt(
                    `Edit labels for "${task.title || 'Task'}":\n\nEnter labels separated by commas.\nExample: bug, urgent, review`,
                    currentLabels
                );
                
                if (input === null) {
                    console.log('[TaskMenuController] Labels edit cancelled');
                    return;
                }
                
                result = input.split(',').map(l => l.trim()).filter(l => l.length > 0);
            }
            
            if (result === null || result === undefined) {
                console.log('[TaskMenuController] Labels edit cancelled');
                return;
            }

            // Use OptimisticUI system
            if (window.optimisticUI?.updateTask) {
                await window.optimisticUI.updateTask(taskId, { labels: result });
            } else {
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ labels: result })
                });
                if (!response.ok) throw new Error('API call failed');
                this.showToast('Labels updated', 'success');
            }
        } catch (error) {
            console.error('[TaskMenuController] Labels update failed:', error);
            this.showToast('Failed to update labels', 'error');
        }
    }

    /**
     * 8. DUPLICATE - Duplicate task with confirmation (with browser fallback)
     */
    async handleDuplicate(taskId) {
        console.log(`[TaskMenuController] Duplicating task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            let confirmed = false;
            
            // Try custom confirmation modal
            if (window.taskDuplicateConfirmation?.show) {
                try {
                    confirmed = await window.taskDuplicateConfirmation.show(task);
                } catch (e) {
                    console.warn('[TaskMenuController] Duplicate modal failed, using browser fallback');
                    confirmed = window.confirm(`Duplicate task "${task.title || 'this task'}"?`);
                }
            } else {
                // Fallback to browser confirm
                confirmed = window.confirm(`Duplicate task "${task.title || 'this task'}"?`);
            }
            
            if (!confirmed) {
                console.log('[TaskMenuController] Duplication cancelled');
                return;
            }

            // Create duplicate data
            const duplicateData = {
                title: task.title ? `${task.title} [Copy]` : 'Untitled Task [Copy]',
                description: task.description,
                priority: task.priority,
                due_date: task.due_date,
                assignee_ids: task.assignee_ids,
                labels: task.labels,
                meeting_id: task.meeting_id,
                workspace_id: task.workspace_id,
                status: 'todo'
            };

            // Use OptimisticUI createTask or direct API
            if (window.optimisticUI?.createTask) {
                await window.optimisticUI.createTask(duplicateData);
            } else {
                const response = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(duplicateData)
                });
                if (!response.ok) throw new Error('API call failed');
                this.showToast('Task duplicated', 'success');
                
                // Refresh task list
                if (window.taskBootstrap?.bootstrap) {
                    await window.taskBootstrap.bootstrap();
                }
            }
        } catch (error) {
            console.error('[TaskMenuController] Duplicate failed:', error);
            this.showToast('Failed to duplicate task', 'error');
        }
    }

    /**
     * 9. SNOOZE - Snooze task with time picker (with browser fallback)
     */
    async handleSnooze(taskId) {
        console.log(`[TaskMenuController] Snoozing task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            let snoozeUntil;
            
            // Try custom snooze modal
            if (window.taskSnoozeModal?.show) {
                try {
                    snoozeUntil = await window.taskSnoozeModal.show(task.snoozed_until);
                } catch (e) {
                    console.warn('[TaskMenuController] Snooze modal failed, using browser fallback');
                    snoozeUntil = undefined;
                }
            }
            
            // Fallback: use browser prompt
            if (snoozeUntil === undefined && !window.taskSnoozeModal) {
                const options = '1 = Tomorrow\n2 = Next Week\n3 = Next Month\n4 = Custom (enter date YYYY-MM-DD)';
                const choice = window.prompt(`Snooze task "${task.title || 'this task'}" until:\n\n${options}`);
                
                if (choice === null) {
                    console.log('[TaskMenuController] Snooze cancelled');
                    return;
                }
                
                const today = new Date();
                switch (choice.trim()) {
                    case '1':
                        today.setDate(today.getDate() + 1);
                        snoozeUntil = today.toISOString();
                        break;
                    case '2':
                        today.setDate(today.getDate() + 7);
                        snoozeUntil = today.toISOString();
                        break;
                    case '3':
                        today.setMonth(today.getMonth() + 1);
                        snoozeUntil = today.toISOString();
                        break;
                    default:
                        if (/^\d{4}-\d{2}-\d{2}$/.test(choice.trim())) {
                            snoozeUntil = new Date(choice.trim()).toISOString();
                        } else {
                            this.showToast('Invalid option. Please try again.', 'error');
                            return;
                        }
                }
            }
            
            if (snoozeUntil === null || snoozeUntil === undefined) {
                console.log('[TaskMenuController] Snooze cancelled');
                return;
            }

            // Use OptimisticUI system
            if (window.optimisticUI?.updateTask) {
                await window.optimisticUI.updateTask(taskId, { snoozed_until: snoozeUntil });
            } else {
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ snoozed_until: snoozeUntil })
                });
                if (!response.ok) throw new Error('API call failed');
                this.showToast('Task snoozed', 'success');
            }
        } catch (error) {
            console.error('[TaskMenuController] Snooze failed:', error);
            this.showToast('Failed to snooze task', 'error');
        }
    }

    /**
     * 10. MERGE - Merge with another task (with browser fallback)
     */
    async handleMerge(taskId) {
        console.log(`[TaskMenuController] Merging task ${taskId}`);
        
        const sourceTask = await this.fetchTask(taskId);
        if (!sourceTask) return;

        try {
            let targetTaskId;
            
            // Try custom merge modal
            if (window.taskMergeModal?.show) {
                try {
                    targetTaskId = await window.taskMergeModal.show(sourceTask);
                } catch (e) {
                    console.warn('[TaskMenuController] Merge modal failed, using browser fallback');
                    targetTaskId = undefined;
                }
            }
            
            // Fallback: use browser prompt
            if (targetTaskId === undefined && !window.taskMergeModal) {
                const input = window.prompt(
                    `Merge "${sourceTask.title || 'this task'}" into another task.\n\nEnter the target task ID to merge into:`
                );
                
                if (input === null || input.trim() === '') {
                    console.log('[TaskMenuController] Merge cancelled');
                    return;
                }
                
                targetTaskId = parseInt(input.trim(), 10);
                if (isNaN(targetTaskId)) {
                    this.showToast('Invalid task ID', 'error');
                    return;
                }
            }
            
            if (targetTaskId === null || targetTaskId === undefined) {
                console.log('[TaskMenuController] Merge cancelled');
                return;
            }

            // API endpoint is: POST /api/tasks/<target_task_id>/merge with source_task_id in body
            const response = await fetch(`/api/tasks/${targetTaskId}/merge`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_task_id: taskId
                })
            });

            if (!response.ok) {
                // If merge endpoint doesn't work, perform client-side merge
                if (response.status === 404) {
                    console.warn('[TaskMenuController] Merge API not found, using client-side merge');
                    await this.performClientSideMerge(taskId, targetTaskId);
                    return;
                }
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || 'Failed to merge tasks');
            }

            const data = await response.json();
            
            if (data.success) {
                this.showToast('Tasks merged successfully', 'success');
                
                // Refresh task list
                if (window.taskBootstrap?.bootstrap) {
                    await window.taskBootstrap.bootstrap();
                }
            } else {
                throw new Error(data.error || data.message || 'Failed to merge tasks');
            }
        } catch (error) {
            console.error('[TaskMenuController] Merge failed:', error);
            this.showToast(error.message || 'Failed to merge tasks', 'error');
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
     * 12. ARCHIVE - Archive task with confirmation (with browser fallback)
     */
    async handleArchive(taskId) {
        console.log(`[TaskMenuController] Archiving task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            let confirmed = false;
            
            // Try custom confirmation modal
            if (window.taskConfirmModal?.confirmArchive) {
                try {
                    confirmed = await window.taskConfirmModal.confirmArchive(task.title);
                } catch (e) {
                    console.warn('[TaskMenuController] Archive modal failed, using browser fallback');
                    confirmed = window.confirm(`Archive task "${task.title || 'this task'}"?\n\nArchived tasks can be restored later.`);
                }
            } else {
                // Fallback to browser confirm
                confirmed = window.confirm(`Archive task "${task.title || 'this task'}"?\n\nArchived tasks can be restored later.`);
            }
            
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

            // Use OptimisticUI archiveTask or direct API
            if (window.optimisticUI?.archiveTask) {
                await window.optimisticUI.archiveTask(taskId);
            } else {
                // Direct API fallback - archive = set status to completed
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        status: 'completed',
                        completed_at: new Date().toISOString()
                    })
                });
                if (!response.ok) throw new Error('API call failed');
                
                // Remove from DOM
                if (taskCard) {
                    taskCard.remove();
                }
                this.showToast('Task archived', 'success');
            }
        } catch (error) {
            console.error('[TaskMenuController] Archive failed:', error);
            
            // Rollback
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            if (taskCard) {
                taskCard.style.opacity = '';
                taskCard.style.pointerEvents = '';
            }
            this.showToast('Failed to archive task', 'error');
        }
    }

    /**
     * 13. DELETE - Permanently delete task with confirmation (with browser fallback)
     */
    async handleDelete(taskId) {
        console.log(`[TaskMenuController] Deleting task ${taskId}`);
        
        try {
            const task = await this.fetchTask(taskId);
            if (!task) {
                console.error('[TaskMenuController] Task not found:', taskId);
                return;
            }

            console.log('[TaskMenuController] Task fetched successfully:', task);

            let confirmed = false;
            
            // Try custom confirmation modal
            if (window.taskConfirmModal?.confirmDelete) {
                try {
                    confirmed = await window.taskConfirmModal.confirmDelete(task.title);
                } catch (e) {
                    console.warn('[TaskMenuController] Delete modal failed, using browser fallback');
                    confirmed = window.confirm(`Delete task "${task.title || 'this task'}" permanently?\n\nThis action cannot be undone.`);
                }
            } else {
                // Fallback to browser confirm
                confirmed = window.confirm(`Delete task "${task.title || 'this task'}" permanently?\n\nThis action cannot be undone.`);
            }
            
            console.log('[TaskMenuController] Confirmation result:', confirmed);
            
            if (!confirmed) {
                console.log('[TaskMenuController] Delete cancelled by user');
                return;
            }

            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);

            // Optimistic UI - fade out
            if (taskCard) {
                taskCard.style.opacity = '0.5';
                taskCard.style.pointerEvents = 'none';
            }

            console.log('[TaskMenuController] Calling optimisticUI.deleteTask...');
            
            // Use OptimisticUI deleteTask (soft delete with 15s undo window)
            if (window.optimisticUI?.deleteTask) {
                await window.optimisticUI.deleteTask(taskId);
            } else {
                // Direct API fallback
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' }
                });
                if (!response.ok) throw new Error('API call failed');
                
                // Remove from DOM manually
                if (taskCard) {
                    taskCard.remove();
                }
                this.showToast('Task deleted', 'success');
            }

            console.log('[TaskMenuController] Delete successful');
        } catch (error) {
            console.error('[TaskMenuController] Delete failed with error:', error);
            this.showToast('Failed to delete task', 'error');
            
            // Rollback UI changes
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            if (taskCard) {
                taskCard.style.opacity = '';
                taskCard.style.pointerEvents = '';
            }
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
     * REMOVED: updateTask() - All updates now go through window.optimisticUI.updateTask()
     * This ensures proper IndexedDB caching, offline queue, WebSocket broadcasts, and rollback support
     */

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

        // Update target task using OptimisticUI
        await window.optimisticUI.updateTask(targetTaskId, {
            labels: mergedLabels,
            priority: mergedPriority
        });

        // Delete source task using OptimisticUI (soft delete with undo)
        await window.optimisticUI.deleteTask(sourceTaskId);

        // Toast handled by OptimisticUI system
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

// Export class for orchestrator
window.TaskMenuController = TaskMenuController;

// Auto-instantiate on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (!window.taskMenuController) {
            window.taskMenuController = new TaskMenuController();
            console.log('[TaskMenuController] Auto-instantiated on DOMContentLoaded');
        }
    });
} else if (!window.taskMenuController) {
    window.taskMenuController = new TaskMenuController();
    console.log('[TaskMenuController] Auto-instantiated (DOM ready)');
}
