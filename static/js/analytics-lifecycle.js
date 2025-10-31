/**
 * Analytics Lifecycle Manager - CROWN⁵+ Event Orchestration
 * 
 * Manages the 10-event lifecycle for analytics intelligence:
 * 1. analytics_bootstrap - Cache-first paint
 * 2. analytics_ws_subscribe - Socket handshake
 * 3. analytics_header_reconcile - ETag validation
 * 4. analytics_overview_hydrate - Default tab load
 * 5. analytics_prefetch_tabs - Background prefetch
 * 6. analytics_delta_apply - Real-time updates
 * 7. analytics_filter_change - Date range changes
 * 8. analytics_tab_switch - Tab navigation
 * 9. analytics_export_initiated - Export tracking
 * 10. analytics_idle_sync - Background validation
 * 
 * Performance targets:
 * - First Paint: <200ms (cache warm)
 * - Full Sync: <450ms (cache cold)
 * - Delta Apply: <100ms
 * - Tab Switch: <150ms
 */

import { analyticsCache } from './analytics-cache.js';

export class AnalyticsLifecycle {
    constructor(socket, workspaceId) {
        this.socket = socket;
        this.workspaceId = workspaceId;
        this.days = 30; // Default time range
        this.currentSnapshot = null;
        this.lastEventId = null;
        this.syncIntervalId = null;
        this.prefetchController = null;
        this.telemetry = {
            firstPaint: null,
            fullSync: null,
            deltaCount: 0,
            driftDetections: 0
        };

        // Event handlers (to be set by consumer)
        this.onSnapshotUpdate = null;
        this.onDeltaUpdate = null;
        this.onError = null;

        this._setupSocketHandlers();
    }

    /**
     * Bootstrap analytics - cache-first pattern
     * 
     * Flow:
     * 1. Check IndexedDB cache
     * 2. Paint cached data immediately (<200ms)
     * 3. Validate checksums with server
     * 4. Apply delta if needed
     * 5. Start background sync
     */
    async bootstrap() {
        const startTime = performance.now();
        console.log('🚀 Analytics bootstrap started');

        try {
            // Step 1: Check cache
            const cached = await analyticsCache.get(this.workspaceId, this.days);

            if (cached && cached.snapshot && !cached.stale) {
                // Cache hit - instant paint
                this.currentSnapshot = cached.snapshot;
                this.lastEventId = cached.last_event_id;
                
                const paintTime = performance.now() - startTime;
                this.telemetry.firstPaint = paintTime;
                
                console.log(`✨ Cache-first paint: ${Math.round(paintTime)}ms`);
                
                // Trigger UI update
                if (this.onSnapshotUpdate) {
                    this.onSnapshotUpdate(this.currentSnapshot, 'cache');
                }

                // Background validation
                this._validateCacheInBackground();
            } else {
                console.log('❄️ Cold start - requesting full snapshot');
            }

            // Step 2: WebSocket handshake
            this._subscribeToAnalyticsChannel();

            // Step 3: Request bootstrap from server
            this._requestBootstrap(cached);

            // Step 4: Start idle sync loop
            this._startIdleSync();

        } catch (e) {
            console.error('Bootstrap failed:', e);
            if (this.onError) {
                this.onError('bootstrap', e);
            }
        }
    }

    /**
     * Subscribe to /analytics WebSocket namespace
     * @private
     */
    _subscribeToAnalyticsChannel() {
        this.socket.emit('join_workspace', {
            workspace_id: this.workspaceId
        });
        console.log('📡 Subscribed to analytics channel');
    }

    /**
     * Request bootstrap from server
     * @private
     */
    _requestBootstrap(cached) {
        const payload = {
            workspace_id: this.workspaceId,
            days: this.days,
            cached_checksums: cached?.checksums || {},
            last_event_id: this.lastEventId
        };

        this.socket.emit('analytics_bootstrap_request', payload);
        console.log('📨 Bootstrap request sent:', payload);
    }

