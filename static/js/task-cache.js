/**
 * CROWN⁴.5 Task Cache Layer - IndexedDB Implementation
 * Provides cache-first architecture with <200ms first paint, offline queue,
 * vector clock ordering, and deterministic event replay.
 */

class VectorClock {
    /**
     * Create normalized vector clock for deterministic ordering
     * @param {Object} clocks - { nodeId: counter }
     */
    constructor(clocks = {}) {
        this.clocks = clocks;
    }

    /**
     * Increment local node counter
     * @param {string} nodeId
     */
    increment(nodeId) {
        this.clocks[nodeId] = (this.clocks[nodeId] || 0) + 1;
        return this;
    }

    /**
     * Merge with another vector clock (take max of each counter)
     * @param {VectorClock} other
     * @returns {VectorClock} New merged clock
     */
    merge(other) {
        const merged = { ...this.clocks };
        for (const [node, counter] of Object.entries(other.clocks)) {
            merged[node] = Math.max(merged[node] || 0, counter);
        }
        return new VectorClock(merged);
    }

    /**
     * Compare with another vector clock for deterministic ordering
     * @param {VectorClock} other
     * @returns {number} -1 if this < other, 0 if concurrent, 1 if this > other
     */
    compare(other) {
        const allNodes = new Set([
            ...Object.keys(this.clocks),
            ...Object.keys(other.clocks)
        ]);

        let thisGreater = false;
        let otherGreater = false;

        for (const node of allNodes) {
            const thisCount = this.clocks[node] || 0;
            const otherCount = other.clocks[node] || 0;

            if (thisCount > otherCount) thisGreater = true;
            if (otherCount > thisCount) otherGreater = true;
        }

        if (thisGreater && !otherGreater) return 1;  // this dominates
        if (otherGreater && !thisGreater) return -1; // other dominates
        return 0; // concurrent
    }

    /**
     * Check if this clock dominates (is greater than) another
     * @param {VectorClock} other
     * @returns {boolean}
     */
    dominates(other) {
        return this.compare(other) === 1;
    }

    /**
     * Serialize to normalized tuple for storage
     * @returns {Array<[string, number]>}
     */
    toTuple() {
        return Object.entries(this.clocks).sort((a, b) => a[0].localeCompare(b[0]));
    }

    /**
     * Create from stored tuple
     * @param {Array<[string, number]>} tuple
     * @returns {VectorClock}
     */
    static fromTuple(tuple) {
        const clocks = {};
        for (const [node, counter] of tuple) {
            clocks[node] = counter;
        }
        return new VectorClock(clocks);
    }

    /**
     * Clone this vector clock
     * @returns {VectorClock}
     */
    clone() {
        return new VectorClock({ ...this.clocks });
    }

    toString() {
        return JSON.stringify(this.toTuple());
    }
}

class TaskCache {
    constructor() {
        this.db = null;
        this.dbName = 'MinaTasksDB';
        this.version = 3; // Incremented for temp_tasks store addition
        this.ready = false;
        this.initPromise = null;
        this.nodeId = this._getOrCreateNodeId();
    }

