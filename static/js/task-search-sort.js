/**
 * CROWN⁴.5 Task Search & Sort Module
 * Real-time search filtering and multi-criteria sorting
 * CROWN⁴.9: Respects hydration gate to prevent flicker
 */

class TaskSearchSort {
    constructor() {
        this.searchInput = document.getElementById('task-search-input');
        this.searchClearBtn = document.getElementById('search-clear-btn');
        this.sortSelect = document.getElementById('task-sort-select');
        this.visibleCountEl = document.getElementById('visible-task-count');
        this.totalCountEl = document.getElementById('total-task-count');
        this.tasksContainer = document.getElementById('tasks-list-container');

        // Ledger-backed cache + broadcast channel hooks
        this.cache = window.taskCache || window.optimisticUI?.cache || null;
        this.broadcast = window.broadcastSync || null;
        this.viewStateKey = 'tasks_page';
        this.isApplyingRemoteState = false;

        this.searchQuery = '';
        this.currentSort = 'default';
        this.currentFilter = 'active'; // Default to 'active' tab to hide archived tasks
        this.quickFilter = null; // Added for quick filter support

        this.handleSearchInput = null;
        this.handleSearchClear = null;
        this.handleSortChange = null;
        
        // CROWN⁴.9: Track hydration state for deferred operations
        this._hydrationReady = false;
        this._deferredFilterApply = false;
        
        // CROWN⁴.12: User action lock prevents background restores from overwriting user clicks
        this._userActionTimestamp = 0;
        this._userActionLockDuration = 3000; // 3 seconds lock after user clicks
        
        // CROWN⁴.13: Skip initial load hydration to prevent flicker
        // Always start with 'active' filter, only hydrate on visibility changes
        this._isInitialLoad = true;

        this.init();
        // CROWN⁴.13: Don't hydrate on initial load - use default 'active' filter
        // This prevents persisted 'archived' state from overwriting the default
        // Hydration only happens on visibility change (tab switch back)
        this.registerCrossTabSync();
        console.log('[TaskSearchSort] Initialized with default filter: active (skipping initial hydration)');
    }
    
    /**
     * CROWN⁴.9: Check if hydration is ready (global or local state)
     * @returns {boolean}
     */
    _isHydrationReady() {
        return this._hydrationReady || 
               window.taskHydrationReady || 
               (window.taskBootstrap?.isHydrationReady?.() ?? false);
    }
    
    /**
     * CROWN⁴.12: Check if user action lock is active
     * Prevents background state restores from overwriting recent user clicks
     * @returns {boolean}
     */
    _isUserActionLocked() {
        const elapsed = Date.now() - this._userActionTimestamp;
        const locked = elapsed < this._userActionLockDuration;
        if (locked) {
            console.log(`[TaskSearchSort] User action lock active (${elapsed}ms ago) - blocking background restore`);
        }
        return locked;
    }
    
    /**
     * CROWN⁴.12: Set user action lock when user clicks filter/sort
     */
    _setUserActionLock() {
        this._userActionTimestamp = Date.now();
        console.log('[TaskSearchSort] User action lock set');
    }

