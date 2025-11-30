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
        
        // Critical inline styles to guarantee visibility
        Object.assign(this.overlay.style, {
            position: 'fixed',
            top: '0',
            left: '0',
            right: '0',
            bottom: '0',
            zIndex: '999999',
            display: 'none',
            alignItems: 'flex-end',
            justifyContent: 'center',
            background: 'rgba(0, 0, 0, 0.5)'
        });
        
        this.overlay.innerHTML = `
            <div class="task-sheet task-priority-sheet" style="
                width: 100%;
                max-width: 500px;
                background: #1e293b;
                border-radius: 20px 20px 0 0;
                overflow: hidden;
                box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.5);
            ">
                <div class="task-sheet-handle" style="width: 36px; height: 5px; background: #475569; border-radius: 3px; margin: 12px auto 8px;"></div>
                <div class="task-sheet-header" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 20px 16px; border-bottom: 1px solid rgba(255,255,255,0.1);">
                    <h3 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0;">Set Priority</h3>
                    <button class="task-sheet-close" aria-label="Close" style="width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.05); border: none; border-radius: 50%; color: #94a3b8; cursor: pointer;">
                        <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
                <div class="task-sheet-body" style="padding: 8px 12px 32px;">
                    <button class="task-sheet-option" data-priority="urgent" style="display: flex; align-items: center; gap: 16px; width: 100%; padding: 16px; background: none; border: none; border-radius: 12px; cursor: pointer; text-align: left;">
                        <div style="width: 12px; height: 12px; border-radius: 50%; background: #ef4444; box-shadow: 0 0 8px rgba(239,68,68,0.5);"></div>
                        <div style="flex: 1;">
                            <span style="display: block; font-size: 16px; font-weight: 500; color: #f8fafc;">Urgent</span>
                            <span style="display: block; font-size: 13px; color: #94a3b8;">Needs immediate attention</span>
                        </div>
                    </button>
                    <button class="task-sheet-option" data-priority="high" style="display: flex; align-items: center; gap: 16px; width: 100%; padding: 16px; background: none; border: none; border-radius: 12px; cursor: pointer; text-align: left;">
                        <div style="width: 12px; height: 12px; border-radius: 50%; background: #f97316;"></div>
                        <div style="flex: 1;">
                            <span style="display: block; font-size: 16px; font-weight: 500; color: #f8fafc;">High</span>
                            <span style="display: block; font-size: 13px; color: #94a3b8;">Important and time-sensitive</span>
                        </div>
                    </button>
                    <button class="task-sheet-option" data-priority="medium" style="display: flex; align-items: center; gap: 16px; width: 100%; padding: 16px; background: none; border: none; border-radius: 12px; cursor: pointer; text-align: left;">
                        <div style="width: 12px; height: 12px; border-radius: 50%; background: #6b7280;"></div>
                        <div style="flex: 1;">
                            <span style="display: block; font-size: 16px; font-weight: 500; color: #f8fafc;">Medium</span>
                            <span style="display: block; font-size: 13px; color: #94a3b8;">Standard priority</span>
                        </div>
                    </button>
                    <button class="task-sheet-option" data-priority="low" style="display: flex; align-items: center; gap: 16px; width: 100%; padding: 16px; background: none; border: none; border-radius: 12px; cursor: pointer; text-align: left;">
                        <div style="width: 12px; height: 12px; border-radius: 50%; background: #475569;"></div>
                        <div style="flex: 1;">
                            <span style="display: block; font-size: 16px; font-weight: 500; color: #f8fafc;">Low</span>
                            <span style="display: block; font-size: 13px; color: #94a3b8;">Can wait, nice to have</span>
                        </div>
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
            // Touch feedback on press
            btn.addEventListener('touchstart', () => {
                btn.style.transform = 'scale(0.98)';
                btn.style.background = 'rgba(255,255,255,0.08)';
            }, { passive: true });
            
            btn.addEventListener('touchend', () => {
                btn.style.transform = '';
                if (!btn.classList.contains('selected')) {
                    btn.style.background = '';
                }
            }, { passive: true });
            
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
        
        // Update selected state styling
        this.overlay.querySelectorAll('.task-sheet-option').forEach(btn => {
            const isSelected = btn.dataset.priority === currentPriority;
            btn.classList.toggle('selected', isSelected);
            
            if (isSelected) {
                btn.style.background = 'rgba(59, 130, 246, 0.1)';
                btn.style.border = '1px solid rgba(59, 130, 246, 0.3)';
                btn.style.borderRadius = '12px';
                
                // Add checkmark indicator
                let check = btn.querySelector('.selected-check');
                if (!check) {
                    check = document.createElement('span');
                    check.className = 'selected-check';
                    check.innerHTML = `<svg width="20" height="20" fill="none" stroke="#3b82f6" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>`;
                    check.style.cssText = 'margin-left: auto;';
                    btn.appendChild(check);
                }
            } else {
                btn.style.background = '';
                btn.style.border = '';
                
                const check = btn.querySelector('.selected-check');
                if (check) check.remove();
            }
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
        // Capture and clear callback before timeout to prevent race conditions
        const resolve = this.resolveCallback;
        this.resolveCallback = null;
        const taskId = this.currentTaskId;
        this.currentTaskId = null;
        
        this.overlay.classList.remove('visible');
        this.sheet.classList.remove('visible');
        
        setTimeout(() => {
            this.overlay.style.display = 'none';
            // Resolve with cached callback to prevent overwrites on rapid re-entry
            if (resolve) {
                resolve(result);
            }
        }, 300);
        
        console.log('[TaskPrioritySheet] Closed for task:', taskId, 'with result:', result);
    }

    static isMobile() {
        return window.matchMedia('(max-width: 768px)').matches || 
               ('ontouchstart' in window) ||
               (navigator.maxTouchPoints > 0);
    }
}

window.taskPrioritySheet = new TaskPrioritySheet();
console.log('[TaskPrioritySheet] Initialized');
