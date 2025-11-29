/**
 * CROWN⁴.6 Mina Tasks - Linear-Inspired Performance & Animations
 * 
 * Design Philosophy:
 * - Load in <200ms with instant perceived performance
 * - Optimistic UI: Actions respond immediately, sync in background
 * - FLIP animations: Smooth, natural motion that guides attention
 * - Prefetch next actions: Always one step ahead
 * - No spinners: Skeleton loaders → content in one smooth transition
 * 
 * Inspired by Linear's "ink flows" animation philosophy
 */

class MinaTasksLinear {
    constructor() {
        this.tasks = [];
        this.loadStartTime = performance.now();
        this.socket = null;
        this.prefetchCache = new Map();
        this.pendingOptimisticActions = new Map();
        this.animationQueue = [];
        
        // Performance targets
        this.PERFORMANCE_TARGET_MS = 200;
        this.ANIMATION_DURATION = 220; // Slightly longer for smoothness
        this.PREFETCH_DELAY = 150;
        
        // State management
        this.isOnline = navigator.onLine;
        this.filter = 'all';
        this.sortBy = 'default';
        
        this.init();
    }
    
    async init() {
        console.log('[Mina Tasks] Initializing Linear-inspired interface...');
        
        // CROWN⁴.6: Skeleton is now visible by default in HTML
        // No need to call showSkeletonLoader() - prevents double flash
        // TaskBootstrap handles initial loading state
        
        // Phase 2: Load tasks with aggressive caching
        const tasksPromise = this.loadTasksOptimized();
        
        // Phase 3: Setup interactions (parallel)
        this.setupEventListeners();
        this.setupWebSocket();
        this.setupPrefetching();
        this.setupOfflineDetection();
        
        // Phase 4: Wait for tasks, then animate in
        const tasks = await tasksPromise;
        this.tasks = tasks;
        
        // Update window.tasks for downstream scripts (provenance, emotional UI)
        if (typeof window !== 'undefined') {
            window.tasks = tasks;
        }
        
        // Render with FLIP animation
        this.renderTasksWithFLIP(tasks);
        
        // Performance logging
        const loadTime = performance.now() - this.loadStartTime;
        console.log(`[Mina Tasks] Loaded in ${loadTime.toFixed(2)}ms (target: <${this.PERFORMANCE_TARGET_MS}ms)`);
        
        if (loadTime > this.PERFORMANCE_TARGET_MS) {
            console.warn(`[Performance] Load time exceeded target by ${(loadTime - this.PERFORMANCE_TARGET_MS).toFixed(2)}ms`);
        }
        
        // Start prefetching related data
        this.prefetchRelatedData();
    }
    
    /**
     * Show skeleton loader instantly (0ms perceived load time)
     * CROWN⁴.6: Now defers to TaskBootstrap for state management
     * Skeleton is visible by default in HTML - no action needed
     */
    showSkeletonLoader() {
        // CROWN⁴.6: Skeleton is visible by default in HTML
        // TaskBootstrap manages the state transitions
        // This method kept for backwards compatibility but is now a no-op
        console.log('[Linear] Skeleton already visible by default');
    }
    