    /**
     * Validate cache in background (non-blocking)
     * @private
     */
    async _validateCacheInBackground() {
        // Wait for server response to validate
        console.log('🔍 Cache validation queued (awaiting server response)');
    }

    /**
     * Set up WebSocket event handlers
     * @private
     */
    _setupSocketHandlers() {
        // Bootstrap response
        this.socket.on('analytics_bootstrap_response', (data) => {
            this._handleBootstrapResponse(data);
        });

        // Delta updates
        this.socket.on('analytics_delta_apply', (event) => {
            this._handleDeltaUpdate(event);
        });

        // Filter response
        this.socket.on('analytics_filter_response', (data) => {
            this._handleFilterResponse(data);
        });

        // Tab data
        this.socket.on('analytics_tab_data', (data) => {
            this._handleTabData(data);
        });

        // Drift detection
        this.socket.on('analytics_drift_detected', (data) => {
            this._handleDriftDetection(data);
        });

        // Sync OK
        this.socket.on('analytics_sync_ok', (data) => {
            console.log('✅ Background sync OK');
        });

        // Error handling
        this.socket.on('error', (error) => {
            console.error('WebSocket error:', error);
            if (this.onError) {
                this.onError('socket', error);
            }
        });
    }

    /**
     * Handle bootstrap response from server
     * @private
     */
    async _handleBootstrapResponse(data) {
        const syncTime = performance.now();
        console.log('📦 Bootstrap response:', data.status);

        try {
            if (data.status === 'valid') {
                // Cache is valid - no action needed
                console.log('✅ Cache validated - no updates needed');
                this.lastEventId = data.last_event_id;
            } else if (data.status === 'snapshot') {
                // Full snapshot received
                const snapshot = data.snapshot;
                this.currentSnapshot = snapshot;
                this.lastEventId = data.last_event_id;

                // Update cache
                await analyticsCache.set(this.workspaceId, this.days, snapshot);

                // Calculate sync time
                const syncDuration = performance.now() - syncTime;
                this.telemetry.fullSync = syncDuration;
                console.log(`🔄 Full sync completed: ${Math.round(syncDuration)}ms`);

                // Trigger UI update
                if (this.onSnapshotUpdate) {
                    this.onSnapshotUpdate(snapshot, 'server');
                }
            }
        } catch (e) {
            console.error('Bootstrap response handling failed:', e);
        }
    }

    /**
     * Handle real-time delta update
     * @private
     */
    async _handleDeltaUpdate(event) {
        const deltaStart = performance.now();
        console.log('⚡ Delta received:', event.payload.delta);

        try {
            const delta = event.payload.delta;
            
            // Apply delta to cache
            const updated = await analyticsCache.applyDelta(
                this.workspaceId,
                this.days,
                delta
            );

            if (updated) {
                this.currentSnapshot = updated;
                this.lastEventId = event.id;
                
                const deltaTime = performance.now() - deltaStart;
                this.telemetry.deltaCount++;
                
                console.log(`✨ Delta applied: ${Math.round(deltaTime)}ms`);

                // Trigger delta UI update
                if (this.onDeltaUpdate) {
                    this.onDeltaUpdate(delta, updated);
                }
            }
        } catch (e) {
            console.error('Delta apply failed:', e);
        }
    }

    /**
     * Handle filter change response
     * @private
     */
    async _handleFilterResponse(data) {
        console.log('🔍 Filter response received');

        try {
            const snapshot = data.snapshot;
            this.currentSnapshot = snapshot;

            // Update cache with new filters
            await analyticsCache.set(this.workspaceId, this.days, snapshot);

            // Trigger UI update
            if (this.onSnapshotUpdate) {
                this.onSnapshotUpdate(snapshot, 'filter');
            }
        } catch (e) {
            console.error('Filter response handling failed:', e);
        }
    }

