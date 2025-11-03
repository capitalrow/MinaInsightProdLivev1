/**
 * CROWN⁴.5 Quick Actions Bar
 * Provides keyboard shortcuts, quick filters, and bulk actions in a sticky bar
 */

class QuickActionsBar {
    constructor() {
        this.bar = document.getElementById('quick-actions-bar');
        this.toggleBtn = document.getElementById('quick-actions-toggle');
        this.minimizeBtn = document.getElementById('quick-actions-minimize');
        this.isMinimized = localStorage.getItem('quickActionsMinimized') === 'true';
        
        this.init();
        console.log('[QuickActionsBar] Initialized');
    }
    
    init() {
        // Restore minimized state
        if (this.isMinimized) {
            this.bar?.classList.add('minimized');
        }
        
        // Minimize button handler
        this.minimizeBtn?.addEventListener('click', () => {
            this.toggleMinimized();
        });
        
        // Shortcut hint buttons
        document.querySelectorAll('.shortcut-hint').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                this.triggerShortcut(action);
            });
        });
        
        // Quick filter buttons
        document.querySelectorAll('.quick-filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const filter = btn.dataset.quickFilter;
                this.applyQuickFilter(filter, btn);
            });
        });
        
        // Bulk action buttons
        document.getElementById('quick-select-all')?.addEventListener('click', () => {
            this.selectAllTasks();
        });
        
        document.getElementById('quick-complete-selected')?.addEventListener('click', () => {
            this.completeSelectedTasks();
        });
    }
    
    toggleMinimized() {
        this.isMinimized = !this.isMinimized;
        this.bar?.classList.toggle('minimized');
        localStorage.setItem('quickActionsMinimized', this.isMinimized);
    }
    
    triggerShortcut(action) {
        console.log(`[QuickActionsBar] Triggering shortcut: ${action}`);
        
        switch (action) {
            case 'new-task':
                // Trigger new task creation
                document.querySelector('.btn-primary')?.click();
                break;
            
            case 'search':
                // Focus search input
                const searchInput = document.getElementById('task-search-input');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
                break;
            
            case 'command-palette':
                // Trigger command palette if keyboard shortcuts module is available
                if (window.taskShortcuts) {
                    window.taskShortcuts._handleCommandPalette();
                } else {
                    console.warn('Command palette not available');
                }
                break;
            
            case 'help':
                // Show help dialog
                if (window.taskShortcuts) {
                    window.taskShortcuts._handleHelp();
                } else {
                    this.showQuickHelp();
                }
                break;
        }
    }
    
    applyQuickFilter(filter, buttonEl) {
        console.log(`[QuickActionsBar] Applying quick filter: ${filter}`);
        
        // Check if clicking the same filter again BEFORE removing classes
        const isSameFilter = buttonEl.classList.contains('active');
        
        // Remove active state from all quick filter buttons
        document.querySelectorAll('.quick-filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        if (isSameFilter) {
            // Clear the quick filter (toggle off)
            this.clearQuickFilter();
            
            // Show toast notification
            if (window.showToast) {
                window.showToast('Quick filter cleared', 'info');
            }
        } else {
            // Add active state to clicked button
            buttonEl.classList.add('active');
            
            // Use TaskSearchSort API to apply filter
            const taskSearchSort = window.getTaskSearchSort?.();
            if (taskSearchSort) {
                taskSearchSort.setQuickFilter(filter);
            } else {
                console.warn('[QuickActionsBar] TaskSearchSort not available');
            }
            
            // Show toast notification
            if (window.showToast) {
                window.showToast(`Filter applied: ${filter.replace('-', ' ')}`, 'info');
            }
        }
    }
    
    selectAllTasks() {
        console.log('[QuickActionsBar] Selecting all tasks');
        
        // Trigger bulk operations select all if available
        if (window.TaskBulkOperations?.selectAll) {
            window.TaskBulkOperations.selectAll();
        } else {
            // Fallback: manually select all visible tasks
            const checkboxes = document.querySelectorAll('.task-card:not([style*="display: none"]) .task-checkbox');
            checkboxes.forEach(cb => {
                if (!cb.checked) {
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        }
    }
    
    completeSelectedTasks() {
        console.log('[QuickActionsBar] Completing selected tasks');
        
        // Trigger bulk complete if available
        const bulkCompleteBtn = document.getElementById('bulk-complete-btn');
        if (bulkCompleteBtn) {
            bulkCompleteBtn.click();
        } else {
            console.warn('Bulk complete button not found');
        }
    }
    
    showQuickHelp() {
        // Simple fallback help dialog
        const helpText = `
Keyboard Shortcuts:
- N: Create new task
- /: Focus search
- Cmd/Ctrl + K: Open command palette
- ?: Show this help
- Escape: Close dialogs
- ↑/↓: Navigate tasks
        `.trim();
        
        if (window.showToast) {
            window.showToast(helpText, 'info', 5000);
        } else {
            alert(helpText);
        }
    }
    
    // Public API to clear active quick filter
    clearQuickFilter() {
        document.querySelectorAll('.quick-filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Use TaskSearchSort API to clear filter
        const taskSearchSort = window.getTaskSearchSort?.();
        if (taskSearchSort) {
            taskSearchSort.clearQuickFilter();
        }
    }
}

// Initialize on DOM ready
let quickActionsBar;
document.addEventListener('DOMContentLoaded', () => {
    quickActionsBar = new QuickActionsBar();
});

// Make available globally
window.QuickActionsBar = QuickActionsBar;
window.getQuickActionsBar = () => quickActionsBar;
