/**
 * Dashboard JavaScript
 * Handles dynamic data loading and real-time updates for the Mina dashboard
 */

class MinaDashboard {
    constructor() {
        this.apiBase = '/api';
        this.refreshInterval = 30000; // 30 seconds
        this.refreshTimers = new Map();
        this.cache = null;
        this.workspaceId = typeof WORKSPACE_ID !== 'undefined' ? WORKSPACE_ID : 1;
        this.performanceMetrics = {
            bootstrapStart: null,
            cacheHydrationTime: null,
            networkFetchTime: null,
            totalBootstrapTime: null
        };
        this.telemetry = null;
        this.init();
    }

    async init() {
        console.log('[Dashboard] Initializing Mina Dashboard (CROWN⁴ Cache-First)');
        this.performanceMetrics.bootstrapStart = performance.now();
        
        // Initialize CROWN⁴ Telemetry
        if (typeof CROWNTelemetry !== 'undefined') {
            this.telemetry = new CROWNTelemetry(this.workspaceId);
            await this.telemetry.init();
            
            // Make telemetry globally available for WebSocket manager
            window.crownTelemetry = this.telemetry;
            
            // Inject telemetry into existing WebSocket manager if it exists
            if (window.wsManager) {
                window.wsManager.telemetry = this.telemetry;
                console.log('📊 Telemetry injected into WebSocket manager');
            }
        }
        
        // Initialize IndexedDB cache
        await this.initCache();
        
        // Cache-first bootstrap: Load from cache first, then network
        await this.cacheFirstBootstrap();
        
        this.setupEventListeners();
        this.startAutoRefresh();
        
        // Start CROWN ¹⁰ 30-second reconciliation cycle
        if (typeof ReconciliationCycle !== 'undefined') {
            this.reconciliation = new ReconciliationCycle(this.workspaceId);
            this.reconciliation.start();
            console.log('✅ ETag reconciliation cycle started (30s interval)');
            
            // Make globally available for debugging
            window.reconciliation = this.reconciliation;
        }
        
        // Log performance metrics
        this.performanceMetrics.totalBootstrapTime = performance.now() - this.performanceMetrics.bootstrapStart;
        console.log(`⚡ Dashboard bootstrap: ${this.performanceMetrics.totalBootstrapTime.toFixed(0)}ms (target: <200ms)`);
        console.log(`   ├─ Cache hydration: ${this.performanceMetrics.cacheHydrationTime?.toFixed(0) || 'N/A'}ms`);
        console.log(`   └─ Network fetch: ${this.performanceMetrics.networkFetchTime?.toFixed(0) || 'N/A'}ms`);
        
        // Emit bootstrap complete event for PerformanceValidator
        document.dispatchEvent(new CustomEvent('task:bootstrap:complete', {
            detail: {
                first_paint_ms: this.performanceMetrics.totalBootstrapTime,
                cache_hydration_ms: this.performanceMetrics.cacheHydrationTime,
                network_fetch_ms: this.performanceMetrics.networkFetchTime
            }
        }));
        
        // Record bootstrap metrics in telemetry
        if (this.telemetry) {
            await this.telemetry.recordBootstrap(this.performanceMetrics);
            
            // Initialize performance monitor UI (Ctrl+Shift+P to toggle)
            if (typeof CROWNPerformanceMonitor !== 'undefined') {
                new CROWNPerformanceMonitor(this.telemetry);
            }
        }
    }
    
    /**
     * Initialize IndexedDB cache
     */
    async initCache() {
        try {
            if (typeof IndexedDBCache === 'undefined') {
                console.warn('⚠️  IndexedDBCache not available, falling back to network-only');
                return;
            }
            
            this.cache = new IndexedDBCache(this.workspaceId);
            await this.cache.init();
            console.log('✅ IndexedDB cache initialized');
        } catch (error) {
            console.error('❌ Failed to initialize cache:', error);
            this.cache = null;
        }
    }
    
