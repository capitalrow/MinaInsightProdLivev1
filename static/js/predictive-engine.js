/**
 * CROWN⁴.5 Predictive Engine
 * Smart heuristic-based system for ML-style due date and priority suggestions.
 * Learns from user patterns stored in IndexedDB.
 */

class PredictiveEngine {
    constructor() {
        this.cache = null;
        this.patterns = {
            keywords: new Map(),
            durations: new Map(),
            priorities: new Map(),
            labels: new Map()
        };
        this.initialized = false;
        this.minSamples = 3; // Minimum samples to make predictions
    }

    /**
     * Initialize engine and load patterns from cache
     * @returns {Promise<void>}
     */
    async init() {
        if (this.initialized) {
            return;
        }

        this.cache = window.taskCache;
        if (!this.cache) {
            console.warn('⚠️ TaskCache not available for PredictiveEngine');
            return;
        }

        await this._loadPatterns();
        this.initialized = true;
        console.log('🤖 PredictiveEngine initialized');
    }

    /**
     * Load learned patterns from completed tasks
     * @returns {Promise<void>}
     */
    async _loadPatterns() {
        try {
            const tasks = await this.cache.getAllTasks();
            const completedTasks = tasks.filter(t => t.status === 'completed' && t.completed_at);

            console.log(`🧠 Learning from ${completedTasks.length} completed tasks...`);

            for (const task of completedTasks) {
                this._learnFromTask(task);
            }

            console.log(`✅ Patterns learned: ${this.patterns.keywords.size} keywords, ${this.patterns.durations.size} duration patterns`);
        } catch (error) {
            console.error('❌ Failed to load patterns:', error);
        }
    }

    /**
     * Learn patterns from a completed task
     * @param {Object} task
     */
    _learnFromTask(task) {
        if (!task.created_at || !task.completed_at) {
            return;
        }

        // Calculate completion duration
        const createdAt = new Date(task.created_at);
        const completedAt = new Date(task.completed_at);
        const durationMs = completedAt - createdAt;
        const durationDays = Math.ceil(durationMs / (1000 * 60 * 60 * 24));

        // Extract keywords from title and description
        const text = `${task.title || ''} ${task.description || ''}`.toLowerCase();
        const keywords = this._extractKeywords(text);

        // Learn duration patterns for keywords
        for (const keyword of keywords) {
            if (!this.patterns.durations.has(keyword)) {
                this.patterns.durations.set(keyword, []);
            }
            this.patterns.durations.get(keyword).push(durationDays);

            // Learn priority patterns
            if (task.priority) {
                if (!this.patterns.priorities.has(keyword)) {
                    this.patterns.priorities.set(keyword, new Map());
                }
                const priorityMap = this.patterns.priorities.get(keyword);
                priorityMap.set(task.priority, (priorityMap.get(task.priority) || 0) + 1);
            }

            // Learn label patterns
            if (task.labels && task.labels.length > 0) {
                if (!this.patterns.labels.has(keyword)) {
                    this.patterns.labels.set(keyword, new Map());
                }
                const labelMap = this.patterns.labels.get(keyword);
                for (const label of task.labels) {
                    labelMap.set(label, (labelMap.get(label) || 0) + 1);
                }
            }
        }

        // Store task metadata for future reference
        this.patterns.keywords.set(task.id, keywords);
    }

    /**
     * Extract keywords from text using simple NLP
     * @param {string} text
     * @returns {Array<string>}
     */
    _extractKeywords(text) {
        // Remove common stop words
        const stopWords = new Set(['the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but', 'in', 'with', 'to', 'for', 'of', 'as', 'by', 'from']);
        
        const words = text
            .toLowerCase()
            .replace(/[^\w\s]/g, ' ')
            .split(/\s+/)
            .filter(word => word.length > 2 && !stopWords.has(word));

        // Keep only significant words (appear in fewer than 50% of tasks)
        return [...new Set(words)].slice(0, 5); // Top 5 keywords
    }

