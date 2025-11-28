/**
 * CROWN⁴.6 Meeting Intelligence Mode
 * Groups tasks by their source meeting - a key differentiator feature
 */

class MeetingIntelligenceMode {
    constructor() {
        this.isActive = false;
        this.meetings = new Map();
        this.taskElements = []; // Store live DOM references
        this.init();
    }

    init() {
        console.log('[MeetingIntelligenceMode] Initializing...');
        
        const toggleBtn = document.getElementById('meeting-intelligence-toggle');
        if (!toggleBtn) {
            console.warn('[MeetingIntelligenceMode] Toggle button not found');
            return;
        }

        // Toggle button click handler
        toggleBtn.addEventListener('click', () => {
            this.toggle();
        });

        console.log('[MeetingIntelligenceMode] Initialized');
    }

    /**
     * Toggle between meeting mode and normal mode
     */
    async toggle() {
        this.isActive = !this.isActive;
        
        const toggleBtn = document.getElementById('meeting-intelligence-toggle');
        if (toggleBtn) {
            toggleBtn.classList.toggle('active', this.isActive);
        }

        // CROWN⁴.6: Add/remove 'meeting-mode-on' class to body
        document.body.classList.toggle('meeting-mode-on', this.isActive);

        // CROWN⁴.6 FIX: Begin view transition to prevent counter flicker during DOM manipulation
        if (window.taskStateStore) {
            window.taskStateStore.beginViewTransition();
        }

        try {
            if (this.isActive) {
                await this.activateMeetingMode();
                // CROWN⁴.6: Notify TaskStateStore of view mode change
                window.dispatchEvent(new CustomEvent('meetingMode:activated'));
            } else {
                this.deactivateMeetingMode();
                // CROWN⁴.6: Notify TaskStateStore of view mode change
                window.dispatchEvent(new CustomEvent('meetingMode:deactivated'));
            }
        } finally {
            // CROWN⁴.6 FIX: End view transition after DOM manipulation completes
            requestAnimationFrame(() => {
                if (window.taskStateStore) {
                    window.taskStateStore.endViewTransition();
                }
            });
        }
    }

    /**
     * Activate meeting-grouped view
     */
    async activateMeetingMode() {
        console.log('[MeetingIntelligenceMode] Activating meeting mode...');

        const container = document.getElementById('tasks-list-container');
        if (!container) return;

        // Get all task cards (live DOM elements)
        let taskCards = Array.from(container.querySelectorAll('.task-card'));
        
        // CROWN⁴.6 FIX: If DOM is empty but cache has tasks, re-render from cache first
        if (taskCards.length === 0 && window.cacheManager) {
            console.log('[MeetingIntelligenceMode] DOM empty, attempting to restore from cache...');
            try {
                const cachedTasks = await window.cacheManager.getTasks();
                if (cachedTasks && cachedTasks.length > 0) {
                    console.log(`[MeetingIntelligenceMode] Found ${cachedTasks.length} tasks in cache, re-rendering...`);
                    // Trigger a re-render from cache
                    if (window.taskBootstrap) {
                        await window.taskBootstrap.renderTasks(cachedTasks, { fromCache: true });
                        // Re-query for task cards after render
                        taskCards = Array.from(container.querySelectorAll('.task-card'));
                    }
                }
            } catch (error) {
                console.error('[MeetingIntelligenceMode] Failed to restore from cache:', error);
            }
        }
        
        if (taskCards.length === 0) {
            console.log('[MeetingIntelligenceMode] No task cards found, showing empty state');
            container.innerHTML = `
                <div class="empty-state meeting-mode-empty">
                    <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                    </svg>
                    <h3>No tasks to group</h3>
                    <p class="text-secondary">Create tasks from meetings to see them grouped here</p>
                </div>
            `;
            return;
        }

        console.log(`[MeetingIntelligenceMode] Found ${taskCards.length} task cards to group`);
        
        // Store references to live task elements
        this.taskElements = taskCards;

        // Fetch meeting data for all tasks
        await this.fetchMeetingData(taskCards);

        // Group tasks by meeting
        const groupedTasks = this.groupTasksByMeeting(taskCards);

        // Render grouped view (using live DOM elements)
        this.renderMeetingGroups(groupedTasks);
        // Note: Counter update handled by view transition wrapper in toggle()
    }

