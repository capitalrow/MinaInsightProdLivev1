/**
 * CROWN⁴.6 MVP+ Tasks Page Initialization
 * Wires all critical handlers so the Tasks page is interactive even if
 * individual modules load late. Designed to be idempotent and defensive.
 */
(function() {
    'use strict';

    console.log('[DEBUG] ========== task-page-init.js STARTING ==========');

    const INIT_FLAGS = window.__tasksPageInitFlags || (window.__tasksPageInitFlags = {
        actionsMenu: false,
        newTaskButtons: false,
        proposalsButton: false,
        searchSort: false,
        inlineEditing: false,
        proposalsUI: false
    });

    const logState = () => {
        console.log('[DEBUG] Task page init flags:', { ...INIT_FLAGS, masterReady: window.__tasksPageMasterInitialized });
    };

    const bindNewTaskButtons = () => {
        if (INIT_FLAGS.newTaskButtons || window.__taskNewButtonsReady) return;

        const buttons = [
            document.getElementById('new-task-btn'),
            document.getElementById('empty-state-create-btn')
        ].filter(Boolean);

        if (buttons.length === 0) return;

        const handler = (e) => {
            e.preventDefault();
            document.dispatchEvent(new CustomEvent('task:create-new'));

            if (window.taskModalManager?.openCreateModal) {
                window.taskModalManager.openCreateModal();
            } else if (window.toastManager) {
                window.toastManager.show('Opening task creator…', 'info', 1500);
            }
        };

        buttons.forEach((btn) => {
            if (btn.dataset.bound === 'new-task') return;
            btn.addEventListener('click', handler);
            btn.dataset.bound = 'new-task';
        });

        INIT_FLAGS.newTaskButtons = true;
        window.__taskNewButtonsReady = true;
        console.log('✅ New Task buttons wired');
    };

    const bindProposalButton = () => {
        if (INIT_FLAGS.proposalsButton || window.__taskProposalUIReady) return;
        const proposalsBtn = document.querySelector('.btn-generate-proposals');
        if (!proposalsBtn) return;

        if (!window.taskProposalUI && window.TaskProposalUI && window.optimisticUI) {
            window.taskProposalUI = new window.TaskProposalUI(window.optimisticUI);
            INIT_FLAGS.proposalsUI = true;
            window.__taskProposalUIReady = true;
            console.log('✅ TaskProposalUI instantiated from fallback path');
        }

        const handler = async (e) => {
            e.preventDefault();
            if (window.taskProposalUI?.startProposalStream) {
                await window.taskProposalUI.startProposalStream(proposalsBtn);
            } else {
                console.warn('[TasksInit] Proposal UI not ready; dispatching click for delegated listener');
                proposalsBtn.dispatchEvent(new Event('click', { bubbles: true }));
            }
        };

        if (proposalsBtn.dataset.bound !== 'ai-proposals') {
            proposalsBtn.addEventListener('click', handler);
            proposalsBtn.dataset.bound = 'ai-proposals';
        }

        INIT_FLAGS.proposalsButton = true;
        console.log('✅ AI Proposals button wired');
    };

    const ensureSearchSort = () => {
        if (INIT_FLAGS.searchSort || window.taskSearchSort || window.__taskSearchSortReady) return;
        if (typeof window.TaskSearchSort === 'undefined') return;

        try {
            window.taskSearchSort = new window.TaskSearchSort();
            INIT_FLAGS.searchSort = true;
            window.__taskSearchSortReady = true;
            console.log('✅ TaskSearchSort initialized (fallback)');
        } catch (error) {
            console.error('❌ Failed to initialize TaskSearchSort:', error);
        }
    };

    const ensureInlineEditing = () => {
        if (INIT_FLAGS.inlineEditing || window.taskInlineEditing || window.__taskInlineEditingReady) return;
        if (!window.optimisticUI || typeof window.TaskInlineEditing === 'undefined') return;

        try {
            window.taskInlineEditing = new window.TaskInlineEditing(window.optimisticUI);
            INIT_FLAGS.inlineEditing = true;
            window.__taskInlineEditingReady = true;
            console.log('✅ TaskInlineEditing initialized (fallback)');
        } catch (error) {
            console.error('❌ Failed to initialize TaskInlineEditing:', error);
        }
    };

    const ensureTaskActionsMenu = () => {
        if (INIT_FLAGS.actionsMenu || window.__taskActionsMenuReady) return;

        if (!window.TaskActionsMenu) {
            console.error('❌ TaskActionsMenu class not available!');
            return;
        }

        if (!window.taskStore) {
            console.warn('⚠️ taskStore not available yet, waiting for taskStoreReady event...');
            window.addEventListener('taskStoreReady', ensureTaskActionsMenu, { once: true });
            return;
        }

        const start = () => {
            try {
                window.taskActionsMenu = new window.TaskActionsMenu(window.optimisticUI);
                INIT_FLAGS.actionsMenu = true;
                window.__taskActionsMenuReady = true;
                console.log('✅ Task actions menu initialized successfully');

                if (window.tasksWS?.init) {
                    try {
                        window.tasksWS.init();
                        console.log('✅ Task WebSocket handlers initialized');
                    } catch (wsError) {
                        console.error('❌ Failed to initialize WebSocket handlers:', wsError);
                    }
                }
            } catch (error) {
                console.error('❌ Failed to initialize TaskActionsMenu:', error);
            }
        };

        if (window.optimisticUI) {
            start();
        } else {
            console.warn('⚠️ optimisticUI not available yet, retrying in 100ms...');
            setTimeout(start, 100);
        }
    };

    const ensureTranscriptNavigation = () => {
        if (window.taskTranscriptNavigation) return;
        const NavClass = window.TaskTranscriptNavigation || (typeof TaskTranscriptNavigation !== 'undefined' ? TaskTranscriptNavigation : null);
        if (!NavClass) return;

        try {
            window.taskTranscriptNavigation = new NavClass();
            console.log('✅ TaskTranscriptNavigation initialized (fallback)');
        } catch (error) {
            console.error('❌ Failed to initialize TaskTranscriptNavigation:', error);
        }
    };

    const initTaskPage = () => {
        ensureTaskActionsMenu();
        bindNewTaskButtons();
        bindProposalButton();
        ensureSearchSort();
        ensureInlineEditing();
        ensureTranscriptNavigation();
        logState();

        // If master init failed to mark readiness, retry a limited number of times
        if (!window.__tasksPageMasterInitialized) {
            let retries = 0;
            const retryInterval = setInterval(() => {
                retries += 1;
                ensureSearchSort();
                ensureInlineEditing();
                bindProposalButton();
                if (window.__tasksPageMasterInitialized || retries >= 5) {
                    clearInterval(retryInterval);
                    logState();
                }
            }, 150);
        }
    };

    if (document.readyState === 'loading') {
        console.log('[DEBUG] DOM still loading, waiting for DOMContentLoaded...');
        document.addEventListener('DOMContentLoaded', initTaskPage);
    } else {
        console.log('[DEBUG] DOM already loaded, initializing immediately');
        initTaskPage();
    }

    console.log('[DEBUG] ========== task-page-init.js LOADED ==========');
})();
