/**
 * CROWN⁴.5 Task Search & Sort Module
 * Real-time search filtering and multi-criteria sorting
 */

class TaskSearchSort {
    constructor() {
        this.searchInput = document.getElementById('task-search-input');
        this.searchClearBtn = document.getElementById('search-clear-btn');
        this.sortSelect = document.getElementById('task-sort-select');
        this.visibleCountEl = document.getElementById('visible-task-count');
        this.totalCountEl = document.getElementById('total-task-count');
        this.tasksContainer = document.getElementById('tasks-list-container');
        
        this.searchQuery = '';
        this.currentSort = 'default';
        this.currentFilter = 'active'; // Default to 'active' tab to hide archived tasks
        this.quickFilter = null; // Added for quick filter support
        
        this.init();
        console.log('[TaskSearchSort] Initialized with default filter: active');
    }
    
    init() {
        // Search input handler with debouncing
        let searchTimeout;
        this.searchInput?.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.searchQuery = e.target.value.toLowerCase().trim();
                this.updateClearButton();
                this.applyFiltersAndSort();
            }, 150); // 150ms debounce for smooth performance
        });
        
        // Clear button
        this.searchClearBtn?.addEventListener('click', () => {
            this.searchInput.value = '';
            this.searchQuery = '';
            this.updateClearButton();
            this.applyFiltersAndSort();
            this.searchInput.focus();
        });
        
        // Sort selector
        this.sortSelect?.addEventListener('change', (e) => {
            this.currentSort = e.target.value;
            this.applyFiltersAndSort();
        });
        
        // Listen for filter tab changes
        document.addEventListener('filterChanged', (e) => {
            this.currentFilter = e.detail.filter;
            this.applyFiltersAndSort();
        });
        
        // Apply initial filter after tasks bootstrap completes
        document.addEventListener('task:bootstrap:complete', () => {
            this.applyFiltersAndSort();
            console.log('[TaskSearchSort] Initial filter applied after bootstrap: active (hiding archived tasks)');
        });
        
        // Reapply filter when tasks are mutated (OptimisticUI + WebSocket sync)
        // CRITICAL: Listen on window (not document) because OptimisticUI dispatches on window
        const taskMutationEvents = [
            'task:created', 
            'task:updated', 
            'task:deleted', 
            'task:restored',
            'task:completed'    // Handle completion events for filter updates
        ];
        taskMutationEvents.forEach(eventName => {
            window.addEventListener(eventName, () => {
                // Small delay to ensure DOM update completes
                requestAnimationFrame(() => {
                    this.applyFiltersAndSort();
                });
            });
        });
        
        // Initial count update
        this.updateCounts();
    }
    
    updateClearButton() {
        if (this.searchQuery.length > 0) {
            this.searchClearBtn?.classList.remove('hidden');
        } else {
            this.searchClearBtn?.classList.add('hidden');
        }
    }
    
    applyFiltersAndSort() {
        const tasks = Array.from(this.tasksContainer?.querySelectorAll('.task-card') || []);
        
        // 1. Apply search filter
        let visibleTasks = tasks.filter(task => {
            if (!this.searchQuery) return true;
            
            const title = task.querySelector('.task-title')?.textContent.toLowerCase() || '';
            const assignee = task.querySelector('.task-assignee')?.textContent.toLowerCase() || '';
            const labels = Array.from(task.querySelectorAll('.task-label'))
                .map(label => label.textContent.toLowerCase())
                .join(' ');
            
            return title.includes(this.searchQuery) || 
                   assignee.includes(this.searchQuery) || 
                   labels.includes(this.searchQuery);
        });
        
        // 2. Apply archive filter (from filter tabs: All/Active/Archived)
        // CRITICAL: Deleted tasks should NEVER show up, regardless of filter
        visibleTasks = visibleTasks.filter(task => !task.dataset.deletedAt);
        
        if (this.currentFilter === 'active') {
            // Active = not archived (deleted already filtered above)
            visibleTasks = visibleTasks.filter(task => !task.dataset.archivedAt);
        } else if (this.currentFilter === 'archived') {
            // Archived = has archived_at timestamp (deleted already filtered above)
            visibleTasks = visibleTasks.filter(task => task.dataset.archivedAt);
        }
        // 'all' shows active + archived (deleted already filtered above)
        
        // 2.5. Apply quick filter (from Quick Actions Bar)
        if (this.quickFilter) {
            visibleTasks = this.applyQuickFilterLogic(visibleTasks, this.quickFilter);
        }
        
        // 3. Apply sorting
        if (this.currentSort !== 'default') {
            visibleTasks = this.sortTasks(visibleTasks, this.currentSort);
        }
        
        // 4. Update DOM visibility
        tasks.forEach(task => {
            if (visibleTasks.includes(task)) {
                task.style.display = '';
                task.style.order = visibleTasks.indexOf(task);
            } else {
                task.style.display = 'none';
            }
        });
        
        // 5. Update counts
        this.updateCounts(visibleTasks.length, tasks.length);
    }
    
    sortTasks(tasks, sortType) {
        const sorted = [...tasks];
        
        const priorityOrder = { high: 3, medium: 2, low: 1 };
        
        sorted.sort((a, b) => {
            switch (sortType) {
                case 'priority': {
                    const priorityA = priorityOrder[a.dataset.priority] || 0;
                    const priorityB = priorityOrder[b.dataset.priority] || 0;
                    return priorityB - priorityA; // High to low
                }
                
                case 'priority-reverse': {
                    const priorityA = priorityOrder[a.dataset.priority] || 0;
                    const priorityB = priorityOrder[b.dataset.priority] || 0;
                    return priorityA - priorityB; // Low to high
                }
                
                case 'due-date': {
                    const dateA = a.dataset.dueDate ? new Date(a.dataset.dueDate) : new Date('9999-12-31');
                    const dateB = b.dataset.dueDate ? new Date(b.dataset.dueDate) : new Date('9999-12-31');
                    return dateA - dateB; // Soonest first
                }
                
                case 'due-date-reverse': {
                    const dateA = a.dataset.dueDate ? new Date(a.dataset.dueDate) : new Date('1970-01-01');
                    const dateB = b.dataset.dueDate ? new Date(b.dataset.dueDate) : new Date('1970-01-01');
                    return dateB - dateA; // Latest first
                }
                
                case 'created': {
                    const idA = parseInt(a.dataset.taskId) || 0;
                    const idB = parseInt(b.dataset.taskId) || 0;
                    return idB - idA; // Newest first (higher IDs)
                }
                
                case 'created-reverse': {
                    const idA = parseInt(a.dataset.taskId) || 0;
                    const idB = parseInt(b.dataset.taskId) || 0;
                    return idA - idB; // Oldest first (lower IDs)
                }
                
                case 'title': {
                    const titleA = a.querySelector('.task-title')?.textContent.toLowerCase() || '';
                    const titleB = b.querySelector('.task-title')?.textContent.toLowerCase() || '';
                    return titleA.localeCompare(titleB); // A to Z
                }
                
                case 'title-reverse': {
                    const titleA = a.querySelector('.task-title')?.textContent.toLowerCase() || '';
                    const titleB = b.querySelector('.task-title')?.textContent.toLowerCase() || '';
                    return titleB.localeCompare(titleA); // Z to A
                }
                
                default:
                    return 0;
            }
        });
        
        return sorted;
    }
    
    updateCounts(visible = null, total = null) {
        if (visible === null) {
            const tasks = this.tasksContainer?.querySelectorAll('.task-card') || [];
            const visibleTasks = Array.from(tasks).filter(task => task.style.display !== 'none');
            visible = visibleTasks.length;
            total = tasks.length;
        }
        
        if (this.visibleCountEl) {
            this.visibleCountEl.textContent = visible;
        }
        
        if (this.totalCountEl) {
            this.totalCountEl.textContent = total;
        }
    }
    
    applyQuickFilterLogic(tasks, filter) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const nextWeek = new Date(today);
        nextWeek.setDate(nextWeek.getDate() + 7);
        
        return tasks.filter(task => {
            switch (filter) {
                case 'high-priority':
                    return task.dataset.priority === 'high';
                
                case 'today': {
                    const dueDateStr = task.dataset.dueDate;
                    if (!dueDateStr) return false;
                    const dueDate = new Date(dueDateStr);
                    dueDate.setHours(0, 0, 0, 0);
                    return dueDate.getTime() === today.getTime();
                }
                
                case 'this-week': {
                    const dueDateStr = task.dataset.dueDate;
                    if (!dueDateStr) return false;
                    const dueDate = new Date(dueDateStr);
                    dueDate.setHours(0, 0, 0, 0);
                    return dueDate >= today && dueDate < nextWeek;
                }
                
                case 'unassigned':
                    return !task.dataset.assignedTo || task.dataset.assignedTo === '';
                
                default:
                    return true;
            }
        });
    }
    
    // Public API for external updates
    refresh() {
        this.applyFiltersAndSort();
    }
    
    clearSearch() {
        this.searchInput.value = '';
        this.searchQuery = '';
        this.updateClearButton();
        this.applyFiltersAndSort();
    }
    
    setFilter(filter) {
        this.currentFilter = filter;
        this.applyFiltersAndSort();
    }
    
    setQuickFilter(filter) {
        this.quickFilter = filter;
        this.applyFiltersAndSort();
    }
    
    clearQuickFilter() {
        this.quickFilter = null;
        this.applyFiltersAndSort();
    }
}

// Initialize and expose globally
let taskSearchSort;
document.addEventListener('DOMContentLoaded', () => {
    taskSearchSort = new TaskSearchSort();
});

// Make available globally for other modules
window.TaskSearchSort = TaskSearchSort;
window.getTaskSearchSort = () => taskSearchSort;
