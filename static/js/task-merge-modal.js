/**
 * Task Merge Modal
 * Select target task from list and preview merged data
 */

class TaskMergeModal {
    constructor() {
        this.modal = null;
        this.resolveCallback = null;
        this.sourceTask = null;
        this.selectedTargetId = null;
        this.availableTasks = [];
        this.init();
    }

    init() {
        this.createModal();
        this.setupEventListeners();
    }

    createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'task-merge-modal-overlay';
        this.modal.innerHTML = `
            <div class="task-merge-modal">
                <div class="task-merge-modal-header">
                    <h3>Merge Tasks</h3>
                    <button class="task-merge-modal-close" title="Close">
                        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                    </button>
                </div>
                <div class="task-merge-modal-body">
                    <div class="task-merge-source">
                        <div class="task-merge-section-label">From:</div>
                        <div class="task-merge-source-task"></div>
                    </div>
                    
                    <div class="task-merge-arrow">
                        <svg width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M16.01 11H4v2h12.01v3L20 12l-3.99-4z"/>
                        </svg>
                    </div>

                    <div class="task-merge-target">
                        <div class="task-merge-section-label">Merge into:</div>
                        <div class="task-merge-search">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24" class="search-icon">
                                <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
                            </svg>
                            <input type="text" 
                                   class="task-merge-search-input" 
                                   placeholder="Search tasks..." 
                                   autocomplete="off">
                        </div>
                        <div class="task-merge-target-list"></div>
                        <div class="task-merge-loading" style="display: none;">
                            <div class="spinner"></div>
                            <div>Loading tasks...</div>
                        </div>
                    </div>

                    <div class="task-merge-preview" style="display: none;">
                        <div class="task-merge-section-label">Preview merged task:</div>
                        <div class="task-merge-preview-content"></div>
                    </div>

                    <div class="task-merge-warning">
                        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
                        </svg>
                        <span>The source task will be deleted after merging. This action cannot be undone.</span>
                    </div>
                </div>
                <div class="task-merge-modal-footer">
                    <button class="btn-secondary task-merge-cancel">Cancel</button>
                    <button class="btn-primary task-merge-confirm" disabled>Merge Tasks</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.modal);
    }

    setupEventListeners() {
        const closeBtn = this.modal.querySelector('.task-merge-modal-close');
        const cancelBtn = this.modal.querySelector('.task-merge-cancel');
        const confirmBtn = this.modal.querySelector('.task-merge-confirm');
        const searchInput = this.modal.querySelector('.task-merge-search-input');

        closeBtn.addEventListener('click', () => this.close(null));
        cancelBtn.addEventListener('click', () => this.close(null));
        confirmBtn.addEventListener('click', () => {
            if (this.selectedTargetId) {
                this.close(this.selectedTargetId);
            }
        });

        searchInput.addEventListener('input', (e) => {
            this.filterTasks(e.target.value);
        });

        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close(null);
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('visible')) {
                this.close(null);
            }
        });
    }

    async show(sourceTask) {
        this.sourceTask = sourceTask;
        this.selectedTargetId = null;
        
        this.renderSourceTask();
        
        const loading = this.modal.querySelector('.task-merge-loading');
        const targetList = this.modal.querySelector('.task-merge-target-list');
        const confirmBtn = this.modal.querySelector('.task-merge-confirm');
        const preview = this.modal.querySelector('.task-merge-preview');
        
        loading.style.display = 'flex';
        targetList.style.display = 'none';
        preview.style.display = 'none';
        confirmBtn.disabled = true;

        this.modal.classList.remove('hidden');
        this.modal.style.display = 'flex';
        requestAnimationFrame(() => {
            this.modal.classList.add('visible');
        });

        try {
            await this.loadTasks();
            this.renderTargetTasks();
            loading.style.display = 'none';
            targetList.style.display = 'block';
            
            const searchInput = this.modal.querySelector('.task-merge-search-input');
            searchInput.value = '';
            searchInput.focus();
        } catch (err) {
            loading.style.display = 'none';
            console.error('Failed to load tasks:', err);
            window.toast?.error('Failed to load tasks');
        }

        return new Promise((resolve) => {
            this.resolveCallback = resolve;
        });
    }

    renderSourceTask() {
        const sourceContainer = this.modal.querySelector('.task-merge-source-task');
        sourceContainer.innerHTML = `
            <div class="task-merge-task-card">
                <div class="task-merge-task-title">${this.sourceTask.title || 'Untitled Task'}</div>
                <div class="task-merge-task-meta">
                    <span class="priority-badge priority-${(this.sourceTask.priority || 'medium').toLowerCase()}">
                        ${this.sourceTask.priority || 'Medium'}
                    </span>
                    ${this.sourceTask.due_date ? `<span class="task-merge-due-date">${new Date(this.sourceTask.due_date).toLocaleDateString()}</span>` : ''}
                </div>
            </div>
        `;
    }

    async loadTasks() {
        const response = await fetch('/api/tasks');
        if (!response.ok) {
            throw new Error('Failed to load tasks');
        }
        const data = await response.json();
        this.availableTasks = (data.tasks || []).filter(t => t.id !== this.sourceTask.id && !t.completed);
    }

    renderTargetTasks(filteredTasks = null) {
        const tasks = filteredTasks || this.availableTasks;
        const targetList = this.modal.querySelector('.task-merge-target-list');
        
        if (tasks.length === 0) {
            targetList.innerHTML = '<div class="task-merge-empty">No tasks available to merge into</div>';
            return;
        }

        targetList.innerHTML = tasks.map(task => `
            <div class="task-merge-task-option ${this.selectedTargetId === task.id ? 'selected' : ''}" 
                 data-task-id="${task.id}">
                <div class="task-merge-task-title">${task.title || 'Untitled Task'}</div>
                <div class="task-merge-task-meta">
                    <span class="priority-badge priority-${(task.priority || 'medium').toLowerCase()}">
                        ${task.priority || 'Medium'}
                    </span>
                    ${task.due_date ? `<span class="task-merge-due-date">${new Date(task.due_date).toLocaleDateString()}</span>` : ''}
                    ${task.labels && task.labels.length > 0 ? `<span class="task-merge-labels">${task.labels.length} labels</span>` : ''}
                </div>
            </div>
        `).join('');

        targetList.querySelectorAll('.task-merge-task-option').forEach(option => {
            option.addEventListener('click', () => {
                const taskId = parseInt(option.dataset.taskId);
                this.selectTargetTask(taskId);
            });
        });
    }

    selectTargetTask(taskId) {
        this.selectedTargetId = taskId;
        
        const options = this.modal.querySelectorAll('.task-merge-task-option');
        options.forEach(opt => {
            if (parseInt(opt.dataset.taskId) === taskId) {
                opt.classList.add('selected');
            } else {
                opt.classList.remove('selected');
            }
        });

        const confirmBtn = this.modal.querySelector('.task-merge-confirm');
        confirmBtn.disabled = false;

        this.renderMergePreview();
    }

    renderMergePreview() {
        const targetTask = this.availableTasks.find(t => t.id === this.selectedTargetId);
        if (!targetTask) return;

        const preview = this.modal.querySelector('.task-merge-preview');
        const content = this.modal.querySelector('.task-merge-preview-content');
        
        const mergedLabels = [...new Set([...(this.sourceTask.labels || []), ...(targetTask.labels || [])])];
        const mergedPriority = this.getHigherPriority(this.sourceTask.priority, targetTask.priority);
        
        content.innerHTML = `
            <div class="task-merge-preview-item">
                <span class="task-merge-preview-label">Title:</span>
                <span class="task-merge-preview-value">${targetTask.title || 'Untitled Task'}</span>
            </div>
            <div class="task-merge-preview-item">
                <span class="task-merge-preview-label">Priority:</span>
                <span class="task-merge-preview-value">
                    <span class="priority-badge priority-${mergedPriority.toLowerCase()}">${mergedPriority}</span>
                </span>
            </div>
            <div class="task-merge-preview-item">
                <span class="task-merge-preview-label">Labels:</span>
                <span class="task-merge-preview-value">
                    ${mergedLabels.length > 0 ? mergedLabels.map(l => `<span class="task-label-chip">${l}</span>`).join(' ') : 'None'}
                </span>
            </div>
            <div class="task-merge-preview-note">
                All other properties will be preserved from the target task.
            </div>
        `;
        
        preview.style.display = 'block';
    }

    getHigherPriority(p1, p2) {
        const priorities = { high: 3, medium: 2, low: 1 };
        const priority1 = priorities[(p1 || 'medium').toLowerCase()] || 2;
        const priority2 = priorities[(p2 || 'medium').toLowerCase()] || 2;
        
        if (priority1 >= priority2) {
            return Object.keys(priorities).find(key => priorities[key] === priority1) || 'medium';
        } else {
            return Object.keys(priorities).find(key => priorities[key] === priority2) || 'medium';
        }
    }

    filterTasks(searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        if (!term) {
            this.renderTargetTasks();
            return;
        }

        const filtered = this.availableTasks.filter(task => {
            const title = (task.title || '').toLowerCase();
            const labels = (task.labels || []).join(' ').toLowerCase();
            return title.includes(term) || labels.includes(term);
        });

        this.renderTargetTasks(filtered);
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

window.taskMergeModal = new TaskMergeModal();
