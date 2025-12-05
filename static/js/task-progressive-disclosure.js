/**
 * CROWN⁴.8 Progressive Disclosure System
 * 
 * Features:
 * - Mobile tap-to-expand cards
 * - Swipe gestures (left: complete, right: snooze)
 * - Haptic feedback on interactions
 * - Completion celebration particles
 * - Graceful degradation for unsupported features
 */

class TaskProgressiveDisclosure {
    constructor(options = {}) {
        this.options = {
            swipeThreshold: 0.3, // 30% of card width to trigger action
            swipeVelocityThreshold: 0.5, // px/ms
            hapticEnabled: true,
            celebrationEnabled: true,
            ...options
        };
        
        this.isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        this.supportsHaptic = 'vibrate' in navigator;
        this.isLowEndDevice = this.detectLowEndDevice();
        
        this.activeSwipeCard = null;
        this.swipeStartX = 0;
        this.swipeStartY = 0;
        this.swipeStartTime = 0;
        
        this.init();
    }
    
    init() {
        this.bindCardInteractions();
        this.bindSwipeGestures();
        this.setupCompletionObserver();
        this.addDensityToggle();
        
        console.log('[ProgressiveDisclosure] Initialized', {
            touch: this.isTouchDevice,
            haptic: this.supportsHaptic,
            lowEnd: this.isLowEndDevice
        });
    }
    
    /**
     * Detect low-end devices for performance optimization
     */
    detectLowEndDevice() {
        // Check hardware concurrency (CPU cores)
        const cores = navigator.hardwareConcurrency || 2;
        // Check device memory if available
        const memory = navigator.deviceMemory || 4;
        
        return cores <= 2 || memory <= 2;
    }
    
