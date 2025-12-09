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
    let groupByMeeting = localStorage.getItem('tasks_group_by_meeting') === 'true';

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    function init() {
        loadTasksData();
        loadMeetingHeatmap();
        bindEventListeners();
        initializeKeyboardShortcuts();
        initGroupingToggle();
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
        
        // Position menu
        const rect = e.currentTarget.getBoundingClientRect();
        menu.style.left = `${rect.left}px`;
        menu.style.top = `${rect.bottom + 4}px`;
        menu.style.display = 'block';

        // Adjust if off screen
        const menuRect = menu.getBoundingClientRect();
        if (menuRect.right > window.innerWidth) {
            menu.style.left = `${window.innerWidth - menuRect.width - 16}px`;
        }
        if (menuRect.bottom > window.innerHeight) {
            menu.style.top = `${rect.top - menuRect.height - 4}px`;
        }
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
                if (longPressActiveCard) {
                    hideTranscriptPreview(longPressActiveCard);
                    longPressActiveCard = null;
                }
            });

            card.addEventListener('touchmove', () => {
                clearTimeout(longPressTimer);
            }, { passive: true });

            card.addEventListener('touchcancel', () => {
                clearTimeout(longPressTimer);
                if (longPressActiveCard) {
                    hideTranscriptPreview(longPressActiveCard);
                    longPressActiveCard = null;
                }
            });
        });
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
                headers: { 'X-CSRF-Token': getCSRFToken() }
            });

            if (response.ok) {
                showUndoToast('Task duplicated');
                window.location.reload();
            } else {
                console.error('[Tasks] Duplicate failed');
            }
        } catch (err) {
            console.error('[Tasks] Duplicate error:', err);
        }
    }

    // Open edit modal (placeholder)
    function openEditModal(taskId) {
        const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        const title = card?.querySelector('.task-title')?.textContent || '';
        const newTitle = prompt('Edit task title:', title);
        if (newTitle && newTitle !== title) {
            updateTaskTitle(taskId, newTitle);
        }
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
                const card = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
                const titleEl = card?.querySelector('.task-title');
                if (titleEl) titleEl.textContent = newTitle;
                showUndoToast('Task updated');
            }
        } catch (err) {
            console.error('[Tasks] Update title failed:', err);
        }
    }

    // Meeting Intelligence Mode - Group by Meeting Toggle
    function initGroupingToggle() {
        const toggleBtn = document.getElementById('toggle-grouping');
        if (!toggleBtn) return;

        updateGroupingButtonState(toggleBtn);
        
        if (groupByMeeting) {
            renderGroupedByMeeting();
        }

        toggleBtn.addEventListener('click', () => {
            groupByMeeting = !groupByMeeting;
            localStorage.setItem('tasks_group_by_meeting', groupByMeeting);
            updateGroupingButtonState(toggleBtn);
            
            if (groupByMeeting) {
                renderGroupedByMeeting();
            } else {
                renderFlatList();
            }
        });
    }

    function updateGroupingButtonState(btn) {
        if (groupByMeeting) {
            btn.classList.add('active');
            btn.title = 'Switch to flat list';
        } else {
            btn.classList.remove('active');
            btn.title = 'Group by meeting';
        }
    }

    function renderGroupedByMeeting() {
        const taskList = document.getElementById('task-list');
        const taskGroups = document.getElementById('task-groups');
        if (!taskList || !taskGroups) return;

        const cards = Array.from(taskList.querySelectorAll('.task-card'));
        if (cards.length === 0) return;

        const meetingGroups = new Map();
        const noMeetingTasks = [];

        cards.forEach(card => {
            const meetingId = card.dataset.meetingId;
            if (meetingId) {
                if (!meetingGroups.has(meetingId)) {
                    const meetingLink = card.querySelector('.provenance-meeting');
                    const meetingTitle = meetingLink?.textContent.trim() || 'Unknown Meeting';
                    meetingGroups.set(meetingId, { title: meetingTitle, cards: [] });
                }
                meetingGroups.get(meetingId).cards.push(card);
            } else {
                noMeetingTasks.push(card);
            }
        });

        taskList.innerHTML = '';
        taskGroups.innerHTML = '';

        meetingGroups.forEach((group, meetingId) => {
            const groupEl = document.createElement('div');
            groupEl.className = 'meeting-group';
            groupEl.innerHTML = `
                <div class="meeting-group-header">
                    <svg viewBox="0 0 24 24" width="16" height="16"><path d="M19 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
                    <span class="group-title">${escapeHtml(group.title)}</span>
                    <span class="group-count">${group.cards.length}</span>
                </div>
                <div class="meeting-group-tasks" data-meeting-id="${meetingId}"></div>
            `;
            
            const tasksContainer = groupEl.querySelector('.meeting-group-tasks');
            group.cards.forEach(card => tasksContainer.appendChild(card));
            taskGroups.appendChild(groupEl);
        });

        if (noMeetingTasks.length > 0) {
            const manualGroup = document.createElement('div');
            manualGroup.className = 'meeting-group';
            manualGroup.innerHTML = `
                <div class="meeting-group-header">
                    <svg viewBox="0 0 24 24" width="16" height="16"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    <span class="group-title">Manual Tasks</span>
                    <span class="group-count">${noMeetingTasks.length}</span>
                </div>
                <div class="meeting-group-tasks"></div>
            `;
            
            const tasksContainer = manualGroup.querySelector('.meeting-group-tasks');
            noMeetingTasks.forEach(card => tasksContainer.appendChild(card));
            taskGroups.appendChild(manualGroup);
        }

        taskGroups.classList.add('grouped-view');
    }

    function renderFlatList() {
        const taskGroups = document.getElementById('task-groups');
        const taskList = document.getElementById('task-list');
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
