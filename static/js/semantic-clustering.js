/**
 * CROWN⁴.5 Semantic Clustering
 * Groups tasks by semantic meaning: Follow-ups, Decisions, Reviews, etc.
 * 
 * Features:
 * - Automatic task categorization
 * - Collapsible cluster groups
 * - Visual cluster indicators
 */

class SemanticClustering {
    constructor() {
        this.clusters = new Map();
        this.clusterDefinitions = {
            'follow_ups': {
                label: '📋 Follow-ups',
                keywords: ['follow up', 'check in', 'follow-up', 'reach out', 'contact', 'email'],
                color: '#3b82f6'
            },
            'decisions': {
                label: '⚖️ Decisions',
                keywords: ['decide', 'decision', 'choose', 'approve', 'review decision', 'make a call'],
                color: '#a855f7'
            },
            'reviews': {
                label: '🔍 Reviews',
                keywords: ['review', 'evaluate', 'assess', 'analyze', 'examine', 'check'],
                color: '#06b6d4'
            },
            'action_items': {
                label: '✅ Action Items',
                keywords: ['implement', 'create', 'build', 'develop', 'fix', 'update', 'add'],
                color: '#10b981'
            },
            'research': {
                label: '📚 Research',
                keywords: ['research', 'investigate', 'explore', 'find out', 'look into', 'study'],
                color: '#f59e0b'
            },
            'meetings': {
                label: '🗓️ Meetings',
                keywords: ['schedule', 'meeting', 'call', 'sync', 'standup', 'demo'],
                color: '#ec4899'
            }
        };
        
        console.log('[SemanticClustering] Initialized');
    }

    /**
     * Classify task into clusters
     * @param {Object} task
     * @returns {Array} Cluster IDs
     */
    classifyTask(task) {
        const text = `${task.title} ${task.description || ''}`.toLowerCase();
        const matches = [];

        for (const [clusterId, definition] of Object.entries(this.clusterDefinitions)) {
            const hasMatch = definition.keywords.some(keyword => 
                text.includes(keyword.toLowerCase())
            );
            
            if (hasMatch) {
                matches.push(clusterId);
            }
        }

        // Default to action_items if no match
        return matches.length > 0 ? matches : ['action_items'];
    }

    /**
     * Group tasks by clusters
     * @param {Array} tasks
     * @returns {Map} Clustered tasks
     */
    groupTasks(tasks) {
        const grouped = new Map();

        // Initialize clusters
        for (const clusterId of Object.keys(this.clusterDefinitions)) {
            grouped.set(clusterId, []);
        }

        // Classify and group tasks
        tasks.forEach(task => {
            const clusterIds = this.classifyTask(task);
            clusterIds.forEach(clusterId => {
                grouped.get(clusterId).push(task);
            });
        });

        return grouped;
    }

    /**
     * Render clustered tasks
     * @param {Array} tasks
     * @param {HTMLElement} container
     */
    renderClustered(tasks, container) {
        if (!container) return;

        const grouped = this.groupTasks(tasks);
        container.innerHTML = '';

        // Render each cluster
        for (const [clusterId, clusterTasks] of grouped.entries()) {
            if (clusterTasks.length === 0) continue;

            const definition = this.clusterDefinitions[clusterId];
            const clusterElement = this._createClusterElement(
                definition.label,
                clusterTasks,
                definition.color,
                clusterId
            );

            container.appendChild(clusterElement);
        }

        console.log(`[SemanticClustering] Rendered ${grouped.size} clusters`);
    }

