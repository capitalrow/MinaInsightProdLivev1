/**
 * CROWN⁴.6 TasksPageOrchestrator - Unified Module Initialization
 * 
 * Loaded LAST after all task module scripts. Ensures:
 * 1. TaskCache is initialized (IndexedDB ready)
 * 2. All critical modules are instantiated in correct dependency order
 * 3. Fires tasks:ready event when all modules are ready
 * 
 * This orchestrator doesn't prevent modules from auto-initializing -
 * it ensures they ARE initialized even if auto-init failed.
 */

class TasksPageOrchestrator {
    constructor() {
        this.initialized = false;
        this.initPromise = null;
        this.modules = {};
    }

    async init() {
        if (this.initialized) {
            console.log('[Orchestrator] Already initialized');
            return this.modules;
        }
        
        if (this.initPromise) {
            console.log('[Orchestrator] Init already in progress, waiting...');
            return this.initPromise;
        }

        this.initPromise = this._doInit();
        return this.initPromise;
    }

    async _doInit() {
        console.log('[Orchestrator] ========== Starting Module Initialization ==========');
        const startTime = performance.now();

        try {
            // Step 1: Wait for TaskCache to be ready (IndexedDB)
            console.log('[Orchestrator] Step 1: Waiting for TaskCache...');
            await this._waitForTaskCache();
            console.log('[Orchestrator] ✅ TaskCache ready');

            // Step 2: Ensure TaskBootstrap exists (depends on TaskCache)
            console.log('[Orchestrator] Step 2: Ensuring TaskBootstrap...');
            await this._ensureTaskBootstrap();

            // Step 3: Ensure OptimisticUI exists (depends on TaskCache)
            console.log('[Orchestrator] Step 3: Ensuring OptimisticUI...');
            await this._ensureOptimisticUI();

            // Step 4: Ensure TaskMenuController exists
            console.log('[Orchestrator] Step 4: Ensuring TaskMenuController...');
            await this._ensureTaskMenuController();

            // Step 5: Ensure TaskActionsMenu exists (depends on OptimisticUI, TaskMenuController)
            console.log('[Orchestrator] Step 5: Ensuring TaskActionsMenu...');
            await this._ensureTaskActionsMenu();

            // Step 5.5: Ensure TaskProposalUI exists (AI proposals feature)
            console.log('[Orchestrator] Step 5.5: Ensuring TaskProposalUI...');
            await this._ensureTaskProposalUI();

            // Step 6: Initialize helper modules
            console.log('[Orchestrator] Step 6: Initializing helper modules...');
            await this._initHelperModules();

            // Step 7: Wire WebSocket events for real-time sync
            console.log('[Orchestrator] Step 7: Wiring WebSocket events...');
            this._wireWebSocketEvents();

            // Mark as initialized
            this.initialized = true;
            
            const elapsed = Math.round(performance.now() - startTime);
            console.log(`[Orchestrator] ========== All Modules Ready in ${elapsed}ms ==========`);
            console.log('[Orchestrator] Modules:', Object.keys(this.modules).join(', '));

            // Dispatch ready event for downstream consumers
            document.dispatchEvent(new CustomEvent('tasks:ready', {
                detail: {
                    modules: Object.keys(this.modules),
                    elapsed
                }
            }));
            
            // Also dispatch dependencies-ready for TaskMenuController
            document.dispatchEvent(new CustomEvent('tasks:dependencies-ready', {
                detail: {
                    modules: this.modules,
                    status: this.getModuleStatus(),
                    elapsed
                }
            }));
            
            console.log('[Orchestrator] Module status:', this.getModuleStatus());

            return this.modules;

        } catch (error) {
            console.error('[Orchestrator] ❌ Initialization failed:', error);
            throw error;
        }
    }

    async _waitForTaskCache() {
        if (window.taskCache) {
            if (window.taskCache.ready) {
                await this._cleanupStaleTempTasks();
                return window.taskCache;
            }
            if (typeof window.taskCache.init === 'function') {
                await window.taskCache.init();
                await this._cleanupStaleTempTasks();
                return window.taskCache;
            }
        }

        return new Promise((resolve, reject) => {
            const maxWait = 5000;
            const startTime = Date.now();
            
            const check = () => {
                if (window.taskCache) {
                    if (window.taskCache.ready) {
                        this._cleanupStaleTempTasks().then(() => {
                            resolve(window.taskCache);
                        });
                        return;
                    }
                    if (typeof window.taskCache.init === 'function') {
                        window.taskCache.init().then(() => {
                            return this._cleanupStaleTempTasks();
                        }).then(() => {
                            resolve(window.taskCache);
                        }).catch(reject);
                        return;
                    }
                }
                
                if (Date.now() - startTime > maxWait) {
                    reject(new Error('TaskCache not available after 5 seconds'));
                    return;
                }
                
                setTimeout(check, 50);
            };
            
            check();
        });
    }

