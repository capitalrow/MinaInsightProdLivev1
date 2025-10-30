/**
 * CROWN⁴ Telemetry System
 * 
 * Tracks and persists performance metrics for CROWN⁴ compliance:
 * - Bootstrap time (<200ms target)
 * - Event propagation latency (<300ms target)
 * - Cache hit ratio (>80% target)
 * - Sequence lag (0 target - zero desync)
 * - Offline queue depth
 */

class CROWNTelemetry {
    constructor(workspaceId) {
        this.workspaceId = workspaceId;
        this.dbName = `crown_telemetry_ws${workspaceId}`;
        this.db = null;
        
        // CROWN⁴.5: Session trace ID for request tracing
        this.sessionTraceId = this.generateTraceId();
        this.lastEmotionTime = null;
        
        // In-memory metrics for current session
        this.sessionMetrics = {
            bootstrapTime: null,
            cacheHydrationTime: null,
            networkFetchTime: null,
            cacheHits: 0,
            cacheMisses: 0,
            eventPropagations: [],
            sequenceLags: [],
            offlineQueueDepth: 0,
            emotionCues: {},
            calmScore: 100
        };
        
        // Performance targets (CROWN⁴ specification)
        this.targets = {
            bootstrap: 200,        // ms
            propagation: 300,      // ms
            cacheHitRatio: 0.80,   // 80%
            sequenceLag: 0,        // zero desync
            quietWindow: 5000      // ms between animations for calm UI
        };
        
        // Don't auto-init - let caller control initialization timing
    }
    
    generateTraceId() {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return `trace_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    createTraceChildId(parentId = null) {
        const parent = parentId || this.sessionTraceId;
        return `${parent}_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
    }
    
    /**
     * Initialize telemetry database
     */
    async init() {
        try {
            this.db = await this.openDB();
            console.log('📊 CROWN⁴ Telemetry initialized');
        } catch (error) {
            console.error('❌ Failed to initialize telemetry:', error);
        }
    }
    
