/**
 * CROWN⁴.5 Transcript Span Linking
 * Links tasks to specific transcript spans with morphing transitions.
 * 
 * Features:
 * - Link tasks to transcript timestamps
 * - Jump to transcript with morph animation
 * - Highlight linked span
 * - Bidirectional navigation
 */

class TranscriptSpanLinking {
    constructor() {
        this.linkedSpans = new Map(); // task_id -> span data
        this._init();
        console.log('[TranscriptSpanLinking] Initialized');
    }

    /**
     * Initialize linking system
     */
    _init() {
        this._setupListeners();
    }

    /**
     * Setup event listeners
     */
    _setupListeners() {
        // Listen for link creation events
        window.addEventListener('task_link_created', (e) => {
            this.linkTaskToSpan(e.detail);
        });

        // Listen for jump events
        window.addEventListener('task_link_jump', (e) => {
            this.jumpToSpan(e.detail.task_id);
        });

        // Handle click on task cards
        document.addEventListener('click', (e) => {
            const linkButton = e.target.closest('.task-link-button');
            if (linkButton) {
                const taskId = linkButton.dataset.taskId;
                this.jumpToSpan(taskId);
            }
        });
    }

    /**
     * Link task to transcript span
     * @param {Object} linkData
     */
    linkTaskToSpan(linkData) {
        const {
            task_id,
            span_start,
            span_end,
            transcript_text,
            session_id
        } = linkData;

        this.linkedSpans.set(task_id, {
            span_start,
            span_end,
            transcript_text,
            session_id,
            linked_at: Date.now()
        });

        // Add link indicator to task card
        this._addLinkIndicator(task_id, transcript_text);

        console.log(`[TranscriptSpanLinking] Linked task ${task_id} to span [${span_start}s - ${span_end}s]`);
    }

