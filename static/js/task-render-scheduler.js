/**
 * CROWN⁴.12 TaskRenderScheduler - Priority-Based Render Queue
 * 
 * Solves the "last-writer-wins" problem by enforcing priority ordering
 * and context validation for all render requests.
 * 
 * Priority Levels (lower = higher priority):
 * 1. user_action - Direct user clicks (tabs, menus)
 * 2. filter_change - User-initiated filter/search
 * 3. optimistic - Optimistic UI updates
 * 4. cache - IndexedDB cache hydration
 * 5. api - HTTP API responses
 * 6. websocket - Real-time WebSocket updates
 */

class TaskRenderScheduler {
    static PRIORITY = {
        user_action: 1,
        filter_change: 2,
        optimistic: 3,
        cache: 4,
        api: 5,
        websocket: 6,
        unknown: 10
    };

    constructor(options = {}) {
        this.onRender = options.onRender || (() => {});
        this.enabled = false;
        this.queue = [];
        this.currentContext = {
            filter: 'active',
            search: '',
            sort: { field: 'created_at', direction: 'desc' }
        };
        this.schedulerVersion = 0;
        this.lastAcceptedVersion = {};
        this.processingQueue = false;
        this.processDebounceTimer = null;
        this.processDebounceMs = 16;
        
        console.log('📋 [RenderScheduler] Initialized');
    }

    enable() {
        this.enabled = true;
        console.log('✅ [RenderScheduler] Enabled - accepting render requests');
        this.processQueue();
    }

    disable() {
        this.enabled = false;
        console.log('🚫 [RenderScheduler] Disabled');
    }

    updateContext(newContext) {
        const changed = 
            this.currentContext.filter !== newContext.filter ||
            this.currentContext.search !== newContext.search ||
            JSON.stringify(this.currentContext.sort) !== JSON.stringify(newContext.sort);
        
        if (changed) {
            this.currentContext = { ...this.currentContext, ...newContext };
            this.schedulerVersion++;
            console.log(`🔄 [RenderScheduler] Context updated (v${this.schedulerVersion}):`, this.currentContext);
            this.pruneStaleRequests();
        }
    }

    getContext() {
        return { ...this.currentContext };
    }

    enqueueRender(request) {
        const {
            tasks,
            source = 'unknown',
            filterContext = this.currentContext.filter,
            searchQuery = this.currentContext.search,
            sortConfig = this.currentContext.sort,
            version = Date.now(),
            fromCache = false,
            isUserAction = false
        } = request;

        const priority = isUserAction 
            ? TaskRenderScheduler.PRIORITY.user_action 
            : (TaskRenderScheduler.PRIORITY[source] || TaskRenderScheduler.PRIORITY.unknown);

        const contextSnapshot = {
            filter: filterContext,
            search: searchQuery,
            sort: sortConfig
        };

        const renderRequest = {
            id: `${source}_${version}`,
            tasks,
            source,
            priority,
            contextSnapshot,
            version,
            fromCache,
            isUserAction,
            enqueuedAt: Date.now(),
            schedulerVersionAtEnqueue: this.schedulerVersion
        };

        if (isUserAction) {
            this.cancelLowerPriorityRequests(priority);
        }

        const existingIndex = this.queue.findIndex(r => r.source === source);
        if (existingIndex >= 0) {
            this.queue[existingIndex] = renderRequest;
            console.log(`🔄 [RenderScheduler] Replaced ${source} request (${tasks?.length || 0} tasks, priority ${priority})`);
        } else {
            this.queue.push(renderRequest);
            console.log(`📥 [RenderScheduler] Enqueued ${source} request (${tasks?.length || 0} tasks, priority ${priority})`);
        }

        this.queue.sort((a, b) => a.priority - b.priority);

        this.scheduleProcessQueue();
    }

    cancelLowerPriorityRequests(thresholdPriority) {
        const before = this.queue.length;
        this.queue = this.queue.filter(r => r.priority <= thresholdPriority);
        const removed = before - this.queue.length;
        if (removed > 0) {
            console.log(`🗑️ [RenderScheduler] Cancelled ${removed} lower-priority requests`);
        }
    }

