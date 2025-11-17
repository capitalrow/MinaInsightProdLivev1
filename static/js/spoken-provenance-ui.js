/**
 * CROWN⁴.6 Spoken Provenance UI
 * 
 * THE SIGNATURE MINA FEATURE
 * 
 * Shows the "spoken provenance" for every task:
 * - Which meeting it came from
 * - Who said it
 * - What was said (the exact quote)
 * - How confident Mina was in extracting it
 * 
 * This is the one feature that makes Mina Tasks truly different from
 * Linear, Notion, Motion, Asana - NO ONE ELSE does meeting-informed task management
 */

class SpokenProvenanceUI {
    constructor() {
        this.provenanceCache = new Map(); // task_id → provenance_data
        this.activePreview = null;
        
        this.init();
    }
    
    async init() {
        console.log('[Spoken Provenance] Initializing meeting-native task origins...');
        
        // Setup provenance indicators on all tasks
        this.setupProvenanceIndicators();
        
        // Setup hover/long-press preview
        this.setupContextPreview();
        
        // Setup click navigation to transcript
        this.setupTranscriptNavigation();
    }
    
    /**
     * Add provenance indicators to task cards
     * Shows: Meeting name, speaker, confidence badge
     */
    setupProvenanceIndicators() {
        const taskCards = document.querySelectorAll('.task-card');
        
        taskCards.forEach(card => {
            const taskId = parseInt(card.dataset.taskId);
            const meetingId = parseInt(card.dataset.meetingId);
            const extractedByAI = card.dataset.extractedByAi === 'true';
            
            if (!meetingId && !extractedByAI) return;
            
            // Add provenance badge to task metadata
            this.addProvenanceBadge(card, taskId, meetingId, extractedByAI);
        });
        
        console.log(`[Spoken Provenance] Added indicators to ${taskCards.length} tasks`);
    }
    
