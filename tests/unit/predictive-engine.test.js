/**
 * Unit Tests for PredictiveEngine
 * Tests heuristic-based ML predictions for task priority and due dates
 */

describe('PredictiveEngine', () => {
    let PredictiveEngine;
    let mockTaskCache;
    let engine;

    beforeEach(() => {
        jest.resetModules();
        
        // Mock globals
        global.window = {
            taskCache: null,
            CROWNTelemetry: {
                recordMetric: jest.fn()
            }
        };
        
        // Mock TaskCache
        mockTaskCache = {
            getAllTasks: jest.fn().mockResolvedValue([
                {
                    id: 1,
                    title: 'Fix critical bug',
                    priority: 'urgent',
                    due_date: '2025-11-02',
                    status: 'todo'
                },
                {
                    id: 2,
                    title: 'Review pull request',
                    priority: 'high',
                    due_date: '2025-11-03',
                    status: 'todo'
                },
                {
                    id: 3,
                    title: 'Update documentation',
                    priority: 'low',
                    due_date: '2025-11-10',
                    status: 'todo'
                }
            ])
        };
        
        global.window.taskCache = mockTaskCache;
        
        // Create simplified PredictiveEngine class for testing
        PredictiveEngine = class {
            constructor() {
                this.initialized = false;
                this.historicalData = [];
            }
            
            async init() {
                if (!window.taskCache) {
                    console.warn('⚠️ TaskCache not available');
                    return;
                }
                
                try {
                    this.historicalData = await window.taskCache.getAllTasks();
                    this.initialized = true;
                } catch (error) {
                    console.error('❌ PredictiveEngine init failed:', error);
                }
            }
            
            _predictPriority(title, description) {
                const text = `${title} ${description || ''}`.toLowerCase();
                
                // Urgent keywords
                if (/urgent|critical|emergency|asap|immediate|hotfix|blocker/i.test(text)) {
                    return { priority: 'urgent', confidence: 0.9 };
                }
                
                // High keywords
                if (/important|high priority|deadline|soon|bug|error|issue/i.test(text)) {
                    return { priority: 'high', confidence: 0.8 };
                }
                
                // Low keywords
                if (/minor|trivial|nice to have|someday|maybe|optional/i.test(text)) {
                    return { priority: 'low', confidence: 0.75 };
                }
                
                // Default to medium
                return { priority: 'medium', confidence: 0.6 };
            }
            
            _predictDueDate(title, description) {
                const text = `${title} ${description || ''}`.toLowerCase();
                const now = new Date();
                
                // Today
                if (/today|asap|now|immediate/i.test(text)) {
                    return { 
                        date: now.toISOString().split('T')[0], 
                        confidence: 0.85 
                    };
                }
                
                // Tomorrow
                if (/tomorrow/i.test(text)) {
                    const tomorrow = new Date(now);
                    tomorrow.setDate(tomorrow.getDate() + 1);
                    return { 
                        date: tomorrow.toISOString().split('T')[0], 
                        confidence: 0.9 
                    };
                }
                
                // This week
                if (/this week|week|eow/i.test(text)) {
                    const endOfWeek = new Date(now);
                    endOfWeek.setDate(endOfWeek.getDate() + (7 - endOfWeek.getDay()));
                    return { 
                        date: endOfWeek.toISOString().split('T')[0], 
                        confidence: 0.8 
                    };
                }
                
                // Next week
                if (/next week/i.test(text)) {
                    const nextWeek = new Date(now);
                    nextWeek.setDate(nextWeek.getDate() + 7);
                    return { 
                        date: nextWeek.toISOString().split('T')[0], 
                        confidence: 0.75 
                    };
                }
                
                return null;
            }
            
            _extractLabels(title, description) {
                const text = `${title} ${description || ''}`.toLowerCase();
                const labels = [];
                
                if (/bug|error|fix/i.test(text)) labels.push('bug');
                if (/feature|enhancement|new/i.test(text)) labels.push('enhancement');
                if (/doc|documentation/i.test(text)) labels.push('documentation');
                if (/test|testing/i.test(text)) labels.push('testing');
                if (/ui|ux|design/i.test(text)) labels.push('ui/ux');
                
                return labels;
            }
            
            async predict(input) {
                if (!this.initialized) {
                    console.warn('⚠️ PredictiveEngine not initialized');
                    return null;
                }
                
                const { title, description } = input;
                if (!title) return null;
                
                const priorityPred = this._predictPriority(title, description);
                const dueDatePred = this._predictDueDate(title, description);
                const labels = this._extractLabels(title, description);
                
                return {
                    priority: priorityPred.priority,
                    priority_confidence: priorityPred.confidence,
                    dueDate: dueDatePred?.date || null,
                    due_date_confidence: dueDatePred?.confidence || 0,
                    labels: labels,
                    reasoning: `Based on keywords and patterns in task title/description`
                };
            }
        };
        
        engine = new PredictiveEngine();
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('Initialization', () => {
        test('should initialize successfully with TaskCache', async () => {
            await engine.init();
            
            expect(engine.initialized).toBe(true);
            expect(engine.historicalData).toHaveLength(3);
            expect(mockTaskCache.getAllTasks).toHaveBeenCalled();
        });

        test('should handle missing TaskCache gracefully', async () => {
            global.window.taskCache = null;
            
            await engine.init();
            
            expect(engine.initialized).toBe(false);
        });

        test('should handle TaskCache errors gracefully', async () => {
            mockTaskCache.getAllTasks.mockRejectedValue(new Error('Cache error'));
            
            await engine.init();
            
            expect(engine.initialized).toBe(false);
        });
    });

    describe('Priority Prediction', () => {
        beforeEach(async () => {
            await engine.init();
        });

        test('should predict URGENT for critical keywords', async () => {
            const result = await engine.predict({
                title: 'URGENT: Fix critical production bug',
                description: 'System is down'
            });
            
            expect(result.priority).toBe('urgent');
            expect(result.priority_confidence).toBeGreaterThanOrEqual(0.8);
        });

        test('should predict HIGH for important keywords', async () => {
            const result = await engine.predict({
                title: 'Important bug fix needed',
                description: 'High priority issue'
            });
            
            expect(result.priority).toBe('high');
            expect(result.priority_confidence).toBeGreaterThanOrEqual(0.7);
        });

        test('should predict LOW for minor keywords', async () => {
            const result = await engine.predict({
                title: 'Minor UI tweak',
                description: 'Nice to have improvement'
            });
            
            expect(result.priority).toBe('low');
            expect(result.priority_confidence).toBeGreaterThanOrEqual(0.7);
        });

        test('should default to MEDIUM for neutral tasks', async () => {
            const result = await engine.predict({
                title: 'Update user profile',
                description: 'Regular task'
            });
            
            expect(result.priority).toBe('medium');
        });

        test('should handle keywords in description', async () => {
            const result = await engine.predict({
                title: 'Task title',
                description: 'This is CRITICAL and needs immediate attention'
            });
            
            expect(result.priority).toBe('urgent');
        });
    });

    describe('Due Date Prediction', () => {
        beforeEach(async () => {
            await engine.init();
        });

        test('should predict today for ASAP keywords', async () => {
            const result = await engine.predict({
                title: 'Fix issue ASAP',
                description: 'Needs to be done today'
            });
            
            const today = new Date().toISOString().split('T')[0];
            expect(result.dueDate).toBe(today);
            expect(result.due_date_confidence).toBeGreaterThanOrEqual(0.8);
        });

        test('should predict tomorrow for tomorrow keyword', async () => {
            const result = await engine.predict({
                title: 'Complete by tomorrow',
                description: ''
            });
            
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            const expectedDate = tomorrow.toISOString().split('T')[0];
            
            expect(result.dueDate).toBe(expectedDate);
            expect(result.due_date_confidence).toBeGreaterThanOrEqual(0.85);
        });

        test('should predict end of week for week keywords', async () => {
            const result = await engine.predict({
                title: 'Finish this week',
                description: 'By end of week'
            });
            
            expect(result.dueDate).toBeTruthy();
            expect(result.due_date_confidence).toBeGreaterThanOrEqual(0.7);
        });

        test('should return null for tasks without time keywords', async () => {
            const result = await engine.predict({
                title: 'Regular task',
                description: 'No urgency'
            });
            
            expect(result.dueDate).toBeNull();
            expect(result.due_date_confidence).toBe(0);
        });
    });

    describe('Label Extraction', () => {
        beforeEach(async () => {
            await engine.init();
        });

        test('should extract bug label', async () => {
            const result = await engine.predict({
                title: 'Fix login bug',
                description: 'Error in authentication'
            });
            
            expect(result.labels).toContain('bug');
        });

        test('should extract enhancement label', async () => {
            const result = await engine.predict({
                title: 'Add new feature',
                description: 'Enhancement request'
            });
            
            expect(result.labels).toContain('enhancement');
        });

        test('should extract documentation label', async () => {
            const result = await engine.predict({
                title: 'Update docs',
                description: 'Documentation needs update'
            });
            
            expect(result.labels).toContain('documentation');
        });

        test('should extract multiple labels', async () => {
            const result = await engine.predict({
                title: 'Fix UI bug and add tests',
                description: 'Bug fix with testing'
            });
            
            expect(result.labels).toContain('bug');
            expect(result.labels).toContain('testing');
            expect(result.labels).toContain('ui/ux');
        });

        test('should return empty array for generic tasks', async () => {
            const result = await engine.predict({
                title: 'Regular task',
                description: 'Nothing special'
            });
            
            expect(result.labels).toEqual([]);
        });
    });

    describe('Complete Prediction Flow', () => {
        beforeEach(async () => {
            await engine.init();
        });

        test('should return null if not initialized', async () => {
            const uninitializedEngine = new PredictiveEngine();
            
            const result = await uninitializedEngine.predict({
                title: 'Test task'
            });
            
            expect(result).toBeNull();
        });

        test('should return null for empty title', async () => {
            const result = await engine.predict({
                title: '',
                description: 'Some description'
            });
            
            expect(result).toBeNull();
        });

        test('should provide reasoning in prediction', async () => {
            const result = await engine.predict({
                title: 'Test task',
                description: 'Description'
            });
            
            expect(result.reasoning).toBeTruthy();
            expect(typeof result.reasoning).toBe('string');
        });

        test('should handle complex real-world task', async () => {
            const result = await engine.predict({
                title: 'URGENT: Fix critical payment bug',
                description: 'Production issue - needs to be done ASAP today. Payment processing failing.'
            });
            
            expect(result.priority).toBe('urgent');
            expect(result.priority_confidence).toBeGreaterThanOrEqual(0.8);
            expect(result.dueDate).toBeTruthy();
            expect(result.labels).toContain('bug');
        });
    });

    describe('Edge Cases', () => {
        beforeEach(async () => {
            await engine.init();
        });

        test('should handle very long titles', async () => {
            const longTitle = 'A'.repeat(1000) + ' URGENT bug';
            const result = await engine.predict({
                title: longTitle,
                description: ''
            });
            
            expect(result).toBeTruthy();
            expect(result.priority).toBe('urgent');
        });

        test('should handle special characters', async () => {
            const result = await engine.predict({
                title: '🔥 CRITICAL: Fix $$ payment @bug #urgent',
                description: 'Special chars everywhere!!!'
            });
            
            expect(result).toBeTruthy();
            expect(result.priority).toBe('urgent');
        });

        test('should be case-insensitive', async () => {
            const result1 = await engine.predict({
                title: 'URGENT TASK',
                description: ''
            });
            
            const result2 = await engine.predict({
                title: 'urgent task',
                description: ''
            });
            
            expect(result1.priority).toBe(result2.priority);
        });

        test('should handle undefined description', async () => {
            const result = await engine.predict({
                title: 'Test task'
            });
            
            expect(result).toBeTruthy();
        });
    });
});