    async _cleanupStaleTempTasks() {
        if (window.taskCache?.cleanupStaleTempTasks) {
            try {
                const result = await window.taskCache.cleanupStaleTempTasks();
                if (result.removed > 0) {
                    console.log(`[Orchestrator] Cleaned up ${result.removed} stale temp tasks`);
                }
            } catch (err) {
                console.warn('[Orchestrator] Failed to cleanup stale temp tasks:', err);
            }
        }
    }

    async _ensureTaskBootstrap() {
        // CROWN⁴.10 SINGLETON GUARD: Check both instance AND instantiation flag
        if (window.taskBootstrap) {
            this.modules.taskBootstrap = window.taskBootstrap;
            console.log('[Orchestrator] ✅ TaskBootstrap already exists');
            return;
        }
        
        // Check singleton guard flag to prevent race conditions
        if (window.__minaTaskBootstrapInstantiated) {
            console.warn('[Orchestrator] ⚠️ TaskBootstrap instantiation flag set but instance missing - waiting...');
            // Brief wait for instance to become available
            await new Promise(resolve => setTimeout(resolve, 50));
            if (window.taskBootstrap) {
                this.modules.taskBootstrap = window.taskBootstrap;
                console.log('[Orchestrator] ✅ TaskBootstrap available after wait');
                return;
            }
        }
        
        if (typeof TaskBootstrap !== 'undefined') {
            window.__minaTaskBootstrapInstantiated = true; // Set flag FIRST
            window.taskBootstrap = new TaskBootstrap();
            this.modules.taskBootstrap = window.taskBootstrap;
            console.log('[Orchestrator] ✅ TaskBootstrap created (singleton)');
        } else if (typeof window.TaskBootstrap !== 'undefined') {
            window.__minaTaskBootstrapInstantiated = true; // Set flag FIRST
            window.taskBootstrap = new window.TaskBootstrap();
            this.modules.taskBootstrap = window.taskBootstrap;
            console.log('[Orchestrator] ✅ TaskBootstrap created from window.TaskBootstrap (singleton)');
        } else {
            console.warn('[Orchestrator] ⚠️ TaskBootstrap class not available');
        }
    }

    async _ensureOptimisticUI() {
        // CROWN⁴.10 SINGLETON GUARD: Check both instance AND instantiation flag
        if (window.optimisticUI) {
            this.modules.optimisticUI = window.optimisticUI;
            console.log('[Orchestrator] ✅ OptimisticUI already exists');
            return;
        }
        
        // Check singleton guard flag to prevent race conditions
        if (window.__minaOptimisticUIInstantiated) {
            console.warn('[Orchestrator] ⚠️ OptimisticUI instantiation flag set but instance missing - waiting...');
            await new Promise(resolve => setTimeout(resolve, 50));
            if (window.optimisticUI) {
                this.modules.optimisticUI = window.optimisticUI;
                console.log('[Orchestrator] ✅ OptimisticUI available after wait');
                return;
            }
        }
        
        if (typeof OptimisticUI !== 'undefined') {
            window.__minaOptimisticUIInstantiated = true;
            window.optimisticUI = new OptimisticUI();
            this.modules.optimisticUI = window.optimisticUI;
            console.log('[Orchestrator] ✅ OptimisticUI created (singleton)');
        } else if (typeof window.OptimisticUI !== 'undefined') {
            window.__minaOptimisticUIInstantiated = true;
            window.optimisticUI = new window.OptimisticUI();
            this.modules.optimisticUI = window.optimisticUI;
            console.log('[Orchestrator] ✅ OptimisticUI created from window.OptimisticUI (singleton)');
        } else {
            console.warn('[Orchestrator] ⚠️ OptimisticUI class not available');
        }
    }

