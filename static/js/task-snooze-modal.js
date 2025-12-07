/**
 * Task Snooze Modal
 * Date/time picker for snoozed_until field with smart presets
 */

class TaskSnoozeModal {
    constructor() {
        this.modal = null;
        this.resolveCallback = null;
        this.init();
    }

    init() {
        this.createModal();
        this.setupEventListeners();
    }

    createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'task-snooze-modal-overlay';
        this.modal.innerHTML = `
            <div class="task-snooze-modal">
                <div class="task-snooze-modal-header">
                    <h3>Snooze Task</h3>
                    <button class="task-snooze-modal-close" title="Close">
                        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                    </button>
                </div>
                <div class="task-snooze-modal-body">
                    <div class="task-snooze-info">
                        <svg width="40" height="40" fill="currentColor" viewBox="0 0 24 24" style="opacity: 0.5; margin-bottom: 12px;">
                            <path d="M7.88 3.39L6.6 1.86 2 5.71l1.29 1.53 4.59-3.85zM22 5.72l-4.6-3.86-1.29 1.53 4.6 3.86L22 5.72zM12 4c-4.97 0-9 4.03-9 9s4.02 9 9 9c4.97 0 9-4.03 9-9s-4.03-9-9-9zm0 16c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7zm1-11h-2v6l5.25 3.15.75-1.23-4-2.42V9z"/>
                        </svg>
                        <p>Hide this task until a specific date and time</p>
                    </div>
                    
                    <div class="task-snooze-presets">
                        <button class="task-snooze-preset" data-hours="3">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.2 3.2.8-1.3-4.5-2.7V7z"/>
                            </svg>
                            Later Today (3 hours)
                        </button>
                        <button class="task-snooze-preset" data-hours="24">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.2 3.2.8-1.3-4.5-2.7V7z"/>
                            </svg>
                            Tomorrow
                        </button>
                        <button class="task-snooze-preset" data-days="3">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11z"/>
                            </svg>
                            In 3 Days
                        </button>
                        <button class="task-snooze-preset" data-days="7">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11z"/>
                            </svg>
                            Next Week
                        </button>
                    </div>

                    <div class="task-snooze-custom">
                        <label class="task-snooze-label">Or choose a custom date & time:</label>
                        <input type="datetime-local" 
                               class="task-snooze-datetime-input" 
                               min="">
                    </div>
                </div>
                <div class="task-snooze-modal-footer">
                    <button class="btn-secondary task-snooze-cancel">Cancel</button>
                    <button class="btn-primary task-snooze-save">Snooze Task</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.modal);
    }

    setupEventListeners() {
        const closeBtn = this.modal.querySelector('.task-snooze-modal-close');
        const cancelBtn = this.modal.querySelector('.task-snooze-cancel');
        const saveBtn = this.modal.querySelector('.task-snooze-save');
        const datetimeInput = this.modal.querySelector('.task-snooze-datetime-input');
        const presets = this.modal.querySelectorAll('.task-snooze-preset');

        closeBtn.addEventListener('click', () => this.close(null));
        cancelBtn.addEventListener('click', () => this.close(null));
        saveBtn.addEventListener('click', () => {
            const value = datetimeInput.value;
            if (value) {
                this.close(new Date(value).toISOString());
            } else {
                window.toast?.error('Please select a date and time');
            }
        });

        presets.forEach(btn => {
            btn.addEventListener('click', () => {
                const hours = parseInt(btn.dataset.hours);
                const days = parseInt(btn.dataset.days);
                
                const snoozeUntil = new Date();
                if (hours) {
                    snoozeUntil.setHours(snoozeUntil.getHours() + hours);
                } else if (days) {
                    snoozeUntil.setDate(snoozeUntil.getDate() + days);
                }
                
                this.setDatetimeInput(snoozeUntil);
                presets.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });

        datetimeInput.addEventListener('change', () => {
            presets.forEach(btn => btn.classList.remove('active'));
        });

        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close(null);
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('visible')) {
                this.close(null);
            }
        });
    }

    async show(currentSnoozeUntil = null) {
        const datetimeInput = this.modal.querySelector('.task-snooze-datetime-input');
        
        const now = new Date();
        datetimeInput.min = now.toISOString().slice(0, 16);
        
        if (currentSnoozeUntil) {
            this.setDatetimeInput(new Date(currentSnoozeUntil));
        } else {
            datetimeInput.value = '';
        }

        const presets = this.modal.querySelectorAll('.task-snooze-preset');
        presets.forEach(btn => btn.classList.remove('active'));

        this.modal.classList.remove('hidden');
        this.modal.style.display = 'flex';
        requestAnimationFrame(() => {
            this.modal.classList.add('visible');
        });

        return new Promise((resolve) => {
            this.resolveCallback = resolve;
        });
    }

    setDatetimeInput(date) {
        const datetimeInput = this.modal.querySelector('.task-snooze-datetime-input');
        const localISOTime = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
            .toISOString()
            .slice(0, 16);
        datetimeInput.value = localISOTime;
    }

    close(result) {
        this.modal.classList.remove('visible');
        
        setTimeout(() => {
            this.modal.style.display = 'none';
            if (this.resolveCallback) {
                this.resolveCallback(result);
                this.resolveCallback = null;
            }
        }, 200);
    }
}

window.taskSnoozeModal = new TaskSnoozeModal();
