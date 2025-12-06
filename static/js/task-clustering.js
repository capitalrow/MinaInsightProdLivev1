/**
 * CROWN⁴.5 Semantic Task Clustering
 * Groups related tasks using AI-powered semantic similarity.
 */

class TaskClusteringManager {
    constructor() {
        this.enabled = false;
        this.clusters = [];
        this.viewMode = 'list'; // 'list' or 'clusters'
        this.toggleButtonAdded = false;
        this.init();
    }

    init() {
        // REFACTORED: Do NOT add cluster toggle by default
        // The toggle button is now in the header actions area (tasks.html)
        // and will call enableClustering() when clicked
        
        // Listen for task updates
        window.addEventListener('tasks:updated', () => {
            if (this.enabled) {
                this.refreshClusters();
            }
        });

        // Listen for external clustering toggle requests
        document.addEventListener('clustering:toggle', () => {
            this.toggleClustering();
        });

        console.log('🔗 CROWN⁴.5 TaskClusteringManager initialized (toggle button NOT auto-added)');
    }

    // REMOVED: addClusterToggle() - no longer auto-adds button to filter tabs
    // The button is now explicitly placed in header-actions in tasks.html

    async toggleClustering() {
        this.enabled = !this.enabled;
        
        // Update body class for CSS targeting
        document.body.classList.toggle('clustering-active', this.enabled);
        
        // Update any toggle button that might exist
        const toggleBtn = document.querySelector('.btn-cluster-toggle, .cluster-toggle');
        if (toggleBtn) {
            toggleBtn.classList.toggle('active', this.enabled);
        }

        if (this.enabled) {
            await this.fetchAndDisplayClusters();
        } else {
            this.showNormalView();
        }
    }

