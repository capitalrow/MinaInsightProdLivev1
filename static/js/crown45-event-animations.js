/**
 * CROWN⁴.5 Complete 20-Event Animation Matrix
 * Maps all CROWN⁴.5 events to their emotional architecture animations.
 * 
 * Event → Emotion → Animation Cue
 */

class CROWN45EventAnimations {
    constructor() {
        this.animations = window.emotionalAnimations || null;
        this.quietState = window.quietStateManager || null;
        
        if (!this.animations) {
            console.warn('[CROWN45EventAnimations] EmotionalAnimations not found');
        }
        
        console.log('[CROWN45EventAnimations] Initialized');
    }

    /**
     * Handle event and trigger appropriate animation
     * @param {string} eventType - CROWN⁴.5 event type
     * @param {Element} targetElement - DOM element to animate
     * @param {Object} metadata - Event metadata
     */
    handleEvent(eventType, targetElement, metadata = {}) {
        if (!this.animations || !targetElement) {
            console.warn('[CROWN45EventAnimations] Cannot animate: missing animations or target');
            return;
        }

        // Route to specific event handler
        switch (eventType) {
            // 1. tasks_bootstrap
            case 'tasks_bootstrap':
                this._handleBootstrap(targetElement, metadata);
                break;

            // 2. tasks_ws_subscribe (invisible)
            case 'tasks_ws_subscribe':
                // No animation - deterministic backfill
                break;

            // 3. task_nlp:proposed
            case 'task_nlp:proposed':
                this._handleNLPProposed(targetElement, metadata);
                break;

            // 4. task_create:manual
            case 'task_create:manual':
                this._handleTaskCreate(targetElement, metadata);
                break;

            // 5. task_create:nlp_accept
            case 'task_create:nlp_accept':
                this._handleNLPAccept(targetElement, metadata);
                break;

            // 6. task_update:title
            case 'task_update:title':
                this._handleTitleUpdate(targetElement, metadata);
                break;

            // 7. task_update:status_toggle
            case 'task_update:status_toggle':
                this._handleStatusToggle(targetElement, metadata);
                break;

            // 8. task_update:priority
            case 'task_update:priority':
                this._handlePriorityUpdate(targetElement, metadata);
                break;

            // 9. task_update:due
            case 'task_update:due':
                this._handleDueUpdate(targetElement, metadata);
                break;

            // 10. task_update:assign
            case 'task_update:assign':
                this._handleAssignUpdate(targetElement, metadata);
                break;

            // 11. task_update:labels
            case 'task_update:labels':
                this._handleLabelsUpdate(targetElement, metadata);
                break;

            // 12. task_snooze
            case 'task_snooze':
                this._handleSnooze(targetElement, metadata);
                break;

            // 13. task_merge
            case 'task_merge':
                this._handleMerge(targetElement, metadata);
                break;

            // 14. task_link:jump_to_span
            case 'task_link:jump_to_span':
                this._handleJumpToSpan(targetElement, metadata);
                break;

            // 15. filter_apply
            case 'filter_apply':
                this._handleFilterApply(targetElement, metadata);
                break;

            // 16. tasks_refresh
            case 'tasks_refresh':
                this._handleRefresh(targetElement, metadata);
                break;

            // 17. tasks_idle_sync
            case 'tasks_idle_sync':
                // Invisible - background checksum reconciliation
                break;

            // 18. tasks_offline_queue:replay
            case 'tasks_offline_queue:replay':
                this._handleOfflineReplay(targetElement, metadata);
                break;

            // 19. task_delete
            case 'task_delete':
                this._handleDelete(targetElement, metadata);
                break;

            // 20. tasks_multiselect:bulk
            case 'tasks_multiselect:bulk':
                this._handleBulkOperation(targetElement, metadata);
                break;

            default:
                console.log(`[CROWN45EventAnimations] No animation for: ${eventType}`);
        }
    }

    // Event-specific animation handlers

    /**
     * 1. tasks_bootstrap - "Remembered instantly"
     * Emotion: Familiarity → Fade-in ≤200ms
     */
    _handleBootstrap(element, metadata) {
        element.style.opacity = '0';
        requestAnimationFrame(() => {
            element.style.transition = 'opacity 200ms ease-out';
            element.style.opacity = '1';
        });
    }

