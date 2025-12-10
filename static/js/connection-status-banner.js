/**
 * Connection Status Banner - CROWN⁴ Degraded State UI
 * 
 * Displays a persistent banner when WebSocket connections are degraded,
 * showing retry countdown and manual reconnect button.
 * 
 * Integrates with WebSocketManager events:
 * - connection_degraded: Show banner
 * - connection_recovered: Hide banner
 */

class ConnectionStatusBanner {
    constructor() {
        this.banner = null;
        this.countdownInterval = null;
        this.nextRetryTime = null;
        this.degradedNamespaces = new Set();
        
        this.init();
    }
    
    init() {
        this.createBanner();
        this.setupEventListeners();
    }
    
    createBanner() {
        // Add styles FIRST to prevent flash of unstyled content
        this.addStyles();
        
        if (document.getElementById('connection-status-banner')) {
            this.banner = document.getElementById('connection-status-banner');
            return;
        }
        
        this.banner = document.createElement('div');
        this.banner.id = 'connection-status-banner';
        this.banner.className = 'connection-banner connection-banner-hidden';
        // Inline style ensures banner is hidden even before CSS parses
        this.banner.style.transform = 'translateY(-100%)';
        this.banner.style.visibility = 'hidden';
        this.banner.setAttribute('role', 'alert');
        this.banner.setAttribute('aria-live', 'polite');
        
        this.banner.innerHTML = `
            <div class="connection-banner-content">
                <div class="connection-banner-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                        <line x1="12" y1="9" x2="12" y2="13"></line>
                        <line x1="12" y1="17" x2="12.01" y2="17"></line>
                    </svg>
                </div>
                <div class="connection-banner-text">
                    <span class="connection-banner-message">Realtime updates paused</span>
                    <span class="connection-banner-status">Attempting to reconnect...</span>
                </div>
                <div class="connection-banner-countdown">
                    <span class="countdown-label">Next retry in</span>
                    <span class="countdown-value">--</span>
                </div>
                <button class="connection-banner-retry-btn" type="button">
                    Retry Now
                </button>
                <button class="connection-banner-dismiss" type="button" aria-label="Dismiss">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
        `;
        
        document.body.insertBefore(this.banner, document.body.firstChild);
        
        this.banner.querySelector('.connection-banner-retry-btn').addEventListener('click', () => {
            this.handleManualRetry();
        });
        
        this.banner.querySelector('.connection-banner-dismiss').addEventListener('click', () => {
            this.dismiss();
        });
    }
    
