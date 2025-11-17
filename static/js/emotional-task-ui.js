/**
 * CROWN⁴.6 Emotional Task UI
 * 
 * Meeting-informed emotional cues that adjust UI based on meeting context:
 * - Stressful meeting → calming animations
 * - High-energy workshop → energizing animations
 * - Decision-heavy meeting → clarity-focused UI
 * - Creative brainstorm → playful, open animations
 * 
 * This is a signature Mina feature: No other task manager understands meeting emotion
 */

class EmotionalTaskUI {
    constructor() {
        this.emotionalStates = {
            CALM: 'calm',           // Gentle, soothing
            ENERGIZING: 'energizing', // Vibrant, active
            FOCUSED: 'focused',      // Clear, minimal
            PLAYFUL: 'playful',      // Creative, expressive
            NEUTRAL: 'neutral'       // Standard
        };
        
        this.meetingEmotions = new Map(); // meeting_id → emotional_state
        this.taskEmotions = new Map();    // task_id → emotional_state
        
        this.init();
    }
    
    async init() {
        console.log('[Emotional UI] Initializing meeting-informed emotional cues...');
        
        // Analyze meetings to determine emotional states
        await this.analyzeMeetingEmotions();
        
        // Apply emotional cues to tasks
        this.applyEmotionalCues();
        
        // Setup dynamic adjustments
        this.setupEmotionalAdaptations();
    }
    
    /**
     * Analyze meetings to determine their emotional character
     */
    async analyzeMeetingEmotions() {
        try {
            // Fetch meeting analytics
            const response = await fetch('/api/tasks/meeting-heatmap');
            const data = await response.json();
            
            if (!data.success || !data.meetings) return;
            
            for (const meeting of data.meetings) {
                const emotion = this.inferMeetingEmotion(meeting);
                this.meetingEmotions.set(meeting.meeting_id, emotion);
            }
            
            console.log(`[Emotional UI] Analyzed ${this.meetingEmotions.size} meetings for emotional context`);
            
        } catch (error) {
            console.log('[Emotional UI] Failed to analyze meetings:', error.message);
        }
    }
    
    /**
     * Infer emotional state from meeting characteristics
     */
    inferMeetingEmotion(meeting) {
        const {
            total_tasks,
            active_tasks,
            completed_count,
            heat_intensity,
            days_ago,
            meeting_title = ''
        } = meeting;
        
        // High-stress indicators
        const isHighStress = (
            active_tasks > 8 ||
            heat_intensity > 80 ||
            (days_ago < 2 && active_tasks > 5)
        );
        
        // High-energy indicators
        const isHighEnergy = (
            total_tasks > 10 ||
            meeting_title.toLowerCase().includes('workshop') ||
            meeting_title.toLowerCase().includes('brainstorm') ||
            meeting_title.toLowerCase().includes('kickoff')
        );
        
        // Decision-focused indicators
        const isDecisionFocused = (
            meeting_title.toLowerCase().includes('review') ||
            meeting_title.toLowerCase().includes('decision') ||
            meeting_title.toLowerCase().includes('approval') ||
            completed_count / total_tasks > 0.7
        );
        
        // Creative indicators
        const isCreative = (
            meeting_title.toLowerCase().includes('brainstorm') ||
            meeting_title.toLowerCase().includes('ideation') ||
            meeting_title.toLowerCase().includes('design')
        );
        
        // Determine emotional state based on indicators
        if (isHighStress && !isHighEnergy) {
            return this.emotionalStates.CALM; // Stressful → calming
        } else if (isHighEnergy && !isHighStress) {
            return this.emotionalStates.ENERGIZING; // High-energy → energizing
        } else if (isDecisionFocused) {
            return this.emotionalStates.FOCUSED; // Decisions → clarity
        } else if (isCreative) {
            return this.emotionalStates.PLAYFUL; // Creative → playful
        } else {
            return this.emotionalStates.NEUTRAL;
        }
    }
    
    /**
     * Apply emotional cues to task cards based on their meeting origin
     */
    applyEmotionalCues() {
        const taskCards = document.querySelectorAll('.task-card');
        
        taskCards.forEach(card => {
            const meetingId = parseInt(card.dataset.meetingId);
            if (!meetingId) return;
            
            const emotion = this.meetingEmotions.get(meetingId) || this.emotionalStates.NEUTRAL;
            this.taskEmotions.set(parseInt(card.dataset.taskId), emotion);
            
            // Add emotional state class
            card.classList.add(`emotion-${emotion}`);
            
            // Add meeting emotion indicator
            this.addEmotionalIndicator(card, emotion);
        });
        
        console.log(`[Emotional UI] Applied emotional cues to ${taskCards.length} tasks`);
    }
    