    /**
     * 3. task_nlp:proposed - "Trust in AI suggestions"
     * Emotion: Curiosity → Confidence-graded glow
     */
    _handleNLPProposed(element, metadata) {
        const confidence = metadata.confidence || 0.8;
        const glowIntensity = confidence * 100;
        
        element.style.boxShadow = `0 0 ${glowIntensity}px rgba(59, 130, 246, ${confidence})`;
        this.animations.shimmer(element, {
            duration: 1500,
            emotion_cue: 'nlp_proposed',
            onComplete: () => {
                element.style.boxShadow = '';
            }
        });
    }

    /**
     * 4. task_create:manual - "Instant agency"
     * Emotion: Momentum → Pop-in + optimistic insert
     */
    _handleTaskCreate(element, metadata) {
        element.style.transform = 'scale(0.9)';
        element.style.opacity = '0';
        
        requestAnimationFrame(() => {
            element.style.transition = 'all 300ms cubic-bezier(0.34, 1.56, 0.64, 1)';
            element.style.transform = 'scale(1)';
            element.style.opacity = '1';
        });
    }

    /**
     * 5. task_create:nlp_accept - "Seamless AI→Action"
     * Emotion: Momentum → Morph "Suggested" → normal
     */
    _handleNLPAccept(element, metadata) {
        this.animations.morph(element, {
            duration: 800,
            emotion_cue: 'nlp_accept',
            onComplete: () => {
                // Remove AI proposal badge
                const badge = element.querySelector('.ai-proposal-badge');
                if (badge) {
                    badge.style.transition = 'opacity 300ms';
                    badge.style.opacity = '0';
                    setTimeout(() => badge.remove(), 300);
                }
            }
        });
    }

    /**
     * 6. task_update:title - "Fluid editing"
     * Emotion: Control → Inline save tick
     */
    _handleTitleUpdate(element, metadata) {
        const title = element.querySelector('.task-title');
        if (title) {
            title.style.transition = 'color 200ms';
            title.style.color = 'var(--color-success, #10b981)';
            setTimeout(() => {
                title.style.color = '';
            }, 500);
        }
    }

    /**
     * 7. task_update:status_toggle - "Productive satisfaction"
     * Emotion: Satisfaction → Checkmark burst + slide
     */
    _handleStatusToggle(element, metadata) {
        const isCompleted = metadata.status === 'completed';
        
        if (isCompleted) {
            // Burst animation on checkbox
            const checkbox = element.querySelector('.task-checkbox');
            if (checkbox) {
                this.animations.burst(checkbox.parentElement, {
                    duration: 500,
                    emotion_cue: 'task_completed'
                });
            }
            
            // Slide animation on task card
            element.style.transition = 'all 400ms cubic-bezier(0.4, 0.0, 0.2, 1)';
            element.style.transform = 'translateX(8px)';
            element.style.opacity = '0.6';
            
            setTimeout(() => {
                element.style.transform = '';
                element.style.opacity = '';
            }, 400);
        } else {
            // Uncomplete - reverse animation
            element.style.transition = 'all 300ms ease-out';
            element.style.opacity = '1';
        }
    }

    /**
     * 8. task_update:priority - "Controlled momentum"
     * Emotion: Control → Spring reorder
     */
    _handlePriorityUpdate(element, metadata) {
        // Spring reorder animation
        element.style.transition = 'transform 600ms cubic-bezier(0.34, 1.56, 0.64, 1)';
        element.style.transform = 'translateY(-4px)';
        
        setTimeout(() => {
            element.style.transform = 'translateY(0)';
        }, 100);
        
        // Highlight priority badge
        const badge = element.querySelector('.priority-badge');
        if (badge) {
            this.animations.burst(badge, {
                duration: 400,
                emotion_cue: 'priority_change'
            });
        }
    }

    /**
     * 9. task_update:due - "Intelligent defaults"
     * Emotion: Assurance → Due date shimmer
     */
    _handleDueUpdate(element, metadata) {
        const dueBadge = element.querySelector('.due-date-badge');
        if (dueBadge) {
            this.animations.shimmer(dueBadge, {
                duration: 1000,
                emotion_cue: 'due_date_update'
            });
        }
    }

