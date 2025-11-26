/**
 * CROWN⁴.6 Task Transcript Navigation
 * Implements "Jump to Transcript" functionality - Mina's signature meeting-native feature
 * Navigates from task to the exact transcript moment where it was mentioned
 */

class TaskTranscriptNavigation {
    constructor() {
        this.returnStateKey = 'task:return-state';
        this.pendingNavigation = null;
        this.init();
    }

    init() {
        console.log('[TaskTranscriptNavigation] Initializing...');

        // Listen for "jump-to-transcript" actions from task menus
        document.addEventListener('click', (e) => {
            const jumpBtn = e.target.closest('[data-action="jump-to-transcript"]');
            if (!jumpBtn) return;

            e.preventDefault();
            this.handleJumpClick(jumpBtn);
        });

        console.log('[TaskTranscriptNavigation] Initialized successfully');
    }

    handleJumpClick(jumpBtn) {
        const taskId = jumpBtn.dataset.taskId
            || jumpBtn.closest('[data-task-id]')?.dataset.taskId
            || jumpBtn.closest('.task-menu')?.dataset.taskId;

        if (!taskId) {
            console.warn('[TaskTranscriptNavigation] Missing taskId on jump action');
            this.showToast('❌ Unable to jump to transcript (missing task id)', 'error');
            return;
        }

        const optimisticMeetingId = jumpBtn.dataset.meetingId
            || jumpBtn.closest('[data-meeting-id]')?.dataset.meetingId;

        const optimisticSpan = this.parseSpanFromDataset(jumpBtn.dataset, jumpBtn.closest('[data-transcript-start-ms]'));

        this.saveReturnState(taskId);
        this.jumpToTranscript(taskId, {
            meetingId: optimisticMeetingId,
            transcriptSpan: optimisticSpan
        });
    }

    parseSpanFromDataset(dataset = {}, fallbackElement = null) {
        const startMs = dataset.transcriptStartMs
            || dataset.transcriptSpanStart
            || fallbackElement?.dataset?.transcriptStartMs;
        const endMs = dataset.transcriptEndMs
            || dataset.transcriptSpanEnd
            || fallbackElement?.dataset?.transcriptEndMs;

        if (startMs === undefined || startMs === null) return null;

        return {
            start_ms: Number(startMs),
            end_ms: endMs !== undefined && endMs !== null ? Number(endMs) : undefined
        };
    }

    saveReturnState(taskId) {
        const state = {
            taskId,
            path: window.location.pathname + window.location.search + window.location.hash,
            scrollY: window.scrollY,
            captured_at: Date.now()
        };

        try {
            sessionStorage.setItem(this.returnStateKey, JSON.stringify(state));
            if (history?.replaceState) {
                history.replaceState({ ...history.state, taskReturnState: state }, document.title);
            }
        } catch (err) {
            console.warn('[TaskTranscriptNavigation] Unable to persist return state', err);
        }
    }

