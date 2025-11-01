/**
 * CROWN⁴.5 Calm Score Widget
 * Visual indicator of emotional architecture health and system responsiveness
 */

class CalmScoreWidget {
    constructor() {
        this.currentScore = 100;
        this.scoreHistory = [];
        this.maxHistoryLength = 60; // 60 seconds of data
        this.widget = null;
        this.updateInterval = null;
        
        this.init();
    }

    init() {
        this.createWidget();
        this.startMonitoring();
        
        // Listen for telemetry updates
        window.addEventListener('crown:telemetry:update', (e) => {
            if (e.detail && e.detail.calmScore !== undefined) {
                this.updateScore(e.detail.calmScore);
            }
        });

        console.log('🧘 CROWN⁴.5 Calm Score Widget initialized');
    }

    createWidget() {
        const container = document.createElement('div');
        container.className = 'calm-score-widget';
        container.innerHTML = `
            <div class="calm-score-container">
                <div class="calm-score-icon">🧘</div>
                <div class="calm-score-details">
                    <div class="calm-score-label">Calm Score</div>
                    <div class="calm-score-value">100</div>
                </div>
                <div class="calm-score-bar">
                    <div class="calm-score-fill" style="width: 100%;"></div>
                </div>
            </div>
        `;

        // Add styles
        this.addStyles();

        // Append to page (top-right corner)
        document.body.appendChild(container);
        this.widget = container;

        // Add click handler to show details
        container.addEventListener('click', () => this.showDetails());
    }

    addStyles() {
        if (document.getElementById('calm-score-widget-styles')) return;

        const style = document.createElement('style');
        style.id = 'calm-score-widget-styles';
        style.textContent = `
            .calm-score-widget {
                position: fixed;
                top: 1rem;
                right: 1rem;
                z-index: 9999;
                background: var(--glass-bg);
                backdrop-filter: var(--backdrop-blur);
                border: 1px solid var(--glass-border);
                border-radius: var(--radius-xl);
                padding: 0.75rem 1rem;
                min-width: 160px;
                cursor: pointer;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            }

            .calm-score-widget:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            }

            .calm-score-container {
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }

            .calm-score-icon {
                font-size: 1.5rem;
                animation: calm-pulse 3s ease-in-out infinite;
            }

            @keyframes calm-pulse {
                0%, 100% {
                    transform: scale(1);
                    opacity: 1;
                }
                50% {
                    transform: scale(1.1);
                    opacity: 0.8;
                }
            }

            .calm-score-details {
                flex: 1;
            }

            .calm-score-label {
                font-size: 0.75rem;
                color: var(--color-text-secondary);
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            .calm-score-value {
                font-size: 1.25rem;
                font-weight: 700;
                color: var(--color-text-primary);
                line-height: 1;
                margin-top: 0.125rem;
            }

            .calm-score-bar {
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: rgba(0, 0, 0, 0.1);
                border-radius: 0 0 var(--radius-xl) var(--radius-xl);
                overflow: hidden;
            }

            .calm-score-fill {
                height: 100%;
                background: linear-gradient(90deg, #10b981, #34d399);
                transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1), background 0.3s;
            }

            .calm-score-fill.warning {
                background: linear-gradient(90deg, #f59e0b, #fbbf24);
            }

            .calm-score-fill.danger {
                background: linear-gradient(90deg, #ef4444, #f87171);
            }

            .calm-score-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(4px);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 2rem;
                animation: modalFadeIn 0.2s ease-out;
            }

            @keyframes modalFadeIn {
                from {
                    opacity: 0;
                }
                to {
                    opacity: 1;
                }
            }

            .calm-score-modal-content {
                background: var(--color-bg-primary);
                border: 1px solid var(--glass-border);
                border-radius: var(--radius-2xl);
                max-width: 600px;
                width: 100%;
                max-height: 80vh;
                overflow-y: auto;
                padding: 2rem;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                animation: modalSlideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }

            @keyframes modalSlideIn {
                from {
                    transform: translateY(20px);
                    opacity: 0;
                }
                to {
                    transform: translateY(0);
                    opacity: 1;
                }
            }

            .calm-score-modal h2 {
                margin: 0 0 1.5rem 0;
                font-size: 1.5rem;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }

            .calm-score-chart {
                height: 120px;
                background: var(--glass-bg);
                border-radius: var(--radius-lg);
                padding: 1rem;
                margin-bottom: 1.5rem;
                position: relative;
                overflow: hidden;
            }

            .calm-score-metrics {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                gap: 1rem;
            }

            .calm-metric-card {
                background: var(--glass-bg);
                border: 1px solid var(--glass-border);
                border-radius: var(--radius-lg);
                padding: 1rem;
            }

            .calm-metric-label {
                font-size: 0.75rem;
                color: var(--color-text-secondary);
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 0.5rem;
            }

            .calm-metric-value {
                font-size: 1.5rem;
                font-weight: 700;
                color: var(--color-text-primary);
            }

            .calm-metric-unit {
                font-size: 0.875rem;
                font-weight: 400;
                color: var(--color-text-secondary);
                margin-left: 0.25rem;
            }

            .close-modal-btn {
                position: absolute;
                top: 1.5rem;
                right: 1.5rem;
                background: transparent;
                border: none;
                font-size: 1.5rem;
                cursor: pointer;
                color: var(--color-text-secondary);
                padding: 0.5rem;
                line-height: 1;
            }

            .close-modal-btn:hover {
                color: var(--color-text-primary);
            }
        `;

        document.head.appendChild(style);
    }

    startMonitoring() {
        // Update every second
        this.updateInterval = setInterval(() => {
            this.calculateAndUpdateScore();
        }, 1000);
    }

