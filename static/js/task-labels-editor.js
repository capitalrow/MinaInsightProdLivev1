/**
 * Task Labels Editor
 * Multi-select tag editor with create/select functionality
 * Fetches available labels from /api/tasks/labels endpoint
 */

class TaskLabelsEditor {
    constructor() {
        this.modal = null;
        this.resolveCallback = null;
        this.selectedLabels = [];
        this.availableLabels = [];
        this.init();
    }

    init() {
        this.createModal();
        this.setupEventListeners();
    }

    createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'task-labels-modal-overlay';
        this.modal.innerHTML = `
            <div class="task-labels-modal">
                <div class="task-labels-modal-header">
                    <h3>Edit Labels</h3>
                    <button class="task-labels-modal-close" title="Close">
                        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                    </button>
                </div>
                <div class="task-labels-modal-body">
                    <div class="task-labels-input-wrapper">
                        <input type="text" 
                               class="task-labels-input" 
                               placeholder="Type to create or search labels..." 
                               autocomplete="off">
                        <button class="task-labels-create-btn" style="display: none;">
                            <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
                            </svg>
                            Create
                        </button>
                    </div>
                    <div class="task-labels-selected" style="display: none;">
                        <div class="task-labels-selected-label">Selected:</div>
                        <div class="task-labels-selected-list"></div>
                    </div>
                    <div class="task-labels-suggestions"></div>
                    <div class="task-labels-loading" style="display: none;">
                        <div class="spinner"></div>
                        <div>Loading labels...</div>
                    </div>
                </div>
                <div class="task-labels-modal-footer">
                    <button class="btn-secondary task-labels-cancel">Cancel</button>
                    <button class="btn-primary task-labels-save">Save</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.modal);
    }

    setupEventListeners() {
        const closeBtn = this.modal.querySelector('.task-labels-modal-close');
        const cancelBtn = this.modal.querySelector('.task-labels-cancel');
        const saveBtn = this.modal.querySelector('.task-labels-save');
        const input = this.modal.querySelector('.task-labels-input');
        const createBtn = this.modal.querySelector('.task-labels-create-btn');

        closeBtn.addEventListener('click', () => this.close(null));
        cancelBtn.addEventListener('click', () => this.close(null));
        saveBtn.addEventListener('click', () => this.close(this.selectedLabels));

        input.addEventListener('input', (e) => {
            this.handleInputChange(e.target.value);
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const value = input.value.trim();
                if (value) {
                    this.addLabel(value);
                    input.value = '';
                    this.handleInputChange('');
                }
            }
        });

        createBtn.addEventListener('click', () => {
            const value = input.value.trim();
            if (value) {
                this.addLabel(value);
                input.value = '';
                this.handleInputChange('');
            }
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

    async show(currentLabels = []) {
        this.selectedLabels = [...(currentLabels || [])];
        
        const loading = this.modal.querySelector('.task-labels-loading');
        const suggestions = this.modal.querySelector('.task-labels-suggestions');

        loading.style.display = 'flex';
        suggestions.style.display = 'none';

        this.modal.classList.remove('hidden');
        this.modal.style.display = 'flex';
        requestAnimationFrame(() => {
            this.modal.classList.add('visible');
        });

        try {
            await this.loadLabels();
            this.renderSuggestions();
            this.updateSelectedDisplay();
            loading.style.display = 'none';
            suggestions.style.display = 'block';
            
            const input = this.modal.querySelector('.task-labels-input');
            input.value = '';
            input.focus();
        } catch (err) {
            loading.style.display = 'none';
            console.error('Failed to load labels:', err);
        }

        return new Promise((resolve) => {
            this.resolveCallback = resolve;
        });
    }

    async loadLabels() {
        const response = await fetch('/api/tasks/labels');
        if (!response.ok) {
            throw new Error('Failed to load labels');
        }
        const data = await response.json();
        this.availableLabels = data.labels || [];
    }

    handleInputChange(value) {
        const trimmed = value.trim();
        const createBtn = this.modal.querySelector('.task-labels-create-btn');
        
        if (trimmed && !this.availableLabels.includes(trimmed) && !this.selectedLabels.includes(trimmed)) {
            createBtn.style.display = 'flex';
        } else {
            createBtn.style.display = 'none';
        }

        this.renderSuggestions(trimmed);
    }

    renderSuggestions(filterTerm = '') {
        const suggestions = this.modal.querySelector('.task-labels-suggestions');
        const term = filterTerm.toLowerCase();
        
        const filteredLabels = this.availableLabels.filter(label => {
            if (this.selectedLabels.includes(label)) return false;
            if (!term) return true;
            return label.toLowerCase().includes(term);
        });

        if (filteredLabels.length === 0) {
            suggestions.innerHTML = '<div class="task-labels-empty">No suggestions available</div>';
            return;
        }

        suggestions.innerHTML = filteredLabels.map(label => `
            <button class="task-label-suggestion" data-label="${label}">
                <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M17.63 5.84C17.27 5.33 16.67 5 16 5L5 5.01C3.9 5.01 3 5.9 3 7v10c0 1.1.9 1.99 2 1.99L16 19c.67 0 1.27-.33 1.63-.84L22 12l-4.37-6.16z"/>
                </svg>
                <span>${label}</span>
            </button>
        `).join('');

        suggestions.querySelectorAll('.task-label-suggestion').forEach(btn => {
            btn.addEventListener('click', () => {
                this.addLabel(btn.dataset.label);
                this.modal.querySelector('.task-labels-input').value = '';
                this.handleInputChange('');
            });
        });
    }

    addLabel(label) {
        const trimmed = label.trim();
        if (!trimmed) return;
        
        if (!this.selectedLabels.includes(trimmed)) {
            this.selectedLabels.push(trimmed);
            
            if (!this.availableLabels.includes(trimmed)) {
                this.availableLabels.push(trimmed);
            }
            
            this.updateSelectedDisplay();
            this.renderSuggestions();
        }
    }

    removeLabel(label) {
        this.selectedLabels = this.selectedLabels.filter(l => l !== label);
        this.updateSelectedDisplay();
        this.renderSuggestions();
    }

    updateSelectedDisplay() {
        const selectedContainer = this.modal.querySelector('.task-labels-selected');
        const selectedList = this.modal.querySelector('.task-labels-selected-list');
        
        if (this.selectedLabels.length === 0) {
            selectedContainer.style.display = 'none';
            return;
        }

        selectedContainer.style.display = 'flex';
        
        selectedList.innerHTML = this.selectedLabels.map(label => `
            <span class="task-label-chip">
                <span>${label}</span>
                <button class="task-label-chip-remove" data-label="${label}">
                    <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                </button>
            </span>
        `).join('');

        selectedList.querySelectorAll('.task-label-chip-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeLabel(btn.dataset.label);
            });
        });
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

window.taskLabelsEditor = new TaskLabelsEditor();
