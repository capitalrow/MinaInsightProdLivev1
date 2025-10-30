/**
 * CROWN⁴.5 Conflict Resolution UI
 * Handles 409 (Conflict) responses with subtle reconciliation indicators.
 * 
 * Features:
 * - Detects vector clock conflicts (409 responses)
 * - Shows subtle "Reconciling..." indicator
 * - Auto-merges non-conflicting changes
 * - Prompts user for conflicting field resolution
 * - Tracks resolution metrics
 */

class ConflictResolutionUI {
    constructor() {
        this.activeConflicts = new Map();
        this.reconciliationIndicator = null;
        this.metrics = {
            totalConflicts: 0,
            autoResolved: 0,
            userResolved: 0,
            failed: 0
        };
        
        this._init();
        console.log('[ConflictResolutionUI] Initialized');
    }

    /**
     * Initialize UI components
     */
    _init() {
        this._createReconciliationIndicator();
        this._setupConflictListeners();
    }

    /**
     * Create reconciliation indicator
     */
    _createReconciliationIndicator() {
        // Check if already exists
        if (document.getElementById('reconciliation-indicator')) {
            this.reconciliationIndicator = document.getElementById('reconciliation-indicator');
            return;
        }

        const indicator = document.createElement('div');
        indicator.id = 'reconciliation-indicator';
        indicator.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9998;
            background: rgba(59, 130, 246, 0.95);
            backdrop-filter: blur(8px);
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            opacity: 0;
            pointer-events: none;
            transition: opacity 300ms ease-out;
            display: flex;
            align-items: center;
            gap: 8px;
        `;

        indicator.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round" 
                 class="reconcile-spinner" style="animation: spin 1s linear infinite;">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
            </svg>
            <span>Reconciling changes...</span>
        `;

        // Add spinner animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(indicator);
        this.reconciliationIndicator = indicator;
    }

    /**
     * Setup conflict event listeners
     */
    _setupConflictListeners() {
        // Listen for 409 conflict events from API/WebSocket
        window.addEventListener('task_conflict_detected', (e) => {
            this.handleConflict(e.detail);
        });

        // Listen for manual sync events
        window.addEventListener('manual_sync_requested', () => {
            this.showReconciliationIndicator();
        });
    }

    /**
     * Handle conflict
     * @param {Object} conflict - Conflict data
     * @returns {Promise<Object>} Resolution result
     */
    async handleConflict(conflict) {
        this.metrics.totalConflicts++;
        
        console.log('[ConflictResolutionUI] Conflict detected:', conflict);
        
        const {
            task_id,
            local_version,
            server_version,
            conflicting_fields,
            event_type
        } = conflict;

        // Store conflict
        this.activeConflicts.set(task_id, conflict);

        // Show reconciliation indicator
        this.showReconciliationIndicator();

        try {
            // Step 1: Attempt auto-resolution
            const autoResolved = await this._attemptAutoResolution(conflict);
            
            if (autoResolved) {
                this.metrics.autoResolved++;
                this.hideReconciliationIndicator();
                this.activeConflicts.delete(task_id);
                
                console.log('[ConflictResolutionUI] Auto-resolved conflict');
                return { success: true, method: 'auto' };
            }

            // Step 2: User resolution required
            const userResolution = await this._promptUserResolution(conflict);
            
            if (userResolution.success) {
                this.metrics.userResolved++;
                this.activeConflicts.delete(task_id);
                
                console.log('[ConflictResolutionUI] User resolved conflict');
                return { success: true, method: 'user', resolution: userResolution };
            }

            // Step 3: Resolution failed
            this.metrics.failed++;
            this.hideReconciliationIndicator();
            
            return { success: false, reason: 'User cancelled or timeout' };

        } catch (error) {
            console.error('[ConflictResolutionUI] Resolution error:', error);
            this.metrics.failed++;
            this.hideReconciliationIndicator();
            
            return { success: false, error: error.message };
        }
    }

