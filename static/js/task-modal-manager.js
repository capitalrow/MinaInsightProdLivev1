/**
 * TaskModalManager - Unified Modal for Create/Edit/View Task Operations
 * Uses SmartSelectors for consistent UI across all modes
 */

class TaskModalManager {
    constructor() {
        console.log('[TaskModalManager] Constructor called');
        
        this.overlay = document.getElementById('task-modal-overlay');
        this.modal = this.overlay?.querySelector('.modal');
        this.form = document.getElementById('task-create-form');
        
        this.mode = null; // 'create', 'edit', 'view'
        this.currentTaskId = null;
        this.currentTaskData = null;
        
        // CRITICAL FIX: Track successful submission to prevent "Save as draft?" dialog
        // After successful save, close() should NOT prompt for draft confirmation
        this._submitSuccess = false;
        
        this.selectors = {
            datePicker: null,
            assigneeSelector: null,
            prioritySelector: null,
            labelSelector: null
        };
        
        if (!this.overlay) {
            console.error('[TaskModalManager] Modal overlay (#task-modal-overlay) not found');
            return;
        }
        if (!this.modal) {
            console.error('[TaskModalManager] Modal (.modal) not found inside overlay');
            return;
        }
        if (!this.form) {
            console.error('[TaskModalManager] Form (#task-create-form) not found');
            return;
        }
        
        console.log('[TaskModalManager] All required DOM elements found');
        this.init();
    }
    
    init() {
        console.log('[TaskModalManager] Initializing...');
        
        this.initializeSelectors();
        this.attachEventListeners();
        
        console.log('[TaskModalManager] Ready');
        
        window.taskModalManager = this;
    }
    
    initializeSelectors() {
        const dueDateInput = document.getElementById('task-due-date');
        if (dueDateInput && window.DatePicker) {
            this.selectors.datePicker = new window.DatePicker(dueDateInput, {
                shortcuts: true,
                onChange: (value) => {
                    console.log('[TaskModal] Due date changed:', value);
                }
            });
        }
        
        const assigneeInput = document.getElementById('task-assignee');
        if (assigneeInput && window.AssigneeSelector) {
            this.selectors.assigneeSelector = new window.AssigneeSelector(assigneeInput, {
                placeholder: 'Search users...',
                onChange: (value) => {
                    console.log('[TaskModal] Assignee changed:', value);
                }
            });
        }
        
        const prioritySelect = document.getElementById('task-priority');
        if (prioritySelect && window.PrioritySelector) {
            this.selectors.prioritySelector = new window.PrioritySelector(prioritySelect, {
                visual: true,
                onChange: (value) => {
                    console.log('[TaskModal] Priority changed:', value);
                }
            });
        }
        
        console.log('[TaskModalManager] Selectors initialized:', this.selectors);
    }
    
