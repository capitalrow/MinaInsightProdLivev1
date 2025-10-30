/**
 * CROWN⁴.5 Predictive UI Integration
 * Provides real-time AI suggestions for due dates, priorities, and categories
 * while user types task title.
 */

class TaskPredictiveUI {
    constructor() {
        this.debounceTimer = null;
        this.lastPrediction = null;
        this.suggestionCache = new Map();
        this.enabled = true;
    }

    /**
     * Initialize predictive UI for task creation form
     * @param {HTMLElement} formElement - Task creation form
     */
    init(formElement) {
        if (!formElement) {
            console.warn('⚠️ Predictive UI: Form element not found');
            return;
        }

        const titleInput = formElement.querySelector('[name="title"]');
        const descriptionInput = formElement.querySelector('[name="description"]');
        const dueDateInput = formElement.querySelector('[name="due_date"]');
        const prioritySelect = formElement.querySelector('[name="priority"]');
        const categorySelect = formElement.querySelector('[name="category"]');

        if (!titleInput) {
            console.warn('⚠️ Predictive UI: Title input not found');
            return;
        }

        // Create suggestion container
        const suggestionsContainer = this.createSuggestionsContainer();
        titleInput.parentElement.insertBefore(suggestionsContainer, titleInput.nextSibling);

        // Listen for title/description changes
        titleInput.addEventListener('input', () => {
            this.handleInputChange(titleInput, descriptionInput, suggestionsContainer, {
                dueDateInput,
                prioritySelect,
                categorySelect
            });
        });

        if (descriptionInput) {
            descriptionInput.addEventListener('input', () => {
                this.handleInputChange(titleInput, descriptionInput, suggestionsContainer, {
                    dueDateInput,
                    prioritySelect,
                    categorySelect
                });
            });
        }

        console.log('✅ Predictive UI initialized');
    }

