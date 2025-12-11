/**
 * CROWN⁴.6 Tasks Core JavaScript
 * Handles task interactions, optimistic UI, and API integration
 */

(function() {
    'use strict';

    const API_BASE = '/api/tasks';
    let currentFilter = window.TASKS_CURRENT_FILTER || 'active';
    let tasksData = [];
    let undoQueue = [];
    let contextMenuTaskId = null;
    let currentGroupBy = localStorage.getItem('tasks_group_by') || 'none';
    let collapsedGroups = JSON.parse(localStorage.getItem('tasks_collapsed_groups') || '{}');

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    function init() {
        loadTasksData();
        loadMeetingHeatmap();
        bindEventListeners();
        initializeKeyboardShortcuts();
        initGroupingToggle();
        initContextBubble();
        
        // Initialize quick action modals
        initAssignModal();
        initDueDateModal();
        initPriorityModal();
        initLabelsModal();
    }

    function loadTasksData() {
        const dataElement = document.getElementById('tasks-data');
        if (dataElement) {
            try {
                tasksData = JSON.parse(dataElement.textContent);
            } catch (e) {
                console.error('[Tasks] Failed to parse tasks data:', e);
                tasksData = [];
            }
        }
    }

    async function loadMeetingHeatmap() {
        const heatmapContainer = document.getElementById('heatmap-items');
        if (!heatmapContainer) return;

        try {
            const response = await fetch(`${API_BASE}/meeting-heatmap`);
            const data = await response.json();
            
            if (data.success && data.meetings && data.meetings.length > 0) {
                heatmapContainer.innerHTML = data.meetings.slice(0, 5).map((meeting, index) => {
                    const isRecent = meeting.days_ago <= 1;
                    return `<a href="/dashboard/meetings/${meeting.meeting_id}" 
                               class="heatmap-item ${isRecent ? 'recent' : ''}"
                               title="${meeting.active_tasks} active tasks">
                        ${escapeHtml(meeting.meeting_title)} (${meeting.active_tasks})
                    </a>`;
                }).join('');
            } else {
                document.getElementById('meeting-heatmap').style.display = 'none';
            }
        } catch (e) {
            console.error('[Tasks] Failed to load heatmap:', e);
            document.getElementById('meeting-heatmap').style.display = 'none';
        }
    }

    function bindEventListeners() {
        // Checkbox click (complete/uncomplete task)
        document.querySelectorAll('.task-checkbox').forEach(checkbox => {
            checkbox.addEventListener('click', handleCheckboxClick);
        });

        // Action buttons
        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', handleActionClick);
        });

        // Mobile long-press for transcript preview
        initTranscriptLongPress();

        // Inline title editing
        initInlineEditing();

        // New task button
        const newTaskBtn = document.getElementById('new-task-btn');
        if (newTaskBtn) {
            newTaskBtn.addEventListener('click', openNewTaskModal);
        }

        // New task modal
        const newTaskForm = document.getElementById('new-task-form');
        if (newTaskForm) {
            newTaskForm.addEventListener('submit', handleNewTaskSubmit);
        }

        const modalClose = document.getElementById('new-task-modal-close');
        if (modalClose) {
            modalClose.addEventListener('click', closeNewTaskModal);
        }

        const modalCancel = document.getElementById('new-task-cancel');
        if (modalCancel) {
            modalCancel.addEventListener('click', closeNewTaskModal);
        }

        // Modal overlay click to close
        const modalOverlay = document.getElementById('new-task-modal');
        if (modalOverlay) {
            modalOverlay.addEventListener('click', (e) => {
                if (e.target === modalOverlay) closeNewTaskModal();
            });
        }

        // Context menu
        document.querySelectorAll('.context-menu-item').forEach(item => {
            item.addEventListener('click', handleContextMenuAction);
        });

        // Close context menu on outside click
        document.addEventListener('click', (e) => {
            const menu = document.getElementById('task-context-menu');
            if (menu && !menu.contains(e.target) && !e.target.closest('[data-action="menu"]')) {
                menu.style.display = 'none';
            }
        });

        // Undo button
        const undoBtn = document.getElementById('undo-btn');
        if (undoBtn) {
            undoBtn.addEventListener('click', handleUndo);
        }

        // Search input
        const searchInput = document.getElementById('task-search');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => filterTasks(e.target.value), 300);
            });
        }

        // Drag and drop
        document.querySelectorAll('.task-card[draggable="true"]').forEach(card => {
            card.addEventListener('dragstart', handleDragStart);
            card.addEventListener('dragend', handleDragEnd);
            card.addEventListener('dragover', handleDragOver);
            card.addEventListener('drop', handleDrop);
            card.addEventListener('dragleave', handleDragLeave);
        });
    }

    function initializeKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                if (e.key === 'Escape') {
                    e.target.blur();
                    closeNewTaskModal();
                }
                return;
            }

            switch(e.key.toLowerCase()) {
                case 'n':
                    e.preventDefault();
                    openNewTaskModal();
                    break;
                case '/':
                case 's':
                    e.preventDefault();
                    document.getElementById('task-search')?.focus();
                    break;
                case '?':
                    showKeyboardShortcuts();
                    break;
                case 'escape':
                    closeNewTaskModal();
                    document.getElementById('task-context-menu').style.display = 'none';
                    break;
            }
        });
    }

    async function handleCheckboxClick(e) {
        e.stopPropagation();
        const taskId = parseInt(e.currentTarget.dataset.taskId);
        const card = e.currentTarget.closest('.task-card');
        const isCompleted = e.currentTarget.classList.contains('completed');

        // Optimistic UI update
        e.currentTarget.classList.toggle('completed');
        card.classList.toggle('completed');
        
        if (!isCompleted) {
            e.currentTarget.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12"><polyline points="20 6 9 17 4 12"/></svg>';
        } else {
            e.currentTarget.innerHTML = '';
        }

        const newStatus = isCompleted ? 'todo' : 'completed';
        
        try {
            const response = await fetch(`${API_BASE}/${taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify({ status: newStatus })
            });

            if (response.ok) {
                // Add to undo queue
                undoQueue.push({
                    taskId,
                    previousStatus: isCompleted ? 'completed' : 'todo',
                    timestamp: Date.now()
                });

                // Show undo toast
                showUndoToast(isCompleted ? 'Task reopened' : 'Task completed');
            } else {
                // Revert on failure
                e.currentTarget.classList.toggle('completed');
                card.classList.toggle('completed');
                console.error('[Tasks] Failed to update task status');
            }
        } catch (err) {
            // Revert on error
            e.currentTarget.classList.toggle('completed');
            card.classList.toggle('completed');
            console.error('[Tasks] Error updating task:', err);
        }
    }

    function handleActionClick(e) {
        e.stopPropagation();
        const action = e.currentTarget.dataset.action;
        const taskId = parseInt(e.currentTarget.dataset.taskId);

        switch(action) {
            case 'menu':
                showContextMenu(e, taskId);
                break;
            case 'transcript':
                navigateToTranscript(taskId);
                break;
            case 'snooze':
                snoozeTask(taskId);
                break;
        }
    }

    function showContextMenu(e, taskId) {
        const menu = document.getElementById('task-context-menu');
        if (!menu) return;

        contextMenuTaskId = taskId;
        
        // Make menu visible first to calculate its dimensions
        menu.style.visibility = 'hidden';
        menu.style.display = 'block';
        
        const menuRect = menu.getBoundingClientRect();
        const rect = e.currentTarget.getBoundingClientRect();
        const padding = 12;
        
        // Calculate initial position (try to position below and left-aligned)
        let left = rect.left;
        let top = rect.bottom + 4;
        
        // Ensure menu fits horizontally - prefer left-aligned but shift left if needed
        const maxLeft = window.innerWidth - menuRect.width - padding;
        if (left > maxLeft) {
            left = Math.max(padding, maxLeft);
        }
        
        // Ensure menu fits vertically - flip above if needed
        if (top + menuRect.height > window.innerHeight - padding) {
            top = rect.top - menuRect.height - 4;
            // If still off screen, position at top with some padding
            if (top < padding) {
                top = padding;
            }
        }
        
        menu.style.left = `${left}px`;
        menu.style.top = `${top}px`;
        menu.style.visibility = 'visible';
    }

    async function handleContextMenuAction(e) {
        const action = e.currentTarget.dataset.action;
        const menu = document.getElementById('task-context-menu');
        menu.style.display = 'none';

        if (!contextMenuTaskId) return;

        switch(action) {
            case 'edit':
                openEditModal(contextMenuTaskId);
                break;
            case 'assign':
                openAssignModal(contextMenuTaskId);
                break;
            case 'set-due':
                openDueDateModal(contextMenuTaskId);
                break;
            case 'priority':
                openPriorityModal(contextMenuTaskId);
                break;
            case 'labels':
                openLabelsModal(contextMenuTaskId);
                break;
            case 'delete':
                await deleteTask(contextMenuTaskId);
                break;
            case 'archive':
                await archiveTask(contextMenuTaskId);
                break;
            case 'duplicate':
                await duplicateTask(contextMenuTaskId);
                break;
        }
    }

    async function deleteTask(taskId) {
        if (!confirm('Are you sure you want to delete this task?')) return;

        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (card) card.style.opacity = '0.5';

        try {
            const response = await fetch(`${API_BASE}/${taskId}`, {
                method: 'DELETE',
                headers: { 'X-CSRF-Token': getCSRFToken() }
            });

            if (response.ok) {
                if (card) {
                    card.style.transition = 'all 0.3s ease';
                    card.style.transform = 'translateX(-100%)';
                    card.style.opacity = '0';
                    setTimeout(() => card.remove(), 300);
                }
                showUndoToast('Task deleted');
            } else {
                if (card) card.style.opacity = '1';
                console.error('[Tasks] Failed to delete task');
            }
        } catch (err) {
            if (card) card.style.opacity = '1';
            console.error('[Tasks] Error deleting task:', err);
        }
    }

    function openNewTaskModal() {
        const modal = document.getElementById('new-task-modal');
        if (modal) {
            modal.style.display = 'flex';
            document.getElementById('new-task-title')?.focus();
        }
    }

    function closeNewTaskModal() {
        const modal = document.getElementById('new-task-modal');
        if (modal) {
            modal.style.display = 'none';
            document.getElementById('new-task-form')?.reset();
        }
    }

    async function handleNewTaskSubmit(e) {
        e.preventDefault();

        const title = document.getElementById('new-task-title').value.trim();
        const description = document.getElementById('new-task-description').value.trim();
        const dueDate = document.getElementById('new-task-due-date').value;
        const priority = document.getElementById('new-task-priority').value;

        if (!title) return;

        const submitBtn = e.target.querySelector('[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';

        try {
            const response = await fetch(API_BASE + '/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify({
                    title,
                    description: description || null,
                    due_date: dueDate || null,
                    priority,
                    source: 'manual'
                })
            });

            if (response.ok) {
                closeNewTaskModal();
                // Reload page to show new task (for now - will optimize with optimistic UI later)
                window.location.reload();
            } else {
                const data = await response.json();
                alert(data.message || 'Failed to create task');
            }
        } catch (err) {
            console.error('[Tasks] Error creating task:', err);
            alert('Failed to create task. Please try again.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Task';
        }
    }

    function filterTasks(query) {
        const normalizedQuery = query.toLowerCase().trim();
        const cards = document.querySelectorAll('.task-card');

        cards.forEach(card => {
            const title = card.querySelector('.task-title')?.textContent.toLowerCase() || '';
            const meeting = card.querySelector('.provenance-meeting')?.textContent.toLowerCase() || '';
            
            if (!normalizedQuery || title.includes(normalizedQuery) || meeting.includes(normalizedQuery)) {
                card.classList.add('is-visible');
            } else {
                card.classList.remove('is-visible');
            }
        });
    }

    // Drag and Drop
    let draggedCard = null;

    function handleDragStart(e) {
        draggedCard = e.currentTarget;
        e.currentTarget.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
    }

    function handleDragEnd(e) {
        e.currentTarget.classList.remove('dragging');
        document.querySelectorAll('.task-card').forEach(card => {
            card.classList.remove('drag-over');
        });
        draggedCard = null;
    }

    function handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        if (e.currentTarget !== draggedCard) {
            e.currentTarget.classList.add('drag-over');
        }
    }

    function handleDragLeave(e) {
        e.currentTarget.classList.remove('drag-over');
    }

    async function handleDrop(e) {
        e.preventDefault();
        e.currentTarget.classList.remove('drag-over');

        if (!draggedCard || e.currentTarget === draggedCard) return;

        const taskList = document.getElementById('task-list');
        const targetCard = e.currentTarget;
        const targetRect = targetCard.getBoundingClientRect();
        const dropY = e.clientY;

        // Insert before or after based on drop position
        if (dropY < targetRect.top + targetRect.height / 2) {
            taskList.insertBefore(draggedCard, targetCard);
        } else {
            taskList.insertBefore(draggedCard, targetCard.nextSibling);
        }

        // Update positions on server
        await updateTaskPositions();
    }

    async function updateTaskPositions() {
        const cards = document.querySelectorAll('.task-card');
        const positions = [];

        cards.forEach((card, index) => {
            const taskId = parseInt(card.dataset.taskId);
            positions.push({ task_id: taskId, position: index });
        });

        try {
            await fetch(`${API_BASE}/reorder`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify({ positions })
            });
        } catch (err) {
            console.error('[Tasks] Failed to update positions:', err);
        }
    }

    // Undo functionality
    function showUndoToast(message) {
        const toast = document.getElementById('undo-toast');
        const text = document.getElementById('undo-text');
        if (!toast || !text) return;

        text.textContent = message;
        toast.style.display = 'flex';

        // Auto-hide after 5 seconds
        setTimeout(() => {
            toast.style.display = 'none';
        }, 5000);
    }

    async function handleUndo() {
        const lastAction = undoQueue.pop();
        if (!lastAction) return;

        try {
            await fetch(`${API_BASE}/${lastAction.taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify({ status: lastAction.previousStatus })
            });

            // Reload to reflect changes
            window.location.reload();
        } catch (err) {
            console.error('[Tasks] Undo failed:', err);
        }

        document.getElementById('undo-toast').style.display = 'none';
    }

    async function snoozeTask(taskId) {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(9, 0, 0, 0);

        try {
            await fetch(`${API_BASE}/${taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify({ snoozed_until: tomorrow.toISOString() })
            });
            showUndoToast('Task snoozed until tomorrow');
        } catch (err) {
            console.error('[Tasks] Snooze failed:', err);
        }
    }

    function navigateToTranscript(taskId) {
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        const meetingLink = card?.querySelector('.provenance-meeting');
        if (meetingLink) {
            window.location.href = meetingLink.href;
        }
    }

    function showKeyboardShortcuts() {
        alert('Keyboard Shortcuts:\n\nN - New task\n/ or S - Search\n? - Show shortcuts\nEsc - Close modal');
    }

    // Transcript Long-Press for Mobile
    let longPressTimer = null;
    let longPressActiveCard = null;

    function initTranscriptLongPress() {
        const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        if (!isTouchDevice) return;

        document.querySelectorAll('.task-card').forEach(card => {
            const preview = card.querySelector('.transcript-preview');
            if (!preview) return;

            card.addEventListener('touchstart', (e) => {
                if (e.target.closest('.task-checkbox, .action-btn, .provenance-meeting')) return;
                
                longPressTimer = setTimeout(() => {
                    showTranscriptPreview(card, preview);
                    longPressActiveCard = card;
                    navigator.vibrate?.(50);
                }, 500);
            }, { passive: true });

            card.addEventListener('touchend', () => {
                clearTimeout(longPressTimer);
            });

            card.addEventListener('touchmove', () => {
                clearTimeout(longPressTimer);
            }, { passive: true });

            card.addEventListener('touchcancel', () => {
                clearTimeout(longPressTimer);
            });
        });

        document.addEventListener('touchstart', (e) => {
            if (longPressActiveCard && !e.target.closest('.transcript-preview')) {
                hideTranscriptPreview(longPressActiveCard);
                longPressActiveCard = null;
            }
        }, { passive: true });
    }

    function showTranscriptPreview(card, preview) {
        card.classList.add('transcript-active');
        preview.classList.add('visible');
    }

    function hideTranscriptPreview(card) {
        card.classList.remove('transcript-active');
        const preview = card.querySelector('.transcript-preview');
        if (preview) preview.classList.remove('visible');
    }

    // Transcript Context Bubble (CROWN⁴.6 Section 7)
    let contextBubble = null;
    let contextBubbleTimeout = null;

    function initContextBubble() {
        // Create the context bubble element
        if (!contextBubble) {
            contextBubble = document.createElement('div');
            contextBubble.className = 'transcript-context-bubble';
            contextBubble.id = 'transcript-context-bubble';
            document.body.appendChild(contextBubble);
        }

        // Bind hover/click events to context triggers (timestamp buttons)
        document.querySelectorAll('.context-trigger').forEach(trigger => {
            // Hover for desktop
            trigger.addEventListener('mouseenter', (e) => showContextBubble(e.target));
            trigger.addEventListener('mouseleave', () => scheduleHideBubble());
            
            // Click for mobile
            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleContextBubble(e.target);
            });
        });

        // Also bind to spoken-quote elements for tasks without transcript_span
        document.querySelectorAll('.spoken-quote').forEach(quote => {
            // Hover for desktop
            quote.addEventListener('mouseenter', (e) => showContextBubble(e.currentTarget, true));
            quote.addEventListener('mouseleave', () => scheduleHideBubble());
            
            // Long-press for mobile
            let longPressTimer;
            quote.addEventListener('touchstart', (e) => {
                longPressTimer = setTimeout(() => {
                    showContextBubble(e.currentTarget, true);
                    navigator.vibrate?.(30);
                }, 400);
            }, { passive: true });
            quote.addEventListener('touchend', () => clearTimeout(longPressTimer));
            quote.addEventListener('touchmove', () => clearTimeout(longPressTimer), { passive: true });
        });

        // Keep bubble visible when hovering over it
        contextBubble.addEventListener('mouseenter', () => clearTimeout(contextBubbleTimeout));
        contextBubble.addEventListener('mouseleave', () => hideBubble());

        // Close bubble on outside click
        document.addEventListener('click', (e) => {
            if (contextBubble.classList.contains('visible') && 
                !contextBubble.contains(e.target) && 
                !e.target.closest('.context-trigger') &&
                !e.target.closest('.spoken-quote')) {
                hideBubble();
            }
        });
    }

    function showContextBubble(trigger, isFromQuote = false) {
        clearTimeout(contextBubbleTimeout);
        
        const card = trigger.closest('.task-card');
        const provenance = card?.querySelector('.task-provenance');
        if (!card || !provenance) return;

        // Get transcript data from provenance data attributes
        const taskId = card.dataset.taskId;
        const sessionId = provenance.dataset.sessionId;
        const startMs = parseInt(provenance.dataset.transcriptStart) || 0;
        const endMs = parseInt(provenance.dataset.transcriptEnd) || startMs + 10000;
        const transcriptText = provenance.dataset.transcriptText;
        const aiIntent = provenance.dataset.aiIntent || '';
        const meetingTitle = provenance.dataset.meetingTitle || '';
        
        // Get speaker info from data attribute or element
        let speaker = provenance.dataset.speaker || '';
        if (!speaker) {
            const speakerEl = provenance.querySelector('.provenance-speaker');
            speaker = speakerEl?.dataset.speaker || '';
        }
        const speakerDisplay = speaker || 'From meeting';
        const speakerInitials = speaker ? speaker.slice(0, 2).toUpperCase() : 'M';

        // Get meeting link
        const meetingLink = provenance.querySelector('.jump-to-transcript');
        const meetingUrl = meetingLink?.href || '#';
        const meetingLinkTitle = meetingTitle || meetingLink?.textContent?.trim() || 'Meeting';

        // Format timestamp (only show if we have one)
        const hasTimestamp = startMs > 0;
        const mins = Math.floor(startMs / 60000);
        const secs = Math.floor((startMs / 1000) % 60);
        const timestamp = hasTimestamp ? `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}` : '';

        // Build bubble content
        const displayText = transcriptText || 'View the full transcript for context around this task.';
        
        // Build AI intent section if available
        const intentHtml = aiIntent && aiIntent !== displayText ? `
            <div class="context-bubble-intent">
                <svg viewBox="0 0 24 24" width="12" height="12"><path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5 0 4 4 0 0 1-5 0 4 4 0 0 1-5 0A10 10 0 0 0 12 2z"/></svg>
                <span>Mina understood: ${escapeHtml(aiIntent)}</span>
            </div>
        ` : '';
        
        contextBubble.innerHTML = `
            <div class="context-bubble-header">
                <div class="context-bubble-speaker">
                    <span class="speaker-avatar">${escapeHtml(speakerInitials)}</span>
                    ${escapeHtml(speakerDisplay)}
                </div>
                ${hasTimestamp ? `<span class="context-bubble-time">${timestamp}</span>` : ''}
            </div>
            <div class="context-bubble-text">
                "${escapeHtml(displayText)}"
            </div>
            ${intentHtml}
            <div class="context-bubble-footer">
                <span class="context-bubble-meeting">${escapeHtml(meetingLinkTitle)}</span>
                <a href="${meetingUrl}" class="context-bubble-link">
                    <svg viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    Jump to transcript
                </a>
            </div>
        `;

        // Position bubble
        const triggerRect = trigger.getBoundingClientRect();
        const bubbleWidth = 340;
        
        let left = triggerRect.left;
        let top = triggerRect.bottom + 8;

        // Adjust if off-screen
        if (left + bubbleWidth > window.innerWidth - 20) {
            left = window.innerWidth - bubbleWidth - 20;
        }
        if (left < 20) left = 20;

        // Check if bubble would go below viewport
        if (top + 200 > window.innerHeight) {
            top = triggerRect.top - 200 - 8;
            contextBubble.classList.add('above');
        } else {
            contextBubble.classList.remove('above');
        }

        contextBubble.style.left = `${left}px`;
        contextBubble.style.top = `${top}px`;
        contextBubble.classList.add('visible');
    }

    function toggleContextBubble(trigger) {
        if (contextBubble.classList.contains('visible')) {
            hideBubble();
        } else {
            showContextBubble(trigger);
        }
    }

    function scheduleHideBubble() {
        contextBubbleTimeout = setTimeout(() => hideBubble(), 300);
    }

    function hideBubble() {
        if (contextBubble) {
            contextBubble.classList.remove('visible');
        }
    }

    // Archive task
    async function archiveTask(taskId) {
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (card) card.style.opacity = '0.5';

        try {
            const response = await fetch(`${API_BASE}/${taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify({ status: 'archived' })
            });

            if (response.ok) {
                if (currentFilter === 'active') {
                    if (card) {
                        card.style.transition = 'all 0.3s ease';
                        card.style.transform = 'translateX(-100%)';
                        card.style.opacity = '0';
                        setTimeout(() => card.remove(), 300);
                    }
                }
                showUndoToast('Task archived');
            } else {
                if (card) card.style.opacity = '1';
            }
        } catch (err) {
            if (card) card.style.opacity = '1';
            console.error('[Tasks] Archive failed:', err);
        }
    }

    // Duplicate task
    async function duplicateTask(taskId) {
        try {
            const response = await fetch(`${API_BASE}/${taskId}/duplicate`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken() 
                }
            });

            const data = await response.json();
            
            if (response.ok && data.success) {
                showUndoToast('Task duplicated');
                // Reload to show the new task
                window.location.reload();
            } else {
                console.error('[Tasks] Duplicate failed:', data.message || 'Unknown error');
                showUndoToast('Failed to duplicate task');
            }
        } catch (err) {
            console.error('[Tasks] Duplicate error:', err);
            showUndoToast('Failed to duplicate task');
        }
    }

    // Inline Title Editing
    function initInlineEditing() {
        document.querySelectorAll('.task-title').forEach(titleEl => {
            titleEl.classList.add('editable');
            titleEl.addEventListener('click', (e) => {
                if (e.target.closest('.task-title-input')) return;
                startInlineEdit(titleEl);
            });
        });
    }

    function startInlineEdit(titleEl) {
        if (titleEl.querySelector('.task-title-input')) return;
        
        const currentText = titleEl.textContent.trim();
        const taskId = titleEl.closest('.task-card')?.dataset.taskId;
        
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'task-title-input';
        input.value = currentText;
        
        titleEl.textContent = '';
        titleEl.appendChild(input);
        input.focus();
        input.select();
        
        const finishEdit = async (save) => {
            const newText = input.value.trim();
            input.remove();
            titleEl.textContent = save && newText ? newText : currentText;
            
            if (save && newText && newText !== currentText && taskId) {
                await updateTaskTitle(taskId, newText);
            }
        };
        
        input.addEventListener('blur', () => finishEdit(true));
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                input.blur();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                finishEdit(false);
            }
        });
    }

    async function updateTaskTitle(taskId, newTitle) {
        try {
            const response = await fetch(`${API_BASE}/${taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify({ title: newTitle })
            });

            if (response.ok) {
                showUndoToast('Task updated');
            }
        } catch (err) {
            console.error('[Tasks] Update title failed:', err);
        }
    }

    // Context Menu - Edit (triggers inline edit)
    function openEditModal(taskId) {
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        const titleEl = card?.querySelector('.task-title');
        if (titleEl) startInlineEdit(titleEl);
    }

    // ===== Quick Action Modals =====
    let currentModalTaskId = null;
    let currentLabels = [];

    // Context Menu - Assign
    async function openAssignModal(taskId) {
        currentModalTaskId = taskId;
        const modal = document.getElementById('assign-modal');
        const userList = document.getElementById('user-list');
        modal.style.display = 'flex';
        userList.innerHTML = 'Loading...';

        try {
            const response = await fetch(`${API_BASE}/workspace-users`);
            const data = await response.json();
            if (data.success && data.users) {
                userList.innerHTML = data.users.map(user => `
                    <button class="user-item ${user.is_current_user ? 'current' : ''}" data-user-id="${user.id}">
                        <span class="user-avatar">${(user.display_name || user.username).slice(0, 2).toUpperCase()}</span>
                        <div class="user-info">
                            <div class="user-name">${user.display_name || user.username}</div>
                            <div class="user-email">${user.email || ''}</div>
                        </div>
                    </button>
                `).join('') + `<button class="user-item" data-user-id=""><span class="user-avatar">—</span><div class="user-info"><div class="user-name">Unassign</div></div></button>`;
                
                userList.querySelectorAll('.user-item').forEach(item => {
                    item.addEventListener('click', () => selectAssignee(item.dataset.userId));
                });
            }
        } catch (err) {
            userList.innerHTML = '<p>Failed to load users</p>';
        }
    }

    function selectAssignee(userId) {
        const modal = document.getElementById('assign-modal');
        modal.style.display = 'none';
        if (currentModalTaskId) {
            const value = userId ? parseInt(userId) : null;
            updateTaskField(currentModalTaskId, { assigned_to_id: value });
            updateAssigneeUI(currentModalTaskId, userId);
        }
    }

    function updateAssigneeUI(taskId, userId) {
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (!card) return;
        let meta = card.querySelector('.task-meta');
        let assigneeEl = meta?.querySelector('.meta-item.assignee');
        
        if (!userId) {
            if (assigneeEl) assigneeEl.remove();
            return;
        }
        
        // We don't have user name here - will update on page refresh
        showUndoToast('Assignee updated');
    }

    // Context Menu - Set Due Date
    function openDueDateModal(taskId) {
        currentModalTaskId = taskId;
        const modal = document.getElementById('due-date-modal');
        const input = document.getElementById('due-date-input');
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        input.value = card?.dataset.dueDate || '';
        modal.style.display = 'flex';
    }

    function initDueDateModal() {
        document.getElementById('due-date-cancel')?.addEventListener('click', () => {
            document.getElementById('due-date-modal').style.display = 'none';
        });
        
        document.getElementById('due-date-save')?.addEventListener('click', () => {
            const input = document.getElementById('due-date-input');
            const modal = document.getElementById('due-date-modal');
            modal.style.display = 'none';
            if (currentModalTaskId) {
                updateTaskField(currentModalTaskId, { due_date: input.value || null });
                updateDueDateUI(currentModalTaskId, input.value);
            }
        });
        
        document.querySelectorAll('.date-shortcut').forEach(btn => {
            btn.addEventListener('click', () => {
                const days = parseInt(btn.dataset.days);
                const input = document.getElementById('due-date-input');
                if (days === -1) {
                    input.value = '';
                } else {
                    const d = new Date();
                    d.setDate(d.getDate() + days);
                    input.value = d.toISOString().split('T')[0];
                }
            });
        });
    }

    function updateDueDateUI(taskId, dueDate) {
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (!card) return;
        card.dataset.dueDate = dueDate || '';
        showUndoToast('Due date updated');
    }

    // Context Menu - Set Priority
    function openPriorityModal(taskId) {
        currentModalTaskId = taskId;
        const modal = document.getElementById('priority-modal');
        modal.style.display = 'flex';
    }

    function initPriorityModal() {
        document.getElementById('priority-cancel')?.addEventListener('click', () => {
            document.getElementById('priority-modal').style.display = 'none';
        });
        
        document.querySelectorAll('.priority-option').forEach(btn => {
            btn.addEventListener('click', () => {
                const priority = btn.dataset.priority;
                const modal = document.getElementById('priority-modal');
                modal.style.display = 'none';
                if (currentModalTaskId) {
                    const card = document.querySelector(`.task-card[data-task-id="${currentModalTaskId}"]`);
                    updateTaskField(currentModalTaskId, { priority });
                    updatePriorityUI(card, priority);
                }
            });
        });
    }

    // Context Menu - Labels
    function openLabelsModal(taskId) {
        currentModalTaskId = taskId;
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        
        // Get existing labels from card
        const labelEls = card?.querySelectorAll('.task-label');
        currentLabels = labelEls ? Array.from(labelEls).map(el => el.textContent) : [];
        
        renderCurrentLabels();
        document.getElementById('labels-modal').style.display = 'flex';
        document.getElementById('labels-input').value = '';
        document.getElementById('labels-input').focus();
    }

    function renderCurrentLabels() {
        const container = document.getElementById('current-labels');
        container.innerHTML = currentLabels.map(label => `
            <span class="label-chip">
                ${label}
                <button data-label="${label}" aria-label="Remove ${label}">
                    <svg viewBox="0 0 24 24" width="12" height="12"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            </span>
        `).join('');
        
        container.querySelectorAll('.label-chip button').forEach(btn => {
            btn.addEventListener('click', () => {
                currentLabels = currentLabels.filter(l => l !== btn.dataset.label);
                renderCurrentLabels();
            });
        });
    }

    function initLabelsModal() {
        document.getElementById('labels-cancel')?.addEventListener('click', () => {
            document.getElementById('labels-modal').style.display = 'none';
        });
        
        document.getElementById('labels-save')?.addEventListener('click', () => {
            document.getElementById('labels-modal').style.display = 'none';
            if (currentModalTaskId) {
                updateTaskField(currentModalTaskId, { labels: currentLabels });
                updateLabelsUI(currentModalTaskId, currentLabels);
            }
        });
        
        document.getElementById('labels-input')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const input = e.target;
                const label = input.value.trim();
                if (label && !currentLabels.includes(label)) {
                    currentLabels.push(label);
                    renderCurrentLabels();
                }
                input.value = '';
            }
        });
        
        document.querySelectorAll('.label-suggestion').forEach(btn => {
            btn.addEventListener('click', () => {
                const label = btn.dataset.label;
                if (!currentLabels.includes(label)) {
                    currentLabels.push(label);
                    renderCurrentLabels();
                }
            });
        });
    }

    function updateLabelsUI(taskId, labels) {
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (!card) return;
        
        const meta = card.querySelector('.task-meta');
        if (!meta) return;
        
        // Remove existing labels
        meta.querySelectorAll('.task-label').forEach(el => el.remove());
        
        // Add new labels (max 2 visible)
        labels.slice(0, 2).forEach(label => {
            const span = document.createElement('span');
            span.className = 'task-label';
            span.textContent = label;
            meta.appendChild(span);
        });
        
        showUndoToast('Labels updated');
    }

    // Assign modal cancel
    function initAssignModal() {
        document.getElementById('assign-cancel')?.addEventListener('click', () => {
            document.getElementById('assign-modal').style.display = 'none';
        });
    }

    // Close modals on backdrop click
    document.querySelectorAll('.quick-modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.style.display = 'none';
        });
    });

    async function updateTaskField(taskId, fields) {
        try {
            const response = await fetch(`${API_BASE}/${taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify(fields)
            });

            if (response.ok) {
                showUndoToast('Task updated');
            }
        } catch (err) {
            console.error('[Tasks] Update field failed:', err);
        }
    }

    function updatePriorityUI(card, priority) {
        if (!card) return;
        const checkbox = card.querySelector('.task-checkbox');
        if (!checkbox) return;
        
        // Update checkbox styling
        checkbox.classList.remove('priority-high', 'priority-medium');
        if (priority === 'high' || priority === 'urgent') {
            checkbox.classList.add('priority-high');
        } else if (priority === 'medium') {
            checkbox.classList.add('priority-medium');
        }
        card.dataset.priority = priority;
        
        // Update or create priority badge
        const titleRow = card.querySelector('.task-title-row');
        if (titleRow) {
            let badge = titleRow.querySelector('.priority-badge');
            if (priority === 'low') {
                // Remove badge for low priority
                if (badge) badge.remove();
            } else {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'priority-badge';
                    titleRow.appendChild(badge);
                }
                badge.className = `priority-badge priority-${priority}`;
                badge.textContent = priority;
            }
        }
    }

    // Enhanced Group By Dropdown
    function initGroupingToggle() {
        const dropdown = document.getElementById('group-by-dropdown');
        const btn = document.getElementById('group-by-btn');
        const menu = document.getElementById('group-by-menu');
        if (!dropdown || !btn || !menu) return;

        // Set initial state from localStorage
        updateGroupBySelection(currentGroupBy);
        if (currentGroupBy !== 'none') {
            renderGrouped(currentGroupBy);
        }

        // Toggle dropdown
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.classList.toggle('open');
            btn.setAttribute('aria-expanded', dropdown.classList.contains('open'));
        });

        // Handle option selection
        menu.querySelectorAll('.group-by-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                const groupBy = option.dataset.group;
                setGroupBy(groupBy);
                dropdown.classList.remove('open');
                btn.setAttribute('aria-expanded', 'false');
            });
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target)) {
                dropdown.classList.remove('open');
                btn.setAttribute('aria-expanded', 'false');
            }
        });

        // Close on Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && dropdown.classList.contains('open')) {
                dropdown.classList.remove('open');
                btn.setAttribute('aria-expanded', 'false');
            }
        });
    }

    function setGroupBy(groupBy) {
        currentGroupBy = groupBy;
        localStorage.setItem('tasks_group_by', groupBy);
        updateGroupBySelection(groupBy);
        
        if (groupBy === 'none') {
            renderFlatList();
        } else {
            renderGrouped(groupBy);
        }
    }

    function updateGroupBySelection(groupBy) {
        const menu = document.getElementById('group-by-menu');
        const btn = document.getElementById('group-by-btn');
        if (!menu || !btn) return;

        menu.querySelectorAll('.group-by-option').forEach(option => {
            const isActive = option.dataset.group === groupBy;
            option.classList.toggle('active', isActive);
            option.setAttribute('aria-selected', isActive);
        });

        // Update button state
        if (groupBy !== 'none') {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    }

    function renderGrouped(groupBy) {
        const taskList = document.getElementById('task-list');
        const taskGroups = document.getElementById('task-groups');
        if (!taskGroups) return;

        const cards = Array.from(taskGroups.querySelectorAll('.task-card'));
        if (cards.length === 0) return;

        const groups = groupTaskCards(cards, groupBy);
        const groupOrder = getGroupOrder(groupBy);
        const groupLabels = getGroupLabels(groupBy);
        const groupIcons = getGroupIcons(groupBy);

        taskGroups.innerHTML = '';

        groupOrder.forEach(key => {
            const group = groups.get(key);
            if (!group || group.length === 0) return;

            const groupEl = createCollapsibleGroup(
                groupBy, 
                key, 
                groupLabels[key] || key, 
                groupIcons[key] || groupIcons.default, 
                group
            );
            taskGroups.appendChild(groupEl);
        });

        // Add "other" group for items not matching standard keys
        const otherKeys = Array.from(groups.keys()).filter(k => !groupOrder.includes(k));
        otherKeys.forEach(key => {
            const group = groups.get(key);
            if (!group || group.length === 0) return;

            const groupEl = createCollapsibleGroup(
                groupBy, 
                key, 
                groupLabels[key] || key, 
                groupIcons[key] || groupIcons.default, 
                group
            );
            taskGroups.appendChild(groupEl);
        });

        taskGroups.classList.add('grouped-view');
    }

    function groupTaskCards(cards, groupBy) {
        const groups = new Map();

        cards.forEach(card => {
            let key;
            switch (groupBy) {
                case 'meeting':
                    const meetingId = card.dataset.meetingId;
                    if (meetingId) {
                        key = meetingId;
                        if (!groups.has(key)) {
                            const meetingLink = card.querySelector('.provenance-meeting');
                            groups.set(key, { title: meetingLink?.textContent.trim() || 'Unknown Meeting', cards: [] });
                        }
                        groups.get(key).cards.push(card);
                    } else {
                        key = 'manual';
                        if (!groups.has(key)) groups.set(key, { title: 'Manual Tasks', cards: [] });
                        groups.get(key).cards.push(card);
                    }
                    return;
                case 'priority':
                    key = card.dataset.priority || 'low';
                    break;
                case 'status':
                    key = card.dataset.status || 'todo';
                    break;
                case 'due':
                    key = getDueDateGroup(card.dataset.dueDate);
                    break;
                default:
                    key = 'all';
            }
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(card);
        });

        return groups;
    }

    function getDueDateGroup(dateStr) {
        if (!dateStr) return 'no_date';
        const dueDate = new Date(dateStr);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        const weekEnd = new Date(today);
        weekEnd.setDate(weekEnd.getDate() + 7);

        if (dueDate < today) return 'overdue';
        if (dueDate.toDateString() === today.toDateString()) return 'today';
        if (dueDate < weekEnd) return 'this_week';
        return 'later';
    }

    function getGroupOrder(groupBy) {
        switch (groupBy) {
            case 'priority':
                return ['urgent', 'high', 'medium', 'low'];
            case 'status':
                return ['todo', 'in_progress', 'blocked', 'completed'];
            case 'due':
                return ['overdue', 'today', 'this_week', 'later', 'no_date'];
            case 'meeting':
                return []; // Dynamic based on meetings
            default:
                return [];
        }
    }

    function getGroupLabels(groupBy) {
        switch (groupBy) {
            case 'priority':
                return { urgent: 'Urgent', high: 'High Priority', medium: 'Medium Priority', low: 'Low Priority' };
            case 'status':
                return { todo: 'To Do', in_progress: 'In Progress', blocked: 'Blocked', completed: 'Completed' };
            case 'due':
                return { overdue: 'Overdue', today: 'Today', this_week: 'This Week', later: 'Later', no_date: 'No Due Date' };
            case 'meeting':
                return { manual: 'Manual Tasks' };
            default:
                return {};
        }
    }

    function getGroupIcons(groupBy) {
        const icons = {
            priority: {
                urgent: '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>',
                high: '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>',
                medium: '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>',
                low: '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>',
                default: '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>'
            },
            status: {
                todo: '<svg viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="12" r="10"/></svg>',
                in_progress: '<svg viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
                blocked: '<svg viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>',
                completed: '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
                default: '<svg viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="12" r="10"/></svg>'
            },
            due: {
                overdue: '<svg viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
                today: '<svg viewBox="0 0 24 24" width="16" height="16"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
                this_week: '<svg viewBox="0 0 24 24" width="16" height="16"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
                later: '<svg viewBox="0 0 24 24" width="16" height="16"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
                no_date: '<svg viewBox="0 0 24 24" width="16" height="16"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="9" y1="15" x2="15" y2="15"/></svg>',
                default: '<svg viewBox="0 0 24 24" width="16" height="16"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="10" x2="21" y2="10"/></svg>'
            },
            meeting: {
                manual: '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
                default: '<svg viewBox="0 0 24 24" width="16" height="16"><path d="M19 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>'
            }
        };
        return icons[groupBy] || { default: '<svg viewBox="0 0 24 24" width="16" height="16"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>' };
    }

    function createCollapsibleGroup(groupType, key, label, icon, items) {
        // Handle meeting groups which have a different structure
        const cards = Array.isArray(items) ? items : (items.cards || []);
        const title = Array.isArray(items) ? label : (items.title || label);
        
        const groupEl = document.createElement('div');
        groupEl.className = 'task-group';
        groupEl.dataset.groupType = groupType;
        groupEl.dataset.groupKey = key;
        
        // Check if this group is collapsed
        const groupId = `${groupType}_${key}`;
        if (collapsedGroups[groupId]) {
            groupEl.classList.add('collapsed');
        }

        groupEl.innerHTML = `
            <div class="task-group-header" role="button" aria-expanded="${!collapsedGroups[groupId]}" tabindex="0">
                <svg class="collapse-icon" viewBox="0 0 24 24" width="14" height="14"><polyline points="6 9 12 15 18 9"/></svg>
                <span class="group-icon">${icon}</span>
                <span class="group-title">${escapeHtml(title)}</span>
                <span class="group-count">${cards.length}</span>
            </div>
            <div class="task-group-content"></div>
        `;

        const header = groupEl.querySelector('.task-group-header');
        const content = groupEl.querySelector('.task-group-content');

        // Add click handler for collapse/expand
        header.addEventListener('click', () => toggleGroupCollapse(groupEl, groupId));
        header.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleGroupCollapse(groupEl, groupId);
            }
        });

        // Append cards
        cards.forEach(card => content.appendChild(card));

        return groupEl;
    }

    function toggleGroupCollapse(groupEl, groupId) {
        const isCollapsed = groupEl.classList.toggle('collapsed');
        const header = groupEl.querySelector('.task-group-header');
        header.setAttribute('aria-expanded', !isCollapsed);
        
        // Persist state
        collapsedGroups[groupId] = isCollapsed;
        localStorage.setItem('tasks_collapsed_groups', JSON.stringify(collapsedGroups));
        
        // Broadcast to other tabs
        if (window.BroadcastChannel) {
            try {
                const channel = new BroadcastChannel('mina_tasks_sync');
                channel.postMessage({ type: 'group_collapse', groupId, isCollapsed });
                channel.close();
            } catch (e) {}
        }
    }

    function renderFlatList() {
        const taskGroups = document.getElementById('task-groups');
        if (!taskGroups) return;

        const allCards = Array.from(taskGroups.querySelectorAll('.task-card'));
        
        allCards.sort((a, b) => {
            const posA = parseInt(a.dataset.position) || 0;
            const posB = parseInt(b.dataset.position) || 0;
            return posA - posB;
        });

        taskGroups.innerHTML = '';
        
        const newList = document.createElement('div');
        newList.className = 'task-list';
        newList.id = 'task-list';
        
        allCards.forEach(card => newList.appendChild(card));
        taskGroups.appendChild(newList);
        taskGroups.classList.remove('grouped-view');
    }

    // Listen for group collapse updates from other tabs
    if (window.BroadcastChannel) {
        try {
            const syncChannel = new BroadcastChannel('mina_tasks_sync');
            syncChannel.onmessage = (e) => {
                if (e.data.type === 'group_collapse') {
                    collapsedGroups[e.data.groupId] = e.data.isCollapsed;
                    const groupEl = document.querySelector(`.task-group[data-group-type="${e.data.groupId.split('_')[0]}"][data-group-key="${e.data.groupId.split('_').slice(1).join('_')}"]`);
                    if (groupEl) {
                        groupEl.classList.toggle('collapsed', e.data.isCollapsed);
                        groupEl.querySelector('.task-group-header')?.setAttribute('aria-expanded', !e.data.isCollapsed);
                    }
                }
            };
        } catch (e) {}
    }

    // Utilities
    function getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || '';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

})();