    /**
     * Load tasks with optimized strategy:
     * 1. Check cache first (instant)
     * 2. Fetch with minimal payload
     * 3. Use ETags to avoid unnecessary transfers
     */
    async loadTasksOptimized() {
        const cacheKey = 'mina_tasks_v1';
        
        // Try cache first (instant)
        const cached = this.getFromCache(cacheKey);
        if (cached && (Date.now() - cached.timestamp < 30000)) {
            console.log('[Cache] Using cached tasks (fresh)');
            // Still fetch in background to update
            this.fetchTasksInBackground(cacheKey);
            return cached.data;
        }
        
        // Fetch fresh data
        try {
            const response = await fetch('/api/tasks/?per_page=100', {
                headers: {
                    'Accept': 'application/json',
                    'Cache-Control': 'max-age=10'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            const tasks = data.tasks || [];
            
            // Cache for next time
            this.setCache(cacheKey, tasks);
            
            return tasks;
        } catch (error) {
            console.error('[API] Failed to load tasks:', error);
            
            // Fallback to stale cache if available
            if (cached) {
                console.log('[Cache] Using stale cached tasks as fallback');
                return cached.data;
            }
            
            return [];
        }
    }
    
    /**
     * Background fetch to update cache without blocking UI
     */
    async fetchTasksInBackground(cacheKey) {
        try {
            const response = await fetch('/api/tasks/?per_page=100');
            const data = await response.json();
            const tasks = data.tasks || [];
            this.setCache(cacheKey, tasks);
            
            // If tasks changed, update UI smoothly
            if (JSON.stringify(tasks) !== JSON.stringify(this.tasks)) {
                this.updateTasksSmooth(tasks);
            }
        } catch (error) {
            console.log('[Background fetch] Failed silently:', error.message);
        }
    }
    
    /**
     * Smoothly update tasks when data changes (WebSocket, filter, background sync)
     * Uses keyed diff-based DOM reconciliation with FLIP animations
     * Per architect guidance: preserve listeners, reorder via insertBefore, <200ms target
     */
    async updateTasksSmooth(newTasks) {
        const container = document.getElementById('tasks-list-container');
        if (!container) return;
        
        // Update internal state
        const oldTasks = this.tasks;
        this.tasks = newTasks;
        
        // Update window.tasks for downstream scripts
        if (typeof window !== 'undefined') {
            window.tasks = newTasks;
        }
        
        const startTime = performance.now();
        
        // Build id→element map from current DOM (keyed diff)
        const existingCards = Array.from(container.querySelectorAll('.task-card'));
        const cardMap = new Map();
        existingCards.forEach(card => {
            const taskId = parseInt(card.dataset.taskId);
            cardMap.set(taskId, card);
        });
        
        // FLIP Phase 1: Capture FIRST positions before mutations
        const firstPositions = new Map();
        existingCards.forEach(card => {
            const rect = card.getBoundingClientRect();
            firstPositions.set(card, { top: rect.top, left: rect.left });
        });
        
        // DOM Reconciliation: walk newTasks in order, reposition out-of-place nodes
        const nodesToAnimate = [];
        const newTaskFragments = []; // Track new tasks for batch fragment fetch
        
        for (let i = 0; i < newTasks.length; i++) {
            const task = newTasks[i];
            const existingCard = cardMap.get(task.id);
            
            if (existingCard) {
                // Reuse existing node (preserves event listeners)
                // Update content if changed
                this.patchTaskCard(existingCard, task);
                
                // Check if node is already in correct position
                const currentNodeAtPosition = container.children[i];
                
                if (existingCard !== currentNodeAtPosition) {
                    // Out of place - move it using insertBefore (preserves listeners)
                    const referenceNode = container.children[i] || null;
                    container.insertBefore(existingCard, referenceNode);
                    nodesToAnimate.push(existingCard);
                }
                
                cardMap.delete(task.id); // Mark as processed
            } else {
                // New task - needs server-rendered fragment
                newTaskFragments.push({ task, index: i });
            }
        }
        
        // Handle new task insertions via fragment hydration
        if (newTaskFragments.length > 0) {
            try {
                // Fetch and insert fragments for all new tasks
                const hydratedCount = await this.hydrateNewTasks(newTaskFragments, container);
                
                if (hydratedCount === 0) {
                    // All fragments failed - fall back to reload
                    console.warn(`[Smooth Update] Fragment hydration failed for all ${newTaskFragments.length} tasks - reloading`);
                    setTimeout(() => window.location.reload(), 100);
                    return;
                }
                
                // Re-run reconciliation after hydration (tasks now exist in DOM)
                console.log(`[Smooth Update] Hydrated ${hydratedCount}/${newTaskFragments.length} tasks - re-running reconciliation`);
                return await this.updateTasksSmooth(newTasks);
            } catch (error) {
                console.error(`[Smooth Update] Fragment hydration error:`, error);
                // Fall back to reload on error
                setTimeout(() => window.location.reload(), 100);
                return;
            }
        }
        
        // Remove tasks that no longer exist (remaining in cardMap)
        // Let them animate out gracefully in situ - no container clearing
        cardMap.forEach((card, taskId) => {
            card.style.transition = 'opacity 200ms ease-out, transform 200ms ease-out';
            card.style.opacity = '0';
            card.style.transform = 'translateX(-20px)';
            setTimeout(() => {
                if (card.parentNode) {
                    card.parentNode.removeChild(card);
                }
            }, 200);
        });
        
        // FLIP Phase 2: Capture LAST positions after mutations
        const lastPositions = new Map();
        nodesToAnimate.forEach(card => {
            const rect = card.getBoundingClientRect();
            lastPositions.set(card, { top: rect.top, left: rect.left });
        });
        
        // FLIP Phase 3 & 4: Invert and Play animations
        nodesToAnimate.forEach((card, index) => {
            const first = firstPositions.get(card);
            const last = lastPositions.get(card);
            
            if (first && last) {
                // Calculate delta (invert)
                const deltaY = first.top - last.top;
                const deltaX = first.left - last.left;
                
                // Set initial transform (pre-animation)
                card.style.transform = `translate(${deltaX}px, ${deltaY}px)`;
                card.style.transition = 'none';
                
                // Animate to final position (play)
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        card.style.transition = `transform ${this.ANIMATION_DURATION}ms cubic-bezier(0.4, 0, 0.2, 1)`;
                        card.style.transitionDelay = `${index * 12}ms`; // Stagger for "ink flow"
                        card.style.transform = 'translate(0, 0)';
                    });
                });
            }
        });
        