    async fetchAndDisplayClusters() {
        try {
            // Show loading state
            this.showLoadingState();

            console.log('🔗 Fetching clusters from /api/tasks/clusters');
            const response = await fetch('/api/tasks/clusters', {
                credentials: 'include'  // ✅ Include session cookies for mobile/PWA
            });
            
            console.log('🔗 Cluster response status:', response.status, response.statusText);
            
            // Check if response is OK
            if (!response.ok) {
                // Handle authentication errors (mobile/PWA session loss)
                if (response.status === 401 || response.status === 302) {
                    console.error('❌ Authentication required - session may have expired');
                    this.showError('Session expired. Please refresh the page.');
                    this.enabled = false;
                    // Optionally trigger a page reload after a delay
                    setTimeout(() => window.location.reload(), 2000);
                    return;
                }
                
                const errorText = await response.text();
                console.error('❌ Clustering API error:', {
                    status: response.status,
                    statusText: response.statusText,
                    body: errorText.substring(0, 200)
                });
                this.showError(`Failed to group tasks (${response.status})`);
                this.enabled = false;
                return;
            }

            const data = await response.json();
            console.log('🔗 Cluster response data:', data);

            if (data.success) {
                this.clusters = data.clusters;
                console.log('✅ Received', data.clusters.length, 'clusters');
                this.displayClusters();
                
                // Record telemetry
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('task_clustering_enabled', 1);
                    window.CROWNTelemetry.recordMetric('task_clusters_count', data.clusters.length);
                }
            } else {
                console.error('❌ Clustering failed:', data.error, data);
                this.showError(`Failed to group tasks: ${data.error || 'Unknown error'}`);
                this.enabled = false;
            }
        } catch (error) {
            console.error('❌ Clustering exception:', error);
            console.error('Error stack:', error.stack);
            this.showError(`Failed to group tasks: ${error.message}`);
            this.enabled = false;
        }
    }

    async refreshClusters() {
        if (this.enabled) {
            await this.fetchAndDisplayClusters();
        }
    }

    displayClusters() {
        const container = document.getElementById('tasks-list-container');
        if (!container) return;

        let html = '';

        // Add cluster info header
        html += `
            <div class="clusters-header" style="margin-bottom: 2rem; padding: 1rem; background: var(--glass-bg); border-radius: var(--radius-lg); border: 1px solid var(--glass-border);">
                <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;">
                    <span style="font-size: 1.5rem;">🔗</span>
                    <h3 style="margin: 0; font-size: 1.25rem; font-weight: 600;">Grouped by Similarity</h3>
                </div>
                <p style="margin: 0; color: var(--color-text-secondary); font-size: 0.875rem;">
                    ${this.clusters.length} groups found using ${this.clusters[0]?.label ? 'AI semantic analysis' : 'keyword matching'}
                </p>
            </div>
        `;

        // Render each cluster
        this.clusters.forEach((cluster, index) => {
            html += this.renderCluster(cluster, index);
        });

        container.innerHTML = html;

        // Attach event listeners
        this.attachClusterEventListeners();
        
        // Restore selection state across view toggle
        if (window.selectionManager) {
            window.selectionManager.restoreSelectionUI();
        }
    }

    renderCluster(cluster, index) {
        const clusterColor = this.getClusterColor(index);
        
        let html = `
            <div class="task-cluster" data-cluster-id="${cluster.id}" style="margin-bottom: 2rem;">
                <div class="cluster-header" style="
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 1rem 1.5rem;
                    background: var(--glass-bg);
                    backdrop-filter: var(--backdrop-blur);
                    border: 1px solid var(--glass-border);
                    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
                    border-left: 4px solid ${clusterColor};
                ">
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <h3 style="margin: 0; font-size: 1.125rem; font-weight: 600;">
                            ${this.escapeHtml(cluster.label)}
                        </h3>
                        <span class="cluster-count-badge" style="
                            padding: 0.25rem 0.75rem;
                            background: rgba(99, 102, 241, 0.1);
                            color: var(--color-primary);
                            border-radius: var(--radius-full);
                            font-size: 0.875rem;
                            font-weight: 500;
                        ">
                            ${cluster.size} tasks
                        </span>
                    </div>
                    <button class="cluster-collapse-btn" data-cluster-id="${cluster.id}" style="
                        background: transparent;
                        border: none;
                        cursor: pointer;
                        padding: 0.5rem;
                        color: var(--color-text-secondary);
                        font-size: 1.25rem;
                    ">
                        ▼
                    </button>
                </div>
                <div class="cluster-tasks" data-cluster-id="${cluster.id}" style="
                    display: flex;
                    flex-direction: column;
                    gap: 1rem;
                    padding: 1rem;
                    background: var(--glass-bg);
                    border: 1px solid var(--glass-border);
                    border-top: none;
                    border-radius: 0 0 var(--radius-xl) var(--radius-xl);
                ">
        `;

        // Render tasks in this cluster
        cluster.tasks.forEach(task => {
            html += this.renderClusteredTask(task);
        });

        html += `
                </div>
            </div>
        `;

        return html;
    }

    renderClusteredTask(task) {
        const priority = task.priority || 'medium';
        const status = task.status || 'todo';
        const isCompleted = status === 'completed';
        const dueDate = task.due_date || null;
        const meetingTitle = task.meeting_title || 'Unknown meeting';

        return `
            <div class="task-card clustered ${isCompleted ? 'completed' : ''}" 
                 data-task-id="${task.id}" 
                 data-status="${status}"
                 style="margin: 0;">
                <div class="checkbox-wrapper">
                    <input type="checkbox" ${isCompleted ? 'checked' : ''} class="task-checkbox" data-task-id="${task.id}">
                </div>
                <h3 class="task-title">${this.escapeHtml(task.title || task.description || 'Untitled Task')}</h3>
                <span class="priority-badge priority-${priority.toLowerCase()}">
                    ${priority}
                </span>
                ${dueDate ? `
                    <span class="due-date-badge">${this.escapeHtml(dueDate)}</span>
                ` : ''}
                <span class="meeting-source">${this.escapeHtml(meetingTitle)}</span>
            </div>
        `;
    }

    attachClusterEventListeners() {
        // Collapse/expand clusters
        document.querySelectorAll('.cluster-collapse-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const clusterId = e.target.dataset.clusterId;
                const tasksContainer = document.querySelector(`.cluster-tasks[data-cluster-id="${clusterId}"]`);
                const isCollapsed = tasksContainer.style.display === 'none';
                
                tasksContainer.style.display = isCollapsed ? 'flex' : 'none';
                e.target.textContent = isCollapsed ? '▼' : '▶';
            });
        });

        // Note: Checkbox changes are handled by centralized event delegation in tasks.html
        // This prevents duplicate handlers and ensures selection mode works correctly
        
        // Task clicks
        document.querySelectorAll('.task-card.clustered').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.classList.contains('task-checkbox')) return;
                
                const taskId = card.dataset.taskId;
                window.dispatchEvent(new CustomEvent('task:clicked', {
                    detail: { task_id: taskId }
                }));
            });
        });
    }

    async showNormalView() {
        // Disable clustering mode to prevent event loop
        this.enabled = false;
        
        // Update UI state
        const toggleBtn = document.querySelector('.cluster-toggle');
        if (toggleBtn) {
            toggleBtn.classList.remove('active');
        }
        
        // Re-render normal flat task list
        const allTasks = await window.taskCache.getAllTasks();
        
        // Get active filter
        const viewState = await window.taskCache.getViewState('tasks_page');
        const activeFilter = viewState?.activeFilter || 'all';
        
        // Apply filter
        let filteredTasks = allTasks;
        if (activeFilter === 'pending') {
            filteredTasks = allTasks.filter(t => t.status === 'todo' || t.status === 'in_progress');
        } else if (activeFilter === 'completed') {
            filteredTasks = allTasks.filter(t => t.status === 'completed' || t.status === 'done');
        }
        
        // Re-render flat list (renderTasks automatically updates counters via _updateCountersFromDOM)
        if (window.taskBootstrap) {
            const ctx = window.taskBootstrap._getCurrentViewContext?.() || { filter: activeFilter, search: '', sort: { field: 'created_at', direction: 'desc' } };
            await window.taskBootstrap.renderTasks(filteredTasks, { 
                fromCache: true, 
                source: 'filter_change',
                isUserAction: true,
                filterContext: ctx.filter,
                searchQuery: ctx.search,
                sortConfig: ctx.sort
            });
        }
        
        // Restore selection state after view switches back
        setTimeout(() => {
            if (window.selectionManager) {
                window.selectionManager.restoreSelectionUI();
            }
        }, 100);
        
        console.log(`✅ Restored normal view with ${filteredTasks.length} tasks (filter: ${activeFilter})`);
    }

    showLoadingState() {
        const container = document.getElementById('tasks-list-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 4rem; color: var(--color-text-secondary);">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">🔗</div>
                    <p style="font-size: 1.125rem;">Analyzing task relationships...</p>
                    <p style="font-size: 0.875rem; margin-top: 0.5rem;">Using AI to group similar tasks</p>
                </div>
            `;
        }
    }

    showError(message) {
        const container = document.getElementById('tasks-list-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 4rem; color: var(--color-danger);">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">❌</div>
                    <p style="font-size: 1.125rem;">${this.escapeHtml(message)}</p>
                </div>
            `;
        }
    }

    getClusterColor(index) {
        const colors = [
            '#6366f1', // indigo
            '#8b5cf6', // purple
            '#ec4899', // pink
            '#f59e0b', // amber
            '#10b981', // emerald
            '#3b82f6', // blue
            '#ef4444'  // red
        ];
        return colors[index % colors.length];
    }

    formatDueDate(dueDate) {
        if (!dueDate) return '';
        
        const due = new Date(dueDate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        const diffDays = Math.floor((due - today) / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Tomorrow';
        if (diffDays < 0) return `${Math.abs(diffDays)}d overdue`;
        if (diffDays <= 7) return `In ${diffDays}d`;
        
        return due.toLocaleDateString();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.taskClusteringManager = new TaskClusteringManager();
    });
} else {
    window.taskClusteringManager = new TaskClusteringManager();
}

console.log('🔗 CROWN⁴.5 Task Clustering loaded');
