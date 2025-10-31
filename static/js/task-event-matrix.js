/**
 * CROWN⁴.5 Event Matrix Handler
 * 
 * Implements all 20 canonical task events with deterministic sequencing,
 * optimistic UI, and comprehensive telemetry.
 * 
 * Event List:
 * 1. tasks_bootstrap - Initial load
 * 2. tasks_ws_subscribe - WebSocket connection
 * 3. task_nlp:proposed - AI suggestion
 * 4. task_create:manual - Manual creation
 * 5. task_create:nlp_accept - Accept AI suggestion
 * 6. task_update:title - Edit title
 * 7. task_update:status_toggle - Checkbox toggle
 * 8. task_update:priority - Change priority
 * 9. task_update:due - Set due date
 * 10. task_update:assign - Assign user
 * 11. task_update:labels - Modify labels
 * 12. task_snooze - Snooze task
 * 13. task_merge - Merge duplicate
 * 14. task_link:jump_to_span - View in transcript
 * 15. filter_apply - Filter/sort/search
 * 16. tasks_refresh - Pull updates
 * 17. tasks_idle_sync - 30s background sync
 * 18. tasks_offline_queue:replay - Reconnect replay
 * 19. task_delete - Delete task
 * 20. tasks_multiselect:bulk - Bulk operations
 */

class TaskEventMatrix {
    constructor() {
        this.eventHandlers = new Map();
        this.eventStats = {};
        this.store = window.TaskStore;
        this.sequencer = window.TaskEventSequencer;
        this.telemetry = window.CROWNTelemetry;
        
        this.registerAllHandlers();
        console.log('✅ TaskEventMatrix initialized with 20 event handlers');
    }
    
    /**
     * Register all 20 event handlers
     */
    registerAllHandlers() {
        // 1. Bootstrap
        this.register('tasks_bootstrap', this.handleBootstrap.bind(this));
        
        // 2. WebSocket subscribe
        this.register('tasks_ws_subscribe', this.handleWSSubscribe.bind(this));
        
        // 3. NLP Proposed
        this.register('task_nlp:proposed', this.handleNLPProposed.bind(this));
        
        // 4. Manual Create
        this.register('task_create:manual', this.handleCreateManual.bind(this));
        
        // 5. Accept NLP
        this.register('task_create:nlp_accept', this.handleNLPAccept.bind(this));
        
        // 6-11. Updates
        this.register('task_update:title', this.handleUpdateTitle.bind(this));
        this.register('task_update:status_toggle', this.handleStatusToggle.bind(this));
        this.register('task_update:priority', this.handleUpdatePriority.bind(this));
        this.register('task_update:due', this.handleUpdateDue.bind(this));
        this.register('task_update:assign', this.handleUpdateAssign.bind(this));
        this.register('task_update:labels', this.handleUpdateLabels.bind(this));
        
        // 12. Snooze
        this.register('task_snooze', this.handleSnooze.bind(this));
        
        // 13. Merge
        this.register('task_merge', this.handleMerge.bind(this));
        
        // 14. Jump to transcript
        this.register('task_link:jump_to_span', this.handleJumpToTranscript.bind(this));
        
        // 15. Filter
        this.register('filter_apply', this.handleFilterApply.bind(this));
        
        // 16. Refresh
        this.register('tasks_refresh', this.handleRefresh.bind(this));
        
        // 17. Idle sync
        this.register('tasks_idle_sync', this.handleIdleSync.bind(this));
        
        // 18. Offline replay
        this.register('tasks_offline_queue:replay', this.handleOfflineReplay.bind(this));
        
        // 19. Delete
        this.register('task_delete', this.handleDelete.bind(this));
        
        // 20. Bulk operations
        this.register('tasks_multiselect:bulk', this.handleBulkOperation.bind(this));
    }
    
    /**
     * Register event handler
     */
    register(eventType, handler) {
        this.eventHandlers.set(eventType, handler);
        this.eventStats[eventType] = { count: 0, latency: [], errors: 0 };
    }
    
