/**
 * CROWN⁴.5 Temporal Recovery Engine
 * Detects event drift and reorders events to maintain deterministic state
 * 
 * Features:
 * - Out-of-order event detection via sequence numbers
 * - Event buffering and reordering
 * - Gap detection with server backfill requests
 * - Vector clock comparison for concurrent events
 * - Timeout-based force application to prevent infinite waits
 */

class TemporalRecoveryEngine {
    constructor(taskStore) {
        this.taskStore = taskStore;
        this.eventBuffer = new Map(); // event_id -> event
        this.expectedSequence = null; // Next expected sequence number
        this.lastAppliedSequence = null; // Last successfully applied sequence
        this.gaps = new Set(); // Missing sequence numbers
        this.gapTimers = new Map(); // sequence -> timeout handle
        this.workspaceId = null;
        
        // Configuration
        this.GAP_TIMEOUT_MS = 5000; // Force apply after 5s if gap not filled
        this.MAX_BUFFER_SIZE = 100; // Max buffered events before force flush
        this.BACKFILL_ENABLED = true; // Enable server backfill requests
    }
    
    /**
     * Initialize engine for workspace
     */
    async init(workspaceId, lastEventId = null) {
        this.workspaceId = workspaceId;
        
        // Fetch last applied sequence from server or IndexedDB
        if (lastEventId) {
            const lastEvent = await this._fetchEventMetadata(lastEventId);
            if (lastEvent) {
                this.lastAppliedSequence = lastEvent.workspace_sequence_num;
                this.expectedSequence = this.lastAppliedSequence + 1;
            }
        }
        
        if (this.expectedSequence === null) {
            this.expectedSequence = 1; // Start from 1 for new workspaces
        }
        
        console.log(`🕐 TemporalRecoveryEngine initialized for workspace ${workspaceId}`);
        console.log(`   Expected sequence: ${this.expectedSequence}`);
    }
    
    /**
     * Process incoming event with sequence validation
     * @param {Object} event - Event with sequence metadata
     * @returns {Promise<Object>} - Processing result
     */
    async processEvent(event) {
        const { event_id, workspace_sequence_num, vector_clock, event_type } = event;
        
        if (!workspace_sequence_num) {
            console.warn('⚠️ Event missing sequence number, applying immediately:', event_id);
            return await this._applyEvent(event);
        }
        
        // Check if event is in expected order
        if (workspace_sequence_num === this.expectedSequence) {
            // Perfect order - apply immediately
            await this._applyEvent(event);
            this.lastAppliedSequence = workspace_sequence_num;
            this.expectedSequence++;
            
            // Check buffer for next sequential events
            await this._flushSequentialEvents();
            
            return { status: 'applied', sequence: workspace_sequence_num };
        }
        
        // Out of order event detected
        if (workspace_sequence_num < this.expectedSequence) {
            // Duplicate or already processed
            console.warn(`⚠️ Duplicate event ${event_id} (seq ${workspace_sequence_num} < expected ${this.expectedSequence})`);
            return { status: 'duplicate', sequence: workspace_sequence_num };
        }
        
        // Future event - buffer and detect gaps
        console.warn(`⏰ Out-of-order event ${event_id} (seq ${workspace_sequence_num} > expected ${this.expectedSequence})`);
        this._bufferEvent(event);
        this._detectGaps(workspace_sequence_num);
        
        return { status: 'buffered', sequence: workspace_sequence_num, gap_detected: true };
    }
    
    /**
     * Apply event to task store (authoritative, non-optimistic)
     * @private
     */
    async _applyEvent(event) {
        const { event_type, data } = event;
        
        try {
            // Mark as server-authoritative (actor_rank = 100)
            const authoritativeData = {
                ...data,
                _actor_rank: 100,
                _authoritative: true
            };
            
            switch (event_type) {
                case 'task_create':
                    // Server-confirmed task creation
                    if (data.provisional_id) {
                        await this.taskStore.confirmTask(data.provisional_id, authoritativeData);
                    } else {
                        // Direct server creation (no optimistic)
                        this.taskStore.tasks.set(authoritativeData.id, authoritativeData);
                        await this.taskStore.cache.put(this.taskStore.cache.STORES.TASKS, authoritativeData);
                    }
                    break;
                    
                case 'task_update':
                    // Server-authoritative update (bypass optimistic flag)
                    this.taskStore.tasks.set(authoritativeData.id, authoritativeData);
                    await this.taskStore.cache.put(this.taskStore.cache.STORES.TASKS, authoritativeData);
                    break;
                    
                case 'task_delete':
                    // Server-authoritative delete
                    const deleteData = {
                        ...authoritativeData,
                        deleted_at: authoritativeData.deleted_at || new Date().toISOString()
                    };
                    this.taskStore.tasks.set(deleteData.id, deleteData);
                    await this.taskStore.cache.put(this.taskStore.cache.STORES.TASKS, deleteData);
                    break;
                    
                default:
                    console.warn(`Unknown event type: ${event_type}`);
            }
            
            console.log(`✅ Applied event ${event.event_id} (seq ${event.workspace_sequence_num})`);
        } catch (error) {
            console.error(`❌ Failed to apply event ${event.event_id}:`, error);
            throw error;
        }
    }
    
