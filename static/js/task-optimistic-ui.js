/**
 * CROWN⁴.5 Optimistic UI Update System
 * Applies changes instantly to DOM, queues to IndexedDB, syncs to server.
 * Provides <150ms reconciliation on success, rollback on failure.
 */

class OptimisticUI {
    constructor() {
        this.cache = window.taskCache;
        this.pendingOperations = new Map();
        this.operationCounter = 0;
        this._setupReconnectHandler();
    }

    /**
     * Setup WebSocket reconnect handler to retry pending operations
     */
    _setupReconnectHandler() {
        if (!window.wsManager) {
            console.warn('⚠️ WebSocketManager not available for reconnect handling');
            return;
        }

        // Listen for connection status changes
        window.wsManager.on('connection_status', (data) => {
            if (data.namespace === '/tasks') {
                if (data.connected) {
                    console.log('🔄 WebSocket reconnected, retrying pending operations...');
                    this._showConnectionBanner('online', 'Connected', 2000);
                    this._retryPendingOperations();
                } else {
                    this._showConnectionBanner('offline', 'Offline - changes will sync when reconnected');
                }
            }
        });
        
        window.wsManager.on('reconnecting', (data) => {
            if (data.namespace === '/tasks') {
                this._showConnectionBanner('reconnecting', 'Reconnecting...');
            }
        });
    }
    
    _showConnectionBanner(status, message, autohideDuration = 0) {
        const banner = document.getElementById('connection-banner');
        if (!banner) return;
        
        banner.className = `connection-banner ${status}`;
        banner.querySelector('.connection-message').textContent = message;
        
        const pendingCount = this.pendingOperations.size;
        const pendingEl = banner.querySelector('.pending-count');
        if (pendingCount > 0) {
            pendingEl.textContent = `(${pendingCount} pending)`;
            pendingEl.style.display = 'inline';
        } else {
            pendingEl.style.display = 'none';
        }
        
        banner.style.display = 'flex';
        
        if (autohideDuration > 0) {
            setTimeout(() => {
                banner.style.display = 'none';
            }, autohideDuration);
        }
    }

    /**
     * Retry pending operations after WebSocket reconnect
     */
    async _retryPendingOperations() {
        if (this.pendingOperations.size === 0) {
            console.log('✅ No pending operations to retry');
            return;
        }

        console.log(`🔄 Retrying ${this.pendingOperations.size} pending operations...`);
        const operations = Array.from(this.pendingOperations.entries());

        for (const [opId, operation] of operations) {
            try {
                console.log(`🔄 Retrying operation ${opId} (${operation.type})`);
                
                if (operation.type === 'create') {
                    // Use clean original data, not optimistic version
                    await this._syncToServer(opId, 'create', operation.data, operation.tempId);
                } else if (operation.type === 'update') {
                    // Use clean updates data
                    await this._syncToServer(opId, 'update', operation.data, operation.taskId);
                } else if (operation.type === 'delete') {
                    await this._syncToServer(opId, 'delete', {}, operation.taskId);
                }
            } catch (error) {
                console.error(`❌ Retry failed for operation ${opId}:`, error);
            }
        }
    }

    /**
     * Retry a single operation
     */
    async _retryOperation(opId) {
        const operation = this.pendingOperations.get(opId);
        if (!operation) {
            console.warn(`⚠️ Operation ${opId} not found for retry`);
            return;
        }

        console.log(`🔄 Retrying operation ${opId} (${operation.type})`);
        
        try {
            if (operation.type === 'create') {
                await this._syncToServer(opId, 'create', operation.data, operation.tempId);
            } else if (operation.type === 'update') {
                await this._syncToServer(opId, 'update', operation.data, operation.taskId);
            } else if (operation.type === 'delete') {
                await this._syncToServer(opId, 'delete', {}, operation.taskId);
            }
            
            if (window.toast) {
                window.toast.success('Changes saved successfully');
            }
        } catch (error) {
            console.error(`❌ Retry failed for operation ${opId}:`, error);
        }
    }

