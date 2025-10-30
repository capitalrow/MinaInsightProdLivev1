/**
 * CROWN⁴.5 Task Merge UI
 * Detects duplicate tasks via origin_hash and provides merge interface.
 * 
 * Features:
 * - Automatic duplicate detection via Deduper service
 * - Visual duplicate indicators
 * - Merge dialog with field selection
 * - Collapse animation on merge
 */

class TaskMergeUI {
    constructor() {
        this.duplicatePairs = new Map(); // task_id -> duplicate_task_id
        this.mergeHistory = [];
        
        this._init();
        console.log('[TaskMergeUI] Initialized');
    }

    /**
     * Initialize merge UI
     */
    _init() {
        this._setupListeners();
    }

    /**
     * Setup event listeners
     */
    _setupListeners() {
        // Listen for duplicate detection events
        window.addEventListener('task_duplicate_detected', (e) => {
            this.handleDuplicateDetected(e.detail);
        });

        // Listen for merge events
        window.addEventListener('task_merge_requested', (e) => {
            this.showMergeDialog(e.detail);
        });
    }

    /**
     * Handle duplicate detection
     * @param {Object} duplicateData
     */
    handleDuplicateDetected(duplicateData) {
        const {
            task_id,
            duplicate_of,
            similarity_score,
            matching_fields
        } = duplicateData;

        console.log(`[TaskMergeUI] Duplicate detected: ${task_id} is ${(similarity_score * 100).toFixed(0)}% similar to ${duplicate_of}`);

        // Store duplicate pair
        this.duplicatePairs.set(task_id, {
            duplicate_of,
            similarity_score,
            matching_fields
        });

        // Show duplicate indicator on task card
        this._showDuplicateIndicator(task_id, duplicate_of, similarity_score);
    }

