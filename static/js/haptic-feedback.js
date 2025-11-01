/**
 * CROWN⁴.5 Haptic Feedback System
 * Provides tactile feedback for emotional architecture
 * Supports mobile devices, trackpads (limited), and future devices
 */

class HapticFeedbackManager {
    constructor() {
        this.enabled = true;
        this.supported = this.checkSupport();
        this.patterns = this.definePatterns();
        this.lastHapticTime = 0;
        this.minInterval = 50; // Prevent haptic spam (50ms minimum between feedback)
        
        this.init();
    }

    init() {
        // Check user preferences
        this.loadPreferences();

        // Listen for key events
        this.attachEventListeners();

        console.log(`🎮 CROWN⁴.5 Haptic Feedback ${this.supported ? 'enabled' : 'not supported on this device'}`);
    }

    checkSupport() {
        // Check for Vibration API (mobile/tablet)
        if ('vibrate' in navigator) {
            return 'vibration';
        }

        // Check for experimental Haptic API (some browsers)
        if ('haptics' in navigator) {
            return 'haptics';
        }

        // Check for gamepad vibration
        if ('getGamepads' in navigator) {
            const gamepads = navigator.getGamepads();
            if (gamepads && gamepads.some(g => g && g.vibrationActuator)) {
                return 'gamepad';
            }
        }

        // Fallback: assume trackpad on macOS (no direct API, but we can try)
        const isMac = /Mac|iPad|iPhone/.test(navigator.platform);
        if (isMac) {
            return 'trackpad-fallback';
        }

        return false;
    }

    definePatterns() {
        return {
            // Task interactions
            taskComplete: [50, 30, 50],          // Double tap
            taskCreate: [30],                     // Single light tap
            taskDelete: [100],                    // Single strong tap
            taskUpdate: [20],                     // Subtle tap
            
            // Errors and warnings
            error: [100, 50, 100, 50, 100],      // Triple strong tap
            warning: [50, 30, 50],                // Double medium tap
            
            // UI interactions
            buttonPress: [10],                    // Very light tap
            toggle: [20, 10, 20],                 // Light double tap
            swipe: [15],                          // Quick light tap
            
            // Success states
            success: [30, 20, 50],                // Crescendo
            celebration: [50, 30, 50, 30, 100],   // Party!
            
            // Sync and offline
            syncComplete: [30, 20, 30],           // Smooth sync
            offlineMode: [100, 100],              // Strong double tap
            onlineMode: [50, 30, 50],             // Back online
            
            // Drag and drop
            dragStart: [20],                      // Pick up
            dragDrop: [40],                       // Drop
            dragCancel: [10, 10],                 // Cancel
            
            // Notifications
            notification: [30, 50, 30],           // Attention
            urgentNotification: [100, 50, 100],   // Urgent!
        };
    }

    loadPreferences() {
        try {
            const stored = localStorage.getItem('crown_haptics_enabled');
            if (stored !== null) {
                this.enabled = stored === 'true';
            }
        } catch (error) {
            console.warn('Failed to load haptic preferences:', error);
        }
    }

    savePreferences() {
        try {
            localStorage.setItem('crown_haptics_enabled', this.enabled.toString());
        } catch (error) {
            console.warn('Failed to save haptic preferences:', error);
        }
    }

