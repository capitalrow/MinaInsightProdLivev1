/**
 * CROWN⁵+ Analytics Controller - Living Intelligence System
 * 
 * Orchestrates the complete analytics experience:
 * - Cache-first bootstrap (<200ms warm paint)
 * - Real-time delta streaming
 * - Emotional UI layer (pulses, count-ups, shimmers)
 * - Intelligent prefetching
 * - Self-healing background sync
 * 
 * Replaces traditional request-response with event-driven architecture.
 */

import { analyticsCache } from './analytics-cache.js';
import { AnalyticsLifecycle } from './analytics-lifecycle.js';

export class Crown5Analytics {
    constructor(workspaceId, socketNamespace) {
        this.workspaceId = workspaceId;
        this.socket = socketNamespace;
        this.lifecycle = null;
        this.charts = {};
        this.emotionalState = 'calm'; // calm | pulsing | loading
        this.currentTab = 'overview';
        this.days = 30;

        // UI Elements
        this.kpiElements = {};
        this.chartElements = {};

        this._init();
    }

    /**
     * Initialize CROWN⁵+ analytics
     * @private
     */
    async _init() {
        console.log('🌟 CROWN⁵+ Analytics initializing...');

        // Setup lifecycle manager
        this.lifecycle = new AnalyticsLifecycle(this.socket, this.workspaceId);
        
        // Set event handlers
        this.lifecycle.onSnapshotUpdate = this._handleSnapshotUpdate.bind(this);
        this.lifecycle.onDeltaUpdate = this._handleDeltaUpdate.bind(this);
        this.lifecycle.onError = this._handleError.bind(this);

        // Cache UI elements
        this._cacheUIElements();

        // Setup UI handlers
        this._setupDateRangeFilter();
        this._setupTabSwitching();
        this._setupExportButton();

        // Bootstrap analytics (cache-first)
        await this.lifecycle.bootstrap();

        console.log('✨ CROWN⁵+ Analytics ready');
    }

    /**
     * Cache references to UI elements for fast updates
     * @private
     */
    _cacheUIElements() {
        // KPI elements
        this.kpiElements = {
            totalMeetings: document.querySelector('[data-widget="kpi-meetings"] .text-3xl'),
            totalTasks: document.querySelector('[data-widget="kpi-tasks"] .text-3xl'),
            taskCompletionRate: document.querySelector('[data-widget="kpi-tasks"] .px-2'),
            hoursSaved: document.querySelector('[data-widget="kpi-hours"] .text-3xl'),
            avgDuration: document.querySelector('[data-widget="kpi-duration"] .text-3xl')
        };

        // Chart canvases
        this.chartElements = {
            meetingActivity: document.getElementById('meetingActivityChart'),
            taskStatus: document.getElementById('taskStatusChart'),
            speakerDistribution: document.getElementById('speakerChart')
        };
    }

    /**
     * Handle snapshot update (cache hit or server response)
     * @private
     */
    async _handleSnapshotUpdate(snapshot, source) {
        console.log(`📊 Snapshot update (source: ${source})`);

        try {
            const kpis = snapshot.kpis || {};
            const charts = snapshot.charts || {};

            // Determine animation style based on source
            const animate = source !== 'cache'; // Animate server updates, instant for cache

            if (animate) {
                this.emotionalState = 'loading';
            }

            // Update KPIs with count-up animation
            this._updateKPI('totalMeetings', kpis.total_meetings || 0, animate);
            this._updateKPI('totalTasks', kpis.total_tasks || 0, animate);
            this._updateKPI('hoursSaved', kpis.hours_saved || 0, animate);
            this._updateKPI('avgDuration', `${kpis.avg_duration || 0}m`, animate, true);

            // Update completion rate badge
            if (this.kpiElements.taskCompletionRate) {
                this.kpiElements.taskCompletionRate.textContent = `${kpis.task_completion_rate || 0}%`;
            }

            // Update charts
            await this._updateCharts(charts);

            // Reset emotional state
            if (animate) {
                setTimeout(() => {
                    this.emotionalState = 'calm';
                }, 600);
            }

        } catch (e) {
            console.error('Snapshot update failed:', e);
        }
    }

    /**
     * Handle delta update (real-time KPI changes)
     * @private
     */
    async _handleDeltaUpdate(delta, updatedSnapshot) {
        console.log('⚡ Delta update received');

        try {
            this.emotionalState = 'pulsing';

            const changes = delta.changes || {};

            // Apply KPI changes with micro-pulse
            if (changes.kpis) {
                for (const [key, value] of Object.entries(changes.kpis)) {
                    const elementKey = this._kpiKeyToElementKey(key);
                    if (elementKey) {
                        this._updateKPI(elementKey, value, true, key === 'avg_duration');
                        this._pulseElement(this.kpiElements[elementKey]?.parentElement);
                    }
                }
            }

            // Apply chart changes
            if (changes.charts) {
                await this._updateCharts(changes.charts);
            }

            // Reset emotional state
            setTimeout(() => {
                this.emotionalState = 'calm';
            }, 800);

        } catch (e) {
            console.error('Delta update failed:', e);
        }
    }

