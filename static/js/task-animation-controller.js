/**
 * CROWN⁴.6: Task Animation Controller
 * 
 * Wires up optimistic UI animations for task actions:
 * - Burst confetti on completion
 * - Glide away on deletion
 * - Snooze animation on snooze
 * 
 * Integrates with QuietStateManager to limit concurrent animations ≤3
 */
class TaskAnimationController {
    constructor() {
        this.init();
        console.log('[TaskAnimationController] Initialized');
    }

    init() {
        // Listen for task completion events
        window.addEventListener('task:completed', (e) => {
            this.animateCompletion(e.detail.taskId);
        });

        // Listen for task deletion events
        window.addEventListener('task:deleted', (e) => {
            this.animateDeletion(e.detail.taskId);
        });

        // Listen for task snooze events (if implemented)
        window.addEventListener('task:snoozed', (e) => {
            this.animateSnooze(e.detail.taskId);
        });

        // Listen for checkbox changes directly
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('task-checkbox')) {
                const taskId = e.target.dataset.taskId;
                if (e.target.checked) {
                    // Small delay to allow OptimisticUI to update first
                    setTimeout(() => this.animateCompletion(taskId), 50);
                }
            }
        });
    }

    /**
     * Animate task completion with burst confetti + fade
     */
    animateCompletion(taskId) {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!card) return;

        // Queue animations via QuietStateManager
        if (window.quietStateManager) {
            // Burst confetti first (high priority)
            window.quietStateManager.queueAnimation(
                () => {
                    this._burstConfetti(card);
                },
                {
                    priority: 9,
                    duration: 600,
                    metadata: { type: 'burst-confetti', taskId }
                }
            );

            // Then fade out the card
            window.quietStateManager.queueAnimation(
                () => {
                    card.classList.add('completing');
                },
                {
                    priority: 8,
                    duration: 600,
                    onComplete: () => {
                        card.classList.remove('completing');
                    },
                    metadata: { type: 'task-complete', taskId }
                }
            );
        } else {
            // Fallback if QuietStateManager not available
            this._burstConfetti(card);
            card.classList.add('completing');
            setTimeout(() => card.classList.remove('completing'), 600);
        }

        console.log(`[TaskAnimationController] Animated completion for task ${taskId}`);
    }

    /**
     * Animate task deletion with glide away
     */
    animateDeletion(taskId) {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!card) return;

        if (window.quietStateManager) {
            window.quietStateManager.queueAnimation(
                () => {
                    card.classList.add('deleting');
                },
                {
                    priority: 7,
                    duration: 400,
                    onComplete: () => {
                        card.remove();
                    },
                    metadata: { type: 'task-delete', taskId }
                }
            );
        } else {
            // Fallback
            card.classList.add('deleting');
            setTimeout(() => card.remove(), 400);
        }

        console.log(`[TaskAnimationController] Animated deletion for task ${taskId}`);
    }

    /**
     * Animate task snooze with upward float
     */
    animateSnooze(taskId) {
        const card = document.querySelector(`[data-task-id="${taskId}"]`);
        if (!card) return;

        if (window.quietStateManager) {
            window.quietStateManager.queueAnimation(
                () => {
                    card.classList.add('snoozing');
                },
                {
                    priority: 6,
                    duration: 500,
                    onComplete: () => {
                        card.classList.remove('snoozing');
                        // Hide snoozed tasks
                        card.style.display = 'none';
                    },
                    metadata: { type: 'task-snooze', taskId }
                }
            );
        } else {
            // Fallback
            card.classList.add('snoozing');
            setTimeout(() => {
                card.classList.remove('snoozing');
                card.style.display = 'none';
            }, 500);
        }

        console.log(`[TaskAnimationController] Animated snooze for task ${taskId}`);
    }

    /**
     * Burst confetti effect for task completion
     */
    _burstConfetti(element) {
        const rect = element.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        // Create 15 confetti particles
        for (let i = 0; i < 15; i++) {
            const particle = document.createElement('div');
            particle.className = 'confetti-particle';
            
            // Random colors from CROWN palette
            const colors = [
                '#10b981', // green
                '#3b82f6', // blue
                '#8b5cf6', // purple
                '#f59e0b', // amber
                '#ec4899'  // pink
            ];
            const color = colors[Math.floor(Math.random() * colors.length)];

            particle.style.cssText = `
                position: fixed;
                left: ${centerX}px;
                top: ${centerY}px;
                width: 8px;
                height: 8px;
                background: ${color};
                border-radius: 50%;
                pointer-events: none;
                z-index: 9999;
            `;
            document.body.appendChild(particle);

            // Calculate random trajectory
            const angle = (i / 15) * Math.PI * 2;
            const velocity = 120 + Math.random() * 80;
            const dx = Math.cos(angle) * velocity;
            const dy = Math.sin(angle) * velocity - 50; // Upward bias

            // Animate particle
            particle.animate([
                { 
                    transform: 'translate(0, 0) scale(1) rotate(0deg)', 
                    opacity: 1 
                },
                { 
                    transform: `translate(${dx}px, ${dy}px) scale(0.3) rotate(${Math.random() * 360}deg)`, 
                    opacity: 0 
                }
            ], {
                duration: 800 + Math.random() * 200,
                easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)'
            }).onfinish = () => particle.remove();
        }
    }
}

// Initialize on DOMContentLoaded
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        window.taskAnimationController = new TaskAnimationController();
        console.log('✅ TaskAnimationController initialized globally');
    });
}