    /**
     * Create suggestions container element
     * @returns {HTMLElement}
     */
    createSuggestionsContainer() {
        const container = document.createElement('div');
        container.className = 'predictive-suggestions';
        container.style.cssText = `
            display: none;
            margin-top: 8px;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 8px;
            color: white;
            font-size: 13px;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
            animation: slideDown 0.2s ease-out;
        `;
        container.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0zM4.5 7.5a.5.5 0 0 0 0 1h5.793l-2.147 2.146a.5.5 0 0 0 .708.708l3-3a.5.5 0 0 0 0-.708l-3-3a.5.5 0 1 0-.708.708L10.293 7.5H4.5z"/>
                </svg>
                <strong>AI Suggestions</strong>
                <span class="confidence-badge" style="margin-left: auto; padding: 2px 8px; background: rgba(255,255,255,0.2); border-radius: 12px; font-size: 11px;"></span>
            </div>
            <div class="suggestions-content"></div>
            <div style="margin-top: 8px; font-size: 11px; opacity: 0.8;">
                Click a suggestion to apply it automatically
            </div>
        `;
        return container;
    }

    /**
     * Handle input change with debouncing
     * @param {HTMLInputElement} titleInput
     * @param {HTMLTextAreaElement} descriptionInput
     * @param {HTMLElement} container
     * @param {Object} formInputs - Form input elements
     */
    handleInputChange(titleInput, descriptionInput, container, formInputs) {
        if (!this.enabled) return;

        const title = titleInput.value.trim();
        const description = descriptionInput ? descriptionInput.value.trim() : '';

        // Hide suggestions if title is too short
        if (title.length < 5) {
            container.style.display = 'none';
            return;
        }

        // Debounce API calls (300ms)
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            this.fetchSuggestions(title, description, container, formInputs);
        }, 300);
    }

    /**
     * Fetch suggestions from API
     * @param {string} title
     * @param {string} description
     * @param {HTMLElement} container
     * @param {Object} formInputs
     */
    async fetchSuggestions(title, description, container, formInputs) {
        const cacheKey = `${title}:${description}`;

        // Check cache first
        if (this.suggestionCache.has(cacheKey)) {
            this.renderSuggestions(this.suggestionCache.get(cacheKey), container, formInputs);
            return;
        }

        try {
            const response = await fetch('/api/tasks/suggest', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify({ title, description })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            if (result.success && result.suggestions) {
                // Cache the result
                this.suggestionCache.set(cacheKey, result.suggestions);
                this.lastPrediction = result.suggestions;

                // Render suggestions
                this.renderSuggestions(result.suggestions, container, formInputs);

                // Emit telemetry
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordEvent('predictive_suggestion_shown', {
                        confidence: result.suggestions.confidence,
                        has_due_date: !!result.suggestions.due_date,
                        has_priority: !!result.suggestions.priority,
                        has_category: !!result.suggestions.category
                    });
                }
            }
        } catch (error) {
            console.error('❌ Failed to fetch suggestions:', error);
            container.style.display = 'none';
        }
    }

    /**
     * Render suggestions in container
     * @param {Object} suggestions
     * @param {HTMLElement} container
     * @param {Object} formInputs
     */
    renderSuggestions(suggestions, container, formInputs) {
        const content = container.querySelector('.suggestions-content');
        const confidenceBadge = container.querySelector('.confidence-badge');

        // Update confidence badge
        const confidencePercent = Math.round(suggestions.confidence * 100);
        confidenceBadge.textContent = `${confidencePercent}% confident`;
        confidenceBadge.style.background = this.getConfidenceColor(suggestions.confidence);

        // Build suggestion items
        const items = [];

        if (suggestions.due_date) {
            items.push(this.createSuggestionItem(
                '📅',
                'Due Date',
                this.formatDate(suggestions.due_date),
                () => this.applySuggestion('due_date', suggestions.due_date, formInputs.dueDateInput)
            ));
        }

        if (suggestions.priority) {
            items.push(this.createSuggestionItem(
                this.getPriorityIcon(suggestions.priority),
                'Priority',
                this.capitalizeFirst(suggestions.priority),
                () => this.applySuggestion('priority', suggestions.priority, formInputs.prioritySelect)
            ));
        }

        if (suggestions.category) {
            items.push(this.createSuggestionItem(
                '🏷️',
                'Category',
                this.capitalizeFirst(suggestions.category),
                () => this.applySuggestion('category', suggestions.category, formInputs.categorySelect)
            ));
        }

        if (items.length > 0) {
            content.innerHTML = items.join('');
            container.style.display = 'block';

            // Add animation
            container.style.animation = 'none';
            setTimeout(() => {
                container.style.animation = 'slideDown 0.2s ease-out';
            }, 10);
        } else {
            container.style.display = 'none';
        }
    }

    /**
     * Create suggestion item HTML
     * @param {string} icon
     * @param {string} label
     * @param {string} value
     * @param {Function} onClick
     * @returns {string}
     */
    createSuggestionItem(icon, label, value, onClick) {
        const id = `suggestion-${label.toLowerCase().replace(/\s+/g, '-')}-${Date.now()}`;
        
        // Store click handler
        setTimeout(() => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('click', onClick);
            }
        }, 0);

        return `
            <div id="${id}" class="suggestion-item" style="
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 6px 8px;
                margin-bottom: 4px;
                background: rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                cursor: pointer;
                transition: all 0.2s;
            " onmouseover="this.style.background='rgba(255,255,255,0.25)'" 
               onmouseout="this.style.background='rgba(255,255,255,0.15)'">
                <span>${icon}</span>
                <span style="opacity: 0.9;">${label}:</span>
                <strong>${value}</strong>
                <svg style="margin-left: auto;" width="12" height="12" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0zM4.5 7.5a.5.5 0 0 0 0 1h5.793l-2.147 2.146a.5.5 0 0 0 .708.708l3-3a.5.5 0 0 0 0-.708l-3-3a.5.5 0 1 0-.708.708L10.293 7.5H4.5z"/>
                </svg>
            </div>
        `;
    }

    /**
     * Apply suggestion to form input
     * @param {string} field
     * @param {*} value
     * @param {HTMLElement} input
     */
    applySuggestion(field, value, input) {
        if (!input) {
            console.warn(`⚠️ Input not found for field: ${field}`);
            return;
        }

        // Set value
        if (input.tagName === 'SELECT') {
            input.value = value;
        } else if (input.type === 'date') {
            input.value = value;
        } else {
            input.value = value;
        }

        // Trigger change event
        input.dispatchEvent(new Event('change', { bubbles: true }));

        // Visual feedback
        input.style.background = 'rgba(102, 126, 234, 0.1)';
        setTimeout(() => {
            input.style.background = '';
        }, 500);

        // Emit telemetry
        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordEvent('predictive_suggestion_applied', {
                field,
                value,
                confidence: this.lastPrediction?.confidence || 0
            });
        }

        console.log(`✅ Applied suggestion: ${field} = ${value}`);
    }

    /**
     * Get confidence color based on score
     * @param {number} confidence
     * @returns {string}
     */
    getConfidenceColor(confidence) {
        if (confidence >= 0.8) return 'rgba(76, 175, 80, 0.8)'; // Green
        if (confidence >= 0.5) return 'rgba(255, 193, 7, 0.8)'; // Yellow
        return 'rgba(244, 67, 54, 0.8)'; // Red
    }

    /**
     * Get priority icon
     * @param {string} priority
     * @returns {string}
     */
    getPriorityIcon(priority) {
        const icons = {
            urgent: '🔴',
            high: '🟠',
            medium: '🟡',
            low: '🟢'
        };
        return icons[priority] || '⚪';
    }

    /**
     * Format date for display
     * @param {string} dateStr
     * @returns {string}
     */
    formatDate(dateStr) {
        const date = new Date(dateStr);
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);

        if (date.toDateString() === today.toDateString()) {
            return 'Today';
        } else if (date.toDateString() === tomorrow.toDateString()) {
            return 'Tomorrow';
        } else {
            return date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric',
                year: date.getFullYear() !== today.getFullYear() ? 'numeric' : undefined
            });
        }
    }

    /**
     * Capitalize first letter
     * @param {string} str
     * @returns {string}
     */
    capitalizeFirst(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    /**
     * Enable/disable predictive UI
     * @param {boolean} enabled
     */
    setEnabled(enabled) {
        this.enabled = enabled;
        console.log(`Predictive UI ${enabled ? 'enabled' : 'disabled'}`);
    }

    /**
     * Clear suggestion cache
     */
    clearCache() {
        this.suggestionCache.clear();
        console.log('✅ Suggestion cache cleared');
    }
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(style);

// Export singleton
window.taskPredictiveUI = new TaskPredictiveUI();

console.log('🤖 CROWN⁴.5 Predictive UI loaded');
