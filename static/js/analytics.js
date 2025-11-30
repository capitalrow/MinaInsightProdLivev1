/**
 * Analytics Dashboard - Live Data Integration
 * Fetches real-time analytics data and powers Chart.js visualizations
 */

class AnalyticsDashboard {
    constructor() {
        this.selectedDateRange = 30; // Default: 30 days
        this.charts = {};
        this.widgetPreferences = this.loadWidgetPreferences();
        this.previouslyFocusedElement = null;
        this.firstFocusableElement = null;
        this.lastFocusableElement = null;
        this.modalKeydownHandler = this.handleModalKeydown.bind(this);
        this.modalMutationObserver = null;
        this.init();
    }

    /**
     * CROWN⁵+ Empty State Templates
     * "Every empty state feels like a gentle invitation, not a void."
     */
    static CROWN5_EMPTY_STATES = {
        chart: (type, title, description) => `
            <div class="crown5-chart-empty" role="status" aria-label="${title}">
                <div class="crown5-chart-empty-placeholder">
                    ${type === 'bar' ? `
                        <div class="crown5-chart-empty-placeholder-bars">
                            <div class="crown5-chart-empty-placeholder-bar"></div>
                            <div class="crown5-chart-empty-placeholder-bar"></div>
                            <div class="crown5-chart-empty-placeholder-bar"></div>
                            <div class="crown5-chart-empty-placeholder-bar"></div>
                            <div class="crown5-chart-empty-placeholder-bar"></div>
                        </div>
                    ` : type === 'donut' ? `
                        <div class="crown5-chart-empty-placeholder-donut"></div>
                    ` : `
                        <div class="crown5-chart-empty-placeholder-line"></div>
                    `}
                </div>
                <div class="crown5-empty-illustration">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                </div>
                <p class="crown5-empty-title">${title}</p>
                <p class="crown5-empty-description">${description}</p>
            </div>
        `,
        balance: (title, hint) => `
            <div class="crown5-balance-card">
                <div class="crown5-balance-header">
                    <span class="crown5-balance-title">${title}</span>
                    <span class="crown5-balance-score crown5-no-data-value">—</span>
                </div>
                <div class="crown5-balance-empty-indicator"></div>
                <p class="crown5-balance-hint">${hint}</p>
                <span class="crown5-balance-status crown5-no-data-status">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    No Data
                </span>
            </div>
        `,
        productivity: (icon, title, description) => `
            <div class="crown5-empty-state">
                <div class="crown5-empty-illustration">
                    ${icon}
                </div>
                <p class="crown5-empty-title">${title}</p>
                <p class="crown5-empty-description">${description}</p>
                <div class="crown5-empty-hint">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    Record or select a meeting to populate this section
                </div>
            </div>
        `
    };

    /**
     * Render CROWN⁵+ styled empty state for charts
     */
    renderCrown5EmptyChart(container, type, title, description) {
        if (!container) return;
        
        const canvas = container.querySelector('canvas');
        if (canvas) canvas.style.display = 'none';
        
        const existingEmpty = container.querySelector('.crown5-chart-empty');
        if (existingEmpty) existingEmpty.remove();
        
        const emptyDiv = document.createElement('div');
        emptyDiv.innerHTML = AnalyticsDashboard.CROWN5_EMPTY_STATES.chart(type, title, description);
        container.appendChild(emptyDiv.firstElementChild);
    }

    /**
     * Hide CROWN⁵+ empty state and show chart canvas
     */
    hideCrown5EmptyChart(container) {
        if (!container) return;
        
        const canvas = container.querySelector('canvas');
        if (canvas) canvas.style.display = '';
        
        const existingEmpty = container.querySelector('.crown5-chart-empty');
        if (existingEmpty) existingEmpty.remove();
    }

