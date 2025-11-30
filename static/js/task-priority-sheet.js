/**
 * Task Priority Sheet - Mobile-first bottom sheet for priority selection
 * Modern UX following Notion/Linear patterns
 */

class TaskPrioritySheet {
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
            <div class="task-sheet task-priority-sheet">
                <div class="task-sheet-handle"></div>
                <div class="task-sheet-header">
                    <h3>Set Priority</h3>
                    <button class="task-sheet-close" aria-label="Close">
                        <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
                <div class="task-sheet-body">
                    <button class="task-sheet-option" data-priority="urgent">
                        <div class="task-priority-indicator urgent"></div>
                        <div class="task-sheet-option-content">
                            <span class="task-sheet-option-title">Urgent</span>
                            <span class="task-sheet-option-desc">Needs immediate attention</span>
                        </div>
                        <svg class="task-sheet-check" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                        </svg>
                    </button>
                    <button class="task-sheet-option" data-priority="high">
                        <div class="task-priority-indicator high"></div>
                        <div class="task-sheet-option-content">
                            <span class="task-sheet-option-title">High</span>
                            <span class="task-sheet-option-desc">Important and time-sensitive</span>
                        </div>
                        <svg class="task-sheet-check" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                        </svg>
                    </button>
                    <button class="task-sheet-option" data-priority="medium">
                        <div class="task-priority-indicator medium"></div>
                        <div class="task-sheet-option-content">
                            <span class="task-sheet-option-title">Medium</span>
                            <span class="task-sheet-option-desc">Standard priority</span>
                        </div>
                        <svg class="task-sheet-check" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                        </svg>
                    </button>
                    <button class="task-sheet-option" data-priority="low">
                        <div class="task-priority-indicator low"></div>
                        <div class="task-sheet-option-content">
                            <span class="task-sheet-option-title">Low</span>
                            <span class="task-sheet-option-desc">Can wait, nice to have</span>
                        </div>
                        <svg class="task-sheet-check" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.overlay);
        this.sheet = this.overlay.querySelector('.task-sheet');
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

        this.overlay.querySelectorAll('.task-sheet-option').forEach(btn => {
            btn.addEventListener('click', () => {
                const priority = btn.dataset.priority;
                this.close(priority);
            });
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay.classList.contains('visible')) {
                this.close(undefined);
            }
        });
    }

    async open(taskId, currentPriority = 'medium') {
        this.currentTaskId = taskId;
        
        this.overlay.querySelectorAll('.task-sheet-option').forEach(btn => {
            const isSelected = btn.dataset.priority === currentPriority;
            btn.classList.toggle('selected', isSelected);
        });

        this.overlay.style.display = 'flex';
        
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                this.overlay.classList.add('visible');
                this.sheet.classList.add('visible');
            });
        });

        console.log('[TaskPrioritySheet] Opened for task:', taskId);

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

window.taskPrioritySheet = new TaskPrioritySheet();
console.log('[TaskPrioritySheet] Initialized');
