/**
 * Analytics Prefetch Controller - CROWN⁵+ Intelligent Tab Prefetching
 * 
 * Prefetches secondary tab data (Engagement, Productivity, Insights) in background:
 * - Triggered on idle time (2s after page load)
 * - Triggered on scroll proximity to tabs
 * - Cancellable via AbortController
 * - Respects network conditions (prefers-reduced-data)
 * 
 * Prefetch priority:
 * 1. Engagement (highest probability of next tab)
 * 2. Productivity
 * 3. Insights
 */

export class AnalyticsPrefetchController {
    constructor(lifecycle, workspaceId, currentTab = 'overview') {
        this.lifecycle = lifecycle;
        this.workspaceId = workspaceId;
        this.currentTab = currentTab;
        
        // Prefetch state
        this.prefetchedTabs = new Set();
        this.abortController = null;
        this.idleTimeoutId = null;
        this.scrollListenerId = null;
        
        // Prefetch configuration
        this.prefetchPriority = ['engagement', 'productivity', 'insights'];
        this.idleDelay = 2000; // 2 seconds after page load
        this.scrollThreshold = 300; // pixels from tab bar
        
        // Network awareness
        this.respectsNetworkConditions = this._checkNetworkConditions();
        
        this._init();
    }

    /**
     * Initialize prefetch controller
     * @private
     */
    _init() {
        console.log('🔮 Prefetch controller initialized');

        // Check if we should prefetch at all
        if (!this.respectsNetworkConditions) {
            console.log('⚠️ Prefetch disabled - network conditions');
            return;
        }

        // Start idle-based prefetching
        this._startIdlePrefetch();

        // Setup scroll-based prefetching
        this._setupScrollPrefetch();
    }

    /**
     * Check network conditions (respects prefers-reduced-data)
     * @private
     */
    _checkNetworkConditions() {
        // Check if user has reduced data preference
        if (window.matchMedia && window.matchMedia('(prefers-reduced-data: reduce)').matches) {
            return false;
        }

        // Check connection quality (if available)
        if (navigator.connection) {
            const conn = navigator.connection;
            
            // Don't prefetch on slow connections
            if (conn.saveData || conn.effectiveType === 'slow-2g' || conn.effectiveType === '2g') {
                return false;
            }
        }

        return true;
    }

    /**
     * Start idle-based prefetching
     * @private
     */
    _startIdlePrefetch() {
        // Wait for idle time after page load
        this.idleTimeoutId = setTimeout(() => {
            this._prefetchNextTabs();
        }, this.idleDelay);

        console.log(`🕒 Idle prefetch scheduled (${this.idleDelay}ms)`);
    }

    /**
     * Setup scroll-based prefetching
     * @private
     */
    _setupScrollPrefetch() {
        let scrollTimeout;
        
        this.scrollListenerId = () => {
            // Debounce scroll events
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                this._checkScrollProximity();
            }, 150);
        };

        window.addEventListener('scroll', this.scrollListenerId, { passive: true });
    }

    /**
     * Check if scroll position is near tab bar
     * @private
     */
    _checkScrollProximity() {
        const tabBar = document.querySelector('.analytics-tab');
        if (!tabBar) return;

        const rect = tabBar.getBoundingClientRect();
        const distanceFromViewport = Math.abs(rect.top - window.innerHeight);

        // If tab bar is within threshold, start prefetching
        if (distanceFromViewport < this.scrollThreshold && !this.prefetchedTabs.size) {
            console.log('📜 Scroll proximity triggered prefetch');
            this._prefetchNextTabs();
        }
    }

    /**
     * Prefetch secondary tabs in priority order
     * @private
     */
    async _prefetchNextTabs() {
        // Cancel any existing prefetch operation
        if (this.abortController) {
            this.abortController.abort();
        }

        // Create new abort controller
        this.abortController = new AbortController();

        try {
            for (const tab of this.prefetchPriority) {
                // Skip if already prefetched or current tab
                if (this.prefetchedTabs.has(tab) || this.currentTab === tab) {
                    continue;
                }

                // Check if aborted
                if (this.abortController.signal.aborted) {
                    console.log('⚠️ Prefetch aborted');
                    break;
                }

                // Prefetch tab
                console.log(`🔮 Prefetching tab: ${tab}`);
                await this._prefetchTab(tab);
                
                // Mark as prefetched
                this.prefetchedTabs.add(tab);

                // Small delay between prefetches to avoid overwhelming
                await this._delay(500);
            }

            console.log('✅ Prefetch completed');
        } catch (e) {
            if (e.name === 'AbortError') {
                console.log('Prefetch cancelled');
            } else {
                console.error('Prefetch error:', e);
            }
        }
    }

    /**
     * Prefetch specific tab data
     * @private
     */
    async _prefetchTab(tabName) {
        return new Promise((resolve, reject) => {
            if (this.abortController.signal.aborted) {
                reject(new DOMException('Prefetch aborted', 'AbortError'));
                return;
            }

            // Request tab data from server (use 'prefetch' as from_tab to avoid UI disruption)
            this.lifecycle.socket.emit('analytics_tab_switch_request', {
                workspace_id: this.workspaceId,
                from_tab: 'prefetch',
                to_tab: tabName,
                user_id: window.currentUserId,
                days: this.lifecycle.days
            });

            // Listen for tab data response
            const timeout = setTimeout(() => {
                console.warn(`Prefetch timeout for ${tabName}`);
                resolve(); // Resolve even if timeout (non-critical)
            }, 3000);

            const handler = (data) => {
                if (data.tab === tabName) {
                    clearTimeout(timeout);
                    this.lifecycle.socket.off('analytics_tab_data', handler);
                    
                    // Cache the fetched tab data in the lifecycle snapshot
                    if (this.lifecycle.currentSnapshot) {
                        this.lifecycle.currentSnapshot.tabs = this.lifecycle.currentSnapshot.tabs || {};
                        this.lifecycle.currentSnapshot.tabs[tabName] = data.data;
                        console.log(`✅ Prefetched and cached: ${tabName}`);
                    }
                    
                    resolve(data);
                }
            };

            this.lifecycle.socket.on('analytics_tab_data', handler);

            // Handle abort
            this.abortController.signal.addEventListener('abort', () => {
                clearTimeout(timeout);
                this.lifecycle.socket.off('analytics_tab_data', handler);
                reject(new DOMException('Prefetch aborted', 'AbortError'));
            });
        });
    }

    /**
     * Utility delay function
     * @private
     */
    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Update current tab (called when user actually switches)
     */
    onTabSwitch(newTab) {
        this.currentTab = newTab;
        
        // If tab was prefetched, mark it as used
        if (this.prefetchedTabs.has(newTab)) {
            console.log(`✨ Prefetch hit: ${newTab}`);
        }
    }

    /**
     * Cancel all prefetch operations
     */
    cancel() {
        if (this.abortController) {
            this.abortController.abort();
        }
        if (this.idleTimeoutId) {
            clearTimeout(this.idleTimeoutId);
        }
        if (this.scrollListenerId) {
            window.removeEventListener('scroll', this.scrollListenerId);
        }
        console.log('🧹 Prefetch controller cancelled');
    }

    /**
     * Get prefetch statistics
     */
    getStats() {
        return {
            prefetchedTabs: Array.from(this.prefetchedTabs),
            currentTab: this.currentTab,
            networkConditions: this.respectsNetworkConditions,
            hitRate: this.prefetchedTabs.has(this.currentTab) ? 100 : 0
        };
    }
}