    /**
     * Open IndexedDB for telemetry storage
     */
    openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, 1);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Metrics store: historical performance data
                if (!db.objectStoreNames.contains('metrics')) {
                    const metricsStore = db.createObjectStore('metrics', { 
                        keyPath: 'id', 
                        autoIncrement: true 
                    });
                    metricsStore.createIndex('timestamp', 'timestamp', { unique: false });
                    metricsStore.createIndex('type', 'type', { unique: false });
                }
                
                // Events store: event propagation tracking
                if (!db.objectStoreNames.contains('events')) {
                    const eventsStore = db.createObjectStore('events', { 
                        keyPath: 'eventId' 
                    });
                    eventsStore.createIndex('timestamp', 'timestamp', { unique: false });
                }
            };
        });
    }
    
    /**
     * Record bootstrap metrics
     */
    async recordBootstrap(metrics) {
        this.sessionMetrics.bootstrapTime = metrics.totalBootstrapTime;
        this.sessionMetrics.cacheHydrationTime = metrics.cacheHydrationTime;
        this.sessionMetrics.networkFetchTime = metrics.networkFetchTime;
        
        await this.saveMetric({
            type: 'bootstrap',
            timestamp: Date.now(),
            data: {
                totalTime: metrics.totalBootstrapTime,
                cacheTime: metrics.cacheHydrationTime,
                networkTime: metrics.networkFetchTime,
                targetMet: metrics.totalBootstrapTime < this.targets.bootstrap
            }
        });
        
        // Log compliance status
        const status = metrics.totalBootstrapTime < this.targets.bootstrap ? '✅' : '⚠️';
        console.log(
            `${status} Bootstrap: ${metrics.totalBootstrapTime.toFixed(0)}ms ` +
            `(target: <${this.targets.bootstrap}ms)`
        );
    }
    
    /**
     * Record cache hit or miss
     */
    recordCacheAccess(hit) {
        if (hit) {
            this.sessionMetrics.cacheHits++;
        } else {
            this.sessionMetrics.cacheMisses++;
        }
    }
    
    /**
     * Get cache hit ratio
     */
    getCacheHitRatio() {
        const total = this.sessionMetrics.cacheHits + this.sessionMetrics.cacheMisses;
        return total > 0 ? this.sessionMetrics.cacheHits / total : 0;
    }
    
    /**
     * Record event propagation latency
     * @param {string} eventId - Event identifier
     * @param {number} sentTimestamp - When event was sent (ms since epoch)
     * @param {number} receivedTimestamp - When event was received (ms since epoch)
     */
    async recordEventPropagation(eventId, sentTimestamp, receivedTimestamp) {
        const latency = receivedTimestamp - sentTimestamp;
        
        this.sessionMetrics.eventPropagations.push({
            eventId,
            latency,
            timestamp: Date.now()
        });
        
        // Keep only last 100 events in memory
        if (this.sessionMetrics.eventPropagations.length > 100) {
            this.sessionMetrics.eventPropagations.shift();
        }
        
        await this.saveMetric({
            type: 'event_propagation',
            timestamp: Date.now(),
            data: {
                eventId,
                latency,
                targetMet: latency < this.targets.propagation
            }
        });
        
        // Log if target missed
        if (latency >= this.targets.propagation) {
            console.warn(
                `⚠️ Event propagation slow: ${latency.toFixed(0)}ms ` +
                `(target: <${this.targets.propagation}ms) - ${eventId}`
            );
        }
    }
    
    /**
     * Record sequence lag (gap in event sequence)
     */
    async recordSequenceLag(expected, received) {
        const lag = received - expected;
        
        if (lag > 0) {
            this.sessionMetrics.sequenceLags.push({
                expected,
                received,
                lag,
                timestamp: Date.now()
            });
            
            await this.saveMetric({
                type: 'sequence_lag',
                timestamp: Date.now(),
                data: {
                    expected,
                    received,
                    lag,
                    targetMet: lag === 0
                }
            });
            
            console.error(`❌ Sequence lag detected: expected ${expected}, got ${received} (gap: ${lag})`);
        }
    }
    
    /**
     * Update offline queue depth
     */
    updateOfflineQueueDepth(depth) {
        this.sessionMetrics.offlineQueueDepth = depth;
    }
    
    /**
     * Record emotion cue (CROWN⁴.5 Telemetry 2.0)
     */
    async recordEmotionCue(cue, context = {}) {
        const now = Date.now();
        
        if (!this.sessionMetrics.emotionCues[cue]) {
            this.sessionMetrics.emotionCues[cue] = { count: 0, lastTimestamp: null };
        }
        
        this.sessionMetrics.emotionCues[cue].count++;
        this.sessionMetrics.emotionCues[cue].lastTimestamp = now;
        
        if (this.lastEmotionTime) {
            const timeSinceLastEmotion = now - this.lastEmotionTime;
            this.sessionMetrics.calmScore = Math.min(100, Math.max(0, 
                (timeSinceLastEmotion / this.targets.quietWindow) * 100
            ));
        }
        
        this.lastEmotionTime = now;
        
        await this.saveMetric({
            type: 'emotion_cue',
            timestamp: now,
            data: {
                cue,
                count: this.sessionMetrics.emotionCues[cue].count,
                calm_score: this.sessionMetrics.calmScore,
                context
            }
        });
    }
    
    /**
     * Get average event propagation latency
     */
    getAveragePropagationLatency() {
        if (this.sessionMetrics.eventPropagations.length === 0) return 0;
        
        const sum = this.sessionMetrics.eventPropagations.reduce(
            (acc, event) => acc + event.latency, 
            0
        );
        return sum / this.sessionMetrics.eventPropagations.length;
    }
    
    /**
     * Get P95 event propagation latency
     */
    getP95PropagationLatency() {
        if (this.sessionMetrics.eventPropagations.length === 0) return 0;
        
        const latencies = this.sessionMetrics.eventPropagations
            .map(e => e.latency)
            .sort((a, b) => a - b);
        
        const p95Index = Math.floor(latencies.length * 0.95);
        return latencies[p95Index] || 0;
    }
    
    /**
     * Get total sequence lag
     */
    getTotalSequenceLag() {
        return this.sessionMetrics.sequenceLags.reduce(
            (acc, lag) => acc + lag.lag, 
            0
        );
    }
    
    /**
     * Get current telemetry summary
     */
    getSummary() {
        const avgPropagation = this.getAveragePropagationLatency();
        const p95Propagation = this.getP95PropagationLatency();
        const cacheHitRatio = this.getCacheHitRatio();
        const totalLag = this.getTotalSequenceLag();
        
        return {
            bootstrap: {
                time: this.sessionMetrics.bootstrapTime,
                target: this.targets.bootstrap,
                status: this.sessionMetrics.bootstrapTime < this.targets.bootstrap ? 'pass' : 'fail'
            },
            propagation: {
                avg: avgPropagation,
                p95: p95Propagation,
                target: this.targets.propagation,
                status: p95Propagation < this.targets.propagation ? 'pass' : 'fail',
                count: this.sessionMetrics.eventPropagations.length
            },
            cache: {
                hitRatio: cacheHitRatio,
                hits: this.sessionMetrics.cacheHits,
                misses: this.sessionMetrics.cacheMisses,
                target: this.targets.cacheHitRatio,
                status: cacheHitRatio >= this.targets.cacheHitRatio ? 'pass' : 'fail'
            },
            sequence: {
                totalLag: totalLag,
                lagCount: this.sessionMetrics.sequenceLags.length,
                target: this.targets.sequenceLag,
                status: totalLag === 0 ? 'pass' : 'fail'
            },
            offline: {
                queueDepth: this.sessionMetrics.offlineQueueDepth
            }
        };
    }
    
    /**
     * Log telemetry summary to console
     */
    logSummary() {
        const summary = this.getSummary();
        
        console.group('📊 CROWN⁴ Telemetry Summary');
        console.log(`${summary.bootstrap.status === 'pass' ? '✅' : '❌'} Bootstrap: ${summary.bootstrap.time?.toFixed(0) || 'N/A'}ms (target: <${summary.bootstrap.target}ms)`);
        console.log(`${summary.propagation.status === 'pass' ? '✅' : '❌'} Event Propagation (P95): ${summary.propagation.p95.toFixed(0)}ms (target: <${summary.propagation.target}ms)`);
        console.log(`   ├─ Average: ${summary.propagation.avg.toFixed(0)}ms`);
        console.log(`   └─ Events tracked: ${summary.propagation.count}`);
        console.log(`${summary.cache.status === 'pass' ? '✅' : '❌'} Cache Hit Ratio: ${(summary.cache.hitRatio * 100).toFixed(1)}% (target: >=${summary.cache.target * 100}%)`);
        console.log(`   ├─ Hits: ${summary.cache.hits}`);
        console.log(`   └─ Misses: ${summary.cache.misses}`);
        console.log(`${summary.sequence.status === 'pass' ? '✅' : '❌'} Sequence Integrity: ${summary.sequence.totalLag === 0 ? 'Perfect' : `${summary.sequence.lagCount} gaps detected`}`);
        console.log(`📦 Offline Queue: ${summary.offline.queueDepth} pending operations`);
        console.groupEnd();
    }
    
    /**
     * Save metric to IndexedDB
     */
    async saveMetric(metric) {
        if (!this.db) return;
        
        metric.trace_id = this.sessionTraceId;
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['metrics'], 'readwrite');
            const store = transaction.objectStore('metrics');
            const request = store.add(metric);
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Get historical metrics
     */
    async getHistoricalMetrics(type = null, limit = 100) {
        if (!this.db) return [];
        
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['metrics'], 'readonly');
            const store = transaction.objectStore('metrics');
            
            let request;
            if (type) {
                const index = store.index('type');
                request = index.getAll(type, limit);
            } else {
                request = store.getAll(null, limit);
            }
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Record a generic metric (key-value pair)
     * @param {string} metricName - Name of the metric
     * @param {number} value - Metric value
     */
    recordMetric(metricName, value) {
        // Store in session metrics
        if (!this.sessionMetrics.customMetrics) {
            this.sessionMetrics.customMetrics = {};
        }
        this.sessionMetrics.customMetrics[metricName] = value;
        
        // Optionally persist to IndexedDB
        this.saveMetric({
            type: 'custom',
            name: metricName,
            value: value,
            timestamp: Date.now()
        }).catch(err => console.warn('Failed to save custom metric:', err));
    }
    
    /**
     * Record a generic event
     * @param {string} eventName - Name of the event
     * @param {Object} data - Event data
     */
    recordEvent(eventName, data) {
        const event = {
            eventId: `${eventName}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            type: eventName,
            data: data,
            timestamp: Date.now()
        };
        
        // Persist to IndexedDB events store
        if (this.db) {
            const transaction = this.db.transaction(['events'], 'readwrite');
            const store = transaction.objectStore('events');
            store.add(event).catch(err => console.warn('Failed to save event:', err));
        }
    }
}

// Auto-initialize telemetry instance
(async function() {
    // Get workspace ID from page context (or use 'default')
    const workspaceId = window.WORKSPACE_ID || 'default';
    
    // Create instance
    const telemetryInstance = new CROWNTelemetry(workspaceId);
    
    // Initialize database
    await telemetryInstance.init();
    
    // Make instance globally available
    window.CROWNTelemetry = telemetryInstance;
    
    console.log('✅ CROWNTelemetry initialized and ready');
})();