    /**
     * 10. task_update:assign - "Clear ownership"
     * Emotion: Clarity → Avatar fade + toast
     */
    _handleAssignUpdate(element, metadata) {
        const assigneeBadge = element.querySelector('.assignee-badge');
        if (assigneeBadge) {
            assigneeBadge.style.transition = 'all 400ms ease-out';
            assigneeBadge.style.transform = 'scale(1.1)';
            assigneeBadge.style.opacity = '0';
            
            setTimeout(() => {
                assigneeBadge.style.transform = 'scale(1)';
                assigneeBadge.style.opacity = '1';
            }, 100);
        }
    }

    /**
     * 11. task_update:labels - "Lightweight organisation"
     * Emotion: Organization → Chip animate
     */
    _handleLabelsUpdate(element, metadata) {
        const labels = element.querySelectorAll('.label-badge');
        labels.forEach((label, index) => {
            setTimeout(() => {
                label.style.transition = 'all 300ms cubic-bezier(0.34, 1.56, 0.64, 1)';
                label.style.transform = 'scale(1.05)';
                
                setTimeout(() => {
                    label.style.transform = 'scale(1)';
                }, 150);
            }, index * 50);
        });
    }

    /**
     * 12. task_snooze - "Calm deferral"
     * Emotion: Relief → Slide to Snoozed
     */
    _handleSnooze(element, metadata) {
        element.style.transition = 'all 500ms cubic-bezier(0.4, 0.0, 0.2, 1)';
        element.style.transform = 'translateX(100%)';
        element.style.opacity = '0';
        
        setTimeout(() => {
            // Reset for repositioning
            element.style.transition = 'none';
            element.style.transform = '';
            element.style.opacity = '1';
        }, 500);
    }

    /**
     * 13. task_merge - "No clutter"
     * Emotion: Organization → Collapse + badge
     */
    _handleMerge(element, metadata) {
        element.style.transition = 'all 600ms cubic-bezier(0.4, 0.0, 0.2, 1)';
        element.style.transform = 'scale(0.8)';
        element.style.opacity = '0';
        element.style.height = '0';
        element.style.margin = '0';
        
        setTimeout(() => {
            element.remove();
        }, 600);
    }

    /**
     * 14. task_link:jump_to_span - "Perfect recall"
     * Emotion: Curiosity → Morph transition
     */
    _handleJumpToSpan(element, metadata) {
        this.animations.morph(element, {
            duration: 800,
            emotion_cue: 'jump_to_span'
        });
    }

    /**
     * 15. filter_apply - "Sub-100ms response"
     * Emotion: Control → Fluid reorder
     */
    _handleFilterApply(element, metadata) {
        element.style.transition = 'opacity 150ms ease-out';
        element.style.opacity = '0.5';
        
        setTimeout(() => {
            element.style.opacity = '1';
        }, 80);
    }

    /**
     * 16. tasks_refresh - "Live truth"
     * Emotion: Assurance → List shimmer
     */
    _handleRefresh(element, metadata) {
        this.animations.shimmer(element, {
            duration: 1200,
            emotion_cue: 'tasks_refresh'
        });
    }

    /**
     * 18. tasks_offline_queue:replay - "Works offline"
     * Emotion: Trust → No jank; "Synced" toast
     */
    _handleOfflineReplay(element, metadata) {
        // Smooth fade-in for replayed tasks
        element.style.opacity = '0';
        requestAnimationFrame(() => {
            element.style.transition = 'opacity 300ms ease-out';
            element.style.opacity = '1';
        });
    }

    /**
     * 19. task_delete - "Safe closure"
     * Emotion: Closure → Slide-out + undo toast
     */
    _handleDelete(element, metadata) {
        element.style.transition = 'all 400ms cubic-bezier(0.4, 0.0, 0.2, 1)';
        element.style.transform = 'translateX(-100%)';
        element.style.opacity = '0';
        
        setTimeout(() => {
            element.remove();
        }, 400);
    }

    /**
     * 20. tasks_multiselect:bulk - "Scale efficiency"
     * Emotion: Control → Group animation
     */
    _handleBulkOperation(element, metadata) {
        const selectedTasks = element.querySelectorAll('.task-card.selected');
        selectedTasks.forEach((task, index) => {
            setTimeout(() => {
                this.animations.burst(task, {
                    duration: 300,
                    emotion_cue: 'bulk_operation'
                });
            }, index * 50);
        });
    }
}

// Initialize global instance
window.CROWN45EventAnimations = CROWN45EventAnimations;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.crown45Animations) {
            window.crown45Animations = new CROWN45EventAnimations();
            console.log('[CROWN45EventAnimations] Global instance created');
        }
    });
}
