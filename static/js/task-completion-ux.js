/**
 * CROWN⁴.6 Task 5: Perfect Completion UX
 * 
 * Satisfying completion animations, intelligent recommendations,
 * undo functionality, and progress celebrations.
 * 
 * Features:
 * - Confetti particle burst on completion
 * - Smooth fade-out with celebration
 * - Intelligent next-task recommendations
 * - Graceful undo with reversal animation
 * - Progress milestones (streaks, daily goals)
 */

class TaskCompletionUX {
    constructor() {
        this.canvas = null;
        this.ctx = null;
        this.particles = [];
        this.completionHistory = [];
        this.undoStack = [];
        this.dailyCompletions = 0;
        this.currentStreak = 0;
        
        this.init();
    }
    
    init() {
        this.createCanvas();
        this.loadCompletionHistory();
        this.attachEventListeners();
        
        console.log('[CompletionUX] Initialized with celebration system');
    }
    
    /**
     * Create canvas for particle effects
     */
    createCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.id = 'completion-canvas';
        this.canvas.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 9999;
        `;
        document.body.appendChild(this.canvas);
        
        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
        
        window.addEventListener('resize', () => this.resizeCanvas());
    }
    
    resizeCanvas() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    /**
     * Attach event listeners for completion
     */
    attachEventListeners() {
        window.addEventListener('task:completed', (e) => {
            this.handleCompletion(e.detail);
        });
        
        // Listen for keyboard undo (Ctrl+Z / Cmd+Z)
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
                if (this.undoStack.length > 0) {
                    e.preventDefault();
                    this.undoLastCompletion();
                }
            }
        });
    }
    
    /**
     * Handle task completion with full UX treatment
     */
    async handleCompletion(detail) {
        const { taskId, task } = detail;
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        
        if (!card) return;
        
        // Add to undo stack
        this.undoStack.push({ taskId, task, timestamp: Date.now() });
        
        // Trim undo stack to last 10 completions
        if (this.undoStack.length > 10) {
            this.undoStack.shift();
        }
        
        // Track completion history
        this.completionHistory.push({
            taskId,
            completedAt: new Date().toISOString()
        });
        this.dailyCompletions++;
        this.saveCompletionHistory();
        
        // Step 1: Celebration animation
        await this.celebrateCompletion(card, task);
        
        // Step 2: Show undo notification
        this.showUndoNotification(taskId, task);
        
        // Step 3: Check for milestones
        this.checkMilestones();
        
        // Step 4: Show intelligent recommendations (after 500ms)
        setTimeout(() => {
            this.showRecommendations(task);
        }, 500);
    }
    
    /**
     * Celebrate task completion with confetti and animations
     */
    async celebrateCompletion(card, task) {
        const rect = card.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        // Launch confetti particles
        this.launchConfetti(centerX, centerY, task.priority);
        
        // Add completion animation class
        card.classList.add('celebrating-completion');
        
        // Wait for animation
        await new Promise(resolve => setTimeout(resolve, 600));
        
        card.classList.remove('celebrating-completion');
    }
    
    /**
     * Launch confetti particles from completion point
     */
    launchConfetti(x, y, priority = 'medium') {
        const particleCount = priority === 'high' ? 40 : priority === 'medium' ? 25 : 15;
        const colors = this.getConfettiColors(priority);
        
        for (let i = 0; i < particleCount; i++) {
            const angle = (Math.PI * 2 * i) / particleCount;
            const velocity = 3 + Math.random() * 4;
            
            this.particles.push({
                x,
                y,
                vx: Math.cos(angle) * velocity,
                vy: Math.sin(angle) * velocity - 2, // Upward bias
                gravity: 0.15,
                life: 1,
                decay: 0.015 + Math.random() * 0.01,
                size: 4 + Math.random() * 4,
                color: colors[Math.floor(Math.random() * colors.length)],
                rotation: Math.random() * Math.PI * 2,
                rotationSpeed: (Math.random() - 0.5) * 0.2
            });
        }
        
        // Start animation loop if not already running
        if (this.particles.length === particleCount) {
            this.animateParticles();
        }
    }
    
    /**
     * Get confetti colors based on task priority
     */
    getConfettiColors(priority) {
        const colorSets = {
            high: ['#EF4444', '#F59E0B', '#FBBF24', '#FCD34D'],
            medium: ['#8B5CF6', '#A78BFA', '#C4B5FD', '#DDD6FE'],
            low: ['#10B981', '#34D399', '#6EE7B7', '#A7F3D0']
        };
        
        return colorSets[priority] || colorSets.medium;
    }
    
    /**
     * Animate confetti particles
     */
    animateParticles() {
        if (this.particles.length === 0) return;
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Update and draw particles
        this.particles = this.particles.filter(p => {
            // Update physics
            p.vy += p.gravity;
            p.x += p.vx;
            p.y += p.vy;
            p.rotation += p.rotationSpeed;
            p.life -= p.decay;
            
            // Draw particle
            if (p.life > 0) {
                this.ctx.save();
                this.ctx.globalAlpha = p.life;
                this.ctx.translate(p.x, p.y);
                this.ctx.rotate(p.rotation);
                this.ctx.fillStyle = p.color;
                this.ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
                this.ctx.restore();
            }
            
            // Keep particle if still alive
            return p.life > 0;
        });
        
        // Continue animation loop
        if (this.particles.length > 0) {
            requestAnimationFrame(() => this.animateParticles());
        }
    }
    
    /**
     * Show undo notification with toast
     */
    showUndoNotification(taskId, task) {
        const toast = document.createElement('div');
        toast.className = 'completion-undo-toast';
        toast.innerHTML = `
            <div class="undo-toast-content">
                <span class="undo-icon">✓</span>
                <span class="undo-message">Task completed</span>
                <button class="undo-button" data-task-id="${taskId}">
                    Undo
                </button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => {
            toast.classList.add('visible');
        });
        
        // Handle undo click
        const undoBtn = toast.querySelector('.undo-button');
        undoBtn.addEventListener('click', () => {
            this.undoCompletion(taskId);
            toast.remove();
        });
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove('visible');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }
    
    /**
     * Undo the last completion
     */
    async undoLastCompletion() {
        if (this.undoStack.length === 0) return;
        
        const last = this.undoStack[this.undoStack.length - 1];
        await this.undoCompletion(last.taskId);
    }
    
    /**
     * Undo a specific task completion
     */
    async undoCompletion(taskId) {
        // Find in undo stack
        const index = this.undoStack.findIndex(item => item.taskId === taskId);
        if (index === -1) return;
        
        const item = this.undoStack[index];
        this.undoStack.splice(index, 1);
        
        // Optimistically update UI
        if (window.optimisticUI) {
            await window.optimisticUI.toggleTaskStatus(taskId);
        }
        
        // Show reversal animation
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (card) {
            card.classList.add('undoing-completion');
            await new Promise(resolve => setTimeout(resolve, 400));
            card.classList.remove('undoing-completion');
        }
        
        // Update history
        this.dailyCompletions = Math.max(0, this.dailyCompletions - 1);
        
        console.log(`[CompletionUX] Undid completion for task ${taskId}`);
    }
    
    /**
     * Check and celebrate milestones
     */
    checkMilestones() {
        const milestones = [
            { count: 5, message: '🎯 5 tasks completed today!' },
            { count: 10, message: '🔥 10 tasks - You\'re on fire!' },
            { count: 20, message: '⚡ 20 tasks - Unstoppable!' },
            { count: 50, message: '🏆 50 tasks - Legendary!' }
        ];
        
        const milestone = milestones.find(m => m.count === this.dailyCompletions);
        
        if (milestone) {
            this.showMilestoneCelebration(milestone);
        }
    }
    
    /**
     * Show milestone celebration
     */
    showMilestoneCelebration(milestone) {
        const toast = document.createElement('div');
        toast.className = 'milestone-toast';
        toast.innerHTML = `
            <div class="milestone-content">
                <div class="milestone-message">${milestone.message}</div>
                <div class="milestone-subtext">Keep up the momentum!</div>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => {
            toast.classList.add('visible');
        });
        
        // Launch extra confetti for milestone
        const centerX = window.innerWidth / 2;
        const centerY = window.innerHeight / 2;
        this.launchConfetti(centerX, centerY, 'high');
        
        // Auto-remove after 4 seconds
        setTimeout(() => {
            toast.classList.remove('visible');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
    
    /**
     * Show intelligent next-task recommendations
     */
    async showRecommendations(completedTask) {
        if (!window.tasks || window.tasks.length === 0) return;
        
        // Get pending tasks
        const pending = window.tasks.filter(t => t.status !== 'completed');
        if (pending.length === 0) {
            this.showAllDoneMessage();
            return;
        }
        
        // Intelligent recommendation logic
        const recommendations = this.getSmartRecommendations(completedTask, pending);
        
        if (recommendations.length > 0) {
            this.showRecommendationCard(recommendations.slice(0, 3));
        }
    }
    
    /**
     * Get smart task recommendations based on context
     */
    getSmartRecommendations(completedTask, pendingTasks) {
        const scored = pendingTasks.map(task => {
            let score = 0;
            
            // Same meeting = high relevance
            if (task.meeting_id === completedTask.meeting_id) {
                score += 50;
            }
            
            // Same assignee
            if (task.assigned_to === completedTask.assigned_to) {
                score += 20;
            }
            
            // High priority tasks
            if (task.priority === 'high') {
                score += 30;
            } else if (task.priority === 'medium') {
                score += 15;
            }
            
            // Due soon (within 7 days)
            if (task.due_date) {
                const daysUntilDue = (new Date(task.due_date) - new Date()) / (1000 * 60 * 60 * 24);
                if (daysUntilDue < 7 && daysUntilDue > 0) {
                    score += 25;
                }
            }
            
            // Impact score
            if (task.impact_score) {
                score += task.impact_score * 0.5;
            }
            
            return { task, score };
        });
        
        // Sort by score and return tasks
        scored.sort((a, b) => b.score - a.score);
        return scored.map(item => item.task);
    }
    
    /**
     * Show recommendation card
     */
    showRecommendationCard(tasks) {
        const card = document.createElement('div');
        card.className = 'recommendation-card';
        card.innerHTML = `
            <div class="recommendation-header">
                <span class="recommendation-icon">💡</span>
                <h3>What's next?</h3>
                <button class="recommendation-close">×</button>
            </div>
            <div class="recommendation-list">
                ${tasks.map(task => `
                    <div class="recommendation-item" data-task-id="${task.id}">
                        <div class="recommendation-task-info">
                            <div class="recommendation-task-title">${this.escapeHtml(task.title)}</div>
                            <div class="recommendation-task-meta">
                                ${task.meeting?.title ? `📅 ${this.escapeHtml(task.meeting.title)}` : ''}
                                ${task.priority ? `<span class="priority-badge priority-${task.priority}">${task.priority}</span>` : ''}
                            </div>
                        </div>
                        <button class="recommendation-action" data-task-id="${task.id}">
                            Start
                        </button>
                    </div>
                `).join('')}
            </div>
        `;
        
        document.body.appendChild(card);
        
        // Animate in
        requestAnimationFrame(() => {
            card.classList.add('visible');
        });
        
        // Handle close
        card.querySelector('.recommendation-close').addEventListener('click', () => {
            card.classList.remove('visible');
            setTimeout(() => card.remove(), 300);
        });
        
        // Handle task actions
        card.querySelectorAll('.recommendation-action').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const taskId = e.target.dataset.taskId;
                
                // Update status to in_progress
                if (window.optimisticUI) {
                    await window.optimisticUI.updateTask(taskId, { status: 'in_progress' });
                }
                
                // Close recommendations
                card.classList.remove('visible');
                setTimeout(() => card.remove(), 300);
            });
        });
        
        // Auto-close after 10 seconds
        setTimeout(() => {
            if (card.parentNode) {
                card.classList.remove('visible');
                setTimeout(() => card.remove(), 300);
            }
        }, 10000);
    }
    
    /**
     * Show "all done" message when no tasks remain
     */
    showAllDoneMessage() {
        const toast = document.createElement('div');
        toast.className = 'all-done-toast';
        toast.innerHTML = `
            <div class="all-done-content">
                <div class="all-done-icon">🎉</div>
                <div class="all-done-message">All caught up!</div>
                <div class="all-done-subtext">No more tasks to complete</div>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => {
            toast.classList.add('visible');
        });
        
        // Extra celebration
        const centerX = window.innerWidth / 2;
        const centerY = window.innerHeight / 2;
        this.launchConfetti(centerX, centerY, 'high');
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove('visible');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }
    
    /**
     * Load completion history from localStorage
     */
    loadCompletionHistory() {
        try {
            const stored = localStorage.getItem('mina_completion_history');
            if (stored) {
                const history = JSON.parse(stored);
                const today = new Date().toDateString();
                
                // Filter to today's completions
                this.completionHistory = history.filter(item => {
                    const itemDate = new Date(item.completedAt).toDateString();
                    return itemDate === today;
                });
                
                this.dailyCompletions = this.completionHistory.length;
            }
        } catch (error) {
            console.error('[CompletionUX] Failed to load history:', error);
        }
    }
    
    /**
     * Save completion history to localStorage
     */
    saveCompletionHistory() {
        try {
            // Keep only last 100 completions
            const trimmed = this.completionHistory.slice(-100);
            localStorage.setItem('mina_completion_history', JSON.stringify(trimmed));
        } catch (error) {
            console.error('[CompletionUX] Failed to save history:', error);
        }
    }
    
    /**
     * Escape HTML for safe rendering
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize globally when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.taskCompletionUX = new TaskCompletionUX();
    });
} else {
    // DOM already loaded
    window.taskCompletionUX = new TaskCompletionUX();
}
