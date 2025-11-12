/**
 * CROWN⁴.5 Phase 1.3: Task Merge UI Component
 * Displays duplicate detection results and merge options
 */

class TaskMergeUI {
    constructor() {
        this.activeModal = null;
        this.onMergeCallback = null;
        this.onCreateAnywayCallback = null;
        this.onCancelCallback = null;
    }

    async checkDuplicate(taskData) {
        try {
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('duplicate_check_started', 1);
            }

            const response = await fetch('/api/tasks/check-duplicate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: taskData.title,
                    description: taskData.description,
                    assigned_to_id: taskData.assigned_to_id,
                    meeting_id: taskData.meeting_id,
                    session_id: taskData.session_id
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }

            const result = await response.json();

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('duplicate_check_completed', 1);
                if (result.is_duplicate) {
                    window.CROWNTelemetry.recordMetric('duplicate_detected', 1);
                    window.CROWNTelemetry.recordMetric(`duplicate_type_${result.duplicate_type}`, 1);
                }
            }

            return result;

        } catch (error) {
            console.error('Failed to check duplicate:', error);
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('duplicate_check_error', 1);
            }

            return {
                success: false,
                is_duplicate: false,
                duplicate_type: 'error',
                message: error.message
            };
        }
    }

    showDuplicateModal(duplicateResult, taskData) {
        return new Promise((resolve) => {
            this.closeModal();

            const modal = this.createDuplicateModal(duplicateResult, taskData);
            document.body.appendChild(modal);
            this.activeModal = modal;

            setTimeout(() => modal.classList.add('visible'), 10);

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('duplicate_modal_shown', 1);
            }

            this.onMergeCallback = (targetTaskId) => {
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('duplicate_merge_selected', 1);
                }
                this.closeModal();
                resolve({ action: 'merge', targetTaskId });
            };

            this.onCreateAnywayCallback = () => {
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('duplicate_create_anyway', 1);
                }
                this.closeModal();
                resolve({ action: 'create_anyway' });
            };

            this.onCancelCallback = () => {
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('duplicate_modal_cancelled', 1);
                }
                this.closeModal();
                resolve({ action: 'cancel' });
            };
        });
    }

    createDuplicateModal(duplicateResult, taskData) {
        const modal = document.createElement('div');
        modal.className = 'task-merge-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-labelledby', 'merge-modal-title');

        const duplicateType = duplicateResult.duplicate_type;
        const confidence = duplicateResult.confidence || 0;
        const existingTask = duplicateResult.existing_task;
        const similarTasks = duplicateResult.similar_tasks || [];

        const isExactDuplicate = duplicateType === 'exact';
        const title = isExactDuplicate 
            ? 'Exact Duplicate Detected' 
            : `Possible Duplicate (${Math.round(confidence * 100)}% similar)`;

        const icon = isExactDuplicate ? '⚠️' : '🔍';

        modal.innerHTML = `
            <div class="modal-backdrop"></div>
            <div class="modal-content merge-modal-content">
                <div class="modal-header">
                    <div class="modal-title-row">
                        <span class="modal-icon">${icon}</span>
                        <h2 id="merge-modal-title">${title}</h2>
                    </div>
                    <button class="modal-close-btn" aria-label="Close">×</button>
                </div>

                <div class="modal-body">
                    <div class="duplicate-info">
                        <p class="duplicate-message">
                            ${duplicateResult.recommendation}
                        </p>
                    </div>

                    <div class="task-comparison">
                        <div class="task-card new-task">
                            <div class="task-card-header">
                                <span class="task-label">New Task</span>
                            </div>
                            <div class="task-card-body">
                                <div class="task-title">${this.escapeHtml(taskData.title)}</div>
                                ${taskData.description ? `
                                    <div class="task-description">${this.escapeHtml(taskData.description)}</div>
                                ` : ''}
                                ${this.renderTaskMetadata(taskData)}
                            </div>
                        </div>

                        ${existingTask ? `
                            <div class="merge-arrow">→</div>
                            <div class="task-card existing-task">
                                <div class="task-card-header">
                                    <span class="task-label">Existing Task</span>
                                    <span class="confidence-badge">${Math.round(confidence * 100)}% match</span>
                                </div>
                                <div class="task-card-body">
                                    <div class="task-title">${this.escapeHtml(existingTask.title)}</div>
                                    ${existingTask.description ? `
                                        <div class="task-description">${this.escapeHtml(existingTask.description)}</div>
                                    ` : ''}
                                    ${this.renderTaskMetadata(existingTask)}
                                </div>
                            </div>
                        ` : ''}
                    </div>

                    ${similarTasks.length > 0 && !existingTask ? `
                        <div class="similar-tasks-list">
                            <h3>Similar Tasks Found</h3>
                            ${similarTasks.slice(0, 3).map(task => `
                                <div class="similar-task-item" data-task-id="${task.id}">
                                    <div class="similar-task-content">
                                        <div class="similar-task-title">${this.escapeHtml(task.title)}</div>
                                        <div class="similar-task-meta">
                                            ${task.priority ? `<span class="priority-${task.priority}">${task.priority}</span>` : ''}
                                            ${task.status ? `<span class="status-${task.status}">${task.status}</span>` : ''}
                                        </div>
                                    </div>
                                    <span class="similarity-score">${Math.round(task.similarity * 100)}%</span>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>

                <div class="modal-footer">
                    ${existingTask ? `
                        <button class="btn btn-primary merge-btn" data-task-id="${existingTask.id}">
                            Merge with Existing
                        </button>
                    ` : ''}
                    <button class="btn btn-secondary create-anyway-btn">
                        Create Anyway
                    </button>
                    <button class="btn btn-ghost cancel-btn">
                        Cancel
                    </button>
                </div>
            </div>
        `;

        this.attachModalEventListeners(modal, existingTask);

        return modal;
    }

    renderTaskMetadata(task) {
        const parts = [];

        if (task.priority) {
            parts.push(`<span class="task-meta-item priority-${task.priority}">${task.priority}</span>`);
        }

        if (task.status) {
            parts.push(`<span class="task-meta-item status-${task.status}">${task.status}</span>`);
        }

        if (task.due_date) {
            parts.push(`<span class="task-meta-item">Due: ${task.due_date}</span>`);
        }

        if (task.labels && task.labels.length > 0) {
            parts.push(`<span class="task-meta-item">Labels: ${task.labels.join(', ')}</span>`);
        }

        return parts.length > 0 
            ? `<div class="task-metadata">${parts.join('')}</div>` 
            : '';
    }

    attachModalEventListeners(modal, existingTask) {
        const closeBtn = modal.querySelector('.modal-close-btn');
        const cancelBtn = modal.querySelector('.cancel-btn');
        const createAnywayBtn = modal.querySelector('.create-anyway-btn');
        const mergeBtn = modal.querySelector('.merge-btn');
        const backdrop = modal.querySelector('.modal-backdrop');

        closeBtn?.addEventListener('click', () => this.onCancelCallback?.());
        cancelBtn?.addEventListener('click', () => this.onCancelCallback?.());
        backdrop?.addEventListener('click', () => this.onCancelCallback?.());
        createAnywayBtn?.addEventListener('click', () => this.onCreateAnywayCallback?.());

        if (mergeBtn && existingTask) {
            mergeBtn.addEventListener('click', () => {
                this.onMergeCallback?.(existingTask.id);
            });
        }

        modal.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.onCancelCallback?.();
            }
        });
    }

    closeModal() {
        if (this.activeModal) {
            this.activeModal.classList.remove('visible');
            setTimeout(() => {
                this.activeModal.remove();
                this.activeModal = null;
            }, 300);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async mergeTasksViaAPI(targetTaskId, sourceTaskData) {
        try {
            const createResponse = await fetch('/api/tasks/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(sourceTaskData)
            });

            if (!createResponse.ok) {
                throw new Error('Failed to create temporary task');
            }

            const { task: tempTask } = await createResponse.json();

            const mergeResponse = await fetch(`/api/tasks/${targetTaskId}/merge`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    source_task_id: tempTask.id
                })
            });

            if (!mergeResponse.ok) {
                throw new Error('Failed to merge tasks');
            }

            return await mergeResponse.json();

        } catch (error) {
            console.error('Failed to merge tasks:', error);
            throw error;
        }
    }
}

