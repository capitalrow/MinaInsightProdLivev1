class TaskInlineEditing {
    constructor(taskOptimisticUI) {
        this.taskUI = taskOptimisticUI;
        this.workspaceUsers = null; // Cache for workspace users
        this.fetchingUsers = null; // Promise for in-flight fetch
        this.init();
        console.log('[TaskInlineEditing] Initialized');
    }

    init() {
        document.addEventListener('click', (e) => {
            // Task title inline editing
            if (e.target.classList.contains('task-title') && !e.target.classList.contains('completed')) {
                this.editTitle(e.target);
            } else if (e.target.classList.contains('priority-badge')) {
                this.editPriority(e.target);
            } else if (e.target.classList.contains('due-date-badge')) {
                this.editDueDate(e.target);
            } else if (e.target.classList.contains('assignee-badge')) {
                this.editAssignee(e.target);
            }
        });
    }

    /**
     * Fetch workspace users for assignee selector (with caching)
     * @returns {Promise<Array>} Array of user objects
     */
    async fetchWorkspaceUsers() {
        // Return cached users if available
        if (this.workspaceUsers) {
            return this.workspaceUsers;
        }

        // Return existing fetch promise if already in flight
        if (this.fetchingUsers) {
            return this.fetchingUsers;
        }

        // Fetch users from API
        this.fetchingUsers = fetch('/api/tasks/workspace-users')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    this.workspaceUsers = data.users;
                    return this.workspaceUsers;
                } else {
                    throw new Error(data.message || 'Failed to fetch workspace users');
                }
            })
            .catch(err => {
                console.error('[TaskInlineEditing] Error fetching workspace users:', err);
                // Fallback to empty array
                this.workspaceUsers = [];
                return this.workspaceUsers;
            })
            .finally(() => {
                this.fetchingUsers = null;
            });

        return this.fetchingUsers;
    }

    /**
     * Inline editing for task title using contenteditable
     * @param {HTMLElement} titleElement - The task title div
     */
    editTitle(titleElement) {
        // Prevent multiple edit sessions
        if (titleElement.hasAttribute('contenteditable')) {
            return;
        }

        const card = titleElement.closest('[data-task-id]');
        if (!card) return;

        const taskId = card.dataset.taskId;
        const originalText = titleElement.textContent.trim();

        // Enable contenteditable
        titleElement.setAttribute('contenteditable', 'true');
        titleElement.classList.add('editing');
        titleElement.focus();

        // Select all text
        const range = document.createRange();
        range.selectNodeContents(titleElement);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);

        const save = async () => {
            const newText = titleElement.textContent.trim();

            // Remove listeners
            titleElement.removeEventListener('blur', save);
            titleElement.removeEventListener('keydown', handleKeydown);

            // Remove contenteditable
            titleElement.removeAttribute('contenteditable');
            titleElement.classList.remove('editing');

            // If text changed, update task
            if (newText && newText !== originalText) {
                try {
                    // Show saving state
                    titleElement.classList.add('saving');

                    // Update task via optimistic UI
                    await this.taskUI.updateTask(taskId, { title: newText });

                    // Show saved state briefly
                    titleElement.classList.remove('saving');
                    titleElement.classList.add('saved');
                    setTimeout(() => {
                        titleElement.classList.remove('saved');
                    }, 2000);

                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_success', 1, { field: 'title' });
                    }
                } catch (error) {
                    console.error('Failed to update title:', error);

                    // Rollback to original text
                    titleElement.textContent = originalText;
                    titleElement.classList.remove('saving');

                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_failure', 1, { field: 'title' });
                    }
                }
            } else if (!newText) {
                // Don't allow empty titles
                titleElement.textContent = originalText;
            }
        };

        const cancel = () => {
            // Remove listeners
            titleElement.removeEventListener('blur', save);
            titleElement.removeEventListener('keydown', handleKeydown);

            titleElement.textContent = originalText;
            titleElement.removeAttribute('contenteditable');
            titleElement.classList.remove('editing');
        };

        // Handle keyboard shortcuts - persistent listener
        const handleKeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                titleElement.blur(); // Triggers save
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancel();
            }
        };

        // Save on blur
        titleElement.addEventListener('blur', save);

        // Handle keyboard shortcuts
        titleElement.addEventListener('keydown', handleKeydown);
    }

    editPriority(badge) {
        const card = badge.closest('[data-task-id]');
        if (!card) return;

        const taskId = card.dataset.taskId;
        const currentPriority = badge.textContent.trim().toLowerCase();

        const priorities = ['low', 'medium', 'high', 'critical'];
        const select = document.createElement('select');
        select.className = 'inline-edit-select priority-select';
        
        priorities.forEach(p => {
            const option = document.createElement('option');
            option.value = p;
            option.textContent = p.charAt(0).toUpperCase() + p.slice(1);
            option.selected = p === currentPriority;
            select.appendChild(option);
        });

        // Save all original attributes for restoration
        const originalHTML = badge.innerHTML;
        const originalClassName = badge.className;
        const originalTitle = badge.title || `Click to change priority (current: ${currentPriority})`;
        const originalDataTaskId = badge.dataset.taskId || taskId;
        
        badge.replaceWith(select);
        select.focus();

        const save = async () => {
            const newPriority = select.value;
            
            if (newPriority !== currentPriority) {
                try {
                    await this.taskUI.updatePriority(taskId, newPriority);
                    
                    const newBadge = document.createElement('span');
                    newBadge.className = `priority-badge priority-${newPriority}`;
                    newBadge.dataset.taskId = taskId;
                    newBadge.title = `Click to change priority (current: ${newPriority})`;
                    newBadge.textContent = newPriority.charAt(0).toUpperCase() + newPriority.slice(1);
                    select.replaceWith(newBadge);
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_success', 1, { field: 'priority' });
                    }
                } catch (error) {
                    console.error('Failed to update priority:', error);
                    
                    // Rollback with all attributes
                    const restoredBadge = document.createElement('span');
                    restoredBadge.className = originalClassName;
                    restoredBadge.dataset.taskId = originalDataTaskId;
                    restoredBadge.title = originalTitle;
                    restoredBadge.innerHTML = originalHTML;
                    select.replaceWith(restoredBadge);
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_failure', 1, { field: 'priority' });
                    }
                }
            } else {
                // No change - restore with all attributes
                const newBadge = document.createElement('span');
                newBadge.className = originalClassName;
                newBadge.dataset.taskId = originalDataTaskId;
                newBadge.title = originalTitle;
                newBadge.innerHTML = originalHTML;
                select.replaceWith(newBadge);
            }
        };

        const cancel = () => {
            // Cancel - restore with all attributes
            const newBadge = document.createElement('span');
            newBadge.className = originalClassName;
            newBadge.dataset.taskId = originalDataTaskId;
            newBadge.title = originalTitle;
            newBadge.innerHTML = originalHTML;
            select.replaceWith(newBadge);
        };

        select.addEventListener('blur', save);
        select.addEventListener('change', save);
        select.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') save();
            if (e.key === 'Escape') cancel();
        });
    }

    editDueDate(badge) {
        const card = badge.closest('[data-task-id]');
        if (!card) return;

        const taskId = card.dataset.taskId;

        const input = document.createElement('input');
        input.type = 'date';
        input.className = 'inline-edit-input date-input';

        const existingDate = badge.dataset.isoDate;
        if (existingDate) {
            input.value = existingDate.split('T')[0];
        }

        // Save all original attributes for restoration
        const originalHTML = badge.innerHTML;
        const originalIsoDate = badge.dataset.isoDate;
        const originalClassName = badge.className;
        const originalTitle = badge.title || 'Click to change due date';
        const originalDataTaskId = badge.dataset.taskId || taskId;
        const isAddMode = badge.classList.contains('due-date-add');
        
        badge.replaceWith(input);
        input.focus();

        const save = async () => {
            const newDate = input.value;
            
            try {
                if (newDate) {
                    // Set due date
                    const isoDate = new Date(newDate).toISOString();
                    await this.taskUI.updateTask(taskId, { due_date: isoDate });
                    
                    // Calculate overdue/due-soon status
                    const isOverdue = this.isDueDateOverdue(isoDate);
                    const isDueSoon = !isOverdue && this.isDueDateWithin(isoDate, 1); // 1 day
                    
                    const newBadge = document.createElement('span');
                    newBadge.className = `due-date-badge${isOverdue ? ' overdue' : ''}${isDueSoon ? ' due-soon' : ''}`;
                    newBadge.dataset.isoDate = isoDate;
                    newBadge.dataset.taskId = originalDataTaskId;
                    newBadge.title = 'Click to change due date';
                    newBadge.textContent = window.taskVirtualList?._formatDueDate(isoDate) || this.formatDueDate(isoDate);
                    input.replaceWith(newBadge);
                } else if (existingDate) {
                    // Clear due date
                    await this.taskUI.updateTask(taskId, { due_date: null });
                    
                    const addBadge = document.createElement('span');
                    addBadge.className = 'due-date-badge due-date-add';
                    addBadge.dataset.taskId = originalDataTaskId;
                    addBadge.title = 'Click to set due date';
                    addBadge.textContent = '+ Add due date';
                    input.replaceWith(addBadge);
                } else {
                    // No change (was already empty)
                    const addBadge = document.createElement('span');
                    addBadge.className = 'due-date-badge due-date-add';
                    addBadge.dataset.taskId = originalDataTaskId;
                    addBadge.title = 'Click to set due date';
                    addBadge.textContent = '+ Add due date';
                    input.replaceWith(addBadge);
                }
                
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('inline_edit_success', 1, { field: 'due_date' });
                }
            } catch (error) {
                console.error('Failed to update due date:', error);
                
                // Rollback with all attributes
                const restoredBadge = document.createElement('span');
                restoredBadge.className = originalClassName;
                restoredBadge.dataset.taskId = originalDataTaskId;
                restoredBadge.title = originalTitle;
                if (originalIsoDate) {
                    restoredBadge.dataset.isoDate = originalIsoDate;
                }
                restoredBadge.innerHTML = originalHTML;
                input.replaceWith(restoredBadge);
                
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('inline_edit_failure', 1, { field: 'due_date' });
                }
            }
        };

        const cancel = () => {
            // Cancel - restore with all attributes
            const restoredBadge = document.createElement('span');
            restoredBadge.className = originalClassName;
            restoredBadge.dataset.taskId = originalDataTaskId;
            restoredBadge.title = originalTitle;
            if (originalIsoDate) {
                restoredBadge.dataset.isoDate = originalIsoDate;
            }
            restoredBadge.innerHTML = originalHTML;
            input.replaceWith(restoredBadge);
        };

        input.addEventListener('blur', save);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') save();
            if (e.key === 'Escape') cancel();
        });
    }

    async editAssignee(badge) {
        const card = badge.closest('[data-task-id]');
        if (!card) return;

        const taskId = card.dataset.taskId;
        const originalUserId = badge.dataset.userId;
        const originalHTML = badge.innerHTML;
        const originalClassName = badge.className;

        // Show loading state while fetching users
        const loadingSpan = document.createElement('span');
        loadingSpan.className = 'assignee-badge assignee-loading';
        loadingSpan.textContent = 'Loading...';
        badge.replaceWith(loadingSpan);

        // Fetch workspace users
        const users = await this.fetchWorkspaceUsers();

        // Create select dropdown
        const select = document.createElement('select');
        select.className = 'inline-edit-select assignee-select';
        
        // Unassigned option
        const unassignedOption = document.createElement('option');
        unassignedOption.value = '';
        unassignedOption.textContent = 'Unassigned';
        unassignedOption.selected = !originalUserId;
        select.appendChild(unassignedOption);
        
        // Add all workspace users
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user.id;
            option.textContent = user.is_current_user ? 
                `👤 ${user.full_name} (You)` : 
                `👤 ${user.full_name}`;
            option.selected = originalUserId && String(user.id) === String(originalUserId);
            select.appendChild(option);
        });

        const initialValue = select.value;
        loadingSpan.replaceWith(select);
        select.focus();

        const save = async () => {
            const newValue = select.value;
            
            // No change - restore original
            if (newValue === initialValue) {
                const restoredBadge = document.createElement('span');
                restoredBadge.className = originalClassName;
                if (originalUserId) {
                    restoredBadge.dataset.userId = originalUserId;
                }
                restoredBadge.innerHTML = originalHTML;
                select.replaceWith(restoredBadge);
                return;
            }
            
            // Convert values for comparison
            const newAssignedToId = newValue ? parseInt(newValue) : null;
            const oldAssignedToId = originalUserId ? parseInt(originalUserId) : null;
            
            if (newAssignedToId !== oldAssignedToId) {
                try {
                    await this.taskUI.updateTask(taskId, { assigned_to_id: newAssignedToId });
                    
                    // Create new badge with updated assignee
                    const newBadge = document.createElement('span');
                    if (newAssignedToId) {
                        const selectedUser = users.find(u => u.id === newAssignedToId);
                        newBadge.className = 'assignee-badge';
                        newBadge.dataset.userId = newAssignedToId;
                        newBadge.title = 'Click to change assignee';
                        newBadge.textContent = selectedUser ? 
                            `👤 ${selectedUser.is_current_user ? 'Me' : selectedUser.full_name}` : 
                            '👤 Assigned';
                    } else {
                        newBadge.className = 'assignee-badge assignee-add';
                        newBadge.title = 'Click to assign';
                        newBadge.textContent = '+ Assign';
                    }
                    select.replaceWith(newBadge);
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_success', 1, { field: 'assignee' });
                    }
                } catch (error) {
                    console.error('Failed to update assignee:', error);
                    
                    // Error rollback - restore original
                    const restoredBadge = document.createElement('span');
                    restoredBadge.className = originalClassName;
                    if (originalUserId) {
                        restoredBadge.dataset.userId = originalUserId;
                    }
                    restoredBadge.innerHTML = originalHTML;
                    select.replaceWith(restoredBadge);
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_failure', 1, { field: 'assignee' });
                    }
                }
            } else {
                // No effective change - restore original
                const restoredBadge = document.createElement('span');
                restoredBadge.className = originalClassName;
                if (originalUserId) {
                    restoredBadge.dataset.userId = originalUserId;
                }
                restoredBadge.innerHTML = originalHTML;
                select.replaceWith(restoredBadge);
            }
        };

        const cancel = () => {
            const restoredBadge = document.createElement('span');
            restoredBadge.className = originalClassName;
            if (originalUserId) {
                restoredBadge.dataset.userId = originalUserId;
            }
            restoredBadge.innerHTML = originalHTML;
            select.replaceWith(restoredBadge);
        };

        select.addEventListener('blur', save);
        select.addEventListener('change', save);
        select.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') save();
            if (e.key === 'Escape') cancel();
        });
    }

    formatDueDate(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diffTime = date - now;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        if (diffDays < 0) {
            return `Overdue`;
        } else if (diffDays === 0) {
            return 'Due today';
        } else if (diffDays === 1) {
            return 'Due tomorrow';
        } else if (diffDays < 7) {
            return `Due in ${diffDays} days`;
        } else {
            return `Due ${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
        }
    }

    /**
     * Check if due date is overdue (in the past)
     * @param {string} dueDateStr - ISO date string
     * @returns {boolean}
     */
    isDueDateOverdue(dueDateStr) {
        if (!dueDateStr) return false;
        const dueDate = new Date(dueDateStr);
        const now = new Date();
        now.setHours(0, 0, 0, 0); // Start of today
        return dueDate < now;
    }

    /**
     * Check if due date is within specified days
     * @param {string} dueDateStr - ISO date string
     * @param {number} days - Number of days to check
     * @returns {boolean}
     */
    isDueDateWithin(dueDateStr, days) {
        if (!dueDateStr) return false;
        const dueDate = new Date(dueDateStr);
        const now = new Date();
        now.setHours(0, 0, 0, 0);
        const targetDate = new Date(now);
        targetDate.setDate(now.getDate() + days);
        return dueDate >= now && dueDate <= targetDate;
    }
}

window.TaskInlineEditing = TaskInlineEditing;
