class TaskProposalUI {
    constructor(taskUI) {
        this.taskUI = taskUI || window.optimisticUI;
        this.currentStream = null;
        this.currentAbortController = null;
        this.proposalContainer = null;
        this.acceptedProposals = new Map();
        this.proposalMap = new Map();
        this.pendingProposals = [];
        this.acceptedProposalIds = new Set();
        this.processingProposalIds = new Set();
        this.meetingId = null;
        this.meetingTitle = null;
        this.buttonMeetingId = null;
        this.metadataReceived = false;
        this.isStreaming = false;
        this.streamTimeout = null;
        this.STREAM_TIMEOUT_MS = 30000;
        this.init();
        this._bindGenerateButtons();
        this._registerReconciliationHandlers();
        console.log('[TaskProposalUI] Initialized');
    }

    init() {
        this.createModal();
        this.bindEvents();
        console.log('[TaskProposalUI] Initialized with idempotent handlers');
    }

    generateProposalId(task) {
        const titleHash = task.title ? task.title.substring(0, 50) : '';
        const priorityHash = task.priority || 'medium';
        const meetingHash = this.meetingId || 'no-meeting';
        return `proposal_${meetingHash}_${titleHash}_${priorityHash}`.replace(/\s+/g, '_').toLowerCase();
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
                <div class="ai-proposals-drag-handle"></div>
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
                e.preventDefault();
                e.stopPropagation();
                await this.acceptProposal(target);
            } else if (target.classList.contains('btn-reject-proposal')) {
                e.preventDefault();
                await this.rejectProposal(target);
            } else if (target.classList.contains('btn-accept-all')) {
                e.preventDefault();
                await this.acceptAllProposals(target);
            } else if (target.classList.contains('btn-retry')) {
                const generateBtn = document.querySelector('.btn-generate-proposals');
                if (generateBtn) {
                    await this.startProposalStream(generateBtn);
                }
            }
        });
    }

    _bindGenerateButtons() {
        const buttons = document.querySelectorAll('.btn-generate-proposals');
        buttons.forEach((btn) => {
            if (btn.dataset.bound === 'ai-proposals-direct') return;
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.startProposalStream(btn);
            });
            btn.dataset.bound = 'ai-proposals-direct';
        });
    }

    _registerReconciliationHandlers() {
        window.addEventListener('reconcile:complete', (event) => {
            const { type, taskId } = event.detail || {};
            if (type !== 'create') return;

            const entry = this.acceptedProposals.get(taskId);
            if (!entry) return;

            const { card } = entry;
            card.classList.remove('proposal-optimistic');
            card.classList.add('proposal-reconciled');

            const statusEl = card.querySelector('.proposal-status');
            if (statusEl) {
                statusEl.textContent = 'Synced to workspace';
            }
        });
    }

    openModal() {
        if (!this.modal) {
            console.error('[TaskProposalUI] Modal not created');
            return;
        }
        this.modal.classList.add('visible');
        document.body.style.overflow = 'hidden';
        
        const firstFocusable = this.modal.querySelector('button');
        if (firstFocusable) firstFocusable.focus();
    }

    showStreamingState() {
        const content = this.modal.querySelector('.ai-proposals-content');
        if (!content) return;
        
        content.innerHTML = `
            <div class="ai-proposals-streaming">
                <div class="streaming-indicator">
                    <div class="streaming-dot"></div>
                    <div class="streaming-dot"></div>
                    <div class="streaming-dot"></div>
                </div>
                <p class="streaming-text">Analyzing your meetings for action items...</p>
            </div>
        `;
        
        const footer = this.modal.querySelector('.ai-proposals-footer');
        if (footer) footer.style.display = 'none';
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

    resetState() {
        this.proposalMap.clear();
        this.pendingProposals = [];
        this.acceptedProposalIds.clear();
        this.processingProposalIds.clear();
        this.meetingId = null;
        this.meetingTitle = null;
        this.metadataReceived = false;
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

        this.resetState();
        this.buttonMeetingId = meetingId ? parseInt(meetingId) : null;
        this.openModal();
        this.showStreamingState();

        const requestBody = { max_proposals: 5 };
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

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[TaskProposalUI] Stream aborted');
            } else {
                console.error('[TaskProposalUI] Stream error:', error);
                this.showError(error.message || 'Failed to generate proposals');
            }
        } finally {
            this.onStreamComplete();
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
                this.drainPendingProposals();
                break;
                
            case 'proposal':
                if (data.task) {
                    if (this.metadataReceived) {
                        this.addProposal(data.task);
                    } else {
                        this.pendingProposals.push(data.task);
                    }
                }
                break;
                
            case 'done':
                if (!this.metadataReceived && this.pendingProposals.length > 0) {
                    console.log('[TaskProposalUI] No metadata, using fallback meetingId:', this.buttonMeetingId);
                    this.meetingId = this.buttonMeetingId;
                    this.meetingTitle = null;
                    this.drainPendingProposals();
                }
                break;
                
            case 'error':
                this.showError(data.message || 'An error occurred');
                break;
        }
    }

    drainPendingProposals() {
        if (this.pendingProposals.length === 0) return;
        
        console.log('[TaskProposalUI] Draining', this.pendingProposals.length, 'pending proposals');
        const proposals = [...this.pendingProposals];
        this.pendingProposals = [];
        
        proposals.forEach(task => {
            this.addProposal(task);
        });
    }

    addProposal(task) {
        task.meeting_id = this.meetingId;
        task.meeting_title = this.meetingTitle;
        
        const proposalId = this.generateProposalId(task);
        
        if (this.proposalMap.has(proposalId)) {
            console.log('[TaskProposalUI] Duplicate proposal ignored:', proposalId);
            return;
        }
        
        task.proposal_id = proposalId;
        this.proposalMap.set(proposalId, task);
        this.renderProposal(task);
    }

    renderProposal(task) {
        const content = this.modal.querySelector('.ai-proposals-content');
        if (!content) {
            console.error('[TaskProposalUI] Cannot find .ai-proposals-content container');
            return;
        }

        const proposalCard = document.createElement('div');
        const confidence = typeof task.confidence === 'number'
            ? task.confidence
            : (typeof task.confidence_score === 'number' ? task.confidence_score : null);
        const confidencePercent = confidence !== null ? Math.round(confidence * 100) : null;
        const glowClass = confidencePercent !== null
            ? (confidencePercent >= 85 ? 'proposal-glow-strong' : confidencePercent >= 60 ? 'proposal-glow-medium' : 'proposal-glow-low')
            : '';

        const meetingSource = task.meeting_title 
            ? `<div class="task-meeting-source"><span class="meeting-icon">📅</span> ${this.escapeHtml(task.meeting_title)}</div>` 
            : '';

        proposalCard.className = `task-card ai-proposal ai-proposal-card proposal-enter ${glowClass}`.trim();
        proposalCard.dataset.proposalId = task.proposal_id;
        if (confidencePercent !== null) {
            proposalCard.dataset.confidence = confidencePercent;
        }
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
                    ${confidencePercent !== null ? `<span class="confidence-pill">${confidencePercent}% confidence</span>` : ''}
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
                <button class="btn-accept-proposal" data-proposal-id="${task.proposal_id}">
                    <svg class="btn-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    <span class="btn-text">Accept</span>
                </button>
                <button class="btn-reject-proposal" data-proposal-id="${task.proposal_id}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Dismiss
                </button>
            </div>
        `;

        content.appendChild(proposalCard);
        
        requestAnimationFrame(() => {
            proposalCard.classList.add('visible');
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

        if (this.proposalMap.size === 0) {
            this.showEmpty();
        }

        this.updateFooter();
    }

    updateFooter() {
        const footer = this.modal.querySelector('.ai-proposals-footer');
        const countEl = footer.querySelector('.proposals-count');
        const acceptAllBtn = footer.querySelector('.btn-accept-all');
        
        const activeCards = this.modal.querySelectorAll('.ai-proposal-card:not(.accepted):not(.rejected)');
        const activeCount = activeCards.length;
        const totalCount = this.proposalMap.size;
        const acceptedCount = this.acceptedProposalIds.size;
        
        if (activeCount > 0) {
            footer.style.display = 'flex';
            if (acceptedCount > 0) {
                countEl.textContent = `${activeCount} of ${totalCount} remaining`;
            } else {
                countEl.textContent = `${activeCount} suggestion${activeCount !== 1 ? 's' : ''} available`;
            }
            acceptAllBtn.disabled = this.processingProposalIds.size > 0;
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
        const acceptedCount = this.acceptedProposalIds.size;
        
        content.innerHTML = `
            <div class="ai-proposals-complete">
                <div class="complete-animation">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 11-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                </div>
                <h4>All done!</h4>
                <p>${acceptedCount} task${acceptedCount !== 1 ? 's' : ''} added to your list</p>
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
        const proposalId = button.dataset.proposalId;
        
        if (this.acceptedProposalIds.has(proposalId)) {
            console.log('[TaskProposalUI] Proposal already accepted:', proposalId);
            return;
        }
        
        if (this.processingProposalIds.has(proposalId)) {
            console.log('[TaskProposalUI] Proposal already processing:', proposalId);
            return;
        }
        
        const proposal = this.proposalMap.get(proposalId);
        if (!proposal) {
            console.error('[TaskProposalUI] Proposal not found:', proposalId);
            return;
        }

        const card = button.closest('.ai-proposal-card');
        
        this.processingProposalIds.add(proposalId);
        
        button.disabled = true;
        const btnText = button.querySelector('.btn-text');
        const btnIcon = button.querySelector('.btn-icon');
        const originalText = btnText ? btnText.textContent : 'Accept';
        if (btnText) btnText.textContent = 'Creating...';
        if (btnIcon) btnIcon.classList.add('animate-spin');
        
        const rejectBtn = card ? card.querySelector('.btn-reject-proposal') : null;
        if (rejectBtn) rejectBtn.disabled = true;

        try {
            const taskData = {
                title: proposal.title,
                description: proposal.description || '',
                priority: proposal.priority || 'medium',
                category: proposal.category || '',
                status: 'todo',
                meeting_id: proposal.meeting_id || this.meetingId,
                source: 'task_nlp:proposed'
            };

            let result;

            if (this.taskUI?.createTask) {
                const optimisticTask = await this.taskUI.createTask(taskData);
                result = { success: true, task: optimisticTask };
            } else {
                const response = await fetch('/api/tasks/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(taskData)
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    if (errorData.duplicate) {
                        console.log('[TaskProposalUI] Task already exists (server dedupe)');
                        this.acceptedProposalIds.add(proposalId);
                        this.markCardAsAccepted(card, proposal.title);
                        return;
                    }
                    throw new Error(errorData.error || 'Failed to create task');
                }

                result = await response.json();
            }

            if (result.success || result.task) {
                this.acceptedProposalIds.add(proposalId);
                this.markCardAsAccepted(card, proposal.title);

                if (window.ToastNotifications) {
                    window.ToastNotifications.show('Task added successfully', 'success');
                } else if (window.toast) {
                    window.toast.success('Task added successfully');
                }

                if (result.task?.id && this.acceptedProposals) {
                    this.acceptedProposals.set(result.task.id, { card, proposal });
                }

                this.refreshTaskList();
                this.updateFooter();
                this.checkAllAccepted();
            } else {
                throw new Error(result.message || result.error || 'Failed to accept proposal');
            }

        } catch (error) {
            console.error('[TaskProposalUI] Accept error:', error);
            
            this.processingProposalIds.delete(proposalId);
            button.disabled = false;
            if (btnText) btnText.textContent = originalText;
            if (btnIcon) btnIcon.classList.remove('animate-spin');
            if (rejectBtn) rejectBtn.disabled = false;
            
            if (window.toast) {
                window.toast.error(error.message || 'Failed to create task');
            }
        } finally {
            this.processingProposalIds.delete(proposalId);
        }
    }

    markCardAsAccepted(card, taskTitle) {
        card.classList.add('accepted');
        card.innerHTML = `
            <div class="ai-proposal-success">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span>Task created: ${this.escapeHtml(taskTitle)}</span>
            </div>
        `;
    }

    refreshTaskList() {
        if (window.taskCache && typeof window.taskCache.invalidate === 'function') {
            window.taskCache.invalidate();
        }

        if (this.taskUI && typeof this.taskUI.loadTasks === 'function') {
            this.taskUI.loadTasks();
        }
    }

    checkAllAccepted() {
        const remainingCards = this.modal.querySelectorAll('.ai-proposal-card:not(.accepted):not(.rejected)');
        if (remainingCards.length === 0 && !this.isStreaming && this.acceptedProposalIds.size > 0) {
            setTimeout(() => this.showAllAccepted(), 300);
        }
    }

    async rejectProposal(button) {
        const proposalId = button.dataset.proposalId;
        const card = button.closest('.ai-proposal-card');
        
        if (this.processingProposalIds.has(proposalId)) {
            return;
        }
        
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
                if (remainingCards.length === 0 && !this.isStreaming && this.acceptedProposalIds.size === 0) {
                    this.showEmpty();
                }
            }, 300);
        }, 100);
    }

    async acceptAllProposals(button) {
        if (button) {
            button.disabled = true;
            button.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin">
                    <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="32"></circle>
                </svg>
                Accepting...
            `;
        }
        
        const acceptBtns = this.modal.querySelectorAll('.ai-proposal-card:not(.accepted):not(.rejected) .btn-accept-proposal');
        
        for (const btn of acceptBtns) {
            await this.acceptProposal(btn);
            await new Promise(r => setTimeout(r, 200));
        }
        
        if (button) {
            button.disabled = false;
            button.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                Accept All
            `;
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

    async _checkDuplicate(payload) {
        try {
            const response = await fetch('/api/tasks/check-duplicate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: payload.title,
                    description: payload.description,
                    meeting_id: payload.meeting_id
                })
            });

            if (!response.ok) return null;
            return await response.json();
        } catch (error) {
            console.warn('[TaskProposalUI] Duplicate check failed:', error);
            return null;
        }
    }

    async _generateOriginHash(payload) {
        try {
            const text = `${payload.title || ''}|${payload.description || ''}|${payload.meeting_id || ''}|${payload.category || ''}`;
            const encoder = new TextEncoder();
            const data = encoder.encode(text);
            const buffer = await crypto.subtle.digest('SHA-256', data);
            return Array.from(new Uint8Array(buffer)).map(b => b.toString(16).padStart(2, '0')).join('');
        } catch (error) {
            console.warn('[TaskProposalUI] Failed to generate origin_hash:', error);
            return null;
        }
    }

    _highlightDuplicate(card, existingTask, confidence) {
        card.classList.add('proposal-duplicate');
        const status = card.querySelector('.proposal-status') || document.createElement('div');
        status.className = 'proposal-status duplicate';
        status.innerHTML = `Duplicate detected${confidence ? ` (${Math.round(confidence * 100)}% match)` : ''}. Opening existing task…`;
        if (!card.contains(status)) {
            card.querySelector('.ai-proposal-actions')?.before(status);
        }

        if (window.toastManager) {
            window.toastManager.show('Similar task already exists. Jumping to it.', 'warning');
        }

        if (existingTask?.id) {
            window.dispatchEvent(new CustomEvent('task:duplicate-detected', { detail: existingTask }));
        }
    }

    _morphProposalToTask(card, optimisticTask, originHash) {
        card.classList.add('proposal-optimistic');
        card.dataset.taskId = optimisticTask.id;
        card.dataset.originHash = originHash || '';

        const status = document.createElement('div');
        status.className = 'proposal-status syncing';
        status.textContent = 'Syncing to workspace…';
        card.querySelector('.ai-proposal-actions')?.before(status);

        const badge = card.querySelector('.ai-proposal-badge');
        if (badge) {
            badge.textContent = 'Accepted';
            badge.classList.add('accepted');
        }

        const acceptBtn = card.querySelector('.btn-accept-proposal');
        const rejectBtn = card.querySelector('.btn-reject-proposal');
        if (acceptBtn) acceptBtn.remove();
        if (rejectBtn) rejectBtn.remove();

        const content = card.querySelector('.task-content');
        if (content) {
            content.classList.add('proposal-to-task');
        }
    }
}

if (typeof window !== 'undefined') {
    window.TaskProposalUI = TaskProposalUI;
}
