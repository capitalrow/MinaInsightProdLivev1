/**
 * CROWN⁴.5 Cognitive Synchronizer
 * 
 * Self-improving NLP system that learns from user corrections.
 * Provides feedback loop for AI task extraction accuracy.
 * 
 * Features:
 * - User correction tracking
 * - Pattern learning for NLP improvements
 * - Confidence calibration
 * - Feedback to AI engine
 */

class CognitiveSynchronizer {
    constructor() {
        this.corrections = [];
        this.patterns = {
            titleCorrections: [],
            priorityCorrections: [],
            dueDateCorrections: [],
            rejects: []
        };
        
        this.stats = {
            totalSuggestions: 0,
            accepted: 0,
            modified: 0,
            rejected: 0,
            acceptanceRate: 0
        };
        
        this.loadHistory();
        console.log('✅ CognitiveSynchronizer initialized');
    }
    
    /**
     * Load correction history from storage
     */
    loadHistory() {
        try {
            const stored = localStorage.getItem('mina_cognitive_corrections');
            if (stored) {
                const data = JSON.parse(stored);
                this.corrections = data.corrections || [];
                this.patterns = data.patterns || this.patterns;
                this.stats = data.stats || this.stats;
                
                console.log(`📚 Loaded ${this.corrections.length} corrections from history`);
            }
        } catch (error) {
            console.warn('⚠️ Failed to load correction history:', error);
        }
    }
    
    /**
     * Save correction history to storage
     */
    saveHistory() {
        try {
            const data = {
                corrections: this.corrections.slice(-500),  // Keep last 500
                patterns: this.patterns,
                stats: this.stats,
                lastUpdated: new Date().toISOString()
            };
            localStorage.setItem('mina_cognitive_corrections', JSON.stringify(data));
        } catch (error) {
            console.warn('⚠️ Failed to save correction history:', error);
        }
    }
    
    /**
     * Track AI suggestion acceptance/modification/rejection
     * @param {Object} suggestion - Original AI suggestion
     * @param {Object} action - User action {type: 'accept'|'modify'|'reject', final: actualTask}
     */
    trackSuggestion(suggestion, action) {
        this.stats.totalSuggestions++;
        
        const correction = {
            suggestion,
            action: action.type,
            final: action.final || null,
            timestamp: Date.now(),
            confidence: suggestion.confidence || 0.8
        };
        
        this.corrections.push(correction);
        
        // Update stats
        if (action.type === 'accept') {
            this.stats.accepted++;
        } else if (action.type === 'modify') {
            this.stats.modified++;
            this.learnFromModification(suggestion, action.final);
        } else if (action.type === 'reject') {
            this.stats.rejected++;
            this.learnFromRejection(suggestion);
        }
        
        this.stats.acceptanceRate = this.stats.accepted / this.stats.totalSuggestions;
        
        this.saveHistory();
        
        console.log(`📊 Suggestion tracked: ${action.type} (acceptance rate: ${(this.stats.acceptanceRate * 100).toFixed(1)}%)`);
    }
    
    /**
     * Learn from user modification
     */
    learnFromModification(suggestion, final) {
        // Track title corrections
        if (suggestion.title !== final.title) {
            this.patterns.titleCorrections.push({
                original: suggestion.title,
                corrected: final.title,
                contextHash: this.hashContext(suggestion),
                timestamp: Date.now()
            });
        }
        
        // Track priority corrections
        if (suggestion.priority !== final.priority) {
            this.patterns.priorityCorrections.push({
                suggested: suggestion.priority,
                actual: final.priority,
                context: {
                    title: suggestion.title,
                    keywords: this.extractKeywords(suggestion.title)
                },
                timestamp: Date.now()
            });
        }
        
        // Track due date corrections
        if (suggestion.due_date !== final.due_date) {
            this.patterns.dueDateCorrections.push({
                suggested: suggestion.due_date,
                actual: final.due_date,
                priority: final.priority,
                timestamp: Date.now()
            });
        }
        
        console.log('🧠 Learned from modification:', {
            titleChanged: suggestion.title !== final.title,
            priorityChanged: suggestion.priority !== final.priority,
            dueDateChanged: suggestion.due_date !== final.due_date
        });
    }
    
    /**
     * Learn from user rejection
     */
    learnFromRejection(suggestion) {
        this.patterns.rejects.push({
            title: suggestion.title,
            priority: suggestion.priority,
            confidence: suggestion.confidence,
            contextHash: this.hashContext(suggestion),
            timestamp: Date.now()
        });
        
        console.log('❌ Learned from rejection:', suggestion.title);
    }
    
    /**
     * Get improvement suggestions for AI engine
     * @returns {Object} Feedback for NLP improvement
     */
    getAIFeedback() {
        const feedback = {
            acceptanceRate: this.stats.acceptanceRate,
            commonTitleErrors: this.analyzeCommonTitleErrors(),
            priorityBias: this.analyzePriorityBias(),
            dueDateBias: this.analyzeDueDateBias(),
            recommendations: []
        };
        
        // Generate recommendations
        if (this.stats.acceptanceRate < 0.6) {
            feedback.recommendations.push({
                type: 'low_acceptance',
                message: 'Acceptance rate below 60%, consider more conservative suggestions',
                priority: 'high'
            });
        }
        
        if (this.patterns.priorityCorrections.length > 10) {
            const biasAnalysis = this.analyzePriorityBias();
            if (biasAnalysis.bias !== 'none') {
                feedback.recommendations.push({
                    type: 'priority_bias',
                    message: `Priority suggestions tend to be ${biasAnalysis.bias}`,
                    data: biasAnalysis,
                    priority: 'medium'
                });
            }
        }
        
        return feedback;
    }
    
