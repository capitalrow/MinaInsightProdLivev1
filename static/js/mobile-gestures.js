/**
 * Mobile Gestures Manager
 * Handles touch interactions: pull-to-refresh, swipe-to-archive, long-press selection
 */

(function() {
    'use strict';
    
    // Gesture configuration
    const GESTURE_CONFIG = {
        pullToRefresh: {
            threshold: 80,           // Pull distance to trigger refresh
            resistance: 2.5,         // Pull resistance factor
            maxPull: 120,           // Maximum pull distance
            snapBackDuration: 300   // Animation duration for snap back
        },
        swipe: {
            threshold: 80,           // Swipe distance to trigger action (matches archiveWidth)
            velocity: 0.3,           // Minimum swipe velocity
            archiveWidth: 80,        // Width of archive button revealed
            maxSwipe: 150            // Maximum swipe distance allowed
        },
        longPress: {
            duration: 500,           // Long press duration in ms
            moveThreshold: 10        // Max movement allowed during long press
        }
    };
    
    // State
    let pullRefreshActive = false;
    let pullStartY = 0;
    let pullCurrentY = 0;
    let pullIndicator = null;
    let selectionMode = false;
    let selectedCards = new Set();
    
    // Touch tracking
    let touchStartX = 0;
    let touchStartY = 0;
    let touchStartTime = 0;
    let longPressTimer = null;
    let currentSwipeCard = null;
    
    // Lifecycle tracking (for PJAX teardown/reinit)
    let isInitialized = false;
    let eventListeners = [];
    
    /**
     * Add tracked event listener (for PJAX lifecycle management)
     */
    function addTrackedListener(element, event, handler, options) {
        element.addEventListener(event, handler, options);
        eventListeners.push({ element, event, handler, options });
    }
    
    /**
     * Destroy mobile gestures (cleanup for PJAX navigation)
     */
    function destroy() {
        if (!isInitialized) {
            return; // Not initialized, nothing to destroy
        }
        
        console.log('📱 Destroying mobile gestures...');
        
        // Remove all tracked event listeners
        eventListeners.forEach(({ element, event, handler, options }) => {
            element.removeEventListener(event, handler, options);
        });
        eventListeners = [];
        
        // Remove pull indicator
        if (pullIndicator && pullIndicator.parentNode) {
            pullIndicator.parentNode.removeChild(pullIndicator);
            pullIndicator = null;
        }
        
        // Clear any active timers
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
        
        // Reset state
        pullRefreshActive = false;
        selectionMode = false;
        selectedCards.clear();
        currentSwipeCard = null;
        isInitialized = false;
        
        console.log('📱 Mobile gestures destroyed');
    }
    
    /**
     * Initialize mobile gestures
     */
    function init() {
        // Prevent double initialization
        if (isInitialized) {
            console.log('📱 Mobile gestures already initialized, skipping');
            return;
        }
        
        // Only initialize on dashboard, meetings, or tasks page
        const isValidPage = document.querySelector('.dashboard-container, .meetings-container, .tasks-container');
        if (!isValidPage) {
            return; // Not on a supported page, skip initialization
        }
        
        if (!isMobileDevice()) {
            console.log('📱 Desktop detected - mobile gestures disabled');
            return;
        }
        
        console.log('📱 Mobile gestures initialized');
        setupPullToRefresh();
        setupSwipeToArchive();
        setupLongPress();
        
        isInitialized = true;
    }
    
    /**
     * Check if device is mobile
     */
    function isMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               (window.innerWidth <= 768);
    }
    
    /**
     * Trigger haptic feedback
     */
    function haptic(type = 'light') {
        if (navigator.vibrate) {
            const patterns = {
                light: [10],
                medium: [20],
                heavy: [30],
                success: [10, 20, 10],
                error: [50, 50, 50]
            };
            navigator.vibrate(patterns[type] || patterns.light);
        }
    }
    
    /**
     * Setup pull-to-refresh gesture
     */
    function setupPullToRefresh() {
        const container = document.querySelector('.dashboard-container, .meetings-container, .tasks-container') || document.body;
        
        // Create pull indicator
        pullIndicator = document.createElement('div');
        pullIndicator.className = 'pull-refresh-indicator';
        pullIndicator.innerHTML = `
            <div class="pull-refresh-spinner"></div>
            <span class="pull-refresh-text">Pull to refresh</span>
        `;
        pullIndicator.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            background: linear-gradient(180deg, rgba(139, 92, 246, 0.1), transparent);
            transform: translateY(-60px);
            transition: transform 0.3s ease;
            z-index: 100;
            pointer-events: none;
        `;
        document.body.insertBefore(pullIndicator, document.body.firstChild);
        
        // Add spinner styles
        const spinnerStyle = document.createElement('style');
        spinnerStyle.textContent = `
            .pull-refresh-spinner {
                width: 24px;
                height: 24px;
                border: 3px solid rgba(139, 92, 246, 0.3);
                border-top-color: rgb(139, 92, 246);
                border-radius: 50%;
                transition: transform 0.3s ease;
            }
            
            .pull-refresh-spinner.spinning {
                animation: spin 0.8s linear infinite;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            .pull-refresh-text {
                color: rgb(139, 92, 246);
                font-size: 14px;
                font-weight: 500;
            }
        `;
        document.head.appendChild(spinnerStyle);
        
        // Touch event handlers
        container.addEventListener('touchstart', handlePullStart, { passive: true });
        container.addEventListener('touchmove', handlePullMove, { passive: false });
        container.addEventListener('touchend', handlePullEnd, { passive: true });
    }
    
    /**
     * Handle pull start
     */
    function handlePullStart(e) {
        // Only activate if scrolled to top
        if (window.scrollY === 0 && !pullRefreshActive) {
            pullStartY = e.touches[0].clientY;
            pullCurrentY = pullStartY;
        }
    }
    
    /**
     * Handle pull move
     */
    function handlePullMove(e) {
        if (pullStartY === 0 || !pullIndicator) return;
        
        pullCurrentY = e.touches[0].clientY;
        const pullDistance = pullCurrentY - pullStartY;
        
        // Only pull down, not up
        if (pullDistance > 0 && window.scrollY === 0) {
            e.preventDefault(); // Prevent default scroll
            
            // Apply resistance
            const resistedDistance = Math.min(
                pullDistance / GESTURE_CONFIG.pullToRefresh.resistance,
                GESTURE_CONFIG.pullToRefresh.maxPull
            );
            
            // Update indicator position
            pullIndicator.style.transform = `translateY(${resistedDistance - 60}px)`;
            
            // Rotate spinner based on pull distance
            const spinner = pullIndicator.querySelector('.pull-refresh-spinner');
            if (spinner) {
                spinner.style.transform = `rotate(${resistedDistance * 3}deg)`;
            }
            
            // Update text when threshold reached
            const text = pullIndicator.querySelector('.pull-refresh-text');
            if (text) {
                if (resistedDistance >= GESTURE_CONFIG.pullToRefresh.threshold) {
                    text.textContent = 'Release to refresh';
                    haptic('light');
                } else {
                    text.textContent = 'Pull to refresh';
                }
            }
        }
    }
    
    /**
     * Handle pull end
     */
    function handlePullEnd(e) {
        if (pullStartY === 0) return;
        
        const pullDistance = (pullCurrentY - pullStartY) / GESTURE_CONFIG.pullToRefresh.resistance;
        
        if (pullDistance >= GESTURE_CONFIG.pullToRefresh.threshold) {
            // Trigger refresh
            triggerRefresh();
        } else {
            // Snap back
            snapBack();
        }
        
        pullStartY = 0;
        pullCurrentY = 0;
    }
    
    /**
     * Trigger dashboard refresh
     */
    async function triggerRefresh() {
        if (!pullIndicator) return;
        
        pullRefreshActive = true;
        
        // Show loading state
        pullIndicator.style.transform = 'translateY(0)';
        const spinner = pullIndicator.querySelector('.pull-refresh-spinner');
        const text = pullIndicator.querySelector('.pull-refresh-text');
        if (spinner) {
            spinner.classList.add('spinning');
            spinner.style.transform = 'rotate(0)';
        }
        if (text) {
            text.textContent = 'Refreshing...';
        }
        
        haptic('medium');
        
        try {
            // Emit refresh event via WebSocket
            if (window.wsManager && window.wsManager.socket) {
                window.wsManager.socket.emit('dashboard_refresh_request', {
                    workspace_id: window.WORKSPACE_ID || 1,
                    timestamp: Date.now()
                });
            }
            
            // Wait for response or timeout
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            haptic('success');
        } catch (error) {
            console.error('❌ Refresh failed:', error);
            haptic('error');
        } finally {
            // Hide indicator
            setTimeout(() => {
                snapBack();
                spinner.classList.remove('spinning');
                pullRefreshActive = false;
            }, 500);
        }
    }
    
    /**
     * Snap indicator back to hidden position
     */
    function snapBack() {
        if (!pullIndicator) return;
        
        pullIndicator.style.transform = 'translateY(-60px)';
        const spinner = pullIndicator.querySelector('.pull-refresh-spinner');
        if (spinner) {
            spinner.style.transform = 'rotate(0)';
        }
    }
    
    /**
     * Setup swipe-to-archive gesture
     */
    function setupSwipeToArchive() {
        // Delegate event listeners to parent container
        const meetingsContainer = document.querySelector('.meetings-list, #active-meetings, #archive-meetings');
        if (!meetingsContainer) {
            console.log('📱 Meetings list not found - swipe gestures disabled');
            return;
        }
        
        meetingsContainer.addEventListener('touchstart', handleSwipeStart, { passive: true });
        meetingsContainer.addEventListener('touchmove', handleSwipeMove, { passive: false });
        meetingsContainer.addEventListener('touchend', handleSwipeEnd, { passive: true });
    }
    
    /**
     * Handle swipe start
     */
    function handleSwipeStart(e) {
        const card = e.target.closest('.meeting-card');
        if (!card || selectionMode) return;
        
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        touchStartTime = Date.now();
        currentSwipeCard = card;
        
        // Ensure card is positioned for swiping
        card.style.transition = 'none';
        card.style.position = 'relative';
        card.style.left = '0';
    }
    
    /**
     * Handle swipe move
     */
    function handleSwipeMove(e) {
        if (!currentSwipeCard) return;
        
        const currentX = e.touches[0].clientX;
        const currentY = e.touches[0].clientY;
        const deltaX = currentX - touchStartX;
        const deltaY = currentY - touchStartY;
        
        // Only swipe left, and only if horizontal movement is dominant
        if (Math.abs(deltaX) > Math.abs(deltaY) && deltaX < 0) {
            e.preventDefault();
            
            // Clamp swipe distance to maxSwipe (allows exceeding archiveWidth to reach threshold)
            const swipeDistance = Math.max(deltaX, -GESTURE_CONFIG.swipe.maxSwipe);
            currentSwipeCard.style.left = `${swipeDistance}px`;
            
            // Show archive button
            let archiveBtn = currentSwipeCard.querySelector('.archive-action');
            if (!archiveBtn) {
                archiveBtn = document.createElement('div');
                archiveBtn.className = 'archive-action';
                archiveBtn.innerHTML = '🗑️ Archive';
                archiveBtn.style.cssText = `
                    position: absolute;
                    right: 0;
                    top: 0;
                    bottom: 0;
                    width: ${GESTURE_CONFIG.swipe.archiveWidth}px;
                    background: linear-gradient(135deg, #ef4444, #dc2626);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: 600;
                    font-size: 14px;
                `;
                currentSwipeCard.appendChild(archiveBtn);
            }
            
            // Visual feedback when threshold is reached
            if (Math.abs(deltaX) >= GESTURE_CONFIG.swipe.threshold && !currentSwipeCard.dataset.thresholdReached) {
                currentSwipeCard.dataset.thresholdReached = 'true';
                archiveBtn.style.transform = 'scale(1.1)';
                haptic('medium');
            }
        }
    }
    
    /**
     * Handle swipe end
     */
    function handleSwipeEnd(e) {
        if (!currentSwipeCard) return;
        
        const currentX = e.changedTouches[0].clientX;
        const deltaX = currentX - touchStartX;
        const velocity = Math.abs(deltaX) / (Date.now() - touchStartTime);
        
        currentSwipeCard.style.transition = 'left 0.3s ease';
        
        // Check if swipe threshold reached
        if (Math.abs(deltaX) >= GESTURE_CONFIG.swipe.threshold || 
            velocity >= GESTURE_CONFIG.swipe.velocity) {
            // Archive action
            archiveMeeting(currentSwipeCard);
        } else {
            // Snap back
            currentSwipeCard.style.left = '0';
            delete currentSwipeCard.dataset.thresholdReached;
            setTimeout(() => {
                const archiveBtn = currentSwipeCard.querySelector('.archive-action');
                if (archiveBtn) {
                    archiveBtn.style.transform = 'scale(1)';
                    archiveBtn.remove();
                }
            }, 300);
        }
        
        currentSwipeCard = null;
    }
    
    /**
     * Archive meeting with animation
     */
    function archiveMeeting(card) {
        haptic('medium');
        
        // Slide out animation
        card.style.left = '-100%';
        card.style.opacity = '0';
        
        setTimeout(() => {
            const meetingId = card.dataset.meetingId;
            console.log('📦 Archiving meeting:', meetingId);
            
            // Emit archive event
            if (window.wsManager && window.wsManager.socket) {
                window.wsManager.socket.emit('meeting_archived', {
                    meeting_id: parseInt(meetingId),
                    workspace_id: window.WORKSPACE_ID || 1,
                    timestamp: Date.now()
                });
            }
            
            // Remove from DOM
            card.remove();
            haptic('success');
        }, 300);
    }
    
    /**
     * Setup long-press for selection mode
     */
    function setupLongPress() {
        const meetingsContainer = document.querySelector('.meetings-list, #active-meetings, #archive-meetings');
        if (!meetingsContainer) {
            console.log('📱 Meetings list not found - long-press gestures disabled');
            return;
        }
        
        meetingsContainer.addEventListener('touchstart', handleLongPressStart, { passive: true });
        meetingsContainer.addEventListener('touchmove', handleLongPressMove, { passive: true });
        meetingsContainer.addEventListener('touchend', handleLongPressEnd, { passive: true });
    }
    
    /**
     * Handle long press start
     */
    function handleLongPressStart(e) {
        const card = e.target.closest('.meeting-card');
        if (!card) return;
        
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        
        // Start long press timer
        longPressTimer = setTimeout(() => {
            activateSelectionMode(card);
        }, GESTURE_CONFIG.longPress.duration);
    }
    
    /**
     * Handle long press move
     */
    function handleLongPressMove(e) {
        if (!longPressTimer) return;
        
        const currentX = e.touches[0].clientX;
        const currentY = e.touches[0].clientY;
        const deltaX = Math.abs(currentX - touchStartX);
        const deltaY = Math.abs(currentY - touchStartY);
        
        // Cancel long press if moved too much
        if (deltaX > GESTURE_CONFIG.longPress.moveThreshold || 
            deltaY > GESTURE_CONFIG.longPress.moveThreshold) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    }
    
    /**
     * Handle long press end
     */
    function handleLongPressEnd(e) {
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
        
        // Handle card selection in selection mode
        if (selectionMode) {
            const card = e.target.closest('.meeting-card');
            if (card) {
                toggleCardSelection(card);
            }
        }
    }
    
    /**
     * Activate selection mode
     */
    function activateSelectionMode(initialCard) {
        selectionMode = true;
        haptic('heavy');
        
        console.log('✨ Selection mode activated');
        
        // Add selection mode UI
        const toolbar = createSelectionToolbar();
        document.body.appendChild(toolbar);
        
        // Add checkboxes to all cards
        const cards = document.querySelectorAll('.meeting-card');
        cards.forEach(card => {
            addCheckbox(card);
        });
        
        // Select initial card
        toggleCardSelection(initialCard);
    }
    
    /**
     * Create selection mode toolbar
     */
    function createSelectionToolbar() {
        const toolbar = document.createElement('div');
        toolbar.className = 'selection-toolbar';
        toolbar.style.cssText = `
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            height: 60px;
            background: linear-gradient(180deg, rgba(0, 0, 0, 0.9), #000);
            display: flex;
            align-items: center;
            justify-content: space-around;
            z-index: 1000;
            animation: slideUp 0.3s ease-out;
        `;
        
        toolbar.innerHTML = `
            <button class="toolbar-btn" onclick="window.mobileGestures.cancelSelection()">
                ✖️ Cancel
            </button>
            <span class="selected-count">0 selected</span>
            <button class="toolbar-btn primary" onclick="window.mobileGestures.archiveSelected()">
                🗑️ Archive
            </button>
        `;
        
        return toolbar;
    }
    
    /**
     * Add checkbox to card
     */
    function addCheckbox(card) {
        const checkbox = document.createElement('div');
        checkbox.className = 'selection-checkbox';
        checkbox.style.cssText = `
            position: absolute;
            left: 16px;
            top: 16px;
            width: 24px;
            height: 24px;
            border: 2px solid rgba(139, 92, 246, 0.5);
            border-radius: 6px;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        `;
        card.style.paddingLeft = '52px';
        card.insertBefore(checkbox, card.firstChild);
    }
    
    /**
     * Toggle card selection
     */
    function toggleCardSelection(card) {
        const meetingId = card.dataset.meetingId;
        const checkbox = card.querySelector('.selection-checkbox');
        
        if (selectedCards.has(meetingId)) {
            selectedCards.delete(meetingId);
            checkbox.innerHTML = '';
            checkbox.style.background = 'rgba(0, 0, 0, 0.5)';
            haptic('light');
        } else {
            selectedCards.add(meetingId);
            checkbox.innerHTML = '✓';
            checkbox.style.background = 'rgb(139, 92, 246)';
            checkbox.style.borderColor = 'rgb(139, 92, 246)';
            haptic('medium');
        }
        
        // Update toolbar count
        const countEl = document.querySelector('.selected-count');
        if (countEl) {
            countEl.textContent = `${selectedCards.size} selected`;
        }
    }
    
    /**
     * Cancel selection mode
     */
    function cancelSelection() {
        selectionMode = false;
        selectedCards.clear();
        
        // Remove toolbar
        const toolbar = document.querySelector('.selection-toolbar');
        if (toolbar) toolbar.remove();
        
        // Remove checkboxes
        const checkboxes = document.querySelectorAll('.selection-checkbox');
        checkboxes.forEach(cb => cb.remove());
        
        // Reset card padding
        const cards = document.querySelectorAll('.meeting-card');
        cards.forEach(card => card.style.paddingLeft = '');
        
        haptic('light');
    }
    
    /**
     * Archive selected meetings
     */
    function archiveSelected() {
        if (selectedCards.size === 0) return;
        
        haptic('heavy');
        
        console.log(`📦 Archiving ${selectedCards.size} meetings`);
        
        // Emit batch archive event
        if (window.wsManager && window.wsManager.socket) {
            window.wsManager.socket.emit('meetings_batch_archived', {
                meeting_ids: Array.from(selectedCards).map(id => parseInt(id)),
                workspace_id: window.WORKSPACE_ID || 1,
                timestamp: Date.now()
            });
        }
        
        // Remove cards with animation
        selectedCards.forEach(meetingId => {
            const card = document.querySelector(`[data-meeting-id="${meetingId}"]`);
            if (card) {
                card.style.transition = 'all 0.3s ease';
                card.style.transform = 'translateX(-100%)';
                card.style.opacity = '0';
                setTimeout(() => card.remove(), 300);
            }
        });
        
        // Cancel selection mode
        setTimeout(() => {
            cancelSelection();
            haptic('success');
        }, 400);
    }
    
    // Add keyframe animation for toolbar
    const toolbarStyle = document.createElement('style');
    toolbarStyle.textContent = `
        @keyframes slideUp {
            from {
                transform: translateY(100%);
            }
            to {
                transform: translateY(0);
            }
        }
        
        .toolbar-btn {
            padding: 8px 20px;
            border-radius: 8px;
            border: none;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            font-weight: 500;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .toolbar-btn:active {
            transform: scale(0.95);
        }
        
        .toolbar-btn.primary {
            background: linear-gradient(135deg, #8b5cf6, #7c3aed);
        }
        
        .selected-count {
            color: white;
            font-weight: 600;
            font-size: 16px;
        }
    `;
    document.head.appendChild(toolbarStyle);
    
    // Export public API
    window.mobileGestures = {
        init,
        destroy,
        cancelSelection,
        archiveSelected
    };
    
    // Auto-initialize on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // PJAX lifecycle hooks: reinitialize after navigation
    // Listen for PJAX navigation events from smooth-navigation.js
    window.addEventListener('pjax:beforeTransition', () => {
        console.log('📱 PJAX navigation detected, destroying gestures...');
        destroy();
    });
    
    window.addEventListener('pjax:complete', () => {
        console.log('📱 PJAX navigation complete, reinitializing gestures...');
        // Wait a tick for DOM to settle
        setTimeout(init, 100);
    });
    
    // Also listen for custom navigation events from smooth-navigation
    window.addEventListener('navigation:complete', () => {
        console.log('📱 Navigation complete, checking gesture initialization...');
        if (!isInitialized) {
            init();
        }
    });
    
})();
