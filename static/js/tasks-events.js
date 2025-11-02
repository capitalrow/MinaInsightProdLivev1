/**
 * CROWN ¹⁰ Tasks Page - Event Synchronization
 * Handles real-time task updates, offline queue replay, and cross-surface sync
 */

class TasksEventManager {
    constructor() {
        this.socket = null;
        this.workspaceId = typeof WORKSPACE_ID !== 'undefined' ? WORKSPACE_ID : 1;
        this.userId = typeof USER_ID !== 'undefined' ? USER_ID : null;
        this.offlineQueue = [];
        this.lastSequenceNum = 0;
        this.isOnline = navigator.onLine;
        this.cache = null;
        
        // Vector clock for distributed conflict resolution
        this.vectorClock = this.loadVectorClock();
        
        this.init();
    }
    
    async init() {
        console.log('[Tasks] Initializing CROWN ¹⁰ event synchronization');
        
        // Initialize IndexedDB cache
        await this.initCache();
        
        // Load offline queue from localStorage
        this.loadOfflineQueue();
        
        // Setup WebSocket listeners
        this.setupWebSocketListeners();
        
        // Setup online/offline detection
        this.setupNetworkListeners();
        
        // Load last sequence number
        this.lastSequenceNum = this.getLastSequenceNum();
    }
    
    async initCache() {
        try {
            if (typeof CacheManager !== 'undefined') {
                this.cache = new CacheManager();
                await this.cache.init();
                console.log('✅ Tasks cache initialized');
            }
        } catch (error) {
            console.error('❌ Failed to initialize cache:', error);
        }
    }
    
    setupWebSocketListeners() {
        if (!window.io) {
            console.warn('[Tasks] Socket.IO not available');
            return;
        }
        
        // Connect to /tasks namespace
        this.socket = window.io('/tasks', {
            transports: ['websocket', 'polling']
        });
        
        // Connection events
        this.socket.on('connect', () => {
            console.log('✅ Tasks WebSocket connected');
            this.isOnline = true;
            
            // Join workspace room
            this.socket.emit('join_workspace', {
                workspace_id: this.workspaceId
            });
            
            // Request event replay to catch up
            this.socket.emit('request_event_replay', {
                workspace_id: this.workspaceId,
                last_sequence_num: this.lastSequenceNum
            });
            
            // Replay offline queue if any
            if (this.offlineQueue.length > 0) {
                this.replayOfflineQueue();
            }
        });
        
        this.socket.on('disconnect', () => {
            console.warn('⚠️ Tasks WebSocket disconnected');
            this.isOnline = false;
        });
        
        this.socket.on('error', (error) => {
            console.error('❌ Tasks WebSocket error:', error);
        });
        
        // Event replay handler
        this.socket.on('event_replay', async (data) => {
            console.log(`📦 Tasks event replay: ${data.count} events`);
            
            if (data.events && data.events.length > 0) {
                for (const event of data.events) {
                    await this.handleEvent(event);
                }
                
                this.saveLastSequenceNum(data.last_sequence_num);
            }
        });
        
        // CROWN ¹⁰ Task Event Handlers
        this.socket.on('task_update', async (event) => {
            console.log('✓ Task updated:', event);
            await this.handleTaskUpdate(event);
        });
        
        this.socket.on('tasks_generation', async (event) => {
            console.log('📋 Tasks generated:', event);
            await this.handleTasksGenerated(event);
        });
        
        this.socket.on('task_complete', async (event) => {
            console.log('✅ Task completed:', event);
            await this.handleTaskComplete(event);
        });
        
        this.socket.on('task_created', async (event) => {
            console.log('🆕 Task created:', event);
            await this.handleTaskCreated(event);
        });
        
        this.socket.on('task_deleted', async (event) => {
            console.log('🗑️ Task deleted:', event);
            await this.handleTaskDeleted(event);
        });
        
        // Offline queue acknowledgments
        this.socket.on('offline_queue:saved', (data) => {
            console.log('💾 Offline queue saved to server');
        });
        
        this.socket.on('offline_queue:cleared', (data) => {
            console.log('🗑️ Offline queue cleared from server');
        });
        
        console.log('✅ Tasks WebSocket listeners registered');
    }
    