    /**
     * Attempt automatic conflict resolution
     * @param {Object} conflict - Conflict data
     * @returns {Promise<boolean>} Success
     */
    async _attemptAutoResolution(conflict) {
        const {
            local_version,
            server_version,
            conflicting_fields
        } = conflict;

        // Auto-resolve if only non-critical fields conflict
        const nonCriticalFields = ['labels', 'description', 'category'];
        const allNonCritical = conflicting_fields.every(field => 
            nonCriticalFields.includes(field)
        );

        if (allNonCritical) {
            // Merge non-critical fields (server wins for simplicity)
            const merged = {
                ...local_version,
                ...server_version
            };

            // Apply merged version
            await this._applyResolution(conflict.task_id, merged, 'auto');
            
            return true;
        }

        // Check for timestamp-based resolution
        if (this._canResolveByTimestamp(conflict)) {
            const winner = this._selectWinnerByTimestamp(conflict);
            await this._applyResolution(conflict.task_id, winner, 'timestamp');
            
            return true;
        }

        return false;
    }

    /**
     * Check if conflict can be resolved by timestamp
     * @param {Object} conflict
     * @returns {boolean}
     */
    _canResolveByTimestamp(conflict) {
        const { local_version, server_version } = conflict;
        return local_version.updated_at && server_version.updated_at;
    }

    /**
     * Select winner by timestamp (last write wins)
     * @param {Object} conflict
     * @returns {Object} Winner version
     */
    _selectWinnerByTimestamp(conflict) {
        const { local_version, server_version } = conflict;
        const localTime = new Date(local_version.updated_at).getTime();
        const serverTime = new Date(server_version.updated_at).getTime();
        
        return localTime > serverTime ? local_version : server_version;
    }

    /**
     * Prompt user for conflict resolution
     * @param {Object} conflict
     * @returns {Promise<Object>} User resolution
     */
    async _promptUserResolution(conflict) {
        const {
            task_id,
            local_version,
            server_version,
            conflicting_fields
        } = conflict;

        return new Promise((resolve) => {
            // Create conflict resolution modal
            const modal = this._createResolutionModal(conflict);
            document.body.appendChild(modal);

            // Show modal
            requestAnimationFrame(() => {
                modal.style.opacity = '1';
            });

            // Handle resolution buttons
            modal.querySelector('.btn-keep-local').addEventListener('click', async () => {
                await this._applyResolution(task_id, local_version, 'user_local');
                modal.remove();
                this.hideReconciliationIndicator();
                resolve({ success: true, choice: 'local' });
            });

            modal.querySelector('.btn-keep-server').addEventListener('click', async () => {
                await this._applyResolution(task_id, server_version, 'user_server');
                modal.remove();
                this.hideReconciliationIndicator();
                resolve({ success: true, choice: 'server' });
            });

            modal.querySelector('.btn-merge').addEventListener('click', async () => {
                const merged = this._createMergedVersion(local_version, server_version, conflicting_fields);
                await this._applyResolution(task_id, merged, 'user_merge');
                modal.remove();
                this.hideReconciliationIndicator();
                resolve({ success: true, choice: 'merge' });
            });

            // Timeout after 30s
            setTimeout(() => {
                if (document.body.contains(modal)) {
                    modal.remove();
                    this.hideReconciliationIndicator();
                    resolve({ success: false, reason: 'timeout' });
                }
            }, 30000);
        });
    }