    /**
     * Predict due date for a new task
     * @param {Object} taskData - { title, description, priority }
     * @returns {Object} - { dueDate: Date|null, confidence: number, reasoning: string }
     */
    predictDueDate(taskData) {
        const keywords = this._extractKeywords(`${taskData.title || ''} ${taskData.description || ''}`);
        const durations = [];

        // Collect duration samples from matching keywords
        for (const keyword of keywords) {
            if (this.patterns.durations.has(keyword)) {
                durations.push(...this.patterns.durations.get(keyword));
            }
        }

        if (durations.length < this.minSamples) {
            return {
                dueDate: null,
                confidence: 0,
                reasoning: 'Not enough historical data for prediction'
            };
        }

        // Calculate median duration (more robust than mean)
        const median = this._calculateMedian(durations);
        const dueDate = new Date();
        dueDate.setDate(dueDate.getDate() + median);

        // Calculate confidence based on sample size and variance
        const variance = this._calculateVariance(durations, median);
        const confidence = Math.min(100, Math.max(0, 
            (durations.length / 10) * 50 + // Sample size factor (max 50 points)
            (1 / (1 + variance)) * 50      // Low variance = high confidence (max 50 points)
        ));

        return {
            dueDate,
            confidence: Math.round(confidence),
            reasoning: `Based on ${durations.length} similar tasks (avg ${median} days to complete)`
        };
    }

    /**
     * Predict priority for a new task
     * @param {Object} taskData - { title, description }
     * @returns {Object} - { priority: string|null, confidence: number, reasoning: string }
     */
    predictPriority(taskData) {
        const keywords = this._extractKeywords(`${taskData.title || ''} ${taskData.description || ''}`);
        const priorityCounts = new Map();

        // Collect priority samples from matching keywords
        for (const keyword of keywords) {
            if (this.patterns.priorities.has(keyword)) {
                const priorityMap = this.patterns.priorities.get(keyword);
                for (const [priority, count] of priorityMap.entries()) {
                    priorityCounts.set(priority, (priorityCounts.get(priority) || 0) + count);
                }
            }
        }

        if (priorityCounts.size === 0) {
            return {
                priority: null,
                confidence: 0,
                reasoning: 'Not enough historical data for prediction'
            };
        }

        // Find most common priority
        let maxCount = 0;
        let predictedPriority = null;
        let totalCount = 0;

        for (const [priority, count] of priorityCounts.entries()) {
            totalCount += count;
            if (count > maxCount) {
                maxCount = count;
                predictedPriority = priority;
            }
        }

        const confidence = Math.round((maxCount / totalCount) * 100);

        return {
            priority: predictedPriority,
            confidence,
            reasoning: `${maxCount}/${totalCount} similar tasks had '${predictedPriority}' priority`
        };
    }

    /**
     * Suggest labels for a new task
     * @param {Object} taskData - { title, description }
     * @returns {Array<Object>} - [{ label: string, confidence: number }]
     */
    suggestLabels(taskData) {
        const keywords = this._extractKeywords(`${taskData.title || ''} ${taskData.description || ''}`);
        const labelCounts = new Map();

        // Collect label samples from matching keywords
        for (const keyword of keywords) {
            if (this.patterns.labels.has(keyword)) {
                const labelMap = this.patterns.labels.get(keyword);
                for (const [label, count] of labelMap.entries()) {
                    labelCounts.set(label, (labelCounts.get(label) || 0) + count);
                }
            }
        }

        if (labelCounts.size === 0) {
            return [];
        }

        // Calculate total occurrences
        const totalCount = Array.from(labelCounts.values()).reduce((a, b) => a + b, 0);

        // Sort labels by frequency and return top 3
        const suggestions = Array.from(labelCounts.entries())
            .map(([label, count]) => ({
                label,
                confidence: Math.round((count / totalCount) * 100)
            }))
            .sort((a, b) => b.confidence - a.confidence)
            .slice(0, 3);

        return suggestions;
    }

