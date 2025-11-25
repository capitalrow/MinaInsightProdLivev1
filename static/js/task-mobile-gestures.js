/**
 * CROWN⁴.6 Task Mobile Gestures
 * Mobile-first gestures for tasks: swipe-right-to-complete, swipe-left-to-snooze
 * Designed for 90-120Hz devices with haptic feedback
 */

class TaskMobileGestures {
    constructor() {
        this.GESTURE_CONFIG = {
            swipe: {
                threshold: 80,
                velocity: 0.3,
                maxSwipe: 150,
                completeWidth: 80,
                snoozeWidth: 80
            },
            longPress: {
                duration: 400,
                moveThreshold: 10
            },
            animation: {
                duration: 300,
                easing: 'cubic-bezier(0.4, 0, 0.2, 1)'
            }
        };

        this.touchStartX = 0;
        this.touchStartY = 0;
        this.touchStartTime = 0;
        this.currentSwipeCard = null;
        this.swipeDirection = null;
        this.longPressTimer = null;
        this.isInitialized = false;
        this.eventListeners = [];
    }

    init() {
        if (this.isInitialized) return;
        if (!this._isMobileDevice()) {
            console.log('[TaskMobileGestures] Desktop detected - disabled');
            return;
        }

        const container = document.getElementById('tasks-list-container');
        if (!container) {
            console.warn('[TaskMobileGestures] Tasks container not found');
            return;
        }

        this._addStyles();
        this._attachEventListeners(container);
        this.isInitialized = true;
        console.log('[TaskMobileGestures] Initialized');
    }

    destroy() {
        if (!this.isInitialized) return;
        
        this.eventListeners.forEach(({ element, event, handler, options }) => {
            element.removeEventListener(event, handler, options);
        });
        this.eventListeners = [];
        
        if (this.longPressTimer) {
            clearTimeout(this.longPressTimer);
            this.longPressTimer = null;
        }
        
        this.isInitialized = false;
        console.log('[TaskMobileGestures] Destroyed');
    }

