/**
 * CROWN⁴.6 Developer Performance Panel
 * Ctrl+Shift+M keyboard shortcut to view real-time performance metrics
 */

class DevPerformancePanel {
    constructor() {
        this.isVisible = false;
        this.panelElement = null;
        this.refreshInterval = null;
        this.init();
    }

    init() {
        console.log('[DevPerformancePanel] Initializing...');

        // Create panel element
        this.createPanel();

        // Listen for keyboard shortcut: Ctrl+Shift+M
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'M') {
                e.preventDefault();
                this.toggle();
            }
        });

        // Close on Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.hide();
            }
        });

        console.log('[DevPerformancePanel] Initialized - Press Ctrl+Shift+M to open');
    }

    createPanel() {
        const panel = document.createElement('div');
        panel.className = 'dev-performance-panel';
        panel.id = 'dev-performance-panel';
        
        panel.innerHTML = `
            <div class="dev-panel-content" onclick="event.stopPropagation()">
                <div class="dev-panel-header">
                    <div>
                        <div class="dev-panel-title">
                            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                            </svg>
                            Performance Metrics
                        </div>
                        <div class="dev-panel-subtitle">CROWN⁴.6 Developer Panel</div>
                    </div>
                    <button class="dev-panel-close" onclick="window.devPerformancePanel.hide()">
                        ESC
                    </button>
                </div>

                <div class="dev-metrics-grid">
                    <div class="dev-metric-card" id="metric-first-paint">
                        <div class="dev-metric-label">First Paint</div>
                        <div class="dev-metric-value">--</div>
                        <div class="dev-metric-target">Target: ≤200ms</div>
                    </div>

                    <div class="dev-metric-card" id="metric-cache-ratio">
                        <div class="dev-metric-label">Cache Hit Ratio</div>
                        <div class="dev-metric-value">--</div>
                        <div class="dev-metric-target">Target: ≥80%</div>
                    </div>

                    <div class="dev-metric-card" id="metric-ws-latency">
                        <div class="dev-metric-label">WS Latency (P95)</div>
                        <div class="dev-metric-value">--</div>
                        <div class="dev-metric-target">Target: ≤300ms</div>
                    </div>

                    <div class="dev-metric-card" id="metric-calm-score">
                        <div class="dev-metric-label">Calm Score</div>
                        <div class="dev-metric-value">--</div>
                        <div class="dev-metric-target">Motion budget compliance</div>
                    </div>
                </div>

                <div class="dev-panel-footer">
                    Press Ctrl+Shift+M to close • Metrics refresh every 2 seconds
                </div>
            </div>
        `;

        // Click outside to close
        panel.addEventListener('click', () => {
            this.hide();
        });

        document.body.appendChild(panel);
        this.panelElement = panel;
    }

    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    show() {
        if (!this.panelElement) return;

        this.panelElement.classList.add('visible');
        this.isVisible = true;

        // Initial metrics load
        this.updateMetrics();

        // Auto-refresh every 2 seconds
        this.refreshInterval = setInterval(() => {
            this.updateMetrics();
        }, 2000);

        console.log('[DevPerformancePanel] Opened');
    }

    hide() {
        if (!this.panelElement) return;

        this.panelElement.classList.remove('visible');
        this.isVisible = false;

        // Stop auto-refresh
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }

        console.log('[DevPerformancePanel] Closed');
    }

    updateMetrics() {
        // Get metrics from performance validator and CROWN telemetry
        const validator = window.performanceValidator;
        const telemetry = window.CROWNTelemetry;

        // Metric 1: First Paint
        this.updateMetric('first-paint', 
            validator?.metrics?.first_paint_ms,
            200,
            'ms',
            (val) => val !== null && val !== undefined && !isNaN(val)
        );

        // Metric 2: Cache Hit Ratio
        if (telemetry) {
            const ratio = telemetry.getCacheHitRatio();
            this.updateMetric('cache-ratio',
                ratio > 0 ? ratio * 100 : null,
                80,
                '%',
                (val) => val !== null
            );
        }

        // Metric 3: WebSocket Latency (P95)
        this.updateMetric('ws-latency',
            validator?.metrics?.ws_propagation_p95,
            300,
            'ms',
            (val) => val !== null && val !== undefined && !isNaN(val)
        );

        // Metric 4: Calm Score
        if (telemetry?.sessionMetrics?.calmScore !== undefined) {
            this.updateMetric('calm-score',
                telemetry.sessionMetrics.calmScore,
                90,
                '/100',
                (val) => val !== null,
                true // higher is better
            );
        }
    }

    updateMetric(metricId, value, target, unit, isValid, higherIsBetter = false) {
        const card = document.getElementById(`metric-${metricId}`);
        if (!card) return;

        const valueElement = card.querySelector('.dev-metric-value');
        
        if (isValid(value)) {
            // Format value
            const formattedValue = typeof value === 'number' 
                ? (value < 10 ? value.toFixed(1) : Math.round(value))
                : value;
            
            valueElement.textContent = `${formattedValue}${unit}`;

            // Determine status color
            let status;
            if (higherIsBetter) {
                // Higher is better (e.g., calm score)
                status = value >= target ? 'success' : value >= target * 0.8 ? 'warning' : 'error';
            } else {
                // Lower is better (e.g., latency)
                status = value <= target ? 'success' : value <= target * 1.5 ? 'warning' : 'error';
            }

            card.className = `dev-metric-card ${status}`;
        } else {
            valueElement.textContent = 'N/A';
            card.className = 'dev-metric-card neutral';
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.devPerformancePanel = new DevPerformancePanel();
});
