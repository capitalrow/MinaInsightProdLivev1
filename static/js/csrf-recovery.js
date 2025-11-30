/**
 * Enterprise CSRF Recovery Module
 * 
 * Implements industry-standard patterns used by Slack, Notion, Figma:
 * 1. Silent auto-retry with fresh token on 419 errors
 * 2. Form data preservation before reload
 * 3. Multi-tab token synchronization
 * 4. User-friendly error handling
 */

(function() {
    'use strict';

    const CSRF_RECOVERY = {
        maxRetries: 1,
        syncChannel: null,
        
        init() {
            this.setupBroadcastChannel();
            this.interceptFetch();
            this.setupFormRecovery();
            console.log('[CSRF] Recovery module initialized');
        },
        
        setupBroadcastChannel() {
            if ('BroadcastChannel' in window) {
                this.syncChannel = new BroadcastChannel('mina_csrf_sync');
                this.syncChannel.onmessage = (event) => {
                    if (event.data.type === 'TOKEN_REFRESH') {
                        this.updateToken(event.data.token);
                        console.log('[CSRF] Token synced from another tab');
                    }
                };
            }
        },
        
        broadcastTokenRefresh(token) {
            if (this.syncChannel) {
                this.syncChannel.postMessage({ 
                    type: 'TOKEN_REFRESH', 
                    token: token 
                });
            }
        },
        
        getToken() {
            const meta = document.querySelector('meta[name="csrf-token"]');
            return meta ? meta.getAttribute('content') : null;
        },
        
        updateToken(newToken) {
            const meta = document.querySelector('meta[name="csrf-token"]');
            if (meta) {
                meta.setAttribute('content', newToken);
            }
            
            document.querySelectorAll('input[name="csrf_token"]').forEach(input => {
                input.value = newToken;
            });
        },
        
        async fetchFreshToken() {
            try {
                const response = await fetch('/api/csrf-token', {
                    method: 'GET',
                    credentials: 'same-origin'
                });
                
                if (response.ok) {
                    const data = await response.json();
                    return data.token;
                }
            } catch (e) {
                console.error('[CSRF] Failed to fetch fresh token:', e);
            }
            return null;
        },
        
        interceptFetch() {
            const originalFetch = window.fetch;
            const self = this;
            
            window.fetch = async function(url, options = {}) {
                const response = await originalFetch(url, options);
                
                if (response.status === 419) {
                    const data = await response.clone().json().catch(() => ({}));
                    
                    if (data.new_token && data.refresh_required) {
                        console.log('[CSRF] Token expired, auto-recovering...');
                        
                        self.updateToken(data.new_token);
                        self.broadcastTokenRefresh(data.new_token);
                        
                        if (options._retryCount === undefined) {
                            options._retryCount = 0;
                        }
                        
                        if (options._retryCount < self.maxRetries) {
                            options._retryCount++;
                            
                            if (options.headers) {
                                options.headers['X-CSRFToken'] = data.new_token;
                            }
                            
                            if (options.body instanceof FormData) {
                                options.body.set('csrf_token', data.new_token);
                            }
                            
                            console.log('[CSRF] Retrying request with fresh token...');
                            return originalFetch(url, options);
                        }
                    }
                }
                
                return response;
            };
        },
        
        setupFormRecovery() {
            document.addEventListener('submit', (e) => {
                const form = e.target;
                if (form.tagName === 'FORM') {
                    this.saveFormData(form);
                }
            });
            
            window.addEventListener('load', () => {
                this.restoreFormData();
            });
        },
        
        saveFormData(form) {
            try {
                const formData = new FormData(form);
                const data = {};
                
                formData.forEach((value, key) => {
                    if (key !== 'csrf_token' && key !== 'password') {
                        data[key] = value;
                    }
                });
                
                if (Object.keys(data).length > 0) {
                    sessionStorage.setItem('mina_form_recovery', JSON.stringify({
                        data: data,
                        url: window.location.href,
                        timestamp: Date.now()
                    }));
                }
            } catch (e) {
                console.warn('[CSRF] Could not save form data:', e);
            }
        },
        
        restoreFormData() {
            try {
                const saved = sessionStorage.getItem('mina_form_recovery');
                if (!saved) return;
                
                const { data, url, timestamp } = JSON.parse(saved);
                
                if (Date.now() - timestamp > 5 * 60 * 1000) {
                    sessionStorage.removeItem('mina_form_recovery');
                    return;
                }
                
                if (window.location.href !== url) {
                    return;
                }
                
                Object.entries(data).forEach(([key, value]) => {
                    const input = document.querySelector(`[name="${key}"]`);
                    if (input && !input.value) {
                        input.value = value;
                    }
                });
                
                sessionStorage.removeItem('mina_form_recovery');
                
                this.showToast('Your previous entry has been restored.', 'info');
                console.log('[CSRF] Form data restored');
                
            } catch (e) {
                console.warn('[CSRF] Could not restore form data:', e);
            }
        },
        
        showToast(message, type = 'info') {
            if (window.showToast) {
                window.showToast(message, type);
                return;
            }
            
            const toast = document.createElement('div');
            toast.className = `csrf-toast csrf-toast-${type}`;
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                padding: 12px 20px;
                background: var(--color-surface-elevated, #2d2d2d);
                color: var(--color-text-primary, #fff);
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                z-index: 10000;
                animation: slideIn 0.3s ease;
            `;
            
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => CSRF_RECOVERY.init());
    } else {
        CSRF_RECOVERY.init();
    }
    
    window.CSRFRecovery = CSRF_RECOVERY;

})();
