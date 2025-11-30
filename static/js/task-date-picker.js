/**
 * Task Date Picker
 * Beautiful calendar picker with quick presets (Today, Tomorrow, Next Week)
 */

class TaskDatePicker {
    constructor() {
        this.popover = null;
        this.resolveCallback = null;
        this.currentTaskId = null;
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
        this.popover.className = 'task-date-picker-popover';
        this.popover.style.display = 'none'; // Critical: Hide immediately to prevent FOUC
        this.popover.innerHTML = `
            <div class="task-date-picker-content">
                <div class="task-date-picker-presets">
                    <button class="task-date-preset" data-preset="today">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        <span>Today</span>
                    </button>
                    <button class="task-date-preset" data-preset="tomorrow">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
                        </svg>
                        <span>Tomorrow</span>
                    </button>
                    <button class="task-date-preset" data-preset="next-week">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                        </svg>
                        <span>Next Week</span>
                    </button>
                </div>
                <div class="task-date-picker-divider"></div>
                <div class="task-date-picker-custom">
                    <label>Custom Date</label>
                    <input type="date" class="task-date-input" />
                </div>
                <div class="task-date-picker-actions">
                    <button class="task-date-clear">Clear</button>
                    <button class="task-date-cancel">Cancel</button>
                    <button class="task-date-apply">Apply</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.popover);
    }

    setupEventListeners() {
        const presetButtons = this.popover.querySelectorAll('.task-date-preset');
        presetButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const preset = btn.dataset.preset;
                this.applyPreset(preset);
            });
        });

        this.popover.querySelector('.task-date-clear').addEventListener('click', () => {
            this.close(null);
        });

        this.popover.querySelector('.task-date-cancel').addEventListener('click', () => {
            this.close(undefined);
        });

        this.popover.querySelector('.task-date-apply').addEventListener('click', () => {
            const dateInput = this.popover.querySelector('.task-date-input');
            const selectedDate = dateInput.value;
            if (selectedDate) {
                this.close(selectedDate);
            }
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
        
        const dateInput = this.popover.querySelector('.task-date-input');
        dateInput.value = '';

        // CRITICAL: Set display BEFORE positioning so dimensions are calculable
        this.popover.style.display = 'block';
        this.popover.style.visibility = 'hidden'; // Hide during positioning
        
        // Wait for layout to calculate dimensions
        requestAnimationFrame(() => {
            this.position(triggerElement);
            this.popover.style.visibility = 'visible'; // Show after positioning
            this.popover.classList.add('visible');
            
            console.log('[TaskDatePicker] Popover shown at:', {
                top: this.popover.style.top,
                left: this.popover.style.left
            });
            
            // Reset justOpened flag after a short delay
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
            return;
        }

        const triggerRect = triggerElement.getBoundingClientRect();
        const popoverRect = this.popover.getBoundingClientRect();
        
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

    applyPreset(preset) {
        const today = new Date();
        let selectedDate;

        switch (preset) {
            case 'today':
                selectedDate = today;
                break;
            case 'tomorrow':
                selectedDate = new Date(today);
                selectedDate.setDate(today.getDate() + 1);
                break;
            case 'next-week':
                selectedDate = new Date(today);
                selectedDate.setDate(today.getDate() + 7);
                break;
        }

        const dateStr = selectedDate.toISOString().split('T')[0];
        this.close(dateStr);
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

window.taskDatePicker = new TaskDatePicker();