    /**
     * Get or create unique node ID for this client
     * @returns {string}
     */
    _getOrCreateNodeId() {
        let nodeId = localStorage.getItem('mina_node_id');
        if (!nodeId) {
            nodeId = `node_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            localStorage.setItem('mina_node_id', nodeId);
        }
        return nodeId;
    }

    /**
     * Initialize IndexedDB database with CROWN⁴.5 schema
     * @returns {Promise<IDBDatabase>}
     */
    async init() {
        if (this.ready) return this.db;
        if (this.initPromise) return this.initPromise;

        this.initPromise = new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.version);

            request.onerror = () => {
                console.error('❌ IndexedDB failed to open:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                this.ready = true;
                console.log('✅ TaskCache IndexedDB initialized');
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                console.log('🔧 Creating IndexedDB schema for CROWN⁴.5...');

                // Store 1: Tasks - Main task data with CROWN⁴.5 fields (numeric IDs only)
                if (!db.objectStoreNames.contains('tasks')) {
                    const taskStore = db.createObjectStore('tasks', { keyPath: 'id' });
                    taskStore.createIndex('status', 'status', { unique: false });
                    taskStore.createIndex('priority', 'priority', { unique: false });
                    taskStore.createIndex('created_at', 'created_at', { unique: false });
                    taskStore.createIndex('updated_at', 'updated_at', { unique: false });
                    taskStore.createIndex('reconciliation_status', 'reconciliation_status', { unique: false });
                    taskStore.createIndex('snoozed_until', 'snoozed_until', { unique: false });
                    taskStore.createIndex('due_date', 'due_date', { unique: false });
                    console.log('  ✓ Created "tasks" store');
                }

                // Store 2: Temporary Tasks - Optimistic creates with string IDs (temp_*)
                // Persists temp tasks until server responds with real numeric ID
                // Survives page refreshes and offline mode
                if (!db.objectStoreNames.contains('temp_tasks')) {
                    const tempTaskStore = db.createObjectStore('temp_tasks', { keyPath: 'id' });
                    tempTaskStore.createIndex('created_at', 'created_at', { unique: false });
                    tempTaskStore.createIndex('status', 'status', { unique: false });
                    console.log('  ✓ Created "temp_tasks" store (for optimistic UI persistence)');
                }

                // Store 3: Event Ledger - Stores all events with vector clocks
                if (!db.objectStoreNames.contains('events')) {
                    const eventStore = db.createObjectStore('events', { keyPath: 'id', autoIncrement: true });
                    eventStore.createIndex('event_type', 'event_type', { unique: false });
                    eventStore.createIndex('task_id', 'task_id', { unique: false });
                    eventStore.createIndex('timestamp', 'timestamp', { unique: false });
                    eventStore.createIndex('vector_clock', 'vector_clock', { unique: false });
                    eventStore.createIndex('sync_status', 'sync_status', { unique: false }); // pending, synced, failed
                    console.log('  ✓ Created "events" store');
                }

                // Store 3: Offline Queue - Pending operations when offline
                if (!db.objectStoreNames.contains('offline_queue')) {
                    const queueStore = db.createObjectStore('offline_queue', { keyPath: 'id', autoIncrement: true });
                    queueStore.createIndex('timestamp', 'timestamp', { unique: false });
                    queueStore.createIndex('vector_clock', 'vector_clock', { unique: false });
                    queueStore.createIndex('priority', 'priority', { unique: false });
                    console.log('  ✓ Created "offline_queue" store');
                }

                // Store 4: Compaction/Archival - Pruned old events to prevent unbounded growth
                if (!db.objectStoreNames.contains('compaction')) {
                    const compactionStore = db.createObjectStore('compaction', { keyPath: 'id', autoIncrement: true });
                    compactionStore.createIndex('compaction_date', 'compaction_date', { unique: false });
                    compactionStore.createIndex('event_count', 'event_count', { unique: false });
                    console.log('  ✓ Created "compaction" store');
                }

                // Store 5: Metadata - Cache metadata, sync state, vector clocks
                if (!db.objectStoreNames.contains('metadata')) {
                    db.createObjectStore('metadata', { keyPath: 'key' });
                    console.log('  ✓ Created "metadata" store');
                }

                // Store 6: View State - Filters, sort, scroll position, toast state
                if (!db.objectStoreNames.contains('view_state')) {
                    db.createObjectStore('view_state', { keyPath: 'key' });
                    console.log('  ✓ Created "view_state" store');
                }

                console.log('✅ IndexedDB schema created successfully');
            };
        });

        return this.initPromise;
    }

    /**
     * ENTERPRISE-GRADE: Save pending operation to offline_queue
     * Supports all operation types (create/update/delete)
     * CRITICAL: Persists FULL operation object including all metadata
     */
    async savePendingOperation(opId, operation) {
        await this.init();
        
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction('offline_queue', 'readwrite');
            const store = tx.objectStore('offline_queue');
            
            // CRITICAL FIX: Persist the COMPLETE operation object
            // This includes task (for rollback), previous (for update rollback), queueId (for cleanup)
            const queueItem = {
                operation_id: opId,
                // Core operation fields
                type: operation.type,
                data: operation.data,
                task_id: operation.taskId,
                temp_id: operation.tempId,
                timestamp: operation.timestamp || Date.now(),
                // Failure tracking
                failed: operation.failed || false,
                last_error: operation.lastError,
                retry_count: operation.retryCount || 0,
                // Rollback metadata (CRITICAL for post-refresh operations)
                task: operation.task,  // Full optimistic task for create rollback
                previous: operation.previous,  // Previous state for update rollback
                updates: operation.updates,  // Update data
                queue_id: operation.queueId  // Offline queue reference for cleanup
            };
            
            const request = store.put(queueItem);
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * ENTERPRISE-GRADE: Get all pending operations from offline_queue
     * Returns map of operation_id -> operation for rehydration
     * CRITICAL: Restores FULL operation object with all metadata
     */
    async getAllPendingOperations() {
        await this.init();
        
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction('offline_queue', 'readonly');
            const store = tx.objectStore('offline_queue');
            const request = store.getAll();
            
            request.onsuccess = () => {
                const operations = new Map();
                const items = request.result || [];
                
                for (const item of items) {
                    if (item.operation_id) {
                        // CRITICAL FIX: Restore COMPLETE operation object
                        // Includes all metadata needed for rollback, reconciliation, and cleanup
                        operations.set(item.operation_id, {
                            // Core operation fields
                            type: item.type,
                            data: item.data,
                            taskId: item.task_id,
                            tempId: item.temp_id,
                            timestamp: item.timestamp || Date.now(),
                            // Failure tracking
                            failed: item.failed || false,
                            lastError: item.last_error,
                            retryCount: item.retry_count || 0,
                            // Rollback metadata (CRITICAL for post-refresh operations)
                            task: item.task,  // Full optimistic task for create rollback
                            previous: item.previous,  // Previous state for update rollback
                            updates: item.updates,  // Update data
                            queueId: item.queue_id  // Offline queue reference for cleanup
                        });
                    }
                }
                
                console.log(`✅ [Offline-First] Loaded ${operations.size} pending operations from IndexedDB`);
                resolve(operations);
            };
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * ENTERPRISE-GRADE: Remove pending operation from offline_queue
     * Called after successful sync
     */
    async removePendingOperation(opId) {
        await this.init();
        
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction('offline_queue', 'readwrite');
            const store = tx.objectStore('offline_queue');
            
            // Find and delete by operation_id (not primary key)
            const request = store.openCursor();
            
            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    if (cursor.value.operation_id === opId) {
                        cursor.delete();
                        resolve();
                    } else {
                        cursor.continue();
                    }
                } else {
                    resolve(); // Not found, that's okay
                }
            };
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * ENTERPRISE-GRADE: Clean orphaned temp tasks (safe, prevents data loss)
     * Only removes temp IDs that are:
     * 1. NOT in the offline queue (already synced/failed)
     * 2. Older than 10 minutes (safe threshold for failed operations)
     * This preserves legitimate offline tasks that are still pending sync.
     * Updated to check temp_tasks store (v3 schema)
     * @returns {Promise<number>} Number of tasks removed
     */
    async cleanOrphanedTempTasks() {
        await this.init();
        
        console.log('🧹 [Cleanup] Starting cleanOrphanedTempTasks()...');
        
        return new Promise(async (resolve, reject) => {
            try {
                // Get all temp tasks from temp_tasks store and queued operations
                const transaction = this.db.transaction(['temp_tasks', 'offline_queue'], 'readonly');
                const tempTaskStore = transaction.objectStore('temp_tasks');
                const queueStore = transaction.objectStore('offline_queue');
                
                const tempTasksRequest = tempTaskStore.getAll();
                const queueRequest = queueStore.getAll();
                
                await Promise.all([
                    new Promise(res => tempTasksRequest.onsuccess = res),
                    new Promise(res => queueRequest.onsuccess = res)
                ]);
                
                const allTempTasks = tempTasksRequest.result || [];
                const queuedOps = queueRequest.result || [];
                
                console.log(`🧹 [Cleanup] Found ${allTempTasks.length} temp tasks and ${queuedOps.length} queued operations`);
                if (allTempTasks.length > 0) {
                    console.log('🧹 [Cleanup] Temp tasks:', allTempTasks.map(t => ({ id: t.id, created_at: t.created_at, title: t.title })));
                }
                if (queuedOps.length > 0) {
                    console.log('🧹 [Cleanup] Queued operations:', queuedOps.map(op => ({ type: op.type, temp_id: op.temp_id, data_temp_id: op.data?.temp_id })));
                }
                
                // Build set of temp IDs that are in the offline queue (should NOT be deleted)
                const queuedTempIds = new Set();
                queuedOps.forEach(op => {
                    if (op.temp_id) queuedTempIds.add(op.temp_id);
                    if (op.data && op.data.temp_id) queuedTempIds.add(op.data.temp_id);
                });
                
                console.log(`🧹 [Cleanup] Found ${queuedTempIds.size} temp IDs in offline queue`);
                
                // Find orphaned temp tasks (older than 10 minutes AND not in queue)
                const now = Date.now();
                const SAFE_THRESHOLD_MS = 10 * 60 * 1000; // 10 minutes
                const orphanedTempIds = [];
                
                allTempTasks.forEach(task => {
                    console.log(`🧹 [Cleanup] Evaluating temp task: ${task.id} (created: ${task.created_at})`);
                    
                    // Skip if in offline queue (legitimate pending task)
                    if (queuedTempIds.has(task.id)) {
                        console.log(`✅ [Cleanup] Preserving queued temp task: ${task.id}`);
                        return;
                    }
                    
                    // CRITICAL: Validate created_at timestamp (preserve if invalid to be safe)
                    // Reject: null, undefined, 0, empty string, non-ISO strings
                    if (!task.created_at || task.created_at === 0 || task.created_at === '0') {
                        console.log(`✅ Preserving temp task with missing/invalid created_at: ${task.id}`);
                        return;
                    }
                    
                    // Parse timestamp and validate
                    const createdTimestamp = new Date(task.created_at).getTime();
                    
                    // CRITICAL: Skip if timestamp is NaN or epoch/negative
                    if (Number.isNaN(createdTimestamp) || createdTimestamp <= 0) {
                        console.log(`✅ Preserving temp task with invalid timestamp: ${task.id}`);
                        return;
                    }
                    
                    // Calculate age from valid timestamp
                    const taskAge = now - createdTimestamp;
                    
                    // CRITICAL: Sanity check - if age is negative or unreasonably large (>1 year), preserve
                    const ONE_YEAR_MS = 365 * 24 * 60 * 60 * 1000;
                    if (taskAge < 0 || taskAge > ONE_YEAR_MS) {
                        console.log(`✅ Preserving temp task with suspicious age: ${task.id} (age: ${taskAge}ms)`);
                        return;
                    }
                    
                    if (taskAge < SAFE_THRESHOLD_MS) {
                        console.log(`⏳ Preserving recent temp task: ${task.id} (age: ${Math.round(taskAge/1000)}s)`);
                        return;
                    }
                    
                    // This is a confirmed orphaned temp task - safe to remove
                    console.log(`🗑️ Orphaned temp task confirmed for deletion: ${task.id} (age: ${Math.round(taskAge/1000)}s, not in queue)`);
                    orphanedTempIds.push(task.id);
                });
                
                // Delete orphaned temp tasks from temp_tasks store
                if (orphanedTempIds.length > 0) {
                    const deleteTransaction = this.db.transaction(['temp_tasks'], 'readwrite');
                    const deleteStore = deleteTransaction.objectStore('temp_tasks');
                    
                    orphanedTempIds.forEach(tempId => {
                        deleteStore.delete(tempId);
                        console.log(`🧹 Removing orphaned temp task: ${tempId}`);
                    });
                    
                    deleteTransaction.oncomplete = () => {
                        console.log(`✅ Cache hygiene: Removed ${orphanedTempIds.length} orphaned temp tasks from temp_tasks store`);
                        resolve(orphanedTempIds.length);
                    };
                    deleteTransaction.onerror = () => reject(deleteTransaction.error);
                } else {
                    console.log('✅ No orphaned temp tasks found in temp_tasks store');
                    resolve(0);
                }
                
            } catch (error) {
                console.error('❌ Failed to clean orphaned temp tasks:', error);
                reject(error);
            }
        });
    }

    /**
     * Validate task ID before operations (ENTERPRISE-GRADE)
     * Prevents temp IDs from causing database errors
     * @param {any} taskId
     * @returns {boolean}
     */
    static isValidTaskId(taskId) {
        // Valid IDs are integers (from database) or null (for new tasks)
        if (taskId === null || taskId === undefined) return true;
        
        // Numeric IDs are valid
        if (typeof taskId === 'number' && Number.isInteger(taskId) && taskId > 0) {
            return true;
        }
        
        // String representation of numbers are valid
        if (typeof taskId === 'string' && /^\d+$/.test(taskId)) {
            return true;
        }
        
        // Temp IDs are NOT valid for server operations (flagged for reconciliation)
        if (typeof taskId === 'string' && taskId.startsWith('temp_')) {
            console.warn(`⚠️ Temp ID detected: ${taskId} - needs reconciliation`);
            return false;
        }
        
        return false;
    }

    /**
     * Sanitize task for server sync by removing cache-internal fields (CROWN⁴.5)
     * @param {Object} task - Task object
     * @returns {Object} - Sanitized copy without internal fields
     */
    static sanitizeForSync(task) {
        // Handle falsy inputs (e.g., task_delete has no data payload)
        if (!task) {
            return task;
        }
        
        const { _checksum, _cached_at, _reconciled_at, _reconciliation_strategy, ...sanitized } = task;
        return sanitized;
    }

    /**
     * Get all tasks from cache (cache-first)
     * ENTERPRISE-GRADE: Returns ALL tasks from both 'tasks' and 'temp_tasks' stores
     * Temp tasks are marked with syncing flag for UI rendering
     * Survives page refresh - temp tasks persist until server confirms
     * @returns {Promise<Array>}
     */
    async getAllTasks() {
        await this.init();
        
        // Read from both stores in parallel for performance
        const [realTasks, tempTasks] = await Promise.all([
            // Get all real tasks (numeric IDs)
            new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['tasks'], 'readonly');
                const store = transaction.objectStore('tasks');
                const request = store.getAll();
                request.onsuccess = () => resolve(request.result || []);
                request.onerror = () => reject(request.error);
            }),
            // Get all temp tasks (string IDs)
            new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['temp_tasks'], 'readonly');
                const store = transaction.objectStore('temp_tasks');
                const request = store.getAll();
                request.onsuccess = () => resolve(request.result || []);
                request.onerror = () => reject(request.error);
            })
        ]);
        
        // Mark temp tasks with syncing flag for UI rendering
        tempTasks.forEach(task => {
            task._is_syncing = true;
            task._sync_status = 'pending';
            task._temp = true;
        });
        
        // Merge real tasks and temp tasks
        const allTasks = [...realTasks, ...tempTasks];
        
        // Log temp tasks for debugging
        if (tempTasks.length > 0) {
            console.log(`📦 Loaded ${tempTasks.length} temp task(s) from temp_tasks store:`, tempTasks.map(t => t.id));
        }
        
        // CROWN⁴.5 FIX: Emit cache hit event for performance tracking (bulk load)
        // This ensures cache hit rate is properly tracked when bootstrap loads all tasks
        if (allTasks.length > 0) {
            window.dispatchEvent(new CustomEvent('cache:hit', {
                detail: { 
                    bulkLoad: true, 
                    taskCount: allTasks.length,
                    tempCount: tempTasks.length,
                    cached: true 
                }
            }));
        } else {
            window.dispatchEvent(new CustomEvent('cache:miss', {
                detail: { 
                    bulkLoad: true, 
                    taskCount: 0,
                    cached: false 
                }
            }));
        }
        
        return allTasks;
    }

    /**
     * Get ONLY temp tasks from temp_tasks store (for reconciliation merge)
     * ENTERPRISE-GRADE: Returns tasks with sync_status for UI rendering
     * @returns {Promise<Array>}
     */
    async getTempTasks() {
        await this.init();
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['temp_tasks'], 'readonly');
            const store = transaction.objectStore('temp_tasks');
            const request = store.getAll();
            
            request.onsuccess = () => {
                const tempTasks = request.result || [];
                
                console.log(`📦 [Offline-First] Retrieved ${tempTasks.length} temp tasks from IndexedDB`);
                
                // Mark temp tasks with appropriate sync flags based on sync_status
                tempTasks.forEach(task => {
                    task._temp = true;
                    
                    // Map sync_status to UI flags
                    if (task.sync_status === 'pending') {
                        task._is_syncing = true;
                        task._sync_status = 'pending';
                        console.log(`📦 [Offline-First] Task ${task.id}: PENDING sync (${task.title})`);
                    } else if (task.sync_status === 'failed') {
                        task._is_syncing = false;
                        task._sync_status = 'failed';
                        task._sync_error = task.last_error || 'Unknown error';
                        console.log(`📦 [Offline-First] Task ${task.id}: FAILED sync - ${task.last_error} (${task.title})`);
                    } else if (task.sync_status === 'confirmed') {
                        // Confirmed tasks should have been removed from temp_tasks, but handle gracefully
                        task._is_syncing = false;
                        task._sync_status = 'confirmed';
                        console.warn(`⚠️ [Offline-First] Task ${task.id}: Already CONFIRMED but still in temp_tasks store`);
                    } else {
                        // Default to pending for legacy tasks without sync_status
                        task._is_syncing = true;
                        task._sync_status = 'pending';
                        console.log(`📦 [Offline-First] Task ${task.id}: Legacy task, defaulting to PENDING`);
                    }
                });
                
                console.log(`📦 [Offline-First] Returning ${tempTasks.length} temp tasks with sync metadata`);
                resolve(tempTasks);
            };
            request.onerror = () => {
                console.error(`❌ [Offline-First] Failed to retrieve temp tasks:`, request.error);
                reject(request.error);
            };
        });
    }

    /**
     * Get tasks with filtering (status, priority, search)
     * Emits explicit cache telemetry for bootstrap path tracking
     * @param {Object} filters - Filter criteria
     * @returns {Promise<Array>}
     */
    async getFilteredTasks(filters = {}) {
        await this.init();
        const allTasks = await this.getAllTasks();
        
        const filteredTasks = allTasks.filter(task => {
            // CACHE HYGIENE: Always filter out deleted tasks unless explicitly requested
            if (!filters.include_deleted && task.deleted_at) {
                return false;
            }

            // Status filter
            if (filters.status && task.status !== filters.status) {
                return false;
            }

            // Priority filter
            if (filters.priority && task.priority !== filters.priority) {
                return false;
            }

            // Search filter
            if (filters.search) {
                const searchLower = filters.search.toLowerCase();
                const titleMatch = task.title?.toLowerCase().includes(searchLower);
                const descMatch = task.description?.toLowerCase().includes(searchLower);
                if (!titleMatch && !descMatch) return false;
            }

            // Labels filter
            if (filters.labels && filters.labels.length > 0) {
                if (!task.labels || !filters.labels.some(label => task.labels.includes(label))) {
                    return false;
                }
            }

            // Snoozed filter
            if (filters.show_snoozed === false) {
                if (task.snoozed_until && new Date(task.snoozed_until) > new Date()) {
                    return false;
                }
            }

            // Due date filters
            if (filters.due_date) {
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const taskDue = task.due_date ? new Date(task.due_date) : null;

                if (filters.due_date === 'today' && (!taskDue || taskDue.getTime() !== today.getTime())) {
                    return false;
                }
                if (filters.due_date === 'overdue' && (!taskDue || taskDue >= today)) {
                    return false;
                }
                if (filters.due_date === 'this_week') {
                    const weekEnd = new Date(today);
                    weekEnd.setDate(today.getDate() + 7);
                    if (!taskDue || taskDue < today || taskDue > weekEnd) {
                        return false;
                    }
                }
            }

            return true;
        });
        
        // NOTE: Cache hit/miss events are emitted by getAllTasks() above,
        // so bootstrap path (which calls this method) has correct cache telemetry
        return filteredTasks;
    }

    /**
     * Get single task by ID
     * @param {number|string} taskId - Numeric ID or temp string ID
     * @returns {Promise<Object|null>}
     */
    async getTask(taskId) {
        await this.init();
        
        // Check temp_tasks store first for string IDs starting with 'temp_'
        if (typeof taskId === 'string' && taskId.startsWith('temp_')) {
            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['temp_tasks'], 'readonly');
                const store = transaction.objectStore('temp_tasks');
                const request = store.get(taskId);
                
                request.onsuccess = () => {
                    const result = request.result || null;
                    if (result) {
                        console.log(`📦 Retrieved temp task from temp_tasks store: ${taskId}`);
                        window.dispatchEvent(new CustomEvent('cache:hit', {
                            detail: { taskId, cached: true, temp: true }
                        }));
                    } else {
                        console.warn(`⚠️ Temp task not found: ${taskId}`);
                        window.dispatchEvent(new CustomEvent('cache:miss', {
                            detail: { taskId, cached: false, temp: true }
                        }));
                    }
                    resolve(result);
                };
                request.onerror = () => reject(request.error);
            });
        }
        
        // Normal IndexedDB lookup for numeric IDs
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readonly');
            const store = transaction.objectStore('tasks');
            const numericId = typeof taskId === 'string' ? parseInt(taskId, 10) : taskId;
            const request = store.get(numericId);

            request.onsuccess = () => {
                const result = request.result || null;
                
                // Emit cache hit/miss event for performance tracking
                if (result) {
                    window.dispatchEvent(new CustomEvent('cache:hit', {
                        detail: { taskId, cached: true }
                    }));
                } else {
                    window.dispatchEvent(new CustomEvent('cache:miss', {
                        detail: { taskId, cached: false }
                    }));
                }
                
                resolve(result);
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Save or update task in cache (optimistic update)
     * @param {Object} task - Task data
     * @returns {Promise<void>}
     */
    async saveTask(task) {
        await this.init();
        
        // CRITICAL CACHE CORRUPTION FIX: Validate task is not an error response
        // Gap #7: Error responses with 'error' or 'success: false' fields were being cached as tasks
        if (!task || typeof task !== 'object') {
            console.warn('⚠️ Attempted to save invalid task (null/non-object):', task);
            return;
        }
        
        // Reject error responses
        if (task.error || task.success === false) {
            console.warn('⚠️ Rejected error response from being cached as task:', task);
            return;
        }
        
        // Validate required task fields exist
        if (!task.hasOwnProperty('title') || !task.hasOwnProperty('status')) {
            console.warn('⚠️ Rejected object missing required task fields (title/status):', task);
            return;
        }
        
        // CRITICAL FIX: Handle temporary IDs from optimistic UI
        // Store temp tasks in dedicated IndexedDB store (survives page refresh)
        if (typeof task.id === 'string' && task.id.startsWith('temp_')) {
            console.log(`💾 [Offline-First] saveTask() called with temp ID: ${task.id}`);
            console.log(`💾 [Offline-First] Task: "${task.title}" (status: ${task.status})`);
            
            // Ensure timestamps
            const now = new Date().toISOString();
            if (!task.created_at) task.created_at = now;
            task.updated_at = now;
            task._temp = true; // Mark as temporary
            
            // ENTERPRISE-GRADE: Add sync metadata for resilient offline-first behavior
            // This metadata prevents data loss during rollback and enables retry logic
            if (!task.sync_status) {
                task.sync_status = 'pending'; // pending | failed | confirmed
            }
            if (!task.operation_id) {
                task.operation_id = `op_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            }
            if (!task.retry_count) {
                task.retry_count = 0;
            }
            // last_error will be set on failure
            
            console.log(`💾 [Offline-First] Metadata: sync_status=${task.sync_status}, operation_id=${task.operation_id}`);
            
            // Store in temp_tasks object store (string IDs allowed)
            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['temp_tasks'], 'readwrite');
                const store = transaction.objectStore('temp_tasks');
                const request = store.put(task);
                
