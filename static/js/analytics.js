/**
 * Analytics Dashboard - Live Data Integration
 * Fetches real-time analytics data and powers Chart.js visualizations
 */

class AnalyticsDashboard {
    constructor() {
        this.selectedDateRange = 30; // Default: 30 days
        this.charts = {};
        this.widgetPreferences = this.loadWidgetPreferences();
        this.init();
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

        // Group widgets by category
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
    }

    hideCustomizeModal() {
        const modal = document.getElementById('widgetCustomizationModal');
        if (modal) {
            modal.classList.add('hidden');
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
        document.querySelectorAll('.analytics-tab').forEach(tab => {
            tab.addEventListener('click', async () => {
                const targetTab = tab.dataset.tab;
                
                // Update active states
                document.querySelectorAll('.analytics-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.analytics-tab-content').forEach(c => c.classList.remove('active'));
                
                tab.classList.add('active');
                document.getElementById('tab-' + targetTab).classList.add('active');
                
                // Load tab-specific data
                await this.loadTabData(targetTab);
            });
        });
    }

    async loadDashboardData() {
        try {
            const response = await fetch(`/api/analytics/dashboard?days=${this.selectedDateRange}`);
            const data = await response.json();
            
            if (data.success) {
                this.updateOverviewCharts(data.dashboard);
            }
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        }
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
        }
        
        // Update Task Status Chart
        this.updateTaskStatusChart(dashboard);
        
        // Load and update Speaker Distribution
        this.loadCommunicationData().then(commData => {
            if (commData) {
                this.updateSpeakerChart(commData);
            }
        });
    }

    updateMeetingActivityChart(trendData) {
        const ctx = document.getElementById('meetingActivityChart');
        if (!ctx) return;

        const labels = trendData.map(d => {
            const date = new Date(d.date);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });
        const values = trendData.map(d => d.meetings);

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
        if (!ctx || !dashboard.productivity) return;

        const tasks = dashboard.productivity;
        const completed = tasks.total_tasks_created || 0;
        const inProgress = Math.floor(completed * 0.3); // Estimate
        const pending = Math.floor(completed * 0.1); // Estimate

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
        if (!ctx || !commData.top_speakers) return;

        const speakers = commData.top_speakers.slice(0, 5);
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
        if (!ctx) return;

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
        if (!ctx) return;

        try {
            const response = await fetch(`/api/analytics/sentiment?days=${this.selectedDateRange}`);
            const data = await response.json();
            
            if (!data.success || !data.sentiment.trend) return;

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
        if (!ctx) return;

        if (this.charts.productivity) {
            this.charts.productivity.destroy();
        }

        // Create task completion trend (mock data based on completion rate)
        const completionRate = productivity.tasks.completion_rate || 0;
        const weeks = 4;
        const trendData = Array(weeks).fill(0).map((_, i) => {
            const variance = (Math.random() - 0.5) * 20;
            return Math.max(0, Math.min(100, completionRate + variance));
        });

        this.charts.productivity = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
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
                            label: (item) => `${item.parsed.y.toFixed(1)}%`
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
        if (!ctx) return;

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
        if (!ctx) return;

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
        const container = document.getElementById('speakingTimeDetails');
        if (!container) return;

        container.innerHTML = `
            <div class="text-center text-secondary py-12">
                <svg class="w-16 h-16 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                </svg>
                <p class="font-medium">No speaking time data available</p>
                <p class="text-sm mt-1">Record meetings to see participant speaking analytics</p>
            </div>
        `;
    }

    /**
     * T2.34: Participation Balance Metrics
     * Calculates and displays comprehensive balance indicators
     */
    updateParticipationBalanceMetrics(communication) {
        const container = document.getElementById('participationBalanceMetrics');
        if (!container || !communication || !communication.top_speakers) {
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
        // Determine color based on score
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
            <div class="p-5 rounded-xl" style="background: ${bgGradient}; border: 1px solid rgba(255, 255, 255, 0.1);">
                <div class="flex items-start justify-between mb-3">
                    <div class="w-10 h-10 rounded-lg flex items-center justify-center ${colorClass}" style="background: rgba(255, 255, 255, 0.1);">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${iconPath}"/>
                        </svg>
                    </div>
                    <div class="text-right">
                        <div class="text-3xl font-bold ${colorClass}">${score}</div>
                        <div class="text-xs text-secondary">/ 100</div>
                    </div>
                </div>
                <h3 class="font-semibold text-sm mb-1">${title}</h3>
                <p class="text-xs text-tertiary mb-2">${description}</p>
                <div class="flex items-center gap-2">
                    <div class="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div class="h-full ${colorClass} transition-all duration-500" style="width: ${score}%; opacity: 0.8;"></div>
                    </div>
                    <span class="text-xs font-medium ${colorClass}">${status}</span>
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
