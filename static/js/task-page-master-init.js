/**
 * CROWN⁴.6 Tasks Page - Master Initialization
 * Wires up ALL interactive features in correct dependency order
 * This file ensures every button, menu, and handler works correctly
 */

(function() {
    'use strict';
    
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
    
    /**
     * Initialize filter tabs (All/Pending/Completed)
     */
    function initFilterTabs() {
        console.log('[MasterInit] Initializing filter tabs...');
        
        const filterTabs = document.querySelectorAll('.filter-tab');
        
        filterTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                
                const filter = tab.dataset.filter;
                console.log(`[FilterTabs] Switching to filter: ${filter}`);
                
                // Update active state
                filterTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                // Dispatch custom event for TaskSearchSort to listen
                document.dispatchEvent(new CustomEvent('filterChanged', {
                    detail: { filter }
                }));
                
                // Telemetry
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('filter_tab_clicked', 1, { filter });
                }
            });
        });
        
        initState.filterTabs = true;
        console.log('[MasterInit] ✅ Filter tabs initialized');
    }
    
    /**
     * Initialize "New Task" button
     */
    function initNewTaskButton() {
        console.log('[MasterInit] Initializing New Task button...');
        
        // Find all "New Task" buttons (header + empty state)
        const newTaskButtons = document.querySelectorAll('.btn-primary');
        
        newTaskButtons.forEach(btn => {
            if (btn.textContent.includes('New Task') || btn.textContent.includes('first task')) {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    console.log('[NewTask] Button clicked, opening modal...');
                    
                    // Dispatch event to open task creation modal
                    document.dispatchEvent(new CustomEvent('task:create-new'));
                    
                    // If task modal manager exists, use it
                    if (window.taskModalManager && typeof window.taskModalManager.openCreateModal === 'function') {
                        window.taskModalManager.openCreateModal();
                    } else {
                        // Fallback: Try to show modal overlay directly
                        const modalOverlay = document.getElementById('task-modal-overlay');
                        if (modalOverlay) {
                            modalOverlay.classList.remove('hidden');
                            console.log('[NewTask] Modal overlay shown');
                        } else {
                            console.warn('[NewTask] No modal overlay found - modal system may not be loaded');
                            // Show a simple toast instead
                            if (window.toastManager) {
                                window.toastManager.show('Task creation modal not ready. Please refresh the page.', 'warning', 3000);
                            }
                        }
                    }
                    
                    // Telemetry
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('new_task_button_clicked', 1);
                    }
                });
            }
        });
        
        initState.newTaskButton = true;
        console.log('[MasterInit] ✅ New Task button initialized');
    }
    
    /**
     * Initialize task checkbox toggles
     */
    function initCheckboxHandlers() {
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
                
                try {
                    // Update via optimistic UI
                    if (window.optimisticUI) {
                        await window.optimisticUI.updateTask(taskId, { completed });
                        console.log(`[Checkbox] ✅ Task ${taskId} updated successfully`);
                    } else {
                        console.warn('[Checkbox] optimisticUI not available, falling back to direct API call');
                        
                        // Fallback: Direct API call
                        const response = await fetch(`/api/tasks/${taskId}`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({ completed })
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
        console.log('[MasterInit] ✅ Checkbox handlers initialized');
    }
    
    /**
     * Initialize delete confirmation handlers
     */
    function initDeleteHandlers() {
        console.log('[MasterInit] Initializing delete handlers...');
        
        // Listen for delete events from task menu
        document.addEventListener('task:delete', async (e) => {
            const taskId = e.detail.taskId;
            console.log(`[Delete] Delete requested for task ${taskId}`);
            
            // Show confirmation dialog
            const confirmed = confirm('Delete this task? This action cannot be undone.');
            
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
                
                // Show success toast
                if (window.toastManager) {
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
        console.log('[MasterInit] ✅ Delete handlers initialized');
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
    function initializeAllFeatures() {
        console.log('[MasterInit] Starting comprehensive initialization...');
        
        // 1. Initialize non-dependent features first
        initFilterTabs();
        initNewTaskButton();
        initCheckboxHandlers();
        initDeleteHandlers();
        
        // 2. Initialize class-based features
        initTaskSearchSort();
        
        // 3. Wait for optimisticUI, then initialize dependent features
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
        console.log('[MasterInit] Initialization status:', initState);
        console.log('[MasterInit] ========== Tasks Page Master Initialization COMPLETE ==========');
        
        // Dispatch ready event
        document.dispatchEvent(new CustomEvent('tasksPageReady', {
            detail: { initState }
        }));
    }
    
    // Start initialization when DOM is ready
    if (document.readyState === 'loading') {
        console.log('[MasterInit] DOM still loading, waiting for DOMContentLoaded...');
        document.addEventListener('DOMContentLoaded', initializeAllFeatures);
    } else {
        console.log('[MasterInit] DOM already loaded, initializing immediately...');
        // Wait a tick to ensure other scripts have loaded
        setTimeout(initializeAllFeatures, 100);
    }
    
})();
