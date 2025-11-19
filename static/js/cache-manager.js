/**
 * CROWN⁴ Cache Manager - IndexedDB Layer
 * Provides sub-200ms dashboard load times through intelligent caching
 * 
 * Architecture:
 * - meetings: Cached meeting records with metadata
 * - tasks: Cached task records with status/priority
 * - analytics_snapshots: Workspace-wide KPI snapshots
 * - event_log: CROWN⁴ event sequence for sync validation
 * - metadata: Cache timestamps and checksums
 */

class CacheManager {
    constructor() {
        this.dbName = 'mina_cache';
        this.dbVersion = 1;
        this.db = null;
        this.isInitialized = false;
    }

    /**
     * Initialize IndexedDB with complete schema
     * @returns {Promise<void>}
     */
    async init() {
        if (this.isInitialized) {
            return;
        }

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onerror = () => {
                console.error('❌ IndexedDB failed to open:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                this.isInitialized = true;
                console.log('✅ IndexedDB initialized:', this.dbName);
                
                // Fire ready event for dependent modules
                window.dispatchEvent(new CustomEvent('cacheManagerReady', { 
                    detail: { cacheManager: this } 
                }));
                console.log('📡 cacheManagerReady event fired');
                
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                console.log('🔧 Creating IndexedDB schema...');

                // Store 1: meetings - Meeting records with full metadata
                if (!db.objectStoreNames.contains('meetings')) {
                    const meetingsStore = db.createObjectStore('meetings', { keyPath: 'id' });
                    meetingsStore.createIndex('workspace_id', 'workspace_id', { unique: false });
                    meetingsStore.createIndex('created_at', 'created_at', { unique: false });
                    meetingsStore.createIndex('status', 'status', { unique: false });
                    meetingsStore.createIndex('session_id', 'session_id', { unique: false });
                    console.log('📁 Created meetings store with indexes');
                }

                // Store 2: tasks - Task records with priority/status
                if (!db.objectStoreNames.contains('tasks')) {
                    const tasksStore = db.createObjectStore('tasks', { keyPath: 'id' });
                    tasksStore.createIndex('meeting_id', 'meeting_id', { unique: false });
                    tasksStore.createIndex('assigned_to_id', 'assigned_to_id', { unique: false });
                    tasksStore.createIndex('status', 'status', { unique: false });
                    tasksStore.createIndex('priority', 'priority', { unique: false });
                    tasksStore.createIndex('due_date', 'due_date', { unique: false });
                    console.log('📁 Created tasks store with indexes');
                }

                // Store 3: analytics_snapshots - Workspace KPI snapshots
                if (!db.objectStoreNames.contains('analytics_snapshots')) {
                    const analyticsStore = db.createObjectStore('analytics_snapshots', { keyPath: 'id', autoIncrement: true });
                    analyticsStore.createIndex('workspace_id', 'workspace_id', { unique: false });
                    analyticsStore.createIndex('timestamp', 'timestamp', { unique: false });
                    analyticsStore.createIndex('snapshot_type', 'snapshot_type', { unique: false });
                    console.log('📁 Created analytics_snapshots store with indexes');
                }

                // Store 4: event_log - CROWN⁴ event sequence for validation
                if (!db.objectStoreNames.contains('event_log')) {
                    const eventStore = db.createObjectStore('event_log', { keyPath: 'id', autoIncrement: true });
                    eventStore.createIndex('event_type', 'event_type', { unique: false });
                    eventStore.createIndex('workspace_id', 'workspace_id', { unique: false });
                    eventStore.createIndex('timestamp', 'timestamp', { unique: false });
                    eventStore.createIndex('sequence_number', 'sequence_number', { unique: false });
                    console.log('📁 Created event_log store with indexes');
                }

                // Store 5: metadata - Cache control metadata (timestamps, checksums)
                if (!db.objectStoreNames.contains('metadata')) {
                    const metadataStore = db.createObjectStore('metadata', { keyPath: 'key' });
                    metadataStore.createIndex('workspace_id', 'workspace_id', { unique: false });
                    metadataStore.createIndex('updated_at', 'updated_at', { unique: false });
                    console.log('📁 Created metadata store with indexes');
                }

                console.log('✅ IndexedDB schema created successfully');
            };
        });
    }

    /**
     * Store meetings in cache
     * @param {Array} meetings - Meeting records
     * @param {number} workspaceId - Workspace ID
     * @returns {Promise<void>}
     */
    async cacheMeetings(meetings, workspaceId) {
        if (!this.db) await this.init();

        const tx = this.db.transaction(['meetings', 'metadata'], 'readwrite');
        const meetingsStore = tx.objectStore('meetings');
        const metadataStore = tx.objectStore('metadata');

        // Clear old meetings for this workspace
        const index = meetingsStore.index('workspace_id');
        const oldMeetings = await this._getAllFromIndex(index, workspaceId);
        for (const meeting of oldMeetings) {
            meetingsStore.delete(meeting.id);
        }

        // Cache new meetings
        for (const meeting of meetings) {
            meetingsStore.put({
                ...meeting,
                workspace_id: workspaceId,
                cached_at: Date.now()
            });
        }

        // Update metadata
        metadataStore.put({
            key: `meetings_${workspaceId}`,
            workspace_id: workspaceId,
            count: meetings.length,
            updated_at: Date.now()
        });

        return this._waitForTransaction(tx);
    }

    /**
     * Get cached meetings
     * @param {number} workspaceId - Workspace ID
     * @returns {Promise<Array>}
     */
    async getCachedMeetings(workspaceId) {
        if (!this.db) await this.init();

        const tx = this.db.transaction('meetings', 'readonly');
        const store = tx.objectStore('meetings');
        const index = store.index('workspace_id');

        return this._getAllFromIndex(index, workspaceId);
    }

    /**
     * Store tasks in cache
     * @param {Array} tasks - Task records
     * @param {number} workspaceId - Workspace ID
     * @returns {Promise<void>}
     */
    async cacheTasks(tasks, workspaceId) {
        if (!this.db) await this.init();

        const tx = this.db.transaction(['tasks', 'metadata'], 'readwrite');
        const tasksStore = tx.objectStore('tasks');
        const metadataStore = tx.objectStore('metadata');

        // Cache tasks
        for (const task of tasks) {
            tasksStore.put({
                ...task,
                workspace_id: workspaceId,
                cached_at: Date.now()
            });
        }

        // Update metadata
        metadataStore.put({
            key: `tasks_${workspaceId}`,
            workspace_id: workspaceId,
            count: tasks.length,
            updated_at: Date.now()
        });

        return this._waitForTransaction(tx);
    }

    /**
     * Get cached tasks for a user
     * @param {number} userId - User ID
     * @returns {Promise<Array>}
     */
    async getCachedTasks(userId) {
        if (!this.db) await this.init();

        const tx = this.db.transaction('tasks', 'readonly');
        const store = tx.objectStore('tasks');
        const index = store.index('assigned_to_id');

        return this._getAllFromIndex(index, userId);
    }

    /**
     * Store analytics snapshot
     * @param {Object} snapshot - Analytics data
     * @param {number} workspaceId - Workspace ID
     * @returns {Promise<void>}
     */
    async cacheAnalyticsSnapshot(snapshot, workspaceId) {
        if (!this.db) await this.init();

        const tx = this.db.transaction(['analytics_snapshots', 'metadata'], 'readwrite');
        const analyticsStore = tx.objectStore('analytics_snapshots');
        const metadataStore = tx.objectStore('metadata');

        // Store snapshot
        analyticsStore.put({
            workspace_id: workspaceId,
            snapshot_type: 'dashboard',
            data: snapshot,
            timestamp: Date.now()
        });

        // Update metadata
        metadataStore.put({
            key: `analytics_${workspaceId}`,
            workspace_id: workspaceId,
            updated_at: Date.now()
        });

        return this._waitForTransaction(tx);
    }

    /**
     * Get latest analytics snapshot
     * @param {number} workspaceId - Workspace ID
     * @returns {Promise<Object|null>}
     */
    async getCachedAnalytics(workspaceId) {
        if (!this.db) await this.init();

        const tx = this.db.transaction('analytics_snapshots', 'readonly');
        const store = tx.objectStore('analytics_snapshots');
        const index = store.index('workspace_id');

        const snapshots = await this._getAllFromIndex(index, workspaceId);
        
        // Return most recent snapshot
        if (snapshots.length > 0) {
            return snapshots.sort((a, b) => b.timestamp - a.timestamp)[0];
        }
        
        return null;
    }

    /**
     * Log CROWN⁴ event for sync validation
     * @param {Object} event - Event data
     * @returns {Promise<void>}
     */
    async logEvent(event) {
        if (!this.db) await this.init();

        const tx = this.db.transaction('event_log', 'readwrite');
        const store = tx.objectStore('event_log');

        store.put({
            event_type: event.event_type,
            workspace_id: event.workspace_id,
            payload: event.payload,
            sequence_number: event.sequence_number,
            timestamp: Date.now()
        });

        return this._waitForTransaction(tx);
    }

    /**
     * Get cache metadata
     * @param {string} key - Metadata key
     * @returns {Promise<Object|null>}
     */
    async getMetadata(key) {
        if (!this.db) await this.init();

        return new Promise((resolve, reject) => {
            const tx = this.db.transaction('metadata', 'readonly');
            const store = tx.objectStore('metadata');
            const request = store.get(key);

            request.onsuccess = () => resolve(request.result || null);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Clear all cache for a workspace
     * @param {number} workspaceId - Workspace ID
     * @returns {Promise<void>}
     */
    async clearWorkspaceCache(workspaceId) {
        if (!this.db) await this.init();

        const stores = ['meetings', 'tasks', 'analytics_snapshots', 'event_log', 'metadata'];
        const tx = this.db.transaction(stores, 'readwrite');

        for (const storeName of stores) {
            const store = tx.objectStore(storeName);
            const index = store.index('workspace_id');
            const items = await this._getAllFromIndex(index, workspaceId);
            
            for (const item of items) {
                store.delete(item.id || item.key);
            }
        }

        return this._waitForTransaction(tx);
    }

    /**
     * Check if cache is fresh (less than maxAge ms old)
     * @param {string} key - Metadata key
     * @param {number} maxAge - Maximum age in milliseconds
     * @returns {Promise<boolean>}
     */
    async isCacheFresh(key, maxAge = 300000) { // Default 5 minutes
        const metadata = await this.getMetadata(key);
        
        if (!metadata) {
            return false;
        }

        const age = Date.now() - metadata.updated_at;
        return age < maxAge;
    }

    /**
     * Helper: Get all items from an index
     * @private
     */
    _getAllFromIndex(index, keyValue) {
        return new Promise((resolve, reject) => {
            const request = index.getAll(keyValue);
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Helper: Wait for transaction to complete
     * @private
     */
    _waitForTransaction(tx) {
        return new Promise((resolve, reject) => {
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }
}

// Export singleton instance
window.cacheManager = new CacheManager();
