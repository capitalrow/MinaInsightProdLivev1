/**
 * SmartSelectors - Reusable UI Components for Task Management
 * Provides DatePicker, AssigneeSelector, PrioritySelector, and LabelSelector
 * Used across TaskModal, inline editing, and bulk operations
 */

class DatePicker {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            shortcuts: options.shortcuts !== false,
            allowPast: options.allowPast !== false,
            placeholder: options.placeholder || 'Select date',
            onChange: options.onChange || null
        };
        
        this.init();
    }
    
    init() {
        console.log('[DatePicker] Initializing for input:', this.input.id);
        this.input.type = 'date';
        this.input.placeholder = this.options.placeholder;
        
        if (this.options.shortcuts) {
            console.log('[DatePicker] Creating shortcuts...');
            this.createShortcuts();
        }
        
        this.input.addEventListener('change', () => {
            if (this.options.onChange) {
                this.options.onChange(this.getValue());
            }
        });
        
        console.log('[DatePicker] Initialized successfully');
    }
    
    createShortcuts() {
        console.log('[DatePicker] Creating shortcut buttons...');
        const container = document.createElement('div');
        container.className = 'date-picker-shortcuts';
        container.style.cssText = `
            display: flex !important;
            gap: 8px;
            margin-top: 12px;
            flex-wrap: wrap;
            padding: 4px 0;
            visibility: visible !important;
        `;
        
        const shortcuts = [
            { label: 'Today', getValue: () => this.formatDate(new Date()) },
            { label: 'Tomorrow', getValue: () => {
                const tomorrow = new Date();
                tomorrow.setDate(tomorrow.getDate() + 1);
                return this.formatDate(tomorrow);
            }},
            { label: 'Next Week', getValue: () => {
                const nextWeek = new Date();
                nextWeek.setDate(nextWeek.getDate() + 7);
                return this.formatDate(nextWeek);
            }},
            { label: 'Clear', getValue: () => '' }
        ];
        
        shortcuts.forEach(shortcut => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = shortcut.label;
            btn.className = 'date-shortcut-btn';
            btn.style.cssText = 'display: inline-block !important; padding: 8px 16px; border: 1px solid #cbd5e0; border-radius: 6px; background: #ffffff; cursor: pointer; font-size: 14px; font-weight: 500; color: #2d3748; transition: all 0.2s ease; visibility: visible !important;';
            
            btn.addEventListener('click', () => {
                this.setValue(shortcut.getValue());
            });
            
            container.appendChild(btn);
        });
        
        console.log('[DatePicker] Appending shortcuts container to parent:', this.input.parentNode);
        this.input.parentNode.appendChild(container);
        console.log('[DatePicker] Shortcuts created successfully');
    }
    
    formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
    
    getValue() {
        return this.input.value;
    }
    
    setValue(value) {
        this.input.value = value;
        if (this.options.onChange) {
            this.options.onChange(value);
        }
    }
}

