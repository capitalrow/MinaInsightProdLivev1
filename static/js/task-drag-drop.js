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
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.createPlaceholder();
        
        // Listen for task renders to make cards draggable
        window.addEventListener('tasks:rendered', () => {
            this.makeTasksDraggable();
        });

        console.log('✅ TaskDragDrop initialized');
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
            // Make card draggable
            card.setAttribute('draggable', 'true');
            card.dataset.dragIndex = index;
            
            // Remove existing listeners to avoid duplicates
            card.removeEventListener('dragstart', this.handleDragStart);
            card.removeEventListener('dragenter', this.handleDragEnter);
            card.removeEventListener('dragleave', this.handleDragLeave);
            
            // Add drag event listeners
            card.addEventListener('dragstart', this.handleDragStart.bind(this));
            card.addEventListener('dragenter', this.handleDragEnter.bind(this));
            card.addEventListener('dragleave', this.handleDragLeave.bind(this));
        });
    }

    handleDragStart(e) {
        this.isDragging = true;
        this.draggedElement = e.currentTarget;
        this.draggedTaskId = parseInt(this.draggedElement.dataset.taskId);
        this.draggedIndex = parseInt(this.draggedElement.dataset.dragIndex);
        
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
        
        if (newIndex !== -1 && newIndex !== this.draggedIndex) {
            await this.reorderTask(this.draggedTaskId, this.draggedIndex, newIndex);
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

    async reorderTask(taskId, oldIndex, newIndex) {
        try {
            // Get all tasks in current order
            const allCards = Array.from(document.querySelectorAll('.task-card, .task-item-enhanced'));
            const taskOrder = allCards.map(card => parseInt(card.dataset.taskId));
            
            // Calculate new positions for affected tasks
            const updates = [];
            
            if (newIndex > oldIndex) {
                // Moving down: shift tasks between oldIndex and newIndex up
                for (let i = oldIndex + 1; i <= newIndex; i++) {
                    updates.push({
                        task_id: taskOrder[i],
                        position: i - 1
                    });
                }
                updates.push({
                    task_id: taskId,
                    position: newIndex
                });
            } else {
                // Moving up: shift tasks between newIndex and oldIndex down
                for (let i = newIndex; i < oldIndex; i++) {
                    updates.push({
                        task_id: taskOrder[i],
                        position: i + 1
                    });
                }
                updates.push({
                    task_id: taskId,
                    position: newIndex
                });
            }
            
            // Animate the reorder with GSAP
            this.animateReorder(allCards, oldIndex, newIndex);
            
            // Optimistically update positions in cache
            for (const update of updates) {
                await this.optimisticUI.cache.updateTask(update.task_id, {
                    position: update.position
                });
            }
            
            // Persist to backend
            const response = await fetch('/api/tasks/reorder', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ updates })
            });
            
            if (!response.ok) {
                throw new Error('Failed to reorder tasks');
            }
            
            const result = await response.json();
            
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
                    affected_count: updates.length
                });
            }
            
            // Haptic feedback
            if (window.hapticFeedback) {
                window.hapticFeedback.trigger('medium');
            }
            
            // Re-render tasks to reflect new order
            const tasks = await this.optimisticUI.cache.getTasks();
            const activeTasks = tasks.filter(t => !t.deleted_at && !t.archived_at);
            
            // Sort by position
            activeTasks.sort((a, b) => (a.position || 0) - (b.position || 0));
            
            if (window.taskBootstrap) {
                const ctx = window.taskBootstrap._getCurrentViewContext?.() || { filter: 'active', search: '', sort: { field: 'created_at', direction: 'desc' } };
                await window.taskBootstrap.renderTasks(activeTasks, { 
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
