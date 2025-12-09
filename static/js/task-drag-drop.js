/**
 * CROWN⁴.5 Task Drag-and-Drop Reordering
 * Native HTML5 Drag-and-Drop with GSAP animations and position persistence
 * Part of Phase 3 Task 9
 */

class TaskDragDrop {
    constructor(optimisticUI) {
        this.optimisticUI = optimisticUI;
        this.draggedElement = null;
        this.draggedTaskId = null;
        this.draggedIndex = null;
        this.dropZoneElement = null;
        this.placeholder = null;
        this.isDragging = false;
        
        // Touch-specific state
        this.touchClone = null;
        this.touchStartY = 0;
        this.touchStartX = 0;
        this.longPressTimer = null;
        this.longPressDelay = 300; // ms to hold before drag starts
        this.touchScrollThreshold = 10; // px movement before canceling long press
        this.isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        
        // Bound handler references for proper cleanup
        this._boundTouchStart = this.handleTouchStart.bind(this);
        this._boundTouchMove = this.handleTouchMove.bind(this);
        this._boundTouchEnd = this.handleTouchEnd.bind(this);
        this._boundTouchCancel = this.handleTouchCancel.bind(this);
        this._boundDragStart = this.handleDragStart.bind(this);
        this._boundDragEnter = this.handleDragEnter.bind(this);
        this._boundDragLeave = this.handleDragLeave.bind(this);
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.createPlaceholder();
        
        // Listen for task renders to make cards draggable
        window.addEventListener('tasks:rendered', () => {
            this.makeTasksDraggable();
        });

        console.log('[DragDrop] ✅ TaskDragDrop initialized');
    }

    createPlaceholder() {
        // Create a visual placeholder for drop zones
        this.placeholder = document.createElement('div');
        this.placeholder.className = 'task-drag-placeholder';
        this.placeholder.innerHTML = `
            <div class="placeholder-content">
                <i data-feather="move"></i>
                <span>Drop here</span>
            </div>
        `;
    }

    setupEventListeners() {
        // Global drag events
        document.addEventListener('dragover', this.handleDragOver.bind(this));
        document.addEventListener('dragend', this.handleDragEnd.bind(this));
        document.addEventListener('drop', this.handleDrop.bind(this));
    }

    makeTasksDraggable() {
        const taskCards = document.querySelectorAll('.task-card, .task-item-enhanced');
        
        taskCards.forEach((card, index) => {
            // Make card draggable (desktop only - touch uses long-press)
            card.setAttribute('draggable', 'true');
            card.dataset.dragIndex = index;
            
            // Remove existing listeners to avoid duplicates (using stored bound refs)
            card.removeEventListener('dragstart', this._boundDragStart);
            card.removeEventListener('dragenter', this._boundDragEnter);
            card.removeEventListener('dragleave', this._boundDragLeave);
            
            // Add drag event listeners (desktop)
            card.addEventListener('dragstart', this._boundDragStart);
            card.addEventListener('dragenter', this._boundDragEnter);
            card.addEventListener('dragleave', this._boundDragLeave);
            
            // Add touch event listeners (mobile) - remove first to avoid duplicates
            if (this.isTouchDevice) {
                card.removeEventListener('touchstart', this._boundTouchStart);
                card.removeEventListener('touchmove', this._boundTouchMove);
                card.removeEventListener('touchend', this._boundTouchEnd);
                card.removeEventListener('touchcancel', this._boundTouchCancel);
                
                card.addEventListener('touchstart', this._boundTouchStart, { passive: false });
                card.addEventListener('touchmove', this._boundTouchMove, { passive: false });
                card.addEventListener('touchend', this._boundTouchEnd, { passive: false });
                card.addEventListener('touchcancel', this._boundTouchCancel, { passive: false });
            }
        });
    }

