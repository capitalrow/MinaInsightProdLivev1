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
            <div class="task-sheet task-date-sheet" style="
                width: 100%;
                max-width: 500px;
                background: #1e293b;
                border-radius: 20px 20px 0 0;
                overflow: hidden;
                box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.5);
            ">
                <div style="width: 36px; height: 5px; background: #475569; border-radius: 3px; margin: 12px auto 8px;"></div>
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 20px 16px; border-bottom: 1px solid rgba(255,255,255,0.1);">
                    <div>
                        <h3 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0;">Set Due Date</h3>
                        <span class="current-selection-display" style="font-size: 13px; color: #94a3b8; display: none;"></span>
                    </div>
                    <button class="task-sheet-close" aria-label="Close" style="width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.05); border: none; border-radius: 50%; color: #94a3b8; cursor: pointer;">
                        <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
                <div style="padding: 16px 20px 32px;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 20px;">
                        <button class="task-sheet-preset" data-preset="today" style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 14px 16px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; color: #f8fafc; cursor: pointer; transition: all 0.15s ease; min-height: 64px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <svg width="16" height="16" fill="none" stroke="#94a3b8" viewBox="0 0 24 24">
                                    <circle cx="12" cy="12" r="10" stroke-width="2"/>
                                    <path stroke-linecap="round" stroke-width="2" d="M12 6v6l4 2"/>
                                </svg>
                                <span style="font-size: 14px; font-weight: 600;">Today</span>
                            </div>
                            <span class="preset-date" style="font-size: 12px; color: #64748b;"></span>
                        </button>
                        <button class="task-sheet-preset" data-preset="tomorrow" style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 14px 16px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; color: #f8fafc; cursor: pointer; transition: all 0.15s ease; min-height: 64px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <svg width="16" height="16" fill="none" stroke="#94a3b8" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707"/>
                                </svg>
                                <span style="font-size: 14px; font-weight: 600;">Tomorrow</span>
                            </div>
                            <span class="preset-date" style="font-size: 12px; color: #64748b;"></span>
                        </button>
                        <button class="task-sheet-preset" data-preset="next-week" style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 14px 16px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; color: #f8fafc; cursor: pointer; transition: all 0.15s ease; min-height: 64px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <svg width="16" height="16" fill="none" stroke="#94a3b8" viewBox="0 0 24 24">
                                    <rect x="3" y="4" width="18" height="18" rx="2" stroke-width="2"/>
                                    <path stroke-linecap="round" stroke-width="2" d="M16 2v4M8 2v4M3 10h18"/>
                                </svg>
                                <span style="font-size: 14px; font-weight: 600;">Next Week</span>
                            </div>
                            <span class="preset-date" style="font-size: 12px; color: #64748b;"></span>
                        </button>
                        <button class="task-sheet-preset" data-preset="next-month" style="display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 14px 16px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; color: #f8fafc; cursor: pointer; transition: all 0.15s ease; min-height: 64px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <svg width="16" height="16" fill="none" stroke="#94a3b8" viewBox="0 0 24 24">
                                    <rect x="3" y="4" width="18" height="18" rx="2" stroke-width="2"/>
                                    <path stroke-linecap="round" stroke-width="2" d="M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>
                                </svg>
                                <span style="font-size: 14px; font-weight: 600;">Next Month</span>
                            </div>
                            <span class="preset-date" style="font-size: 12px; color: #64748b;"></span>
                        </button>
                    </div>
                    
                    <div style="height: 1px; background: rgba(255,255,255,0.1); margin: 16px 0;"></div>
                    
                    <div style="margin-bottom: 20px;">
                        <label style="display: block; font-size: 13px; font-weight: 500; color: #94a3b8; margin-bottom: 8px;">Custom date</label>
                        <input type="date" class="task-sheet-date-input" style="width: 100%; padding: 14px 16px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; color: #f8fafc; font-size: 16px; box-sizing: border-box;" />
                    </div>
                    
                    <div style="display: flex; gap: 12px;">
                        <button class="task-sheet-clear" style="flex: 1; padding: 14px 20px; border-radius: 12px; font-size: 15px; font-weight: 600; cursor: pointer; background: transparent; border: 1px solid rgba(239,68,68,0.3); color: #f87171; transition: all 0.15s ease;">Clear</button>
                        <button class="task-sheet-apply" style="flex: 1; padding: 14px 20px; border-radius: 12px; font-size: 15px; font-weight: 600; cursor: pointer; background: #3b82f6; border: none; color: white; transition: all 0.15s ease;">Apply</button>
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
            // Helper to reset button state
            const resetBtn = () => {
                btn.style.transform = '';
                btn.style.background = '';
                btn.style.borderColor = '';
            };
            
            // Touch feedback on press
            btn.addEventListener('touchstart', () => {
                btn.style.transform = 'scale(0.97)';
                btn.style.background = 'rgba(59, 130, 246, 0.15)';
                btn.style.borderColor = 'rgba(59, 130, 246, 0.4)';
            }, { passive: true });
            
            btn.addEventListener('touchend', resetBtn, { passive: true });
            btn.addEventListener('touchcancel', resetBtn, { passive: true });
            btn.addEventListener('touchmove', resetBtn, { passive: true });
            
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

    formatRelativeDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        
        const diff = Math.floor((date - today) / (1000 * 60 * 60 * 24));
        
        if (diff === 0) return 'Today';
        if (diff === 1) return 'Tomorrow';
        if (diff === -1) return 'Yesterday';
        if (diff > 1 && diff <= 7) return `${dayNames[date.getDay()]}`;
        
        return `${dayNames[date.getDay()]}, ${monthNames[date.getMonth()]} ${date.getDate()}`;
    }

    updatePresetLabels() {
        const presets = this.overlay.querySelectorAll('.task-sheet-preset');
        const today = new Date();
        
        const dates = {
            'today': this.formatRelativeDate(today.toISOString().split('T')[0]),
            'tomorrow': (() => {
                const d = new Date(today);
                d.setDate(today.getDate() + 1);
                return this.formatRelativeDate(d.toISOString().split('T')[0]);
            })(),
            'next-week': (() => {
                const d = new Date(today);
                d.setDate(today.getDate() + 7);
                return this.formatRelativeDate(d.toISOString().split('T')[0]);
            })(),
            'next-month': (() => {
                const d = new Date(today);
                d.setMonth(today.getMonth() + 1);
                return this.formatRelativeDate(d.toISOString().split('T')[0]);
            })()
        };
        
        presets.forEach(btn => {
            const preset = btn.dataset.preset;
            const existingSubtext = btn.querySelector('.preset-date');
            if (existingSubtext) {
                existingSubtext.textContent = dates[preset] || '';
            }
        });
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

        // Update preset labels with relative dates
        this.updatePresetLabels();
        
        // Show current selection in header if date exists
        const selectionDisplay = this.overlay.querySelector('.current-selection-display');
        if (selectionDisplay) {
            if (currentDate) {
                const formattedDate = this.formatRelativeDate(currentDate.split('T')[0]);
                selectionDisplay.textContent = `Currently: ${formattedDate}`;
                selectionDisplay.style.display = 'block';
            } else {
                selectionDisplay.textContent = '';
                selectionDisplay.style.display = 'none';
            }
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
        
        console.log('[TaskDateSheet] Closed for task:', taskId, 'with result:', result);
    }

    static isMobile() {
        return window.matchMedia('(max-width: 768px)').matches || 
               ('ontouchstart' in window) ||
               (navigator.maxTouchPoints > 0);
    }
}

window.taskDateSheet = new TaskDateSheet();
console.log('[TaskDateSheet] Initialized');
