/**
 * Task Assignee Selector
 * Multi-user assignee selector with search functionality
 * Fetches users from /api/tasks/users endpoint
 */

class TaskAssigneeSelector {
    constructor() {
        this.modal = null;
        this.resolveCallback = null;
        this.selectedAssignees = [];
        this.allUsers = [];
        this.init();
    }

    init() {
        this.createModal();
        this.setupEventListeners();
    }

    createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'task-assignee-modal-overlay';
        this.modal.innerHTML = `
            <div class="task-assignee-modal">
                <div class="task-assignee-modal-header">
                    <h3>Assign to...</h3>
                    <button class="task-assignee-modal-close" title="Close">
                        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                    </button>
                </div>
                <div class="task-assignee-modal-body">
                    <div class="task-assignee-search">
                        <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24" class="search-icon">
                            <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
                        </svg>
                        <input type="text" 
                               class="task-assignee-search-input" 
                               placeholder="Search team members..." 
                               autocomplete="off">
                    </div>
                    <div class="task-assignee-selected" style="display: none;">
                        <div class="task-assignee-selected-label">Selected:</div>
                        <div class="task-assignee-selected-list"></div>
                    </div>
                    <div class="task-assignee-list"></div>
                    <div class="task-assignee-loading" style="display: none;">
                        <div class="spinner"></div>
                        <div>Loading team members...</div>
                    </div>
                    <div class="task-assignee-error" style="display: none;"></div>
                </div>
                <div class="task-assignee-modal-footer">
                    <button class="btn-secondary task-assignee-cancel">Cancel</button>
                    <button class="btn-primary task-assignee-save">Save</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.modal);
    }

    setupEventListeners() {
        const closeBtn = this.modal.querySelector('.task-assignee-modal-close');
        const cancelBtn = this.modal.querySelector('.task-assignee-cancel');
        const saveBtn = this.modal.querySelector('.task-assignee-save');
        const searchInput = this.modal.querySelector('.task-assignee-search-input');

        closeBtn.addEventListener('click', () => this.close(null));
        cancelBtn.addEventListener('click', () => this.close(null));
        saveBtn.addEventListener('click', () => this.close(this.selectedAssignees));

        searchInput.addEventListener('input', (e) => {
            this.filterUsers(e.target.value);
        });

        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close(null);
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('visible')) {
                this.close(null);
            }
        });
    }

    async show(currentAssigneeIds = []) {
        this.selectedAssignees = [...(currentAssigneeIds || [])];
        
        const loading = this.modal.querySelector('.task-assignee-loading');
        const list = this.modal.querySelector('.task-assignee-list');
        const error = this.modal.querySelector('.task-assignee-error');

        loading.style.display = 'flex';
        list.style.display = 'none';
        error.style.display = 'none';

        this.modal.classList.remove('hidden');
        this.modal.style.display = 'flex';
        requestAnimationFrame(() => {
            this.modal.classList.add('visible');
        });

        try {
            await this.loadUsers();
            this.renderUsers();
            loading.style.display = 'none';
            list.style.display = 'block';
            
            const searchInput = this.modal.querySelector('.task-assignee-search-input');
            searchInput.value = '';
            searchInput.focus();
        } catch (err) {
            loading.style.display = 'none';
            error.style.display = 'block';
            error.textContent = 'Failed to load team members. Please try again.';
        }

        return new Promise((resolve) => {
            this.resolveCallback = resolve;
        });
    }

    async loadUsers() {
        const response = await fetch('/api/tasks/users');
        if (!response.ok) {
            throw new Error('Failed to load users');
        }
        const data = await response.json();
        this.allUsers = data.users || [];
    }

    renderUsers(filteredUsers = null) {
        const users = filteredUsers || this.allUsers;
        const list = this.modal.querySelector('.task-assignee-list');
        
        if (users.length === 0) {
            list.innerHTML = '<div class="task-assignee-empty">No team members found</div>';
            return;
        }

        list.innerHTML = users.map(user => {
            const isSelected = this.selectedAssignees.includes(user.id);
            return `
                <div class="task-assignee-item ${isSelected ? 'selected' : ''}" 
                     data-user-id="${user.id}">
                    <div class="task-assignee-avatar">
                        ${this.getInitials(user.display_name || user.username)}
                    </div>
                    <div class="task-assignee-info">
                        <div class="task-assignee-name">${user.display_name || user.username}</div>
                        ${user.email ? `<div class="task-assignee-email">${user.email}</div>` : ''}
                    </div>
                    <div class="task-assignee-checkbox">
                        <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                        </svg>
                    </div>
                </div>
            `;
        }).join('');

        list.querySelectorAll('.task-assignee-item').forEach(item => {
            item.addEventListener('click', () => {
                const userId = parseInt(item.dataset.userId);
                this.toggleUser(userId, item);
            });
        });

        this.updateSelectedDisplay();
    }

    toggleUser(userId, itemElement) {
        const index = this.selectedAssignees.indexOf(userId);
        if (index > -1) {
            this.selectedAssignees.splice(index, 1);
            itemElement.classList.remove('selected');
        } else {
            this.selectedAssignees.push(userId);
            itemElement.classList.add('selected');
        }
        this.updateSelectedDisplay();
    }

    updateSelectedDisplay() {
        const selectedContainer = this.modal.querySelector('.task-assignee-selected');
        const selectedList = this.modal.querySelector('.task-assignee-selected-list');
        
        if (this.selectedAssignees.length === 0) {
            selectedContainer.style.display = 'none';
            return;
        }

        selectedContainer.style.display = 'flex';
        const selectedUsers = this.allUsers.filter(u => this.selectedAssignees.includes(u.id));
        
        selectedList.innerHTML = selectedUsers.map(user => `
            <span class="task-assignee-chip">
                ${user.display_name || user.username}
                <button class="task-assignee-chip-remove" data-user-id="${user.id}">
                    <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                </button>
            </span>
        `).join('');

        selectedList.querySelectorAll('.task-assignee-chip-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const userId = parseInt(btn.dataset.userId);
                this.selectedAssignees = this.selectedAssignees.filter(id => id !== userId);
                this.renderUsers();
            });
        });
    }

    filterUsers(searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        if (!term) {
            this.renderUsers();
            return;
        }

        const filtered = this.allUsers.filter(user => {
            const name = (user.display_name || user.username || '').toLowerCase();
            const email = (user.email || '').toLowerCase();
            return name.includes(term) || email.includes(term);
        });

        this.renderUsers(filtered);
    }

    getInitials(name) {
        if (!name) return '?';
        const parts = name.trim().split(' ');
        if (parts.length >= 2) {
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        }
        return name[0].toUpperCase();
    }

    close(result) {
        this.modal.classList.remove('visible');
        
        setTimeout(() => {
            this.modal.style.display = 'none';
            if (this.resolveCallback) {
                this.resolveCallback(result);
                this.resolveCallback = null;
            }
        }, 200);
    }
}

window.taskAssigneeSelector = new TaskAssigneeSelector();
