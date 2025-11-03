/**
 * CROWN ¹⁰ Analytics Page - Real-time KPI Updates
 * Handles analytics_update, analytics_delta events with efficient delta application
 */

class AnalyticsEventManager {
    constructor() {
        this.socket = null;
        this.workspaceId = typeof WORKSPACE_ID !== 'undefined' ? WORKSPACE_ID : 1;
        this.lastSequenceNum = 0;
        this.cache = null;
        
        this.init();
    }
    
    async init() {
        console.log('[Analytics] Initializing CROWN ¹⁰ event synchronization');
        
        // Initialize cache
        await this.initCache();
        
        // Setup WebSocket listeners
        this.setupWebSocketListeners();
        
        // Load last sequence number
        this.lastSequenceNum = this.getLastSequenceNum();
    }
    
    async initCache() {
        try {
            if (typeof CacheManager !== 'undefined') {
                this.cache = new CacheManager();
                await this.cache.init();
                console.log('✅ Analytics cache initialized');
            }
        } catch (error) {
            console.error('❌ Failed to initialize cache:', error);
        }
    }
    
    setupWebSocketListeners() {
        if (!window.io) {
            console.warn('[Analytics] Socket.IO not available');
            return;
        }
        
        // Connect to /analytics namespace
        this.socket = window.io('/analytics', {
            transports: ['websocket', 'polling']
        });
        
        // Connection events
        this.socket.on('connect', () => {
            console.log('✅ Analytics WebSocket connected');
            
            // Join workspace room
            this.socket.emit('join_workspace', {
                workspace_id: this.workspaceId
            });
            
            // Request event replay
            this.socket.emit('request_event_replay', {
                workspace_id: this.workspaceId,
                last_sequence_num: this.lastSequenceNum
            });
        });
        
        this.socket.on('disconnect', () => {
            console.warn('⚠️ Analytics WebSocket disconnected');
        });
        
        this.socket.on('error', (error) => {
            console.error('❌ Analytics WebSocket error:', error);
        });
        
        // Event replay handler
        this.socket.on('event_replay', async (data) => {
            console.log(`📦 Analytics event replay: ${data.count} events`);
            
            if (data.events && data.events.length > 0) {
                for (const event of data.events) {
                    await this.handleEvent(event);
                }
                
                this.saveLastSequenceNum(data.last_sequence_num);
            }
        });
        
        // CROWN ¹⁰ Analytics Event Handlers
        this.socket.on('analytics_update', async (event) => {
            console.log('📊 Analytics updated:', event);
            await this.handleAnalyticsUpdate(event);
        });
        
        this.socket.on('analytics_delta', async (event) => {
            console.log('📈 Analytics delta:', event);
            await this.handleAnalyticsDelta(event);
        });
        
        this.socket.on('analytics_refresh', async (event) => {
            console.log('🔄 Analytics refresh:', event);
            await this.handleAnalyticsRefresh(event);
        });
        
        console.log('✅ Analytics WebSocket listeners registered');
    }
    
    /**
     * Handle analytics update event (full refresh)
     */
    async handleAnalyticsUpdate(event) {
        const { data, sequence_num } = event;
        
        // Update sequence number
        if (sequence_num) {
            this.saveLastSequenceNum(sequence_num);
        }
        
        // Invalidate cache
        if (this.cache) {
            await this.cache.invalidate('analytics');
        }
        
        // Reload analytics with calm pulse animation
        if (window.analyticsManager) {
            await window.analyticsManager.refreshAnalytics();
        }
        
        // Broadcast to other tabs
        if (window.broadcastSync) {
            window.broadcastSync.broadcast('ANALYTICS_REFRESH', data);
        }
    }
    
    /**
     * Handle analytics delta event (efficient partial update)
     * CROWN ¹⁰ Law #4: Cross-Surface Awareness via delta application
     */
    async handleAnalyticsDelta(event) {
        const { data } = event;
        
        if (!data || !data.delta) {
            // No delta - trigger full refresh
            return this.handleAnalyticsUpdate(event);
        }
        
        const delta = data.delta;
        
        // Apply delta updates directly to DOM without full reload
        this.applyDelta(delta);
        
        // Update cache with delta
        if (this.cache) {
            await this.cache.updateAnalyticsDelta(delta);
        }
        
        console.log('📊 Analytics delta applied:', delta);
    }
    