    setupNetworkListeners() {
        window.addEventListener('online', () => {
            console.log('🌐 Network online');
            this.isOnline = true;
            
            // Reconnect WebSocket if needed
            if (this.socket && !this.socket.connected) {
                this.socket.connect();
            }
        });
        
        window.addEventListener('offline', () => {
            console.warn('📴 Network offline - queueing mutations');
            this.isOnline = false;
        });
    }
    
    /**
     * Handle task update event
     */
    async handleTaskUpdate(event) {
        const { data, sequence_num, vector_clock } = event;
        
        // Update sequence number
        if (sequence_num) {
            this.saveLastSequenceNum(sequence_num);
        }
        
        // Invalidate cache
        if (this.cache) {
            await this.cache.invalidate('tasks');
        }
        
        // Update UI if tasks manager exists
        if (window.tasksManager) {
            await window.tasksManager.refreshTasks();
        }
        
        // Broadcast to other tabs
        if (window.broadcastSync) {
            window.broadcastSync.broadcast('TASK_UPDATE', data);
        }
    }
    
    /**
     * Handle tasks generated event
     */
    async handleTasksGenerated(event) {
        const { data } = event;
        
        // Invalidate cache
        if (this.cache) {
            await this.cache.invalidate('tasks');
        }
        
        // Reload tasks list
        if (window.tasksManager) {
            await window.tasksManager.refreshTasks();
        }
        
        // Show notification
        const count = data.tasks?.length || 0;
        this.showNotification(`${count} tasks generated`, 'success');
    }
    
    /**
     * Handle task complete event
     */
    async handleTaskComplete(event) {
        const { data } = event;
        
        // Invalidate caches
        if (this.cache) {
            await this.cache.invalidate('tasks');
            await this.cache.invalidate('analytics');
        }
        
        // Update UI
        if (window.tasksManager) {
            await window.tasksManager.refreshTasks();
        }
        
        // Show notification with calm tick animation
        this.showNotification('Task completed', 'success');
    }
    
    /**
     * Handle task created event
     */
    async handleTaskCreated(event) {
        const { data } = event;
        
        // Invalidate cache
        if (this.cache) {
            await this.cache.invalidate('tasks');
        }
        
        // Reload tasks
        if (window.tasksManager) {
            await window.tasksManager.refreshTasks();
        }
    }
    
    /**
     * Handle task deleted event
     */
    async handleTaskDeleted(event) {
        const { data } = event;
        
        // Invalidate cache
        if (this.cache) {
            await this.cache.invalidate('tasks');
        }
        
        // Remove from UI
        if (window.tasksManager) {
            await window.tasksManager.refreshTasks();
        }
    }
    
    /**
     * Generic event handler
     */
    async handleEvent(event) {
        const handlers = {
            'task_update': () => this.handleTaskUpdate(event),
            'tasks_generation': () => this.handleTasksGenerated(event),
            'task_complete': () => this.handleTaskComplete(event),
            'task_created': () => this.handleTaskCreated(event),
            'task_deleted': () => this.handleTaskDeleted(event)
        };
        
        const handler = handlers[event.event_type];
        if (handler) {
            await handler();
        }
    }
    
    /**
     * Queue mutation for offline replay
     */
    queueMutation(operation, payload) {
        if (this.isOnline) {
            // Online - send immediately
            return this.sendMutation(operation, payload);
        }
        
        // Offline - queue for replay
        const mutation = {
            client_ulid: this.generateULID(),
            operation,
            payload,
            timestamp: new Date().toISOString(),
            vector_clock: this.incrementVectorClock()
        };
        
        this.offlineQueue.push(mutation);
        this.saveOfflineQueue();
        
        console.log('📴 Mutation queued for offline replay:', mutation);
        
        return Promise.resolve({ success: true, queued: true });
    }
    
    /**
     * Send mutation to server
     */
    sendMutation(operation, payload) {
        return new Promise((resolve, reject) => {
            if (!this.socket || !this.socket.connected) {
                // Queue if disconnected
                return this.queueMutation(operation, payload);
            }
            
            const mutation = {
                event_type: operation,
                payload: {
                    ...payload,
                    user_id: this.userId,
                    workspace_id: this.workspaceId,
                    vector_clock: this.incrementVectorClock()
                }
            };
            
            this.socket.emit('task_event', mutation, (response) => {
                if (response && response.success) {
                    resolve(response);
                } else {
                    reject(new Error(response?.message || 'Mutation failed'));
                }
            });
        });
    }
    
