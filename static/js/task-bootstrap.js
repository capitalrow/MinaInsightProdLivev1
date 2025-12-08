/**
 * CROWN⁴.5 Task Bootstrap - Cache-First Architecture
 * Achieves <200ms first paint by loading from IndexedDB first,
 * then syncing with server in background.
 */

class TaskBootstrap {
    constructor() {
        this.cache = window.taskCache;
        this.initialized = false;
        this.syncInProgress = false;
        this.lastSyncTimestamp = null;
        this.currentState = null; // 'loading', 'empty', 'tasks', 'error'
        this.perf = {
            cache_load_start: 0,
            cache_load_end: 0,
            first_paint: 0,
            sync_start: 0,
            sync_end: 0
        };
        
        // CROWN⁴.6: Singleton TaskGrouping instance
        this.taskGrouping = null;
        this.groupingThreshold = 4; // Enable grouping for 4+ tasks (lowered for testing)
        
        // CROWN⁴.9 FIX: Render lock and debounce to prevent render loops
        this._renderInProgress = false;
        this._renderDebounceTimer = null;
        this._lastRenderTime = 0;
        this._renderDebounceMs = 250; // Minimum 250ms between renders (increased for stability)
        this._pendingRenderArgs = null;
        
        // CROWN⁴.11 FIX: Post-hydration settling phase
        // After hydration, wait for data sources to stabilize before accepting new renders
        this._postHydrationSettlingMs = 500; // 500ms settling period
        this._hydrationCompleteTime = 0;
        
        // CROWN⁴.10 FIX: Payload hash comparison to prevent redundant renders
        // Stores hash of last rendered task list to skip identical payloads
        this._lastRenderPayloadHash = null;
        this._renderHashSkipCount = 0; // Telemetry: count of skipped renders
        
        // CROWN⁴.9 HYDRATION GATE: Industry-standard SSR hydration pattern
        // Blocks ALL empty renders until first successful hydration completes
        // This prevents flicker during initialization when multiple systems
        // (cache, WebSocket, BroadcastSync, MultiTabSync) race to render
        this._hydrationReady = false;
        this._hydrationStartTime = null;
        this._ssrCardCount = 0; // Count of server-rendered cards on page load
        this._firstRenderComplete = false;
        this._deferredRenderQueue = []; // Queue for renders before hydration
        
        // Expose hydration state globally for other modules to check
        window.taskHydrationReady = false;
        
        // CROWN⁴.12: Priority-based render scheduler
        // Routes all renders through a central scheduler that enforces priority ordering
        // and validates context to prevent stale payloads from overwriting user intent
        this.renderScheduler = null;
        this._renderRequestSeq = 0;
        this._initRenderScheduler();
    }
    
    /**
     * CROWN⁴.12: Initialize the render scheduler
     * The scheduler controls all render requests with priority-based ordering
     */
    _initRenderScheduler() {
        if (typeof TaskRenderScheduler === 'undefined') {
            console.warn('⚠️ [TaskBootstrap] TaskRenderScheduler not loaded, using direct rendering');
            return;
        }
        
        this.renderScheduler = new TaskRenderScheduler({
            onRender: (tasks, options) => this._executeRender(tasks, options)
        });
        
        // Listen for context changes from filter/search
        document.addEventListener('task:view-context-changed', (e) => {
            if (this.renderScheduler && e.detail) {
                this.renderScheduler.updateContext({
                    filter: e.detail.filter || 'active',
                    search: e.detail.search || '',
                    sort: e.detail.sort || { field: 'created_at', direction: 'desc' }
                });
            }
        });
        
        console.log('📋 [TaskBootstrap] RenderScheduler integrated');
    }
    
    /**
     * CROWN⁴.12: Get current view context for render requests
     * Retrieves filter/search/sort state from scheduler or TaskSearchSort
     * @returns {Object} { filter, search, sort } - always returns normalized objects
     */
    _getCurrentViewContext() {
        const defaultSort = { field: 'created_at', direction: 'desc' };
        const defaultContext = { filter: 'active', search: '', sort: defaultSort };
        
        // Priority 1: Get from scheduler if available
        if (this.renderScheduler) {
            const ctx = this.renderScheduler.getContext();
            return {
                filter: ctx.filter || 'active',
                search: ctx.search || '',
                sort: (ctx.sort && ctx.sort.field) ? ctx.sort : defaultSort
            };
        }
        
        // Priority 2: Get from TaskSearchSort if available
        if (window.taskSearchSort) {
            const sortConfig = window.taskSearchSort.mapSortKeyToConfig?.(window.taskSearchSort.currentSort);
            return {
                filter: window.taskSearchSort.currentFilter || 'active',
                search: window.taskSearchSort.searchQuery || '',
                sort: (sortConfig && sortConfig.field) ? sortConfig : defaultSort
            };
        }
        
        return defaultContext;
    }
    
    /**
     * CROWN⁴.9: Check if hydration is complete
     * Other modules should check this before triggering renders
     * @returns {boolean}
     */
    isHydrationReady() {
        return this._hydrationReady;
    }
    
    /**
     * CROWN⁴.10: Compute a fast hash of task list for change detection
     * Uses task IDs + updated_at timestamps for efficient comparison
     * @param {Array} tasks - Task array
     * @returns {string} Hash string for comparison
     */
    _computeRenderPayloadHash(tasks) {
        if (!tasks || tasks.length === 0) {
            return 'empty';
        }
        
        // Fast hash: concatenate id:updated_at for each task
        // This catches any task addition, removal, or modification
        const hashParts = tasks.map(t => {
            const id = t.id || 0;
            const updated = t.updated_at || t.created_at || '';
            const status = t.status || '';
            const pinned = t.is_pinned ? '1' : '0';
            return `${id}:${updated}:${status}:${pinned}`;
        });
        
        // Sort for deterministic hash (task order might vary)
        hashParts.sort();
        
        return hashParts.join('|');
    }
    
    /**
     * CROWN⁴.9: Mark hydration as complete and process deferred renders
     * Called after first successful render with actual task data
     */
    _markHydrationComplete() {
        if (this._hydrationReady) return; // Already done
        
        this._hydrationReady = true;
        window.taskHydrationReady = true;
        this._firstRenderComplete = true;
        this._hydrationCompleteTime = Date.now(); // CROWN⁴.11: Track for settling phase
        
        const hydrationTime = this._hydrationStartTime 
            ? Date.now() - this._hydrationStartTime 
            : 0;
        
        console.log(`✅ [TaskBootstrap] Hydration complete in ${hydrationTime}ms`);
        
        // CROWN⁴.12: Enable the render scheduler now that hydration is complete
        if (this.renderScheduler) {
            this.renderScheduler.enable();
            console.log('📋 [TaskBootstrap] RenderScheduler enabled after hydration');
        }
        
        // CROWN⁴.10: Add tasks-hydrated class to container to disable future animations
        // This prevents CSS animation replay during re-renders/reconciliation
        const container = document.getElementById('tasks-list-container');
        if (container) {
            container.classList.add('tasks-hydrated');
            console.log(`🎨 [TaskBootstrap] Added tasks-hydrated class - animations disabled for future renders`);
        }
        
        // Emit hydration complete event for other modules
        document.dispatchEvent(new CustomEvent('tasks:hydrated', {
            detail: { 
                timestamp: Date.now(),
                hydrationTime,
                taskCount: this._ssrCardCount
            }
        }));
        
        // Process any deferred renders (take only the last one - latest wins)
        if (this._deferredRenderQueue.length > 0) {
            const lastRender = this._deferredRenderQueue[this._deferredRenderQueue.length - 1];
            this._deferredRenderQueue = [];
            console.log(`📋 [TaskBootstrap] Processing deferred render (${lastRender.tasks?.length || 0} tasks)`);
            // Only process if it has actual tasks
            if (lastRender.tasks && lastRender.tasks.length > 0) {
                this._doRenderTasks(lastRender.tasks, lastRender.options);
            }
        }
    }