    /**
     * CROWN⁴ Cache-First Bootstrap Pattern
     * Target: <200ms bootstrap from cache
     */
    async cacheFirstBootstrap() {
        const cacheStart = performance.now();
        
        // Try cache first
        if (this.cache) {
            try {
                const [cachedMeetings, cachedTasks, cachedAnalytics] = await Promise.all([
                    this.cache.getCachedMeetings(),
                    this.cache.getAll(this.cache.STORES.TASKS),
                    this.cache.getAll(this.cache.STORES.ANALYTICS)
                ]);
                
                // Hydrate UI from cache immediately
                if (cachedMeetings.data && cachedMeetings.data.length > 0) {
                    this.renderRecentMeetings(cachedMeetings.data.slice(0, 5));
                    console.log(`📦 Cache hit: ${cachedMeetings.count} meetings (checksum: ${cachedMeetings.checksum?.substring(0, 8)}...)`);
                    
                    // Track cache hit
                    if (this.telemetry) {
                        this.telemetry.recordCacheAccess(true);
                    }
                } else {
                    // Track cache miss
                    if (this.telemetry) {
                        this.telemetry.recordCacheAccess(false);
                    }
                }
                
                this.performanceMetrics.cacheHydrationTime = performance.now() - cacheStart;
                console.log(`⚡ Cache hydration: ${this.performanceMetrics.cacheHydrationTime.toFixed(0)}ms`);
            } catch (error) {
                console.error('❌ Cache hydration failed:', error);
            }
        }
        
        // Fetch fresh data from network in background
        const networkStart = performance.now();
        await this.loadDashboardData();
        this.performanceMetrics.networkFetchTime = performance.now() - networkStart;
    }