    /**
     * Bind card tap/click interactions
     */
    bindCardInteractions() {
        document.addEventListener('click', (e) => {
            const card = e.target.closest('.task-card');
            if (!card) return;
            
            // Don't expand if clicking interactive elements
            const interactiveElements = [
                '.task-checkbox',
                '.task-title',
                '.task-menu-trigger',
                '.quick-action-btn',
                '.priority-dot',
                '.due-date-compact',
                '.assignee-compact',
                '.provenance-compact',
                'button',
                'input',
                'a'
            ];
            
            const isInteractive = interactiveElements.some(sel => e.target.closest(sel));
            if (isInteractive) return;
            
            // Toggle expanded state on mobile
            if (this.isTouchDevice) {
                this.toggleCardExpanded(card);
            }
        });
        
        // Close expanded cards when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.task-card')) {
                this.collapseAllCards();
            }
        });
    }
    
    /**
     * Toggle card expanded state (mobile)
     */
    toggleCardExpanded(card) {
        const wasExpanded = card.classList.contains('expanded');
        
        // Collapse all other cards first
        this.collapseAllCards();
        
        if (!wasExpanded) {
            card.classList.add('expanded');
            this.triggerHaptic('light');
        }
    }
    
    /**
     * Collapse all expanded cards
     */
    collapseAllCards() {
        document.querySelectorAll('.task-card.expanded').forEach(card => {
            card.classList.remove('expanded');
        });
    }
    
    /**
     * Bind swipe gesture handlers
     */
    bindSwipeGestures() {
        if (!this.isTouchDevice) return;
        
        document.addEventListener('touchstart', (e) => this.handleSwipeStart(e), { passive: true });
        document.addEventListener('touchmove', (e) => this.handleSwipeMove(e), { passive: false });
        document.addEventListener('touchend', (e) => this.handleSwipeEnd(e), { passive: true });
    }
    
    handleSwipeStart(e) {
        const card = e.target.closest('.task-card');
        if (!card) return;
        
        // Don't start swipe on interactive elements
        if (e.target.closest('.task-checkbox, .task-menu-trigger, button, input')) {
            return;
        }
        
        this.activeSwipeCard = card;
        this.swipeStartX = e.touches[0].clientX;
        this.swipeStartY = e.touches[0].clientY;
        this.swipeStartTime = Date.now();
        
        card.style.transition = 'none';
    }
    
    handleSwipeMove(e) {
        if (!this.activeSwipeCard) return;
        
        const currentX = e.touches[0].clientX;
        const currentY = e.touches[0].clientY;
        const diffX = currentX - this.swipeStartX;
        const diffY = currentY - this.swipeStartY;
        
        // If vertical scroll is dominant, cancel swipe
        if (Math.abs(diffY) > Math.abs(diffX) * 1.5) {
            this.cancelSwipe();
            return;
        }
        
        // Prevent scrolling during horizontal swipe
        if (Math.abs(diffX) > 10) {
            e.preventDefault();
        }
        
        // Apply transform with resistance at edges
        const resistance = 0.4;
        const transform = diffX * resistance;
        this.activeSwipeCard.style.transform = `translateX(${transform}px)`;
        
        // Show action indicator
        this.updateSwipeIndicator(diffX);
    }
    
    handleSwipeEnd(e) {
        if (!this.activeSwipeCard) return;
        
        const card = this.activeSwipeCard;
        const cardWidth = card.offsetWidth;
        const endX = e.changedTouches[0].clientX;
        const diffX = endX - this.swipeStartX;
        const elapsed = Date.now() - this.swipeStartTime;
        const velocity = Math.abs(diffX) / elapsed;
        
        // Restore transition
        card.style.transition = '';
        card.style.transform = '';
        
        // Check if swipe threshold met
        const thresholdMet = Math.abs(diffX) > cardWidth * this.options.swipeThreshold;
        const velocityMet = velocity > this.options.swipeVelocityThreshold;
        
        if (thresholdMet || velocityMet) {
            if (diffX < 0) {
                // Swipe left: Complete
                this.handleSwipeComplete(card);
            } else {
                // Swipe right: Snooze
                this.handleSwipeSnooze(card);
            }
        }
        
        this.hideSwipeIndicator();
        this.activeSwipeCard = null;
    }
    
    cancelSwipe() {
        if (this.activeSwipeCard) {
            this.activeSwipeCard.style.transition = '';
            this.activeSwipeCard.style.transform = '';
            this.hideSwipeIndicator();
            this.activeSwipeCard = null;
        }
    }
    
    updateSwipeIndicator(diffX) {
        const card = this.activeSwipeCard;
        if (!card) return;
        
        // Create or update indicator
        let indicator = card.querySelector('.swipe-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'swipe-indicator';
            indicator.innerHTML = `
                <span class="swipe-action-icon"></span>
                <span class="swipe-action-text"></span>
            `;
            card.appendChild(indicator);
        }
        
        const iconEl = indicator.querySelector('.swipe-action-icon');
        const textEl = indicator.querySelector('.swipe-action-text');
        
        if (diffX < -20) {
            indicator.className = 'swipe-indicator swipe-complete';
            iconEl.innerHTML = '✓';
            textEl.textContent = 'Complete';
        } else if (diffX > 20) {
            indicator.className = 'swipe-indicator swipe-snooze';
            iconEl.innerHTML = '⏰';
            textEl.textContent = 'Snooze';
        } else {
            indicator.className = 'swipe-indicator';
            iconEl.innerHTML = '';
            textEl.textContent = '';
        }
    }
    
    hideSwipeIndicator() {
        if (this.activeSwipeCard) {
            const indicator = this.activeSwipeCard.querySelector('.swipe-indicator');
            if (indicator) {
                indicator.remove();
            }
        }
    }
    
    /**
     * Handle swipe-to-complete
     */
    async handleSwipeComplete(card) {
        const taskId = card.dataset.taskId;
        if (!taskId) return;
        
        this.triggerHaptic('medium');
        
        // Trigger completion celebration
        this.celebrateCompletion(card);
        
        // Find and check the checkbox
        const checkbox = card.querySelector('.task-checkbox');
        if (checkbox && !checkbox.checked) {
            checkbox.checked = true;
            checkbox.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }
    
    /**
     * Handle swipe-to-snooze
     */
    handleSwipeSnooze(card) {
        const taskId = card.dataset.taskId;
        if (!taskId) return;
        
        this.triggerHaptic('light');
        
        // Dispatch snooze event for task handler to pick up
        document.dispatchEvent(new CustomEvent('task:snooze-requested', {
            detail: { taskId: parseInt(taskId), card }
        }));
        
        // Visual feedback
        card.classList.add('snoozed-flash');
        setTimeout(() => card.classList.remove('snoozed-flash'), 300);
    }
    
    /**
     * Trigger haptic feedback
     */
    triggerHaptic(intensity = 'light') {
        if (!this.options.hapticEnabled || !this.supportsHaptic) return;
        
        const patterns = {
            light: [10],
            medium: [20],
            heavy: [30],
            success: [10, 50, 10]
        };
        
        try {
            navigator.vibrate(patterns[intensity] || patterns.light);
        } catch (e) {
            // Silently fail if haptic not available
        }
    }
    
    /**
     * Setup observer to watch for task completions
     */
    setupCompletionObserver() {
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('task-checkbox') && e.target.checked) {
                const card = e.target.closest('.task-card');
                if (card) {
                    this.celebrateCompletion(card);
                }
            }
        });
    }
    
    /**
     * Completion celebration with particles
     */
    celebrateCompletion(card) {
        if (!this.options.celebrationEnabled) return;
        
        const checkbox = card.querySelector('.task-checkbox');
        if (!checkbox) return;
        
        // Haptic feedback
        this.triggerHaptic('success');
        
        // Create particle burst
        const rect = checkbox.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        // Limit particles on low-end devices
        const particleCount = this.isLowEndDevice ? 4 : 8;
        
        for (let i = 0; i < particleCount; i++) {
            this.createParticle(centerX, centerY, i, particleCount);
        }
        
        // Subtle screen flash
        this.screenFlash();
    }
    
    /**
     * Create a single celebration particle
     */
    createParticle(x, y, index, total) {
        const particle = document.createElement('div');
        particle.className = 'completion-particle';
        
        // Random angle distributed around the circle
        const baseAngle = (index / total) * 360;
        const angle = baseAngle + (Math.random() * 30 - 15);
        const radian = angle * (Math.PI / 180);
        
        // Random distance
        const distance = 30 + Math.random() * 40;
        
        // Random color from celebration palette
        const colors = ['#4ade80', '#22c55e', '#86efac', '#a5b4fc', '#c4b5fd'];
        const color = colors[Math.floor(Math.random() * colors.length)];
        
        particle.style.cssText = `
            position: fixed;
            left: ${x}px;
            top: ${y}px;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: ${color};
            pointer-events: none;
            z-index: 10000;
            will-change: transform, opacity;
        `;
        
        document.body.appendChild(particle);
        
        // Animate using Web Animations API for better performance
        const animation = particle.animate([
            { 
                transform: 'translate(-50%, -50%) scale(1)',
                opacity: 1 
            },
            { 
                transform: `translate(
                    calc(-50% + ${Math.cos(radian) * distance}px), 
                    calc(-50% + ${Math.sin(radian) * distance}px)
                ) scale(0)`,
                opacity: 0 
            }
        ], {
            duration: 400 + Math.random() * 200,
            easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
            fill: 'forwards'
        });
        
        animation.onfinish = () => particle.remove();
    }
    
    /**
     * Subtle screen flash on completion
     */
    screenFlash() {
        // Check for reduced motion preference
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return;
        }
        
        const flash = document.createElement('div');
        flash.className = 'completion-flash';
        flash.style.cssText = `
            position: fixed;
            inset: 0;
            background: rgba(74, 222, 128, 0.05);
            pointer-events: none;
            z-index: 9999;
        `;
        
        document.body.appendChild(flash);
        
        requestAnimationFrame(() => {
            flash.style.transition = 'opacity 200ms ease-out';
            flash.style.opacity = '0';
            
            setTimeout(() => flash.remove(), 200);
        });
    }
    
    /**
     * Add density toggle to toolbar
     */
    addDensityToggle() {
        const toolbar = document.querySelector('.search-sort-toolbar, .header-actions');
        if (!toolbar) return;
        
        // Check if toggle already exists
        if (toolbar.querySelector('.density-toggle')) return;
        
        const toggleWrapper = document.createElement('div');
        toggleWrapper.className = 'density-toggle';
        toggleWrapper.innerHTML = `
            <button class="density-btn" data-density="compact" title="Compact view">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="4" y1="6" x2="20" y2="6"></line>
                    <line x1="4" y1="12" x2="20" y2="12"></line>
                    <line x1="4" y1="18" x2="20" y2="18"></line>
                </svg>
            </button>
            <button class="density-btn active" data-density="comfortable" title="Comfortable view">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="3" y="3" width="7" height="7" rx="1"></rect>
                    <rect x="14" y="3" width="7" height="7" rx="1"></rect>
                    <rect x="3" y="14" width="7" height="7" rx="1"></rect>
                    <rect x="14" y="14" width="7" height="7" rx="1"></rect>
                </svg>
            </button>
            <button class="density-btn" data-density="spacious" title="Spacious view">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="3" y="4" width="18" height="6" rx="1"></rect>
                    <rect x="3" y="14" width="18" height="6" rx="1"></rect>
                </svg>
            </button>
        `;
        
        // Add click handlers
        toggleWrapper.addEventListener('click', (e) => {
            const btn = e.target.closest('.density-btn');
            if (!btn) return;
            
            const density = btn.dataset.density;
            this.setDensity(density);
            
            // Update active state
            toggleWrapper.querySelectorAll('.density-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
        
        toolbar.appendChild(toggleWrapper);
        
        // Load saved preference
        const savedDensity = localStorage.getItem('task-density') || 'comfortable';
        this.setDensity(savedDensity);
        toggleWrapper.querySelector(`[data-density="${savedDensity}"]`)?.classList.add('active');
    }
    
    /**
     * Set task list density
     */
    setDensity(density) {
        const taskList = document.querySelector('.task-list, .tasks-list-container, #task-list');
        if (!taskList) return;
        
        // Remove existing density classes
        taskList.classList.remove('density-compact', 'density-comfortable', 'density-spacious');
        
        // Add new density class
        taskList.classList.add(`density-${density}`);
        
        // Save preference
        localStorage.setItem('task-density', density);
        
        // Trigger haptic on mobile
        this.triggerHaptic('light');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.taskProgressiveDisclosure = new TaskProgressiveDisclosure();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TaskProgressiveDisclosure;
}
