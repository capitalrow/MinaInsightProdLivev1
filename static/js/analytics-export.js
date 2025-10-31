/**
 * Analytics Export Worker - CROWN⁵+ Professional Data Export
 * 
 * Features:
 * - CSV and JSON export formats
 * - Async export with progress tracking
 * - Event auditing (analytics_export_initiated)
 * - Toast notification system
 * - Professional download experience
 */

export class AnalyticsExportWorker {
    constructor(lifecycle, workspaceId) {
        this.lifecycle = lifecycle;
        this.workspaceId = workspaceId;
        this.isExporting = false;
    }

    /**
     * Export analytics data as CSV
     */
    async exportAsCSV() {
        if (this.isExporting) {
            this._showToast('Export already in progress', 'warning');
            return;
        }

        try {
            this.isExporting = true;
            this._showToast('Preparing export...', 'info');

            // Broadcast export initiated event
            this._broadcastExportEvent('csv');

            // Get current snapshot
            const snapshot = this.lifecycle.currentSnapshot;
            if (!snapshot) {
                throw new Error('No data available to export');
            }

            // Generate CSV
            const csv = this._generateCSV(snapshot);

            // Download file
            this._downloadFile(csv, 'analytics-export.csv', 'text/csv');

            this._showToast('Export successful!', 'success');
        } catch (e) {
            console.error('Export failed:', e);
            this._showToast('Export failed: ' + e.message, 'error');
        } finally {
            this.isExporting = false;
        }
    }

    /**
     * Export analytics data as JSON
     */
    async exportAsJSON() {
        if (this.isExporting) {
            this._showToast('Export already in progress', 'warning');
            return;
        }

        try {
            this.isExporting = true;
            this._showToast('Preparing export...', 'info');

            // Broadcast export initiated event
            this._broadcastExportEvent('json');

            // Get current snapshot
            const snapshot = this.lifecycle.currentSnapshot;
            if (!snapshot) {
                throw new Error('No data available to export');
            }

            // Generate JSON
            const json = JSON.stringify(snapshot, null, 2);

            // Download file
            this._downloadFile(json, 'analytics-export.json', 'application/json');

            this._showToast('Export successful!', 'success');
        } catch (e) {
            console.error('Export failed:', e);
            this._showToast('Export failed: ' + e.message, 'error');
        } finally {
            this.isExporting = false;
        }
    }

    /**
     * Generate CSV from snapshot
     * @private
     */
    _generateCSV(snapshot) {
        const kpis = snapshot.kpis || {};
        
        // CSV header
        let csv = 'Metric,Value\n';
        
        // KPIs
        csv += `Total Meetings,${kpis.total_meetings || 0}\n`;
        csv += `Total Tasks,${kpis.total_tasks || 0}\n`;
        csv += `Task Completion Rate,${kpis.task_completion_rate || 0}%\n`;
        csv += `Average Duration,${kpis.avg_duration || 0}m\n`;
        csv += `Hours Saved,${kpis.hours_saved || 0}\n`;
        
        // Timestamp
        csv += `\nExported At,${new Date().toISOString()}\n`;
        csv += `Workspace ID,${this.workspaceId}\n`;
        csv += `Date Range,Last ${snapshot.days || 30} days\n`;
        
        return csv;
    }

    /**
     * Broadcast export initiated event
     * @private
     */
    _broadcastExportEvent(format) {
        try {
            this.lifecycle.socket.emit('analytics_export_initiated', {
                workspace_id: this.workspaceId,
                format: format,
                timestamp: new Date().toISOString()
            });
        } catch (e) {
            console.warn('Failed to broadcast export event:', e);
        }
    }

    /**
     * Download file to user's device
     * @private
     */
    _downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Cleanup
        setTimeout(() => URL.revokeObjectURL(url), 100);
    }

    /**
     * Show toast notification
     * @private
     */
    _showToast(message, type = 'info') {
        // Check if toast container exists
        let container = document.getElementById('analytics-toast-container');
        
        if (!container) {
            container = document.createElement('div');
            container.id = 'analytics-toast-container';
            container.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 12px;
            `;
            document.body.appendChild(container);
        }

        // Create toast element
        const toast = document.createElement('div');
        toast.className = 'analytics-toast';
        
        const colors = {
            info: 'rgba(99, 102, 241, 0.95)',
            success: 'rgba(34, 197, 94, 0.95)',
            warning: 'rgba(249, 115, 22, 0.95)',
            error: 'rgba(239, 68, 68, 0.95)'
        };
        
        toast.style.cssText = `
            background: ${colors[type] || colors.info};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            font-size: 14px;
            font-weight: 500;
            min-width: 250px;
            max-width: 400px;
            animation: slideInRight 0.3s ease-out;
        `;
        
        toast.textContent = message;
        
        // Add to container
        container.appendChild(toast);

        // Auto-remove after 3 seconds
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-in';
            setTimeout(() => {
                toast.remove();
                
                // Remove container if empty
                if (container.children.length === 0) {
                    container.remove();
                }
            }, 300);
        }, 3000);

        // Add animation keyframes if not already added
        this._addToastAnimations();
    }

    /**
     * Add toast animation keyframes
     * @private
     */
    _addToastAnimations() {
        if (document.getElementById('analytics-toast-animations')) return;

        const style = document.createElement('style');
        style.id = 'analytics-toast-animations';
        style.textContent = `
            @keyframes slideInRight {
                from {
                    opacity: 0;
                    transform: translateX(100%);
                }
                to {
                    opacity: 1;
                    transform: translateX(0);
                }
            }
            
            @keyframes slideOutRight {
                from {
                    opacity: 1;
                    transform: translateX(0);
                }
                to {
                    opacity: 0;
                    transform: translateX(100%);
                }
            }
        `;
        document.head.appendChild(style);
    }
}
