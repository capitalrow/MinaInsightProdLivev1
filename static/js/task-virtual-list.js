/**
 * CROWN⁴.5 Virtual List for >50 Tasks
 * Renders only visible tasks for optimal performance with large lists.
 * Uses intersection observer for dynamic rendering.
 */

class VirtualList {
    constructor(options = {}) {
        this.containerSelector = options.container || '#tasks-list-container';
        this.itemHeight = options.itemHeight || 120; // Estimated task card height
        this.bufferSize = options.bufferSize || 5; // Extra items above/below viewport
        this.threshold = options.threshold || 50; // Enable virtual list above this count
        
        this.container = null;
        this.scrollContainer = null;
        this.allItems = [];
        this.visibleItems = new Set();
        this.observer = null;
        this.enabled = false;
        
        this._init();
    }

    /**
     * Initialize virtual list
     */
    _init() {
        this.container = document.querySelector(this.containerSelector);
        if (!this.container) {
            console.warn('⚠️ Virtual list container not found');
            return;
        }

        this.scrollContainer = window;
        
        // Setup intersection observer
        if ('IntersectionObserver' in window) {
            this.observer = new IntersectionObserver(
                this._handleIntersection.bind(this),
                {
                    root: null,
                    rootMargin: `${this.itemHeight * this.bufferSize}px`,
                    threshold: 0
                }
            );
        }
    }

    /**
     * Render tasks with virtual list
     * @param {Array} tasks
     * @returns {Promise<void>}
     */
    async render(tasks) {
        this.allItems = tasks;

        // Enable virtual list only for large lists
        if (tasks.length > this.threshold && this.observer) {
            this.enabled = true;
            await this._renderVirtual(tasks);
        } else {
            this.enabled = false;
            await this._renderFull(tasks);
        }
    }

    /**
     * Render full list (for small lists)
     * @param {Array} tasks
     */
    async _renderFull(tasks) {
        if (!this.container) return;

        const tasksHTML = tasks.map((task, index) => 
            this._renderTaskCard(task, index)
        ).join('');

        this.container.innerHTML = tasksHTML;
        this._attachEventListeners();
    }

    /**
     * Render virtual list (for large lists)
     * @param {Array} tasks
     */
    async _renderVirtual(tasks) {
        if (!this.container) return;

        console.log(`📜 Virtual list enabled (${tasks.length} tasks)`);

        // Create container with total height
        const totalHeight = tasks.length * this.itemHeight;
        this.container.style.minHeight = `${totalHeight}px`;
        this.container.style.position = 'relative';

        // Calculate visible range
        const scrollTop = window.scrollY;
        const viewportHeight = window.innerHeight;
        
        const startIndex = Math.max(0, Math.floor(scrollTop / this.itemHeight) - this.bufferSize);
        const endIndex = Math.min(
            tasks.length,
            Math.ceil((scrollTop + viewportHeight) / this.itemHeight) + this.bufferSize
        );

        // Render visible items
        const visibleTasks = tasks.slice(startIndex, endIndex);
        const tasksHTML = visibleTasks.map((task, i) => 
            this._renderTaskCard(task, startIndex + i, true)
        ).join('');

        this.container.innerHTML = tasksHTML;
        this._attachEventListeners();

        // Observe all rendered items
        const cards = this.container.querySelectorAll('.task-card');
        cards.forEach(card => {
            if (this.observer) {
                this.observer.observe(card);
            }
        });

        // Setup scroll listener for continuous rendering
        this._setupScrollListener();
    }

