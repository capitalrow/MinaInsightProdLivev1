/**
 * CROWN⁹ Copilot Streaming Client
 * 
 * Implements 12-event lifecycle with token-level streaming,
 * cross-surface sync, and emotional micro-interactions.
 * 
 * Target: ≤600ms first token latency
 */

class CopilotStreamingClient {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.workspace_id = null;
        this.user_id = null;
        this.conversationSession = this.generateSessionId();
        this.metrics = {
            queryStartTime: null,
            firstTokenTime: null,
            totalTokens: 0
        };
        
        // Event callbacks
        this.onBootstrapComplete = null;
        this.onStreamToken = null;
        this.onStreamSection = null;
        this.onStreamComplete = null;
        this.onActionResult = null;
        this.onError = null;
        this.onConnectionChange = null;
        
        // Offline resilience - message queue
        this.offlineQueue = [];
        this.maxQueueSize = 50;
        this.isReplayingQueue = false;
        
        // IndexedDB for persistent queue (CROWN⁹ offline resilience)
        this.dbName = 'CopilotOfflineDB';
        this.dbVersion = 1;
        this.db = null;
        
        this.initializeDB();
        this.initialize();
    }
    
    /**
     * Initialize IndexedDB for persistent offline queue.
     */
    async initializeDB() {
        if (!('indexedDB' in window)) {
            console.warn('[Copilot] IndexedDB not available, using in-memory queue');
            return;
        }
        
        try {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = (event) => {
                console.error('[Copilot] IndexedDB error:', event.target.error);
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains('offlineQueue')) {
                    const store = db.createObjectStore('offlineQueue', { keyPath: 'id', autoIncrement: true });
                    store.createIndex('timestamp', 'timestamp', { unique: false });
                    store.createIndex('type', 'type', { unique: false });
                }
            };
            
            request.onsuccess = (event) => {
                this.db = event.target.result;
                console.log('[Copilot] IndexedDB initialized for offline resilience');
                this.loadQueueFromDB();
            };
        } catch (error) {
            console.error('[Copilot] Failed to initialize IndexedDB:', error);
        }
    }
    
    /**
     * Load offline queue from IndexedDB on startup.
     */
    async loadQueueFromDB() {
        if (!this.db) return;
        
        try {
            const transaction = this.db.transaction(['offlineQueue'], 'readonly');
            const store = transaction.objectStore('offlineQueue');
            const request = store.getAll();
            
            request.onsuccess = () => {
                const items = request.result || [];
                if (items.length > 0) {
                    this.offlineQueue = items.map(item => ({
                        ...item,
                        fromDB: true
                    }));
                    console.log(`[Copilot] Loaded ${items.length} queued messages from storage`);
                    
                    // Show notification about queued messages
                    if (this.onConnectionChange) {
                        this.onConnectionChange({
                            connected: this.connected,
                            queuedMessages: this.offlineQueue.length
                        });
                    }
                }
            };
        } catch (error) {
            console.error('[Copilot] Failed to load queue from DB:', error);
        }
    }
    
    /**
     * Save message to IndexedDB offline queue.
     */
    async saveToOfflineQueue(item) {
        if (!this.db) {
            this.offlineQueue.push(item);
            return;
        }
        
        try {
            const transaction = this.db.transaction(['offlineQueue'], 'readwrite');
            const store = transaction.objectStore('offlineQueue');
            await store.add(item);
            this.offlineQueue.push(item);
        } catch (error) {
            console.error('[Copilot] Failed to save to offline queue:', error);
            this.offlineQueue.push(item);
        }
    }
    
    /**
     * Clear offline queue from IndexedDB.
     */
    async clearOfflineQueue() {
        if (!this.db) {
            this.offlineQueue = [];
            return;
        }
        
        try {
            const transaction = this.db.transaction(['offlineQueue'], 'readwrite');
            const store = transaction.objectStore('offlineQueue');
            await store.clear();
            this.offlineQueue = [];
            console.log('[Copilot] Offline queue cleared');
        } catch (error) {
            console.error('[Copilot] Failed to clear offline queue:', error);
            this.offlineQueue = [];
        }
    }
    
    /**
     * Initialize WebSocket connection to copilot namespace.
     */
    initialize() {
        try {
            // Connect to /copilot namespace
            this.socket = io('/copilot', {
                transports: ['websocket', 'polling'],
                upgrade: true,
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionDelayMax: 5000,
                reconnectionAttempts: 5
            });
            
            this.setupEventHandlers();
            console.log('[Copilot] Initializing WebSocket connection...');
            
        } catch (error) {
            console.error('[Copilot] Initialization error:', error);
            if (this.onError) {
                this.onError({ type: 'connection_error', error });
            }
        }
    }
    
    /**
     * Setup WebSocket event handlers.
     */
    setupEventHandlers() {
        // Connection events
        this.socket.on('connect', () => {
            this.connected = true;
            console.log('[Copilot] WebSocket connected');
            this.emitLifecycleEvent('context_rehydrate'); // Event #2
            
            // Notify connection change
            if (this.onConnectionChange) {
                this.onConnectionChange({
                    connected: true,
                    queuedMessages: this.offlineQueue.length
                });
            }
            
            // Replay queued messages on reconnect
            if (this.offlineQueue.length > 0) {
                console.log(`[Copilot] Replaying ${this.offlineQueue.length} queued messages`);
                this.replayOfflineQueue();
            }
        });
        
        this.socket.on('disconnect', (reason) => {
            this.connected = false;
            console.log('[Copilot] WebSocket disconnected:', reason);
            
            // Notify connection change
            if (this.onConnectionChange) {
                this.onConnectionChange({
                    connected: false,
                    reason,
                    queuedMessages: this.offlineQueue.length
                });
            }
        });
        
        this.socket.on('reconnect', (attemptNumber) => {
            console.log(`[Copilot] Reconnected after ${attemptNumber} attempts`);
        });
        
        this.socket.on('reconnect_attempt', (attemptNumber) => {
            console.log(`[Copilot] Reconnection attempt ${attemptNumber}`);
            if (this.onConnectionChange) {
                this.onConnectionChange({
                    connected: false,
                    reconnecting: true,
                    attempt: attemptNumber,
                    queuedMessages: this.offlineQueue.length
                });
            }
        });
        
        this.socket.on('error', (error) => {
            console.error('[Copilot] WebSocket error:', error);
            if (this.onError) {
                this.onError({ type: 'websocket_error', error });
            }
        });
        
        // Copilot events
        this.socket.on('connected', (data) => {
            console.log('[Copilot] Namespace connected:', data);
        });
        
        this.socket.on('copilot_bootstrap_complete', (data) => {
            console.log('[Copilot] Bootstrap complete:', data);
            this.workspace_id = data.workspace_id;
            this.user_id = data.user_id;
            
            if (this.onBootstrapComplete) {
                this.onBootstrapComplete(data.context);
            }
            
            this.emitLifecycleEvent('chips_generate', data.context); // Event #3
        });
        
        this.socket.on('copilot_stream', (event) => {
            this.handleStreamEvent(event);
        });
        
        this.socket.on('copilot_action_result', (result) => {
            console.log('[Copilot] Action result:', result);
            if (this.onActionResult) {
                this.onActionResult(result);
            }
            
            if (result.success) {
                this.emitLifecycleEvent('cross_surface_sync', result); // Event #10
            }
        });
    }
    
    /**
     * Bootstrap copilot - Event #1 in CROWN⁹ lifecycle.
     * Loads context and establishes reasoning channel.
     */
    bootstrap(workspace_id = null) {
        if (!this.connected) {
            console.warn('[Copilot] Not connected, waiting...');
            setTimeout(() => this.bootstrap(workspace_id), 500);
            return;
        }
        
        console.log('[Copilot] Bootstrap initiated');
        this.emitLifecycleEvent('copilot_bootstrap'); // Event #1
        
        this.socket.emit('copilot_bootstrap', {
            workspace_id: workspace_id,
            load_context: true
        });
    }
    
    /**
     * Send query to copilot with streaming response.
     * Events: #5 (query_detect), #6 (context_merge), #7 (reasoning_stream)
     * With offline resilience: queues messages when disconnected.
     */
    sendQuery(message, context = {}) {
        // Queue message if not connected (offline resilience)
        if (!this.connected) {
            console.warn('[Copilot] Not connected, queueing message for later');
            this.queueMessage('query', { message, context });
            
            if (this.onError) {
                this.onError({ 
                    type: 'queued_offline', 
                    message: 'Message queued - will send when reconnected',
                    queued: true
                });
            }
            return;
        }
        
        // Reset metrics
        this.metrics = {
            queryStartTime: performance.now(),
            firstTokenTime: null,
            totalTokens: 0
        };
        
        console.log('[Copilot] Sending query:', message.substring(0, 50) + '...');
        this.emitLifecycleEvent('query_detect', { message }); // Event #5
        
        // Emit query to server
        this.socket.emit('copilot_query', {
            message,
            context,
            session_id: this.conversationSession
        });
    }
    
    /**
     * Queue a message for offline resilience.
     * Messages are persisted to IndexedDB and replayed on reconnect.
     */
    queueMessage(type, data) {
        if (this.offlineQueue.length >= this.maxQueueSize) {
            console.warn('[Copilot] Offline queue full, removing oldest message');
            this.offlineQueue.shift();
        }
        
        const queueItem = {
            type,
            data,
            timestamp: Date.now(),
            session_id: this.conversationSession
        };
        
        this.saveToOfflineQueue(queueItem);
        console.log(`[Copilot] Message queued (${this.offlineQueue.length}/${this.maxQueueSize})`);
        
        // Notify UI about queue status
        if (this.onConnectionChange) {
            this.onConnectionChange({
                connected: false,
                queuedMessages: this.offlineQueue.length
            });
        }
    }
    
    /**
     * Replay offline queue when reconnected.
     * Processes messages in order with delay to prevent overwhelming server.
     */
    async replayOfflineQueue() {
        if (this.isReplayingQueue || this.offlineQueue.length === 0) return;
        
        this.isReplayingQueue = true;
        console.log(`[Copilot] Starting queue replay: ${this.offlineQueue.length} messages`);
        
        // Process queue in order
        while (this.offlineQueue.length > 0 && this.connected) {
            const item = this.offlineQueue[0];
            
            try {
                await this.processQueuedItem(item);
                this.offlineQueue.shift(); // Remove processed item
                
                // Small delay between messages to prevent overwhelming
                await new Promise(resolve => setTimeout(resolve, 100));
                
            } catch (error) {
                console.error('[Copilot] Error replaying queued message:', error);
                break;
            }
        }
        
        // Clear IndexedDB queue
        await this.clearOfflineQueue();
        this.isReplayingQueue = false;
        
        console.log('[Copilot] Queue replay complete');
        
        if (this.onConnectionChange) {
            this.onConnectionChange({
                connected: true,
                queuedMessages: 0,
                queueReplayed: true
            });
        }
    }
    
    /**
     * Process a single queued item.
     */
    async processQueuedItem(item) {
        console.log(`[Copilot] Replaying queued ${item.type} from ${new Date(item.timestamp).toLocaleTimeString()}`);
        
        switch (item.type) {
            case 'query':
                // Reset metrics for replayed query
                this.metrics = {
                    queryStartTime: performance.now(),
                    firstTokenTime: null,
                    totalTokens: 0
                };
                
                this.socket.emit('copilot_query', {
                    message: item.data.message,
                    context: item.data.context,
                    session_id: this.conversationSession,
                    replayed: true,
                    original_timestamp: item.timestamp
                });
                break;
                
            case 'action':
                this.socket.emit('copilot_action', {
                    ...item.data,
                    replayed: true,
                    original_timestamp: item.timestamp
                });
                break;
                
            default:
                console.warn(`[Copilot] Unknown queue item type: ${item.type}`);
        }
    }
    
    /**
     * Handle streaming events from server.
     */
    handleStreamEvent(event) {
        const { type, content, section, error } = event;
        
        switch (type) {
            case 'token':
                // Record first token timing
                if (this.metrics.firstTokenTime === null) {
                    this.metrics.firstTokenTime = performance.now();
                    const latency = this.metrics.firstTokenTime - this.metrics.queryStartTime;
                    console.log(`[Copilot] First token latency: ${latency.toFixed(0)}ms`);
                    
                    if (latency > 600) {
                        console.warn(`[Copilot] First token latency exceeded target (${latency.toFixed(0)}ms > 600ms)`);
                    }
                }
                
                this.metrics.totalTokens++;
                
                if (this.onStreamToken) {
                    this.onStreamToken(content, section);
                }
                break;
            
            case 'section':
                console.log('[Copilot] Section:', section);
                if (this.onStreamSection) {
                    this.onStreamSection(section, content);
                }
                break;
            
            case 'metrics':
                console.log('[Copilot] Metrics:', event);
                
                if (event.event === 'complete') {
                    const totalLatency = performance.now() - this.metrics.queryStartTime;
                    console.log(`[Copilot] Stream complete: ${totalLatency.toFixed(0)}ms total, ` +
                              `${this.metrics.totalTokens} tokens, calm_score=${event.calm_score?.toFixed(2)}`);
                }
                break;
            
            case 'complete':
                console.log('[Copilot] Reasoning stream complete');
                this.emitLifecycleEvent('response_commit', event); // Event #8
                
                if (this.onStreamComplete) {
                    this.onStreamComplete(event.message, event.metrics);
                }
                break;
            
            case 'error':
                console.error('[Copilot] Stream error:', error);
                if (this.onError) {
                    this.onError({ type: 'stream_error', error: error || content });
                }
                break;
        }
    }
    
    /**
     * Execute action from copilot (Event #9).
     * Triggers cross-surface broadcast.
     * With offline resilience: queues actions when disconnected.
     */
    executeAction(action, parameters = {}) {
        // Queue action if not connected (offline resilience)
        if (!this.connected) {
            console.warn('[Copilot] Not connected, queueing action for later');
            this.queueMessage('action', { action, parameters, workspace_id: this.workspace_id });
            
            if (this.onError) {
                this.onError({ 
                    type: 'queued_offline', 
                    message: `Action "${action}" queued - will execute when reconnected`,
                    queued: true
                });
            }
            return;
        }
        
        console.log('[Copilot] Executing action:', action);
        this.emitLifecycleEvent('action_trigger', { action, parameters }); // Event #9
        
        this.socket.emit('copilot_action', {
            action,
            parameters,
            workspace_id: this.workspace_id
        });
    }
    
    /**
     * Get current offline queue status.
     */
    getQueueStatus() {
        return {
            queuedMessages: this.offlineQueue.length,
            maxQueueSize: this.maxQueueSize,
            isReplaying: this.isReplayingQueue,
            connected: this.connected
        };
    }
    
    /**
     * Emit lifecycle event for tracking and UI updates.
     */
    emitLifecycleEvent(eventName, data = {}) {
        const event = new CustomEvent('copilot:lifecycle', {
            detail: {
                event: eventName,
                timestamp: Date.now(),
                data
            }
        });
        window.dispatchEvent(event);
        console.log(`[Copilot Lifecycle] ${eventName}`, data);
    }
    
    /**
     * Generate unique session ID for conversation tracking.
     */
    generateSessionId() {
        return `copilot_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    /**
     * Disconnect and cleanup.
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.connected = false;
            console.log('[Copilot] Disconnected');
        }
    }
}

// Export for use in other modules
window.CopilotStreamingClient = CopilotStreamingClient;
