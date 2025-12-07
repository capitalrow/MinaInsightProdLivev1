/**
 * CROWN⁴.6 Transcript Context Preview
 * Shows spoken context tooltip on hover over provenance badges
 * Uses embedded data attributes for instant display (no API call needed)
 */

class TaskContextPreview {
    constructor() {
        this.tooltip = null;
        this.currentBadge = null;
        this.hideTimeout = null;
        this.showTimeout = null;
        this.init();
    }

    init() {
        console.log('[TaskContextPreview] Initializing...');
        this.createTooltip();
        this.attachEventListeners();
    }

    /**
     * Create the tooltip element
     */
    createTooltip() {
        // Remove existing tooltip if present
        const existing = document.getElementById('transcript-context-tooltip');
        if (existing) existing.remove();
        
        this.tooltip = document.createElement('div');
        this.tooltip.id = 'transcript-context-tooltip';
        this.tooltip.className = 'context-preview-tooltip hidden';
        document.body.appendChild(this.tooltip);
    }

    /**
     * Attach event listeners to provenance badges
     */
    attachEventListeners() {
        // Use event delegation on the tasks container
        const container = document.getElementById('tasks-list-container');
        if (!container) {
            console.warn('[TaskContextPreview] Tasks container not found');
            return;
        }

        // Mouse events for desktop - target provenance badges specifically
        container.addEventListener('mouseenter', (e) => {
            const badge = e.target.closest('.provenance-compact[data-action="show-context-preview"]');
            if (badge && badge.dataset.hasContext === 'true') {
                this.scheduleShow(badge);
            }
        }, true);

        container.addEventListener('mouseleave', (e) => {
            const badge = e.target.closest('.provenance-compact[data-action="show-context-preview"]');
            if (badge) {
                this.scheduleHide();
            }
        }, true);

        // Click handler for mobile and alternative interaction
        container.addEventListener('click', (e) => {
            const badge = e.target.closest('.provenance-compact[data-action="show-context-preview"]');
            if (badge && badge.dataset.hasContext === 'true') {
                e.preventDefault();
                e.stopPropagation();
                
                // Toggle tooltip on click
                if (this.currentBadge === badge && !this.tooltip.classList.contains('hidden')) {
                    this.hide();
                } else {
                    this.showPreview(badge);
                }
            }
        });

        // Tooltip hover handlers - prevent hiding when hovering tooltip
        this.tooltip.addEventListener('mouseenter', () => {
            if (this.hideTimeout) {
                clearTimeout(this.hideTimeout);
                this.hideTimeout = null;
            }
        });

        this.tooltip.addEventListener('mouseleave', () => {
            this.scheduleHide();
        });

        // Touch events for mobile (long-press)
        let touchTimer = null;
        
        container.addEventListener('touchstart', (e) => {
            const badge = e.target.closest('.provenance-compact[data-action="show-context-preview"]');
            if (badge && badge.dataset.hasContext === 'true') {
                touchTimer = setTimeout(() => {
                    this.showPreview(badge);
                    touchTimer = null;
                }, 400);
            }
        }, { passive: true });

        container.addEventListener('touchend', () => {
            if (touchTimer) {
                clearTimeout(touchTimer);
                touchTimer = null;
            }
        }, { passive: true });

        container.addEventListener('touchmove', () => {
            if (touchTimer) {
                clearTimeout(touchTimer);
                touchTimer = null;
            }
        }, { passive: true });

        // Dismiss on tap outside tooltip (mobile)
        document.addEventListener('touchstart', (e) => {
            if (!this.tooltip.classList.contains('hidden')) {
                if (!this.tooltip.contains(e.target) && !e.target.closest('.provenance-compact')) {
                    this.hide();
                }
            }
        }, { passive: true });

        // Dismiss on click outside
        document.addEventListener('click', (e) => {
            if (!this.tooltip.classList.contains('hidden')) {
                if (!this.tooltip.contains(e.target) && !e.target.closest('.provenance-compact')) {
                    this.hide();
                }
            }
        });

        // Hide on scroll
        window.addEventListener('scroll', () => this.hide(), { passive: true });
        
        // Hide on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.tooltip.classList.contains('hidden')) {
                this.hide();
            }
        });
    }

    /**
     * Cancel any pending timers
     */
    cancelPendingTimers() {
        if (this.showTimeout) {
            clearTimeout(this.showTimeout);
            this.showTimeout = null;
        }
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }
    }

    /**
     * Schedule showing the preview after short delay
     */
    scheduleShow(badge) {
        this.cancelPendingTimers();
        
        // Show after 300ms hover (faster for specific element)
        this.showTimeout = setTimeout(() => {
            this.showPreview(badge);
        }, 300);
    }

    /**
     * Schedule hiding the preview
     */
    scheduleHide() {
        if (this.showTimeout) {
            clearTimeout(this.showTimeout);
            this.showTimeout = null;
        }

        // Hide after 200ms delay
        this.hideTimeout = setTimeout(() => {
            this.hide();
        }, 200);
    }

    /**
     * Show preview for a provenance badge using embedded data
     */
    showPreview(badge) {
        this.cancelPendingTimers();
        this.currentBadge = badge;

        // Extract context from data attributes (instant, no API call)
        const context = {
            task_id: badge.dataset.taskId,
            meeting_id: badge.dataset.meetingId,
            meeting_title: badge.dataset.meetingTitle || 'Unknown Meeting',
            speaker: badge.dataset.contextSpeaker || '',
            quote: this.decodeHtml(badge.dataset.contextQuote) || '',
            confidence: parseFloat(badge.dataset.confidence) || 0,
            start_ms: parseInt(badge.dataset.contextStartMs) || 0
        };

        // Format timestamp
        if (context.start_ms > 0) {
            const totalSeconds = Math.floor(context.start_ms / 1000);
            const minutes = Math.floor(totalSeconds / 60);
            const seconds = totalSeconds % 60;
            context.start_time_formatted = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }

        this.renderTooltip(context, badge);
    }

    /**
     * Decode HTML entities in data attributes
     */
    decodeHtml(html) {
        if (!html) return '';
        const txt = document.createElement('textarea');
        txt.innerHTML = html;
        return txt.value;
    }

    /**
     * Render the tooltip with context
     */
    renderTooltip(context, badge) {
        const { speaker, quote, start_time_formatted, meeting_title, confidence, task_id } = context;

        // Build tooltip HTML
        this.tooltip.innerHTML = `
            <button class="context-close-btn" aria-label="Close" title="Close">
                <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
            </button>
            <div class="context-preview-content">
                <div class="context-preview-header">
                    <div class="context-meeting-badge">
                        <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M20 6h-2.18c.11-.31.18-.65.18-1 0-1.66-1.34-3-3-3-1.05 0-1.96.54-2.5 1.35l-.5.67-.5-.68C10.96 2.54 10.05 2 9 2 7.34 2 6 3.34 6 5c0 .35.07.69.18 1H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-5-2c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zM9 4c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm11 15H4v-2h16v2zm0-5H4V8h5.08L7 10.83 8.62 12 11 8.76l1-1.36 1 1.36L15.38 12 17 10.83 14.92 8H20v6z"/>
                        </svg>
                        <span>${this.escapeHtml(this.truncate(meeting_title, 25))}</span>
                    </div>
                    ${start_time_formatted ? `
                        <div class="context-timestamp">
                            <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/>
                            </svg>
                            <span>${start_time_formatted}</span>
                        </div>
                    ` : ''}
                </div>
                
                ${speaker ? `
                    <div class="context-speaker">
                        <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                        </svg>
                        <span>${this.escapeHtml(speaker)}</span>
                        ${confidence >= 0.8 ? `<span class="confidence-indicator" title="AI Confidence: ${Math.round(confidence * 100)}%"></span>` : ''}
                    </div>
                ` : ''}
                
                <div class="context-quote">
                    <svg class="quote-icon" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z"/>
                    </svg>
                    <p>${this.escapeHtml(quote || 'No spoken context available')}</p>
                </div>
                
                <div class="context-actions">
                    <button class="context-jump-btn" data-task-id="${task_id}" title="Jump to transcript">
                        <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
                        </svg>
                        <span>Jump to moment</span>
                    </button>
                </div>
            </div>
        `;

        // Attach close button handler
        const closeBtn = this.tooltip.querySelector('.context-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.hide();
            });
        }

        // Attach jump button handler
        const jumpBtn = this.tooltip.querySelector('.context-jump-btn');
        if (jumpBtn) {
            jumpBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const taskId = e.currentTarget.dataset.taskId;
                if (window.taskTranscriptNavigation) {
                    window.taskTranscriptNavigation.navigateToTranscript(taskId);
                }
                this.hide();
            });
        }

        this.positionTooltip(badge);
        this.tooltip.classList.remove('hidden');
    }

    /**
     * Position tooltip relative to badge
     */
    positionTooltip(badge) {
        const badgeRect = badge.getBoundingClientRect();
        
        // Need to show tooltip first (hidden but in DOM) to get its dimensions
        this.tooltip.style.visibility = 'hidden';
        this.tooltip.classList.remove('hidden');
        const tooltipRect = this.tooltip.getBoundingClientRect();
        this.tooltip.style.visibility = '';
        
        // Default: show above the badge
        let top = badgeRect.top - tooltipRect.height - 8;
        let left = badgeRect.left + (badgeRect.width / 2) - (tooltipRect.width / 2);

        // If not enough space above, show below
        if (top < 10) {
            top = badgeRect.bottom + 8;
            this.tooltip.classList.add('below');
        } else {
            this.tooltip.classList.remove('below');
        }

        // Keep within viewport horizontally
        const viewportWidth = window.innerWidth;
        if (left < 10) {
            left = 10;
        } else if (left + tooltipRect.width > viewportWidth - 10) {
            left = viewportWidth - tooltipRect.width - 10;
        }

        this.tooltip.style.top = `${top}px`;
        this.tooltip.style.left = `${left}px`;
    }

    /**
     * Hide the tooltip
     */
    hide() {
        this.cancelPendingTimers();
        this.tooltip.classList.add('hidden');
        this.currentBadge = null;
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
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Reinitialize after dynamic content updates
     */
    reinit() {
        console.log('[TaskContextPreview] Reinitializing...');
        this.hide();
        this.createTooltip();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('tasks-list-container')) {
        window.taskContextPreview = new TaskContextPreview();
    }
});

// Also expose for dynamic reinitialization
window.TaskContextPreview = TaskContextPreview;
