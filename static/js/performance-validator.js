/**
 * CROWN⁴.5 Performance Validation Dashboard
 * Validates and reports on all performance targets
 */

class PerformanceValidator {
    constructor() {
        this.targets = {
            firstPaint: 200,           // ms - Bootstrap/First Paint
            mutationApply: 50,         // ms - DOM update latency
            reconcileP95: 150,         // ms - Event reconciliation P95
            scrollFPS: 60,             // FPS - Scroll performance
            wsPropagation: 300,        // ms - WebSocket propagation
            cacheHitRate: 0.9          // 90% cache hit rate
        };

        this.metrics = {
            firstPaint: [],
            mutationApply: [],
            reconcile: [],
            scrollFPS: [],
            wsPropagation: [],
            cacheHits: 0,
            cacheMisses: 0
        };

        this.init();
    }

    init() {
        this.setupPerformanceObservers();
        this.monitorScrollPerformance();
        
        console.log('📊 CROWN⁴.5 Performance Validator initialized');
        
        // Auto-print performance report every 30 seconds
        this.startAutoReporting();
        
        // Expose to window for manual inspection
        window.performanceValidator = this;
        
        // Add keyboard shortcut (Ctrl+Shift+P) to show dashboard
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'P') {
                e.preventDefault();
                this.printReport();
            }
        });
    }

    startAutoReporting() {
        // Print initial report after 5 seconds (allow metrics to collect)
        setTimeout(() => {
            console.log('📊 Initial CROWN⁴.5 Performance Report:');
            this.printReport();
        }, 5000);
        
        // Then print every 30 seconds
        setInterval(() => {
            this.printReport();
        }, 30000);
    }

    setupPerformanceObservers() {
        // CROWN⁴.6: Use early First Paint marker from inline script
        if (window.__FIRST_PAINT_TIME !== undefined) {
            console.log(`⚡ [PerformanceValidator] Using early First Paint: ${Math.round(window.__FIRST_PAINT_TIME)}ms`);
            this.recordMetric('firstPaint', window.__FIRST_PAINT_TIME);
        }
        
        // Listen for task bootstrap completion event (fallback)
        document.addEventListener('task:bootstrap:complete', (e) => {
            if (e.detail && e.detail.first_paint_ms && this.metrics.firstPaint.length === 0) {
                console.log(`📊 [PerformanceValidator] Captured first paint: ${e.detail.first_paint_ms.toFixed(2)}ms`);
                this.recordMetric('firstPaint', e.detail.first_paint_ms);
            }
        });
        
        // Monitor paint timing from Performance API (fallback)
        if (window.performance && window.performance.getEntriesByType && this.metrics.firstPaint.length === 0) {
            const paintEntries = window.performance.getEntriesByType('paint');
            paintEntries.forEach(entry => {
                if (entry.name === 'first-contentful-paint') {
                    this.recordMetric('firstPaint', entry.startTime);
                }
            });
        }

        // Monitor navigation timing for initial load (fallback)
        if (window.performance && window.performance.timing && this.metrics.firstPaint.length === 0) {
            window.addEventListener('load', () => {
                if (this.metrics.firstPaint.length === 0) {
                    const timing = window.performance.timing;
                    const firstPaint = timing.domContentLoadedEventEnd - timing.navigationStart;
                    this.recordMetric('firstPaint', firstPaint);
                }
            });
        }

        // Monitor DOM mutations
        this.observeDOMMutations();

        // Monitor cache performance
        this.monitorCachePerformance();

        // Monitor WebSocket propagation (if available)
        this.monitorWebSocketPropagation();

        // Monitor reconciliation performance
        this.monitorReconciliation();
    }

    observeDOMMutations() {
        const observer = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                if (entry.entryType === 'measure' && entry.name.includes('mutation')) {
                    this.recordMetric('mutationApply', entry.duration);
                }
            }
        });

        try {
            observer.observe({ entryTypes: ['measure'] });
        } catch (e) {
            console.warn('Performance observer not supported');
        }

        // Also manually track DOM updates
        this.setupMutationTracking();
    }

    setupMutationTracking() {
        const originalAppendChild = Element.prototype.appendChild;
        const originalInsertBefore = Element.prototype.insertBefore;
        const self = this;

        Element.prototype.appendChild = function(...args) {
            const start = performance.now();
            const result = originalAppendChild.apply(this, args);
            const duration = performance.now() - start;
            self.recordMetric('mutationApply', duration);
            return result;
        };

        Element.prototype.insertBefore = function(...args) {
            const start = performance.now();
            const result = originalInsertBefore.apply(this, args);
            const duration = performance.now() - start;
            self.recordMetric('mutationApply', duration);
            return result;
        };
    }

    monitorScrollPerformance() {
        let lastScrollTime = 0;
        let frameCount = 0;
        let fps = 60;

        const measureFPS = () => {
            const now = performance.now();
            if (lastScrollTime) {
                const delta = now - lastScrollTime;
                fps = 1000 / delta;
                this.recordMetric('scrollFPS', fps);
            }
            lastScrollTime = now;
            frameCount++;
        };

        // Monitor scroll events
        let scrolling = false;
        window.addEventListener('scroll', () => {
            if (!scrolling) {
                scrolling = true;
                frameCount = 0;
                lastScrollTime = 0;
            }
        });

        // Use requestAnimationFrame to measure FPS during scroll
        const checkScroll = () => {
            if (scrolling) {
                measureFPS();
            }
            requestAnimationFrame(checkScroll);
        };
        requestAnimationFrame(checkScroll);

        // Stop measuring after scroll ends
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                scrolling = false;
            }, 200);
        });
    }

    monitorCachePerformance() {
        // Hook into TaskCache if available
        window.addEventListener('cache:hit', () => {
            this.metrics.cacheHits++;
        });

        window.addEventListener('cache:miss', () => {
            this.metrics.cacheMisses++;
        });
    }

    monitorWebSocketPropagation() {
        // Hook into telemetry for WebSocket metrics
        window.addEventListener('ws:propagation', (e) => {
            if (e.detail && e.detail.latency) {
                this.recordMetric('wsPropagation', e.detail.latency);
            }
        });

        // Also pull from CROWNTelemetry directly
        setInterval(() => {
            if (window.CROWNTelemetry && window.CROWNTelemetry.sessionMetrics) {
                const propagations = window.CROWNTelemetry.sessionMetrics.eventPropagations || [];
                propagations.forEach(p => {
                    if (p.latency) {
                        this.recordMetric('wsPropagation', p.latency);
                    }
                });
            }
        }, 5000); // Check every 5 seconds
    }

    monitorReconciliation() {
        // Listen for reconciliation completion events
        window.addEventListener('reconcile:complete', (e) => {
            if (e.detail && e.detail.reconcileTime) {
                this.recordMetric('reconcile', e.detail.reconcileTime);
            }
        });
    }

    recordMetric(metricName, value) {
        if (this.metrics[metricName] && Array.isArray(this.metrics[metricName])) {
            this.metrics[metricName].push({
                value,
                timestamp: Date.now()
            });

            // Keep last 100 measurements
            if (this.metrics[metricName].length > 100) {
                this.metrics[metricName].shift();
            }
        }
    }

    getStats(metricName) {
        const data = this.metrics[metricName];
        if (!data || !Array.isArray(data) || data.length === 0) {
            return null;
        }

        const values = data.map(d => d.value).sort((a, b) => a - b);
        const sum = values.reduce((a, b) => a + b, 0);

        return {
            count: values.length,
            avg: sum / values.length,
            min: values[0],
            max: values[values.length - 1],
            p50: values[Math.floor(values.length * 0.50)],
            p95: values[Math.floor(values.length * 0.95)],
            p99: values[Math.floor(values.length * 0.99)]
        };
    }

    getCacheHitRate() {
        const total = this.metrics.cacheHits + this.metrics.cacheMisses;
        if (total === 0) return null;
        return this.metrics.cacheHits / total;
    }

    validate() {
        const report = {
            timestamp: new Date().toISOString(),
            passed: true,
            metrics: {}
        };

        // Validate First Paint
        const firstPaintStats = this.getStats('firstPaint');
        if (firstPaintStats) {
            report.metrics.firstPaint = {
                target: this.targets.firstPaint,
                actual: firstPaintStats.avg,
                passed: firstPaintStats.avg <= this.targets.firstPaint,
                stats: firstPaintStats
            };
            if (!report.metrics.firstPaint.passed) report.passed = false;
        }

        // Validate Mutation Apply
        const mutationStats = this.getStats('mutationApply');
        if (mutationStats) {
            report.metrics.mutationApply = {
                target: this.targets.mutationApply,
                actual: mutationStats.p95,
                passed: mutationStats.p95 <= this.targets.mutationApply,
                stats: mutationStats
            };
            if (!report.metrics.mutationApply.passed) report.passed = false;
        }

        // Validate Scroll FPS
        const scrollStats = this.getStats('scrollFPS');
        if (scrollStats) {
            report.metrics.scrollFPS = {
                target: this.targets.scrollFPS,
                actual: scrollStats.avg,
                passed: scrollStats.avg >= this.targets.scrollFPS,
                stats: scrollStats
            };
            if (!report.metrics.scrollFPS.passed) report.passed = false;
        }

        // Validate WebSocket Propagation
        const wsStats = this.getStats('wsPropagation');
        if (wsStats) {
            report.metrics.wsPropagation = {
                target: this.targets.wsPropagation,
                actual: wsStats.p95,
                passed: wsStats.p95 <= this.targets.wsPropagation,
                stats: wsStats
            };
            if (!report.metrics.wsPropagation.passed) report.passed = false;
        }

        // Validate Reconciliation
        const reconcileStats = this.getStats('reconcile');
        if (reconcileStats) {
            const reconcileTarget = this.targets.reconcileP95;
            report.metrics.reconcile = {
                target: reconcileTarget,
                actual: reconcileStats.p95,
                passed: reconcileStats.p95 <= reconcileTarget,
                stats: reconcileStats
            };
            if (!report.metrics.reconcile.passed) report.passed = false;
        }

        // Validate Cache Hit Rate
        const cacheHitRate = this.getCacheHitRate();
        if (cacheHitRate !== null) {
            report.metrics.cacheHitRate = {
                target: this.targets.cacheHitRate,
                actual: cacheHitRate,
                passed: cacheHitRate >= this.targets.cacheHitRate,
                hits: this.metrics.cacheHits,
                misses: this.metrics.cacheMisses
            };
            if (!report.metrics.cacheHitRate.passed) report.passed = false;
        }

        // Get telemetry data if available
        if (window.CROWNTelemetry && window.CROWNTelemetry.getSummary) {
            const telemetrySummary = window.CROWNTelemetry.getSummary();
            
            // Add Bootstrap/First Paint from telemetry
            if (telemetrySummary.bootstrap) {
                report.metrics.bootstrap = {
                    target: this.targets.firstPaint,
                    actual: telemetrySummary.bootstrap.time,
                    passed: telemetrySummary.bootstrap.status === 'pass'
                };
                if (!report.metrics.bootstrap.passed) report.passed = false;
            }

            // Add WS Propagation from telemetry
            if (telemetrySummary.propagation) {
                report.metrics.propagation = {
                    target: this.targets.wsPropagation,
                    actual: telemetrySummary.propagation.p95,
                    passed: telemetrySummary.propagation.status === 'pass',
                    stats: {
                        avg: telemetrySummary.propagation.avg,
                        p95: telemetrySummary.propagation.p95
                    }
                };
                if (!report.metrics.propagation.passed) report.passed = false;
            }
        }

        return report;
    }

    printReport() {
        const report = this.validate();
        
        console.log('\n╔════════════════════════════════════════════════════════╗');
        console.log('║         CROWN⁴.5 Performance Validation Report         ║');
        console.log('╚════════════════════════════════════════════════════════╝\n');

        console.log(`Overall Status: ${report.passed ? '✅ PASS' : '❌ FAIL'}\n`);

        // Bootstrap / First Paint
        if (report.metrics.bootstrap || report.metrics.firstPaint) {
            const metric = report.metrics.bootstrap || report.metrics.firstPaint;
            console.log(`${metric.passed ? '✅' : '❌'} First Paint: ${metric.actual?.toFixed(0) || 'N/A'}ms (target: ≤${metric.target}ms)`);
        }

        // Mutation Apply
        if (report.metrics.mutationApply) {
            const m = report.metrics.mutationApply;
            console.log(`${m.passed ? '✅' : '❌'} Mutation Apply (P95): ${m.actual.toFixed(1)}ms (target: ≤${m.target}ms)`);
            console.log(`   └─ Avg: ${m.stats.avg.toFixed(1)}ms, Count: ${m.stats.count}`);
        }

        // Scroll FPS
        if (report.metrics.scrollFPS) {
            const m = report.metrics.scrollFPS;
            console.log(`${m.passed ? '✅' : '❌'} Scroll Performance: ${m.actual.toFixed(1)} FPS (target: ≥${m.target} FPS)`);
            console.log(`   └─ Min: ${m.stats.min.toFixed(1)} FPS, Count: ${m.stats.count}`);
        }

        // Reconciliation
        if (report.metrics.reconcile) {
            const m = report.metrics.reconcile;
            console.log(`${m.passed ? '✅' : '❌'} Reconciliation (P95): ${m.actual.toFixed(1)}ms (target: ≤${m.target}ms)`);
            console.log(`   └─ Avg: ${m.stats.avg.toFixed(1)}ms, Count: ${m.stats.count}`);
        }

        // WebSocket Propagation
        if (report.metrics.propagation || report.metrics.wsPropagation) {
            const m = report.metrics.propagation || report.metrics.wsPropagation;
            console.log(`${m.passed ? '✅' : '❌'} WS Propagation (P95): ${m.actual.toFixed(0)}ms (target: ≤${m.target}ms)`);
            if (m.stats) {
                console.log(`   └─ Avg: ${m.stats.avg.toFixed(0)}ms`);
            }
        }

        // Cache Hit Rate
        if (report.metrics.cacheHitRate) {
            const m = report.metrics.cacheHitRate;
            console.log(`${m.passed ? '✅' : '❌'} Cache Hit Rate: ${(m.actual * 100).toFixed(1)}% (target: ≥${m.target * 100}%)`);
            console.log(`   └─ Hits: ${m.hits}, Misses: ${m.misses}`);
        }

        console.log('\n─────────────────────────────────────────────────────────');
        console.log(`Report generated: ${report.timestamp}`);
        console.log('─────────────────────────────────────────────────────────\n');

        return report;
    }

    showDashboard() {
        const report = this.validate();
        
        // Create modal dashboard
        const modal = document.createElement('div');
        modal.className = 'performance-dashboard-modal';
        modal.innerHTML = `
            <div class="performance-dashboard-content">
                <button class="close-dashboard-btn">×</button>
                <h2>
                    <span>📊</span>
                    <span>CROWN⁴.5 Performance Dashboard</span>
                </h2>
                
                <div class="performance-status ${report.passed ? 'pass' : 'fail'}">
                    <span class="status-icon">${report.passed ? '✅' : '❌'}</span>
                    <span class="status-text">${report.passed ? 'All targets met' : 'Some targets not met'}</span>
                </div>

                <div class="performance-metrics">
                    ${this.renderMetricCards(report)}
                </div>

                <div style="margin-top: 1.5rem; text-align: center;">
                    <button class="btn-primary" onclick="window.performanceValidator.printReport()">
                        Print Report to Console
                    </button>
                </div>
            </div>
        `;

        this.addDashboardStyles();
        document.body.appendChild(modal);

        // Close handler
        const closeBtn = modal.querySelector('.close-dashboard-btn');
        closeBtn.addEventListener('click', () => modal.remove());
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    }

    renderMetricCards(report) {
        let html = '';

        const metrics = [
            { key: 'bootstrap', name: 'Bootstrap / First Paint', unit: 'ms', inverse: false },
            { key: 'mutationApply', name: 'Mutation Apply (P95)', unit: 'ms', inverse: false },
            { key: 'reconcile', name: 'Reconciliation (P95)', unit: 'ms', inverse: false },
            { key: 'scrollFPS', name: 'Scroll Performance', unit: 'FPS', inverse: true },
            { key: 'propagation', name: 'WS Propagation (P95)', unit: 'ms', inverse: false },
            { key: 'cacheHitRate', name: 'Cache Hit Rate', unit: '%', inverse: true, multiplier: 100 }
        ];

        metrics.forEach(({ key, name, unit, inverse, multiplier = 1 }) => {
            const metric = report.metrics[key];
            if (!metric) return;

            const actual = metric.actual * multiplier;
            const target = metric.target * multiplier;
            const operator = inverse ? '≥' : '≤';

            html += `
                <div class="metric-card ${metric.passed ? 'pass' : 'fail'}">
                    <div class="metric-header">
                        <span class="metric-icon">${metric.passed ? '✅' : '❌'}</span>
                        <span class="metric-name">${name}</span>
                    </div>
                    <div class="metric-value">
                        ${actual !== null && actual !== undefined ? actual.toFixed(1) : 'N/A'} ${unit}
                    </div>
                    <div class="metric-target">
                        Target: ${operator}${target.toFixed(0)} ${unit}
                    </div>
                </div>
            `;
        });

        return html;
    }

    addDashboardStyles() {
        if (document.getElementById('performance-dashboard-styles')) return;

        const style = document.createElement('style');
        style.id = 'performance-dashboard-styles';
        style.textContent = `
            .performance-dashboard-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(4px);
                z-index: 10001;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 2rem;
            }

            .performance-dashboard-content {
                background: var(--color-bg-primary);
                border: 1px solid var(--glass-border);
                border-radius: var(--radius-2xl);
                max-width: 800px;
                width: 100%;
                max-height: 90vh;
                overflow-y: auto;
                padding: 2rem;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            }

            .performance-dashboard-content h2 {
                margin: 0 0 1.5rem 0;
                font-size: 1.5rem;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }

            .close-dashboard-btn {
                position: absolute;
                top: 1.5rem;
                right: 1.5rem;
                background: transparent;
                border: none;
                font-size: 1.5rem;
                cursor: pointer;
                color: var(--color-text-secondary);
                padding: 0.5rem;
            }

            .performance-status {
                padding: 1rem 1.5rem;
                border-radius: var(--radius-lg);
                margin-bottom: 2rem;
                display: flex;
                align-items: center;
                gap: 1rem;
                font-size: 1.125rem;
                font-weight: 600;
            }

            .performance-status.pass {
                background: rgba(16, 185, 129, 0.1);
                border: 2px solid #10b981;
                color: #10b981;
            }

            .performance-status.fail {
                background: rgba(239, 68, 68, 0.1);
                border: 2px solid #ef4444;
                color: #ef4444;
            }

            .performance-metrics {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
            }

            .metric-card {
                padding: 1.5rem;
                border-radius: var(--radius-lg);
                border: 2px solid;
            }

            .metric-card.pass {
                background: rgba(16, 185, 129, 0.05);
                border-color: #10b981;
            }

            .metric-card.fail {
                background: rgba(239, 68, 68, 0.05);
                border-color: #ef4444;
            }

            .metric-header {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-bottom: 1rem;
            }

            .metric-name {
                font-size: 0.875rem;
                font-weight: 600;
                color: var(--color-text-primary);
            }

            .metric-value {
                font-size: 2rem;
                font-weight: 700;
                color: var(--color-text-primary);
                margin-bottom: 0.5rem;
            }

            .metric-target {
                font-size: 0.75rem;
                color: var(--color-text-secondary);
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            .btn-primary {
                padding: 0.75rem 1.5rem;
                background: var(--color-primary);
                color: white;
                border: none;
                border-radius: var(--radius-lg);
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }

            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
            }
        `;

        document.head.appendChild(style);
    }
}

// Initialize global instance IMMEDIATELY (no DOMContentLoaded wait)
// This ensures the event listener is attached before task-bootstrap can emit events
window.performanceValidator = new PerformanceValidator();

// Auto-print report after 10 seconds of page load
setTimeout(() => {
    if (window.performanceValidator) {
        console.log('\n🚀 Auto-generating CROWN⁴.5 Performance Report...\n');
        window.performanceValidator.printReport();
    }
}, 10000);

console.log('📊 CROWN⁴.5 Performance Validator loaded');
console.log('💡 Call window.performanceValidator.showDashboard() to view metrics');
console.log('💡 Call window.performanceValidator.printReport() for console report');
