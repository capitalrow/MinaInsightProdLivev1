/**
 * CROWN⁴.5 Telemetry Dashboard
 * Real-time performance metrics and Calm Score composite.
 * 
 * Features:
 * - Calm Score (composite metric)
 * - Cache hit rate
 * - Animation queue depth
 * - Conflict resolution rate
 * - Offline queue size
 * - Sync latency
 * - Event throughput
 */

class CROWNTelemetryDashboard {
    constructor(options = {}) {
        this.enabled = options.enabled !== false;
        this.updateInterval = options.updateInterval || 1000; // 1 second
        this.updateTimer = null;
        this.dashboardElement = null;
        this.isVisible = false;
        
        // Metrics
        this.metrics = {
            calmScore: 100,
            cacheHitRate: 0,
            animationQueueDepth: 0,
            conflictResolutionRate: 0,
            offlineQueueSize: 0,
            avgSyncLatency: 0,
            eventThroughput: 0,
            totalEvents: 0,
            totalConflicts: 0,
            totalAnimations: 0,
            lastUpdate: Date.now()
        };
        
        // Event counters
        this.eventCounters = new Map();
        this.lastEventCount = 0;
        
        if (this.enabled) {
            this._init();
        }
        
        console.log('[CROWNTelemetryDashboard] Initialized');
    }

    /**
     * Initialize dashboard
     */
    _init() {
        this._createDashboard();
        this._setupListeners();
        this._startUpdates();
    }