    addStyles() {
        if (document.getElementById('connection-banner-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'connection-banner-styles';
        style.textContent = `
            .connection-banner {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                z-index: 9999;
                background: linear-gradient(135deg, #2c3e50 0%, #1a252f 100%);
                border-bottom: 2px solid #e67e22;
                padding: 12px 16px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                transform: translateY(-100%);
                transition: transform 0.3s ease-out;
            }
            
            .connection-banner.connection-banner-visible {
                transform: translateY(0);
            }
            
            .connection-banner.connection-banner-hidden {
                transform: translateY(-100%);
            }
            
            .connection-banner-content {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 16px;
                max-width: 1200px;
                margin: 0 auto;
                flex-wrap: wrap;
            }
            
            .connection-banner-icon {
                color: #e67e22;
                flex-shrink: 0;
                animation: pulse-warning 2s infinite;
            }
            
            @keyframes pulse-warning {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.6; }
            }
            
            .connection-banner-text {
                display: flex;
                flex-direction: column;
                gap: 2px;
            }
            
            .connection-banner-message {
                color: #fff;
                font-weight: 600;
                font-size: 14px;
            }
            
            .connection-banner-status {
                color: #bdc3c7;
                font-size: 12px;
            }
            
            .connection-banner-countdown {
                display: flex;
                align-items: center;
                gap: 6px;
                padding: 4px 12px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 20px;
            }
            
            .countdown-label {
                color: #bdc3c7;
                font-size: 12px;
            }
            
            .countdown-value {
                color: #e67e22;
                font-weight: 700;
                font-size: 14px;
                min-width: 30px;
                text-align: center;
            }
            
            .connection-banner-retry-btn {
                background: #e67e22;
                color: #fff;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .connection-banner-retry-btn:hover {
                background: #d35400;
                transform: translateY(-1px);
            }
            
            .connection-banner-retry-btn:active {
                transform: translateY(0);
            }
            
            .connection-banner-retry-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            
            .connection-banner-dismiss {
                background: transparent;
                border: none;
                color: #7f8c8d;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                transition: color 0.2s;
            }
            
            .connection-banner-dismiss:hover {
                color: #fff;
            }
            
            @media (max-width: 768px) {
                .connection-banner-content {
                    gap: 10px;
                }
                
                .connection-banner-text {
                    flex: 1;
                    min-width: 0;
                }
                
                .connection-banner-countdown {
                    display: none;
                }
            }
        `;
        
        document.head.appendChild(style);
    }
    
    setupEventListeners() {
        if (!window.wsManager) {
            console.warn('[ConnectionBanner] WebSocketManager not available');
            return;
        }
        
        window.wsManager.on('connection_degraded', (data) => {
            this.show(data);
        });
        
        window.wsManager.on('connection_recovered', (data) => {
            this.hide(data.namespace);
        });
        
        window.wsManager.on('connection_status', (data) => {
            if (data.connected && this.degradedNamespaces.has(data.namespace)) {
                this.hide(data.namespace);
            }
        });
    }
    
    show(data) {
        const { namespace, attempts } = data;
        this.degradedNamespaces.add(namespace);
        
        const statusEl = this.banner.querySelector('.connection-banner-status');
        statusEl.textContent = `Attempting to reconnect (${attempts} attempts)...`;
        
        this.updateCountdown();
        this.startCountdownTimer();
        
        // Remove inline hiding styles when showing
        this.banner.style.visibility = 'visible';
        this.banner.style.transform = '';
        this.banner.classList.remove('connection-banner-hidden');
        this.banner.classList.add('connection-banner-visible');
        
        if (window.toast) {
            window.toast.warning('Connection interrupted. Attempting to reconnect...', 3000);
        }
    }
    
    hide(namespace) {
        this.degradedNamespaces.delete(namespace);
        
        if (this.degradedNamespaces.size === 0) {
            this.stopCountdownTimer();
            
            this.banner.classList.remove('connection-banner-visible');
            this.banner.classList.add('connection-banner-hidden');
            
            if (window.toast) {
                window.toast.success('Connection restored!', 3000);
            }
        }
    }
    
    dismiss() {
        this.banner.classList.remove('connection-banner-visible');
        this.banner.classList.add('connection-banner-hidden');
        this.stopCountdownTimer();
    }
    
    handleManualRetry() {
        const retryBtn = this.banner.querySelector('.connection-banner-retry-btn');
        retryBtn.disabled = true;
        retryBtn.textContent = 'Retrying...';
        
        this.degradedNamespaces.forEach(namespace => {
            if (window.wsManager) {
                window.wsManager.forceReconnect(namespace);
            }
        });
        
        setTimeout(() => {
            retryBtn.disabled = false;
            retryBtn.textContent = 'Retry Now';
        }, 2000);
    }
    
    updateCountdown() {
        const countdownEl = this.banner.querySelector('.countdown-value');
        
        if (!window.wsManager) {
            countdownEl.textContent = '--';
            return;
        }
        
        const namespace = Array.from(this.degradedNamespaces)[0];
        if (!namespace) {
            countdownEl.textContent = '--';
            return;
        }
        
        const attempts = window.wsManager.reconnectAttempts[namespace] || 0;
        let delay;
        
        if (attempts <= 5) {
            delay = Math.min(1000 * Math.pow(2, attempts - 1), 30000);
        } else if (attempts <= 12) {
            delay = 60000;
        } else {
            delay = 120000;
        }
        
        const seconds = Math.ceil(delay / 1000);
        countdownEl.textContent = `${seconds}s`;
    }
    
    startCountdownTimer() {
        this.stopCountdownTimer();
        
        let seconds = 30;
        const countdownEl = this.banner.querySelector('.countdown-value');
        
        this.countdownInterval = setInterval(() => {
            seconds--;
            if (seconds <= 0) {
                this.updateCountdown();
                return;
            }
            countdownEl.textContent = `${seconds}s`;
        }, 1000);
    }
    
    stopCountdownTimer() {
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
    }
}

window.addEventListener('DOMContentLoaded', () => {
    window.connectionStatusBanner = new ConnectionStatusBanner();
});

if (typeof module !== 'undefined' && module.exports) {
    module.exports = ConnectionStatusBanner;
}
