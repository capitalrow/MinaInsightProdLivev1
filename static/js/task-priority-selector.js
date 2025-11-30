/**
 * Task Priority Selector
 * Beautiful priority selector with visual badges (High, Medium, Low)
 */

class TaskPrioritySelector {
    constructor() {
        this.popover = null;
        this.resolveCallback = null;
        this.triggerElement = null;
        this.justOpened = false; // Prevent immediate close from click propagation
        this.init();
    }

    init() {
        this.createPopover();
        this.setupEventListeners();
    }

    createPopover() {
        this.popover = document.createElement('div');
        this.popover.className = 'task-priority-selector-popover';
        this.popover.style.display = 'none'; // Critical: Hide immediately to prevent FOUC
        this.popover.innerHTML = `
            <div class="task-priority-selector-content">
                <button class="task-priority-option" data-priority="high">
                    <div class="task-priority-badge task-priority-high">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"/>
                        </svg>
                        <span>High</span>
                    </div>
                    <div class="task-priority-desc">Urgent and important</div>
                </button>
                <button class="task-priority-option" data-priority="medium">
                    <div class="task-priority-badge task-priority-medium">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14"/>
                        </svg>
                        <span>Medium</span>
                    </div>
                    <div class="task-priority-desc">Important but not urgent</div>
                </button>
                <button class="task-priority-option" data-priority="low">
                    <div class="task-priority-badge task-priority-low">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/>
                        </svg>
                        <span>Low</span>
                    </div>
                    <div class="task-priority-desc">Nice to have</div>
                </button>
            </div>
        `;
        
        document.body.appendChild(this.popover);
    }

    setupEventListeners() {
        const priorityOptions = this.popover.querySelectorAll('.task-priority-option');
        priorityOptions.forEach(btn => {
            btn.addEventListener('click', () => {
                const priority = btn.dataset.priority;
                this.close(priority);
            });
        });

        document.addEventListener('click', (e) => {
            // Skip if popover was just opened (prevents immediate close from click propagation)
            if (this.justOpened) return;
            
            if (this.popover.classList.contains('visible') && 
                !this.popover.contains(e.target) &&
                e.target !== this.triggerElement) {
                this.close(undefined);
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.popover.classList.contains('visible')) {
                this.close(undefined);
            }
        });
    }

    async show(triggerElement) {
        this.triggerElement = triggerElement;
        this.justOpened = true; // Prevent immediate close from click propagation

        // CRITICAL: Set display BEFORE positioning so dimensions are calculable
        this.popover.style.display = 'block';
        this.popover.style.visibility = 'hidden'; // Hide during positioning
        
        // Wait for layout to calculate dimensions
        requestAnimationFrame(() => {
            this.position(triggerElement);
            this.popover.style.visibility = 'visible'; // Show after positioning
            this.popover.classList.add('visible');
            
            console.log('[TaskPrioritySelector] Popover shown at:', {
                top: this.popover.style.top,
                left: this.popover.style.left,
                display: this.popover.style.display
            });
            
            // Reset justOpened flag after a short delay to allow click propagation to complete
            setTimeout(() => {
                this.justOpened = false;
            }, 150);
        });

        return new Promise((resolve) => {
            this.resolveCallback = resolve;
        });
    }

    position(triggerElement) {
        // Default to center of screen if no valid trigger
        if (!triggerElement || triggerElement === document.body) {
            const popoverRect = this.popover.getBoundingClientRect();
            const centerX = Math.max(16, (window.innerWidth - popoverRect.width) / 2);
            const centerY = Math.max(16, (window.innerHeight - popoverRect.height) / 2);
            this.popover.style.top = `${centerY}px`;
            this.popover.style.left = `${centerX}px`;
            console.log('[TaskPrioritySelector] Centered popover (no valid trigger)');
            return;
        }

        const triggerRect = triggerElement.getBoundingClientRect();
        const popoverRect = this.popover.getBoundingClientRect();
        
        // Calculate initial position below the trigger
        let top = triggerRect.bottom + 8;
        let left = triggerRect.left;

        // Flip to above if not enough space below
        if (top + popoverRect.height > window.innerHeight - 16) {
            top = Math.max(16, triggerRect.top - popoverRect.height - 8);
        }

        // Ensure popover stays within horizontal bounds
        if (left + popoverRect.width > window.innerWidth - 16) {
            left = window.innerWidth - popoverRect.width - 16;
        }

        if (left < 16) {
            left = 16;
        }

        // Ensure top doesn't go off-screen
        if (top < 16) {
            top = 16;
        }

        this.popover.style.top = `${top}px`;
        this.popover.style.left = `${left}px`;
    }

    close(result) {
        this.popover.classList.remove('visible');
        
        setTimeout(() => {
            this.popover.style.display = 'none';
            if (this.resolveCallback) {
                this.resolveCallback(result);
                this.resolveCallback = null;
            }
            this.triggerElement = null;
        }, 200);
    }
}

window.taskPrioritySelector = new TaskPrioritySelector();
