/**
 * MINA CROWN+ INTERACTIVE COMPONENTS SYSTEM
 * Premium interactive UI components using Crown+ Design System
 * - Toast Notifications (with reduced motion support)
 * - Modal Dialogs (with focus trapping)
 * - Loading States
 * - Skeleton Loaders
 */

class CrownToast {
    constructor() {
        this.container = null;
        this.toasts = new Map();
        this.prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        this.init();
    }

    init() {
        if (!document.getElementById('crown-toast-container')) {
            this.container = document.createElement('div');
            this.container.id = 'crown-toast-container';
            this.container.className = 'crown-toast-container';
            this.container.setAttribute('aria-live', 'polite');
            this.container.setAttribute('aria-atomic', 'false');
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('crown-toast-container');
        }

        window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
            this.prefersReducedMotion = e.matches;
        });
    }

    show(options = {}) {
        const {
            title = '',
            message = '',
            type = 'info',
            duration = 5000,
            closable = true
        } = options;

        const toastId = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');

        const iconMap = {
            success: 'fas fa-check-circle',
            error: 'fas fa-times-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        toast.innerHTML = `
            <div class="toast-icon">
                <i class="${iconMap[type] || iconMap.info}"></i>
            </div>
            <div class="toast-content">
                ${title ? `<div class="toast-title">${title}</div>` : ''}
                <div class="toast-message">${message}</div>
            </div>
            ${closable ? `
                <button class="toast-close" aria-label="Close notification">
                    <i class="fas fa-times"></i>
                </button>
            ` : ''}
        `;

        if (closable) {
            const closeBtn = toast.querySelector('.toast-close');
            closeBtn.addEventListener('click', () => this.dismiss(toastId));
        }

        this.container.appendChild(toast);
        this.toasts.set(toastId, toast);

        if (!this.prefersReducedMotion) {
            requestAnimationFrame(() => {
                toast.style.animation = 'slide-in-right 0.3s ease-out';
            });
        }

        if (duration > 0) {
            setTimeout(() => this.dismiss(toastId), duration);
        }

        return toastId;
    }

    dismiss(toastId) {
        const toast = this.toasts.get(toastId);
        if (!toast || !toast.parentElement) return;

        if (!this.prefersReducedMotion) {
            toast.style.animation = 'slide-out-right 0.3s ease-in';
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.remove();
                }
                this.toasts.delete(toastId);
            }, 300);
        } else {
            toast.remove();
            this.toasts.delete(toastId);
        }
    }

    success(message, title = 'Success') {
        return this.show({ message, title, type: 'success' });
    }

    error(message, title = 'Error') {
        return this.show({ message, title, type: 'error', duration: 8000 });
    }

    warning(message, title = 'Warning') {
        return this.show({ message, title, type: 'warning', duration: 6000 });
    }

    info(message, title = '') {
        return this.show({ message, title, type: 'info' });
    }

    clearAll() {
        this.toasts.forEach((toast, id) => this.dismiss(id));
    }
}

class CrownModal {
    constructor() {
        this.activeModal = null;
        this.previousFocus = null;
        this.focusableElements = [];
        this.prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        this.init();
    }

    init() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'crown-modal-overlay';
        this.overlay.style.display = 'none';
        document.body.appendChild(this.overlay);

        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.close();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal) {
                this.close();
            } else if (e.key === 'Tab' && this.activeModal) {
                this.handleTabKey(e);
            }
        });

        window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
            this.prefersReducedMotion = e.matches;
        });
    }

    handleTabKey(e) {
        if (!this.activeModal) return;

        if (this.focusableElements.length === 0) {
            e.preventDefault();
            this.activeModal.focus();
            return;
        }

        const firstElement = this.focusableElements[0];
        const lastElement = this.focusableElements[this.focusableElements.length - 1];

        if (e.shiftKey) {
            if (document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
            }
        } else {
            if (document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
            }
        }
    }

    getFocusableElements(modal) {
        const focusableSelectors = [
            'a[href]',
            'button:not([disabled])',
            'textarea:not([disabled])',
            'input:not([disabled])',
            'select:not([disabled])',
            '[tabindex]:not([tabindex="-1"])'
        ].join(',');

        return Array.from(modal.querySelectorAll(focusableSelectors));
    }

    show(options = {}) {
        const {
            title = '',
            content = '',
            type = 'default',
            showClose = true,
            buttons = []
        } = options;

        this.previousFocus = document.activeElement;

        const modal = document.createElement('div');
        modal.className = `crown-modal crown-modal-${type}`;
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-labelledby', 'modal-title');
        modal.setAttribute('tabindex', '-1');

        modal.innerHTML = `
            <div class="crown-modal-header">
                <h2 class="crown-modal-title" id="modal-title">${title}</h2>
                ${showClose ? `
                    <button class="crown-modal-close" aria-label="Close dialog">
                        <i class="fas fa-times"></i>
                    </button>
                ` : ''}
            </div>
            <div class="crown-modal-body">
                ${content}
            </div>
            ${buttons.length > 0 ? `
                <div class="crown-modal-footer">
                    ${buttons.map(btn => `
                        <button class="btn ${btn.className || 'btn-secondary'}" data-action="${btn.action || 'close'}">
                            ${btn.label || 'OK'}
                        </button>
                    `).join('')}
                </div>
            ` : ''}
        `;

        this.overlay.innerHTML = '';
        this.overlay.appendChild(modal);
        this.overlay.style.display = 'flex';
        this.activeModal = modal;

        if (showClose) {
            const closeBtn = modal.querySelector('.crown-modal-close');
            closeBtn.addEventListener('click', () => this.close());
        }

        const actionBtns = modal.querySelectorAll('[data-action]');
        actionBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.getAttribute('data-action');
                if (action === 'close') {
                    this.close();
                } else if (options.onAction) {
                    options.onAction(action);
                }
            });
        });

        this.focusableElements = this.getFocusableElements(modal);
        
        if (!this.prefersReducedMotion) {
            modal.style.animation = 'modal-fade-in 0.3s ease-out';
        }
        
        document.body.style.overflow = 'hidden';

        setTimeout(() => {
            if (this.focusableElements.length > 0) {
                this.focusableElements[0].focus();
            } else {
                modal.focus();
            }
        }, 10);

        return modal;
    }

    close() {
        if (!this.activeModal) return;

        if (!this.prefersReducedMotion) {
            this.activeModal.style.animation = 'modal-fade-out 0.3s ease-in';
            setTimeout(() => {
                this.cleanup();
            }, 300);
        } else {
            this.cleanup();
        }
    }

    cleanup() {
        this.overlay.style.display = 'none';
        this.overlay.innerHTML = '';
        this.activeModal = null;
        this.focusableElements = [];
        document.body.style.overflow = '';

        if (this.previousFocus && typeof this.previousFocus.focus === 'function') {
            this.previousFocus.focus();
        }
        this.previousFocus = null;
    }

    confirm(options = {}) {
        return new Promise((resolve) => {
            const confirmOptions = {
                ...options,
                buttons: [
                    { label: options.cancelLabel || 'Cancel', className: 'btn-secondary', action: 'cancel' },
                    { label: options.confirmLabel || 'Confirm', className: 'btn-primary', action: 'confirm' }
                ],
                onAction: (action) => {
                    this.close();
                    resolve(action === 'confirm');
                }
            };
            this.show(confirmOptions);
        });
    }

    alert(options = {}) {
        return new Promise((resolve) => {
            const alertOptions = {
                ...options,
                buttons: [
                    { label: options.buttonLabel || 'OK', className: 'btn-primary', action: 'close' }
                ],
                onAction: () => {
                    this.close();
                    resolve();
                }
            };
            this.show(alertOptions);
        });
    }
}

class CrownLoading {
    constructor() {
        this.overlay = null;
        this.init();
    }

    init() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'loading-overlay';
        this.overlay.style.display = 'none';
        this.overlay.setAttribute('role', 'status');
        this.overlay.setAttribute('aria-live', 'polite');

        this.overlay.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner"></div>
                <div class="loading-message">Loading...</div>
            </div>
        `;

        document.body.appendChild(this.overlay);
    }

    show(message = 'Loading...') {
        const messageEl = this.overlay.querySelector('.loading-message');
        if (messageEl) {
            messageEl.textContent = message;
        }
        this.overlay.style.display = 'flex';
    }

    hide() {
        this.overlay.style.display = 'none';
    }
}

