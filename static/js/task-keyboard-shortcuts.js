/**
 * CROWN⁴.5 Keyboard Shortcuts
 * Quick task creation, command palette, actions, and snooze.
 * Shortcuts: N, Cmd+K, Cmd+Enter, S
 */

class TaskKeyboardShortcuts {
    constructor() {
        this.shortcuts = new Map();
        this.commandPaletteOpen = false;
        this._registerShortcuts();
        this._setupListeners();
    }

    /**
     * Register all keyboard shortcuts
     */
    _registerShortcuts() {
        // N - New Task
        this.register('n', {
            description: 'Create new task',
            handler: this._handleNewTask.bind(this),
            global: true
        });

        // Cmd+K / Ctrl+K - Command Palette
        this.register(['cmd+k', 'ctrl+k'], {
            description: 'Open command palette',
            handler: this._handleCommandPalette.bind(this),
            global: true,
            preventDefault: true
        });

        // Cmd+Enter / Ctrl+Enter - Quick Complete
        this.register(['cmd+enter', 'ctrl+enter'], {
            description: 'Toggle task completion',
            handler: this._handleQuickComplete.bind(this),
            global: false
        });

        // S - Snooze
        this.register('s', {
            description: 'Snooze selected task',
            handler: this._handleSnooze.bind(this),
            global: false
        });

        // Escape - Close dialogs
        this.register('escape', {
            description: 'Close dialogs',
            handler: this._handleEscape.bind(this),
            global: true
        });

        // Arrow keys - Navigation
        this.register(['up', 'down'], {
            description: 'Navigate tasks',
            handler: this._handleNavigation.bind(this),
            global: false
        });

        // / - Search
        this.register('/', {
            description: 'Focus search',
            handler: this._handleSearch.bind(this),
            global: true,
            preventDefault: true
        });

        // ? - Help
        this.register('?', {
            description: 'Show keyboard shortcuts',
            handler: this._handleHelp.bind(this),
            global: true
        });
    }

    /**
     * Register keyboard shortcut
     * @param {string|Array} keys
     * @param {Object} config
     */
    register(keys, config) {
        const keyArray = Array.isArray(keys) ? keys : [keys];
        
        keyArray.forEach(key => {
            this.shortcuts.set(key.toLowerCase(), config);
        });
    }

    /**
     * Setup keyboard event listeners
     */
    _setupListeners() {
        document.addEventListener('keydown', (e) => {
            this._handleKeyDown(e);
        });
    }

    /**
     * Handle keydown event
     * @param {KeyboardEvent} e
     */
    _handleKeyDown(e) {
        // Build key string
        const key = this._buildKeyString(e);
        const shortcut = this.shortcuts.get(key);

        if (!shortcut) return;

        // Check if we should ignore (typing in input)
        if (this._shouldIgnore(e, shortcut)) return;

        // Prevent default if needed
        if (shortcut.preventDefault) {
            e.preventDefault();
        }

        // Execute handler
        shortcut.handler(e);
    }

    /**
     * Build key string from event
     * @param {KeyboardEvent} e
     * @returns {string}
     */
    _buildKeyString(e) {
        const parts = [];

        if (e.ctrlKey) parts.push('ctrl');
        if (e.metaKey) parts.push('cmd');
        if (e.altKey) parts.push('alt');
        if (e.shiftKey && e.key.length > 1) parts.push('shift');

        const key = e.key.toLowerCase();
        parts.push(key);

        return parts.join('+');
    }

    /**
     * Check if we should ignore this shortcut
     * @param {KeyboardEvent} e
     * @param {Object} shortcut
     * @returns {boolean}
     */
    _shouldIgnore(e, shortcut) {
        // ALWAYS ignore if typing in input/textarea/contentEditable
        // This prevents data loss when user is typing
        const target = e.target;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
            return true;
        }

        // Allow global shortcuts only if not in input field
        if (shortcut.global) return false;

