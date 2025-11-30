class TaskProposalUI {
    constructor(taskUI) {
        this.taskUI = taskUI;
        this.currentStream = null;
        this.currentAbortController = null;
        this.modal = null;
        this.proposals = [];
        this.isStreaming = false;
        this.streamTimeout = null;
        this.STREAM_TIMEOUT_MS = 30000;
        this.meetingId = null;
        this.meetingTitle = null;
        this.totalProposals = 0;
        this.acceptedCount = 0;
        this.metadataReceived = false;
        this.pendingProposals = [];
        this.buttonMeetingId = null;
        this.init();
    }

    init() {
        this.createModal();
        this.bindEvents();
        console.log('[TaskProposalUI] Initialized with modal');
    }

    createModal() {
        if (document.getElementById('ai-proposals-modal-overlay')) {
            this.modal = document.getElementById('ai-proposals-modal-overlay');
            return;
        }

        const overlay = document.createElement('div');
        overlay.id = 'ai-proposals-modal-overlay';
        overlay.className = 'ai-proposals-modal-overlay';
        overlay.innerHTML = `
            <div class="ai-proposals-modal" role="dialog" aria-labelledby="ai-proposals-title" aria-modal="true">
                <div class="ai-proposals-header">
                    <h2 id="ai-proposals-title" class="ai-proposals-title">
                        <svg class="ai-sparkle" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                        </svg>
                        AI Suggestions
                    </h2>
                    <button class="ai-proposals-close" aria-label="Close">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
                <div class="ai-proposals-body">
                    <div class="ai-proposals-content"></div>
                </div>
                <div class="ai-proposals-footer" style="display: none;">
                    <span class="proposals-count"></span>
                    <button class="btn-accept-all" disabled>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        Accept All
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        this.modal = overlay;

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.closeModal();
            }
        });

        const closeBtn = overlay.querySelector('.ai-proposals-close');
        closeBtn.addEventListener('click', () => this.closeModal());

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('visible')) {
                this.closeModal();
            }
        });
    }

    bindEvents() {
        document.addEventListener('click', async (e) => {
            const target = e.target.closest('button');
            if (!target) return;

            if (target.classList.contains('btn-generate-proposals')) {
                e.preventDefault();
                await this.startProposalStream(target);
            } else if (target.classList.contains('btn-accept-proposal')) {
                await this.acceptProposal(target);
            } else if (target.classList.contains('btn-reject-proposal')) {
                await this.rejectProposal(target);
            } else if (target.classList.contains('btn-accept-all')) {
                await this.acceptAllProposals();
            } else if (target.classList.contains('btn-retry')) {
                const generateBtn = document.querySelector('.btn-generate-proposals');
                if (generateBtn) {
                    await this.startProposalStream(generateBtn);
                }
            }
        });
    }

    openModal() {
        if (!this.modal) this.createModal();
        this.modal.classList.add('visible');
        document.body.style.overflow = 'hidden';
        
        const firstFocusable = this.modal.querySelector('button');
        if (firstFocusable) firstFocusable.focus();
    }

    closeModal() {
        if (this.isStreaming) {
            this.stopStream();
        }
        
        this.modal.classList.remove('visible');
        document.body.style.overflow = '';
        
        const generateBtn = document.querySelector('.btn-generate-proposals');
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.innerHTML = `
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                </svg>
                AI Proposals
            `;
        }
    }

    async startProposalStream(button) {
        const meetingId = button.dataset.meetingId;
        
        button.disabled = true;
        button.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin">
                <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="32"></circle>
            </svg>
            Generating...
        `;

        this.proposals = [];
        this.meetingId = null;
        this.meetingTitle = null;
        this.totalProposals = 0;
        this.acceptedCount = 0;
        this.metadataReceived = false;
        this.pendingProposals = [];
        this.buttonMeetingId = meetingId ? parseInt(meetingId) : null;
        this.openModal();
        this.showStreamingState();

        const requestBody = { max_proposals: 3 };
        if (meetingId && meetingId.trim() !== '') {
            requestBody.meeting_id = parseInt(meetingId);
        }

        try {
            this.currentAbortController = new AbortController();
            
            this.streamTimeout = setTimeout(() => {
                console.warn('[TaskProposalUI] Stream timeout reached');
                this.stopStream();
                this.showError('Request timed out. Please try again.');
            }, this.STREAM_TIMEOUT_MS);

            const response = await fetch('/api/tasks/ai-proposals/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody),
                signal: this.currentAbortController.signal
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.isStreaming = true;
            const reader = response.body.getReader();
            this.currentStream = reader;
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            this.handleStreamEvent(data);
                        } catch (e) {
                            console.warn('[TaskProposalUI] Parse error:', e);
                        }
                    }
                }
            }

            this.onStreamComplete();

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[TaskProposalUI] Stream aborted');
            } else {
                console.error('[TaskProposalUI] Stream error:', error);
                this.showError(error.message || 'Failed to generate proposals');
            }
        } finally {
            this.cleanup();
            button.disabled = false;
            button.innerHTML = `
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                </svg>
                AI Proposals
            `;
        }
    }

    stopStream() {
        if (this.currentAbortController) {
            this.currentAbortController.abort();
            this.currentAbortController = null;
        }
        
        if (this.currentStream) {
            this.currentStream.cancel().catch(() => {});
            this.currentStream = null;
        }
        
        this.cleanup();
    }

    cleanup() {
        if (this.streamTimeout) {
            clearTimeout(this.streamTimeout);
            this.streamTimeout = null;
        }
        this.isStreaming = false;
        this.currentAbortController = null;
        this.currentStream = null;
    }

    handleStreamEvent(data) {
        switch (data.type) {
            case 'metadata':
                this.meetingId = data.meeting_id;
                this.meetingTitle = data.meeting_title;
                this.metadataReceived = true;
                console.log('[TaskProposalUI] Meeting context:', this.meetingId, this.meetingTitle);
                
                if (this.pendingProposals.length > 0) {
                    console.log('[TaskProposalUI] Processing', this.pendingProposals.length, 'queued proposals');
                    this.pendingProposals.forEach(task => {
                        task.meeting_id = this.meetingId;
                        task.meeting_title = this.meetingTitle;
                        this.proposals.push(task);
                        this.totalProposals++;
                        this.renderProposal(task);
                    });
                    this.pendingProposals = [];
                }
                break;
            case 'proposal':
                if (data.task) {
                    if (this.metadataReceived) {
                        data.task.meeting_id = this.meetingId;
                        data.task.meeting_title = this.meetingTitle;
                        this.proposals.push(data.task);
                        this.totalProposals++;
                        this.renderProposal(data.task);
                    } else {
                        console.log('[TaskProposalUI] Queueing proposal until metadata received');
                        this.pendingProposals.push(data.task);
                    }
                }
                break;
            case 'done':
                if (!this.metadataReceived && this.pendingProposals.length > 0) {
                    console.log('[TaskProposalUI] No metadata received, using button meetingId:', this.buttonMeetingId);
                    this.meetingId = this.buttonMeetingId;
                    this.meetingTitle = null;
                    this.pendingProposals.forEach(task => {
                        task.meeting_id = this.meetingId;
                        task.meeting_title = this.meetingTitle;
                        this.proposals.push(task);
                        this.totalProposals++;
                        this.renderProposal(task);
                    });
                    this.pendingProposals = [];
                }
                this.onStreamComplete();
                break;
            case 'error':
                this.showError(data.message || 'An error occurred');
                break;
        }
    }

    showStreamingState() {
        const content = this.modal.querySelector('.ai-proposals-content');
        const footer = this.modal.querySelector('.ai-proposals-footer');
        
        content.innerHTML = `
            <div class="ai-proposals-streaming">
                <div class="streaming-animation">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
                <div class="streaming-text">Analyzing your meetings...</div>
                <div class="streaming-subtext">Generating actionable task suggestions</div>
            </div>
        `;
        
        footer.style.display = 'none';
    }

    renderProposal(task) {
        const content = this.modal.querySelector('.ai-proposals-content');
        
        const streamingEl = content.querySelector('.ai-proposals-streaming');
        if (streamingEl) {
            streamingEl.remove();
        }

        const index = this.proposals.length - 1;
        const card = document.createElement('div');
        card.className = 'ai-proposal-card';
        card.dataset.proposalIndex = index;
        
        const meetingSource = task.meeting_title 
            ? `<span class="meeting-source"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>${this.escapeHtml(task.meeting_title)}</span>`
            : '';
        
        card.innerHTML = `
            <div class="ai-proposal-header">
                <div class="ai-proposal-badge">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                    </svg>
                    AI Suggestion
                </div>
                ${meetingSource}
            </div>
            <h3 class="ai-proposal-title">${this.escapeHtml(task.title)}</h3>
            ${task.description ? `<p class="ai-proposal-description">${this.escapeHtml(task.description)}</p>` : ''}
            <div class="ai-proposal-meta">
                <span class="priority-pill ${task.priority || 'medium'}">${this.capitalizeFirst(task.priority || 'medium')} Priority</span>
                ${task.category ? `<span class="category-pill">${this.escapeHtml(task.category)}</span>` : ''}
            </div>
            <div class="ai-proposal-actions">
                <button class="btn-accept-proposal" data-proposal-index="${index}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    Accept
                </button>
                <button class="btn-reject-proposal" data-proposal-index="${index}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Dismiss
                </button>
            </div>
        `;

        content.appendChild(card);
        
        requestAnimationFrame(() => {
            card.classList.add('visible');
        });

        this.updateFooter();
    }

    onStreamComplete() {
        this.cleanup();
        
        const content = this.modal.querySelector('.ai-proposals-content');
        const streamingEl = content.querySelector('.ai-proposals-streaming');
        if (streamingEl) {
            streamingEl.remove();
        }

        if (this.proposals.length === 0) {
            this.showEmpty();
        }

        this.updateFooter();
    }

    updateFooter() {
        const footer = this.modal.querySelector('.ai-proposals-footer');
        const countEl = footer.querySelector('.proposals-count');
        const acceptAllBtn = footer.querySelector('.btn-accept-all');
        
        const activeProposals = this.modal.querySelectorAll('.ai-proposal-card:not(.accepted):not(.rejected)');
        const count = activeProposals.length;
        const acceptedCards = this.modal.querySelectorAll('.ai-proposal-card.accepted');
        
        if (count > 0) {
            footer.style.display = 'flex';
            if (acceptedCards.length > 0) {
                countEl.textContent = `${count} of ${this.totalProposals} remaining`;
            } else {
                countEl.textContent = `${count} suggestion${count !== 1 ? 's' : ''} available`;
            }
            acceptAllBtn.disabled = false;
        } else {
            footer.style.display = 'none';
        }
    }

    showEmpty() {
        const content = this.modal.querySelector('.ai-proposals-content');
        content.innerHTML = `
            <div class="ai-proposals-empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                </svg>
                <h4>No suggestions available</h4>
                <p>Try recording more meetings or adding existing tasks for better context.</p>
            </div>
        `;
    }
    
    showAllAccepted() {
        const content = this.modal.querySelector('.ai-proposals-content');
        const footer = this.modal.querySelector('.ai-proposals-footer');
        
        content.innerHTML = `
            <div class="ai-proposals-complete">
                <div class="complete-animation">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 11-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                </div>
                <h4>All done!</h4>
                <p>${this.acceptedCount} task${this.acceptedCount !== 1 ? 's' : ''} added to your list</p>
                <button class="btn-close-complete" onclick="this.closest('.ai-proposals-modal-overlay').classList.remove('visible'); document.body.style.overflow = '';">
                    Close
                </button>
            </div>
        `;
        
        footer.style.display = 'none';
    }

    showError(message) {
        const content = this.modal.querySelector('.ai-proposals-content');
        const footer = this.modal.querySelector('.ai-proposals-footer');
        
        content.innerHTML = `
            <div class="ai-proposals-error">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <h4>Something went wrong</h4>
                <p>${this.escapeHtml(message)}</p>
                <button class="btn-retry">Try Again</button>
            </div>
        `;
        
        footer.style.display = 'none';

        if (window.toast) {
            window.toast.error('Failed to generate AI proposals');
        }
    }

    async acceptProposal(button) {
        const index = parseInt(button.dataset.proposalIndex);
        const proposal = this.proposals[index];
        if (!proposal) return;

        const card = button.closest('.ai-proposal-card');
        button.disabled = true;
        button.classList.add('btn-loading');

        try {
            const taskData = {
                title: proposal.title,
                description: proposal.description || '',
                priority: proposal.priority || 'medium',
                status: 'todo',
                source: 'ai_proposal'
            };
            
            if (proposal.meeting_id) {
                taskData.meeting_id = proposal.meeting_id;
            }
            
            const response = await fetch('/api/tasks/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });

            if (!response.ok) {
                throw new Error('Failed to create task');
            }

            const data = await response.json();
            this.acceptedCount++;
            
            card.classList.add('accepted');
            card.innerHTML = `
                <div class="ai-proposal-success">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    <span>Task created: ${this.escapeHtml(proposal.title)}</span>
                </div>
            `;

            if (window.toast) {
                window.toast.success('Task created successfully');
            }

            if (window.taskCache && typeof window.taskCache.invalidate === 'function') {
                window.taskCache.invalidate();
            }

            if (this.taskUI && typeof this.taskUI.loadTasks === 'function') {
                this.taskUI.loadTasks();
            }

            this.updateFooter();
            
            const remainingCards = this.modal.querySelectorAll('.ai-proposal-card:not(.accepted):not(.rejected)');
            if (remainingCards.length === 0 && !this.isStreaming) {
                this.showAllAccepted();
            }

        } catch (error) {
            console.error('[TaskProposalUI] Accept error:', error);
            button.disabled = false;
            button.classList.remove('btn-loading');
            
            if (window.toast) {
                window.toast.error('Failed to create task');
            }
        }
    }

    async rejectProposal(button) {
        const card = button.closest('.ai-proposal-card');
        card.classList.add('rejected');
        
        setTimeout(() => {
            card.style.height = card.offsetHeight + 'px';
            card.style.overflow = 'hidden';
            requestAnimationFrame(() => {
                card.style.height = '0';
                card.style.padding = '0';
                card.style.margin = '0';
                card.style.opacity = '0';
            });
            
            setTimeout(() => {
                card.remove();
                this.updateFooter();
                
                const remainingCards = this.modal.querySelectorAll('.ai-proposal-card:not(.accepted):not(.rejected)');
                if (remainingCards.length === 0 && !this.isStreaming) {
                    this.showEmpty();
                }
            }, 300);
        }, 100);
    }

    async acceptAllProposals() {
        const acceptBtns = this.modal.querySelectorAll('.ai-proposal-card:not(.accepted):not(.rejected) .btn-accept-proposal');
        
        for (const btn of acceptBtns) {
            await this.acceptProposal(btn);
            await new Promise(r => setTimeout(r, 300));
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    capitalizeFirst(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
}

if (typeof window !== 'undefined') {
    window.TaskProposalUI = TaskProposalUI;
}