    /**
     * CROWN⁴.6: State transition guard
     * Prevents reverting from 'tasks' state to loading/empty/error
     * unless explicitly forced (e.g., for full refresh)
     * @param {string} targetState - State trying to transition to
     * @param {boolean} force - Force transition even from 'tasks' state
     * @returns {boolean} Whether transition is allowed
     */
    _canTransitionTo(targetState, force = false) {
        // Always allow forced transitions
        if (force) return true;
        
        // Once tasks are rendered, don't revert to overlay states
        // This prevents visual flicker during background sync/validation
        if (this.currentState === 'tasks' && ['loading', 'empty', 'error'].includes(targetState)) {
            console.log(`🛡️ [StateGuard] Blocked transition from 'tasks' to '${targetState}'`);
            return false;
        }
        
        return true;
    }

    /**
     * Show loading state with skeleton loaders
     * CROWN⁴.6: Guarded - won't revert from 'tasks' state
     * @param {boolean} force - Force show even if tasks already rendered
     */
    showLoadingState(force = false) {
        if (!this._canTransitionTo('loading', force)) return;
        
        console.log('📊 Showing loading state');
        this._hideOverlayStates();
        const loadingState = document.getElementById('tasks-loading-state');
        if (loadingState) {
            loadingState.style.display = 'flex';
            this.currentState = 'loading';
        }
    }

    /**
     * Show empty state when no tasks exist
     * CROWN⁴.6: Guarded - won't revert from 'tasks' state
     * @param {boolean} force - Force show even if tasks already rendered
     */
    showEmptyState(force = false) {
        if (!this._canTransitionTo('empty', force)) return;
        
        console.log('📭 Showing empty state');
        this._hideOverlayStates();
        // Also hide task list for empty state
        const tasksContainer = document.getElementById('tasks-list-container');
        if (tasksContainer) tasksContainer.style.display = 'none';
        
        const emptyState = document.getElementById('tasks-empty-state');
        if (emptyState) {
            emptyState.style.display = 'block';
            this.currentState = 'empty';
        }
    }

    /**
     * Show error state with retry option
     * CROWN⁴.6: Guarded - won't revert from 'tasks' state
     * @param {string} errorMessage - Optional custom error message
     * @param {boolean} force - Force show even if tasks already rendered
     */
    showErrorState(errorMessage, force = false) {
        if (!this._canTransitionTo('error', force)) return;
        
        console.log('❌ Showing error state:', errorMessage);
        this._hideOverlayStates();
        // Also hide task list for error state
        const tasksContainer = document.getElementById('tasks-list-container');
        if (tasksContainer) tasksContainer.style.display = 'none';
        
        const errorState = document.getElementById('tasks-error-state');
        if (errorState) {
            if (errorMessage) {
                const messageEl = errorState.querySelector('.error-state-message');
                if (messageEl) {
                    messageEl.textContent = errorMessage;
                }
            }
            errorState.style.display = 'block';
            this.currentState = 'error';
        }
    }

    /**
     * Show tasks list (hide all state overlays)
     * CROWN⁴.7: Optimized for SSR - no-op if already visible
     */
    showTasksList() {
        const tasksContainer = document.getElementById('tasks-list-container');
        
        // CROWN⁴.7: Skip if already visible (SSR scenario) for performance
        if (tasksContainer && tasksContainer.style.display === 'flex') {
            this.currentState = 'tasks';
            return; // Already visible, no action needed
        }
        
        console.log('✅ Showing tasks list');
        this._hideOverlayStates();
        if (tasksContainer) {
            tasksContainer.style.display = 'flex';
            this.currentState = 'tasks';
        }
    }

    /**
     * CROWN⁴.6: Hide only overlay states (loading/empty/error)
     * Never hides task list - that's handled explicitly in showEmptyState/showErrorState
     */
    _hideOverlayStates() {
        const overlayStates = [
            'tasks-loading-state',
            'tasks-empty-state',
            'tasks-error-state'
        ];
        
        overlayStates.forEach(stateId => {
            const el = document.getElementById(stateId);
            if (el) {
                el.style.display = 'none';
            }
        });
    }

    /**
     * Hide all state containers (including tasks list)
     * CROWN⁴.6: Use _hideOverlayStates() for normal transitions
     * This method now only used for forced full resets
     */
    hideAllStates() {
        this._hideOverlayStates();
        const tasksContainer = document.getElementById('tasks-list-container');
        if (tasksContainer) {
            tasksContainer.style.display = 'none';
        }
    }