        return false;
    }

    // Shortcut Handlers

    /**
     * Handle new task (N)
     */
    _handleNewTask() {
        console.log('[Keyboard] ⌨️ N pressed - New Task');
        console.log('[Keyboard] Looking for create button...');
        
        // Show task creation modal/form
        const createButton = document.querySelector('[data-action="create-task"]');
        if (createButton) {
            console.log('[Keyboard] ✅ Found create button, triggering click');
            createButton.click();
        } else {
            console.log('[Keyboard] Create button not found, showing quick dialog');
            this._showQuickCreateDialog();
        }
    }

    /**
     * Handle command palette (Cmd+K)
     */
    _handleCommandPalette() {
        console.log('[Keyboard] ⌨️ Cmd+K pressed - Command Palette');
        console.log('[Keyboard] Current palette state:', this.commandPaletteOpen ? 'OPEN' : 'CLOSED');
        
        if (this.commandPaletteOpen) {
            console.log('[Keyboard] Closing command palette');
            this._closeCommandPalette();
        } else {
            console.log('[Keyboard] Opening command palette');
            this._openCommandPalette();
        }
    }

    /**
     * Handle quick complete (Cmd+Enter)
     */
    async _handleQuickComplete() {
        console.log('[Keyboard] ⌨️ Cmd+Enter pressed - Quick Complete');
        
        const selectedTask = this._getSelectedTask();
        if (!selectedTask) {
            console.log('[Keyboard] ⚠️ No task selected for quick complete');
            return;
        }

        const taskId = selectedTask.dataset.taskId;
        console.log('[Keyboard] Selected task:', taskId);
        console.log('[Keyboard] Current status:', selectedTask.dataset?.status);
        
        if (window.optimisticUI) {
            console.log('[Keyboard] Calling optimisticUI.toggleTaskStatus()');
            const result = await window.optimisticUI.toggleTaskStatus(taskId);
            console.log('[Keyboard] ✅ Toggle result:', result);
        } else {
            console.error('[Keyboard] ❌ optimisticUI not available');
        }
    }

    /**
     * Handle snooze (S)
     */
    _handleSnooze() {
        console.log('[Keyboard] ⌨️ S pressed - Snooze');
        
        const selectedTask = this._getSelectedTask();
        if (!selectedTask) {
            console.log('[Keyboard] ⚠️ No task selected for snooze');
            return;
        }

        console.log('[Keyboard] Snoozing task:', selectedTask.dataset.taskId);
        this._showSnoozeDialog(selectedTask.dataset.taskId);
    }

    /**
     * Handle escape
     */
    _handleEscape() {
        // Close command palette
        if (this.commandPaletteOpen) {
            this._closeCommandPalette();
            return;
        }

        // Close any open dialogs
        const dialogs = document.querySelectorAll('.dialog.open, .modal.open');
        dialogs.forEach(dialog => dialog.classList.remove('open'));
    }

    /**
     * Handle navigation (Up/Down)
     * @param {KeyboardEvent} e
     */
    _handleNavigation(e) {
        const direction = e.key === 'ArrowUp' ? -1 : 1;
        this._moveTaskSelection(direction);
    }

    /**
     * Handle search (/)
     */
    _handleSearch() {
        console.log('[Keyboard] ⌨️ / pressed - Focus Search');
        
        const searchInput = document.querySelector('[data-search="tasks"]');
        if (searchInput) {
            console.log('[Keyboard] ✅ Found search input, focusing');
            searchInput.focus();
            searchInput.select();
        } else {
            console.log('[Keyboard] ⚠️ Search input not found');
        }
    }

    /**
     * Handle help (?)
     */
    _handleHelp() {
        console.log('[Keyboard] ⌨️ ? pressed - Show Help');
        this._showShortcutsHelp();
    }

    // Helper Methods

    /**
     * Show quick create dialog
     */
    _showQuickCreateDialog() {
        const dialog = document.createElement('div');
        dialog.className = 'quick-create-dialog';
        dialog.innerHTML = `
            <div class="dialog-overlay"></div>
            <div class="dialog-content">
                <h3>Quick Create Task</h3>
                <input type="text" 
                       placeholder="Task title..." 
                       class="task-title-input"
                       autofocus>
                <textarea placeholder="Description (optional)" 
                          class="task-description-input"></textarea>
                <div class="dialog-actions">
                    <button class="btn btn-secondary" data-action="cancel">Cancel</button>
                    <button class="btn btn-primary" data-action="create">Create</button>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);
        dialog.classList.add('open');

        // Handle create
        dialog.querySelector('[data-action="create"]').addEventListener('click', async () => {
            const title = dialog.querySelector('.task-title-input').value;
            const description = dialog.querySelector('.task-description-input').value;

            if (title.trim()) {
                if (window.optimisticUI) {
                    await window.optimisticUI.createTask({ title, description });
                }
                dialog.remove();
            }
        });

        // Handle cancel
        dialog.querySelector('[data-action="cancel"]').addEventListener('click', () => {
            dialog.remove();
        });

        // Handle enter to create
        dialog.querySelector('.task-title-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                dialog.querySelector('[data-action="create"]').click();
            }
        });
    }

    /**
     * Open command palette
     */
    _openCommandPalette() {
        const palette = document.createElement('div');
        palette.id = 'command-palette';
        palette.className = 'command-palette';
        palette.innerHTML = `
            <div class="palette-overlay"></div>
            <div class="palette-content">
                <input type="text" 
                       placeholder="Type a command..." 
                       class="palette-input"
                       autofocus>
                <div class="palette-results">
                    <div class="command-item" data-command="new-task">
                        <span class="command-icon">➕</span>
                        <span class="command-label">Create New Task</span>
                        <kbd>N</kbd>
                    </div>
                    <div class="command-item" data-command="filter-active">
                        <span class="command-icon">🔍</span>
                        <span class="command-label">Show Active Tasks</span>
                    </div>
                    <div class="command-item" data-command="filter-completed">
                        <span class="command-icon">✅</span>
                        <span class="command-label">Show Completed Tasks</span>
                    </div>
                    <div class="command-item" data-command="refresh">
                        <span class="command-icon">🔄</span>
                        <span class="command-label">Refresh Tasks</span>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(palette);
        this.commandPaletteOpen = true;

        // Handle command selection
        palette.querySelectorAll('.command-item').forEach(item => {
            item.addEventListener('click', () => {
                this._executeCommand(item.dataset.command);
                this._closeCommandPalette();
            });
        });

        // Handle search
        const input = palette.querySelector('.palette-input');
        input.addEventListener('input', (e) => {
            this._filterCommands(e.target.value);
        });
    }

    /**
     * Close command palette
     */
    _closeCommandPalette() {
        const palette = document.getElementById('command-palette');
        if (palette) {
            palette.remove();
        }
        this.commandPaletteOpen = false;
    }

    /**
     * Execute command
     * @param {string} command
     */
    async _executeCommand(command) {
        console.log('⚡ Executing command:', command);

        switch (command) {
            case 'new-task':
                this._handleNewTask();
                break;
            case 'filter-active':
                await this._applyFilter({ status: 'todo' });
                break;
            case 'filter-completed':
                await this._applyFilter({ status: 'completed' });
                break;
            case 'refresh':
                if (window.taskBootstrap) {
                    await window.taskBootstrap.syncInBackground();
                }
                break;
        }
    }

    /**
     * Filter commands
     * @param {string} query
     */
    _filterCommands(query) {
        const items = document.querySelectorAll('.command-item');
        const searchLower = query.toLowerCase();

        items.forEach(item => {
            const label = item.querySelector('.command-label').textContent.toLowerCase();
            if (label.includes(searchLower)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    }

    /**
     * Show snooze dialog
     * @param {string} taskId
     */
    _showSnoozeDialog(taskId) {
        const dialog = document.createElement('div');
        dialog.className = 'snooze-dialog';
        dialog.innerHTML = `
            <div class="dialog-overlay"></div>
            <div class="dialog-content">
                <h3>Snooze Task</h3>
                <div class="snooze-options">
                    <button class="snooze-option" data-hours="1">1 hour</button>
                    <button class="snooze-option" data-hours="4">4 hours</button>
                    <button class="snooze-option" data-hours="24">Tomorrow</button>
                    <button class="snooze-option" data-hours="168">Next week</button>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);

        dialog.querySelectorAll('.snooze-option').forEach(btn => {
            btn.addEventListener('click', async () => {
                const hours = parseInt(btn.dataset.hours);
                const snoozeUntil = new Date(Date.now() + hours * 60 * 60 * 1000);

                if (window.optimisticUI) {
                    await window.optimisticUI.snoozeTask(taskId, snoozeUntil);
                }

                dialog.remove();
            });
        });
    }

    /**
     * Show shortcuts help
     */
    _showShortcutsHelp() {
        const help = Array.from(this.shortcuts.entries())
            .map(([key, config]) => `
                <tr>
                    <td><kbd>${key}</kbd></td>
                    <td>${config.description}</td>
                </tr>
            `).join('');

        const dialog = document.createElement('div');
        dialog.className = 'shortcuts-help-dialog';
        dialog.innerHTML = `
            <div class="dialog-overlay"></div>
            <div class="dialog-content">
                <h3>Keyboard Shortcuts</h3>
                <table class="shortcuts-table">
                    <thead>
                        <tr>
                            <th>Shortcut</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${help}
                    </tbody>
                </table>
                <button class="btn btn-primary" data-action="close">Close</button>
            </div>
        `;

        document.body.appendChild(dialog);

        dialog.querySelector('[data-action="close"]').addEventListener('click', () => {
            dialog.remove();
        });
    }

    /**
     * Get currently selected task
     * @returns {Element|null}
     */
    _getSelectedTask() {
        return document.querySelector('.task-card.selected') || 
               document.querySelector('.task-card:focus') ||
               document.querySelector('.task-card:hover');
    }

    /**
     * Move task selection
     * @param {number} direction - -1 for up, 1 for down
     */
    _moveTaskSelection(direction) {
        const cards = Array.from(document.querySelectorAll('.task-card'));
        const selected = this._getSelectedTask();
        
        let nextIndex = 0;
        if (selected) {
            const currentIndex = cards.indexOf(selected);
            nextIndex = currentIndex + direction;
        }

        nextIndex = Math.max(0, Math.min(cards.length - 1, nextIndex));
        
        if (cards[nextIndex]) {
            cards.forEach(c => c.classList.remove('selected'));
            cards[nextIndex].classList.add('selected');
            cards[nextIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    /**
     * Apply filter
     * @param {Object} filter
     */
    async _applyFilter(filter) {
        if (window.tasksWS) {
            window.tasksWS.emit('task_event', {
                event_type: 'filter_change',
                data: filter
            });
        }
    }
}

// Export singleton
window.taskShortcuts = new TaskKeyboardShortcuts();

console.log('⌨️ CROWN⁴.5 Keyboard Shortcuts loaded');
