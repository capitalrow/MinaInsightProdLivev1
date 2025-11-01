class EmotionalAnimations {
    constructor() {
        this.injectStyles();
        console.log('[EmotionalAnimations] Initialized');
    }

    injectStyles() {
        if (document.getElementById('emotional-animations-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'emotional-animations-styles';
        styles.textContent = `
            @keyframes burst {
                0% {
                    transform: scale(1);
                    opacity: 1;
                }
                50% {
                    transform: scale(1.2);
                    opacity: 0.8;
                }
                100% {
                    transform: scale(1);
                    opacity: 1;
                }
            }

            @keyframes shimmer {
                0% {
                    background-position: -200% center;
                }
                100% {
                    background-position: 200% center;
                }
            }

            @keyframes morph {
                0%, 100% {
                    border-radius: var(--radius-xl);
                    transform: scale(1);
                }
                25% {
                    border-radius: var(--radius-md);
                    transform: scale(1.02);
                }
                50% {
                    border-radius: var(--radius-2xl);
                    transform: scale(0.98);
                }
                75% {
                    border-radius: var(--radius-lg);
                    transform: scale(1.01);
                }
            }

            @keyframes slideInBounce {
                0% {
                    transform: translateY(-100px);
                    opacity: 0;
                }
                60% {
                    transform: translateY(5px);
                    opacity: 1;
                }
                80% {
                    transform: translateY(-2px);
                }
                100% {
                    transform: translateY(0);
                }
            }

            @keyframes pulse {
                0%, 100% {
                    transform: scale(1);
                    opacity: 1;
                }
                50% {
                    transform: scale(1.15);
                    opacity: 0.9;
                }
            }

            @keyframes glow {
                0%, 100% {
                    box-shadow: 0 0 5px rgba(99, 102, 241, 0.3);
                }
                50% {
                    box-shadow: 0 0 20px rgba(99, 102, 241, 0.6);
                }
            }

            @keyframes gradientPulse {
                0%, 100% {
                    background-position: 0% 50%;
                }
                50% {
                    background-position: 100% 50%;
                }
            }

            @keyframes popIn {
                0% {
                    transform: scale(0.8);
                    opacity: 0;
                }
                50% {
                    transform: scale(1.05);
                }
                100% {
                    transform: scale(1);
                    opacity: 1;
                }
            }

            .emotion-burst {
                animation: burst 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
            }

            .emotion-pulse {
                animation: pulse 0.4s ease-in-out;
            }

            .emotion-glow {
                animation: glow 1.5s ease-in-out infinite;
            }

            .emotion-gradient-pulse {
                background: linear-gradient(270deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1));
                background-size: 200% 200%;
                animation: gradientPulse 3s ease infinite;
            }

            .emotion-pop-in {
                animation: popIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            }

            .emotion-shimmer {
                position: relative;
                overflow: hidden;
            }

            .emotion-shimmer::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(
                    90deg,
                    transparent 0%,
                    rgba(255, 255, 255, 0.4) 50%,
                    transparent 100%
                );
                background-size: 200% 100%;
                animation: shimmer 1.5s ease-in-out;
                pointer-events: none;
                z-index: 1;
            }

            .emotion-morph {
                animation: morph 0.8s ease-in-out;
            }

            .emotion-slide {
                animation: slideInBounce 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
            }

            @media (prefers-reduced-motion: reduce) {
                .emotion-burst,
                .emotion-shimmer::before,
                .emotion-morph,
                .emotion-slide {
                    animation: none !important;
                }
            }
        `;
        document.head.appendChild(styles);
    }

    burst(element, options = {}) {
        const {
            duration = 500,
            onComplete = null,
            emotion_cue = 'burst'
        } = options;

        if (!element || !window.quietStateManager) {
            if (element) {
                element.classList.add('emotion-burst');
                setTimeout(() => element.classList.remove('emotion-burst'), duration);
            }
            return;
        }

        return window.quietStateManager.queueAnimation((setCancelHandler) => {
            element.classList.add('emotion-burst');

            const timeoutId = setTimeout(() => {
                element.classList.remove('emotion-burst');
                if (onComplete) onComplete();
            }, duration);

            setCancelHandler(() => {
                clearTimeout(timeoutId);
                element.classList.remove('emotion-burst');
            });

            if (window.CROWNTelemetry && window.CROWNTelemetry.recordEmotionCue) {
                window.CROWNTelemetry.recordEmotionCue(emotion_cue);
            }
        }, { duration, priority: 8, metadata: { type: 'emotion_burst', emotion_cue } });
    }

    shimmer(element, options = {}) {
        const {
            duration = 1500,
            onComplete = null,
            emotion_cue = 'shimmer'
        } = options;

        if (!element || !window.quietStateManager) {
            if (element) {
                element.classList.add('emotion-shimmer');
                setTimeout(() => element.classList.remove('emotion-shimmer'), duration);
            }
            return;
        }

        return window.quietStateManager.queueAnimation((setCancelHandler) => {
            element.classList.add('emotion-shimmer');

            const timeoutId = setTimeout(() => {
                element.classList.remove('emotion-shimmer');
                if (onComplete) onComplete();
            }, duration);

            setCancelHandler(() => {
                clearTimeout(timeoutId);
                element.classList.remove('emotion-shimmer');
            });

            if (window.CROWNTelemetry && window.CROWNTelemetry.recordEmotionCue) {
                window.CROWNTelemetry.recordEmotionCue(emotion_cue);
            }
        }, { duration, priority: 6, metadata: { type: 'emotion_shimmer', emotion_cue } });
    }

    morph(element, options = {}) {
        const {
            duration = 800,
            onComplete = null,
            emotion_cue = 'morph'
        } = options;

        if (!element || !window.quietStateManager) {
            if (element) {
                element.classList.add('emotion-morph');
                setTimeout(() => element.classList.remove('emotion-morph'), duration);
            }
            return;
        }

        return window.quietStateManager.queueAnimation((setCancelHandler) => {
            element.classList.add('emotion-morph');

            const timeoutId = setTimeout(() => {
                element.classList.remove('emotion-morph');
                if (onComplete) onComplete();
            }, duration);

            setCancelHandler(() => {
                clearTimeout(timeoutId);
                element.classList.remove('emotion-morph');
            });

            if (window.CROWNTelemetry && window.CROWNTelemetry.recordEmotionCue) {
                window.CROWNTelemetry.recordEmotionCue(emotion_cue);
            }
        }, { duration, priority: 7, metadata: { type: 'emotion_morph', emotion_cue } });
    }

    slide(element, options = {}) {
        const {
            duration = 600,
            onComplete = null,
            emotion_cue = 'slide'
        } = options;

        if (!element || !window.quietStateManager) {
            if (element) {
                element.classList.add('emotion-slide');
                setTimeout(() => element.classList.remove('emotion-slide'), duration);
            }
            return;
        }

        return window.quietStateManager.queueAnimation((setCancelHandler) => {
            element.classList.add('emotion-slide');

            const timeoutId = setTimeout(() => {
                element.classList.remove('emotion-slide');
                if (onComplete) onComplete();
            }, duration);

            setCancelHandler(() => {
                clearTimeout(timeoutId);
                element.classList.remove('emotion-slide');
            });

            if (window.CROWNTelemetry && window.CROWNTelemetry.recordEmotionCue) {
                window.CROWNTelemetry.recordEmotionCue(emotion_cue);
            }
        }, { duration, priority: 7, metadata: { type: 'emotion_slide', emotion_cue } });
    }

    pulse(element, options = {}) {
        const {
            duration = 400,
            onComplete = null,
            emotion_cue = 'pulse'
        } = options;

        if (!element || !window.quietStateManager) {
            if (element) {
                element.classList.add('emotion-pulse');
                setTimeout(() => element.classList.remove('emotion-pulse'), duration);
            }
            return;
        }

        return window.quietStateManager.queueAnimation((setCancelHandler) => {
            element.classList.add('emotion-pulse');

            const timeoutId = setTimeout(() => {
                element.classList.remove('emotion-pulse');
                if (onComplete) onComplete();
            }, duration);

            setCancelHandler(() => {
                clearTimeout(timeoutId);
                element.classList.remove('emotion-pulse');
            });

            if (window.CROWNTelemetry && window.CROWNTelemetry.recordEmotionCue) {
                window.CROWNTelemetry.recordEmotionCue(emotion_cue);
            }
        }, { duration, priority: 5, metadata: { type: 'emotion_pulse', emotion_cue } });
    }

    glow(element, options = {}) {
        const {
            duration = 1500,
            onComplete = null,
            emotion_cue = 'glow'
        } = options;

        if (!element || !window.quietStateManager) {
            if (element) {
                element.classList.add('emotion-glow');
                setTimeout(() => element.classList.remove('emotion-glow'), duration);
            }
            return;
        }

        return window.quietStateManager.queueAnimation((setCancelHandler) => {
            element.classList.add('emotion-glow');

            const timeoutId = setTimeout(() => {
                element.classList.remove('emotion-glow');
                if (onComplete) onComplete();
            }, duration);

            setCancelHandler(() => {
                clearTimeout(timeoutId);
                element.classList.remove('emotion-glow');
            });

            if (window.CROWNTelemetry && window.CROWNTelemetry.recordEmotionCue) {
                window.CROWNTelemetry.recordEmotionCue(emotion_cue);
            }
        }, { duration, priority: 4, metadata: { type: 'emotion_glow', emotion_cue } });
    }

    gradientPulse(element, options = {}) {
        const {
            duration = 3000,
            onComplete = null,
            emotion_cue = 'gradient_pulse'
        } = options;

        if (!element || !window.quietStateManager) {
            if (element) {
                element.classList.add('emotion-gradient-pulse');
                setTimeout(() => element.classList.remove('emotion-gradient-pulse'), duration);
            }
            return;
        }

        return window.quietStateManager.queueAnimation((setCancelHandler) => {
            element.classList.add('emotion-gradient-pulse');

            const timeoutId = setTimeout(() => {
                element.classList.remove('emotion-gradient-pulse');
                if (onComplete) onComplete();
            }, duration);

            setCancelHandler(() => {
                clearTimeout(timeoutId);
                element.classList.remove('emotion-gradient-pulse');
            });

            if (window.CROWNTelemetry && window.CROWNTelemetry.recordEmotionCue) {
                window.CROWNTelemetry.recordEmotionCue(emotion_cue);
            }
        }, { duration, priority: 3, metadata: { type: 'emotion_gradient_pulse', emotion_cue } });
    }

    popIn(element, options = {}) {
        const {
            duration = 400,
            onComplete = null,
            emotion_cue = 'pop_in'
        } = options;

        if (!element || !window.quietStateManager) {
            if (element) {
                element.classList.add('emotion-pop-in');
                setTimeout(() => element.classList.remove('emotion-pop-in'), duration);
            }
            return;
        }

        return window.quietStateManager.queueAnimation((setCancelHandler) => {
            element.classList.add('emotion-pop-in');

            const timeoutId = setTimeout(() => {
                element.classList.remove('emotion-pop-in');
                if (onComplete) onComplete();
            }, duration);

            setCancelHandler(() => {
                clearTimeout(timeoutId);
                element.classList.remove('emotion-pop-in');
            });

            if (window.CROWNTelemetry && window.CROWNTelemetry.recordEmotionCue) {
                window.CROWNTelemetry.recordEmotionCue(emotion_cue);
            }
        }, { duration, priority: 7, metadata: { type: 'emotion_pop_in', emotion_cue } });
    }

    celebrate(element, sequence = ['burst', 'shimmer']) {
        if (!element) return;

        let delay = 0;
        sequence.forEach((animationType, index) => {
            setTimeout(() => {
                if (this[animationType]) {
                    this[animationType](element, {
                        emotion_cue: `celebrate_${animationType}`
                    });
                }
            }, delay);
            delay += index === 0 ? 500 : 800;
        });
    }
}

window.EmotionalAnimations = EmotionalAnimations;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.emotionalAnimations) {
            window.emotionalAnimations = new EmotionalAnimations();
            console.log('[EmotionalAnimations] Global instance created');
        }
    });
}
