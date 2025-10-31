/**
 * CROWN⁴.5 Session Context Service
 * 
 * Shared service linking tasks ↔ transcript ↔ dashboard
 * Provides seamless context switching and origin_hash deduplication
 * 
 * Features:
 * - Cross-domain context tracking
 * - Origin hash deduplication
 * - Transcript span linking
 * - Context confidence scoring
 */

class SessionContext {
    constructor() {
        this.contexts = new Map();  // {session_id: context}
        this.taskToSession = new Map();  // {task_id: session_id}
        this.originHashes = new Set();  // Dedupe tracking
        
        console.log('✅ SessionContext initialized');
    }
    
    /**
     * Create context for a session
     * @param {string} sessionId - Meeting/session ID
     * @param {Object} metadata - Session metadata
     */
    createContext(sessionId, metadata = {}) {
        if (this.contexts.has(sessionId)) {
            console.warn(`⚠️ Context for session ${sessionId} already exists`);
            return this.contexts.get(sessionId);
        }
        
        const context = {
            session_id: sessionId,
            created_at: new Date().toISOString(),
            metadata: {
                title: metadata.title || 'Unknown Session',
                start_time: metadata.start_time,
                end_time: metadata.end_time,
                participants: metadata.participants || [],
                ...metadata
            },
            tasks: [],
            transcript_spans: [],
            derived_entities: [],
            context_confidence: 1.0
        };
        
        this.contexts.set(sessionId, context);
        console.log(`✅ Created context for session: ${sessionId}`);
        
        return context;
    }
    
    /**
     * Link task to session context
     * @param {Object} task - Task object
     * @param {string} sessionId - Session ID
     * @param {Object} options - Link options {transcript_span, origin_hash, confidence}
     */
    linkTaskToSession(task, sessionId, options = {}) {
        let context = this.contexts.get(sessionId);
        if (!context) {
            context = this.createContext(sessionId);
        }
        
        // Check for duplicate by origin_hash
        if (options.origin_hash) {
            if (this.originHashes.has(options.origin_hash)) {
                console.warn(`⚠️ Duplicate detected: origin_hash ${options.origin_hash}`);
                return { duplicate: true, origin_hash: options.origin_hash };
            }
            this.originHashes.add(options.origin_hash);
        }
        
        // Add task to context
        const taskLink = {
            task_id: task.id,
            title: task.title,
            transcript_span: options.transcript_span || null,
            origin_hash: options.origin_hash || null,
            confidence: options.confidence || 0.8,
            extracted_by_ai: task.extracted_by_ai || false,
            linked_at: new Date().toISOString()
        };
        
        context.tasks.push(taskLink);
        this.taskToSession.set(task.id, sessionId);
        
        console.log(`🔗 Linked task ${task.id} to session ${sessionId}`);
        
        return { success: true, context };
    }
    
    /**
     * Get session context for a task
     * @param {number} taskId - Task ID
     * @returns {Object|null} Session context
     */
    getSessionForTask(taskId) {
        const sessionId = this.taskToSession.get(taskId);
        if (!sessionId) return null;
        
        return this.contexts.get(sessionId);
    }
    
    /**
     * Get all tasks for a session
     * @param {string} sessionId - Session ID
     * @returns {Array} Task links
     */
    getTasksForSession(sessionId) {
        const context = this.contexts.get(sessionId);
        return context ? context.tasks : [];
    }
    
    /**
     * Add transcript span to context
     * @param {string} sessionId - Session ID
     * @param {Object} span - Transcript span {start, end, text, speaker}
     */
    addTranscriptSpan(sessionId, span) {
        const context = this.contexts.get(sessionId);
        if (!context) {
            console.warn(`⚠️ No context found for session ${sessionId}`);
            return;
        }
        
        context.transcript_spans.push({
            ...span,
            added_at: new Date().toISOString()
        });
    }
    
    /**
     * Find tasks by transcript span
     * @param {string} sessionId - Session ID
     * @param {number} timestamp - Timestamp in transcript
     * @returns {Array} Tasks linked to that span
     */
    findTasksByTranscriptTime(sessionId, timestamp) {
        const context = this.contexts.get(sessionId);
        if (!context) return [];
        
        return context.tasks.filter(task => {
            if (!task.transcript_span) return false;
            const span = task.transcript_span;
            return timestamp >= span.start && timestamp <= span.end;
        });
    }
    
    /**
     * Jump to transcript location for task
     * @param {number} taskId - Task ID
     * @returns {Object} {sessionId, span, url}
     */
    getTranscriptLocationForTask(taskId) {
        const sessionId = this.taskToSession.get(taskId);
        if (!sessionId) {
            return { error: 'Task not linked to session' };
        }
        
        const context = this.contexts.get(sessionId);
        const taskLink = context.tasks.find(t => t.task_id === taskId);
        
        if (!taskLink || !taskLink.transcript_span) {
            return { error: 'No transcript span for task' };
        }
        
        // Construct URL to transcript view
        const span = taskLink.transcript_span;
        const url = `/meetings/${sessionId}?time=${span.start}`;
        
        return {
            success: true,
            sessionId,
            span,
            url,
            context
        };
    }
    
    /**
     * Update context confidence based on user interactions
     * @param {string} sessionId - Session ID
     * @param {number} delta - Confidence delta (-1 to +1)
     */
    updateConfidence(sessionId, delta) {
        const context = this.contexts.get(sessionId);
        if (!context) return;
        
        context.context_confidence = Math.max(0, Math.min(1, context.context_confidence + delta));
        
        console.log(`📊 Updated context confidence for ${sessionId}: ${context.context_confidence.toFixed(2)}`);
    }
    
    /**
     * Deduplicate tasks by origin_hash
     * @param {Array} tasks - Array of tasks
     * @returns {Object} {unique: Array, duplicates: Array}
     */
    deduplicateTasks(tasks) {
        const unique = [];
        const duplicates = [];
        
        for (const task of tasks) {
            const hash = task.origin_hash;
            if (!hash) {
                unique.push(task);
                continue;
            }
            
            if (this.originHashes.has(hash)) {
                duplicates.push(task);
            } else {
                this.originHashes.add(hash);
                unique.push(task);
            }
        }
        
        return { unique, duplicates };
    }
    
    /**
     * Get all contexts
     */
    getAllContexts() {
        return Array.from(this.contexts.values());
    }
    
    /**
     * Clear context for a session
     */
    clearContext(sessionId) {
        const context = this.contexts.get(sessionId);
        if (context) {
            // Remove origin hashes
            context.tasks.forEach(task => {
                if (task.origin_hash) {
                    this.originHashes.delete(task.origin_hash);
                }
            });
            
            // Remove task mappings
            context.tasks.forEach(task => {
                this.taskToSession.delete(task.task_id);
            });
        }
        
        this.contexts.delete(sessionId);
        console.log(`🗑️ Cleared context for session: ${sessionId}`);
    }
    
    /**
     * Export context for persistence
     */
    exportContexts() {
        return {
            contexts: Array.from(this.contexts.entries()),
            taskToSession: Array.from(this.taskToSession.entries()),
            originHashes: Array.from(this.originHashes)
        };
    }
    
    /**
     * Import contexts from storage
     */
    importContexts(data) {
        this.contexts = new Map(data.contexts || []);
        this.taskToSession = new Map(data.taskToSession || []);
        this.originHashes = new Set(data.originHashes || []);
        
        console.log(`📥 Imported ${this.contexts.size} contexts`);
    }
}

// Global instance
window.TaskSessionContext = new SessionContext();

console.log('✅ CROWN⁴.5 SessionContext loaded');
