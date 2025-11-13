/**
 * CROWN⁴.6 Task Grouping & Focus Slices
 * Organizes tasks into intelligent sections to prevent overwhelming users
 * 
 * Implements progressive grouping strategy:
 * - Focus Slices: Pinned, Recently Updated, Due Soon (always visible)
 * - Meeting Sections: Grouped by meeting_id (collapsible, collapsed by default)
 * - All Other Tasks: Catch-all section
 */

class TaskGrouping {
    constructor(taskStore) {
        this.taskStore = taskStore;
        this.sectionStates = this.loadSectionStates();
        console.log('[TaskGrouping] Initialized with section states:', this.sectionStates);
    }

    /**
     * Load section expand/collapse states from localStorage
     */
    loadSectionStates() {
        try {
            const saved = localStorage.getItem('crown_task_section_states');
            return saved ? JSON.parse(saved) : {};
        } catch (error) {
            console.error('[TaskGrouping] Failed to load section states:', error);
            return {};
        }
    }

    /**
     * Save section expand/collapse state
     * @param {string} sectionId - Section identifier
     * @param {boolean} expanded - Whether section is expanded
     */
    saveSectionState(sectionId, expanded) {
        this.sectionStates[sectionId] = expanded;
        try {
            localStorage.setItem('crown_task_section_states', JSON.stringify(this.sectionStates));
            console.log('[TaskGrouping] Saved section state:', sectionId, expanded);
        } catch (error) {
            console.error('[TaskGrouping] Failed to save section state:', error);
        }
    }

    /**
     * Get section state (default varies by section type)
     * @param {string} sectionId - Section identifier
     * @param {boolean} defaultExpanded - Default state if not saved
     */
    getSectionState(sectionId, defaultExpanded = true) {
        return this.sectionStates.hasOwnProperty(sectionId) 
            ? this.sectionStates[sectionId] 
            : defaultExpanded;
    }

    /**
     * Group tasks into Focus Slices and Meeting Sections
     * @param {Array} tasks - Array of task objects
     * @returns {Object} Grouped tasks
     */
    groupTasks(tasks) {
        const now = Date.now();
        const oneDayAgo = now - (24 * 60 * 60 * 1000);
        const sevenDaysFromNow = now + (7 * 24 * 60 * 60 * 1000);

        const groups = {
            pinned: [],
            recentlyUpdated: [],
            dueSoon: [],
            meetings: {},
            other: []
        };

        tasks.forEach(task => {
            const taskUpdatedAt = new Date(task.updated_at).getTime();
            const taskDueDate = task.due_date ? new Date(task.due_date).getTime() : null;

            // Pinned tasks (highest priority)
            if (task.is_pinned) {
                groups.pinned.push(task);
                return;
            }

            // Recently updated (last 24 hours)
            if (taskUpdatedAt > oneDayAgo) {
                groups.recentlyUpdated.push(task);
                return;
            }

            // Due soon (next 7 days)
            if (taskDueDate && taskDueDate <= sevenDaysFromNow && taskDueDate >= now) {
                groups.dueSoon.push(task);
                return;
            }

            // Group by meeting
            if (task.meeting_id) {
                if (!groups.meetings[task.meeting_id]) {
                    const meetingTitle = task.meeting_title || 
                                       task.meeting_name || 
                                       (task.created_at ? `Meeting on ${new Date(task.created_at).toLocaleDateString()}` : `Task Group ${task.meeting_id.toString().substring(0, 8)}`);
                    groups.meetings[task.meeting_id] = {
                        id: task.meeting_id,
                        title: meetingTitle,
                        tasks: []
                    };
                }
                groups.meetings[task.meeting_id].tasks.push(task);
                return;
            }

            // Everything else
            groups.other.push(task);
        });

        // Sort within groups
        groups.pinned.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
        groups.recentlyUpdated.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
        groups.dueSoon.sort((a, b) => new Date(a.due_date) - new Date(b.due_date));
        groups.other.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        // Convert meetings object to array and sort by most recent meeting
        groups.meetingsList = Object.values(groups.meetings).sort((a, b) => {
            const aLatest = Math.max(...a.tasks.map(t => new Date(t.created_at).getTime()));
            const bLatest = Math.max(...b.tasks.map(t => new Date(t.created_at).getTime()));
            return bLatest - aLatest;
        });

        return groups;
    }

