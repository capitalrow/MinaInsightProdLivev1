/**
 * CROWN⁴.5 Task Prefetch Adapter
 * 
 * Integrates PrefetchController with Tasks page for intelligent background loading.
 * Warms detail cache after bootstrap to enable instant modal opens.
 * 
 * Key Features:
 * - Deferred until bootstrap complete (preserves <200ms first paint)
 * - Write-through to IndexedDB for cache consistency
 * - Workspace-scoped cache keys for multi-tenant security
 * - IntersectionObserver for visible task prefetching
 * - Request idle callback for low-priority background loading
 */

class TaskPrefetchAdapter {
    constructor() {
        this.prefetchController = null;
        this.initialized = false;
        this.observer = null;
        this.prefetchQueue = [];
    }

    /**
     * Initialize task prefetch adapter
     * Called AFTER bootstrap completes to avoid impacting first paint
     */
    async init() {
        if (this.initialized) {
            return;
        }

        console.log('🎯 TaskPrefetchAdapter initializing...');

        // Create PrefetchController with tasks adapter
        this.prefetchController = new window.PrefetchController({
            maxConcurrent: 2,  // Lower limit to not compete with user actions
            maxCacheSize: 100,  // More tasks than sessions
            cacheTimeout: 120000,  // 2 minutes (tasks change more frequently)
            adapter: this._createTasksAdapter()
        });

        // Set up intersection observer for visible tasks
        this._setupIntersectionObserver();

        // Listen for new task cards being added
        this._observeTaskCards();

        this.initialized = true;
        console.log('✅ TaskPrefetchAdapter ready');
    }

    /**
     * Create tasks adapter for PrefetchController
     * CROWN⁴.5: Pluggable adapter pattern
     */
    _createTasksAdapter() {
        const workspaceId = window.WORKSPACE_ID || 1;

        return {
            name: 'tasks',
            
            /**
             * Cache key function - workspace-scoped for multi-tenant isolation
             */
            keyFn: (taskId) => `task_${workspaceId}_${taskId}`,
            
            /**
             * Request function - fetches mini detail bundle
             */
            requestFn: (taskId) => `/api/tasks/${taskId}?detail=mini`,
            
            /**
             * Hydrate function - write through to IndexedDB
             * CROWN⁴.6: Uses setTaskDetail method for proper cache persistence
             */
            hydrateFn: async (taskId, data) => {
                if (!window.taskCache || typeof window.taskCache.setTaskDetail !== 'function') {
                    return;
                }

                try {
                    await window.taskCache.setTaskDetail(taskId, data);
                    console.log(`💾 Hydrated task ${taskId} to IndexedDB`);
                } catch (error) {
                    console.warn(`⚠️ Failed to hydrate task ${taskId}:`, error);
                }
            }
        };
    }

    /**
     * Set up IntersectionObserver for visible task cards
     */
    _setupIntersectionObserver() {
        // Options: prefetch when 50% visible, with 100px margin
        const options = {
            root: null,
            rootMargin: '100px',
            threshold: 0.5
        };

        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const taskCard = entry.target;
                    const taskId = taskCard.dataset.taskId;
                    
                    if (taskId && !this.prefetchController.isPrefetched(taskId)) {
                        // Schedule prefetch via requestIdleCallback for low priority
                        this._schedulePrefetch(taskId, { priority: 1 });
                    }
                }
            });
        }, options);
    }

    /**
     * Observe all task cards for prefetching
     */
    _observeTaskCards() {
        const taskCards = document.querySelectorAll('.task-card[data-task-id]');
        
        taskCards.forEach(card => {
            this.observer.observe(card);
        });

        console.log(`👀 Observing ${taskCards.length} task cards for prefetching`);

        // Set up MutationObserver to watch for new task cards
        const taskList = document.getElementById('tasks-list');
        if (taskList) {
            const mutationObserver = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1 && node.classList.contains('task-card')) {
                            const taskId = node.dataset.taskId;
                            if (taskId) {
                                this.observer.observe(node);
                            }
                        }
                    });
                });
            });

            mutationObserver.observe(taskList, {
                childList: true,
                subtree: true
            });
        }
    }

    /**
     * Schedule prefetch via requestIdleCallback
     * @param {string} taskId - Task ID to prefetch
     * @param {Object} options - Prefetch options
     */
    _schedulePrefetch(taskId, options = {}) {
        if ('requestIdleCallback' in window) {
            requestIdleCallback(() => {
                this._executePrefetch(taskId, options);
            }, { timeout: 2000 });
        } else {
            // Fallback: use setTimeout with delay
            setTimeout(() => {
                this._executePrefetch(taskId, options);
            }, 100);
        }
    }

    /**
     * Execute prefetch
     */
    async _executePrefetch(taskId, options = {}) {
        try {
            await this.prefetchController.prefetch(taskId, options);
            
            // Emit telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordEvent('task_prefetched', {
                    task_id: taskId,
                    priority: options.priority || 0
                });
            }
        } catch (error) {
            // Silently fail - prefetch is optional
            console.debug(`Prefetch failed for task ${taskId}:`, error);
        }
    }

    /**
     * Prefetch specific task (for high-priority scenarios)
     * @param {string} taskId - Task ID to prefetch
     * @param {Object} options - Prefetch options
     */
    async prefetchTask(taskId, options = {}) {
        if (!this.initialized) {
            await this.init();
        }

        return this.prefetchController.prefetch(taskId, options);
    }

    /**
     * Get cached task data
     * @param {string} taskId - Task ID
     * @returns {Object|null} Cached task data or null
     */
    getCachedTask(taskId) {
        if (!this.initialized || !this.prefetchController) {
            return null;
        }

        return this.prefetchController.getCached(taskId);
    }

    /**
     * Prefetch tasks in viewport on bootstrap complete
     * Called by TaskBootstrap after first paint
     */
    prefetchVisibleTasks() {
        console.log('🚀 Prefetching visible tasks...');

        const visibleTaskCards = document.querySelectorAll('.task-card[data-task-id]');
        const taskIds = Array.from(visibleTaskCards)
            .slice(0, 10)  // Limit to first 10 visible
            .map(card => card.dataset.taskId)
            .filter(id => id && !this.prefetchController.isPrefetched(id));

        // Prefetch with increasing priority
        taskIds.forEach((taskId, index) => {
            this._schedulePrefetch(taskId, { priority: 10 - index });
        });

        console.log(`📦 Scheduled ${taskIds.length} tasks for prefetching`);
    }

    /**
     * Abort all active prefetches
     */
    abortAll() {
        if (this.prefetchController) {
            return this.prefetchController.abortAll();
        }
        return 0;
    }

    /**
     * Get prefetch statistics
     */
    getStats() {
        if (this.prefetchController) {
            return this.prefetchController.getStats();
        }
        return null;
    }
}

// Create singleton instance
const taskPrefetchAdapter = new TaskPrefetchAdapter();

// Listen for bootstrap complete event
document.addEventListener('task:bootstrap:complete', () => {
    console.log('📡 Bootstrap complete, activating task prefetching...');
    
    // Initialize adapter (deferred for performance)
    setTimeout(() => {
        taskPrefetchAdapter.init().then(() => {
            // Prefetch visible tasks
            taskPrefetchAdapter.prefetchVisibleTasks();
        });
    }, 100);
});

// Export for use in other modules
window.taskPrefetchAdapter = taskPrefetchAdapter;
