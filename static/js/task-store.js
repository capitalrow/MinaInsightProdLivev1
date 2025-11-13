/**
 * CROWN⁴.5 TaskStore
 * Central task state management with IndexedDB persistence, delta merging, and conflict resolution
 * 
 * Features:
 * - Field-level delta merge using (updated_at, actor_rank) for server authority
 * - Optimistic updates with rollback on conflict
 * - Vector clock support for distributed ordering
 * - Cache-first architecture with <200ms bootstrap
 */

class TaskStore {
    constructor(cacheManager, cacheValidator) {
        this.cache = cacheManager;
        this.validator = cacheValidator;
        this.tasks = new Map(); // In-memory task map (id -> task)
        this.listeners = new Set(); // Change listeners
        this.userId = null;
        
        // Actor rank for conflict resolution (server > user)
        this.ACTOR_RANK = {
            server: 100,
            user: 50,
            ai_proposal: 25
        };
    }
    
    /**
     * Initialize store with user ID
     */
    async init(userId) {
        this.userId = userId;
        console.log(`🏪 TaskStore initialized for user ${userId}`);
    }
    
    /**
     * Bootstrap store from IndexedDB cache
     * CROWN⁴.5: Target <200ms for 100 tasks
     */
    async bootstrap() {
        const startTime = performance.now();
        
        try {
            // Load tasks from IndexedDB cache
            const cached = await this.cache.getCachedTasksWithChecksum();
            
            if (cached.data && cached.data.length > 0) {
                // Hydrate in-memory map
                cached.data.forEach(task => {
                    this.tasks.set(task.id, task);
                });
                
                const bootstrapTime = Math.round(performance.now() - startTime);
                console.log(`⚡ TaskStore bootstrapped: ${cached.data.length} tasks in ${bootstrapTime}ms`);
                console.log(`   Cache checksum: ${cached.checksum?.substring(0, 8)}...`);
                console.log(`   Last event ID: ${cached.last_event_id}`);
                
                this._notifyListeners({ type: 'bootstrap', tasks: Array.from(this.tasks.values()) });
                
                return {
                    success: true,
                    count: cached.data.length,
                    checksum: cached.checksum,
                    last_event_id: cached.last_event_id,
                    cached_at: cached.cached_at,
                    bootstrap_time: bootstrapTime
                };
            } else {
                console.log('📦 No cached tasks found, starting with empty store');
                return {
                    success: true,
                    count: 0,
                    checksum: null,
                    last_event_id: null,
                    cached_at: null,
                    bootstrap_time: Math.round(performance.now() - startTime)
                };
            }
        } catch (error) {
            console.error('❌ Bootstrap failed:', error);
            return {
                success: false,
                error: error.message,
                bootstrap_time: Math.round(performance.now() - startTime)
            };
        }
    }
    
    /**
     * Sync store with server data using delta merge
     * @param {Array} serverTasks - Tasks from server
     * @param {string} serverChecksum - Server data checksum
     * @param {number} lastEventId - Last event ID for deterministic replay
     * @returns {Object} - Sync result with delta summary
     */
    async syncWithServer(serverTasks, serverChecksum, lastEventId = null) {
        const startTime = performance.now();
        
        try {
            const cachedTasks = Array.from(this.tasks.values());
            
            // Validate checksums and calculate delta
            const validation = await this.validator.validate({
                cachedData: cachedTasks,
                serverData: serverTasks,
                key: 'tasks',
                persistChecksum: true
            });
            
            if (validation.isValid) {
                console.log('✅ Tasks in sync, no delta merge needed');
                return {
                    success: true,
                    drift: false,
                    delta: null,
                    sync_time: Math.round(performance.now() - startTime)
                };
            }
            
            // Calculate delta (added, modified, removed)
            const delta = this.validator.calculateDelta(cachedTasks, serverTasks, 'id');
            const summary = this.validator.getDeltaSummary(delta);
            
            console.log(`🔄 Applying delta merge: ${summary}`);
            
            // Apply delta with field-level merge for conflicts
            const mergeResult = await this._applyDeltaWithMerge(delta);
            
            // Persist merged tasks to IndexedDB
            const mergedTasks = Array.from(this.tasks.values());
            await this.cache.cacheTasksWithChecksum(mergedTasks, serverChecksum, lastEventId);
            
            const syncTime = Math.round(performance.now() - startTime);
            console.log(`✅ Delta merge complete in ${syncTime}ms`);
            
            this._notifyListeners({ type: 'sync', delta, mergeResult });
            
            return {
                success: true,
                drift: true,
                delta,
                summary,
                mergeResult,
                sync_time: syncTime
            };
        } catch (error) {
            console.error('❌ Sync failed:', error);
            return {
                success: false,
                error: error.message,
                sync_time: Math.round(performance.now() - startTime)
            };
        }
    }
    
