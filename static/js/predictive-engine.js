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
     * @param {Object} taskData - { title, description, priority }
     * @returns {Promise<Object>}
     */
    async predict(taskData) {
        if (!this.initialized) {
            await this.init();
        }

        const predictions = {
            dueDate: this.predictDueDate(taskData),
            priority: this.predictPriority(taskData),
            labels: this.suggestLabels(taskData),
            timestamp: new Date().toISOString()
        };

        // Emit telemetry
        if (window.CROWNTelemetry && window.CROWNTelemetry.recordMetric) {
            window.CROWNTelemetry.recordMetric('prediction_made', 1, {
                due_date_confidence: predictions.dueDate.confidence,
                priority_confidence: predictions.priority.confidence,
                label_suggestions: predictions.labels.length
            });
        }

        return predictions;
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
}

// Export singleton
window.predictiveEngine = new PredictiveEngine();

console.log('🤖 CROWN⁴.5 PredictiveEngine loaded');