    /**
     * Get comprehensive predictions for a new task
     * Uses backend ML predictions first, falls back to local patterns
     * @param {Object} taskData - { title, description, priority }
     * @returns {Promise<Object>}
     */
    async predict(taskData) {
        if (!this.initialized) {
            await this.init();
        }

        // Try backend API predictions first (CROWN⁴.5 server-side ML)
        try {
            const backendPredictions = await this._getBackendPredictions(taskData);
            if (backendPredictions) {
                console.log('🤖 Using backend ML predictions');
                
                // Emit telemetry
                if (window.CROWNTelemetry && window.CROWNTelemetry.recordMetric) {
                    window.CROWNTelemetry.recordMetric('prediction_made_backend', 1, {
                        due_date_confidence: backendPredictions.due_date_confidence || 0,
                        priority_confidence: backendPredictions.priority_confidence || 0,
                        overall_confidence: backendPredictions.overall_confidence || 0
                    });
                }
                
                return backendPredictions;
            }
        } catch (error) {
            console.warn('⚠️ Backend predictions failed, using local patterns:', error);
        }

        // Fallback to local pattern-based predictions
        console.log('🧠 Using local pattern learning');
        const dueDatePred = this.predictDueDate(taskData);
        const priorityPred = this.predictPriority(taskData);
        const labelsSugg = this.suggestLabels(taskData);
        
        // Match template expectations: flat structure with labels as array of strings
        const predictions = {
            dueDate: dueDatePred.dueDate ? dueDatePred.dueDate.toISOString().split('T')[0] : null,
            due_date_confidence: dueDatePred.confidence / 100,
            priority: priorityPred.priority,
            priority_confidence: priorityPred.confidence / 100,
            labels: labelsSugg.map(l => l.label), // Template expects array of strings
            overall_confidence: (
                (dueDatePred.confidence / 100) * 0.4 + 
                (priorityPred.confidence / 100) * 0.3 + 
                (labelsSugg.length > 0 ? 0.3 : 0)
            ),
            timestamp: new Date().toISOString()
        };

        // Emit telemetry
        if (window.CROWNTelemetry && window.CROWNTelemetry.recordMetric) {
            window.CROWNTelemetry.recordMetric('prediction_made_local', 1, {
                due_date_confidence: predictions.due_date_confidence,
                priority_confidence: predictions.priority_confidence,
                label_suggestions: predictions.labels.length
            });
        }

        return predictions;
    }

