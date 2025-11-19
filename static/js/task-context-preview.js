/**
 * CROWN⁴.6 Transcript Context Preview
 * Shows spoken context tooltip on hover over tasks with transcript links
 */

class TaskContextPreview {
    constructor() {
        this.tooltip = null;
        this.currentTaskId = null;
        this.cache = new Map(); // Cache fetched contexts
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
        this.tooltip = document.createElement('div');
        this.tooltip.id = 'transcript-context-tooltip';
        this.tooltip.className = 'context-preview-tooltip hidden';
        document.body.appendChild(this.tooltip);
    }

    /**
     * Attach event listeners to task cards
     */
    attachEventListeners() {
        // Use event delegation on the tasks container
        const container = document.getElementById('tasks-list-container');
        if (!container) {
            console.warn('[TaskContextPreview] Tasks container not found');
            return;
        }

        // Mouse events for desktop
        container.addEventListener('mouseenter', (e) => {
            // Don't trigger on menu button or if menu is open
            if (e.target.closest('.task-menu-trigger, .task-menu')) {
                this.cancelPendingTimers();
                return;
            }
            
            const card = e.target.closest('.task-card[data-task-id]');
            if (card && this.shouldShowPreview(card)) {
                this.scheduleShow(card);
            }
        }, true); // Use capture phase

        container.addEventListener('mouseleave', (e) => {
            const card = e.target.closest('.task-card[data-task-id]');
            if (card) {
                this.scheduleHide();
            }
        }, true);

        // Tooltip hover handlers - prevent hiding when hovering tooltip
        this.tooltip.addEventListener('mouseenter', () => {
            // Cancel any pending hide
            if (this.hideTimeout) {
                clearTimeout(this.hideTimeout);
                this.hideTimeout = null;
            }
        });

        this.tooltip.addEventListener('mouseleave', () => {
            // Hide when leaving tooltip
            this.scheduleHide();
        });

        // Touch events for mobile (long-press)
        let touchTimer = null;
        let touchStartTarget = null;
        
        container.addEventListener('touchstart', (e) => {
            // Don't trigger on menu button or if menu is open
            if (e.target.closest('.task-menu-trigger, .task-menu')) {
                this.cancelPendingTimers();
                return;
            }
            
            const card = e.target.closest('.task-card[data-task-id]');
            if (card && this.shouldShowPreview(card)) {
                touchStartTarget = card;
                touchTimer = setTimeout(() => {
                    this.showPreview(card);
                    touchTimer = null;
                }, 500); // 500ms long-press
            }
        }, true);

        container.addEventListener('touchend', (e) => {
            if (touchTimer) {
                clearTimeout(touchTimer);
                touchTimer = null;
            }
            touchStartTarget = null;
            // Don't auto-hide on mobile - user needs to tap close or outside
        }, true);

        // Dismiss on tap outside tooltip (mobile)
        document.addEventListener('touchstart', (e) => {
            if (!this.tooltip.classList.contains('hidden')) {
                if (!this.tooltip.contains(e.target) && !e.target.closest('.task-card[data-task-id]')) {
                    this.hide();
                }
            }
        });

        // Hide on scroll
        window.addEventListener('scroll', () => this.hide(), { passive: true });
    }

    /**
     * Check if preview should be shown for this card
     */
    shouldShowPreview(card) {
        // Don't show if menu is currently open
        if (document.querySelector('.task-menu')) {
            return false;
        }
        
        // Only show for AI-extracted tasks
        return card.dataset.extractedByAi === 'true';
    }

    /**
     * Cancel any pending show/hide timers and hide tooltip
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
        // Also hide any currently displayed tooltip
        this.hide();
    }

    /**
     * Schedule showing the preview after delay
     */
    scheduleShow(card) {
        // Clear any pending hide
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }

        // Show after 800ms hover
        this.showTimeout = setTimeout(() => {
            this.showPreview(card);
        }, 800);
    }

    /**
     * Schedule hiding the preview
     */
    scheduleHide() {
        // Clear any pending show
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
     * Show preview for a task card
     */
    async showPreview(card) {
        const taskId = parseInt(card.dataset.taskId);
        if (!taskId) return;

        this.currentTaskId = taskId;

        // Check cache first
        if (this.cache.has(taskId)) {
            this.renderTooltip(this.cache.get(taskId), card);
            return;
        }

        // Show loading state
        this.renderLoading(card);

        try {
            // Fetch context from API
            const context = await this.fetchContext(taskId);
            
            if (context && this.currentTaskId === taskId) {
                this.cache.set(taskId, context);
                this.renderTooltip(context, card);
            }
        } catch (error) {
            console.error('[TaskContextPreview] Error fetching context:', error);
            this.hide();
        }
    }

    /**
     * Fetch transcript context from API
     */
    async fetchContext(taskId) {
        const response = await fetch(`/api/tasks/${taskId}/transcript-context`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        return data.success ? data.context : null;
    }

    /**
     * Render loading state
     */
    renderLoading(card) {
        this.tooltip.innerHTML = `
            <div class="context-preview-loading">
                <div class="loading-spinner"></div>
                <span>Loading context...</span>
            </div>
        `;
        this.positionTooltip(card);
        this.tooltip.classList.remove('hidden');
    }

    /**
     * Render the tooltip with context
     */
    renderTooltip(context, card) {
        if (!context) {
            this.hide();
            return;
        }

        const { speaker, quote, start_time_formatted, meeting_title, confidence } = context;

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
                        ${confidence ? `<span class="confidence-indicator" title="AI Confidence: ${Math.round(confidence * 100)}%"></span>` : ''}
                    </div>
                ` : ''}
                
                <div class="context-quote">
                    <svg class="quote-icon" width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z"/>
                    </svg>
                    <p>${this.escapeHtml(quote || 'No spoken context available')}</p>
                </div>
                
                <div class="context-actions">
                    <button class="context-jump-btn" data-task-id="${context.task_id}" title="Jump to transcript">
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

        this.positionTooltip(card);
        this.tooltip.classList.remove('hidden');
    }

    /**
     * Position tooltip relative to card
     */
    positionTooltip(card) {
        const cardRect = card.getBoundingClientRect();
        const tooltipRect = this.tooltip.getBoundingClientRect();
        
        // Default: show above the card
        let top = cardRect.top - tooltipRect.height - 8;
        let left = cardRect.left + (cardRect.width / 2) - (tooltipRect.width / 2);

        // If not enough space above, show below
        if (top < 10) {
            top = cardRect.bottom + 8;
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
        this.tooltip.classList.add('hidden');
        this.currentTaskId = null;
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
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('tasks-list-container')) {
        window.taskContextPreview = new TaskContextPreview();
    }
});
