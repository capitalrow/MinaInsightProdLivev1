/**
 * CROWN⁴.6 Meeting Heatmap Component
 * Visualizes which meetings have active tasks with gradient glow indicators
 */

class MeetingHeatmap {
    constructor() {
        this.meetings = [];
        this.selectedMeetingId = null;
        this.init();
    }

    async init() {
        console.log('[MeetingHeatmap] Initializing...');
        await this.fetchHeatmapData();
        this.render();
        this.attachEventListeners();
    }

    /**
     * Fetch meeting heatmap data from API
     */
    async fetchHeatmapData() {
        try {
            const response = await fetch('/api/tasks/meeting-heatmap', {
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`[MeetingHeatmap] HTTP ${response.status}: ${errorText}`);
                throw new Error(`HTTP ${response.status}: ${errorText.substring(0, 100)}`);
            }

            const data = await response.json();
            
            if (!data.success) {
                console.error('[MeetingHeatmap] API returned error:', data.message || 'Unknown error');
                this.meetings = [];
                // Don't return early - still render the empty state UI
            } else {
                this.meetings = data.meetings || [];
                console.log(`[MeetingHeatmap] ✅ Loaded ${this.meetings.length} meetings with ${data.total_meetings} total`);
            }
            
        } catch (error) {
            console.error('[MeetingHeatmap] Error fetching data:', {
                message: error.message,
                stack: error.stack,
                error: error
            });
            this.meetings = [];
        }
    }

    /**
     * Render the heatmap component with inline fallback styles
     */
    render() {
        const container = document.getElementById('meeting-heatmap-container');
        if (!container) {
            console.warn('[MeetingHeatmap] Container not found');
            return;
        }

        if (this.meetings.length === 0) {
            container.innerHTML = `
                <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2rem 1rem;text-align:center;color:rgba(255,255,255,0.5);">
                    <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="margin-bottom:0.75rem;opacity:0.3;">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                    </svg>
                    <p style="font-size:0.875rem;font-weight:500;margin:0 0 0.25rem 0;">No meetings with tasks yet</p>
                    <span style="font-size:0.75rem;">Tasks from meetings will appear here</span>
                </div>
            `;
            return;
        }

        const meetingsHTML = this.meetings.map(meeting => this.renderMeetingCard(meeting)).join('');
        
        container.innerHTML = `
            <div class="heatmap-header" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;padding:0 0.25rem;">
                <h3 class="heatmap-title" style="display:flex;align-items:center;gap:0.5rem;font-size:0.875rem;font-weight:600;color:rgba(255,255,255,0.9);margin:0;">
                    <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24" style="opacity:0.7;">
                        <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V9.03l7-3.5v7.46z"/>
                    </svg>
                    Meeting Activity
                </h3>
                <span class="heatmap-count" style="font-size:0.75rem;color:rgba(255,255,255,0.5);font-weight:500;background:rgba(255,255,255,0.1);padding:0.25rem 0.5rem;border-radius:4px;">${this.meetings.length} active</span>
            </div>
            <div class="heatmap-grid" style="display:flex;flex-direction:column;gap:0.5rem;">
                ${meetingsHTML}
            </div>
        `;
    }

