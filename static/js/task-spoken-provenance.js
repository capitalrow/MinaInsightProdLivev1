/**
 * CROWN⁴.6 Spoken Provenance UI
 * Server-rendered badges with zero-fetch context preview
 * This is Mina's unique differentiator - showing "who said what, when"
 * 
 * ARCHITECTURE NOTE:
 * All provenance data is server-rendered in task_card_macro.html with full context
 * embedded in data attributes. No client-side fetching or dynamic enhancement needed.
 */

class TaskSpokenProvenance {
    constructor() {
        console.log('[TaskSpokenProvenance] Server-rendered provenance active (zero fetches)');
    }
}

// Global instance
window.taskSpokenProvenance = new TaskSpokenProvenance();

/**
 * CROWN⁴.6: Context Preview Handler
 * Shows transcript context bubble when user hovers/clicks on provenance badge
 */
class ContextPreviewHandler {
    constructor() {
        this.activePreview = null;
        this.hoverTimeout = null;
        this.HOVER_DELAY_MS = 800; // Show preview after 800ms hover
        this.init();
    }

    init() {
        console.log('[ContextPreview] Initializing handlers');
        
        const tasksContainer = document.getElementById('tasks-list-container');
        if (!tasksContainer) {
            console.warn('[ContextPreview] Tasks container not found');
            return;
        }
        
        // Handle click on provenance badge (mobile and desktop)
        tasksContainer.addEventListener('click', (e) => {
            const badge = e.target.closest('.provenance-badge');
            if (!badge) return;
            
            e.preventDefault();
            e.stopPropagation();
            
            const taskId = badge.dataset.taskId;
            this.showContextPreview(taskId, badge);
        });
        
        // Handle hover on provenance badge (desktop only)
        if (!this.isTouchDevice()) {
            tasksContainer.addEventListener('mouseenter', (e) => {
                const badge = e.target.closest('.provenance-badge');
                if (!badge) return;
                
                const taskId = badge.dataset.taskId;
                
                // Clear any existing hover timeout
                if (this.hoverTimeout) {
                    clearTimeout(this.hoverTimeout);
                }
                
                // Show preview after delay
                this.hoverTimeout = setTimeout(() => {
                    this.showContextPreview(taskId, badge);
                }, this.HOVER_DELAY_MS);
                
            }, true);
            
            tasksContainer.addEventListener('mouseleave', (e) => {
                const badge = e.target.closest('.provenance-badge');
                if (!badge) return;
                
                // Clear hover timeout
                if (this.hoverTimeout) {
                    clearTimeout(this.hoverTimeout);
                    this.hoverTimeout = null;
                }
                
                // Don't hide preview immediately - let user move to it
                setTimeout(() => {
                    if (this.activePreview && !this.activePreview.matches(':hover')) {
                        this.hideContextPreview();
                    }
                }, 200);
                
            }, true);
        }
        
        // Close preview when clicking outside
        document.addEventListener('click', (e) => {
            if (this.activePreview && !e.target.closest('.context-preview-bubble') && !e.target.closest('.provenance-badge')) {
                this.hideContextPreview();
            }
        });
        
        console.log('[ContextPreview] ✓ Handlers initialized');
    }
    
