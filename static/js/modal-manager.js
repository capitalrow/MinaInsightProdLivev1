/**
 * CROWN Global Modal Manager
 * Centralized modal lifecycle management to prevent stacking
 * 
 * Features:
 * - Single active modal enforcement
 * - Promise-based open/close API
 * - Focus trapping and body scroll lock
 * - Queue management for rapid interactions
 */

class ModalManager {
    constructor() {
        if (ModalManager.instance) {
            return ModalManager.instance;
        }
        
        this.activeModal = null;
        this.modalQueue = [];
        this.isTransitioning = false;
        this.registeredModals = new Map();
        this.previousActiveElement = null;
        
        this.init();
        ModalManager.instance = this;
    }
    
    static getInstance() {
        if (!ModalManager.instance) {
            ModalManager.instance = new ModalManager();
        }
        return ModalManager.instance;
    }
    
    init() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal) {
                e.preventDefault();
                this.close();
            }
        });
        
        console.log('[ModalManager] Initialized');
    }
    
    register(id, modalConfig) {
        this.registeredModals.set(id, {
            element: modalConfig.element,
            onOpen: modalConfig.onOpen || (() => {}),
            onClose: modalConfig.onClose || (() => {}),
            focusFirst: modalConfig.focusFirst || null
        });
    }
    
    unregister(id) {
        this.registeredModals.delete(id);
    }
    
    async open(modalElement, options = {}) {
        if (this.isTransitioning) {
            return new Promise((resolve, reject) => {
                this.modalQueue.push({ modalElement, options, resolve, reject });
            });
        }
        
        if (this.activeModal) {
            await this.close();
        }
        
        return new Promise((resolve) => {
            this.isTransitioning = true;
            this.previousActiveElement = document.activeElement;
            
            this.lockScroll();
            
            this.activeModal = modalElement;
            modalElement.classList.add('visible', 'show');
            modalElement.setAttribute('aria-hidden', 'false');
            
            const handleTransitionEnd = () => {
                this.isTransitioning = false;
                modalElement.removeEventListener('transitionend', handleTransitionEnd);
                
                this.trapFocus(modalElement);
                
                if (options.onOpen) {
                    options.onOpen();
                }
                
                resolve(true);
                
                this.processQueue();
            };
            
            modalElement.addEventListener('transitionend', handleTransitionEnd);
            
            setTimeout(() => {
                if (this.isTransitioning) {
                    handleTransitionEnd();
                }
            }, 350);
        });
    }
    
    async close() {
        if (!this.activeModal || this.isTransitioning) {
            return Promise.resolve(false);
        }
        
        return new Promise((resolve) => {
            this.isTransitioning = true;
            const modal = this.activeModal;
            
            modal.classList.remove('visible', 'show');
            modal.setAttribute('aria-hidden', 'true');
            
            const handleTransitionEnd = () => {
                this.unlockScroll();
                this.activeModal = null;
                this.isTransitioning = false;
                modal.removeEventListener('transitionend', handleTransitionEnd);
                
                if (this.previousActiveElement && this.previousActiveElement.focus) {
                    this.previousActiveElement.focus();
                }
                
                resolve(true);
                
                this.processQueue();
            };
            
            modal.addEventListener('transitionend', handleTransitionEnd);
            
            setTimeout(() => {
                if (this.isTransitioning && this.activeModal === modal) {
                    handleTransitionEnd();
                }
            }, 350);
        });
    }
    
    processQueue() {
        if (this.modalQueue.length > 0 && !this.isTransitioning) {
            const next = this.modalQueue.shift();
            this.open(next.modalElement, next.options)
                .then(next.resolve)
                .catch(next.reject);
        }
    }
    
    lockScroll() {
        const scrollY = window.scrollY;
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollY}px`;
        document.body.style.width = '100%';
        document.body.dataset.scrollY = scrollY;
    }
    
    unlockScroll() {
        const scrollY = document.body.dataset.scrollY || '0';
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.width = '';
        window.scrollTo(0, parseInt(scrollY));
        delete document.body.dataset.scrollY;
    }
    
    trapFocus(modal) {
        const focusableSelectors = [
            'button:not([disabled])',
            'input:not([disabled])',
            'select:not([disabled])',
            'textarea:not([disabled])',
            'a[href]',
            '[tabindex]:not([tabindex="-1"])'
        ].join(', ');
        
        const focusableElements = modal.querySelectorAll(focusableSelectors);
        if (focusableElements.length > 0) {
            focusableElements[0].focus();
        }
    }
    
    isOpen() {
        return this.activeModal !== null;
    }
    
    getActiveModal() {
        return this.activeModal;
    }
}

if (typeof window !== 'undefined') {
    window.ModalManager = ModalManager;
    window.modalManager = ModalManager.getInstance();
}
