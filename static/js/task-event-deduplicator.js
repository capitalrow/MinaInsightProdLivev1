/**
 * CROWN⁴.5 Task Event Deduplicator
 * Prevents double-apply of events when both WebSocket and BroadcastChannel deliver the same update.
 * 
 * Architecture:
 * - Maintains a rolling window of recently processed event IDs
 * - Both WebSocket handlers and MultiTabSync check before processing
 * - Uses event_id from CROWN metadata, or generates composite ID from task data
 * - LRU eviction keeps memory bounded
 */

class TaskEventDeduplicator {
    constructor(options = {}) {
        this.maxEvents = options.maxEvents || 500;
        this.ttlMs = options.ttlMs || 60000; // 60 seconds default TTL
        this.processedEvents = new Map(); // eventId -> { timestamp, source }
        this._cleanupInterval = null;
        
        this._startCleanup();
        console.log('✅ [TaskEventDeduplicator] Initialized');
    }
    
    /**
     * Generate a unique event ID from event data
     * Prioritizes CROWN event_id, falls back to deterministic composite key
     * @param {string} eventType - Event type (task_created, task_updated, etc.)
     * @param {Object} data - Event data
     * @returns {string} Unique event identifier
     */
    generateEventId(eventType, data) {
        // Priority 1: Use CROWN event_id if available
        if (data?.event_id) {
            return `crown_${data.event_id}`;
        }
        
        // Priority 2: Use task's _crown_event_id
        const task = data?.task || data?.data?.task || data;
        if (task?._crown_event_id) {
            return `crown_${task._crown_event_id}`;
        }
        
        // Priority 3: Generate DETERMINISTIC composite ID from task data
        // CRITICAL: Do NOT use Date.now() - it causes WebSocket and BroadcastChannel
        // to generate different IDs for the same event, defeating deduplication
        const taskId = task?.id || data?.task_id || data?.taskId || 'unknown';
        
        // Use task's updated_at timestamp (from server) for versioning, NOT Date.now()
        // If no updated_at, fall back to created_at, then use task_id only
        const serverTimestamp = task?.updated_at || task?.created_at || data?.timestamp || '';
        
        // Build deterministic fingerprint from immutable payload fields
        const fingerprint = [
            eventType,
            taskId,
            task?.status || '',
            task?.priority || '',
            (task?.title || '').substring(0, 30),
            serverTimestamp
        ].join('|');
        
        // Simple deterministic hash to keep ID compact
        const hash = this._simpleHash(fingerprint);
        
        return `composite_${taskId}_${hash}`;
    }
    
    /**
     * Simple deterministic hash function for composite IDs
     * @param {string} str - String to hash
     * @returns {string} 8-character hex hash
     * @private
     */
    _simpleHash(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        return Math.abs(hash).toString(16).padStart(8, '0').substring(0, 8);
    }
    
    /**
     * Check if an event has already been processed
     * @param {string} eventId - Event identifier
     * @returns {boolean} True if already processed
     */
    isDuplicate(eventId) {
        if (!eventId) return false;
        
        const entry = this.processedEvents.get(eventId);
        if (!entry) return false;
        
        // Check if TTL has expired
        if (Date.now() - entry.timestamp > this.ttlMs) {
            this.processedEvents.delete(eventId);
            return false;
        }
        
        return true;
    }
    
    /**
     * Mark an event as processed
     * @param {string} eventId - Event identifier
     * @param {string} source - Source channel ('websocket' | 'broadcast')
     */
    markProcessed(eventId, source = 'unknown') {
        if (!eventId) return;
        
        this.processedEvents.set(eventId, {
            timestamp: Date.now(),
            source
        });
        
        // LRU eviction if over capacity
        if (this.processedEvents.size > this.maxEvents) {
            this._evictOldest();
        }
    }
    
    /**
     * Check and mark in one atomic operation
     * Returns true if this is a NEW event (should process), false if duplicate
     * @param {string} eventType - Event type
     * @param {Object} data - Event data
     * @param {string} source - Source channel
     * @returns {{isNew: boolean, eventId: string, duplicateSource?: string}}
     */
    checkAndMark(eventType, data, source) {
        const eventId = this.generateEventId(eventType, data);
        
        if (this.isDuplicate(eventId)) {
            const entry = this.processedEvents.get(eventId);
            console.log(`🔄 [Dedup] Skipping duplicate ${eventType} (id=${eventId.substring(0, 30)}...) - already via ${entry?.source}`);
            return { isNew: false, eventId, duplicateSource: entry?.source };
        }
        
        this.markProcessed(eventId, source);
        console.log(`✅ [Dedup] Processing ${eventType} via ${source} (id=${eventId.substring(0, 30)}...)`);
        return { isNew: true, eventId };
    }
    
    /**
     * Evict oldest entries when over capacity
     * @private
     */
    _evictOldest() {
        const toEvict = this.processedEvents.size - this.maxEvents + 50; // Evict 50 extra for buffer
        if (toEvict <= 0) return;
        
        const entries = Array.from(this.processedEvents.entries())
            .sort((a, b) => a[1].timestamp - b[1].timestamp);
        
        for (let i = 0; i < toEvict && i < entries.length; i++) {
            this.processedEvents.delete(entries[i][0]);
        }
    }
    
    /**
     * Start periodic cleanup of expired entries
     * @private
     */
    _startCleanup() {
        this._cleanupInterval = setInterval(() => {
            const now = Date.now();
            let cleaned = 0;
            
            for (const [eventId, entry] of this.processedEvents.entries()) {
                if (now - entry.timestamp > this.ttlMs) {
                    this.processedEvents.delete(eventId);
                    cleaned++;
                }
            }
            
            if (cleaned > 0) {
                console.log(`🧹 [Dedup] Cleaned ${cleaned} expired entries, ${this.processedEvents.size} remaining`);
            }
        }, 30000); // Cleanup every 30 seconds
    }
    
    /**
     * Get stats for debugging
     * @returns {Object}
     */
    getStats() {
        const now = Date.now();
        const sources = { websocket: 0, broadcast: 0, unknown: 0 };
        
        for (const entry of this.processedEvents.values()) {
            sources[entry.source] = (sources[entry.source] || 0) + 1;
        }
        
        return {
            total: this.processedEvents.size,
            bySource: sources,
            maxEvents: this.maxEvents,
            ttlMs: this.ttlMs
        };
    }
    
    /**
     * Cleanup
     */
    destroy() {
        if (this._cleanupInterval) {
            clearInterval(this._cleanupInterval);
        }
        this.processedEvents.clear();
    }
}

// Singleton instance
if (!window.taskEventDeduplicator) {
    window.taskEventDeduplicator = new TaskEventDeduplicator();
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TaskEventDeduplicator;
}