    async _ensureTaskMenuController() {
        if (window.taskMenuController) {
            this.modules.taskMenuController = window.taskMenuController;
            console.log('[Orchestrator] ✅ TaskMenuController already exists');
            return;
        }
        
        if (typeof TaskMenuController !== 'undefined') {
            window.taskMenuController = new TaskMenuController();
            this.modules.taskMenuController = window.taskMenuController;
            console.log('[Orchestrator] ✅ TaskMenuController created');
        } else if (typeof window.TaskMenuController !== 'undefined') {
            window.taskMenuController = new window.TaskMenuController();
            this.modules.taskMenuController = window.taskMenuController;
            console.log('[Orchestrator] ✅ TaskMenuController created (from window.TaskMenuController)');
        } else {
            console.warn('[Orchestrator] ⚠️ TaskMenuController class not available');
        }
    }

    async _ensureTaskActionsMenu() {
        if (window.taskActionsMenu) {
            this.modules.taskActionsMenu = window.taskActionsMenu;
            console.log('[Orchestrator] ✅ TaskActionsMenu already exists');
            return;
        }
        
        if (!window.optimisticUI) {
            console.warn('[Orchestrator] ⚠️ Cannot create TaskActionsMenu - OptimisticUI not available');
            return;
        }
        
        if (typeof TaskActionsMenu !== 'undefined') {
            window.taskActionsMenu = new TaskActionsMenu(window.optimisticUI);
            this.modules.taskActionsMenu = window.taskActionsMenu;
            console.log('[Orchestrator] ✅ TaskActionsMenu created');
        } else if (typeof window.TaskActionsMenu !== 'undefined') {
            window.taskActionsMenu = new window.TaskActionsMenu(window.optimisticUI);
            this.modules.taskActionsMenu = window.taskActionsMenu;
            console.log('[Orchestrator] ✅ TaskActionsMenu created (from window.TaskActionsMenu)');
        } else {
            console.warn('[Orchestrator] ⚠️ TaskActionsMenu class not available');
        }
    }

    async _ensureTaskProposalUI() {
        if (window.taskProposalUI) {
            this.modules.taskProposalUI = window.taskProposalUI;
            console.log('[Orchestrator] ✅ TaskProposalUI already exists');
            return;
        }
        
        const taskUI = window.taskBootstrap || this.modules.taskBootstrap;
        
        if (typeof TaskProposalUI !== 'undefined') {
            window.taskProposalUI = new TaskProposalUI(taskUI);
            this.modules.taskProposalUI = window.taskProposalUI;
            console.log('[Orchestrator] ✅ TaskProposalUI created');
        } else if (typeof window.TaskProposalUI !== 'undefined') {
            window.taskProposalUI = new window.TaskProposalUI(taskUI);
            this.modules.taskProposalUI = window.taskProposalUI;
            console.log('[Orchestrator] ✅ TaskProposalUI created (from window.TaskProposalUI)');
        } else {
            console.warn('[Orchestrator] ⚠️ TaskProposalUI class not available');
        }
    }

    async _initHelperModules() {
        const helpers = [
            ['TaskConfirmModal', 'taskConfirmModal'],
            ['TaskDatePicker', 'taskDatePicker'],
            ['TaskPrioritySelector', 'taskPrioritySelector'],
            ['TaskAssigneeSelector', 'taskAssigneeSelector'],
            ['TaskLabelsEditor', 'taskLabelsEditor'],
            ['TaskSnoozeModal', 'taskSnoozeModal'],
            ['TaskMergeModal', 'taskMergeModal'],
            ['TaskDuplicateConfirmation', 'taskDuplicateConfirmation']
        ];

        const failedModules = [];
        
        for (const [className, instanceName] of helpers) {
            if (window[instanceName]) {
                this.modules[instanceName] = window[instanceName];
                console.log(`[Orchestrator]   ✓ ${className} (already exists)`);
                continue;
            }
            
            const Constructor = window[className] || (typeof eval(className) !== 'undefined' ? eval(className) : null);
            if (Constructor) {
                try {
                    window[instanceName] = new Constructor();
                    this.modules[instanceName] = window[instanceName];
                    console.log(`[Orchestrator]   ✓ ${className}`);
                } catch (e) {
                    console.warn(`[Orchestrator]   ✗ ${className}: ${e.message}`);
                    failedModules.push(className);
                }
            } else {
                console.warn(`[Orchestrator]   ✗ ${className}: Constructor not available`);
                failedModules.push(className);
            }
        }
        
        if (failedModules.length > 0) {
            console.error('[Orchestrator] ❌ Failed to initialize modules:', failedModules.join(', '));
        }
        
        return failedModules;
    }
    
    /**
     * Check if all critical dependencies are ready
     */
    isReady() {
        const critical = ['optimisticUI', 'taskMenuController', 'taskActionsMenu'];
        return critical.every(mod => !!this.modules[mod] || !!window[mod]);
    }
    
