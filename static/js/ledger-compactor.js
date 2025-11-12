/**
 * LedgerCompactor - CROWN⁴.5 Event Ledger Maintenance
 * 
 * Implements daily mutation compression for EventLedger. Monitors ledger status
 * and triggers compaction to reduce database size while maintaining audit trail.
 * 
 * Key Features:
 * - Monitor ledger status and compaction metrics
 * - Trigger manual/automatic compaction
 * - Track compaction success rates
 * - Telemetry for ledger health
 * 
 * Integration:
 * - Monitors EventLedger size growth
 * - Triggers background compaction
 * - Reports metrics to telemetry system
 */

class LedgerCompactor {
    constructor() {
        this.initialized = false;
        
        // Metrics tracking
        this.metrics = {
            totalCompactions: 0,
            eventsCompacted: 0,
            eventsDeleted: 0,
            summariesCreated: 0,
            failedCompactions: 0,
            lastCompactionTime: null
        };
        
        // Configuration
        this.config = {
            autoCompact: false,            // Auto-compact on schedule
            compactionInterval: 86400000,  // Daily (24 hours)
            batchSize: 1000,               // Events per compaction batch
            monitoringInterval: 3600000    // Monitor every 1 hour
        };
        
        // State
        this.monitoringTimer = null;
        this.ledgerStatus = null;
    }

    /**
     * Initialize LedgerCompactor
     */
    async init() {
        if (this.initialized) {
            return;
        }

        console.log('🗜️ LedgerCompactor initializing...');

        // Load initial ledger status
        await this.refreshStatus();

        // Start monitoring if enabled
        if (this.config.autoCompact) {
            this.startMonitoring();
        }

        this.initialized = true;
        console.log('✅ LedgerCompactor ready');
    }

    /**
     * Refresh ledger status from server
     * @returns {Promise<Object>} Ledger status
     */
    async refreshStatus() {
        if (!this.initialized && !this.config) {
            await this.init();
        }

        try {
            const response = await fetch('/api/tasks/ledger/status', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (!result.success) {
                console.error('❌ Failed to get ledger status:', result.message);
                return null;
            }

            this.ledgerStatus = result.status;

            // Update local metrics
            if (result.status.metrics) {
                Object.assign(this.metrics, {
                    totalCompactions: result.status.metrics.total_compactions || 0,
                    eventsCompacted: result.status.metrics.events_compacted || 0,
                    eventsDeleted: result.status.metrics.events_deleted || 0,
                    summariesCreated: result.status.metrics.summaries_created || 0,
                    failedCompactions: result.status.metrics.compaction_failures || 0,
                    lastCompactionTime: result.status.metrics.last_compaction_time
                });
            }

            console.log('📊 Ledger status:', {
                totalEvents: this.ledgerStatus.total_events,
                readyForCompaction: this.ledgerStatus.events_ready_for_compaction
            });

            // Emit telemetry
            this.emitTelemetry('status-refresh', {
                totalEvents: this.ledgerStatus.total_events,
                readyForCompaction: this.ledgerStatus.events_ready_for_compaction
            });

            return this.ledgerStatus;

        } catch (error) {
            console.error('❌ Failed to refresh ledger status:', error);
            return null;
        }
    }

    /**
     * Trigger ledger compaction
     * @param {Object} options Compaction options
     * @returns {Promise<Object>} Compaction result
     */
    async compact(options = {}) {
        if (!this.initialized) {
            await this.init();
        }

        const {
            dryRun = false,
            batchSize = this.config.batchSize
        } = options;

        try {
            console.log(`🗜️ Starting ledger compaction (batch_size=${batchSize}, dry_run=${dryRun})...`);

            const response = await fetch('/api/tasks/ledger/compact', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    dry_run: dryRun,
                    batch_size: batchSize
                })
            });

            const result = await response.json();

            if (!result.success) {
                console.error('❌ Compaction failed:', result.message);
                this.metrics.failedCompactions++;
                
                this.emitTelemetry('compaction-failed', {
                    error: result.message,
                    dryRun
                });
                
                return null;
            }

            const { result: compactionResult } = result;