                request.onsuccess = () => {
                    console.log(`✅ [Offline-First] Temp task persisted to IndexedDB: ${task.id}`);
                    resolve();
                };
                request.onerror = () => {
                    console.error(`❌ [Offline-First] FAILED to store temp task: ${task.id}`, request.error);
                    reject(request.error);
                };
            });
        }
        
        // Step 1: Normalize string IDs to numbers (e.g., "123" -> 123, "0" -> 0)
        if (typeof task.id === 'string') {
            const numericId = parseInt(task.id, 10);
            if (isNaN(numericId)) {
                console.error('❌ CRITICAL: Task ID is non-numeric string:', task.id);
                throw new Error(`Task ID "${task.id}" cannot be converted to number for IndexedDB storage.`);
            }
            task.id = numericId;
        }
        
        // Step 2: Validate ID exists after normalization (catches null/undefined)
        if (!task.id && task.id !== 0) {
            console.error('❌ CRITICAL: Cannot save task without ID field. Task data:', task);
            throw new Error('Task missing required "id" field for IndexedDB storage. This prevents cache persistence.');
        }
        
        // Ensure timestamps
        const now = new Date().toISOString();
        if (!task.created_at) task.created_at = now;
        task.updated_at = now;
        
        // Generate checksum for cache validation (CROWN⁴.5)
        let checksum = null;
        if (window.cacheValidator) {
            try {
                checksum = await window.cacheValidator.generateChecksum(task);
                task._checksum = checksum;
                task._cached_at = now;
            } catch (error) {
                console.warn('Failed to generate task checksum:', error);
            }
        }
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks', 'metadata'], 'readwrite');
            const taskStore = transaction.objectStore('tasks');
            const metaStore = transaction.objectStore('metadata');
            
            const request = taskStore.put(task);
            
            // Store checksum in metadata ONLY after task write succeeds (CROWN⁴.5)
            request.onsuccess = () => {
                if (checksum) {
                    metaStore.put({
                        key: `task_checksum_${task.id}`,
                        checksum: checksum,
                        algorithm: 'SHA-256',
                        task_id: task.id,
                        updated_at: now
                    });
                }
            };
            
            request.onerror = () => {
                console.error(`❌ Failed to save task ${task.id}, checksum not persisted`);
            };

            transaction.oncomplete = () => {
                if (checksum) {
                    console.log(`✅ Task ${task.id} saved with checksum: ${checksum.substring(0, 8)}...`);
                }
                resolve();
            };
            transaction.onerror = () => reject(transaction.error);
        });
    }

    /**
     * Save multiple tasks (bulk operation)
     * @param {Array} tasks - Array of task objects
     * @returns {Promise<void>}
     */
    async saveTasks(tasks) {
        await this.init();
        
        // CRITICAL CACHE CORRUPTION FIX: Filter out invalid tasks and error responses
        const validTasks = [];
        const rejectedTasks = [];
        
        tasks.forEach((task, index) => {
            // Validate task is not an error response
            if (!task || typeof task !== 'object') {
                rejectedTasks.push({ index, reason: 'null/non-object', data: task });
                return;
            }
            
            if (task.error || task.success === false) {
                rejectedTasks.push({ index, reason: 'error response', data: task });
                return;
            }
            
            if (!task.hasOwnProperty('title') || !task.hasOwnProperty('status')) {
                rejectedTasks.push({ index, reason: 'missing required fields', data: task });
                return;
            }
            
            validTasks.push(task);
        });
        
        if (rejectedTasks.length > 0) {
            console.warn(`⚠️ Rejected ${rejectedTasks.length} invalid tasks from bulk save:`, rejectedTasks);
        }
        
        if (validTasks.length === 0) {
            console.warn('⚠️ No valid tasks to save in bulk operation');
            return;
        }
        
        // CRITICAL FIX: Normalize all task IDs first, THEN validate
        
        // Step 1: Normalize string IDs to numbers for all tasks
        const normalizationErrors = [];
        validTasks.forEach((task, index) => {
            if (typeof task.id === 'string') {
                const numericId = parseInt(task.id, 10);
                if (isNaN(numericId)) {
                    normalizationErrors.push({ index, id: task.id, title: task.title || 'Untitled' });
                } else {
                    task.id = numericId;
                }
            }
        });
        
        if (normalizationErrors.length > 0) {
            console.error(`❌ CRITICAL: ${normalizationErrors.length} tasks have non-numeric IDs:`, normalizationErrors);
            throw new Error(`${normalizationErrors.length} tasks have non-numeric IDs. First bad ID: "${normalizationErrors[0].id}" (task: ${normalizationErrors[0].title})`);
        }
        
        // Step 2: Validate all tasks have IDs after normalization
        const missingIdTasks = [];
        tasks.forEach((task, index) => {
            if (!task.id && task.id !== 0) {
                missingIdTasks.push({ index, title: task.title || 'Untitled', data: task });
            }
        });
        
        if (missingIdTasks.length > 0) {
            console.error(`❌ CRITICAL: ${missingIdTasks.length} tasks missing ID field:`, missingIdTasks);
            throw new Error(`${missingIdTasks.length} tasks missing required "id" field. First missing: index ${missingIdTasks[0].index} (${missingIdTasks[0].title})`);
        }
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readwrite');
            const store = transaction.objectStore('tasks');

            const now = new Date().toISOString();
            tasks.forEach(task => {
                if (!task.created_at) task.created_at = now;
                task.updated_at = now;
                store.put(task);
            });

            transaction.oncomplete = () => {
                console.log(`✅ Cached ${tasks.length} tasks to IndexedDB`);
                resolve();
            };
            transaction.onerror = () => reject(transaction.error);
        });
    }

    /**
     * Reconcile temporary task with real ID from server
     * Called when server confirms task creation and returns real numeric ID
     * CRITICAL: Transaction completes BEFORE calling saveTask() to avoid nested transaction errors
     * @param {number} realId - Real numeric ID from server
     * @param {string} tempId - Temporary string ID (e.g., "temp_123")
     * @returns {Promise<void>}
     */
    async reconcileTempTask(realId, tempId) {
        await this.init();
        console.log(`🔄 Reconciling temp task: ${tempId} → ${realId}`);
        
        // Step 1: Atomic read + delete from temp_tasks store
        // CRITICAL: Wait for transaction to COMPLETE before calling saveTask()
        const tempTask = await new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['temp_tasks'], 'readwrite');
            const tempStore = transaction.objectStore('temp_tasks');
            let tempTaskData = null;
            
            // Read temp task
            const getRequest = tempStore.get(tempId);
            
            getRequest.onsuccess = () => {
                tempTaskData = getRequest.result;
                
                if (!tempTaskData) {
                    console.warn(`⚠️ Temp task not found (already reconciled?): ${tempId} - treating as no-op`);
                    // Transaction will complete and resolve null
                    return;
                }
                
                // Delete from temp_tasks atomically
                const deleteRequest = tempStore.delete(tempId);
                
                deleteRequest.onsuccess = () => {
                    console.log(`🗑️ Removed temp task from temp_tasks store: ${tempId}`);
                };
                deleteRequest.onerror = () => reject(deleteRequest.error);
            };
            getRequest.onerror = () => reject(getRequest.error);
            
            // Wait for transaction to COMPLETE before resolving
            // This ensures no nested transactions when we call saveTask() later
            transaction.oncomplete = () => {
                console.log(`✅ Temp task delete transaction completed: ${tempId}`);
                resolve(tempTaskData);
            };
            transaction.onerror = () => reject(transaction.error);
        });
        
        // If temp task was missing (already reconciled), exit gracefully
        if (!tempTask) {
            return;
        }
        
        // Step 2: Create real task with numeric ID
        const realTask = {
            ...tempTask,
            id: realId,
            _temp: false,
            _is_syncing: false,
            _sync_status: 'complete',
            updated_at: new Date().toISOString()
        };
        
        // Step 3: AFTER transaction completes, save through normal saveTask() path
        // This adds checksums, metadata, and emits proper events for validators
        // No nested transaction errors because previous transaction is complete
        await this.saveTask(realTask);
        
        console.log(`✅ Reconciled temp task ${tempId} → ${realId} with full metadata`);
        
        // Emit event for UI updates and telemetry
        window.dispatchEvent(new CustomEvent('task:reconciled', {
            detail: { tempId, realId, task: realTask }
        }));
    }

    /**
     * Delete task from cache (handles both temp and real IDs)
     * @param {number|string} taskId - Numeric ID or temp string ID
     * @returns {Promise<void>}
     */
    async deleteTask(taskId) {
        await this.init();
        
        // Handle temp task deletion (from temp_tasks store)
        if (typeof taskId === 'string' && taskId.startsWith('temp_')) {
            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction(['temp_tasks'], 'readwrite');
                const store = transaction.objectStore('temp_tasks');
                const request = store.delete(taskId);
                
                request.onsuccess = () => {
                    console.log(`🗑️ Deleted temp task from temp_tasks store: ${taskId}`);
                    resolve();
                };
                request.onerror = () => {
                    console.warn(`⚠️ Failed to delete temp task ${taskId}:`, request.error);
                    // Don't throw, just log warning
                    resolve();
                };
            });
        }
        
        // Handle real task deletion (from tasks store)
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readwrite');
            const store = transaction.objectStore('tasks');
            const numericId = typeof taskId === 'string' ? parseInt(taskId, 10) : taskId;
            const request = store.delete(numericId);

            request.onsuccess = () => {
                console.log(`🗑️ Deleted task from tasks store: ${numericId}`);
                resolve();
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Add event to ledger (for event sourcing and replay)
     * @param {Object} event - Event data with vector clock
     * @returns {Promise<number>} Event ID
     */
    async addEvent(event) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['events'], 'readwrite');
            const store = transaction.objectStore('events');

            // Create or increment vector clock
            let vectorClock;
            if (event.vector_clock) {
                vectorClock = VectorClock.fromTuple(event.vector_clock);
            } else {
                vectorClock = new VectorClock();
            }
            vectorClock.increment(this.nodeId);

            const eventRecord = {
                ...event,
                timestamp: event.timestamp || Date.now(),
                sync_status: event.sync_status || 'pending',
                vector_clock: vectorClock.toTuple() // Store as normalized tuple
            };

            const request = store.add(eventRecord);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get all pending events (not yet synced)
     * @returns {Promise<Array>}
     */
    async getPendingEvents() {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['events'], 'readonly');
            const store = transaction.objectStore('events');
            const index = store.index('sync_status');
            const request = index.getAll('pending');

            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Mark event as synced
     * @param {number} eventId
     * @returns {Promise<void>}
     */
    async markEventSynced(eventId) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['events'], 'readwrite');
            const store = transaction.objectStore('events');
            const getRequest = store.get(eventId);

            getRequest.onsuccess = () => {
                const event = getRequest.result;
                if (event) {
                    event.sync_status = 'synced';
                    event.synced_at = Date.now();
                    store.put(event);
                }
                resolve();
            };

            getRequest.onerror = () => reject(getRequest.error);
        });
    }

    /**
     * Add operation to offline queue
     * @param {Object} operation - Operation data with vector clock
     * @returns {Promise<number>} Queue ID
     */
    async queueOfflineOperation(operation) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['offline_queue'], 'readwrite');
            const store = transaction.objectStore('offline_queue');

            // Create or increment vector clock
            let vectorClock;
            if (operation.vector_clock) {
                vectorClock = VectorClock.fromTuple(operation.vector_clock);
            } else {
                vectorClock = new VectorClock();
            }
            vectorClock.increment(this.nodeId);

            const queueItem = {
                ...operation,
                timestamp: Date.now(),
                priority: operation.priority || 0,
                vector_clock: vectorClock.toTuple() // Store as normalized tuple
            };

            const request = store.add(queueItem);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get all offline queue items (ordered by CROWN⁴.5 priority rules)
     * @returns {Promise<Array>}
     */
    async getOfflineQueue() {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['offline_queue'], 'readonly');
            const store = transaction.objectStore('offline_queue');
            const request = store.getAll();

            request.onsuccess = () => {
                const queue = request.result || [];
                
                // Sort by CROWN⁴.5 priority rules:
                // 1. Higher priority operations first
                // 2. Vector clock comparison for causal ordering
                // 3. Timestamp as deterministic tie-breaker
                queue.sort((a, b) => {
                    // Rule 1: Priority (higher first)
                    if (a.priority !== b.priority) {
                        return b.priority - a.priority;
                    }

                    // Rule 2: Vector clock comparison
                    const aVC = VectorClock.fromTuple(a.vector_clock);
                    const bVC = VectorClock.fromTuple(b.vector_clock);
                    const comparison = aVC.compare(bVC);
                    
                    if (comparison !== 0) {
                        return comparison;
                    }

                    // Rule 3: Timestamp tie-breaker (earlier first)
                    return a.timestamp - b.timestamp;
                });
                
                resolve(queue);
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * ENTERPRISE-GRADE: Update sync status for a temp task (offline-first resilience)
     * Prevents data loss by marking tasks as failed instead of deleting them
     * @param {string} tempId - Temporary task ID
     * @param {string} status - 'pending' | 'failed' | 'confirmed'
     * @param {string|null} error - Error message if status is 'failed'
     * @returns {Promise<void>}
     */
    async updateTempTaskStatus(tempId, status, error = null) {
        await this.init();
        
        console.log(`🔄 [Offline-First] Updating temp task ${tempId} status to: ${status}`);
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['temp_tasks'], 'readwrite');
            const store = transaction.objectStore('temp_tasks');
            const getRequest = store.get(tempId);
            
            getRequest.onsuccess = () => {
                const task = getRequest.result;
                if (!task) {
                    console.warn(`⚠️ [Offline-First] Temp task ${tempId} not found in IndexedDB`);
                    resolve();
                    return;
                }
                
                // Update sync metadata
                task.sync_status = status;
                task.updated_at = new Date().toISOString();
                
                if (status === 'failed') {
                    task.last_error = error || 'Unknown error';
                    task.retry_count = (task.retry_count || 0) + 1;
                    console.log(`❌ [Offline-First] Task ${tempId} marked as FAILED: ${error} (retry #${task.retry_count})`);
                } else if (status === 'confirmed') {
                    console.log(`✅ [Offline-First] Task ${tempId} marked as CONFIRMED - ready for cleanup`);
                }
                
                store.put(task);
            };
            
            transaction.oncomplete = () => {
                console.log(`✅ [Offline-First] Temp task ${tempId} status updated to: ${status}`);
                resolve();
            };
            transaction.onerror = () => {
                console.error(`❌ [Offline-First] Failed to update temp task ${tempId} status:`, transaction.error);
                reject(transaction.error);
            };
        });
    }

    /**
     * ENTERPRISE-GRADE: Remove confirmed temp task after successful server reconciliation
     * Only removes tasks that have been successfully synced to server
     * @param {string} tempId - Temporary task ID
     * @returns {Promise<void>}
     */
    async removeTempTask(tempId) {
        await this.init();
        
        console.log(`🧹 [Offline-First] Removing confirmed temp task: ${tempId}`);
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['temp_tasks'], 'readwrite');
            const store = transaction.objectStore('temp_tasks');
            
            // Safety check: Verify task is confirmed before deletion
            const getRequest = store.get(tempId);
            
            getRequest.onsuccess = () => {
                const task = getRequest.result;
                if (!task) {
                    console.warn(`⚠️ [Offline-First] Temp task ${tempId} already removed`);
                    resolve();
                    return;
                }
                
                // Only delete if confirmed (prevents accidental data loss)
                if (task.sync_status === 'confirmed') {
                    store.delete(tempId);
                    console.log(`✅ [Offline-First] Confirmed temp task ${tempId} removed from IndexedDB`);
                } else {
                    console.warn(`⚠️ [Offline-First] Skipping removal of temp task ${tempId} - not confirmed (status: ${task.sync_status})`);
                }
                resolve();
            };
            
            transaction.onerror = () => {
                console.error(`❌ [Offline-First] Failed to remove temp task ${tempId}:`, transaction.error);
                reject(transaction.error);
            };
        });
    }

    /**
     * Clear offline queue after successful sync
     * @returns {Promise<void>}
     */
    async clearOfflineQueue() {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['offline_queue'], 'readwrite');
            const store = transaction.objectStore('offline_queue');
            const request = store.clear();

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Remove specific item from offline queue
     * @param {number} queueId
     * @returns {Promise<void>}
     */
    async removeFromQueue(queueId) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['offline_queue'], 'readwrite');
            const store = transaction.objectStore('offline_queue');
            const request = store.delete(queueId);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get metadata value
     * @param {string} key
     * @returns {Promise<any>}
     */
    async getMetadata(key) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['metadata'], 'readonly');
            const store = transaction.objectStore('metadata');
            const request = store.get(key);

            request.onsuccess = () => resolve(request.result?.value);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Set metadata value
     * @param {string} key
     * @param {any} value
     * @returns {Promise<void>}
     */
    async setMetadata(key, value) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['metadata'], 'readwrite');
            const store = transaction.objectStore('metadata');
            const request = store.put({ key, value, updated_at: Date.now() });

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * CROWN⁴.5: Track event sequence number and detect gaps
     * MONOTONIC: Only accepts non-decreasing event_ids to prevent backwards rollback
     * @param {number} event_id - Event ID from server
     * @returns {Promise<{gap_detected: boolean, gap_type: string, expected: number, received: number}>}
     */
    async trackEventSequence(event_id) {
        if (!event_id) {
            return { gap_detected: false, gap_type: 'none' };
        }

        const lastEventId = await this.getMetadata('last_event_id');
        
        // First event received
        if (lastEventId === null || lastEventId === undefined) {
            await this.setMetadata('last_event_id', event_id);
            console.log(`📊 Sequence tracking initialized: event_id=${event_id}`);
            return { gap_detected: false, gap_type: 'init', expected: null, received: event_id };
        }

        const expected = lastEventId + 1;
        
        // DUPLICATE: Received same event_id again (idempotent replay)
        if (event_id === lastEventId) {
            console.log(`🔁 Duplicate event_id=${event_id} (already processed)`);
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordEvent('sequence_duplicate', {
                    event_id,
                    last_event_id: lastEventId
                });
            }
            return { gap_detected: false, gap_type: 'duplicate', expected, received: event_id };
        }

        // REGRESSION: Received event_id < last_event_id (stale/replayed event)
        if (event_id < lastEventId) {
            console.warn(`⏪ Regression detected: event_id=${event_id} < last_event_id=${lastEventId} (ignoring stale event)`);
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordEvent('sequence_regression', {
                    expected: lastEventId,
                    received: event_id,
                    regression_size: lastEventId - event_id
                });
            }
            // DO NOT update last_event_id - prevent backwards rollback
            return { gap_detected: true, gap_type: 'regression', expected: lastEventId, received: event_id };
        }

        // FORWARD GAP: Received event_id > expected (missing events)
        if (event_id > expected) {
            const gap_size = event_id - expected;
            console.warn(`⚠️ Forward gap detected! Expected event_id=${expected}, received=${event_id} (missing ${gap_size} events)`);
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordEvent('sequence_gap_forward', {
                    expected,
                    received: event_id,
                    gap_size
                });
            }
            
            // Update to new event_id (move forward despite gap)
            await this.setMetadata('last_event_id', event_id);
            return { gap_detected: true, gap_type: 'forward', expected, received: event_id, gap_size };
        }

        // SEQUENTIAL: event_id === expected (normal case)
        await this.setMetadata('last_event_id', event_id);
        return { gap_detected: false, gap_type: 'sequential', expected, received: event_id };
    }

    /**
     * CROWN⁴.5: Get last tracked event ID
     * @returns {Promise<number|null>}
     */
    async getLastEventId() {
        return await this.getMetadata('last_event_id');
    }

    /**
     * Get view state (filters, sort, scroll position)
     * @param {string} key
     * @returns {Promise<any>}
     */
    async getViewState(key) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['view_state'], 'readonly');
            const store = transaction.objectStore('view_state');
            const request = store.get(key);

            request.onsuccess = () => resolve(request.result?.value);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Set view state
     * @param {string} key
     * @param {any} value
     * @returns {Promise<void>}
     */
    async setViewState(key, value) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['view_state'], 'readwrite');
            const store = transaction.objectStore('view_state');
            const request = store.put({ key, value, updated_at: Date.now() });

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Compact old events to prevent unbounded growth (CROWN⁴.5 requirement)
     * Archives events older than retention period
     * @param {number} retentionDays - Keep events from last N days (default: 30)
     * @returns {Promise<Object>} Compaction summary
     */
    async compactEvents(retentionDays = 30) {
        await this.init();
        
        const cutoffTimestamp = Date.now() - (retentionDays * 24 * 60 * 60 * 1000);
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['events', 'compaction'], 'readwrite');
            const eventStore = transaction.objectStore('events');
            const compactionStore = transaction.objectStore('compaction');
            const timestampIndex = eventStore.index('timestamp');
            
            const request = timestampIndex.openCursor(IDBKeyRange.upperBound(cutoffTimestamp));
            const eventsToArchive = [];
            const eventIdsToDelete = [];

            request.onsuccess = (event) => {
                const cursor = event.target.result;
                
                if (cursor) {
                    // Only compact synced events
                    if (cursor.value.sync_status === 'synced') {
                        eventsToArchive.push(cursor.value);
                        eventIdsToDelete.push(cursor.value.id);
                    }
                    cursor.continue();
                } else {
                    // Archive completed, create compaction summary
                    if (eventsToArchive.length > 0) {
                        const summary = {
                            compaction_date: Date.now(),
                            event_count: eventsToArchive.length,
                            oldest_event: Math.min(...eventsToArchive.map(e => e.timestamp)),
                            newest_event: Math.max(...eventsToArchive.map(e => e.timestamp)),
                            event_types: eventsToArchive.reduce((acc, e) => {
                                acc[e.event_type] = (acc[e.event_type] || 0) + 1;
                                return acc;
                            }, {})
                        };

                        compactionStore.add(summary);

                        // Delete archived events
                        eventIdsToDelete.forEach(id => eventStore.delete(id));

                        console.log(`✅ Compacted ${eventsToArchive.length} old events`);
                    }

                    resolve({
                        compacted: eventsToArchive.length,
                        cutoff_timestamp: cutoffTimestamp,
                        retention_days: retentionDays
                    });
                }
            };

            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Clear only tasks cache (preserves events, queue, metadata)
     * @returns {Promise<void>}
     */
    async clearAllTasks() {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readwrite');
            const store = transaction.objectStore('tasks');
            const request = store.clear();

            request.onsuccess = () => {
                console.log('✅ Tasks cache cleared');
                resolve();
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Clear all caches (used for reset/logout)
     * @returns {Promise<void>}
     */
    async clearAll() {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(
                ['tasks', 'events', 'offline_queue', 'compaction', 'metadata', 'view_state'],
                'readwrite'
            );

            transaction.objectStore('tasks').clear();
            transaction.objectStore('events').clear();
            transaction.objectStore('offline_queue').clear();
            transaction.objectStore('compaction').clear();
            transaction.objectStore('metadata').clear();
            transaction.objectStore('view_state').clear();

            transaction.oncomplete = () => {
                console.log('✅ All caches cleared');
                resolve();
            };
            transaction.onerror = () => reject(transaction.error);
        });
    }

    /**
     * Get cache statistics for debugging
     * @returns {Promise<Object>}
     */
    async getStats() {
        await this.init();
        
        const taskCount = await this.getAllTasks().then(t => t.length);
        const pendingEvents = await this.getPendingEvents().then(e => e.length);
        const queuedOps = await this.getOfflineQueue().then(q => q.length);
        const lastSync = await this.getMetadata('last_sync_timestamp');
        const lastCompaction = await this.getMetadata('last_compaction_timestamp');

        // Get total event count
        const totalEvents = await new Promise((resolve) => {
            const tx = this.db.transaction(['events'], 'readonly');
            const request = tx.objectStore('events').count();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => resolve(0);
        });

        return {
            tasks: taskCount,
            total_events: totalEvents,
            pending_events: pendingEvents,
            queued_operations: queuedOps,
            last_sync: lastSync,
            last_compaction: lastCompaction,
            node_id: this.nodeId,
            cache_ready: this.ready
        };
    }
}

// Export VectorClock class for external use
window.VectorClock = VectorClock;

// Export singleton instance
window.taskCache = new TaskCache();

console.log('📦 CROWN⁴.5 TaskCache with VectorClock loaded');
