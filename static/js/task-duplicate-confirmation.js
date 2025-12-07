/**
 * Task Duplicate Confirmation Modal
 * Shows preview of task to be duplicated and confirms duplication
 */

class TaskDuplicateConfirmation {
    constructor() {
        this.modal = null;
        this.resolveCallback = null;
        this.init();
    }

    init() {
        this.createModal();
        this.setupEventListeners();
    }

    createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'task-duplicate-modal-overlay';
        this.modal.innerHTML = `
            <div class="task-duplicate-modal">
                <div class="task-duplicate-modal-header">
                    <h3>Duplicate Task</h3>
                    <button class="task-duplicate-modal-close" title="Close">
                        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                    </button>
                </div>
                <div class="task-duplicate-modal-body">
                    <div class="task-duplicate-info">
                        <svg width="48" height="48" fill="currentColor" viewBox="0 0 24 24" style="opacity: 0.5; margin-bottom: 16px;">
                            <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                        </svg>
                        <p>This will create a copy of the task with all its properties:</p>
                    </div>
                    <div class="task-duplicate-preview">
                        <div class="task-duplicate-preview-item">
                            <span class="task-duplicate-preview-label">Title:</span>
                            <span class="task-duplicate-preview-value task-duplicate-title"></span>
                        </div>
                        <div class="task-duplicate-preview-item">
                            <span class="task-duplicate-preview-label">Priority:</span>
                            <span class="task-duplicate-preview-value task-duplicate-priority"></span>
                        </div>
                        <div class="task-duplicate-preview-item">
                            <span class="task-duplicate-preview-label">Due Date:</span>
                            <span class="task-duplicate-preview-value task-duplicate-due-date"></span>
                        </div>
                        <div class="task-duplicate-preview-item">
                            <span class="task-duplicate-preview-label">Assignees:</span>
                            <span class="task-duplicate-preview-value task-duplicate-assignees"></span>
                        </div>
                        <div class="task-duplicate-preview-item">
                            <span class="task-duplicate-preview-label">Labels:</span>
                            <span class="task-duplicate-preview-value task-duplicate-labels"></span>
                        </div>
                    </div>
                    <div class="task-duplicate-note">
                        The new task will be marked as <strong>[Copy]</strong> and will appear in your task list.
                    </div>
                </div>
                <div class="task-duplicate-modal-footer">
                    <button class="btn-secondary task-duplicate-cancel">Cancel</button>
                    <button class="btn-primary task-duplicate-confirm">
                        <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                        </svg>
                        Create Duplicate
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.modal);
    }

    setupEventListeners() {
        const closeBtn = this.modal.querySelector('.task-duplicate-modal-close');
        const cancelBtn = this.modal.querySelector('.task-duplicate-cancel');
        const confirmBtn = this.modal.querySelector('.task-duplicate-confirm');

        closeBtn.addEventListener('click', () => this.close(false));
        cancelBtn.addEventListener('click', () => this.close(false));
        confirmBtn.addEventListener('click', () => this.close(true));

        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close(false);
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('visible')) {
                this.close(false);
            }
        });
    }

    async show(task) {
        this.populatePreview(task);

        this.modal.classList.remove('hidden');
        this.modal.style.display = 'flex';
        requestAnimationFrame(() => {
            this.modal.classList.add('visible');
        });

        return new Promise((resolve) => {
            this.resolveCallback = resolve;
        });
    }

    populatePreview(task) {
        const titleEl = this.modal.querySelector('.task-duplicate-title');
        const priorityEl = this.modal.querySelector('.task-duplicate-priority');
        const dueDateEl = this.modal.querySelector('.task-duplicate-due-date');
        const assigneesEl = this.modal.querySelector('.task-duplicate-assignees');
        const labelsEl = this.modal.querySelector('.task-duplicate-labels');

        titleEl.textContent = task.title ? `${task.title} [Copy]` : 'Untitled Task [Copy]';
        
        priorityEl.innerHTML = `
            <span class="priority-badge priority-${(task.priority || 'medium').toLowerCase()}">
                ${task.priority || 'Medium'}
            </span>
        `;
        
        if (task.due_date) {
            const date = new Date(task.due_date);
            dueDateEl.textContent = date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                year: 'numeric' 
            });
        } else {
            dueDateEl.textContent = 'Not set';
            dueDateEl.style.opacity = '0.5';
        }

        if (task.assignee_ids && task.assignee_ids.length > 0) {
            assigneesEl.textContent = `${task.assignee_ids.length} assignee(s)`;
        } else {
            assigneesEl.textContent = 'Unassigned';
            assigneesEl.style.opacity = '0.5';
        }

        if (task.labels && task.labels.length > 0) {
            labelsEl.innerHTML = task.labels.map(label => 
                `<span class="task-label-chip">${label}</span>`
            ).join(' ');
        } else {
            labelsEl.textContent = 'No labels';
            labelsEl.style.opacity = '0.5';
        }
    }

    close(result) {
        this.modal.classList.remove('visible');
        
        setTimeout(() => {
            this.modal.style.display = 'none';
            if (this.resolveCallback) {
                this.resolveCallback(result);
                this.resolveCallback = null;
            }
        }, 200);
    }
}

window.taskDuplicateConfirmation = new TaskDuplicateConfirmation();