class AssigneeSelector {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            multiple: options.multiple || false,
            placeholder: options.placeholder || 'Search users...',
            onChange: options.onChange || null
        };
        
        this.selectedUsers = [];
        this.allUsers = [];
        this.dropdown = null;
        this.isLoading = false;
        
        this.init();
    }
    
    async init() {
        this.input.placeholder = this.options.placeholder;
        this.input.autocomplete = 'off';
        
        await this.loadUsers();
        this.createDropdown();
        this.attachEventListeners();
    }
    
    async loadUsers() {
        this.isLoading = true;
        try {
            const response = await fetch('/api/tasks/workspace-users', {
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.allUsers = data.users || [];
            } else {
                console.error('[AssigneeSelector] Failed to load users');
                this.allUsers = [];
            }
        } catch (error) {
            console.error('[AssigneeSelector] Error loading users:', error);
            this.allUsers = [];
        } finally {
            this.isLoading = false;
        }
    }
    
    createDropdown() {
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'assignee-dropdown hidden';
        this.dropdown.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            max-height: 200px;
            overflow-y: auto;
            background: white;
            border: 1px solid var(--color-border, #e0e0e0);
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            margin-top: 4px;
            z-index: 1000;
        `;
        
        const container = this.input.parentElement;
        container.style.position = 'relative';
        container.appendChild(this.dropdown);
    }
    
    attachEventListeners() {
        this.input.addEventListener('focus', () => {
            this.showDropdown();
        });
        
        this.input.addEventListener('input', () => {
            this.filterUsers(this.input.value);
        });
        
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
                this.hideDropdown();
            }
        });
    }
    
    showDropdown() {
        this.filterUsers(this.input.value);
        this.dropdown.classList.remove('hidden');
    }
    
    hideDropdown() {
        this.dropdown.classList.add('hidden');
    }
    
    filterUsers(query) {
        const lowerQuery = query.toLowerCase();
        const filtered = this.allUsers.filter(user => {
            const name = (user.display_name || user.username || '').toLowerCase();
            const email = (user.email || '').toLowerCase();
            return name.includes(lowerQuery) || email.includes(lowerQuery);
        });
        
        this.renderDropdown(filtered);
    }
    
    renderDropdown(users) {
        this.dropdown.innerHTML = '';
        
        if (users.length === 0) {
            const emptyMsg = document.createElement('div');
            emptyMsg.textContent = this.isLoading ? 'Loading users...' : 'No users found';
            emptyMsg.style.cssText = 'padding: 12px; color: var(--color-text-secondary, #666); text-align: center;';
            this.dropdown.appendChild(emptyMsg);
            return;
        }
        
        users.forEach(user => {
            const item = document.createElement('div');
            item.className = 'assignee-dropdown-item';
            item.style.cssText = `
                padding: 10px 12px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 8px;
            `;
            
            item.innerHTML = `
                <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--color-primary, #4a9eff); color: white; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 14px;">
                    ${this.getInitials(user)}
                </div>
                <div>
                    <div style="font-weight: 500; color: var(--color-text-primary, #000);">
                        ${this.escapeHtml(user.display_name || user.username)}
                    </div>
                    ${user.email ? `<div style="font-size: 12px; color: var(--color-text-secondary, #666);">${this.escapeHtml(user.email)}</div>` : ''}
                </div>
            `;
            
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = 'var(--color-bg-hover, #f5f5f5)';
            });
            
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = '';
            });
            
            item.addEventListener('click', () => {
                this.selectUser(user);
            });
            
            this.dropdown.appendChild(item);
        });
    }
    
    selectUser(user) {
        if (this.options.multiple) {
            if (!this.selectedUsers.find(u => u.id === user.id)) {
                this.selectedUsers.push(user);
                this.updateMultipleDisplay();
            }
        } else {
            this.selectedUsers = [user];
            this.input.value = user.display_name || user.username;
            this.hideDropdown();
        }
        
        if (this.options.onChange) {
            this.options.onChange(this.getValue());
        }
    }
    
    updateMultipleDisplay() {
        this.input.value = this.selectedUsers.map(u => u.display_name || u.username).join(', ');
    }
    
    getInitials(user) {
        const name = user.display_name || user.username || 'U';
        const parts = name.split(' ');
        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return name.substring(0, 2).toUpperCase();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    getValue() {
        if (this.options.multiple) {
            return this.selectedUsers.map(u => u.id);
        }
        return this.selectedUsers.length > 0 ? this.selectedUsers[0].id : null;
    }
    
    setValue(userId) {
        const user = this.allUsers.find(u => u.id === userId);
        if (user) {
            this.selectUser(user);
        }
    }
}

class PrioritySelector {
    constructor(selectElement, options = {}) {
        this.select = selectElement;
        this.options = {
            onChange: options.onChange || null,
            visual: options.visual !== false
        };
        
        this.init();
    }
    
    init() {
        if (this.options.visual) {
            this.createVisualSelector();
        }
        
        this.select.addEventListener('change', () => {
            if (this.options.onChange) {
                this.options.onChange(this.getValue());
            }
            if (this.options.visual) {
                this.updateVisualState();
            }
        });
    }
    
    createVisualSelector() {
        const container = document.createElement('div');
        container.className = 'priority-visual-selector';
        container.style.cssText = 'display: flex; gap: 8px; margin-top: 8px;';
        
        const priorities = [
            { value: 'low', label: 'Low', color: '#4CAF50' },
            { value: 'medium', label: 'Medium', color: '#FFA726' },
            { value: 'high', label: 'High', color: '#EF5350' },
            { value: 'urgent', label: 'Urgent', color: '#D32F2F' }
        ];
        
        this.visualButtons = [];
        
        priorities.forEach(priority => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = priority.label;
            btn.className = 'priority-btn';
            btn.dataset.priority = priority.value;
            btn.style.cssText = `
                padding: 6px 14px;
                border: 2px solid ${priority.color};
                border-radius: 4px;
                background: white;
                color: ${priority.color};
                cursor: pointer;
                font-weight: 500;
                font-size: 13px;
                transition: all 0.2s;
            `;
            
            btn.addEventListener('click', () => {
                this.setValue(priority.value);
            });
            
            this.visualButtons.push(btn);
            container.appendChild(btn);
        });
        
        this.select.parentNode.appendChild(container);
        this.updateVisualState();
    }
    
    updateVisualState() {
        if (!this.visualButtons) return;
        
        const currentValue = this.getValue();
        
        this.visualButtons.forEach(btn => {
            const isSelected = btn.dataset.priority === currentValue;
            const color = btn.style.borderColor;
            
            if (isSelected) {
                btn.style.background = color;
                btn.style.color = 'white';
                btn.style.fontWeight = '600';
            } else {
                btn.style.background = 'white';
                btn.style.color = color;
                btn.style.fontWeight = '500';
            }
        });
    }
    
    getValue() {
        return this.select.value;
    }
    
    setValue(value) {
        this.select.value = value;
        if (this.options.onChange) {
            this.options.onChange(value);
        }
        if (this.options.visual) {
            this.updateVisualState();
        }
    }
}

class LabelSelector {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            placeholder: options.placeholder || 'Add labels...',
            onChange: options.onChange || null,
            allowCreate: options.allowCreate !== false
        };
        
        this.selectedLabels = [];
        this.allLabels = [];
        this.dropdown = null;
        
        this.init();
    }
    
    async init() {
        this.input.placeholder = this.options.placeholder;
        this.input.autocomplete = 'off';
        
        await this.loadLabels();
        this.createTagContainer();
        this.createDropdown();
        this.attachEventListeners();
    }
    
    async loadLabels() {
        this.allLabels = ['bug', 'feature', 'enhancement', 'documentation', 'urgent', 'low-priority'];
    }
    
    createTagContainer() {
        this.tagContainer = document.createElement('div');
        this.tagContainer.className = 'label-tags-container';
        this.tagContainer.style.cssText = `
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
            min-height: 32px;
        `;
        
        this.input.parentNode.appendChild(this.tagContainer);
    }
    
    createDropdown() {
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'label-dropdown hidden';
        this.dropdown.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            max-height: 150px;
            overflow-y: auto;
            background: white;
            border: 1px solid var(--color-border, #e0e0e0);
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            margin-top: 4px;
            z-index: 1000;
        `;
        
        const container = this.input.parentElement;
        container.style.position = 'relative';
        container.appendChild(this.dropdown);
    }
    
    attachEventListeners() {
        this.input.addEventListener('focus', () => {
            this.showDropdown();
        });
        
        this.input.addEventListener('input', () => {
            this.filterLabels(this.input.value);
        });
        
        this.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && this.input.value.trim()) {
                e.preventDefault();
                this.addLabel(this.input.value.trim());
                this.input.value = '';
            }
        });
        
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
                this.hideDropdown();
            }
        });
    }
    
    showDropdown() {
        this.filterLabels(this.input.value);
        this.dropdown.classList.remove('hidden');
    }
    
    hideDropdown() {
        this.dropdown.classList.add('hidden');
    }
    
    filterLabels(query) {
        const lowerQuery = query.toLowerCase();
        const filtered = this.allLabels.filter(label => 
            label.toLowerCase().includes(lowerQuery) && 
            !this.selectedLabels.includes(label)
        );
        
        this.renderDropdown(filtered, query);
    }
    
    renderDropdown(labels, query) {
        this.dropdown.innerHTML = '';
        
        if (labels.length === 0 && this.options.allowCreate && query.trim()) {
            const createItem = document.createElement('div');
            createItem.className = 'label-dropdown-item';
            createItem.style.cssText = 'padding: 10px 12px; cursor: pointer; color: var(--color-primary, #4a9eff);';
            createItem.textContent = `Create "${query}"`;
            
            createItem.addEventListener('click', () => {
                this.addLabel(query);
                this.input.value = '';
            });
            
            this.dropdown.appendChild(createItem);
            return;
        }
        
        labels.forEach(label => {
            const item = document.createElement('div');
            item.className = 'label-dropdown-item';
            item.style.cssText = 'padding: 10px 12px; cursor: pointer;';
            item.textContent = label;
            
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = 'var(--color-bg-hover, #f5f5f5)';
            });
            
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = '';
            });
            
            item.addEventListener('click', () => {
                this.addLabel(label);
                this.input.value = '';
            });
            
            this.dropdown.appendChild(item);
        });
    }
    
    addLabel(label) {
        if (!this.selectedLabels.includes(label)) {
            this.selectedLabels.push(label);
            this.renderTags();
            
            if (this.options.onChange) {
                this.options.onChange(this.getValue());
            }
        }
    }
    
    removeLabel(label) {
        this.selectedLabels = this.selectedLabels.filter(l => l !== label);
        this.renderTags();
        
        if (this.options.onChange) {
            this.options.onChange(this.getValue());
        }
    }
    
    renderTags() {
        this.tagContainer.innerHTML = '';
        
        this.selectedLabels.forEach(label => {
            const tag = document.createElement('span');
            tag.className = 'label-tag';
            tag.style.cssText = `
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 4px 10px;
                background: var(--color-bg-secondary, #f0f0f0);
                border-radius: 4px;
                font-size: 13px;
                color: var(--color-text-primary, #000);
            `;
            
            tag.innerHTML = `
                <span>${this.escapeHtml(label)}</span>
                <button type="button" style="border: none; background: none; cursor: pointer; padding: 0; color: var(--color-text-secondary, #666);">
                    <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            `;
            
            tag.querySelector('button').addEventListener('click', () => {
                this.removeLabel(label);
            });
            
            this.tagContainer.appendChild(tag);
        });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    getValue() {
        return this.selectedLabels;
    }
    
    setValue(labels) {
        this.selectedLabels = Array.isArray(labels) ? labels : [];
        this.renderTags();
    }
}

window.DatePicker = DatePicker;
window.AssigneeSelector = AssigneeSelector;
window.PrioritySelector = PrioritySelector;
window.LabelSelector = LabelSelector;
