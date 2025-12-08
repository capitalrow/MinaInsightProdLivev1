class TaskInlineEditing {
    constructor(taskOptimisticUI) {
        this.taskUI = taskOptimisticUI;
        this.workspaceUsers = null; // Cache for workspace users
        this.fetchingUsers = null; // Promise for in-flight fetch
        this.init();
        console.log('[InlineEdit] ✅ TaskInlineEditing initialized');
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
            } else if (e.target.classList.contains('task-assignees') || e.target.closest('.task-assignees')) {
                // CROWN⁴.5: Multi-assignee editing
                const assigneeElement = e.target.classList.contains('task-assignees') ? 
                    e.target : e.target.closest('.task-assignees');
                this.editAssignees(assigneeElement);
            } else if (e.target.classList.contains('assignee-badge')) {
                // Legacy: single assignee (backward compat)
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
            console.log('[InlineEdit] Already editing, ignoring');
            return;
        }

        const card = titleElement.closest('[data-task-id]');
        if (!card) return;

        const taskId = card.dataset.taskId;
        const originalText = titleElement.textContent.trim();
        
        console.log('[InlineEdit] ✏️ TITLE EDIT START');
        console.log('[InlineEdit] Task ID:', taskId);
        console.log('[InlineEdit] Original text:', originalText);

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
                console.log('[InlineEdit] 📝 Title changed:', originalText, '→', newText);
                try {
                    // Show saving state
                    titleElement.classList.add('saving');

                    console.log('[InlineEdit] 📤 Calling optimisticUI.updateTask()');
                    // Update task via optimistic UI
                    await this.taskUI.updateTask(taskId, { title: newText });
                    console.log('[InlineEdit] ✅ Title update successful');

                    // Emit task updated event for CognitiveSynchronizer
                    document.dispatchEvent(new CustomEvent('task:updated', {
                        detail: {
                            taskId: parseInt(taskId),
                            updates: { title: newText },
                            previousValues: { title: originalText }
                        }
                    }));

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
                    console.error('[InlineEdit] ❌ Failed to update title:', error);

                    // Rollback to original text
                    titleElement.textContent = originalText;
                    titleElement.classList.remove('saving');

                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_failure', 1, { field: 'title' });
                    }
                }
            } else if (!newText) {
                console.log('[InlineEdit] Empty title, reverting to original');
                // Don't allow empty titles
                titleElement.textContent = originalText;
            } else {
                console.log('[InlineEdit] No change detected');
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

    /**
     * CROWN⁴.6: One-tap priority cycling with spring reorder animation
     * Click to cycle: low → medium → high → critical → low
     */
    async editPriority(badge) {
        const card = badge.closest('[data-task-id]');
        if (!card) return;

        const taskId = card.dataset.taskId;
        const currentPriority = badge.textContent.trim().toLowerCase();

        // Cycle through priorities
        const priorityOrder = ['low', 'medium', 'high', 'critical'];
        const currentIndex = priorityOrder.indexOf(currentPriority);
        const nextIndex = (currentIndex + 1) % priorityOrder.length;
        const newPriority = priorityOrder[nextIndex];

        try {
            // Optimistic update: immediately change the badge
            badge.textContent = newPriority.charAt(0).toUpperCase() + newPriority.slice(1);
            badge.className = `priority-badge priority-${newPriority}`;
            badge.title = `Click to cycle priority (current: ${newPriority})`;
            
            // Add spring animation class
            badge.classList.add('priority-changing');
            setTimeout(() => badge.classList.remove('priority-changing'), 300);

            // Update via optimistic UI
            await this.taskUI.updateTask(taskId, { priority: newPriority });

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('inline_edit_success', 1, { 
                    field: 'priority',
                    from: currentPriority,
                    to: newPriority
                });
            }

            // Trigger reorder if QuietStateManager exists
            if (window.quietStateManager) {
                window.quietStateManager.scheduleAnimation('task-reorder', card);
            }
        } catch (error) {
            console.error('Failed to update priority:', error);
            
            // Rollback on error
            badge.textContent = currentPriority.charAt(0).toUpperCase() + currentPriority.slice(1);
            badge.className = `priority-badge priority-${currentPriority}`;
            badge.title = `Click to cycle priority (current: ${currentPriority})`;

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('inline_edit_failure', 1, { field: 'priority' });
            }
        }
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

    /**
     * CROWN⁴.5: Multi-assignee editing with search and chips
     * @param {HTMLElement} assigneeElement - The task-assignees div
     */
    async editAssignees(assigneeElement) {
        const card = assigneeElement.closest('[data-task-id]');
        if (!card) return;

        const taskId = card.dataset.taskId;
        
        // Get current task data from TaskStore
        const task = window.taskStore?.getTaskById(taskId);
        const originalAssigneeIds = task?.assignee_ids || [];
        const originalHTML = assigneeElement.innerHTML;
        const originalClassName = assigneeElement.className;

        // Show loading state
        assigneeElement.innerHTML = '<svg width="12" height="12" class="spin-animation" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Loading...';

        // Fetch workspace users
        const users = await this.fetchWorkspaceUsers();

        // Create multi-select UI container
        const container = document.createElement('div');
        container.className = 'assignee-multi-select';
        container.innerHTML = `
            <div class="assignee-search-wrapper">
                <input type="text" 
                       class="assignee-search-input" 
                       placeholder="Search team members..."
                       autocomplete="off">
            </div>
            <div class="assignee-chips"></div>
            <div class="assignee-dropdown"></div>
            <div class="assignee-actions">
                <button class="btn-save">Save</button>
                <button class="btn-cancel">Cancel</button>
            </div>
        `;

        // Track selected assignees
        let selectedAssigneeIds = [...originalAssigneeIds];

        const searchInput = container.querySelector('.assignee-search-input');
        const chipsContainer = container.querySelector('.assignee-chips');
        const dropdown = container.querySelector('.assignee-dropdown');
        const saveBtn = container.querySelector('.btn-save');
        const cancelBtn = container.querySelector('.btn-cancel');

        // Render chips for selected assignees
        const renderChips = () => {
            if (selectedAssigneeIds.length === 0) {
                chipsContainer.innerHTML = '<div class="assignee-empty-state">No assignees selected</div>';
                return;
            }

            chipsContainer.innerHTML = selectedAssigneeIds
                .map(userId => {
                    const user = users.find(u => u.id === userId);
                    if (!user) return '';
                    
                    const escapedName = this.escapeHtml(user.display_name || user.username);
                    return `
                        <div class="assignee-chip" data-user-id="${user.id}">
                            <span class="chip-name">${escapedName}</span>
                            <button class="chip-remove" data-user-id="${user.id}" title="Remove ${escapedName}">×</button>
                        </div>
                    `;
                })
                .filter(Boolean)
                .join('');
        };

        // Render dropdown with filtered users
        const renderDropdown = (searchTerm = '') => {
            const filtered = users.filter(user => {
                const name = (user.display_name || user.username || '').toLowerCase();
                const email = (user.email || '').toLowerCase();
                const term = searchTerm.toLowerCase();
                return name.includes(term) || email.includes(term);
            });

            if (filtered.length === 0) {
                dropdown.innerHTML = '<div class="assignee-no-results">No users found</div>';
                return;
            }

            dropdown.innerHTML = filtered
                .map(user => {
                    const isSelected = selectedAssigneeIds.includes(user.id);
                    const escapedName = this.escapeHtml(user.display_name || user.username);
                    const escapedEmail = this.escapeHtml(user.email || '');
                    
                    return `
                        <div class="assignee-option ${isSelected ? 'selected' : ''}" 
                             data-user-id="${user.id}"
                             title="${escapedEmail}">
                            <div class="option-checkbox">
                                ${isSelected ? '✓' : ''}
                            </div>
                            <div class="option-info">
                                <div class="option-name">${escapedName}${user.is_current_user ? ' (You)' : ''}</div>
                                <div class="option-email">${escapedEmail}</div>
                            </div>
                        </div>
                    `;
                })
                .join('');
        };

        // Initial render
        renderChips();
        renderDropdown();

        // Replace assignee element with container
        assigneeElement.replaceWith(container);
        searchInput.focus();

        // Event: Search input
        searchInput.addEventListener('input', (e) => {
            renderDropdown(e.target.value);
        });

        // Event: Click on dropdown option to toggle selection
        dropdown.addEventListener('click', (e) => {
            const option = e.target.closest('.assignee-option');
            if (!option) return;

            const userId = parseInt(option.dataset.userId);
            const index = selectedAssigneeIds.indexOf(userId);

            if (index > -1) {
                // Remove
                selectedAssigneeIds.splice(index, 1);
            } else {
                // Add
                selectedAssigneeIds.push(userId);
            }

            renderChips();
            renderDropdown(searchInput.value);
        });

        // Event: Click remove button on chip
        chipsContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('chip-remove')) {
                e.stopPropagation();
                const userId = parseInt(e.target.dataset.userId);
                const index = selectedAssigneeIds.indexOf(userId);
                if (index > -1) {
                    selectedAssigneeIds.splice(index, 1);
                    renderChips();
                    renderDropdown(searchInput.value);
                }
            }
        });

        // Event: Save button
        const save = async () => {
            // Check if changed
            const hasChanged = JSON.stringify([...originalAssigneeIds].sort()) !== 
                              JSON.stringify([...selectedAssigneeIds].sort());

            if (!hasChanged) {
                cancel();
                return;
            }

            try {
                // Show saving state
                saveBtn.disabled = true;
                saveBtn.textContent = 'Saving...';

                await this.taskUI.updateTask(taskId, { 
                    assignee_ids: selectedAssigneeIds 
                });

                // Success - TaskStore will broadcast and re-render
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('inline_edit_success', 1, { 
                        field: 'assignees',
                        count: selectedAssigneeIds.length 
                    });
                }

                // Remove container (TaskStore will re-render the task card)
                container.remove();

            } catch (error) {
                console.error('Failed to update assignees:', error);

                // Error rollback - restore original
                const restoredElement = document.createElement('div');
                restoredElement.className = originalClassName;
                restoredElement.innerHTML = originalHTML;
                container.replaceWith(restoredElement);

                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('inline_edit_failure', 1, { field: 'assignees' });
                }
            }
        };

        // Event: Cancel button
        const cancel = () => {
            const restoredElement = document.createElement('div');
            restoredElement.className = originalClassName;
            restoredElement.innerHTML = originalHTML;
            container.replaceWith(restoredElement);
        };

        saveBtn.addEventListener('click', save);
        cancelBtn.addEventListener('click', cancel);

        // Event: Escape key to cancel
        container.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                cancel();
            }
        });
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
