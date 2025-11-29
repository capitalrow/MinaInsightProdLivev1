/**
 * CROWN⁴.6 Tasks Page - Master Initialization
 * Wires up ALL interactive features in correct dependency order
 * This file ensures every button, menu, and handler works correctly
 */

(function() {
    'use strict';

    if (window.__tasksPageMasterInitialized) {
        console.log('[MasterInit] Skipping duplicate initialization; already initialized');
        return;
    }

    console.log('[MasterInit] ========== Tasks Page Master Initialization STARTING ==========');
    
    // Track initialization state
    const initState = {
        optimisticUI: false,
        taskSearchSort: false,
        taskInlineEditing: false,
        filterTabs: false,
        newTaskButton: false,
        checkboxHandlers: false,
        deleteHandlers: false,
        proposalUI: false
    };

    const dispatchTaskEvent = (eventName, detail = {}) => {
        document.dispatchEvent(new CustomEvent(eventName, { detail }));

        // Optional bridge to the backend EventSequencer
        if (window.eventSequencerBridge?.recordEvent) {
            try {
                window.eventSequencerBridge.recordEvent(eventName, detail);
            } catch (err) {
                console.warn('[MasterInit] Failed to record event with sequencer bridge', err);
            }
        }
    };
    
    /**
     * Initialize filter tabs (All/Active/Archived)
     */
    function initFilterTabs() {
        if (window.__taskFilterTabsReady) return;
        console.log('[MasterInit] Initializing filter tabs (All/Active/Archived)...');
        
        const handleFilterClick = (e) => {
            const tab = e.target.closest('.filter-tab');
            if (!tab) return;

            e.preventDefault();

            const filter = tab.dataset.filter;
            const filterTabs = document.querySelectorAll('.filter-tab');

            console.log(`[FilterTabs] Switching to filter: ${filter}`);

            filterTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            dispatchTaskEvent('filterChanged', { filter });
            dispatchTaskEvent('task:filter-changed', { filter });

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('filter_tab_clicked', 1, { filter });
            }
        };

        document.addEventListener('click', handleFilterClick);
        
        initState.filterTabs = true;
        window.__taskFilterTabsReady = true;
        console.log('[MasterInit] ✅ Filter tabs initialized (All/Active/Archived)');
    }
    
    /**
     * Initialize "New Task" button
     */
    function initNewTaskButton() {
        if (window.__taskNewButtonsReady) return;
        console.log('[MasterInit] Initializing New Task button...');
        
        const delegatedHandler = (e) => {
            const btn = e.target.closest('#new-task-btn, #empty-state-create-btn');
            if (!btn) return;

            e.preventDefault();
            console.log('[NewTask] Button clicked, opening modal...');

            dispatchTaskEvent('task:create-new', { source: btn.id || 'tasks-header' });

            if (window.taskModalManager?.openCreateModal) {
                window.taskModalManager.openCreateModal();
            } else {
                const modalOverlay = document.getElementById('task-modal-overlay');
                if (modalOverlay) {
                    modalOverlay.classList.remove('hidden');
                    console.log('[NewTask] Modal overlay shown');
                } else if (window.toastManager) {
                    window.toastManager.show('Task creation modal not ready. Please refresh the page.', 'warning', 3000);
                }
            }

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('new_task_button_clicked', 1);
            }
        };

        document.addEventListener('click', delegatedHandler);

        initState.newTaskButton = true;
        window.__taskNewButtonsReady = true;
        console.log('[MasterInit] ✅ New Task button initialized');
    }

    /**
     * Initialize delegated task menu trigger events
     */
    function initTaskMenuTriggers() {
        if (window.__taskMenuTriggerDelegationReady) return;

        document.addEventListener('click', (e) => {
            const trigger = e.target.closest('.task-menu-trigger');
            if (!trigger) return;

            const taskId = trigger.dataset.taskId;
            dispatchTaskEvent('task:menu-open', { taskId });
        });

        window.__taskMenuTriggerDelegationReady = true;
        console.log('[MasterInit] ✅ Task menu trigger delegation initialized');
    }
    
    /**
     * Initialize task checkbox toggles
     */
    function initCheckboxHandlers() {
        if (window.__taskCheckboxHandlersReady) return;
        console.log('[MasterInit] Initializing checkbox handlers...');
        
        // Use event delegation for dynamic task cards
        document.addEventListener('change', async (e) => {
            if (e.target.classList.contains('task-checkbox')) {
                const checkbox = e.target;
                const card = checkbox.closest('[data-task-id]');
                
                if (!card) {
                    console.error('[Checkbox] No task card found');
                    return;
                }
                
                const taskId = card.dataset.taskId;
                const completed = checkbox.checked;

                console.log(`[Checkbox] Task ${taskId} completion toggled to: ${completed}`);

                dispatchTaskEvent('task_update:status_toggle', { taskId, completed });
                
                try {
                    // Prepare correct update payload
                    const updates = {
                        status: completed ? 'completed' : 'todo',
                        completed_at: completed ? new Date().toISOString() : null
                    };
                    let updatedTask = null;

                    // Update via optimistic UI (ledger-backed + reconciliation aware)
                    if (window.optimisticUI?.toggleTaskStatus) {
                        updatedTask = await window.optimisticUI.toggleTaskStatus(taskId);
                        console.log(`[Checkbox] ✅ Task ${taskId} toggled via optimisticUI.toggleTaskStatus`);
                    } else if (window.optimisticUI?.updateTask) {
                        updatedTask = await window.optimisticUI.updateTask(taskId, updates);
                        console.log(`[Checkbox] ✅ Task ${taskId} updated successfully`);
                    } else {
                        console.warn('[Checkbox] optimisticUI not available, falling back to direct API call');

                        // Fallback: Direct API call
                        const response = await fetch(`/api/tasks/${taskId}`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify(updates)
                        });

                        if (!response.ok) {
                            throw new Error('Failed to update task');
                        }

                        // Update UI manually
                        if (completed) {
                            card.classList.add('completed');
                            card.dataset.status = 'completed';
                        } else {
                            card.classList.remove('completed');
                            card.dataset.status = 'pending';
                        }

                        updatedTask = { id: taskId, ...updates };
                    }

                    // Broadcast cross-tab + refresh local sort/filter counts
                    if (window.broadcastSync?.broadcast) {
                        window.broadcastSync.broadcast(window.broadcastSync.EVENTS.TASK_UPDATE, {
                            taskId,
                            changes: updates
                        });
                    }

                    if (window.multiTabSync?.broadcastTaskUpdated) {
                        window.multiTabSync.broadcastTaskUpdated(updatedTask || { id: taskId, ...updates });
                    }

                    if (window.taskSearchSort?.refresh) {
                        window.taskSearchSort.refresh();
                    }

                    // Telemetry
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('task_checkbox_toggled', 1, { taskId, completed });
                    }
                    
                } catch (error) {
                    console.error('[Checkbox] Failed to update task:', error);
                    
                    // Revert checkbox state
                    checkbox.checked = !completed;
                    
                    // Show error toast
                    if (window.toastManager) {
                        window.toastManager.show('Failed to update task. Please try again.', 'error', 3000);
                    }
                }
            }
        });
        
        initState.checkboxHandlers = true;
        window.__taskCheckboxHandlersReady = true;
        console.log('[MasterInit] ✅ Checkbox handlers initialized');
    }
    
    /**
     * Initialize restore task handlers (for archived tasks)
     */
    function initRestoreHandlers() {
        if (window.__taskRestoreHandlersReady) return;
        console.log('[MasterInit] Initializing restore task handlers...');
        
        // Use event delegation for restore buttons
        document.addEventListener('click', async (e) => {
            if (e.target.classList.contains('btn-restore-task') || e.target.closest('.btn-restore-task')) {
                const btn = e.target.classList.contains('btn-restore-task') ? e.target : e.target.closest('.btn-restore-task');
                const taskId = btn.dataset.taskId;
                const card = btn.closest('[data-task-id]');
                
                if (!taskId || !card) {
                    console.error('[Restore] No task ID or card found');
                    return;
                }
                
                console.log(`[Restore] Restoring archived task ${taskId}`);
                
                try {
                    // Disable button during restore
                    btn.disabled = true;
                    btn.style.opacity = '0.5';
                    
                    // Use OptimisticUI to unarchive
                    if (window.optimisticUI && typeof window.optimisticUI.unarchiveTask === 'function') {
                        await window.optimisticUI.unarchiveTask(taskId);
                    } else if (window.optimisticUI && typeof window.optimisticUI.updateTask === 'function') {
                        // Fallback: Use updateTask
                        await window.optimisticUI.updateTask(taskId, {
                            archived_at: null,
                            status: 'todo'
                        });
                    } else {
                        // Last resort: Direct API call
                        const response = await fetch(`/api/tasks/${taskId}`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({
                                archived_at: null,
                                status: 'todo'
                            })
                        });
                        
                        if (!response.ok) {
                            throw new Error('Failed to restore task');
                        }
                        
                        // Refresh task list to show restored task
                        if (window.taskBootstrap) {
                            await window.taskBootstrap.bootstrap();
                        }
                    }
                    
                    console.log(`[Restore] ✅ Task ${taskId} restored successfully`);
                    
                    // Toast handled by OptimisticUI
                    
                    // Telemetry
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('task_restored', 1, { taskId });
                    }
                } catch (error) {
                    console.error('[Restore] Failed to restore task:', error);
                    
                    // Re-enable button on error
                    btn.disabled = false;
                    btn.style.opacity = '';
                    
                    // Show error toast
                    if (window.toastManager) {
                        window.toastManager.show('Failed to restore task. Please try again.', 'error', 3000);
                    }
                }
            }
        });
        
        console.log('[MasterInit] ✅ Restore task handlers initialized');
        window.__taskRestoreHandlersReady = true;
    }
    
    /**
     * Initialize delete confirmation handlers
     */
    function initDeleteHandlers() {
        if (window.__taskDeleteHandlersReady) return;
        console.log('[MasterInit] Initializing delete handlers...');
        
        // Listen for delete events from task menu
        document.addEventListener('task:delete', async (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Delete] Delete requested for task ${taskId}`);
            
            // Get task title for context
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            const taskTitle = taskCard?.querySelector('.task-title')?.textContent?.trim() || '';
            
            // Show beautiful confirmation modal
            let confirmed = true;
            if (window.taskConfirmModal?.confirmDelete) {
                confirmed = await window.taskConfirmModal.confirmDelete(taskTitle);
            } else {
                confirmed = window.confirm('Are you sure you want to delete this task?');
            }
            
            if (!confirmed) {
                console.log('[Delete] User cancelled delete');
                return;
            }
            
            try {
                console.log(`[Delete] Deleting task ${taskId}...`);
                
                // Delete via optimistic UI
                if (window.optimisticUI && typeof window.optimisticUI.deleteTask === 'function') {
                    await window.optimisticUI.deleteTask(taskId);
                } else {
                    // Fallback: Direct API call
                    const response = await fetch(`/api/tasks/${taskId}`, {
                        method: 'DELETE',
                        credentials: 'same-origin'
                    });
                    
                    if (!response.ok) {
                        throw new Error('Failed to delete task');
                    }
                    
                    // Remove from DOM
                    const card = document.querySelector(`[data-task-id="${taskId}"]`);
                    if (card) {
                        card.remove();
                    }
                }
                
                console.log(`[Delete] ✅ Task ${taskId} deleted successfully`);
                
                // Show success toast with undo functionality
                if (window.toast) {
                    window.toast.success('Task deleted', 5000, {
                        undoCallback: async () => {
                            console.log('[Delete] Undo requested');
                            // TODO: Implement task restore from soft delete
                            window.toast.info('Undo functionality coming soon', 2000);
                        },
                        undoText: 'Undo'
                    });
                } else if (window.toastManager) {
                    window.toastManager.show('Task deleted', 'success', 2000);
                }
                
                // Telemetry
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('task_deleted', 1, { taskId });
                }
                
            } catch (error) {
                console.error('[Delete] Failed to delete task:', error);
                
                // Show error toast
                if (window.toastManager) {
                    window.toastManager.show('Failed to delete task. Please try again.', 'error', 3000);
                }
            }
        });
        
        initState.deleteHandlers = true;
        window.__taskDeleteHandlersReady = true;
        console.log('[MasterInit] ✅ Delete handlers initialized');
    }
    
    /**
     * Initialize task menu action handlers
     */
    function initTaskMenuHandlers() {
        if (window.__taskMenuHandlersReady) return;
        console.log('[MasterInit] Initializing task menu action handlers...');
        
        // Edit task title
        document.addEventListener('task:edit', (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Menu] Edit task ${taskId}`);
            
            // Trigger inline editing
            if (window.taskInlineEditing && typeof window.taskInlineEditing.startEditing === 'function') {
                window.taskInlineEditing.startEditing(taskId);
            } else {
                console.warn('[Menu] Inline editing not available');
                alert('Edit functionality will be available soon');
            }
        });
        
        // Toggle task completion status
        document.addEventListener('task:toggle-status', async (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Menu] Toggle status for task ${taskId}`);
            
            // Find the task card and checkbox
            const card = document.querySelector(`[data-task-id="${taskId}"]`);
            const checkbox = card?.querySelector('.task-checkbox');
            
            if (!checkbox) {
                console.error('[Menu] Checkbox not found for task', taskId);
                return;
            }
            
            // Toggle the checkbox (this will trigger the existing checkbox handler)
            checkbox.checked = !checkbox.checked;
            checkbox.dispatchEvent(new Event('change', { bubbles: true }));
        });
        
        // Change priority
        document.addEventListener('task:priority', async (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Menu] Change priority for task ${taskId}`);
            
            // Show beautiful priority selector
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            if (!taskCard || !window.taskPrioritySelector) {
                console.error('[Menu] Cannot show priority selector');
                return;
            }
            
            const newPriority = await window.taskPrioritySelector.show(taskCard);
            
            if (!newPriority) {
                console.log('[Menu] Priority selection cancelled');
                return;
            }
            
            try {
                if (window.optimisticUI && typeof window.optimisticUI.updateTask === 'function') {
                    await window.optimisticUI.updateTask(taskId, { priority: newPriority });
                    
                    if (window.toast) {
                        window.toast.success(`Priority changed to ${newPriority}`, 2000);
                    } else if (window.toastManager) {
                        window.toastManager.show(`Priority changed to ${newPriority}`, 'success', 2000);
                    }
                }
            } catch (error) {
                console.error('[Menu] Failed to update priority:', error);
                if (window.toast) {
                    window.toast.error('Failed to update priority', 3000);
                } else if (window.toastManager) {
                    window.toastManager.show('Failed to update priority', 'error', 3000);
                }
            }
        });
        
        // Set due date
        document.addEventListener('task:due-date', async (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Menu] Set due date for task ${taskId}`);
            
            // Show beautiful date picker
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            if (!taskCard || !window.taskDatePicker) {
                console.error('[Menu] Cannot show date picker');
                return;
            }
            
            const dateStr = await window.taskDatePicker.show(taskCard);
            
            if (dateStr === undefined) {
                console.log('[Menu] Date selection cancelled');
                return;
            }
            
            try {
                if (window.optimisticUI && typeof window.optimisticUI.updateTask === 'function') {
                    const updateData = dateStr === null ? { due_date: null } : { due_date: dateStr };
                    await window.optimisticUI.updateTask(taskId, updateData);
                    
                    const message = dateStr === null ? 'Due date cleared' : 'Due date updated';
                    if (window.toast) {
                        window.toast.success(message, 2000);
                    } else if (window.toastManager) {
                        window.toastManager.show(message, 'success', 2000);
                    }
                }
            } catch (error) {
                console.error('[Menu] Failed to update due date:', error);
                if (window.toast) {
                    window.toast.error('Failed to update due date', 3000);
                } else if (window.toastManager) {
                    window.toastManager.show('Failed to update due date', 'error', 3000);
                }
            }
        });
        
        // Assign task
        document.addEventListener('task:assign', async (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Menu] Assign task ${taskId}`);
            
            alert('Task assignment feature coming soon!');
        });
        
        // Edit labels
        document.addEventListener('task:labels', async (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Menu] Edit labels for task ${taskId}`);
            
            alert('Labels feature coming soon!');
        });
        
        // Archive task
        document.addEventListener('task:archive', async (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Menu] Archive task ${taskId}`);
            
            // Get task title for context
            const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
            const taskTitle = taskCard?.querySelector('.task-title')?.textContent?.trim() || '';
            
            // Show beautiful confirmation modal
            let confirmed = true;
            if (window.taskConfirmModal?.confirmArchive) {
                confirmed = await window.taskConfirmModal.confirmArchive(taskTitle);
            } else {
                confirmed = window.confirm('Archive this task?');
            }
            
            if (!confirmed) {
                console.log('[Menu] Archive cancelled');
                return;
            }
            
            try {
                if (window.optimisticUI && typeof window.optimisticUI.updateTask === 'function') {
                    await window.optimisticUI.updateTask(taskId, { deleted_at: new Date().toISOString() });
                    
                    if (window.toast) {
                        window.toast.success('Task archived', 5000, {
                            undoCallback: async () => {
                                console.log('[Archive] Undo requested');
                                await window.optimisticUI.updateTask(taskId, { deleted_at: null });
                                window.toast.info('Task restored', 2000);
                            },
                            undoText: 'Undo'
                        });
                    } else if (window.toastManager) {
                        window.toastManager.show('Task archived', 'success', 2000);
                    }
                }
            } catch (error) {
                console.error('[Menu] Failed to archive task:', error);
                if (window.toast) {
                    window.toast.error('Failed to archive task', 3000);
                } else if (window.toastManager) {
                    window.toastManager.show('Failed to archive task', 'error', 3000);
                }
            }
        });
        
        // Jump to transcript
        document.addEventListener('task:jump', async (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Menu] Jump to transcript for task ${taskId}`);
            
            try {
                // Get full task data from cache to access session_id
                let sessionId = null;
                let transcriptSpan = null;
                
                if (window.optimisticUI?.cache) {
                    const task = await window.optimisticUI.cache.getTask(taskId);
                    if (task) {
                        sessionId = task.session_id;
                        transcriptSpan = task.transcript_span;
                    }
                }
                
                // Fallback: try to get from card dataset
                if (!sessionId) {
                    const card = document.querySelector(`[data-task-id="${taskId}"]`);
                    sessionId = card?.dataset.sessionId;
                    transcriptSpan = transcriptSpan || card?.dataset.transcriptSpan;
                }
                
                if (!sessionId) {
                    if (window.toast) {
                        window.toast.warning('No transcript session found for this task', 3000);
                    } else if (window.toastManager) {
                        window.toastManager.show('No transcript session found for this task', 'warning', 3000);
                    }
                    return;
                }
                
                // Navigate to session transcript page (correct route)
                let url = `/sessions/${sessionId}`;
                if (transcriptSpan) {
                    try {
                        const span = typeof transcriptSpan === 'string' ? JSON.parse(transcriptSpan) : transcriptSpan;
                        if (span.start_ms !== undefined) {
                            url += `?t=${span.start_ms}`;
                        }
                    } catch (e) {
                        console.error('[Menu] Failed to parse transcript span:', e);
                    }
                }
                
                console.log(`[Menu] Navigating to session transcript: ${url}`);
                window.location.href = url;
            } catch (error) {
                console.error('[Menu] Failed to jump to transcript:', error);
                if (window.toast) {
                    window.toast.error('Failed to navigate to transcript', 3000);
                } else if (window.toastManager) {
                    window.toastManager.show('Failed to navigate to transcript', 'error', 3000);
                }
            }
        });
        
        console.log('[MasterInit] ✅ Task menu handlers initialized');
        window.__taskMenuHandlersReady = true;
    }
    
    /**
     * Initialize TaskSearchSort class instance
     */
    function initTaskSearchSort() {
        console.log('[MasterInit] Initializing TaskSearchSort...');
        
        if (typeof TaskSearchSort === 'undefined') {
            console.warn('[MasterInit] TaskSearchSort class not available');
            return false;
        }
        
        try {
            window.taskSearchSort = new TaskSearchSort();
            initState.taskSearchSort = true;
            window.__taskSearchSortReady = true;
            console.log('[MasterInit] ✅ TaskSearchSort initialized');
            return true;
        } catch (error) {
            console.error('[MasterInit] Failed to initialize TaskSearchSort:', error);
            return false;
        }
    }
    
    /**
     * Initialize TaskInlineEditing class instance
     */
    function initTaskInlineEditing() {
        console.log('[MasterInit] Initializing TaskInlineEditing...');
        
        if (typeof TaskInlineEditing === 'undefined') {
            console.warn('[MasterInit] TaskInlineEditing class not available');
            return false;
        }
        
        if (!window.optimisticUI) {
            console.warn('[MasterInit] optimisticUI not available, delaying TaskInlineEditing init');
            return false;
        }
        
        try {
            window.taskInlineEditing = new TaskInlineEditing(window.optimisticUI);
            initState.taskInlineEditing = true;
            window.__taskInlineEditingReady = true;
            console.log('[MasterInit] ✅ TaskInlineEditing initialized');
            return true;
        } catch (error) {
            console.error('[MasterInit] Failed to initialize TaskInlineEditing:', error);
            return false;
        }
    }
    
    /**
     * Initialize TaskProposalUI class instance
     */
    function initTaskProposalUI() {
        console.log('[MasterInit] Initializing TaskProposalUI...');
        
        if (typeof TaskProposalUI === 'undefined') {
            console.warn('[MasterInit] TaskProposalUI class not available');
            return false;
        }
        
        if (!window.optimisticUI) {
            console.warn('[MasterInit] optimisticUI not available, delaying TaskProposalUI init');
            return false;
        }
        
        try {
            window.taskProposalUI = new TaskProposalUI(window.optimisticUI);
            initState.proposalUI = true;
            window.__taskProposalUIReady = true;
            console.log('[MasterInit] ✅ TaskProposalUI initialized');
            return true;
        } catch (error) {
            console.error('[MasterInit] Failed to initialize TaskProposalUI:', error);
            return false;
        }
    }
    
    /**
     * Master initialization function
     */
    async function initializeAllFeatures() {
        console.log('[MasterInit] Starting comprehensive initialization...');
        
        // 0. CRITICAL: Initialize WebSocket connection to /tasks namespace FIRST
        // This MUST happen before any task operations to ensure real-time sync works
        if (window.wsManager && window.WORKSPACE_ID) {
            console.log('[MasterInit] Initializing /tasks WebSocket connection...');
            try {
                // Check if already connected to tasks namespace
                const isTasksConnected = window.wsManager.getConnectionStatus('tasks');
                if (!isTasksConnected) {
                    window.wsManager.init(window.WORKSPACE_ID, ['tasks']);
                    console.log('[MasterInit] ✅ /tasks WebSocket namespace initialized');
                    
                    // Wait briefly for connection to establish
                    await new Promise(resolve => setTimeout(resolve, 100));
                    
                    // Verify connection
                    const connected = window.wsManager.getConnectionStatus('tasks');
                    if (connected) {
                        console.log('[MasterInit] ✅ /tasks WebSocket confirmed connected');
                    } else {
                        console.warn('[MasterInit] ⚠️ /tasks WebSocket not yet connected - operations will use HTTP fallback');
                    }
                } else {
                    console.log('[MasterInit] ✅ /tasks WebSocket already connected');
                }
                
                // Initialize TaskWebSocketHandlers if available
                if (window.tasksWS && typeof window.tasksWS.init === 'function') {
                    window.tasksWS.init();
                    console.log('[MasterInit] ✅ TaskWebSocketHandlers initialized');
                }
            } catch (error) {
                console.error('[MasterInit] ❌ WebSocket initialization failed:', error);
                console.log('[MasterInit] Task operations will use HTTP fallback');
            }
        } else {
            console.warn('[MasterInit] ⚠️ wsManager or WORKSPACE_ID not available');
            console.log('[MasterInit] wsManager:', !!window.wsManager);
            console.log('[MasterInit] WORKSPACE_ID:', window.WORKSPACE_ID);
        }
        
        // 1. CROWN⁴.5: Bootstrap cache-first task loading FIRST (critical for <200ms first paint)
        // MUST await bootstrap completion before metrics can be logged accurately
        if (window.taskBootstrap && typeof window.taskBootstrap.bootstrap === 'function') {
            console.log('[MasterInit] Starting CROWN⁴.5 cache-first bootstrap...');
            try {
                await window.taskBootstrap.bootstrap();
                console.log('[MasterInit] ✅ Bootstrap completed successfully');
            } catch (error) {
                console.error('[MasterInit] ❌ Bootstrap failed:', error);
                // Continue initialization even if bootstrap fails
            }
        } else {
            console.warn('[MasterInit] ⚠️ taskBootstrap not available - performance metrics may be incomplete');
        }
        
        // 1.5. ENTERPRISE-GRADE: Rehydrate pending operations from IndexedDB
        // This ensures retry mechanism works after page refresh
        if (window.optimisticUI && typeof window.optimisticUI.rehydratePendingOperations === 'function') {
            console.log('[MasterInit] Rehydrating pending operations...');
            try {
                await window.optimisticUI.rehydratePendingOperations();
                console.log('[MasterInit] ✅ Pending operations rehydrated successfully');
            } catch (error) {
                console.error('[MasterInit] ❌ Failed to rehydrate pending operations:', error);
            }
        }
        
        // 2. Initialize TaskModalManager (requires SmartSelectors from task-smart-selectors.js)
        if (typeof TaskModalManager !== 'undefined') {
            console.log('[MasterInit] Initializing TaskModalManager...');
            try {
                window.taskModalManager = new TaskModalManager();
                console.log('[MasterInit] ✅ TaskModalManager initialized successfully');
            } catch (error) {
                console.error('[MasterInit] ❌ TaskModalManager initialization failed:', error);
            }
        } else {
            console.error('[MasterInit] ❌ TaskModalManager class not found - ensure task-modal-manager.js loaded before master init');
        }
        
        // 3. Initialize non-dependent features
        initFilterTabs();
        initNewTaskButton();
        initTaskMenuTriggers();
        initCheckboxHandlers();
        initRestoreHandlers();
        initDeleteHandlers();
        initTaskMenuHandlers();
        initTaskActionsMenu();

        // 4. Initialize class-based features
        initTaskSearchSort();
        
        // 5. Wait for optimisticUI, then initialize dependent features
        if (window.optimisticUI) {
            initState.optimisticUI = true;
            initTaskInlineEditing();
            initTaskProposalUI();
        } else {
            console.warn('[MasterInit] optimisticUI not available yet, waiting for event...');
            
            // Listen for optimisticUI ready event
            window.addEventListener('optimisticUIReady', () => {
                console.log('[MasterInit] optimisticUI is now ready, initializing dependent features...');
                initState.optimisticUI = true;
                initTaskInlineEditing();
                initTaskProposalUI();
            }, { once: true });
        }
        
        // Log initialization summary
        window.__tasksPageMasterInitialized = true;
        window.__tasksPageInitState = initState;
        console.log('[MasterInit] Initialization status:', initState);
        console.log('[MasterInit] ========== Tasks Page Master Initialization COMPLETE ==========');
        
        // Dispatch ready event
        document.dispatchEvent(new CustomEvent('tasksPageReady', {
            detail: { initState }
        }));
    }
    
    // Start initialization when DOM is ready - properly await async initialization
    // CROWN⁴.6: Use window load event to ensure all deferred scripts have executed
    const startInit = () => {
        console.log('[MasterInit] Starting deferred initialization...');
        console.log('[MasterInit] taskBootstrap available:', !!window.taskBootstrap);
        initializeAllFeatures().catch(error => {
            console.error('[MasterInit] Initialization failed:', error);
        });
    };
    
    if (document.readyState === 'complete') {
        console.log('[MasterInit] Document already complete, initializing immediately...');
        // Small delay to ensure all module initializations complete
        setTimeout(startInit, 50);
    } else {
        console.log('[MasterInit] Waiting for window load event...');
        window.addEventListener('load', () => {
            console.log('[MasterInit] Window load event fired');
            startInit();
        });
    }
    
})();