    /**
     * Handle analytics refresh event
     */
    async handleAnalyticsRefresh(event) {
        const { data } = event;
        
        // Invalidate cache
        if (this.cache) {
            await this.cache.invalidate('analytics');
        }
        
        // Reload analytics
        if (window.analyticsManager) {
            await window.analyticsManager.refreshAnalytics();
        }
    }
    
    /**
     * Apply delta to analytics KPIs with calm pulse animation
     * Updates individual metrics without full page reload
     */
    applyDelta(delta) {
        const metrics = {
            total_meetings: '[data-metric="total-meetings"]',
            total_tasks: '[data-metric="total-tasks"]',
            action_items: '[data-metric="action-items"]',
            completion_rate: '[data-metric="completion-rate"]',
            hours_saved: '[data-metric="hours-saved"]',
            avg_meeting_length: '[data-metric="avg-meeting-length"]'
        };
        
        // Apply each delta with calm pulse animation
        for (const [key, selector] of Object.entries(metrics)) {
            if (delta[key] !== undefined) {
                const element = document.querySelector(selector);
                if (element) {
                    // Add calm pulse animation
                    element.classList.add('calm-pulse');
                    
                    // Update value
                    const valueElement = element.querySelector('.metric-value') || element;
                    valueElement.textContent = this.formatMetricValue(key, delta[key]);
                    
                    // Remove animation after completion
                    setTimeout(() => {
                        element.classList.remove('calm-pulse');
                    }, 400);
                }
            }
        }
        
        // Update delta indicators (arrows/percentages)
        if (delta.changes) {
            for (const [key, change] of Object.entries(delta.changes)) {
                this.updateChangeIndicator(key, change);
            }
        }
    }
    
    /**
     * Format metric value based on type
     */
    formatMetricValue(key, value) {
        if (key === 'completion_rate') {
            return `${value}%`;
        }
        if (key === 'avg_meeting_length') {
            return `${value}m`;
        }
        if (key === 'hours_saved') {
            return `${value}h`;
        }
        return value.toString();
    }
    
    /**
     * Update change indicator with arrow and percentage
     */
    updateChangeIndicator(key, change) {
        const element = document.querySelector(`[data-metric="${key}"]`);
        if (!element) return;
        
        let changeElement = element.querySelector('.metric-change');
        if (!changeElement) {
            changeElement = document.createElement('span');
            changeElement.className = 'metric-change';
            element.appendChild(changeElement);
        }
        
        const isPositive = change.value > 0;
        const arrow = isPositive ? '↑' : '↓';
        const className = isPositive ? 'positive' : 'negative';
        
        changeElement.className = `metric-change ${className}`;
        changeElement.textContent = `${arrow} ${Math.abs(change.value)}%`;
        
        // Add pulse animation
        changeElement.classList.add('calm-pulse');
        setTimeout(() => {
            changeElement.classList.remove('calm-pulse');
        }, 400);
    }
    
    /**
     * Generic event handler
     */
    async handleEvent(event) {
        const handlers = {
            'analytics_update': () => this.handleAnalyticsUpdate(event),
            'analytics_delta': () => this.handleAnalyticsDelta(event),
            'analytics_refresh': () => this.handleAnalyticsRefresh(event)
        };
        
        const handler = handlers[event.event_type];
        if (handler) {
            await handler();
        }
    }
    
    /**
     * Sequence number tracking
     */
    getLastSequenceNum() {
        try {
            const stored = localStorage.getItem(`mina_analytics_last_seq_${this.workspaceId}`);
            return stored ? parseInt(stored, 10) : 0;
        } catch (error) {
            return 0;
        }
    }
    
    saveLastSequenceNum(sequenceNum) {
        try {
            localStorage.setItem(
                `mina_analytics_last_seq_${this.workspaceId}`,
                sequenceNum.toString()
            );
        } catch (error) {
            console.error('Failed to save sequence number:', error);
        }
    }
}

// Auto-initialize when DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.analyticsEvents = new AnalyticsEventManager();
    });
} else {
    window.analyticsEvents = new AnalyticsEventManager();
}