    /**
     * Dispatch event through sequencer
     */
    async dispatch(event) {
        const startTime = performance.now();
        const eventType = event.event_type || event.type;
        
        // Validate sequence
        const validation = this.sequencer.validateAndOrder(event);
        
        if (!validation.accepted) {
            console.warn(`⚠️ Event rejected: ${validation.reason}`, event);
            
            if (validation.shouldReplay) {
                // Request replay of missing events
                this.requestReplay(validation.missingRange);
            }
            
            return { success: false, reason: validation.reason };
        }
        
        // Find handler
        const handler = this.eventHandlers.get(eventType);
        if (!handler) {
            console.warn(`⚠️ No handler for event type: ${eventType}`);
            return { success: false, reason: 'no_handler' };
        }
        
        // Execute handler
        try {
            const result = await handler(event);
            
            // Track metrics
            const latency = performance.now() - startTime;
            this.eventStats[eventType].count++;
            this.eventStats[eventType].latency.push(latency);
            
            // Emit telemetry
            if (this.telemetry) {
                this.telemetry.track(eventType, {
                    latency_ms: latency,
                    success: true,
                    event_id: event.event_id,
                    sequence_num: event.sequence_num
                });
            }
            
            return { success: true, result, latency };
            
        } catch (error) {
            console.error(`❌ Event handler error (${eventType}):`, error);
            this.eventStats[eventType].errors++;
            
            if (this.telemetry) {
                this.telemetry.track(`${eventType}:error`, {
                    error: error.message,
                    event_id: event.event_id
                });
            }
            
            return { success: false, error: error.message };
        }
    }
    
    // ========== Event Handlers ==========
    
    /**
     * 1. Bootstrap - Initial load with cache-first strategy
     */
    async handleBootstrap(event) {
        console.log('🚀 Bootstrap started');
        const tasks = event.payload?.tasks || [];
        await this.store.sync(tasks);
        return { taskCount: tasks.length };
    }
    
    /**
     * 2. WebSocket subscribe
     */
    async handleWSSubscribe(event) {
        console.log('📡 WebSocket subscribed');
        return { connected: true };
    }
    
    /**
     * 3. NLP Proposed - AI suggested task
     */
    async handleNLPProposed(event) {
        const task = event.payload;
        await this.store.upsertTask({
            ...task,
            emotional_state: 'pending_suggest',
            confidence: event.confidence || 0.8
        });
        
        // Emit emotional cue
        this.emitEmotionalCue('curiosity', task.id);
        
        return { taskId: task.id };
    }
    
    /**
     * 4. Manual Create
     */
    async handleCreateManual(event) {
        const task = event.payload;
        await this.store.upsertTask(task);
        
        // Emit emotional cue
        this.emitEmotionalCue('momentum', task.id);
        
        return { taskId: task.id };
    }
    
    /**
     * 5. Accept NLP
     */
    async handleNLPAccept(event) {
        const task = event.payload;
        await this.store.upsertTask({
            ...task,
            emotional_state: 'accepted',
            status: 'todo'
        });
        
        return { taskId: task.id };
    }
    
    /**
     * 6. Update Title
     */
    async handleUpdateTitle(event) {
        const { task_id, title } = event.payload;
        const task = this.store.getTask(task_id);
        if (task) {
            await this.store.upsertTask({ ...task, title });
        }
        return { taskId: task_id };
    }
    
    /**
     * 7. Status Toggle - Most important for satisfaction feedback
     */
    async handleStatusToggle(event) {
        const { task_id, status } = event.payload;
        const task = this.store.getTask(task_id);
        
        if (task) {
            await this.store.upsertTask({
                ...task,
                status,
                completed_at: status === 'completed' ? new Date().toISOString() : null
            });
            
            // Emit emotional cue
            if (status === 'completed') {
                this.emitEmotionalCue('satisfaction', task_id);
            }
        }
        
        return { taskId: task_id, status };
    }
    
    /**
     * 8. Update Priority
     */
    async handleUpdatePriority(event) {
        const { task_id, priority } = event.payload;
        const task = this.store.getTask(task_id);
        if (task) {
            await this.store.upsertTask({ ...task, priority });
        }
        return { taskId: task_id, priority };
    }
    
    /**
     * 9. Update Due Date
     */
    async handleUpdateDue(event) {
        const { task_id, due_date } = event.payload;
        const task = this.store.getTask(task_id);
        if (task) {
            await this.store.upsertTask({ ...task, due_date });
            this.emitEmotionalCue('calm_trust', task_id);
        }
        return { taskId: task_id };
    }
    
    /**
     * 10. Update Assign
     */
    async handleUpdateAssign(event) {
        const { task_id, assigned_to_id } = event.payload;
        const task = this.store.getTask(task_id);
        if (task) {
            await this.store.upsertTask({ ...task, assigned_to_id });
        }
        return { taskId: task_id };
    }
    