    /**
     * Buffer out-of-order event
     * @private
     */
    _bufferEvent(event) {
        const { event_id, workspace_sequence_num } = event;
        
        this.eventBuffer.set(event_id, event);
        console.log(`📦 Buffered event ${event_id} (seq ${workspace_sequence_num}), buffer size: ${this.eventBuffer.size}`);
        
        // Force flush if buffer too large
        if (this.eventBuffer.size >= this.MAX_BUFFER_SIZE) {
            console.warn(`⚠️ Buffer size exceeded ${this.MAX_BUFFER_SIZE}, forcing flush`);
            this._forceFlushBuffer();
        }
    }
    
    /**
     * Detect sequence gaps and start timers
     * @private
     */
    _detectGaps(receivedSequence) {
        // Add all missing sequences between expected and received
        for (let seq = this.expectedSequence; seq < receivedSequence; seq++) {
            if (!this.gaps.has(seq)) {
                this.gaps.add(seq);
                console.warn(`⚠️ Gap detected: sequence ${seq} missing`);
                
                // Start timeout timer for this gap
                this._startGapTimer(seq);
            }
        }
        
        // Request backfill if enabled
        if (this.BACKFILL_ENABLED && this.gaps.size > 0) {
            this._requestBackfill(Array.from(this.gaps));
        }
    }
    
    /**
     * Start timeout timer for a gap
     * CROWN⁴.5: Never skip gaps - trigger full resync on timeout
     * @private
     */
    _startGapTimer(sequence) {
        if (this.gapTimers.has(sequence)) {
            return; // Timer already running
        }
        
        const timer = setTimeout(() => {
            console.error(`⏱️ Gap timeout for sequence ${sequence} - triggering full resync`);
            
            // CRITICAL: Do NOT delete gap or call _forceFlushBuffer
            // Unresolved gaps must trigger full resync to maintain ledger integrity
            this._triggerFullResync();
        }, this.GAP_TIMEOUT_MS);
        
        this.gapTimers.set(sequence, timer);
    }
    
    /**
     * Flush sequential events from buffer using vector clock for concurrent ordering
     * @private
     */
    async _flushSequentialEvents() {
        let flushed = 0;
        
        while (true) {
            // Find all events with expected sequence
            const candidates = Array.from(this.eventBuffer.values())
                .filter(e => e.workspace_sequence_num === this.expectedSequence);
            
            if (candidates.length === 0) {
                break; // No sequential event found
            }
            
            // If multiple events with same sequence (concurrent), use vector clock
            let nextEvent;
            if (candidates.length === 1) {
                nextEvent = candidates[0];
            } else {
                console.log(`🔀 ${candidates.length} concurrent events at seq ${this.expectedSequence}, using vector clock`);
                nextEvent = this._selectEventByVectorClock(candidates);
            }
            
            // Apply event
            await this._applyEvent(nextEvent);
            
            // Update tracking
            this.eventBuffer.delete(nextEvent.event_id);
            this.lastAppliedSequence = nextEvent.workspace_sequence_num;
            this.expectedSequence++;
            flushed++;
            
            // Clear gap if filled
            if (this.gaps.has(nextEvent.workspace_sequence_num)) {
                this.gaps.delete(nextEvent.workspace_sequence_num);
                this._clearGapTimer(nextEvent.workspace_sequence_num);
            }
        }
        
        if (flushed > 0) {
            console.log(`🚿 Flushed ${flushed} sequential events from buffer`);
        }
    }
    
    /**
     * Select event from concurrent candidates using vector clock
     * CROWN⁴.5: Deterministic ordering for concurrent events
     * @private
     */
    _selectEventByVectorClock(events) {
        // Sort by vector clock (lexicographic comparison for determinism)
        const sorted = events.sort((a, b) => {
            const aVector = a.vector_clock || '';
            const bVector = b.vector_clock || '';
            
            // Lexicographic comparison
            if (aVector < bVector) return -1;
            if (aVector > bVector) return 1;
            
            // Tie-breaker: event_id (deterministic)
            return a.event_id < b.event_id ? -1 : 1;
        });
        
        return sorted[0];
    }
    