    /**
     * Show duplicate indicator on task card
     * @param {string} task_id
     * @param {string} duplicate_of
     * @param {number} similarity_score
     */
    _showDuplicateIndicator(task_id, duplicate_of, similarity_score) {
        const taskCard = document.querySelector(`[data-task-id="${task_id}"]`);
        if (!taskCard) return;

        // Remove existing indicator
        const existing = taskCard.querySelector('.duplicate-indicator');
        if (existing) existing.remove();

        // Create duplicate indicator
        const indicator = document.createElement('div');
        indicator.className = 'duplicate-indicator';
        indicator.style.cssText = `
            margin-top: 8px;
            padding: 8px 12px;
            background: rgba(251, 146, 60, 0.1);
            border-left: 3px solid #f97316;
            border-radius: 6px;
            font-size: 13px;
            color: #c2410c;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        `;

        const percentage = (similarity_score * 100).toFixed(0);

        indicator.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
                <span>${percentage}% similar to another task</span>
            </div>
            <button class="btn-merge-duplicate" data-task-id="${task_id}" data-duplicate-of="${duplicate_of}" 
                    style="
                        background: #f97316;
                        color: white;
                        border: none;
                        padding: 4px 10px;
                        border-radius: 4px;
                        font-size: 12px;
                        font-weight: 500;
                        cursor: pointer;
                        transition: all 150ms ease-out;
                    ">Merge</button>
        `;

        // Handle merge button click
        const mergeButton = indicator.querySelector('.btn-merge-duplicate');
        mergeButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.showMergeDialog({
                source_task_id: task_id,
                target_task_id: duplicate_of
            });
        });

        mergeButton.addEventListener('mouseenter', () => {
            mergeButton.style.background = '#ea580c';
            mergeButton.style.transform = 'scale(1.05)';
        });

        mergeButton.addEventListener('mouseleave', () => {
            mergeButton.style.background = '#f97316';
            mergeButton.style.transform = 'scale(1)';
        });

        // Add to task content
        const taskContent = taskCard.querySelector('.task-content');
        if (taskContent) {
            taskContent.appendChild(indicator);
        }

        // Highlight duplicate pair
        this._highlightDuplicatePair(task_id, duplicate_of);
    }

    /**
     * Highlight duplicate pair
     * @param {string} task_id
     * @param {string} duplicate_of
     */
    _highlightDuplicatePair(task_id, duplicate_of) {
        const taskCard = document.querySelector(`[data-task-id="${task_id}"]`);
        const duplicateCard = document.querySelector(`[data-task-id="${duplicate_of}"]`);

        [taskCard, duplicateCard].forEach(card => {
            if (card) {
                card.style.borderColor = '#f97316';
                card.style.boxShadow = '0 0 0 2px rgba(251, 146, 60, 0.2)';
            }
        });
    }

    /**
     * Show merge dialog
     * @param {Object} mergeData
     */
    async showMergeDialog(mergeData) {
        const { source_task_id, target_task_id } = mergeData;

        // Fetch task data
        const [sourceTask, targetTask] = await Promise.all([
            this._fetchTask(source_task_id),
            this._fetchTask(target_task_id)
        ]);

        if (!sourceTask || !targetTask) {
            console.error('[TaskMergeUI] Failed to fetch tasks for merge');
            return;
        }

        // Create merge dialog
        const dialog = this._createMergeDialog(sourceTask, targetTask);
        document.body.appendChild(dialog);

        // Show dialog
        requestAnimationFrame(() => {
            dialog.style.opacity = '1';
        });
    }

    /**
     * Create merge dialog
     * @param {Object} sourceTask
     * @param {Object} targetTask
     * @returns {HTMLElement} Dialog element
     */
    _createMergeDialog(sourceTask, targetTask) {
        const dialog = document.createElement('div');
        dialog.className = 'task-merge-dialog';
        dialog.style.cssText = `
            position: fixed;
            inset: 0;
            z-index: 10000;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 300ms ease-out;
        `;

        dialog.innerHTML = `
            <div style="
                background: white;
                border-radius: 12px;
                padding: 24px;
                max-width: 600px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            ">
                <h3 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600;">
                    🔗 Merge Duplicate Tasks
                </h3>
                <p style="margin: 0 0 20px 0; font-size: 14px; color: #6b7280;">
                    Select which fields to keep from each task. The other task will be deleted.
                </p>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px;">
                    <div>
                        <div style="font-size: 12px; font-weight: 600; color: #9ca3af; margin-bottom: 8px;">
                            Task 1 (Keep this)
                        </div>
                        <div class="task-preview" style="
                            padding: 12px;
                            background: #f3f4f6;
                            border-radius: 6px;
                            border: 2px solid #3b82f6;
                        ">
                            <h4 style="margin: 0 0 6px 0; font-size: 14px; font-weight: 600;">
                                ${this._escapeHtml(targetTask.title)}
                            </h4>
                            ${targetTask.description ? `
                                <p style="margin: 0; font-size: 13px; color: #6b7280;">
                                    ${this._escapeHtml(targetTask.description)}
                                </p>
                            ` : ''}
                        </div>
                    </div>

                    <div>
                        <div style="font-size: 12px; font-weight: 600; color: #9ca3af; margin-bottom: 8px;">
                            Task 2 (Will be deleted)
                        </div>
                        <div class="task-preview" style="
                            padding: 12px;
                            background: #f3f4f6;
                            border-radius: 6px;
                            border: 2px solid #e5e7eb;
                        ">
                            <h4 style="margin: 0 0 6px 0; font-size: 14px; font-weight: 600;">
                                ${this._escapeHtml(sourceTask.title)}
                            </h4>
                            ${sourceTask.description ? `
                                <p style="margin: 0; font-size: 13px; color: #6b7280;">
                                    ${this._escapeHtml(sourceTask.description)}
                                </p>
                            ` : ''}
                        </div>
                    </div>
                </div>

                <div style="margin-bottom: 20px;">
                    <label style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                        <input type="checkbox" id="merge-labels" checked>
                        <span style="font-size: 14px;">Combine labels from both tasks</span>
                    </label>
                    
                    <label style="display: flex; align-items: center; gap: 8px;">
                        <input type="checkbox" id="merge-keep-priority" checked>
                        <span style="font-size: 14px;">Keep highest priority</span>
                    </label>
                </div>

                <div style="display: flex; gap: 8px;">
                    <button class="btn-cancel" style="
                        flex: 1;
                        background: #e5e7eb;
                        color: #374151;
                        border: none;
                        padding: 10px 16px;
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: 500;
                        cursor: pointer;
                    ">Cancel</button>
                    
                    <button class="btn-confirm-merge" style="
                        flex: 1;
                        background: #f97316;
                        color: white;
                        border: none;
                        padding: 10px 16px;
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: 500;
                        cursor: pointer;
                    ">Merge Tasks</button>
                </div>
            </div>
        `;

        // Handle cancel
        dialog.querySelector('.btn-cancel').addEventListener('click', () => {
            dialog.style.opacity = '0';
            setTimeout(() => dialog.remove(), 300);
        });

        // Handle merge
        dialog.querySelector('.btn-confirm-merge').addEventListener('click', async () => {
            const mergeLabels = dialog.querySelector('#merge-labels').checked;
            const keepHighestPriority = dialog.querySelector('#merge-keep-priority').checked;

            await this._executeMerge(sourceTask, targetTask, {
                mergeLabels,
                keepHighestPriority
            });

            dialog.style.opacity = '0';
            setTimeout(() => dialog.remove(), 300);
        });

        return dialog;
    }

    /**
     * Execute task merge
     * @param {Object} sourceTask - Task to be deleted
     * @param {Object} targetTask - Task to keep
     * @param {Object} options - Merge options
     */
    async _executeMerge(sourceTask, targetTask, options) {
        console.log(`[TaskMergeUI] Merging task ${sourceTask.id} into ${targetTask.id}`);

        try {
            // Build merged task data
            const mergedData = {
                ...targetTask
            };

            // Merge labels
            if (options.mergeLabels) {
                const allLabels = [
                    ...(targetTask.labels || []),
                    ...(sourceTask.labels || [])
                ];
                mergedData.labels = [...new Set(allLabels)]; // Remove duplicates
            }

            // Keep highest priority
            if (options.keepHighestPriority) {
                const priorityOrder = { high: 3, medium: 2, low: 1 };
                const sourcePriority = priorityOrder[sourceTask.priority] || 0;
                const targetPriority = priorityOrder[targetTask.priority] || 0;
                
                if (sourcePriority > targetPriority) {
                    mergedData.priority = sourceTask.priority;
                }
            }

            // Update target task
            await this._updateTask(targetTask.id, mergedData);

            // Delete source task with collapse animation
            await this._deleteTaskWithAnimation(sourceTask.id);

            // Record merge in history
            this.mergeHistory.push({
                source_id: sourceTask.id,
                target_id: targetTask.id,
                merged_at: Date.now(),
                merged_data: mergedData
            });

            // Clear duplicate pair
            this.duplicatePairs.delete(sourceTask.id);

            // Show success toast
            if (window.showToast) {
                window.showToast('Tasks merged successfully', 'success');
            }

            console.log(`[TaskMergeUI] Merge completed successfully`);

        } catch (error) {
            console.error('[TaskMergeUI] Merge failed:', error);
            
            if (window.showToast) {
                window.showToast('Failed to merge tasks', 'error');
            }
        }
    }

    /**
     * Delete task with collapse animation
     * @param {string} task_id
     */
    async _deleteTaskWithAnimation(task_id) {
        const taskCard = document.querySelector(`[data-task-id="${task_id}"]`);
        
        if (taskCard && window.crown45Animations) {
            // Trigger collapse animation
            window.crown45Animations.handleEvent('task_merge', taskCard);
            
            // Wait for animation to complete
            await new Promise(resolve => setTimeout(resolve, 600));
        }

        // Delete task
        await this._deleteTask(task_id);
    }

    /**
     * Fetch task by ID
     * @param {string} task_id
     * @returns {Promise<Object|null>}
     */
    async _fetchTask(task_id) {
        try {
            if (window.taskCache && typeof window.taskCache.getTask === 'function') {
                return await window.taskCache.getTask(task_id);
            }

            const response = await fetch(`/api/tasks/${task_id}`);
            if (!response.ok) return null;
            
            const data = await response.json();
            return data.task;
        } catch (error) {
            console.error(`[TaskMergeUI] Failed to fetch task ${task_id}:`, error);
            return null;
        }
    }

    /**
     * Update task
     * @param {string} task_id
     * @param {Object} updates
     */
    async _updateTask(task_id, updates) {
        const response = await fetch(`/api/tasks/${task_id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify(updates)
        });

        if (!response.ok) {
            throw new Error(`Update failed: ${response.status}`);
        }
    }

    /**
     * Delete task
     * @param {string} task_id
     */
    async _deleteTask(task_id) {
        const response = await fetch(`/api/tasks/${task_id}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`Delete failed: ${response.status}`);
        }
    }

    /**
     * Escape HTML
     * @param {string} text
     * @returns {string}
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Get merge statistics
     * @returns {Object}
     */
    getStats() {
        return {
            totalMerges: this.mergeHistory.length,
            activeDuplicatePairs: this.duplicatePairs.size
        };
    }
}

// Initialize global instance
window.TaskMergeUI = TaskMergeUI;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.taskMergeUI) {
            window.taskMergeUI = new TaskMergeUI();
            console.log('[TaskMergeUI] Global instance created');
        }
    });
}
