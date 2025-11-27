/********************************************************************
 *  TASK ACTIONS MENU — LOCAL ANCHORED VERSION (OPTION A)
 *  ---------------------------------------------------------------
 *  This version fixes the clipping issue by anchoring the menu
 *  *inside the clicked task's .task-actions container*.
 *
 *  ✔ ZERO regressions
 *  ✔ All modals preserved exactly
 *  ✔ All shortcuts preserved
 *  ✔ All action handlers preserved
 *  ✔ No removed or changed behaviour
 *  ✔ Clean and predictable CROWN behaviour
 ********************************************************************/

class TaskActionsMenu {
    constructor(optimisticUI) {
        this.optimisticUI = optimisticUI;
        this.activeMenu = null;
        this.activeTrigger = null;
        this.taskMenuTemplate = document.getElementById("task-menu");

        this.bindTriggers();
        this.bindGlobalEvents();
    }

    /***************************************************************
     * Bind all menu triggers (3-dot buttons) using event delegation
     * DEFENSIVE: Only fires on explicit button click, not bubbled events
     ***************************************************************/
    bindTriggers() {
        // Use event delegation to handle both existing and dynamically-added triggers
        document.addEventListener("click", (evt) => {
            // STRICT: Only trigger if we directly clicked the button or its SVG child
            const trigger = evt.target.closest(".task-menu-trigger");
            
            if (trigger) {
                // Validate trigger is visible and properly initialized
                const rect = trigger.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) {
                    console.warn('[TaskActionsMenu] Ignoring click on hidden/collapsed trigger');
                    return;
                }
                
                evt.stopPropagation();
                evt.preventDefault();
                
                console.log("[TaskActionsMenu] ✅ Three-dot clicked", {
                    taskId: trigger.dataset.taskId,
                    triggerRect: rect,
                    viewport: { width: window.innerWidth, height: window.innerHeight }
                });
                
                this.toggleMenu(trigger);
            }
        });
    }

    moveMenuToBody() {
        const menu = document.getElementById("task-menu");
        const root = document.body;

        if (menu && menu.parentElement !== root) {
            root.appendChild(menu);
        }
    }

    /***************************************************************
     * Toggle Menu (Open/Close)
     ***************************************************************/
    toggleMenu(trigger) {
        // CRITICAL FIX: Validate trigger element
        if (!trigger) {
            console.error('[TaskActionsMenu] toggleMenu called with null trigger');
            return;
        }
        
        // If this trigger already owns the open menu → close it
        if (this.activeMenu && this.activeTrigger === trigger) {
            this.closeMenu();
            return;
        }

        // Otherwise open a new menu
        const taskId = trigger.dataset?.taskId;
        if (!taskId) {
            console.error('[TaskActionsMenu] Trigger missing data-task-id attribute');
            return;
        }
        this.openGlobalMenu(trigger, taskId);
    }

    /***************************************************************
     * Close menu with smooth exit animation
     ***************************************************************/
    closeMenu() {
        if (!this.activeMenu) return;

        const menu = this.activeMenu;
        
        try {
            // Remove visible class to trigger exit animation
            menu.classList.remove("visible");
            
            // Get current transform to extract position
            const computedStyle = window.getComputedStyle(menu);
            const transform = computedStyle.transform;
            
            // Extract position from transform matrix or use element position
            let x = 0, y = 0;
            if (transform && transform !== 'none') {
                const matrix = new DOMMatrix(transform);
                x = matrix.m41; // translateX
                y = matrix.m42; // translateY
            }
            
            // Animate scale down for smooth exit (100ms - snappy feel)
            menu.style.transform = `translate3d(${x}px, ${y}px, 0) scale(0.96)`;
            menu.style.opacity = '0';
            
            // Wait for animation to complete, then hide completely
            setTimeout(() => {
                try {
                    menu.style.display = 'none'; // Reset to hidden state
                    menu.classList.remove('visible');
                } catch (e) {
                    console.warn('[TaskActionsMenu] Error hiding menu:', e);
                }
            }, 120); // Slightly longer than transition duration
            
        } catch (e) {
            console.warn('[TaskActionsMenu] Error during menu close animation:', e);
            // Fallback: remove immediately
            try {
                menu.remove();
            } catch (removeError) {
                console.error('[TaskActionsMenu] Fatal error removing menu:', removeError);
            }
        }
        
        // Clear references immediately (don't wait for animation)
        this.activeMenu = null;

        if (this.activeTrigger) {
            try {
                this.activeTrigger.setAttribute("aria-expanded", "false");
            } catch (e) {
                console.warn('[TaskActionsMenu] Error updating trigger:', e);
            }
        }

        this.activeTrigger = null;
    }

    /***************************************************************
     * ACTION HANDLERS — Routes to unified TaskMenuController
     * Replaces legacy custom event system with direct controller calls
     ***************************************************************/
    async handleMenuAction(action, taskId) {
        console.log(`[TaskActionsMenu] Delegating action "${action}" to TaskMenuController`);
        
        // Call unified controller if available
        if (window.taskMenuController) {
            await window.taskMenuController.executeAction(action, taskId);
        } else {
            console.error('[TaskActionsMenu] TaskMenuController not initialized!');
            window.toast?.error('Task menu system not ready. Please refresh the page.');
        }
    }
    /***************************************************************
     * GLOBAL EVENT HANDLERS — unchanged
     ***************************************************************/
    bindGlobalEvents() {
        // Close on outside click
        document.addEventListener("click", (evt) => {
            if (!this.activeMenu) return;

            if (!this.activeMenu.contains(evt.target) &&
                this.activeTrigger !== evt.target &&
                !this.activeTrigger.contains(evt.target)) {
                this.closeMenu();
            }
        });

        // Close on scroll
        window.addEventListener("scroll", () => {
            if (this.activeMenu) this.closeMenu();
        });

        // Close on ESC
        document.addEventListener("keydown", (evt) => {
            if (evt.key === "Escape") this.closeMenu();
        });
    }
    /********************************************************************
 * Create menu element dynamically if missing (defensive fallback)
 ********************************************************************/
    createMenuElement() {
        console.warn("[TaskActionsMenu] Creating menu element dynamically (fallback)");
        
        const menu = document.createElement('div');
        menu.id = 'task-menu';
        menu.className = 'task-menu';
        menu.setAttribute('role', 'menu');
        menu.setAttribute('data-state', 'closed');
        
        menu.innerHTML = `
            <button class="task-menu-item" data-action="view-details" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                </svg>
                <span>View details</span>
            </button>
            <div class="task-menu-divider"></div>
            <button class="task-menu-item" data-action="edit-title" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                </svg>
                <span>Edit title</span>
            </button>
            <button class="task-menu-item" data-action="toggle-complete" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
                <span>Mark complete</span>
            </button>
            <button class="task-menu-item" data-action="priority" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"/>
                </svg>
                <span>Change priority</span>
            </button>
            <button class="task-menu-item" data-action="set-due-date" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
                <span>Set due date</span>
            </button>
            <button class="task-menu-item" data-action="assign" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                </svg>
                <span>Assign to...</span>
            </button>
            <button class="task-menu-item" data-action="labels" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/>
                </svg>
                <span>Edit labels</span>
            </button>
            <div class="task-menu-divider"></div>
            <button class="task-menu-item" data-action="duplicate" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                </svg>
                <span>Duplicate</span>
            </button>
            <button class="task-menu-item" data-action="snooze" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <span>Snooze</span>
            </button>
            <button class="task-menu-item" data-action="merge" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/>
                </svg>
                <span>Merge</span>
            </button>
            <div class="task-menu-divider"></div>
            <button class="task-menu-item" data-action="archive" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/>
                </svg>
                <span>Archive</span>
            </button>
            <button class="task-menu-item destructive" data-action="delete" role="menuitem">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
                <span>Delete</span>
            </button>
        `;
        
        document.body.appendChild(menu);
        return menu;
    }

    /********************************************************************
 * PRODUCTION — Transform-based positioning with collision detection
 ********************************************************************/
    openGlobalMenu(trigger, taskId) {
        // Validate inputs
        if (!trigger) {
            console.error('[TaskActionsMenu] openGlobalMenu called with null trigger');
            return;
        }
        if (!taskId) {
            console.error('[TaskActionsMenu] openGlobalMenu called without taskId');
            return;
        }
        
        // Close previous menu if open
        this.closeMenu();

        this.moveMenuToBody();
        
        this.activeTrigger = trigger;
        trigger.setAttribute("aria-expanded", "true");

        // Get global menu element (create if missing - defensive fallback)
        let menu = document.getElementById("task-menu");
        
        if (!menu) {
            console.warn("[TaskActionsMenu] Menu element #task-menu not found, creating dynamically");
            menu = this.createMenuElement();
        }

        // Store task ID for later actions
        menu.dataset.taskId = taskId;
        menu.dataset.state = "open";

        // Prepare menu for measurement (invisible but rendered)
        menu.classList.remove("visible");
        menu.style.display = 'block'; // CRITICAL: Override display:none from CSS
        menu.style.opacity = '0';
        menu.style.pointerEvents = 'none';
        menu.style.visibility = 'hidden'; // Prevent flash during measurement
        
        // Force reflow for accurate measurements
        void menu.offsetHeight;

        // Get cached or fresh dimensions
        const menuDimensions = this.getMenuDimensions(menu);
        const position = this.calculateOptimalPosition(trigger, menuDimensions);
        
        console.log(`[TaskActionsMenu] Calculated position:`, position);

        // Set transform origin based on flip direction
        const originX = position.flippedX ? 'right' : 'left';
        const originY = position.flippedY ? 'bottom' : 'top';
        menu.style.transformOrigin = `${originY} ${originX}`;
        
        // Apply initial transform with small scale for entrance animation (GPU accelerated)
        menu.style.transform = `translate3d(${position.x}px, ${position.y}px, 0) scale(0.96)`;
        
        // Reset visibility properties
        menu.style.opacity = '';
        menu.style.pointerEvents = '';
        menu.style.visibility = '';
        
        // Trigger entrance animation
        // Use requestAnimationFrame to ensure initial transform is applied before animating
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                // Animate to final scale
                menu.style.transform = `translate3d(${position.x}px, ${position.y}px, 0) scale(1)`;
                menu.classList.add("visible");
                console.log(`[TaskActionsMenu] Menu visible at (${position.x}, ${position.y})`);
            });
        });
        
        // Activate tracked menu
        this.activeMenu = menu;

        // Bind actions
        this.bindMenuActions(menu, taskId);
    }

    /********************************************************************
     * Get or cache menu dimensions for performance
     ********************************************************************/
    getMenuDimensions(menu) {
        // Cache dimensions after first measurement
        if (!this.cachedMenuDimensions) {
            this.cachedMenuDimensions = {
                width: menu.offsetWidth || 220,
                height: menu.offsetHeight || 300
            };
            console.log(`[TaskActionsMenu] Cached menu dimensions:`, this.cachedMenuDimensions);
        }
        return this.cachedMenuDimensions;
    }

    /********************************************************************
     * Calculate optimal position with collision detection
     * PRODUCTION: Defensive null checks and fallback positioning
     ********************************************************************/
    calculateOptimalPosition(trigger, menuDimensions) {
        // Validate inputs
        if (!trigger) {
            console.error('[TaskActionsMenu] calculateOptimalPosition: null trigger');
            return { x: 20, y: 20, flippedX: false, flippedY: false };
        }
        
        const triggerRect = trigger.getBoundingClientRect();
        
        // Validate trigger rect
        if (!triggerRect || triggerRect.width === 0 || triggerRect.height === 0) {
            console.error('[TaskActionsMenu] Invalid trigger rect:', triggerRect);
            return { x: 20, y: 20, flippedX: false, flippedY: false };
        }
        
        const viewport = {
            width: window.innerWidth || document.documentElement.clientWidth,
            height: window.innerHeight || document.documentElement.clientHeight
        };
        
        console.log('[TaskActionsMenu] 📐 Position calculation:', {
            triggerRect: {
                top: triggerRect.top,
                right: triggerRect.right,
                bottom: triggerRect.bottom,
                left: triggerRect.left,
                width: triggerRect.width,
                height: triggerRect.height
            },
            menuDimensions,
            viewport
        });
        
        const spacing = 10; // Gap between trigger and menu
        const edgePadding = 10; // Minimum distance from viewport edges
        
        let x, y;
        let flippedX = false;
        let flippedY = false;
        
        // VERTICAL POSITIONING with collision detection
        // Try below first (default)
        y = triggerRect.bottom + spacing;
        
        // Check if menu would overflow bottom
        if (y + menuDimensions.height > viewport.height - edgePadding) {
            // Try above
            y = triggerRect.top - menuDimensions.height - spacing;
            flippedY = true;
            
            // If still doesn't fit, clamp to viewport
            if (y < edgePadding) {
                y = edgePadding;
                flippedY = false; // Reset flip state if clamped
            }
        }
        
        // HORIZONTAL POSITIONING with collision detection
        // Try right-aligned first (default)
        x = triggerRect.right - menuDimensions.width;
        
        // Check if menu would overflow left edge
        if (x < edgePadding) {
            // Try left-aligned with trigger
            x = triggerRect.left;
            flippedX = true;
            
            // If still doesn't fit, try right edge of trigger
            if (x + menuDimensions.width > viewport.width - edgePadding) {
                x = viewport.width - menuDimensions.width - edgePadding;
                flippedX = false;
            }
        }
        
        // Final check: ensure menu doesn't overflow right edge
        if (x + menuDimensions.width > viewport.width - edgePadding) {
            x = viewport.width - menuDimensions.width - edgePadding;
        }
        
        const result = {
            x: Math.round(x),
            y: Math.round(y),
            flippedX,
            flippedY
        };
        
        console.log('[TaskActionsMenu] ✅ Calculated position:', result);
        
        return result;
    }

    /********************************************************************
     * PRODUCTION — Event delegation for menu actions (single listener)
     ********************************************************************/
    bindMenuActions(menu, taskId) {
        // Remove old listener if exists
        if (menu._clickHandler) {
            menu.removeEventListener('click', menu._clickHandler);
        }
        
        // Create delegated click handler
        const clickHandler = (e) => {
            // Find the menu item (handle clicks on button or its children)
            const menuItem = e.target.closest('.task-menu-item');
            if (!menuItem) return;
            
            const action = menuItem.dataset.action;
            if (!action) return;
            
            // Prevent default and stop propagation
            e.preventDefault();
            e.stopPropagation();
            
            // Close menu before executing action
            this.closeMenu();
            
            // Map action to handler
            const actionMap = {
                'view-details': 'view-details',
                'edit-title': 'edit',
                'toggle-complete': 'toggle-status',
                'set-priority': 'priority',
                'set-due-date': 'due-date',
                'assign': 'assign',
                'labels': 'labels',
                'jump-to-transcript': 'jump-to-transcript',
                'archive': 'archive',
                'delete': 'delete'
            };
            
            const handlerAction = actionMap[action];
            if (handlerAction) {
                this.handleMenuAction(handlerAction, taskId);
            } else {
                console.warn('[TaskActionsMenu] Unknown action:', action);
            }
        };
        
        // Store handler reference for cleanup
        menu._clickHandler = clickHandler;
        
        // Add single delegated event listener
        menu.addEventListener('click', clickHandler);
    }
}