    /**
     * Create resolution modal
     * @param {Object} conflict
     * @returns {HTMLElement} Modal element
     */
    _createResolutionModal(conflict) {
        const modal = document.createElement('div');
        modal.className = 'conflict-resolution-modal';
        modal.style.cssText = `
            position: fixed;
            inset: 0;
            z-index: 10000;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 300ms ease-out;
        `;

        const { local_version, server_version, conflicting_fields } = conflict;

        modal.innerHTML = `
            <div style="
                background: white;
                border-radius: 12px;
                padding: 24px;
                max-width: 500px;
                width: 90%;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            ">
                <h3 style="margin: 0 0 12px 0; font-size: 18px; font-weight: 600; color: #1f2937;">
                    ⚠️ Conflict Detected
                </h3>
                <p style="margin: 0 0 16px 0; font-size: 14px; color: #6b7280;">
                    This task was modified in multiple places. Please choose which version to keep.
                </p>
                
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 12px; font-weight: 600; color: #9ca3af; margin-bottom: 8px;">
                        Conflicting fields:
                    </div>
                    <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                        ${conflicting_fields.map(field => `
                            <span style="
                                background: #fef3c7;
                                color: #92400e;
                                padding: 4px 8px;
                                border-radius: 4px;
                                font-size: 12px;
                                font-weight: 500;
                            ">${field}</span>
                        `).join('')}
                    </div>
                </div>

                <div style="display: flex; gap: 8px; margin-top: 20px;">
                    <button class="btn-keep-local" style="
                        flex: 1;
                        background: #3b82f6;
                        color: white;
                        border: none;
                        padding: 10px 16px;
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: 500;
                        cursor: pointer;
                    ">Keep My Changes</button>
                    
                    <button class="btn-keep-server" style="
                        flex: 1;
                        background: #6b7280;
                        color: white;
                        border: none;
                        padding: 10px 16px;
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: 500;
                        cursor: pointer;
                    ">Keep Server Version</button>
                    
                    <button class="btn-merge" style="
                        flex: 1;
                        background: #10b981;
                        color: white;
                        border: none;
                        padding: 10px 16px;
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: 500;
                        cursor: pointer;
                    ">Merge Both</button>
                </div>
            </div>
        `;

        return modal;
    }

    /**
     * Create merged version
     * @param {Object} local
     * @param {Object} server
     * @param {Array} conflicting_fields
     * @returns {Object} Merged version
     */
    _createMergedVersion(local, server, conflicting_fields) {
        const merged = { ...server };

        // Merge strategy: combine arrays, keep latest timestamp for scalars
        conflicting_fields.forEach(field => {
            if (Array.isArray(local[field]) && Array.isArray(server[field])) {
                // Merge arrays (union)
                merged[field] = [...new Set([...local[field], ...server[field]])];
            } else if (local.updated_at && server.updated_at) {
                // Use latest version
                const localTime = new Date(local.updated_at).getTime();
                const serverTime = new Date(server.updated_at).getTime();
                merged[field] = localTime > serverTime ? local[field] : server[field];
            }
        });

        return merged;
    }

    /**
     * Apply resolution
     * @param {string} task_id
     * @param {Object} resolved_version
     * @param {string} method
     * @returns {Promise<void>}
     */
    async _applyResolution(task_id, resolved_version, method) {
        // Update cache
        if (window.taskCache) {
            await window.taskCache.updateTask(resolved_version);
        }

        // Update UI
        window.dispatchEvent(new CustomEvent('task_conflict_resolved', {
            detail: {
                task_id,
                resolved_version,
                method
            }
        }));

        console.log(`[ConflictResolutionUI] Conflict resolved via: ${method}`);
    }

    /**
     * Show reconciliation indicator
     */
    showReconciliationIndicator() {
        if (this.reconciliationIndicator) {
            this.reconciliationIndicator.style.opacity = '1';
        }
    }

    /**
     * Hide reconciliation indicator
     */
    hideReconciliationIndicator() {
        if (this.reconciliationIndicator) {
            setTimeout(() => {
                this.reconciliationIndicator.style.opacity = '0';
            }, 500);
        }
    }

    /**
     * Get conflict metrics
     * @returns {Object} Metrics
     */
    getMetrics() {
        return {
            ...this.metrics,
            activeConflicts: this.activeConflicts.size,
            autoResolutionRate: this.metrics.totalConflicts > 0
                ? Math.round((this.metrics.autoResolved / this.metrics.totalConflicts) * 100)
                : 0
        };
    }
}

// Initialize global instance
window.ConflictResolutionUI = ConflictResolutionUI;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.conflictResolutionUI) {
            window.conflictResolutionUI = new ConflictResolutionUI();
            console.log('[ConflictResolutionUI] Global instance created');
        }
    });
}
