/**
 * WebSocket Manager - CROWN⁴ Real-time Synchronization
 * 
 * Manages Socket.IO connections to multiple namespaces:
 * - /dashboard: Dashboard real-time updates
 * - /tasks: Task synchronization  
 * - /analytics: Analytics refresh
 * - /meetings: Meeting updates
 * 
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Workspace room management
 * - Event sequencing validation
 * - Cross-tab synchronization via BroadcastChannel
 */

class WebSocketManager {
    constructor(telemetry = null) {
        this.sockets = {};
        this.workspaceId = null;
        this.isConnected = false;
        this.reconnectAttempts = {};
        this.maxReconnectAttempts = 5;
        this.baseReconnectDelay = 1000; // Start with 1 second
        this.maxReconnectDelay = 30000; // Max 30 seconds
        this.eventHandlers = {};
        this.lastEventId = null;
        this.lastSequenceNum = {};
        this.telemetry = telemetry; // CROWN⁴ telemetry for event propagation tracking
        
        // BroadcastChannel for cross-tab sync
        if ('BroadcastChannel' in window) {
            this.broadcastChannel = new BroadcastChannel('mina_sync');
            this.setupBroadcastChannel();
        }
        
        // Store for event sequencing
        this.eventSequence = [];
        this.lastAppliedSequence = 0;
        
        // AbortController for cleanup on reconnect
        this.abortControllers = {};
        this.pendingRequests = new Map();
    }
    
    /**
     * Initialize WebSocket connections
     * @param {number} workspaceId - Current workspace ID
     * @param {Array<string>} namespaces - Namespaces to connect (default: ['dashboard'])
     */
    init(workspaceId, namespaces = ['dashboard']) {
        this.workspaceId = workspaceId;
        
        namespaces.forEach(namespace => {
            this.connect(namespace);
        });
        
        // Set up heartbeat
        this.startHeartbeat();
        
        console.log(`🔌 WebSocket Manager initialized for workspace ${workspaceId}`);
    }
    
    /**
     * Check if connected to a specific namespace (or any namespace if none specified)
     * @param {string} [namespace] - Optional namespace to check (e.g., 'tasks', '/tasks')
     * @returns {boolean} True if connected
     */
    getConnectionStatus(namespace) {
        if (!namespace) {
            return this.isConnected;
        }
        
        // Normalize namespace (remove leading slash if present)
        const normalizedNs = namespace.startsWith('/') ? namespace.slice(1) : namespace;
        const socket = this.sockets[normalizedNs];
        
        return socket && socket.connected;
    }
    
    /**
     * Connect to a specific namespace
     * @param {string} namespace - Namespace name (e.g., 'dashboard', 'tasks')
     */
    connect(namespace) {
        if (this.sockets[namespace]) {
            console.warn(`Already connected to /${namespace}`);
            return;
        }
        
        // Initialize reconnect attempts counter for this namespace
        if (!this.reconnectAttempts[namespace]) {
            this.reconnectAttempts[namespace] = 0;
        }
        
        // Calculate exponential backoff delay
        const delay = this.calculateBackoffDelay(namespace);
        
        // Create Socket.IO connection with exponential backoff
        const socket = io(`/${namespace}`, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionDelay: delay,
            reconnectionDelayMax: this.maxReconnectDelay,
            reconnectionAttempts: this.maxReconnectAttempts,
            randomizationFactor: 0.5 // Add jitter to prevent thundering herd
        });
        
        // Connection event handlers
        socket.on('connect', () => {
            console.log(`✅ Connected to /${namespace} namespace`);
            this.isConnected = true;
            this.reconnectAttempts[namespace] = 0;
            
            // Abort any pending requests from before reconnection
            this.abortPendingRequests(namespace);
            
            // Join workspace room
            if (this.workspaceId) {
                socket.emit('join_workspace', { workspace_id: this.workspaceId });
            }
            
            // Request event ledger replay to catch up on missed events
            this.requestEventReplay(namespace);
            
            // Emit connection status
            this.emit('connection_status', { namespace, connected: true });
        });
        
        socket.on('disconnect', (reason) => {
            console.warn(`⚠️ Disconnected from /${namespace}: ${reason}`);
            this.isConnected = false;
            this.emit('connection_status', { namespace, connected: false, reason });
        });
        
