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
        this.version = 2; // Incremented for schema changes
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

            request.onsuccess = async () => {
                this.db = request.result;
                this.ready = true;
                console.log('✅ TaskCache IndexedDB initialized');
                
                // CROWN⁴.5: Run migrations for backward compatibility
                if (window.cacheMigration) {
                    try {
                        const migrationResult = await window.cacheMigration.runMigrations(this.db);
                        if (migrationResult.migrated) {
                            console.log(`🔄 Cache migrated from v${migrationResult.from_version} to v${migrationResult.to_version}`);
                        }
                    } catch (error) {
                        console.error('❌ Migration failed:', error);
                    }
                }
                
                // Schedule cache hygiene routine on idle (CROWN⁴.5)
                this._scheduleHygieneRoutine();
                
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                console.log('🔧 Creating IndexedDB schema for CROWN⁴.5...');

                // Store 1: Tasks - Main task data with CROWN⁴.5 fields
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

                // Store 2: Event Ledger - Stores all events with vector clocks
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
     * ENTERPRISE-GRADE: Clean orphaned temp tasks (safe, prevents data loss)
     * Only removes temp IDs that are:
     * 1. NOT in the offline queue (already synced/failed)
     * 2. Older than 10 minutes (safe threshold for failed operations)
     * This preserves legitimate offline tasks that are still pending sync.
     * @returns {Promise<number>} Number of tasks removed
     */
    async cleanOrphanedTempTasks() {
        await this.init();
        
        return new Promise(async (resolve, reject) => {
            try {
                // Get all tasks with temp IDs
                const transaction = this.db.transaction(['tasks', 'offline_queue'], 'readonly');
                const taskStore = transaction.objectStore('tasks');
                const queueStore = transaction.objectStore('offline_queue');
                
                const tasksRequest = taskStore.getAll();
                const queueRequest = queueStore.getAll();
                
                await Promise.all([
                    new Promise(res => tasksRequest.onsuccess = res),
                    new Promise(res => queueRequest.onsuccess = res)
                ]);
                
                const allTasks = tasksRequest.result || [];
                const queuedOps = queueRequest.result || [];
                
                // Build set of temp IDs that are in the offline queue (should NOT be deleted)
                const queuedTempIds = new Set();
                queuedOps.forEach(op => {
                    if (op.temp_id) queuedTempIds.add(op.temp_id);
                    if (op.data && op.data.temp_id) queuedTempIds.add(op.data.temp_id);
                });
                
                // CRITICAL FIX: Also protect in-flight operations (dequeued but not yet confirmed)
                // These are tracked in OptimisticUI.pendingOperations
                if (window.optimisticUI && window.optimisticUI.pendingOperations) {
                    for (const [opId, operation] of window.optimisticUI.pendingOperations.entries()) {
                        if (operation.tempId && typeof operation.tempId === 'string') {
                            queuedTempIds.add(operation.tempId);
                            console.log(`✅ Protecting in-flight temp task: ${operation.tempId} (operation ${opId})`);
                        }
                    }
                }
                
                // Find orphaned temp tasks (NOT in queue, older than 10 minutes)
                const now = Date.now();
                const SAFE_THRESHOLD_MS = 10 * 60 * 1000; // 10 minutes
                const orphanedTempIds = [];
                
                allTasks.forEach(task => {
                    if (task.id && typeof task.id === 'string' && task.id.startsWith('temp_')) {
                        // Skip if in offline queue (legitimate pending task)
                        if (queuedTempIds.has(task.id)) {
                            console.log(`✅ Preserving queued temp task: ${task.id}`);
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
                    }
                });
                
                // Delete orphaned temp tasks
                if (orphanedTempIds.length > 0) {
                    const deleteTransaction = this.db.transaction(['tasks'], 'readwrite');
                    const deleteStore = deleteTransaction.objectStore('tasks');
                    
                    orphanedTempIds.forEach(tempId => {
                        deleteStore.delete(tempId);
                        console.log(`🧹 Removing orphaned temp task: ${tempId}`);
                    });
                    
                    deleteTransaction.oncomplete = () => {
                        console.log(`✅ Cache hygiene: Removed ${orphanedTempIds.length} orphaned temp tasks`);
                        resolve(orphanedTempIds.length);
                    };
                    deleteTransaction.onerror = () => reject(deleteTransaction.error);
                } else {
                    console.log('✅ No orphaned temp tasks found');
                    resolve(0);
                }
                
            } catch (error) {
                console.error('❌ Failed to clean orphaned temp tasks:', error);
                reject(error);
            }
        });
    }

    /**
     * Schedule cache hygiene routine to run on idle (CROWN⁴.5)
     * Automatically cleans orphaned temp IDs every hour when browser is idle
     */
    _scheduleHygieneRoutine() {
        // Run initial cleanup after 30 seconds (let app settle)
        setTimeout(() => {
            this.cleanOrphanedTempTasks().catch(err => 
                console.error('Initial hygiene failed:', err)
            );
        }, 30000);
        
        // Schedule recurring cleanup every hour on idle
        const runHygiene = () => {
            if (typeof requestIdleCallback !== 'undefined') {
                requestIdleCallback(async (deadline) => {
                    if (deadline.timeRemaining() > 50) {
                        try {
                            const removed = await this.cleanOrphanedTempTasks();
                            if (removed > 0) {
                                console.log(`🧹 [Hygiene] Removed ${removed} orphaned temp tasks`);
                            }
                        } catch (error) {
                            console.error('Hygiene routine failed:', error);
                        }
                    }
                    // Schedule next run in 1 hour
                    setTimeout(runHygiene, 60 * 60 * 1000);
                }, { timeout: 10000 });
            } else {
                // Fallback for browsers without requestIdleCallback
                setTimeout(async () => {
                    try {
                        await this.cleanOrphanedTempTasks();
                    } catch (error) {
                        console.error('Hygiene routine failed:', error);
                    }
                    // Schedule next run in 1 hour
                    setTimeout(runHygiene, 60 * 60 * 1000);
                }, 5000);
            }
        };
        
        // Start the hygiene cycle
        runHygiene();
        console.log('🧹 Cache hygiene routine scheduled (runs hourly on idle)');
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
     * ENTERPRISE-GRADE: Returns ALL tasks including temp IDs (they'll be marked as "syncing" in UI)
     * @returns {Promise<Array>}
     */
    async getAllTasks() {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readonly');
            const store = transaction.objectStore('tasks');
            const request = store.getAll();

            request.onsuccess = () => {
                const allTasks = request.result || [];
                
                // Mark temp tasks with syncing flag for UI rendering
                allTasks.forEach(task => {
                    if (task.id && typeof task.id === 'string' && task.id.startsWith('temp_')) {
                        task._is_syncing = true;
                        task._sync_status = 'pending';
                    }
                });
                
                resolve(allTasks);
            };
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get tasks with filtering (status, priority, search)
     * @param {Object} filters - Filter criteria
     * @returns {Promise<Array>}
     */
    async getFilteredTasks(filters = {}) {
        await this.init();
        const allTasks = await this.getAllTasks();

        return allTasks.filter(task => {
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
    }

    /**
     * Get single task by ID
     * @param {number} taskId
     * @returns {Promise<Object|null>}
     */
    async getTask(taskId) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readonly');
            const store = transaction.objectStore('tasks');
            const request = store.get(taskId);

            request.onsuccess = () => resolve(request.result || null);
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
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readwrite');
            const store = transaction.objectStore('tasks');

            const now = new Date().toISOString();
            tasks.forEach(task => {
                if (!task.created_at) task.created_at = now;
                task.updated_at = now;
                store.put(task);
            });

            transaction.oncomplete = () => resolve();
            transaction.onerror = () => reject(transaction.error);
        });
    }

    /**
     * Delete task from cache
     * @param {number} taskId
     * @returns {Promise<void>}
     */
    async deleteTask(taskId) {
        await this.init();
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readwrite');
            const store = transaction.objectStore('tasks');
            const request = store.delete(taskId);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Reconcile temporary ID to real ID (CROWN⁴.5 ID Reconciliation)
     * Used when offline-created tasks get confirmed by the server
     * @param {string} temp_id - Temporary ID (e.g., temp_1234567890_abc123_f8e9)
     * @param {number} real_id - Real database ID from server
     * @returns {Promise<boolean>} True if reconciliation succeeded
     */
    async reconcileTempID(temp_id, real_id) {
        await this.init();
        
        console.log(`🔄 Reconciling temp ID: ${temp_id} → ${real_id}`);
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks', 'metadata', 'offline_queue'], 'readwrite');
            const taskStore = transaction.objectStore('tasks');
            const metaStore = transaction.objectStore('metadata');
            const queueStore = transaction.objectStore('offline_queue');
            
            // 1. Get task with temp ID
            const getRequest = taskStore.get(temp_id);
            
            getRequest.onsuccess = () => {
                const task = getRequest.result;
                
                if (!task) {
                    console.warn(`⚠️ No task found with temp ID: ${temp_id}`);
                    resolve(false);
                    return;
                }
                
                // 2. Update task with real ID
                task.id = real_id;
                task._reconciled_from = temp_id;
                task._reconciled_at = new Date().toISOString();
                
                // 3. Save with real ID
                const putRequest = taskStore.put(task);
                
                putRequest.onsuccess = () => {
                    // 4. Delete temp ID entry
                    taskStore.delete(temp_id);
                    
                    // 5. Update metadata checksum key
                    const oldChecksumKey = `task_checksum_${temp_id}`;
                    const newChecksumKey = `task_checksum_${real_id}`;
                    
                    const getMetaRequest = metaStore.get(oldChecksumKey);
                    getMetaRequest.onsuccess = () => {
                        const checksumMeta = getMetaRequest.result;
                        if (checksumMeta) {
                            // Update checksum metadata with new key
                            checksumMeta.key = newChecksumKey;
                            checksumMeta.task_id = real_id;
                            metaStore.put(checksumMeta);
                            metaStore.delete(oldChecksumKey);
                        }
                    };
                    
                    // 6. Update offline queue entries that reference temp ID
                    const queueIndex = queueStore.index('task_id');
                    const queueRequest = queueIndex.getAll(temp_id);
                    
                    queueRequest.onsuccess = () => {
                        const queueEntries = queueRequest.result;
                        queueEntries.forEach(entry => {
                            entry.task_id = real_id;
                            entry.reconciled = true;
                            entry.reconciled_at = new Date().toISOString();
                            queueStore.put(entry);
                        });
                    };
                    
                    console.log(`✅ Reconciliation complete: ${temp_id} → ${real_id}`);
                };
                
                putRequest.onerror = () => {
                    console.error(`❌ Failed to save reconciled task ${real_id}`);
                };
            };
            
            getRequest.onerror = () => {
                console.error(`❌ Failed to get task with temp ID: ${temp_id}`);
            };
            
            transaction.oncomplete = () => resolve(true);
            transaction.onerror = () => {
                console.error(`❌ Reconciliation transaction failed:`, transaction.error);
                reject(transaction.error);
            };
        });
    }

    /**
     * Validate cache against server data and auto-reconcile if drift detected
     * CROWN⁴.5: Checksum-based validation with field-level delta comparison
     * @param {Array} serverTasks - Tasks from server (source of truth)
     * @param {Object} options - Validation options
     * @returns {Promise<Object>} Validation result with reconciliation details
     */
    async validateAndReconcile(serverTasks, options = {}) {
        const startTime = performance.now();
        const {
            autoReconcile = true,
            compareFields = ['id', 'title', 'status', 'updated_at', 'due_date'],
            verbose = false
        } = options;
        
        console.log(`🔍 Starting cache validation (auto-reconcile: ${autoReconcile})`);
        
        try {
            // 1. Load cached tasks
            const cachedTasks = await this.getAllTasks();
            
            // 2. Use CacheValidator to check for drift
            if (!window.cacheValidator) {
                console.warn('⚠️ CacheValidator not available, skipping validation');
                return { validated: false, reason: 'validator_unavailable' };
            }
            
            const validator = window.cacheValidator;
            
            // 3. Generate checksums for comparison
            const validation = await validator.validate({
                cachedData: cachedTasks,
                serverData: serverTasks,
                key: 'tasks_collection',
                persistChecksum: true
            });
            
            // 4. If drift detected, calculate delta and reconcile
            if (validation.drift && autoReconcile) {
                console.warn(`⚠️ Cache drift detected - calculating delta for auto-reconciliation`);
                
                const delta = validator.calculateDelta(
                    cachedTasks,
                    serverTasks,
                    'id',
                    compareFields
                );
                
                if (verbose) {
                    console.log(`📊 Delta summary: ${validator.getDeltaSummary(delta)}`);
                    console.log('   Added:', delta.added.length);
                    console.log('   Modified:', delta.modified.length);
                    console.log('   Removed:', delta.removed.length);
                    console.log('   Unchanged:', delta.unchanged.length);
                }
                
                // 5. Apply delta (merge server changes into cache)
                const reconciledTasks = validator.mergeDelta(cachedTasks, delta, 'id');
                
                // 6. Save reconciled data back to cache
                await this.saveTasks(reconciledTasks);
                
                const reconciliationTime = Math.round(performance.now() - startTime);
                
                console.log(`✅ Auto-reconciliation complete in ${reconciliationTime}ms`);
                
                return {
                    validated: true,
                    hadDrift: true,
                    reconciled: true,
                    delta,
                    validation,
                    reconciliationTime,
                    tasksCount: reconciledTasks.length
                };
            }
            
            // 7. No drift - cache is valid
            const validationTime = Math.round(performance.now() - startTime);
            console.log(`✅ Cache validated successfully in ${validationTime}ms (no drift)`);
            
            return {
                validated: true,
                hadDrift: false,
                reconciled: false,
                validation,
                validationTime,
                tasksCount: cachedTasks.length
            };
            
        } catch (error) {
            console.error('❌ Cache validation failed:', error);
            return {
                validated: false,
                error: error.message,
                validationTime: Math.round(performance.now() - startTime)
            };
        }
    }
    
    /**
     * Quick checksum validation without full reconciliation
     * Used for fast drift detection during idle sync
     * @param {Array} serverTasks - Tasks from server
     * @returns {Promise<boolean>} True if cache is valid (no drift)
     */
    async quickValidate(serverTasks) {
        if (!window.cacheValidator) return true; // Assume valid if validator unavailable
        
        try {
            const cachedTasks = await this.getAllTasks();
            const validation = await window.cacheValidator.validate({
                cachedData: cachedTasks,
                serverData: serverTasks,
                key: 'tasks_quick_check',
                persistChecksum: false
            });
            
            return validation.isValid;
        } catch (error) {
            console.warn('⚠️ Quick validation failed:', error);
            return true; // Assume valid on error to avoid unnecessary reconciliation
        }
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
