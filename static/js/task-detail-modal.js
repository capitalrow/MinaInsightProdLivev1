/**
 * CROWN⁴.5 Task Detail Modal Controller
 * 
 * Manages the comprehensive task detail modal with:
 * - Tab navigation (Details, Comments, History, Attachments)
 * - Real-time data population and updates
 * - Comment system with CRUD operations
 * - History timeline rendering
 * - Keyboard shortcuts (ESC to close)
 */

class TaskDetailModal {
    constructor() {
        this.overlay = document.getElementById('task-detail-modal-overlay');
        this.modal = this.overlay?.querySelector('.task-modal');
        this.currentTaskId = null;
        this.currentTaskData = null;
        this.hasUnsavedChanges = false;
        
        if (!this.overlay) {
            console.error('[TaskDetailModal] Modal overlay not found');
            return;
        }
        
        this.init();
    }
    
    init() {
        console.log('[TaskDetailModal] Initializing...');
        
        // Close button
        document.getElementById('task-detail-close')?.addEventListener('click', () => {
            this.close();
        });
        
        document.getElementById('task-detail-cancel')?.addEventListener('click', () => {
            this.close();
        });
        
        // Save button
        document.getElementById('task-detail-save')?.addEventListener('click', () => {
            this.saveChanges();
        });
        
        // Click overlay to close
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.close();
            }
        });
        
        // Tab switching
        document.querySelectorAll('.task-detail-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
            });
        });
        
        // Track changes
        this.trackChanges();
        
        // Comment system
        this.initCommentSystem();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay.classList.contains('visible')) {
                this.close();
            }
        });
        
        console.log('[TaskDetailModal] Initialized successfully');
    }
    
    open(taskId) {
        console.log(`[TaskDetailModal] Opening modal for task: ${taskId}`);
        
        this.currentTaskId = taskId;
        this.hasUnsavedChanges = false;
        
        // Find the task card
        const taskCard = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (!taskCard) {
            console.error(`[TaskDetailModal] Task card not found: ${taskId}`);
            return;
        }
        
        // Populate modal with task data
        this.populateTaskData(taskCard);
        
        // Load additional data (comments, history)
        this.loadComments(taskId);
        this.loadHistory(taskId);
        
        // Show modal
        this.overlay.classList.remove('hidden');
        requestAnimationFrame(() => {
            this.overlay.classList.add('visible');
        });
        
        // Switch to Details tab by default
        this.switchTab('details');
    }
    
    close() {
        if (this.hasUnsavedChanges) {
            const confirmClose = confirm('You have unsaved changes. Are you sure you want to close?');
            if (!confirmClose) return;
        }
        
        console.log('[TaskDetailModal] Closing modal');
        
        this.overlay.classList.remove('visible');
        setTimeout(() => {
            this.overlay.classList.add('hidden');
            this.currentTaskId = null;
            this.currentTaskData = null;
            this.hasUnsavedChanges = false;
        }, 200);
    }
    
    switchTab(tabName) {
        console.log(`[TaskDetailModal] Switching to tab: ${tabName}`);
        
        // Update tab buttons
        document.querySelectorAll('.task-detail-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        
        // Update panels
        document.querySelectorAll('.task-detail-panel').forEach(panel => {
            panel.classList.toggle('active', panel.dataset.panel === tabName);
        });
    }
    
    populateTaskData(taskCard) {
        // Extract data from task card
        const title = taskCard.querySelector('.task-title')?.textContent || '';
        const status = taskCard.dataset.status || 'pending';
        const priority = taskCard.dataset.priority || 'medium';
        const dueDate = taskCard.dataset.dueDate || '';
        const created = taskCard.dataset.created || '';
        const assignedTo = taskCard.dataset.assignedTo || '';
        const description = taskCard.dataset.description || '';
        const source = taskCard.dataset.source || 'manual';
        
        // Populate form fields
        const titleEl = document.getElementById('detail-title');
        if (titleEl) titleEl.textContent = title;
        
        const statusEl = document.getElementById('detail-status');
        if (statusEl) statusEl.value = status;
        
        const priorityEl = document.getElementById('detail-priority');
        if (priorityEl) priorityEl.value = priority;
        
        const dueDateEl = document.getElementById('detail-due-date');
        if (dueDateEl && dueDate) {
            // Convert to YYYY-MM-DD format
            const date = new Date(dueDate);
            dueDateEl.value = date.toISOString().split('T')[0];
        }
        
        const createdEl = document.getElementById('detail-created');
        if (createdEl) {
            createdEl.textContent = created ? this.formatDate(new Date(created)) : 'N/A';
        }
        
        const descEl = document.getElementById('detail-description');
        if (descEl) descEl.value = description;
        
        const sourceEl = document.getElementById('detail-source');
        if (sourceEl) {
            const sourceLabel = source === 'ai' ? 
                '<span class="assignee-badge">🤖 AI Generated</span>' : 
                '<span class="assignee-badge">👤 Manual Entry</span>';
            sourceEl.innerHTML = sourceLabel;
        }
        
        // Populate assignees
        this.populateAssignees(assignedTo);
        
        // Store current data for change tracking
        this.currentTaskData = {
            title,
            status,
            priority,
            dueDate,
            description,
            assignedTo
        };
    }
    
    populateAssignees(assignedTo) {
        const container = document.getElementById('detail-assignees');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (!assignedTo || assignedTo === '') {
            container.innerHTML = '<span class="task-detail-value">Unassigned</span>';
            return;
        }
        
        // Handle multiple assignees (comma-separated)
        const assignees = assignedTo.split(',').map(a => a.trim()).filter(Boolean);
        
        assignees.forEach(assignee => {
            const badge = document.createElement('div');
            badge.className = 'assignee-badge';
            badge.textContent = assignee;
            container.appendChild(badge);
        });
    }
    
    trackChanges() {
        // Track changes to form fields
        const fields = [
            'detail-status',
            'detail-priority',
            'detail-due-date',
            'detail-description'
        ];
        
        fields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                field.addEventListener('change', () => {
                    this.hasUnsavedChanges = true;
                    console.log('[TaskDetailModal] Unsaved changes detected');
                });
            }
        });
    }
    
    async saveChanges() {
        console.log('[TaskDetailModal] Saving changes...');
        
        const updates = {
            status: document.getElementById('detail-status')?.value,
            priority: document.getElementById('detail-priority')?.value,
            due_date: document.getElementById('detail-due-date')?.value,
            description: document.getElementById('detail-description')?.value
        };
        
        try {
            const response = await fetch(`/api/tasks/${this.currentTaskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updates)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('[TaskDetailModal] Task updated successfully:', data);
            
            // Update the task card in the UI
            this.updateTaskCard(data.task);
            
            // Reset unsaved changes flag
            this.hasUnsavedChanges = false;
            
            // Show success notification
            if (window.showToast) {
                window.showToast('Task updated successfully', 'success');
            }
            
            // Close modal
            this.close();
            
        } catch (error) {
            console.error('[TaskDetailModal] Error saving task:', error);
            if (window.showToast) {
                window.showToast('Failed to save task changes', 'error');
            }
        }
    }
    
    updateTaskCard(taskData) {
        const taskCard = document.querySelector(`.task-card[data-task-id="${this.currentTaskId}"]`);
        if (!taskCard) return;
        
        // Update dataset attributes
        if (taskData.status) taskCard.dataset.status = taskData.status;
        if (taskData.priority) taskCard.dataset.priority = taskData.priority;
        if (taskData.due_date) taskCard.dataset.dueDate = taskData.due_date;
        if (taskData.description) taskCard.dataset.description = taskData.description;
        
        // Update visual elements
        const priorityBadge = taskCard.querySelector('.task-priority');
        if (priorityBadge && taskData.priority) {
            priorityBadge.className = `task-priority priority-${taskData.priority}`;
            priorityBadge.textContent = taskData.priority.charAt(0).toUpperCase() + taskData.priority.slice(1);
        }
        
        // Trigger re-filter if needed
        const filterEvent = new CustomEvent('filterChanged');
        document.dispatchEvent(filterEvent);
    }
    
    initCommentSystem() {
        const addCommentBtn = document.getElementById('add-comment');
        const cancelCommentBtn = document.getElementById('cancel-comment');
        const commentInput = document.getElementById('comment-input');
        
        if (addCommentBtn) {
            addCommentBtn.addEventListener('click', () => {
                this.addComment();
            });
        }
        
        if (cancelCommentBtn) {
            cancelCommentBtn.addEventListener('click', () => {
                if (commentInput) commentInput.value = '';
            });
        }
    }
    
    async loadComments(taskId) {
        console.log(`[TaskDetailModal] Loading comments for task: ${taskId}`);
        
        const container = document.getElementById('comments-list');
        if (!container) return;
        
        try {
            const response = await fetch(`/api/tasks/${taskId}/comments`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            const comments = data.comments || [];
            
            // Update badge count
            const badge = document.getElementById('comments-count');
            if (badge) badge.textContent = comments.length;
            
            if (comments.length === 0) {
                container.innerHTML = `
                    <div class="comments-empty">
                        <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                        </svg>
                        <p>No comments yet</p>
                        <p class="text-secondary">Be the first to comment</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = comments.map(comment => `
                <div class="comment-item">
                    <div class="comment-header">
                        <span class="comment-author">${this.escapeHtml(comment.author || 'User')}</span>
                        <span class="comment-time">${this.formatDate(new Date(comment.created_at))}</span>
                    </div>
                    <div class="comment-text">${this.escapeHtml(comment.text)}</div>
                </div>
            `).join('');
            
        } catch (error) {
            console.error('[TaskDetailModal] Error loading comments:', error);
            container.innerHTML = '<p class="text-secondary">Failed to load comments</p>';
        }
    }
    
    async addComment() {
        const input = document.getElementById('comment-input');
        if (!input || !input.value.trim()) {
            if (window.showToast) {
                window.showToast('Please enter a comment', 'warning');
            }
            return;
        }
        
        const commentText = input.value.trim();
        console.log(`[TaskDetailModal] Adding comment to task: ${this.currentTaskId}`);
        
        try {
            const response = await fetch(`/api/tasks/${this.currentTaskId}/comments`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ text: commentText })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            // Clear input
            input.value = '';
            
            // Reload comments
            await this.loadComments(this.currentTaskId);
            
            if (window.showToast) {
                window.showToast('Comment added', 'success');
            }
            
        } catch (error) {
            console.error('[TaskDetailModal] Error adding comment:', error);
            if (window.showToast) {
                window.showToast('Failed to add comment', 'error');
            }
        }
    }
    
    async loadHistory(taskId) {
        console.log(`[TaskDetailModal] Loading history for task: ${taskId}`);
        
        const container = document.getElementById('history-timeline');
        if (!container) return;
        
        try {
            const response = await fetch(`/api/tasks/${taskId}/history`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            const history = data.history || [];
            
            if (history.length === 0) {
                container.innerHTML = `
                    <div class="comments-empty">
                        <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        <p>No history yet</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = history.map(event => {
                const isMajor = ['created', 'completed', 'archived'].includes(event.action);
                return `
                    <div class="history-item ${isMajor ? 'major' : ''}">
                        <div class="history-header">
                            <span class="history-action">${this.formatAction(event.action)}</span>
                            <span class="history-time">${this.formatDate(new Date(event.timestamp))}</span>
                        </div>
                        ${event.details ? `<div class="history-details">${this.formatHistoryDetails(event)}</div>` : ''}
                    </div>
                `;
            }).join('');
            
        } catch (error) {
            console.error('[TaskDetailModal] Error loading history:', error);
            container.innerHTML = '<p class="text-secondary">Failed to load history</p>';
        }
    }
    
    formatAction(action) {
        const actions = {
            created: 'Created',
            updated: 'Updated',
            completed: 'Completed',
            reopened: 'Reopened',
            priority_changed: 'Priority changed',
            due_date_changed: 'Due date changed',
            assigned: 'Assigned',
            unassigned: 'Unassigned',
            archived: 'Archived',
            restored: 'Restored'
        };
        return actions[action] || action;
    }
    
    formatHistoryDetails(event) {
        if (event.action === 'priority_changed' && event.old_value && event.new_value) {
            return `Priority: <span class="history-change-old">${event.old_value}</span> → <span class="history-change-new">${event.new_value}</span>`;
        }
        if (event.action === 'due_date_changed' && event.old_value && event.new_value) {
            return `Due date: <span class="history-change-old">${event.old_value}</span> → <span class="history-change-new">${event.new_value}</span>`;
        }
        return event.details || '';
    }
    
    formatDate(date) {
        const now = new Date();
        const diff = now - date;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (seconds < 60) return 'just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;
        
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
        });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize on DOM ready
let taskDetailModal;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        taskDetailModal = new TaskDetailModal();
    });
} else {
    taskDetailModal = new TaskDetailModal();
}

// Export for use by other modules
window.openTaskDetail = (taskId) => {
    if (taskDetailModal) {
        taskDetailModal.open(taskId);
    }
};
