/**
 * CROWN⁴.5 Task Search & Sort Module
 * Real-time search filtering and multi-criteria sorting
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

        this.init();
        this.hydrateFromViewState();
        this.registerCrossTabSync();
        console.log('[TaskSearchSort] Initialized with default filter: active');
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
            }, 150); // 150ms debounce for smooth performance
        });

        // Clear button
        this.searchClearBtn?.addEventListener('click', () => {
            this.searchInput.value = '';
            this.searchQuery = '';
            this.updateClearButton();
            this.safeApplyFiltersAndSort();
            this.searchInput.focus();
        });

        // Sort selector
        this.sortSelect?.addEventListener('change', (e) => {
            this.currentSort = e.target.value;
            this.safeApplyFiltersAndSort();
        });

                this.applyFiltersAndSort();
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
            this.applyFiltersAndSort();
            this.searchInput?.focus();
            document.dispatchEvent(new CustomEvent('task:search-cleared'));
        };

        // Delegated sort selector handler
        this.handleSortChange = (e) => {
            if (e.target.id !== 'task-sort-select') return;
            this.currentSort = e.target.value;
            this.applyFiltersAndSort();
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
        
        // Apply initial filter after tasks bootstrap completes
        document.addEventListener('task:bootstrap:complete', () => {
            this.safeApplyFiltersAndSort();
            console.log('[TaskSearchSort] Initial filter applied after bootstrap: active (hiding archived tasks)');
        });
        
        // Reapply filter when tasks are mutated (OptimisticUI + WebSocket sync)
        // CRITICAL: Listen on window (not document) because OptimisticUI dispatches on window
        const taskMutationEvents = [
            'task:created', 
            'task:updated', 
            'task:deleted', 
            'task:restored',
            'task:completed'    // Handle completion events for filter updates
        ];
        taskMutationEvents.forEach(eventName => {
            window.addEventListener(eventName, () => {
                // Small delay to ensure DOM update completes
                requestAnimationFrame(() => {
                    this.safeApplyFiltersAndSort();
                });
            });
        });
        
        // Apply initial filter immediately if tasks already in DOM (server-rendered)
        // This ensures filter counts match tab counters on page load
        const initialTasks = this.tasksContainer?.querySelectorAll('.task-card') || [];
        if (initialTasks.length > 0) {
            console.log(`[TaskSearchSort] Found ${initialTasks.length} server-rendered tasks, applying initial filter`);
            this.applyFiltersAndSort();
        } else {
            // If no tasks in DOM yet, the bootstrap:complete event will trigger filtering
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
     */
    async hydrateFromViewState() {
        if (!this.cache?.getViewState) return;

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
     * Register BroadcastChannel + idle visibility sync
     */
    registerCrossTabSync() {
        if (this.broadcast?.on) {
            this.broadcast.on(this.broadcast.EVENTS.FILTER_APPLY, async (payload) => {
                if (!payload) return;
                this.isApplyingRemoteState = true;
                if (payload.filter) {
                    this.currentFilter = payload.filter;
                    this.setActiveFilterTab(payload.filter);
                }
                await this.applyFiltersAndSort();
                this.isApplyingRemoteState = false;
            });

            this.broadcast.on(this.broadcast.EVENTS.SEARCH_QUERY, async (payload) => {
                if (!payload?.query) return;
                this.isApplyingRemoteState = true;
                this.searchQuery = payload.query.toLowerCase();
                if (this.searchInput) this.searchInput.value = payload.query;
                this.updateClearButton();
                await this.applyFiltersAndSort();
                this.isApplyingRemoteState = false;
            });

            this.broadcast.on(this.broadcast.EVENTS.UI_STATE_SYNC, async (payload) => {
                if (!payload) return;
                this.isApplyingRemoteState = true;
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
                this.isApplyingRemoteState = false;
            });
        }

        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                // Idle callback keeps main thread free when returning to tab
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
        // Prefer ledger-backed cache rendering when available
        if (this.cache?.getAllTasks && window.taskBootstrap?.renderTasks) {
            const allTasks = await this.cache.getAllTasks();
            const nonDeleted = allTasks.filter(task => !task.deleted_at);
            const filteredTasks = this.filterTasksData(nonDeleted);
            const sortedTasks = this.sortTaskData(filteredTasks, this.currentSort);

            await window.taskBootstrap.renderTasks(sortedTasks, { fromCache: true });
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
        tasks.forEach(task => {
            if (visibleTasks.includes(task)) {
                task.style.display = '';
                task.style.order = visibleTasks.indexOf(task);
            } else {
                task.style.display = 'none';
            }
        });

        // 5. Update counts and persist view state
        this.updateCounts(visibleTasks.length, tasks.length);
        await this.persistViewState();
    }

    filterTasksData(tasks) {
        return tasks.filter(task => {
            if (this.currentFilter === 'active' && task.archived_at) return false;
            if (this.currentFilter === 'archived' && !task.archived_at) return false;

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
        if (this.broadcast?.broadcast) {
            this.broadcast.broadcast(this.broadcast.EVENTS.FILTER_APPLY, viewState);
            this.broadcast.broadcast(this.broadcast.EVENTS.SEARCH_QUERY, { query: this.searchQuery });
            this.broadcast.broadcast(this.broadcast.EVENTS.UI_STATE_SYNC, viewState);
        }

        if (window.multiTabSync?.broadcastFilterChanged) {
            window.multiTabSync.broadcastFilterChanged(viewState);
        }
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