if (typeof window !== 'undefined') {
    window.TaskMergeUI = TaskMergeUI;
}

const addMergeUIStyles = () => {
    if (document.getElementById('task-merge-ui-styles')) return;

    const style = document.createElement('style');
    style.id = 'task-merge-ui-styles';
    style.textContent = `
        .task-merge-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .task-merge-modal.visible {
            opacity: 1;
        }

        .modal-backdrop {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
        }

        .merge-modal-content {
            position: relative;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-xl);
            max-width: 800px;
            width: 90%;
            max-height: 90vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            transform: scale(0.95);
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .task-merge-modal.visible .merge-modal-content {
            transform: scale(1);
        }

        .modal-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--glass-border);
        }

        .modal-title-row {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .modal-icon {
            font-size: 1.5rem;
        }

        .modal-header h2 {
            margin: 0;
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--color-text-primary);
        }

        .modal-close-btn {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: transparent;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: var(--color-text-secondary);
            width: 2rem;
            height: 2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: var(--radius-md);
            transition: all 0.2s;
        }

        .modal-close-btn:hover {
            background: var(--color-bg-secondary);
            color: var(--color-text-primary);
        }

        .modal-body {
            padding: 1.5rem;
            overflow-y: auto;
            flex: 1;
        }

        .duplicate-info {
            margin-bottom: 1.5rem;
        }

        .duplicate-message {
            margin: 0;
            color: var(--color-text-secondary);
            line-height: 1.5;
        }

        .task-comparison {
            display: flex;
            gap: 1rem;
            align-items: center;
            margin-bottom: 1.5rem;
        }

        .merge-arrow {
            font-size: 1.5rem;
            color: var(--color-text-secondary);
            flex-shrink: 0;
        }

        .task-card {
            flex: 1;
            background: var(--color-bg-secondary);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-lg);
            overflow: hidden;
        }

        .task-card-header {
            padding: 0.75rem 1rem;
            background: var(--color-bg-tertiary);
            border-bottom: 1px solid var(--glass-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .task-label {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--color-text-secondary);
        }

        .confidence-badge {
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.25rem 0.5rem;
            background: var(--color-primary);
            color: white;
            border-radius: var(--radius-full);
        }

        .task-card-body {
            padding: 1rem;
        }

        .task-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--color-text-primary);
            margin-bottom: 0.5rem;
        }

        .task-description {
            font-size: 0.875rem;
            color: var(--color-text-secondary);
            margin-bottom: 0.75rem;
        }

        .task-metadata {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }

        .task-meta-item {
            font-size: 0.75rem;
            padding: 0.25rem 0.5rem;
            background: var(--color-bg-tertiary);
            border-radius: var(--radius-sm);
            color: var(--color-text-secondary);
        }

        .task-meta-item.priority-urgent {
            background: var(--color-error);
            color: white;
        }

        .task-meta-item.priority-high {
            background: var(--color-warning);
            color: white;
        }

        .similar-tasks-list {
            margin-top: 1.5rem;
        }

        .similar-tasks-list h3 {
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--color-text-secondary);
            margin: 0 0 0.75rem 0;
        }

        .similar-task-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem;
            background: var(--color-bg-secondary);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            margin-bottom: 0.5rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .similar-task-item:hover {
            border-color: var(--color-primary);
            background: var(--color-bg-tertiary);
        }

        .similar-task-content {
            flex: 1;
        }

        .similar-task-title {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--color-text-primary);
            margin-bottom: 0.25rem;
        }

        .similar-task-meta {
            display: flex;
            gap: 0.5rem;
        }

        .similar-task-meta span {
            font-size: 0.75rem;
            padding: 0.125rem 0.375rem;
            background: var(--color-bg-tertiary);
            border-radius: var(--radius-sm);
            color: var(--color-text-secondary);
        }

        .similarity-score {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--color-primary);
        }

        .modal-footer {
            padding: 1rem 1.5rem;
            border-top: 1px solid var(--glass-border);
            display: flex;
            gap: 0.75rem;
            justify-content: flex-end;
        }

        .btn {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: var(--radius-md);
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary {
            background: var(--color-primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--color-primary-hover);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        .btn-secondary {
            background: var(--color-bg-secondary);
            color: var(--color-text-primary);
            border: 1px solid var(--glass-border);
        }

        .btn-secondary:hover {
            background: var(--color-bg-tertiary);
            border-color: var(--color-text-secondary);
        }

        .btn-ghost {
            background: transparent;
            color: var(--color-text-secondary);
        }

        .btn-ghost:hover {
            background: var(--color-bg-secondary);
            color: var(--color-text-primary);
        }

        @media (max-width: 768px) {
            .task-comparison {
                flex-direction: column;
            }

            .merge-arrow {
                transform: rotate(90deg);
            }
        }
    `;

    document.head.appendChild(style);
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addMergeUIStyles);
} else {
    addMergeUIStyles();
}
