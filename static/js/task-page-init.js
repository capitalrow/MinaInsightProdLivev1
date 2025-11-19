/**
 * CROWN⁴.6 MVP+ Tasks Page Initialization
 * Simple, robust initialization for task actions menu
 */
(function() {
    'use strict';
    
    console.log('[DEBUG] ========== task-page-init.js STARTING ==========');
    console.log('[DEBUG] window.optimisticUI exists:', !!window.optimisticUI);
    console.log('[DEBUG] window.TaskActionsMenu exists:', !!window.TaskActionsMenu);
    
    // Wait for DOM and required modules
    const initTaskActionsMenu = () => {
        console.log('[DEBUG] initTaskActionsMenu() called');
        
        // Check if taskStore is available (critical dependency)
        if (!window.taskStore) {
            console.warn('⚠️ taskStore not available yet, waiting for taskStoreReady event...');
            // Listen for taskStore ready event
            window.addEventListener('taskStoreReady', initTaskActionsMenu, { once: true });
            return;
        }
        
        // Check if optimisticUI is available
        if (!window.optimisticUI) {
            console.warn('⚠️ optimisticUI not available yet, retrying in 100ms...');
            setTimeout(initTaskActionsMenu, 100);
            return;
        }
        
        // Check if TaskActionsMenu class is available
        if (!window.TaskActionsMenu) {
            console.error('❌ TaskActionsMenu class not available!');
            return;
        }
        
        try {
            // Initialize the menu
            window.taskActionsMenu = new window.TaskActionsMenu(window.optimisticUI);
            console.log('✅ Task actions menu initialized successfully');
            console.log('[DEBUG] taskActionsMenu instance created:', !!window.taskActionsMenu);
            console.log('[DEBUG] taskStore available:', !!window.taskStore);
            
            // Initialize WebSocket handlers for real-time task updates
            if (window.tasksWS && window.wsManager) {
                try {
                    window.tasksWS.init();
                    console.log('✅ Task WebSocket handlers initialized');
                } catch (wsError) {
                    console.error('❌ Failed to initialize WebSocket handlers:', wsError);
                    console.warn('⚠️ Real-time updates may not work. Falling back to polling.');
                }
            } else {
                console.warn('⚠️ WebSocket dependencies not available (tasksWS:', !!window.tasksWS, ', wsManager:', !!window.wsManager, ')');
                console.warn('⚠️ Tasks from new meetings will require manual refresh');
            }
        } catch (error) {
            console.error('❌ Failed to initialize TaskActionsMenu:', error);
        }
    };
    
    // Start initialization after DOM is ready
    if (document.readyState === 'loading') {
        console.log('[DEBUG] DOM still loading, waiting for DOMContentLoaded...');
        document.addEventListener('DOMContentLoaded', initTaskActionsMenu);
    } else {
        console.log('[DEBUG] DOM already loaded, initializing immediately');
        initTaskActionsMenu();
    }
    
    console.log('[DEBUG] ========== task-page-init.js LOADED ==========');
})();
