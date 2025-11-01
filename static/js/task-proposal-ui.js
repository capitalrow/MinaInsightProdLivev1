class TaskProposalUI {
    constructor(taskUI) {
        this.taskUI = taskUI;
        this.init();
        console.log('[TaskProposalUI] Initialized');
    }

    init() {
        document.addEventListener('click', async (e) => {
            if (e.target.classList.contains('btn-accept-proposal')) {
                const taskId = e.target.dataset.taskId;
                await this.acceptProposal(taskId, e.target);
            } else if (e.target.classList.contains('btn-reject-proposal')) {
                const taskId = e.target.dataset.taskId;
                await this.rejectProposal(taskId, e.target);
            }
        });
    }

    async acceptProposal(taskId, button) {
        const card = button.closest('.task-card');
        if (!card) return;

        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = 'Accepting...';

        try {
            const response = await fetch(`/api/tasks/${taskId}/accept`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (result.success) {
                if (window.EmotionalAnimations) {
                    window.EmotionalAnimations.playAnimation(card, 'burst', 'positive');
                }

                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('task_proposal_accepted', 1);
                }

                setTimeout(() => {
                    card.classList.remove('ai-proposal');
                    card.dataset.emotionalState = 'accepted';
                    
                    const badge = card.querySelector('.ai-proposal-badge');
                    if (badge) {
                        const checkboxWrapper = document.createElement('div');
                        checkboxWrapper.className = 'task-checkbox-wrapper';
                        checkboxWrapper.innerHTML = `
                            <input type="checkbox" 
                                   class="task-checkbox" 
                                   data-task-id="${taskId}">
                        `;
                        badge.replaceWith(checkboxWrapper);
                    }

                    const actions = card.querySelector('.ai-proposal-actions');
                    if (actions) {
                        actions.remove();
                    }
                }, 500);
            } else {
                throw new Error(result.message || 'Failed to accept proposal');
            }
        } catch (error) {
            console.error('Failed to accept proposal:', error);
            button.textContent = originalText;
            button.disabled = false;

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_proposal_accept_failure', 1);
            }

            alert('Failed to accept task proposal. Please try again.');
        }
    }

    async rejectProposal(taskId, button) {
        const card = button.closest('.task-card');
        if (!card) return;

        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = 'Rejecting...';

        try {
            const response = await fetch(`/api/tasks/${taskId}/reject`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (result.success) {
                if (window.EmotionalAnimations) {
                    window.EmotionalAnimations.playAnimation(card, 'slide', 'neutral');
                }

                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('task_proposal_rejected', 1);
                }

                setTimeout(() => {
                    card.style.opacity = '0';
                    setTimeout(() => {
                        card.remove();
                    }, 300);
                }, 500);
            } else {
                throw new Error(result.message || 'Failed to reject proposal');
            }
        } catch (error) {
            console.error('Failed to reject proposal:', error);
            button.textContent = originalText;
            button.disabled = false;

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_proposal_reject_failure', 1);
            }

            alert('Failed to reject task proposal. Please try again.');
        }
    }
}

window.TaskProposalUI = TaskProposalUI;
