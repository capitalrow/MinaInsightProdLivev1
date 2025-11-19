class QuietStateManager {
    constructor(maxConcurrent = 3) {
        this.maxConcurrent = maxConcurrent;
        this.activeAnimations = new Map();
        this.animationQueue = [];
        this.nextId = 1;
        
        console.log('[QuietStateManager] Initialized with maxConcurrent:', maxConcurrent);
    }

    queueAnimation(animationFn, options = {}) {
        const {
            priority = 5,
            duration = 300,
            onComplete = null,
            metadata = {}
        } = options;

        const animationId = `anim_${this.nextId++}`;

        if (this.activeAnimations.size < this.maxConcurrent) {
            this._startAnimation(animationId, animationFn, duration, onComplete, metadata);
        } else {
            this.animationQueue.push({
                id: animationId,
                fn: animationFn,
                priority,
                duration,
                onComplete,
                metadata,
                queuedAt: Date.now()
            });

            this.animationQueue.sort((a, b) => b.priority - a.priority);

            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('animation_queued', 1);
                window.CROWNTelemetry.recordMetric('animation_queue_depth', this.animationQueue.length);
            }
        }

        return animationId;
    }

    _startAnimation(id, animationFn, duration, onComplete, metadata) {
        const startTime = Date.now();
        let timeoutId = null;
        let cancelled = false;
        let userCancelFn = null;

        const cleanup = () => {
            if (cancelled) return;
            
            this.activeAnimations.delete(id);

            if (window.CROWNTelemetry) {
                const actualDuration = Date.now() - startTime;
                window.CROWNTelemetry.recordMetric('animation_duration_ms', actualDuration);
                window.CROWNTelemetry.recordMetric('animation_completed', 1);
            }

            if (onComplete) {
                onComplete();
            }

            this._processQueue();
        };

        const cancel = () => {
            cancelled = true;
            
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }
            
            if (userCancelFn) {
                try {
                    userCancelFn();
                } catch (err) {
                    console.error('[QuietStateManager] User cancel error:', err);
                }
            }
            
            this.activeAnimations.delete(id);
            
            if (onComplete) {
                onComplete();
            }
            
            this._processQueue();
        };

        this.activeAnimations.set(id, {
            startTime,
            duration,
            metadata,
            cancel
        });

        try {
            const result = animationFn((cancelFn) => {
                userCancelFn = cancelFn;
            });
            
            if (result && typeof result.then === 'function') {
                result.then(cleanup).catch(err => {
                    console.error('[QuietStateManager] Animation error:', err);
                    cleanup();
                });
            } else {
                timeoutId = setTimeout(cleanup, duration);
            }
        } catch (err) {
            console.error('[QuietStateManager] Animation error:', err);
            cleanup();
        }

        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('animation_started', 1);
            window.CROWNTelemetry.recordMetric('concurrent_animations', this.activeAnimations.size);
        }
    }

    _processQueue() {
        while (this.animationQueue.length > 0 && this.activeAnimations.size < this.maxConcurrent) {
            const next = this.animationQueue.shift();
            
            if (window.CROWNTelemetry) {
                const queueTime = Date.now() - next.queuedAt;
                window.CROWNTelemetry.recordMetric('animation_queue_wait_ms', queueTime);
                window.CROWNTelemetry.recordMetric('animation_dequeued', 1);
            }

            this._startAnimation(next.id, next.fn, next.duration, next.onComplete, next.metadata);
        }
    }

    cancelAnimation(id) {
        const animation = this.activeAnimations.get(id);
        if (animation && animation.cancel) {
            animation.cancel();
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('animation_cancelled', 1);
            }
            
            return true;
        }

        const queueIndex = this.animationQueue.findIndex(item => item.id === id);
        if (queueIndex !== -1) {
            this.animationQueue.splice(queueIndex, 1);
            
            if (window.CROWNTelemetry) {
                window.CROWNTelemetry.recordMetric('animation_cancelled', 1);
                window.CROWNTelemetry.recordMetric('animation_queue_depth', this.animationQueue.length);
            }
            
            return true;
        }

        return false;
    }

    cancelAll() {
        // Cancel all active animations
        for (const [id, animation] of this.activeAnimations.entries()) {
            if (animation.cancel) {
                animation.cancel();
            }
        }
        
        this.activeAnimations.clear();
        this.animationQueue = [];
        
        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('animations_cancelled_all', 1);
        }
    }

    getStats() {
        return {
            active: this.activeAnimations.size,
            queued: this.animationQueue.length,
            maxConcurrent: this.maxConcurrent,
            calmScore: this._calculateCalmScore()
        };
    }

    // Alias for CalmScoreWidget compatibility
    getState() {
        return this.getStats();
    }

    _calculateCalmScore() {
        const utilizationRatio = this.activeAnimations.size / this.maxConcurrent;
        const queuePressure = Math.min(this.animationQueue.length / 10, 1);
        
        const calmScore = Math.max(0, Math.min(100, 
            100 - (utilizationRatio * 50) - (queuePressure * 50)
        ));

        return Math.round(calmScore);
    }

    setMaxConcurrent(max) {
        this.maxConcurrent = Math.max(1, max);
        this._processQueue();
    }
}

window.QuietStateManager = QuietStateManager;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.quietStateManager) {
            window.quietStateManager = new QuietStateManager(3);
            console.log('[QuietStateManager] Global instance created');
        }
    });
}