    _isMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               (window.innerWidth <= 768);
    }

    _addTrackedListener(element, event, handler, options) {
        element.addEventListener(event, handler, options);
        this.eventListeners.push({ element, event, handler, options });
    }

    _haptic(type = 'light') {
        if (navigator.vibrate) {
            const patterns = {
                light: [10],
                medium: [20],
                heavy: [30],
                success: [10, 30, 10],
                error: [50, 50, 50]
            };
            navigator.vibrate(patterns[type] || patterns.light);
        }
    }

    _addStyles() {
        if (document.getElementById('task-mobile-gestures-styles')) return;

        const style = document.createElement('style');
        style.id = 'task-mobile-gestures-styles';
        style.textContent = `
            .task-card-swipe-container {
                position: relative;
                overflow: hidden;
            }

            .task-swipe-action {
                position: absolute;
                top: 0;
                bottom: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 600;
                font-size: 14px;
                color: white;
                opacity: 0;
                transition: opacity 200ms ease, transform 200ms ease;
            }

            .task-swipe-action.complete {
                right: 0;
                width: ${this.GESTURE_CONFIG.swipe.completeWidth}px;
                background: linear-gradient(135deg, #10b981, #059669);
            }

            .task-swipe-action.snooze {
                left: 0;
                width: ${this.GESTURE_CONFIG.swipe.snoozeWidth}px;
                background: linear-gradient(135deg, #f59e0b, #d97706);
            }

            .task-swipe-action.visible {
                opacity: 1;
            }

            .task-swipe-action.threshold-reached {
                transform: scale(1.1);
            }

            .task-swipe-action svg {
                width: 24px;
                height: 24px;
                margin-right: 4px;
            }

            .task-card.swiping {
                transition: none !important;
            }

            .task-card.snap-back {
                transition: transform ${this.GESTURE_CONFIG.animation.duration}ms ${this.GESTURE_CONFIG.animation.easing} !important;
            }

            .task-card.completing {
                animation: taskCompleteSwipe ${this.GESTURE_CONFIG.animation.duration}ms ${this.GESTURE_CONFIG.animation.easing} forwards;
            }

            .task-card.snoozing {
                animation: taskSnoozeSwipe ${this.GESTURE_CONFIG.animation.duration}ms ${this.GESTURE_CONFIG.animation.easing} forwards;
            }

            @keyframes taskCompleteSwipe {
                0% { transform: translateX(var(--swipe-x)); opacity: 1; }
                100% { transform: translateX(100%); opacity: 0; }
            }

            @keyframes taskSnoozeSwipe {
                0% { transform: translateX(var(--swipe-x)); opacity: 1; }
                100% { transform: translateX(-100%); opacity: 0; }
            }

            .swipe-up-transcript-preview {
                position: fixed;
                left: 16px;
                right: 16px;
                bottom: 0;
                background: rgba(20, 20, 25, 0.98);
                backdrop-filter: blur(24px);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px 16px 0 0;
                padding: 20px;
                transform: translateY(100%);
                transition: transform 300ms ${this.GESTURE_CONFIG.animation.easing};
                z-index: 10000;
                max-height: 50vh;
                overflow-y: auto;
            }

            .swipe-up-transcript-preview.visible {
                transform: translateY(0);
            }

            .swipe-up-transcript-preview .preview-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
            }

            .swipe-up-transcript-preview .preview-title {
                font-size: 14px;
                font-weight: 600;
                color: var(--color-text-primary);
            }

            .swipe-up-transcript-preview .preview-close {
                background: transparent;
                border: none;
                color: var(--color-text-secondary);
                cursor: pointer;
                padding: 8px;
                border-radius: 8px;
            }

            .swipe-up-transcript-preview .preview-quote {
                font-size: 15px;
                line-height: 1.7;
                color: var(--color-text-primary);
                font-style: italic;
                padding: 16px;
                background: rgba(99, 102, 241, 0.05);
                border-left: 4px solid rgba(99, 102, 241, 0.4);
                border-radius: 8px;
                margin-bottom: 16px;
            }

            .swipe-up-transcript-preview .preview-speaker {
                font-size: 13px;
                color: var(--color-text-secondary);
                margin-bottom: 8px;
            }

            .swipe-up-transcript-preview .jump-btn {
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.1));
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 8px;
                color: #a5b4fc;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
            }
        `;
        document.head.appendChild(style);
    }

    _attachEventListeners(container) {
        this._addTrackedListener(container, 'touchstart', this._handleTouchStart.bind(this), { passive: true });
        this._addTrackedListener(container, 'touchmove', this._handleTouchMove.bind(this), { passive: false });
        this._addTrackedListener(container, 'touchend', this._handleTouchEnd.bind(this), { passive: true });
    }

    _handleTouchStart(e) {
        const card = e.target.closest('.task-card');
        if (!card) return;
        
        if (e.target.closest('.task-menu-trigger, .task-menu, .task-checkbox, button')) {
            return;
        }

        this.touchStartX = e.touches[0].clientX;
        this.touchStartY = e.touches[0].clientY;
        this.touchStartTime = Date.now();
        this.currentSwipeCard = card;
        this.swipeDirection = null;

        this.longPressTimer = setTimeout(() => {
            this._handleLongPress(card);
        }, this.GESTURE_CONFIG.longPress.duration);
    }

    _handleTouchMove(e) {
        if (!this.currentSwipeCard) return;

        const currentX = e.touches[0].clientX;
        const currentY = e.touches[0].clientY;
        const deltaX = currentX - this.touchStartX;
        const deltaY = currentY - this.touchStartY;

        if (Math.abs(deltaX) > this.GESTURE_CONFIG.longPress.moveThreshold ||
            Math.abs(deltaY) > this.GESTURE_CONFIG.longPress.moveThreshold) {
            if (this.longPressTimer) {
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
            }
        }

        if (Math.abs(deltaY) > Math.abs(deltaX)) {
            return;
        }

        e.preventDefault();

        if (!this.swipeDirection) {
            this.swipeDirection = deltaX > 0 ? 'right' : 'left';
            this._showSwipeAction(this.currentSwipeCard, this.swipeDirection);
            this.currentSwipeCard.classList.add('swiping');
        }

        const clampedDelta = Math.max(-this.GESTURE_CONFIG.swipe.maxSwipe, 
                                       Math.min(this.GESTURE_CONFIG.swipe.maxSwipe, deltaX));

        if ((this.swipeDirection === 'right' && deltaX > 0) ||
            (this.swipeDirection === 'left' && deltaX < 0)) {
            this.currentSwipeCard.style.transform = `translateX(${clampedDelta}px)`;
            
            const threshold = this.GESTURE_CONFIG.swipe.threshold;
            const actionEl = this.currentSwipeCard.querySelector(
                this.swipeDirection === 'right' ? '.task-swipe-action.complete' : '.task-swipe-action.snooze'
            );

            if (actionEl) {
                if (Math.abs(clampedDelta) >= threshold) {
                    if (!actionEl.classList.contains('threshold-reached')) {
                        actionEl.classList.add('threshold-reached');
                        this._haptic('medium');
                    }
                } else {
                    actionEl.classList.remove('threshold-reached');
                }
            }
        }
    }

    _handleTouchEnd(e) {
        if (this.longPressTimer) {
            clearTimeout(this.longPressTimer);
            this.longPressTimer = null;
        }

        if (!this.currentSwipeCard) return;

        const currentX = e.changedTouches[0].clientX;
        const deltaX = currentX - this.touchStartX;
        const velocity = Math.abs(deltaX) / (Date.now() - this.touchStartTime);
        const threshold = this.GESTURE_CONFIG.swipe.threshold;

        this.currentSwipeCard.classList.remove('swiping');

        if (Math.abs(deltaX) >= threshold || velocity >= this.GESTURE_CONFIG.swipe.velocity) {
            if (this.swipeDirection === 'right') {
                this._completeTask(this.currentSwipeCard);
            } else if (this.swipeDirection === 'left') {
                this._snoozeTask(this.currentSwipeCard);
            }
        } else {
            this._snapBack(this.currentSwipeCard);
        }

        this.currentSwipeCard = null;
        this.swipeDirection = null;
    }

    _showSwipeAction(card, direction) {
        this._removeSwipeActions(card);

        const action = document.createElement('div');
        action.className = `task-swipe-action ${direction === 'right' ? 'complete' : 'snooze'} visible`;
        
        if (direction === 'right') {
            action.innerHTML = `
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
                Done
            `;
        } else {
            action.innerHTML = `
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                Snooze
            `;
        }

        card.style.position = 'relative';
        card.insertBefore(action, card.firstChild);
    }

    _removeSwipeActions(card) {
        const actions = card.querySelectorAll('.task-swipe-action');
        actions.forEach(a => a.remove());
    }

    _snapBack(card) {
        card.classList.add('snap-back');
        card.style.transform = 'translateX(0)';
        
        setTimeout(() => {
            card.classList.remove('snap-back');
            this._removeSwipeActions(card);
        }, this.GESTURE_CONFIG.animation.duration);
    }

    async _completeTask(card) {
        const taskId = card.dataset.taskId;
        if (!taskId) return;

        this._haptic('success');

        card.style.setProperty('--swipe-x', card.style.transform.match(/translateX\((.+)\)/)?.[1] || '0px');
        card.classList.add('completing');

        try {
            if (window.optimisticUI) {
                await window.optimisticUI.toggleTaskStatus(taskId);
            }

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('task_swipe_complete', 1);
            }
        } catch (error) {
            console.error('[TaskMobileGestures] Complete failed:', error);
            this._haptic('error');
            card.classList.remove('completing');
            this._snapBack(card);
        }
    }

    async _snoozeTask(card) {
        const taskId = card.dataset.taskId;
        if (!taskId) return;

        this._haptic('medium');

        card.style.setProperty('--swipe-x', card.style.transform.match(/translateX\((.+)\)/)?.[1] || '0px');
        card.classList.add('snoozing');

        this._showSnoozeOptions(taskId, card);
    }

    _showSnoozeOptions(taskId, card) {
        const existingModal = document.querySelector('.snooze-quick-modal');
        if (existingModal) existingModal.remove();

        const modal = document.createElement('div');
        modal.className = 'snooze-quick-modal';
        modal.style.cssText = `
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(20, 20, 25, 0.98);
            backdrop-filter: blur(24px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 16px 16px 0 0;
            padding: 20px;
            z-index: 10001;
            transform: translateY(100%);
            transition: transform 300ms ${this.GESTURE_CONFIG.animation.easing};
        `;

        modal.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3 style="font-size: 16px; font-weight: 600; color: var(--color-text-primary);">Snooze until...</h3>
                <button class="snooze-cancel" style="background: none; border: none; color: var(--color-text-secondary); font-size: 14px; cursor: pointer;">Cancel</button>
            </div>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">
                <button class="snooze-option" data-hours="1" style="padding: 14px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 12px; color: #fbbf24; font-weight: 600; cursor: pointer;">
                    1 Hour
                </button>
                <button class="snooze-option" data-hours="4" style="padding: 14px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 12px; color: #fbbf24; font-weight: 600; cursor: pointer;">
                    4 Hours
                </button>
                <button class="snooze-option" data-hours="24" style="padding: 14px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 12px; color: #fbbf24; font-weight: 600; cursor: pointer;">
                    Tomorrow
                </button>
                <button class="snooze-option" data-hours="168" style="padding: 14px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 12px; color: #fbbf24; font-weight: 600; cursor: pointer;">
                    Next Week
                </button>
            </div>
        `;

        document.body.appendChild(modal);
        requestAnimationFrame(() => {
            modal.style.transform = 'translateY(0)';
        });

        modal.querySelector('.snooze-cancel').addEventListener('click', () => {
            this._closeSnoozeModal(modal);
            card.classList.remove('snoozing');
            this._snapBack(card);
        });

        modal.querySelectorAll('.snooze-option').forEach(btn => {
            btn.addEventListener('click', async () => {
                const hours = parseInt(btn.dataset.hours);
                const snoozeUntil = new Date(Date.now() + hours * 60 * 60 * 1000);

                try {
                    if (window.optimisticUI && window.optimisticUI.snoozeTask) {
                        await window.optimisticUI.snoozeTask(taskId, snoozeUntil);
                    } else if (window.tasksWS) {
                        window.tasksWS.emit('task_event', {
                            event_type: 'task_snooze',
                            data: {
                                task_id: parseInt(taskId),
                                snoozed_until: snoozeUntil.toISOString()
                            }
                        });
                    }

                    this._haptic('success');
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('task_swipe_snooze', 1, { hours });
                    }
                } catch (error) {
                    console.error('[TaskMobileGestures] Snooze failed:', error);
                    this._haptic('error');
                    card.classList.remove('snoozing');
                    this._snapBack(card);
                }

                this._closeSnoozeModal(modal);
            });
        });

        const backdrop = document.createElement('div');
        backdrop.className = 'snooze-backdrop';
        backdrop.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 10000;
        `;
        backdrop.addEventListener('click', () => {
            this._closeSnoozeModal(modal);
            card.classList.remove('snoozing');
            this._snapBack(card);
        });
        document.body.insertBefore(backdrop, modal);
    }

    _closeSnoozeModal(modal) {
        const backdrop = document.querySelector('.snooze-backdrop');
        if (backdrop) backdrop.remove();
        
        modal.style.transform = 'translateY(100%)';
        setTimeout(() => modal.remove(), 300);
    }

    _handleLongPress(card) {
        if (!card.dataset.extractedByAi || card.dataset.extractedByAi !== 'true') {
            return;
        }

        this._haptic('heavy');
        this._showTranscriptPreview(card);
    }

    async _showTranscriptPreview(card) {
        const taskId = card.dataset.taskId;
        const badge = card.querySelector('.provenance-badge');
        
        const quote = badge?.dataset.contextQuote || '';
        const speaker = badge?.dataset.contextSpeaker || '';
        const meetingTitle = badge?.dataset.meetingTitle || 'Meeting';
        const meetingId = badge?.dataset.meetingId || card.dataset.meetingId;
        const startMs = badge?.dataset.contextStartMs || 0;

        const existing = document.querySelector('.swipe-up-transcript-preview');
        if (existing) existing.remove();

        const preview = document.createElement('div');
        preview.className = 'swipe-up-transcript-preview';
        preview.innerHTML = `
            <div class="preview-header">
                <span class="preview-title">📍 From: ${this._escapeHtml(meetingTitle)}</span>
                <button class="preview-close">✕</button>
            </div>
            ${speaker ? `<div class="preview-speaker">🎙 ${this._escapeHtml(speaker)}</div>` : ''}
            ${quote ? `<div class="preview-quote">"${this._escapeHtml(quote)}"</div>` : '<div class="preview-quote" style="opacity: 0.5;">No transcript context available</div>'}
            ${meetingId ? `<button class="jump-btn" data-meeting-id="${meetingId}" data-start-ms="${startMs}">
                ⚡ Jump to Transcript
            </button>` : ''}
        `;

        document.body.appendChild(preview);

        requestAnimationFrame(() => {
            preview.classList.add('visible');
        });

        preview.querySelector('.preview-close').addEventListener('click', () => {
            this._closeTranscriptPreview(preview);
        });

        const jumpBtn = preview.querySelector('.jump-btn');
        if (jumpBtn) {
            jumpBtn.addEventListener('click', () => {
                const mid = jumpBtn.dataset.meetingId;
                const sms = jumpBtn.dataset.startMs;
                window.location.href = `/meetings/${mid}?highlight_time=${sms}`;
            });
        }

        const backdrop = document.createElement('div');
        backdrop.className = 'transcript-preview-backdrop';
        backdrop.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 9999;
        `;
        backdrop.addEventListener('click', () => {
            this._closeTranscriptPreview(preview);
        });
        document.body.insertBefore(backdrop, preview);

        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('task_longpress_context', 1);
        }
    }

    _closeTranscriptPreview(preview) {
        const backdrop = document.querySelector('.transcript-preview-backdrop');
        if (backdrop) backdrop.remove();
        
        preview.classList.remove('visible');
        setTimeout(() => preview.remove(), 300);
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

window.taskMobileGestures = new TaskMobileGestures();

document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.tasks-container')) {
        window.taskMobileGestures.init();
    }
});

window.addEventListener('tasks:bootstrap:complete', () => {
    if (window.taskMobileGestures && !window.taskMobileGestures.isInitialized) {
        window.taskMobileGestures.init();
    }
});

console.log('📱 CROWN⁴.6 Task Mobile Gestures loaded');
