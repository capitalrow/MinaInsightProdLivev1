/**
 * CROWN⁴.6 Task Transcript Navigation
 * Implements "Jump to Transcript" functionality - Mina's signature meeting-native feature
 * Navigates from task to the exact transcript moment where it was mentioned
 */

class TaskTranscriptNavigation {
    constructor() {
        this.init();
    }

    init() {
        console.log('[TaskTranscriptNavigation] Initializing...');

        // Listen for "jump-to-transcript" actions from task menus
        document.addEventListener('click', (e) => {
            const jumpBtn = e.target.closest('[data-action="jump-to-transcript"], .jump-to-transcript-btn');
            if (!jumpBtn) return;

            e.preventDefault();

            const taskId = jumpBtn.dataset.taskId
                || jumpBtn.closest('[data-task-id]')?.dataset.taskId
                || jumpBtn.closest('.task-menu')?.dataset.taskId;

            if (!taskId) return;

            this.emitJumpEvent(taskId);
            this.jumpToTranscript(taskId);
        });

        console.log('[TaskTranscriptNavigation] Initialized successfully');
    }

    emitJumpEvent(taskId) {
        document.dispatchEvent(new CustomEvent('task:jump-to-transcript', {
            detail: { taskId }
        }));

        if (window.eventSequencerBridge?.recordEvent) {
            try {
                window.eventSequencerBridge.recordEvent('task:jump-to-transcript', { taskId });
            } catch (err) {
                console.warn('[TaskTranscriptNavigation] Unable to forward jump event to sequencer bridge', err);
            }
        }
    }

    /**
     * Jump to the transcript moment where this task was mentioned
     * @param {string|number} taskId - Task ID
     */
    async jumpToTranscript(taskId) {
        try {
            console.log(`[TaskTranscriptNavigation] Jumping to transcript for task: ${taskId}`);
            
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
                return;
            }
            
            // Check if meeting_id exists
            if (!task.meeting_id) {
                this.showToast('❌ No meeting associated with this task', 'error');
                return;
            }
            
            // Navigate to session/meeting page with timestamp anchor
            const transcriptSpan = task.transcript_span;
            const meetingId = task.meeting_id;
            
            // Build URL with timestamp parameter for auto-scroll
            const targetUrl = `/meetings/${meetingId}?highlight_time=${transcriptSpan.start_ms}`;
            
            console.log(`[TaskTranscriptNavigation] Navigating to: ${targetUrl}`);
            
            // Show loading toast
            this.showToast('📍 Jumping to transcript moment...', 'info', 1500);
            
            // Navigate after brief delay
            setTimeout(() => {
                window.location.href = targetUrl;
            }, 300);
            
            // Record telemetry
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_jump_to_transcript', 1, {
                    taskId,
                    meetingId,
                    hasTranscriptSpan: true
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
