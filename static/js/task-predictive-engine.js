/**
 * CROWN⁴.5 Predictive Engine
 * 
 * ML-based system for smart defaults and user intent prediction.
 * Learns from user patterns to suggest due dates, priorities, and next actions.
 * 
 * Features:
 * - Pattern learning from user behavior
 * - Smart due date suggestions
 * - Priority prediction
 * - Next-task recommendations
 */

class PredictiveEngine {
    constructor() {
        this.patterns = {
            dueDates: [],
            priorities: [],
            completionTimes: [],
            taskSequences: []
        };
        
        this.suggestions = new Map();
        this.accuracy = {
            dueDate: 0,
            priority: 0,
            overall: 0
        };
        
        this.loadPatterns();
        console.log('✅ PredictiveEngine initialized');
    }
    
    /**
     * Load learned patterns from localStorage
     */
    loadPatterns() {
        try {
            const stored = localStorage.getItem('mina_task_patterns');
            if (stored) {
                this.patterns = JSON.parse(stored);
                console.log('📚 Loaded task patterns from storage');
            }
        } catch (error) {
            console.warn('⚠️ Failed to load patterns:', error);
        }
    }
    
    /**
     * Save patterns to localStorage
     */
    savePatterns() {
        try {
            localStorage.setItem('mina_task_patterns', JSON.stringify(this.patterns));
        } catch (error) {
            console.warn('⚠️ Failed to save patterns:', error);
        }
    }
    
    /**
     * Learn from user behavior
     * @param {Object} task - Completed or modified task
     * @param {string} action - Action taken (created, completed, updated)
     */
    learn(task, action) {
        const now = Date.now();
        
        // Learn due date patterns
        if (task.due_date && task.created_at) {
            const createdTime = new Date(task.created_at).getTime();
            const dueTime = new Date(task.due_date).getTime();
            const daysUntilDue = Math.round((dueTime - createdTime) / (1000 * 60 * 60 * 24));
            
            this.patterns.dueDates.push({
                priority: task.priority,
                category: task.category,
                daysUntilDue,
                timestamp: now
            });
        }
        
        // Learn priority patterns
        if (task.priority) {
            this.patterns.priorities.push({
                title: this.extractKeywords(task.title),
                priority: task.priority,
                completed: task.status === 'completed',
                timestamp: now
            });
        }
        
        // Learn completion time patterns
        if (action === 'completed' && task.created_at && task.completed_at) {
            const createdTime = new Date(task.created_at).getTime();
            const completedTime = new Date(task.completed_at).getTime();
            const completionHours = (completedTime - createdTime) / (1000 * 60 * 60);
            
            this.patterns.completionTimes.push({
                priority: task.priority,
                completionHours,
                timestamp: now
            });
        }
        
        // Limit pattern storage (keep last 1000)
        Object.keys(this.patterns).forEach(key => {
            if (this.patterns[key].length > 1000) {
                this.patterns[key] = this.patterns[key].slice(-1000);
            }
        });
        
        this.savePatterns();
    }
    
    /**
     * Suggest due date for new task
     * @param {Object} task - Task object with title, priority, etc.
     * @returns {Object} {date: Date, confidence: number}
     */
    suggestDueDate(task) {
        if (this.patterns.dueDates.length === 0) {
            // Default: 7 days for medium, 3 for high, 14 for low
            const defaults = {
                urgent: 1,
                high: 3,
                medium: 7,
                low: 14
            };
            const days = defaults[task.priority] || 7;
            return {
                date: new Date(Date.now() + days * 24 * 60 * 60 * 1000),
                confidence: 0.5,
                reason: 'default'
            };
        }
        
        // Find similar patterns
        const similar = this.patterns.dueDates.filter(p =>
            p.priority === task.priority
        );
        
        if (similar.length === 0) {
            return this.suggestDueDate({ ...task, priority: 'medium' });
        }
        
        // Average days until due
        const avgDays = similar.reduce((sum, p) => sum + p.daysUntilDue, 0) / similar.length;
        const date = new Date(Date.now() + avgDays * 24 * 60 * 60 * 1000);
        
        return {
            date,
            confidence: Math.min(0.9, similar.length / 10),
            reason: 'pattern_match',
            sampleSize: similar.length
        };
    }
    
    /**
     * Suggest priority for new task
     * @param {Object} task - Task object with title
     * @returns {Object} {priority: string, confidence: number}
     */
    suggestPriority(task) {
        const keywords = this.extractKeywords(task.title);
        
        if (this.patterns.priorities.length === 0) {
            return {
                priority: 'medium',
                confidence: 0.5,
                reason: 'default'
            };
        }
        
        // Find patterns with similar keywords
        const scores = { urgent: 0, high: 0, medium: 0, low: 0 };
        let totalMatches = 0;
        
        for (const pattern of this.patterns.priorities) {
            const matchCount = pattern.title.filter(kw => keywords.includes(kw)).length;
            if (matchCount > 0) {
                scores[pattern.priority] += matchCount;
                totalMatches += matchCount;
            }
        }
        
        if (totalMatches === 0) {
            return {
                priority: 'medium',
                confidence: 0.5,
                reason: 'no_match'
            };
        }
        
        // Find priority with highest score
        const predicted = Object.entries(scores)
            .sort((a, b) => b[1] - a[1])[0][0];
        
        const confidence = Math.min(0.9, scores[predicted] / totalMatches);
        
        return {
            priority: predicted,
            confidence,
            reason: 'keyword_match',
            matches: totalMatches
        };
    }
    
    /**
     * Predict next likely task based on patterns
     * @returns {Array} Array of suggested next tasks
     */
    suggestNextTasks() {
        // Analyze task sequences from history
        // This would require task history tracking
        // For now, return empty array
        return [];
    }
    
    /**
     * Extract keywords from text for pattern matching
     */
    extractKeywords(text) {
        if (!text) return [];
        
        // Simple keyword extraction (could be enhanced with NLP)
        const stopWords = new Set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for']);
        const words = text.toLowerCase()
            .replace(/[^\w\s]/g, '')
            .split(/\s+/)
            .filter(w => w.length > 2 && !stopWords.has(w));
        
        return [...new Set(words)];
    }
    
    /**
     * Update accuracy metrics based on user feedback
     */
    updateAccuracy(suggestionType, accepted) {
        // Track whether suggestions were accepted
        const key = `${suggestionType}_accepted`;
        const total = localStorage.getItem(`${key}_total`) || 0;
        const count = localStorage.getItem(`${key}_count`) || 0;
        
        localStorage.setItem(`${key}_total`, parseInt(total) + 1);
        if (accepted) {
            localStorage.setItem(`${key}_count`, parseInt(count) + 1);
        }
        
        // Recalculate accuracy
        const newTotal = parseInt(total) + 1;
        const newCount = parseInt(count) + (accepted ? 1 : 0);
        this.accuracy[suggestionType] = newTotal > 0 ? newCount / newTotal : 0;
        this.accuracy.overall = Object.values(this.accuracy).reduce((a, b) => a + b, 0) / Object.keys(this.accuracy).length;
    }
    
    /**
     * Get accuracy statistics
     */
    getAccuracy() {
        return { ...this.accuracy };
    }
    
    /**
     * Clear learned patterns (for testing/reset)
     */
    clearPatterns() {
        this.patterns = {
            dueDates: [],
            priorities: [],
            completionTimes: [],
            taskSequences: []
        };
        this.savePatterns();
        console.log('🗑️ Predictive patterns cleared');
    }
}

// Global instance
window.TaskPredictiveEngine = new PredictiveEngine();

console.log('✅ CROWN⁴.5 PredictiveEngine loaded');