    /**
     * Add link indicator to task card
     * @param {string} task_id
     * @param {string} preview_text
     */
    _addLinkIndicator(task_id, preview_text) {
        const taskCard = document.querySelector(`[data-task-id="${task_id}"]`);
        if (!taskCard) return;

        // Remove existing indicator
        const existing = taskCard.querySelector('.transcript-link-indicator');
        if (existing) existing.remove();

        // Create link indicator
        const indicator = document.createElement('div');
        indicator.className = 'transcript-link-indicator';
        indicator.style.cssText = `
            margin-top: 8px;
            padding: 8px 12px;
            background: rgba(59, 130, 246, 0.1);
            border-left: 3px solid #3b82f6;
            border-radius: 6px;
            font-size: 13px;
            color: #1e40af;
            cursor: pointer;
            transition: all 200ms ease-out;
        `;

        const truncatedText = preview_text.length > 60
            ? preview_text.substring(0, 60) + '...'
            : preview_text;

        indicator.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                </svg>
                <span>"${truncatedText}"</span>
            </div>
        `;

        indicator.addEventListener('click', (e) => {
            e.stopPropagation();
            this.jumpToSpan(task_id);
        });

        indicator.addEventListener('mouseenter', () => {
            indicator.style.background = 'rgba(59, 130, 246, 0.15)';
            indicator.style.transform = 'translateX(4px)';
        });

        indicator.addEventListener('mouseleave', () => {
            indicator.style.background = 'rgba(59, 130, 246, 0.1)';
            indicator.style.transform = 'translateX(0)';
        });

        // Add to task content
        const taskContent = taskCard.querySelector('.task-content');
        if (taskContent) {
            taskContent.appendChild(indicator);
        }
    }

    /**
     * Jump to transcript span with morph animation
     * @param {string} task_id
     */
    async jumpToSpan(task_id) {
        const spanData = this.linkedSpans.get(task_id);
        if (!spanData) {
            console.warn(`[TranscriptSpanLinking] No span linked for task ${task_id}`);
            return;
        }

        console.log(`[TranscriptSpanLinking] Jumping to span for task ${task_id}`);

        // Step 1: Trigger morph animation on task card
        const taskCard = document.querySelector(`[data-task-id="${task_id}"]`);
        if (taskCard && window.crown45Animations) {
            window.crown45Animations.handleEvent('task_link:jump_to_span', taskCard);
        }

        // Step 2: Navigate to transcript page/section
        await this._navigateToTranscript(spanData);

        // Step 3: Highlight the span
        setTimeout(() => {
            this._highlightSpan(spanData);
        }, 300);

        // Step 4: Record telemetry
        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordEvent('task_link:jump_to_span', {
                task_id,
                span_start: spanData.span_start,
                span_end: spanData.span_end
            });
        }
    }

    /**
     * Navigate to transcript
     * @param {Object} spanData
     */
    async _navigateToTranscript(spanData) {
        const { session_id, span_start } = spanData;

        // Check if transcript is on current page
        const transcriptContainer = document.querySelector('#transcript-container');
        
        if (transcriptContainer) {
            // Scroll to transcript section
            transcriptContainer.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        } else {
            // Navigate to transcript page
            const transcriptUrl = `/sessions/${session_id}/transcript?t=${span_start}`;
            window.location.href = transcriptUrl;
        }
    }

    /**
     * Highlight transcript span
     * @param {Object} spanData
     */
    _highlightSpan(spanData) {
        const { span_start, span_end } = spanData;

        // Find transcript segments in range
        const segments = document.querySelectorAll('.transcript-segment');
        
        segments.forEach(segment => {
            const segmentStart = parseFloat(segment.dataset.startTime || 0);
            const segmentEnd = parseFloat(segment.dataset.endTime || 0);

            // Check if segment overlaps with span
            if (segmentStart >= span_start && segmentEnd <= span_end) {
                this._highlightSegment(segment);
            }
        });

        // Alternative: highlight by timestamp attribute
        const targetSegment = document.querySelector(`[data-timestamp="${span_start}"]`);
        if (targetSegment) {
            this._highlightSegment(targetSegment);
        }
    }

    /**
     * Highlight individual segment
     * @param {HTMLElement} segment
     */
    _highlightSegment(segment) {
        // Add highlight class
        segment.classList.add('linked-highlight');

        // Apply highlight styles
        segment.style.cssText = `
            background: rgba(59, 130, 246, 0.15);
            border-left: 4px solid #3b82f6;
            padding-left: 12px;
            margin-left: -12px;
            transition: all 300ms ease-out;
        `;

        // Scroll segment into view
        segment.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });

        // Pulse animation
        segment.style.animation = 'pulse 1s ease-out 2';

        // Remove highlight after 5 seconds
        setTimeout(() => {
            segment.style.background = '';
            segment.style.borderLeft = '';
            segment.style.paddingLeft = '';
            segment.style.marginLeft = '';
            segment.classList.remove('linked-highlight');
        }, 5000);
    }

    /**
     * Create link from transcript to task
     * @param {number} timestamp - Transcript timestamp
     * @param {string} selectedText - Selected transcript text
     */
    createLinkFromTranscript(timestamp, selectedText) {
        // Show task selection dialog
        this._showTaskSelectionDialog(timestamp, selectedText);
    }

    /**
     * Show task selection dialog
     * @param {number} timestamp
     * @param {string} selectedText
     */
    _showTaskSelectionDialog(timestamp, selectedText) {
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'task-link-modal';
        modal.style.cssText = `
            position: fixed;
            inset: 0;
            z-index: 10000;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
        `;

        modal.innerHTML = `
            <div style="
                background: white;
                border-radius: 12px;
                padding: 24px;
                max-width: 400px;
                width: 90%;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            ">
                <h3 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600;">
                    Link to Task
                </h3>
                <p style="margin: 0 0 16px 0; font-size: 14px; color: #6b7280;">
                    Select a task to link this transcript segment to:
                </p>
                
                <div style="margin-bottom: 16px; max-height: 300px; overflow-y: auto;">
                    <div id="task-selection-list"></div>
                </div>

                <div style="display: flex; gap: 8px;">
                    <button class="btn-cancel" style="
                        flex: 1;
                        background: #e5e7eb;
                        color: #374151;
                        border: none;
                        padding: 10px 16px;
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: 500;
                        cursor: pointer;
                    ">Cancel</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Load tasks
        this._loadTasksForLinking(modal, timestamp, selectedText);

        // Handle cancel
        modal.querySelector('.btn-cancel').addEventListener('click', () => {
            modal.remove();
        });
    }