    /**
     * Create cluster element
     * @param {string} label
     * @param {Array} tasks
     * @param {string} color
     * @param {string} clusterId
     * @returns {HTMLElement}
     */
    _createClusterElement(label, tasks, color, clusterId) {
        const cluster = document.createElement('div');
        cluster.className = 'semantic-cluster';
        cluster.dataset.clusterId = clusterId;
        cluster.style.cssText = `
            margin-bottom: 20px;
            border-radius: 8px;
            overflow: hidden;
        `;

        const isCollapsed = localStorage.getItem(`cluster_${clusterId}_collapsed`) === 'true';

        cluster.innerHTML = `
            <div class="cluster-header" style="
                background: ${color}15;
                border-left: 4px solid ${color};
                padding: 12px 16px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                cursor: pointer;
                user-select: none;
                transition: all 150ms ease-out;
            ">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span class="cluster-icon" style="
                        font-size: 18px;
                        transition: transform 200ms ease-out;
                        transform: rotate(${isCollapsed ? '-90deg' : '0deg'});
                    ">▼</span>
                    <span style="font-weight: 600; font-size: 15px; color: #1f2937;">
                        ${label}
                    </span>
                </div>
                <span class="cluster-count" style="
                    background: ${color};
                    color: white;
                    padding: 4px 10px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: 600;
                ">${tasks.length}</span>
            </div>
            <div class="cluster-tasks" style="
                padding: 8px;
                display: ${isCollapsed ? 'none' : 'block'};
                transition: all 200ms ease-out;
            "></div>
        `;

        // Add tasks
        const tasksContainer = cluster.querySelector('.cluster-tasks');
        tasks.forEach(task => {
            const taskCard = this._createTaskCard(task);
            tasksContainer.appendChild(taskCard);
        });

        // Toggle collapse
        const header = cluster.querySelector('.cluster-header');
        const icon = cluster.querySelector('.cluster-icon');
        
        header.addEventListener('click', () => {
            const isCollapsed = tasksContainer.style.display === 'none';
            tasksContainer.style.display = isCollapsed ? 'block' : 'none';
            icon.style.transform = isCollapsed ? 'rotate(0deg)' : 'rotate(-90deg)';
            
            // Save state
            localStorage.setItem(`cluster_${clusterId}_collapsed`, !isCollapsed);
        });

        header.addEventListener('mouseenter', () => {
            header.style.background = `${color}25`;
        });

        header.addEventListener('mouseleave', () => {
            header.style.background = `${color}15`;
        });

        return cluster;
    }

    /**
     * Create task card
     * @param {Object} task
     * @returns {HTMLElement}
     */
    _createTaskCard(task) {
        const card = document.createElement('div');
        card.className = 'task-card-mini';
        card.dataset.taskId = task.id;
        card.style.cssText = `
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 150ms ease-out;
        `;

        const isCompleted = task.status === 'completed';

        card.innerHTML = `
            <div style="display: flex; align-items: start; gap: 10px;">
                <input type="checkbox" 
                       class="task-checkbox" 
                       ${isCompleted ? 'checked' : ''}
                       data-task-id="${task.id}"
                       style="margin-top: 2px;">
                <div style="flex: 1;">
                    <h4 style="
                        margin: 0 0 4px 0;
                        font-size: 14px;
                        font-weight: 500;
                        color: ${isCompleted ? '#9ca3af' : '#1f2937'};
                        text-decoration: ${isCompleted ? 'line-through' : 'none'};
                    ">${this._escapeHtml(task.title)}</h4>
                    ${task.due_date ? `
                        <div style="font-size: 12px; color: #6b7280;">
                            📅 ${this._formatDate(task.due_date)}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;

        card.addEventListener('mouseenter', () => {
            card.style.background = '#f9fafb';
            card.style.borderColor = '#3b82f6';
            card.style.transform = 'translateX(4px)';
        });

        card.addEventListener('mouseleave', () => {
            card.style.background = 'white';
            card.style.borderColor = '#e5e7eb';
            card.style.transform = 'translateX(0)';
        });

        card.addEventListener('click', (e) => {
            if (!e.target.classList.contains('task-checkbox')) {
                // Navigate to task detail or trigger task view
                window.dispatchEvent(new CustomEvent('task_clicked', {
                    detail: { task_id: task.id }
                }));
            }
        });

        return card;
    }

    /**
     * Escape HTML
     * @param {string} text
     * @returns {string}
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Format date
     * @param {string} dateStr
     * @returns {string}
     */
    _formatDate(dateStr) {
        const date = new Date(dateStr);
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);

        if (date.toDateString() === today.toDateString()) {
            return 'Today';
        } else if (date.toDateString() === tomorrow.toDateString()) {
            return 'Tomorrow';
        } else {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }
    }

    /**
     * Toggle clustering mode
     * @param {boolean} enabled
     */
    toggleMode(enabled) {
        localStorage.setItem('semantic_clustering_enabled', enabled);
        window.dispatchEvent(new CustomEvent('clustering_mode_changed', {
            detail: { enabled }
        }));
    }

    /**
     * Check if clustering mode is enabled
     * @returns {boolean}
     */
    isEnabled() {
        return localStorage.getItem('semantic_clustering_enabled') === 'true';
    }
}

// Initialize global instance
window.SemanticClustering = SemanticClustering;

if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        if (!window.semanticClustering) {
            window.semanticClustering = new SemanticClustering();
            console.log('[SemanticClustering] Global instance created');
        }
    });
}