    /**
     * Render single task card using shared CROWN⁴.18 renderer
     * @param {Object} task
     * @param {number} index
     * @param {boolean} isVirtual
     * @returns {string} HTML
     */
    _renderTaskCard(task, index, isVirtual = false) {
        // Use shared TaskCardRenderer for consistent SSR-matching output
        if (window.taskCardRenderer) {
            return window.taskCardRenderer.render(task, {
                isVirtual: isVirtual,
                virtualIndex: index,
                itemHeight: this.itemHeight
            });
        }
        
        // Fallback: minimal render if shared renderer not loaded
        console.warn('⚠️ TaskCardRenderer not available, using fallback');
        const priority = task.priority || 'medium';
        const status = task.status || 'todo';
        const isCompleted = status === 'completed';
        
        return `
            <div class="task-card${isCompleted ? ' completed' : ''}" 
                 data-task-id="${task.id}"
                 data-index="${index}"
                 data-status="${status}"
                 data-priority="${priority}"
                 ${isVirtual ? `style="position: absolute; top: ${index * this.itemHeight}px; left: 0; right: 0;"` : ''}>
                <div class="checkbox-wrapper">
                    <input type="checkbox" ${isCompleted ? 'checked' : ''} class="task-checkbox" data-task-id="${task.id}">
                </div>
                <div class="task-content">
                    <div class="task-primary-row task-tier-1">
                        <h3 class="task-title">${this._escapeHtml(task.title || 'Untitled Task')}</h3>
                        <div class="task-essential-meta">
                            <span class="priority-dot priority-${priority.toLowerCase()}" title="Priority: ${priority}"></span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Handle intersection observer events
     * @param {Array} entries
     */
    _handleIntersection(entries) {
        entries.forEach(entry => {
            const card = entry.target;
            const index = parseInt(card.dataset.index);

            if (entry.isIntersecting) {
                this.visibleItems.add(index);
                card.classList.add('visible');
            } else {
                this.visibleItems.delete(index);
                card.classList.remove('visible');
            }
        });
    }

    /**
     * Setup scroll listener for continuous rendering
     */
    _setupScrollListener() {
        let scrollTimeout;
        
        const handleScroll = () => {
            if (scrollTimeout) {
                window.cancelAnimationFrame(scrollTimeout);
            }

            scrollTimeout = window.requestAnimationFrame(() => {
                this._updateVisibleRange();
            });
        };

        window.addEventListener('scroll', handleScroll, { passive: true });
    }

    /**
     * Update visible range on scroll
     */
    _updateVisibleRange() {
        if (!this.enabled || !this.container) return;

        const scrollTop = window.scrollY;
        const viewportHeight = window.innerHeight;
        
        const startIndex = Math.max(0, Math.floor(scrollTop / this.itemHeight) - this.bufferSize);
        const endIndex = Math.min(
            this.allItems.length,
            Math.ceil((scrollTop + viewportHeight) / this.itemHeight) + this.bufferSize
        );

        // Check if we need to render new items
        const currentCards = Array.from(this.container.querySelectorAll('.task-card'));
        const currentIndices = currentCards.map(card => parseInt(card.dataset.index));
        
        const minCurrent = Math.min(...currentIndices);
        const maxCurrent = Math.max(...currentIndices);

        // Re-render if scroll moved significantly
        if (startIndex < minCurrent - this.bufferSize || endIndex > maxCurrent + this.bufferSize) {
            this._renderVirtual(this.allItems);
        }
    }

    /**
     * Attach event listeners to task cards
     * NOTE: Checkbox toggle is handled by event delegation in task-page-master-init.js
     */
    _attachEventListeners() {
        // NOTE: Checkbox toggle is handled via event delegation in task-page-master-init.js
        // This prevents duplicate handlers which caused race conditions and update failures

        // Task click (for details/edit)
        const cards = this.container.querySelectorAll('.task-card');
        cards.forEach(card => {
            card.addEventListener('click', (e) => {
                // Ignore checkbox clicks
                if (e.target.classList.contains('task-checkbox')) return;
                
                const taskId = card.dataset.taskId;
                this._handleTaskClick(taskId);
            });
        });
    }

    /**
     * Handle task card click
     * @param {string} taskId
     */
    _handleTaskClick(taskId) {
        window.dispatchEvent(new CustomEvent('task:clicked', {
            detail: { task_id: taskId }
        }));
    }

    /**
     * Format due date
     * @param {string} dueDate
     * @returns {string}
     */
    _formatDueDate(dueDate) {
        if (!dueDate) return '';
        
        const due = new Date(dueDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        const diffDays = Math.floor((due - today) / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Tomorrow';
        if (diffDays < 0) return `${Math.abs(diffDays)}d overdue`;
        if (diffDays <= 7) return `In ${diffDays}d`;
        
        return due.toLocaleDateString();
    }

    /**
     * Escape HTML
     * @param {string} text
     * @returns {string}
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Scroll to task
     * @param {number} index
     */
    scrollToTask(index) {
        const scrollTop = index * this.itemHeight;
        window.scrollTo({
            top: scrollTop,
            behavior: 'smooth'
        });
    }

    /**
     * Get performance stats
     * @returns {Object}
     */
    getStats() {
        return {
            enabled: this.enabled,
            total_items: this.allItems.length,
            visible_items: this.visibleItems.size,
            item_height: this.itemHeight,
            threshold: this.threshold
        };
    }

    /**
     * Cleanup
     */
    destroy() {
        if (this.observer) {
            this.observer.disconnect();
        }
    }
}

// Export singleton with default config
window.taskVirtualList = new VirtualList({
    container: '#tasks-list-container',
    itemHeight: 120,
    bufferSize: 5,
    threshold: 50
});

console.log('📜 CROWN⁴.5 VirtualList loaded');