    /**
     * Load all dashboard data
     */
    async loadDashboardData() {
        try {
            await Promise.all([
                this.loadStats(),
                this.loadRecentMeetings(),
                this.loadMyTasks(),
                this.loadAnalyticsOverview()
            ]);
        } catch (error) {
            console.error('[Dashboard] Failed to load dashboard data:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    /**
     * Load dashboard statistics
     */
    async loadStats() {
        try {
            const [meetingsResponse, tasksResponse] = await Promise.all([
                fetch(`${this.apiBase}/meetings/stats`),
                fetch(`${this.apiBase}/tasks/stats`)
            ]);

            const meetingsStats = await meetingsResponse.json();
            const tasksStats = await tasksResponse.json();

            if (meetingsStats.success) {
                this.updateStatsCards(meetingsStats.stats, tasksStats.stats);
            }
        } catch (error) {
            console.error('[Dashboard] Failed to load stats:', error);
        }
    }

    /**
     * Update statistics cards
     */
    updateStatsCards(meetingStats, taskStats) {
        // Update meeting stats
        this.updateStatCard('total-meetings', meetingStats.total_meetings || 0);
        this.updateStatCard('this-week-meetings', meetingStats.this_week_meetings || 0);
        
        // Update task stats
        this.updateStatCard('total-tasks', taskStats?.total_tasks || 0);
        this.updateStatCard('task-completion-rate', `${taskStats?.completion_rate || 0}%`);
        
        // Update active meetings
        this.updateStatCard('active-meetings', meetingStats.live_meetings || 0);
        
        // Update my active tasks
        this.updateStatCard('my-active-tasks', taskStats?.my_active_tasks || 0);
    }

    /**
     * Update individual stat card
     */
    updateStatCard(cardId, value) {
        const card = document.querySelector(`[data-stat="${cardId}"]`);
        if (card) {
            const valueElement = card.querySelector('.stat-value');
            if (valueElement) {
                valueElement.textContent = value;
            }
        }
    }

    /**
     * Load recent meetings
     */
    async loadRecentMeetings() {
        try {
            const response = await fetch(`${this.apiBase}/meetings/recent?limit=5`);
            const data = await response.json();

            if (data.success) {
                this.renderRecentMeetings(data.meetings);
                
                // Cache meetings for next bootstrap
                if (this.cache && data.meetings) {
                    try {
                        await this.cache.cacheMeetings(data.meetings, data.checksum || this.generateChecksum(data.meetings));
                    } catch (error) {
                        console.warn('⚠️  Failed to cache meetings:', error);
                    }
                }
            }
        } catch (error) {
            console.error('[Dashboard] Failed to load recent meetings:', error);
        }
    }

    /**
     * Render recent meetings list
     */
    renderRecentMeetings(meetings) {
        const container = document.getElementById('recent-meetings-list');
        if (!container) return;

        if (meetings.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p class="text-gray-500">No meetings yet.</p>
                    <a href="/live" class="btn btn-primary btn-sm">Start your first meeting</a>
                </div>
            `;
            return;
        }

        container.innerHTML = meetings.map(meeting => `
            <div class="meeting-item" data-meeting-id="${meeting.id}">
                <div class="meeting-info">
                    <div class="meeting-title">${this.escapeHtml(meeting.title)}</div>
                    <div class="meeting-date">${this.formatDate(meeting.created_at)}</div>
                </div>
                <div class="meeting-actions">
                    <span class="meeting-status status-${meeting.status}">
                        ${this.capitalizeFirst(meeting.status)}
                    </span>
                    <button class="btn-icon" onclick="dashboard.viewMeeting(${meeting.id})" title="View Details">
                        <i data-feather="eye"></i>
                    </button>
                </div>
            </div>
        `).join('');

        // Re-initialize feather icons
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    }

    /**
     * Load user's tasks
     */
    async loadMyTasks() {
        try {
            const response = await fetch(`${this.apiBase}/tasks/my-tasks`);
            const data = await response.json();

            if (data.success) {
                this.renderMyTasks(data.tasks);
                
                // Cache tasks for next bootstrap
                if (this.cache && data.tasks) {
                    try {
                        const allTasks = [...data.tasks.todo, ...data.tasks.in_progress, ...data.tasks.completed];
                        if (allTasks.length > 0) {
                            await this.cache.cacheTasks(allTasks);
                        }
                    } catch (error) {
                        console.warn('⚠️  Failed to cache tasks:', error);
                    }
                }
            }
        } catch (error) {
            console.error('[Dashboard] Failed to load my tasks:', error);
        }
    }

    /**
     * Render user's tasks
     */
    renderMyTasks(taskGroups) {
        const container = document.getElementById('my-tasks-list');
        if (!container) return;

        const allTasks = [
            ...taskGroups.todo,
            ...taskGroups.in_progress,
            ...taskGroups.completed.slice(0, 3) // Show only 3 completed tasks
        ];

        if (allTasks.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p class="text-gray-500">No tasks assigned.</p>
                    <p class="text-gray-400 text-sm">Tasks will appear here when created from meetings.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = allTasks.map(task => `
            <div class="task-item" data-task-id="${task.id}">
                <div class="task-content">
                    <h3 class="task-title">${this.escapeHtml(task.title)}</h3>
                    <div class="task-meta">
                        <span class="task-status status-${task.status}">
                            ${this.capitalizeFirst(task.status)}
                        </span>
                        <span class="task-priority priority-${task.priority}">
                            ${this.capitalizeFirst(task.priority)} priority
                        </span>
                        ${task.due_date ? `<span class="task-due">Due ${this.formatDate(task.due_date)}</span>` : ''}
                    </div>
                </div>
                <div class="task-actions">
                    <button class="btn-icon" onclick="dashboard.updateTaskStatus(${task.id}, '${this.getNextStatus(task.status)}')" title="Update Status">
                        <i data-feather="${this.getStatusIcon(task.status)}"></i>
                    </button>
                </div>
            </div>
        `).join('');

        // Re-initialize feather icons
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    }

    /**
     * Load analytics overview
     */
    async loadAnalyticsOverview() {
        try {
            const response = await fetch(`${this.apiBase}/analytics/dashboard?days=7`);
            const data = await response.json();

            if (data.success) {
                this.renderAnalyticsOverview(data.dashboard);
            }
        } catch (error) {
            console.error('[Dashboard] Failed to load analytics:', error);
        }
    }

    /**
     * Render analytics overview
     */
    renderAnalyticsOverview(dashboard) {
        // Update effectiveness score
        this.updateAnalyticsWidget('effectiveness-score', dashboard.averages.effectiveness, '%');
        
        // Update engagement score
        this.updateAnalyticsWidget('engagement-score', dashboard.averages.engagement, '%');
        
        // Update sentiment score
        this.updateAnalyticsWidget('sentiment-score', dashboard.averages.sentiment, '%');
        
        // Update productivity metrics
        this.updateAnalyticsWidget('total-tasks-created', dashboard.productivity.total_tasks_created);
        this.updateAnalyticsWidget('total-decisions-made', dashboard.productivity.total_decisions_made);
    }

    /**
     * Update analytics widget
     */
    updateAnalyticsWidget(widgetId, value, suffix = '') {
        const widget = document.querySelector(`[data-analytics="${widgetId}"]`);
        if (widget) {
            const valueElement = widget.querySelector('.analytics-value');
            if (valueElement) {
                valueElement.textContent = `${value}${suffix}`;
            }
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Refresh button
        const refreshButton = document.getElementById('refresh-dashboard');
        if (refreshButton) {
            refreshButton.addEventListener('click', () => {
                this.loadDashboardData();
                this.showNotification('Dashboard refreshed', 'success');
            });
        }

        // Auto-refresh toggle
        const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }
        
        // CROWN ¹⁰ WebSocket Event Listeners
        this.setupWebSocketListeners();
    }
    
    /**
     * CROWN ¹⁰ Cross-Surface Event Synchronization
     * Wire WebSocket listeners for real-time dashboard updates
     */
    setupWebSocketListeners() {
        if (!window.socket) {
            console.warn('[Dashboard] Socket.IO not available, skipping WebSocket listeners');
            return;
        }
        
        const dashboardSocket = window.socket.io(`/dashboard`, {
            transports: ['websocket', 'polling']
        });
        
        // Store socket reference
        this.socket = dashboardSocket;
        
        // Connection events
        dashboardSocket.on('connect', () => {
            console.log('✅ Dashboard WebSocket connected');
            
            // Join workspace room for isolated broadcasts
            dashboardSocket.emit('join_workspace', {
                workspace_id: this.workspaceId
            });
            
            // Request event replay to catch up
            const lastSequence = this.getLastSequenceNum();
            dashboardSocket.emit('request_event_replay', {
                workspace_id: this.workspaceId,
                last_sequence_num: lastSequence,
                namespace: '/dashboard',
                is_initial_sync: lastSequence === 0
            });
        });
        
        dashboardSocket.on('disconnect', () => {
            console.warn('⚠️ Dashboard WebSocket disconnected');
        });
        
        dashboardSocket.on('error', (error) => {
            console.error('❌ Dashboard WebSocket error:', error);
        });
        
        // Event replay handler
        dashboardSocket.on('event_replay', async (data) => {
            console.log(`📦 Event replay received: ${data.count} events (seq ${data.last_sequence_num})`);
            
            if (data.events && data.events.length > 0) {
                for (const event of data.events) {
                    await this.handleWebSocketEvent(event);
                }
                
                // Update last sequence number
                this.saveLastSequenceNum(data.last_sequence_num);
            }
        });
        
        // CROWN ¹⁰ Event Handlers: SESSION/MEETING LIFECYCLE
        dashboardSocket.on('session_update:created', async (event) => {
            console.log('🆕 New meeting created:', event);
            await this.handleSessionCreated(event);
        });
        
        dashboardSocket.on('meeting_update', async (event) => {
            console.log('📝 Meeting updated:', event);
            await this.handleMeetingUpdate(event);
        });
        
        dashboardSocket.on('session_refined_ready', async (event) => {
            console.log('✨ Meeting refined:', event);
            await this.handleSessionRefined(event);
        });
        
        // CROWN ¹⁰ Event Handlers: ANALYTICS
        dashboardSocket.on('analytics_refresh', async (event) => {
            console.log('📊 Analytics refresh:', event);
            await this.handleAnalyticsRefresh(event);
        });
        
        dashboardSocket.on('analytics_update', async (event) => {
            console.log('📈 Analytics update:', event);
            await this.handleAnalyticsUpdate(event);
        });
        
        // CROWN ¹⁰ Event Handlers: TASKS
        dashboardSocket.on('task_update', async (event) => {
            console.log('✓ Task updated:', event);
            await this.handleTaskUpdate(event);
        });
        
        dashboardSocket.on('tasks_generation', async (event) => {
            console.log('📋 Tasks generated:', event);
            await this.handleTasksGenerated(event);
        });
        
        // CROWN ¹⁰ Event Handlers: SYSTEM
        dashboardSocket.on('dashboard_idle_sync', async (event) => {
            console.log('🔄 Idle sync triggered:', event);
            await this.handleIdleSync(event);
        });
        
        dashboardSocket.on('cache_invalidate', async (event) => {
            console.log('🗑️ Cache invalidated:', event);
            await this.handleCacheInvalidate(event);
        });
        
        console.log('✅ Dashboard WebSocket listeners registered');
    }
    
    /**
     * Handle new meeting created event
     */
    async handleSessionCreated(event) {
        const { data, checksum } = event;
        
        // Invalidate meetings cache
        if (this.cache) {
            await this.cache.invalidate('meetings');
        }
        
        // Reload meetings list with calm pulse animation
        await this.loadRecentMeetings();
        
        // Update stats
        await this.loadStats();
        
        // Show notification
        this.showNotification('New meeting recorded', 'success');
        
        // Track telemetry
        if (this.telemetry) {
            this.telemetry.recordEvent('session_created', {
                event_id: event.event_id,
                latency_ms: Date.now() - new Date(event.timestamp).getTime()
            });
        }
    }
    
    /**
     * Handle meeting update event
     */
    async handleMeetingUpdate(event) {
        const { data } = event;
        
        // Invalidate cache
        if (this.cache) {
            await this.cache.invalidate('meetings');
        }
        
        // Reload meetings
        await this.loadRecentMeetings();
        
        // Track telemetry
        if (this.telemetry) {
            this.telemetry.recordEvent('meeting_update', {
                event_id: event.event_id,
                latency_ms: Date.now() - new Date(event.timestamp).getTime()
            });
        }
    }
    
    /**
     * Handle session refined event (transcript finalized + insights generated)
     */
    async handleSessionRefined(event) {
        const { data } = event;
        
        // Invalidate cache
        if (this.cache) {
            await this.cache.invalidate('meetings');
            await this.cache.invalidate('analytics');
        }
        
        // Reload with calm flip animation
        await this.loadRecentMeetings();
        await this.loadAnalyticsOverview();
        
        // Show notification
        this.showNotification('Meeting insights ready', 'success');
    }
    
    /**
     * Handle analytics refresh event
     */
    async handleAnalyticsRefresh(event) {
        const { data } = event;
        
        // Invalidate analytics cache
        if (this.cache) {
            await this.cache.invalidate('analytics');
        }
        
        // Reload analytics with pulse animation
        await this.loadAnalyticsOverview();
        
        // Track telemetry
        if (this.telemetry) {
            this.telemetry.recordEvent('analytics_refresh', {
                event_id: event.event_id,
                latency_ms: Date.now() - new Date(event.timestamp).getTime()
            });
        }
    }
    
    /**
     * Handle analytics update event (KPI changes)
     */
    async handleAnalyticsUpdate(event) {
        const { data } = event;
        
        // Apply delta update directly without full reload
        if (data.delta) {
            this.applyAnalyticsDelta(data.delta);
        } else {
            // Full reload if no delta
            await this.loadAnalyticsOverview();
        }
    }
    
    /**
     * Apply analytics delta for efficient updates
     */
    applyAnalyticsDelta(delta) {
        // Update individual KPIs without reloading entire dashboard
        if (delta.total_meetings !== undefined) {
            this.updateStatCard('total-meetings', delta.total_meetings);
        }
        if (delta.total_tasks !== undefined) {
            this.updateStatCard('total-tasks', delta.total_tasks);
        }
        if (delta.completion_rate !== undefined) {
            this.updateStatCard('task-completion-rate', `${delta.completion_rate}%`);
        }
        
        console.log('📊 Analytics delta applied:', delta);
    }
    
    /**
     * Handle task update event
     */
    async handleTaskUpdate(event) {
        const { data } = event;
        
        // Invalidate tasks cache
        if (this.cache) {
            await this.cache.invalidate('tasks');
        }
        
        // Reload tasks and stats
        await this.loadMyTasks();
        await this.loadStats();
        
        // Track telemetry
        if (this.telemetry) {
            this.telemetry.recordEvent('task_update', {
                event_id: event.event_id,
                latency_ms: Date.now() - new Date(event.timestamp).getTime()
            });
        }
    }
    
    /**
     * Handle tasks generated event
     */
    async handleTasksGenerated(event) {
        const { data } = event;
        
        // Invalidate caches
        if (this.cache) {
            await this.cache.invalidate('tasks');
            await this.cache.invalidate('analytics');
        }
        
        // Reload tasks and stats
        await this.loadMyTasks();
        await this.loadStats();
        
        // Show notification
        const taskCount = data.tasks?.length || 0;
        this.showNotification(`${taskCount} tasks generated`, 'success');
    }
    
    /**
     * Handle idle sync event (30s reconciliation)
     */
    async handleIdleSync(event) {
        const { data } = event;
        
        // Check checksum to determine if sync needed
        const currentChecksum = await this.getCurrentChecksum();
        
        if (data.checksum && data.checksum !== currentChecksum) {
            console.log('🔄 Checksum mismatch, syncing...');
            
            // Invalidate all caches
            if (this.cache) {
                await this.cache.invalidate('meetings');
                await this.cache.invalidate('tasks');
                await this.cache.invalidate('analytics');
            }
            
            // Full reload
            await this.loadDashboardData();
        }
    }
    
    /**
     * Handle cache invalidate event
     */
    async handleCacheInvalidate(event) {
        const { data } = event;
        const cacheKey = data.cache_key || 'all';
        
        if (this.cache) {
            if (cacheKey === 'all') {
                await this.cache.clear();
            } else {
                await this.cache.invalidate(cacheKey);
            }
        }
        
        // Reload affected data
        if (cacheKey === 'meetings' || cacheKey === 'all') {
            await this.loadRecentMeetings();
        }
        if (cacheKey === 'tasks' || cacheKey === 'all') {
            await this.loadMyTasks();
        }
        if (cacheKey === 'analytics' || cacheKey === 'all') {
            await this.loadAnalyticsOverview();
        }
    }
    
    /**
     * Generic WebSocket event handler
     */
    async handleWebSocketEvent(event) {
        // Update last sequence number
        if (event.sequence_num) {
            this.saveLastSequenceNum(event.sequence_num);
        }
        
        // Route to specific handler based on event type
        const handlers = {
            'session_update:created': () => this.handleSessionCreated(event),
            'meeting_update': () => this.handleMeetingUpdate(event),
            'session_refined_ready': () => this.handleSessionRefined(event),
            'analytics_refresh': () => this.handleAnalyticsRefresh(event),
            'analytics_update': () => this.handleAnalyticsUpdate(event),
            'task_update': () => this.handleTaskUpdate(event),
            'tasks_generation': () => this.handleTasksGenerated(event),
            'dashboard_idle_sync': () => this.handleIdleSync(event),
            'cache_invalidate': () => this.handleCacheInvalidate(event)
        };
        
        const handler = handlers[event.event_type];
        if (handler) {
            await handler();
        }
    }
    
    /**
     * Get last processed sequence number from localStorage
     */
    getLastSequenceNum() {
        try {
            const stored = localStorage.getItem(`mina_last_seq_${this.workspaceId}`);
            return stored ? parseInt(stored, 10) : 0;
        } catch (error) {
            return 0;
        }
    }
    
    /**
     * Save last processed sequence number to localStorage
     */
    saveLastSequenceNum(sequenceNum) {
        try {
            localStorage.setItem(`mina_last_seq_${this.workspaceId}`, sequenceNum.toString());
        } catch (error) {
            console.error('Failed to save sequence number:', error);
        }
    }
    
    /**
     * Get current checksum for sync validation
     */
    async getCurrentChecksum() {
        if (this.cache) {
            const metadata = await this.cache.getMetadata('dashboard_checksum');
            return metadata?.checksum || null;
        }
        return null;
    }
    
    /**
     * Generate checksum from data
     */
    generateChecksum(data) {
        // Simple checksum generation (can be replaced with MD5)
        const str = JSON.stringify(data);
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return hash.toString(16);
    }

    /**
     * Start auto-refresh
     */
    startAutoRefresh() {
        this.stopAutoRefresh(); // Clear existing timers
        
        const timer = setInterval(() => {
            this.loadDashboardData();
        }, this.refreshInterval);
        
        this.refreshTimers.set('dashboard', timer);
        console.log('[Dashboard] Auto-refresh started');
    }

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        this.refreshTimers.forEach((timer, key) => {
            clearInterval(timer);
        });
        this.refreshTimers.clear();
        console.log('[Dashboard] Auto-refresh stopped');
    }

    /**
     * View meeting details
     */
    async viewMeeting(meetingId) {
        try {
            const response = await fetch(`${this.apiBase}/meetings/${meetingId}`);
            const data = await response.json();

            if (data.success) {
                this.showMeetingModal(data.meeting);
            } else {
                this.showError('Failed to load meeting details');
            }
        } catch (error) {
            console.error('[Dashboard] Failed to load meeting details:', error);
            this.showError('Failed to load meeting details');
        }
    }

    /**
     * Update task status with optimistic UI updates and server reconciliation (CROWN⁴ Task #11)
     */
    async updateTaskStatus(taskId, newStatus) {
        // Find the task element
        const taskElement = document.querySelector(`.task-item[data-task-id="${taskId}"]`);
        if (!taskElement) {
            console.warn('[Dashboard] Task element not found:', taskId);
            return;
        }
        
        // Store original HTML for rollback
        const originalHTML = taskElement.innerHTML;
        const originalStatus = taskElement.querySelector('.task-status')?.textContent?.trim()?.toLowerCase() || '';
        
        try {
            // OPTIMISTIC UPDATE: Immediately update UI before server responds
            const statusSpan = taskElement.querySelector('.task-status');
            const actionButton = taskElement.querySelector('.btn-icon');
            
            if (statusSpan) {
                statusSpan.className = `task-status status-${newStatus}`;
                statusSpan.textContent = this.capitalizeFirst(newStatus);
            }
            
            // Update button icon
            if (actionButton) {
                const nextStatus = this.getNextStatus(newStatus);
                actionButton.setAttribute('onclick', `dashboard.updateTaskStatus(${taskId}, '${nextStatus}')`);
                actionButton.setAttribute('title', 'Update Status');
                
                const icon = actionButton.querySelector('i[data-feather]');
                if (icon) {
                    icon.setAttribute('data-feather', this.getStatusIcon(newStatus));
                    if (typeof feather !== 'undefined') {
                        feather.replace();
                    }
                }
            }
            
            // Add visual feedback for optimistic update
            taskElement.style.opacity = '0.7';
            taskElement.style.transition = 'opacity 0.2s ease';
            
            console.log(`[Dashboard] Optimistic update: Task ${taskId} → ${newStatus}`);
            
            // SERVER RECONCILIATION: Send request to server
            const response = await fetch(`${this.apiBase}/tasks/${taskId}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ status: newStatus })
            });

            const data = await response.json();
            
            // Restore full opacity
            taskElement.style.opacity = '1';

            if (data.success) {
                // Server confirmed - keep optimistic update
                this.showNotification('Task status updated', 'success');
                
                // CROWN⁴ Task #12: Broadcast to other tabs
                if (window.broadcastSync) {
                    window.broadcastSync.broadcastTaskUpdate(taskId, { status: newStatus });
                }
                
                // Reconcile with server data if different
                if (data.task && data.task.status !== newStatus) {
                    console.log(`[Dashboard] Server reconciliation: ${newStatus} → ${data.task.status}`);
                    
                    // CRITICAL: Immediately revert optimistic changes before async reload
                    // Prevents race condition where button handler points to wrong status
                    taskElement.innerHTML = originalHTML;
                    taskElement.style.opacity = '1';
                    
                    // Re-initialize feather icons
                    if (typeof feather !== 'undefined') {
                        feather.replace();
                    }
                    
                    // Re-render with server data and refresh stats
                    this.loadMyTasks();
                    this.loadStats();
                } else {
                    // Refresh stats only (tasks already updated optimistically)
                    this.loadStats();
                }
            } else {
                // ROLLBACK: Server rejected - restore original state
                console.warn('[Dashboard] Server rejected update, rolling back:', data.message);
                taskElement.innerHTML = originalHTML;
                taskElement.style.opacity = '1';  // Reset opacity
                
                // Re-initialize feather icons after rollback
                if (typeof feather !== 'undefined') {
                    feather.replace();
                }
                
                this.showError(data.message || 'Failed to update task');
            }
        } catch (error) {
            // ROLLBACK: Network error - restore original state
            console.error('[Dashboard] Failed to update task, rolling back:', error);
            taskElement.innerHTML = originalHTML;
            taskElement.style.opacity = '1';  // Reset opacity
            
            // Re-initialize feather icons after rollback
            if (typeof feather !== 'undefined') {
                feather.replace();
            }
            
            this.showError('Failed to update task - network error');
        }
    }

    /**
     * Utility functions
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
        });
    }

    capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    getNextStatus(currentStatus) {
        const statusFlow = {
            'todo': 'in_progress',
            'in_progress': 'completed',
            'completed': 'todo'
        };
        return statusFlow[currentStatus] || 'todo';
    }

    getStatusIcon(status) {
        const icons = {
            'todo': 'play',
            'in_progress': 'check',
            'completed': 'rotate-ccw',
            'cancelled': 'x'
        };
        return icons[status] || 'circle';
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button class="notification-close" onclick="this.parentElement.remove()">×</button>
        `;

        // Add to page
        const container = document.getElementById('notifications') || document.body;
        container.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    /**
     * Show error message
     */
    showError(message) {
        this.showNotification(message, 'error');
    }
    
    /**
     * Generate simple checksum from data (for cache validation)
     */
    generateChecksum(data) {
        const str = JSON.stringify(data);
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        return Math.abs(hash).toString(16);
    }

    /**
     * Show meeting modal
     */
    showMeetingModal(meeting) {
        // Create modal HTML
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${this.escapeHtml(meeting.title)}</h3>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                </div>
                <div class="modal-body">
                    <div class="meeting-details">
                        <p><strong>Status:</strong> ${this.capitalizeFirst(meeting.status)}</p>
                        <p><strong>Created:</strong> ${this.formatDate(meeting.created_at)}</p>
                        ${meeting.description ? `<p><strong>Description:</strong> ${this.escapeHtml(meeting.description)}</p>` : ''}
                        ${meeting.participants ? `<p><strong>Participants:</strong> ${meeting.participants.length}</p>` : ''}
                        ${meeting.tasks ? `<p><strong>Tasks Created:</strong> ${meeting.tasks.length}</p>` : ''}
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Close</button>
                    <a href="/dashboard/meetings/${meeting.id}" class="btn btn-primary">View Full Details</a>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new MinaDashboard();
});