    /**
     * Create task optimistically
     * @param {Object} taskData
     * @returns {Promise<Object>} Created task
     */
    async createTask(taskData) {
        const opId = this._generateOperationId();
        const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        const optimisticTask = {
            id: tempId,
            ...taskData,
            status: taskData.status || 'todo',
            priority: taskData.priority || 'medium',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            _optimistic: true,
            _operation_id: opId
        };

        try {
            // Step 1: Update DOM immediately (<50ms)
            this._addTaskToDOM(optimisticTask);
            
            // Step 2: Save to IndexedDB
            await this.cache.saveTask(optimisticTask);
            
            // Step 3: Queue event and offline operation via OfflineQueueManager
            await this.cache.addEvent({
                event_type: 'task_create',
                task_id: tempId,
                data: taskData,
                timestamp: Date.now()
            });

            // Use OfflineQueueManager for proper session tracking and replay
            let queueId = null;
            if (window.offlineQueue) {
                queueId = await window.offlineQueue.queueOperation({
                    type: 'task_create',
                    temp_id: tempId,
                    data: taskData,
                    priority: 10,
                    operation_id: opId  // Link queue entry to operation
                });
            }

            // Step 4: Sync to server
            // Store ORIGINAL clean data (not optimistic version) for retry
            this.pendingOperations.set(opId, { 
                type: 'create', 
                tempId, 
                task: optimisticTask,  // Keep for rollback
                data: taskData,  // Original clean data for retry
                queueId  // Store queue ID to remove on success
            });
            this._syncToServer(opId, 'create', taskData, tempId);

            return optimisticTask;
        } catch (error) {
            console.error('❌ Optimistic create failed:', error);
            this._rollbackCreate(tempId);
            throw error;
        }
    }

    /**
     * Update task optimistically
     * @param {number|string} taskId
     * @param {Object} updates
     * @returns {Promise<Object>} Updated task
     */
    async updateTask(taskId, updates) {
        const opId = this._generateOperationId();
        
        try {
            // Get current task
            const currentTask = await this.cache.getTask(taskId);
            if (!currentTask) {
                throw new Error('Task not found');
            }

            // Create optimistic version
            const optimisticTask = {
                ...currentTask,
                ...updates,
                updated_at: new Date().toISOString(),
                _optimistic: true,
                _operation_id: opId
            };

            // Step 1: Update DOM immediately
            this._updateTaskInDOM(taskId, optimisticTask);
            
            // Step 2: Update IndexedDB
            await this.cache.saveTask(optimisticTask);
            
            // Step 3: Queue event via OfflineQueueManager
            await this.cache.addEvent({
                event_type: 'task_update',
                task_id: taskId,
                data: updates,
                timestamp: Date.now()
            });

            // Use OfflineQueueManager for proper session tracking and replay
            let queueId = null;
            if (window.offlineQueue) {
                queueId = await window.offlineQueue.queueOperation({
                    type: 'task_update',
                    task_id: taskId,
                    data: updates,
                    priority: 5,
                    operation_id: opId  // Link queue entry to operation
                });
            }

            // Step 4: Sync to server
            // Store clean updates data for retry
            this.pendingOperations.set(opId, { 
                type: 'update', 
                taskId, 
                previous: currentTask,  // Keep for rollback
                updates,  // Clean updates data for retry
                data: updates,  // Explicit clean data reference
                queueId  // Store queue ID to remove on success
            });
            this._syncToServer(opId, 'update', updates, taskId);

            return optimisticTask;
        } catch (error) {
            console.error('❌ Optimistic update failed:', error);
            throw error;
        }
    }