            if (compactionResult.events_compacted > 0) {
                console.log('✅ Compaction completed:', {
                    eventsCompacted: compactionResult.events_compacted,
                    eventsDeleted: compactionResult.events_deleted,
                    summaryId: compactionResult.summary_id
                });

                // Update metrics (if not dry run)
                if (!dryRun) {
                    this.metrics.totalCompactions++;
                    this.metrics.eventsCompacted += compactionResult.events_compacted;
                    this.metrics.eventsDeleted += compactionResult.events_deleted;
                    if (compactionResult.summary_id) {
                        this.metrics.summariesCreated++;
                    }
                    this.metrics.lastCompactionTime = new Date().toISOString();
                }

                // Emit telemetry
                this.emitTelemetry('compaction-completed', {
                    eventsCompacted: compactionResult.events_compacted,
                    eventsDeleted: compactionResult.events_deleted,
                    dryRun,
                    summaryId: compactionResult.summary_id
                });
            } else {
                console.log('✅ No events ready for compaction');
                
                this.emitTelemetry('compaction-skipped', {
                    reason: 'no_events_ready',
                    dryRun
                });
            }

            // Refresh status after compaction
            await this.refreshStatus();

            return compactionResult;

        } catch (error) {
            console.error('❌ Failed to compact ledger:', error);
            this.metrics.failedCompactions++;
            
            this.emitTelemetry('compaction-error', {
                error: error.message
            });
            
            return null;
        }
    }

    /**
     * Start periodic monitoring and auto-compaction
     */
    startMonitoring() {
        // Clear existing timer
        if (this.monitoringTimer) {
            clearInterval(this.monitoringTimer);
        }

        // Monitor immediately
        this.checkAndCompact();

        // Then monitor periodically
        this.monitoringTimer = setInterval(
            () => this.checkAndCompact(),
            this.config.monitoringInterval
        );

        console.log(`📊 Ledger monitoring started (every ${this.config.monitoringInterval / 1000}s)`);
    }

    /**
     * Stop periodic monitoring
     */
    stopMonitoring() {
        if (this.monitoringTimer) {
            clearInterval(this.monitoringTimer);
            this.monitoringTimer = null;
            console.log('⏸️ Ledger monitoring stopped');
        }
    }

    /**
     * Check ledger status and auto-compact if needed
     */
    async checkAndCompact() {
        try {
            // Refresh status
            const status = await this.refreshStatus();

            if (!status) {
                return;
            }

            // Auto-compact if events ready
            if (status.events_ready_for_compaction > 0) {
                console.log(`🔔 Auto-compaction triggered: ${status.events_ready_for_compaction} events ready`);
                await this.compact({ dryRun: false });
            }

        } catch (error) {
            console.error('❌ Monitor check failed:', error);
        }
    }

    /**
     * Get current metrics
     * @returns {Object} Current metrics
     */
    getMetrics() {
        return {
            ...this.metrics,
            ledgerStatus: this.ledgerStatus,
            autoCompactEnabled: this.config.autoCompact
        };
    }

    /**
     * Get current ledger status
     * @returns {Object} Ledger status
     */
    getStatus() {
        return this.ledgerStatus;
    }

    /**
     * Update configuration
     * @param {Object} newConfig Configuration updates
     */
    updateConfig(newConfig) {
        Object.assign(this.config, newConfig);
        console.log('⚙️ LedgerCompactor config updated:', this.config);

        // Restart monitoring if settings changed
        if (this.monitoringTimer && (newConfig.monitoringInterval || newConfig.autoCompact !== undefined)) {
            if (newConfig.autoCompact === false) {
                this.stopMonitoring();
            } else {
                this.startMonitoring();
            }
        }
    }

    /**
     * Emit telemetry event
     * @param {string} action Action name
     * @param {Object} data Event data
     */
    emitTelemetry(action, data) {
        // Emit custom event for telemetry systems
        document.dispatchEvent(new CustomEvent('telemetry:ledger-compactor', {
            detail: {
                action,
                timestamp: new Date().toISOString(),
                ...data,
                metrics: this.getMetrics()
            }
        }));
    }

    /**
     * Cleanup on shutdown
     */
    destroy() {
        this.stopMonitoring();
        this.initialized = false;
        console.log('🛑 LedgerCompactor destroyed');
    }
}

// Create singleton instance
const ledgerCompactor = new LedgerCompactor();

// Auto-initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        ledgerCompactor.init();
    });
} else {
    ledgerCompactor.init();
}

// Export for use in other modules
window.ledgerCompactor = ledgerCompactor;
