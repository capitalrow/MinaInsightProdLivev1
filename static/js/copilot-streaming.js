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
        
        this.initialize();
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
        });
        
        this.socket.on('disconnect', () => {
            this.connected = false;
            console.log('[Copilot] WebSocket disconnected');
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
     */
    sendQuery(message, context = {}) {
        if (!this.connected) {
            console.error('[Copilot] Not connected');
            if (this.onError) {
                this.onError({ type: 'not_connected', message: 'WebSocket not connected' });
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
     */
    executeAction(action, parameters = {}) {
        if (!this.connected) {
            console.error('[Copilot] Not connected');
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