const CrownUI = {
    toast: null,
    modal: null,
    loading: null,

    init() {
        this.toast = new CrownToast();
        this.modal = new CrownModal();
        this.loading = new CrownLoading();
        this.addStyles();
        console.log('✨ Crown+ Interactive Components initialized');
    },

    addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .crown-toast-container {
                position: fixed;
                top: 80px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 12px;
                pointer-events: none;
            }

            .crown-toast-container > * {
                pointer-events: all;
            }

            .toast-close {
                background: none;
                border: none;
                color: var(--text-secondary);
                cursor: pointer;
                padding: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: var(--radius-md);
                transition: all 0.2s ease;
            }

            .toast-close:hover {
                background: rgba(255, 255, 255, 0.1);
                color: var(--text-primary);
            }

            .toast-close:focus {
                outline: 2px solid var(--color-brand-500);
                outline-offset: 2px;
            }

            @media (prefers-reduced-motion: no-preference) {
                @keyframes slide-in-right {
                    from {
                        opacity: 0;
                        transform: translateX(100px);
                    }
                    to {
                        opacity: 1;
                        transform: translateX(0);
                    }
                }

                @keyframes slide-out-right {
                    to {
                        opacity: 0;
                        transform: translateX(100px);
                    }
                }
            }

            .crown-modal-overlay {
                position: fixed;
                inset: 0;
                background: rgba(10, 14, 26, 0.8);
                backdrop-filter: blur(8px);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
                padding: 20px;
            }

            .crown-modal {
                background: var(--surface-primary);
                border: 1px solid var(--border-primary);
                border-radius: var(--radius-2xl);
                box-shadow: var(--shadow-2xl);
                max-width: 500px;
                width: 100%;
                max-height: 90vh;
                overflow: hidden;
                display: flex;
                flex-direction: column;
            }

            .crown-modal:focus {
                outline: 2px solid var(--color-brand-500);
                outline-offset: 4px;
            }

            .crown-modal-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: var(--space-6);
                border-bottom: 1px solid var(--border-primary);
            }

            .crown-modal-title {
                font-size: var(--font-size-xl);
                font-weight: var(--font-weight-semibold);
                color: var(--text-primary);
                margin: 0;
            }

            .crown-modal-close {
                background: none;
                border: none;
                color: var(--text-secondary);
                cursor: pointer;
                padding: var(--space-2);
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: var(--radius-md);
                transition: all 0.2s ease;
            }

            .crown-modal-close:hover {
                background: var(--surface-secondary);
                color: var(--text-primary);
            }

            .crown-modal-close:focus {
                outline: 2px solid var(--color-brand-500);
                outline-offset: 2px;
            }

            .crown-modal-body {
                padding: var(--space-6);
                overflow-y: auto;
                flex: 1;
            }

            .crown-modal-footer {
                display: flex;
                align-items: center;
                justify-content: flex-end;
                gap: var(--space-3);
                padding: var(--space-6);
                border-top: 1px solid var(--border-primary);
            }

            @media (prefers-reduced-motion: no-preference) {
                @keyframes modal-fade-in {
                    from {
                        opacity: 0;
                        transform: scale(0.95) translateY(-20px);
                    }
                    to {
                        opacity: 1;
                        transform: scale(1) translateY(0);
                    }
                }

                @keyframes modal-fade-out {
                    to {
                        opacity: 0;
                        transform: scale(0.95) translateY(-20px);
                    }
                }
            }

            @keyframes spinner-rotate {
                to {
                    transform: rotate(360deg);
                }
            }

            .loading-content {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: var(--space-4);
            }

            .loading-message {
                font-size: var(--font-size-base);
                font-weight: var(--font-weight-medium);
                color: var(--text-primary);
            }
        `;
        document.head.appendChild(style);
    }
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => CrownUI.init());
} else {
    CrownUI.init();
}

window.CrownUI = CrownUI;