    /**
     * Add subtle emotional indicator to task card
     */
    addEmotionalIndicator(card, emotion) {
        // Don't add if already exists
        if (card.querySelector('.emotional-indicator')) return;
        
        const indicator = document.createElement('div');
        indicator.className = `emotional-indicator emotion-${emotion}`;
        indicator.title = this.getEmotionalDescription(emotion);
        
        // Add to card metadata area
        const metadata = card.querySelector('.task-metadata');
        if (metadata) {
            metadata.appendChild(indicator);
        }
    }
    
    /**
     * Get description for emotional state
     */
    getEmotionalDescription(emotion) {
        const descriptions = {
            calm: 'From a high-intensity meeting - Mina helps you stay calm',
            energizing: 'From a high-energy session - Keep the momentum!',
            focused: 'From a decision-focused meeting - Clarity is key',
            playful: 'From a creative session - Think freely!',
            neutral: 'Standard task'
        };
        
        return descriptions[emotion] || descriptions.neutral;
    }
    
    /**
     * Setup dynamic emotional adaptations
     */
    setupEmotionalAdaptations() {
        // Adjust animation speeds based on emotional state
        this.adjustAnimationSpeeds();
        
        // Adjust color vibrancy
        this.adjustColorVibrancy();
        
        // Adjust spacing and breathing room
        this.adjustVisualDensity();
    }
    
    /**
     * Adjust animation speeds for emotional context
     */
    adjustAnimationSpeeds() {
        const styleEl = document.createElement('style');
        styleEl.id = 'emotional-animation-speeds';
        
        styleEl.textContent = `
            /* CALM: Slower, gentler animations */
            .emotion-calm {
                --animation-duration: 320ms;
                --hover-lift: -1px;
            }
            
            .emotion-calm .task-card {
                transition-duration: 320ms;
                transition-timing-function: cubic-bezier(0.25, 0.1, 0.25, 1);
            }
            
            .emotion-calm:hover {
                transform: translateY(var(--hover-lift));
            }
            
            /* ENERGIZING: Faster, more responsive */
            .emotion-energizing {
                --animation-duration: 160ms;
                --hover-lift: -3px;
            }
            
            .emotion-energizing .task-card {
                transition-duration: 160ms;
                transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
            }
            
            .emotion-energizing:hover {
                transform: translateY(var(--hover-lift)) scale(1.01);
            }
            
            /* FOCUSED: Crisp, immediate */
            .emotion-focused {
                --animation-duration: 140ms;
                --hover-lift: -1px;
            }
            
            .emotion-focused .task-card {
                transition-duration: 140ms;
                transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
            }
            
            /* PLAYFUL: Bouncy, expressive */
            .emotion-playful {
                --animation-duration: 240ms;
                --hover-lift: -4px;
            }
            
            .emotion-playful .task-card {
                transition-duration: 240ms;
                transition-timing-function: cubic-bezier(0.68, -0.55, 0.27, 1.55);
            }
            
            .emotion-playful:hover {
                transform: translateY(var(--hover-lift)) rotate(0.5deg);
            }
        `;
        
        document.head.appendChild(styleEl);
    }
    
    /**
     * Adjust color vibrancy based on emotional state
     */
    adjustColorVibrancy() {
        const styleEl = document.createElement('style');
        styleEl.id = 'emotional-color-vibrancy';
        
        styleEl.textContent = `
            /* CALM: Desaturated, soothing colors */
            .emotion-calm {
                filter: saturate(0.8) brightness(0.95);
            }
            
            .emotion-calm::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(135deg, rgba(147, 197, 253, 0.05) 0%, transparent 100%);
                pointer-events: none;
                border-radius: inherit;
            }
            
            /* ENERGIZING: Vibrant, saturated colors */
            .emotion-energizing {
                filter: saturate(1.2) brightness(1.05);
            }
            
            .emotion-energizing::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(135deg, rgba(251, 191, 36, 0.05) 0%, rgba(239, 68, 68, 0.03) 100%);
                pointer-events: none;
                border-radius: inherit;
            }
            
            /* FOCUSED: High contrast, clear */
            .emotion-focused {
                filter: contrast(1.05);
            }
            
            .emotion-focused {
                border-color: rgba(99, 102, 241, 0.15) !important;
            }
            
            /* PLAYFUL: Colorful gradients */
            .emotion-playful {
                filter: saturate(1.1) hue-rotate(2deg);
            }
            
            .emotion-playful::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(135deg, rgba(167, 139, 250, 0.06) 0%, rgba(139, 92, 246, 0.03) 100%);
                pointer-events: none;
                border-radius: inherit;
            }
        `;
        
        document.head.appendChild(styleEl);
    }
    