    /**
     * Replay offline queue (FIFO order)
     */
    async replayOfflineQueue() {
        if (this.offlineQueue.length === 0) {
            return;
        }
        
        console.log(`🔄 Replaying ${this.offlineQueue.length} offline mutations...`);
        
        const queue = [...this.offlineQueue];
        const failed = [];
        
        for (const mutation of queue) {
            try {
                await this.sendMutation(mutation.operation, mutation.payload);
                console.log('✅ Replayed:', mutation.operation);
            } catch (error) {
                console.error('❌ Replay failed:', mutation.operation, error);
                failed.push(mutation);
            }
        }
        
        if (failed.length === 0) {
            // All succeeded - clear queue
            this.offlineQueue = [];
            this.saveOfflineQueue();
            this.showNotification('All changes synced', 'success');
        } else if (failed.length < queue.length) {
            // Partial success
            this.offlineQueue = failed;
            this.saveOfflineQueue();
            this.showNotification(`${queue.length - failed.length} changes synced, ${failed.length} failed`, 'warning');
        } else {
            // All failed - keep queue
            this.showNotification('Sync failed - changes will retry later', 'error');
        }
    }
    
    /**
     * Vector clock management for distributed conflict resolution
     */
    incrementVectorClock() {
        const clientId = this.getClientId();
        this.vectorClock[clientId] = (this.vectorClock[clientId] || 0) + 1;
        this.saveVectorClock();
        return { ...this.vectorClock };
    }
    
    loadVectorClock() {
        try {
            const stored = localStorage.getItem(`mina_vector_clock_${this.workspaceId}`);
            return stored ? JSON.parse(stored) : {};
        } catch (error) {
            return {};
        }
    }
    
    saveVectorClock() {
        try {
            localStorage.setItem(
                `mina_vector_clock_${this.workspaceId}`,
                JSON.stringify(this.vectorClock)
            );
        } catch (error) {
            console.error('Failed to save vector clock:', error);
        }
    }
    
    getClientId() {
        let clientId = localStorage.getItem('mina_client_id');
        if (!clientId) {
            clientId = this.generateULID();
            localStorage.setItem('mina_client_id', clientId);
        }
        return clientId;
    }
    
    /**
     * Offline queue persistence
     */
    loadOfflineQueue() {
        try {
            const stored = localStorage.getItem(`mina_offline_queue_${this.workspaceId}`);
            this.offlineQueue = stored ? JSON.parse(stored) : [];
        } catch (error) {
            this.offlineQueue = [];
        }
    }
    
    saveOfflineQueue() {
        try {
            localStorage.setItem(
                `mina_offline_queue_${this.workspaceId}`,
                JSON.stringify(this.offlineQueue)
            );
            
            // Also backup to server
            if (this.socket && this.socket.connected) {
                this.socket.emit('offline_queue:save', {
                    session_id: null,
                    queue_data: this.offlineQueue
                });
            }
        } catch (error) {
            console.error('Failed to save offline queue:', error);
        }
    }
    
    /**
     * Sequence number tracking
     */
    getLastSequenceNum() {
        try {
            const stored = localStorage.getItem(`mina_tasks_last_seq_${this.workspaceId}`);
            return stored ? parseInt(stored, 10) : 0;
        } catch (error) {
            return 0;
        }
    }
    
    saveLastSequenceNum(sequenceNum) {
        try {
            localStorage.setItem(
                `mina_tasks_last_seq_${this.workspaceId}`,
                sequenceNum.toString()
            );
        } catch (error) {
            console.error('Failed to save sequence number:', error);
        }
    }
    
    /**
     * Generate ULID for client-side idempotency
     */
    generateULID() {
        // Simple ULID-like implementation (timestamp + random)
        const timestamp = Date.now().toString(36);
        const random = Math.random().toString(36).substring(2, 15);
        return `${timestamp}-${random}`;
    }
    
    /**
     * Show notification (delegates to page manager if exists)
     */
    showNotification(message, type = 'info') {
        if (window.tasksManager && typeof window.tasksManager.showNotification === 'function') {
            window.tasksManager.showNotification(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
}

// Auto-initialize when DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.tasksEvents = new TasksEventManager();
    });
} else {
    window.tasksEvents = new TasksEventManager();
}
