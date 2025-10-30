/**
 * CROWN⁴.5 Idempotency Layer
 * Prevents duplicate operations from retry logic, network issues, or user actions.
 * Uses time-based eviction to prevent memory leaks.
 */

class IdempotencyManager {
    constructor() {
        this.processedOperations = new Map();  // opId -> { timestamp, type, result }
        this.evictionThreshold = 5 * 60 * 1000;  // 5 minutes (operations older than this are evicted)
        this.maxEntries = 1000;  // Max entries to prevent unbounded growth
        
        // Run cleanup every minute
        this.cleanupInterval = setInterval(() => this._cleanup(), 60 * 1000);
        
        console.log('✅ Idempotency Manager initialized');
    }
    
    /**
     * Check if operation has already been processed
     * @param {string} opId - Operation ID
     * @returns {boolean|Object} False if not processed, operation result if already processed
     */
    check(opId) {
        const existing = this.processedOperations.get(opId);
        
        if (!existing) {
            return false;
        }
        
        // Check if operation is still within validity window
        const age = Date.now() - existing.timestamp;
        if (age > this.evictionThreshold) {
            // Expired - treat as new
            this.processedOperations.delete(opId);
            return false;
        }
        
        console.log(`🔒 Operation ${opId} already processed ${age}ms ago (idempotent skip)`);
        return existing;
    }
    
    /**
     * Mark operation as processed
     * @param {string} opId - Operation ID
     * @param {string} type - Operation type (create, update, delete)
     * @param {Object} result - Operation result
     */
    markProcessed(opId, type, result = null) {
        this.processedOperations.set(opId, {
            timestamp: Date.now(),
            type,
            result
        });
        
        // Enforce max entries limit
        if (this.processedOperations.size > this.maxEntries) {
            this._evictOldest();
        }
    }
    
    /**
     * Clear a specific operation (useful for failed operations that should be retried)
     * @param {string} opId - Operation ID
     */
    clear(opId) {
        this.processedOperations.delete(opId);
        console.log(`🗑️ Cleared operation ${opId} from idempotency cache`);
    }
    
    /**
     * Get deduplicated operation ID for request data
     * Creates deterministic ID from operation content to catch exact duplicates
     * @param {string} type - Operation type
     * @param {Object} data - Operation data
     * @returns {string} Content-based operation ID
     */
    getContentBasedOpId(type, data) {
        const normalized = JSON.stringify({
            type,
            ...this._sortObject(data)
        });
        
        // Simple hash function (FNV-1a)
        let hash = 2166136261;
        for (let i = 0; i < normalized.length; i++) {
            hash ^= normalized.charCodeAt(i);
            hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
        }
        
        return `content_${(hash >>> 0).toString(36)}`;
    }
    
    /**
     * Check if content-based duplicate exists (catches rapid double-clicks)
     * @param {string} type - Operation type
     * @param {Object} data - Operation data
     * @param {number} withinMs - Time window to check (default: 2 seconds)
     * @returns {boolean|Object} False if not duplicate, existing operation if duplicate
     */
    checkContentDuplicate(type, data, withinMs = 2000) {
        const contentId = this.getContentBasedOpId(type, data);
        const existing = this.processedOperations.get(contentId);
        
        if (!existing) {
            return false;
        }
        
        const age = Date.now() - existing.timestamp;
        if (age <= withinMs) {
            console.warn(`⚠️ Content-based duplicate detected within ${age}ms (likely double-click)`);
            return existing;
        }
        
        return false;
    }
    
    /**
     * Mark content as processed (for content-based deduplication)
     * @param {string} type - Operation type
     * @param {Object} data - Operation data
     * @param {Object} result - Operation result
     */
    markContentProcessed(type, data, result = null) {
        const contentId = this.getContentBasedOpId(type, data);
        this.markProcessed(contentId, type, result);
    }
    
    /**
     * Cleanup expired operations
     * @private
     */
    _cleanup() {
        const now = Date.now();
        let evicted = 0;
        
        for (const [opId, entry] of this.processedOperations.entries()) {
            const age = now - entry.timestamp;
            if (age > this.evictionThreshold) {
                this.processedOperations.delete(opId);
                evicted++;
            }
        }
        
        if (evicted > 0) {
            console.log(`🧹 Idempotency cleanup: evicted ${evicted} expired operations (${this.processedOperations.size} remaining)`);
        }
    }
    
    /**
     * Evict oldest entries when max size exceeded
     * @private
     */
    _evictOldest() {
        const entries = Array.from(this.processedOperations.entries());
        entries.sort((a, b) => a[1].timestamp - b[1].timestamp);
        
        const toEvict = Math.floor(this.maxEntries * 0.2);  // Evict 20%
        for (let i = 0; i < toEvict; i++) {
            this.processedOperations.delete(entries[i][0]);
        }
        
        console.log(`🧹 Idempotency eviction: removed ${toEvict} oldest entries (max size: ${this.maxEntries})`);
    }
    
    /**
     * Helper: Sort object keys recursively for consistent hashing
     * @private
     */
    _sortObject(obj) {
        if (obj === null || typeof obj !== 'object') {
            return obj;
        }
        
        if (Array.isArray(obj)) {
            return obj.map(item => this._sortObject(item));
        }
        
        return Object.keys(obj)
            .sort()
            .reduce((result, key) => {
                result[key] = this._sortObject(obj[key]);
                return result;
            }, {});
    }
    
    /**
     * Get statistics
     * @returns {Object} Statistics
     */
    getStats() {
        return {
            total_tracked: this.processedOperations.size,
            max_entries: this.maxEntries,
            eviction_threshold_ms: this.evictionThreshold
        };
    }
    
    /**
     * Clear all tracked operations (debug/test only)
     */
    clearAll() {
        this.processedOperations.clear();
        console.log('🗑️ All idempotency entries cleared');
    }
    
    /**
     * Destroy manager and cleanup
     */
    destroy() {
        if (this.cleanupInterval) {
            clearInterval(this.cleanupInterval);
            this.cleanupInterval = null;
        }
        this.processedOperations.clear();
        console.log('🔒 Idempotency Manager destroyed');
    }
}

// Export singleton
window.idempotencyManager = new IdempotencyManager();

console.log('🔒 CROWN⁴.5 Idempotency Layer loaded');