    /**
     * Deactivate meeting mode and restore normal view
     */
    deactivateMeetingMode() {
        console.log('[MeetingIntelligenceMode] Deactivating meeting mode...');

        const container = document.getElementById('tasks-list-container');
        if (!container) return;

        // Clear container
        container.innerHTML = '';

        // Re-append all live task elements in their original order
        this.taskElements.forEach(taskCard => {
            // Remove from any meeting group if still attached
            if (taskCard.parentNode) {
                taskCard.parentNode.removeChild(taskCard);
            }
            container.appendChild(taskCard);
        });

        // Clear stored references
        this.taskElements = [];

        console.log('[MeetingIntelligenceMode] Normal mode restored with live elements');
        
        // Re-apply current filter so TaskSearchSort can update visibility
        requestAnimationFrame(() => {
            if (window.taskSearchSort) {
                window.taskSearchSort.applyFiltersAndSort();
            }
            // Note: Counter update handled by view transition wrapper in toggle()
        });
    }

    /**
     * Fetch meeting data for tasks
     */
    async fetchMeetingData(taskCards) {
        const meetingIds = new Set();
        
        taskCards.forEach(card => {
            const meetingId = card.dataset.meetingId;
            if (meetingId) {
                meetingIds.add(parseInt(meetingId));
            }
        });

        // Fetch meeting data from API
        const promises = Array.from(meetingIds).map(async (meetingId) => {
            try {
                const response = await fetch(`/api/meetings/${meetingId}`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.success && data.meeting) {
                        this.meetings.set(meetingId, data.meeting);
                    }
                }
            } catch (error) {
                console.error(`[MeetingIntelligenceMode] Error fetching meeting ${meetingId}:`, error);
            }
        });