    pruneStaleRequests() {
        const before = this.queue.length;
        this.queue = this.queue.filter(r => {
            if (r.isUserAction) return true;
            if (r.schedulerVersionAtEnqueue < this.schedulerVersion) {
                console.log(`🗑️ [RenderScheduler] Pruned stale ${r.source} request (version ${r.schedulerVersionAtEnqueue} < ${this.schedulerVersion})`);
                return false;
            }
            return true;
        });
        const removed = before - this.queue.length;
        if (removed > 0) {
            console.log(`🗑️ [RenderScheduler] Pruned ${removed} stale requests after context change`);
        }
    }

    scheduleProcessQueue() {
        if (this.processDebounceTimer) {
            clearTimeout(this.processDebounceTimer);
        }
        this.processDebounceTimer = setTimeout(() => {
            this.processDebounceTimer = null;
            this.processQueue();
        }, this.processDebounceMs);
    }

    processQueue() {
        if (!this.enabled) {
            console.log('⏸️ [RenderScheduler] Not enabled, skipping queue processing');
            return;
        }

        if (this.processingQueue) {
            console.log('🔒 [RenderScheduler] Already processing, will retry');
            this.scheduleProcessQueue();
            return;
        }

        if (this.queue.length === 0) {
            return;
        }

        this.processingQueue = true;

        try {
            const request = this.queue[0];

            if (!this.validateContext(request)) {
                console.log(`❌ [RenderScheduler] Rejected ${request.source} - context mismatch`);
                this.queue.shift();
                this.processingQueue = false;
                this.processQueue();
                return;
            }

            if (!this.validateVersion(request)) {
                console.log(`❌ [RenderScheduler] Rejected ${request.source} - outdated version`);
                this.queue.shift();
                this.processingQueue = false;
                this.processQueue();
                return;
            }

            this.queue.shift();
            this.lastAcceptedVersion[request.source] = request.version;

            console.log(`✅ [RenderScheduler] Executing ${request.source} render (${request.tasks?.length || 0} tasks, priority ${request.priority})`);

            this.onRender(request.tasks, {
                fromCache: request.fromCache,
                source: request.source,
                isSchedulerApproved: true
            });

        } finally {
            this.processingQueue = false;
        }

        if (this.queue.length > 0) {
            this.scheduleProcessQueue();
        }
    }

    validateContext(request) {
        if (request.isUserAction) {
            return true;
        }

        if (request.source === 'filter_change' || request.source === 'user_action') {
            return true;
        }

        const { filter, search } = request.contextSnapshot;
        const currentFilter = this.currentContext.filter;
        const currentSearch = this.currentContext.search;

        if (filter !== currentFilter) {
            console.log(`🔍 [RenderScheduler] Context mismatch: filter ${filter} !== ${currentFilter}`);
            return false;
        }

        if (search !== currentSearch) {
            console.log(`🔍 [RenderScheduler] Context mismatch: search "${search}" !== "${currentSearch}"`);
            return false;
        }

        return true;
    }

    validateVersion(request) {
        if (request.isUserAction) {
            return true;
        }

        const lastVersion = this.lastAcceptedVersion[request.source] || 0;
        if (request.version <= lastVersion) {
            console.log(`🔍 [RenderScheduler] Version outdated: ${request.version} <= ${lastVersion}`);
            return false;
        }

        return true;
    }

    getQueueStatus() {
        return {
            enabled: this.enabled,
            queueLength: this.queue.length,
            currentContext: this.currentContext,
            schedulerVersion: this.schedulerVersion,
            queue: this.queue.map(r => ({
                source: r.source,
                priority: r.priority,
                taskCount: r.tasks?.length || 0,
                age: Date.now() - r.enqueuedAt
            }))
        };
    }

    clearQueue() {
        const count = this.queue.length;
        this.queue = [];
        console.log(`🗑️ [RenderScheduler] Cleared ${count} queued requests`);
    }
}

window.TaskRenderScheduler = TaskRenderScheduler;