    /**
     * Apply delta with field-level conflict resolution
     * Uses (updated_at, actor_rank) to determine authority
     * @private
     */
    async _applyDeltaWithMerge(delta) {
        const result = {
            added: 0,
            updated: 0,
            removed: 0,
            conflicts: 0
        };
        
        // Remove deleted tasks
        for (const task of delta.removed) {
            if (this.tasks.has(task.id)) {
                this.tasks.delete(task.id);
                result.removed++;
            }
        }
        
        // Add new tasks
        for (const task of delta.added) {
            this.tasks.set(task.id, task);
            result.added++;
        }
        
        // Merge modified tasks (field-level conflict resolution)
        for (const { id, cached, server } of delta.modified) {
            const merged = this._mergeTaskFields(cached, server);
            
            if (merged.hadConflict) {
                result.conflicts++;
                console.warn(`⚠️ Resolved conflict for task ${id}:`, merged.conflicts);
            }
            
            this.tasks.set(id, merged.task);
            result.updated++;
        }
        
        return result;
    }
    
    /**
     * Merge task fields with conflict resolution using (updated_at, actor_rank)
     * CROWN⁴.5: Server authority via actor rank precedence
     * @private
     */
    _mergeTaskFields(cached, server) {
        const merged = {}; // Build merged task field-by-field
        const conflicts = [];
        let hadConflict = false;
        
        // Get actor ranks (default to server rank if not specified)
        const cachedRank = cached._actor_rank || this.ACTOR_RANK.user;
        const serverRank = server._actor_rank || this.ACTOR_RANK.server;
        
        // Compare updated_at timestamps
        const cachedTime = new Date(cached.updated_at || 0).getTime();
        const serverTime = new Date(server.updated_at || 0).getTime();
        
        // All task fields to compare (comprehensive field-level merge)
        const allFields = new Set([
            ...Object.keys(cached),
            ...Object.keys(server)
        ]);
        
        // Filter out internal/metadata fields that shouldn't be compared
        const skipFields = ['_optimistic_update', '_provisional', '_updated_at', '_cached_at', '_actor_rank'];
        
        for (const field of allFields) {
            if (skipFields.includes(field)) continue;
            
            const cachedValue = cached[field];
            const serverValue = server[field];
            
            // If values match, no conflict
            if (JSON.stringify(cachedValue) === JSON.stringify(serverValue)) {
                merged[field] = serverValue;
                continue;
            }
            
            // Conflict detected - apply (updated_at, actor_rank) authority rules
            let winner = 'server';
            let chosenValue = serverValue;
            
            // Rule 1: Higher actor rank wins
            if (cachedRank > serverRank) {
                winner = 'cached';
                chosenValue = cachedValue;
            } else if (serverRank > cachedRank) {
                winner = 'server';
                chosenValue = serverValue;
            } else {
                // Rule 2: If ranks equal, newer updated_at wins
                if (cachedTime > serverTime) {
                    winner = 'cached';
                    chosenValue = cachedValue;
                } else {
                    winner = 'server';
                    chosenValue = serverValue;
                }
            }
            
            // Log conflict
            if (cachedValue !== undefined && serverValue !== undefined) {
                hadConflict = true;
                conflicts.push({
                    field,
                    cached: cachedValue,
                    cached_rank: cachedRank,
                    cached_time: new Date(cachedTime).toISOString(),
                    server: serverValue,
                    server_rank: serverRank,
                    server_time: new Date(serverTime).toISOString(),
                    resolution: winner
                });
            }
            
            merged[field] = chosenValue;
        }
        
        return { task: merged, hadConflict, conflicts };
    }
    
    /**
     * Get task by ID
     */
    getTask(taskId) {
        return this.tasks.get(taskId);
    }
    
    /**
     * Get all tasks
     */
    getAllTasks() {
        return Array.from(this.tasks.values());
    }
    
    /**
     * Get filtered tasks
     */
    getFilteredTasks(filter = {}) {
        let tasks = Array.from(this.tasks.values());
        
        // Apply status filter
        if (filter.status) {
            const statuses = Array.isArray(filter.status) ? filter.status : [filter.status];
            tasks = tasks.filter(t => statuses.includes(t.status));
        }
        
        // Apply priority filter
        if (filter.priority) {
            const priorities = Array.isArray(filter.priority) ? filter.priority : [filter.priority];
            tasks = tasks.filter(t => priorities.includes(t.priority));
        }
        
        // Apply search query
        if (filter.query) {
            const query = filter.query.toLowerCase();
            tasks = tasks.filter(t =>
                t.title?.toLowerCase().includes(query) ||
                t.description?.toLowerCase().includes(query)
            );
        }
        
        // Filter out soft-deleted tasks by default
        if (!filter.include_deleted) {
            tasks = tasks.filter(t => !t.deleted_at);
        }
        
        return tasks;
    }
    
