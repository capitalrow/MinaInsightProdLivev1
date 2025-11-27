/**
 * CROWN⁴.6 TasksPageOrchestrator - Unified Module Initialization
 * 
 * Solves script loading race conditions by:
 * 1. Waiting for IndexedDB/TaskCache to be ready
 * 2. Instantiating modules in correct dependency order
 * 3. Registering them on window
 * 4. Dispatching tasks:ready event for downstream consumers
 */

class TasksPageOrchestrator {
    constructor() {
        this.initialized = false;
        this.initPromise = null;
        this.modules = {};
        
        // Signal to other modules that orchestrator is managing initialization
        window._orchestratorActive = true;
    }

    /**
     * Initialize all task page modules in correct dependency order
     * @returns {Promise} Resolves when all modules are ready
     */
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

            // Step 2: Initialize TaskBootstrap (depends on TaskCache)
            console.log('[Orchestrator] Step 2: Initializing TaskBootstrap...');
            if (typeof TaskBootstrap !== 'undefined' && !window.taskBootstrap) {
                window.taskBootstrap = new TaskBootstrap();
                this.modules.taskBootstrap = window.taskBootstrap;
                console.log('[Orchestrator] ✅ TaskBootstrap created');
            } else if (window.taskBootstrap) {
                this.modules.taskBootstrap = window.taskBootstrap;
                console.log('[Orchestrator] ✅ TaskBootstrap already exists');
            }

            // Step 3: Initialize OptimisticUI (depends on TaskCache)
            console.log('[Orchestrator] Step 3: Initializing OptimisticUI...');
            if (typeof OptimisticUI !== 'undefined' && !window.optimisticUI) {
                window.optimisticUI = new OptimisticUI();
                this.modules.optimisticUI = window.optimisticUI;
                console.log('[Orchestrator] ✅ OptimisticUI created');
            } else if (window.optimisticUI) {
                this.modules.optimisticUI = window.optimisticUI;
                console.log('[Orchestrator] ✅ OptimisticUI already exists');
            }

            // Step 4: Initialize TaskMenuController
            console.log('[Orchestrator] Step 4: Initializing TaskMenuController...');
            if (typeof TaskMenuController !== 'undefined' && !window.taskMenuController) {
                window.taskMenuController = new TaskMenuController();
                this.modules.taskMenuController = window.taskMenuController;
                console.log('[Orchestrator] ✅ TaskMenuController created');
            } else if (window.taskMenuController) {
                this.modules.taskMenuController = window.taskMenuController;
                console.log('[Orchestrator] ✅ TaskMenuController already exists');
            }

            // Step 5: Initialize TaskActionsMenu (depends on OptimisticUI, TaskMenuController)
            console.log('[Orchestrator] Step 5: Initializing TaskActionsMenu...');
            if (typeof TaskActionsMenu !== 'undefined' && !window.taskActionsMenu) {
                if (window.optimisticUI) {
                    window.taskActionsMenu = new TaskActionsMenu(window.optimisticUI);
                    this.modules.taskActionsMenu = window.taskActionsMenu;
                    console.log('[Orchestrator] ✅ TaskActionsMenu created');
                } else {
                    console.warn('[Orchestrator] ⚠️ Cannot create TaskActionsMenu - OptimisticUI not available');
                }
            } else if (window.taskActionsMenu) {
                this.modules.taskActionsMenu = window.taskActionsMenu;
                console.log('[Orchestrator] ✅ TaskActionsMenu already exists');
            }

            // Step 6: Initialize helper modules
            console.log('[Orchestrator] Step 6: Initializing helper modules...');
            await this._initHelperModules();

            // Mark as initialized
            this.initialized = true;
            
            const elapsed = Math.round(performance.now() - startTime);
            console.log(`[Orchestrator] ========== All Modules Ready in ${elapsed}ms ==========`);

            // Dispatch ready event for downstream consumers
            document.dispatchEvent(new CustomEvent('tasks:ready', {
                detail: {
                    modules: Object.keys(this.modules),
                    elapsed
                }
            }));

            return this.modules;

        } catch (error) {
            console.error('[Orchestrator] ❌ Initialization failed:', error);
            throw error;
        }
    }

    /**
     * Wait for TaskCache to be initialized
     */
    async _waitForTaskCache() {
        // If taskCache exists and has init method, call it
        if (window.taskCache) {
            if (window.taskCache.ready) {
                return window.taskCache;
            }
            if (typeof window.taskCache.init === 'function') {
                await window.taskCache.init();
                return window.taskCache;
            }
        }

        // Wait for taskCache to appear (max 5 seconds)
        return new Promise((resolve, reject) => {
            const maxWait = 5000;
            const startTime = Date.now();
            
            const check = () => {
                if (window.taskCache) {
                    if (window.taskCache.ready) {
                        resolve(window.taskCache);
                        return;
                    }
                    if (typeof window.taskCache.init === 'function') {
                        window.taskCache.init().then(() => {
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

    /**
     * Initialize helper modules (confirmation modals, pickers, etc.)
     */
    async _initHelperModules() {
        // Task Confirmation Modal
        if (typeof TaskConfirmModal !== 'undefined' && !window.taskConfirmModal) {
            window.taskConfirmModal = new TaskConfirmModal();
            console.log('[Orchestrator]   ✓ TaskConfirmModal');
        }

        // Task Date Picker
        if (typeof TaskDatePicker !== 'undefined' && !window.taskDatePicker) {
            window.taskDatePicker = new TaskDatePicker();
            console.log('[Orchestrator]   ✓ TaskDatePicker');
        }

        // Task Priority Selector
        if (typeof TaskPrioritySelector !== 'undefined' && !window.taskPrioritySelector) {
            window.taskPrioritySelector = new TaskPrioritySelector();
            console.log('[Orchestrator]   ✓ TaskPrioritySelector');
        }

        // Task Snooze Modal
        if (typeof TaskSnoozeModal !== 'undefined' && !window.taskSnoozeModal) {
            window.taskSnoozeModal = new TaskSnoozeModal();
            console.log('[Orchestrator]   ✓ TaskSnoozeModal');
        }

        // Task Merge Modal
        if (typeof TaskMergeModal !== 'undefined' && !window.taskMergeModal) {
            window.taskMergeModal = new TaskMergeModal();
            console.log('[Orchestrator]   ✓ TaskMergeModal');
        }

        // Task Duplicate Confirmation
        if (typeof TaskDuplicateConfirmation !== 'undefined' && !window.taskDuplicateConfirmation) {
            window.taskDuplicateConfirmation = new TaskDuplicateConfirmation();
            console.log('[Orchestrator]   ✓ TaskDuplicateConfirmation');
        }
    }
}

// Create orchestrator and expose ready promise
window.tasksOrchestrator = new TasksPageOrchestrator();

// Auto-initialize when DOM is ready and all scripts have loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Small delay to ensure all deferred scripts have executed
        setTimeout(() => {
            window.tasksReady = window.tasksOrchestrator.init();
        }, 10);
    });
} else {
    // DOM already loaded, but wait a tick for other scripts
    setTimeout(() => {
        window.tasksReady = window.tasksOrchestrator.init();
    }, 10);
}

console.log('[Orchestrator] TasksPageOrchestrator loaded - awaiting DOM ready');