    /**
     * Add provenance badge showing meeting origin
     */
    addProvenanceBadge(card, taskId, meetingId, extractedByAI) {
        const metadata = card.querySelector('.task-metadata');
        if (!metadata || metadata.querySelector('.provenance-badge')) return;
        
        // Get task data from window.tasks if available
        let taskData = null;
        if (window.tasks) {
            taskData = window.tasks.find(t => t.id === taskId);
        }
        
        const badge = document.createElement('button');
        badge.className = 'provenance-badge';
        badge.dataset.taskId = taskId;
        badge.dataset.meetingId = meetingId;
        
        // Badge content
        const meetingTitle = taskData?.meeting?.title || 'Meeting';
        const speaker = taskData?.extraction_context?.speaker || null;
        const confidence = taskData?.confidence_score || null;
        
        let badgeHTML = `
            <svg class="provenance-icon" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                      d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
            </svg>
            <span class="provenance-text">${this.truncate(meetingTitle, 25)}</span>
        `;
        
        // Add speaker indicator if available
        if (speaker) {
            badgeHTML += `
                <span class="provenance-speaker" title="Suggested by ${speaker}">
                    <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                    </svg>
                </span>
            `;
        }
        
        // Add confidence indicator if AI-extracted
        if (extractedByAI && confidence != null) {
            const confClass = confidence >= 0.8 ? 'high' : confidence >= 0.5 ? 'medium' : 'low';
            badgeHTML += `
                <span class="provenance-confidence ${confClass}" 
                      title="AI confidence: ${Math.round(confidence * 100)}%">
                    ${this.getConfidenceIcon(confClass)}
                </span>
            `;
        }
        
        badge.innerHTML = badgeHTML;
        
        // Click handler - show context preview
        badge.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.showContextPreview(taskId, meetingId, badge);
        });
        
        // Hover handler - prefetch context
        badge.addEventListener('mouseenter', () => {
            this.prefetchContext(taskId);
        });
        
        metadata.appendChild(badge);
    }
    
    /**
     * Get confidence indicator icon
     */
    getConfidenceIcon(level) {
        const icons = {
            high: '<svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
            medium: '<svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg>',
            low: '<svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>'
        };
        return icons[level] || icons.medium;
    }
    
    /**
     * Setup context preview on hover/long-press
     */
    setupContextPreview() {
        let longPressTimer = null;
        let currentCard = null;
        
        document.addEventListener('mousedown', (e) => {
            const card = e.target.closest('.task-card');
            if (!card) return;
            
            currentCard = card;
            const taskId = parseInt(card.dataset.taskId);
            
            // Long press: show context after 500ms
            longPressTimer = setTimeout(() => {
                this.showInlineContextPreview(taskId, card);
            }, 500);
        });
        
        document.addEventListener('mouseup', () => {
            clearTimeout(longPressTimer);
            currentCard = null;
        });
        
        document.addEventListener('mouseleave', () => {
            clearTimeout(longPressTimer);
        });
    }
    
    /**
     * Show inline context preview (5-10 seconds of transcript)
     */
    async showInlineContextPreview(taskId, card) {
        // Check if already showing preview
        if (this.activePreview) {
            this.hideContextPreview();
        }
        
        // Get context data
        const context = await this.fetchContext(taskId);
        if (!context || !context.quote) return;
        
        // Create preview bubble
        const preview = document.createElement('div');
        preview.className = 'context-preview-bubble';
        preview.innerHTML = `
            <div class="context-preview-header">
                <span class="context-preview-label">What was said:</span>
                <button class="context-preview-close">
                    <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <blockquote class="context-preview-quote">
                "${context.quote}"
            </blockquote>
            <div class="context-preview-footer">
                <span class="context-preview-speaker">
                    ${context.speaker || 'Unknown speaker'}
                </span>
                <span class="context-preview-time">
                    ${context.start_time_formatted || '00:00'}
                </span>
            </div>
            <button class="context-preview-jump" data-task-id="${taskId}">
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M13 10V3L4 14h7v7l9-11h-7z"/>
                </svg>
                Jump to full transcript
            </button>
        `;
        
        // Position below card
        const rect = card.getBoundingClientRect();
        preview.style.cssText = `
            position: fixed;
            top: ${rect.bottom + 8}px;
            left: ${rect.left}px;
            max-width: ${rect.width}px;
            z-index: 9999;
        `;
        
        document.body.appendChild(preview);
        this.activePreview = preview;
        
        // Fade in
        requestAnimationFrame(() => {
            preview.classList.add('show');
        });
        
        // Setup close handler
        preview.querySelector('.context-preview-close').addEventListener('click', () => {
            this.hideContextPreview();
        });
        
        // Setup jump handler
        preview.querySelector('.context-preview-jump').addEventListener('click', () => {
            const meetingId = card.dataset.meetingId;
            this.jumpToTranscript(taskId, meetingId, context);
        });
        
        // Auto-hide after 10 seconds
        setTimeout(() => {
            if (this.activePreview === preview) {
                this.hideContextPreview();
            }
        }, 10000);
    }
    
    /**
     * Hide context preview bubble
     */
    hideContextPreview() {
        if (!this.activePreview) return;
        
        this.activePreview.classList.remove('show');
        setTimeout(() => {
            this.activePreview?.remove();
            this.activePreview = null;
        }, 200);
    }
    
    /**
     * Show full context preview modal (on click)
     */
    async showContextPreview(taskId, meetingId, triggerElement) {
        const context = await this.fetchContext(taskId);
        if (!context) {
            this.showToast('No transcript context available for this task', 'info');
            return;
        }
        
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'provenance-modal-overlay';
        modal.innerHTML = `
            <div class="provenance-modal">
                <div class="provenance-modal-header">
                    <div class="provenance-modal-title">
                        <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
                        </svg>
                        Spoken Provenance
                    </div>
                    <button class="provenance-modal-close">
                        <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
                
                <div class="provenance-modal-content">
                    <div class="provenance-section">
                        <label class="provenance-label">From Meeting:</label>
                        <div class="provenance-meeting-name">${context.meeting_title || 'Untitled Meeting'}</div>
                    </div>
                    
                    <div class="provenance-section">
                        <label class="provenance-label">Suggested by:</label>
                        <div class="provenance-speaker-info">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                            </svg>
                            ${context.speaker || 'Unknown speaker'}
                        </div>
                    </div>
                    
                    <div class="provenance-section">
                        <label class="provenance-label">What was said:</label>
                        <blockquote class="provenance-quote">
                            "${context.quote}"
                        </blockquote>
                        ${context.full_segments && context.full_segments.length > 0 ? `
                            <div class="provenance-full-context">
                                <div class="provenance-full-label">Full context:</div>
                                ${context.full_segments.map(seg => `<p>${seg}</p>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                    
                    ${context.confidence != null ? `
                        <div class="provenance-section">
                            <label class="provenance-label">AI Confidence:</label>
                            <div class="provenance-confidence-bar">
                                <div class="provenance-confidence-fill" 
                                     style="width: ${context.confidence * 100}%"
                                     data-confidence="${context.confidence}">
                                </div>
                                <span class="provenance-confidence-text">
                                    ${Math.round(context.confidence * 100)}%
                                </span>
                            </div>
                        </div>
                    ` : ''}
                    
                    <div class="provenance-section">
                        <label class="provenance-label">Timestamp:</label>
                        <div class="provenance-timestamp">
                            ${context.start_time_formatted || '00:00'}
                        </div>
                    </div>
                </div>
                
                <div class="provenance-modal-footer">
                    <button class="btn-secondary" data-action="close">Close</button>
                    <button class="btn-primary" data-action="jump">
                        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                  d="M13 10V3L4 14h7v7l9-11h-7z"/>
                        </svg>
                        Jump to Transcript
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Fade in
        requestAnimationFrame(() => {
            modal.classList.add('show');
        });
        
        // Setup handlers
        modal.querySelector('[data-action="close"]').addEventListener('click', () => {
            this.closeModal(modal);
        });
        
        modal.querySelector('.provenance-modal-close').addEventListener('click', () => {
            this.closeModal(modal);
        });
        
        modal.querySelector('[data-action="jump"]').addEventListener('click', () => {
            this.jumpToTranscript(taskId, meetingId, context);
            this.closeModal(modal);
        });
        
        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal(modal);
            }
        });
    }
    
    /**
     * Close provenance modal
     */
    closeModal(modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.remove();
        }, 200);
    }
    
    /**
     * Setup transcript navigation
     */
    setupTranscriptNavigation() {
        document.addEventListener('click', (e) => {
            const jumpBtn = e.target.closest('[data-action="jump-to-transcript"]');
            if (!jumpBtn) return;
            
            const taskId = parseInt(jumpBtn.dataset.taskId);
            const meetingId = parseInt(jumpBtn.dataset.meetingId);
            
            this.jumpToTranscript(taskId, meetingId);
        });
    }
    
    /**
     * Jump to transcript moment
     */
    async jumpToTranscript(taskId, meetingId, context = null) {
        if (!context) {
            context = await this.fetchContext(taskId);
        }
        
        if (!context || !context.start_ms) {
            this.showToast('Cannot navigate to transcript - timing data unavailable', 'error');
            return;
        }
        
        // Navigate to meeting page with timestamp
        const url = `/dashboard/meetings/${meetingId}?t=${context.start_ms}&highlight=${taskId}`;
        window.location.href = url;
    }
    
    /**
     * Fetch context data for a task
     */
    async fetchContext(taskId) {
        // Check cache first
        if (this.provenanceCache.has(taskId)) {
            return this.provenanceCache.get(taskId);
        }
        
        try {
            const response = await fetch(`/api/tasks/${taskId}/transcript-context`);
            const data = await response.json();
            
            if (data.success && data.context) {
                this.provenanceCache.set(taskId, data.context);
                return data.context;
            }
            
            return null;
        } catch (error) {
            console.error('[Provenance] Failed to fetch context:', error);
            return null;
        }
    }
    
    /**
     * Prefetch context for upcoming interaction
     */
    async prefetchContext(taskId) {
        if (this.provenanceCache.has(taskId)) return;
        
        // Prefetch in background
        this.fetchContext(taskId);
    }
    
    // Utilities
    truncate(str, maxLen) {
        if (!str || str.length <= maxLen) return str;
        return str.substring(0, maxLen - 3) + '...';
    }
    
    showToast(message, type = 'info') {
        console.log(`[Toast ${type}]`, message);
        // TODO: Integrate with toast notification system
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.spokenProvenanceUI = new SpokenProvenanceUI();
    });
} else {
    window.spokenProvenanceUI = new SpokenProvenanceUI();
}