    /**
     * Create dashboard UI
     */
    _createDashboard() {
        // Check if already exists
        if (document.getElementById('crown-telemetry-dashboard')) {
            this.dashboardElement = document.getElementById('crown-telemetry-dashboard');
            return;
        }

        const dashboard = document.createElement('div');
        dashboard.id = 'crown-telemetry-dashboard';
        dashboard.className = 'crown-dashboard';
        dashboard.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9997;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(12px);
            border-radius: 12px;
            padding: 16px;
            min-width: 280px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            color: white;
            font-family: system-ui, -apple-system, sans-serif;
            opacity: 0;
            transform: translateY(20px);
            transition: all 300ms cubic-bezier(0.4, 0.0, 0.2, 1);
            pointer-events: none;
        `;

        dashboard.innerHTML = `
            <div class="dashboard-header" style="
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
            ">
                <div>
                    <h3 style="margin: 0; font-size: 14px; font-weight: 600; color: #f1f5f9;">
                        CROWN⁴.5 Telemetry
                    </h3>
                    <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
                        <span id="telemetry-status">Active</span> • 
                        <span id="telemetry-uptime">0s</span>
                    </div>
                </div>
                <div class="calm-score-circle" style="
                    width: 48px;
                    height: 48px;
                    border-radius: 50%;
                    background: conic-gradient(
                        from 0deg,
                        #10b981 0%,
                        #10b981 var(--calm-percentage, 100%),
                        rgba(255, 255, 255, 0.1) var(--calm-percentage, 100%),
                        rgba(255, 255, 255, 0.1) 100%
                    );
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    position: relative;
                ">
                    <div style="
                        position: absolute;
                        inset: 4px;
                        background: #0f172a;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        flex-direction: column;
                    ">
                        <div style="font-size: 16px; font-weight: 700; line-height: 1;" id="calm-score-value">100</div>
                        <div style="font-size: 8px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px;">Calm</div>
                    </div>
                </div>
            </div>

            <div class="dashboard-metrics">
                ${this._createMetricRow('Cache Hit', 'cache-hit', '0%', '#3b82f6')}
                ${this._createMetricRow('Animations', 'animations', '0', '#a855f7')}
                ${this._createMetricRow('Conflicts', 'conflicts', '0%', '#f59e0b')}
                ${this._createMetricRow('Offline Queue', 'offline-queue', '0', '#ef4444')}
                ${this._createMetricRow('Sync Latency', 'sync-latency', '0ms', '#10b981')}
                ${this._createMetricRow('Events/sec', 'event-throughput', '0', '#06b6d4')}
            </div>

            <div class="dashboard-footer" style="
                margin-top: 12px;
                padding-top: 12px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                gap: 8px;
            ">
                <button class="btn-toggle-details" style="
                    flex: 1;
                    background: rgba(255, 255, 255, 0.1);
                    border: none;
                    color: white;
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 150ms ease-out;
                ">Details</button>
                <button class="btn-reset-metrics" style="
                    background: rgba(239, 68, 68, 0.2);
                    border: none;
                    color: #fca5a5;
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 150ms ease-out;
                ">Reset</button>
            </div>
        `;

        document.body.appendChild(dashboard);
        this.dashboardElement = dashboard;

        // Setup button handlers
        dashboard.querySelector('.btn-toggle-details').addEventListener('click', () => {
            this.toggleDetails();
        });

        dashboard.querySelector('.btn-reset-metrics').addEventListener('click', () => {
            this.resetMetrics();
        });
    }

    /**
     * Create metric row
     * @param {string} label
     * @param {string} id
     * @param {string} initialValue
     * @param {string} color
     * @returns {string} HTML
     */
    _createMetricRow(label, id, initialValue, color) {
        return `
            <div class="metric-row" style="
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 8px 0;
            ">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="
                        width: 3px;
                        height: 16px;
                        background: ${color};
                        border-radius: 2px;
                    "></div>
                    <span style="font-size: 12px; color: #cbd5e1;">${label}</span>
                </div>
                <span id="metric-${id}" style="
                    font-size: 13px;
                    font-weight: 600;
                    font-variant-numeric: tabular-nums;
                    color: ${color};
                ">${initialValue}</span>
            </div>
        `;
    }

    /**
     * Setup event listeners
     */
    _setupListeners() {
        // Record all CROWN events
        window.addEventListener('crown_event', (e) => {
            this.recordEvent(e.detail.event_type);
        });

        // Record animation events
        window.addEventListener('crown_animation', (e) => {
            this.metrics.totalAnimations++;
        });

        // Record conflict events
        window.addEventListener('task_conflict_detected', () => {
            this.metrics.totalConflicts++;
        });

        // Keyboard shortcut to toggle dashboard (Ctrl+Shift+D)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'D') {
                e.preventDefault();
                this.toggle();
            }
        });
    }

    /**
     * Start periodic updates
     */
    _startUpdates() {
        this.updateTimer = setInterval(() => {
            this.updateMetrics();
        }, this.updateInterval);
    }

    /**
     * Update all metrics
     */
    updateMetrics() {
        if (!this.dashboardElement || !this.isVisible) return;

        // Calculate Calm Score
        this.metrics.calmScore = this._calculateCalmScore();

        // Get metrics from other components
        this._collectComponentMetrics();

        // Calculate event throughput
        const currentEventCount = this.metrics.totalEvents;
        const timeDelta = (Date.now() - this.metrics.lastUpdate) / 1000;
        this.metrics.eventThroughput = Math.round((currentEventCount - this.lastEventCount) / timeDelta);
        this.lastEventCount = currentEventCount;
        this.metrics.lastUpdate = Date.now();

        // Update UI
        this._updateUI();
    }

    /**
     * Calculate Calm Score (0-100)
     * Composite metric: cache hit rate + low animation queue + low conflicts + low offline queue
     */
    _calculateCalmScore() {
        let score = 100;

        // Factor 1: Cache performance (30%)
        const cacheScore = this.metrics.cacheHitRate * 30;

        // Factor 2: Animation queue (25%)
        const maxQueue = 10;
        const queuePressure = Math.min(this.metrics.animationQueueDepth / maxQueue, 1);
        const queueScore = (1 - queuePressure) * 25;

        // Factor 3: Conflict resolution (25%)
        const conflictScore = this.metrics.conflictResolutionRate * 25;

        // Factor 4: Offline queue (20%)
        const maxOffline = 20;
        const offlinePressure = Math.min(this.metrics.offlineQueueSize / maxOffline, 1);
        const offlineScore = (1 - offlinePressure) * 20;

        score = cacheScore + queueScore + conflictScore + offlineScore;
        return Math.max(0, Math.min(100, Math.round(score)));
    }

    /**
     * Collect metrics from other components
     */
    _collectComponentMetrics() {
        // QuietStateManager metrics
        if (window.quietStateManager) {
            const stats = window.quietStateManager.getStats();
            this.metrics.animationQueueDepth = stats.queued || 0;
        }

        // Conflict resolution metrics
        if (window.conflictResolutionUI) {
            const stats = window.conflictResolutionUI.getMetrics();
            this.metrics.conflictResolutionRate = stats.autoResolutionRate / 100 || 0;
        }

        // Offline queue metrics
        if (window.offlineQueue) {
            const stats = window.offlineQueue.getStats?.() || {};
            this.metrics.offlineQueueSize = stats.queueSize || 0;
        }

        // Cache metrics
        if (window.taskCache) {
            const stats = window.taskCache.getStats?.() || {};
            this.metrics.cacheHitRate = stats.hitRate || 0;
        }

        // Idle sync metrics
        if (window.idleSyncTimer) {
            const stats = window.idleSyncTimer.getMetrics();
            this.metrics.avgSyncLatency = stats.avgSyncInterval ? stats.avgSyncInterval * 1000 : 0;
        }
    }

    /**
     * Update dashboard UI
     */
    _updateUI() {
        if (!this.dashboardElement) return;

        // Update Calm Score
        const calmScoreEl = this.dashboardElement.querySelector('#calm-score-value');
        const calmCircle = this.dashboardElement.querySelector('.calm-score-circle');
        
        if (calmScoreEl && calmCircle) {
            calmScoreEl.textContent = this.metrics.calmScore;
            calmCircle.style.setProperty('--calm-percentage', `${this.metrics.calmScore}%`);
            
            // Color gradient based on score
            const color = this.metrics.calmScore >= 80 ? '#10b981' :
                         this.metrics.calmScore >= 60 ? '#f59e0b' : '#ef4444';
            calmCircle.style.background = `conic-gradient(
                from 0deg,
                ${color} 0%,
                ${color} ${this.metrics.calmScore}%,
                rgba(255, 255, 255, 0.1) ${this.metrics.calmScore}%,
                rgba(255, 255, 255, 0.1) 100%
            )`;
        }

        // Update individual metrics
        this._updateMetricValue('cache-hit', `${Math.round(this.metrics.cacheHitRate * 100)}%`);
        this._updateMetricValue('animations', this.metrics.animationQueueDepth);
        this._updateMetricValue('conflicts', `${Math.round(this.metrics.conflictResolutionRate * 100)}%`);
        this._updateMetricValue('offline-queue', this.metrics.offlineQueueSize);
        this._updateMetricValue('sync-latency', `${Math.round(this.metrics.avgSyncLatency)}ms`);
        this._updateMetricValue('event-throughput', `${this.metrics.eventThroughput}`);
    }

    /**
     * Update metric value
     * @param {string} id
     * @param {string|number} value
     */
    _updateMetricValue(id, value) {
        const element = this.dashboardElement.querySelector(`#metric-${id}`);
        if (element) {
            element.textContent = value;
        }
    }