    /**
     * Load tasks for linking
     * @param {HTMLElement} modal
     * @param {number} timestamp
     * @param {string} selectedText
     */
    async _loadTasksForLinking(modal, timestamp, selectedText) {
        const listContainer = modal.querySelector('#task-selection-list');
        
        try {
            // Fetch tasks (use task cache if available)
            const tasks = await this._fetchTasks();

            if (tasks.length === 0) {
                listContainer.innerHTML = '<p style="color: #9ca3af; text-align: center;">No tasks found</p>';
                return;
            }

            // Render task list
            tasks.forEach(task => {
                const taskItem = document.createElement('div');
                taskItem.style.cssText = `
                    padding: 12px;
                    border: 1px solid #e5e7eb;
                    border-radius: 6px;
                    margin-bottom: 8px;
                    cursor: pointer;
                    transition: all 150ms ease-out;
                `;

                taskItem.innerHTML = `
                    <div style="font-weight: 500; font-size: 14px; color: #1f2937;">
                        ${task.title}
                    </div>
                `;

                taskItem.addEventListener('mouseenter', () => {
                    taskItem.style.background = '#f3f4f6';
                    taskItem.style.borderColor = '#3b82f6';
                });

                taskItem.addEventListener('mouseleave', () => {
                    taskItem.style.background = '';
                    taskItem.style.borderColor = '#e5e7eb';
                });

                taskItem.addEventListener('click', () => {
                    this._confirmLink(task.id, timestamp, selectedText);
                    modal.remove();
                });

                listContainer.appendChild(taskItem);
            });

        } catch (error) {
            console.error('[TranscriptSpanLinking] Failed to load tasks:', error);
            listContainer.innerHTML = '<p style="color: #ef4444;">Failed to load tasks</p>';
        }
    }

    /**
     * Fetch tasks for linking
     * @returns {Promise<Array>} Tasks
     */
    async _fetchTasks() {
        if (window.taskCache && typeof window.taskCache.getAllTasks === 'function') {
            return await window.taskCache.getAllTasks();
        }

        // Fallback: fetch from API
        const response = await fetch('/api/tasks?per_page=50');
        const data = await response.json();
        return data.tasks || [];
    }

    /**
     * Confirm link creation
     * @param {string} task_id
     * @param {number} timestamp
     * @param {string} selectedText
     */
    async _confirmLink(task_id, timestamp, selectedText) {
        const linkData = {
            task_id,
            span_start: timestamp,
            span_end: timestamp + 10, // Default 10s span
            transcript_text: selectedText,
            session_id: this._getCurrentSessionId()
        };

        // Save link
        this.linkTaskToSpan(linkData);

        // Persist to server
        await this._saveLinkToServer(linkData);

        // Show success toast
        if (window.showToast) {
            window.showToast('Task linked to transcript', 'success');
        }
    }

    /**
     * Get current session ID
     * @returns {string|null}
     */
    _getCurrentSessionId() {
        const urlMatch = window.location.pathname.match(/\/sessions\/(\d+)/);
        return urlMatch ? urlMatch[1] : null;
    }

    /**
     * Save link to server
     * @param {Object} linkData
     */
    async _saveLinkToServer(linkData) {
        try {
            const response = await fetch('/api/tasks/links', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify(linkData)
            });

            if (!response.ok) {
                throw new Error(`Failed to save link: ${response.status}`);
            }

            console.log('[TranscriptSpanLinking] Link saved to server');
        } catch (error) {
            console.error('[TranscriptSpanLinking] Save link error:', error);
        }
    }
}

// Add pulse animation
if (!document.getElementById('transcript-linking-styles')) {
    const style = document.createElement('style');
    style.id = 'transcript-linking-styles';
    style.textContent = `
        @keyframes pulse {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.7;
            }
        }
    `;
    document.head.appendChild(style);
}

// Initialize global instance
window.TranscriptSpanLinking = TranscriptSpanLinking;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.transcriptSpanLinking) {
            window.transcriptSpanLinking = new TranscriptSpanLinking();
            console.log('[TranscriptSpanLinking] Global instance created');
        }
    });
}