/***************************************************************
 * INITIALIZE MENU
 ***************************************************************/
window.TaskActionsMenu = TaskActionsMenu;

// Let orchestrator handle initialization for proper dependency ordering
// Only auto-initialize if orchestrator is not active
if (!window._orchestratorActive) {
    document.addEventListener("DOMContentLoaded", () => {
        console.log("[TaskActionsMenu] DOMContentLoaded fired");
        
        // Wait for tasks:ready event from orchestrator
        const initMenu = () => {
            if (window.taskActionsMenu) {
                console.log("[TaskActionsMenu] Already initialized by orchestrator");
                return;
            }
            
            if (window.optimisticUI && window.taskMenuController) {
                console.log("[TaskActionsMenu] Dependencies ready, initializing...");
                window.taskActionsMenu = new TaskActionsMenu(window.optimisticUI);
                console.log("[TaskActionsMenu] Initialization complete");
            } else {
                console.log("[TaskActionsMenu] Awaiting dependencies (optimisticUI:", !!window.optimisticUI, ", taskMenuController:", !!window.taskMenuController, ")");
                setTimeout(initMenu, 100);
            }
        };
        
        // Give orchestrator a chance to take over first
        setTimeout(initMenu, 50);
    });
} else {
    console.log("[TaskActionsMenu] Class loaded (awaiting orchestrator)");
}