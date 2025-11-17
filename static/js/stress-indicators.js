/**
 * CROWN⁴.6 Stress Indicators
 * Detects overdue tasks and high workload, provides visual feedback
 */

class StressIndicators {
    constructor() {
        this.stressThreshold = 10; // Show amber dot when >10 pending tasks
        this.highStressThreshold = 20; // Red dot when >20 pending tasks
        this.init();
    }

    init() {
        console.log('[StressIndicators] Initializing...');
        
        // Mark overdue tasks on load
        this.markOverdueTasks();
        
        // Update stress indicator
        this.updateStressIndicator();
        
        // Listen for task updates
        document.addEventListener('tasks:updated', () => {
            this.markOverdueTasks();
            this.updateStressIndicator();
        });

        // Re-check every 60 seconds (in case tasks become overdue)
        setInterval(() => {
            this.markOverdueTasks();
            this.updateStressIndicator();
        }, 60000);

        console.log('[StressIndicators] Initialized');
    }

    /**
     * Mark overdue tasks with red glow
     */
    markOverdueTasks() {
        const now = new Date();
        const taskCards = document.querySelectorAll('.task-card');
        
        let overdueCount = 0;
        
        taskCards.forEach(card => {
            const dueDateStr = card.dataset.dueDate;
            
            if (!dueDateStr) {
                card.classList.remove('overdue');
                return;
            }
            
            const dueDate = new Date(dueDateStr);
            const isCompleted = card.classList.contains('completed');
            
            if (!isCompleted && dueDate < now) {
                card.classList.add('overdue');
                overdueCount++;
            } else {
                card.classList.remove('overdue');
            }
        });
        
        if (overdueCount > 0) {
            console.log(`[StressIndicators] ${overdueCount} overdue task(s) detected`);
        }
    }

    /**
     * Update stress indicator dot in header
     */
    updateStressIndicator() {
        const indicator = document.getElementById('stress-indicator');
        if (!indicator) {
            console.warn('[StressIndicators] Stress indicator element not found');
            return;
        }

        // Count pending tasks
        const pendingTasks = document.querySelectorAll('.task-card:not(.completed)').length;
        
        if (pendingTasks > this.stressThreshold) {
            indicator.classList.remove('hidden');
            
            // Update tooltip
            const tooltip = indicator.querySelector('.stress-tooltip');
            if (tooltip) {
                tooltip.textContent = `${pendingTasks} pending tasks`;
            }
            
            // High stress level
            if (pendingTasks > this.highStressThreshold) {
                indicator.classList.add('high-stress');
            } else {
                indicator.classList.remove('high-stress');
            }
            
            console.log(`[StressIndicators] High workload detected: ${pendingTasks} pending tasks`);
        } else {
            indicator.classList.add('hidden');
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.stressIndicators = new StressIndicators();
});
