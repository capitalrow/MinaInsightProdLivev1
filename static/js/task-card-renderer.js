/**
 * CROWN⁴.18 Shared Task Card Renderer
 * JavaScript implementation that mirrors the SSR template exactly:
 * templates/dashboard/_task_card_macro.html
 * 
 * This ensures visual consistency between:
 * - Server-side rendered cards (initial page load)
 * - Client-side rendered cards (filter changes, real-time updates, virtual list)
 * 
 * CROWN⁴.9: 3-Tier Progressive Disclosure - Scan → Glance → Detail
 * PHASE 4: Accessibility Enhanced - WCAG 2.1 AA Compliant
 */

class TaskCardRenderer {
    constructor() {
        this.escapeDiv = document.createElement('div');
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text 
     * @returns {string}
     */
    escapeHtml(text) {
        if (!text) return '';
        this.escapeDiv.textContent = text;
        return this.escapeDiv.innerHTML;
    }

    /**
     * Truncate text to specified length
     * @param {string} text 
     * @param {number} length 
     * @param {boolean} killwords 
     * @returns {string}
     */
    truncate(text, length = 50, killwords = true) {
        if (!text || text.length <= length) return text || '';
        if (killwords) {
            return text.substring(0, length) + '...';
        }
        const truncated = text.substring(0, length);
        const lastSpace = truncated.lastIndexOf(' ');
        return (lastSpace > 0 ? truncated.substring(0, lastSpace) : truncated) + '...';
    }

    /**
     * Format date for display (e.g., "Dec 08")
     * @param {Date|string} date 
     * @returns {string}
     */
    formatDateShort(date) {
        if (!date) return '';
        const d = date instanceof Date ? date : new Date(date);
        if (isNaN(d.getTime())) return '';
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return `${months[d.getMonth()]} ${String(d.getDate()).padStart(2, '0')}`;
    }

    /**
     * Format date for full display (e.g., "December 08, 2025")
     * @param {Date|string} date 
     * @returns {string}
     */
    formatDateFull(date) {
        if (!date) return '';
        const d = date instanceof Date ? date : new Date(date);
        if (isNaN(d.getTime())) return '';
        const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                        'July', 'August', 'September', 'October', 'November', 'December'];
        return `${months[d.getMonth()]} ${String(d.getDate()).padStart(2, '0')}, ${d.getFullYear()}`;
    }

