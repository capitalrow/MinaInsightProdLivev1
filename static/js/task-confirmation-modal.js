/**
 * Task Confirmation Modal
 * Beautiful, branded confirmation dialogs for destructive actions
 * Replaces browser confirm() with modern UX
 */

class TaskConfirmationModal {
    constructor() {
        this.overlay = null;
        this.modal = null;
        this.resolveCallback = null;
        this.init();
    }

    init() {
        this.createModal();
        this.setupEventListeners();
    }

    createModal() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'task-confirm-overlay';
        this.overlay.innerHTML = `
            <div class="task-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
                <div class="task-confirm-header">
                    <h3 id="confirm-title"></h3>
                    <button class="task-confirm-close" aria-label="Close">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="20" height="20">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
                <div class="task-confirm-body">
                    <p class="task-confirm-message"></p>
                    <div class="task-confirm-details"></div>
                </div>
                <div class="task-confirm-actions">
                    <button class="task-confirm-cancel">Cancel</button>
                    <button class="task-confirm-confirm"></button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.overlay);
        this.modal = this.overlay.querySelector('.task-confirm-modal');
    }

    setupEventListeners() {
        const closeBtn = this.overlay.querySelector('.task-confirm-close');
        const cancelBtn = this.overlay.querySelector('.task-confirm-cancel');
        const confirmBtn = this.overlay.querySelector('.task-confirm-confirm');

        closeBtn.addEventListener('click', () => this.close(false));
        cancelBtn.addEventListener('click', () => this.close(false));
        confirmBtn.addEventListener('click', () => this.close(true));

        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.close(false);
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.overlay.classList.contains('visible')) {
                this.close(false);
            }
        });
    }

    async show(options = {}) {
        const {
            title = 'Confirm Action',
            message = 'Are you sure?',
            details = null,
            confirmText = 'Confirm',
            confirmStyle = 'primary',
            cancelText = 'Cancel'
        } = options;

        this.overlay.querySelector('#confirm-title').textContent = title;
        this.overlay.querySelector('.task-confirm-message').textContent = message;
        
        const detailsEl = this.overlay.querySelector('.task-confirm-details');
        if (details) {
            detailsEl.innerHTML = details;
            detailsEl.style.display = 'block';
        } else {
            detailsEl.innerHTML = '';
            detailsEl.style.display = 'none';
        }

        const confirmBtn = this.overlay.querySelector('.task-confirm-confirm');
        confirmBtn.textContent = confirmText;
        confirmBtn.className = `task-confirm-confirm task-confirm-${confirmStyle}`;

        this.overlay.querySelector('.task-confirm-cancel').textContent = cancelText;

        this.overlay.style.display = 'flex';
        requestAnimationFrame(() => {
            this.overlay.classList.add('visible');
        });

        return new Promise((resolve) => {
            this.resolveCallback = resolve;
        });
    }

    close(confirmed) {
        this.overlay.classList.remove('visible');
        
        setTimeout(() => {
            this.overlay.style.display = 'none';
            if (this.resolveCallback) {
                this.resolveCallback(confirmed);
                this.resolveCallback = null;
            }
        }, 200);
    }

    async confirmDelete(taskTitle) {
        return this.show({
            title: 'Delete task?',
            message: 'This action cannot be undone.',
            details: taskTitle ? `<div class="task-confirm-task-title">"${taskTitle}"</div>` : null,
            confirmText: 'Delete',
            confirmStyle: 'destructive',
            cancelText: 'Cancel'
        });
    }

    async confirmArchive(taskTitle) {
        return this.show({
            title: 'Archive task?',
            message: 'You can restore it later from the archive.',
            details: taskTitle ? `<div class="task-confirm-task-title">"${taskTitle}"</div>` : null,
            confirmText: 'Archive',
            confirmStyle: 'primary',
            cancelText: 'Cancel'
        });
    }
}

window.taskConfirmModal = new TaskConfirmationModal();