    /**
     * Map KPI field names to UI element keys
     * @private
     */
    _kpiKeyToElementKey(key) {
        const map = {
            'total_meetings': 'totalMeetings',
            'total_tasks': 'totalTasks',
            'hours_saved': 'hoursSaved',
            'avg_duration': 'avgDuration'
        };
        return map[key];
    }

    /**
     * Update KPI with optional count-up animation
     * @private
     */
    _updateKPI(elementKey, value, animate = false, isText = false) {
        const element = this.kpiElements[elementKey];
        if (!element) return;

        if (!animate || isText) {
            // Instant update
            element.textContent = value;
        } else {
            // Count-up animation
            const currentValue = parseInt(element.textContent) || 0;
            const targetValue = parseInt(value) || 0;
            
            if (currentValue === targetValue) return;

            const duration = 600; // ms
            const steps = 30;
            const stepDuration = duration / steps;
            const increment = (targetValue - currentValue) / steps;

            let step = 0;
            const interval = setInterval(() => {
                step++;
                const newValue = Math.round(currentValue + (increment * step));
                element.textContent = newValue;

                if (step >= steps) {
                    element.textContent = targetValue;
                    clearInterval(interval);
                }
            }, stepDuration);
        }
    }

    /**
     * Pulse animation on KPI card
     * @private
     */
    _pulseElement(element) {
        if (!element) return;

        element.style.transition = 'transform 0.3s ease, box-shadow 0.3s ease';
        element.style.transform = 'scale(1.02)';
        element.style.boxShadow = '0 0 20px rgba(99, 102, 241, 0.3)';

        setTimeout(() => {
            element.style.transform = 'scale(1)';
            element.style.boxShadow = '';
        }, 300);
    }

    /**
     * Update charts (placeholder - to be implemented with custom rendering)
     * @private
     */
    async _updateCharts(chartsData) {
        // TODO: Replace Chart.js with custom canvas rendering for 60fps
        // For now, keep existing Chart.js implementation
        console.log('📈 Charts update (placeholder):', chartsData);
    }

    /**
     * Handle errors
     * @private
     */
    _handleError(source, error) {
        console.error(`Error from ${source}:`, error);
        // TODO: Show user-friendly error toast
    }

    /**
     * Setup date range filter
     * @private
     */
    _setupDateRangeFilter() {
        const select = document.querySelector('.date-range-select');
        if (!select) return;

        select.addEventListener('change', (e) => {
            const days = parseInt(e.target.value);
            this.days = days;
            this.lifecycle.changeFilter(days);
        });
    }

    /**
     * Setup tab switching
     * @private
     */
    _setupTabSwitching() {
        const tabs = document.querySelectorAll('.analytics-tab');
        
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const toTab = tab.dataset.tab;
                const fromTab = this.currentTab;

                if (toTab === fromTab) return;

                // Update UI
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                const tabContents = document.querySelectorAll('.analytics-tab-content');
                tabContents.forEach(content => content.classList.remove('active'));
                document.getElementById(`tab-${toTab}`)?.classList.add('active');

                // Notify lifecycle
                this.lifecycle.switchTab(fromTab, toTab);

                this.currentTab = toTab;
            });
        });
    }

    /**
     * Setup export button
     * @private
     */
    _setupExportButton() {
        const exportBtn = document.querySelector('.btn-outline:has(svg[viewBox="0 0 24 24"]) + .btn-outline');
        // TODO: Implement export worker
        console.log('Export button setup (placeholder)');
    }

    /**
     * Get telemetry data
     */
    getTelemetry() {
        return this.lifecycle.getTelemetry();
    }

    /**
     * Cleanup
     */
    destroy() {
        if (this.lifecycle) {
            this.lifecycle.destroy();
        }
    }
}

// Auto-initialize if on analytics page
if (document.querySelector('.analytics-workspace')) {
    // Wait for socket connection
    window.addEventListener('DOMContentLoaded', async () => {
        // Get workspace ID from context
        const workspaceId = window.currentWorkspaceId || 1;

        // Connect to analytics namespace
        const analyticsSocket = io('/analytics');

        analyticsSocket.on('connect', () => {
            console.log('✅ Analytics WebSocket connected');
            
            // Initialize CROWN⁵+ analytics
            window.crown5Analytics = new Crown5Analytics(workspaceId, analyticsSocket);
        });

        analyticsSocket.on('disconnect', () => {
            console.warn('⚠️ Analytics WebSocket disconnected');
        });
    });
}
