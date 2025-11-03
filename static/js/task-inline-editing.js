class TaskInlineEditing {
    constructor(taskOptimisticUI) {
        this.taskUI = taskOptimisticUI;
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

        const priorities = ['low', 'medium', 'high', 'urgent'];
        const select = document.createElement('select');
        select.className = 'inline-edit-select priority-select';
        
        priorities.forEach(p => {
            const option = document.createElement('option');
            option.value = p;
            option.textContent = p.charAt(0).toUpperCase() + p.slice(1);
            option.selected = p === currentPriority;
            select.appendChild(option);
        });

        const originalHTML = badge.innerHTML;
        const originalClassName = badge.className;
        badge.replaceWith(select);
        select.focus();

        const save = async () => {
            const newPriority = select.value;
            
            if (newPriority !== currentPriority) {
                try {
                    await this.taskUI.updatePriority(taskId, newPriority);
                    
                    const newBadge = document.createElement('span');
                    newBadge.className = `priority-badge priority-${newPriority}`;
                    newBadge.textContent = newPriority.charAt(0).toUpperCase() + newPriority.slice(1);
                    select.replaceWith(newBadge);
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_success', 1, { field: 'priority' });
                    }
                } catch (error) {
                    console.error('Failed to update priority:', error);
                    
                    const restoredBadge = document.createElement('span');
                    restoredBadge.className = originalClassName;
                    restoredBadge.innerHTML = originalHTML;
                    select.replaceWith(restoredBadge);
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_failure', 1, { field: 'priority' });
                    }
                }
            } else {
                const newBadge = document.createElement('span');
                newBadge.className = originalClassName;
                newBadge.innerHTML = originalHTML;
                select.replaceWith(newBadge);
            }
        };

        const cancel = () => {
            const newBadge = document.createElement('span');
            newBadge.className = originalClassName;
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

        const originalHTML = badge.innerHTML;
        const originalIsoDate = badge.dataset.isoDate;
        const originalClassName = badge.className;
        const isAddMode = badge.classList.contains('due-date-add');
        badge.replaceWith(input);
        input.focus();

        const save = async () => {
            const newDate = input.value;
            
            try {
                if (newDate) {
                    const isoDate = new Date(newDate).toISOString();
                    await this.taskUI.updateTask(taskId, { due_date: isoDate });
                    
                    const newBadge = document.createElement('span');
                    newBadge.className = 'due-date-badge';
                    newBadge.dataset.isoDate = isoDate;
                    newBadge.textContent = window.taskVirtualList?._formatDueDate(isoDate) || this.formatDueDate(newDate);
                    input.replaceWith(newBadge);
                } else if (existingDate) {
                    await this.taskUI.updateTask(taskId, { due_date: null });
                    
                    const addBadge = document.createElement('span');
                    addBadge.className = 'due-date-badge due-date-add';
                    addBadge.textContent = '+ Add due date';
                    input.replaceWith(addBadge);
                } else {
                    const addBadge = document.createElement('span');
                    addBadge.className = 'due-date-badge due-date-add';
                    addBadge.textContent = '+ Add due date';
                    input.replaceWith(addBadge);
                }
                
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('inline_edit_success', 1, { field: 'due_date' });
                }
            } catch (error) {
                console.error('Failed to update due date:', error);
                
                const restoredBadge = document.createElement('span');
                restoredBadge.className = originalClassName;
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
            const restoredBadge = document.createElement('span');
            restoredBadge.className = originalClassName;
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

    editAssignee(badge) {
        const card = badge.closest('[data-task-id]');
        if (!card) return;

        const taskId = card.dataset.taskId;
        const originalUserId = badge.dataset.userId;
        const originalHTML = badge.innerHTML;
        const originalClassName = badge.className;
        const isAssignedToMe = originalUserId && String(originalUserId) === String(window.currentUserId);
        const isUnassigned = badge.classList.contains('assignee-add');

        const select = document.createElement('select');
        select.className = 'inline-edit-select assignee-select';
        
        const unassignedOption = document.createElement('option');
        unassignedOption.value = '';
        unassignedOption.textContent = 'Unassigned';
        unassignedOption.selected = isUnassigned;
        select.appendChild(unassignedOption);
        
        const meOption = document.createElement('option');
        meOption.value = 'me';
        meOption.textContent = 'Assign to me';
        meOption.selected = isAssignedToMe;
        select.appendChild(meOption);
        
        if (!isUnassigned && !isAssignedToMe) {
            const otherOption = document.createElement('option');
            otherOption.value = 'other';
            otherOption.textContent = originalHTML;
            otherOption.selected = true;
            select.appendChild(otherOption);
        }

        const initialValue = select.value;
        badge.replaceWith(select);
        select.focus();

        const save = async () => {
            const newValue = select.value;
            
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
            
            const newAssignedToId = newValue === 'me' ? window.currentUserId : null;
            const oldAssignedToId = originalUserId ? parseInt(originalUserId) : null;
            
            if (newAssignedToId !== oldAssignedToId) {
                try {
                    await this.taskUI.updateTask(taskId, { assigned_to_id: newAssignedToId });
                    
                    if (newValue === 'me') {
                        const newBadge = document.createElement('span');
                        newBadge.className = 'assignee-badge';
                        newBadge.dataset.userId = window.currentUserId;
                        newBadge.textContent = '👤 Me';
                        select.replaceWith(newBadge);
                    } else {
                        const newBadge = document.createElement('span');
                        newBadge.className = 'assignee-badge assignee-add';
                        newBadge.textContent = '+ Assign';
                        select.replaceWith(newBadge);
                    }
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('inline_edit_success', 1, { field: 'assignee' });
                    }
                } catch (error) {
                    console.error('Failed to update assignee:', error);
                    
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
}

window.TaskInlineEditing = TaskInlineEditing;