    /**
     * Record event
     * @param {string} eventType
     */
    recordEvent(eventType) {
        this.metrics.totalEvents++;
        
        // Track event type distribution
        const count = this.eventCounters.get(eventType) || 0;
        this.eventCounters.set(eventType, count + 1);
    }

    /**
     * Show dashboard
     */
    show() {
        if (!this.dashboardElement) return;
        
        this.isVisible = true;
        this.dashboardElement.style.opacity = '1';
        this.dashboardElement.style.transform = 'translateY(0)';
        this.dashboardElement.style.pointerEvents = 'auto';
        
        console.log('[CROWNTelemetryDashboard] Dashboard shown');
    }

    /**
     * Hide dashboard
     */
    hide() {
        if (!this.dashboardElement) return;
        
        this.isVisible = false;
        this.dashboardElement.style.opacity = '0';
        this.dashboardElement.style.transform = 'translateY(20px)';
        this.dashboardElement.style.pointerEvents = 'none';
        
        console.log('[CROWNTelemetryDashboard] Dashboard hidden');
    }

    /**
     * Toggle dashboard visibility
     */
    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    /**
     * Toggle details view
     */
    toggleDetails() {
        console.log('[CROWNTelemetryDashboard] Details view:', {
            metrics: this.metrics,
            eventDistribution: Object.fromEntries(this.eventCounters)
        });
    }

    /**
     * Reset metrics
     */
    resetMetrics() {
        this.metrics.totalEvents = 0;
        this.metrics.totalConflicts = 0;
        this.metrics.totalAnimations = 0;
        this.lastEventCount = 0;
        this.eventCounters.clear();
        
        console.log('[CROWNTelemetryDashboard] Metrics reset');
    }

    /**
     * Get all metrics
     * @returns {Object}
     */
    getAllMetrics() {
        return {
            ...this.metrics,
            eventDistribution: Object.fromEntries(this.eventCounters)
        };
    }
}

// Initialize global instance
window.CROWNTelemetryDashboard = CROWNTelemetryDashboard;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.crownTelemetry) {
            window.crownTelemetry = new CROWNTelemetryDashboard({
                enabled: true,
                updateInterval: 1000
            });
            
            // Auto-show dashboard if in development mode
            if (window.location.hostname === 'localhost' || window.location.hostname.includes('repl')) {
                setTimeout(() => {
                    window.crownTelemetry.show();
                }, 2000);
            }
            
            console.log('[CROWNTelemetryDashboard] Global instance created');
            console.log('💡 Press Ctrl+Shift+D to toggle telemetry dashboard');
        }
    });
}