    /**
     * Check if date is overdue
     * @param {Date|string} dueDate 
     * @returns {boolean}
     */
    isOverdue(dueDate) {
        if (!dueDate) return false;
        const d = dueDate instanceof Date ? dueDate : new Date(dueDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return d < today;
    }

    /**
     * Check if date is due soon (within 2 days)
     * @param {Date|string} dueDate 
     * @returns {boolean}
     */
    isDueSoon(dueDate) {
        if (!dueDate) return false;
        const d = dueDate instanceof Date ? dueDate : new Date(dueDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const twoDaysFromNow = new Date(today);
        twoDaysFromNow.setDate(twoDaysFromNow.getDate() + 2);
        return d >= today && d <= twoDaysFromNow;
    }

    /**
     * Render a task card HTML matching the SSR template exactly
     * @param {Object} task - Task object with all properties
     * @param {Object} options - Rendering options (e.g., for virtual list positioning)
     * @returns {string} HTML string
     */
    render(task, options = {}) {
        const { isVirtual = false, virtualIndex = 0, itemHeight = 120 } = options;

        // Precompute context data (mirrors Jinja2 template logic)
        const extractionContext = task.extraction_context || {};
        const fullQuote = extractionContext.evidence_quote || '';
        const speaker = extractionContext.speaker || '';
        
        const transcriptSpan = task.transcript_span || {};
        const startMs = transcriptSpan.start_ms !== undefined && transcriptSpan.start_ms !== null 
            ? transcriptSpan.start_ms : 0;
        
        const hasProvenance = task.extracted_by_ai && task.meeting;
        const hasTranscript = task.meeting_id && task.transcript_span && 
                              transcriptSpan.start_ms !== undefined && transcriptSpan.start_ms !== null;
        
        const labels = task.labels || [];
        const hasDetailContent = hasProvenance || hasTranscript || labels.length > 0 || task.description;
        
        const priority = (task.priority || 'medium').toLowerCase();
        const priorityText = priority.charAt(0).toUpperCase() + priority.slice(1);
        
        const status = task.status || 'todo';
        const isCompleted = status === 'completed';
        const statusText = isCompleted ? 'Completed' : 'Active';

        // Parse due date
        let dueDate = null;
        let isOverdueFlag = false;
        let isDueSoonFlag = false;
        if (task.due_date) {
            dueDate = task.due_date instanceof Date ? task.due_date : new Date(task.due_date);
            if (!isNaN(dueDate.getTime())) {
                isOverdueFlag = task.is_overdue !== undefined ? task.is_overdue : this.isOverdue(dueDate);
                isDueSoonFlag = task.is_due_soon !== undefined ? task.is_due_soon : this.isDueSoon(dueDate);
            } else {
                dueDate = null;
            }
        }

        // Assignee info
        const assignedTo = task.assigned_to || null;
        const assigneeName = assignedTo ? (assignedTo.display_name || assignedTo.username || '') : '';

        // Meeting info
        const meetingTitle = task.meeting ? (task.meeting.title || '') : '';

        // Build aria-label
        let ariaLabel = `${statusText} task: ${this.escapeHtml(task.title || 'Untitled Task')}. Priority: ${priorityText}`;
        if (dueDate) {
            ariaLabel += `. Due ${this.formatDateFull(dueDate)}`;
        }
        if (assigneeName) {
            ariaLabel += `. Assigned to ${this.escapeHtml(assigneeName)}`;
        }

        // Virtual list positioning
        const virtualStyle = isVirtual 
            ? `position: absolute; top: ${virtualIndex * itemHeight}px; left: 0; right: 0;` 
            : '';

        // Build the HTML (matching SSR template structure exactly)
        return `
<div class="task-card${isCompleted ? ' completed' : ''}" 
     data-task-id="${task.id}"
     data-meeting-id="${task.meeting_id || ''}"
     data-session-id="${task.session_id || ''}"
     data-extracted-by-ai="${task.extracted_by_ai ? 'true' : 'false'}"
     data-status="${status}"
     data-priority="${priority}"
     data-assigned-to="${task.assigned_to_id || ''}"
     data-due-date="${task.due_date || ''}"
     data-labels="${this.escapeHtml(JSON.stringify(labels))}"
     data-transcript-span="${this.escapeHtml(JSON.stringify(transcriptSpan))}"
     data-updated-at="${task.updated_at || ''}"
     data-is-pinned="${task.is_pinned ? 'true' : 'false'}"
     data-has-detail="${hasDetailContent ? 'true' : 'false'}"
     ${isVirtual ? `data-index="${virtualIndex}"` : ''}
     role="article"
     tabindex="0"
     aria-label="${this.escapeHtml(ariaLabel)}"
     aria-expanded="false"
     ${virtualStyle ? `style="${virtualStyle}"` : ''}>
    
    <div class="checkbox-wrapper">
        <input type="checkbox" 
               ${isCompleted ? 'checked' : ''} 
               class="task-checkbox" 
               id="task-checkbox-${task.id}"
               data-task-id="${task.id}"
               aria-label="Mark task '${this.escapeHtml(this.truncate(task.title, 50))}' as ${isCompleted ? 'incomplete' : 'complete'}"
               aria-describedby="task-title-${task.id}">
    </div>
    
    <div class="task-content">
        <div class="task-primary-row task-tier-1">
            <h3 class="task-title" id="task-title-${task.id}" data-field="title">${this.escapeHtml(task.title || 'Untitled Task')}</h3>
            
            <div class="task-essential-meta">
                <span class="priority-dot priority-${priority}" 
                      data-field="priority"
                      role="img"
                      aria-label="Priority: ${priorityText}"
                      title="Priority: ${priorityText}">
                    <span class="sr-only">${priorityText} priority</span>
                </span>
                
                ${hasDetailContent ? `
                <button class="task-expand-trigger" 
                        aria-label="Expand details for task: ${this.escapeHtml(this.truncate(task.title, 30))}" 
                        aria-expanded="false"
                        aria-controls="task-details-${task.id}"
                        title="Show details">
                    <svg class="expand-icon" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                    </svg>
                </button>
                ` : ''}
            </div>
        </div>
        
        <div class="task-secondary-row task-tier-2" id="task-details-${task.id}-tier2">
            ${dueDate ? `
            <span class="due-date-compact${isOverdueFlag ? ' overdue' : ''}${isDueSoonFlag ? ' due-soon' : ''}" 
                  data-field="due_date"
                  role="text"
                  aria-label="Due date: ${this.formatDateFull(dueDate)}${isOverdueFlag ? ', overdue' : ''}${isDueSoonFlag ? ', due soon' : ''}"
                  title="Due ${this.formatDateFull(dueDate)}">
                <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11z"/>
                </svg>
                <span>${this.formatDateShort(dueDate)}</span>
            </span>
            ` : ''}
            
            ${assignedTo ? `
            <span class="assignee-compact" 
                  data-field="assignee" 
                  role="text"
                  aria-label="Assigned to ${this.escapeHtml(assigneeName)}"
                  title="Assigned to ${this.escapeHtml(assigneeName)}">
                <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                </svg>
                <span>${this.escapeHtml(assigneeName)}</span>
            </span>
            ` : ''}
            
            ${hasDetailContent && !dueDate && !assignedTo ? `
            <span class="tier2-hint" aria-hidden="true">
                <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <span>Details available</span>
            </span>
            ` : ''}
        </div>
        
        <div class="task-tertiary-row task-tier-3" id="task-details-${task.id}">
            ${labels.length > 0 ? `
            <div class="labels-compact" data-field="labels" role="list" aria-label="Task labels">
                ${labels.slice(0, 3).map(label => `
                <span class="label-compact" role="listitem">${this.escapeHtml(label)}</span>
                `).join('')}
                ${labels.length > 3 ? `
                <span class="label-compact label-overflow" role="listitem" aria-label="${labels.length - 3} more labels">+${labels.length - 3}</span>
                ` : ''}
            </div>
            ` : ''}
            
            ${hasProvenance ? `
            <button class="provenance-compact" 
                  data-task-id="${task.id}"
                  data-action="show-context-preview"
                  data-has-context="${fullQuote ? 'true' : 'false'}"
                  data-context-quote="${this.escapeHtml(fullQuote)}"
                  data-context-speaker="${this.escapeHtml(speaker)}"
                  data-context-start-ms="${startMs}"
                  data-meeting-id="${task.meeting_id}"
                  data-meeting-title="${this.escapeHtml(meetingTitle)}"
                  data-confidence="${task.confidence_score || 0}"
                  aria-label="View context from meeting: ${this.escapeHtml(meetingTitle)}${speaker ? `, spoken by ${this.escapeHtml(speaker)}` : ''}"
                  title="From meeting: ${this.escapeHtml(meetingTitle)}${speaker ? ` - ${this.escapeHtml(speaker)}` : ''}">
                <svg class="provenance-icon" width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/>
                </svg>
                <span>${this.escapeHtml(this.truncate(meetingTitle, 15))}</span>
                ${task.confidence_score && task.confidence_score >= 0.8 ? `
                <span class="confidence-dot high" aria-hidden="true"></span>
                <span class="sr-only">High confidence extraction</span>
                ` : ''}
            </button>
            ` : ''}
            
            ${hasTranscript ? `
            <button class="provenance-compact jump-to-transcript-btn" 
                    data-action="jump-to-transcript"
                    data-task-id="${task.id}"
                    aria-label="Jump to transcript at ${Math.floor(startMs / 60000)} minutes ${Math.floor((startMs / 1000) % 60)} seconds"
                    title="Jump to transcript at ${Math.floor(startMs / 60000)}:${String(Math.floor((startMs / 1000) % 60)).padStart(2, '0')}">
                <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                </svg>
                <span>Transcript</span>
            </button>
            ` : ''}
            
            ${task.description ? `
            <div class="task-description-preview">
                <p class="description-text">${this.escapeHtml(this.truncate(task.description, 100))}</p>
            </div>
            ` : ''}
        </div>
    </div>
    
    <div class="task-actions" role="group" aria-label="Task actions">
        <span class="priority-badge priority-${priority}" 
              data-field="priority"
              aria-hidden="true"
              title="Click to change priority">
            ${priorityText}
        </span>
        
        <button class="task-menu-trigger" 
                data-task-id="${task.id}"
                type="button"
                aria-haspopup="menu"
                aria-expanded="false"
                aria-label="Open actions menu for task: ${this.escapeHtml(this.truncate(task.title, 30))}"
                title="More actions">
            <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="5" r="2"/>
                <circle cx="12" cy="12" r="2"/>
                <circle cx="12" cy="19" r="2"/>
            </svg>
        </button>
    </div>
</div>`;
    }

    /**
     * Render multiple task cards
     * @param {Array} tasks - Array of task objects
     * @param {Object} options - Rendering options
     * @returns {string} HTML string of all cards
     */
    renderAll(tasks, options = {}) {
        if (!tasks || tasks.length === 0) return '';
        return tasks.map((task, index) => {
            const cardOptions = { ...options };
            if (options.isVirtual) {
                cardOptions.virtualIndex = (options.startIndex || 0) + index;
            }
            return this.render(task, cardOptions);
        }).join('');
    }

    /**
     * Update an existing task card in place (for reconciliation)
     * @param {HTMLElement} cardElement - Existing card DOM element
     * @param {Object} task - Updated task data
     * @returns {boolean} Whether update was needed
     */
    updateCard(cardElement, task) {
        if (!cardElement || !task) return false;

        let updated = false;
        const priority = (task.priority || 'medium').toLowerCase();
        const status = task.status || 'todo';
        const isCompleted = status === 'completed';

        // Update data attributes
        if (cardElement.dataset.status !== status) {
            cardElement.dataset.status = status;
            cardElement.classList.toggle('completed', isCompleted);
            updated = true;
        }

        if (cardElement.dataset.priority !== priority) {
            cardElement.dataset.priority = priority;
            const priorityDot = cardElement.querySelector('.priority-dot');
            if (priorityDot) {
                priorityDot.className = `priority-dot priority-${priority}`;
            }
            updated = true;
        }

        // Update checkbox
        const checkbox = cardElement.querySelector('.task-checkbox');
        if (checkbox && checkbox.checked !== isCompleted) {
            checkbox.checked = isCompleted;
            updated = true;
        }

        // Update title
        const titleEl = cardElement.querySelector('.task-title');
        if (titleEl && titleEl.textContent !== (task.title || 'Untitled Task')) {
            titleEl.textContent = task.title || 'Untitled Task';
            updated = true;
        }

        // Update pinned state
        if (cardElement.dataset.isPinned !== (task.is_pinned ? 'true' : 'false')) {
            cardElement.dataset.isPinned = task.is_pinned ? 'true' : 'false';
            updated = true;
        }

        // Update updated_at timestamp
        if (task.updated_at && cardElement.dataset.updatedAt !== task.updated_at) {
            cardElement.dataset.updatedAt = task.updated_at;
            updated = true;
        }

        return updated;
    }
}

// Export singleton instance
window.taskCardRenderer = new TaskCardRenderer();

console.log('🎨 CROWN⁴.18 TaskCardRenderer loaded - SSR-compatible client rendering');