    /**
     * Adjust visual density (spacing, padding) for emotional context
     */
    adjustVisualDensity() {
        const styleEl = document.createElement('style');
        styleEl.id = 'emotional-visual-density';
        
        styleEl.textContent = `
            /* CALM: More breathing room */
            .emotion-calm {
                padding: calc(var(--space-4) * 1.2);
                margin-bottom: calc(var(--space-3) * 1.3);
            }
            
            /* FOCUSED: Tighter, more compact */
            .emotion-focused {
                padding: calc(var(--space-4) * 0.9);
                margin-bottom: calc(var(--space-3) * 0.85);
            }
            
            /* PLAYFUL: Irregular spacing for organic feel */
            .emotion-playful:nth-child(even) {
                margin-left: 4px;
            }
            
            .emotion-playful:nth-child(odd) {
                margin-right: 4px;
            }
        `;
        
        document.head.appendChild(styleEl);
    }
    
    /**
     * Get emotional state for a task
     */
    getTaskEmotion(taskId) {
        return this.taskEmotions.get(taskId) || this.emotionalStates.NEUTRAL;
    }
    
    /**
     * Update emotional state for a meeting (called when meeting data changes)
     */
    updateMeetingEmotion(meetingId, newData) {
        const emotion = this.inferMeetingEmotion(newData);
        this.meetingEmotions.set(meetingId, emotion);
        
        // Re-apply to affected tasks
        const affectedCards = document.querySelectorAll(`[data-meeting-id="${meetingId}"]`);
        affectedCards.forEach(card => {
            // Remove old emotional classes
            Object.values(this.emotionalStates).forEach(state => {
                card.classList.remove(`emotion-${state}`);
            });
            
            // Add new emotional class
            card.classList.add(`emotion-${emotion}`);
            
            // Update indicator
            const indicator = card.querySelector('.emotional-indicator');
            if (indicator) {
                Object.values(this.emotionalStates).forEach(state => {
                    indicator.classList.remove(`emotion-${state}`);
                });
                indicator.classList.add(`emotion-${emotion}`);
                indicator.title = this.getEmotionalDescription(emotion);
            }
        });
        
        console.log(`[Emotional UI] Updated emotion for meeting ${meetingId} to ${emotion}`);
    }
    
    /**
     * Trigger emotional pulse animation (for notifications, completions)
     */
    triggerEmotionalPulse(card, intensity = 1.0) {
        const taskId = parseInt(card.dataset.taskId);
        const emotion = this.getTaskEmotion(taskId);
        
        // Create pulse effect based on emotional state
        const pulse = document.createElement('div');
        pulse.className = `emotional-pulse emotion-${emotion}`;
        pulse.style.cssText = `
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 100%;
            height: 100%;
            border-radius: inherit;
            pointer-events: none;
            opacity: 0;
        `;
        
        card.style.position = 'relative';
        card.appendChild(pulse);
        
        // Emotional-specific pulse colors
        const pulseColors = {
            calm: 'rgba(147, 197, 253, 0.4)',
            energizing: 'rgba(251, 191, 36, 0.4)',
            focused: 'rgba(99, 102, 241, 0.4)',
            playful: 'rgba(167, 139, 250, 0.4)',
            neutral: 'rgba(99, 102, 241, 0.3)'
        };
        
        const color = pulseColors[emotion] || pulseColors.neutral;
        const duration = emotion === 'calm' ? 800 : emotion === 'energizing' ? 400 : 600;
        
        // Animate pulse
        pulse.animate([
            { 
                opacity: intensity * 0.8,
                transform: 'translate(-50%, -50%) scale(1)',
                boxShadow: `0 0 0 0 ${color}`
            },
            { 
                opacity: 0,
                transform: 'translate(-50%, -50%) scale(1.5)',
                boxShadow: `0 0 0 20px transparent`
            }
        ], {
            duration,
            easing: emotion === 'playful' ? 'cubic-bezier(0.68, -0.55, 0.27, 1.55)' : 'cubic-bezier(0.4, 0, 0.2, 1)'
        }).onfinish = () => pulse.remove();
    }
}

// Initialize emotional UI when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.emotionalTaskUI = new EmotionalTaskUI();
    });
} else {
    window.emotionalTaskUI = new EmotionalTaskUI();
}

// Export for use by other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EmotionalTaskUI;
}