// CSS for notifications and modals
const dashboardStyles = `
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 16px;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        z-index: 1000;
        display: flex;
        align-items: center;
        gap: 8px;
        max-width: 300px;
    }

    .notification-success {
        background: #10b981;
        color: white;
    }

    .notification-error {
        background: #ef4444;
        color: white;
    }

    .notification-info {
        background: #3b82f6;
        color: white;
    }

    .notification-close {
        background: none;
        border: none;
        color: inherit;
        font-size: 18px;
        cursor: pointer;
        padding: 0;
        width: 20px;
        height: 20px;
    }

    .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }

    .modal-content {
        background: white;
        border-radius: 8px;
        width: 90%;
        max-width: 600px;
        max-height: 90vh;
        overflow: auto;
    }

    .modal-header {
        padding: 20px;
        border-bottom: 1px solid #e5e7eb;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .modal-body {
        padding: 20px;
    }

    .modal-footer {
        padding: 20px;
        border-top: 1px solid #e5e7eb;
        display: flex;
        gap: 10px;
        justify-content: flex-end;
    }

    .modal-close {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        padding: 0;
        width: 30px;
        height: 30px;
    }

    .empty-state {
        text-align: center;
        padding: 40px 20px;
    }

    .btn-icon {
        background: none;
        border: none;
        padding: 4px;
        cursor: pointer;
        color: #6b7280;
        border-radius: 4px;
    }

    .btn-icon:hover {
        background: #f3f4f6;
        color: #374151;
    }
`;

// Inject styles
const styleSheet = document.createElement('style');
styleSheet.textContent = dashboardStyles;
document.head.appendChild(styleSheet);