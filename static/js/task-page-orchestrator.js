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

            // Step 6: Initialize helper modules
            console.log('[Orchestrator] Step 6: Initializing helper modules...');
            await this._initHelperModules();

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

            return this.modules;

        } catch (error) {
            console.error('[Orchestrator] ❌ Initialization failed:', error);
            throw error;
        }
    }

    async _waitForTaskCache() {
        if (window.taskCache) {
            if (window.taskCache.ready) {
                return window.taskCache;
            }
            if (typeof window.taskCache.init === 'function') {
                await window.taskCache.init();
                return window.taskCache;
            }
        }

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

    async _ensureTaskBootstrap() {
        if (window.taskBootstrap) {
            this.modules.taskBootstrap = window.taskBootstrap;
            console.log('[Orchestrator] ✅ TaskBootstrap already exists');
            return;
        }
        
        if (typeof TaskBootstrap !== 'undefined') {
            window.taskBootstrap = new TaskBootstrap();
            this.modules.taskBootstrap = window.taskBootstrap;
            console.log('[Orchestrator] ✅ TaskBootstrap created');
        } else if (typeof window.TaskBootstrap !== 'undefined') {
            window.taskBootstrap = new window.TaskBootstrap();
            this.modules.taskBootstrap = window.taskBootstrap;
            console.log('[Orchestrator] ✅ TaskBootstrap created (from window.TaskBootstrap)');
        } else {
            console.warn('[Orchestrator] ⚠️ TaskBootstrap class not available');
        }
    }

    async _ensureOptimisticUI() {
        if (window.optimisticUI) {
            this.modules.optimisticUI = window.optimisticUI;
            console.log('[Orchestrator] ✅ OptimisticUI already exists');
            return;
        }
        
        if (typeof OptimisticUI !== 'undefined') {
            window.optimisticUI = new OptimisticUI();
            this.modules.optimisticUI = window.optimisticUI;
            console.log('[Orchestrator] ✅ OptimisticUI created');
        } else if (typeof window.OptimisticUI !== 'undefined') {
            window.optimisticUI = new window.OptimisticUI();
            this.modules.optimisticUI = window.optimisticUI;
            console.log('[Orchestrator] ✅ OptimisticUI created (from window.OptimisticUI)');
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

    async _initHelperModules() {
        const helpers = [
            ['TaskConfirmModal', 'taskConfirmModal'],
            ['TaskDatePicker', 'taskDatePicker'],
            ['TaskPrioritySelector', 'taskPrioritySelector'],
            ['TaskSnoozeModal', 'taskSnoozeModal'],
            ['TaskMergeModal', 'taskMergeModal'],
            ['TaskDuplicateConfirmation', 'taskDuplicateConfirmation']
        ];

        for (const [className, instanceName] of helpers) {
            if (window[instanceName]) {
                continue;
            }
            
            const Constructor = window[className] || (typeof eval(className) !== 'undefined' ? eval(className) : null);
            if (Constructor) {
                try {
                    window[instanceName] = new Constructor();
                    console.log(`[Orchestrator]   ✓ ${className}`);
                } catch (e) {
                    console.warn(`[Orchestrator]   ✗ ${className}: ${e.message}`);
                }
            }
        }
    }
}

// Create orchestrator instance
window.tasksOrchestrator = new TasksPageOrchestrator();

// Initialize immediately since we're loaded last
// All deferred scripts should have executed by now
window.tasksReady = window.tasksOrchestrator.init();

console.log('[Orchestrator] TasksPageOrchestrator loaded - initializing immediately');
