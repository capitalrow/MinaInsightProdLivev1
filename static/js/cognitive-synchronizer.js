/**
 * CROWN⁴.5 Phase 1.4: Cognitive Synchronizer
 * Learns from user corrections to improve future predictions
 */

class CognitiveSynchronizer {
    constructor() {
        this.predictedValues = new Map(); // taskId -> {field -> predictedValue}
        this.correctionQueue = [];
        this.initialized = false;
    }

    initialize() {
        if (this.initialized) return;

        console.log('🧠 CROWN⁴.5 Cognitive Synchronizer initialized');
        
        // Listen for task update events to detect corrections
        document.addEventListener('task:updated', (e) => {
            this.handleTaskUpdate(e.detail);
        });

        // Listen for task creation with predictions
        document.addEventListener('task:prediction-applied', (e) => {
            this.storePrediction(e.detail);
        });

        // Listen for task deletion to cleanup predictions
        document.addEventListener('task:deleted', (e) => {
            const { taskId } = e.detail;
            this.clearPredictions(taskId);
        });

        this.initialized = true;
    }

    /**
     * Store predicted values when they're applied to a task
     */
    storePrediction(data) {
        const { taskId, predictions } = data;
        
        if (!this.predictedValues.has(taskId)) {
            this.predictedValues.set(taskId, {});
        }

        const taskPredictions = this.predictedValues.get(taskId);

        // Store each predicted field
        if (predictions.title !== undefined) {
            taskPredictions.title = predictions.title;
        }
        if (predictions.priority !== undefined) {
            taskPredictions.priority = predictions.priority;
        }
        if (predictions.dueDate !== undefined) {
            taskPredictions.dueDate = predictions.dueDate;
        }
        if (predictions.labels !== undefined) {
            taskPredictions.labels = predictions.labels;
        }

        console.log(`📝 Stored predictions for task ${taskId}:`, taskPredictions);

        // Record telemetry
        if (window.CROWNTelemetry) {
            window.CROWNTelemetry.recordMetric('prediction_stored', 1);
        }
    }

    /**
     * Handle task updates to detect when predicted values are changed
     */
    async handleTaskUpdate(data) {
        const { taskId, updates, previousValues } = data;

        if (!this.predictedValues.has(taskId)) {
            return; // No predictions stored for this task
        }

        const predictions = this.predictedValues.get(taskId);
        const corrections = [];

        // Check each field that was updated
        for (const [field, newValue] of Object.entries(updates)) {
            const predictedValue = predictions[field];
            
            if (predictedValue !== undefined && predictedValue !== newValue) {
                // User changed a predicted value - this is a correction!
                corrections.push({
                    taskId,
                    field,
                    predictedValue,
                    actualValue: newValue
                });

                console.log(
                    `🔄 Correction detected: ${field} ` +
                    `predicted=${predictedValue} → actual=${newValue}`
                );

                // Remove from predictions (already corrected)
                delete predictions[field];
            }
        }

        // Send corrections to backend for learning
        if (corrections.length > 0) {
            await this.recordCorrections(corrections);
        }
    }

    /**
     * Send corrections to backend learning endpoint
     */
    async recordCorrections(corrections) {
        if (!window.predictiveEngine) {
            console.warn('⚠️ PredictiveEngine not available for learning');
            return;
        }

        for (const correction of corrections) {
            try {
                await window.predictiveEngine.recordCorrection(
                    correction.taskId,
                    correction.field,
                    correction.predictedValue,
                    correction.actualValue
                );

                console.log(`✅ Correction recorded: ${correction.field}`);

                // Record telemetry
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('correction_recorded', 1);
                    window.CROWNTelemetry.recordMetric(`correction_${correction.field}`, 1);
                }
            } catch (error) {
                console.error('Failed to record correction:', error);
                
                if (window.CROWNTelemetry) {
                    window.CROWNTelemetry.recordMetric('correction_error', 1);
                }
            }
        }
    }

    /**
     * Manually track a correction (for inline editing integration)
     */
    async trackCorrection(taskId, field, previousValue, newValue) {
        const predictions = this.predictedValues.get(taskId);
        
        if (predictions && predictions[field] !== undefined) {
            const predictedValue = predictions[field];
            
            if (predictedValue !== newValue) {
                console.log(
                    `🔄 Manual correction: ${field} ` +
                    `predicted=${predictedValue} → actual=${newValue}`
                );

                await this.recordCorrections([{
                    taskId,
                    field,
                    predictedValue,
                    actualValue: newValue
                }]);

                delete predictions[field];
            }
        }
    }

    /**
     * Clear predictions for a task (when deleted)
     */
    clearPredictions(taskId) {
        this.predictedValues.delete(taskId);
    }

    /**
     * Get prediction statistics
     */
    getStats() {
        const totalTasks = this.predictedValues.size;
        let totalPredictions = 0;

        for (const predictions of this.predictedValues.values()) {
            totalPredictions += Object.keys(predictions).length;
        }

        return {
            tasksWithPredictions: totalTasks,
            activePredictions: totalPredictions,
            correctionQueueSize: this.correctionQueue.length
        };
    }
}

// Global instance
if (typeof window !== 'undefined') {
    window.cognitiveSynchronizer = new CognitiveSynchronizer();
    window.CognitiveSynchronizer = CognitiveSynchronizer;
}

// Auto-initialize on DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (window.cognitiveSynchronizer) {
            window.cognitiveSynchronizer.initialize();
        }
    });
} else {
    if (window.cognitiveSynchronizer) {
        window.cognitiveSynchronizer.initialize();
    }
}