    /**
     * Get predictions from backend ML service
     * @param {Object} taskData
     * @returns {Promise<Object|null>}
     */
    async _getBackendPredictions(taskData) {
        try {
            const response = await fetch('/api/tasks/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: taskData.title?.trim(),
                    description: taskData.description?.trim() || null,
                    task_type: taskData.task_type || 'action_item',
                    meeting_id: taskData.meeting_id || null
                })
            });

            if (!response.ok) {
                if (response.status === 401) {
                    console.warn('⚠️ Not authenticated - skipping backend predictions');
                    return null;
                }
                throw new Error(`Backend API failed: ${response.status}`);
            }

            const result = await response.json();
            
            if (!result.success) {
                console.warn('⚠️ Backend API returned error:', result.message);
                return null;
            }

            const predictions = result.predictions;

            // Transform backend format to match template expectations (flat structure)
            return {
                priority: predictions.priority?.value || null,
                priority_confidence: predictions.priority?.confidence || 0,
                dueDate: predictions.due_date?.value || null,
                due_date_confidence: predictions.due_date?.confidence || 0,
                assignee_id: predictions.assignee_id?.value || null,
                assignee_confidence: predictions.assignee_id?.confidence || 0,
                labels: [], // Backend doesn't return labels yet, placeholder for future
                overall_confidence: predictions.overall_confidence || 0,
                timestamp: new Date().toISOString()
            };

        } catch (error) {
            // Network error or server unavailable - return null to trigger fallback
            return null;
        }
    }

    /**
     * Record prediction correction for backend learning (CognitiveSynchronizer)
     * @param {number} taskId
     * @param {string} field
     * @param {*} predictedValue
     * @param {*} actualValue
     */
    async recordCorrection(taskId, field, predictedValue, actualValue) {
        try {
            await fetch('/api/tasks/predict/learn', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    task_id: taskId,
                    field,
                    predicted_value: predictedValue,
                    actual_value: actualValue
                })
            });

            console.log(`📝 Correction sent to backend: ${field} ${predictedValue} → ${actualValue}`);
        } catch (error) {
            console.warn('⚠️ Failed to send correction to backend:', error);
        }
    }

    /**
     * Update patterns when a task is completed
     * @param {Object} task
     * @returns {Promise<void>}
     */
    async updatePattern(task) {
        if (task.status === 'completed' && task.completed_at) {
            this._learnFromTask(task);
            
            // Periodically save patterns to IndexedDB
            if (this.patterns.keywords.size % 10 === 0) {
                await this._savePatterns();
            }
        }
    }

    /**
     * Save learned patterns to IndexedDB for persistence
     * @returns {Promise<void>}
     */
    async _savePatterns() {
        try {
            const patternsData = {
                durations: Array.from(this.patterns.durations.entries()),
                priorities: Array.from(this.patterns.priorities.entries()).map(([k, v]) => [k, Array.from(v.entries())]),
                labels: Array.from(this.patterns.labels.entries()).map(([k, v]) => [k, Array.from(v.entries())]),
                lastUpdated: new Date().toISOString()
            };

            await this.cache.setMetadata('predictive_patterns', patternsData);
            console.log('💾 Predictive patterns saved');
        } catch (error) {
            console.error('❌ Failed to save patterns:', error);
        }
    }

    /**
     * Calculate median of an array
     * @param {Array<number>} arr
     * @returns {number}
     */
    _calculateMedian(arr) {
        const sorted = [...arr].sort((a, b) => a - b);
        const mid = Math.floor(sorted.length / 2);
        return sorted.length % 2 === 0 
            ? (sorted[mid - 1] + sorted[mid]) / 2 
            : sorted[mid];
    }

    /**
     * Calculate variance of an array
     * @param {Array<number>} arr
     * @param {number} mean
     * @returns {number}
     */
    _calculateVariance(arr, mean) {
        const squaredDiffs = arr.map(x => Math.pow(x - mean, 2));
        return squaredDiffs.reduce((a, b) => a + b, 0) / arr.length;
    }

    /**
     * Get stats about learned patterns
     * @returns {Object}
     */
    getStats() {
        return {
            keywords: this.patterns.keywords.size,
            duration_patterns: this.patterns.durations.size,
            priority_patterns: this.patterns.priorities.size,
            label_patterns: this.patterns.labels.size,
            initialized: this.initialized
        };
    }

    /**
     * CROWN⁴.6: Analyze a task and emit AI partner nudge suggestions
     * @param {Object} task - Task to analyze
     * @returns {Object} - Analysis results with suggestions
     */
    async analyzeTaskForNudges(task) {
        if (!this.initialized) {
            await this.init();
        }

        const suggestions = [];

        const dueDatePrediction = this.predictDueDate(task);
        if (dueDatePrediction.confidence >= 70 && !task.due_date) {
            suggestions.push({
                type: 'due_date_suggestion',
                confidence: dueDatePrediction.confidence / 100,
                data: {
                    taskId: task.id,
                    taskTitle: task.title,
                    suggestedDate: this._formatDate(dueDatePrediction.dueDate),
                    suggestedDueDate: dueDatePrediction.dueDate.toISOString(),
                    reasoning: dueDatePrediction.reasoning
                }
            });
        }

        const priorityPrediction = this.predictPriority(task);
        if (priorityPrediction.confidence >= 75 && 
            priorityPrediction.priority === 'high' && 
            task.priority !== 'high' && 
            task.priority !== 'urgent') {
            suggestions.push({
                type: 'priority_suggestion',
                confidence: priorityPrediction.confidence / 100,
                data: {
                    taskId: task.id,
                    taskTitle: task.title,
                    suggestedPriority: priorityPrediction.priority,
                    meetingTitle: task.meeting?.title || 'a recent meeting',
                    reasoning: priorityPrediction.reasoning
                }
            });
        }

        if (task.extracted_by_ai && task.transcript_span?.speaker_name) {
            suggestions.push({
                type: 'smart_assignee',
                confidence: 0.8,
                data: {
                    taskId: task.id,
                    taskTitle: task.title,
                    speakerName: task.transcript_span.speaker_name,
                    userId: null
                }
            });
        }

        for (const suggestion of suggestions) {
            if (suggestion.confidence >= 0.7) {
                this._emitNudge(suggestion);
            }
        }

        return {
            taskId: task.id,
            suggestions,
            analyzed_at: new Date().toISOString()
        };
    }

    /**
     * Check for overdue tasks and emit cleanup suggestions
     */
    async checkForNudgeOpportunities() {
        if (!this.cache) return;

        try {
            const tasks = await this.cache.getAllTasks();
            const now = new Date();
            
            const overdueTasks = tasks.filter(t => 
                t.status !== 'completed' && 
                t.due_date && 
                new Date(t.due_date) < now
            );

            for (const task of overdueTasks.slice(0, 3)) {
                this._emitNudge({
                    type: 'overdue_nudge',
                    confidence: 0.9,
                    data: {
                        taskId: task.id,
                        taskTitle: task.title,
                        dueDate: task.due_date
                    }
                });
            }

            const completedTasks = tasks.filter(t => 
                t.status === 'completed' && 
                !t.archived_at
            );

            if (completedTasks.length >= 5) {
                this._emitNudge({
                    type: 'cleanup_suggestion',
                    confidence: 0.85,
                    data: {
                        completedCount: completedTasks.length
                    }
                });
            }
        } catch (error) {
            console.error('[PredictiveEngine] Error checking for nudge opportunities:', error);
        }
    }

    /**
     * Emit a nudge event for AI Partner Nudges to handle
     * @param {Object} suggestion
     */
    _emitNudge(suggestion) {
        window.dispatchEvent(new CustomEvent('prediction:ready', {
            detail: {
                type: suggestion.type,
                data: suggestion.data,
                confidence: suggestion.confidence
            }
        }));
        console.log('[PredictiveEngine] Emitted nudge:', suggestion.type);
    }

    /**
     * Record user feedback on a nudge (accepted/rejected)
     * @param {Object} feedback - { nudge_type, accepted, data }
     */
    recordFeedback(feedback) {
        console.log('[PredictiveEngine] Nudge feedback:', feedback);

        try {
            const feedbackLog = JSON.parse(localStorage.getItem('mina_nudge_feedback') || '[]');
            feedbackLog.push({
                ...feedback,
                timestamp: Date.now()
            });
            if (feedbackLog.length > 100) {
                feedbackLog.shift();
            }
            localStorage.setItem('mina_nudge_feedback', JSON.stringify(feedbackLog));
        } catch (e) {
            console.warn('[PredictiveEngine] Failed to record feedback:', e);
        }
    }

    /**
     * Format date for user display
     * @param {Date} date
     * @returns {string}
     */
    _formatDate(date) {
        const now = new Date();
        const diff = Math.ceil((date - now) / (1000 * 60 * 60 * 24));
        
        if (diff === 0) return 'today';
        if (diff === 1) return 'tomorrow';
        if (diff <= 7) return `in ${diff} days`;
        
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
}

// Export singleton
window.predictiveEngine = new PredictiveEngine();

console.log('🤖 CROWN⁴.5 PredictiveEngine loaded');