    /**
     * Bootstrap tasks page with cache-first loading
     * Target: <200ms first paint
     * CROWN⁴.9: Implements hydration gate pattern for flicker-free initialization
     * @returns {Promise<Object>} Bootstrap results
     */
    async bootstrap() {
        console.log('🚀 Starting CROWN⁴.9 cache-first bootstrap with hydration gate...');
        this.perf.cache_load_start = performance.now();
        
        // CROWN⁴.9: Start hydration timing
        this._hydrationStartTime = Date.now();

        // CROWN⁴.8 FIX: Check if server already rendered tasks BEFORE any DOM manipulation
        // This prevents the flicker caused by cache clearing server content
        const container = document.getElementById('tasks-list-container');
        const serverRenderedTasks = container?.querySelectorAll('.task-card') || [];
        const hasServerContent = serverRenderedTasks.length > 0;
        
        // CROWN⁴.9: Capture SSR card count for hydration gate
        this._ssrCardCount = serverRenderedTasks.length;
        console.log(`📊 [HydrationGate] SSR card count captured: ${this._ssrCardCount}`);
        
        if (hasServerContent) {
            console.log(`✅ [Bootstrap] Server rendered ${serverRenderedTasks.length} tasks - skipping cache DOM swap`);
            this.currentState = 'tasks';
            this.showTasksList();
            
            // Hydrate TaskStateStore from server DOM without re-rendering
            const serverTasks = Array.from(serverRenderedTasks).map(card => ({
                id: card.dataset.taskId,
                status: card.dataset.status || 'todo',
                priority: card.dataset.priority || 'medium',
                updated_at: card.dataset.updatedAt || '',
                is_pinned: card.dataset.isPinned === 'true'
            }));
            
            if (window.taskStateStore) {
                window.taskStateStore.hydrate(serverTasks, 'server');
            }
            
            // CROWN⁴.10: Initialize payload hash from SSR content
            // This ensures subsequent identical payloads are skipped
            this._lastRenderPayloadHash = this._computeRenderPayloadHash(serverTasks);
            console.log(`📊 [Bootstrap] SSR payload hash initialized: ${this._lastRenderPayloadHash.substring(0, 50)}...`);
            
            // CROWN⁴.9: Mark hydration as complete IMMEDIATELY for SSR content
            // Server-rendered content is already the "hydrated" state
            this._markHydrationComplete();
            
            // Background: sync cache to IndexedDB without touching DOM
            this.syncInBackground();
            this.initialized = true;
            
            // Emit bootstrap complete with server source
            // CROWN⁴.7 PERFORMANCE FIX: For SSR, use browser's actual FCP (paint happened before JS)
            // Don't use JS timing as it misrepresents when content became visible
            requestAnimationFrame(() => {
                // Try to get actual browser FCP
                let browserFCP = null;
                if (window.performance && window.performance.getEntriesByName) {
                    const fcpEntries = window.performance.getEntriesByName('first-contentful-paint', 'paint');
                    if (fcpEntries.length > 0) {
                        browserFCP = fcpEntries[0].startTime;
                    }
                }
                // Fallback to inline marker if available
                if (browserFCP === null && window.__FIRST_PAINT_TIME !== undefined) {
                    browserFCP = window.__FIRST_PAINT_TIME;
                }
                
                document.dispatchEvent(new CustomEvent('task:bootstrap:complete', {
                    detail: {
                        cached_tasks: serverRenderedTasks.length,
                        first_paint_ms: browserFCP !== null ? browserFCP : 0, // Use browser FCP for SSR
                        source: 'server',
                        hydrationReady: true,
                        ssr: true // Flag for SSR scenario
                    }
                }));
                console.log(`📊 [Bootstrap] SSR first paint: ${browserFCP !== null ? browserFCP.toFixed(2) + 'ms (browser FCP)' : 'instant (SSR)'}`);
            });
            
            return { success: true, source: 'server', task_count: serverRenderedTasks.length };
        }

        // No server content - proceed with cache-first loading
        this.currentState = 'loading';

        try {
            // Step 1: Load from cache immediately (target: <50ms)
            const cachedTasks = await this.loadFromCache();
            this.perf.cache_load_end = performance.now();
            
            const cacheLoadTime = this.perf.cache_load_end - this.perf.cache_load_start;
            console.log(`📦 Cache loaded in ${cacheLoadTime.toFixed(2)}ms (${cachedTasks.length} tasks)`);

            // Step 2: CROWN⁴.5 - Validate cache checksum
            const checksumValid = await this.validateCacheChecksum(cachedTasks);
            if (!checksumValid) {
                console.warn('⚠️ Cache checksum validation failed - triggering reconciliation');
                // Continue with cached data but mark for reconciliation
                this.needsReconciliation = true;
            }

            // Step 3: Render UI immediately (target: <200ms total)
            const cacheContext = this._getCurrentViewContext();
            await this.renderTasks(cachedTasks, { 
                fromCache: true, 
                source: 'cache',
                filterContext: cacheContext.filter,
                searchQuery: cacheContext.search,
                sortConfig: cacheContext.sort
            });
            this.perf.first_paint = performance.now();
            
            const firstPaintTime = this.perf.first_paint - this.perf.cache_load_start;
            console.log(`🎨 First paint in ${firstPaintTime.toFixed(2)}ms`);

            // Emit performance metric
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('first_paint_ms', firstPaintTime);
                window.CROWNTelemetry.recordMetric('cache_load_ms', cacheLoadTime);
                window.CROWNTelemetry.recordMetric('checksum_valid', checksumValid ? 1 : 0);
            }

            // CRITICAL FIX: Clear stale pendingOperations from memory BEFORE rehydration
            // This ensures zombie operations don't persist in the UI
            if (window.optimisticUI) {
                const staleOpIds = await this._getStaleOperationIds();
                if (staleOpIds.length > 0) {
                    console.log(`🧹 [Bootstrap] Clearing ${staleOpIds.length} stale operations from memory`);
                    staleOpIds.forEach(opId => {
                        window.optimisticUI.pendingOperations.delete(opId);
                    });
                }
            }

            // Step 4: Start background sync (with reconciliation if needed)
            this.syncInBackground();

            this.initialized = true;

            // CROWN⁴.6: Emit bootstrap complete event AFTER paint
            // Use double-rAF to ensure browser has actually painted the DOM
            // This gives telemetry subscribers time to attach and captures true visual completion
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    const actualFirstPaint = performance.now() - this.perf.cache_load_start;
                    document.dispatchEvent(new CustomEvent('task:bootstrap:complete', {
                        detail: {
                            cached_tasks: cachedTasks.length,
                            first_paint_ms: actualFirstPaint,
                            cache_load_ms: cacheLoadTime,
                            meets_target: actualFirstPaint < 200,
                            source: 'cache'
                        }
                    }));
                    console.log(`📊 [Bootstrap] Emitted first paint event: ${actualFirstPaint.toFixed(2)}ms (after paint)`);
                });
            });

            return {
                success: true,
                cached_tasks: cachedTasks.length,
                cache_load_ms: cacheLoadTime,
                first_paint_ms: firstPaintTime,
                checksum_valid: checksumValid,
                meets_target: firstPaintTime < 200
            };
        } catch (error) {
            console.error('❌ Bootstrap failed:', error);
            console.error('❌ Error details:', error.message, error.stack);
            
            // Fallback: Load from server directly
            return this.fallbackToServer();
        }
    }

    /**
     * CROWN⁴.5: Validate cache checksum against server
     * @param {Array} cachedTasks - Cached tasks
     * @returns {Promise<boolean>} Whether checksum is valid
     */
    async validateCacheChecksum(cachedTasks) {
        try {
            // Get stored checksum from metadata
            const storedChecksum = await this.cache.getMetadata('last_checksum');
            if (!storedChecksum) {
                console.log('📊 No stored checksum found - first load');
                return true; // First load, no checksum to validate
            }

            // Compute current checksum of cached data (AWAIT the Promise!)
            const currentChecksum = await this.computeChecksum(cachedTasks);

            // Compare checksums
            const isValid = storedChecksum === currentChecksum;
            
            if (isValid) {
                console.log('✅ Cache checksum valid:', currentChecksum.substring(0, 8));
            } else {
                console.warn('❌ Cache checksum mismatch!');
                console.warn('  Expected:', storedChecksum.substring(0, 8));
                console.warn('  Got:', currentChecksum.substring(0, 8));
            }

            return isValid;
        } catch (error) {
            console.error('❌ Checksum validation failed:', error);
            return false; // Assume invalid on error, trigger reconciliation
        }
    }

    /**
     * Deterministic JSON serialization with deep key sorting
     * Matches Python's json.dumps(sort_keys=True) behavior EXACTLY (including spacing)
     * @param {any} obj - Object to serialize
     * @returns {string} JSON string with sorted keys at all levels
     */
    deterministicStringify(obj) {
        if (obj === null || obj === undefined) {
            return JSON.stringify(obj);
        }
        
        if (typeof obj !== 'object') {
            return JSON.stringify(obj);
        }
        
        if (Array.isArray(obj)) {
            // Arrays: serialize each element deterministically
            // Python uses ', ' separator (comma + space)
            return '[' + obj.map(item => this.deterministicStringify(item)).join(', ') + ']';
        }
        
        // Objects: sort keys and serialize recursively
        const sortedKeys = Object.keys(obj).sort();
        const pairs = sortedKeys.map(key => {
            const value = obj[key];
            const serializedKey = JSON.stringify(key);
            const serializedValue = this.deterministicStringify(value);
            // Python uses ': ' separator (colon + space)
            return `${serializedKey}: ${serializedValue}`;
        });
        
        // Python uses ', ' separator (comma + space)
        return '{' + pairs.join(', ') + '}';
    }

    /**
     * Compute SHA-256 checksum of task data (matches backend cache_validator exactly)
     * Algorithm: Sort tasks → SHA-256 each task → concatenate → SHA-256 aggregate
     * @param {Array} tasks - Task list
     * @returns {Promise<string>} SHA-256 checksum (hex string)
     */
    async computeChecksum(tasks) {
        try {
            // Step 1: Sort tasks by ID for deterministic checksum (matches backend)
            const sorted = [...tasks].sort((a, b) => {
                const aId = parseInt(a.id, 10) || 0;
                const bId = parseInt(b.id, 10) || 0;
                return aId - bId;
            });

            // Step 2: Generate individual checksums for each task (matches backend generate_checksum)
            const individualChecksums = [];
            const encoder = new TextEncoder();
            
            for (const task of sorted) {
                // Remove excluded fields (matches backend exclude_fields)
                const cleanTask = {...task};
                delete cleanTask.checksum;
                delete cleanTask.last_validated;
                delete cleanTask._cached_at;
                
                // JSON serialize with sorted keys (matches backend json.dumps(sort_keys=True))
                const taskJson = this.deterministicStringify(cleanTask);
                
                // SHA-256 hash
                const taskData = encoder.encode(taskJson);
                const taskHashBuffer = await crypto.subtle.digest('SHA-256', taskData);
                const taskHashArray = Array.from(new Uint8Array(taskHashBuffer));
                const taskHashHex = taskHashArray.map(b => b.toString(16).padStart(2, '0')).join('');
                
                individualChecksums.push(taskHashHex);
            }
            
            // Step 3: Concatenate individual checksums (matches backend ''.join(item_checksums))
            const aggregateData = individualChecksums.join('');
            
            // Step 4: Compute final aggregate checksum (matches backend hashlib.sha256(aggregate_data.encode))
            const finalData = encoder.encode(aggregateData);
            const finalHashBuffer = await crypto.subtle.digest('SHA-256', finalData);
            const finalHashArray = Array.from(new Uint8Array(finalHashBuffer));
            const finalHashHex = finalHashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            
            return finalHashHex;
        } catch (error) {
            console.error('❌ Checksum computation failed:', error);
            // Fallback to empty checksum if crypto.subtle not available
            return '0000000000000000000000000000000000000000000000000000000000000000';
        }
    }

    /**
     * Load tasks from IndexedDB cache
     * ENTERPRISE-GRADE: Cleans corrupted temp IDs before loading
     * @returns {Promise<Array>} Cached tasks
     */
    async loadFromCache() {
        await this.cache.init();

        // ENTERPRISE-GRADE: Clean only orphaned temp tasks (preserves legitimate offline tasks)
        try {
            const removedCount = await this.cache.cleanOrphanedTempTasks();
            if (removedCount > 0) {
                console.log(`🧹 Cache hygiene: Removed ${removedCount} orphaned temp tasks`);
            }
        } catch (cleanupError) {
            console.warn('⚠️ Cache cleanup failed (non-fatal):', cleanupError);
        }

        // Load view state (filters, sort, scroll position)
        const viewState = await this.cache.getViewState('tasks_page') || {
            filter: 'all',
            sort: { field: 'created_at', direction: 'desc' },
            scroll_position: 0
        };

        // Load tasks with filters
        const filters = this.buildFiltersFromViewState(viewState);
        const tasks = await this.cache.getFilteredTasks(filters);

        // PREVENTION LAYER: Filter out deleted tasks from cache before rendering
        // This prevents stale deleted tasks from showing on page refresh
        const activeTasks = tasks.filter(task => !task.deleted_at);
        
        if (tasks.length !== activeTasks.length) {
            console.log(`🗑️ Filtered out ${tasks.length - activeTasks.length} deleted tasks from cache`);
        }

        // Apply sort
        const sortedTasks = this.sortTasks(activeTasks, viewState.sort);

        return sortedTasks;
    }

    /**
     * Build filter object from view state
     * @param {Object} viewState
     * @returns {Object} Filters
     */
    buildFiltersFromViewState(viewState) {
        const filters = {};

        if (viewState.status && viewState.status !== 'all') {
            filters.status = viewState.status;
        }

        if (viewState.priority && viewState.priority !== 'all') {
            filters.priority = viewState.priority;
        }

        if (viewState.search) {
            filters.search = viewState.search;
        }

        if (viewState.labels && viewState.labels.length > 0) {
            filters.labels = viewState.labels;
        }

        if (viewState.due_date) {
            filters.due_date = viewState.due_date;
        }

        // Hide snoozed by default
        filters.show_snoozed = viewState.show_snoozed !== false;

        return filters;
    }

    /**
     * Sort tasks by field and direction
     * @param {Array} tasks
     * @param {Object} sort - { field, direction }
     * @returns {Array} Sorted tasks
     */
    sortTasks(tasks, sort = { field: 'created_at', direction: 'desc' }) {
        const { field, direction } = sort;
        const multiplier = direction === 'asc' ? 1 : -1;

        return tasks.sort((a, b) => {
            let aVal = a[field];
            let bVal = b[field];

            // Handle dates
            if (field === 'created_at' || field === 'updated_at' || field === 'due_date') {
                aVal = aVal ? new Date(aVal).getTime() : 0;
                bVal = bVal ? new Date(bVal).getTime() : 0;
            }

            // Handle nulls
            if (aVal === null || aVal === undefined) return 1;
            if (bVal === null || bVal === undefined) return -1;

            if (aVal < bVal) return -1 * multiplier;
            if (aVal > bVal) return 1 * multiplier;
            return 0;
        });
    }

    /**
     * Render tasks to DOM
     * CROWN⁴.12: Routes through priority-based RenderScheduler
     * CROWN⁴.9: Hydration gate protects against flicker during initialization
     * @param {Array} tasks
     * @param {Object} options - { fromCache, source, isFilterChange, isUserAction }
     * @returns {Promise<void>}
     */
    async renderTasks(tasks, options = {}) {
        const taskCount = tasks?.length || 0;
        const container = document.getElementById('tasks-list-container');
        const existingCards = container?.querySelectorAll('.task-card')?.length || 0;
        
        // Determine source and priority flags
        const source = options.source || (options.fromCache ? 'cache' : 'api');
        const isUserAction = options.isFilterChange || options.isUserAction || false;
        
        console.log(`🔧 [TaskBootstrap] renderTasks() called with ${taskCount} tasks (source: ${source}, SSR: ${existingCards}, hydrationReady: ${this._hydrationReady})`);
        
        // CROWN⁴.9 HYDRATION GATE: Before hydration, handle specially
        if (!this._hydrationReady) {
            // Empty render with SSR content = DEFER
            if (taskCount === 0 && existingCards > 0) {
                console.log(`🚫 [HydrationGate] BLOCKED empty render - SSR has ${existingCards} cards`);
                this._deferredRenderQueue.push({ tasks, options });
                return;
            }
            
            // Non-empty render = This IS the hydration, execute directly
            if (taskCount > 0) {
                console.log(`✅ [HydrationGate] Allowing render with ${taskCount} tasks - completing hydration`);
                await this._executeRender(tasks, { ...options, source, isSchedulerApproved: true });
                return;
            }
        }
        
        // CROWN⁴.12: Route through scheduler if available
        if (this.renderScheduler) {
            // Get current context from scheduler or infer from options
            const currentContext = this.renderScheduler.getContext();
            
            this._renderRequestSeq++;
            this.renderScheduler.enqueueRender({
                tasks,
                source,
                filterContext: options.filterContext || currentContext.filter,
                searchQuery: options.searchQuery || currentContext.search,
                sortConfig: options.sortConfig || currentContext.sort,
                version: this._renderRequestSeq,
                fromCache: options.fromCache || false,
                isUserAction
            });
            return;
        }
        
        // Fallback: direct render if no scheduler
        await this._executeRender(tasks, options);
    }
    
    /**
     * CROWN⁴.12: Execute render (called by scheduler or directly during hydration)
     * @param {Array} tasks
     * @param {Object} options
     */
    async _executeRender(tasks, options = {}) {
        const taskCount = tasks?.length || 0;
        const now = Date.now();
        
        // Skip if scheduler didn't approve (safety check)
        if (this._hydrationReady && this.renderScheduler && !options.isSchedulerApproved) {
            console.log(`⚠️ [TaskBootstrap] Render bypassed scheduler - blocking`);
            return;
        }
        
        // CROWN⁴.10: Skip if payload unchanged
        const payloadHash = this._computeRenderPayloadHash(tasks);
        if (this._hydrationReady && payloadHash === this._lastRenderPayloadHash) {
            this._renderHashSkipCount++;
            console.log(`🔄 [TaskBootstrap] SKIP redundant render #${this._renderHashSkipCount} - payload unchanged (${taskCount} tasks)`);
            return;
        }
        
        // Prevent concurrent renders
        if (this._renderInProgress) {
            console.log(`🔒 [TaskBootstrap] Render in progress, queueing`);
            this._pendingRenderArgs = { tasks, options };
            return;
        }
        
        this._renderInProgress = true;
        this._lastRenderTime = now;
        
        try {
            await this._doRenderTasks(tasks, options);
            this._lastRenderPayloadHash = payloadHash;
            
            // Mark hydration complete after first successful render with tasks
            if (!this._hydrationReady && taskCount > 0) {
                this._markHydrationComplete();
            }
        } finally {
            this._renderInProgress = false;
            
            // Process pending render if any (only after hydration)
            if (this._pendingRenderArgs && this._hydrationReady) {
                const pending = this._pendingRenderArgs;
                this._pendingRenderArgs = null;
                console.log(`📋 [TaskBootstrap] Processing pending render (${pending.tasks?.length || 0} tasks)`);
                setTimeout(() => this.renderTasks(pending.tasks, pending.options), 10);
            }
        }
    }
    
    /**
     * Internal render implementation
     * @private
     */
    async _doRenderTasks(tasks, options = {}) {
        const container = document.getElementById('tasks-list-container');
        
        if (!container) {
            console.warn('⚠️ Tasks container not found, skipping render');
            return;
        }
        
        // CROWN⁴.13 FIX: Apply Active filter BEFORE rendering to prevent flicker
        // This ensures completed/cancelled tasks never appear in Active tab during hydration
        let filteredTasks = tasks;
        const currentFilter = options.filterContext || 
                             window.taskSearchSort?.currentFilter || 
                             'active'; // Default to 'active' filter
        
        if (currentFilter === 'active' && tasks && tasks.length > 0) {
            const beforeCount = tasks.length;
            filteredTasks = tasks.filter(task => {
                const status = task.status || 'todo';
                return status !== 'completed' && status !== 'cancelled';
            });
            const afterCount = filteredTasks.length;
            if (beforeCount !== afterCount) {
                console.log(`🔧 [TaskBootstrap] Pre-filtered ${beforeCount - afterCount} archived tasks for Active view`);
            }
        } else if (currentFilter === 'archived' && tasks && tasks.length > 0) {
            filteredTasks = tasks.filter(task => {
                const status = task.status || 'todo';
                return status === 'completed' || status === 'cancelled';
            });
        } else if (currentFilter === 'all' && tasks && tasks.length > 0) {
            // CROWN⁴.14: Sort completed tasks to bottom in 'all' view
            // This improves visual hierarchy - active tasks first
            filteredTasks = [...tasks].sort((a, b) => {
                const aCompleted = a.status === 'completed' || a.status === 'cancelled';
                const bCompleted = b.status === 'completed' || b.status === 'cancelled';
                if (aCompleted && !bCompleted) return 1;
                if (!aCompleted && bCompleted) return -1;
                return 0; // Preserve existing order within groups
            });
            console.log(`🔧 [TaskBootstrap] Sorted completed tasks to bottom in All view`);
        }
        tasks = filteredTasks;
        
        // CROWN⁴.9 FIX: Check existing content FIRST before any processing
        const existingCards = container.querySelectorAll('.task-card').length;

        // CROWN⁴.5: Determine state based on task count
        if (!tasks || tasks.length === 0) {
            console.log(`🔧 [TaskBootstrap] No tasks to render (existing cards: ${existingCards})`);
            
            // CROWN⁴.9 FIX: Never replace existing content with empty state
            // This prevents flicker when cache returns empty during bootstrap
            if (existingCards > 0) {
                console.warn(`⚠️ [TaskBootstrap] Skipping empty render - ${existingCards} cards already exist`);
                return;
            }
            
            // Only show empty state if truly no content exists
            this.showEmptyState();
            container.innerHTML = '';
            return;
        }
        
        // CROWN⁴.6: Hydrate TaskStateStore FIRST - single source of truth
        if (tasks && Array.isArray(tasks) && tasks.length > 0 && window.taskStateStore) {
            const source = options.fromCache ? 'cache' : 'server';
            window.taskStateStore.hydrate(tasks, source);
            console.log(`[TaskBootstrap] Hydrated TaskStateStore from ${source}`);
        }

        // Log sample task to verify data structure
        if (tasks.length > 0) {
            const sample = tasks[0];
            console.log('🔧 [TaskBootstrap] Sample task from renderTasks:', {
                id: sample.id,
                title: sample.title?.substring(0, 30),
                is_pinned: sample.is_pinned,
                updated_at: sample.updated_at,
                due_date: sample.due_date,
                meeting_id: sample.meeting_id
            });
        }

        // Render tasks with error protection
        try {
            // CROWN⁴.6: Use TaskGrouping for medium lists (12-50 tasks)
            // Virtual list will handle >50 without grouping for performance
            console.log('🔧 [TaskBootstrap] Checking grouping conditions:', {
                'window.TaskGrouping exists': typeof window.TaskGrouping !== 'undefined',
                'task count': tasks.length,
                'groupingThreshold': this.groupingThreshold,
                'meets threshold': tasks.length >= this.groupingThreshold,
                'below 50': tasks.length <= 50
            });
            
            const useGrouping = window.TaskGrouping && 
                               tasks.length >= this.groupingThreshold && 
                               tasks.length <= 50;
            
            console.log(`🔧 [TaskBootstrap] useGrouping decision: ${useGrouping}`);
            
            if (useGrouping) {
                console.log('🔧 [TaskBootstrap] Using TaskGrouping for render');
                
                // Initialize singleton TaskGrouping instance
                if (!this.taskGrouping) {
                    try {
                        this.taskGrouping = new window.TaskGrouping(window.taskStore);
                        console.log('✅ [TaskBootstrap] TaskGrouping singleton created successfully');
                    } catch (error) {
                        console.error('❌ [TaskBootstrap] Failed to create TaskGrouping instance:', error);
                        throw error;
                    }
                }
                
                // Track task indices for proper animation
                let globalIndex = 0;
                
                // Create task renderer that preserves index and returns DOM
                const taskRenderer = (task) => {
                    const wrapper = document.createElement('div');
                    wrapper.innerHTML = this.renderTaskCard(task, globalIndex++);
                    return wrapper.firstElementChild;
                };
                
                // Render grouped sections
                console.log('🔧 [TaskBootstrap] Calling taskGrouping.render()...');
                const groupedContainer = this.taskGrouping.render(tasks, taskRenderer);
                container.innerHTML = '';
                container.appendChild(groupedContainer);
                
                console.log(`✅ [TaskBootstrap] Rendered ${tasks.length} tasks with grouping`);
            } else {
                console.log('🔧 [TaskBootstrap] Using flat list render (no grouping)');
                // Fallback to flat list for small counts or very large (virtualized) lists
                
                // CROWN⁴.14: Add divider before completed tasks in 'all' view
                const currentViewFilter = options.filterContext || 
                                         window.taskSearchSort?.currentFilter || 
                                         'active';
                
                if (currentViewFilter === 'all') {
                    // Find first completed task index
                    const firstCompletedIndex = tasks.findIndex(t => 
                        t.status === 'completed' || t.status === 'cancelled'
                    );
                    
                    if (firstCompletedIndex > 0) {
                        // Split into active and completed sections
                        const activeTasks = tasks.slice(0, firstCompletedIndex);
                        const completedTasks = tasks.slice(firstCompletedIndex);
                        
                        const activeHTML = activeTasks.map((task, index) => 
                            this.renderTaskCard(task, index)
                        ).join('');
                        
                        const dividerHTML = `
                            <div class="completed-section-divider" role="separator" aria-label="Completed tasks section">
                                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                                </svg>
                                <span>Completed (${completedTasks.length})</span>
                            </div>
                        `;
                        
                        const completedHTML = completedTasks.map((task, index) => 
                            this.renderTaskCard(task, firstCompletedIndex + index)
                        ).join('');
                        
                        container.innerHTML = activeHTML + dividerHTML + completedHTML;
                        console.log(`✅ [TaskBootstrap] Rendered ${activeTasks.length} active + ${completedTasks.length} completed with divider`);
                    } else {
                        // All tasks are same type (all active or all completed)
                        const tasksHTML = tasks.map((task, index) => this.renderTaskCard(task, index)).join('');
                        container.innerHTML = tasksHTML;
                        console.log(`✅ [TaskBootstrap] Rendered ${tasks.length} tasks as flat list (no divider needed)`);
                    }
                } else {
                    const tasksHTML = tasks.map((task, index) => this.renderTaskCard(task, index)).join('');
                    container.innerHTML = tasksHTML;
                    console.log(`✅ [TaskBootstrap] Rendered ${tasks.length} tasks as flat list`);
                }
            }
            
            // Show tasks list (hides all state overlays)
            this.showTasksList();
        } catch (renderError) {
            console.error('❌ renderTaskCard failed:', renderError);
            // Keep existing content on render error
            throw renderError;
        }

        // Add stagger animation
        const cards = container.querySelectorAll('.task-card');
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.05}s`;
        });

        // Attach event listeners (checkbox toggle, etc.)
        this._attachEventListeners();

        // CROWN⁴.6 FIX: Always update counters after render to match visible DOM
        // Use sync DOM-based counting to avoid race conditions
        // This ensures counters match what user sees regardless of cache/server source
        this._updateCountersFromDOM();

        // Show cache indicator if from cache
        if (options.fromCache) {
            this.showCacheIndicator();
        }

        // Restore scroll position
        const viewState = await this.cache.getViewState('tasks_page');
        if (viewState && viewState.scroll_position) {
            window.scrollTo(0, viewState.scroll_position);
        }
    }

    /**
     * CROWN⁴.18: Render single task card using shared TaskCardRenderer
     * Ensures visual consistency between SSR and client-side rendering
     * @param {Object} task
     * @param {number} index
     * @returns {string} HTML
     */
    renderTaskCard(task, index) {
        // Use shared TaskCardRenderer for SSR-matching output
        if (window.taskCardRenderer) {
            return window.taskCardRenderer.render(task, {
                isVirtual: false,
                virtualIndex: index
            });
        }
        
        // Fallback: minimal render if shared renderer not loaded
        console.warn('⚠️ TaskCardRenderer not available, using fallback');
        const priority = task.priority || 'medium';
        const status = task.status || 'todo';
        const isCompleted = status === 'completed';
        const priorityText = priority.charAt(0).toUpperCase() + priority.slice(1);
        
        return `
            <div class="task-card${isCompleted ? ' completed' : ''}" 
                 data-task-id="${task.id}"
                 data-status="${status}"
                 data-priority="${priority}"
                 data-updated-at="${task.updated_at || ''}"
                 data-is-pinned="${task.is_pinned ? 'true' : 'false'}"
                 role="article"
                 tabindex="0"
                 aria-expanded="false">
                <div class="checkbox-wrapper">
                    <input type="checkbox" 
                           ${isCompleted ? 'checked' : ''} 
                           class="task-checkbox" 
                           data-task-id="${task.id}"
                           aria-label="Mark task as ${isCompleted ? 'incomplete' : 'complete'}">
                </div>
                <div class="task-content">
                    <div class="task-primary-row task-tier-1">
                        <h3 class="task-title" data-field="title">${this.escapeHtml(task.title || 'Untitled Task')}</h3>
                        <div class="task-essential-meta">
                            <span class="priority-dot priority-${priority.toLowerCase()}" 
                                  data-field="priority"
                                  role="img"
                                  aria-label="Priority: ${priorityText}"
                                  title="Priority: ${priorityText}">
                                <span class="sr-only">${priorityText} priority</span>
                            </span>
                        </div>
                    </div>
                </div>
                <div class="task-actions" role="group" aria-label="Task actions">
                    <button class="task-menu-trigger" 
                            data-task-id="${task.id}"
                            type="button"
                            aria-haspopup="menu"
                            aria-expanded="false"
                            title="More actions">
                        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <circle cx="12" cy="5" r="2"/>
                            <circle cx="12" cy="12" r="2"/>
                            <circle cx="12" cy="19" r="2"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Attach event listeners to task cards
     * Handles checkbox toggle, card clicks, and other interactions
     */
    _attachEventListeners() {
        const container = document.getElementById('tasks-list-container');
        if (!container) {
            console.warn('[TaskBootstrap] tasks-list-container not found, cannot attach event listeners');
            return;
        }

        // Checkbox toggle (with optimistic UI)
        const checkboxes = container.querySelectorAll('.task-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', async (e) => {
                const taskId = e.target.dataset.taskId;
                
                // Call optimistic UI handler
                if (window.optimisticUI) {
                    try {
                        await window.optimisticUI.toggleTaskStatus(taskId);
                        
                        // Track telemetry
                        if (window.CROWNTelemetry) {
                            window.CROWNTelemetry.recordMetric('task_status_toggle', 1, {
                                task_id: taskId,
                                new_status: e.target.checked ? 'completed' : 'todo'
                            });
                        }
                    } catch (error) {
                        console.error('❌ Failed to toggle task status:', error);
                        
                        // Rollback checkbox state on error
                        e.target.checked = !e.target.checked;
                    }
                }
            });
        });

        // Task card clicks (for detail view - future implementation)
        const cards = container.querySelectorAll('.task-card');
        cards.forEach(card => {
            card.addEventListener('click', (e) => {
                // Ignore clicks on interactive elements
                if (e.target.classList.contains('task-checkbox')) return;
                if (e.target.classList.contains('task-title')) return;
                if (e.target.closest('.task-actions')) return;
                if (e.target.closest('.task-menu-trigger')) return;
                if (e.target.closest('.task-metadata')) return;
                
                const taskId = card.dataset.taskId;
                
                // Dispatch custom event for task detail view (future)
                window.dispatchEvent(new CustomEvent('task:clicked', {
                    detail: { task_id: taskId }
                }));
            });
        });

        console.log(`[TaskBootstrap] Attached event listeners to ${checkboxes.length} checkboxes and ${cards.length} cards`);
    }

    /**
     * Update task counters in UI
     * CROWN⁴.6: Delegates to TaskStateStore for single source of truth
     * Kept for backward compatibility with external callers
     * @param {Array} tasks - Optional, will hydrate TaskStateStore if provided
     */
    async updateCounters(tasks) {
        // CROWN⁴.6: If tasks provided, hydrate the store first
        if (tasks && Array.isArray(tasks) && tasks.length > 0) {
            if (window.taskStateStore) {
                window.taskStateStore.hydrate(tasks, 'updateCounters');
            }
        }
        
        // Delegate to single source of truth
        console.log('[TaskBootstrap] updateCounters() delegating to TaskStateStore');
        this._updateCountersFromDOM();
    }

    /**
     * CROWN⁴.6: Counter update - delegates to TaskStateStore
     * TaskStateStore is the ONLY source of truth for counter values
     * This method triggers a refresh from the store
     */
    _updateCountersFromDOM() {
        // PRIMARY: Use TaskStateStore if available (single source of truth)
        if (window.taskStateStore && window.taskStateStore._initialized) {
            window.taskStateStore.forceRefresh();
            return;
        }
        
        // FALLBACK: Build store from DOM if TaskStateStore not ready
        // This only happens during initial page load before hydration
        console.log('[TaskBootstrap] TaskStateStore not ready, building from DOM...');
        
        const cards = document.querySelectorAll('.task-card');
        const tasks = [];
        
        cards.forEach(card => {
            const taskId = card.dataset?.taskId;
            if (!taskId) return;
            
            // Skip temp tasks
            if (taskId.startsWith('temp_') || taskId.includes('_temp_')) return;
            
            // Skip deleted tasks
            if (card.classList.contains('deleting') || card.dataset?.deleted === 'true') return;
            
            tasks.push({
                id: taskId,
                status: card.dataset?.status || 'todo',
                workspace_id: window.WORKSPACE_ID
            });
        });
        
        // Hydrate store with DOM-derived tasks
        if (window.taskStateStore) {
            window.taskStateStore.hydrate(tasks, 'dom-fallback');
        } else {
            // Ultra-fallback: direct badge update (should rarely happen)
            this._directBadgeUpdate(tasks);
        }
    }
    
    /**
     * Ultra-fallback direct badge update when TaskStateStore unavailable
     * @param {Array} tasks
     */
    _directBadgeUpdate(tasks) {
        const counters = { all: 0, active: 0, archived: 0 };
        
        tasks.forEach(task => {
            counters.all++;
            const status = (task.status || 'todo').toLowerCase();
            if (status === 'completed' || status === 'cancelled') {
                counters.archived++;
            } else {
                counters.active++;
            }
        });
        
        console.log('[TaskBootstrap] Direct badge update (fallback):', counters);
        
        Object.entries(counters).forEach(([key, count]) => {
            const badge = document.querySelector(`[data-counter="${key}"]`);
            if (badge) badge.textContent = count;
        });
    }

    /**
     * Show cache indicator (subtle notification)
     */
    showCacheIndicator() {
        const indicator = document.getElementById('cache-indicator');
        if (indicator) {
            indicator.style.display = 'block';
            indicator.classList.add('fade-in');
            
            setTimeout(() => {
                indicator.classList.remove('fade-in');
                indicator.classList.add('fade-out');
                setTimeout(() => {
                    indicator.style.display = 'none';
                }, 300);
            }, 2000);
        }
    }

    /**
     * Sync with server in background
     * @returns {Promise<void>}
     */
    async syncInBackground() {
        if (this.syncInProgress) {
            console.log('⏳ Sync already in progress, skipping');
            return;
        }

        this.syncInProgress = true;
        this.perf.sync_start = performance.now();
        console.log('🔄 Starting background sync...');

        try {
            // Fetch tasks from server
            const response = await fetch('/api/tasks/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }

            const data = await response.json();
            let serverTasks = data.tasks || [];
            const usersMap = data.users || {};  // CROWN⁴.8: Users map for rehydration
            const serverChecksum = data.checksum; // CROWN⁴.5: Server sends checksum

            // CROWN⁴.8: Rehydrate assigned_to from users map (Linear pattern)
            // This ensures assignee names persist through background syncs
            for (const task of serverTasks) {
                if (task.assigned_to_id && usersMap[task.assigned_to_id]) {
                    task.assigned_to = usersMap[task.assigned_to_id];
                }
                if (task.assignee_ids && task.assignee_ids.length > 0) {
                    task.assignees = task.assignee_ids
                        .map(id => usersMap[id])
                        .filter(Boolean);
                }
            }

            this.perf.sync_end = performance.now();
            const syncTime = this.perf.sync_end - this.perf.sync_start;
            console.log(`✅ Background sync completed in ${syncTime.toFixed(2)}ms (${serverTasks.length} tasks)`);

            // CROWN⁴.6 FIX: Don't save empty results to cache if we already have tasks
            // This prevents wiping out server-rendered content from cache
            const container = document.getElementById('tasks-list-container');
            const hasExistingTasks = container && container.querySelectorAll('.task-card').length > 0;
            
            if (serverTasks.length === 0 && hasExistingTasks) {
                console.warn('⚠️ Sync returned 0 tasks but DOM has content - preserving cache');
                // Don't save empty to cache, don't re-render
                // Just emit event and return
                window.dispatchEvent(new CustomEvent('tasks:sync:success', {
                    detail: { tasks: serverTasks, sync_time_ms: syncTime, preserved_cache: true }
                }));
                return;
            }
            
            // Update cache with server data (now with rehydrated user objects)
            await this.cache.saveTasks(serverTasks);
            
            // CROWN⁴.5: Store server checksum for future validation
            if (serverChecksum) {
                await this.cache.setMetadata('last_checksum', serverChecksum);
                console.log('📊 Stored server checksum:', serverChecksum.substring(0, 8));
            }
            
            // Update last sync timestamp
            this.lastSyncTimestamp = Date.now();
            await this.cache.setMetadata('last_sync_timestamp', this.lastSyncTimestamp);

            // CROWN⁴.5: ALWAYS merge temp tasks after background sync
            // CRITICAL FIX: This must run ALWAYS (not just when reconciliation needed)
            // to ensure temp tasks survive page refresh
            console.log('🔄 Merging temp tasks with server data...');
            
            // Get ONLY temp tasks from temp_tasks store (not getAllTasks - that would duplicate)
            const tempTasks = await this.cache.getTempTasks();
            
            console.log(`📦 Found ${tempTasks.length} temp tasks to merge with ${serverTasks.length} server tasks`);
            
            // Always merge and render (even if tempTasks.length === 0)
            // This ensures UI updates with latest server data + any unsynced temp tasks
            // NO FILTERING - show ALL temp tasks until reconcileTempTask() explicitly removes them
            // This ensures temp tasks survive refresh even if timing/title matches cause false positives
            // reconcileTempTask() will handle cleanup when server confirms creation
            
            // Merge: temp tasks first (show at top as "Syncing"), then server tasks
            const mergedTasks = [...tempTasks, ...serverTasks];
            
            const apiContext = this._getCurrentViewContext();
            await this.renderTasks(mergedTasks, { 
                fromCache: false, 
                source: 'api',
                filterContext: apiContext.filter,
                searchQuery: apiContext.search,
                sortConfig: apiContext.sort
            });
            this.needsReconciliation = false;

            // Emit sync success event
            window.dispatchEvent(new CustomEvent('tasks:sync:success', {
                detail: { tasks: serverTasks, sync_time_ms: syncTime }
            }));

            // Schedule compaction if needed
            await this.maybeCompact();

        } catch (error) {
            console.error('❌ Background sync failed:', error);
            this.syncInProgress = false;

            // Emit sync error event
            window.dispatchEvent(new CustomEvent('tasks:sync:error', {
                detail: { error: error.message }
            }));
        } finally {
            this.syncInProgress = false;
        }
    }

    /**
     * Maybe run compaction if enough time has passed
     * @returns {Promise<void>}
     */
    async maybeCompact() {
        const lastCompaction = await this.cache.getMetadata('last_compaction_timestamp');
        const now = Date.now();
        const oneDayMs = 24 * 60 * 60 * 1000;

        // Compact once per day
        if (!lastCompaction || (now - lastCompaction) > oneDayMs) {
            console.log('🗜️ Running event compaction...');
            const result = await this.cache.compactEvents(30); // 30 day retention
            await this.cache.setMetadata('last_compaction_timestamp', now);
            console.log(`✅ Compacted ${result.compacted} events`);
        }
    }
    
    /**
     * CRITICAL FIX: Get operation IDs for stale operations older than threshold
     * These need to be cleared from in-memory pendingOperations map
     * @returns {Promise<Array<string>>} Array of stale operation IDs
     */
    async _getStaleOperationIds() {
        try {
            await this.cache.init();
            
            return new Promise((resolve, reject) => {
                const tx = this.cache.db.transaction(['offline_queue'], 'readonly');
                const store = tx.objectStore('offline_queue');
                const request = store.getAll();
                
                request.onsuccess = () => {
                    const ops = request.result || [];
                    const now = Date.now();
                    const STALE_THRESHOLD_MS = 2 * 60 * 1000; // 2 minutes
                    
                    const staleOpIds = ops
                        .filter(op => {
                            const opTime = op.timestamp ? new Date(op.timestamp).getTime() : 0;
                            const opAge = now - opTime;
                            return opAge > STALE_THRESHOLD_MS && op.type === 'create';
                        })
                        .map(op => op.operation_id)
                        .filter(Boolean);
                    
                    console.log(`🧹 [Bootstrap] Found ${staleOpIds.length} stale operation IDs`);
                    resolve(staleOpIds);
                };
                
                request.onerror = () => {
                    console.error('❌ Failed to get stale operation IDs:', request.error);
                    resolve([]); // Return empty on error, don't block bootstrap
                };
            });
        } catch (error) {
            console.error('❌ _getStaleOperationIds failed:', error);
            return [];
        }
    }

    /**
     * Fallback to server-only loading
     * @returns {Promise<Object>}
     */
    async fallbackToServer() {
        console.log('⚠️ Falling back to server-only loading...');
        const fallbackStart = performance.now();
        
        try {
            const response = await fetch('/api/tasks/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            let tasks = data.tasks || [];
            const usersMap = data.users || {};  // CROWN⁴.8: Users map for rehydration

            // CROWN⁴.8: Rehydrate assigned_to from users map (Linear pattern)
            for (const task of tasks) {
                if (task.assigned_to_id && usersMap[task.assigned_to_id]) {
                    task.assigned_to = usersMap[task.assigned_to_id];
                }
                if (task.assignee_ids && task.assignee_ids.length > 0) {
                    task.assignees = task.assignee_ids
                        .map(id => usersMap[id])
                        .filter(Boolean);
                }
            }

            const fallbackContext = this._getCurrentViewContext();
            await this.renderTasks(tasks, { 
                fromCache: false, 
                source: 'api',
                filterContext: fallbackContext.filter,
                searchQuery: fallbackContext.search,
                sortConfig: fallbackContext.sort
            });
            
            // CROWN⁴.6: Emit bootstrap complete event using double-rAF for fallback path
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    const firstPaintTime = performance.now() - fallbackStart;
                    document.dispatchEvent(new CustomEvent('task:bootstrap:complete', {
                        detail: {
                            cached_tasks: 0,
                            first_paint_ms: firstPaintTime,
                            cache_load_ms: 0,
                            meets_target: firstPaintTime < 200,
                            source: 'server_fallback'
                        }
                    }));
                    console.log(`📊 [Fallback] Emitted first paint event: ${firstPaintTime.toFixed(2)}ms`);
                });
            });

            return {
                success: true,
                cached_tasks: 0,
                fallback: true,
                tasks: tasks.length
            };
        } catch (error) {
            console.error('❌ Fallback failed:', error);
            
            // CROWN⁴.6: Still emit event on error so First Paint is recorded (with error state)
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    const firstPaintTime = performance.now() - fallbackStart;
                    document.dispatchEvent(new CustomEvent('task:bootstrap:complete', {
                        detail: {
                            cached_tasks: 0,
                            first_paint_ms: firstPaintTime,
                            cache_load_ms: 0,
                            meets_target: false,
                            source: 'error',
                            error: error.message
                        }
                    }));
                    console.log(`📊 [Error] Emitted first paint event: ${firstPaintTime.toFixed(2)}ms`);
                });
            });
            
            // CROWN⁴.5: Show error state on complete failure
            this.showErrorState(error.message || 'Unable to load tasks from server. Please check your connection.');
            
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Retry bootstrap after error
     * @returns {Promise<void>}
     */
    async retryBootstrap() {
        console.log('🔄 Retrying bootstrap...');
        this.showLoadingState();
        
        try {
            await this.bootstrap();
        } catch (error) {
            console.error('❌ Retry failed:', error);
            this.showErrorState('Retry failed. Please try again or clear your cache.');
        }
    }

    /**
     * Check if due date is overdue
     * @param {string} dueDate
     * @returns {boolean}
     */
    isDueDateOverdue(dueDate) {
        if (!dueDate) return false;
        const due = new Date(dueDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return due < today;
    }

    /**
     * Check if due date is within N days
     * @param {string} dueDate
     * @param {number} days - Number of days
     * @returns {boolean}
     */
    isDueDateWithin(dueDate, days) {
        if (!dueDate) return false;
        const due = new Date(dueDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const targetDate = new Date(today);
        targetDate.setDate(today.getDate() + days);
        return due >= today && due <= targetDate;
    }

    /**
     * Format due date for display
     * @param {string} dueDate
     * @returns {string}
     */
    formatDueDate(dueDate) {
        if (!dueDate) return 'No due date';
        
        const due = new Date(dueDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        const diffDays = Math.floor((due - today) / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Tomorrow';
        if (diffDays === -1) return 'Yesterday';
        if (diffDays < 0) return `${Math.abs(diffDays)}d overdue`;
        if (diffDays <= 7) return `In ${diffDays}d`;
        
        return due.toLocaleDateString();
    }

    /**
     * Escape HTML for XSS prevention
     * @param {string} text
     * @returns {string}
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export class for orchestrator
window.TaskBootstrap = TaskBootstrap;

// CROWN⁴.10 SINGLETON GUARD: Prevent double instantiation
// Uses a dedicated flag that is checked BEFORE instance creation
// This prevents race conditions between auto-instantiate and orchestrator
if (!window.__minaTaskBootstrapInstantiated) {
    // Auto-instantiate if taskCache is ready
    if (window.taskCache && window.taskCache.ready) {
        window.__minaTaskBootstrapInstantiated = true; // Set flag FIRST to prevent races
        window.taskBootstrap = new TaskBootstrap();
        console.log('🚀 CROWN⁴.5 TaskBootstrap loaded (auto-instantiated, singleton)');
    } else {
        console.log('🚀 CROWN⁴.5 TaskBootstrap class loaded (orchestrator will instantiate)');
    }
} else {
    console.warn('⚠️ [TaskBootstrap] BLOCKED duplicate instantiation attempt (singleton guard)');
}

// ========================================
// CROWN⁴.5 Empty/Loading/Error State Event Handlers
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    // Empty State - "Create your first task" button
    const emptyStateCreateBtn = document.getElementById('empty-state-create-btn');
    if (emptyStateCreateBtn) {
        emptyStateCreateBtn.addEventListener('click', () => {
            console.log('📝 Empty state create button clicked');
            // Open the task modal (same as "New Task" button)
            const newTaskBtn = document.querySelector('[data-action="new-task"], #create-task-btn');
            if (newTaskBtn) {
                newTaskBtn.click();
            } else {
                // Fallback: directly open modal
                const modal = document.getElementById('task-modal-overlay');
                if (modal) {
                    modal.classList.remove('hidden');
                    const titleInput = document.getElementById('task-title');
                    if (titleInput) titleInput.focus();
                }
            }
        });
    }

    // Error State - "Retry" button
    const errorStateRetryBtn = document.getElementById('error-state-retry-btn');
    if (errorStateRetryBtn) {
        errorStateRetryBtn.addEventListener('click', async () => {
            console.log('🔄 Error state retry clicked');
            if (window.taskBootstrap) {
                // Show loading state
                window.taskBootstrap.showLoadingState();
                
                // Attempt to re-bootstrap
                try {
                    await window.taskBootstrap.bootstrap();
                } catch (error) {
                    console.error('❌ Retry failed:', error);
                    window.taskBootstrap.showErrorState('Still unable to load tasks. Please try again later.');
                }
            } else {
                // Fallback: reload page
                window.location.reload();
            }
        });
    }

    // Error State - "Clear Cache" button
    const errorStateClearCacheBtn = document.getElementById('error-state-clear-cache-btn');
    if (errorStateClearCacheBtn) {
        errorStateClearCacheBtn.addEventListener('click', async () => {
            console.log('🗑️ Clear cache button clicked');
            
            if (window.taskCache) {
                try {
                    // Clear the IndexedDB cache
                    await window.taskCache.clear();
                    console.log('✅ Cache cleared successfully');
                    
                    // Show loading state
                    if (window.taskBootstrap) {
                        window.taskBootstrap.showLoadingState();
                    }
                    
                    // Reload the page to fetch fresh data
                    setTimeout(() => {
                        window.location.reload();
                    }, 500);
                } catch (error) {
                    console.error('❌ Failed to clear cache:', error);
                    alert('Failed to clear cache. Please refresh the page manually.');
                }
            } else {
                // Fallback: just reload
                window.location.reload();
            }
        });
    }
});

console.log('✅ Empty/Loading/Error state handlers initialized');
