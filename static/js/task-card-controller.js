/**
 * CROWN⁴.5 Task Card Controller
 * Lightweight bridge between TaskInlineEditing and taskOptimisticUI
 * Manages two-mode card states (view/edit) and delegates to optimistic update pipeline
 */

class TaskCardController {
    constructor(cardElement) {
        this.card = cardElement;
        this.taskId = cardElement.dataset.taskId;
        this.optimisticUI = window.taskOptimisticUI;
        this.isEditing = false;
        
        // Track original values for rollback
        this.originalValues = {};
        
        if (!this.optimisticUI) {
            console.error('❌ TaskOptimisticUI not available for card', this.taskId);
        }
    }
    
    /**
     * Update task priority via optimistic UI pipeline
     * @param {string} taskId - Task ID
     * @param {string} newPriority - New priority value
     * @returns {Promise<void>}
     */
    async updatePriority(taskId, newPriority) {
        if (!this.optimisticUI) {
            throw new Error('TaskOptimisticUI not available');
        }
        
        console.log(`📝 [TaskCardController] Updating priority for task ${taskId} to ${newPriority}`);
        
        try {
            // Call optimistic UI's update method
            await this.optimisticUI.updateTask(taskId, { priority: newPriority });
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_priority_update', 1, { taskId, newPriority });
            }
        } catch (error) {
            console.error('❌ Failed to update priority:', error);
            throw error;
        }
    }
    
    /**
     * Update task status via optimistic UI pipeline
     * @param {string} taskId - Task ID
     * @param {string} newStatus - New status value
     * @returns {Promise<void>}
     */
    async updateStatus(taskId, newStatus) {
        if (!this.optimisticUI) {
            throw new Error('TaskOptimisticUI not available');
        }
        
        console.log(`📝 [TaskCardController] Updating status for task ${taskId} to ${newStatus}`);
        
        try {
            await this.optimisticUI.updateTask(taskId, { status: newStatus });
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_status_update', 1, { taskId, newStatus });
            }
        } catch (error) {
            console.error('❌ Failed to update status:', error);
            throw error;
        }
    }
    
    /**
     * Update task due date via optimistic UI pipeline
     * @param {string} taskId - Task ID
     * @param {string} newDueDate - New due date (ISO format)
     * @returns {Promise<void>}
     */
    async updateDueDate(taskId, newDueDate) {
        if (!this.optimisticUI) {
            throw new Error('TaskOptimisticUI not available');
        }
        
        console.log(`📝 [TaskCardController] Updating due date for task ${taskId} to ${newDueDate}`);
        
        try {
            await this.optimisticUI.updateTask(taskId, { due_date: newDueDate });
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_due_date_update', 1, { taskId, newDueDate });
            }
        } catch (error) {
            console.error('❌ Failed to update due date:', error);
            throw error;
        }
    }
    
    /**
     * Update task assignees via optimistic UI pipeline
     * @param {string} taskId - Task ID
     * @param {Array<number>} assigneeIds - Array of user IDs to assign
     * @returns {Promise<void>}
     */
    async updateAssignees(taskId, assigneeIds) {
        if (!this.optimisticUI) {
            throw new Error('TaskOptimisticUI not available');
        }
        
        console.log(`📝 [TaskCardController] Updating assignees for task ${taskId}`, assigneeIds);
        
        try {
            await this.optimisticUI.updateTask(taskId, { assignee_ids: assigneeIds });
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_assignees_update', 1, { taskId, count: assigneeIds.length });
            }
        } catch (error) {
            console.error('❌ Failed to update assignees:', error);
            throw error;
        }
    }
    
    /**
     * Update task title via optimistic UI pipeline
     * @param {string} taskId - Task ID
     * @param {string} newTitle - New title
     * @returns {Promise<void>}
     */
    async updateTitle(taskId, newTitle) {
        if (!this.optimisticUI) {
            throw new Error('TaskOptimisticUI not available');
        }
        
        console.log(`📝 [TaskCardController] Updating title for task ${taskId}`, newTitle);
        
        try {
            await this.optimisticUI.updateTask(taskId, { title: newTitle });
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_title_update', 1, { taskId });
            }
        } catch (error) {
            console.error('❌ Failed to update title:', error);
            throw error;
        }
    }
    
    /**
     * Enter editing mode for card
     * @param {string} field - Field being edited (title, priority, due_date, assignee)
     */
    enterEditMode(field) {
        this.isEditing = true;
        this.card.classList.add('is-editing');
        this.card.dataset.editingField = field;
        
        console.log(`✏️ [TaskCardController] Entering edit mode for ${field} on task ${this.taskId}`);
        
        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('task_edit_mode_enter', 1, { taskId: this.taskId, field });
        }
    }
    
    /**
     * Exit editing mode for card
     */
    exitEditMode() {
        this.isEditing = false;
        this.card.classList.remove('is-editing');
        delete this.card.dataset.editingField;
        
        console.log(`👁️ [TaskCardController] Exiting edit mode for task ${this.taskId}`);
        
        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('task_edit_mode_exit', 1, { taskId: this.taskId });
        }
    }
    
    /**
     * Toggle mobile details expansion
     */
    toggleDetails() {
        const detailsSection = this.card.querySelector('.task-details');
        if (detailsSection) {
            const isExpanded = detailsSection.classList.toggle('expanded');
            this.card.dataset.detailsExpanded = isExpanded;
            
            console.log(`📱 [TaskCardController] ${isExpanded ? 'Expanded' : 'Collapsed'} details for task ${this.taskId}`);
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_details_toggle', 1, { taskId: this.taskId, expanded: isExpanded });
            }
        }
    }
}

// Global registry for task card controllers
window.taskCardControllers = window.taskCardControllers || new Map();

/**
 * Initialize controller for a task card
 * @param {HTMLElement} cardElement - Task card element
 * @returns {TaskCardController}
 */
function initializeTaskCardController(cardElement) {
    const taskId = cardElement.dataset.taskId;
    
    if (!window.taskCardControllers.has(taskId)) {
        const controller = new TaskCardController(cardElement);
        window.taskCardControllers.set(taskId, controller);
        console.log(`✅ [TaskCardController] Initialized controller for task ${taskId}`);
    }
    
    return window.taskCardControllers.get(taskId);
}

/**
 * Get controller for a task
 * @param {string} taskId - Task ID
 * @returns {TaskCardController|null}
 */
function getTaskCardController(taskId) {
    return window.taskCardControllers.get(taskId) || null;
}

// Export to global scope
window.TaskCardController = TaskCardController;
window.initializeTaskCardController = initializeTaskCardController;
window.getTaskCardController = getTaskCardController;

console.log('✅ TaskCardController module loaded');
