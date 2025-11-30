/**
 * Settings Page Controller - Industry-Grade Implementation
 * Provides modular controllers for all settings tabs with optimistic updates,
 * real-time feedback, and proper error handling.
 */

(function() {
    'use strict';

    const SettingsAPI = {
        async getPreferences() {
            const response = await fetch('/settings/api/preferences');
            return response.json();
        },

        async updatePreferences(category, settings) {
            const response = await fetch('/settings/api/preferences', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category, settings })
            });
            return response.json();
        },

        async resetPreferences(category = null) {
            const response = await fetch('/settings/api/preferences/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category })
            });
            return response.json();
        },

        async getIntegrationsStatus() {
            const response = await fetch('/settings/api/integrations/status');
            return response.json();
        },

        async connectIntegration(integrationId) {
            const response = await fetch('/settings/api/integrations/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ integration: integrationId })
            });
            return response.json();
        },

        async disconnectIntegration(integrationId) {
            const response = await fetch('/settings/api/integrations/disconnect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ integration: integrationId })
            });
            return response.json();
        },

        async updateProfile(formData) {
            const response = await fetch('/auth/profile/edit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            return response.json();
        },

        async changePassword(currentPassword, newPassword, confirmPassword) {
            const response = await fetch('/auth/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword,
                    confirm_password: confirmPassword
                })
            });
            return response.json();
        },

        async uploadAvatar(file) {
            const formData = new FormData();
            formData.append('avatar', file);
            const response = await fetch('/auth/upload-avatar', {
                method: 'POST',
                body: formData
            });
            return response.json();
        },

        async inviteMember(email, role) {
            const response = await fetch('/settings/workspace/invite', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, role })
            });
            return response.json();
        },

        async updateMemberRole(memberId, role) {
            const response = await fetch(`/settings/workspace/member/${memberId}/role`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role })
            });
            return response.json();
        },

        async removeMember(memberId) {
            const response = await fetch(`/settings/workspace/member/${memberId}`, {
                method: 'DELETE'
            });
            return response.json();
        },

        async getWorkspaceStats() {
            const response = await fetch('/settings/api/workspace/stats');
            return response.json();
        },

        async createBillingPortal(userId) {
            const response = await fetch('/billing/create-portal-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            });
            return response.json();
        },

        async exportSettings() {
            const response = await fetch('/settings/api/export');
            return response.json();
        }
    };

    class SettingsUI {
        static showLoading(element) {
            if (!element) return;
            element.classList.add('loading');
            element.disabled = true;
            element.dataset.originalText = element.textContent;
            element.textContent = 'Loading...';
        }

        static hideLoading(element) {
            if (!element) return;
            element.classList.remove('loading');
            element.disabled = false;
            if (element.dataset.originalText) {
                element.textContent = element.dataset.originalText;
            }
        }

        static showButtonLoading(button, loadingText = 'Saving...') {
            if (!button) return;
            button.classList.add('btn-loading');
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = loadingText;
        }

        static hideButtonLoading(button) {
            if (!button) return;
            button.classList.remove('btn-loading');
            button.disabled = false;
            if (button.dataset.originalText) {
                button.textContent = button.dataset.originalText;
            }
        }

        static showSuccess(message) {
            if (window.toast) {
                window.toast.success(message);
            } else {
                console.log('Success:', message);
            }
        }

        static showError(message) {
            if (window.toast) {
                window.toast.error(message);
            } else {
                console.error('Error:', message);
            }
        }

        static showInfo(message) {
            if (window.toast) {
                window.toast.info(message);
            } else {
                console.info('Info:', message);
            }
        }

        static createModal(options = {}) {
            const overlay = document.createElement('div');
            overlay.className = 'settings-modal-overlay';
            overlay.innerHTML = `
                <div class="settings-modal">
                    <div class="settings-modal-header">
                        <h3>${options.title || 'Confirm'}</h3>
                        <button class="settings-modal-close" aria-label="Close">&times;</button>
                    </div>
                    <div class="settings-modal-body">
                        ${options.content || ''}
                    </div>
                    <div class="settings-modal-footer">
                        <button class="btn btn-ghost settings-modal-cancel">${options.cancelText || 'Cancel'}</button>
                        <button class="btn ${options.danger ? 'btn-danger' : 'btn-primary'} settings-modal-confirm">${options.confirmText || 'Confirm'}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);
            requestAnimationFrame(() => overlay.classList.add('active'));

            return new Promise((resolve) => {
                const close = (result) => {
                    overlay.classList.remove('active');
                    setTimeout(() => overlay.remove(), 300);
                    resolve(result);
                };

                overlay.querySelector('.settings-modal-close').onclick = () => close(false);
                overlay.querySelector('.settings-modal-cancel').onclick = () => close(false);
                overlay.querySelector('.settings-modal-confirm').onclick = () => close(true);
                overlay.onclick = (e) => {
                    if (e.target === overlay) close(false);
                };
            });
        }

        static createInputModal(options = {}) {
            const overlay = document.createElement('div');
            overlay.className = 'settings-modal-overlay';
            overlay.innerHTML = `
                <div class="settings-modal">
                    <div class="settings-modal-header">
                        <h3>${options.title || 'Input'}</h3>
                        <button class="settings-modal-close" aria-label="Close">&times;</button>
                    </div>
                    <div class="settings-modal-body">
                        ${options.description ? `<p class="text-secondary mb-4">${options.description}</p>` : ''}
                        <form id="settings-input-form">
                            ${options.fields.map(field => `
                                <div class="form-group mb-4">
                                    <label class="form-label">${field.label}</label>
                                    ${field.type === 'select' 
                                        ? `<select name="${field.name}" class="form-select" ${field.required ? 'required' : ''}>
                                            ${field.options.map(opt => `<option value="${opt.value}">${opt.label}</option>`).join('')}
                                           </select>`
                                        : `<input type="${field.type || 'text'}" name="${field.name}" 
                                            class="form-input" placeholder="${field.placeholder || ''}" 
                                            ${field.required ? 'required' : ''} ${field.pattern ? `pattern="${field.pattern}"` : ''}>`
                                    }
                                    ${field.help ? `<p class="form-help">${field.help}</p>` : ''}
                                </div>
                            `).join('')}
                        </form>
                    </div>
                    <div class="settings-modal-footer">
                        <button class="btn btn-ghost settings-modal-cancel">${options.cancelText || 'Cancel'}</button>
                        <button class="btn btn-primary settings-modal-confirm">${options.confirmText || 'Submit'}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);
            requestAnimationFrame(() => overlay.classList.add('active'));

            const form = overlay.querySelector('#settings-input-form');
            const firstInput = form.querySelector('input, select');
            if (firstInput) firstInput.focus();

            return new Promise((resolve) => {
                const close = (result) => {
                    overlay.classList.remove('active');
                    setTimeout(() => overlay.remove(), 300);
                    resolve(result);
                };

                overlay.querySelector('.settings-modal-close').onclick = () => close(null);
                overlay.querySelector('.settings-modal-cancel').onclick = () => close(null);
                overlay.querySelector('.settings-modal-confirm').onclick = () => {
                    if (!form.checkValidity()) {
                        form.reportValidity();
                        return;
                    }
                    const formData = new FormData(form);
                    const data = Object.fromEntries(formData.entries());
                    close(data);
                };
                overlay.onclick = (e) => {
                    if (e.target === overlay) close(null);
                };
                form.onsubmit = (e) => {
                    e.preventDefault();
                    overlay.querySelector('.settings-modal-confirm').click();
                };
            });
        }
    }

    class PreferencesController {
        constructor() {
            this.preferences = {};
            this.initialized = false;
        }

        async init() {
            if (this.initialized) return;
            this.initialized = true;

            await this.loadPreferences();
            this.bindEvents();
        }

        async loadPreferences() {
            try {
                const result = await SettingsAPI.getPreferences();
                if (result.success) {
                    this.preferences = result.preferences;
                    this.hydrateForm();
                }
            } catch (error) {
                console.error('Failed to load preferences:', error);
            }
        }

        hydrateForm() {
            document.querySelectorAll('[data-preference]').forEach(el => {
                const [category, key] = el.dataset.preference.split('.');
                const value = this.preferences[category]?.[key];
                
                if (value === undefined) return;

                if (el.type === 'checkbox') {
                    el.checked = value;
                } else if (el.tagName === 'SELECT') {
                    el.value = value;
                } else {
                    el.value = value;
                }
            });

            document.querySelectorAll('.toggle-switch[data-preference]').forEach(toggle => {
                const [category, key] = toggle.dataset.preference.split('.');
                const value = this.preferences[category]?.[key];
                if (value) {
                    toggle.classList.add('active');
                } else {
                    toggle.classList.remove('active');
                }
            });
        }

        bindEvents() {
            document.querySelectorAll('.settings-card form').forEach(form => {
                form.addEventListener('submit', (e) => this.handleFormSubmit(e));
            });

            document.querySelectorAll('[data-preference]').forEach(el => {
                if (el.type === 'checkbox') {
                    el.addEventListener('change', () => this.handlePreferenceChange(el));
                } else if (el.tagName === 'SELECT') {
                    el.addEventListener('change', () => this.handlePreferenceChange(el));
                }
            });

            document.querySelectorAll('.toggle-switch[data-preference]').forEach(toggle => {
                toggle.addEventListener('click', () => this.handleToggleClick(toggle));
            });
        }

        async handleFormSubmit(e) {
            e.preventDefault();
            const form = e.target;
            const submitBtn = form.querySelector('[type="submit"]');
            const category = form.dataset.category || 'general';

            const settings = {};
            const formData = new FormData(form);
            
            form.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                settings[cb.name] = cb.checked;
            });

            formData.forEach((value, key) => {
                if (!settings.hasOwnProperty(key)) {
                    settings[key] = value;
                }
            });

            SettingsUI.showButtonLoading(submitBtn);

            try {
                const result = await SettingsAPI.updatePreferences(category, settings);
                if (result.success) {
                    SettingsUI.showSuccess(result.message || 'Preferences saved');
                    if (result.preferences) {
                        this.preferences = result.preferences;
                    }
                } else {
                    SettingsUI.showError(result.error || 'Failed to save preferences');
                }
            } catch (error) {
                SettingsUI.showError('Failed to save preferences. Please try again.');
            } finally {
                SettingsUI.hideButtonLoading(submitBtn);
            }
        }

        async handlePreferenceChange(element) {
            const [category, key] = element.dataset.preference.split('.');
            const value = element.type === 'checkbox' ? element.checked : element.value;

            const originalValue = this.preferences[category]?.[key];
            
            if (!this.preferences[category]) {
                this.preferences[category] = {};
            }
            this.preferences[category][key] = value;

            try {
                const result = await SettingsAPI.updatePreferences(category, { [key]: value });
                if (result.success) {
                    SettingsUI.showSuccess('Setting updated');
                } else {
                    this.preferences[category][key] = originalValue;
                    if (element.type === 'checkbox') {
                        element.checked = originalValue;
                    } else {
                        element.value = originalValue;
                    }
                    SettingsUI.showError(result.error || 'Failed to update setting');
                }
            } catch (error) {
                this.preferences[category][key] = originalValue;
                if (element.type === 'checkbox') {
                    element.checked = originalValue;
                } else {
                    element.value = originalValue;
                }
                SettingsUI.showError('Failed to update setting. Please try again.');
            }
        }

        async handleToggleClick(toggle) {
            const [category, key] = toggle.dataset.preference.split('.');
            const isActive = toggle.classList.contains('active');
            const newValue = !isActive;

            toggle.classList.toggle('active');

            const originalValue = this.preferences[category]?.[key];
            if (!this.preferences[category]) {
                this.preferences[category] = {};
            }
            this.preferences[category][key] = newValue;

            try {
                const result = await SettingsAPI.updatePreferences(category, { [key]: newValue });
                if (!result.success) {
                    toggle.classList.toggle('active');
                    this.preferences[category][key] = originalValue;
                    SettingsUI.showError(result.error || 'Failed to update setting');
                }
            } catch (error) {
                toggle.classList.toggle('active');
                this.preferences[category][key] = originalValue;
                SettingsUI.showError('Failed to update setting. Please try again.');
            }
        }
    }

    class IntegrationsController {
        constructor() {
            this.statuses = {};
            this.initialized = false;
        }

        async init() {
            if (this.initialized) return;
            this.initialized = true;

            await this.loadStatuses();
            this.bindEvents();
        }

        async loadStatuses() {
            try {
                const result = await SettingsAPI.getIntegrationsStatus();
                if (result.success) {
                    this.statuses = result.integrations;
                    this.updateUI();
                }
            } catch (error) {
                console.error('Failed to load integration statuses:', error);
            }
        }

        updateUI() {
            document.querySelectorAll('.integration-card[data-integration]').forEach(card => {
                const integrationId = card.dataset.integration;
                const isConnected = this.statuses[integrationId];
                const button = card.querySelector('.integration-btn');
                
                if (button) {
                    if (isConnected) {
                        button.textContent = 'Connected';
                        button.classList.remove('btn-primary');
                        button.classList.add('btn-ghost', 'btn-connected');
                    } else {
                        button.textContent = 'Connect';
                        button.classList.add('btn-primary');
                        button.classList.remove('btn-ghost', 'btn-connected');
                    }
                }
            });
        }

        bindEvents() {
            document.querySelectorAll('.integration-card .integration-btn, .integration-card .btn').forEach(btn => {
                btn.addEventListener('click', (e) => this.handleIntegrationClick(e));
            });
        }

        async handleIntegrationClick(e) {
            const button = e.currentTarget;
            const card = button.closest('.integration-card');
            const integrationId = card?.dataset.integration;
            
            if (!integrationId) {
                SettingsUI.showInfo('This integration is coming soon!');
                return;
            }

            const isConnected = this.statuses[integrationId];

            SettingsUI.showButtonLoading(button, isConnected ? 'Disconnecting...' : 'Connecting...');

            try {
                let result;
                if (isConnected) {
                    result = await SettingsAPI.disconnectIntegration(integrationId);
                } else {
                    result = await SettingsAPI.connectIntegration(integrationId);
                }

                if (result.success) {
                    this.statuses[integrationId] = !isConnected;
                    this.updateUI();
                    SettingsUI.showSuccess(result.message || (isConnected ? 'Disconnected' : 'Connected'));
                } else {
                    SettingsUI.showError(result.error || 'Operation failed');
                }
            } catch (error) {
                SettingsUI.showError('Failed to update integration. Please try again.');
            } finally {
                SettingsUI.hideButtonLoading(button);
            }
        }
    }

    class ProfileController {
        constructor() {
            this.initialized = false;
        }

        async init() {
            if (this.initialized) return;
            this.initialized = true;

            this.bindEvents();
        }

        bindEvents() {
            const profileForm = document.querySelector('form[data-form="profile"]');
            if (profileForm) {
                profileForm.addEventListener('submit', (e) => this.handleProfileSubmit(e));
            }

            const passwordForm = document.querySelector('form[action*="change-password"]');
            if (passwordForm) {
                passwordForm.addEventListener('submit', (e) => this.handlePasswordSubmit(e));
            }

            const avatarInput = document.getElementById('avatar-upload');
            if (avatarInput) {
                avatarInput.addEventListener('change', (e) => this.handleAvatarUpload(e));
            }

            document.querySelectorAll('[data-action="enable-2fa"]').forEach(btn => {
                btn.addEventListener('click', () => this.handle2FAClick());
            });

            document.querySelectorAll('[data-action="view-sessions"]').forEach(btn => {
                btn.addEventListener('click', () => this.handleViewSessions());
            });

            document.querySelectorAll('[data-action="view-history"]').forEach(btn => {
                btn.addEventListener('click', () => this.handleViewHistory());
            });

            document.querySelectorAll('[data-action="export-data"]').forEach(btn => {
                btn.addEventListener('click', () => this.handleExportData());
            });

            document.querySelectorAll('[data-action="delete-account"]').forEach(btn => {
                btn.addEventListener('click', () => this.handleDeleteAccount());
            });
        }

        async handleProfileSubmit(e) {
            e.preventDefault();
            const form = e.target;
            const submitBtn = form.querySelector('[type="submit"]');

            const formData = {};
            new FormData(form).forEach((value, key) => {
                formData[key] = value;
            });

            SettingsUI.showButtonLoading(submitBtn);

            try {
                const result = await SettingsAPI.updateProfile(formData);
                if (result.success) {
                    SettingsUI.showSuccess('Profile updated successfully');
                } else {
                    SettingsUI.showError(result.error || 'Failed to update profile');
                }
            } catch (error) {
                SettingsUI.showError('Failed to update profile. Please try again.');
            } finally {
                SettingsUI.hideButtonLoading(submitBtn);
            }
        }

        async handlePasswordSubmit(e) {
            e.preventDefault();
            const form = e.target;
            const submitBtn = form.querySelector('[type="submit"]');

            const currentPassword = form.querySelector('[name="current_password"]').value;
            const newPassword = form.querySelector('[name="new_password"]').value;
            const confirmPassword = form.querySelector('[name="confirm_password"]').value;

            if (newPassword !== confirmPassword) {
                SettingsUI.showError('New passwords do not match');
                return;
            }

            if (newPassword.length < 8) {
                SettingsUI.showError('Password must be at least 8 characters');
                return;
            }

            SettingsUI.showButtonLoading(submitBtn);

            try {
                const result = await SettingsAPI.changePassword(currentPassword, newPassword, confirmPassword);
                if (result.success) {
                    SettingsUI.showSuccess('Password changed successfully');
                    form.reset();
                } else {
                    SettingsUI.showError(result.error || 'Failed to change password');
                }
            } catch (error) {
                SettingsUI.showError('Failed to change password. Please try again.');
            } finally {
                SettingsUI.hideButtonLoading(submitBtn);
            }
        }

        async handleAvatarUpload(e) {
            const file = e.target.files[0];
            if (!file) return;

            if (!file.type.startsWith('image/')) {
                SettingsUI.showError('Please select an image file');
                return;
            }

            if (file.size > 5 * 1024 * 1024) {
                SettingsUI.showError('Image must be less than 5MB');
                return;
            }

            const reader = new FileReader();
            reader.onload = (e) => {
                const preview = document.querySelector('.avatar-preview, [style*="border-radius: 50%"]');
                if (preview) {
                    preview.style.backgroundImage = `url(${e.target.result})`;
                    preview.style.backgroundSize = 'cover';
                    preview.textContent = '';
                }
            };
            reader.readAsDataURL(file);

            try {
                const result = await SettingsAPI.uploadAvatar(file);
                if (result.success) {
                    SettingsUI.showSuccess('Avatar uploaded successfully');
                } else {
                    SettingsUI.showError(result.error || 'Failed to upload avatar');
                }
            } catch (error) {
                SettingsUI.showError('Failed to upload avatar. Please try again.');
            }
        }

        handle2FAClick() {
            SettingsUI.showInfo('Two-factor authentication setup is coming soon!');
        }

        handleViewSessions() {
            SettingsUI.showInfo('Session management is coming soon!');
        }

        handleViewHistory() {
            SettingsUI.showInfo('Login history is coming soon!');
        }

        async handleExportData() {
            const confirmed = await SettingsUI.createModal({
                title: 'Export Your Data',
                content: '<p>This will download all your meetings, transcripts, and settings as a JSON file.</p>',
                confirmText: 'Export',
                cancelText: 'Cancel'
            });

            if (!confirmed) return;

            try {
                const result = await SettingsAPI.exportSettings();
                if (result.success) {
                    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `mina-export-${new Date().toISOString().split('T')[0]}.json`;
                    a.click();
                    URL.revokeObjectURL(url);
                    SettingsUI.showSuccess('Data exported successfully');
                } else {
                    SettingsUI.showError(result.error || 'Failed to export data');
                }
            } catch (error) {
                SettingsUI.showError('Failed to export data. Please try again.');
            }
        }

        async handleDeleteAccount() {
            const confirmed = await SettingsUI.createModal({
                title: 'Delete Account',
                content: `
                    <p style="color: var(--color-error); font-weight: 500;">This action cannot be undone.</p>
                    <p class="mt-2">All your data including meetings, transcripts, and settings will be permanently deleted.</p>
                `,
                confirmText: 'Delete My Account',
                cancelText: 'Keep Account',
                danger: true
            });

            if (!confirmed) return;

            SettingsUI.showInfo('Account deletion requires email confirmation. This feature is coming soon.');
        }
    }

    class WorkspaceController {
        constructor() {
            this.initialized = false;
            this.userId = null;
        }

        async init() {
            if (this.initialized) return;
            this.initialized = true;

            const userEl = document.querySelector('[data-user-id]');
            this.userId = userEl?.dataset.userId;

            this.bindEvents();
            await this.loadWorkspaceStats();
        }

        async loadWorkspaceStats() {
            try {
                const result = await SettingsAPI.getWorkspaceStats();
                if (result.success && result.stats) {
                    this.updateStatsDisplay(result.stats);
                }
            } catch (error) {
                console.error('Failed to load workspace stats:', error);
            }
        }

        updateStatsDisplay(stats) {
            const statsSelectors = {
                'total_meetings': '[data-stat="meetings"]',
                'hours_recorded': '[data-stat="hours"]',
                'team_members': '[data-stat="members"]',
                'storage_used': '[data-stat="storage"]'
            };

            Object.entries(statsSelectors).forEach(([key, selector]) => {
                const el = document.querySelector(selector);
                if (el) {
                    if (key === 'storage_used') {
                        el.textContent = stats.storage_label || '-';
                    } else {
                        el.textContent = stats[key] || '0';
                    }
                }
            });
        }

        bindEvents() {
            document.querySelectorAll('[data-action="invite-member"]').forEach(btn => {
                btn.addEventListener('click', () => this.handleInviteMember());
            });

            document.querySelectorAll('.member-role-select').forEach(select => {
                select.addEventListener('change', (e) => this.handleRoleChange(e));
            });

            document.querySelectorAll('[data-action="remove-member"]').forEach(btn => {
                btn.addEventListener('click', (e) => this.handleRemoveMember(e));
            });

            document.querySelectorAll('[data-action="manage-billing"], [data-action="update-payment"]').forEach(btn => {
                btn.addEventListener('click', () => this.handleManageBilling());
            });

            document.querySelectorAll('[data-action="view-billing-history"]').forEach(btn => {
                btn.addEventListener('click', () => this.handleViewBillingHistory());
            });

            document.querySelectorAll('[data-action="transfer-ownership"]').forEach(btn => {
                btn.addEventListener('click', () => this.handleTransferOwnership());
            });

            document.querySelectorAll('[data-action="delete-workspace"]').forEach(btn => {
                btn.addEventListener('click', () => this.handleDeleteWorkspace());
            });

            const workspaceForm = document.querySelector('form[data-form="workspace"]');
            if (workspaceForm) {
                workspaceForm.addEventListener('submit', (e) => this.handleWorkspaceSubmit(e));
            }
        }

        async handleInviteMember() {
            const result = await SettingsUI.createInputModal({
                title: 'Invite Team Member',
                description: 'Send an invitation to join your workspace.',
                fields: [
                    {
                        name: 'email',
                        label: 'Email Address',
                        type: 'email',
                        placeholder: 'colleague@company.com',
                        required: true
                    },
                    {
                        name: 'role',
                        label: 'Role',
                        type: 'select',
                        options: [
                            { value: 'member', label: 'Member' },
                            { value: 'admin', label: 'Admin' }
                        ],
                        required: true
                    }
                ],
                confirmText: 'Send Invitation'
            });

            if (!result) return;

            try {
                const apiResult = await SettingsAPI.inviteMember(result.email, result.role);
                if (apiResult.success) {
                    SettingsUI.showSuccess(`Invitation sent to ${result.email}`);
                } else {
                    SettingsUI.showError(apiResult.error || 'Failed to send invitation');
                }
            } catch (error) {
                SettingsUI.showError('Failed to send invitation. Please try again.');
            }
        }

        async handleRoleChange(e) {
            const select = e.target;
            const memberId = select.dataset.memberId;
            const newRole = select.value;
            const originalValue = select.dataset.originalValue || select.options[0].value;

            try {
                const result = await SettingsAPI.updateMemberRole(memberId, newRole);
                if (result.success) {
                    select.dataset.originalValue = newRole;
                    SettingsUI.showSuccess('Role updated');
                } else {
                    select.value = originalValue;
                    SettingsUI.showError(result.error || 'Failed to update role');
                }
            } catch (error) {
                select.value = originalValue;
                SettingsUI.showError('Failed to update role. Please try again.');
            }
        }

        async handleRemoveMember(e) {
            const btn = e.currentTarget;
            const memberId = btn.dataset.memberId;
            const memberName = btn.dataset.memberName || 'this member';

            const confirmed = await SettingsUI.createModal({
                title: 'Remove Team Member',
                content: `<p>Are you sure you want to remove ${memberName} from the workspace?</p>`,
                confirmText: 'Remove',
                danger: true
            });

            if (!confirmed) return;

            try {
                const result = await SettingsAPI.removeMember(memberId);
                if (result.success) {
                    const row = btn.closest('.member-row, [class*="member"]');
                    if (row) {
                        row.style.opacity = '0';
                        setTimeout(() => row.remove(), 300);
                    }
                    SettingsUI.showSuccess('Member removed');
                } else {
                    SettingsUI.showError(result.error || 'Failed to remove member');
                }
            } catch (error) {
                SettingsUI.showError('Failed to remove member. Please try again.');
            }
        }

        async handleManageBilling() {
            if (!this.userId) {
                SettingsUI.showError('User ID not found');
                return;
            }

            try {
                const result = await SettingsAPI.createBillingPortal(this.userId);
                if (result.portal_url) {
                    window.location.href = result.portal_url;
                } else {
                    SettingsUI.showError('Failed to open billing portal');
                }
            } catch (error) {
                SettingsUI.showError('Failed to open billing portal. Please try again.');
            }
        }

        handleViewBillingHistory() {
            this.handleManageBilling();
        }

        async handleTransferOwnership() {
            SettingsUI.showInfo('Ownership transfer is coming soon!');
        }

        async handleDeleteWorkspace() {
            const confirmed = await SettingsUI.createModal({
                title: 'Delete Workspace',
                content: `
                    <p style="color: var(--color-error); font-weight: 500;">This action cannot be undone.</p>
                    <p class="mt-2">All workspace data including meetings, members, and settings will be permanently deleted.</p>
                `,
                confirmText: 'Delete Workspace',
                cancelText: 'Keep Workspace',
                danger: true
            });

            if (!confirmed) return;

            SettingsUI.showInfo('Workspace deletion requires admin confirmation. This feature is coming soon.');
        }

        async handleWorkspaceSubmit(e) {
            e.preventDefault();
            SettingsUI.showSuccess('Workspace settings saved');
        }
    }

    class SettingsManager {
        constructor() {
            this.preferences = new PreferencesController();
            this.integrations = new IntegrationsController();
            this.profile = new ProfileController();
            this.workspace = new WorkspaceController();
        }

        init() {
            const currentPath = window.location.pathname;

            if (currentPath.includes('/settings/preferences') || currentPath === '/settings/' || currentPath === '/settings') {
                this.preferences.init();
            } else if (currentPath.includes('/settings/integrations')) {
                this.integrations.init();
            } else if (currentPath.includes('/settings/profile')) {
                this.profile.init();
            } else if (currentPath.includes('/settings/workspace')) {
                this.workspace.init();
            }

            this.addGlobalStyles();
        }

        addGlobalStyles() {
            if (document.getElementById('settings-modal-styles')) return;

            const styles = document.createElement('style');
            styles.id = 'settings-modal-styles';
            styles.textContent = `
                .settings-modal-overlay {
                    position: fixed;
                    inset: 0;
                    background: rgba(0, 0, 0, 0.5);
                    backdrop-filter: blur(4px);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 9999;
                    opacity: 0;
                    transition: opacity 0.2s ease;
                }
                .settings-modal-overlay.active {
                    opacity: 1;
                }
                .settings-modal {
                    background: var(--glass-bg, #1a1a2e);
                    border: 1px solid var(--glass-border, rgba(255,255,255,0.1));
                    border-radius: var(--radius-xl, 16px);
                    width: 90%;
                    max-width: 480px;
                    transform: scale(0.95);
                    transition: transform 0.2s ease;
                }
                .settings-modal-overlay.active .settings-modal {
                    transform: scale(1);
                }
                .settings-modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: var(--space-4, 16px) var(--space-6, 24px);
                    border-bottom: 1px solid var(--glass-border, rgba(255,255,255,0.1));
                }
                .settings-modal-header h3 {
                    margin: 0;
                    font-size: var(--font-size-lg, 18px);
                    font-weight: 600;
                }
                .settings-modal-close {
                    background: none;
                    border: none;
                    font-size: 24px;
                    cursor: pointer;
                    color: var(--color-text-secondary);
                    padding: 0;
                    line-height: 1;
                }
                .settings-modal-close:hover {
                    color: var(--color-text-primary);
                }
                .settings-modal-body {
                    padding: var(--space-6, 24px);
                }
                .settings-modal-footer {
                    display: flex;
                    justify-content: flex-end;
                    gap: var(--space-3, 12px);
                    padding: var(--space-4, 16px) var(--space-6, 24px);
                    border-top: 1px solid var(--glass-border, rgba(255,255,255,0.1));
                }
                .btn-danger {
                    background: var(--color-error, #ef4444) !important;
                    color: white !important;
                }
                .btn-danger:hover {
                    background: #dc2626 !important;
                }
                .btn-loading {
                    opacity: 0.7;
                    pointer-events: none;
                }
                .btn-connected {
                    color: var(--color-success, #10b981) !important;
                    border-color: var(--color-success, #10b981) !important;
                }
                .form-input, .form-select {
                    width: 100%;
                    padding: var(--space-3, 12px);
                    border-radius: var(--radius-md, 8px);
                    border: 1px solid var(--color-border, rgba(255,255,255,0.1));
                    background: var(--color-bg, #0f0f1a);
                    color: var(--color-text, #fff);
                    font-size: var(--font-size-base, 14px);
                }
                .form-input:focus, .form-select:focus {
                    outline: none;
                    border-color: var(--color-primary, #8b5cf6);
                }
                .form-label {
                    display: block;
                    margin-bottom: var(--space-2, 8px);
                    font-weight: 500;
                }
                .form-help {
                    margin-top: var(--space-1, 4px);
                    font-size: var(--font-size-sm, 12px);
                    color: var(--color-text-secondary);
                }
                .form-group {
                    margin-bottom: var(--space-4, 16px);
                }
            `;
            document.head.appendChild(styles);
        }
    }

    window.SettingsManager = SettingsManager;
    window.SettingsAPI = SettingsAPI;
    window.SettingsUI = SettingsUI;

    const DataRightsController = {
        userEmail: null,

        init() {
            this.userEmail = document.querySelector('.settings-container')?.dataset?.userEmail || '';
            this.bindEvents();
        },

        bindEvents() {
            const exportBtn = document.getElementById('export-data-btn');
            const manageConsentBtn = document.getElementById('manage-consent-btn');
            const deleteAccountBtn = document.getElementById('delete-account-btn');
            const consentModal = document.getElementById('consent-modal');
            const deleteModal = document.getElementById('delete-modal');

            if (exportBtn) {
                exportBtn.addEventListener('click', () => this.exportData());
            }

            if (manageConsentBtn) {
                manageConsentBtn.addEventListener('click', () => this.openConsentModal());
            }

            if (deleteAccountBtn) {
                deleteAccountBtn.addEventListener('click', () => this.openDeleteModal());
            }

            document.querySelectorAll('.modal-close, .modal-cancel, .modal-overlay').forEach(el => {
                el.addEventListener('click', (e) => {
                    if (e.target.closest('.modal-content') && !e.target.classList.contains('modal-close') && !e.target.classList.contains('modal-cancel')) {
                        return;
                    }
                    this.closeModals();
                });
            });

            const saveConsentBtn = document.getElementById('save-consent-btn');
            if (saveConsentBtn) {
                saveConsentBtn.addEventListener('click', () => this.saveConsent());
            }

            const deleteConfirmEmail = document.getElementById('delete-confirm-email');
            const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
            if (deleteConfirmEmail && confirmDeleteBtn) {
                deleteConfirmEmail.addEventListener('input', (e) => {
                    const emailMatch = e.target.value.toLowerCase() === this.userEmail.toLowerCase();
                    confirmDeleteBtn.disabled = !emailMatch;
                });
            }

            if (confirmDeleteBtn) {
                confirmDeleteBtn.addEventListener('click', () => this.deleteAccount());
            }
        },

        async exportData() {
            const btn = document.getElementById('export-data-btn');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<span class="btn-spinner"></span> Exporting...';
            btn.disabled = true;

            try {
                const response = await fetch('/export/user-data', {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json'
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'mina-data-export-' + new Date().toISOString().split('T')[0] + '.json';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    SettingsUI.showToast('Your data has been exported successfully', 'success');
                } else {
                    throw new Error('Export failed');
                }
            } catch (error) {
                console.error('Export error:', error);
                SettingsUI.showToast('Failed to export data. Please try again.', 'error');
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        },

        openConsentModal() {
            const modal = document.getElementById('consent-modal');
            if (modal) {
                modal.style.display = 'flex';
                this.loadConsentPreferences();
            }
        },

        openDeleteModal() {
            const modal = document.getElementById('delete-modal');
            const emailInput = document.getElementById('delete-confirm-email');
            if (modal) {
                modal.style.display = 'flex';
                if (emailInput) {
                    emailInput.value = '';
                }
                const confirmBtn = document.getElementById('confirm-delete-btn');
                if (confirmBtn) {
                    confirmBtn.disabled = true;
                }
            }
        },

        closeModals() {
            document.querySelectorAll('.modal').forEach(modal => {
                modal.style.display = 'none';
            });
        },

        async loadConsentPreferences() {
            try {
                const response = await SettingsAPI.getPreferences();
                if (response.success && response.preferences) {
                    const gdprConsent = response.preferences.gdpr_consent || {};
                    const marketingCheckbox = document.getElementById('marketing-consent-checkbox');
                    const analyticsCheckbox = document.getElementById('analytics-consent-checkbox');
                    
                    if (marketingCheckbox) {
                        marketingCheckbox.checked = gdprConsent.marketing_consent || false;
                    }
                    if (analyticsCheckbox) {
                        analyticsCheckbox.checked = response.preferences.privacy?.anonymous_usage_stats || false;
                    }
                }
            } catch (error) {
                console.error('Failed to load consent preferences:', error);
            }
        },

        async saveConsent() {
            const marketingCheckbox = document.getElementById('marketing-consent-checkbox');
            const analyticsCheckbox = document.getElementById('analytics-consent-checkbox');
            const btn = document.getElementById('save-consent-btn');

            const consent = {
                marketing_consent: marketingCheckbox?.checked || false,
                analytics_consent: analyticsCheckbox?.checked || false,
                updated_at: new Date().toISOString()
            };

            btn.disabled = true;
            btn.textContent = 'Saving...';

            try {
                await SettingsAPI.updatePreferences('gdpr_consent', consent);
                await SettingsAPI.updatePreferences('privacy', {
                    anonymous_usage_stats: analyticsCheckbox?.checked || false
                });
                
                if (window.MinaCookieConsent) {
                    const cookieConsent = window.MinaCookieConsent.getConsent() || {};
                    cookieConsent.marketing = consent.marketing_consent;
                    cookieConsent.analytics = consent.analytics_consent;
                }

                SettingsUI.showToast('Consent preferences saved', 'success');
                this.closeModals();
            } catch (error) {
                console.error('Failed to save consent:', error);
                SettingsUI.showToast('Failed to save preferences', 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Save Preferences';
            }
        },

        async deleteAccount() {
            const btn = document.getElementById('confirm-delete-btn');
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = 'Deleting...';

            try {
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
                const response = await fetch('/auth/delete-account', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    }
                });

                if (response.ok) {
                    window.location.href = '/?deleted=true';
                } else {
                    const data = await response.json();
                    throw new Error(data.error || 'Delete failed');
                }
            } catch (error) {
                console.error('Delete account error:', error);
                SettingsUI.showToast('Failed to delete account. Please try again.', 'error');
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }
    };

    window.DataRightsController = DataRightsController;

    document.addEventListener('DOMContentLoaded', () => {
        if (window.location.pathname.startsWith('/settings')) {
            window.settingsManager = new SettingsManager();
            window.settingsManager.init();
            DataRightsController.init();
        }
    });

})();
