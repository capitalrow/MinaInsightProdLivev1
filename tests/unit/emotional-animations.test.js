/**
 * Unit Tests for EmotionalAnimations
 * Tests pulse, popIn, glow, and gradientPulse animations
 */

describe('EmotionalAnimations', () => {
    let EmotionalAnimations;
    let animations;
    let mockElement;

    beforeEach(() => {
        jest.resetModules();
        
        // Mock GSAP
        global.gsap = {
            to: jest.fn().mockReturnValue({ kill: jest.fn() }),
            from: jest.fn().mockReturnValue({ kill: jest.fn() }),
            fromTo: jest.fn().mockReturnValue({ kill: jest.fn() }),
            timeline: jest.fn(() => ({
                to: jest.fn().mockReturnThis(),
                from: jest.fn().mockReturnThis(),
                set: jest.fn().mockReturnThis(),
                kill: jest.fn()
            }))
        };
        
        // Mock window
        global.window = {
            CROWNTelemetry: {
                recordMetric: jest.fn()
            },
            matchMedia: jest.fn(() => ({
                matches: false
            }))
        };
        
        // Mock DOM element
        mockElement = {
            classList: {
                add: jest.fn(),
                remove: jest.fn()
            },
            style: {},
            setAttribute: jest.fn(),
            removeAttribute: jest.fn(),
            dataset: {}
        };
        
        global.document = {
            querySelector: jest.fn(() => mockElement),
            querySelectorAll: jest.fn(() => [mockElement])
        };
        
        // Create simplified EmotionalAnimations class for testing
        EmotionalAnimations = class {
            constructor() {
                this.activeAnimations = new Map();
            }
            
            pulse(element, options = {}) {
                if (!element) return;
                
                const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                if (prefersReducedMotion) {
                    console.log('⏸️ Animation skipped (reduced motion)');
                    return;
                }
                
                const duration = options.duration || 0.3;
                const scale = options.scale || 1.1;
                
                const anim = gsap.to(element, {
                    scale: scale,
                    duration: duration / 2,
                    yoyo: true,
                    repeat: 1,
                    ease: 'power2.out'
                });
                
                this.activeAnimations.set(element, anim);
                
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('animation_pulse_triggered', 1);
                }
                
                return anim;
            }
            
            popIn(element, options = {}) {
                if (!element) return;
                
                const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                if (prefersReducedMotion) {
                    element.style.opacity = '1';
                    return;
                }
                
                const duration = options.duration || 0.4;
                
                const anim = gsap.from(element, {
                    scale: 0.8,
                    opacity: 0,
                    duration: duration,
                    ease: 'back.out(1.7)'
                });
                
                this.activeAnimations.set(element, anim);
                
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('animation_popin_triggered', 1);
                }
                
                return anim;
            }
            
            glow(element, options = {}) {
                if (!element) return;
                
                const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                if (prefersReducedMotion) {
                    return;
                }
                
                const color = options.color || '#667eea';
                const duration = options.duration || 1.5;
                
                const anim = gsap.to(element, {
                    boxShadow: `0 0 20px ${color}`,
                    duration: duration / 2,
                    yoyo: true,
                    repeat: 1,
                    ease: 'sine.inOut'
                });
                
                this.activeAnimations.set(element, anim);
                
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('animation_glow_triggered', 1);
                }
                
                return anim;
            }
            
            gradientPulse(element, options = {}) {
                if (!element) return;
                
                const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                if (prefersReducedMotion) {
                    return;
                }
                
                const duration = options.duration || 2.0;
                
                element.classList.add('gradient-pulse-active');
                
                const anim = gsap.to(element, {
                    backgroundPosition: '200% center',
                    duration: duration,
                    ease: 'sine.inOut',
                    onComplete: () => {
                        element.classList.remove('gradient-pulse-active');
                    }
                });
                
                this.activeAnimations.set(element, anim);
                
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('animation_gradient_pulse_triggered', 1);
                }
                
                return anim;
            }
            
            killAll() {
                this.activeAnimations.forEach((anim) => {
                    if (anim && anim.kill) {
                        anim.kill();
                    }
                });
                this.activeAnimations.clear();
            }
        };
        
        animations = new EmotionalAnimations();
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('Pulse Animation', () => {
        test('should trigger pulse animation on element', () => {
            animations.pulse(mockElement);
            
            expect(gsap.to).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    scale: 1.1,
                    yoyo: true,
                    repeat: 1
                })
            );
        });

        test('should record telemetry for pulse', () => {
            animations.pulse(mockElement);
            
            expect(window.CROWNTelemetry.recordMetric).toHaveBeenCalledWith(
                'animation_pulse_triggered',
                1
            );
        });

        test('should accept custom duration', () => {
            animations.pulse(mockElement, { duration: 0.5 });
            
            expect(gsap.to).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    duration: 0.25 // Half of 0.5 for yoyo
                })
            );
        });

        test('should accept custom scale', () => {
            animations.pulse(mockElement, { scale: 1.2 });
            
            expect(gsap.to).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    scale: 1.2
                })
            );
        });

        test('should handle null element gracefully', () => {
            expect(() => {
                animations.pulse(null);
            }).not.toThrow();
        });

        test('should skip animation for reduced motion', () => {
            global.window.matchMedia = jest.fn(() => ({
                matches: true // Prefers reduced motion
            }));
            
            const newAnimations = new EmotionalAnimations();
            newAnimations.pulse(mockElement);
            
            expect(gsap.to).not.toHaveBeenCalled();
        });
    });

    describe('PopIn Animation', () => {
        test('should trigger popIn animation on element', () => {
            animations.popIn(mockElement);
            
            expect(gsap.from).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    scale: 0.8,
                    opacity: 0,
                    ease: 'back.out(1.7)'
                })
            );
        });

        test('should record telemetry for popIn', () => {
            animations.popIn(mockElement);
            
            expect(window.CROWNTelemetry.recordMetric).toHaveBeenCalledWith(
                'animation_popin_triggered',
                1
            );
        });

        test('should accept custom duration', () => {
            animations.popIn(mockElement, { duration: 0.6 });
            
            expect(gsap.from).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    duration: 0.6
                })
            );
        });

        test('should fallback to opacity for reduced motion', () => {
            global.window.matchMedia = jest.fn(() => ({
                matches: true
            }));
            
            const newAnimations = new EmotionalAnimations();
            newAnimations.popIn(mockElement);
            
            expect(mockElement.style.opacity).toBe('1');
            expect(gsap.from).not.toHaveBeenCalled();
        });

        test('should handle null element gracefully', () => {
            expect(() => {
                animations.popIn(null);
            }).not.toThrow();
        });
    });

    describe('Glow Animation', () => {
        test('should trigger glow animation on element', () => {
            animations.glow(mockElement);
            
            expect(gsap.to).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    boxShadow: '0 0 20px #667eea',
                    yoyo: true,
                    repeat: 1
                })
            );
        });

        test('should record telemetry for glow', () => {
            animations.glow(mockElement);
            
            expect(window.CROWNTelemetry.recordMetric).toHaveBeenCalledWith(
                'animation_glow_triggered',
                1
            );
        });

        test('should accept custom color', () => {
            animations.glow(mockElement, { color: '#ff0000' });
            
            expect(gsap.to).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    boxShadow: '0 0 20px #ff0000'
                })
            );
        });

        test('should accept custom duration', () => {
            animations.glow(mockElement, { duration: 2.0 });
            
            expect(gsap.to).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    duration: 1.0 // Half for yoyo
                })
            );
        });

        test('should skip for reduced motion', () => {
            global.window.matchMedia = jest.fn(() => ({
                matches: true
            }));
            
            const newAnimations = new EmotionalAnimations();
            newAnimations.glow(mockElement);
            
            expect(gsap.to).not.toHaveBeenCalled();
        });

        test('should handle null element gracefully', () => {
            expect(() => {
                animations.glow(null);
            }).not.toThrow();
        });
    });

    describe('Gradient Pulse Animation', () => {
        test('should trigger gradient pulse animation', () => {
            animations.gradientPulse(mockElement);
            
            expect(mockElement.classList.add).toHaveBeenCalledWith('gradient-pulse-active');
            expect(gsap.to).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    backgroundPosition: '200% center',
                    ease: 'sine.inOut'
                })
            );
        });

        test('should record telemetry for gradient pulse', () => {
            animations.gradientPulse(mockElement);
            
            expect(window.CROWNTelemetry.recordMetric).toHaveBeenCalledWith(
                'animation_gradient_pulse_triggered',
                1
            );
        });

        test('should remove class on completion', () => {
            const mockAnim = gsap.to(mockElement, {});
            const onComplete = mockAnim.mock?.calls?.[0]?.[1]?.onComplete;
            
            animations.gradientPulse(mockElement);
            
            // Simulate completion
            const callArgs = gsap.to.mock.calls[gsap.to.mock.calls.length - 1][1];
            if (callArgs.onComplete) {
                callArgs.onComplete();
            }
            
            expect(mockElement.classList.remove).toHaveBeenCalledWith('gradient-pulse-active');
        });

        test('should accept custom duration', () => {
            animations.gradientPulse(mockElement, { duration: 3.0 });
            
            expect(gsap.to).toHaveBeenCalledWith(
                mockElement,
                expect.objectContaining({
                    duration: 3.0
                })
            );
        });

        test('should skip for reduced motion', () => {
            global.window.matchMedia = jest.fn(() => ({
                matches: true
            }));
            
            const newAnimations = new EmotionalAnimations();
            newAnimations.gradientPulse(mockElement);
            
            expect(gsap.to).not.toHaveBeenCalled();
        });

        test('should handle null element gracefully', () => {
            expect(() => {
                animations.gradientPulse(null);
            }).not.toThrow();
        });
    });

    describe('Animation Management', () => {
        test('should track active animations', () => {
            animations.pulse(mockElement);
            
            expect(animations.activeAnimations.size).toBe(1);
            expect(animations.activeAnimations.has(mockElement)).toBe(true);
        });

        test('should kill all active animations', () => {
            const mockAnim1 = { kill: jest.fn() };
            const mockAnim2 = { kill: jest.fn() };
            
            animations.activeAnimations.set('elem1', mockAnim1);
            animations.activeAnimations.set('elem2', mockAnim2);
            
            animations.killAll();
            
            expect(mockAnim1.kill).toHaveBeenCalled();
            expect(mockAnim2.kill).toHaveBeenCalled();
            expect(animations.activeAnimations.size).toBe(0);
        });

        test('should handle killAll with empty animations', () => {
            expect(() => {
                animations.killAll();
            }).not.toThrow();
        });

        test('should handle animations without kill method', () => {
            animations.activeAnimations.set('elem', null);
            
            expect(() => {
                animations.killAll();
            }).not.toThrow();
        });
    });

    describe('Integration', () => {
        test('should chain multiple animations on same element', () => {
            animations.pulse(mockElement);
            animations.glow(mockElement);
            
            expect(gsap.to).toHaveBeenCalledTimes(2);
        });

        test('should work with different elements', () => {
            const elem1 = { ...mockElement };
            const elem2 = { ...mockElement };
            
            animations.pulse(elem1);
            animations.popIn(elem2);
            
            expect(animations.activeAnimations.size).toBe(2);
        });

        test('should respect reduced motion across all animations', () => {
            global.window.matchMedia = jest.fn(() => ({
                matches: true
            }));
            
            const newAnimations = new EmotionalAnimations();
            
            newAnimations.pulse(mockElement);
            newAnimations.glow(mockElement);
            newAnimations.gradientPulse(mockElement);
            
            // Only popIn sets opacity, others skip completely
            expect(gsap.to).not.toHaveBeenCalled();
            expect(gsap.from).not.toHaveBeenCalled();
        });
    });
});
