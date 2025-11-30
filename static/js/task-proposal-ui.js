class TaskProposalUI {
    constructor(taskUI) {
        this.taskUI = taskUI;
        this.currentStream = null;
        this.currentAbortController = null;
        this.proposalContainer = null;
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
            } else if (e.target.classList.contains('btn-generate-proposals')) {
                await this.startProposalStream(e.target);
            } else if (e.target.classList.contains('btn-stop-stream')) {
                this.stopStream();
            }
        });
    }

    async startProposalStream(button) {
        const meetingId = button.dataset.meetingId;
        
        // Meeting ID is optional - if not provided, uses workspace context
        const requestBody = {
            max_proposals: 3
        };
        
        if (meetingId && meetingId.trim() !== '') {
            requestBody.meeting_id = parseInt(meetingId);
            console.log('[TaskProposalUI] Generating proposals for meeting:', meetingId);
        } else {
            console.log('[TaskProposalUI] Generating proposals from workspace context');
        }

        // Disable button during generation
        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = 'Generating...';

        try {
            console.log('[TaskProposalUI] Starting proposal generation...');
            
            // Create or show proposal container
            this.showProposalContainer();

            // Show streaming indicator
            this.showStreamingState();

            // Create AbortController for cancellation
            this.currentAbortController = new AbortController();

            console.log('[TaskProposalUI] Calling /api/tasks/ai-proposals/stream...');

            // Start SSE stream
            const response = await fetch('/api/tasks/ai-proposals/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody),
                signal: this.currentAbortController.signal
            });

            console.log('[TaskProposalUI] Response status:', response.status, response.statusText);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[TaskProposalUI] API error response:', errorText);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Read SSE stream
            const reader = response.body.getReader();
            this.currentStream = reader;
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.substring(6));
                        this.handleStreamEvent(data);
                    }
                }
            }

            // Complete
            this.hideStreamingState();
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('ai_proposals_generated', 1);
            }

        } catch (error) {
            // Handle abort gracefully
            if (error.name === 'AbortError') {
                console.log('[TaskProposalUI] Stream cancelled by user');
                this.hideStreamingState();
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('ai_proposals_cancelled', 1);
                }
            } else {
                console.error('[TaskProposalUI] Stream error:', error);
                this.showError('Failed to generate proposals. Please try again.');
                
                // Show toast for user feedback
                if (window.toast && typeof window.toast.error === 'function') {
                    window.toast.error('Failed to generate AI proposals');
                } else if (window.toastManager && typeof window.toastManager.show === 'function') {
                    window.toastManager.show('Failed to generate AI proposals', 'error', 3000);
                }
                
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('ai_proposals_error', 1);
                }
            }
        } finally {
            // Clean up state
            this.currentAbortController = null;
            this.currentStream = null;
            button.disabled = false;
            button.textContent = originalText;
        }
    }

    stopStream() {
        console.log('[TaskProposalUI] Stopping stream');
        
        // Abort the fetch request
        if (this.currentAbortController) {
            this.currentAbortController.abort();
            this.currentAbortController = null;
        }
        
        // Cancel the reader
        if (this.currentStream) {
            this.currentStream.cancel().catch(err => {
                console.warn('[TaskProposalUI] Reader cancel error:', err);
            });
            this.currentStream = null;
        }
        
        // Clean up UI
        this.hideStreamingState();
        
        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('ai_proposals_cancelled', 1);
        }
        
        console.log('[TaskProposalUI] Stream stopped successfully');
    }

    showProposalContainer() {
        // Find existing container first (placed in HTML template)
        let container = document.getElementById('ai-proposals-container');
        
        if (!container) {
            // Try to find tasks page container with multiple possible selectors
            const tasksPage = document.querySelector('.tasks-container') || 
                              document.querySelector('.tasks-page-content') ||
                              document.querySelector('.container');
            
            if (tasksPage) {
                container = document.createElement('div');
                container.id = 'ai-proposals-container';
                container.className = 'ai-proposals-section glass-card';
                container.style.cssText = 'margin-bottom: 1.5rem; padding: 1rem; border-radius: 12px; background: var(--card-bg, #fff); box-shadow: 0 2px 8px rgba(0,0,0,0.1);';
                container.innerHTML = `
                    <div class="proposals-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                        <h3 class="proposals-title" style="margin: 0; font-size: 1.1rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem;">
                            <svg class="ai-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                                <polyline points="7.5 4.21 12 6.81 16.5 4.21"/>
                                <polyline points="7.5 19.79 7.5 14.6 3 12"/>
                                <polyline points="21 12 16.5 14.6 16.5 19.79"/>
                                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                                <line x1="12" y1="22.08" x2="12" y2="12"/>
                            </svg>
                            AI Suggestions
                        </h3>
                        <button class="btn-stop-stream btn-icon-sm" style="display: none; padding: 0.25rem 0.5rem; border: none; background: var(--bg-secondary, #f5f5f7); border-radius: 6px; cursor: pointer;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <rect x="6" y="6" width="12" height="12" rx="2"/>
                            </svg>
                        </button>
                    </div>
                    <div class="proposals-content"></div>
                    <div class="streaming-indicator" style="display: none; align-items: center; gap: 0.5rem; padding: 1rem; color: var(--text-secondary, #6b7280);">
                        <div class="streaming-dots" style="display: flex; gap: 0.25rem;">
                            <span style="width: 8px; height: 8px; background: var(--primary, #6366f1); border-radius: 50%; animation: streaming-dot 1.4s infinite ease-in-out;"></span>
                            <span style="width: 8px; height: 8px; background: var(--primary, #6366f1); border-radius: 50%; animation: streaming-dot 1.4s infinite ease-in-out 0.2s;"></span>
                            <span style="width: 8px; height: 8px; background: var(--primary, #6366f1); border-radius: 50%; animation: streaming-dot 1.4s infinite ease-in-out 0.4s;"></span>
                        </div>
                        <span class="streaming-text">Analyzing meeting content...</span>
                    </div>
                `;
                
                // Insert after the search toolbar or at the start of tasks container
                const searchToolbar = tasksPage.querySelector('.search-sort-toolbar');
                const taskFilters = tasksPage.querySelector('.task-filters');
                
                if (searchToolbar && searchToolbar.parentNode === tasksPage) {
                    searchToolbar.insertAdjacentElement('afterend', container);
                } else if (taskFilters && taskFilters.parentNode === tasksPage) {
                    taskFilters.insertAdjacentElement('afterend', container);
                } else {
                    tasksPage.insertBefore(container, tasksPage.firstChild);
                }
                
                console.log('[TaskProposalUI] Created proposals container');
            } else {
                console.error('[TaskProposalUI] Could not find tasks page container');
                return;
            }
        }

        this.proposalContainer = container;
        container.style.display = 'block';
        console.log('[TaskProposalUI] Proposals container shown');
    }

    showStreamingState() {
        if (!this.proposalContainer) return;
        
        const indicator = this.proposalContainer.querySelector('.streaming-indicator');
        const stopBtn = this.proposalContainer.querySelector('.btn-stop-stream');
        
        if (indicator) indicator.style.display = 'flex';
        if (stopBtn) stopBtn.style.display = 'block';

        // Clear previous proposals
        const content = this.proposalContainer.querySelector('.proposals-content');
        if (content) content.innerHTML = '';
    }

    hideStreamingState() {
        if (!this.proposalContainer) return;
        
        const indicator = this.proposalContainer.querySelector('.streaming-indicator');
        const stopBtn = this.proposalContainer.querySelector('.btn-stop-stream');
        
        if (indicator) indicator.style.display = 'none';
        if (stopBtn) stopBtn.style.display = 'none';
    }

    handleStreamEvent(data) {
        switch (data.type) {
            case 'chunk':
                // Update streaming text (optional: show live text accumulation)
                break;
            
            case 'proposal':
                this.renderProposal(data.task);
                break;
            
            case 'done':
                this.hideStreamingState();
                break;
            
            case 'error':
                this.showError(data.message);
                this.hideStreamingState();
                break;
        }
    }

    renderProposal(task) {
        if (!this.proposalContainer) return;

        const content = this.proposalContainer.querySelector('.proposals-content');
        if (!content) return;

        const proposalCard = document.createElement('div');
        proposalCard.className = 'task-card ai-proposal proposal-enter';
        proposalCard.innerHTML = `
            <div class="ai-proposal-badge">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                </svg>
                AI
            </div>
            <div class="task-content">
                <input type="text" 
                       class="task-title-input proposal-title" 
                       value="${this.escapeHtml(task.title)}" 
                       readonly>
                ${task.description ? `<div class="task-description">${this.escapeHtml(task.description)}</div>` : ''}
                <div class="task-meta">
                    <span class="priority-badge priority-${task.priority || 'medium'}">
                        ${task.priority || 'medium'}
                    </span>
                    ${task.category ? `<span class="category-badge">${this.escapeHtml(task.category)}</span>` : ''}
                </div>
            </div>
            <div class="ai-proposal-actions">
                <button class="btn-accept-proposal btn-sm btn-primary" data-proposal='${JSON.stringify(task)}'>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    Accept
                </button>
                <button class="btn-reject-proposal btn-sm btn-ghost" data-proposal='${JSON.stringify(task)}'>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Reject
                </button>
            </div>
        `;

        content.appendChild(proposalCard);

        // Trigger entrance animation
        setTimeout(() => proposalCard.classList.add('proposal-visible'), 50);

        if (window.EmotionalAnimations) {
            window.EmotionalAnimations.playAnimation(proposalCard, 'slide', 'positive');
        }
    }

    showError(message) {
        if (!this.proposalContainer) return;

        const content = this.proposalContainer.querySelector('.proposals-content');
        if (!content) return;

        content.innerHTML = `
            <div class="error-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <p>${this.escapeHtml(message)}</p>
            </div>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async acceptProposal(taskId, button) {
        const card = button.closest('.task-card');
        if (!card) return;

        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = 'Accepting...';

        try {
            // Check if this is a new proposal (no taskId)
            const proposalData = button.dataset.proposal;
            let result;

            if (taskId) {
                // Existing task - just accept
                const response = await fetch(`/api/tasks/${taskId}/accept`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                result = await response.json();
            } else if (proposalData) {
                // New proposal - create task
                const proposal = JSON.parse(proposalData);
                const response = await fetch('/api/tasks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: proposal.title,
                        description: proposal.description || '',
                        priority: proposal.priority || 'medium',
                        category: proposal.category || '',
                        status: 'todo',
                        meeting_id: this.getCurrentMeetingId()
                    })
                });
                result = await response.json();
            } else {
                throw new Error('No task ID or proposal data');
            }

            if (result.success) {
                if (window.EmotionalAnimations) {
                    window.EmotionalAnimations.playAnimation(card, 'burst', 'positive');
                }

                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('task_proposal_accepted', 1);
                }

                // Remove card from proposals section
                setTimeout(() => {
                    card.style.opacity = '0';
                    setTimeout(() => {
                        card.remove();
                        
                        // Check if proposals section is empty
                        if (this.proposalContainer) {
                            const content = this.proposalContainer.querySelector('.proposals-content');
                            if (content && content.children.length === 0) {
                                this.proposalContainer.style.display = 'none';
                            }
                        }
                    }, 300);
                }, 500);

                // Show toast notification
                if (window.ToastNotifications) {
                    window.ToastNotifications.show('Task added successfully', 'success');
                }
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

            if (window.ToastNotifications) {
                window.ToastNotifications.show('Failed to add task', 'error');
            } else {
                alert('Failed to accept task proposal. Please try again.');
            }
        }
    }

    async rejectProposal(taskId, button) {
        const card = button.closest('.task-card');
        if (!card) return;

        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = 'Rejecting...';

        try {
            // Check if this is a new proposal (no taskId)
            const proposalData = button.dataset.proposal;
            let result;

            if (taskId) {
                // Existing task - reject via API
                const response = await fetch(`/api/tasks/${taskId}/reject`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                result = await response.json();
            } else if (proposalData) {
                // New proposal - just remove from UI
                result = { success: true };
            } else {
                throw new Error('No task ID or proposal data');
            }

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
                        
                        // Check if proposals section is empty
                        if (this.proposalContainer) {
                            const content = this.proposalContainer.querySelector('.proposals-content');
                            if (content && content.children.length === 0) {
                                this.proposalContainer.style.display = 'none';
                            }
                        }
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

    getCurrentMeetingId() {
        // Extract meeting ID from page context or button dataset
        const button = document.querySelector('.btn-generate-proposals');
        return button ? parseInt(button.dataset.meetingId) : null;
    }
}

window.TaskProposalUI = TaskProposalUI;