    attachEventListeners() {
        // Task completion
        window.addEventListener('task:completed', () => {
            this.trigger('taskComplete');
        });

        // Task creation
        window.addEventListener('task:created', () => {
            this.trigger('taskCreate');
        });

        // Task deletion
        window.addEventListener('task:deleted', () => {
            this.trigger('taskDelete');
        });

        // Task updates
        window.addEventListener('task:updated', () => {
            this.trigger('taskUpdate');
        });

        // Errors
        window.addEventListener('crown:error', (e) => {
            if (e.detail && e.detail.severity === 'critical') {
                this.trigger('error');
            } else {
                this.trigger('warning');
            }
        });

        // Success states
        window.addEventListener('crown:success', () => {
            this.trigger('success');
        });

        // Sync events
        window.addEventListener('sync:complete', () => {
            this.trigger('syncComplete');
        });

        window.addEventListener('offline:mode', () => {
            this.trigger('offlineMode');
        });

        window.addEventListener('online:mode', () => {
            this.trigger('onlineMode');
        });

        // Button presses (add to existing buttons via event delegation)
        document.addEventListener('click', (e) => {
            const button = e.target.closest('button, .btn, [role="button"]');
            if (button && !button.hasAttribute('data-no-haptic')) {
                this.trigger('buttonPress');
            }
        });

        // Toggle switches
        document.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox' || e.target.type === 'radio') {
                this.trigger('toggle');
            }
        });
    }

    trigger(patternName, options = {}) {
        if (!this.enabled || !this.supported) {
            return false;
        }

        // Rate limiting to prevent haptic spam
        const now = Date.now();
        if (now - this.lastHapticTime < this.minInterval) {
            return false;
        }
        this.lastHapticTime = now;

        const pattern = this.patterns[patternName];
        if (!pattern) {
            console.warn(`Unknown haptic pattern: ${patternName}`);
            return false;
        }

        // Apply intensity multiplier if provided
        const intensity = options.intensity || 1.0;
        const adjustedPattern = pattern.map(duration => Math.round(duration * intensity));

        return this.vibrate(adjustedPattern);
    }

    vibrate(pattern) {
        try {
            switch (this.supported) {
                case 'vibration':
                    return this.vibrateWithAPI(pattern);
                
                case 'haptics':
                    return this.vibrateWithHaptics(pattern);
                
                case 'gamepad':
                    return this.vibrateWithGamepad(pattern);
                
                case 'trackpad-fallback':
                    // No direct API for trackpad, fallback to visual feedback
                    return this.visualFeedback(pattern);
                
                default:
                    return false;
            }
        } catch (error) {
            console.warn('Haptic feedback failed:', error);
            return false;
        }
    }

    vibrateWithAPI(pattern) {
        if (!navigator.vibrate) return false;
        
        // Convert pattern array to alternating vibrate/pause format
        const vibratePattern = [];
        pattern.forEach((duration, index) => {
            vibratePattern.push(duration);
            if (index < pattern.length - 1) {
                vibratePattern.push(20); // 20ms pause between vibrations
            }
        });

        navigator.vibrate(vibratePattern);
        
        // Record telemetry
        if (window.CROWNTelemetry && window.CROWNTelemetry.recordMetric) {
            window.CROWNTelemetry.recordMetric('haptic_feedback_triggered', 1);
        }
        
        return true;
    }

    vibrateWithHaptics(pattern) {
        // Experimental Haptics API (not widely supported yet)
        if (!navigator.haptics || !navigator.haptics.vibrate) return false;
        
        navigator.haptics.vibrate({
            duration: pattern.reduce((sum, d) => sum + d, 0),
            pattern: pattern
        });
        
        return true;
    }

    vibrateWithGamepad(pattern) {
        const gamepads = navigator.getGamepads();
        if (!gamepads) return false;

        let triggered = false;
        for (const gamepad of gamepads) {
            if (gamepad && gamepad.vibrationActuator) {
                const duration = pattern.reduce((sum, d) => sum + d, 0);
                gamepad.vibrationActuator.playEffect('dual-rumble', {
                    duration: duration,
                    strongMagnitude: 0.5,
                    weakMagnitude: 0.3
                });
                triggered = true;
            }
        }

        return triggered;
    }

    visualFeedback(pattern) {
        // Fallback for devices without haptic support
        // Create a subtle visual pulse
        const pulse = document.createElement('div');
        pulse.className = 'haptic-visual-feedback';
        pulse.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            width: 100px;
            height: 100px;
            margin: -50px 0 0 -50px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.3), transparent);
            pointer-events: none;
            z-index: 999999;
            animation: hapticPulse 0.3s ease-out;
        `;

        document.body.appendChild(pulse);

        setTimeout(() => pulse.remove(), 300);

        return true;
    }

    setEnabled(enabled) {
        this.enabled = enabled;
        this.savePreferences();
        
        // Trigger feedback to confirm change
        if (enabled) {
            setTimeout(() => this.trigger('success'), 100);
        }
    }

    isEnabled() {
        return this.enabled;
    }

    isSupported() {
        return this.supported !== false;
    }

    getSupportedType() {
        return this.supported;
    }

    customPattern(pattern, intensity = 1.0) {
        return this.vibrate(pattern.map(d => Math.round(d * intensity)));
    }

    addPattern(name, pattern) {
        this.patterns[name] = pattern;
    }
}

// Add CSS for visual feedback fallback
const style = document.createElement('style');
style.textContent = `
    @keyframes hapticPulse {
        0% {
            transform: scale(0);
            opacity: 0;
        }
        50% {
            opacity: 0.5;
        }
        100% {
            transform: scale(1);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Initialize global instance
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.hapticFeedback = new HapticFeedbackManager();
    });
} else {
    window.hapticFeedback = new HapticFeedbackManager();
}

console.log('🎮 CROWN⁴.5 Haptic Feedback System loaded');
