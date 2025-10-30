/**
 * CROWN⁴.5 Offline Indicators
 * Visual feedback for offline state and queue status.
 * - Tiny cloud icon (offline indicator)
 * - "Offline" toast (one-time notification)
 * - Queue size badge
 */

class OfflineIndicators {
    constructor() {
        this.isOffline = !navigator.onLine;
        this.cloudIcon = null;
        this.queueBadge = null;
        this.hasShownOfflineToast = false;
        
        this._init();
        this._setupListeners();
        
        console.log('[OfflineIndicators] Initialized');
    }

    /**
     * Initialize UI elements
     */
    _init() {
        this._createCloudIcon();
        this._updateStatus();
    }

    /**
     * Create cloud icon indicator
     */
    _createCloudIcon() {
        // Check if already exists
        if (document.getElementById('offline-cloud-icon')) {
            this.cloudIcon = document.getElementById('offline-cloud-icon');
            return;
        }

        // Create cloud icon container
        const container = document.createElement('div');
        container.id = 'offline-cloud-icon';
        container.className = 'offline-indicator';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            opacity: 0;
            transition: opacity 300ms ease-out;
            pointer-events: none;
        `;

        // Cloud icon SVG
        container.innerHTML = `
            <div class="cloud-icon-wrapper" style="
                background: rgba(0, 0, 0, 0.8);
                backdrop-filter: blur(8px);
                border-radius: 12px;
                padding: 8px 12px;
                display: flex;
                align-items: center;
                gap: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            ">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                     style="color: #f59e0b;">
                    <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path>
                    <line x1="12" y1="12" x2="12" y2="16"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                </svg>
                <span class="offline-text" style="
                    color: #f59e0b;
                    font-size: 14px;
                    font-weight: 500;
                ">Offline</span>
                <span class="queue-badge" style="
                    background: #f59e0b;
                    color: #000;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 2px 6px;
                    border-radius: 6px;
                    min-width: 18px;
                    text-align: center;
                    display: none;
                ">0</span>
            </div>
        `;

        document.body.appendChild(container);
        this.cloudIcon = container;
        this.queueBadge = container.querySelector('.queue-badge');
    }

    /**
     * Setup network status listeners
     */
    _setupListeners() {
        // Online/offline events
        window.addEventListener('online', () => {
            this.isOffline = false;
            this._updateStatus();
            this._showToast('Back online - syncing...', 'success');
        });

        window.addEventListener('offline', () => {
            this.isOffline = true;
            this._updateStatus();
            
            if (!this.hasShownOfflineToast) {
                this._showToast('Offline - changes will be queued', 'warning');
                this.hasShownOfflineToast = true;
            }
        });

        // Listen for offline queue updates
        window.addEventListener('offline_queue_updated', (e) => {
            this._updateQueueSize(e.detail.queueSize || 0);
        });
    }

    /**
     * Update offline status UI
     */
    _updateStatus() {
        if (!this.cloudIcon) return;

        if (this.isOffline) {
            // Show cloud icon
            this.cloudIcon.style.opacity = '1';
            this.cloudIcon.style.pointerEvents = 'auto';
        } else {
            // Hide cloud icon after 2s (smooth reconnect)
            setTimeout(() => {
                this.cloudIcon.style.opacity = '0';
                this.cloudIcon.style.pointerEvents = 'none';
            }, 2000);
        }
    }

    /**
     * Update queue size badge
     * @param {number} size - Queue size
     */
    _updateQueueSize(size) {
        if (!this.queueBadge) return;

        if (size > 0) {
            this.queueBadge.textContent = size;
            this.queueBadge.style.display = 'block';
        } else {
            this.queueBadge.style.display = 'none';
        }
    }

    /**
     * Show toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type (success, warning, error, info)
     */
    _showToast(message, type = 'info') {
        // Use existing toast system if available
        if (window.showToast) {
            window.showToast(message, type);
            return;
        }

        // Fallback: create simple toast
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 10000;
            background: ${this._getToastColor(type)};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            font-size: 14px;
            font-weight: 500;
            opacity: 0;
            transform: translateY(20px);
            transition: all 300ms cubic-bezier(0.4, 0.0, 0.2, 1);
        `;
        toast.textContent = message;

        document.body.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        });

        // Animate out and remove
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(20px)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * Get toast background color
     * @param {string} type
     * @returns {string} Color
     */
    _getToastColor(type) {
        const colors = {
            success: '#10b981',
            warning: '#f59e0b',
            error: '#ef4444',
            info: '#3b82f6'
        };
        return colors[type] || colors.info;
    }

    /**
     * Manually show offline state (for testing)
     */
    showOffline() {
        this.isOffline = true;
        this._updateStatus();
        this._showToast('Offline mode activated', 'warning');
    }

    /**
     * Manually show online state (for testing)
     */
    showOnline() {
        this.isOffline = false;
        this._updateStatus();
        this._showToast('Back online', 'success');
    }
}

// Initialize global instance
window.OfflineIndicators = OfflineIndicators;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.offlineIndicators) {
            window.offlineIndicators = new OfflineIndicators();
            console.log('[OfflineIndicators] Global instance created');
        }
    });
}
