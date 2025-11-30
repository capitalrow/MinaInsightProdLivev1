/**
 * CROWN⁴.6 Unified Skeleton Manager
 * Provides consistent skeleton loading behavior across all pages
 * 
 * Features:
 * - Skeleton-first rendering (visible by default in HTML)
 * - Cache-aware transitions (instant for cache hits, animated for network)
 * - Smooth fade transitions with reduced motion support
 * - State guards to prevent skeleton flash after content renders
 * - Performance telemetry integration
 */

class SkeletonManager {
    constructor(options = {}) {
        this.options = {
            transitionDuration: 200,
            cacheTransitionDuration: 50,
            fadeClass: 'skeleton-fade-out',
            contentFadeClass: 'content-fade-in',
            minSkeletonTime: 100,
            ...options
        };
        
        this.states = new Map();
        this.initialized = false;
        this.startTimes = new Map();
        this.performanceMetrics = [];
    }
    
    init() {
        if (this.initialized) return;
        this.initialized = true;
        
        this._injectStyles();
        this._setupReducedMotion();
        this._autoRegister();
        
        console.log('[SkeletonManager] Initialized with cache-aware transitions');
    }
    
    _autoRegister() {
        document.querySelectorAll('[data-skeleton-for]').forEach(skeleton => {
            const contentId = skeleton.dataset.skeletonFor;
            const content = document.getElementById(contentId);
            if (content) {
                this.register(contentId, skeleton, content);
                this.startTimes.set(contentId, performance.now());
            }
        });
    }
    
    _injectStyles() {
        if (document.getElementById('skeleton-manager-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'skeleton-manager-styles';
        style.textContent = `
            .skeleton-fade-out {
                opacity: 0;
                transition: opacity ${this.options.transitionDuration}ms ease-out;
                pointer-events: none;
            }
            
            .content-fade-in {
                animation: skeletonContentFadeIn ${this.options.transitionDuration}ms ease-out forwards;
            }
            
            @keyframes skeletonContentFadeIn {
                from {
                    opacity: 0;
                    transform: translateY(8px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .skeleton-container {
                position: relative;
            }
            
            .skeleton-overlay {
                position: absolute;
                inset: 0;
                z-index: 10;
            }
            
            @media (prefers-reduced-motion: reduce) {
                .skeleton-fade-out,
                .content-fade-in {
                    transition: none !important;
                    animation: none !important;
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    _setupReducedMotion() {
        this.prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    
    register(id, skeletonEl, contentEl) {
        if (!skeletonEl || !contentEl) {
            console.warn(`[SkeletonManager] Invalid elements for ${id}`);
            return;
        }
        
        this.states.set(id, {
            skeleton: skeletonEl,
            content: contentEl,
            state: 'loading',
            transitioned: false
        });
        
        skeletonEl.style.display = '';
        contentEl.style.display = 'none';
        
        return this;
    }
    
    showContent(id, options = {}) {
        const entry = this.states.get(id);
        if (!entry) {
            console.warn(`[SkeletonManager] Unknown section: ${id}`);
            return Promise.resolve();
        }
        
        if (entry.state === 'content' && entry.transitioned) {
            return Promise.resolve();
        }
        
        entry.state = 'transitioning';
        
        const isCacheHit = options.source === 'cache';
        const duration = isCacheHit ? this.options.cacheTransitionDuration : this.options.transitionDuration;
        
        const startTime = this.startTimes.get(id) || performance.now();
        const elapsed = performance.now() - startTime;
        
        const minWait = Math.max(0, this.options.minSkeletonTime - elapsed);
        
        return new Promise((resolve) => {
            setTimeout(() => {
                const { skeleton, content } = entry;
                
                content.style.display = '';
                
                if (this.prefersReducedMotion || options.instant || isCacheHit) {
                    skeleton.style.display = 'none';
                    entry.state = 'content';
                    entry.transitioned = true;
                    
                    this._recordMetric(id, elapsed + minWait, options.source || 'unknown');
                    resolve();
                    return;
                }
                
                skeleton.classList.add(this.options.fadeClass);
                content.classList.add(this.options.contentFadeClass);
                
                setTimeout(() => {
                    skeleton.style.display = 'none';
                    skeleton.classList.remove(this.options.fadeClass);
                    
                    setTimeout(() => {
                        content.classList.remove(this.options.contentFadeClass);
                    }, duration);
                    
                    entry.state = 'content';
                    entry.transitioned = true;
                    
                    this._recordMetric(id, elapsed + minWait + duration, options.source || 'network');
                    resolve();
                }, duration);
            }, minWait);
        });
    }
    
    _recordMetric(id, duration, source) {
        this.performanceMetrics.push({
            section: id,
            duration: Math.round(duration),
            source,
            timestamp: Date.now()
        });
        
        console.log(`[SkeletonManager] ${id}: ${Math.round(duration)}ms (${source})`);
    }
    
    getMetrics() {
        return this.performanceMetrics;
    }
    
    showSkeleton(id) {
        const entry = this.states.get(id);
        if (!entry) return;
        
        if (entry.transitioned) {
            console.log(`[SkeletonManager] Ignoring showSkeleton for ${id} - already transitioned`);
            return;
        }
        
        entry.skeleton.style.display = '';
        entry.content.style.display = 'none';
        entry.state = 'loading';
    }
    
    getState(id) {
        const entry = this.states.get(id);
        return entry ? entry.state : null;
    }
    
    isTransitioned(id) {
        const entry = this.states.get(id);
        return entry ? entry.transitioned : false;
    }
    
    reset(id) {
        const entry = this.states.get(id);
        if (!entry) return;
        
        entry.transitioned = false;
        entry.state = 'loading';
        entry.skeleton.style.display = '';
        entry.content.style.display = 'none';
        entry.skeleton.classList.remove(this.options.fadeClass);
        entry.content.classList.remove(this.options.contentFadeClass);
    }
    
    transitionAll(options = {}) {
        const promises = [];
        for (const id of this.states.keys()) {
            promises.push(this.showContent(id, options));
        }
        return Promise.all(promises);
    }
}

window.skeletonManager = new SkeletonManager();

document.addEventListener('DOMContentLoaded', () => {
    window.skeletonManager.init();
});

if (typeof module !== 'undefined' && module.exports) {
    module.exports = SkeletonManager;
}