    /**
     * Jump to the transcript moment where this task was mentioned
     * @param {string|number} taskId - Task ID
     * @param {Object} optimisticContext - initial meeting/span hint from DOM
     */
    async jumpToTranscript(taskId, optimisticContext = {}) {
        try {
            console.log(`[TaskTranscriptNavigation] Jumping to transcript for task: ${taskId}`);

            this.showToast('📍 Preparing transcript jump...', 'info', 1200);

            const resolved = await this.resolveNavigationTarget(taskId, optimisticContext);
            if (!resolved) return;

            const { meetingId, transcriptSpan, source } = resolved;
            const targetUrl = this.buildTranscriptUrl(meetingId, transcriptSpan);

            console.log(`[TaskTranscriptNavigation] Navigating to: ${targetUrl}`);

            this.pendingNavigation = { targetUrl, reconciledWith: source };
            this.showToast('⚡ Jumping to transcript...', 'success', 1800);

            setTimeout(() => {
                window.location.href = targetUrl;
            }, 200);

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_jump_to_transcript', 1, {
                    taskId,
                    meetingId,
                    hasTranscriptSpan: Boolean(transcriptSpan?.start_ms),
                    reconciledWith: source
                });
            }

        } catch (error) {
            console.error('[TaskTranscriptNavigation] Error:', error);
            this.showToast('❌ Failed to jump to transcript', 'error');
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_jump_to_transcript_error', 1, {
                    taskId,
                    error: error.message
                });
            }
        }
    }

    async resolveNavigationTarget(taskId, optimisticContext = {}) {
        const optimisticMeetingId = optimisticContext.meetingId;
        const optimisticSpan = optimisticContext.transcriptSpan;

        if (optimisticMeetingId && optimisticSpan?.start_ms !== undefined) {
            return {
                meetingId: optimisticMeetingId,
                transcriptSpan: optimisticSpan,
                source: 'dom-optimistic'
            };
        }

        // Fetch full task details including transcript_span
        const response = await fetch(`/api/tasks/${taskId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch task details');
        }

        const data = await response.json();
        if (!data.success || !data.task) {
            throw new Error('Task not found');
        }

        const task = data.task;

        // Check if transcript_span exists (explicit null/undefined check, not falsy)
        if (!task.transcript_span || task.transcript_span.start_ms === null || task.transcript_span.start_ms === undefined) {
            this.showNoTranscriptToast(task);
            return null;
        }

        // Check if meeting_id exists
        if (!task.meeting_id) {
            this.showToast('❌ No meeting associated with this task', 'error');
            return null;
        }

        if (optimisticMeetingId && optimisticSpan?.start_ms !== undefined) {
            if (optimisticMeetingId !== task.meeting_id || optimisticSpan.start_ms !== task.transcript_span.start_ms) {
                this.showToast('ℹ️ Transcript location updated from server', 'info', 2000);
            }
        }

        return {
            meetingId: task.meeting_id,
            transcriptSpan: task.transcript_span,
            source: 'server'
        };
    }

    buildTranscriptUrl(meetingId, transcriptSpan = {}) {
        const url = new URL(`/meetings/${meetingId}`, window.location.origin);
        if (transcriptSpan.start_ms !== undefined) {
            url.searchParams.set('highlight_time', transcriptSpan.start_ms);
        }
        if (transcriptSpan.end_ms !== undefined) {
            url.searchParams.set('highlight_end', transcriptSpan.end_ms);
        }

        const returnState = sessionStorage.getItem(this.returnStateKey);
        if (returnState) {
            url.searchParams.set('return_state', btoa(encodeURIComponent(returnState)));
        }

        return url.pathname + url.search;
    }

    /**
     * Show toast when task has no transcript link
     * @param {Object} task - Task object
     */
    showNoTranscriptToast(task) {
        const message = task.extracted_by_ai 
            ? '📝 This task was created manually - no transcript available'
            : '📝 Transcript not available for this task';
        
        this.showToast(message, 'warning', 3000);
    }

    /**
     * Show a toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type (info, success, error, warning)
     * @param {number} duration - Duration in ms
     */
    showToast(message, type = 'info', duration = 2000) {
        if (window.toastManager && typeof window.toastManager.show === 'function') {
            window.toastManager.show(message, type, duration);
        } else {
            console.log(`[Toast] ${message}`);
        }
    }

    /**
     * Get transcript context for a task (for preview tooltips)
     * @param {string|number} taskId - Task ID
     * @returns {Promise<Object>} Transcript context
     */
    async getTranscriptContext(taskId) {
        try {
            const response = await fetch(`/api/tasks/${taskId}/transcript-context`);
            if (!response.ok) {
                return null;
            }
            
            const data = await response.json();
            return data.success ? data.context : null;
        } catch (error) {
            console.error('[TaskTranscriptNavigation] Error fetching context:', error);
            return null;
        }
    }
}

// Global instance
window.taskTranscriptNavigation = new TaskTranscriptNavigation();
