/**
 * CROWN ¹⁰ Reconciliation Cycle - Law #5: ETag Reconciliation Every 30s
 * 
 * Periodically checks for data drift using ETag headers and reconciles
 * local cache with server state when mismatches are detected.
 */

// Guard against multiple declarations (script may be loaded from base.html and page templates)
if (typeof window.ReconciliationCycle !== 'undefined') {
    console.log('📡 ReconciliationCycle already loaded, skipping redeclaration');
} else {

class ReconciliationCycle {
    constructor(workspaceId) {
        this.workspaceId = workspaceId;
        this.interval = 30000; // 30 seconds
        this.timerId = null;
        this.lastETags = {
            meetings: null,
            tasks: null,
            analytics: null
        };
        this.isRunning = false;
        this.reconciliationCount = 0;
        this.driftDetections = 0;
        this.REQUEST_TIMEOUT = 5000; // 5 second timeout for network requests
    }
    
    /**
     * Create a fetch request with timeout using AbortController
     * CROWN⁴.7: Prevents slow networks from blocking reconciliation indefinitely
     */
    fetchWithTimeout(url, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.REQUEST_TIMEOUT);
        
        return fetch(url, { ...options, signal: controller.signal })
            .finally(() => clearTimeout(timeoutId));
    }
    
    /**
     * Start reconciliation cycle
     */
    start() {
        if (this.isRunning) {
            console.warn('[Reconciliation] Already running');
            return;
        }
        
        console.log('[Reconciliation] Starting 30-second ETag cycle');
        this.isRunning = true;
        
        // Run immediately on start
        this.runCycle();
        
        // Then every 30 seconds
        this.timerId = setInterval(() => {
            this.runCycle();
        }, this.interval);
    }
    
    /**
     * Stop reconciliation cycle
     */
    stop() {
        if (!this.isRunning) {
            return;
        }
        
        console.log('[Reconciliation] Stopping ETag cycle');
        
        if (this.timerId) {
            clearInterval(this.timerId);
            this.timerId = null;
        }
        
        this.isRunning = false;
    }
    
    /**
     * Run one reconciliation cycle
     * CROWN⁴.13: Respects action lock to prevent overwriting user changes
     */
    async runCycle() {
        // CROWN⁴.13: Skip if action lock is active
        if (window.taskActionLock && window.taskActionLock.shouldBlockSync()) {
            console.log('[Reconciliation] Skipping cycle - action lock active');
            return;
        }
        
        this.reconciliationCount++;
        
        console.log(`[Reconciliation] Cycle #${this.reconciliationCount} starting...`);
        
        try {
            // Check all surfaces in parallel
            const results = await Promise.allSettled([
                this.checkMeetings(),
                this.checkTasks(),
                this.checkAnalytics()
            ]);
            
            const drifts = results.filter(r => r.status === 'fulfilled' && r.value === true).length;
            if (drifts > 0) {
                this.driftDetections += drifts;
                console.log(`🔄 Detected ${drifts} data drift(s), reconciled successfully`);
            } else {
                console.log('✅ All surfaces in sync (ETags match)');
            }
        } catch (error) {
            console.error('[Reconciliation] Cycle error:', error);
        }
    }
    
    /**
     * Check meetings endpoint for changes (CROWN ¹⁰ Law #5: HEAD + If-None-Match)
     * CROWN⁴.7: Uses timeout to prevent slow network blocking
     */
    async checkMeetings() {
        try {
            // STEP 1: HEAD request with If-None-Match to check ETag
            const headResponse = await this.fetchWithTimeout('/api/meetings/recent?limit=5', {
                method: 'HEAD',
                headers: {
                    'If-None-Match': this.lastETags.meetings || ''
                }
            });
            
            if (headResponse.status === 304) {
                // No changes - ETag matches
                return false;
            }
            
            // STEP 2: ETag changed or first check - get new ETag
            const newETag = headResponse.headers.get('ETag');
            const oldETag = this.lastETags.meetings;
            
            if (!newETag) {
                // No ETag support - fallback to regular GET
                console.warn('[Reconciliation] No ETag header on meetings endpoint');
                return false;
            }
            
            this.lastETags.meetings = newETag;
            
            if (oldETag && oldETag !== newETag) {
                console.log(`🔄 Meetings drift detected (ETag: ${oldETag?.substring(0, 12)}... → ${newETag?.substring(0, 12)}...)`);
                
                // STEP 3: ETag mismatch - fetch full data with GET
                const getResponse = await this.fetchWithTimeout('/api/meetings/recent?limit=5', {
                    method: 'GET'
                });
                
                if (!getResponse.ok) {
                    console.error('[Reconciliation] Failed to fetch meetings:', getResponse.status);
                    return false;
                }
                
                const data = await getResponse.json();
                await this.reconcileMeetings(data);
                
                return true; // Drift detected and reconciled
            }
            
            // First check - just store ETag
            return false;
        } catch (error) {
            if (error.name === 'AbortError') {
                console.warn('[Reconciliation] Meetings check timed out');
            } else {
                console.error('[Reconciliation] Meetings check failed:', error);
            }
            return false;
        }
    }
    
    /**
     * Check tasks endpoint for changes (CROWN ¹⁰ Law #5: HEAD + If-None-Match)
     * CROWN⁴.7: Uses timeout to prevent slow network blocking
     */
    async checkTasks() {
        try {
            // STEP 1: HEAD request with If-None-Match
            const headResponse = await this.fetchWithTimeout('/api/tasks/stats', {
                method: 'HEAD',
                headers: {
                    'If-None-Match': this.lastETags.tasks || ''
                }
            });
            
            if (headResponse.status === 304) {
                // No changes
                return false;
            }
            
            const newETag = headResponse.headers.get('ETag');
            const oldETag = this.lastETags.tasks;
            
            if (!newETag) {
                console.warn('[Reconciliation] No ETag header on tasks endpoint');
                return false;
            }
            
            this.lastETags.tasks = newETag;
            
            if (oldETag && oldETag !== newETag) {
                console.log(`🔄 Tasks drift detected (ETag: ${oldETag?.substring(0, 12)}... → ${newETag?.substring(0, 12)}...)`);
                
                // STEP 2: Fetch full data with GET
                const getResponse = await this.fetchWithTimeout('/api/tasks/stats', {
                    method: 'GET'
                });
                
                if (!getResponse.ok) {
                    console.error('[Reconciliation] Failed to fetch tasks:', getResponse.status);
                    return false;
                }
                
                const data = await getResponse.json();
                await this.reconcileTasks(data);
                
                return true;
            }
            
            return false;
        } catch (error) {
            if (error.name === 'AbortError') {
                console.warn('[Reconciliation] Tasks check timed out');
            } else {
                console.error('[Reconciliation] Tasks check failed:', error);
            }
            return false;
        }
    }
    
    /**
     * Check analytics endpoint for changes (CROWN ¹⁰ Law #5: HEAD + If-None-Match)
     * CROWN⁴.7: Uses timeout to prevent slow network blocking
     */
    async checkAnalytics() {
        try {
            // STEP 1: HEAD request with If-None-Match
            const headResponse = await this.fetchWithTimeout('/api/analytics/dashboard?days=7', {
                method: 'HEAD',
                headers: {
                    'If-None-Match': this.lastETags.analytics || ''
                }
            });
            
            if (headResponse.status === 304) {
                // No changes
                return false;
            }
            
            const newETag = headResponse.headers.get('ETag');
            const oldETag = this.lastETags.analytics;
            
            if (!newETag) {
                console.warn('[Reconciliation] No ETag header on analytics endpoint');
                return false;
            }
            
            this.lastETags.analytics = newETag;
            
            if (oldETag && oldETag !== newETag) {
                console.log(`🔄 Analytics drift detected (ETag: ${oldETag?.substring(0, 12)}... → ${newETag?.substring(0, 12)}...)`);
                
                // STEP 2: Fetch full data with GET
                const getResponse = await this.fetchWithTimeout('/api/analytics/dashboard?days=7', {
                    method: 'GET'
                });
                
                if (!getResponse.ok) {
                    console.error('[Reconciliation] Failed to fetch analytics:', getResponse.status);
                    return false;
                }
                
                const data = await getResponse.json();
                await this.reconcileAnalytics(data);
                
                return true;
            }
            
            return false;
        } catch (error) {
            if (error.name === 'AbortError') {
                console.warn('[Reconciliation] Analytics check timed out');
            } else {
                console.error('[Reconciliation] Analytics check failed:', error);
            }
            return false;
        }
    }
    
    /**
     * Reconcile meetings data (merge server state with local cache)
     */
    async reconcileMeetings(data) {
        if (!data || !data.success) {
            console.warn('[Reconciliation] Invalid meetings data');
            return;
        }
        
        // Invalidate cache
        if (window.dashboard && window.dashboard.cache) {
            await window.dashboard.cache.invalidate('meetings');
        }
        
        // Update UI if dashboard manager exists
        if (window.dashboard && typeof window.dashboard.loadRecentMeetings === 'function') {
            await window.dashboard.loadRecentMeetings();
        }
        
        // Broadcast to other tabs
        if (window.broadcastSync) {
            window.broadcastSync.broadcast('MEETING_UPDATE', {
                source: 'reconciliation',
                checksum: data.checksum
            });
        }
    }
    
    /**
     * Reconcile tasks data
     */
    async reconcileTasks(data) {
        if (!data || !data.success) {
            console.warn('[Reconciliation] Invalid tasks data');
            return;
        }
        
        // Invalidate cache
        if (window.dashboard && window.dashboard.cache) {
            await window.dashboard.cache.invalidate('tasks');
        }
        
        // Update UI
        if (window.dashboard && typeof window.dashboard.loadMyTasks === 'function') {
            await window.dashboard.loadMyTasks();
        }
        
        if (window.dashboard && typeof window.dashboard.loadStats === 'function') {
            await window.dashboard.loadStats();
        }
        
        // Broadcast to other tabs
        if (window.broadcastSync) {
            window.broadcastSync.broadcast('TASK_UPDATE', {
                source: 'reconciliation',
                stats: data.stats
            });
        }
    }
    
    /**
     * Reconcile analytics data
     */
    async reconcileAnalytics(data) {
        if (!data || !data.success) {
            console.warn('[Reconciliation] Invalid analytics data');
            return;
        }
        
        // Invalidate cache
        if (window.dashboard && window.dashboard.cache) {
            await window.dashboard.cache.invalidate('analytics');
        }
        
        // Update UI
        if (window.dashboard && typeof window.dashboard.loadAnalyticsOverview === 'function') {
            await window.dashboard.loadAnalyticsOverview();
        }
        
        // Broadcast to other tabs
        if (window.broadcastSync) {
            window.broadcastSync.broadcast('ANALYTICS_REFRESH', {
                source: 'reconciliation',
                dashboard: data.dashboard
            });
        }
    }
    
    /**
     * Get reconciliation statistics
     */
    getStats() {
        return {
            isRunning: this.isRunning,
            reconciliationCount: this.reconciliationCount,
            driftDetections: this.driftDetections,
            driftRate: this.reconciliationCount > 0 
                ? (this.driftDetections / this.reconciliationCount * 100).toFixed(1) + '%'
                : '0%',
            lastETags: {
                meetings: this.lastETags.meetings?.substring(0, 12) + '...',
                tasks: this.lastETags.tasks?.substring(0, 12) + '...',
                analytics: this.lastETags.analytics?.substring(0, 12) + '...'
            }
        };
    }
}

// Export for use in dashboard
window.ReconciliationCycle = ReconciliationCycle;

} // End of redeclaration guard