    /**
     * Render a single meeting card with inline fallback styles
     * Mobile-optimized: horizontal layout with title+date on left, stats on right
     */
    renderMeetingCard(meeting) {
        const heatClass = this.getHeatClass(meeting.heat_intensity);
        const isSelected = this.selectedMeetingId === meeting.meeting_id;
        
        const dateStr = this.formatMeetingDate(meeting.created_at, meeting.days_ago);
        const totalTasks = meeting.active_tasks || 0;
        
        const borderColor = meeting.heat_intensity >= 70 ? 'rgba(255,71,87,0.3)' : 
                           meeting.heat_intensity >= 40 ? 'rgba(255,165,2,0.3)' : 
                           'rgba(30,144,255,0.3)';
        
        const cardStyle = `
            display:flex;
            align-items:center;
            padding:0.875rem 1rem;
            background:rgba(255,255,255,0.05);
            border:1px solid ${borderColor};
            border-radius:10px;
            cursor:pointer;
            min-height:56px;
            transition:all 0.2s ease;
        `.replace(/\s+/g, ' ').trim();
        
        const contentStyle = `
            display:flex;
            align-items:center;
            justify-content:space-between;
            width:100%;
            gap:0.75rem;
        `.replace(/\s+/g, ' ').trim();
        
        const headerStyle = `
            display:flex;
            flex-direction:column;
            gap:0.125rem;
            flex:1;
            min-width:0;
        `.replace(/\s+/g, ' ').trim();
        
        const titleStyle = `
            font-size:0.8125rem;
            font-weight:600;
            color:rgba(255,255,255,0.95);
            margin:0;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
        `.replace(/\s+/g, ' ').trim();
        
        const dateStyle = `
            font-size:0.6875rem;
            color:rgba(255,255,255,0.5);
        `.replace(/\s+/g, ' ').trim();
        
        const badgeStyle = `
            display:flex;
            align-items:center;
            gap:0.25rem;
            padding:0.25rem 0.5rem;
            background:rgba(34,197,94,0.2);
            border-radius:6px;
            font-size:0.75rem;
            font-weight:600;
            color:#86efac;
            flex-shrink:0;
        `.replace(/\s+/g, ' ').trim();
        
        return `
            <div class="heatmap-meeting-card ${heatClass} ${isSelected ? 'selected' : ''}" 
                 data-meeting-id="${meeting.meeting_id}"
                 data-heat="${meeting.heat_intensity}"
                 role="button"
                 tabindex="0"
                 style="${cardStyle}"
                 aria-label="${this.escapeHtml(meeting.meeting_title)}, ${totalTasks} tasks, ${dateStr}">
                <div class="meeting-card-content" style="${contentStyle}">
                    <div class="meeting-card-header" style="${headerStyle}">
                        <h4 class="meeting-card-title" style="${titleStyle}" title="${this.escapeHtml(meeting.meeting_title)}">
                            ${this.escapeHtml(this.truncate(meeting.meeting_title, 40))}
                        </h4>
                        <span class="meeting-card-date" style="${dateStyle}">${dateStr}</span>
                    </div>
                    <div class="meeting-card-stats" style="display:flex;align-items:center;flex-shrink:0;">
                        <div class="stat-badge stat-active" style="${badgeStyle}" title="${totalTasks} active tasks">
                            <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                            </svg>
                            <span>${totalTasks} tasks</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Get heat class based on intensity
     */
    getHeatClass(intensity) {
        if (intensity >= 70) return 'heat-high';
        if (intensity >= 40) return 'heat-medium';
        return 'heat-low';
    }

    /**
     * Format meeting date
     */
    formatMeetingDate(isoDate, daysAgo) {
        if (daysAgo === 0) return 'Today';
        if (daysAgo === 1) return 'Yesterday';
        if (daysAgo < 7) return `${daysAgo}d ago`;
        
        try {
            const date = new Date(isoDate);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        } catch {
            return `${daysAgo}d ago`;
        }
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        const container = document.getElementById('meeting-heatmap-container');
        if (!container) return;

        // Meeting card click - filter tasks by meeting
        container.addEventListener('click', (e) => {
            const card = e.target.closest('.heatmap-meeting-card');
            if (!card) return;

            const meetingId = parseInt(card.dataset.meetingId);
            this.toggleMeetingFilter(meetingId);
        });
    }

    /**
     * Toggle meeting filter
     */
    toggleMeetingFilter(meetingId) {
        // Toggle selection
        if (this.selectedMeetingId === meetingId) {
            this.selectedMeetingId = null;
            this.clearMeetingFilter();
        } else {
            this.selectedMeetingId = meetingId;
            this.applyMeetingFilter(meetingId);
        }

        // Update UI
        this.updateSelectedState();
    }

    /**
     * Apply meeting filter to task list
     */
    applyMeetingFilter(meetingId) {
        const tasks = document.querySelectorAll('.task-card[data-meeting-id]');
        tasks.forEach(task => {
            const taskMeetingId = parseInt(task.dataset.meetingId);
            if (taskMeetingId === meetingId) {
                task.style.display = '';
                task.classList.add('heatmap-filtered');
            } else {
                task.style.display = 'none';
            }
        });

        // Show filtered indicator
        this.showFilterIndicator(meetingId);
    }

    /**
     * Clear meeting filter
     */
    clearMeetingFilter() {
        const tasks = document.querySelectorAll('.task-card');
        tasks.forEach(task => {
            task.style.display = '';
            task.classList.remove('heatmap-filtered');
        });

        this.hideFilterIndicator();
    }

    /**
     * Update selected state in UI
     */
    updateSelectedState() {
        const cards = document.querySelectorAll('.heatmap-meeting-card');
        cards.forEach(card => {
            const cardMeetingId = parseInt(card.dataset.meetingId);
            if (cardMeetingId === this.selectedMeetingId) {
                card.classList.add('selected');
            } else {
                card.classList.remove('selected');
            }
        });
    }

    /**
     * Show filter indicator
     */
    showFilterIndicator(meetingId) {
        const meeting = this.meetings.find(m => m.meeting_id === meetingId);
        if (!meeting) return;

        const indicator = document.getElementById('meeting-filter-indicator');
        if (indicator) {
            indicator.innerHTML = `
                <span class="filter-label">Filtered by:</span>
                <strong>${this.escapeHtml(meeting.meeting_title)}</strong>
                <button class="filter-clear-btn" onclick="window.meetingHeatmap?.clearMeetingFilter()">
                    <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                </button>
            `;
            indicator.style.display = 'flex';
        }
    }

    /**
     * Hide filter indicator
     */
    hideFilterIndicator() {
        const indicator = document.getElementById('meeting-filter-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    /**
     * Utility: Truncate text
     */
    truncate(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    /**
     * Utility: Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Refresh heatmap data
     */
    async refresh() {
        await this.fetchHeatmapData();
        this.render();
        this.attachEventListeners();
        
        // Re-apply filter if active
        if (this.selectedMeetingId) {
            this.applyMeetingFilter(this.selectedMeetingId);
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('meeting-heatmap-container')) {
        window.meetingHeatmap = new MeetingHeatmap();
    }
});