    /**
     * Handle tab data response
     * @private
     */
    _handleTabData(data) {
        console.log('📑 Tab data received:', data.tab);

        // Merge tab data into snapshot
        if (this.currentSnapshot) {
            this.currentSnapshot.tabs = this.currentSnapshot.tabs || {};
            this.currentSnapshot.tabs[data.tab] = data.data;

            // Trigger UI update
            if (this.onSnapshotUpdate) {
                this.onSnapshotUpdate(this.currentSnapshot, 'tab');
            }
        }
    }

    /**
     * Handle cache drift detection
     * @private
     */
    async _handleDriftDetection(data) {
        console.warn('⚠️ Cache drift detected - applying delta');
        
        this.telemetry.driftDetections++;
        
        try {
            const delta = data.delta;
            
            // Apply delta to repair cache
            const updated = await analyticsCache.applyDelta(
                this.workspaceId,
                this.days,
                delta
            );

            if (updated) {
                this.currentSnapshot = updated;
                console.log('✅ Cache repaired via delta');

                // Silent UI update (no animation)
                if (this.onSnapshotUpdate) {
                    this.onSnapshotUpdate(updated, 'drift_repair');
                }
            }
        } catch (e) {
            console.error('Drift repair failed:', e);
        }
    }

    /**
     * Start background idle sync (every 30s)
     * @private
     */
    _startIdleSync() {
        // Clear existing interval
        if (this.syncIntervalId) {
            clearInterval(this.syncIntervalId);
        }

        // Start new interval
        this.syncIntervalId = setInterval(() => {
            this._performIdleSync();
        }, 30000); // 30 seconds

        console.log('🔄 Idle sync started (30s interval)');
    }

    /**
     * Perform idle sync validation
     * @private
     */
    async _performIdleSync() {
        try {
            const cached = await analyticsCache.get(this.workspaceId, this.days);
            
            if (!cached) {
                return;
            }

            const payload = {
                workspace_id: this.workspaceId,
                cached_checksums: cached.checksums || {},
                days: this.days
            };

            this.socket.emit('analytics_idle_sync_request', payload);
            console.log('🔍 Idle sync requested');
        } catch (e) {
            console.error('Idle sync failed:', e);
        }
    }

    /**
     * Change date range filter
     */
    changeFilter(days) {
        console.log(`🔍 Changing filter to ${days} days`);
        
        this.days = days;
        
        const payload = {
            workspace_id: this.workspaceId,
            filters: { days },
            user_id: window.currentUserId
        };

        this.socket.emit('analytics_filter_change_request', payload);
    }

    /**
     * Switch to different tab
     */
    switchTab(fromTab, toTab) {
        console.log(`📑 Switching tab: ${fromTab} → ${toTab}`);

        const payload = {
            workspace_id: this.workspaceId,
            from_tab: fromTab,
            to_tab: toTab,
            user_id: window.currentUserId,
            days: this.days
        };

        this.socket.emit('analytics_tab_switch_request', payload);
    }

    /**
     * Get telemetry data
     */
    getTelemetry() {
        return {
            ...this.telemetry,
            calmScore: this._calculateCalmScore()
        };
    }

    /**
     * Calculate CROWN⁵+ calm score
     * @private
     */
    _calculateCalmScore() {
        const scores = [];

        // First paint score
        if (this.telemetry.firstPaint !== null) {
            scores.push(this.telemetry.firstPaint < 200 ? 100 : Math.max(0, 100 - (this.telemetry.firstPaint - 200) / 10));
        }

        // Drift detection penalty
        const driftPenalty = this.telemetry.driftDetections * 5;
        scores.push(Math.max(0, 100 - driftPenalty));

        // Average score
        return scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b) / scores.length) : 0;
    }

    /**
     * Cleanup resources
     */
    destroy() {
        if (this.syncIntervalId) {
            clearInterval(this.syncIntervalId);
        }
        if (this.prefetchController) {
            this.prefetchController.abort();
        }
        console.log('🧹 Lifecycle destroyed');
    }
}
