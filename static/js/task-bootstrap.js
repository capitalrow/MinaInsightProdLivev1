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

            // Step 2: CROWN⁴.5 - Validate cache checksum
            const checksumValid = await this.validateCacheChecksum(cachedTasks);
            if (!checksumValid) {
                console.warn('⚠️ Cache checksum validation failed - triggering reconciliation');
                // Continue with cached data but mark for reconciliation
                this.needsReconciliation = true;
            }

            // Step 3: Render UI immediately (target: <200ms total)
            await this.renderTasks(cachedTasks, { fromCache: true });
            this.perf.first_paint = performance.now();
            
            const firstPaintTime = this.perf.first_paint - this.perf.cache_load_start;
            console.log(`🎨 First paint in ${firstPaintTime.toFixed(2)}ms`);

            // Emit performance metric
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('first_paint_ms', firstPaintTime);
                window.CROWNTelemetry.recordMetric('cache_load_ms', cacheLoadTime);
                window.CROWNTelemetry.recordMetric('checksum_valid', checksumValid ? 1 : 0);
            }

            // Step 4: Start background sync (with reconciliation if needed)
            this.syncInBackground();

            this.initialized = true;

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

        // Attach event listeners (checkbox toggle, etc.)
        this._attachEventListeners();

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
     * Render single task card HTML (CROWN⁴.5 Phase 3: Compact 36-40px Design)
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
        const isDueSoon = task.due_date && this.isDueDateWithin(task.due_date, 1); // 1 day
        const isOverdue = task.due_date && this.isDueDateOverdue(task.due_date) && !isCompleted;

        // Assignee display
        const assigneeText = task.assignee_name || (task.assignee ? 'Assigned' : null);

        return `
            <div class="task-card ${isCompleted ? 'completed' : ''} ${isSyncing ? 'task-syncing' : ''} ${isOverdue ? 'overdue' : ''}" 
                 data-task-id="${task.id}"
                 data-status="${status}"
                 data-priority="${priority}"
                 style="animation-delay: ${index * 0.05}s;">
                
                <!-- Checkbox (36x36px click area with 22x22px visual) -->
                <div class="checkbox-wrapper">
                    <input type="checkbox" 
                           class="task-checkbox" 
                           ${isCompleted ? 'checked' : ''}
                           ${isSyncing ? 'disabled title="Task is syncing with server..."' : ''}
                           data-task-id="${task.id}"
                           aria-label="Mark task as ${isCompleted ? 'incomplete' : 'complete'}">
                </div>

                <!-- Task Title (Inline Editable) -->
                <div class="task-title ${isCompleted ? 'completed' : ''}" 
                     data-task-id="${task.id}"
                     role="button"
                     tabindex="0"
                     title="Click to edit task title">
                    ${this.escapeHtml(task.title || 'Untitled Task')}
                </div>

                <!-- Task Metadata (Compact Inline) -->
                <div class="task-metadata">
                    ${assigneeText ? `
                        <div class="task-assignee" 
                             data-task-id="${task.id}"
                             title="Click to change assignee">
                            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                            </svg>
                            ${this.escapeHtml(assigneeText)}
                        </div>
                    ` : `
                        <div class="task-assignee task-assignee-empty" 
                             data-task-id="${task.id}"
                             title="Click to assign">
                            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/>
                            </svg>
                            Assign
                        </div>
                    `}

                    ${task.due_date ? `
                        <div class="task-due-date ${isOverdue ? 'overdue' : ''} ${isDueSoon ? 'due-soon' : ''}" 
                             data-task-id="${task.id}"
                             title="Click to change due date">
                            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                            </svg>
                            ${this.formatDueDate(task.due_date)}
                        </div>
                    ` : `
                        <div class="task-due-date task-due-date-empty" 
                             data-task-id="${task.id}"
                             title="Click to set due date">
                            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                            </svg>
                            Due date
                        </div>
                    `}

                    ${task.labels && task.labels.length > 0 ? `
                        <div class="task-labels" data-task-id="${task.id}">
                            ${task.labels.slice(0, 2).map(label => `
                                <span class="task-label" data-label="${this.escapeHtml(label)}">
                                    ${this.escapeHtml(label)}
                                </span>
                            `).join('')}
                            ${task.labels.length > 2 ? `
                                <span class="task-label task-label-count" title="${task.labels.slice(2).join(', ')}">
                                    +${task.labels.length - 2}
                                </span>
                            ` : ''}
                        </div>
                    ` : `
                        <div class="task-labels task-labels-empty" 
                             data-task-id="${task.id}"
                             title="Click to add labels">
                            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/>
                            </svg>
                            Labels
                        </div>
                    `}

                    ${isSyncing ? `
                        <span class="syncing-badge">
                            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" class="spin-animation">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                            </svg>
                            Syncing
                        </span>
                    ` : ''}
                </div>

                <!-- Task Actions (Hidden until hover) -->
                <div class="task-actions">
                    <!-- Priority Quick Selector -->
                    <button class="task-action-btn priority-btn" 
                            data-task-id="${task.id}"
                            data-priority="${priority}"
                            title="Change priority (${priority})"
                            aria-label="Change priority">
                        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"/>
                        </svg>
                    </button>

                    <!-- Archive (Complete → Archive → Delete lifecycle) -->
                    ${isCompleted ? `
                        <button class="task-action-btn archive-btn" 
                                data-task-id="${task.id}"
                                title="Archive completed task"
                                aria-label="Archive task">
                            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/>
                            </svg>
                        </button>
                    ` : ''}

                    <!-- More Actions Menu -->
                    <button class="task-menu-trigger" 
                            data-task-id="${task.id}"
                            title="More actions"
                            aria-label="More actions"
                            aria-haspopup="true">
                        <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                            <circle cx="12" cy="12" r="2"/>
                            <circle cx="12" cy="5" r="2"/>
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

        // Update counter badges with emotional pulse animation
        Object.entries(counters).forEach(([key, count]) => {
            const badge = document.querySelector(`[data-counter="${key}"]`);
            if (badge) {
                const oldCount = parseInt(badge.textContent, 10) || 0;
                badge.textContent = count;
                
                // Add CROWN⁴.5 emotional pulse animation on counter change
                if (oldCount !== count && window.emotionalAnimations) {
                    window.emotionalAnimations.pulse(badge, {
                        emotion_cue: 'counter_update'
                    });
                } else {
                    // Fallback: simple CSS animation
                    badge.classList.remove('counter-pulse');
                    void badge.offsetWidth; // Trigger reflow
                    badge.classList.add('counter-pulse');
                }
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
            const serverChecksum = data.checksum; // CROWN⁴.5: Server sends checksum

            this.perf.sync_end = performance.now();
            const syncTime = this.perf.sync_end - this.perf.sync_start;
            console.log(`✅ Background sync completed in ${syncTime.toFixed(2)}ms (${serverTasks.length} tasks)`);

            // Update cache with server data
            await this.cache.saveTasks(serverTasks);
            
            // CROWN⁴.5: Store server checksum for future validation
            if (serverChecksum) {
                await this.cache.setMetadata('last_checksum', serverChecksum);
                console.log('📊 Stored server checksum:', serverChecksum.substring(0, 8));
            }
            
            // Update last sync timestamp
            this.lastSyncTimestamp = Date.now();
            await this.cache.setMetadata('last_sync_timestamp', this.lastSyncTimestamp);

            // CROWN⁴.5: If reconciliation was needed, re-render with server data
            if (this.needsReconciliation) {
                console.log('🔄 Reconciliation complete - re-rendering with server data');
                await this.renderTasks(serverTasks, { fromCache: false });
                this.needsReconciliation = false;
            }

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

// Export singleton
window.taskBootstrap = new TaskBootstrap();

console.log('🚀 CROWN⁴.5 TaskBootstrap loaded');
