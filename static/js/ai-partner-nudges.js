/**
 * CROWN⁴.6 AI Partner Nudges
 * Surfaces PredictiveEngine suggestions as gentle, non-intrusive notifications
 * "AI never interrupts. AI nudges gently. AI respects my style."
 */

class AIPartnerNudges {
    constructor() {
        this.nudgeQueue = [];
        this.isShowingNudge = false;
        this.lastNudgeTime = 0;
        this.dismissedNudges = new Set();
        this.userPreferences = {};
        
        this.CONFIG = {
            minIntervalMs: 30000,
            maxQueueSize: 5,
            nudgeDuration: 8000,
            fadeInDuration: 300,
            fadeOutDuration: 200,
            idleThresholdMs: 10000
        };

        this.nudgeTemplates = {
            snooze_suggestion: {
                icon: '💤',
                message: (data) => `Noticed you postponed "${data.taskTitle}" twice — should I snooze it for you?`,
                actions: ['Snooze 1 day', 'Dismiss']
            },
            due_date_suggestion: {
                icon: '📅',
                message: (data) => `Based on similar tasks, this might be due "${data.suggestedDate}". Set it?`,
                actions: ['Set Due Date', 'Later']
            },
            priority_suggestion: {
                icon: '⚡',
                message: (data) => `This task from "${data.meetingTitle}" seems urgent. Mark as high priority?`,
                actions: ['Set High Priority', 'Skip']
            },
            follow_up_detection: {
                icon: '💬',
                message: (data) => `This sounds like something you meant to follow up on. Turn it into a task?`,
                actions: ['Create Task', 'Ignore']
            },
            meeting_link_suggestion: {
                icon: '🔗',
                message: (data) => `This task seems related to your "${data.meetingTitle}" meeting. Link them?`,
                actions: ['Link', 'No Thanks']
            },
            similar_task_detected: {
                icon: '🔍',
                message: (data) => `Found a similar task: "${data.similarTaskTitle}". Merge them?`,
                actions: ['View & Merge', 'Keep Separate']
            },
            smart_assignee: {
                icon: '👤',
                message: (data) => `${data.speakerName} requested this in the meeting. Assign to them?`,
                actions: ['Assign', 'Skip']
            },
            overdue_nudge: {
                icon: '⏰',
                message: (data) => `"${data.taskTitle}" is overdue. Reschedule or complete it?`,
                actions: ['Reschedule', 'Complete Now']
            },
            cleanup_suggestion: {
                icon: '🧹',
                message: (data) => `You have ${data.completedCount} completed tasks. Archive them to declutter?`,
                actions: ['Archive All', 'Later']
            }
        };

        this.init();
    }

    init() {
        this._loadUserPreferences();
        this._createNudgeContainer();
        this._listenForPredictions();
        this._startIdleMonitor();
        console.log('[AIPartnerNudges] Initialized');
    }

    _loadUserPreferences() {
        try {
            const stored = localStorage.getItem('mina_nudge_preferences');
            if (stored) {
                this.userPreferences = JSON.parse(stored);
            }
        } catch (e) {
            console.warn('[AIPartnerNudges] Failed to load preferences:', e);
        }
    }

    _saveUserPreferences() {
        try {
            localStorage.setItem('mina_nudge_preferences', JSON.stringify(this.userPreferences));
        } catch (e) {
            console.warn('[AIPartnerNudges] Failed to save preferences:', e);
        }
    }