    async showContextPreview(taskId, anchorElement) {
        if (!taskId) return;
        
        // Hide any existing preview first to prevent stacking
        this.hideContextPreview();
        
        // CROWN⁴.6: Use server-hydrated context data (zero fetches)
        const hasContext = anchorElement.dataset.hasContext === 'true';
        if (!hasContext) {
            console.log('[ContextPreview] Task has no context');
            return;
        }
        
        try {
            // Extract context from data attributes (server-rendered, no fetch needed)
            const context = {
                task_id: taskId,
                quote: anchorElement.dataset.contextQuote || '',
                speaker: anchorElement.dataset.contextSpeaker || 'Unknown',
                start_ms: parseInt(anchorElement.dataset.contextStartMs) || 0,
                meeting_id: anchorElement.dataset.meetingId,
                meeting_title: anchorElement.dataset.meetingTitle || 'Meeting',
                confidence: parseFloat(anchorElement.dataset.confidence) || 0,
                start_time_formatted: this.formatTimestamp(parseInt(anchorElement.dataset.contextStartMs) || 0)
            };
            
            console.log('[ContextPreview] Using server-hydrated context (zero fetch)');

            
            // Create preview bubble
            const bubble = this.createBubble(context);
            
            // Position relative to badge
            this.positionBubble(bubble, anchorElement);
            
            // Add to DOM
            document.body.appendChild(bubble);
            
            // Trigger show animation
            requestAnimationFrame(() => {
                bubble.classList.add('show');
            });
            
            // Store reference
            this.activePreview = bubble;
            
            // Track interaction
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordEvent('task_context_preview_shown', {
                    task_id: taskId,
                    has_speaker: !!context.speaker,
                    confidence: context.confidence
                });
            }
            
        } catch (error) {
            console.error('[ContextPreview] Failed to load context:', error);
        }
    }
    
    hideContextPreview() {
        if (!this.activePreview) return;
        
        this.activePreview.classList.remove('show');
        
        setTimeout(() => {
            if (this.activePreview && this.activePreview.parentNode) {
                this.activePreview.remove();
            }
            this.activePreview = null;
        }, 200);
    }
    
    createBubble(context) {
        const bubble = document.createElement('div');
        bubble.className = 'context-preview-bubble';
        
        const speakerDisplay = context.speaker || 'Unknown Speaker';
        const timeDisplay = context.start_time_formatted || '--:--';
        const quoteDisplay = context.quote || 'No transcript available';
        
        bubble.innerHTML = `
            <div class="context-preview-header">
                <span class="context-preview-label">Meeting Context</span>
                <button class="context-preview-close" aria-label="Close">
                    <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            
            <blockquote class="context-preview-quote">
                "${this.escapeHtml(quoteDisplay)}"
            </blockquote>
            
            <div class="context-preview-footer">
                <div class="context-preview-speaker">
                    <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                    </svg>
                    ${this.escapeHtml(speakerDisplay)}
                </div>
                <span class="context-preview-time">${this.escapeHtml(timeDisplay)}</span>
            </div>
            
            ${context.meeting_id ? `
            <button class="context-preview-jump" data-meeting-id="${context.meeting_id}" data-start-ms="${context.start_ms}">
                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                </svg>
                Jump to Full Transcript
            </button>
            ` : ''}
        `;
        
        // Handle close button
        const closeBtn = bubble.querySelector('.context-preview-close');
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.hideContextPreview();
        });
        
        // Handle jump to transcript
        const jumpBtn = bubble.querySelector('.context-preview-jump');
        if (jumpBtn) {
            jumpBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const meetingId = jumpBtn.dataset.meetingId;
                const startMs = jumpBtn.dataset.startMs;
                
                if (meetingId && startMs) {
                    window.location.href = `/meetings/${meetingId}/transcript?t=${startMs}`;
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordEvent('task_jump_to_transcript', {
                            task_id: context.task_id,
                            meeting_id: meetingId,
                            start_ms: startMs
                        });
                    }
                }
            });
        }
        
        // Prevent bubble from closing when clicking inside
        bubble.addEventListener('click', (e) => {
            e.stopPropagation();
        });
        
        return bubble;
    }
    
    positionBubble(bubble, anchor) {
        const rect = anchor.getBoundingClientRect();
        const bubbleWidth = 360;
        const padding = 12;
        
        bubble.style.position = 'fixed';
        bubble.style.top = `${rect.bottom + 8}px`;
        bubble.style.maxWidth = `${bubbleWidth}px`;
        bubble.style.zIndex = '10000';
        
        const centerX = rect.left + (rect.width / 2) - (bubbleWidth / 2);
        const minX = padding;
        const maxX = window.innerWidth - bubbleWidth - padding;
        
        const left = Math.max(minX, Math.min(maxX, centerX));
        bubble.style.left = `${left}px`;
        
        // Check if bubble would overflow bottom
        const bubbleRect = bubble.getBoundingClientRect();
        if (bubbleRect.bottom > window.innerHeight - padding) {
            bubble.style.top = `${rect.top - bubbleRect.height - 8}px`;
        }
    }
    
    isTouchDevice() {
        return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    }
    
    formatTimestamp(ms) {
        if (!ms) return '00:00';
        const totalSeconds = Math.floor(ms / 1000);
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize context preview handler
window.contextPreviewHandler = new ContextPreviewHandler();