    /**
     * Force flush buffered events ONLY if no gaps remain
     * CROWN⁴.5: Never skip gaps - maintain deterministic ledger integrity
     * @private
     */
    async _forceFlushBuffer() {
        // CRITICAL: Only flush if no gaps remain, otherwise trigger full resync
        if (this.gaps.size > 0) {
            console.error(`❌ Cannot force flush with ${this.gaps.size} unresolved gaps: ${Array.from(this.gaps).join(', ')}`);
            console.error('   Triggering full resync to maintain ledger integrity');
            await this._triggerFullResync();
            return;
        }
        
        console.warn(`⚡ Force flushing ${this.eventBuffer.size} buffered events (no gaps remaining)`);
        
        // Sort events by sequence number, then vector clock
        const sortedEvents = Array.from(this.eventBuffer.values())
            .sort((a, b) => {
                // Primary: sequence number
                if (a.workspace_sequence_num !== b.workspace_sequence_num) {
                    return a.workspace_sequence_num - b.workspace_sequence_num;
                }
                
                // Secondary: vector clock (deterministic)
                const aVector = a.vector_clock || '';
                const bVector = b.vector_clock || '';
                if (aVector !== bVector) {
                    return aVector < bVector ? -1 : 1;
                }
                
                // Tertiary: event_id (deterministic tie-breaker)
                return a.event_id < b.event_id ? -1 : 1;
            });
        
        // Apply all events in deterministic order
        for (const event of sortedEvents) {
            try {
                await this._applyEvent(event);
                this.lastAppliedSequence = event.workspace_sequence_num;
            } catch (error) {
                console.error(`Failed to apply buffered event ${event.event_id}:`, error);
            }
        }
        
        // Update expected sequence to last applied + 1
        this.expectedSequence = this.lastAppliedSequence + 1;
        
        // Clear buffer and gaps
        this.eventBuffer.clear();
        this.gaps.clear();
        this._clearAllGapTimers();
        
        console.log(`✅ Force flush complete, expected sequence now ${this.expectedSequence}`);
    }
    
    /**
     * Trigger full resync when gaps cannot be resolved
     * @private
     */
    async _triggerFullResync() {
        console.warn('🔄 Initiating full resync due to unresolved gaps');
        
        try {
            // Request full state from server
            const response = await fetch(`/api/tasks?workspace_id=${this.workspaceId}&full_state=true`);
            
            if (!response.ok) {
                throw new Error(`Resync failed: ${response.statusText}`);
            }
            
            const { tasks, last_event_id, checksum } = await response.json();
            
            // Sync task store with server state
            await this.taskStore.syncWithServer(tasks, checksum, last_event_id);
            
            // Reset recovery engine state
            const lastEvent = await this._fetchEventMetadata(last_event_id);
            if (lastEvent) {
                this.lastAppliedSequence = lastEvent.workspace_sequence_num;
                this.expectedSequence = this.lastAppliedSequence + 1;
            }
            
            // Clear all buffers and gaps
            this.eventBuffer.clear();
            this.gaps.clear();
            this._clearAllGapTimers();
            
            console.log(`✅ Full resync complete, state synchronized`);
        } catch (error) {
            console.error('❌ Full resync failed:', error);
            // Notify user of sync failure
            if (window.toastManager) {
                window.toastManager.show({
                    type: 'error',
                    message: 'Failed to sync tasks. Please refresh the page.',
                    duration: 0 // Persistent
                });
            }
        }
    }
    
    /**
     * Clear gap timer
     * @private
     */
    _clearGapTimer(sequence) {
        const timer = this.gapTimers.get(sequence);
        if (timer) {
            clearTimeout(timer);
            this.gapTimers.delete(sequence);
        }
    }
    
    /**
     * Clear all gap timers
     * @private
     */
    _clearAllGapTimers() {
        for (const timer of this.gapTimers.values()) {
            clearTimeout(timer);
        }
        this.gapTimers.clear();
    }
    
    /**
     * Request backfill from server for missing events
     * @private
     */
    async _requestBackfill(missingSequences) {
        if (missingSequences.length === 0) {
            return;
        }
        
        console.log(`📡 Requesting backfill for sequences: ${missingSequences.join(', ')}`);
        
        try {
            const response = await fetch(`/api/events/backfill?workspace_id=${this.workspaceId}&sequences=${missingSequences.join(',')}`);
            
            if (!response.ok) {
                console.error('Backfill request failed:', response.statusText);
                return;
            }
            
            const { events } = await response.json();
            console.log(`✅ Received ${events.length} backfill events`);
            
            // Process backfilled events
            for (const event of events) {
                await this.processEvent(event);
            }
        } catch (error) {
            console.error('Backfill request error:', error);
        }
    }
    
    /**
     * Fetch event metadata by ID
     * @private
     */
    async _fetchEventMetadata(eventId) {
        try {
            const response = await fetch(`/api/events/${eventId}/metadata`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Failed to fetch event metadata:', error);
        }
        return null;
    }
    
    /**
     * Get engine status
     */
    getStatus() {
        return {
            workspace_id: this.workspaceId,
            expected_sequence: this.expectedSequence,
            last_applied_sequence: this.lastAppliedSequence,
            buffered_events: this.eventBuffer.size,
            gaps: Array.from(this.gaps),
            gap_count: this.gaps.size
        };
    }
    
    /**
     * Reset engine (for testing or workspace switch)
     */
    reset() {
        this._clearAllGapTimers();
        this.eventBuffer.clear();
        this.gaps.clear();
        this.expectedSequence = null;
        this.lastAppliedSequence = null;
        this.workspaceId = null;
        console.log('🔄 TemporalRecoveryEngine reset');
    }
}

// Initialize global singleton when taskStore is available
window.temporalRecoveryEngine = null;

if (window.taskStore) {
    window.temporalRecoveryEngine = new TemporalRecoveryEngine(window.taskStore);
    console.log('🕐 TemporalRecoveryEngine instance created');
}