    calculateAndUpdateScore() {
        let score = 100;

        // Get score from QuietStateManager if available
        if (window.quietStateManager) {
            const state = window.quietStateManager.getState();
            score = state.calmScore;
        }

        // Get score from CROWNTelemetry if available
        if (window.CROWNTelemetry && window.CROWNTelemetry.sessionMetrics) {
            const telemetryScore = window.CROWNTelemetry.sessionMetrics.calmScore;
            if (telemetryScore !== undefined) {
                score = Math.min(score, telemetryScore);
            }
        }

        this.updateScore(score);
    }

    updateScore(score) {
        this.currentScore = Math.round(score);
        
        // Add to history
        this.scoreHistory.push({
            time: Date.now(),
            score: this.currentScore
        });

        // Trim history
        if (this.scoreHistory.length > this.maxHistoryLength) {
            this.scoreHistory.shift();
        }

        // Update UI
        this.renderScore();

        // Record to telemetry
        if (window.CROWNTelemetry && window.CROWNTelemetry.recordMetric) {
            window.CROWNTelemetry.recordMetric('calm_score', this.currentScore);
        }
    }

    renderScore() {
        if (!this.widget) return;

        const valueEl = this.widget.querySelector('.calm-score-value');
        const fillEl = this.widget.querySelector('.calm-score-fill');

        if (valueEl) {
            valueEl.textContent = this.currentScore;
        }

        if (fillEl) {
            fillEl.style.width = `${this.currentScore}%`;
            
            // Update color based on score
            fillEl.classList.remove('warning', 'danger');
            if (this.currentScore < 50) {
                fillEl.classList.add('danger');
            } else if (this.currentScore < 75) {
                fillEl.classList.add('warning');
            }
        }
    }

    showDetails() {
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'calm-score-modal';
        modal.innerHTML = `
            <div class="calm-score-modal-content">
                <button class="close-modal-btn">×</button>
                <h2>
                    <span>🧘</span>
                    <span>Calm Score Insights</span>
                </h2>
                
                <div class="calm-score-chart">
                    ${this.renderMiniChart()}
                </div>

                <div class="calm-score-metrics">
                    <div class="calm-metric-card">
                        <div class="calm-metric-label">Current Score</div>
                        <div class="calm-metric-value">
                            ${this.currentScore}
                            <span class="calm-metric-unit">/ 100</span>
                        </div>
                    </div>

                    <div class="calm-metric-card">
                        <div class="calm-metric-label">Average (1m)</div>
                        <div class="calm-metric-value">
                            ${this.getAverageScore()}
                            <span class="calm-metric-unit">/ 100</span>
                        </div>
                    </div>

                    <div class="calm-metric-card">
                        <div class="calm-metric-label">Animations</div>
                        <div class="calm-metric-value">
                            ${this.getActiveAnimations()}
                            <span class="calm-metric-unit">active</span>
                        </div>
                    </div>

                    <div class="calm-metric-card">
                        <div class="calm-metric-label">System Health</div>
                        <div class="calm-metric-value" style="color: ${this.getHealthColor()};">
                            ${this.getHealthStatus()}
                        </div>
                    </div>
                </div>

                <div style="margin-top: 1.5rem; padding: 1rem; background: var(--glass-bg); border-radius: var(--radius-lg);">
                    <p style="margin: 0; font-size: 0.875rem; color: var(--color-text-secondary); line-height: 1.6;">
                        <strong>What is Calm Score?</strong><br>
                        Calm Score measures how smoothly and responsively the app is performing. 
                        A score above 75 indicates excellent performance with minimal visual interruptions. 
                        Lower scores may indicate heavy animation activity or system load.
                    </p>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close handlers
        const closeBtn = modal.querySelector('.close-modal-btn');
        closeBtn.addEventListener('click', () => modal.remove());
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    renderMiniChart() {
        const width = 100;
        const height = 80;
        const points = this.scoreHistory.slice(-30); // Last 30 seconds

        if (points.length < 2) {
            return `<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--color-text-secondary);">
                Collecting data...
            </div>`;
        }

        const maxScore = 100;
        const pathData = points.map((point, index) => {
            const x = (index / (points.length - 1)) * width;
            const y = height - (point.score / maxScore) * height;
            return `${x},${y}`;
        }).join(' ');

        return `
            <svg width="100%" height="100%" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
                <polyline
                    points="${pathData}"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    style="color: #6366f1;"
                />
                <line
                    x1="0" y1="${height - (75 / maxScore) * height}"
                    x2="${width}" y2="${height - (75 / maxScore) * height}"
                    stroke="rgba(255, 255, 255, 0.2)"
                    stroke-width="1"
                    stroke-dasharray="4 2"
                />
            </svg>
        `;
    }

    getAverageScore() {
        if (this.scoreHistory.length === 0) return 100;
        
        const sum = this.scoreHistory.reduce((acc, point) => acc + point.score, 0);
        return Math.round(sum / this.scoreHistory.length);
    }

    getActiveAnimations() {
        if (window.quietStateManager) {
            const state = window.quietStateManager.getState();
            return state.activeAnimations;
        }
        return 0;
    }

    getHealthStatus() {
        if (this.currentScore >= 75) return 'Excellent';
        if (this.currentScore >= 50) return 'Good';
        if (this.currentScore >= 25) return 'Fair';
        return 'Poor';
    }

    getHealthColor() {
        if (this.currentScore >= 75) return '#10b981';
        if (this.currentScore >= 50) return '#f59e0b';
        return '#ef4444';
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.widget) {
            this.widget.remove();
        }
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.calmScoreWidget = new CalmScoreWidget();
    });
} else {
    window.calmScoreWidget = new CalmScoreWidget();
}

console.log('🧘 CROWN⁴.5 Calm Score Widget loaded');