        socket.on('connect_error', (error) => {
            console.error(`❌ Connection error on /${namespace}:`, error);
            this.reconnectAttempts[namespace]++;
            
            const delay = this.calculateBackoffDelay(namespace);
            console.log(`🔄 Will retry /${namespace} in ${delay}ms (attempt ${this.reconnectAttempts[namespace]}/${this.maxReconnectAttempts})`);
            
            if (this.reconnectAttempts[namespace] >= this.maxReconnectAttempts) {
                console.error(`❌ Max reconnection attempts reached for /${namespace}`);
                this.abortPendingRequests(namespace);
                this.emit('connection_failed', { namespace, error, attempts: this.reconnectAttempts[namespace] });
            }
        });
        
        socket.on('error', (error) => {
            console.error(`❌ Socket error on /${namespace}:`, error);
            this.emit('socket_error', { namespace, error });
        });
        
        // Acknowledgment events
        socket.on('connected', (data) => {
            console.log(`📡 ${namespace} connection acknowledged:`, data);
        });
        
        socket.on('joined_workspace', (data) => {
            console.log(`🏢 Joined workspace room: workspace_${data.workspace_id}`);
        });
        
        // Register CROWN⁴ event listeners
        this.registerCROWNEvents(socket, namespace);
        
        // Register external handlers (CROWN⁴.5 task handlers, etc.)
        this._registerExternalHandlers(socket, namespace);
        