        await Promise.all(promises);
    }

    /**
     * Group tasks by meeting
     */
    groupTasksByMeeting(taskCards) {
        const groups = {
            'with-meeting': new Map(),
            'no-meeting': []
        };

        taskCards.forEach(card => {
            const meetingId = card.dataset.meetingId;
            
            if (meetingId && meetingId !== '') {
                const id = parseInt(meetingId);
                if (!groups['with-meeting'].has(id)) {
                    groups['with-meeting'].set(id, []);
                }
                groups['with-meeting'].get(id).push(card);
            } else {
                groups['no-meeting'].push(card);
            }
        });

        return groups;
    }

    /**
     * Render meeting-grouped view
     */
    renderMeetingGroups(groupedTasks) {
        const container = document.getElementById('tasks-list-container');
        if (!container) return;

        // Clear container
        container.innerHTML = '';

        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'meeting-intelligence-view';

        // Render meeting groups (sorted by most recent first)
        const meetingGroups = Array.from(groupedTasks['with-meeting'].entries())
            .sort((a, b) => {
                const meetingA = this.meetings.get(a[0]);
                const meetingB = this.meetings.get(b[0]);
                if (!meetingA || !meetingB) return 0;
                return new Date(meetingB.created_at) - new Date(meetingA.created_at);
            });

        meetingGroups.forEach(([meetingId, tasks]) => {
            const meeting = this.meetings.get(meetingId);
            const groupElement = this.createMeetingGroup(meeting, tasks, meetingId);
            wrapper.appendChild(groupElement);
        });

        // Render tasks without meeting
        if (groupedTasks['no-meeting'].length > 0) {
            const noMeetingGroup = this.createNoMeetingGroup(groupedTasks['no-meeting']);
            wrapper.appendChild(noMeetingGroup);
        }

        container.appendChild(wrapper);
        console.log('[MeetingIntelligenceMode] Rendered meeting groups with live DOM elements');
    }

    /**
     * Create a single meeting group element
     */
    createMeetingGroup(meeting, tasks, meetingId) {
        const meetingTitle = meeting ? (meeting.title || 'Untitled Meeting') : `Meeting #${meetingId}`;
        const meetingDate = meeting ? this.formatDate(meeting.created_at) : '';
        const taskCount = tasks.length;
        const completedCount = tasks.filter(t => t.classList.contains('completed')).length;
        const pendingCount = taskCount - completedCount;

        // Create group container
        const groupDiv = document.createElement('div');
        groupDiv.className = 'meeting-group';
        groupDiv.dataset.meetingId = meetingId;

        // Create header
        const header = document.createElement('div');
        header.className = 'meeting-group-header';
        header.innerHTML = `
            <div class="meeting-header-content">
                <div class="meeting-icon">
                    <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M20 6h-2.18c.11-.31.18-.65.18-1 0-1.66-1.34-3-3-3-1.05 0-1.96.54-2.5 1.35l-.5.67-.5-.68C10.96 2.54 10.05 2 9 2 7.34 2 6 3.34 6 5c0 .35.07.69.18 1H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-5-2c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zM9 4c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm11 15H4v-2h16v2zm0-5H4V8h5.08L7 10.83 8.62 12 11 8.76l1-1.36 1 1.36L15.38 12 17 10.83 14.92 8H20v6z"/>
                    </svg>
                </div>
                <div class="meeting-info">
                    <h3 class="meeting-title">${this.escapeHtml(meetingTitle)}</h3>
                    ${meetingDate ? `<span class="meeting-date">${meetingDate}</span>` : ''}
                </div>
            </div>
            <div class="meeting-stats">
                <div class="stat-item">
                    <span class="stat-value">${taskCount}</span>
                    <span class="stat-label">task${taskCount !== 1 ? 's' : ''}</span>
                </div>
                <div class="stat-divider"></div>
                <div class="stat-item stat-pending">
                    <span class="stat-value">${pendingCount}</span>
                    <span class="stat-label">pending</span>
                </div>
                <div class="stat-item stat-completed">
                    <span class="stat-value">${completedCount}</span>
                    <span class="stat-label">done</span>
                </div>
            </div>
        `;

        // Create tasks container
        const tasksContainer = document.createElement('div');
        tasksContainer.className = 'meeting-group-tasks';

        // Append live task elements (not clones)
        tasks.forEach(taskCard => {
            tasksContainer.appendChild(taskCard);
        });

        groupDiv.appendChild(header);
        groupDiv.appendChild(tasksContainer);

        return groupDiv;
    }

    /**
     * Create tasks without meeting group
     */
    createNoMeetingGroup(tasks) {
        const taskCount = tasks.length;
        const completedCount = tasks.filter(t => t.classList.contains('completed')).length;
        const pendingCount = taskCount - completedCount;

        // Create group container
        const groupDiv = document.createElement('div');
        groupDiv.className = 'meeting-group no-meeting-group';

        // Create header
        const header = document.createElement('div');
        header.className = 'meeting-group-header';
        header.innerHTML = `
            <div class="meeting-header-content">
                <div class="meeting-icon no-meeting-icon">
                    <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                    </svg>
                </div>
                <div class="meeting-info">
                    <h3 class="meeting-title">Manual Tasks</h3>
                    <span class="meeting-date">Created manually, not from meetings</span>
                </div>
            </div>
            <div class="meeting-stats">
                <div class="stat-item">
                    <span class="stat-value">${taskCount}</span>
                    <span class="stat-label">task${taskCount !== 1 ? 's' : ''}</span>
                </div>
                <div class="stat-divider"></div>
                <div class="stat-item stat-pending">
                    <span class="stat-value">${pendingCount}</span>
                    <span class="stat-label">pending</span>
                </div>
                <div class="stat-item stat-completed">
                    <span class="stat-value">${completedCount}</span>
                    <span class="stat-label">done</span>
                </div>
            </div>
        `;

        // Create tasks container
        const tasksContainer = document.createElement('div');
        tasksContainer.className = 'meeting-group-tasks';

        // Append live task elements (not clones)
        tasks.forEach(taskCard => {
            tasksContainer.appendChild(taskCard);
        });

        groupDiv.appendChild(header);
        groupDiv.appendChild(tasksContainer);

        return groupDiv;
    }

    /**
     * Format date for display
     */
    formatDate(dateString) {
        if (!dateString) return '';
        
        const date = new Date(dateString);
        const now = new Date();
        const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));

        if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays} days ago`;
        } else {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('tasks-list-container')) {
        window.meetingIntelligenceMode = new MeetingIntelligenceMode();
    }
});