    /**
     * Delete task optimistically
     * @param {number|string} taskId
     * @returns {Promise<void>}
     */
    async deleteTask(taskId) {
        const opId = this._generateOperationId();
        
        try {
            // Get task for rollback
            const task = await this.cache.getTask(taskId);
            if (!task) {
                throw new Error('Task not found');
            }

            // Step 1: Remove from DOM immediately
            this._removeTaskFromDOM(taskId);
            
            // Step 2: Delete from IndexedDB
            await this.cache.deleteTask(taskId);
            
            // Step 3: Queue event via OfflineQueueManager
            await this.cache.addEvent({
                event_type: 'task_delete',
                task_id: taskId,
                timestamp: Date.now()
            });

            // Use OfflineQueueManager for proper session tracking and replay
            let queueId = null;
            if (window.offlineQueue) {
                queueId = await window.offlineQueue.queueOperation({
                    type: 'task_delete',
                    task_id: taskId,
                    priority: 8,
                    operation_id: opId  // Link queue entry to operation
                });
            }

            // Step 4: Sync to server
            this.pendingOperations.set(opId, { 
                type: 'delete', 
                taskId, 
                task,  // Keep for rollback
                queueId  // Store queue ID to remove on success
            });
            this._syncToServer(opId, 'delete', null, taskId);

        } catch (error) {
            console.error('❌ Optimistic delete failed:', error);
            throw error;
        }
    }

    /**
     * Toggle task status optimistically
     * @param {number|string} taskId
     * @returns {Promise<Object>}
     */
    async toggleTaskStatus(taskId) {
        const task = await this.cache.getTask(taskId);
        if (!task) return;

        const newStatus = task.status === 'completed' ? 'todo' : 'completed';
        const updates = {
            status: newStatus,
            completed_at: newStatus === 'completed' ? new Date().toISOString() : null
        };

        const result = await this.updateTask(taskId, updates);

        if (newStatus === 'completed' && window.emotionalAnimations) {
            const card = document.querySelector(`[data-task-id="${taskId}"]`);
            if (card) {
                window.emotionalAnimations.celebrate(card, ['burst', 'shimmer']);
            }
        }

        return result;
    }

    /**
     * Snooze task optimistically
     * @param {number|string} taskId
     * @param {Date} snoozeUntil
     * @returns {Promise<Object>}
     */
    async snoozeTask(taskId, snoozeUntil) {
        return this.updateTask(taskId, {
            snoozed_until: snoozeUntil.toISOString()
        });
    }

    /**
     * Update task priority optimistically
     * @param {number|string} taskId
     * @param {string} priority
     * @returns {Promise<Object>}
     */
    async updatePriority(taskId, priority) {
        const result = await this.updateTask(taskId, { priority });

        if (window.emotionalAnimations) {
            const card = document.querySelector(`[data-task-id="${taskId}"]`);
            if (card) {
                window.emotionalAnimations.shimmer(card, {
                    emotion_cue: 'priority_change'
                });
            }
        }

        return result;
    }

    /**
     * Add label to task optimistically
     * @param {number|string} taskId
     * @param {string} label
     * @returns {Promise<Object>}
     */
    async addLabel(taskId, label) {
        const task = await this.cache.getTask(taskId);
        if (!task) return;

        const labels = task.labels || [];
        if (!labels.includes(label)) {
            labels.push(label);
        }

        return this.updateTask(taskId, { labels });
    }

    /**
     * Remove label from task optimistically
     * @param {number|string} taskId
     * @param {string} label
     * @returns {Promise<Object>}
     */
    async removeLabel(taskId, label) {
        const task = await this.cache.getTask(taskId);
        if (!task) return;

        const labels = task.labels || [];
        const updatedLabels = labels.filter(l => l !== label);

        return this.updateTask(taskId, { labels: updatedLabels });
    }