    _createNudgeContainer() {
        if (document.getElementById('ai-nudge-container')) return;

        const container = document.createElement('div');
        container.id = 'ai-nudge-container';
        container.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            max-width: 360px;
            z-index: 9999;
            pointer-events: none;
        `;
        document.body.appendChild(container);

        const style = document.createElement('style');
        style.id = 'ai-nudge-styles';
        style.textContent = `
            .ai-nudge {
                background: rgba(25, 25, 35, 0.98);
                backdrop-filter: blur(24px);
                border: 1px solid rgba(99, 102, 241, 0.2);
                border-radius: 16px;
                padding: 16px;
                margin-top: 12px;
                box-shadow: 
                    0 10px 40px rgba(0, 0, 0, 0.4),
                    0 0 0 1px rgba(255, 255, 255, 0.05);
                pointer-events: auto;
                transform: translateX(120%);
                opacity: 0;
                transition: transform ${this.CONFIG.fadeInDuration}ms cubic-bezier(0.4, 0, 0.2, 1),
                            opacity ${this.CONFIG.fadeInDuration}ms ease;
            }

            .ai-nudge.visible {
                transform: translateX(0);
                opacity: 1;
            }

            .ai-nudge.hiding {
                transform: translateX(120%);
                opacity: 0;
                transition-duration: ${this.CONFIG.fadeOutDuration}ms;
            }

            .ai-nudge-header {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 10px;
            }

            .ai-nudge-icon {
                font-size: 20px;
                line-height: 1;
            }

            .ai-nudge-label {
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: rgba(99, 102, 241, 0.9);
            }

            .ai-nudge-close {
                margin-left: auto;
                background: transparent;
                border: none;
                color: var(--color-text-tertiary, #666);
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                opacity: 0.6;
                transition: opacity 150ms ease;
            }

            .ai-nudge-close:hover {
                opacity: 1;
            }

            .ai-nudge-message {
                font-size: 14px;
                line-height: 1.5;
                color: var(--color-text-primary, #fff);
                margin-bottom: 12px;
            }

            .ai-nudge-actions {
                display: flex;
                gap: 8px;
            }

            .ai-nudge-action {
                flex: 1;
                padding: 10px 14px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                transition: all 150ms ease;
            }

            .ai-nudge-action.primary {
                background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.15));
                border: 1px solid rgba(99, 102, 241, 0.4);
                color: #a5b4fc;
            }

            .ai-nudge-action.primary:hover {
                background: linear-gradient(135deg, rgba(99, 102, 241, 0.3), rgba(139, 92, 246, 0.25));
                border-color: rgba(99, 102, 241, 0.6);
            }

            .ai-nudge-action.secondary {
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: var(--color-text-secondary, #999);
            }

            .ai-nudge-action.secondary:hover {
                background: rgba(255, 255, 255, 0.05);
                border-color: rgba(255, 255, 255, 0.2);
            }

            .ai-nudge-progress {
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 0 0 16px 16px;
                overflow: hidden;
            }

            .ai-nudge-progress-bar {
                height: 100%;
                background: linear-gradient(90deg, rgba(99, 102, 241, 0.6), rgba(139, 92, 246, 0.6));
                transition: width linear;
            }

            @media (max-width: 480px) {
                #ai-nudge-container {
                    left: 16px;
                    right: 16px;
                    bottom: 16px;
                    max-width: none;
                }

                .ai-nudge {
                    border-radius: 12px;
                }
            }
        `;
        document.head.appendChild(style);
    }

    _listenForPredictions() {
        window.addEventListener('prediction:ready', (e) => {
            const { type, data, confidence } = e.detail;
            
            if (confidence && confidence < 0.7) {
                console.log('[AIPartnerNudges] Prediction confidence too low:', confidence);
                return;
            }

            this.queueNudge(type, data);
        });

        if (window.predictiveEngine) {
            const originalPredict = window.predictiveEngine.predict?.bind(window.predictiveEngine);
            if (originalPredict) {
                window.predictiveEngine.predict = async (...args) => {
                    const result = await originalPredict(...args);
                    
                    if (result && result.suggestions) {
                        result.suggestions.forEach(suggestion => {
                            if (suggestion.confidence >= 0.75) {
                                this.queueNudge(suggestion.type, suggestion.data);
                            }
                        });
                    }
                    
                    return result;
                };
            }
        }
    }

    _startIdleMonitor() {
        let idleTimer = null;
        let lastActivity = Date.now();

        const resetTimer = () => {
            lastActivity = Date.now();
            if (idleTimer) {
                clearTimeout(idleTimer);
            }
            idleTimer = setTimeout(() => {
                this._onUserIdle();
            }, this.CONFIG.idleThresholdMs);
        };

        ['mousemove', 'keydown', 'scroll', 'touchstart'].forEach(event => {
            document.addEventListener(event, resetTimer, { passive: true });
        });

        resetTimer();
    }

    _onUserIdle() {
        if (this.nudgeQueue.length > 0 && !this.isShowingNudge) {
            this._showNextNudge();
        }
    }

    queueNudge(type, data) {
        if (!this.nudgeTemplates[type]) {
            console.warn('[AIPartnerNudges] Unknown nudge type:', type);
            return;
        }

        if (this.userPreferences.disabledTypes?.includes(type)) {
            console.log('[AIPartnerNudges] Nudge type disabled by user:', type);
            return;
        }

        const nudgeId = `${type}_${JSON.stringify(data)}`;
        if (this.dismissedNudges.has(nudgeId)) {
            return;
        }

        if (this.nudgeQueue.some(n => n.id === nudgeId)) {
            return;
        }

        if (this.nudgeQueue.length >= this.CONFIG.maxQueueSize) {
            this.nudgeQueue.shift();
        }

        this.nudgeQueue.push({
            id: nudgeId,
            type,
            data,
            timestamp: Date.now()
        });

        console.log('[AIPartnerNudges] Queued nudge:', type);

        const timeSinceLastNudge = Date.now() - this.lastNudgeTime;
        if (timeSinceLastNudge >= this.CONFIG.minIntervalMs && !this.isShowingNudge) {
            this._showNextNudge();
        }
    }

    _showNextNudge() {
        if (this.nudgeQueue.length === 0 || this.isShowingNudge) return;

        const nudge = this.nudgeQueue.shift();
        this._displayNudge(nudge);
    }

    _displayNudge(nudge) {
        const container = document.getElementById('ai-nudge-container');
        if (!container) return;

        this.isShowingNudge = true;
        this.lastNudgeTime = Date.now();

        const template = this.nudgeTemplates[nudge.type];
        const message = template.message(nudge.data);

        const nudgeEl = document.createElement('div');
        nudgeEl.className = 'ai-nudge';
        nudgeEl.dataset.nudgeId = nudge.id;
        nudgeEl.innerHTML = `
            <div class="ai-nudge-header">
                <span class="ai-nudge-icon">${template.icon}</span>
                <span class="ai-nudge-label">Mina Suggestion</span>
                <button class="ai-nudge-close" aria-label="Dismiss">✕</button>
            </div>
            <div class="ai-nudge-message">${this._escapeHtml(message)}</div>
            <div class="ai-nudge-actions">
                ${template.actions.map((action, i) => `
                    <button class="ai-nudge-action ${i === 0 ? 'primary' : 'secondary'}" data-action-index="${i}">
                        ${action}
                    </button>
                `).join('')}
            </div>
            <div class="ai-nudge-progress">
                <div class="ai-nudge-progress-bar" style="width: 100%"></div>
            </div>
        `;

        container.appendChild(nudgeEl);

        requestAnimationFrame(() => {
            nudgeEl.classList.add('visible');
        });

        const progressBar = nudgeEl.querySelector('.ai-nudge-progress-bar');
        progressBar.style.transitionDuration = `${this.CONFIG.nudgeDuration}ms`;
        requestAnimationFrame(() => {
            progressBar.style.width = '0%';
        });

        nudgeEl.querySelector('.ai-nudge-close').addEventListener('click', () => {
            this._dismissNudge(nudgeEl, nudge, 'dismissed');
        });

        nudgeEl.querySelectorAll('.ai-nudge-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const actionIndex = parseInt(btn.dataset.actionIndex);
                this._handleNudgeAction(nudge, actionIndex);
                this._dismissNudge(nudgeEl, nudge, actionIndex === 0 ? 'accepted' : 'dismissed');
            });
        });

        const autoHideTimer = setTimeout(() => {
            this._dismissNudge(nudgeEl, nudge, 'timeout');
        }, this.CONFIG.nudgeDuration);

        nudgeEl.addEventListener('mouseenter', () => {
            progressBar.style.transitionDuration = '0ms';
            progressBar.style.width = progressBar.style.width;
        });

        nudgeEl.addEventListener('mouseleave', () => {
            const remaining = this.CONFIG.nudgeDuration * (parseFloat(progressBar.style.width) / 100);
            progressBar.style.transitionDuration = `${remaining}ms`;
            progressBar.style.width = '0%';
        });
    }

    _handleNudgeAction(nudge, actionIndex) {
        const { type, data } = nudge;

        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordEvent('ai_nudge_action', {
                type,
                action_index: actionIndex,
                accepted: actionIndex === 0
            });
        }

        switch (type) {
            case 'snooze_suggestion':
                if (actionIndex === 0 && data.taskId) {
                    const snoozeUntil = new Date(Date.now() + 24 * 60 * 60 * 1000);
                    if (window.optimisticUI?.snoozeTask) {
                        window.optimisticUI.snoozeTask(data.taskId, snoozeUntil);
                    }
                }
                break;

            case 'due_date_suggestion':
                if (actionIndex === 0 && data.taskId && data.suggestedDueDate) {
                    if (window.optimisticUI?.updateTask) {
                        window.optimisticUI.updateTask(data.taskId, { due_date: data.suggestedDueDate });
                    }
                }
                break;

            case 'priority_suggestion':
                if (actionIndex === 0 && data.taskId) {
                    if (window.optimisticUI?.updateTask) {
                        window.optimisticUI.updateTask(data.taskId, { priority: 'high' });
                    }
                }
                break;

            case 'follow_up_detection':
                if (actionIndex === 0 && data.title) {
                    if (window.optimisticUI?.createTask) {
                        window.optimisticUI.createTask({
                            title: data.title,
                            description: data.context,
                            source: 'ai_follow_up'
                        });
                    }
                }
                break;

            case 'smart_assignee':
                if (actionIndex === 0 && data.taskId && data.userId) {
                    if (window.optimisticUI?.updateTask) {
                        window.optimisticUI.updateTask(data.taskId, { assigned_to_id: data.userId });
                    }
                }
                break;

            case 'cleanup_suggestion':
                if (actionIndex === 0) {
                    this._archiveCompletedTasks();
                }
                break;
        }

        if (window.predictiveEngine?.recordFeedback) {
            window.predictiveEngine.recordFeedback({
                nudge_type: type,
                accepted: actionIndex === 0,
                data
            });
        }
    }

    async _archiveCompletedTasks() {
        if (window.tasksWS) {
            window.tasksWS.emit('task_event', {
                event_type: 'bulk_archive_completed'
            });
        }
    }

    _dismissNudge(nudgeEl, nudge, reason) {
        nudgeEl.classList.add('hiding');
        nudgeEl.classList.remove('visible');

        if (reason === 'dismissed' || reason === 'timeout') {
            this.dismissedNudges.add(nudge.id);
        }

        setTimeout(() => {
            nudgeEl.remove();
            this.isShowingNudge = false;

            setTimeout(() => {
                this._showNextNudge();
            }, 500);
        }, this.CONFIG.fadeOutDuration);

        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordEvent('ai_nudge_dismissed', {
                type: nudge.type,
                reason
            });
        }
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    disableNudgeType(type) {
        if (!this.userPreferences.disabledTypes) {
            this.userPreferences.disabledTypes = [];
        }
        if (!this.userPreferences.disabledTypes.includes(type)) {
            this.userPreferences.disabledTypes.push(type);
            this._saveUserPreferences();
        }
    }

    enableNudgeType(type) {
        if (this.userPreferences.disabledTypes) {
            const index = this.userPreferences.disabledTypes.indexOf(type);
            if (index !== -1) {
                this.userPreferences.disabledTypes.splice(index, 1);
                this._saveUserPreferences();
            }
        }
    }

    clearDismissedNudges() {
        this.dismissedNudges.clear();
    }
}

window.aiPartnerNudges = new AIPartnerNudges();

console.log('🤖 CROWN⁴.6 AI Partner Nudges loaded');
