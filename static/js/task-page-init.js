/**
 * CROWN⁴.5 Tasks Page Initialization
 * Integrates all frontend modules for enterprise-grade task management
 */
(async function() {
    'use strict';
    
    console.log('[DEBUG] task-page-init.js starting...');
    
    // CROWN Telemetry is auto-initialized by crown-telemetry.js
    // Just verify it's available
    if (window.CROWNTelemetry) {
        window.crownTelemetry = window.CROWNTelemetry;
        console.log('📊 CROWN Telemetry ready');
    } else {
        console.warn('⚠️ CROWNTelemetry not available');
    }
    
    // CRITICAL: Register task handlers BEFORE connecting to ensure listeners attach
    if (window.tasksWS && window.wsManager) {
        window.tasksWS.init();
        console.log('✅ Task handlers registered (before connection)');
    } else {
        console.warn('⚠️ Task handlers or WebSocket Manager not available');
    }
    
    // Initialize WebSocket Manager (connects to tasks namespace)
    if (window.wsManager) {
        const workspaceId = window.WORKSPACE_ID || 1;
        await window.wsManager.init(workspaceId, ['tasks']);
        console.log('🔌 WebSocket Manager initialized for workspace', workspaceId);
    } else {
        console.warn('⚠️ WebSocket Manager not available');
    }
    
    // Wait for all modules to load (with 5-second timeout)
    const waitForModules = () => {
        return new Promise((resolve) => {
            const startTime = Date.now();
            const timeout = 5000; // 5 seconds max wait
            
            const check = () => {
                // CROWN⁴.5: Core required modules (must load)
                const coreModulesLoaded = window.taskCache && window.taskBootstrap && window.optimisticUI && 
                    window.offlineQueue && window.multiTabSync && window.idleSyncService && 
                    window.predictiveEngine && window.tasksWS && window.taskVirtualList && 
                    window.taskShortcuts && window.TaskInlineEditing && window.TaskActionsMenu;
                
                // CROWN⁴.5: Optional modules (nice-to-have, but not blocking)
                const optionalModulesLoaded = window.TaskBulkOperations && window.TaskDragDrop;
                
                if (coreModulesLoaded) {
                    if (!optionalModulesLoaded) {
                        console.warn('⚠️ Some optional modules not loaded (bulk operations, drag-drop)');
                    }
                    resolve(true);
                } else if (Date.now() - startTime > timeout) {
                    console.warn('⚠️ Module loading timeout - proceeding with available modules');
                    console.warn('Missing core modules:', {
                        taskCache: !!window.taskCache,
                        taskBootstrap: !!window.taskBootstrap,
                        optimisticUI: !!window.optimisticUI,
                        offlineQueue: !!window.offlineQueue,
                        multiTabSync: !!window.multiTabSync,
                        idleSyncService: !!window.idleSyncService,
                        predictiveEngine: !!window.predictiveEngine,
                        tasksWS: !!window.tasksWS,
                        taskVirtualList: !!window.taskVirtualList,
                        taskShortcuts: !!window.taskShortcuts,
                        TaskInlineEditing: !!window.TaskInlineEditing,
                        TaskActionsMenu: !!window.TaskActionsMenu
                    });
                    console.info('Optional modules:', {
                        TaskBulkOperations: !!window.TaskBulkOperations,
                        TaskDragDrop: !!window.TaskDragDrop
                    });
                    resolve(false);
                } else {
                    setTimeout(check, 100);
                }
            };
            
            check();
        });
    };
    
    console.log('🚀 Initializing CROWN⁴.5 Tasks Page (Phase 2)...');
    
    // Now wait for advanced modules (with timeout)
    const modulesLoaded = await waitForModules();
    
    if (modulesLoaded) {
        console.log('✅ All CROWN⁴.5 modules loaded');
    } else {
        console.warn('⚠️ Some modules failed to load - basic features still work');
    }
    
    // Initialize PredictiveEngine if available
    if (window.predictiveEngine) {
        await window.predictiveEngine.init();
        console.log('🤖 PredictiveEngine initialized');
    } else {
        console.warn('⚠️ PredictiveEngine not available');
    }
    
    // Initialize task editing modules if available
    if (window.TaskInlineEditing && window.optimisticUI) {
        window.taskInlineEditing = new window.TaskInlineEditing(window.optimisticUI);
        console.log('✏️ Inline editing initialized');
    } else {
        console.warn('⚠️ Inline editing not available');
    }
    
    if (window.TaskActionsMenu && window.optimisticUI) {
        window.taskActionsMenu = new window.TaskActionsMenu(window.optimisticUI);
        console.log('🎯 Task actions menu initialized');
    } else {
        console.warn('⚠️ Task actions menu not available');
    }
    
    if (window.TaskBulkOperations && window.optimisticUI) {
        window.taskBulkOperations = new window.TaskBulkOperations(window.optimisticUI);
        console.log('☑️ Bulk operations initialized');
    } else {
        console.warn('⚠️ Bulk operations not available');
    }
    
    if (window.TaskDragDrop && window.optimisticUI) {
        window.taskDragDrop = new window.TaskDragDrop(window.optimisticUI);
        console.log('🔄 Drag-drop reordering initialized');
    } else {
        console.warn('⚠️ Drag-drop reordering not available');
    }
    
    if (window.TaskProposalUI && window.optimisticUI) {
        window.taskProposalUI = new window.TaskProposalUI(window.optimisticUI);
        console.log('✨ AI proposal UI initialized');
    } else {
        console.warn('⚠️ AI proposal UI not available');
    }
    
    // Initialize cache-first bootstrap
    if (window.taskBootstrap) {
        try {
            const startTime = performance.now();
            await window.taskBootstrap.bootstrap();
            const bootstrapTime = performance.now() - startTime;
            console.log(`⚡ Bootstrap completed in ${bootstrapTime.toFixed(2)}ms`);
            
            // Log performance metrics
            if (bootstrapTime < 200) {
                console.log('🎯 CROWN⁴.5 Target Met: <200ms first paint');
            } else {
                console.warn(`⚠️ Bootstrap slower than target: ${bootstrapTime.toFixed(2)}ms > 200ms`);
            }
        } catch (error) {
            console.error('❌ Bootstrap failed:', error);
        }
    } else {
        console.warn('⚠️ TaskBootstrap not available - page may have limited functionality');
    }
    
    console.log('✅ Task page initialization complete');
})();