    handleDragStart(e) {
        this.isDragging = true;
        this.draggedElement = e.currentTarget;
        this.draggedTaskId = parseInt(this.draggedElement.dataset.taskId);
        this.draggedIndex = parseInt(this.draggedElement.dataset.dragIndex);
        
        console.log('[DragDrop] 🎯 DRAG START');
        console.log('[DragDrop] Task ID:', this.draggedTaskId);
        console.log('[DragDrop] Original index:', this.draggedIndex);
        
        // Set drag data
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', this.draggedTaskId);
        
        // Add dragging class with delay to prevent flicker
        setTimeout(() => {
            if (this.draggedElement) {
                this.draggedElement.classList.add('task-dragging');
            }
        }, 0);
        
        // Animate drag start with GSAP
        if (window.gsap) {
            gsap.to(this.draggedElement, {
                opacity: 0.5,
                scale: 0.98,
                duration: 0.2,
                ease: 'power2.out'
            });
        }
        
        // Track telemetry
        if (window.telemetry) {
            window.telemetry.track('task_drag_start', { task_id: this.draggedTaskId });
        }
        
        // Haptic feedback
        if (window.hapticFeedback) {
            window.hapticFeedback.trigger('light');
        }
    }

    handleDragEnter(e) {
        if (!this.isDragging) return;
        
        const dropTarget = e.currentTarget;
        if (dropTarget === this.draggedElement) return;
        
        // Add drop zone styling
        dropTarget.classList.add('task-drag-over');
        
        // Insert placeholder
        const rect = dropTarget.getBoundingClientRect();
        const midpoint = rect.top + rect.height / 2;
        
        if (e.clientY < midpoint) {
            dropTarget.parentNode.insertBefore(this.placeholder, dropTarget);
        } else {
            dropTarget.parentNode.insertBefore(this.placeholder, dropTarget.nextSibling);
        }
        
        // Render feather icons in placeholder
        if (window.feather) {
            feather.replace();
        }
    }

    handleDragLeave(e) {
        const dropTarget = e.currentTarget;
        dropTarget.classList.remove('task-drag-over');
    }

    handleDragOver(e) {
        if (!this.isDragging) return;
        
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
    }

    async handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        
        if (!this.isDragging) return;
        
        console.log('[DragDrop] 📍 DROP EVENT');
        console.log('[DragDrop] Task being dropped:', this.draggedTaskId);
        
        // Calculate new index BEFORE removing placeholder
        // Find placeholder position among all cards
        const parent = this.draggedElement.parentNode;
        const allChildren = Array.from(parent.children);
        let placeholderIndex = -1;
        
        if (this.placeholder && this.placeholder.parentNode) {
            placeholderIndex = allChildren.indexOf(this.placeholder);
            // Remove placeholder after calculating index
            this.placeholder.parentNode.removeChild(this.placeholder);
        }
        
        // If placeholder was found, use its position as new index
        // Adjust for the fact that placeholder will be removed
        let newIndex = placeholderIndex;
        if (newIndex > this.draggedIndex) {
            newIndex--; // Placeholder was after dragged element, so decrement
        }
        
        // Fallback to current position if placeholder wasn't found
        if (newIndex === -1) {
            const allCards = Array.from(document.querySelectorAll('.task-card, .task-item-enhanced'));
            newIndex = allCards.indexOf(this.draggedElement);
        }
        
        console.log('[DragDrop] Position change:', this.draggedIndex, '→', newIndex);
        
