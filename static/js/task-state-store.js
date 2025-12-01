/**
 * TaskStateStore - CROWN⁴.6 Single Source of Truth
 * 
 * This module is the ONLY authority for task data and counter computation.
 * All other modules (Bootstrap, OptimisticUI, WebSocket, Cache) MUST:
 * 1. Mutate task data through TaskStateStore methods
 * 2. Read counters from TaskStateStore.getCounters()
 * 3. Never directly update counter badges
 * 
 * Architecture: Linear/Asana pattern with optimistic updates
 * - Server data hydrates the store on page load
 * - Optimistic mutations update store immediately
 * - WebSocket confirmations reconcile store state
 * - All UI reads from store, never from multiple sources
 */

(function() {
    'use strict';

    class TaskStateStore {
        constructor() {
            this._tasks = new Map();  // taskId -> task object
            this._workspaceId = null;
            this._initialized = false;
            this._listeners = new Set();
            this._pendingTempTasks = new Set();  // temp task IDs being synced
            this._lastCounters = null;
            this._viewMode = 'normal';  // 'normal' or 'meeting' - tracks current view mode
            
            // CROWN⁴.6 FIX: Proper stabilization that preserves server-rendered values
            this._initialLoadComplete = false;  // True after server sync finishes
            this._serverHydrateComplete = false; // True after server data is in store
            this._viewTransitionActive = false; // True during mode switches
            this._stabilizationTimeout = null;
            
            // CROWN⁴.7: Counter update debouncing to prevent rapid flickering
            this._counterUpdateDebounceTimer = null;
            this._pendingCounterUpdate = null;
            
            // Capture server-rendered counter values as baseline
            this._serverRenderedCounters = this._captureServerRenderedCounters();
            
            console.log('[TaskStateStore] Initializing with server-rendered baseline:', this._serverRenderedCounters);
            
            // Listen for view mode changes
            this._setupViewModeListeners();
            
            // Listen for sync completion
            this._setupSyncListeners();
        }
        
        /**
         * Capture server-rendered counter values from DOM as baseline
         * These values are preserved until server sync completes
         */
        _captureServerRenderedCounters() {
            const counters = { all: 0, active: 0, archived: 0 };
            
            // Read from data-counter badges
            const allBadge = document.querySelector('[data-counter="all"]');
            const activeBadge = document.querySelector('[data-counter="active"]');
            const archivedBadge = document.querySelector('[data-counter="archived"]');
            
            if (allBadge) counters.all = parseInt(allBadge.textContent) || 0;
            if (activeBadge) counters.active = parseInt(activeBadge.textContent) || 0;
            if (archivedBadge) counters.archived = parseInt(archivedBadge.textContent) || 0;
            
            return counters;
        }
        
        /**
         * Setup listeners for sync events
         */
        _setupSyncListeners() {
            // Mark initial load complete when background sync finishes
            // CRITICAL: Only complete if server hydrate has occurred (tasks in store)
            window.addEventListener('tasks:sync:success', () => {
                if (this._serverHydrateComplete) {
                    this._completeInitialLoad('sync_success');
                } else {
                    console.log('[TaskStateStore] Sync success received, waiting for server hydrate');
                }
            });
            
            window.addEventListener('tasks:sync:error', () => {
                // On sync error, show whatever we have
                if (this._serverHydrateComplete || this._tasks.size > 0) {
                    this._completeInitialLoad('sync_error');
                } else {
                    console.log('[TaskStateStore] Sync error, but no data yet - preserving server-rendered values');
                }
            });
            
            // Failsafe: Complete initial load after 4 seconds (increased from 3s for slower networks)
            // But only if we have data or server hydrate completed
            this._stabilizationTimeout = setTimeout(() => {
                if (!this._initialLoadComplete) {
                    if (this._serverHydrateComplete || this._tasks.size > 0) {
                        this._completeInitialLoad('timeout');
                    } else {
                        console.log('[TaskStateStore] Timeout but no data - preserving server-rendered values');
                    }
                }
            }, 4000);
        }
        
        /**
         * Complete initial load and enable counter updates
         * @param {string} reason - Why initial load completed
         */
        _completeInitialLoad(reason) {
            if (this._initialLoadComplete) return;
            
            this._initialLoadComplete = true;
            if (this._stabilizationTimeout) {
                clearTimeout(this._stabilizationTimeout);
                this._stabilizationTimeout = null;
            }
            
            console.log(`[TaskStateStore] Initial load complete (${reason}) - counters now live`);
            this._updateAllUI();
        }
        
        /**
         * Setup listeners for view mode changes (Meeting Intelligence Mode)
         */
        _setupViewModeListeners() {
            // Listen for meeting mode activation/deactivation
            window.addEventListener('meetingMode:activated', () => {
                this._viewMode = 'meeting';
                console.log('[TaskStateStore] View mode changed to: meeting');
                // Only update if initial load is complete
                if (this._initialLoadComplete) {
                    this._updateAllUI();
                }
            });
            
            window.addEventListener('meetingMode:deactivated', () => {
                this._viewMode = 'normal';
                console.log('[TaskStateStore] View mode changed to: normal');
                // Only update if initial load is complete
                if (this._initialLoadComplete) {
                    this._updateAllUI();
                }
            });
        }
        
        /**
         * Begin a view transition (pauses counter updates)
         * Used for meeting mode and group similar toggles
         */
        beginViewTransition() {
            this._viewTransitionActive = true;
            console.log('[TaskStateStore] View transition started');
        }
        
        /**
         * End a view transition and update counters
         */
        endViewTransition() {
            this._viewTransitionActive = false;
            console.log('[TaskStateStore] View transition ended');
            if (this._initialLoadComplete) {
                this._updateAllUI();
            }
        }

        /**
         * Initialize store with workspace context
         * @param {number|string} workspaceId
         */
        setWorkspace(workspaceId) {
            this._workspaceId = parseInt(workspaceId) || null;
            console.log('[TaskStateStore] Workspace set:', this._workspaceId);
        }

        /**
         * Hydrate store from server/cache data
         * This is the ONLY entry point for bulk task loading
         * @param {Array} tasks - Array of task objects
         * @param {string} source - 'server', 'cache', or 'websocket'
         */
        hydrate(tasks, source = 'server') {
            if (!Array.isArray(tasks)) {
                console.warn('[TaskStateStore] hydrate() called with non-array:', tasks);
                return;
            }

            const startTime = performance.now();
            let added = 0, updated = 0, skipped = 0;

            tasks.forEach(task => {
                if (!task || !task.id) {
                    skipped++;
                    return;
                }

                const taskId = String(task.id);
                
                // Skip temp tasks - they're managed separately
                if (taskId.startsWith('temp_') || taskId.includes('_temp_')) {
                    skipped++;
                    return;
                }

                // Workspace filter - only accept tasks for current workspace
                if (this._workspaceId && task.workspace_id && 
                    parseInt(task.workspace_id) !== this._workspaceId) {
                    skipped++;
                    return;
                }

                // Skip deleted/soft-deleted tasks
                if (task.deleted_at || task.is_deleted) {
                    skipped++;
                    return;
                }

                if (this._tasks.has(taskId)) {
                    updated++;
                } else {
                    added++;
                }

                this._tasks.set(taskId, {
                    ...task,
                    id: taskId,
                    _storeTimestamp: Date.now()
                });
            });

            this._initialized = true;
            const elapsed = performance.now() - startTime;
            
            console.log(`[TaskStateStore] Hydrated from ${source}:`, {
                added, updated, skipped,
                total: this._tasks.size,
                elapsed: `${elapsed.toFixed(1)}ms`
            });

            this._notifyListeners('hydrate');
            
            // CROWN⁴.6 FIX: Only update UI if initial load is complete
            // During initial load, server-rendered values are preserved
            // Cache hydration should NOT trigger counter updates
            if (this._initialLoadComplete) {
                this._updateAllUI();
            } else if (source === 'server') {
                // Server data is now in store - mark hydrate complete and enable counters
                this._serverHydrateComplete = true;
                this._completeInitialLoad('server_hydrate');
            } else {
                console.log('[TaskStateStore] Skipping UI update during initial load (preserving server-rendered values)');
            }
        }

        /**
         * Add or update a single task (for optimistic UI)
         * @param {Object} task - Task object
         * @param {boolean} isTemp - Whether this is a temp task
         * @returns {string} The task ID
         */
        upsertTask(task, isTemp = false) {
            if (!task || !task.id) {
                console.warn('[TaskStateStore] upsertTask() called with invalid task');
                return null;
            }

            const taskId = String(task.id);

            // Track temp tasks separately
            if (isTemp || taskId.startsWith('temp_')) {
                this._pendingTempTasks.add(taskId);
                console.log('[TaskStateStore] Tracking temp task:', taskId);
                // Don't add temp tasks to main store - they're not confirmed yet
                return taskId;
            }

            // Workspace filter
            if (this._workspaceId && task.workspace_id && 
                parseInt(task.workspace_id) !== this._workspaceId) {
                console.log('[TaskStateStore] Rejecting task from different workspace:', taskId);
                return null;
            }

            this._tasks.set(taskId, {
                ...task,
                id: taskId,
                _storeTimestamp: Date.now()
            });

            console.log('[TaskStateStore] Upserted task:', taskId);
            this._notifyListeners('upsert', taskId);
            this._updateAllUI();
            return taskId;
        }

        /**
         * Reconcile a temp task with its real server ID
         * @param {string} tempId - Temporary task ID
         * @param {string} realId - Real server-assigned ID
         * @param {Object} task - Full task object from server
         */
        reconcileTempTask(tempId, realId, task) {
            // Remove from pending temp tasks
            this._pendingTempTasks.delete(tempId);
            
            // Add the real task to store
            if (task && realId) {
                this.upsertTask({ ...task, id: realId });
                console.log('[TaskStateStore] Reconciled temp → real:', tempId, '→', realId);
            }
        }

        /**
         * Remove a task from the store
         * @param {string|number} taskId
         */
        removeTask(taskId) {
            const id = String(taskId);
            
            // Remove from temp tracking if applicable
            this._pendingTempTasks.delete(id);
            
            // Remove from main store
            if (this._tasks.delete(id)) {
                console.log('[TaskStateStore] Removed task:', id);
                this._notifyListeners('remove', id);
                this._updateAllUI();
                return true;
            }
            return false;
        }

        /**
         * Get a task by ID
         * @param {string|number} taskId
         * @returns {Object|null}
         */
        getTask(taskId) {
            return this._tasks.get(String(taskId)) || null;
        }

        /**
         * Get all tasks as array (filtered, confirmed only)
         * @returns {Array}
         */
        getAllTasks() {
            return Array.from(this._tasks.values());
        }

        /**
         * CORE: Compute counters from store data
         * This is the ONLY place counters should be calculated
         * @returns {Object} { all, active, archived, todo, in_progress, completed, pending }
         */
        computeCounters() {
            const counters = {
                all: 0,
                active: 0,
                archived: 0,
                todo: 0,
                in_progress: 0,
                pending: 0,
                completed: 0,
                cancelled: 0
            };

            this._tasks.forEach(task => {
                // Skip any remaining invalid entries
                if (!task || !task.id) return;
                
                const taskId = String(task.id);
                
                // Skip temp tasks (shouldn't be in store, but double-check)
                if (taskId.startsWith('temp_') || taskId.includes('_temp_')) return;
                
                // Skip deleted tasks
                if (task.deleted_at || task.is_deleted) return;

                // Count as valid task
                counters.all++;

                // Get normalized status
                const status = (task.status || 'todo').toLowerCase().trim();
                
                // Count by status
                if (status === 'todo') counters.todo++;
                else if (status === 'in_progress') counters.in_progress++;
                else if (status === 'pending') counters.pending++;
                else if (status === 'completed') counters.completed++;
                else if (status === 'cancelled') counters.cancelled++;

                // Active vs Archived logic (Linear/Asana pattern)
                // Archived = completed or cancelled
                if (status === 'completed' || status === 'cancelled') {
                    counters.archived++;
                } else {
                    counters.active++;
                }
            });

            // Add pending temp tasks to "pending" for UI feedback
            // But NOT to "all" - they're not confirmed yet
            const pendingCount = this._pendingTempTasks.size;
            if (pendingCount > 0) {
                console.log('[TaskStateStore] Pending temp tasks:', pendingCount);
            }

            this._lastCounters = counters;
            return counters;
        }

        /**
         * Get last computed counters (cached)
         * @returns {Object|null}
         */
        getCounters() {
            return this._lastCounters || this.computeCounters();
        }

        /**
         * Update ALL UI elements that display counters
         * Single point of UI synchronization
         */
        _updateAllUI() {
            // CROWN⁴.6 FIX: Skip updates during initial load or view transitions
            // Server-rendered values are preserved until sync completes
            if (!this._initialLoadComplete) {
                console.log('[TaskStateStore] Initial load not complete - preserving server-rendered counters');
                return;
            }
            
            if (this._viewTransitionActive) {
                console.log('[TaskStateStore] View transition active - skipping counter update');
                return;
            }
            
            const counters = this.computeCounters();
            
            // 1. Update counter badges
            this._updateCounterBadges(counters);
            
            // 2. Update "X of Y tasks" indicator
            this._updatePaginationIndicator(counters);
            
            // 3. Update pending tasks banner
            this._updatePendingBanner(counters);
            
            console.log('[TaskStateStore] UI updated:', counters);
        }

        /**
         * Update counter badge elements with debouncing
         * CROWN⁴.7: Debounce to prevent rapid flickering from consecutive updates
         * @param {Object} counters
         */
        _updateCounterBadges(counters) {
            // Store pending update
            this._pendingCounterUpdate = counters;
            
            // Debounce: wait 100ms for rapid updates to settle
            if (this._counterUpdateDebounceTimer) {
                clearTimeout(this._counterUpdateDebounceTimer);
            }
            
            this._counterUpdateDebounceTimer = setTimeout(() => {
                const finalCounters = this._pendingCounterUpdate;
                this._pendingCounterUpdate = null;
                this._counterUpdateDebounceTimer = null;
                
                if (!finalCounters) return;
                
                Object.entries(finalCounters).forEach(([key, count]) => {
                    const badge = document.querySelector(`[data-counter="${key}"]`);
                    if (badge) {
                        const currentValue = parseInt(badge.textContent) || 0;
                        if (currentValue !== count) {
                            badge.textContent = count;
                            
                            // Subtle animation on change (emotional UX)
                            badge.classList.remove('counter-updated');
                            void badge.offsetWidth; // Force reflow
                            badge.classList.add('counter-updated');
                        }
                    }
                });
            }, 100);
        }

        /**
         * Update "X of Y tasks" pagination indicator
         * CROWN⁴.6: Handles both normal and meeting view modes
         * @param {Object} counters
         */
        _updatePaginationIndicator(counters) {
            const visibleCountEl = document.getElementById('visible-task-count');
            const totalCountEl = document.getElementById('total-task-count');
            
            if (!visibleCountEl && !totalCountEl) return;

            // Count visible task cards in DOM (respects current view mode and filters)
            // In meeting mode, tasks are inside .meeting-group-tasks containers
            const selector = this._viewMode === 'meeting' 
                ? '.meeting-group-tasks .task-card:not([style*="display: none"]):not(.deleting):not(.hidden)'
                : '.task-card:not([style*="display: none"]):not(.deleting):not(.hidden)';
            
            const visibleCards = document.querySelectorAll(selector);
            let visibleCount = 0;
            
            visibleCards.forEach(card => {
                const taskId = card.dataset?.taskId;
                // Only count non-temp, non-deleted tasks
                if (taskId && !taskId.startsWith('temp_') && !taskId.includes('_temp_')) {
                    visibleCount++;
                }
            });

            // Update visible count
            if (visibleCountEl) {
                visibleCountEl.textContent = visibleCount;
            }
            
            // Total always reflects store count (single source of truth)
            if (totalCountEl) {
                totalCountEl.textContent = counters.all;
            }
        }

        /**
         * Update pending tasks banner
         * CROWN⁴.6: Hides in meeting mode, shows accurate count in normal mode
         * @param {Object} counters
         */
        _updatePendingBanner(counters) {
            const banner = document.querySelector('.pending-tasks-banner, [data-pending-banner]');
            if (!banner) return;

            // Hide banner in meeting mode - meeting groups show their own stats
            if (this._viewMode === 'meeting') {
                banner.style.display = 'none';
                return;
            }

            // In normal mode, show pending tasks count (active tasks needing attention)
            const pendingCount = counters.active;
            
            if (pendingCount > 0) {
                banner.textContent = `${pendingCount} pending tasks`;
                banner.style.display = 'inline-block';
            } else {
                banner.style.display = 'none';
            }
        }

        /**
         * Subscribe to store changes
         * @param {Function} callback
         * @returns {Function} Unsubscribe function
         */
        subscribe(callback) {
            this._listeners.add(callback);
            return () => this._listeners.delete(callback);
        }

        /**
         * Notify all listeners of changes
         * @param {string} action
         * @param {string|null} taskId
         */
        _notifyListeners(action, taskId = null) {
            this._listeners.forEach(callback => {
                try {
                    callback({ action, taskId, counters: this.getCounters() });
                } catch (e) {
                    console.error('[TaskStateStore] Listener error:', e);
                }
            });
        }

        /**
         * Force refresh all UI from store state
         * Call this after major state changes
         */
        forceRefresh() {
            console.log('[TaskStateStore] Force refresh triggered');
            this._updateAllUI();
        }

        /**
         * Clear all data (for logout/workspace switch)
         */
        clear() {
            this._tasks.clear();
            this._pendingTempTasks.clear();
            this._lastCounters = null;
            this._initialized = false;
            console.log('[TaskStateStore] Store cleared');
        }

        /**
         * Debug: Get store stats
         */
        getStats() {
            return {
                taskCount: this._tasks.size,
                pendingTempTasks: this._pendingTempTasks.size,
                workspaceId: this._workspaceId,
                initialized: this._initialized,
                counters: this.getCounters()
            };
        }
    }

    // Create singleton instance
    const taskStateStore = new TaskStateStore();

    // Expose globally
    window.taskStateStore = taskStateStore;
    window.TaskStateStore = TaskStateStore;

    // Initialize workspace from page context
    document.addEventListener('DOMContentLoaded', () => {
        const workspaceId = window.WORKSPACE_ID || 
                           document.body.dataset?.workspaceId ||
                           1; // Default workspace
        taskStateStore.setWorkspace(workspaceId);
    });

    console.log('[TaskStateStore] Module loaded - single source of truth ready');
})();
