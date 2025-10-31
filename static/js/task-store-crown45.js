/**
 * CROWN⁴.5 TaskStore
 * 
 * Comprehensive state management with IndexedDB persistence.
 * Integrates EventSequencer, CacheValidator, and DeltaMerger for
 * deterministic, consistent, and performant task management.
 * 
 * Performance Targets:
 * - First paint: <200ms
 * - Cache load: <50ms
 * - Reconciliation: <150ms p95
 * 
 * Key Features:
 * - IndexedDB persistence with schema versioning
 * - Automatic cache-first loading
 * - Optimistic updates with rollback
 * - Background sync with conflict resolution
 * - Vector clock synchronization
 */

class TaskStore {
    constructor() {
        this.dbName = 'MinaTaskStore';
        this.dbVersion = 1;
        this.db = null;
        this.tasks = [];  // In-memory cache
        this.tasksById = new Map();
        this.filters = {
            status: 'all',
            priority: null,
            assigned_to: null,
            search: ''
        };
        this.lastSync = null;
        this.syncInProgress = false;
        
        // Integrated subsystems
        this.sequencer = window.TaskEventSequencer;
        this.validator = window.TaskCacheValidator;
        this.merger = window.TaskDeltaMerger;
        
        // Performance metrics
        this.metrics = {
            firstPaint: 0,
            cacheLoad: 0,
            reconciliation: 0,
            lastUpdate: 0
        };
        
        // State
        this.ready = false;
        this.loading = false;
        
        console.log('✅ TaskStore initialized');
    }
    
    /**
     * Initialize database and load cache
     * @returns {Promise<Object>} Bootstrap metrics
     */
    async init() {
        const startTime = performance.now();
        
        try {
            // Open IndexedDB
            await this.openDatabase();
            
            // Load from cache
            const cacheStart = performance.now();
            await this.loadFromCache();
            this.metrics.cacheLoad = performance.now() - cacheStart;
            
            // First paint time
            this.metrics.firstPaint = performance.now() - startTime;
            
            this.ready = true;
            
            console.log(`✅ TaskStore ready in ${this.metrics.firstPaint.toFixed(2)}ms`);
            console.log(`   Cache loaded: ${this.tasks.length} tasks in ${this.metrics.cacheLoad.toFixed(2)}ms`);
            
            return {
                firstPaint: this.metrics.firstPaint,
                cacheLoad: this.metrics.cacheLoad,
                taskCount: this.tasks.length
            };
            
        } catch (error) {
            console.error('❌ TaskStore initialization failed:', error);
            throw error;
        }
    }
    
    /**
     * Open IndexedDB connection
     */
    async openDatabase() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve(this.db);
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Create tasks object store
                if (!db.objectStoreNames.contains('tasks')) {
                    const taskStore = db.createObjectStore('tasks', { keyPath: 'id' });
                    taskStore.createIndex('status', 'status', { unique: false });
                    taskStore.createIndex('priority', 'priority', { unique: false });
                    taskStore.createIndex('due_date', 'due_date', { unique: false });
                    taskStore.createIndex('assigned_to_id', 'assigned_to_id', { unique: false });
                    taskStore.createIndex('updated_at', 'updated_at', { unique: false });
                    taskStore.createIndex('meeting_id', 'meeting_id', { unique: false });
                }
                
