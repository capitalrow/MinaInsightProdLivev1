/**
 * PrefetchController - Intelligent prefetch management with AbortController
 * 
 * Features:
 * - Abort stale prefetch requests when user navigates quickly
 * - Deduplicate concurrent requests for same resource
 * - Queue management with priority
 * - Memory-efficient caching
 * - Automatic cleanup of old prefetches
 * 
 * CROWN⁴ prefetch optimization for sub-300ms navigation
 */

// Prevent redeclaration using window check
(function() {
    if (window.PrefetchController) {
        console.log('🎯 PrefetchController already loaded, skipping redeclaration');
        return;
    }
    
window.PrefetchController = class PrefetchController {
    constructor(options = {}) {
        // Configuration
        this.maxConcurrent = options.maxConcurrent || 3;
        this.maxCacheSize = options.maxCacheSize || 50;
        this.cacheTimeout = options.cacheTimeout || 60000; // 1 minute default
        
        // CROWN⁴.5: Pluggable resource adapters
        this.adapter = options.adapter || this._getDefaultAdapter();
        
        // State tracking
        this.activeRequests = new Map(); // resourceId -> { abortController, promise, timestamp }
        this.prefetchCache = new Map(); // resourceId -> { data, timestamp }
        this.requestQueue = []; // { resourceId, priority, timestamp }
        this.completedSet = new Set(); // resourceIds that were successfully prefetched
        
        // Statistics
        this.stats = {
            totalPrefetches: 0,
            aborted: 0,
            cacheHits: 0,
            cacheMisses: 0,
            errors: 0
        };
        
        // Start cleanup timer
        this.startCleanupTimer();
        
        console.log('🎯 PrefetchController initialized:', {
            maxConcurrent: this.maxConcurrent,
            maxCacheSize: this.maxCacheSize,
            cacheTimeout: this.cacheTimeout,
            adapter: this.adapter.name || 'custom'
        });
    }
    
    /**
     * CROWN⁴.5: Default adapter for sessions (backwards compatibility)
     */
    _getDefaultAdapter() {
        return {
            name: 'sessions',
            keyFn: (sessionId) => `session_${sessionId}`,
            requestFn: (sessionId) => `/sessions/${sessionId}?format=json`,
            hydrateFn: async (sessionId, data) => data // No-op for sessions
        };
    }
    
    /**
     * Prefetch resource data with intelligent caching and abort control
     * CROWN⁴.5: Now adapter-agnostic (supports sessions, tasks, etc.)
     */
    async prefetch(resourceId, options = {}) {
        const priority = options.priority || 0;
        const force = options.force || false;
        
        // Validation
        if (!resourceId) {
            console.warn('⚠️ PrefetchController: No resourceId provided');
            return null;
        }
        
        // Get cache key from adapter
        const cacheKey = this.adapter.keyFn(resourceId);
        
        // Check cache first (unless force refresh)
        if (!force && this.prefetchCache.has(cacheKey)) {
            const cached = this.prefetchCache.get(cacheKey);
            const age = Date.now() - cached.timestamp;
            
            if (age < this.cacheTimeout) {
                this.stats.cacheHits++;
                console.log(`💨 Prefetch cache hit: ${cacheKey} (age: ${Math.round(age/1000)}s)`);
                return cached.data;
            } else {
                // Cache expired
                this.prefetchCache.delete(cacheKey);
                console.log(`⏰ Prefetch cache expired: ${cacheKey}`);
            }
        }
        
        this.stats.cacheMisses++;
        
        // Check if already in progress
        if (this.activeRequests.has(cacheKey)) {
            console.log(`🔄 Prefetch already in progress: ${cacheKey}, reusing...`);
            const existing = this.activeRequests.get(cacheKey);
            return existing.promise;
        }
        
        // Check concurrent limit
        if (this.activeRequests.size >= this.maxConcurrent) {
            // Queue the request and return a Promise that resolves when it's processed
            return new Promise((resolve, reject) => {
                this.requestQueue.push({ 
                    resourceId, 
                    cacheKey,
                    priority, 
                    timestamp: Date.now(),
                    resolve,
                    reject
                });
                console.log(`⏸️ Prefetch queued (${this.activeRequests.size}/${this.maxConcurrent} active): ${cacheKey}`);
            });
        }
        
        // Execute prefetch
        return this._executePrefetch(resourceId, cacheKey);
    }
    
    /**
     * Execute prefetch with abort controller
     * CROWN⁴.5: Now uses adapter for request URL and hydration
     */
    async _executePrefetch(resourceId, cacheKey) {
        const abortController = new AbortController();
        const startTime = Date.now();
        
        // Get request URL from adapter
        const requestUrl = this.adapter.requestFn(resourceId);
        
        // Create promise for this prefetch
        const promise = fetch(requestUrl, {
            signal: abortController.signal,
            headers: { 'X-Prefetch': 'true' }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(async data => {
            const duration = Date.now() - startTime;
            
            // CROWN⁴.5: Hydrate data via adapter (e.g., write to IndexedDB)
            if (this.adapter.hydrateFn) {
                try {
                    await this.adapter.hydrateFn(resourceId, data);
                } catch (hydrateError) {
                    console.warn(`⚠️ Hydration failed for ${cacheKey}:`, hydrateError);
                }
            }
            
            // Cache the result
            this.prefetchCache.set(cacheKey, {
                data,
                timestamp: Date.now()
            });
            
            // Enforce cache size limit
            if (this.prefetchCache.size > this.maxCacheSize) {
                this._evictOldestCache();
            }
            
            // Mark as completed
            this.completedSet.add(cacheKey);
            
            // Clean up active request
            this.activeRequests.delete(cacheKey);
            
            // Process queue
            this._processQueue();
            
            this.stats.totalPrefetches++;
            console.log(`✅ Prefetch complete: ${cacheKey} (${duration}ms)`);
            
            return data;
        })
        .catch(error => {
            // Clean up active request
            this.activeRequests.delete(cacheKey);
            
            // Process queue even on error
            this._processQueue();
            
            if (error.name === 'AbortError') {
                this.stats.aborted++;
                console.log(`🚫 Prefetch aborted: ${cacheKey}`);
            } else {
                this.stats.errors++;
                console.error(`❌ Prefetch failed: ${cacheKey}`, error);
            }
            
            throw error;
        });
        
        // Track active request
        this.activeRequests.set(cacheKey, {
            abortController,
            promise,
            timestamp: Date.now()
        });
        
        console.log(`🚀 Prefetch started: ${cacheKey} (${this.activeRequests.size}/${this.maxConcurrent} active)`);
        
        return promise;
    }
    
    /**
     * Abort a specific prefetch request
     * CROWN⁴.5: Now uses adapter key
     */
    abort(resourceId) {
        const cacheKey = this.adapter.keyFn(resourceId);
        if (this.activeRequests.has(cacheKey)) {
            const request = this.activeRequests.get(cacheKey);
            request.abortController.abort();
            this.activeRequests.delete(cacheKey);
            console.log(`🛑 Aborted prefetch: ${cacheKey}`);
            
            // Process queue after abort
            this._processQueue();
            
            return true;
        }
        return false;
    }
    
    /**
     * Abort all active prefetch requests
     */
    abortAll() {
        let count = 0;
        for (const [cacheKey, request] of this.activeRequests.entries()) {
            request.abortController.abort();
            count++;
        }
        this.activeRequests.clear();
        
        if (count > 0) {
            console.log(`🛑 Aborted ${count} active prefetches`);
        }
        
        return count;
    }
    
    /**
     * Process queued prefetch requests
     */
    _processQueue() {
        // Process queue only if we have capacity
        while (this.requestQueue.length > 0 && this.activeRequests.size < this.maxConcurrent) {
            // Sort by priority (higher first) and timestamp (older first)
            this.requestQueue.sort((a, b) => {
                if (a.priority !== b.priority) {
                    return b.priority - a.priority; // Higher priority first
                }
                return a.timestamp - b.timestamp; // Older first
            });
            
            // Take next request from queue
            const next = this.requestQueue.shift();
            console.log(`▶️ Processing queued prefetch: ${next.cacheKey}`);
            
            // Execute it and resolve/reject the queued promise
            this._executePrefetch(next.resourceId, next.cacheKey)
                .then(data => {
                    if (next.resolve) {
                        next.resolve(data);
                    }
                })
                .catch(err => {
                    console.warn('Queued prefetch failed:', err);
                    if (next.reject) {
                        next.reject(err);
                    }
                });
        }
    }
    
    /**
     * Evict oldest cache entry to maintain size limit
     */
    _evictOldestCache() {
        let oldestId = null;
        let oldestTime = Infinity;
        
        for (const [sessionId, cached] of this.prefetchCache.entries()) {
            if (cached.timestamp < oldestTime) {
                oldestTime = cached.timestamp;
                oldestId = sessionId;
            }
        }
        
        if (oldestId) {
            this.prefetchCache.delete(oldestId);
            console.log(`🧹 Evicted oldest cache entry: ${oldestId}`);
        }
    }
    
    /**
     * Get cached data (if available and fresh)
     * CROWN⁴.5: Now uses adapter key
     */
    getCached(resourceId) {
        const cacheKey = this.adapter.keyFn(resourceId);
        if (this.prefetchCache.has(cacheKey)) {
            const cached = this.prefetchCache.get(cacheKey);
            const age = Date.now() - cached.timestamp;
            
            if (age < this.cacheTimeout) {
                return cached.data;
            } else {
                this.prefetchCache.delete(cacheKey);
            }
        }
        return null;
    }
    
    /**
     * Check if resource was successfully prefetched
     * CROWN⁴.5: Now uses adapter key
     */
    isPrefetched(resourceId) {
        const cacheKey = this.adapter.keyFn(resourceId);
        return this.completedSet.has(cacheKey) || this.prefetchCache.has(cacheKey);
    }
    
    /**
     * Clear all prefetch cache
     */
    clearCache() {
        const size = this.prefetchCache.size;
        this.prefetchCache.clear();
        this.completedSet.clear();
        console.log(`🧹 Cleared ${size} prefetch cache entries`);
    }
    
    /**
     * Start periodic cleanup timer
     */
    startCleanupTimer() {
        setInterval(() => {
            this._cleanupExpiredCache();
            this._cleanupStaleRequests();
        }, 30000); // Every 30 seconds
    }
    
    /**
     * Clean up expired cache entries
     */
    _cleanupExpiredCache() {
        let cleaned = 0;
        const now = Date.now();
        
        for (const [sessionId, cached] of this.prefetchCache.entries()) {
            const age = now - cached.timestamp;
            if (age > this.cacheTimeout) {
                this.prefetchCache.delete(sessionId);
                cleaned++;
            }
        }
        
        if (cleaned > 0) {
            console.log(`🧹 Cleaned up ${cleaned} expired cache entries`);
        }
    }
    
    /**
     * Clean up stale active requests (hanging > 30s)
     */
    _cleanupStaleRequests() {
        let cleaned = 0;
        const now = Date.now();
        const staleThreshold = 30000; // 30 seconds
        
        for (const [sessionId, request] of this.activeRequests.entries()) {
            const age = now - request.timestamp;
            if (age > staleThreshold) {
                request.abortController.abort();
                this.activeRequests.delete(sessionId);
                cleaned++;
            }
        }
        
        if (cleaned > 0) {
            console.log(`🧹 Cleaned up ${cleaned} stale requests`);
        }
    }
    
    /**
     * Get statistics
     */
    getStats() {
        return {
            ...this.stats,
            activeRequests: this.activeRequests.size,
            queuedRequests: this.requestQueue.length,
            cachedSessions: this.prefetchCache.size,
            completedSessions: this.completedSet.size
        };
    }
    
    /**
     * Log statistics
     */
    logStats() {
        const stats = this.getStats();
        console.log('📊 PrefetchController Stats:', stats);
        return stats;
    }
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.PrefetchController;
}
})(); // End IIFE