    /**
     * Render grouped tasks into sections
     * @param {Array} tasks - Array of task objects
     * @param {Function} taskRenderer - Function to render individual task cards
     * @returns {HTMLElement} Container with grouped sections
     */
    render(tasks, taskRenderer) {
        const container = document.createElement('div');
        container.className = 'task-sections';

        const groups = this.groupTasks(tasks);

        // Render Focus Slices (always expanded)
        if (groups.pinned.length > 0) {
            container.appendChild(this.renderSection(
                'pinned',
                '📌 Pinned',
                groups.pinned,
                taskRenderer,
                true  // Always expanded
            ));
        }

        if (groups.recentlyUpdated.length > 0) {
            container.appendChild(this.renderSection(
                'recently-updated',
                '🔥 Recently Updated',
                groups.recentlyUpdated,
                taskRenderer,
                true  // Always expanded
            ));
        }

        if (groups.dueSoon.length > 0) {
            container.appendChild(this.renderSection(
                'due-soon',
                '📅 Due Soon',
                groups.dueSoon,
                taskRenderer,
                true  // Always expanded
            ));
        }

        // Render Meeting Sections (collapsed by default)
        groups.meetingsList.forEach(meeting => {
            container.appendChild(this.renderSection(
                `meeting-${meeting.id}`,
                `📁 ${meeting.title}`,
                meeting.tasks,
                taskRenderer,
                false  // Collapsed by default
            ));
        });

        // Render Other Tasks
        if (groups.other.length > 0) {
            container.appendChild(this.renderSection(
                'other',
                '📋 All Other Tasks',
                groups.other,
                taskRenderer,
                true  // Always expanded
            ));
        }

        return container;
    }

    /**
     * Render individual section
     * @param {string} id - Section ID
     * @param {string} title - Section title with icon
     * @param {Array} tasks - Tasks in this section
     * @param {Function} taskRenderer - Function to render individual task cards
     * @param {boolean} defaultExpanded - Default expansion state
     */
    renderSection(id, title, tasks, taskRenderer, defaultExpanded) {
        const section = document.createElement('div');
        section.className = 'task-section';
        section.dataset.sectionId = id;

        const expanded = this.getSectionState(id, defaultExpanded);

        // Section header
        const header = document.createElement('button');
        header.className = 'task-section-header';
        header.setAttribute('aria-expanded', expanded);
        header.innerHTML = `
            <span class="section-title">${title}</span>
            <span class="section-count">(${tasks.length})</span>
            <span class="section-toggle">${expanded ? '▼' : '▶'}</span>
        `;

        // Section content
        const content = document.createElement('div');
        content.className = 'task-section-content';
        content.setAttribute('aria-hidden', !expanded);
        if (!expanded) {
            content.style.display = 'none';
        }

        // Render tasks
        tasks.forEach(task => {
            content.appendChild(taskRenderer(task));
        });

        // Toggle handler
        header.addEventListener('click', () => {
            const nowExpanded = header.getAttribute('aria-expanded') === 'true';
            const newExpanded = !nowExpanded;

            header.setAttribute('aria-expanded', newExpanded);
            content.setAttribute('aria-hidden', !newExpanded);
            header.querySelector('.section-toggle').textContent = newExpanded ? '▼' : '▶';

            // Animate (with GSAP if available, fallback to instant)
            if (newExpanded) {
                if (window.gsap) {
                    content.style.display = 'block';
                    window.gsap.from(content, {
                        height: 0,
                        opacity: 0,
                        duration: 0.3,
                        ease: 'power2.out'
                    });
                } else {
                    content.style.display = 'block';
                }
            } else {
                if (window.gsap) {
                    window.gsap.to(content, {
                        height: 0,
                        opacity: 0,
                        duration: 0.3,
                        ease: 'power2.in',
                        onComplete: () => {
                            content.style.display = 'none';
                        }
                    });
                } else {
                    content.style.display = 'none';
                }
            }

            // Save state
            this.saveSectionState(id, newExpanded);

            // Telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_section_toggle', 1, {
                    section: id,
                    expanded: newExpanded,
                    taskCount: tasks.length
                });
            }
        });

        section.appendChild(header);
        section.appendChild(content);

        return section;
    }
}

// Export for use in task page
window.TaskGrouping = TaskGrouping;
console.log('✅ TaskGrouping module loaded');