    /**
     * Create task optimistically
     * @param {Object} taskData - Task data
     * @returns {Object} - Created task with provisional ID
     */
    async createTaskOptimistic(taskData) {
        // Generate provisional client-side ID
        const provisionalId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        const task = {
            id: provisionalId,
            ...taskData,
            _optimistic_update: true,
            _provisional: true,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
        };
        
        // Add to in-memory store
        this.tasks.set(provisionalId, task);
        
        // Persist optimistically to IndexedDB
        await this.cache.updateTask(provisionalId, task);
        
        this._notifyListeners({ type: 'create_optimistic', task });
        
        console.log(`✨ Created optimistic task: ${provisionalId}`);
        return task;
    }
    
    /**
     * Update task optimistically
     * @param {number|string} taskId - Task ID
     * @param {Object} updates - Fields to update
     * @returns {Object} - Updated task
     */
    async updateTaskOptimistic(taskId, updates) {
        const task = this.tasks.get(taskId);
        if (!task) {
            throw new Error(`Task ${taskId} not found`);
        }
        
        const updated = {
            ...task,
            ...updates,
            _optimistic_update: true,
            updated_at: new Date().toISOString()
        };
        
        // Update in-memory store
        this.tasks.set(taskId, updated);
        
        // Persist optimistically to IndexedDB
        await this.cache.updateTask(taskId, updated);
        
        this._notifyListeners({ type: 'update_optimistic', task: updated });
        
        console.log(`✨ Updated task optimistically: ${taskId}`);
        return updated;
    }
    
    /**
     * Confirm optimistic task with server response
     * @param {string} provisionalId - Provisional client ID
     * @param {Object} serverTask - Confirmed task from server
     */
    async confirmTask(provisionalId, serverTask) {
        // Remove provisional task
        this.tasks.delete(provisionalId);
        
        // Add confirmed task with real ID
        this.tasks.set(serverTask.id, serverTask);
        
        // Update IndexedDB
        await this.cache.delete(this.cache.STORES.TASKS, provisionalId);
        await this.cache.put(this.cache.STORES.TASKS, serverTask);
        
        this._notifyListeners({ type: 'confirm', provisionalId, task: serverTask });
        
        console.log(`✅ Confirmed task: ${provisionalId} → ${serverTask.id}`);
    }
    
    /**
     * Rollback optimistic update on failure
     * @param {number|string} taskId - Task ID
     * @param {Object} originalTask - Original task state before optimistic update
     */
    async rollbackTask(taskId, originalTask) {
        if (originalTask) {
            this.tasks.set(taskId, originalTask);
            await this.cache.put(this.cache.STORES.TASKS, originalTask);
        } else {
            this.tasks.delete(taskId);
            await this.cache.delete(this.cache.STORES.TASKS, taskId);
        }
        
        this._notifyListeners({ type: 'rollback', taskId });
        
        console.warn(`↩️  Rolled back task: ${taskId}`);
    }
    
    /**
     * Subscribe to task changes
     * @param {Function} callback - Listener callback
     * @returns {Function} - Unsubscribe function
     */
    subscribe(callback) {
        this.listeners.add(callback);
        return () => this.listeners.delete(callback);
    }
    
    /**
     * Notify all listeners of changes
     * @private
     */
    _notifyListeners(event) {
        for (const listener of this.listeners) {
            try {
                listener(event);
            } catch (error) {
                console.error('Listener error:', error);
            }
        }
    }
    
    /**
     * Get store statistics
     */
    getStats() {
        const tasks = Array.from(this.tasks.values());
        const optimistic = tasks.filter(t => t._optimistic_update).length;
        const provisional = tasks.filter(t => t._provisional).length;
        
        return {
            total: tasks.length,
            optimistic,
            provisional,
            synced: tasks.length - optimistic - provisional
        };
    }
    
    /**
     * Clear all tasks (testing/debugging only)
     */
    async clear() {
        this.tasks.clear();
        await this.cache.clear(this.cache.STORES.TASKS);
        await this.cache.setMetadata('tasks_checksum', null);
        await this.cache.setMetadata('tasks_last_event_id', null);
        console.log('🧹 TaskStore cleared');
    }
}

// Initialize global singleton when cacheManager is ready
window.taskStore = null;

// Initialize TaskStore when cacheManager promise resolves
(async function initializeTaskStore() {
    try {
        console.log('[TaskStore] Waiting for cacheManager to be ready...');
        
        // Wait for cacheManager to initialize
        await window.cacheManagerReady;
        
        console.log('[TaskStore] cacheManager ready, checking dependencies...');
        
        // Check if cacheValidator is available
        if (!window.cacheValidator) {
            console.warn('⚠️ [TaskStore] cacheValidator not available, retrying in 100ms...');
            setTimeout(initializeTaskStore, 100);
            return;
        }
        
        // Create TaskStore instance
        window.taskStore = new TaskStore(window.cacheManager, window.cacheValidator);
        console.log('✅ [TaskStore] TaskStore instance created');
        
        // Fire event to notify dependent modules
        window.dispatchEvent(new CustomEvent('taskStoreReady', { 
            detail: { taskStore: window.taskStore } 
        }));
        console.log('📡 [TaskStore] taskStoreReady event fired');
        
    } catch (error) {
        console.error('❌ [TaskStore] Failed to initialize:', error);
    }
})();