        if (newIndex !== -1 && newIndex !== this.draggedIndex) {
            console.log('[DragDrop] Calling reorderTask()');
            await this.reorderTask(this.draggedTaskId, this.draggedIndex, newIndex);
        } else {
            console.log('[DragDrop] No position change, skipping reorder');
        }
    }

    handleDragEnd(e) {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        
        // Remove dragging class
        if (this.draggedElement) {
            this.draggedElement.classList.remove('task-dragging');
            
            // Animate drag end with GSAP
            if (window.gsap) {
                gsap.to(this.draggedElement, {
                    opacity: 1,
                    scale: 1,
                    duration: 0.3,
                    ease: 'elastic.out(1, 0.5)'
                });
            }
        }
        
        // Remove all drop zone styling
        document.querySelectorAll('.task-drag-over').forEach(el => {
            el.classList.remove('task-drag-over');
        });
        
        // Remove placeholder if still present
        if (this.placeholder && this.placeholder.parentNode) {
            this.placeholder.parentNode.removeChild(this.placeholder);
        }
        
        // Reset state
        this.draggedElement = null;
        this.draggedTaskId = null;
        this.draggedIndex = null;
    }

    // ========== TOUCH EVENT HANDLERS ==========
    
    handleTouchStart(e) {
        // Only handle single touch
        if (e.touches.length !== 1) return;
        
        const touch = e.touches[0];
        const card = e.currentTarget;
        
        // Store touch start position
        this.touchStartX = touch.clientX;
        this.touchStartY = touch.clientY;
        this._touchStartCard = card; // Store for use in timer
        
        // Prevent text selection on long press (iOS Safari)
        card.style.webkitUserSelect = 'none';
        card.style.userSelect = 'none';
        
        // Add temporary contextmenu handler to prevent native menu on long press
        this._contextMenuHandler = (evt) => evt.preventDefault();
        card.addEventListener('contextmenu', this._contextMenuHandler);
        
        // Start long press timer
        this.longPressTimer = setTimeout(() => {
            this.startTouchDrag(this._touchStartCard, touch);
        }, this.longPressDelay);
        
        console.log('[DragDrop] 👆 Touch start on task:', card.dataset.taskId);
    }
    
    handleTouchMove(e) {
        const touch = e.touches[0];
        
        // If not dragging yet, check if we should cancel the long press
        if (!this.isDragging && this.longPressTimer) {
            const deltaX = Math.abs(touch.clientX - this.touchStartX);
            const deltaY = Math.abs(touch.clientY - this.touchStartY);
            
            // If moved too much, cancel long press (user is scrolling)
            if (deltaX > this.touchScrollThreshold || deltaY > this.touchScrollThreshold) {
                this.cancelLongPress();
                return;
            }
        }
        
        // If actively dragging, handle the move
        if (this.isDragging) {
            e.preventDefault(); // Prevent scrolling while dragging
            this.updateTouchDrag(touch);
        }
    }
    
    handleTouchEnd(e) {
        // Cancel any pending long press
        this.cancelLongPress();
        
        if (!this.isDragging) return;
        
        // Prevent the synthetic click that browsers emit after touch
        e.preventDefault();
        e.stopPropagation();
        
        console.log('[DragDrop] 👆 Touch end');
        
        // Add one-time click capture to suppress the synthetic click
        // (some browsers still emit click even with preventDefault on touchend)
        if (this._touchDragActivated) {
            const clickSuppressor = (evt) => {
                evt.preventDefault();
                evt.stopPropagation();
                evt.stopImmediatePropagation();
            };
            document.addEventListener('click', clickSuppressor, { capture: true, once: true });
            
            // Safety cleanup - remove after short delay if not triggered
            setTimeout(() => {
                document.removeEventListener('click', clickSuppressor, { capture: true });
            }, 100);
        }
        
        // Complete the drag operation
        this.completeTouchDrag();
    }
    
    handleTouchCancel(e) {
        console.log('[DragDrop] 👆 Touch cancel');
        this.cancelLongPress();
        this.cancelTouchDrag();
    }
    
    cancelLongPress() {
        if (this.longPressTimer) {
            clearTimeout(this.longPressTimer);
            this.longPressTimer = null;
        }
        
        // Clean up contextmenu handler if it was added
        if (this._touchStartCard && this._contextMenuHandler) {
            this._touchStartCard.removeEventListener('contextmenu', this._contextMenuHandler);
            // Restore user select
            this._touchStartCard.style.webkitUserSelect = '';
            this._touchStartCard.style.userSelect = '';
        }
        this._contextMenuHandler = null;
    }
    
    startTouchDrag(card, touch) {
        this.isDragging = true;
        this._touchDragActivated = true; // Flag to suppress synthetic click
        this.draggedElement = card;
        this.draggedTaskId = parseInt(card.dataset.taskId);
        this.draggedIndex = parseInt(card.dataset.dragIndex);
        
        console.log('[DragDrop] 🎯 TOUCH DRAG START');
        console.log('[DragDrop] Task ID:', this.draggedTaskId);
        
        // Create visual clone for dragging
        this.createTouchClone(card, touch);
        
        // Add dragging class to original
        card.classList.add('task-dragging');
        
        // Animate original to semi-transparent
        if (window.gsap) {
            gsap.to(card, {
                opacity: 0.4,
                scale: 0.98,
                duration: 0.2,
                ease: 'power2.out'
            });
        }
        
        // Haptic feedback
        if (window.hapticFeedback) {
            window.hapticFeedback.trigger('medium');
        } else if (navigator.vibrate) {
            navigator.vibrate(50); // Fallback vibration
        }
        
        // Track telemetry
        if (window.telemetry) {
            window.telemetry.track('task_touch_drag_start', { task_id: this.draggedTaskId });
        }
    }
    
    createTouchClone(card, touch) {
        // Remove existing clone if any
        this.removeTouchClone();
        
        // Clone the card
        this.touchClone = card.cloneNode(true);
        this.touchClone.className = 'task-drag-clone';
        
        // Style the clone
        const rect = card.getBoundingClientRect();
        Object.assign(this.touchClone.style, {
            position: 'fixed',
            top: `${rect.top}px`,
            left: `${rect.left}px`,
            width: `${rect.width}px`,
            height: `${rect.height}px`,
            zIndex: '10000',
            pointerEvents: 'none',
            opacity: '0.9',
            transform: 'rotate(2deg) scale(1.02)',
            boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)',
            transition: 'none',
            willChange: 'transform'
        });
        
        document.body.appendChild(this.touchClone);
        
        // Store offset from touch point to card origin
        this.touchOffsetX = touch.clientX - rect.left;
        this.touchOffsetY = touch.clientY - rect.top;
    }
    
    updateTouchDrag(touch) {
        // Move the clone
        if (this.touchClone) {
            const x = touch.clientX - this.touchOffsetX;
            const y = touch.clientY - this.touchOffsetY;
            this.touchClone.style.left = `${x}px`;
            this.touchClone.style.top = `${y}px`;
        }
        
        // Find element under touch point (ignoring the clone)
        // Guard against missing clone
        if (!this.touchClone) return;
        
        this.touchClone.style.display = 'none';
        const elementBelow = document.elementFromPoint(touch.clientX, touch.clientY);
        this.touchClone.style.display = '';
        
        // Guard against null elementBelow (touch is outside viewport or on non-element)
        if (!elementBelow) {
            // Clear drop zone styling but don't try to update placeholder
            document.querySelectorAll('.task-drag-over').forEach(el => {
                el.classList.remove('task-drag-over');
            });
            return;
        }
        
        // Find the task card under the touch
        const dropTarget = elementBelow.closest('.task-card, .task-item-enhanced');
        
        // Update drop zone styling
        document.querySelectorAll('.task-drag-over').forEach(el => {
            if (el !== dropTarget) {
                el.classList.remove('task-drag-over');
            }
        });
        
        if (dropTarget && dropTarget !== this.draggedElement) {
            dropTarget.classList.add('task-drag-over');
            this.dropZoneElement = dropTarget;
            
            // Position placeholder - guard against missing parent
            if (dropTarget.parentNode) {
                const rect = dropTarget.getBoundingClientRect();
                const midpoint = rect.top + rect.height / 2;
                
                if (touch.clientY < midpoint) {
                    dropTarget.parentNode.insertBefore(this.placeholder, dropTarget);
                } else {
                    dropTarget.parentNode.insertBefore(this.placeholder, dropTarget.nextSibling);
                }
                
                // Render feather icons in placeholder
                if (window.feather) {
                    feather.replace();
                }
            }
        }
    }
    
    async completeTouchDrag() {
        console.log('[DragDrop] 📍 TOUCH DROP');
        
        // Calculate new index from placeholder position
        const parent = this.draggedElement.parentNode;
        const allChildren = Array.from(parent.children);
        let placeholderIndex = -1;
        
        if (this.placeholder && this.placeholder.parentNode) {
            placeholderIndex = allChildren.indexOf(this.placeholder);
            this.placeholder.parentNode.removeChild(this.placeholder);
        }
        
        let newIndex = placeholderIndex;
        if (newIndex > this.draggedIndex) {
            newIndex--;
        }
        
        // Fallback
        if (newIndex === -1) {
            const allCards = Array.from(document.querySelectorAll('.task-card, .task-item-enhanced'));
            newIndex = allCards.indexOf(this.draggedElement);
        }
        
        console.log('[DragDrop] Position change:', this.draggedIndex, '→', newIndex);
        
        // Clean up visual state
        this.cleanupTouchDrag();
        
        // Execute reorder if position changed
        if (newIndex !== -1 && newIndex !== this.draggedIndex) {
            await this.reorderTask(this.draggedTaskId, this.draggedIndex, newIndex);
        }
        
        // Reset state
        this.resetTouchState();
    }
    
    cancelTouchDrag() {
        this.cleanupTouchDrag();
        this.resetTouchState();
    }
    
    cleanupTouchDrag() {
        // Remove clone
        this.removeTouchClone();
        
        // Restore original card
        if (this.draggedElement) {
            this.draggedElement.classList.remove('task-dragging');
            
            if (window.gsap) {
                gsap.to(this.draggedElement, {
                    opacity: 1,
                    scale: 1,
                    duration: 0.3,
                    ease: 'elastic.out(1, 0.5)'
                });
            }
        }
        
        // Remove drop zone styling
        document.querySelectorAll('.task-drag-over').forEach(el => {
            el.classList.remove('task-drag-over');
        });
        
        // Remove placeholder
        if (this.placeholder && this.placeholder.parentNode) {
            this.placeholder.parentNode.removeChild(this.placeholder);
        }
    }
    
    removeTouchClone() {
        if (this.touchClone && this.touchClone.parentNode) {
            this.touchClone.parentNode.removeChild(this.touchClone);
        }
        this.touchClone = null;
    }
    
    resetTouchState() {
        this.isDragging = false;
        this._touchDragActivated = false;
        this.draggedElement = null;
        this.draggedTaskId = null;
        this.draggedIndex = null;
        this.dropZoneElement = null;
        this.touchOffsetX = 0;
        this.touchOffsetY = 0;
    }

    async reorderTask(taskId, oldIndex, newIndex) {
        console.log('[DragDrop] 🔄 REORDER START');
        console.log('[DragDrop] Task:', taskId, '| From:', oldIndex, '→ To:', newIndex);
        
        try {
            // Get all visible cards in current DOM order
            const allCards = Array.from(document.querySelectorAll('.task-card, .task-item-enhanced'));
            console.log('[DragDrop] Visible cards count:', allCards.length);
            
            // CROWN⁴.5 FIX: Calculate position using GLOBAL task list
            // This preserves global order when filters hide intermediate tasks
            
            // Get ALL tasks from cache (including hidden/filtered ones)
            const allTasks = await this.optimisticUI.cache.getTasks();
            const activeTasks = allTasks.filter(t => !t.deleted_at && !t.archived_at);
            
            // Sort ALL tasks by position to get global order
            const globalSorted = [...activeTasks].sort((a, b) => (a.position || 0) - (b.position || 0));
            
            console.log('[DragDrop] Global task order:', globalSorted.map(t => ({id: t.id, pos: t.position})));
            
            // Build array of visible task IDs in DOM order
            const visibleTaskIds = allCards.map(card => parseInt(card.dataset.taskId));
            
            // Remove the dragged task from globalSorted for position calculation
            const globalWithoutDragged = globalSorted.filter(t => t.id !== taskId);
            
            // FIXED ALGORITHM: Use the drop target's global position as the anchor
            // When dropping at position N in filtered view:
            // - If moving down (after card at newIndex): insert right after that card in GLOBAL order
            // - If moving up (before card at newIndex): insert right before that card in GLOBAL order
            
            // Get the anchor task (the visible task we're dropping relative to)
            let anchorTaskId;
            let insertBefore; // true = insert before anchor, false = insert after
            
            if (newIndex > oldIndex) {
                // Moving down: we want to go AFTER the card at newIndex
                anchorTaskId = visibleTaskIds[newIndex];
                insertBefore = false;
            } else {
                // Moving up: we want to go BEFORE the card at newIndex
                anchorTaskId = visibleTaskIds[newIndex];
                insertBefore = true;
            }
            
            // Handle edge cases where anchor is self
            if (anchorTaskId === taskId) {
                if (insertBefore && newIndex > 0) {
                    anchorTaskId = visibleTaskIds[newIndex - 1];
                    insertBefore = false;
                } else if (!insertBefore && newIndex + 1 < visibleTaskIds.length) {
                    anchorTaskId = visibleTaskIds[newIndex + 1];
                    insertBefore = true;
                }
            }
            
            console.log('[DragDrop] Anchor task:', anchorTaskId, insertBefore ? 'insert BEFORE' : 'insert AFTER');
            
            // Find the anchor's position in the global list
            const anchorGlobalIdx = globalWithoutDragged.findIndex(t => t.id === anchorTaskId);
            
            // Determine actual global neighbors based on insertion direction
            let actualPrevTask, actualNextTask;
            
            if (anchorGlobalIdx === -1) {
                // Anchor not found (edge case) - insert at beginning
                actualPrevTask = null;
                actualNextTask = globalWithoutDragged[0] || null;
            } else if (insertBefore) {
                // Insert BEFORE anchor: prev = task before anchor, next = anchor
                actualPrevTask = anchorGlobalIdx > 0 ? globalWithoutDragged[anchorGlobalIdx - 1] : null;
                actualNextTask = globalWithoutDragged[anchorGlobalIdx];
            } else {
                // Insert AFTER anchor: prev = anchor, next = task after anchor
                actualPrevTask = globalWithoutDragged[anchorGlobalIdx];
                actualNextTask = anchorGlobalIdx + 1 < globalWithoutDragged.length 
                    ? globalWithoutDragged[anchorGlobalIdx + 1] 
                    : null;
            }
            
            const globalPrevPosition = actualPrevTask ? (actualPrevTask.position ?? 0) : null;
            const globalNextPosition = actualNextTask ? (actualNextTask.position ?? 0) : null;
            
            console.log('[DragDrop] Actual global neighbors:', { 
                prev: actualPrevTask ? { id: actualPrevTask.id, pos: globalPrevPosition } : null,
                next: actualNextTask ? { id: actualNextTask.id, pos: globalNextPosition } : null
            });
            
            // Calculate new position between actual global neighbors
            let newPosition;
            let redistributionUpdates = []; // Additional tasks to renumber if needed
            
            if (globalPrevPosition !== null && globalNextPosition !== null) {
                // Dropping between two tasks
                const gap = globalNextPosition - globalPrevPosition;
                
                if (gap > 1) {
                    // There's room - use midpoint
                    newPosition = Math.floor((globalPrevPosition + globalNextPosition) / 2);
                } else {
                    // NO GAP - need to redistribute positions to create space
                    // Strategy: Shift all tasks from nextTask onwards by 1000 to create room
                    console.log('[DragDrop] ⚠️ No position gap, redistributing...');
                    
                    const nextTaskIdx = globalWithoutDragged.findIndex(t => t.id === actualNextTask.id);
                    
                    // Shift all tasks from nextTask onwards
                    for (let i = nextTaskIdx; i < globalWithoutDragged.length; i++) {
                        const task = globalWithoutDragged[i];
                        const shiftAmount = 1000;
                        redistributionUpdates.push({
                            task_id: task.id,
                            position: (task.position || 0) + shiftAmount
                        });
                    }
                    
                    // Now there's room - use midpoint between prev and shifted next
                    const shiftedNextPosition = globalNextPosition + 1000;
                    newPosition = Math.floor((globalPrevPosition + shiftedNextPosition) / 2);
                    
                    console.log('[DragDrop] Redistributed', redistributionUpdates.length, 'tasks');
                }
            } else if (globalPrevPosition !== null) {
                // Dropping at the end - add spacing after last
                newPosition = globalPrevPosition + 1000;
            } else if (globalNextPosition !== null) {
                // Dropping at the beginning - subtract spacing from first
                newPosition = globalNextPosition - 1000;
            } else {
                // Only task or edge case - use center
                newPosition = 0;
            }
            
            console.log('[DragDrop] New position calculated:', newPosition, 
                        '(between', globalPrevPosition, 'and', globalNextPosition, ')');
            
            // Combine dragged task update with any redistribution updates
            const updates = [
                ...redistributionUpdates, // Shift tasks first
                {
                    task_id: taskId,
                    position: newPosition
                }
            ];
            
            // Animate the reorder with GSAP
            this.animateReorder(allCards, oldIndex, newIndex);
            
            // Optimistically update positions in cache
            for (const update of updates) {
                await this.optimisticUI.cache.updateTask(update.task_id, {
                    position: update.position
                });
            }
            
            // Persist to backend
            console.log('[DragDrop] 📤 POST /api/tasks/reorder with', updates.length, 'updates (including', redistributionUpdates.length, 'redistributions)');
            const response = await fetch('/api/tasks/reorder', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ updates })
            });
            
            if (!response.ok) {
                console.error('[DragDrop] ❌ Reorder API failed:', response.status);
                throw new Error('Failed to reorder tasks');
            }
            
            const result = await response.json();
            console.log('[DragDrop] ✅ Server confirmed reorder:', result);
            
            // Show success feedback
            if (window.toastManager) {
                window.toastManager.show({
                    message: 'Task order updated',
                    type: 'success',
                    duration: 2000
                });
            }
            
            // Track telemetry
            if (window.telemetry) {
                window.telemetry.track('task_reorder', {
                    task_id: taskId,
                    old_index: oldIndex,
                    new_index: newIndex,
                    new_position: newPosition,
                    visible_tasks_count: visibleTaskIds.length,
                    redistributed_count: redistributionUpdates.length
                });
            }
            
            // Haptic feedback
            if (window.hapticFeedback) {
                window.hapticFeedback.trigger('medium');
            }
            
            // Re-render tasks to reflect new order
            const tasksForRender = await this.optimisticUI.cache.getTasks();
            const tasksToRender = tasksForRender.filter(t => !t.deleted_at && !t.archived_at);
            
            // Sort by position
            tasksToRender.sort((a, b) => (a.position || 0) - (b.position || 0));
            
            if (window.taskBootstrap) {
                const ctx = window.taskBootstrap._getCurrentViewContext?.() || { filter: 'active', search: '', sort: { field: 'created_at', direction: 'desc' } };
                await window.taskBootstrap.renderTasks(tasksToRender, { 
                    fromCache: true, 
                    source: 'optimistic',
                    isUserAction: true,
                    filterContext: ctx.filter,
                    searchQuery: ctx.search,
                    sortConfig: ctx.sort
                });
            }
            
        } catch (error) {
            console.error('Task reorder failed:', error);
            
            // Show error toast
            if (window.toastManager) {
                window.toastManager.show({
                    message: 'Failed to update task order',
                    type: 'error',
                    duration: 4000
                });
            }
            
            // Rollback: re-render tasks from server
            if (window.taskBootstrap) {
                await window.taskBootstrap.bootstrap();
            }
        }
    }

    animateReorder(allCards, oldIndex, newIndex) {
        if (!window.gsap) return;
        
        // Store original positions
        const positions = allCards.map(card => ({
            element: card,
            rect: card.getBoundingClientRect()
        }));
        
        // Move the dragged element to new position in DOM
        const draggedCard = allCards[oldIndex];
        const parent = draggedCard.parentNode;
        
        if (newIndex > oldIndex) {
            // Moving down
            const nextCard = allCards[newIndex + 1];
            parent.insertBefore(draggedCard, nextCard);
        } else {
            // Moving up
            const targetCard = allCards[newIndex];
            parent.insertBefore(draggedCard, targetCard);
        }
        
        // Calculate deltas and animate
        positions.forEach(({ element, rect }) => {
            const newRect = element.getBoundingClientRect();
            const deltaY = rect.top - newRect.top;
            
            if (deltaY !== 0) {
                gsap.fromTo(element,
                    { y: deltaY },
                    {
                        y: 0,
                        duration: 0.4,
                        ease: 'power2.out'
                    }
                );
            }
        });
    }

    enableDragDrop() {
        this.makeTasksDraggable();
    }

    disableDragDrop() {
        const taskCards = document.querySelectorAll('.task-card, .task-item-enhanced');
        taskCards.forEach(card => {
            card.setAttribute('draggable', 'false');
        });
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TaskDragDrop;
}