    attachEventListeners() {
        // Wire up "New Task" button
        const newTaskBtn = document.getElementById('new-task-btn');
        if (newTaskBtn) {
            newTaskBtn.addEventListener('click', () => {
                console.log('[TaskModalManager] New Task button clicked');
                this.openCreateModal();
            });
        } else {
            console.warn('[TaskModalManager] New Task button (#new-task-btn) not found');
        }
        
        const closeBtn = document.getElementById('task-modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.close());
        }
        
        const cancelBtn = document.getElementById('task-form-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.close());
        }
        
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.close();
            }
        });
        
        this.form.addEventListener('submit', (e) => {
            console.log('[TaskModalManager] 🔥 FORM SUBMIT EVENT TRIGGERED!');
            e.preventDefault();
            console.log('[TaskModalManager] Default prevented, calling handleSubmit...');
            this.handleSubmit();
        });
        
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.overlay.classList.contains('hidden')) {
                this.close();
            }
        });
    }
    
    openCreateModal(prefillData = {}) {
        console.log('[TaskModalManager] Opening in CREATE mode', prefillData);
        
        this.mode = 'create';
        this.currentTaskId = null;
        this.currentTaskData = null;
        
        this.updateTitle('Create New Task');
        this.updateSubmitButton('Create Task');
        
        this.form.reset();
        
        if (prefillData.title) {
            document.getElementById('task-title').value = prefillData.title;
        }
        if (prefillData.description) {
            document.getElementById('task-description').value = prefillData.description;
        }
        if (prefillData.priority) {
            this.selectors.prioritySelector?.setValue(prefillData.priority);
        }
        if (prefillData.due_date) {
            this.selectors.datePicker?.setValue(prefillData.due_date);
        }
        if (prefillData.assigned_to_id) {
            this.selectors.assigneeSelector?.setValue(prefillData.assigned_to_id);
        }
        
        this.loadDraft();
        
        this.show();
        
        setTimeout(() => {
            document.getElementById('task-title')?.focus();
        }, 100);
    }
    
    openEditModal(taskId, taskData) {
        console.log('[TaskModalManager] Opening in EDIT mode', taskId, taskData);
        
        this.mode = 'edit';
        this.currentTaskId = taskId;
        this.currentTaskData = taskData;
        
        this.updateTitle('Edit Task');
        this.updateSubmitButton('Save Changes');
        
        document.getElementById('task-title').value = taskData.title || '';
        document.getElementById('task-description').value = taskData.description || '';
        
        if (taskData.priority) {
            this.selectors.prioritySelector?.setValue(taskData.priority);
        }
        
        if (taskData.due_date) {
            this.selectors.datePicker?.setValue(taskData.due_date);
        }
        
        if (taskData.assigned_to_id) {
            this.selectors.assigneeSelector?.setValue(taskData.assigned_to_id);
        }
        
        this.show();
        
        setTimeout(() => {
            document.getElementById('task-title')?.focus();
        }, 100);
    }
    
    openViewModal(taskId, taskData) {
        console.log('[TaskModalManager] Opening in VIEW mode', taskId, taskData);
        
        this.mode = 'view';
        this.currentTaskId = taskId;
        this.currentTaskData = taskData;
        
        this.updateTitle('Task Details');
        this.updateSubmitButton('Close');
        
        document.getElementById('task-title').value = taskData.title || '';
        document.getElementById('task-title').disabled = true;
        
        document.getElementById('task-description').value = taskData.description || '';
        document.getElementById('task-description').disabled = true;
        
        document.getElementById('task-priority').disabled = true;
        document.getElementById('task-due-date').disabled = true;
        document.getElementById('task-assignee').disabled = true;
        
        this.show();
    }
    
    updateTitle(title) {
        const titleEl = this.modal.querySelector('.modal-title');
        if (titleEl) {
            titleEl.textContent = title;
        }
    }
    
    updateSubmitButton(text) {
        const submitBtn = document.getElementById('task-form-submit');
        if (submitBtn) {
            const textNode = submitBtn.childNodes[submitBtn.childNodes.length - 1];
            if (textNode && textNode.nodeType === Node.TEXT_NODE) {
                textNode.textContent = text;
            }
        }
    }
    
    show() {
        this.overlay.classList.remove('hidden');
        requestAnimationFrame(() => {
            this.overlay.style.opacity = '1';
            this.modal.style.transform = 'scale(1)';
        });
    }
    
    close() {
        // CRITICAL FIX: Skip draft prompt if we just successfully saved
        // This prevents the "Save as draft?" dialog from appearing after successful task creation
        if (this._submitSuccess) {
            console.log('[TaskModalManager] Closing after successful submit, skipping draft prompt');
            this._submitSuccess = false; // Reset flag
        } else if (this.mode === 'create' && this.hasUnsavedChanges()) {
            const shouldSave = confirm('Save as draft?');
            if (shouldSave) {
                this.saveDraft();
            } else {
                this.clearDraft();
            }
        }
        
        this.overlay.style.opacity = '0';
        this.modal.style.transform = 'scale(0.95)';
        
        setTimeout(() => {
            this.overlay.classList.add('hidden');
            this.resetForm();
        }, 200);
    }
    
    resetForm() {
        this.form.reset();
        
        document.getElementById('task-title').disabled = false;
        document.getElementById('task-description').disabled = false;
        document.getElementById('task-priority').disabled = false;
        document.getElementById('task-due-date').disabled = false;
        document.getElementById('task-assignee').disabled = false;
        
        this.mode = null;
        this.currentTaskId = null;
        this.currentTaskData = null;
    }
    
    hasUnsavedChanges() {
        const titleValue = document.getElementById('task-title').value.trim();
        const descValue = document.getElementById('task-description').value.trim();
        
        return titleValue.length > 0 || descValue.length > 0;
    }
    
    saveDraft() {
        const draft = this.getFormData();
        localStorage.setItem('task-draft', JSON.stringify(draft));
        console.log('[TaskModal] Draft saved');
    }
    
    loadDraft() {
        const draftJson = localStorage.getItem('task-draft');
        if (draftJson) {
            try {
                const draft = JSON.parse(draftJson);
                console.log('[TaskModal] Loading draft:', draft);
                
                if (draft.title) {
                    document.getElementById('task-title').value = draft.title;
                }
                if (draft.description) {
                    document.getElementById('task-description').value = draft.description;
                }
                if (draft.priority) {
                    this.selectors.prioritySelector?.setValue(draft.priority);
                }
                if (draft.due_date) {
                    this.selectors.datePicker?.setValue(draft.due_date);
                }
                
            } catch (e) {
                console.error('[TaskModal] Failed to load draft:', e);
            }
        }
    }
    
    clearDraft() {
        localStorage.removeItem('task-draft');
        console.log('[TaskModal] Draft cleared');
    }
    
    getFormData() {
        return {
            title: document.getElementById('task-title').value.trim(),
            description: document.getElementById('task-description').value.trim(),
            priority: this.selectors.prioritySelector?.getValue() || 'medium',
            due_date: this.selectors.datePicker?.getValue() || null,
            assigned_to_id: this.selectors.assigneeSelector?.getValue() || null
        };
    }
    
    async handleSubmit() {
        if (this.mode === 'view') {
            this.close();
            return;
        }
        
        const formData = this.getFormData();
        
        if (!formData.title) {
            alert('Please enter a task title');
            document.getElementById('task-title').focus();
            return;
        }
        
        console.log('[TaskModal] Submitting form:', this.mode, formData);
        
        const submitBtn = document.getElementById('task-form-submit');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';
        
        try {
            if (this.mode === 'create') {
                await this.createTask(formData);
            } else if (this.mode === 'edit') {
                await this.updateTask(this.currentTaskId, formData);
            }
            
            this.clearDraft();
            
            // CRITICAL FIX: Mark submit as successful BEFORE calling close()
            // This prevents the "Save as draft?" prompt from appearing
            this._submitSuccess = true;
            
            this.close();
            
            if (window.toastManager) {
                window.toastManager.show(
                    this.mode === 'create' ? 'Task created successfully' : 'Task updated successfully',
                    'success',
                    3000
                );
            }
            
        } catch (error) {
            console.error('[TaskModal] Submit error:', error);
            
            if (window.toastManager) {
                window.toastManager.show('Failed to save task. Please try again.', 'error', 5000);
            } else {
                alert('Failed to save task. Please try again.');
            }
            
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    }
    
    async createTask(formData) {
        console.log('[TaskModal] Creating task via optimisticUI...');
        
        if (!window.optimisticUI) {
            throw new Error('optimisticUI not available');
        }
        
        const taskData = {
            title: formData.title,
            description: formData.description,
            priority: formData.priority,
            status: 'todo',
            due_date: formData.due_date,
            assigned_to_id: formData.assigned_to_id,
            meeting_id: window.CURRENT_MEETING_ID || null
        };
        
        await window.optimisticUI.createTask(taskData);
    }
    
    async updateTask(taskId, formData) {
        console.log('[TaskModal] Updating task via optimisticUI...', taskId);
        
        if (!window.optimisticUI) {
            throw new Error('optimisticUI not available');
        }
        
        const updates = {
            title: formData.title,
            description: formData.description,
            priority: formData.priority,
            due_date: formData.due_date,
            assigned_to_id: formData.assigned_to_id
        };
        
        await window.optimisticUI.updateTask(taskId, updates);
    }
}

// Note: TaskModalManager is now manually instantiated in task-page-master-init.js
// This ensures proper initialization order after SmartSelectors are loaded