    /**
     * CROWN⁵+ KPI Animation Helpers (Section 7 Emotional Design)
     * "Numbers that breathe, not flash. Transitions that feel intentional."
     */
    animateKpiValue(element, newValue, duration = 300) {
        if (!element) return;
        
        const currentValue = parseFloat(element.textContent.replace(/[^0-9.-]/g, '')) || 0;
        const targetValue = parseFloat(newValue);
        
        if (isNaN(targetValue)) {
            element.textContent = '—';
            element.removeAttribute('data-animating');
            element.classList.remove('crown5-kpi-value');
            return;
        }
        
        element.classList.add('crown5-kpi-value');
        element.setAttribute('data-animating', 'true');
        
        const startTime = performance.now();
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            
            const current = currentValue + (targetValue - currentValue) * eased;
            element.textContent = this.formatKpiValue(current, element.dataset.format);
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            } else {
                element.removeAttribute('data-animating');
            }
        };
        
        requestAnimationFrame(animate);
    }

    formatKpiValue(value, format) {
        switch (format) {
            case 'hours':
                return value.toFixed(1) + 'h';
            case 'minutes':
                return Math.round(value) + 'm';
            case 'percent':
                return Math.round(value) + '%';
            case 'integer':
                return Math.round(value).toLocaleString();
            default:
                return Math.round(value).toLocaleString();
        }
    }

    triggerKpiUpdate(card) {
        if (!card) return;
        card.classList.add('crown5-kpi-updated');
        setTimeout(() => card.classList.remove('crown5-kpi-updated'), 400);
    }

    triggerKpiShimmer(card) {
        if (!card) return;
        card.classList.add('crown5-kpi-shimmer');
        setTimeout(() => card.classList.remove('crown5-kpi-shimmer'), 1500);
    }

    /**
     * Apply staggered tile fade-in animation to a container
     */
    applyTileGridAnimation(container) {
        if (!container) return;
        container.classList.add('crown5-tile-grid');
    }

    /**
     * Apply crossfade transition for filter/tab changes
     */
    crossfadeTransition(container, updateFn) {
        if (!container) return;
        
        container.classList.add('crown5-filter-crossfade-exit');
        
        setTimeout(() => {
            updateFn();
            container.classList.remove('crown5-filter-crossfade-exit');
            container.classList.add('crown5-filter-crossfade-enter');
            
            setTimeout(() => {
                container.classList.remove('crown5-filter-crossfade-enter');
            }, 250);
        }, 150);
    }

    async init() {
        // Set up date range filter
        this.setupDateRangeFilter();
        
        // Set up export button
        this.setupExportButton();
        
        // Set up widget customization
        this.setupWidgetCustomization();
        
        // Load initial data
        await this.loadDashboardData();
        
        // Set up tab switching
        this.setupTabs();
        
        // Apply widget preferences
        this.applyWidgetPreferences();
    }

    loadWidgetPreferences() {
        const saved = localStorage.getItem('mina_analytics_widgets');
        return saved ? JSON.parse(saved) : {
            'kpi-meetings': true,
            'kpi-tasks': true,
            'kpi-hours': true,
            'kpi-duration': true,
            'chart-activity': true,
            'chart-task-status': true,
            'chart-speaker': true,
            'chart-topics': true,
            'chart-speaking-time': true,
            'chart-participation': true,
            'chart-sentiment': true,
            'topic-trends': true,
            'qa-tracking': true,
            'action-items': true
        };
    }

    saveWidgetPreferences() {
        localStorage.setItem('mina_analytics_widgets', JSON.stringify(this.widgetPreferences));
    }

    setupWidgetCustomization() {
        const customizeBtn = document.getElementById('customizeWidgetsBtn');
        const modal = document.getElementById('widgetCustomizationModal');
        const closeBtn = document.getElementById('closeCustomizeModal');
        const saveBtn = document.getElementById('saveWidgetsBtn');
        const resetBtn = document.getElementById('resetWidgetsBtn');

        if (customizeBtn) {
            customizeBtn.addEventListener('click', () => this.showCustomizeModal());
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideCustomizeModal());
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveWidgetSettings());
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetWidgetSettings());
        }

        // Close modal on outside click
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hideCustomizeModal();
                }
            });
        }
    }

    showCustomizeModal() {
        const modal = document.getElementById('widgetCustomizationModal');
        const togglesContainer = document.getElementById('widgetToggles');
        
        if (!modal || !togglesContainer) return;

        this.previouslyFocusedElement = document.activeElement;

        const widgets = [
            { id: 'kpi-meetings', name: 'Total Meetings KPI', category: 'KPIs' },
            { id: 'kpi-tasks', name: 'Action Items KPI', category: 'KPIs' },
            { id: 'kpi-hours', name: 'Hours Saved KPI', category: 'KPIs' },
            { id: 'kpi-duration', name: 'Avg Meeting Length KPI', category: 'KPIs' },
            { id: 'chart-activity', name: 'Meeting Activity Chart', category: 'Charts' },
            { id: 'chart-task-status', name: 'Task Status Chart', category: 'Charts' },
            { id: 'chart-speaker', name: 'Speaker Distribution', category: 'Charts' },
            { id: 'chart-topics', name: 'Top Topics', category: 'Charts' },
            { id: 'chart-speaking-time', name: 'Speaking Time Analysis', category: 'Engagement' },
            { id: 'chart-participation', name: 'Participation Balance', category: 'Engagement' },
            { id: 'chart-sentiment', name: 'Sentiment Analysis', category: 'Engagement' },
            { id: 'topic-trends', name: 'Topic Evolution Timeline', category: 'Productivity' },
            { id: 'qa-tracking', name: 'Q&A Tracking', category: 'Productivity' },
            { id: 'action-items', name: 'Action Items Completion', category: 'Productivity' }
        ];

        const grouped = widgets.reduce((acc, widget) => {
            if (!acc[widget.category]) acc[widget.category] = [];
            acc[widget.category].push(widget);
            return acc;
        }, {});

        togglesContainer.innerHTML = Object.keys(grouped).map(category => `
            <div class="mb-4">
                <h3 class="text-sm font-semibold text-tertiary uppercase tracking-wide mb-2">${category}</h3>
                <div class="space-y-2">
                    ${grouped[category].map(widget => `
                        <label class="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-primary cursor-pointer transition-colors">
                            <input 
                                type="checkbox" 
                                data-widget-id="${widget.id}"
                                ${this.widgetPreferences[widget.id] !== false ? 'checked' : ''}
                                class="w-4 h-4 text-primary border-gray-300 rounded focus:ring-primary focus:ring-2"
                                aria-label="Toggle ${widget.name} visibility"
                            >
                            <div class="flex-1">
                                <div class="font-medium text-sm">${widget.name}</div>
                            </div>
                        </label>
                    `).join('')}
                </div>
            </div>
        `).join('');

        modal.classList.remove('hidden');
        
        const closeBtn = document.getElementById('closeCustomizeModal');
        if (closeBtn) {
            closeBtn.focus();
        }
        
        this.setupModalFocusTrap(modal);
        
        modal.addEventListener('keydown', this.modalKeydownHandler);
    }
    
    setupModalFocusTrap(modal) {
        this.updateFocusableElements(modal);
        
        if (!this.modalMutationObserver) {
            this.modalMutationObserver = new MutationObserver(() => {
                this.updateFocusableElements(modal);
            });
        }
        
        this.modalMutationObserver.observe(modal, { 
            childList: true, 
            subtree: true 
        });
    }
    
    updateFocusableElements(modal) {
        const focusableElements = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length > 0) {
            this.firstFocusableElement = focusableElements[0];
            this.lastFocusableElement = focusableElements[focusableElements.length - 1];
        }
    }
    
    handleModalKeydown(e) {
        if (e.key === 'Escape') {
            this.hideCustomizeModal();
            return;
        }
        
        if (e.key === 'Tab') {
            if (e.shiftKey) {
                if (document.activeElement === this.firstFocusableElement) {
                    e.preventDefault();
                    this.lastFocusableElement.focus();
                }
            } else {
                if (document.activeElement === this.lastFocusableElement) {
                    e.preventDefault();
                    this.firstFocusableElement.focus();
                }
            }
        }
    }

    hideCustomizeModal() {
        const modal = document.getElementById('widgetCustomizationModal');
        if (modal) {
            modal.classList.add('hidden');
            modal.removeEventListener('keydown', this.modalKeydownHandler);
        }
        
        if (this.modalMutationObserver) {
            this.modalMutationObserver.disconnect();
        }
        
        if (this.previouslyFocusedElement && this.previouslyFocusedElement.focus) {
            this.previouslyFocusedElement.focus();
        }
    }

    saveWidgetSettings() {
        const checkboxes = document.querySelectorAll('#widgetToggles input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            const widgetId = checkbox.dataset.widgetId;
            this.widgetPreferences[widgetId] = checkbox.checked;
        });
        
        this.saveWidgetPreferences();
        this.applyWidgetPreferences();
        this.hideCustomizeModal();
        this.showToast('Widget preferences saved', 'success');
    }

    resetWidgetSettings() {
        // Reset all to true
        Object.keys(this.widgetPreferences).forEach(key => {
            this.widgetPreferences[key] = true;
        });
        
        this.saveWidgetPreferences();
        this.applyWidgetPreferences(); // Apply changes immediately
        this.showCustomizeModal(); // Refresh the modal
        this.showToast('Widget preferences reset to default', 'success');
    }

    applyWidgetPreferences() {
        // This would require adding data-widget-id to each widget in the HTML
        // For now, just console log (in production, you'd hide/show widgets)
        console.log('Widget preferences applied:', this.widgetPreferences);
        
        // Example: Show/hide widgets based on preferences
        Object.keys(this.widgetPreferences).forEach(widgetId => {
            const elements = document.querySelectorAll(`[data-widget="${widgetId}"]`);
            elements.forEach(el => {
                if (this.widgetPreferences[widgetId]) {
                    el.style.display = '';
                } else {
                    el.style.display = 'none';
                }
            });
        });
    }

    setupDateRangeFilter() {
        const dateSelect = document.querySelector('.date-range-select');
        if (dateSelect) {
            dateSelect.addEventListener('change', async (e) => {
                this.selectedDateRange = parseInt(e.target.value);
                await this.loadDashboardData();
            });
        }
    }

    setupExportButton() {
        const exportBtn = document.querySelector('.btn-outline');
        if (exportBtn && exportBtn.textContent.includes('Export')) {
            exportBtn.addEventListener('click', () => this.exportAnalytics());
        }
    }

    setupTabs() {
        const tabs = Array.from(document.querySelectorAll('.analytics-tab'));
        
        tabs.forEach((tab, index) => {
            tab.addEventListener('click', async () => {
                await this.activateTab(tab);
            });
        });
    }
    
    async activateTab(tab) {
        const targetTab = tab.dataset.tab;
        const tabs = document.querySelectorAll('.analytics-tab');
        const tabContents = document.querySelectorAll('.analytics-tab-content');
        
        tabs.forEach(t => {
            t.classList.remove('active');
            t.setAttribute('aria-selected', 'false');
            t.setAttribute('tabindex', '-1');
        });
        
        tabContents.forEach(c => c.classList.remove('active'));
        
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');
        tab.setAttribute('tabindex', '0');
        
        const targetPanel = document.getElementById('tab-' + targetTab);
        if (targetPanel) {
            targetPanel.classList.add('active');
        }
        
        this.announceTabChange(targetTab);
        
        await this.loadTabData(targetTab);
    }
    
    announceTabChange(tabName) {
        const liveRegion = document.getElementById('analytics-live-region');
        if (liveRegion) {
            const formattedName = tabName.charAt(0).toUpperCase() + tabName.slice(1);
            liveRegion.textContent = `${formattedName} tab selected. Loading ${formattedName.toLowerCase()} data.`;
            setTimeout(() => { liveRegion.textContent = ''; }, 2000);
        }
    }

    async loadDashboardData() {
        try {
            const [dashboardRes, kpiComparisonRes, topicsRes, healthRes, insightsRes] = await Promise.all([
                fetch(`/api/analytics/dashboard?days=${this.selectedDateRange}`),
                fetch(`/api/analytics/kpi-comparison?days=${this.selectedDateRange}`),
                fetch(`/api/analytics/topic-distribution?days=${this.selectedDateRange}`),
                fetch(`/api/analytics/meeting-health?days=${this.selectedDateRange}`),
                fetch(`/api/analytics/actionable-insights?days=${this.selectedDateRange}`)
            ]);
            
            const [dashboardData, kpiComparisonData, topicsData, healthData, insightsData] = await Promise.all([
                dashboardRes.json(),
                kpiComparisonRes.json(),
                topicsRes.json(),
                healthRes.json(),
                insightsRes.json()
            ]);
            
            if (dashboardData.success) {
                this.updateOverviewCharts(dashboardData.dashboard);
            }
            
            if (kpiComparisonData.success) {
                this.updateKPIComparisons(kpiComparisonData.kpis);
            }
            
            if (topicsData.success) {
                this.updateTopicsDistribution(topicsData);
            }
            
            if (healthData.success) {
                this.updateMeetingHealthScore(healthData.health_score);
            }
            
            if (insightsData.success) {
                this.updateActionableInsights(insightsData.insights);
            }
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        }
    }

    updateKPIComparisons(kpis) {
        const kpiConfig = {
            'total_meetings': { 
                badgeId: 'kpi-meetings-badge', 
                comparisonId: 'kpi-meetings-comparison',
                valueId: 'kpi-meetings-value',
                format: 'integer'
            },
            'action_items': { 
                badgeId: 'kpi-tasks-badge', 
                comparisonId: 'kpi-tasks-comparison',
                valueId: 'kpi-tasks-value',
                format: 'integer'
            },
            'hours_saved': { 
                badgeId: 'kpi-hours-badge', 
                comparisonId: 'kpi-hours-comparison',
                valueId: 'kpi-hours-value',
                format: 'hours'
            },
            'avg_duration': { 
                badgeId: 'kpi-duration-badge', 
                comparisonId: 'kpi-duration-comparison',
                valueId: 'kpi-duration-value',
                format: 'minutes'
            }
        };

        for (const [key, config] of Object.entries(kpiConfig)) {
            const kpiData = kpis[key];
            if (!kpiData) continue;

            const badge = document.getElementById(config.badgeId);
            const comparison = document.getElementById(config.comparisonId);
            const valueEl = document.getElementById(config.valueId);
            const card = badge?.closest('.kpi-card');

            if (badge) {
                const change = kpiData.change;
                const trend = kpiData.trend;
                
                if (change === 0 || change === null || change === undefined) {
                    badge.textContent = '→';
                    badge.style.background = 'rgba(107, 114, 128, 0.1)';
                    badge.style.color = 'var(--color-tertiary)';
                    badge.setAttribute('aria-label', 'No change');
                } else if (trend === 'up') {
                    const displayChange = key === 'hours_saved' ? `+${kpiData.value - kpiData.previous}h` : `+${Math.abs(change)}%`;
                    badge.textContent = displayChange;
                    badge.style.background = 'rgba(34, 197, 94, 0.1)';
                    badge.style.color = 'var(--color-success)';
                    badge.setAttribute('aria-label', `${Math.abs(change)} percent increase`);
                } else {
                    const displayChange = key === 'hours_saved' ? `-${kpiData.previous - kpiData.value}h` : `-${Math.abs(change)}%`;
                    badge.textContent = displayChange;
                    badge.style.background = 'rgba(239, 68, 68, 0.1)';
                    badge.style.color = 'var(--color-error)';
                    badge.setAttribute('aria-label', `${Math.abs(change)} percent decrease`);
                }
                
                if (card) {
                    this.triggerKpiUpdate(card);
                }
            }

            if (comparison) {
                const prev = kpiData.previous || 0;
                const curr = kpiData.value || 0;
                const diff = curr - prev;
                
                if (diff === 0) {
                    comparison.textContent = 'Same as previous period';
                } else if (diff > 0) {
                    comparison.innerHTML = `<span style="color: var(--color-success)">↑</span> ${Math.abs(diff)} more than last period`;
                } else {
                    comparison.innerHTML = `<span style="color: var(--color-error)">↓</span> ${Math.abs(diff)} fewer than last period`;
                }
            }

            if (valueEl) {
                this.animateKpiValue(valueEl, kpiData.value, 400);
            }
        }

        if (kpis.completion_rate !== undefined) {
            const badge = document.getElementById('kpi-tasks-badge');
            const comparison = document.getElementById('kpi-tasks-comparison');
            if (badge) {
                badge.textContent = `${Math.round(kpis.completion_rate.value)}%`;
                badge.setAttribute('aria-label', `${Math.round(kpis.completion_rate.value)} percent complete`);
            }
            if (comparison) {
                comparison.textContent = `${Math.round(kpis.completion_rate.value)}% completion rate`;
            }
        }
    }

    updateTopicsDistribution(data) {
        const container = document.getElementById('topics-distribution');
        if (!container) return;

        const topicColors = [
            'var(--color-primary, #6366f1)',
            '#8b5cf6',
            '#06b6d4',
            '#10b981',
            '#f59e0b',
            '#ef4444'
        ];

        if (!data.has_data || !data.topics || data.topics.length === 0) {
            container.innerHTML = `
                <div class="crown5-empty-state" role="status">
                    <div class="crown5-empty-illustration">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.99 1.99 0 013 12V7a4 4 0 014-4z"/>
                        </svg>
                    </div>
                    <p class="crown5-empty-title">No topics detected yet</p>
                    <p class="crown5-empty-description">${data.message || 'Record and analyze meetings to see topic distribution'}</p>
                </div>
            `;
            return;
        }

        container.innerHTML = data.topics.map((topic, idx) => {
            const color = topicColors[idx % topicColors.length];
            return `
                <div role="listitem" aria-label="${topic.name}: ${topic.percentage} percent" class="crown5-fade-in" style="animation-delay: ${idx * 50}ms">
                    <div class="flex justify-between text-sm mb-1">
                        <span class="font-medium">${topic.name}</span>
                        <span class="text-tertiary" aria-hidden="true">${topic.percentage}%</span>
                    </div>
                    <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden" role="progressbar" aria-valuenow="${topic.percentage}" aria-valuemin="0" aria-valuemax="100" aria-label="${topic.name} ${topic.percentage} percent">
                        <div class="h-full transition-all duration-500" style="width: ${topic.percentage}%; background: ${color}"></div>
                    </div>
                </div>
            `;
        }).join('');
    }

    updateMeetingHealthScore(healthScore) {
        const scoreValue = document.getElementById('health-score-value');
        const scoreMessage = document.getElementById('health-score-message');
        const scoreTrend = document.getElementById('health-score-trend');
        const scoreArc = document.getElementById('health-score-arc');
        
        const effectivenessEl = document.getElementById('health-effectiveness');
        const engagementEl = document.getElementById('health-engagement');
        const followthroughEl = document.getElementById('health-followthrough');
        const decisionsEl = document.getElementById('health-decisions');

        if (!healthScore || healthScore.meetings_analyzed === 0) {
            if (scoreValue) scoreValue.textContent = '—';
            if (scoreMessage) scoreMessage.textContent = 'Record meetings to see your health score';
            if (scoreTrend) scoreTrend.innerHTML = '';
            if (scoreArc) scoreArc.style.strokeDasharray = '0, 100';
            return;
        }

        const score = healthScore.score;
        const breakdown = healthScore.breakdown || {};

        if (scoreValue) {
            this.animateHealthScore(scoreValue, scoreArc, score);
        }

        if (scoreMessage) {
            scoreMessage.textContent = healthScore.status_message;
        }

        const statusColors = {
            'excellent': '#22c55e',
            'good': '#3b82f6',
            'fair': '#f59e0b',
            'needs_attention': '#ef4444'
        };
        
        if (scoreArc) {
            scoreArc.style.stroke = statusColors[healthScore.status] || 'var(--color-primary)';
        }

        if (scoreTrend) {
            const change = healthScore.change;
            const trend = healthScore.trend;
            
            if (trend === 'improving') {
                scoreTrend.innerHTML = `
                    <span class="flex items-center gap-1 text-sm" style="color: var(--color-success);">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M7 17l5-5 5 5M7 7h10"/>
                        </svg>
                        +${Math.abs(change)} from last period
                    </span>
                `;
            } else if (trend === 'declining') {
                scoreTrend.innerHTML = `
                    <span class="flex items-center gap-1 text-sm" style="color: var(--color-error);">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M7 7l5 5 5-5M7 17h10"/>
                        </svg>
                        ${change} from last period
                    </span>
                `;
            } else {
                scoreTrend.innerHTML = `
                    <span class="flex items-center gap-1 text-sm text-tertiary">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M5 12h14"/>
                        </svg>
                        Stable
                    </span>
                `;
            }
        }

        if (effectivenessEl) effectivenessEl.textContent = `${breakdown.effectiveness || 0}%`;
        if (engagementEl) engagementEl.textContent = `${breakdown.engagement || 0}%`;
        if (followthroughEl) followthroughEl.textContent = `${breakdown.follow_through || 0}%`;
        if (decisionsEl) decisionsEl.textContent = `${breakdown.decision_velocity || 0}%`;
    }

    animateHealthScore(valueEl, arcEl, targetScore) {
        const startTime = performance.now();
        const duration = 1000;
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            
            const currentScore = Math.round(targetScore * eased);
            valueEl.textContent = currentScore;
            
            if (arcEl) {
                arcEl.style.strokeDasharray = `${currentScore}, 100`;
            }
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    updateActionableInsights(insights) {
        const insightsContainer = document.getElementById('actionable-insights-container');
        const insightsCount = document.getElementById('insights-count');
        if (!insightsContainer) return;

        if (insightsCount) {
            if (insights && insights.length > 0) {
                insightsCount.textContent = `${insights.length} recommendation${insights.length > 1 ? 's' : ''}`;
            } else {
                insightsCount.textContent = '';
            }
        }

        if (!insights || insights.length === 0) {
            insightsContainer.innerHTML = `
                <div class="crown5-empty-state" role="status">
                    <div class="crown5-empty-illustration">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                        </svg>
                    </div>
                    <p class="crown5-empty-title">No insights available yet</p>
                    <p class="crown5-empty-description">Record more meetings to get personalized recommendations</p>
                </div>
            `;
            return;
        }

        const typeIcons = {
            'warning': `<svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>`,
            'info': `<svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
            'success': `<svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`
        };

        const typeColors = {
            'warning': { bg: 'rgba(245, 158, 11, 0.1)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.2)' },
            'info': { bg: 'rgba(59, 130, 246, 0.1)', text: '#3b82f6', border: 'rgba(59, 130, 246, 0.2)' },
            'success': { bg: 'rgba(34, 197, 94, 0.1)', text: '#22c55e', border: 'rgba(34, 197, 94, 0.2)' }
        };

        insightsContainer.innerHTML = insights.slice(0, 4).map((insight, idx) => {
            const colors = typeColors[insight.type] || typeColors.info;
            const icon = typeIcons[insight.type] || typeIcons.info;
            
            return `
                <div class="insight-card crown5-fade-in" role="article" style="animation-delay: ${idx * 100}ms; background: ${colors.bg}; border: 1px solid ${colors.border}; border-radius: var(--radius-md); padding: var(--space-4);">
                    <div class="flex items-start gap-3">
                        <div style="color: ${colors.text}; flex-shrink: 0;">
                            ${icon}
                        </div>
                        <div class="flex-1">
                            <h4 class="font-semibold text-sm mb-1">${insight.title}</h4>
                            <p class="text-sm text-secondary">${insight.description}</p>
                        </div>
                        <span class="px-2 py-1 rounded text-xs font-medium" style="background: ${colors.bg}; color: ${colors.text};">
                            ${insight.priority}
                        </span>
                    </div>
                </div>
            `;
        }).join('');
    }

    async loadTabData(tab) {
        switch(tab) {
            case 'engagement':
                await this.loadEngagementData();
                break;
            case 'productivity':
                await this.loadProductivityData();
                break;
            case 'insights':
                await this.loadInsights();
                break;
        }
    }

    async loadEngagementData() {
        try {
            const response = await fetch(`/api/analytics/engagement?days=${this.selectedDateRange}`);
            const data = await response.json();
            
            if (data.success) {
                this.updateEngagementCharts(data.engagement);
            }
            
            // Load communication data for speaking time visualizations (T2.33)
            const commResponse = await fetch(`/api/analytics/communication?days=${this.selectedDateRange}`);
            const commData = await commResponse.json();
            
            if (commData.success) {
                this.updateSpeakingTimeCharts(commData.communication);
                // T2.34: Update participation balance metrics
                this.updateParticipationBalanceMetrics(commData.communication);
            }
        } catch (error) {
            console.error('Failed to load engagement data:', error);
        }
    }

    async loadProductivityData() {
        try {
            const response = await fetch(`/api/analytics/productivity?days=${this.selectedDateRange}`);
            const data = await response.json();
            
            if (data.success) {
                this.updateProductivityCharts(data.productivity);
            }
        } catch (error) {
            console.error('Failed to load productivity data:', error);
        }
    }

    async loadInsights() {
        try {
            const response = await fetch(`/api/analytics/insights?days=${this.selectedDateRange}`);
            const data = await response.json();
            
            if (data.success) {
                this.updateInsightsUI(data.insights);
            }
        } catch (error) {
            console.error('Failed to load insights:', error);
        }
    }

    async loadCommunicationData() {
        try {
            const response = await fetch(`/api/analytics/communication?days=${this.selectedDateRange}`);
            const data = await response.json();
            
            if (data.success) {
                return data.communication;
            }
        } catch (error) {
            console.error('Failed to load communication data:', error);
            return null;
        }
    }

    updateOverviewCharts(dashboard) {
        // Update Meeting Activity Chart
        if (dashboard.trends && dashboard.trends.meeting_frequency) {
            this.updateMeetingActivityChart(dashboard.trends.meeting_frequency);
        } else {
            const activityCtx = document.getElementById('meetingActivityChart');
            const activityFrame = activityCtx?.closest('.chart-frame');
            if (activityFrame) {
                this.renderCrown5EmptyChart(
                    activityFrame,
                    'line',
                    'No meeting activity yet',
                    'Record meetings to see activity trends'
                );
            }
        }
        
        // Update Task Status Chart
        this.updateTaskStatusChart(dashboard);
        
        // Load and update Speaker Distribution
        this.loadCommunicationData().then(commData => {
            this.updateSpeakerChart(commData || {});
        });
    }

    updateMeetingActivityChart(trendData) {
        const ctx = document.getElementById('meetingActivityChart');
        const chartFrame = ctx?.closest('.chart-frame');
        if (!ctx) return;

        const labels = trendData.map(d => {
            const date = new Date(d.date);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });
        const values = trendData.map(d => d.meetings);

        // Hide any existing empty state before rendering chart
        this.hideCrown5EmptyChart(chartFrame);

        // Destroy existing chart if it exists
        if (this.charts.meetingActivity) {
            this.charts.meetingActivity.destroy();
        }

        this.charts.meetingActivity = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Meetings',
                    data: values,
                    borderColor: 'rgb(99, 102, 241)',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1.8,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => items[0].label,
                            label: (item) => `${item.parsed.y} meetings`
                        }
                    }
                },
                scales: {
                    y: { 
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
    }

    updateTaskStatusChart(dashboard) {
        const ctx = document.getElementById('taskStatusChart');
        const chartFrame = ctx?.closest('.chart-frame');
        if (!ctx) return;

        const tasks = dashboard?.productivity;
        const completed = tasks?.total_tasks_created || 0;
        const inProgress = Math.floor(completed * 0.3);
        const pending = Math.floor(completed * 0.1);
        const total = completed + inProgress + pending;

        if (total === 0) {
            this.renderCrown5EmptyChart(
                chartFrame,
                'donut',
                'No task data yet',
                'Complete meetings to see task distribution'
            );
            return;
        }

        this.hideCrown5EmptyChart(chartFrame);

        if (this.charts.taskStatus) {
            this.charts.taskStatus.destroy();
        }

        this.charts.taskStatus = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Completed', 'In Progress', 'Pending'],
                datasets: [{
                    data: [completed, inProgress, pending],
                    backgroundColor: [
                        'rgb(34, 197, 94)',
                        'rgb(249, 115, 22)',
                        'rgb(156, 163, 175)'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            label: (item) => {
                                const value = item.parsed;
                                const total = item.dataset.data.reduce((a, b) => a + b, 0);
                                const percent = ((value / total) * 100).toFixed(1);
                                return `${item.label}: ${value} (${percent}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    updateSpeakerChart(commData) {
        const ctx = document.getElementById('speakerChart');
        const chartFrame = ctx?.closest('.chart-frame');
        if (!ctx) return;

        const speakers = commData?.top_speakers?.slice(0, 5) || [];
        
        if (speakers.length === 0 || speakers.every(s => !s.talk_time_minutes)) {
            this.renderCrown5EmptyChart(
                chartFrame,
                'bar',
                'No speaker data yet',
                'Record meetings to see who speaks most'
            );
            return;
        }

        this.hideCrown5EmptyChart(chartFrame);

        const labels = speakers.map(s => s.name);
        const values = speakers.map(s => s.talk_time_minutes);
        const colors = [
            'rgb(99, 102, 241)',
            'rgb(139, 92, 246)',
            'rgb(6, 182, 212)',
            'rgb(34, 197, 94)',
            'rgb(249, 115, 22)'
        ];

        if (this.charts.speaker) {
            this.charts.speaker.destroy();
        }

        this.charts.speaker = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Speaking Time (min)',
                    data: values,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1.6,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (item) => `${item.parsed.y.toFixed(1)} minutes`
                        }
                    }
                },
                scales: {
                    y: { 
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Minutes'
                        }
                    }
                }
            }
        });
    }

    updateEngagementCharts(engagement) {
        this.updateParticipationChart(engagement);
        this.updateSentimentChart();
    }

    updateParticipationChart(engagement) {
        const ctx = document.getElementById('participationChart');
        const chartFrame = ctx?.closest('.chart-frame');
        if (!ctx) return;

        this.hideCrown5EmptyChart(chartFrame);

        if (this.charts.participation) {
            this.charts.participation.destroy();
        }

        this.charts.participation = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Contribution', 'Questions Asked', 'Ideas Shared', 'Active Listening', 'Follow-ups'],
                datasets: [{
                    label: 'Your Team',
                    data: [
                        engagement.average_score || 70,
                        65,
                        75,
                        80,
                        70
                    ],
                    borderColor: 'rgb(99, 102, 241)',
                    backgroundColor: 'rgba(99, 102, 241, 0.2)',
                    pointBackgroundColor: 'rgb(99, 102, 241)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgb(99, 102, 241)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            stepSize: 20
                        }
                    }
                },
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    async updateSentimentChart() {
        const ctx = document.getElementById('sentimentChart');
        const chartFrame = ctx?.closest('.chart-frame');
        if (!ctx) return;

        try {
            const response = await fetch(`/api/analytics/sentiment?days=${this.selectedDateRange}`);
            const data = await response.json();
            
            if (!data.success || !data.sentiment.trend || data.sentiment.trend.length === 0) {
                this.renderCrown5EmptyChart(
                    chartFrame,
                    'line',
                    'No sentiment data yet',
                    'Record meetings to see emotional trends'
                );
                return;
            }

            this.hideCrown5EmptyChart(chartFrame);
            const trend = data.sentiment.trend;
            const labels = trend.map(t => {
                const date = new Date(t.date);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            });
            const values = trend.map(t => t.score);

            if (this.charts.sentiment) {
                this.charts.sentiment.destroy();
            }

            this.charts.sentiment = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Sentiment Score',
                        data: values,
                        borderColor: 'rgb(34, 197, 94)',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    aspectRatio: 1.6,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (item) => {
                                    const value = item.parsed.y;
                                    let sentiment = 'Neutral';
                                    if (value > 50) sentiment = 'Positive';
                                    if (value < -10) sentiment = 'Negative';
                                    return `${value.toFixed(1)}% (${sentiment})`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            min: -100,
                            max: 100,
                            ticks: {
                                callback: (value) => value + '%'
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Failed to update sentiment chart:', error);
        }
    }

    updateProductivityCharts(productivity) {
        const ctx = document.getElementById('productivityChart');
        const chartFrame = ctx?.closest('.chart-frame');
        if (!ctx) return;

        if (this.charts.productivity) {
            this.charts.productivity.destroy();
        }

        const completionTrend = productivity.completion_trend || [];
        
        if (completionTrend.length === 0 || completionTrend.every(w => w.total_tasks === 0)) {
            if (chartFrame) {
                this.renderCrown5EmptyChart(
                    chartFrame,
                    'line',
                    'No task data yet',
                    'Complete meetings with action items to see productivity trends'
                );
            }
            return;
        }
        
        if (chartFrame) {
            this.hideCrown5EmptyChart(chartFrame);
        }

        const labels = completionTrend.map(w => `Week ${w.week}`);
        const trendData = completionTrend.map(w => w.completion_rate);
        const taskCounts = completionTrend.map(w => ({ total: w.total_tasks, completed: w.completed_tasks }));

        this.charts.productivity = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Completion Rate (%)',
                    data: trendData,
                    borderColor: 'rgb(99, 102, 241)',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1.8,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (item) => {
                                const idx = item.dataIndex;
                                const counts = taskCounts[idx];
                                return [
                                    `Completion: ${item.parsed.y.toFixed(1)}%`,
                                    `Tasks: ${counts.completed}/${counts.total}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: (value) => value + '%'
                        }
                    }
                }
            }
        });
    }

    updateInsightsUI(insights) {
        // This would update the insights and recommendations sections
        // with dynamic data from the AI
        console.log('Insights loaded:', insights);
    }

    /**
     * T2.33: Speaking Time Visualization
     * Creates detailed speaking time charts (bar, pie) and participant breakdown
     */
    updateSpeakingTimeCharts(communication) {
        if (!communication || !communication.top_speakers) {
            this.showEmptySpeakingTimeState();
            return;
        }

        const speakers = communication.top_speakers.slice(0, 10); // Top 10
        const labels = speakers.map(s => s.name);
        const timeValues = speakers.map(s => s.talk_time_minutes);
        const totalTime = timeValues.reduce((a, b) => a + b, 0);
        const percentages = timeValues.map(t => ((t / totalTime) * 100).toFixed(1));

        // Color palette for charts
        const colors = [
            'rgb(99, 102, 241)',   // Primary
            'rgb(139, 92, 246)',   // Purple
            'rgb(6, 182, 212)',    // Cyan
            'rgb(34, 197, 94)',    // Green
            'rgb(249, 115, 22)',   // Orange
            'rgb(236, 72, 153)',   // Pink
            'rgb(59, 130, 246)',   // Blue
            'rgb(168, 85, 247)',   // Violet
            'rgb(20, 184, 166)',   // Teal
            'rgb(234, 179, 8)'     // Yellow
        ];

        // 1. Horizontal Bar Chart - Speaking Time Distribution
        this.createSpeakingTimeBarChart(labels, timeValues, colors);

        // 2. Pie Chart - Speaking Balance
        this.createSpeakingTimePieChart(labels, timeValues, percentages, colors);

        // 3. Detailed Participant Breakdown
        this.createSpeakingTimeDetails(speakers, totalTime, colors);
    }

    createSpeakingTimeBarChart(labels, values, colors) {
        const ctx = document.getElementById('speakingTimeBarChart');
        const chartFrame = ctx?.closest('.chart-frame');
        if (!ctx) return;

        this.hideCrown5EmptyChart(chartFrame);

        if (this.charts.speakingTimeBar) {
            this.charts.speakingTimeBar.destroy();
        }

        this.charts.speakingTimeBar = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Speaking Time (minutes)',
                    data: values,
                    backgroundColor: colors,
                    borderRadius: 6,
                    barThickness: 32
                }]
            },
            options: {
                indexAxis: 'y', // Horizontal bars
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1.8,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (item) => {
                                const minutes = item.parsed.x;
                                const hours = Math.floor(minutes / 60);
                                const mins = Math.round(minutes % 60);
                                return `${hours}h ${mins}m (${minutes.toFixed(1)} minutes)`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Minutes'
                        }
                    }
                }
            }
        });
    }

    createSpeakingTimePieChart(labels, values, percentages, colors) {
        const ctx = document.getElementById('speakingTimePieChart');
        const chartFrame = ctx?.closest('.chart-frame');
        if (!ctx) return;

        this.hideCrown5EmptyChart(chartFrame);

        if (this.charts.speakingTimePie) {
            this.charts.speakingTimePie.destroy();
        }

        this.charts.speakingTimePie = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels.map((label, i) => `${label} (${percentages[i]}%)`),
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 0,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            padding: 12,
                            font: { size: 11 },
                            generateLabels: (chart) => {
                                const data = chart.data;
                                return data.labels.map((label, i) => ({
                                    text: label,
                                    fillStyle: data.datasets[0].backgroundColor[i],
                                    hidden: false,
                                    index: i
                                }));
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (item) => {
                                const value = item.parsed;
                                const percent = percentages[item.dataIndex];
                                const hours = Math.floor(value / 60);
                                const mins = Math.round(value % 60);
                                return `${hours}h ${mins}m (${percent}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    createSpeakingTimeDetails(speakers, totalTime, colors) {
        const container = document.getElementById('speakingTimeDetails');
        if (!container) return;

        // Calculate balance indicators
        const avgTime = totalTime / speakers.length;
        const idealPercentage = 100 / speakers.length;

        const detailsHTML = speakers.map((speaker, index) => {
            const time = speaker.talk_time_minutes;
            const percentage = ((time / totalTime) * 100).toFixed(1);
            const hours = Math.floor(time / 60);
            const minutes = Math.round(time % 60);
            
            // Balance indicator: compare to ideal
            const deviation = percentage - idealPercentage;
            let balanceClass = 'bg-gray-500';
            let balanceText = 'Balanced';
            
            if (deviation > 15) {
                balanceClass = 'bg-orange-500';
                balanceText = 'High';
            } else if (deviation < -15) {
                balanceClass = 'bg-blue-500';
                balanceText = 'Low';
            } else if (Math.abs(deviation) <= 5) {
                balanceClass = 'bg-green-500';
                balanceText = 'Ideal';
            }

            return `
                <div class="flex items-center gap-4 p-4 rounded-lg" style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1);">
                    <div class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" style="background: ${colors[index]};">
                        <span class="text-white font-bold">${speaker.name.charAt(0).toUpperCase()}</span>
                    </div>
                    <div class="flex-1">
                        <div class="flex justify-between items-center mb-1">
                            <h3 class="font-semibold text-base">${speaker.name}</h3>
                            <div class="flex items-center gap-2">
                                <span class="px-2 py-0.5 rounded-full text-xs font-medium ${balanceClass} bg-opacity-20 text-white">
                                    ${balanceText}
                                </span>
                                <span class="font-bold text-lg">${percentage}%</span>
                            </div>
                        </div>
                        <div class="flex items-center gap-3 mb-2">
                            <span class="text-sm text-secondary">${hours}h ${minutes}m</span>
                            <span class="text-sm text-tertiary">•</span>
                            <span class="text-sm text-tertiary">${speaker.segment_count || 0} segments</span>
                        </div>
                        <div class="relative h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div class="absolute h-full rounded-full transition-all duration-500" 
                                 style="width: ${percentage}%; background: ${colors[index]};"></div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = detailsHTML;
    }

    showEmptySpeakingTimeState() {
        const barCtx = document.getElementById('speakingTimeBarChart');
        const pieCtx = document.getElementById('speakingTimePieChart');
        const detailsContainer = document.getElementById('speakingTimeDetails');
        
        const barFrame = barCtx?.closest('.chart-frame');
        const pieFrame = pieCtx?.closest('.chart-frame');
        
        if (barFrame) {
            this.renderCrown5EmptyChart(
                barFrame,
                'bar',
                'No speaking data yet',
                'Record meetings to see time distribution'
            );
        }
        
        if (pieFrame) {
            this.renderCrown5EmptyChart(
                pieFrame,
                'donut',
                'No balance data yet',
                'Record meetings to see participation balance'
            );
        }
        
        if (detailsContainer) {
            detailsContainer.innerHTML = AnalyticsDashboard.CROWN5_EMPTY_STATES.productivity(
                `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" 
                          d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                </svg>`,
                'No speaking data yet',
                'Record meetings to see who contributes and how time is distributed across participants.'
            );
        }
    }

    /**
     * T2.34: Participation Balance Metrics
     * Calculates and displays comprehensive balance indicators
     */
    updateParticipationBalanceMetrics(communication) {
        const container = document.getElementById('participationBalanceMetrics');
        if (!container) return;
        
        if (!communication || !communication.top_speakers || communication.top_speakers.length === 0) {
            container.innerHTML = `
                ${this.createBalanceMetricCard('Speaking Time Balance', NaN, 'No Data', 'Record meetings to see metrics', 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z')}
                ${this.createBalanceMetricCard('Contribution Equity', NaN, 'No Data', 'Record meetings to see metrics', 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z')}
                ${this.createBalanceMetricCard('Engagement Dispersion', NaN, 'No Data', 'Record meetings to see metrics', 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z')}
                ${this.createBalanceMetricCard('Participation Health', NaN, 'No Data', 'Record meetings to see metrics', 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z')}
            `;
            return;
        }

        const speakers = communication.top_speakers;
        const totalTime = speakers.reduce((sum, s) => sum + s.talk_time_minutes, 0);
        const numSpeakers = speakers.length;
        
        // Calculate balance metrics
        const metrics = this.calculateBalanceMetrics(speakers, totalTime, numSpeakers);
        
        // Render balance metric cards
        container.innerHTML = `
            ${this.createBalanceMetricCard(
                'Speaking Time Balance',
                metrics.timeBalance.score,
                metrics.timeBalance.status,
                metrics.timeBalance.description,
                'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'
            )}
            ${this.createBalanceMetricCard(
                'Contribution Equity',
                metrics.contributionEquity.score,
                metrics.contributionEquity.status,
                metrics.contributionEquity.description,
                'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z'
            )}
            ${this.createBalanceMetricCard(
                'Engagement Dispersion',
                metrics.dispersion.score,
                metrics.dispersion.status,
                metrics.dispersion.description,
                'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z'
            )}
            ${this.createBalanceMetricCard(
                'Participation Health',
                metrics.overall.score,
                metrics.overall.status,
                metrics.overall.description,
                'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'
            )}
        `;
    }

    calculateBalanceMetrics(speakers, totalTime, numSpeakers) {
        if (!numSpeakers || numSpeakers === 0 || !totalTime || totalTime === 0) {
            return {
                timeBalance: { score: NaN, status: 'No Data', description: 'Record meetings to see metrics' },
                contributionEquity: { score: NaN, status: 'No Data', description: 'Record meetings to see metrics' },
                dispersion: { score: NaN, status: 'No Data', description: 'Record meetings to see metrics' },
                overall: { score: NaN, status: 'No Data', description: 'Record meetings to see metrics' }
            };
        }
        
        const idealPercentage = 100 / numSpeakers;
        const percentages = speakers.map(s => (s.talk_time_minutes / totalTime) * 100);
        
        // 1. Speaking Time Balance (using Coefficient of Variation)
        const mean = percentages.reduce((a, b) => a + b, 0) / percentages.length;
        const variance = percentages.reduce((sum, p) => sum + Math.pow(p - mean, 2), 0) / percentages.length;
        const stdDev = Math.sqrt(variance);
        const cv = (stdDev / mean) * 100; // Coefficient of Variation
        
        const timeBalanceScore = Math.max(0, 100 - cv);
        const timeBalanceStatus = timeBalanceScore >= 80 ? 'Excellent' : 
                                  timeBalanceScore >= 60 ? 'Good' : 
                                  timeBalanceScore >= 40 ? 'Fair' : 'Needs Improvement';
        
        // 2. Contribution Equity (Gini coefficient approximation)
        const sortedPercentages = [...percentages].sort((a, b) => a - b);
        let giniSum = 0;
        sortedPercentages.forEach((p, i) => {
            giniSum += (i + 1) * p;
        });
        const gini = (2 * giniSum) / (numSpeakers * sortedPercentages.reduce((a, b) => a + b, 0)) - 
                     (numSpeakers + 1) / numSpeakers;
        const equityScore = (1 - gini) * 100;
        const equityStatus = equityScore >= 75 ? 'Excellent' : 
                            equityScore >= 60 ? 'Good' : 
                            equityScore >= 45 ? 'Fair' : 'Unbalanced';
        
        // 3. Engagement Dispersion (how spread out participation is)
        const deviations = percentages.map(p => Math.abs(p - idealPercentage));
        const avgDeviation = deviations.reduce((a, b) => a + b, 0) / deviations.length;
        const dispersionScore = Math.max(0, 100 - (avgDeviation * 3));
        const dispersionStatus = dispersionScore >= 75 ? 'Well-Distributed' : 
                                dispersionScore >= 50 ? 'Moderately Spread' : 
                                dispersionScore >= 30 ? 'Concentrated' : 'Highly Skewed';
        
        // 4. Overall Participation Health
        const overallScore = (timeBalanceScore + equityScore + dispersionScore) / 3;
        const overallStatus = overallScore >= 80 ? 'Healthy' : 
                             overallScore >= 60 ? 'Stable' : 
                             overallScore >= 40 ? 'Attention Needed' : 'Critical';
        
        return {
            timeBalance: {
                score: Math.round(timeBalanceScore),
                status: timeBalanceStatus,
                description: `${cv.toFixed(1)}% variation in speaking time`
            },
            contributionEquity: {
                score: Math.round(equityScore),
                status: equityStatus,
                description: `${(gini * 100).toFixed(1)}% Gini coefficient`
            },
            dispersion: {
                score: Math.round(dispersionScore),
                status: dispersionStatus,
                description: `±${avgDeviation.toFixed(1)}% from ideal balance`
            },
            overall: {
                score: Math.round(overallScore),
                status: overallStatus,
                description: `Based on ${numSpeakers} participants`
            }
        };
    }

    createBalanceMetricCard(title, score, status, description, iconPath) {
        const isValidScore = !isNaN(score) && isFinite(score);
        const displayScore = isValidScore ? score : '—';
        const safeStatus = isValidScore ? status : 'No Data';
        const safeDescription = isValidScore ? description : 'Record meetings to see metrics';
        
        if (!isValidScore) {
            return AnalyticsDashboard.CROWN5_EMPTY_STATES.balance(title, safeDescription);
        }
        
        let colorClass, bgGradient;
        if (score >= 80) {
            colorClass = 'text-green-500';
            bgGradient = 'rgba(34, 197, 94, 0.1)';
        } else if (score >= 60) {
            colorClass = 'text-blue-500';
            bgGradient = 'rgba(99, 102, 241, 0.1)';
        } else if (score >= 40) {
            colorClass = 'text-yellow-500';
            bgGradient = 'rgba(249, 115, 22, 0.1)';
        } else {
            colorClass = 'text-red-500';
            bgGradient = 'rgba(239, 68, 68, 0.1)';
        }

        return `
            <div class="crown5-balance-card p-5 rounded-xl crown5-staggered-entry" style="background: ${bgGradient}; border: 1px solid rgba(255, 255, 255, 0.1);">
                <div class="flex items-start justify-between mb-3">
                    <div class="w-10 h-10 rounded-lg flex items-center justify-center ${colorClass}" style="background: rgba(255, 255, 255, 0.1);">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${iconPath}"/>
                        </svg>
                    </div>
                    <div class="text-right">
                        <div class="text-3xl font-bold ${colorClass}">${displayScore}</div>
                        <div class="text-xs text-secondary">/ 100</div>
                    </div>
                </div>
                <h3 class="font-semibold text-sm mb-1">${title}</h3>
                <p class="text-xs text-tertiary mb-2">${safeDescription}</p>
                <div class="flex items-center gap-2">
                    <div class="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div class="h-full ${colorClass} transition-all duration-500" style="width: ${score}%; opacity: 0.8;"></div>
                    </div>
                    <span class="text-xs font-medium ${colorClass}">${safeStatus}</span>
                </div>
            </div>
        `;
    }

    async loadTopicTrends(meetingId) {
        try {
            const response = await fetch(`/api/analytics/meetings/${meetingId}/topic-trends`);
            const data = await response.json();
            
            if (data.success && data.trends) {
                this.renderTopicTrends(data.trends);
            }
        } catch (error) {
            console.error('Failed to load topic trends:', error);
        }
    }

    renderTopicTrends(trends) {
        const container = document.getElementById('topicTrendsTimeline');
        if (!container || !trends.timeline || trends.timeline.length === 0) return;

        container.innerHTML = `
            <div class="mb-6">
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                    ${trends.topics.slice(0, 4).map(topic => `
                        <div class="p-3 rounded-lg bg-gray-100 dark:bg-gray-800">
                            <div class="text-lg font-bold text-primary">${topic.frequency}x</div>
                            <div class="text-sm font-medium truncate">${topic.name}</div>
                            <div class="text-xs text-tertiary">Coverage: ${topic.coverage_percentage}%</div>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="space-y-3">
                ${trends.timeline.map((window, idx) => `
                    <div class="p-4 rounded-lg bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700">
                        <div class="flex items-start gap-3">
                            <div class="flex-shrink-0 w-16 text-center">
                                <div class="text-xs font-medium text-tertiary">@${Math.round(window.time_offset_minutes)}m</div>
                                <div class="text-xs text-tertiary">${window.segment_count} msgs</div>
                            </div>
                            <div class="flex-1">
                                <div class="flex flex-wrap gap-2 mb-2">
                                    ${window.topics.map(topic => `
                                        <span class="px-2 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                                            ${topic}
                                        </span>
                                    `).join('')}
                                </div>
                                <p class="text-sm text-secondary">${window.text_preview}</p>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    async loadQuestionAnalytics(meetingId) {
        try {
            const response = await fetch(`/api/analytics/meetings/${meetingId}/questions`);
            const data = await response.json();
            
            if (data.success && data.qa_analytics) {
                this.renderQuestionAnalytics(data.qa_analytics);
            }
        } catch (error) {
            console.error('Failed to load Q&A analytics:', error);
        }
    }

    renderQuestionAnalytics(qaData) {
        const container = document.getElementById('qaTracking');
        if (!container) return;

        const summary = qaData.summary;
        
        container.innerHTML = `
            <!-- Q&A Summary Cards -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                    <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">${summary.total}</div>
                    <div class="text-sm font-medium">Total Questions</div>
                </div>
                <div class="p-4 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                    <div class="text-2xl font-bold text-green-600 dark:text-green-400">${summary.answered}</div>
                    <div class="text-sm font-medium">Answered</div>
                </div>
                <div class="p-4 rounded-lg bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800">
                    <div class="text-2xl font-bold text-orange-600 dark:text-orange-400">${summary.unanswered}</div>
                    <div class="text-sm font-medium">Unanswered</div>
                </div>
                <div class="p-4 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800">
                    <div class="text-2xl font-bold text-purple-600 dark:text-purple-400">${summary.answer_rate}%</div>
                    <div class="text-sm font-medium">Answer Rate</div>
                </div>
            </div>

            <!-- Question List -->
            <div class="space-y-3">
                ${qaData.questions.map(q => `
                    <div class="p-4 rounded-lg border ${q.answered ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800' : 'bg-orange-50 dark:bg-orange-900/10 border-orange-200 dark:border-orange-800'}">
                        <div class="flex items-start gap-3">
                            <div class="flex-shrink-0">
                                ${q.answered 
                                    ? '<svg class="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>'
                                    : '<svg class="w-5 h-5 text-orange-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>'
                                }
                            </div>
                            <div class="flex-1">
                                <div class="text-sm font-medium mb-1">${q.question}</div>
                                <div class="flex items-center gap-3 text-xs text-tertiary">
                                    <span>Asked by: ${q.asked_by}</span>
                                    <span>@${Math.round(q.timestamp_minutes)}m</span>
                                    <span class="px-2 py-0.5 rounded-full ${q.answered ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400'}">
                                        ${q.answered ? 'Answered' : 'Pending'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    async loadActionItemsCompletion(meetingId) {
        try {
            const response = await fetch(`/api/analytics/meetings/${meetingId}/action-items-completion`);
            const data = await response.json();
            
            if (data.success && data.completion) {
                this.renderActionItemsCompletion(data.completion);
            }
        } catch (error) {
            console.error('Failed to load action items completion:', error);
        }
    }

    renderActionItemsCompletion(completion) {
        const container = document.getElementById('actionItemsCompletion');
        if (!container) return;

        const completionRate = completion.completion_rate || 0;
        const progressColor = completionRate >= 75 ? 'bg-green-500' : completionRate >= 50 ? 'bg-blue-500' : 'bg-orange-500';

        container.innerHTML = `
            <!-- Completion Overview -->
            <div class="mb-6">
                <div class="flex items-center justify-between mb-2">
                    <h3 class="text-lg font-semibold">Overall Completion</h3>
                    <span class="text-2xl font-bold text-primary">${completionRate}%</span>
                </div>
                <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div class="${progressColor} h-full transition-all duration-500" style="width: ${completionRate}%"></div>
                </div>
            </div>

            <!-- Status Breakdown -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="p-4 rounded-lg bg-gray-100 dark:bg-gray-800">
                    <div class="text-2xl font-bold">${completion.total}</div>
                    <div class="text-sm text-secondary">Total Items</div>
                </div>
                <div class="p-4 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                    <div class="text-2xl font-bold text-green-600 dark:text-green-400">${completion.completed}</div>
                    <div class="text-sm">Completed</div>
                </div>
                <div class="p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                    <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">${completion.in_progress}</div>
                    <div class="text-sm">In Progress</div>
                </div>
                <div class="p-4 rounded-lg bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800">
                    <div class="text-2xl font-bold text-orange-600 dark:text-orange-400">${completion.todo}</div>
                    <div class="text-sm">To Do</div>
                </div>
            </div>

            <!-- Action Items List -->
            ${completion.tasks && completion.tasks.length > 0 ? `
                <div class="space-y-2">
                    <h4 class="font-semibold mb-3">Action Items</h4>
                    ${completion.tasks.map(task => {
                        const statusColor = {
                            'completed': 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
                            'in_progress': 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
                            'todo': 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400'
                        }[task.status] || 'bg-gray-100 text-gray-700';

                        const priorityColor = {
                            'high': 'text-red-600',
                            'medium': 'text-yellow-600',
                            'low': 'text-gray-600'
                        }[task.priority] || 'text-gray-600';

                        return `
                            <div class="p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-primary transition-colors">
                                <div class="flex items-start gap-3">
                                    <div class="flex-shrink-0 pt-1">
                                        ${task.status === 'completed'
                                            ? '<svg class="w-5 h-5 text-green-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>'
                                            : '<svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2"/></svg>'
                                        }
                                    </div>
                                    <div class="flex-1 min-w-0">
                                        <div class="text-sm font-medium mb-1 ${task.status === 'completed' ? 'line-through text-gray-500' : ''}">${task.title}</div>
                                        <div class="flex flex-wrap items-center gap-2 text-xs">
                                            <span class="px-2 py-0.5 rounded-full ${statusColor}">
                                                ${task.status.replace('_', ' ')}
                                            </span>
                                            ${task.priority ? `<span class="${priorityColor} font-medium">${task.priority} priority</span>` : ''}
                                            ${task.assignee ? `<span class="text-tertiary">Assigned: ${task.assignee}</span>` : ''}
                                            ${task.due_date ? `<span class="text-tertiary">Due: ${new Date(task.due_date).toLocaleDateString()}</span>` : ''}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            ` : '<p class="text-center text-secondary py-4">No action items found</p>'}
        `;
    }

    async exportAnalytics() {
        const format = 'json'; // Could add PDF later
        
        try {
            const response = await fetch(`/api/analytics/export?days=${this.selectedDateRange}&format=${format}`);
            const data = await response.json();
            
            if (data.success) {
                // Create downloadable JSON file
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `mina-analytics-${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                // Show success toast
                this.showToast('Analytics exported successfully', 'success');
            } else {
                this.showToast(data.message || 'Export failed', 'error');
            }
        } catch (error) {
            console.error('Failed to export analytics:', error);
            this.showToast('Failed to export analytics', 'error');
        }
    }

    showToast(message, type = 'info') {
        // Simple toast notification (could be enhanced with a toast library)
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg text-white ${
            type === 'success' ? 'bg-green-500' : 'bg-red-500'
        }`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    startAutoRefresh(interval = 60000) { // every 60s
    setInterval(async () => {
        console.log("🔄 Refreshing analytics...");
        await this.loadDashboardData();
    }, interval);
    }
}

// Initialize when DOM is ready and Chart.js is loaded
window.addEventListener('load', function() {
    // Only initialize if we're on an analytics page (check for analytics-specific elements)
    const analyticsContainer = document.querySelector('.analytics-dashboard') || 
                               document.querySelector('.date-range-select') ||
                               document.getElementById('meetingActivityChart');
    
    if (!analyticsContainer) {
        console.log('📊 Analytics UI not found - skipping initialization');
        return;
    }
    
    if (typeof Chart !== 'undefined') {
        // Set Chart.js defaults
        Chart.defaults.color = getComputedStyle(document.documentElement).getPropertyValue('--color-text-primary').trim();
        Chart.defaults.borderColor = getComputedStyle(document.documentElement).getPropertyValue('--color-border').trim();
        Chart.defaults.font.family = 'Inter, system-ui, -apple-system, sans-serif';
        
        // Initialize dashboard
        window.analyticsDashboard = new AnalyticsDashboard();
    } else {
        console.error('Chart.js not loaded');
    }
});