        this.sockets[namespace] = socket;
    }
    
    /**
     * Register CROWN⁴ event listeners
     * @param {Socket} socket - Socket.IO socket instance
     * @param {string} namespace - Namespace name
     */
    registerCROWNEvents(socket, namespace) {
        // Event 2: session_update:created
        socket.on('session_update:created', (data) => {
            console.log('📬 New session created:', data);
            this.handleSequencedEvent('session_update:created', data, namespace);
        });
        
        // Event 6: task_update
        socket.on('task_update', (data) => {
            console.log('✅ Task updated:', data);
            this.handleSequencedEvent('task_update', data, namespace);
        });
        
        // Event 7: analytics_refresh
        socket.on('analytics_refresh', (data) => {
            console.log('📊 Analytics refreshed:', data);
            this.handleSequencedEvent('analytics_refresh', data, namespace);
        });
        
        // Event 8: dashboard_refresh
        socket.on('dashboard_refresh', (data) => {
            console.log('🔄 Dashboard refreshed:', data);
            this.handleSequencedEvent('dashboard_refresh', data, namespace);
        });
        
        // Event 12: meeting_update
        socket.on('meeting_update', (data) => {
            console.log('📝 Meeting updated:', data);
            this.handleSequencedEvent('meeting_update', data, namespace);
        });
        
        // Event 13: dashboard_idle_sync
        socket.on('dashboard_idle_sync', (data) => {
            console.log('⏱️ Background sync:', data);
            this.handleSequencedEvent('dashboard_idle_sync', data, namespace);
        });
        
        // Event 14: insight_reminder (CROWN⁴ Phase 5)
        socket.on('insight_reminder', (data) => {
            console.log('💡 Insight reminder received:', data);
            this.handleSequencedEvent('insight_reminder', data, namespace);
            
            // Display toast notification with reminder
            if (data.data && data.data.reminder && window.toast) {
                const reminder = data.data.reminder;
                window.toast.info(
                    `${reminder.title}: ${reminder.message}`,
                    6000,  // 6 second duration
                    {
                        actionCallback: reminder.action_url ? () => {
                            window.location.href = reminder.action_url;
                        } : null,
                        actionText: reminder.action_text || 'View'
                    }
                );
            }
        });
        
    }
    
    /**
     * Register external event handlers for a namespace (CROWN⁴.5 integration)
     * Stores callbacks that will be invoked after event sequencing validation.
     * 
     * @param {string} namespace - Namespace (e.g., 'tasks')
     * @param {Object} handlers - Map of event names to handler functions
     * 
     * Example:
     *   wsManager.registerHandlers('tasks', {
     *     'bootstrap_response': (data) => { ... },
     *     'task_created': (data) => { ... }
     *   });
     */
    registerHandlers(namespace, handlers) {
        if (!this.eventHandlers[namespace]) {
            this.eventHandlers[namespace] = {};
        }
        
        // Store handlers (will be invoked by handleSequencedEvent)
        Object.assign(this.eventHandlers[namespace], handlers);
        
        // If socket already exists, register ONE-TIME socket listeners
        // that route through handleSequencedEvent
        const socket = this.sockets[namespace];
        if (socket) {
            Object.keys(handlers).forEach(eventName => {
                // Check if we already registered a listener for this event
                const listenerKey = `_registered_${eventName}`;
                if (!socket[listenerKey]) {
                    socket.on(eventName, (data) => {
                        this.handleSequencedEvent(eventName, data, namespace);
                    });
                    socket[listenerKey] = true;
                    console.log(`📡 Registered listener: ${eventName} on /${namespace}`);
                }
            });
        }
        
        console.log(`✅ ${Object.keys(handlers).length} handlers registered for /${namespace}`);
    }
    
    /**
     * Register socket listeners for external handlers (called during connection)
     * This ensures handlers are attached when namespace connects/reconnects
     * @param {Socket} socket - Socket instance
     * @param {string} namespace - Namespace name
     */
    _registerExternalHandlers(socket, namespace) {
        if (!this.eventHandlers[namespace]) {
            return;
        }
        
        Object.keys(this.eventHandlers[namespace]).forEach(eventName => {
            // Prevent duplicate registration on reconnect
            const listenerKey = `_registered_${eventName}`;
            if (!socket[listenerKey]) {
                socket.on(eventName, (data) => {
                    this.handleSequencedEvent(eventName, data, namespace);
                });
                socket[listenerKey] = true;
                console.log(`📡 Registered listener: ${eventName} on /${namespace}`);
            }
        });
    }
    
    /**
     * Handle sequenced event with ordering validation
     * @param {string} eventName - Event name
     * @param {Object} data - Event data
     * @param {string} namespace - Namespace
     */
    handleSequencedEvent(eventName, data, namespace) {
        const { event_id, sequence_num, checksum, timestamp } = data;
        const receivedTimestamp = Date.now();
        
        // Validate event sequencing
        if (sequence_num) {
            // Track last sequence number per namespace for event replay
            const lastSeq = this.lastSequenceNum[namespace] || 0;
            
            if (sequence_num < lastSeq) {
                console.warn(`⚠️ Out-of-order event ignored: ${eventName} (seq ${sequence_num} < ${lastSeq}) on /${namespace}`);
                return;
            }
            
            // Detect sequence gaps (CROWN⁴ zero-desync requirement)
            if (sequence_num > lastSeq + 1 && lastSeq > 0) {
                const lag = sequence_num - lastSeq - 1;
                console.warn(`⚠️ Sequence gap detected: expected ${lastSeq + 1}, got ${sequence_num} (gap: ${lag}) on /${namespace}`);
                
                // Track sequence lag in telemetry
                if (this.telemetry) {
                    this.telemetry.recordSequenceLag(lastSeq + 1, sequence_num);
                }
            }
            
            // Update last sequence number for this namespace
            this.lastSequenceNum[namespace] = sequence_num;
            this.lastAppliedSequence = sequence_num;
        }
        
        // Track event propagation latency (CROWN⁴ <300ms target)
        if (this.telemetry && timestamp) {
            // Normalize timestamp (could be ISO8601 string or milliseconds)
            const sentTimestamp = typeof timestamp === 'number' ? timestamp : Date.parse(timestamp);
            
            // Only record if timestamp is valid
            if (!isNaN(sentTimestamp)) {
                this.telemetry.recordEventPropagation(
                    event_id || `${eventName}_${sequence_num}`,
                    sentTimestamp,
                    receivedTimestamp
                );
            } else {
                console.warn(`⚠️ Invalid timestamp for event ${eventName}, cannot track propagation`);
            }
        }
        
        // Track last event ID for event replay
        if (event_id) {
            this.lastEventId = event_id;
        }
        
        // Store event
        this.eventSequence.push({
            event_id,
            event_name: eventName,
            sequence_num,
            data: data.data,
            timestamp: new Date(timestamp),
            namespace
        });
        
        // Keep last 100 events
        if (this.eventSequence.length > 100) {
            this.eventSequence.shift();
        }
        
        // Emit to local handlers
        this.emit(eventName, data);
        
        // Invoke namespace-specific registered handlers (CROWN⁴.5)
        if (this.eventHandlers[namespace] && this.eventHandlers[namespace][eventName]) {
            try {
                this.eventHandlers[namespace][eventName](data);
            } catch (error) {
                console.error(`Error in ${namespace}/${eventName} handler:`, error);
            }
        }
        
        // Broadcast to other tabs
        if (this.broadcastChannel) {
            this.broadcastChannel.postMessage({
                type: 'event',
                eventName,
                data,
                namespace,
                timestamp: Date.now()
            });
        }
    }
    
    /**
     * Register event handler
     * @param {string} eventName - Event name
     * @param {Function} handler - Handler function
     */
    on(eventName, handler) {
        if (!this.eventHandlers[eventName]) {
            this.eventHandlers[eventName] = [];
        }
        this.eventHandlers[eventName].push(handler);
    }
    
    /**
     * Emit event to registered handlers
     * @param {string} eventName - Event name
     * @param {Object} data - Event data
     */
    emit(eventName, data) {
        if (this.eventHandlers[eventName]) {
            this.eventHandlers[eventName].forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in event handler for ${eventName}:`, error);
                }
            });
        }
    }
    
    /**
     * Setup BroadcastChannel for cross-tab sync
     */
    setupBroadcastChannel() {
        this.broadcastChannel.addEventListener('message', (event) => {
            const { type, eventName, data } = event.data;
            
            if (type === 'event') {
                // Re-emit event in this tab
                this.emit(eventName, data);
            }
        });
    }
    
    /**
     * Calculate exponential backoff delay for reconnection
     * Formula: min(baseDelay * 2^attempts, maxDelay)
     * @param {string} namespace - Namespace
     * @returns {number} Delay in milliseconds
     */
    calculateBackoffDelay(namespace) {
        const attempts = this.reconnectAttempts[namespace] || 0;
        const exponentialDelay = this.baseReconnectDelay * Math.pow(2, attempts);
        const cappedDelay = Math.min(exponentialDelay, this.maxReconnectDelay);
        
        // Add jitter (±20%) to prevent thundering herd
        const jitter = cappedDelay * 0.2 * (Math.random() - 0.5);
        const finalDelay = Math.round(cappedDelay + jitter);
        
        return finalDelay;
    }
    
    /**
     * Abort all pending requests for a namespace
     * Called on reconnection to clean up stale requests
     * @param {string} namespace - Namespace
     */
    abortPendingRequests(namespace) {
        // Abort controller for this namespace
        if (this.abortControllers[namespace]) {
            console.log(`🛑 Aborting ${this.pendingRequests.size} pending requests for /${namespace}`);
            this.abortControllers[namespace].abort();
            delete this.abortControllers[namespace];
        }
        
        // Clear pending requests map entries for this namespace
        for (const [key, value] of this.pendingRequests.entries()) {
            if (value.namespace === namespace) {
                this.pendingRequests.delete(key);
            }
        }
        
        // Create new abort controller for future requests
        this.abortControllers[namespace] = new AbortController();
        
        console.log(`✅ Pending requests cleaned up for /${namespace}`);
    }
    
    /**
     * Request event ledger replay from server
     * Fetches missed events since last received event
     * Always requests replay to ensure zero-data-loss, even on first connection
     * @param {string} namespace - Namespace
     */
    requestEventReplay(namespace) {
        const lastSeq = this.lastSequenceNum[namespace] || 0;
        
        console.log(`📼 Requesting event replay for /${namespace} from sequence ${lastSeq}${lastSeq === 0 ? ' (initial sync)' : ''}`);
        
        // CRITICAL: Register listener BEFORE emitting request to avoid race condition
        // If we emit first, server might respond before listener is registered
        const socket = this.sockets[namespace];
        if (socket) {
            socket.once('event_replay', (data) => {
                const eventCount = data.events?.length || 0;
                console.log(`📼 Received ${eventCount} replayed events for /${namespace}${lastSeq === 0 ? ' (initial sync)' : ''}`);
                
                // Process replayed events in order
                if (data.events && Array.isArray(data.events)) {
                    data.events.forEach(event => {
                        this.handleSequencedEvent(event.event_name, event, namespace);
                    });
                    
                    console.log(`✅ Event replay completed for /${namespace} (${eventCount} events processed)`);
                } else {
                    console.log(`ℹ️ No events to replay for /${namespace}`);
                }
            });
        }
        
        // Now emit the request - listener is already registered
        // Server will handle both cases:
        // - lastSeq = 0: Send recent events or full initial state
        // - lastSeq > 0: Send events since that sequence number
        this.send(namespace, 'request_event_replay', {
            workspace_id: this.workspaceId,
            last_sequence_num: lastSeq,
            namespace: namespace,
            is_initial_sync: lastSeq === 0
        });
    }
    
    /**
     * Send event to server
     * @param {string} namespace - Namespace
     * @param {string} eventName - Event name  
     * @param {Object} data - Event data
     */
    send(namespace, eventName, data) {
        if (this.sockets[namespace]) {
            this.sockets[namespace].emit(eventName, data);
        } else {
            console.warn(`Socket /${namespace} not connected`);
        }
    }

    /**
     * Send event to server and wait for acknowledgment
     * @param {string} eventName - Event name
     * @param {Object} data - Event data
     * @param {string} namespace - Namespace (e.g., '/tasks')
     * @returns {Promise<Object>} Server response
     */
    async emitWithAck(eventName, data, namespace = 'dashboard') {
        // Remove leading slash if present
        const ns = namespace.startsWith('/') ? namespace.substring(1) : namespace;
        
        const socket = this.sockets[ns];
        if (!socket) {
            throw new Error(`Socket /${ns} not connected`);
        }
        
        if (!socket.connected) {
            throw new Error(`Socket /${ns} is not currently connected`);
        }
        
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error(`Timeout waiting for ${eventName} acknowledgment on /${ns}`));
            }, 10000); // 10 second timeout
            
            socket.emit(eventName, data, (response) => {
                clearTimeout(timeout);
                
                // Check if server returned an error
                if (response && response.success === false) {
                    reject(new Error(response.error || 'Server request failed'));
                } else {
                    resolve(response);
                }
            });
        });
    }
    
    /**
     * Request dashboard sync
     */
    requestSync() {
        this.send('dashboard', 'request_sync', {
            workspace_id: this.workspaceId,
            client_checksum: this.generateChecksum()
        });
    }
    
    /**
     * Generate checksum for current state (placeholder)
     */
    generateChecksum() {
        // TODO: Implement MD5 checksum of dashboard data
        return Date.now().toString();
    }
    
    /**
     * Start heartbeat to keep connection alive
     */
    startHeartbeat() {
        setInterval(() => {
            Object.keys(this.sockets).forEach(namespace => {
                const socket = this.sockets[namespace];
                if (socket.connected) {
                    socket.emit('ping', { timestamp: Date.now() });
                }
            });
        }, 25000); // Every 25 seconds
    }
    
    /**
     * Disconnect from namespace
     * @param {string} namespace - Namespace to disconnect
     */
    disconnect(namespace) {
        if (this.sockets[namespace]) {
            this.sockets[namespace].disconnect();
            delete this.sockets[namespace];
            console.log(`🔌 Disconnected from /${namespace}`);
        }
    }
    
    /**
     * Disconnect all namespaces
     */
    disconnectAll() {
        Object.keys(this.sockets).forEach(namespace => {
            this.disconnect(namespace);
        });
        
        if (this.broadcastChannel) {
            this.broadcastChannel.close();
        }
        
        console.log('🔌 All WebSocket connections closed');
    }
    
    /**
     * Get connection status
     * @returns {Object} Connection status for each namespace
     */
    getStatus() {
        const status = {};
        Object.keys(this.sockets).forEach(namespace => {
            status[namespace] = {
                connected: this.sockets[namespace].connected,
                id: this.sockets[namespace].id
            };
        });
        return status;
    }
}

// Create global singleton instance
// Telemetry will be injected by dashboard.js if available
window.wsManager = new WebSocketManager(window.crownTelemetry || null);

// Auto-cleanup on page unload
window.addEventListener('beforeunload', () => {
    window.wsManager.disconnectAll();
});
