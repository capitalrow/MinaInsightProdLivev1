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
     * Detect if running on mobile/touch device
     */
    isMobile() {
        return window.matchMedia('(max-width: 768px)').matches || 
               ('ontouchstart' in window) ||
               (navigator.maxTouchPoints > 0);
    }

    /**
     * 4. PRIORITY - Change priority with mobile sheet or desktop popover
     */
    async handlePriority(taskId) {
        console.log(`[TaskMenuController] Changing priority for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            const currentPriority = task.priority || 'medium';
            let newPriority;
            
            // Mobile: use bottom sheet (Notion/Linear pattern)
            if (this.isMobile() && window.taskPrioritySheet?.open) {
                console.log('[TaskMenuController] Using mobile priority sheet');
                newPriority = await window.taskPrioritySheet.open(taskId, currentPriority);
            }
            // Desktop: use popover selector
            else if (window.taskPrioritySelector?.show) {
                console.log('[TaskMenuController] Using desktop priority selector');
                const trigger = taskCard || document.body;
                try {
                    newPriority = await window.taskPrioritySelector.show(trigger, currentPriority);
                } catch (e) {
                    console.warn('[TaskMenuController] Priority selector failed:', e);
                    newPriority = null;
                }
            }
            
            // Final fallback: browser prompt
            if (newPriority === undefined || newPriority === null) {
                if (!window.taskPrioritySheet && !window.taskPrioritySelector) {
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
     * 5. DUE DATE - Set due date with mobile sheet or desktop picker
     */
    async handleDueDate(taskId) {
        console.log(`[TaskMenuController] Setting due date for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) return;

        try {
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            const currentDate = task.due_date || null;
            let newDate;
            
            // Mobile: use bottom sheet (Notion/Linear pattern)
            if (this.isMobile() && window.taskDateSheet?.open) {
                console.log('[TaskMenuController] Using mobile date sheet');
                newDate = await window.taskDateSheet.open(taskId, currentDate);
            }
            // Desktop: use popover date picker
            else if (window.taskDatePicker?.show) {
                console.log('[TaskMenuController] Using desktop date picker');
                const trigger = taskCard || document.body;
                try {
                    newDate = await window.taskDatePicker.show(trigger, currentDate);
                } catch (e) {
                    console.warn('[TaskMenuController] Date picker failed:', e);
                    newDate = undefined;
                }
            }
            
            // Final fallback: browser prompt
            if (newDate === undefined && !window.taskDateSheet && !window.taskDatePicker) {
                const currentDateStr = task.due_date ? new Date(task.due_date).toISOString().split('T')[0] : '';
                const choice = window.prompt(
                    `Set due date for "${task.title || 'Task'}":\n\nFormat: YYYY-MM-DD (e.g., 2024-12-31)\nLeave empty to clear due date`,
                    currentDateStr
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
                this.showToast(newDate ? 'Due date updated' : 'Due date cleared', 'success');
            } else {
                // Direct API fallback
                const response = await fetch(`/api/tasks/${taskId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ due_date: newDate || null })
                });
                if (!response.ok) throw new Error('API call failed');
                this.showToast(newDate ? 'Due date updated' : 'Due date cleared', 'success');
            }
            
            // Update DOM immediately for visual feedback (taskCard already declared above)
            if (taskCard) {
                const dueDateBadge = taskCard.querySelector('.task-due-date, .due-date-badge');
                if (dueDateBadge && newDate) {
                    // Format date for display
                    const date = new Date(newDate);
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    const diff = Math.floor((date - today) / (1000 * 60 * 60 * 24));
                    
                    let displayText;
                    if (diff === 0) displayText = 'Today';
                    else if (diff === 1) displayText = 'Tomorrow';
                    else if (diff < 0) displayText = 'Overdue';
                    else if (diff <= 7) displayText = `In ${diff}d`;
                    else displayText = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    
                    dueDateBadge.textContent = displayText;
                    dueDateBadge.style.display = '';
                    
                    // Update overdue styling
                    if (diff < 0) {
                        dueDateBadge.classList.add('overdue');
                    } else {
                        dueDateBadge.classList.remove('overdue');
                    }
                } else if (dueDateBadge && !newDate) {
                    // Clear due date - hide badge
                    dueDateBadge.style.display = 'none';
                }
                
                // Also check for inline "+ Add due date" button and update it
                const addDueDateBtn = taskCard.querySelector('[data-inline-action="add-due-date"]');
                if (addDueDateBtn && newDate) {
                    addDueDateBtn.style.display = 'none';
                } else if (addDueDateBtn && !newDate) {
                    addDueDateBtn.style.display = '';
                }
            }
            
            console.log('[TaskMenuController] Due date updated successfully:', newDate);
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

            // CRITICAL FIX: Look up the full user object(s) for instant UI update
            // This follows industry-standard optimistic UI patterns (Linear, Notion, Asana)
            let assigned_to = null;
            if (result.length > 0 && window.taskAssigneeSelector?.allUsers) {
                // Get the primary assignee (first one) with full user object
                const selectedUser = window.taskAssigneeSelector.allUsers.find(u => u.id === result[0]);
                if (selectedUser) {
                    // Preserve correct field names - username stays as username, display_name is separate
                    assigned_to = {
                        id: selectedUser.id,
                        username: selectedUser.username,
                        display_name: selectedUser.display_name,
                        email: selectedUser.email
                    };
                    console.log('[TaskMenuController] Including full user object for optimistic UI:', assigned_to);
                }
            }

            // Use OptimisticUI system with full user object for instant display
            if (window.optimisticUI?.updateTask) {
                const updatePayload = { assignee_ids: result };
                if (assigned_to) {
                    updatePayload.assigned_to = assigned_to;
                    updatePayload.assigned_to_id = assigned_to.id;
                }
                await window.optimisticUI.updateTask(taskId, updatePayload);
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
     * CROWN⁴.7: Navigate to session using external_session_id (ULID format)
     * Uses session_external_id from task API when available for direct navigation
     */
    async handleJumpToTranscript(taskId) {
        console.log(`[TaskMenuController] Jumping to transcript for task ${taskId}`);
        
        const task = await this.fetchTask(taskId);
        if (!task) {
            this.showToast('Task not found', 'error');
            return;
        }
        
        // Check if we have transcript-related data
        if (!task.meeting_id && !task.session_external_id) {
            this.showToast('No transcript available for this task', 'error');
            return;
        }

        try {
            // Show loading toast
            this.showToast('Loading transcript...', 'info');
            
            let sessionId = null;
            
            // CROWN⁴.7: Use session_external_id directly if available (faster, more reliable)
            if (task.session_external_id) {
                sessionId = task.session_external_id;
                console.log(`[TaskMenuController] Using task.session_external_id: ${sessionId}`);
            } else {
                // Fallback: Fetch meeting details to get the session's external_session_id
                console.log(`[TaskMenuController] Fetching meeting ${task.meeting_id} for session_id`);
                const meetingResponse = await fetch(`/api/meetings/${task.meeting_id}`);
                if (!meetingResponse.ok) {
                    throw new Error('Failed to load meeting details');
                }
                
                const meetingData = await meetingResponse.json();
                if (!meetingData.success || !meetingData.meeting) {
                    throw new Error('Meeting not found');
                }
                
                const meeting = meetingData.meeting;
                
                // Get external_session_id from meeting data
                sessionId = meeting.session_id || meeting.external_session_id;
                console.log(`[TaskMenuController] Got session_id from meeting: ${sessionId}`);
            }
            
            if (!sessionId) {
                throw new Error('No session associated with this meeting');
            }
            
            // Build URL with optional transcript span highlighting
            // Use /refined route to load all insights data (summary, analytics, tasks)
            let targetUrl = `/sessions/${sessionId}/refined`;
            
            // If task has transcript_span, add highlight parameter
            if (task.transcript_span && task.transcript_span.start_ms !== null) {
                targetUrl += `?highlight_time=${task.transcript_span.start_ms}`;
            }
            targetUrl += '#transcript';
            
            console.log(`[TaskMenuController] Navigating to: ${targetUrl}`);
            
            // Navigate
            window.location.href = targetUrl;
            
        } catch (error) {
            console.error('[TaskMenuController] Jump to transcript failed:', error);
            this.showToast('Failed to load transcript', 'error');
        }
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
     * Handles both temp tasks (local only) and server-synced tasks
     */
    async handleDelete(taskId) {
        console.log(`[TaskMenuController] Deleting task ${taskId}`);
        
        const isTempTask = String(taskId).startsWith('temp_');
        
        try {
            // Get task info (from cache, DOM, or API)
            const task = await this.fetchTask(taskId);
            const taskTitle = task?.title || 'this task';

            console.log('[TaskMenuController] Task info retrieved:', taskTitle, isTempTask ? '(temp)' : '(synced)');

            let confirmed = false;
            
            // Try custom confirmation modal
            if (window.taskConfirmModal?.confirmDelete) {
                try {
                    confirmed = await window.taskConfirmModal.confirmDelete(taskTitle);
                } catch (e) {
                    console.warn('[TaskMenuController] Delete modal failed, using browser fallback');
                    confirmed = window.confirm(`Delete task "${taskTitle}" permanently?\n\nThis action cannot be undone.`);
                }
            } else {
                // Fallback to browser confirm
                confirmed = window.confirm(`Delete task "${taskTitle}" permanently?\n\nThis action cannot be undone.`);
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

            console.log('[TaskMenuController] Deleting task...', isTempTask ? '(temp task - local only)' : '(synced task)');
            
            // Handle temp tasks differently - they only exist locally
            if (isTempTask) {
                // Remove from cache
                if (window.taskCache?.deleteTask) {
                    await window.taskCache.deleteTask(taskId);
                }
                if (window.taskCache?.deleteTempTask) {
                    await window.taskCache.deleteTempTask(taskId);
                }
                
                // Remove from DOM with animation
                if (taskCard) {
                    taskCard.style.transition = 'opacity 0.2s, transform 0.2s';
                    taskCard.style.opacity = '0';
                    taskCard.style.transform = 'translateX(-20px)';
                    setTimeout(() => taskCard.remove(), 200);
                }
                
                this.showToast('Task deleted', 'success');
                console.log('[TaskMenuController] Temp task deleted successfully');
                return;
            }
            
            // For synced tasks, use OptimisticUI deleteTask (soft delete with undo window)
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
     * Helper: Fetch task details from cache first, then API
     * Handles temp tasks (not yet synced to server) gracefully
     */
    async fetchTask(taskId) {
        try {
            // 1. Check if this is a temp task (not yet on server)
            const isTempTask = String(taskId).startsWith('temp_');
            
            // 2. Try to get from cache first (works for both temp and synced tasks)
            if (window.taskCache && typeof window.taskCache.getTask === 'function') {
                const cachedTask = await window.taskCache.getTask(taskId);
                if (cachedTask) {
                    console.log('[TaskMenuController] Task found in cache:', taskId);
                    return cachedTask;
                }
            }
            
            // 3. Try optimisticUI cache
            if (window.optimisticUI?.cache?.getTask) {
                const cachedTask = await window.optimisticUI.cache.getTask(taskId);
                if (cachedTask) {
                    console.log('[TaskMenuController] Task found in optimisticUI cache:', taskId);
                    return cachedTask;
                }
            }
            
            // 4. For temp tasks, extract basic info from DOM as fallback
            if (isTempTask) {
                const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
                if (taskCard) {
                    console.log('[TaskMenuController] Extracting temp task from DOM:', taskId);
                    return {
                        id: taskId,
                        title: taskCard.querySelector('.task-title-text')?.textContent?.trim() || 
                               taskCard.querySelector('.task-title')?.textContent?.trim() || 'Untitled',
                        status: taskCard.dataset.status || 'todo',
                        priority: taskCard.dataset.priority || 'medium',
                        meeting_id: taskCard.dataset.meetingId || null,
                        labels: [],
                        _isTemp: true
                    };
                }
                
                // Temp task not in cache and not in DOM - it may have been deleted
                console.warn('[TaskMenuController] Temp task not found:', taskId);
                return null;
            }
            
            // 5. For server tasks, fetch from API
            const response = await fetch(`/api/tasks/${taskId}`);
            if (!response.ok) {
                throw new Error('Failed to fetch task');
            }
            const data = await response.json();
            return data.task;
        } catch (error) {
            console.error('[TaskMenuController] Error fetching task:', error);
            console.error('[TaskMenuController] Task not found:', taskId);
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
