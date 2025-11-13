/**
 * CROWN⁴.6 Spoken Provenance UI
 * Displays meeting context, speaker, and spoken origin for tasks
 * This is Mina's unique differentiator - showing "who said what, when"
 */

class TaskSpokenProvenance {
    constructor() {
        this.init();
    }

    init() {
        console.log('[TaskSpokenProvenance] Initializing...');
        
        // Enhance all task cards with spoken provenance on page load
        this.enhanceAllTaskCards();
        
        // Listen for new tasks being added dynamically
        this.observeTaskCards();
        
        console.log('[TaskSpokenProvenance] Initialized successfully');
    }

    /**
     * Enhance all existing task cards with spoken provenance UI
     */
    enhanceAllTaskCards() {
        const taskCards = document.querySelectorAll('.task-card[data-task-id]');
        taskCards.forEach(card => this.enhanceTaskCard(card));
    }

    /**
     * Observe DOM for dynamically added task cards
     * CROWN⁴.6: Fixed to observe nested insertions (subtree: true)
     */
    observeTaskCards() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) {
                        // Check if the node itself is a task card
                        if (node.classList && node.classList.contains('task-card')) {
                            this.enhanceTaskCard(node);
                        }
                        // Also check descendants (nested task cards)
                        if (node.querySelectorAll) {
                            const nestedCards = node.querySelectorAll('.task-card');
                            nestedCards.forEach(card => this.enhanceTaskCard(card));
                        }
                    }
                });
            });
        });

        const container = document.getElementById('tasks-list-container');
        if (container) {
            // CROWN⁴.6: Observe subtree to catch nested insertions
            observer.observe(container, { childList: true, subtree: true });
        }
    }

    /**
     * Enhance a task card with spoken provenance UI
     * CROWN⁴.6 Optimization: Uses cached data instead of N+1 API fetches
     * @param {HTMLElement} card - Task card element
     */
    async enhanceTaskCard(card) {
        const taskId = card.dataset.taskId;
        if (!taskId || card.dataset.provenanceEnhanced === 'true') {
            return;
        }

        try {
            // CROWN⁴.6: Try to get task from cache first to avoid N+1 fetches
            let task = this.getTaskFromCache(taskId);
            
            // If not in cache and task is AI-extracted, fetch it
            if (!task) {
                const extractedByAI = card.dataset.extractedByAi === 'true';
                if (!extractedByAI) {
                    // Skip non-AI tasks to avoid unnecessary fetches
                    card.dataset.provenanceEnhanced = 'true';
                    return;
                }
                
                // Fetch from API as fallback
                task = await this.fetchTaskDetails(taskId);
                if (!task) {
                    card.dataset.provenanceEnhanced = 'true';
                    return;
                }
            }

            // Mark as enhanced to avoid re-processing
            card.dataset.provenanceEnhanced = 'true';

            // Only add provenance if task was extracted by AI or has transcript context
            if (!task.extracted_by_ai && !task.transcript_span) {
                return;
            }

            // Build and inject provenance UI
            const provenanceHTML = this.buildProvenanceUI(task);
            if (provenanceHTML) {
                this.injectProvenanceUI(card, provenanceHTML);
            }

            // Enable "Jump to Transcript" button in menu if transcript_span exists (explicit check for null/undefined)
            if (task.transcript_span && (task.transcript_span.start_ms !== null && task.transcript_span.start_ms !== undefined)) {
                this.enableJumpToTranscriptButton(taskId);
            }

        } catch (error) {
            console.error(`[TaskSpokenProvenance] Error enhancing card ${taskId}:`, error);
        }
    }

    /**
     * Get task from TaskCache (CROWN⁴.5 IndexedDB cache) or TaskStore
     * @param {string|number} taskId - Task ID
     * @returns {Object|null} Task object
     */
    getTaskFromCache(taskId) {
        // Try CROWN⁴.5 TaskStore first (in-memory)
        if (window.taskStore && typeof window.taskStore.getTask === 'function') {
            const task = window.taskStore.getTask(taskId);
            if (task) {
                console.log(`[TaskSpokenProvenance] Using TaskStore cache for task: ${taskId}`);
                return task;
            }
        }
        
        // Try window.tasks array (server-rendered data)
        if (window.tasks && Array.isArray(window.tasks)) {
            const task = window.tasks.find(t => t.id === parseInt(taskId));
            if (task) {
                console.log(`[TaskSpokenProvenance] Using server-rendered data for task: ${taskId}`);
                return task;
            }
        }
        
        return null;
    }

    /**
     * Fetch task details from API (fallback)
     * @param {string|number} taskId - Task ID
     * @returns {Promise<Object|null>} Task object
     */
    async fetchTaskDetails(taskId) {
        try {
            const response = await fetch(`/api/tasks/${taskId}`);
            if (!response.ok) {
                return null;
            }

            const data = await response.json();
            return data.success ? data.task : null;
        } catch (error) {
            console.error(`[TaskSpokenProvenance] Error fetching task ${taskId}:`, error);
            return null;
        }
    }

    /**
     * Build spoken provenance UI HTML
     * @param {Object} task - Task object
     * @returns {string} HTML string
     */
    buildProvenanceUI(task) {
        const context = task.extraction_context || {};
        const transcriptSpan = task.transcript_span;
        
        const speaker = context.speaker || 'Unknown';
        const quote = context.quote || '';
        const confidence = task.confidence_score;
        const meetingTitle = task.meeting?.title || 'Meeting';

        let html = '<div class="task-provenance">';
        
        // Meeting badge with icon
        html += `
            <div class="task-provenance-meeting">
                <svg class="provenance-icon" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20 6h-2.18c.11-.31.18-.65.18-1 0-1.66-1.34-3-3-3-1.05 0-1.96.54-2.5 1.35l-.5.67-.5-.68C10.96 2.54 10.05 2 9 2 7.34 2 6 3.34 6 5c0 .35.07.69.18 1H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-5-2c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zM9 4c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm11 15H4v-2h16v2zm0-5H4V8h5.08L7 10.83 8.62 12 11 8.76l1-1.36 1 1.36L15.38 12 17 10.83 14.92 8H20v6z"/>
                </svg>
                <span class="provenance-meeting-title" title="From meeting: ${this.escapeHtml(meetingTitle)}">${this.escapeHtml(meetingTitle)}</span>
            </div>
        `;

        // Speaker & confidence indicator
        if (speaker && speaker !== 'Unknown') {
            const confidenceClass = confidence >= 0.8 ? 'high' : confidence >= 0.6 ? 'medium' : 'low';
            html += `
                <div class="task-provenance-speaker">
                    <svg class="provenance-icon" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                    </svg>
                    <span class="provenance-speaker-name">${this.escapeHtml(speaker)}</span>
                    ${confidence ? `<span class="provenance-confidence provenance-confidence-${confidenceClass}" title="AI Confidence: ${Math.round(confidence * 100)}%"></span>` : ''}
                </div>
            `;
        }

        // Quote snippet (if available)
        if (quote && quote.length > 10) {
            const shortQuote = quote.length > 80 ? quote.substring(0, 80) + '...' : quote;
            html += `
                <div class="task-provenance-quote" title="${this.escapeHtml(quote)}">
                    <svg class="provenance-icon" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z"/>
                    </svg>
                    <span class="provenance-quote-text">"${this.escapeHtml(shortQuote)}"</span>
                </div>
            `;
        }

        // Jump to transcript link (if transcript_span exists - explicit null/undefined check)
        if (transcriptSpan && (transcriptSpan.start_ms !== null && transcriptSpan.start_ms !== undefined)) {
            html += `
                <button class="task-provenance-jump" data-action="jump-to-transcript" data-task-id="${task.id}" title="Jump to transcript moment">
                    <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
                    </svg>
                    <span>Jump to transcript</span>
                </button>
            `;
        }

        html += '</div>';

        return html;
    }

    /**
     * Inject provenance UI into task card
     * @param {HTMLElement} card - Task card element
     * @param {string} html - Provenance HTML
     */
    injectProvenanceUI(card, html) {
        const taskMetadata = card.querySelector('.task-metadata');
        if (taskMetadata) {
            // Insert provenance after metadata
            taskMetadata.insertAdjacentHTML('afterend', html);
        } else {
            // Fallback: insert at beginning of task-content
            const taskContent = card.querySelector('.task-content');
            if (taskContent) {
                taskContent.insertAdjacentHTML('afterbegin', html);
            }
        }
    }

    /**
     * Enable "Jump to Transcript" button in task menu
     * @param {string|number} taskId - Task ID
     */
    enableJumpToTranscriptButton(taskId) {
        // Find the task menu and enable the jump button
        document.addEventListener('DOMContentLoaded', () => {
            const menu = document.querySelector(`#task-menu[data-task-id="${taskId}"]`);
            if (!menu) {
                // Menu might not be rendered yet, will be handled when menu opens
                return;
            }

            const jumpBtn = menu.querySelector('[data-action="jump-to-transcript"]');
            if (jumpBtn) {
                jumpBtn.classList.remove('hidden');
            }
        });

        // Also update global menu when it opens for this task
        const originalMenu = document.getElementById('task-menu');
        if (originalMenu) {
            originalMenu.addEventListener('task-menu-opened', (e) => {
                if (e.detail && e.detail.taskId === String(taskId)) {
                    const jumpBtn = originalMenu.querySelector('[data-action="jump-to-transcript"]');
                    if (jumpBtn) {
                        jumpBtn.classList.remove('hidden');
                    }
                }
            });
        }
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global instance
window.taskSpokenProvenance = new TaskSpokenProvenance();
