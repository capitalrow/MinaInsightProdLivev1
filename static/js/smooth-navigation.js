/**
 * Smooth Navigation Manager - CROWN⁴ Cinematic Transitions
 * 
 * Provides GSAP-powered page transitions for seamless navigation
 */

(function() {
    'use strict';

    class SmoothNavigation {
        constructor() {
            this.isNavigating = false;
            this.transitionDuration = 0.6; // 600ms for smooth transitions
            this.init();
        }

        init() {
            console.log('🎬 Smooth Navigation initialized with GSAP transitions');
            // NOTE: Meeting card navigation is handled by dashboard template inline handlers
            // to support session-based navigation with custom loading overlays
            // this.setupMeetingCardNavigation();
            this.setupLinkInterception();
        }

        /**
         * Setup click handlers for meeting cards
         */
        setupMeetingCardNavigation() {
            document.addEventListener('click', (e) => {
                // Find the meeting card (could be the card itself or a child element)
                const meetingCard = e.target.closest('.meeting-card');
                
                if (meetingCard && !this.isNavigating) {
                    // Don't navigate if clicking on interactive elements
                    if (e.target.closest('button, a, input, select, textarea')) {
                        return;
                    }

                    e.preventDefault();
                    const meetingId = meetingCard.dataset.meetingId;
                    
                    if (meetingId) {
                        const targetUrl = `/dashboard/meeting/${meetingId}`;
                        this.navigateTo(targetUrl, meetingCard);
                    }
                }
            });

            // Add hover effect for meeting cards
            const meetingCards = document.querySelectorAll('.meeting-card');
            meetingCards.forEach(card => {
                card.style.cursor = 'pointer';
                
                // Add visual feedback on hover
                card.addEventListener('mouseenter', () => {
                    if (!this.isNavigating) {
                        gsap.to(card, {
                            scale: 1.02,
                            duration: 0.3,
                            ease: 'power2.out'
                        });
                    }
                });

                card.addEventListener('mouseleave', () => {
                    gsap.to(card, {
                        scale: 1,
                        duration: 0.3,
                        ease: 'power2.out'
                    });
                });
            });
        }

        /**
         * Setup interception for internal links
         */
        setupLinkInterception() {
            document.addEventListener('click', (e) => {
                const link = e.target.closest('a');
                
                if (link && this.shouldInterceptLink(link) && !this.isNavigating) {
                    e.preventDefault();
                    this.navigateTo(link.href);
                }
            });
        }

        /**
         * Check if link should be intercepted for smooth navigation
         */
        shouldInterceptLink(link) {
            // Don't intercept external links
            if (link.hostname !== window.location.hostname) {
                return false;
            }

            // Don't intercept links that should open in new tab
            if (link.target === '_blank') {
                return false;
            }

            // Don't intercept links with data-no-transition attribute
            if (link.hasAttribute('data-no-transition')) {
                return false;
            }

            // Don't intercept API calls
            if (link.href.includes('/api/')) {
                return false;
            }

            return true;
        }

        /**
         * Navigate to URL with smooth GSAP transition
         */
        navigateTo(url, sourceElement = null) {
            if (this.isNavigating) return;
            
            this.isNavigating = true;
            console.log(`🎬 Navigating to: ${url}`);
            
            // Emit PJAX beforeTransition event for lifecycle hooks (e.g., mobile gestures)
            window.dispatchEvent(new CustomEvent('pjax:beforeTransition', {
                detail: { url, sourceElement }
            }));

            // Create transition overlay
            const overlay = this.createTransitionOverlay();
            document.body.appendChild(overlay);

            // Animation timeline
            const tl = gsap.timeline({
                onComplete: () => {
                    window.location.href = url;
                }
            });

            // If source element exists, morph from it
            if (sourceElement) {
                const rect = sourceElement.getBoundingClientRect();
                
                // Set initial overlay position to match source element
                gsap.set(overlay, {
                    clipPath: `circle(0% at ${rect.left + rect.width/2}px ${rect.top + rect.height/2}px)`
                });

                // Expand from source element
                tl.to(overlay, {
                    clipPath: `circle(150% at ${rect.left + rect.width/2}px ${rect.top + rect.height/2}px)`,
                    duration: this.transitionDuration,
                    ease: 'power3.inOut'
                });
            } else {
                // Standard fade transition
                tl.fromTo(overlay, {
                    opacity: 0
                }, {
                    opacity: 1,
                    duration: this.transitionDuration,
                    ease: 'power2.inOut'
                });
            }

            // Fade out current content
            tl.to('body > *:not(.transition-overlay)', {
                opacity: 0,
                duration: this.transitionDuration * 0.5,
                ease: 'power2.in'
            }, `-=${this.transitionDuration * 0.3}`);
        }

        /**
         * Create transition overlay element
         */
        createTransitionOverlay() {
            const overlay = document.createElement('div');
            overlay.className = 'transition-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.95) 0%, rgba(118, 75, 162, 0.95) 100%);
                z-index: 99999;
                pointer-events: none;
                display: flex;
                align-items: center;
                justify-content: center;
            `;

            // Add loading spinner
            const spinner = document.createElement('div');
            spinner.innerHTML = `
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="animation: spin 1s linear infinite;">
                    <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" stroke-width="3"/>
                    <path d="M12 2a10 10 0 0 1 10 10" stroke="white" stroke-width="3" stroke-linecap="round"/>
                </svg>
                <style>
                    @keyframes spin {
                        to { transform: rotate(360deg); }
                    }
                </style>
            `;
            overlay.appendChild(spinner);

            return overlay;
        }

        /**
         * Animate page entrance (call this on page load)
         */
        static animatePageEntrance() {
            // Remove any existing transition overlay
            const existingOverlay = document.querySelector('.transition-overlay');
            if (existingOverlay) {
                existingOverlay.remove();
            }

            // Animate content fade in
            gsap.fromTo('body > *:not(script):not(style)', {
                opacity: 0,
                y: 20
            }, {
                opacity: 1,
                y: 0,
                duration: 0.6,
                ease: 'power3.out',
                stagger: 0.05,
                onComplete: () => {
                    // Emit navigation complete event for lifecycle hooks (e.g., mobile gestures reinit)
                    window.dispatchEvent(new CustomEvent('navigation:complete'));
                    window.dispatchEvent(new CustomEvent('pjax:complete'));
                }
            });
        }
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.smoothNavigation = new SmoothNavigation();
            SmoothNavigation.animatePageEntrance();
        });
    } else {
        window.smoothNavigation = new SmoothNavigation();
        SmoothNavigation.animatePageEntrance();
    }
})();
