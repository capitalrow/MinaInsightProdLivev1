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
        
        // Listen for "jump-to-transcript" actions from task cards and menus
        document.addEventListener('click', (e) => {
            const jumpBtn = e.target.closest('[data-action="jump-to-transcript"]');
            if (jumpBtn) {
                e.preventDefault();
                // FIX: Check button's own data-task-id first (for inline task card buttons),
                // then fall back to parent .task-menu (for dropdown menu items),
                // then fall back to parent .task-card (for nested elements)
                const taskId = jumpBtn.dataset.taskId 
                    || jumpBtn.closest('.task-menu')?.dataset.taskId
                    || jumpBtn.closest('.task-card')?.dataset.taskId;
                if (taskId) {
                    this.jumpToTranscript(taskId);
                } else {
                    console.error('[TaskTranscriptNavigation] No taskId found for jump button');
                }
            }
        });
        
        console.log('[TaskTranscriptNavigation] Initialized successfully');
    }

    /**
     * Jump to the transcript moment where this task was mentioned
     * CROWN⁴.7: Uses session_external_id from task API for reliable navigation
     * @param {string|number} taskId - Task ID
     */
    async jumpToTranscript(taskId) {
        try {
            console.log(`[TaskTranscriptNavigation] Jumping to transcript for task: ${taskId}`);
            
            // Fetch full task details including transcript_span and session_external_id
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
            
            // Check if we have session or meeting for navigation
            if (!task.session_external_id && !task.meeting_id) {
                this.showToast('❌ No meeting associated with this task', 'error');
                return;
            }
            
            // Navigate to session/meeting page with timestamp anchor
            const transcriptSpan = task.transcript_span;
            
            // CROWN⁴.7: Use session_external_id directly for /sessions/refined route
            let targetUrl;
            if (task.session_external_id) {
                targetUrl = `/sessions/${task.session_external_id}/refined?highlight_time=${transcriptSpan.start_ms}#transcript`;
                console.log(`[TaskTranscriptNavigation] Using session_external_id: ${task.session_external_id}`);
            } else {
                // Fallback to meeting route
                targetUrl = `/meetings/${task.meeting_id}?highlight_time=${transcriptSpan.start_ms}`;
                console.log(`[TaskTranscriptNavigation] Falling back to meeting route: ${task.meeting_id}`);
            }
            
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
                    sessionId: task.session_external_id,
                    meetingId: task.meeting_id,
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
