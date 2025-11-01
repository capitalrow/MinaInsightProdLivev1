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
        this.perf = {
            cache_load_start: 0,
            cache_load_end: 0,
            first_paint: 0,
            sync_start: 0,
            sync_end: 0
        };
    }

    /**
     * Bootstrap tasks page with cache-first loading
     * Target: <200ms first paint
     * @returns {Promise<Object>} Bootstrap results
     */
    async bootstrap() {
        console.log('🚀 Starting CROWN⁴.5 cache-first bootstrap...');
        this.perf.cache_load_start = performance.now();

        try {
            // Step 1: Load from cache immediately (target: <50ms)
            const cachedTasks = await this.loadFromCache();
            this.perf.cache_load_end = performance.now();
            
            const cacheLoadTime = this.perf.cache_load_end - this.perf.cache_load_start;
            console.log(`📦 Cache loaded in ${cacheLoadTime.toFixed(2)}ms (${cachedTasks.length} tasks)`);

            // Step 2: Render UI immediately (target: <200ms total)
            await this.renderTasks(cachedTasks, { fromCache: true });
            this.perf.first_paint = performance.now();
            
            const firstPaintTime = this.perf.first_paint - this.perf.cache_load_start;
            console.log(`🎨 First paint in ${firstPaintTime.toFixed(2)}ms`);

            // Emit performance metric
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('first_paint_ms', firstPaintTime);
                window.CROWNTelemetry.recordMetric('cache_load_ms', cacheLoadTime);
            }

            // Step 3: Start background sync
            this.syncInBackground();

            this.initialized = true;

            return {
                success: true,
                cached_tasks: cachedTasks.length,
                cache_load_ms: cacheLoadTime,
                first_paint_ms: firstPaintTime,
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

        // Apply sort
        const sortedTasks = this.sortTasks(tasks, viewState.sort);

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
     * @param {Array} tasks
     * @param {Object} options - { fromCache: boolean }
     * @returns {Promise<void>}
     */
    async renderTasks(tasks, options = {}) {
        const container = document.getElementById('tasks-list-container');
        const emptyState = document.getElementById('tasks-empty-state');
        
        if (!container) {
            console.warn('⚠️ Tasks container not found, skipping render');
            return;
        }

        // Show empty state or task list
        if (!tasks || tasks.length === 0) {
            // SAFETY: Only clear if we have NO server-rendered content
            const hasServerContent = container.querySelectorAll('.task-card').length > 0;
            
            if (!hasServerContent) {
                if (emptyState) {
                    emptyState.style.display = 'block';
                    emptyState.classList.add('fade-in');
                }
                if (container) {
                    container.innerHTML = '';
                }
            } else {
                console.warn('⚠️ Keeping server-rendered content (fallback protection)');
            }
            return;
        }

        // Hide empty state
        if (emptyState) {
            emptyState.style.display = 'none';
        }

        // Render tasks with error protection
        try {
            const tasksHTML = tasks.map((task, index) => this.renderTaskCard(task, index)).join('');
            container.innerHTML = tasksHTML;
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

        // Update counters
        this.updateCounters(tasks);

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
     * Render single task card HTML
     * @param {Object} task
     * @param {number} index
     * @returns {string} HTML
     */
    renderTaskCard(task, index) {
        const priority = task.priority || 'medium';
        const status = task.status || 'todo';
        const isCompleted = status === 'completed';
        const isSnoozed = task.snoozed_until && new Date(task.snoozed_until) > new Date();
        const isSyncing = task._is_syncing || (task.id && typeof task.id === 'string' && task.id.startsWith('temp_'));

        return `
            <div class="task-card ${isSyncing ? 'task-syncing' : ''}" 
                 data-task-id="${task.id}"
                 data-status="${status}"
                 data-priority="${priority}"
                 style="animation-delay: ${index * 0.05}s;">
                <div class="task-card-header">
                    <div class="task-checkbox-wrapper">
                        <input type="checkbox" 
                               class="task-checkbox" 
                               ${isCompleted ? 'checked' : ''}
                               ${isSyncing ? 'disabled title="Task is syncing with server..."' : ''}
                               data-task-id="${task.id}">
                    </div>
                    <div class="task-content">
                        <h3 class="task-title ${isCompleted ? 'completed' : ''}">
                            ${this.escapeHtml(task.title || 'Untitled Task')}
                        </h3>
                        ${task.description ? `
                            <p class="task-description">${this.escapeHtml(task.description)}</p>
                        ` : ''}
                        <div class="task-meta">
                            ${isSyncing ? `
                                <span class="syncing-badge">
                                    <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" class="spin-animation">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                                    </svg>
                                    Syncing...
                                </span>
                            ` : ''}
                            <span class="priority-badge priority-${priority.toLowerCase()}">
                                ${priority}
                            </span>
                            ${task.due_date ? `
                                <span class="due-date-badge ${this.isDueDateOverdue(task.due_date) ? 'overdue' : ''}">
                                    <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                    </svg>
                                    ${this.formatDueDate(task.due_date)}
                                </span>
                            ` : ''}
                            ${isSnoozed ? `
                                <span class="snoozed-badge">
                                    <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                    </svg>
                                    Snoozed
                                </span>
                            ` : ''}
                            ${task.labels && task.labels.length > 0 ? `
                                <div class="task-labels">
                                    ${task.labels.slice(0, 3).map(label => `
                                        <span class="label-badge" data-label="${this.escapeHtml(label)}">
                                            ${this.escapeHtml(label)}
                                            <button class="label-remove-btn" data-task-id="${task.id}" data-label="${this.escapeHtml(label)}" title="Remove label">
                                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                    <path d="M18 6L6 18M6 6l12 12"/>
                                                </svg>
                                            </button>
                                        </span>
                                    `).join('')}
                                    ${task.labels.length > 3 ? `
                                        <span class="label-badge label-count" title="${task.labels.slice(3).join(', ')}">+${task.labels.length - 3}</span>
                                    ` : ''}
                                    <button class="label-add-btn" data-task-id="${task.id}" title="Add label">
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M12 5v14m-7-7h14"/>
                                        </svg>
                                    </button>
                                </div>
                            ` : `
                                <div class="task-labels">
                                    <button class="label-add-btn label-add-btn-empty" data-task-id="${task.id}" title="Add label">
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/>
                                        </svg>
                                        Add label
                                    </button>
                                </div>
                            `}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Update task counters in UI
     * CRITICAL: This must ALWAYS calculate counts from ALL tasks, not filtered subset
     * @param {Array} tasks - Currently displayed tasks (may be filtered)
     */
    async updateCounters(tasks) {
        // Fetch ALL tasks from cache to get correct totals
        // The 'tasks' parameter might be filtered, which would give wrong counts
        const allTasks = await this.cache.getAllTasks();
        
        const counters = {
            all: allTasks.length,
            pending: allTasks.filter(t => t.status === 'todo' || t.status === 'in_progress').length,
            todo: allTasks.filter(t => t.status === 'todo').length,
            in_progress: allTasks.filter(t => t.status === 'in_progress').length,
            completed: allTasks.filter(t => t.status === 'completed').length,
            overdue: allTasks.filter(t => this.isDueDateOverdue(t.due_date) && t.status !== 'completed').length
        };

        // Update counter badges
        Object.entries(counters).forEach(([key, count]) => {
            const badge = document.querySelector(`[data-counter="${key}"]`);
            if (badge) {
                badge.textContent = count;
                
                // Add pulse animation on counter change
                badge.classList.remove('counter-pulse');
                void badge.offsetWidth; // Trigger reflow
                badge.classList.add('counter-pulse');
            }
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
            const serverTasks = data.tasks || [];

            this.perf.sync_end = performance.now();
            const syncTime = this.perf.sync_end - this.perf.sync_start;
            console.log(`✅ Background sync completed in ${syncTime.toFixed(2)}ms (${serverTasks.length} tasks)`);

            // Update cache with server data
            await this.cache.saveTasks(serverTasks);
            
            // Update last sync timestamp
            this.lastSyncTimestamp = Date.now();
            await this.cache.setMetadata('last_sync_timestamp', this.lastSyncTimestamp);

            // Re-render with fresh data
            await this.renderTasks(serverTasks, { fromCache: false });

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
     * Fallback to server-only loading
     * @returns {Promise<Object>}
     */
    async fallbackToServer() {
        console.log('⚠️ Falling back to server-only loading...');
        
        try {
            const response = await fetch('/api/tasks/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'
            });

            const data = await response.json();
            const tasks = data.tasks || [];

            await this.renderTasks(tasks, { fromCache: false });

            return {
                success: true,
                cached_tasks: 0,
                fallback: true,
                tasks: tasks.length
            };
        } catch (error) {
            console.error('❌ Fallback failed:', error);
            return {
                success: false,
                error: error.message
            };
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

// Export singleton
window.taskBootstrap = new TaskBootstrap();

console.log('🚀 CROWN⁴.5 TaskBootstrap loaded');
