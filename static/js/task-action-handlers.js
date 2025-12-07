/**
 * Task Action Handlers
 * Listens for custom events from TaskActionsMenu and handles them
 * Opens modals, makes API calls, and updates the UI
 */

class TaskActionHandlers {
    constructor() {
        this.init();
    }

    init() {
        console.log('[TaskActionHandlers] Initializing...');
        this.registerEventListeners();
        console.log('[TaskActionHandlers] Initialized successfully');
    }

    registerEventListeners() {
        // PHASE 3.1: Assign User
        document.addEventListener('task:assign', async (e) => {
            const { taskId } = e.detail;
            await this.handleAssignUser(taskId);
        });

        // PHASE 3.2: Edit Labels
        document.addEventListener('task:labels', async (e) => {
            const { taskId } = e.detail;
            await this.handleEditLabels(taskId);
        });

        // PHASE 3.3: Duplicate Task
        document.addEventListener('task:duplicate', async (e) => {
            const { taskId } = e.detail;
            await this.handleDuplicateTask(taskId);
        });

        // PHASE 3.4: Snooze Task
        document.addEventListener('task:snooze', async (e) => {
            const { taskId } = e.detail;
            await this.handleSnoozeTask(taskId);
        });

        // PHASE 3.5: Merge Tasks
        document.addEventListener('task:merge', async (e) => {
            const { taskId } = e.detail;
            await this.handleMergeTasks(taskId);
        });
    }

    /**
     * PHASE 3.1: Handle assign user action
     * Opens TaskAssigneeSelector modal and updates assignee_ids via PATCH API
     */
    async handleAssignUser(taskId) {
        try {
            console.log(`[TaskActionHandlers] Opening assignee selector for task ${taskId}`);

            // Fetch current task data
            const task = await this.fetchTask(taskId);
            if (!task) return;

            // Open assignee selector modal
            const result = await window.taskAssigneeSelector.show(task.assignee_ids || []);
            
            if (result === null) {
                console.log('[TaskActionHandlers] Assignee selection cancelled');
                return;
            }

            // Update task via PATCH API
            await this.updateTask(taskId, { assignee_ids: result });

            window.toast?.success(`Assignees updated successfully`);
        } catch (error) {
            console.error('[TaskActionHandlers] Error handling assign user:', error);
            window.toast?.error('Failed to update assignees');
        }
    }

    /**
     * PHASE 3.2: Handle edit labels action
     * Opens TaskLabelsEditor modal and updates labels via PATCH API
     */
    async handleEditLabels(taskId) {
        try {
            console.log(`[TaskActionHandlers] Opening labels editor for task ${taskId}`);

            // Fetch current task data
            const task = await this.fetchTask(taskId);
            if (!task) return;

            // Open labels editor modal
            const result = await window.taskLabelsEditor.show(task.labels || []);
            
            if (result === null) {
                console.log('[TaskActionHandlers] Labels edit cancelled');
                return;
            }

            // Update task via PATCH API
            await this.updateTask(taskId, { labels: result });

            window.toast?.success(`Labels updated successfully`);
        } catch (error) {
            console.error('[TaskActionHandlers] Error handling edit labels:', error);
            window.toast?.error('Failed to update labels');
        }
    }