    /**
     * Get the status of all modules
     */
    getModuleStatus() {
        const allModules = [
            'taskCache', 'taskBootstrap', 'optimisticUI', 'taskMenuController', 'taskActionsMenu',
            'taskConfirmModal', 'taskDatePicker', 'taskPrioritySelector', 'taskAssigneeSelector',
            'taskLabelsEditor', 'taskSnoozeModal', 'taskMergeModal', 'taskDuplicateConfirmation', 'toast'
        ];
        
        const status = {};
        for (const mod of allModules) {
            status[mod] = !!window[mod];
        }
        return status;
    }
    
    /**
     * Wire WebSocket events for real-time task synchronization
     * Subscribes to task:updated and task:deleted events from server
     */
    _wireWebSocketEvents() {
        if (!window.wsManager) {
            console.warn('[Orchestrator] ⚠️ WebSocketManager not available for event wiring');
            return;
        }
        
        const tasksSocket = window.wsManager.sockets?.tasks;
        if (!tasksSocket) {
            console.warn('[Orchestrator] ⚠️ Tasks WebSocket not connected yet');
            // Retry when socket connects
            window.wsManager.on('connection_status', (data) => {
                if (data.namespace === '/tasks' && data.connected) {
                    this._wireWebSocketEvents();
                }
            });
            return;
        }
        
        console.log('[Orchestrator] 🔌 Wiring WebSocket task events...');
        
        // Listen for task updates from server (other users/tabs)
        tasksSocket.on('task_updated', async (data) => {
            console.log('[Orchestrator] 📥 Received task_updated event:', data);
            try {
                const task = data.task || data;
                if (task && task.id) {
                    // Update cache
                    if (window.taskCache) {
                        await window.taskCache.saveTask(task);
                    }
                    // Update DOM via OptimisticUI
                    if (window.optimisticUI?._updateTaskInDOM) {
                        window.optimisticUI._updateTaskInDOM(task.id, task);
                    }
                    console.log(`[Orchestrator] ✅ Task ${task.id} synced from server`);
                }
            } catch (error) {
                console.error('[Orchestrator] ❌ Failed to process task_updated:', error);
            }
        });
        
        // Listen for task deletions from server
        tasksSocket.on('task_deleted', async (data) => {
            console.log('[Orchestrator] 📥 Received task_deleted event:', data);
            try {
                const taskId = data.task_id || data.id;
                if (taskId) {
                    // Remove from cache
                    if (window.taskCache) {
                        await window.taskCache.deleteTask(taskId);
                    }
                    // Remove from DOM
                    const taskCard = document.querySelector(`[data-task-id="${taskId}"]`);
                    if (taskCard) {
                        taskCard.remove();
                    }
                    console.log(`[Orchestrator] ✅ Task ${taskId} removed (synced from server)`);
                }
            } catch (error) {
                console.error('[Orchestrator] ❌ Failed to process task_deleted:', error);
            }
        });
        
        // Listen for new tasks created by other users
        tasksSocket.on('task_created', async (data) => {
            console.log('[Orchestrator] 📥 Received task_created event:', data);
            try {
                const task = data.task || data;
                if (task && task.id) {
                    // Only add if not already present (avoid duplicates from own creates)
                    const existing = document.querySelector(`[data-task-id="${task.id}"]`);
                    if (!existing && window.optimisticUI?._addTaskToDOM) {
                        await window.taskCache?.saveTask(task);
                        window.optimisticUI._addTaskToDOM(task);
                        console.log(`[Orchestrator] ✅ New task ${task.id} added from server`);
                    }
                }
            } catch (error) {
                console.error('[Orchestrator] ❌ Failed to process task_created:', error);
            }
        });
        
        console.log('[Orchestrator] ✅ WebSocket task events wired successfully');
    }
}

// Create orchestrator instance
window.tasksOrchestrator = new TasksPageOrchestrator();

// CROWN⁴.6 PERFORMANCE FIX: Defer initialization to allow skeleton to paint first
// Using double-rAF pattern to ensure browser has painted the skeleton before heavy work
// This enables <200ms first paint target
console.log('[Orchestrator] TasksPageOrchestrator loaded - deferring init for skeleton paint');

window.tasksReady = new Promise((resolve) => {
    // Double requestAnimationFrame: ensures browser has painted at least once
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            console.log('[Orchestrator] Skeleton painted, starting module initialization...');
            window.tasksOrchestrator.init().then(resolve).catch(resolve);
        });
    });
});
