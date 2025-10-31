/**
 * CROWN⁴.5 Cache Validator
 * 
 * Maintains cache integrity using MD5 checksums and drift detection.
 * Ensures client cache matches server truth through periodic validation.
 * 
 * Key Features:
 * - MD5 checksum validation for cache consistency
 * - Automatic drift detection and correction
 * - Silent reconciliation without UI disruption
 * - Performance metrics for cache hit rate
 */

class CacheValidator {
    constructor() {
        this.checksums = {};  // {key: checksum}
        this.lastValidation = {};  // {key: timestamp}
        this.driftDetected = new Set();
        this.validationInterval = 30000;  // 30s default
        this.stats = {
            validations: 0,
            drifts: 0,
            corrections: 0,
            hits: 0,
            misses: 0
        };
        
        console.log('✅ CacheValidator initialized');
    }
    
    /**
     * Compute MD5 checksum of data
     * @param {*} data - Any JSON-serializable data
     * @returns {Promise<string>} MD5 hash
     */
    async computeChecksum(data) {
        const normalized = this.normalizeData(data);
        const text = JSON.stringify(normalized);
        const encoder = new TextEncoder();
        const dataBuffer = encoder.encode(text);
        
        // Use SubtleCrypto for MD5 (fallback to simple hash if unavailable)
        if (window.crypto && window.crypto.subtle) {
            try {
                const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
                const hashArray = Array.from(new Uint8Array(hashBuffer));
                return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            } catch (e) {
                console.warn('⚠️ SubtleCrypto not available, using simple hash');
            }
        }
        
        // Fallback to simple hash
        return this.simpleHash(text);
    }
    
    /**
     * Simple hash function (fallback)
     */
    simpleHash(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(36);
    }
    
    /**
     * Normalize data for consistent checksums
     */
    normalizeData(data) {
        if (Array.isArray(data)) {
            // Sort arrays by id if objects, otherwise leave as-is
            const sorted = data.map(item => this.normalizeData(item));
            if (sorted.length > 0 && sorted[0].id !== undefined) {
                return sorted.sort((a, b) => {
                    const aId = a.id || 0;
                    const bId = b.id || 0;
                    return aId - bId;
                });
            }
            return sorted;
        } else if (data !== null && typeof data === 'object') {
            // Sort object keys for consistent ordering
            const normalized = {};
            Object.keys(data).sort().forEach(key => {
                // Skip volatile fields that shouldn't affect checksum
                if (!this.isVolatileField(key)) {
                    normalized[key] = this.normalizeData(data[key]);
                }
            });
            return normalized;
        }
        return data;
    }
    
    /**
     * Check if field is volatile (shouldn't affect checksum)
     */
    isVolatileField(fieldName) {
        const volatileFields = [
            'lastSynced',
            'cached_at',
            'ui_state',
            'scroll_position',
            'selected',
            'hover',
            'focus'
        ];
        return volatileFields.includes(fieldName);
    }
    
    /**
     * Validate cached data against checksum
     * @param {string} key - Cache key
     * @param {*} data - Cached data
     * @param {string} expectedChecksum - Server-provided checksum
     * @returns {Promise<Object>} {valid: boolean, drift: boolean, checksum: string}
     */
    async validate(key, data, expectedChecksum) {
        this.stats.validations++;
        
        const actualChecksum = await this.computeChecksum(data);
        this.checksums[key] = actualChecksum;
        this.lastValidation[key] = Date.now();
        
        const valid = actualChecksum === expectedChecksum;
        
        if (!valid) {
            console.warn(`⚠️ Cache drift detected for "${key}":`);
            console.warn(`   Expected: ${expectedChecksum}`);
            console.warn(`   Actual:   ${actualChecksum}`);
            this.driftDetected.add(key);
            this.stats.drifts++;
            return { valid: false, drift: true, checksum: actualChecksum };
        }
        
        // Clear drift flag if previously detected
        if (this.driftDetected.has(key)) {
            this.driftDetected.delete(key);
            this.stats.corrections++;
            console.log(`✅ Cache drift corrected for "${key}"`);
        }
        
        return { valid: true, drift: false, checksum: actualChecksum };
    }
    
    /**
     * Quick checksum comparison without recomputation
     * @param {string} key - Cache key
     * @param {string} serverChecksum - Server checksum
     * @returns {boolean} True if checksums match
     */
    quickCheck(key, serverChecksum) {
        const localChecksum = this.checksums[key];
        if (!localChecksum) {
            this.stats.misses++;
            return false;
        }
        
        const match = localChecksum === serverChecksum;
        if (match) {
            this.stats.hits++;
        } else {
            this.stats.misses++;
        }
        return match;
    }
    
    /**
     * Compute checksum and store for later quick checks
     * @param {string} key - Cache key
     * @param {*} data - Data to checksum
     * @returns {Promise<string>} Computed checksum
     */
    async update(key, data) {
        const checksum = await this.computeChecksum(data);
        this.checksums[key] = checksum;
        this.lastValidation[key] = Date.now();
        return checksum;
    }
    
    /**
     * Check if cache needs revalidation (time-based)
     * @param {string} key - Cache key
     * @param {number} maxAge - Max age in ms (default: validationInterval)
     * @returns {boolean} True if stale
     */
    isStale(key, maxAge = this.validationInterval) {
        const lastCheck = this.lastValidation[key];
        if (!lastCheck) return true;
        return (Date.now() - lastCheck) > maxAge;
    }
    
    /**
     * Get all keys with detected drift
     * @returns {Array<string>} Drifted keys
     */
    getDriftedKeys() {
        return Array.from(this.driftDetected);
    }
    
    /**
     * Clear cache for a key
     */
    invalidate(key) {
        delete this.checksums[key];
        delete this.lastValidation[key];
        this.driftDetected.delete(key);
        console.log(`🗑️ Cache invalidated: ${key}`);
    }
    
    /**
     * Clear all cache
     */
    clear() {
        this.checksums = {};
        this.lastValidation = {};
        this.driftDetected.clear();
        console.log('🗑️ All cache cleared');
    }
    
    /**
     * Get cache statistics
     */
    getStats() {
        const hitRate = this.stats.hits + this.stats.misses > 0
            ? this.stats.hits / (this.stats.hits + this.stats.misses)
            : 0;
        
        return {
            ...this.stats,
            hitRate: hitRate.toFixed(3),
            driftedKeys: this.getDriftedKeys().length,
            trackedKeys: Object.keys(this.checksums).length
        };
    }
    
    /**
     * Start automatic validation cycle
     */
    startAutoValidation(interval = this.validationInterval) {
        if (this.validationTimer) {
            clearInterval(this.validationTimer);
        }
        
        this.validationTimer = setInterval(() => {
            const staleKeys = Object.keys(this.lastValidation)
                .filter(key => this.isStale(key));
            
            if (staleKeys.length > 0) {
                console.log(`🔄 ${staleKeys.length} cache keys are stale, triggering validation`);
                // Emit event for application to revalidate
                window.dispatchEvent(new CustomEvent('cache:revalidate', {
                    detail: { keys: staleKeys }
                }));
            }
        }, interval);
        
        console.log(`✅ Auto-validation started (interval: ${interval}ms)`);
    }
    
    /**
     * Stop automatic validation
     */
    stopAutoValidation() {
        if (this.validationTimer) {
            clearInterval(this.validationTimer);
            this.validationTimer = null;
            console.log('⏸️ Auto-validation stopped');
        }
    }
}

// Global instance
window.TaskCacheValidator = new CacheValidator();

console.log('✅ CROWN⁴.5 CacheValidator loaded');