    /**
     * PHASE 3.3: Handle duplicate task action
     * Opens TaskDuplicateConfirmation modal and POSTs new task with source task data
     */
    async handleDuplicateTask(taskId) {
        try {
            console.log(`[TaskActionHandlers] Opening duplicate confirmation for task ${taskId}`);

            // Fetch current task data
            const task = await this.fetchTask(taskId);
            if (!task) return;

            // Open duplicate confirmation modal
            const confirmed = await window.taskDuplicateConfirmation.show(task);
            
            if (!confirmed) {
                console.log('[TaskActionHandlers] Duplication cancelled');
                return;
            }

            // Create duplicate via POST API
            const duplicateData = {
                title: task.title ? `${task.title} [Copy]` : 'Untitled Task [Copy]',
                description: task.description,
                priority: task.priority,
                due_date: task.due_date,
                assignee_ids: task.assignee_ids,
                labels: task.labels,
                meeting_id: task.meeting_id,
                workspace_id: task.workspace_id
            };

            const response = await fetch('/api/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(duplicateData)
            });

            if (!response.ok) {
                throw new Error('Failed to duplicate task');
            }

            const data = await response.json();
            
            if (data.success) {
                window.toast?.success(`Task duplicated successfully`);
                
                // Refresh task list (trigger re-render)
                if (window.taskBootstrap) {
                    await window.taskBootstrap.bootstrap();
                }
            } else {
                throw new Error(data.error || 'Failed to duplicate task');
            }
        } catch (error) {
            console.error('[TaskActionHandlers] Error handling duplicate task:', error);
            window.toast?.error('Failed to duplicate task');
        }
    }

    /**
     * PHASE 3.4: Handle snooze task action
     * Opens TaskSnoozeModal and updates snoozed_until via OptimisticUI/PATCH API
     */
    async handleSnoozeTask(taskId) {
        try {
            console.log(`[TaskActionHandlers] Opening snooze modal for task ${taskId}`);

            // Fetch current task data to get existing snoozed_until
            const task = await this.fetchTask(taskId);
            if (!task) return;

            // Open snooze modal with current snoozed_until value
            if (!window.taskSnoozeModal) {
                console.error('[TaskActionHandlers] TaskSnoozeModal not available');
                window.toast?.error('Snooze modal not available');
                return;
            }

            const snoozeUntil = await window.taskSnoozeModal.show(task.snoozed_until);
            
            if (snoozeUntil === null) {
                console.log('[TaskActionHandlers] Snooze cancelled');
                return;
            }

            // Update task via OptimisticUI or PATCH API
            const updates = { snoozed_until: snoozeUntil };

            if (window.optimisticUI && typeof window.optimisticUI.updateTask === 'function') {
                await window.optimisticUI.updateTask(taskId, updates);
                console.log(`[TaskActionHandlers] ✅ Task ${taskId} snoozed via optimisticUI`);
            } else {
                await this.updateTask(taskId, updates);
                console.log(`[TaskActionHandlers] ✅ Task ${taskId} snoozed via PATCH API`);
            }

            // Format the snooze date for user feedback
            const snoozeDate = new Date(snoozeUntil);
            const formattedDate = snoozeDate.toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit'
            });

            window.toast?.success(`Task snoozed until ${formattedDate}`);

            // Refresh task list to update visibility
            if (window.taskSearchSort?.refresh) {
                window.taskSearchSort.refresh();
            }

            // Telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_snoozed', 1, { taskId, snoozeUntil });
            }
        } catch (error) {
            console.error('[TaskActionHandlers] Error handling snooze task:', error);
            window.toast?.error('Failed to snooze task');
        }
    }

    /**
     * PHASE 3.5: Handle merge tasks action
     * Opens TaskMergeModal and POSTs to /api/tasks/merge endpoint
     */
    async handleMergeTasks(sourceTaskId) {
        try {
            console.log(`[TaskActionHandlers] Opening merge modal for task ${sourceTaskId}`);

            // Fetch source task data
            const sourceTask = await this.fetchTask(sourceTaskId);
            if (!sourceTask) return;

            // Open merge modal to select target task
            const targetTaskId = await window.taskMergeModal.show(sourceTask);
            
            if (targetTaskId === null) {
                console.log('[TaskActionHandlers] Merge cancelled');
                return;
            }

            // Merge tasks via POST API
            const response = await fetch('/api/tasks/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_task_id: sourceTaskId,
                    target_task_id: targetTaskId
                })
            });

            if (!response.ok) {
                // If merge endpoint doesn't exist, perform client-side merge
                if (response.status === 404) {
                    console.warn('[TaskActionHandlers] /api/tasks/merge endpoint not found, performing client-side merge');
                    await this.performClientSideMerge(sourceTaskId, targetTaskId);
                    return;
                }
                throw new Error('Failed to merge tasks');
            }

            const data = await response.json();
            
            if (data.success) {
                window.toast?.success(`Tasks merged successfully`);
                
                // Refresh task list
                if (window.taskBootstrap) {
                    await window.taskBootstrap.bootstrap();
                }
            } else {
                throw new Error(data.error || 'Failed to merge tasks');
            }
        } catch (error) {
            console.error('[TaskActionHandlers] Error handling merge tasks:', error);
            window.toast?.error('Failed to merge tasks');
        }
    }

    /**
     * Client-side merge fallback (if /api/tasks/merge doesn't exist)
     */
    async performClientSideMerge(sourceTaskId, targetTaskId) {
        try {
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

            // Update target task with merged data
            await this.updateTask(targetTaskId, {
                labels: mergedLabels,
                priority: mergedPriority
            });

            // Delete source task (soft delete)
            await fetch(`/api/tasks/${sourceTaskId}`, {
                method: 'DELETE'
            });

            window.toast?.success(`Tasks merged successfully`);

            // Refresh task list
            if (window.taskBootstrap) {
                await window.taskBootstrap.bootstrap();
            }
        } catch (error) {
            throw new Error(`Client-side merge failed: ${error.message}`);
        }
    }

    /**
     * Fetch task details from API
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
            console.error('[TaskActionHandlers] Error fetching task:', error);
            window.toast?.error('Failed to fetch task details');
            return null;
        }
    }

    /**
     * Update task via PATCH API
     */
    async updateTask(taskId, updates) {
        try {
            const response = await fetch(`/api/tasks/${taskId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });

            if (!response.ok) {
                throw new Error('Failed to update task');
            }

            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to update task');
            }

            // Optimistic UI will handle cache and DOM updates via WebSocket

            return data.task;
        } catch (error) {
            console.error('[TaskActionHandlers] Error updating task:', error);
            throw error;
        }
    }
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.taskActionHandlers = new TaskActionHandlers();
    });
} else {
    window.taskActionHandlers = new TaskActionHandlers();
}
