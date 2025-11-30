/**
 * Toast Notification System (CROWN⁴ Phase 4)
 * Provides undo functionality for archive operations
 */

class ToastNotification {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Create toast container if it doesn't exist
        if (!document.getElementById('toast-container')) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('toast-container');
        }
    }

    /**
     * Show a toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type (success, error, info, warning)
     * @param {number} duration - Duration in ms (0 = persistent)
     * @param {Object} options - Additional options (undoCallback, undoText)
     */
    show(message, type = 'info', duration = 5000, options = {}) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // Build toast content
        const content = document.createElement('div');
        content.className = 'toast-content';
        
        const messageEl = document.createElement('span');
        messageEl.className = 'toast-message';
        messageEl.textContent = message;
        content.appendChild(messageEl);
        
        // Add undo button if callback provided
        if (options.undoCallback) {
            const undoBtn = document.createElement('button');
            undoBtn.className = 'toast-undo-btn';
            undoBtn.textContent = options.undoText || 'Undo';
            undoBtn.onclick = () => {
                options.undoCallback();
                this.remove(toast);
            };
            content.appendChild(undoBtn);
        }
        
        toast.appendChild(content);
        
        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '×';
        closeBtn.onclick = () => this.remove(toast);
        toast.appendChild(closeBtn);
        
        // Add to container with animation
        this.container.appendChild(toast);
        
        // Trigger animation
        requestAnimationFrame(() => {
            toast.classList.add('toast-show');
        });
        
        // Auto-remove after duration (if not persistent)
        if (duration > 0) {
            setTimeout(() => {
                this.remove(toast);
            }, duration);
        }
        
        return toast;
    }

    remove(toast) {
        toast.classList.remove('toast-show');
        toast.classList.add('toast-hide');
        
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    success(message, duration = 3000, options = {}) {
        return this.show(message, 'success', duration, options);
    }

    error(message, duration = 5000, options = {}) {
        return this.show(message, 'error', duration, options);
    }

    warning(message, duration = 4000, options = {}) {
        return this.show(message, 'warning', duration, options);
    }

    info(message, duration = 3000, options = {}) {
        return this.show(message, 'info', duration, options);
    }
}

// Global toast instance
window.toast = new ToastNotification();

// Compatibility with existing code
window.showToast = function(message, type = 'info', duration = 3000) {
    window.toast.show(message, type, duration);
};