    /**
     * 11. Update Labels
     */
    async handleUpdateLabels(event) {
        const { task_id, labels } = event.payload;
        const task = this.store.getTask(task_id);
        if (task) {
            await this.store.upsertTask({ ...task, labels });
        }
        return { taskId: task_id };
    }
    
    /**
     * 12. Snooze
     */
    async handleSnooze(event) {
        const { task_id, snoozed_until } = event.payload;
        const task = this.store.getTask(task_id);
        if (task) {
            await this.store.upsertTask({ ...task, snoozed_until });
            this.emitEmotionalCue('relief', task_id);
        }
        return { taskId: task_id };
    }
    
    /**
     * 13. Merge
     */
    async handleMerge(event) {
        const { target_id, source_id } = event.payload;
        await this.store.removeTask(source_id);
        return { targetId: target_id, sourceId: source_id };
    }
    
    /**
     * 14. Jump to Transcript
     */
    async handleJumpToTranscript(event) {
        const { task_id, transcript_span } = event.payload;
        this.emitEmotionalCue('curiosity', task_id);
        // Navigation handled by UI
        return { taskId: task_id };
    }
    
    /**
     * 15. Filter Apply
     */
    async handleFilterApply(event) {
        const filters = event.payload;
        this.store.setFilters(filters);
        return { filters };
    }
    
    /**
     * 16. Refresh
     */
    async handleRefresh(event) {
        const tasks = event.payload?.tasks || [];
        await this.store.sync(tasks);
        return { taskCount: tasks.length };
    }
    
    /**
     * 17. Idle Sync (30s interval)
     */
    async handleIdleSync(event) {
        const tasks = event.payload?.tasks || [];
        await this.store.sync(tasks, { silent: true });
        return { taskCount: tasks.length };
    }
    
    /**
     * 18. Offline Queue Replay
     */
    async handleOfflineReplay(event) {
        const events = event.payload?.events || [];
        for (const evt of events) {
            await this.dispatch(evt);
        }
        return { replayed: events.length };
    }
    
    /**
     * 19. Delete
     */
    async handleDelete(event) {
        const { task_id } = event.payload;
        await this.store.removeTask(task_id);
        return { taskId: task_id };
    }
    
    /**
     * 20. Bulk Operations
     */
    async handleBulkOperation(event) {
        const { action, task_ids } = event.payload;
        
        if (action === 'bulk_complete') {
            for (const taskId of task_ids) {
                const task = this.store.getTask(taskId);
                if (task) {
                    await this.store.upsertTask({
                        ...task,
                        status: 'completed',
                        completed_at: new Date().toISOString()
                    }, { skipPersist: true });
                }
            }
            await this.store.saveToCache(this.store.tasks);
        } else if (action === 'bulk_delete') {
            for (const taskId of task_ids) {
                this.store.tasksById.delete(taskId);
            }
            this.store.tasks = this.store.tasks.filter(t => !task_ids.includes(t.id));
            await this.store.saveToCache(this.store.tasks);
        }
        
        return { action, count: task_ids.length };
    }
    
    // ========== Helpers ==========
    
    /**
     * Emit emotional cue for animations
     */
    emitEmotionalCue(emotion, taskId) {
        window.dispatchEvent(new CustomEvent('task:emotion', {
            detail: { emotion, taskId, timestamp: Date.now() }
        }));
    }
    
    /**
     * Request replay of missing events
     */
    requestReplay(range) {
        console.log(`📼 Requesting replay: ${range.start}-${range.end}`);
        // Emit to WebSocket manager
        window.dispatchEvent(new CustomEvent('tasks:request_replay', {
            detail: range
        }));
    }
    
    /**
     * Get event statistics
     */
    getStats() {
        const stats = {};
        for (const [type, data] of Object.entries(this.eventStats)) {
            const latencies = data.latency;
            stats[type] = {
                count: data.count,
                errors: data.errors,
                avgLatency: latencies.length > 0
                    ? latencies.reduce((a, b) => a + b, 0) / latencies.length
                    : 0,
                p95Latency: latencies.length > 0
                    ? latencies.sort((a, b) => a - b)[Math.floor(latencies.length * 0.95)]
                    : 0
            };
        }
        return stats;
    }
}

// Global instance
window.TaskEventMatrix = new TaskEventMatrix();

console.log('✅ CROWN⁴.5 Event Matrix loaded (20 events)');