    /**
     * Analyze common title errors
     */
    analyzeCommonTitleErrors() {
        if (this.patterns.titleCorrections.length < 5) {
            return { insufficient_data: true };
        }
        
        // Find common patterns in corrections
        const errors = {};
        
        for (const correction of this.patterns.titleCorrections) {
            const diff = this.findTitleDifference(correction.original, correction.corrected);
            if (diff) {
                const key = diff.type;
                errors[key] = (errors[key] || 0) + 1;
            }
        }
        
        return errors;
    }
    
    /**
     * Analyze priority bias
     */
    analyzePriorityBias() {
        if (this.patterns.priorityCorrections.length < 5) {
            return { insufficient_data: true };
        }
        
        const biasMap = {
            urgent: 0,
            high: 0,
            medium: 0,
            low: 0
        };
        
        for (const correction of this.patterns.priorityCorrections) {
            const suggested = correction.suggested;
            const actual = correction.actual;
            
            // Track if suggestion was higher or lower than actual
            const priorities = ['low', 'medium', 'high', 'urgent'];
            const suggestedIdx = priorities.indexOf(suggested);
            const actualIdx = priorities.indexOf(actual);
            
            if (suggestedIdx > actualIdx) {
                biasMap[suggested]++;
            } else if (suggestedIdx < actualIdx) {
                biasMap[actual]++;
            }
        }
        
        // Determine overall bias
        const totalCorrections = this.patterns.priorityCorrections.length;
        const highBias = (biasMap.urgent + biasMap.high) / totalCorrections;
        const lowBias = (biasMap.low + biasMap.medium) / totalCorrections;
        
        let bias = 'none';
        if (highBias > 0.6) bias = 'too_high';
        else if (lowBias > 0.6) bias = 'too_low';
        
        return { bias, distribution: biasMap };
    }
    
    /**
     * Analyze due date bias
     */
    analyzeDueDateBias() {
        if (this.patterns.dueDateCorrections.length < 5) {
            return { insufficient_data: true };
        }
        
        let tooEarly = 0;
        let tooLate = 0;
        
        for (const correction of this.patterns.dueDateCorrections) {
            const suggestedTime = new Date(correction.suggested).getTime();
            const actualTime = new Date(correction.actual).getTime();
            
            if (suggestedTime < actualTime) {
                tooEarly++;
            } else if (suggestedTime > actualTime) {
                tooLate++;
            }
        }
        
        const total = this.patterns.dueDateCorrections.length;
        return {
            tooEarly: tooEarly / total,
            tooLate: tooLate / total,
            bias: tooEarly > tooLate ? 'too_early' : (tooLate > tooEarly ? 'too_late' : 'balanced')
        };
    }
    
    /**
     * Find difference between original and corrected title
     */
    findTitleDifference(original, corrected) {
        if (original === corrected) return null;
        
        if (corrected.length > original.length * 1.5) {
            return { type: 'too_brief', original, corrected };
        } else if (corrected.length < original.length * 0.5) {
            return { type: 'too_verbose', original, corrected };
        } else {
            return { type: 'content_change', original, corrected };
        }
    }
    
    /**
     * Hash context for pattern matching
     */
    hashContext(obj) {
        const str = JSON.stringify({
            source: obj.source || 'unknown',
            type: obj.type || 'task'
        });
        
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return hash.toString(36);
    }
    
    /**
     * Extract keywords from text
     */
    extractKeywords(text) {
        if (!text) return [];
        
        const stopWords = new Set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for']);
        return text.toLowerCase()
            .replace(/[^\w\s]/g, '')
            .split(/\s+/)
            .filter(w => w.length > 2 && !stopWords.has(w));
    }
    
    /**
     * Get statistics
     */
    getStats() {
        return {
            ...this.stats,
            totalCorrections: this.corrections.length,
            titleCorrections: this.patterns.titleCorrections.length,
            priorityCorrections: this.patterns.priorityCorrections.length,
            dueDateCorrections: this.patterns.dueDateCorrections.length,
            rejects: this.patterns.rejects.length
        };
    }
    
    /**
     * Clear history (for testing)
     */
    clearHistory() {
        this.corrections = [];
        this.patterns = {
            titleCorrections: [],
            priorityCorrections: [],
            dueDateCorrections: [],
            rejects: []
        };
        this.stats = {
            totalSuggestions: 0,
            accepted: 0,
            modified: 0,
            rejected: 0,
            acceptanceRate: 0
        };
        this.saveHistory();
        console.log('🗑️ Cognitive history cleared');
    }
}

// Global instance
window.TaskCognitiveSync = new CognitiveSynchronizer();

console.log('✅ CROWN⁴.5 CognitiveSynchronizer loaded');