    init() {
        // Delegated search handler with debouncing
        let searchTimeout;
        this.handleSearchInput = (e) => {
            if (e.target.id !== 'task-search-input') return;
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.searchQuery = e.target.value.toLowerCase().trim();
                this.updateClearButton();
                this.safeApplyFiltersAndSort();
                document.dispatchEvent(new CustomEvent('task:search', { detail: { query: this.searchQuery } }));
            }, 150);
        };

        // Delegated clear button handler
        this.handleSearchClear = (e) => {
            const btn = e.target.closest('#search-clear-btn');
            if (!btn) return;
            e.preventDefault();
            this.searchInput = this.searchInput || document.getElementById('task-search-input');
            if (this.searchInput) {
                this.searchInput.value = '';
            }
            this.searchQuery = '';
            this.updateClearButton();
            this.safeApplyFiltersAndSort();
            this.searchInput?.focus();
            document.dispatchEvent(new CustomEvent('task:search-cleared'));
        };

        // Delegated sort selector handler
        this.handleSortChange = (e) => {
            if (e.target.id !== 'task-sort-select') return;
            this.currentSort = e.target.value;
            this.safeApplyFiltersAndSort();
            document.dispatchEvent(new CustomEvent('task:sort', { detail: { sort: this.currentSort } }));
        };

        document.addEventListener('input', this.handleSearchInput);
        document.addEventListener('click', this.handleSearchClear);
        document.addEventListener('change', this.handleSortChange);
        
        // Listen for filter tab changes
        document.addEventListener('filterChanged', (e) => {
            this.currentFilter = e.detail.filter;
            this.safeApplyFiltersAndSort();
        });
        
        // CROWN⁴.9: Listen for hydration complete event
        // This is the ONLY trigger for initial filter application
        document.addEventListener('tasks:hydrated', () => {
            console.log('[TaskSearchSort] Hydration complete - enabling filter operations');
            this._hydrationReady = true;
            
            // CROWN⁴.13 FIX: Clear initial load flag after bootstrap completes
            // This allows IndexedDB hydration on subsequent visibility changes
            this._isInitialLoad = false;
            
            // Apply any deferred filter
            if (this._deferredFilterApply) {
                this._deferredFilterApply = false;
                this.safeApplyFiltersAndSort();
            }
        });
        
        // Apply initial filter after tasks bootstrap completes
        // CROWN⁴.9: Only proceed if hydration is ready
        document.addEventListener('task:bootstrap:complete', (e) => {
            if (e.detail?.hydrationReady || this._isHydrationReady()) {
                this._hydrationReady = true;
                this.safeApplyFiltersAndSort();
                console.log('[TaskSearchSort] Initial filter applied after bootstrap (hydration ready)');
            } else {
                console.log('[TaskSearchSort] Bootstrap complete but hydration not ready - deferring filter');
                this._deferredFilterApply = true;
            }
        });
        
        // Reapply filter when tasks are mutated (OptimisticUI + WebSocket sync)
        // CRITICAL: Listen on window (not document) because OptimisticUI dispatches on window
        // CROWN⁴.9: Only apply if hydration is ready
        const taskMutationEvents = [
            'task:created', 
            'task:updated', 
            'task:deleted', 
            'task:restored',
            'task:completed'    // Handle completion events for filter updates
        ];
        taskMutationEvents.forEach(eventName => {
            window.addEventListener(eventName, () => {
                // Only apply if hydration is ready
                if (!this._isHydrationReady()) {
                    console.log(`[TaskSearchSort] Ignoring ${eventName} - hydration not ready`);
                    return;
                }
                // Small delay to ensure DOM update completes
                requestAnimationFrame(() => {
                    this.safeApplyFiltersAndSort();
                });
            });
        });
        
        // CROWN⁴.9: DON'T apply initial filter immediately
        // Wait for hydration event instead to prevent flicker
        const initialTasks = this.tasksContainer?.querySelectorAll('.task-card') || [];
        if (initialTasks.length > 0) {
            console.log(`[TaskSearchSort] Found ${initialTasks.length} server-rendered tasks - waiting for hydration`);
            // Don't call applyFiltersAndSort here - wait for hydration event
        } else {
            console.log('[TaskSearchSort] No tasks in DOM yet, waiting for bootstrap');
        }
    }

    /**
     * Safely execute async filter/sort pipeline without throwing in event listeners
     */
    safeApplyFiltersAndSort() {
        this.applyFiltersAndSort().catch(error => console.error('[TaskSearchSort] applyFiltersAndSort failed:', error));
    }

    /**
     * Load persisted view state from IndexedDB and reapply locally
     * CROWN⁴.12: Respects user action lock to prevent overwriting user clicks
     * CROWN⁴.13: Skips initial load to prevent flicker
     */
    async hydrateFromViewState() {
        if (!this.cache?.getViewState) return;
        
        // CROWN⁴.13: Skip hydration on initial page load
        // Always use default 'active' filter on fresh load
        if (this._isInitialLoad) {
            console.log('[TaskSearchSort] Skipping hydration on initial load - using default filter');
            return;
        }
        
        // CROWN⁴.12: Skip hydration if user recently clicked a filter tab
        if (this._isUserActionLocked()) {
            console.log('[TaskSearchSort] Skipping hydration - user action lock active');
            return;
        }

        try {
            const viewState = await this.cache.getViewState(this.viewStateKey);
            if (!viewState) return;

            this.isApplyingRemoteState = true;
            if (viewState.search) {
                this.searchQuery = viewState.search.toLowerCase();
                if (this.searchInput) this.searchInput.value = viewState.search;
                this.updateClearButton();
            }

            if (viewState.filter || viewState.status) {
                this.currentFilter = viewState.filter || viewState.status || this.currentFilter;
                this.setActiveFilterTab(this.currentFilter);
            }

            if (viewState.sort) {
                this.currentSort = this.mapSortConfigToKey(viewState.sort);
                if (this.sortSelect) this.sortSelect.value = this.currentSort;
            }

            await this.applyFiltersAndSort();
        } catch (error) {
            console.error('[TaskSearchSort] Failed to hydrate view state:', error);
        } finally {
            this.isApplyingRemoteState = false;
        }
    }

    /**
     * CROWN⁴.14: Check if in settling period (1.5s after hydration)
     * @private
     */
    _isInSettlingPeriod() {
        if (!this._hydrationReady) return true; // Before hydration = always settling
        const settlingMs = 1500; // 1.5 second settling period
        const elapsed = Date.now() - (window.taskBootstrap?._hydrationCompleteTime || 0);
        return elapsed < settlingMs;
    }
    
    /**
     * Register BroadcastChannel + idle visibility sync
     * CROWN⁴.14: Added initial load and settling period guards to prevent echo loops
     */
    registerCrossTabSync() {
        if (this.broadcast?.on) {
            this.broadcast.on(this.broadcast.EVENTS.FILTER_APPLY, async (payload) => {
                if (!payload) return;
                // CROWN⁴.14: Block during initial load
                if (this._isInitialLoad) {
                    console.log('[TaskSearchSort] FILTER_APPLY blocked - initial load');
                    return;
                }
                // CROWN⁴.14: Block during settling period
                if (this._isInSettlingPeriod()) {
                    console.log('[TaskSearchSort] FILTER_APPLY blocked - settling period');
                    return;
                }
                // CROWN⁴.12: Skip if user recently clicked a filter
                if (this._isUserActionLocked()) return;
                
                this.isApplyingRemoteState = true;
                try {
                    if (payload.filter) {
                        this.currentFilter = payload.filter;
                        this.setActiveFilterTab(payload.filter);
                    }
                    await this.applyFiltersAndSort();
                } finally {
                    this.isApplyingRemoteState = false;
                }
            });

            this.broadcast.on(this.broadcast.EVENTS.SEARCH_QUERY, async (payload) => {
                if (!payload?.query) return;
                // CROWN⁴.14: Block during initial load
                if (this._isInitialLoad) {
                    console.log('[TaskSearchSort] SEARCH_QUERY blocked - initial load');
                    return;
                }
                // CROWN⁴.14: Block during settling period
                if (this._isInSettlingPeriod()) {
                    console.log('[TaskSearchSort] SEARCH_QUERY blocked - settling period');
                    return;
                }
                // CROWN⁴.12: Skip if user recently clicked a filter
                if (this._isUserActionLocked()) return;
                
                this.isApplyingRemoteState = true;
                try {
                    this.searchQuery = payload.query.toLowerCase();
                    if (this.searchInput) this.searchInput.value = payload.query;
                    this.updateClearButton();
                    await this.applyFiltersAndSort();
                } finally {
                    this.isApplyingRemoteState = false;
                }
            });

            this.broadcast.on(this.broadcast.EVENTS.UI_STATE_SYNC, async (payload) => {
                if (!payload) return;
                // CROWN⁴.14: Block during initial load
                if (this._isInitialLoad) {
                    console.log('[TaskSearchSort] UI_STATE_SYNC blocked - initial load');
                    return;
                }
                // CROWN⁴.14: Block during settling period
                if (this._isInSettlingPeriod()) {
                    console.log('[TaskSearchSort] UI_STATE_SYNC blocked - settling period');
                    return;
                }
                // CROWN⁴.12: Skip if user recently clicked a filter
                if (this._isUserActionLocked()) return;
                
                this.isApplyingRemoteState = true;
                try {
                    if (payload.search !== undefined) {
                        this.searchQuery = payload.search?.toLowerCase() || '';
                        if (this.searchInput) this.searchInput.value = payload.search || '';
                        this.updateClearButton();
                    }
                    if (payload.filter) {
                        this.currentFilter = payload.filter;
                        this.setActiveFilterTab(payload.filter);
                    }
                    if (payload.sort) {
                        this.currentSort = this.mapSortConfigToKey(payload.sort);
                        if (this.sortSelect) this.sortSelect.value = this.currentSort;
                    }
                    await this.applyFiltersAndSort();
                } finally {
                    this.isApplyingRemoteState = false;
                }
            });
        }

        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                // Idle callback keeps main thread free when returning to tab
                // CROWN⁴.13: _isInitialLoad is cleared in tasks:hydrated, so hydration
                // only happens after bootstrap completes (not on first load)
                const resync = () => this.hydrateFromViewState();
                if ('requestIdleCallback' in window) {
                    window.requestIdleCallback(resync, { timeout: 1000 });
                } else {
                    setTimeout(resync, 250);
                }
            }
        });
    }
    
    updateClearButton() {
        if (this.searchQuery.length > 0) {
            this.searchClearBtn?.classList.remove('hidden');
        } else {
            this.searchClearBtn?.classList.add('hidden');
        }
    }
    
    async applyFiltersAndSort() {
        // CROWN⁴.9: Block filter operations until hydration is complete
        // This prevents the render loop that causes flickering
        if (!this._isHydrationReady()) {
            console.log('[TaskSearchSort] applyFiltersAndSort blocked - hydration not ready');
            this._deferredFilterApply = true;
            return;
        }
        
        // CROWN⁴.12: Build sort config for scheduler context
        const sortConfig = this.mapSortKeyToConfig(this.currentSort) || { field: 'created_at', direction: 'desc' };
        
        // CROWN⁴.12: Dispatch context change BEFORE rendering
        // This updates the scheduler's context so it can reject stale payloads
        document.dispatchEvent(new CustomEvent('task:view-context-changed', {
            detail: {
                filter: this.currentFilter,
                search: this.searchQuery,
                sort: sortConfig
            }
        }));
        console.log(`📋 [TaskSearchSort] Context changed: filter=${this.currentFilter}, search="${this.searchQuery}"`);
        
        // Prefer ledger-backed cache rendering when available
        if (this.cache?.getAllTasks && window.taskBootstrap?.renderTasks) {
            const allTasks = await this.cache.getAllTasks();
            const nonDeleted = allTasks.filter(task => !task.deleted_at);
            
            // CROWN⁴.9 FIX: Prevent render loop during initial bootstrap
            // When cache is empty but server already rendered task cards, skip cache-based render
            // This prevents the loop: renderTasks(0) → broadcasts → applyFiltersAndSort → repeat
            const serverRenderedCards = this.tasksContainer?.querySelectorAll('.task-card')?.length || 0;
            if (nonDeleted.length === 0 && serverRenderedCards > 0) {
                console.log(`[TaskSearchSort] Skipping cache render - cache empty but ${serverRenderedCards} server cards exist`);
                // Update counts from server-rendered DOM instead
                this.updateCounts(serverRenderedCards, serverRenderedCards);
                return;
            }
            
            const filteredTasks = this.filterTasksData(nonDeleted);
            const sortedTasks = this.sortTaskData(filteredTasks, this.currentSort);

            // CROWN⁴.12: Pass full context metadata for scheduler routing
            await window.taskBootstrap.renderTasks(sortedTasks, { 
                fromCache: true, 
                isFilterChange: true,
                source: 'filter_change',
                filterContext: this.currentFilter,
                searchQuery: this.searchQuery,
                sortConfig: sortConfig
            });
            this.updateCounts(sortedTasks.length, nonDeleted.length);
            await this.persistViewState();
            return;
        }

        const tasks = Array.from(this.tasksContainer?.querySelectorAll('.task-card') || []);

        // 1. Apply search filter
        let visibleTasks = tasks.filter(task => {
            if (!this.searchQuery) return true;

            const title = task.querySelector('.task-title')?.textContent.toLowerCase() || '';
            const assignee = task.querySelector('.task-assignee')?.textContent.toLowerCase() || '';
            const labels = Array.from(task.querySelectorAll('.task-label'))
                .map(label => label.textContent.toLowerCase())
                .join(' ');

            return title.includes(this.searchQuery) ||
                   assignee.includes(this.searchQuery) ||
                   labels.includes(this.searchQuery);
        });

        // 2. Apply archive filter (from filter tabs: All/Active/Archived)
        // Filter is based on task.status field: 'todo', 'in_progress', 'pending', 'blocked', 'completed', 'cancelled'
        // Active = todo, in_progress, pending, blocked (not completed/cancelled)
        // Archived = completed or cancelled
        
        if (this.currentFilter === 'active') {
            visibleTasks = visibleTasks.filter(task => {
                const status = task.dataset.status || 'todo';
                return status !== 'completed' && status !== 'cancelled';
            });
        } else if (this.currentFilter === 'archived') {
            visibleTasks = visibleTasks.filter(task => {
                const status = task.dataset.status || 'todo';
                return status === 'completed' || status === 'cancelled';
            });
        }
        // 'all' shows both active and archived tasks
        
        // 2.5. Apply quick filter (from Quick Actions Bar)
        if (this.quickFilter) {
            visibleTasks = this.applyQuickFilterLogic(visibleTasks, this.quickFilter);
        }

        // 3. Apply sorting
        if (this.currentSort !== 'default') {
            visibleTasks = this.sortTasks(visibleTasks, this.currentSort);
        }

        // 4. Update DOM visibility
        // CROWN⁴.13: Use class-based approach to avoid overriding layout-specific display values
        tasks.forEach(task => {
            if (visibleTasks.includes(task)) {
                task.classList.add('is-visible');
                task.classList.remove('is-hidden');
                task.style.order = visibleTasks.indexOf(task);
            } else {
                task.classList.add('is-hidden');
                task.classList.remove('is-visible');
            }
        });

        // 5. Update counts and persist view state
        this.updateCounts(visibleTasks.length, tasks.length);
        await this.persistViewState();
    }

    filterTasksData(tasks) {
        return tasks.filter(task => {
            // Use status field - Active = todo, in_progress, pending, blocked
            // Archived = completed or cancelled (Task model has no archived_at column)
            const status = task.status || 'todo';
            if (this.currentFilter === 'active' && (status === 'completed' || status === 'cancelled')) return false;
            if (this.currentFilter === 'archived' && status !== 'completed' && status !== 'cancelled') return false;

            if (this.quickFilter) {
                const passesQuickFilter = this.applyQuickFilterLogic([task], this.quickFilter).length > 0;
                if (!passesQuickFilter) return false;
            }

            if (this.searchQuery) {
                const title = task.title?.toLowerCase() || '';
                const assignee = (task.assigned_to?.username || task.assigned_to?.email || '')?.toLowerCase();
                const labels = Array.isArray(task.labels) ? task.labels.join(' ').toLowerCase() : '';
                if (!title.includes(this.searchQuery) &&
                    !assignee.includes(this.searchQuery) &&
                    !labels.includes(this.searchQuery)) {
                    return false;
                }
            }

            return true;
        });
    }

    sortTaskData(tasks, sortKey) {
        const sortConfig = this.mapSortKeyToConfig(sortKey);
        if (!sortConfig) return tasks;

        const sortable = [...tasks];
        if (window.taskBootstrap?.sortTasks) {
            return window.taskBootstrap.sortTasks(sortable, sortConfig);
        }

        return sortable;
    }

    mapSortKeyToConfig(sortKey) {
        switch (sortKey) {
            case 'priority':
                return { field: 'priority', direction: 'desc' };
            case 'priority-reverse':
                return { field: 'priority', direction: 'asc' };
            case 'due-date':
                return { field: 'due_date', direction: 'asc' };
            case 'due-date-reverse':
                return { field: 'due_date', direction: 'desc' };
            case 'created':
                return { field: 'created_at', direction: 'desc' };
            case 'created-reverse':
                return { field: 'created_at', direction: 'asc' };
            case 'title':
                return { field: 'title', direction: 'asc' };
            case 'title-reverse':
                return { field: 'title', direction: 'desc' };
            default:
                return { field: 'created_at', direction: 'desc' };
        }
    }

    mapSortConfigToKey(sortConfig) {
        if (!sortConfig) return this.currentSort;

        const { field, direction } = sortConfig;
        const dir = direction === 'asc' ? 'asc' : 'desc';
        if (field === 'priority') return dir === 'asc' ? 'priority-reverse' : 'priority';
        if (field === 'due_date') return dir === 'asc' ? 'due-date' : 'due-date-reverse';
        if (field === 'title') return dir === 'asc' ? 'title' : 'title-reverse';
        if (field === 'created_at') return dir === 'asc' ? 'created-reverse' : 'created';
        return 'default';
    }

    async persistViewState() {
        if (!this.cache?.setViewState || this.isApplyingRemoteState) return;

        const viewState = {
            filter: this.currentFilter,
            status: this.currentFilter,
            search: this.searchQuery,
            sort: this.mapSortKeyToConfig(this.currentSort)
        };

        try {
            await this.cache.setViewState(this.viewStateKey, viewState);
        } catch (error) {
            console.warn('[TaskSearchSort] Failed to persist view state:', error);
        }

        this.broadcastState(viewState);
    }

    broadcastState(viewState) {
        // CROWN⁴.14: Debounce broadcasts to prevent rapid-fire events during initialization
        if (this._broadcastDebounceTimer) {
            clearTimeout(this._broadcastDebounceTimer);
        }
        
        // CROWN⁴.14: Skip broadcasts during initial load or settling period
        if (this._isInitialLoad || this._isInSettlingPeriod()) {
            console.log('[TaskSearchSort] Broadcast skipped - initial load or settling');
            return;
        }
        
        // CROWN⁴.14: Skip if applying remote state (prevents echo loop)
        if (this.isApplyingRemoteState) {
            console.log('[TaskSearchSort] Broadcast skipped - applying remote state');
            return;
        }
        
        this._broadcastDebounceTimer = setTimeout(() => {
            if (this.broadcast?.broadcast) {
                this.broadcast.broadcast(this.broadcast.EVENTS.FILTER_APPLY, viewState);
                this.broadcast.broadcast(this.broadcast.EVENTS.SEARCH_QUERY, { query: this.searchQuery });
                this.broadcast.broadcast(this.broadcast.EVENTS.UI_STATE_SYNC, viewState);
            }

            if (window.multiTabSync?.broadcastFilterChanged) {
                window.multiTabSync.broadcastFilterChanged(viewState);
            }
        }, 300); // 300ms debounce
    }

    setActiveFilterTab(filter) {
        const tabs = document.querySelectorAll('.filter-tab');
        tabs.forEach(tab => {
            if (tab.dataset.filter === filter) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });
    }
    
    sortTasks(tasks, sortType) {
        const sorted = [...tasks];
        
        const priorityOrder = { high: 3, medium: 2, low: 1 };
        
        sorted.sort((a, b) => {
            switch (sortType) {
                case 'priority': {
                    const priorityA = priorityOrder[a.dataset.priority] || 0;
                    const priorityB = priorityOrder[b.dataset.priority] || 0;
                    return priorityB - priorityA; // High to low
                }
                
                case 'priority-reverse': {
                    const priorityA = priorityOrder[a.dataset.priority] || 0;
                    const priorityB = priorityOrder[b.dataset.priority] || 0;
                    return priorityA - priorityB; // Low to high
                }
                
                case 'due-date': {
                    const dateA = a.dataset.dueDate ? new Date(a.dataset.dueDate) : new Date('9999-12-31');
                    const dateB = b.dataset.dueDate ? new Date(b.dataset.dueDate) : new Date('9999-12-31');
                    return dateA - dateB; // Soonest first
                }
                
                case 'due-date-reverse': {
                    const dateA = a.dataset.dueDate ? new Date(a.dataset.dueDate) : new Date('1970-01-01');
                    const dateB = b.dataset.dueDate ? new Date(b.dataset.dueDate) : new Date('1970-01-01');
                    return dateB - dateA; // Latest first
                }
                
                case 'created': {
                    const idA = parseInt(a.dataset.taskId) || 0;
                    const idB = parseInt(b.dataset.taskId) || 0;
                    return idB - idA; // Newest first (higher IDs)
                }
                
                case 'created-reverse': {
                    const idA = parseInt(a.dataset.taskId) || 0;
                    const idB = parseInt(b.dataset.taskId) || 0;
                    return idA - idB; // Oldest first (lower IDs)
                }
                
                case 'title': {
                    const titleA = a.querySelector('.task-title')?.textContent.toLowerCase() || '';
                    const titleB = b.querySelector('.task-title')?.textContent.toLowerCase() || '';
                    return titleA.localeCompare(titleB); // A to Z
                }
                
                case 'title-reverse': {
                    const titleA = a.querySelector('.task-title')?.textContent.toLowerCase() || '';
                    const titleB = b.querySelector('.task-title')?.textContent.toLowerCase() || '';
                    return titleB.localeCompare(titleA); // Z to A
                }
                
                default:
                    return 0;
            }
        });
        
        return sorted;
    }
    
    updateCounts(visible = null, total = null) {
        if (visible === null) {
            const tasks = this.tasksContainer?.querySelectorAll('.task-card') || [];
            const visibleTasks = Array.from(tasks).filter(task => task.style.display !== 'none');
            visible = visibleTasks.length;
            total = tasks.length;
        }
        
        if (this.visibleCountEl) {
            this.visibleCountEl.textContent = visible;
        }
        
        if (this.totalCountEl) {
            this.totalCountEl.textContent = total;
        }
    }
    
    applyQuickFilterLogic(tasks, filter) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const nextWeek = new Date(today);
        nextWeek.setDate(nextWeek.getDate() + 7);

        return tasks.filter(task => {
            const getValue = (prop, datasetKey) => task?.dataset ? task.dataset[datasetKey] : task?.[prop];
            const priority = getValue('priority', 'priority');
            const dueDateStr = getValue('due_date', 'dueDate');
            const assignedTo = getValue('assigned_to', 'assignedTo');

            switch (filter) {
                case 'high-priority':
                    return priority === 'high';

                case 'today': {
                    if (!dueDateStr) return false;
                    const dueDate = new Date(dueDateStr);
                    dueDate.setHours(0, 0, 0, 0);
                    return dueDate.getTime() === today.getTime();
                }

                case 'this-week': {
                    if (!dueDateStr) return false;
                    const dueDate = new Date(dueDateStr);
                    dueDate.setHours(0, 0, 0, 0);
                    return dueDate >= today && dueDate < nextWeek;
                }

                case 'unassigned':
                    return !assignedTo || assignedTo === '';

                default:
                    return true;
            }
        });
    }
    
    // Public API for external updates
    refresh() {
        this.safeApplyFiltersAndSort();
    }

    clearSearch() {
        this.searchInput.value = '';
        this.searchQuery = '';
        this.updateClearButton();
        this.safeApplyFiltersAndSort();
    }

    setFilter(filter) {
        this.currentFilter = filter;
        this.safeApplyFiltersAndSort();
    }

    setQuickFilter(filter) {
        this.quickFilter = filter;
        this.safeApplyFiltersAndSort();
    }

    clearQuickFilter() {
        this.quickFilter = null;
        this.safeApplyFiltersAndSort();
    }
}

// Initialize and expose globally
let taskSearchSort;
document.addEventListener('DOMContentLoaded', () => {
    taskSearchSort = new TaskSearchSort();
});

// Make available globally for other modules
window.TaskSearchSort = TaskSearchSort;
window.getTaskSearchSort = () => taskSearchSort;