        // Trigger reapply of emotional UI and provenance after layout settles
        requestAnimationFrame(() => {
            if (window.emotionalUI) {
                window.emotionalUI.reapplyEmotionalCues();
            }
            if (window.spokenProvenanceUI) {
                window.spokenProvenanceUI.reapplyProvenance();
            }
        });
        
        const updateTime = performance.now() - startTime;
        console.log(`[Smooth Update] Reconciled ${newTasks.length} tasks with FLIP in ${updateTime.toFixed(2)}ms`);
        
        if (updateTime > 200) {
            console.warn(`[Performance] Update exceeded 200ms target: ${updateTime.toFixed(2)}ms`);
        }
    }
    
    /**
     * Hydrate new task cards by fetching server-rendered HTML fragments
     * CROWN⁴.6: Fragment-based hydration for optimistic inserts
     * Returns: Number of successfully hydrated tasks
     */
    async hydrateNewTasks(newTaskFragments, container) {
        const fetchPromises = newTaskFragments.map(({ task }) => 
            fetch(`/api/tasks/${task.id}/html`)
                .then(res => {
                    if (!res.ok) {
                        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
                    }
                    return res.json();
                })
                .then(data => {
                    if (data.success && data.html) {
                        return { taskId: task.id, html: data.html };
                    }
                    throw new Error(`Server returned failure for task ${task.id}`);
                })
                .catch(error => {
                    console.error(`[Fragment Hydration] Failed for task ${task.id}:`, error.message);
                    return null;
                })
        );
        
        const fragments = await Promise.all(fetchPromises);
        let successCount = 0;
        
        // Insert HTML fragments into DOM
        fragments.forEach((fragment, idx) => {
            if (!fragment) return;
            
            const { taskId, html } = fragment;
            const { index } = newTaskFragments[idx];
            
            try {
                // Create temporary container to parse HTML
                const temp = document.createElement('div');
                temp.innerHTML = html;
                const newCard = temp.firstElementChild;
                
                if (!newCard) {
                    console.error(`[Fragment Hydration] No card element in HTML for task ${taskId}`);
                    return;
                }
                
                // Insert at correct position
                const referenceNode = container.children[index] || null;
                container.insertBefore(newCard, referenceNode);
                
                // Add fade-in animation for new card
                newCard.style.opacity = '0';
                newCard.style.transform = 'translateY(10px)';
                
                requestAnimationFrame(() => {
                    newCard.style.transition = 'opacity 300ms ease-out, transform 300ms ease-out';
                    newCard.style.opacity = '1';
                    newCard.style.transform = 'translateY(0)';
                });
                
                successCount++;
                console.log(`[Fragment Hydration] Inserted task ${taskId} at position ${index}`);
            } catch (error) {
                console.error(`[Fragment Hydration] DOM insertion failed for task ${taskId}:`, error);
            }
        });
        
        return successCount;
    }
    
    /**
     * Patch task card content in-place (preserves event listeners)
     */
    patchTaskCard(card, task) {
        // Update title if changed
        const titleEl = card.querySelector('.task-title');
        if (titleEl && titleEl.textContent !== task.title) {
            titleEl.textContent = task.title;
        }
        
        // Update status/completion
        const checkbox = card.querySelector('.task-checkbox');
        const isCompleted = task.status === 'completed';
        if (checkbox && checkbox.checked !== isCompleted) {
            checkbox.checked = isCompleted;
            if (isCompleted) {
                card.classList.add('completed');
            } else {
                card.classList.remove('completed');
            }
        }
        
        // Update priority
        const newPriority = task.priority || 'medium';
        if (card.dataset.priority !== newPriority) {
            card.className = card.className.replace(/task-priority-\w+/, `task-priority-${newPriority}`);
            card.dataset.priority = newPriority;
            
            const priorityBadge = card.querySelector('.priority-badge');
            if (priorityBadge) {
                priorityBadge.className = `priority-badge priority-${newPriority}`;
                priorityBadge.textContent = newPriority;
            }
        }
    }
    
    /**
     * FLIP Animation: First, Last, Invert, Play
     * Smooth, natural movement that guides user's attention
     * Inspired by Linear's "ink flows" aesthetic
     * CROWN⁴.6: Coordinates with TaskBootstrap for state management
     */
    renderTasksWithFLIP(tasks) {
        const container = document.getElementById('tasks-list-container');
        const loadingState = document.getElementById('tasks-loading-state');
        const emptyState = document.getElementById('tasks-empty-state');
        
        if (!container) return;
        
        // CROWN⁴.6: Use TaskBootstrap's state management if available
        // This ensures consistent state transitions across modules
        if (window.taskBootstrap && typeof window.taskBootstrap.showTasksList === 'function') {
            window.taskBootstrap.showTasksList();
        } else {
            // Fallback: Hide skeleton loader directly
            if (loadingState) {
                loadingState.style.display = 'none';
            }
        }
        
        // CRITICAL FIX: Don't replace server-rendered DOM - hydrate it!
        // Server already rendered task cards with all event listeners attached
        const existingCards = Array.from(container.querySelectorAll('.task-card'));
        
        if (existingCards.length === 0 && tasks.length === 0) {
            container.classList.add('hidden');
            if (emptyState) emptyState.classList.remove('hidden');
            return;
        }
        
        if (emptyState) emptyState.classList.add('hidden');
        container.classList.remove('hidden');
        
        // Server rendered tasks - just animate them in smoothly
        // NEVER replace innerHTML - always hydrate from server DOM
        existingCards.forEach((card, i) => {
            // Start invisible and slightly offset
            card.style.opacity = '0';
            card.style.transform = 'translateY(-4px)';
            
            // Stagger animation for smooth cascade
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    card.style.transition = `all ${this.ANIMATION_DURATION}ms cubic-bezier(0.4, 0, 0.2, 1)`;
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                    card.style.transitionDelay = `${i * 25}ms`;
                });
            });
        });
        
        console.log(`[Linear Load] Hydrated ${existingCards.length} server-rendered tasks`);
    }
    
    /**
     * Render individual task card with all metadata
     */
    renderTaskCard(task, index) {
        const isCompleted = task.status === 'completed';
        const priority = task.priority || 'medium';
        const hasTranscript = task.transcript_span && task.transcript_span.start_ms != null;
        
        // Format due date
        let dueDateBadge = '';
        if (task.due_date) {
            const dueDate = new Date(task.due_date);
            const today = new Date();
            const isOverdue = dueDate < today && !isCompleted;
            const isDueSoon = !isOverdue && (dueDate - today) / (1000 * 60 * 60 * 24) <= 3;
            
            dueDateBadge = `
                <span class="due-date-badge ${isOverdue ? 'overdue' : isDueSoon ? 'due-soon' : ''}">
                    <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM7 10h5v5H7z"/>
                    </svg>
                    ${dueDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    ${isOverdue ? '<span class="overdue-badge">OVERDUE</span>' : ''}
                </span>
            `;
        }
        
        // Assignees
        let assigneeBadge = '';
        if (task.assignee_ids && task.assignee_ids.length > 0) {
            assigneeBadge = `
                <span class="task-assignees" data-assignee-count="${task.assignee_ids.length}">
                    <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                    </svg>
                    <span class="assignee-names">
                        ${task.assignee_ids.length === 1 ? 'Assigned' : `${task.assignee_ids.length} people`}
                    </span>
                </span>
            `;
        } else {
            assigneeBadge = `
                <span class="task-assignees task-assignees-empty" title="Click to assign">
                    <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                    </svg>
                    Unassigned
                </span>
            `;
        }
        
        // Labels
        let labelsBadge = '';
        if (task.labels && task.labels.length > 0) {
            labelsBadge = task.labels.map(label => 
                `<span class="task-label">${this.escapeHtml(label)}</span>`
            ).join('');
        }
        
        // Jump to transcript button
        let transcriptBtn = '';
        if (hasTranscript) {
            transcriptBtn = `
                <button class="jump-to-transcript-btn" 
                        data-task-id="${task.id}"
                        data-meeting-id="${task.meeting_id}"
                        title="Jump to moment in transcript">
                    <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                    </svg>
                    <span>View in Transcript</span>
                </button>
            `;
        }
        
        return `
            <div class="task-card ${isCompleted ? 'completed' : ''} task-priority-${priority}"
                 data-task-id="${task.id}"
                 data-status="${task.status}"
                 data-priority="${priority}"
                 style="--animation-index: ${index}">
                <div class="checkbox-wrapper">
                    <input type="checkbox" 
                           class="task-checkbox" 
                           ${isCompleted ? 'checked' : ''}
                           data-task-id="${task.id}"
                           aria-label="Mark task as ${isCompleted ? 'incomplete' : 'complete'}">
                </div>
                <div class="task-content">
                    <h3 class="task-title" data-task-id="${task.id}" contenteditable="false">
                        ${this.escapeHtml(task.title)}
                    </h3>
                    ${task.description ? `<p class="task-description">${this.escapeHtml(task.description)}</p>` : ''}
                    <div class="task-metadata">
                        ${assigneeBadge}
                        ${dueDateBadge}
                        ${labelsBadge}
                        ${transcriptBtn}
                    </div>
                </div>
                <div class="task-actions">
                    <span class="priority-badge priority-${priority}">
                        ${priority}
                    </span>
                    <button class="task-menu-trigger" 
                            data-task-id="${task.id}"
                            aria-label="Task actions">
                        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                            <circle cx="12" cy="5" r="2"/>
                            <circle cx="12" cy="12" r="2"/>
                            <circle cx="12" cy="19" r="2"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
    }
    
    /**
     * Optimistic UI: Update immediately, sync in background
     * If sync fails, rollback with smooth animation
     */
    async toggleTaskOptimistic(taskId, currentChecked) {
        const newChecked = !currentChecked;
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        const checkbox = card?.querySelector('.task-checkbox');
        
        if (!checkbox || !card) return;
        
        // Generate optimistic action ID
        const actionId = `toggle_${taskId}_${Date.now()}`;
        
        // Store original state for potential rollback
        this.pendingOptimisticActions.set(actionId, {
            taskId,
            action: 'toggle',
            originalState: currentChecked,
            element: card
        });
        
        // Update UI immediately (optimistic)
        checkbox.checked = newChecked;
        
        if (newChecked) {
            // Completion animation: burst effect
            this.playCompletionAnimation(card);
            card.classList.add('completed');
        } else {
            card.classList.remove('completed');
        }
        
        // Sync to server in background
        try {
            const response = await fetch(`/api/tasks/${taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    status: newChecked ? 'completed' : 'todo'
                })
            });
            
            if (!response.ok) {
                throw new Error('Server rejected update');
            }
            
            // Success: remove from pending
            this.pendingOptimisticActions.delete(actionId);
            
            // Update local task state
            const task = this.tasks.find(t => t.id === taskId);
            if (task) {
                task.status = newChecked ? 'completed' : 'todo';
            }
            
        } catch (error) {
            console.error('[Optimistic] Failed to sync, rolling back:', error);
            
            // Rollback with smooth animation
            checkbox.checked = currentChecked;
            if (currentChecked) {
                card.classList.add('completed');
            } else {
                card.classList.remove('completed');
            }
            
            this.pendingOptimisticActions.delete(actionId);
            
            // Show toast notification
            this.showToast('Failed to update task. Please try again.', 'error');
        }
    }
    
    /**
     * Completion animation: Burst effect inspired by Things 3
     */
    playCompletionAnimation(card) {
        // Add burst particle effect
        const rect = card.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        // Create burst particles
        for (let i = 0; i < 8; i++) {
            const particle = document.createElement('div');
            particle.className = 'completion-particle';
            particle.style.cssText = `
                position: fixed;
                left: ${centerX}px;
                top: ${centerY}px;
                width: 4px;
                height: 4px;
                border-radius: 50%;
                background: linear-gradient(135deg, #6366f1, #8b5cf6);
                pointer-events: none;
                z-index: 9999;
            `;
            
            document.body.appendChild(particle);
            
            // Animate particle
            const angle = (i / 8) * Math.PI * 2;
            const distance = 60;
            const tx = Math.cos(angle) * distance;
            const ty = Math.sin(angle) * distance;
            
            particle.animate([
                { transform: 'translate(0, 0) scale(1)', opacity: 1 },
                { transform: `translate(${tx}px, ${ty}px) scale(0)`, opacity: 0 }
            ], {
                duration: 600,
                easing: 'cubic-bezier(0.4, 0, 0.2, 1)'
            }).onfinish = () => particle.remove();
        }
        
        // Card subtle pulse
        card.animate([
            { transform: 'scale(1)' },
            { transform: 'scale(1.02)' },
            { transform: 'scale(1)' }
        ], {
            duration: 220,
            easing: 'cubic-bezier(0.4, 0, 0.2, 1)'
        });
    }
    
    /**
     * Prefetch related data to stay ahead of user actions
     */
    async prefetchRelatedData() {
        // Wait a bit for initial interactions
        await this.sleep(this.PREFETCH_DELAY);
        
        // Prefetch meeting heatmap data
        this.prefetchMeetingHeatmap();
        
        // Prefetch task transcript contexts for top 5 tasks
        this.prefetchTranscriptContexts();
    }
    
    async prefetchMeetingHeatmap() {
        try {
            const response = await fetch('/api/tasks/meeting-heatmap');
            const data = await response.json();
            this.prefetchCache.set('meeting_heatmap', {
                data: data.meetings || [],
                timestamp: Date.now()
            });
            console.log('[Prefetch] Meeting heatmap cached');
        } catch (error) {
            console.log('[Prefetch] Meeting heatmap failed:', error.message);
        }
    }
    
    async prefetchTranscriptContexts() {
        const tasksWithTranscript = this.tasks
            .filter(t => t.transcript_span && t.transcript_span.start_ms != null)
            .slice(0, 5);
        
        for (const task of tasksWithTranscript) {
            try {
                const response = await fetch(`/api/tasks/${task.id}/transcript-context`);
                const data = await response.json();
                this.prefetchCache.set(`transcript_${task.id}`, {
                    data: data.context,
                    timestamp: Date.now()
                });
            } catch (error) {
                console.log(`[Prefetch] Transcript context for task ${task.id} failed`);
            }
        }
        
        console.log(`[Prefetch] ${tasksWithTranscript.length} transcript contexts cached`);
    }
    
    /**
     * Setup event listeners with optimistic UI
     */
    setupTaskInteractions() {
        const container = document.getElementById('tasks-list-container');
        if (!container) return;
        
        // Checkbox toggle (optimistic)
        container.addEventListener('change', (e) => {
            if (e.target.classList.contains('task-checkbox')) {
                const taskId = parseInt(e.target.dataset.taskId);
                const checked = e.target.checked;
                this.toggleTaskOptimistic(taskId, !checked);
            }
        });
        
        // Title inline edit
        container.addEventListener('click', (e) => {
            if (e.target.classList.contains('task-title')) {
                this.enableInlineEdit(e.target);
            }
        });
        
        // Jump to transcript
        container.addEventListener('click', (e) => {
            const btn = e.target.closest('.jump-to-transcript-btn');
            if (btn) {
                const taskId = parseInt(btn.dataset.taskId);
                const meetingId = parseInt(btn.dataset.meetingId);
                this.jumpToTranscript(taskId, meetingId);
            }
        });
    }
    
    /**
     * Enable inline editing with smooth transition
     */
    enableInlineEdit(titleElement) {
        if (titleElement.contentEditable === 'true') return;
        
        const originalText = titleElement.textContent.trim();
        titleElement.contentEditable = 'true';
        titleElement.focus();
        
        // Select all text
        const range = document.createRange();
        range.selectNodeContents(titleElement);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        
        // Add editing visual feedback
        titleElement.classList.add('editing');
        
        const saveEdit = async () => {
            const newText = titleElement.textContent.trim();
            titleElement.contentEditable = 'false';
            titleElement.classList.remove('editing');
            
            if (newText && newText !== originalText) {
                const taskId = parseInt(titleElement.dataset.taskId);
                await this.updateTaskTitle(taskId, newText, originalText, titleElement);
            } else {
                titleElement.textContent = originalText;
            }
        };
        
        const cancelEdit = () => {
            titleElement.contentEditable = 'false';
            titleElement.classList.remove('editing');
            titleElement.textContent = originalText;
        };
        
        // Save on blur or Enter
        titleElement.addEventListener('blur', saveEdit, { once: true });
        titleElement.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveEdit();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelEdit();
            }
        }, { once: true });
    }
    
    /**
     * Update task title with optimistic UI
     */
    async updateTaskTitle(taskId, newTitle, originalTitle, element) {
        // Optimistic update already applied via contentEditable
        
        try {
            const response = await fetch(`/api/tasks/${taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ title: newTitle })
            });
            
            if (!response.ok) {
                throw new Error('Server rejected update');
            }
            
            // Update local state
            const task = this.tasks.find(t => t.id === taskId);
            if (task) {
                task.title = newTitle;
            }
            
            this.showToast('Task updated', 'success');
            
        } catch (error) {
            console.error('[Update] Failed to update title:', error);
            element.textContent = originalTitle;
            this.showToast('Failed to update task title', 'error');
        }
    }
    
    /**
     * Jump to transcript moment
     */
    async jumpToTranscript(taskId, meetingId) {
        // Check prefetch cache first
        const cacheKey = `transcript_${taskId}`;
        const cached = this.prefetchCache.get(cacheKey);
        
        if (cached) {
            console.log('[Prefetch] Using cached transcript context');
            this.showTranscriptModal(cached.data);
        } else {
            // Fetch and show
            try {
                const response = await fetch(`/api/tasks/${taskId}/transcript-context`);
                const data = await response.json();
                this.showTranscriptModal(data.context);
            } catch (error) {
                console.error('[Transcript] Failed to fetch context:', error);
                this.showToast('Failed to load transcript context', 'error');
            }
        }
    }
    
    /**
     * Show transcript context modal
     */
    showTranscriptModal(context) {
        // TODO: Implement modal UI
        console.log('[Transcript Context]', context);
        alert(`Jump to: ${context.quote}\nSpeaker: ${context.speaker}`);
    }
    
    /**
     * Setup WebSocket for real-time updates
     */
    setupWebSocket() {
        if (!window.wsManager) {
            console.error('[WebSocket] WebSocketManager not available');
            return;
        }
        
        if (!window.WORKSPACE_ID) {
            console.error('[WebSocket] WORKSPACE_ID not available');
            return;
        }
        
        // Initialize WebSocketManager for /tasks namespace
        console.log('[WebSocket] Initializing connection...');
        window.wsManager.init(window.WORKSPACE_ID, ['tasks']);
        
        console.log('[WebSocket] ✅ Connected to /tasks namespace');
    }
    
    /**
     * Setup offline detection
     */
    setupOfflineDetection() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.syncPendingActions();
            this.hideOfflineBanner();
        });
        
        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.showOfflineBanner();
        });
    }
    
    /**
     * Show offline banner with cloud icon
     */
    showOfflineBanner() {
        const banner = document.getElementById('connection-banner');
        if (banner) {
            banner.classList.remove('hidden', 'online');
            banner.classList.add('offline');
            banner.querySelector('.connection-message').textContent = 'Working offline';
        }
    }
    
    hideOfflineBanner() {
        const banner = document.getElementById('connection-banner');
        if (banner) {
            banner.classList.add('hidden');
        }
    }
    
    /**
     * Sync pending optimistic actions
     */
    async syncPendingActions() {
        console.log(`[Sync] Syncing ${this.pendingOptimisticActions.size} pending actions...`);
        // TODO: Implement sync queue
    }
    
    /**
     * Event listeners setup
     */
    setupEventListeners() {
        // New task button
        document.querySelector('.btn-primary')?.addEventListener('click', () => {
            this.showCreateTaskModal();
        });
    }
    
    showCreateTaskModal() {
        const modal = document.getElementById('task-modal-overlay');
        if (modal) {
            modal.classList.remove('hidden');
        }
    }
    
    /**
     * Setup prefetching strategy
     */
    setupPrefetching() {
        // Prefetch on hover (predictive)
        document.addEventListener('mouseover', (e) => {
            const card = e.target.closest('.task-card');
            if (card) {
                const taskId = parseInt(card.dataset.taskId);
                this.prefetchTaskDetails(taskId);
            }
        });
    }
    
    async prefetchTaskDetails(taskId) {
        if (this.prefetchCache.has(`task_${taskId}`)) return;
        
        try {
            const response = await fetch(`/api/tasks/${taskId}?detail=mini`);
            const data = await response.json();
            this.prefetchCache.set(`task_${taskId}`, {
                data: data.task,
                timestamp: Date.now()
            });
        } catch (error) {
            // Silent fail for prefetch
        }
    }
    
    // Cache utilities
    getFromCache(key) {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : null;
    }
    
    setCache(key, data) {
        localStorage.setItem(key, JSON.stringify({
            data,
            timestamp: Date.now()
        }));
    }
    
    // Toast notification
    showToast(message, type = 'info') {
        console.log(`[Toast ${type}]`, message);
        // TODO: Implement toast UI
    }
    
    // Utility
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    /**
     * Smooth update when background fetch detects changes
     */
    updateTasksSmooth(newTasks) {
        console.log('[Live Update] Tasks changed, updating smoothly...');
        this.tasks = newTasks;
        // TODO: Implement FLIP animation for updates
    }
}

// CROWN⁴.6 PERFORMANCE FIX: Defer initialization to allow skeleton to paint first
// Using double-rAF pattern ensures browser paints skeleton before heavy FLIP work
function initMinaTasksLinear() {
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            console.log('[Linear] Skeleton painted, initializing FLIP animations...');
            window.minaTasksLinear = new MinaTasksLinear();
        });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMinaTasksLinear);
} else {
    initMinaTasksLinear();
}
