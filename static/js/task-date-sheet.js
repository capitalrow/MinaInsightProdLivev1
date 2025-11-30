/**
 * Task Date Sheet - Mobile-first bottom sheet for date selection
 * Modern UX following Notion/Linear patterns
 */

class TaskDateSheet {
    constructor() {
        this.overlay = null;
        this.sheet = null;
        this.resolveCallback = null;
        this.currentTaskId = null;
        this.init();
    }

    init() {
        this.createSheet();
        this.setupEventListeners();
    }

    createSheet() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'task-sheet-overlay';
        this.overlay.innerHTML = `
            <div class="task-sheet task-date-sheet">
                <div class="task-sheet-handle"></div>
                <div class="task-sheet-header">
                    <h3>Set Due Date</h3>
                    <button class="task-sheet-close" aria-label="Close">
                        <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
                <div class="task-sheet-body">
                    <div class="task-sheet-presets">
                        <button class="task-sheet-preset" data-preset="today">
                            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <circle cx="12" cy="12" r="10" stroke-width="2"/>
                                <path stroke-linecap="round" stroke-width="2" d="M12 6v6l4 2"/>
                            </svg>
                            Today
                        </button>
                        <button class="task-sheet-preset" data-preset="tomorrow">
                            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707"/>
                            </svg>
                            Tomorrow
                        </button>
                        <button class="task-sheet-preset" data-preset="next-week">
                            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <rect x="3" y="4" width="18" height="18" rx="2" stroke-width="2"/>
                                <path stroke-linecap="round" stroke-width="2" d="M16 2v4M8 2v4M3 10h18"/>
                            </svg>
                            Next Week
                        </button>
                        <button class="task-sheet-preset" data-preset="next-month">
                            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <rect x="3" y="4" width="18" height="18" rx="2" stroke-width="2"/>
                                <path stroke-linecap="round" stroke-width="2" d="M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>
                            </svg>
                            Next Month
                        </button>
                    </div>
                    
                    <div class="task-sheet-divider"></div>
                    
                    <div class="task-sheet-custom-date">
                        <label class="task-sheet-label">Custom date</label>
                        <input type="date" class="task-sheet-date-input" />
                    </div>
                    
                    <div class="task-sheet-actions">
                        <button class="task-sheet-btn task-sheet-btn-danger task-sheet-clear">Clear</button>
                        <button class="task-sheet-btn task-sheet-btn-primary task-sheet-apply">Apply</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.overlay);
        this.sheet = this.overlay.querySelector('.task-sheet');
        this.dateInput = this.overlay.querySelector('.task-sheet-date-input');
    }

    setupEventListeners() {
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.close(undefined);
            }
        });

        this.overlay.querySelector('.task-sheet-close').addEventListener('click', () => {
            this.close(undefined);
        });

        this.overlay.querySelectorAll('.task-sheet-preset').forEach(btn => {
            btn.addEventListener('click', () => {
                const preset = btn.dataset.preset;
                const date = this.getPresetDate(preset);
                this.close(date);
            });
        });

        this.overlay.querySelector('.task-sheet-clear').addEventListener('click', () => {
            this.close(null); // null means clear the date
        });

        this.overlay.querySelector('.task-sheet-apply').addEventListener('click', () => {
            const value = this.dateInput.value;
            if (value) {
                this.close(value);
            } else {
                window.toast?.error('Please select a date');
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay.classList.contains('visible')) {
                this.close(undefined);
            }
        });
    }

    getPresetDate(preset) {
        const today = new Date();
        let date;

        switch (preset) {
            case 'today':
                date = today;
                break;
            case 'tomorrow':
                date = new Date(today);
                date.setDate(today.getDate() + 1);
                break;
            case 'next-week':
                date = new Date(today);
                date.setDate(today.getDate() + 7);
                break;
            case 'next-month':
                date = new Date(today);
                date.setMonth(today.getMonth() + 1);
                break;
            default:
                return null;
        }

        return date.toISOString().split('T')[0];
    }

    async open(taskId, currentDate = null) {
        this.currentTaskId = taskId;

        // Set minimum date to today
        const today = new Date().toISOString().split('T')[0];
        this.dateInput.min = today;
        
        // Set current value
        if (currentDate) {
            this.dateInput.value = currentDate.split('T')[0];
        } else {
            this.dateInput.value = '';
        }

        this.overlay.style.display = 'flex';
        
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                this.overlay.classList.add('visible');
                this.sheet.classList.add('visible');
            });
        });

        console.log('[TaskDateSheet] Opened for task:', taskId);

        return new Promise((resolve) => {
            this.resolveCallback = resolve;
        });
    }

    close(result) {
        this.overlay.classList.remove('visible');
        this.sheet.classList.remove('visible');
        
        setTimeout(() => {
            this.overlay.style.display = 'none';
            if (this.resolveCallback) {
                this.resolveCallback(result);
                this.resolveCallback = null;
            }
            this.currentTaskId = null;
        }, 300);
    }

    static isMobile() {
        return window.matchMedia('(max-width: 768px)').matches || 
               ('ontouchstart' in window) ||
               (navigator.maxTouchPoints > 0);
    }
}

window.taskDateSheet = new TaskDateSheet();
console.log('[TaskDateSheet] Initialized');