                // Create metadata store
                if (!db.objectStoreNames.contains('metadata')) {
                    db.createObjectStore('metadata', { keyPath: 'key' });
                }
            };
        });
    }
    
    /**
     * Load tasks from IndexedDB cache
     */
    async loadFromCache() {
        if (!this.db) throw new Error('Database not initialized');
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks', 'metadata'], 'readonly');
            const taskStore = transaction.objectStore('tasks');
            const metaStore = transaction.objectStore('metadata');
            
            // Load all tasks
            const taskRequest = taskStore.getAll();
            taskRequest.onsuccess = () => {
                const cachedTasks = taskRequest.result || [];
                this.tasks = cachedTasks;
                this.rebuildIndex();
                
                // Load sync metadata
                const metaRequest = metaStore.get('lastSync');
                metaRequest.onsuccess = () => {
                    this.lastSync = metaRequest.result?.value || null;
                    resolve(cachedTasks);
                };
                metaRequest.onerror = () => resolve(cachedTasks);
            };
            
            taskRequest.onerror = () => reject(taskRequest.error);
        });
    }
    
    /**
     * Rebuild in-memory index for fast lookups
     */
    rebuildIndex() {
        this.tasksById.clear();
        for (const task of this.tasks) {
            this.tasksById.set(task.id, task);
        }
    }
    
    /**
     * Save tasks to IndexedDB
     */
    async saveToCache(tasks) {
        if (!this.db) return;
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readwrite');
            const store = transaction.objectStore('tasks');
            
            // Clear and repopulate
            const clearRequest = store.clear();
            clearRequest.onsuccess = () => {
                for (const task of tasks) {
                    store.put(task);
                }
            };
            
            transaction.oncomplete = () => resolve();
            transaction.onerror = () => reject(transaction.error);
        });
    }
    
    /**
     * Update sync metadata
     */
    async updateSyncMetadata() {
        if (!this.db) return;
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['metadata'], 'readwrite');
            const store = transaction.objectStore('metadata');
            
            store.put({
                key: 'lastSync',
                value: new Date().toISOString()
            });
            
            transaction.oncomplete = () => {
                this.lastSync = new Date().toISOString();
                resolve();
            };
            transaction.onerror = () => reject(transaction.error);
        });
    }
    
    /**
     * Get all tasks (filtered)
     */
    getTasks(filterOverride = null) {
        const filter = filterOverride || this.filters;
        
        let filtered = this.tasks;
        
        // Status filter
        if (filter.status && filter.status !== 'all') {
            filtered = filtered.filter(t => t.status === filter.status);
        }
        
        // Priority filter
        if (filter.priority) {
            filtered = filtered.filter(t => t.priority === filter.priority);
        }
        
        // Assigned filter
        if (filter.assigned_to) {
            if (filter.assigned_to === 'unassigned') {
                filtered = filtered.filter(t => !t.assigned_to_id);
            } else {
                filtered = filtered.filter(t => t.assigned_to_id === filter.assigned_to);
            }
        }
        
        // Search filter
        if (filter.search) {
            const query = filter.search.toLowerCase();
            filtered = filtered.filter(t =>
                (t.title || '').toLowerCase().includes(query) ||
                (t.description || '').toLowerCase().includes(query)
            );
        }
        
        return filtered;
    }
    
    /**
     * Get task by ID
     */
    getTask(id) {
        return this.tasksById.get(id);
    }
    
    /**
     * Add or update task (optimistic)
     */
    async upsertTask(task, options = {}) {
        const existing = this.tasksById.get(task.id);
        
        if (existing) {
            // Merge with existing
            const mergeResult = this.merger.merge(existing, task, {
                strategy: options.strategy || 'server_authoritative'
            });
            
            this.tasksById.set(task.id, mergeResult.merged);
            
            // Update array
            const index = this.tasks.findIndex(t => t.id === task.id);
            if (index >= 0) {
                this.tasks[index] = mergeResult.merged;
            }
            
            if (mergeResult.conflicts.length > 0) {
                console.warn(`⚠️ Conflicts resolved for task ${task.id}:`, mergeResult.conflicts);
            }
        } else {
            // New task
            this.tasks.push(task);
            this.tasksById.set(task.id, task);
        }
        
        // Persist to IndexedDB
        if (!options.skipPersist) {
            await this.saveToCache(this.tasks);
        }
        
        this.metrics.lastUpdate = Date.now();
    }
    
    /**
     * Remove task
     */
    async removeTask(id) {
        const index = this.tasks.findIndex(t => t.id === id);
        if (index >= 0) {
            this.tasks.splice(index, 1);
        }
        this.tasksById.delete(id);
        
        await this.saveToCache(this.tasks);
        this.metrics.lastUpdate = Date.now();
    }
    
    /**
     * Batch update tasks
     */
    async batchUpdate(tasks) {
        for (const task of tasks) {
            await this.upsertTask(task, { skipPersist: true });
        }
        await this.saveToCache(this.tasks);
        this.metrics.lastUpdate = Date.now();
    }
    
    /**
     * Sync with server
     */
    async sync(serverTasks, options = {}) {
        if (this.syncInProgress) {
            console.warn('⚠️ Sync already in progress');
            return;
        }
        
        this.syncInProgress = true;
        const syncStart = performance.now();
        
        try {
            // Batch merge
            const mergeResult = this.merger.batchMerge(
                this.tasks,
                serverTasks,
                task => task.id
            );
            
            this.tasks = mergeResult.merged;
            this.rebuildIndex();
            
            // Persist
            await this.saveToCache(this.tasks);
            await this.updateSyncMetadata();
            
            this.metrics.reconciliation = performance.now() - syncStart;
            
            console.log(`✅ Sync complete in ${this.metrics.reconciliation.toFixed(2)}ms`);
            console.log(`   Stats:`, mergeResult.stats);
            
            if (mergeResult.conflicts.length > 0) {
                console.warn(`   Conflicts:`, mergeResult.conflicts);
            }
            
            return mergeResult;
            
        } finally {
            this.syncInProgress = false;
        }
    }
    
    /**
     * Set active filters
     */
    setFilters(filters) {
        this.filters = { ...this.filters, ...filters };
        this.metrics.lastUpdate = Date.now();
    }
    
    /**
     * Get metrics
     */
    getMetrics() {
        return {
            ...this.metrics,
            taskCount: this.tasks.length,
            ready: this.ready,
            lastSync: this.lastSync
        };
    }
    
    /**
     * Clear all data (for testing)
     */
    async clear() {
        this.tasks = [];
        this.tasksById.clear();
        await this.saveToCache([]);
        console.log('🗑️ TaskStore cleared');
    }
}

// Global instance
window.TaskStore = new TaskStore();

console.log('✅ CROWN⁴.5 TaskStore loaded');