    /**
     * Snooze task optimistically
     * @param {number|string} taskId
     * @param {Date} snoozedUntil - When to unsnooze the task
     * @returns {Promise<Object>}
     */
    async snoozeTask(taskId, snoozedUntil) {
        const task = await this.cache.getTask(taskId);
        if (!task) return;

        // Update task with snooze timestamp
        const result = await this.updateTask(taskId, { 
            snoozed_until: snoozedUntil.toISOString()
        });

        // Hide snoozed task from view with animation (CROWN⁴.5 QuietStateManager)
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (card && window.quietStateManager) {
            window.quietStateManager.queueAnimation((setCancelHandler) => {
                card.style.animation = 'fadeOut 0.3s ease-out';
                const timeoutId = setTimeout(() => {
                    card.style.display = 'none';
                    this._updateCounters();
                }, 300);
                
                setCancelHandler(() => {
                    clearTimeout(timeoutId);
                    card.style.animation = '';
                });
            }, { duration: 300, priority: 6, metadata: { type: 'task_snooze', task_id: taskId } });
        } else if (card) {
            card.style.animation = 'fadeOut 0.3s ease-out';
            setTimeout(() => {
                card.style.display = 'none';
                this._updateCounters();
            }, 300);
        }

        return result;
    }

    /**
     * Merge two tasks optimistically
     * @param {number|string} sourceTaskId - Task to merge from (will be deleted)
     * @param {number|string} targetTaskId - Task to merge into (will be kept)
     * @returns {Promise<Object>}
     */
    async mergeTasks(sourceTaskId, targetTaskId) {
        const sourceTask = await this.cache.getTask(sourceTaskId);
        const targetTask = await this.cache.getTask(targetTaskId);
        
        if (!sourceTask || !targetTask) return;

        const opId = this._generateOperationId();
        
        // Save original target task state for rollback
        const originalTargetTask = { ...targetTask };

        try {
            // Step 1: Hide source task with animation (CROWN⁴.5 QuietStateManager)
            const sourceCard = document.querySelector(`[data-task-id="${sourceTaskId}"]`);
            if (sourceCard && window.quietStateManager) {
                window.quietStateManager.queueAnimation((setCancelHandler) => {
                    sourceCard.style.animation = 'fadeOut 0.3s ease-out';
                    const timeoutId = setTimeout(() => sourceCard.style.display = 'none', 300);
                    
                    setCancelHandler(() => {
                        clearTimeout(timeoutId);
                        sourceCard.style.animation = '';
                    });
                }, { duration: 300, priority: 8, metadata: { type: 'task_merge', task_id: sourceTaskId } });
            } else if (sourceCard) {
                sourceCard.style.animation = 'fadeOut 0.3s ease-out';
                setTimeout(() => sourceCard.style.display = 'none', 300);
            }

            // Step 2: Merge data - combine labels, keep higher priority, combine descriptions
            const mergedLabels = [...new Set([...(targetTask.labels || []), ...(sourceTask.labels || [])])];
            const priorityRank = { urgent: 4, high: 3, medium: 2, low: 1 };
            const mergedPriority = (priorityRank[sourceTask.priority] > priorityRank[targetTask.priority]) 
                ? sourceTask.priority : targetTask.priority;
            
            let mergedDescription = targetTask.description || '';
            if (sourceTask.description && !mergedDescription.includes(sourceTask.description)) {
                mergedDescription = mergedDescription 
                    ? `${mergedDescription}\n\n[Merged from another task]\n${sourceTask.description}`
                    : sourceTask.description;
            }

            // Step 3: Update cache
            const updatedTask = {
                ...targetTask,
                labels: mergedLabels,
                priority: mergedPriority,
                description: mergedDescription,
                updated_at: new Date().toISOString(),
                _optimistic: true,
                _operation_id: opId
            };
            await this.cache.setTask(targetTaskId, updatedTask);

            // Step 4: Update target task DOM
            this._updateTaskInDOM(targetTaskId, updatedTask);

            // Step 5: Sync to server
            const response = await fetch(`/api/tasks/${targetTaskId}/merge`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_task_id: sourceTaskId })
            });

            if (!response.ok) {
                throw new Error(`Merge failed: ${response.statusText}`);
            }

            const data = await response.json();
            
            // Step 6: Reconcile with server truth
            await this.cache.setTask(targetTaskId, data.task);
            this._updateTaskInDOM(targetTaskId, data.task);
            
            // Remove source task from cache
            await this.cache.deleteTask(sourceTaskId);
            
            this._updateCounters();
            this.pendingOperations.delete(opId);
            
            return data.task;
        } catch (error) {
            console.error('❌ Merge failed - rolling back:', error);
            
            // Rollback: restore source task card (CROWN⁴.5 QuietStateManager)
            const sourceCard = document.querySelector(`[data-task-id="${sourceTaskId}"]`);
            if (sourceCard && window.quietStateManager) {
                window.quietStateManager.queueAnimation((setCancelHandler) => {
                    sourceCard.style.display = '';
                    sourceCard.style.animation = 'slideInFromTop 0.3s ease-out';
                    
                    setCancelHandler(() => {
                        sourceCard.style.animation = '';
                    });
                }, { duration: 300, priority: 9, metadata: { type: 'task_merge_rollback', task_id: sourceTaskId } });
            } else if (sourceCard) {
                sourceCard.style.display = '';
                sourceCard.style.animation = 'slideInFromTop 0.3s ease-out';
            }
            
            // Rollback: restore original target task in cache and DOM
            await this.cache.setTask(targetTaskId, originalTargetTask);
            this._updateTaskInDOM(targetTaskId, originalTargetTask);
            
            this.pendingOperations.delete(opId);
            throw error;
        }
    }

    /**
     * Generate unique operation ID
     * @returns {string}
     */
    _generateOperationId() {
        return `op_${Date.now()}_${++this.operationCounter}`;
    }

    /**
     * Add task to DOM
     * @param {Object} task
     */
    _addTaskToDOM(task) {
        const container = document.getElementById('tasks-list-container');
        if (!container) return;

        const taskHTML = window.taskBootstrap.renderTaskCard(task, 0);
        container.insertAdjacentHTML('afterbegin', taskHTML);

        // Add animation (CROWN⁴.5 QuietStateManager)
        const card = container.querySelector(`[data-task-id="${task.id}"]`);
        if (card && window.quietStateManager) {
            window.quietStateManager.queueAnimation((setCancelHandler) => {
                card.classList.add('optimistic-create');
                card.style.animation = 'slideInFromTop 0.3s ease-out';
                
                setCancelHandler(() => {
                    card.classList.remove('optimistic-create');
                    card.style.animation = '';
                });
            }, { duration: 300, priority: 7, metadata: { type: 'task_create', task_id: task.id } });
        } else if (card) {
            card.classList.add('optimistic-create');
            card.style.animation = 'slideInFromTop 0.3s ease-out';
        }

        // Hide empty state
        const emptyState = document.getElementById('tasks-empty-state');
        if (emptyState) {
            emptyState.style.display = 'none';
        }

        // Update counters
        this._updateCounters();
    }

    /**
     * Update task in DOM
     * @param {number|string} taskId
     * @param {Object} task
     */
    _updateTaskInDOM(taskId, task) {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!card) return;

        // Update title
        const titleEl = card.querySelector('.task-title');
        if (titleEl && task.title) {
            titleEl.textContent = task.title;
        }

        // Update description
        const descEl = card.querySelector('.task-description');
        if (task.description) {
            if (descEl) {
                descEl.textContent = task.description;
            } else {
                const contentEl = card.querySelector('.task-content');
                if (contentEl) {
                    const descHTML = `<p class="task-description">${this._escapeHtml(task.description)}</p>`;
                    contentEl.insertAdjacentHTML('afterbegin', descHTML);
                }
            }
        }

        // Update status
        if (task.status) {
            card.dataset.status = task.status;
            const checkbox = card.querySelector('.task-checkbox');
            if (checkbox) {
                checkbox.checked = task.status === 'completed';
            }
            if (task.status === 'completed') {
                card.classList.add('completed');
                if (titleEl) titleEl.classList.add('completed');
            } else {
                card.classList.remove('completed');
                if (titleEl) titleEl.classList.remove('completed');
            }
        }

        // Update priority
        if (task.priority) {
            card.dataset.priority = task.priority;
            const priorityBadge = card.querySelector('.priority-badge');
            if (priorityBadge) {
                priorityBadge.className = `priority-badge priority-${task.priority.toLowerCase()}`;
                priorityBadge.textContent = task.priority;
            }
        }

        // Add optimistic indicator (CROWN⁴.5 QuietStateManager)
        if (window.quietStateManager) {
            window.quietStateManager.queueAnimation((setCancelHandler) => {
                card.classList.add('optimistic-update');
                const timeoutId = setTimeout(() => card.classList.remove('optimistic-update'), 300);
                
                setCancelHandler(() => {
                    clearTimeout(timeoutId);
                    card.classList.remove('optimistic-update');
                });
            }, { duration: 300, priority: 6, metadata: { type: 'task_update', task_id: taskId } });
        } else {
            card.classList.add('optimistic-update');
            setTimeout(() => card.classList.remove('optimistic-update'), 300);
        }

        this._updateCounters();
    }

    /**
     * Remove task from DOM
     * @param {number|string} taskId
     */
    _removeTaskFromDOM(taskId) {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!card) return;

        // Use QuietStateManager for fade-out animation (CROWN⁴.5)
        if (window.quietStateManager) {
            window.quietStateManager.queueAnimation((setCancelHandler) => {
                card.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                card.style.opacity = '0';
                card.style.transform = 'translateX(-20px)';
                
                const timeoutId = setTimeout(() => {
                    card.remove();
                    this._updateCounters();
                    
                    const remaining = document.querySelectorAll('.task-card').length;
                    if (remaining === 0) {
                        const emptyState = document.getElementById('tasks-empty-state');
                        if (emptyState) emptyState.style.display = 'block';
                    }
                }, 300);
                
                setCancelHandler(() => {
                    clearTimeout(timeoutId);
                    card.style.transition = '';
                    card.style.opacity = '';
                    card.style.transform = '';
                });
            }, { duration: 300, priority: 5, metadata: { type: 'task_remove', task_id: taskId } });
        } else {
            card.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
            card.style.opacity = '0';
            card.style.transform = 'translateX(-20px)';
            
            setTimeout(() => {
                card.remove();
                this._updateCounters();
                
                const remaining = document.querySelectorAll('.task-card').length;
                if (remaining === 0) {
                    const emptyState = document.getElementById('tasks-empty-state');
                    if (emptyState) emptyState.style.display = 'block';
                }
            }, 300);
        }
    }

    /**
     * Update task counters
     */
    _updateCounters() {
        const cards = document.querySelectorAll('.task-card');
        const counters = {
            all: cards.length,
            todo: 0,
            in_progress: 0,
            completed: 0,
            overdue: 0
        };

        cards.forEach(card => {
            const status = card.dataset.status || 'todo';
            if (counters[status] !== undefined) {
                counters[status]++;
            }
        });

        Object.entries(counters).forEach(([key, count]) => {
            const badge = document.querySelector(`[data-counter="${key}"]`);
            if (badge) {
                badge.textContent = count;
            }
        });
    }

    /**
     * Sync operation to server via WebSocket
     * Gracefully defers to OfflineQueueManager if socket is disconnected/reconnecting
     * @param {string} opId
     * @param {string} type
     * @param {Object} data
     * @param {number|string} taskId
     */
    async _syncToServer(opId, type, data, taskId) {
        const startTime = performance.now();

        try {
            // Check WebSocket connection (wsManager.sockets.tasks is the socket object)
            const isConnected = window.wsManager && 
                               window.wsManager.sockets.tasks && 
                               window.wsManager.sockets.tasks.connected;
            
            if (!isConnected) {
                // Socket is disconnected or reconnecting - defer to OfflineQueueManager
                console.log(`⏸️ WebSocket not connected, operation queued for replay (${type})`);
                
                // Emit telemetry for deferred operations
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordEvent('task_sync_deferred', {
                        type,
                        reason: 'socket_disconnected'
                    });
                }
                
                // KEEP pendingOperations for reconciliation when OfflineQueueManager replays
                // The pending operation will reconcile when the server eventually responds
                console.log(`💾 Keeping pending operation ${opId} for later reconciliation`);
                
                // Don't throw - OfflineQueueManager will replay when reconnected
                return;
            }

            // Get user and session context
            const userId = window.CURRENT_USER_ID || null;
            const sessionId = window.CURRENT_SESSION_ID || null;
            const workspaceId = window.WORKSPACE_ID || null;

            if (!userId) {
                console.error('❌ User ID not found in page context');
                throw new Error('User not authenticated');
            }

            // Map operation types to WebSocket event names (server expects simple event names)
            let eventName, payload;

            if (type === 'create') {
                // Server listens for 'task_create' (not 'task_create:manual')
                eventName = 'task_create';
                payload = {
                    payload: {
                        ...data,
                        temp_id: taskId,
                        operation_id: opId,
                        user_id: userId,
                        session_id: sessionId,
                        workspace_id: workspaceId
                    }
                };
            } else if (type === 'update') {
                // Server expects 'update_type' field for routing
                // Map to exact server event names (from routes/tasks_websocket.py:6-18)
                eventName = 'task_update';
                let updateType = 'title'; // default
                
                if (data.status !== undefined) {
                    updateType = 'status_toggle';
                } else if (data.priority !== undefined) {
                    updateType = 'priority';
                } else if (data.due_date !== undefined || data.due !== undefined) {
                    updateType = 'due';
                } else if (data.assignee !== undefined || data.assigned_to !== undefined) {
                    updateType = 'assign';
                } else if (data.labels !== undefined) {
                    updateType = 'labels';
                } else if (data.title !== undefined) {
                    updateType = 'title';
                }
                
                payload = {
                    payload: {
                        task_id: taskId,
                        ...data,
                        operation_id: opId,
                        user_id: userId,
                        session_id: sessionId,
                        workspace_id: workspaceId
                    },
                    update_type: updateType
                };
            } else if (type === 'delete') {
                eventName = 'task_delete';
                payload = {
                    payload: {
                        task_id: taskId,
                        operation_id: opId,
                        user_id: userId,
                        session_id: sessionId,
                        workspace_id: workspaceId
                    }
                };
            }

            console.log(`📤 Sending ${eventName} event:`, payload);

            // Emit via WebSocket and wait for server acknowledgment
            const result = await window.wsManager.emitWithAck(eventName, payload, '/tasks');

            const reconcileTime = performance.now() - startTime;
            console.log(`✅ Server acknowledged ${type} in ${reconcileTime.toFixed(2)}ms, response:`, result);

            // Reconcile with server data
            await this._reconcileSuccess(opId, type, result, taskId);

            // Emit telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('optimistic_reconcile_ms', reconcileTime);
            }

        } catch (error) {
            const syncTime = performance.now() - startTime;
            console.error(`❌ Server sync failed for ${type} after ${syncTime.toFixed(2)}ms:`, {
                error: error.message,
                opId,
                taskId,
                type,
                stack: error.stack
            });
            
            const is409Conflict = error.message && (
                error.message.includes('409') || 
                error.message.includes('conflict') ||
                error.message.includes('version mismatch')
            );
            
            // ENTERPRISE-GRADE: Special handling for temp ID validation errors
            const isTempIdError = error.message && (
                error.message.includes('temporary ID') ||
                error.message.includes('TEMP_ID_NOT_RECONCILED') ||
                error.message.includes('temp_')
            );
            
            if (isTempIdError) {
                // Temp ID error - this task needs reconciliation with server
                if (window.toast) {
                    window.toast.warning('This task is still syncing with the server. Please wait a moment and try again.', 5000, {
                        undoText: 'Refresh',
                        undoCallback: () => window.location.reload()
                    });
                }
            } else if (is409Conflict) {
                if (window.toast) {
                    window.toast.warning('Changes conflict detected - reloading latest version', 5000, {
                        undoText: 'Retry',
                        undoCallback: () => this._retryOperation(opId)
                    });
                }
            } else {
                if (window.toast) {
                    window.toast.error(`Save failed - ${error.message}`, 6000, {
                        undoText: 'Retry',
                        undoCallback: () => this._retryOperation(opId)
                    });
                }
            }
            
            // Emit telemetry for failures
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('optimistic_failure_ms', syncTime);
                window.CROWNTelemetry.recordEvent('task_sync_failure', {
                    type,
                    error: error.message,
                    duration_ms: syncTime,
                    is_conflict: is409Conflict,
                    is_temp_id_error: isTempIdError
                });
            }
            
            await this._reconcileFailure(opId, type, taskId, error);
        }
    }

    /**
     * Reconcile successful server response
     * @param {string} opId
     * @param {string} type
     * @param {Object} serverData
     * @param {number|string} taskId
     */
    async _reconcileSuccess(opId, type, serverData, taskId) {
        const operation = this.pendingOperations.get(opId);
        if (!operation) return;

        // Remove from OfflineQueue since WebSocket sync succeeded
        if (operation.queueId && this.cache) {
            try {
                await this.cache.removeFromQueue(operation.queueId);
                console.log(`🗑️ Removed queue entry ${operation.queueId} after successful WebSocket sync`);
            } catch (error) {
                console.warn(`⚠️ Failed to remove queue entry ${operation.queueId}:`, error);
            }
        }

        if (type === 'create') {
            // Replace temp ID with real ID
            const realTask = serverData.task || serverData;
            const tempId = operation.tempId;

            // Update DOM
            const card = document.querySelector(`[data-task-id="${tempId}"]`);
            if (card) {
                card.dataset.taskId = realTask.id;
                card.classList.remove('optimistic-create');
            }

            // Update cache
            await this.cache.deleteTask(tempId);
            await this.cache.saveTask(realTask);

        } else if (type === 'update') {
            // Update with server truth
            const realTask = serverData.task || serverData;
            await this.cache.saveTask(realTask);
            this._updateTaskInDOM(taskId, realTask);
        }

        // Remove operation
        this.pendingOperations.delete(opId);

        // Mark event as synced
        const events = await this.cache.getPendingEvents();
        const relatedEvent = events.find(e => e.task_id === taskId || e.task_id === operation.tempId);
        if (relatedEvent) {
            await this.cache.markEventSynced(relatedEvent.id);
        }
    }

    /**
     * Reconcile failed server sync (rollback)
     * @param {string} opId
     * @param {string} type
     * @param {number|string} taskId
     * @param {Error} error
     */
    async _reconcileFailure(opId, type, taskId, error) {
        const operation = this.pendingOperations.get(opId);
        if (!operation) {
            console.warn(`⚠️ No pending operation found for ${opId}`);
            return;
        }

        console.log(`🔄 Rolling back ${type} operation:`, { opId, taskId });

        if (type === 'create') {
            // Rollback create
            await this._rollbackCreate(operation.tempId);
        } else if (type === 'update') {
            // Rollback to previous state
            await this.cache.saveTask(operation.previous);
            this._updateTaskInDOM(taskId, operation.previous);
        } else if (type === 'delete') {
            // Restore deleted task
            await this.cache.saveTask(operation.task);
            this._addTaskToDOM(operation.task);
        }

        this.pendingOperations.delete(opId);

        // Show detailed error notification
        const errorMsg = error.message || 'Unknown error';
        this._showErrorNotification(`Failed to ${type} task. Changes rolled back.`, errorMsg);
        
        console.log(`✅ Rollback complete for operation ${opId}`);
    }

    /**
     * Rollback task creation
     * @param {string} tempId
     */
    async _rollbackCreate(tempId) {
        this._removeTaskFromDOM(tempId);
        await this.cache.deleteTask(tempId);
    }

    /**
     * Show error notification
     * @param {string} message
     * @param {string} detail - Optional detailed error message
     */
    _showErrorNotification(message, detail = null) {
        console.error(`🚨 Error notification: ${message}`, detail ? `(${detail})` : '');
        
        if (window.showToast) {
            window.showToast(message, 'error');
        } else {
            console.error(message);
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
}

// Export singleton
window.optimisticUI = new OptimisticUI();

console.log('⚡ CROWN⁴.5 OptimisticUI loaded');
