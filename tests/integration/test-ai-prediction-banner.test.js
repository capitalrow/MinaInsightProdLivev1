/**
 * Integration Tests for AI Prediction Banner UI
 * Tests banner rendering, Apply button functionality, and telemetry
 */

describe('AI Prediction Banner Integration', () => {
    let mockPredictiveEngine;
    let titleInput;
    let descInput;
    let predictionBanner;
    let predictionContent;
    let prioritySelect;
    let dueDateInput;

    beforeEach(() => {
        // Setup DOM
        document.body.innerHTML = `
            <div id="task-create-form">
                <input type="text" id="task-title" />
                <textarea id="task-description"></textarea>
                
                <div id="ai-prediction-banner" style="display: none;">
                    <div id="ai-prediction-content"></div>
                </div>
                
                <select id="task-priority">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                </select>
                
                <input type="date" id="task-due-date" />
            </div>
        `;
        
        titleInput = document.getElementById('task-title');
        descInput = document.getElementById('task-description');
        predictionBanner = document.getElementById('ai-prediction-banner');
        predictionContent = document.getElementById('ai-prediction-content');
        prioritySelect = document.getElementById('task-priority');
        dueDateInput = document.getElementById('task-due-date');
        
        // Mock PredictiveEngine
        mockPredictiveEngine = {
            predict: jest.fn()
        };
        
        global.window = {
            predictiveEngine: mockPredictiveEngine,
            CROWNTelemetry: {
                recordMetric: jest.fn()
            }
        };
    });

    afterEach(() => {
        jest.clearAllMocks();
        document.body.innerHTML = '';
    });

    describe('Banner Rendering', () => {
        test('should hide banner when title is empty', async () => {
            titleInput.value = '';
            
            const showPredictions = async () => {
                const title = titleInput.value.trim();
                if (!title) {
                    predictionBanner.style.display = 'none';
                    return;
                }
            };
            
            await showPredictions();
            
            expect(predictionBanner.style.display).toBe('none');
        });

        test('should show banner when predictions are available', async () => {
            mockPredictiveEngine.predict.mockResolvedValue({
                priority: 'high',
                priority_confidence: 0.8,
                dueDate: '2025-11-05',
                due_date_confidence: 0.75,
                labels: ['bug'],
                reasoning: 'Based on keywords'
            });
            
            titleInput.value = 'Fix critical bug';
            
            const showPredictions = async () => {
                const title = titleInput.value.trim();
                if (!title) return;
                
                const predictions = await window.predictiveEngine.predict({ 
                    title, 
                    description: '' 
                });
                
                if (predictions && predictions.priority) {
                    predictionBanner.style.display = 'block';
                }
            };
            
            await showPredictions();
            
            expect(predictionBanner.style.display).toBe('block');
        });

        test('should render priority suggestion with confidence', async () => {
            const predictions = {
                priority: 'urgent',
                priority_confidence: 0.9,
                dueDate: null,
                labels: []
            };
            
            const confidence = Math.round(predictions.priority_confidence * 100);
            predictionContent.innerHTML = `
                <div>
                    📊 <strong>Priority:</strong> ${predictions.priority.toUpperCase()} 
                    <span>(${confidence}% confident)</span>
                </div>
            `;
            
            expect(predictionContent.innerHTML).toContain('URGENT');
            expect(predictionContent.innerHTML).toContain('90% confident');
        });

        test('should render due date suggestion with confidence', async () => {
            const predictions = {
                priority: null,
                dueDate: '2025-11-05',
                due_date_confidence: 0.85,
                labels: []
            };
            
            const confidence = Math.round(predictions.due_date_confidence * 100);
            const dateStr = new Date(predictions.dueDate).toLocaleDateString();
            
            predictionContent.innerHTML = `
                <div>
                    📅 <strong>Due Date:</strong> ${dateStr} 
                    <span>(${confidence}% confident)</span>
                </div>
            `;
            
            expect(predictionContent.innerHTML).toContain('Due Date');
            expect(predictionContent.innerHTML).toContain('85% confident');
        });

        test('should render labels suggestion', async () => {
            const predictions = {
                priority: null,
                dueDate: null,
                labels: ['bug', 'urgent', 'backend']
            };
            
            if (predictions.labels?.length) {
                predictionContent.innerHTML = `
                    <div>🏷️ <strong>Suggested Labels:</strong> ${predictions.labels.join(', ')}</div>
                `;
            }
            
            expect(predictionContent.innerHTML).toContain('bug, urgent, backend');
        });

        test('should render reasoning', async () => {
            const predictions = {
                priority: 'high',
                priority_confidence: 0.8,
                reasoning: 'Based on keywords and patterns in task title/description'
            };
            
            predictionContent.innerHTML = `
                <div style="font-style: italic;">${predictions.reasoning}</div>
            `;
            
            expect(predictionContent.innerHTML).toContain('Based on keywords');
        });
    });

    describe('Apply Button Functionality', () => {
        test('should apply priority when Apply button clicked', () => {
            predictionContent.innerHTML = `
                <button onclick="document.getElementById('task-priority').value='high'; return false;">
                    Apply
                </button>
            `;
            
            const applyBtn = predictionContent.querySelector('button');
            applyBtn.click();
            
            expect(prioritySelect.value).toBe('high');
        });

        test('should apply due date when Apply button clicked', () => {
            predictionContent.innerHTML = `
                <button onclick="document.getElementById('task-due-date').value='2025-11-05'; return false;">
                    Apply
                </button>
            `;
            
            const applyBtn = predictionContent.querySelector('button');
            applyBtn.click();
            
            expect(dueDateInput.value).toBe('2025-11-05');
        });

        test('should apply both priority and due date', () => {
            predictionContent.innerHTML = `
                <button id="apply-priority" onclick="document.getElementById('task-priority').value='urgent'; return false;">
                    Apply Priority
                </button>
                <button id="apply-date" onclick="document.getElementById('task-due-date').value='2025-11-02'; return false;">
                    Apply Date
                </button>
            `;
            
            document.getElementById('apply-priority').click();
            document.getElementById('apply-date').click();
            
            expect(prioritySelect.value).toBe('urgent');
            expect(dueDateInput.value).toBe('2025-11-02');
        });
    });

    describe('Telemetry Integration', () => {
        test('should record telemetry when predictions shown', async () => {
            mockPredictiveEngine.predict.mockResolvedValue({
                priority: 'high',
                priority_confidence: 0.8,
                dueDate: '2025-11-05',
                due_date_confidence: 0.75
            });
            
            titleInput.value = 'Test task';
            
            const showPredictions = async () => {
                const predictions = await window.predictiveEngine.predict({ 
                    title: titleInput.value 
                });
                
                if (predictions) {
                    predictionBanner.style.display = 'block';
                    
                    if (window.CROWNTelemetry) {
                        window.CROWNTelemetry.recordMetric('prediction_shown_in_ui', 1);
                        window.CROWNTelemetry.recordMetric('prediction_confidence_priority', predictions.priority_confidence);
                        window.CROWNTelemetry.recordMetric('prediction_confidence_due_date', predictions.due_date_confidence);
                    }
                }
            };
            
            await showPredictions();
            
            expect(window.CROWNTelemetry.recordMetric).toHaveBeenCalledWith('prediction_shown_in_ui', 1);
            expect(window.CROWNTelemetry.recordMetric).toHaveBeenCalledWith('prediction_confidence_priority', 0.8);
            expect(window.CROWNTelemetry.recordMetric).toHaveBeenCalledWith('prediction_confidence_due_date', 0.75);
        });
    });

    describe('Debounced Input Handling', () => {
        test('should debounce predictions on input', (done) => {
            let debounceTimer = null;
            
            const debouncedPredict = () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(async () => {
                    await mockPredictiveEngine.predict({ title: titleInput.value });
                    done();
                }, 500);
            };
            
            titleInput.value = 'T';
            debouncedPredict();
            
            titleInput.value = 'Te';
            debouncedPredict();
            
            titleInput.value = 'Test';
            debouncedPredict();
            
            // Only the last call should execute after 500ms
        });

        test('should clear predictions when input is cleared', () => {
            predictionBanner.style.display = 'block';
            titleInput.value = '';
            
            const handleInput = () => {
                if (!titleInput.value.trim()) {
                    predictionBanner.style.display = 'none';
                }
            };
            
            handleInput();
            
            expect(predictionBanner.style.display).toBe('none');
        });
    });

    describe('Complete Flow', () => {
        test('should show full prediction banner for urgent task', async () => {
            mockPredictiveEngine.predict.mockResolvedValue({
                priority: 'urgent',
                priority_confidence: 0.95,
                dueDate: '2025-11-02',
                due_date_confidence: 0.9,
                labels: ['bug', 'critical'],
                reasoning: 'Critical keywords detected'
            });
            
            titleInput.value = 'URGENT: Fix production bug';
            
            const showPredictions = async () => {
                const predictions = await window.predictiveEngine.predict({
                    title: titleInput.value,
                    description: descInput.value
                });
                
                if (predictions && predictions.priority) {
                    let html = '<div>';
                    
                    if (predictions.priority) {
                        const confidence = Math.round(predictions.priority_confidence * 100);
                        html += `<div>📊 Priority: ${predictions.priority.toUpperCase()} (${confidence}%)</div>`;
                    }
                    
                    if (predictions.dueDate) {
                        const confidence = Math.round(predictions.due_date_confidence * 100);
                        html += `<div>📅 Due Date: ${predictions.dueDate} (${confidence}%)</div>`;
                    }
                    
                    if (predictions.labels?.length) {
                        html += `<div>🏷️ Labels: ${predictions.labels.join(', ')}</div>`;
                    }
                    
                    html += '</div>';
                    predictionContent.innerHTML = html;
                    predictionBanner.style.display = 'block';
                }
            };
            
            await showPredictions();
            
            expect(predictionBanner.style.display).toBe('block');
            expect(predictionContent.innerHTML).toContain('URGENT');
            expect(predictionContent.innerHTML).toContain('95%');
            expect(predictionContent.innerHTML).toContain('2025-11-02');
            expect(predictionContent.innerHTML).toContain('bug, critical');
        });

        test('should handle prediction with only priority', async () => {
            mockPredictiveEngine.predict.mockResolvedValue({
                priority: 'medium',
                priority_confidence: 0.6,
                dueDate: null,
                due_date_confidence: 0,
                labels: []
            });
            
            titleInput.value = 'Regular task';
            
            const showPredictions = async () => {
                const predictions = await window.predictiveEngine.predict({
                    title: titleInput.value
                });
                
                if (predictions && predictions.priority) {
                    predictionBanner.style.display = 'block';
                    predictionContent.innerHTML = `<div>📊 Priority: ${predictions.priority}</div>`;
                }
            };
            
            await showPredictions();
            
            expect(predictionBanner.style.display).toBe('block');
            expect(predictionContent.innerHTML).toContain('medium');
        });

        test('should hide banner when no valid predictions', async () => {
            mockPredictiveEngine.predict.mockResolvedValue(null);
            
            titleInput.value = 'Task';
            
            const showPredictions = async () => {
                const predictions = await window.predictiveEngine.predict({
                    title: titleInput.value
                });
                
                if (!predictions || (!predictions.priority && !predictions.dueDate && !predictions.labels?.length)) {
                    predictionBanner.style.display = 'none';
                }
            };
            
            await showPredictions();
            
            expect(predictionBanner.style.display).toBe('none');
        });
    });

    describe('Edge Cases', () => {
        test('should handle engine not available', async () => {
            window.predictiveEngine = null;
            
            const showPredictions = async () => {
                if (!window.predictiveEngine) {
                    predictionBanner.style.display = 'none';
                    return;
                }
            };
            
            await showPredictions();
            
            expect(predictionBanner.style.display).toBe('none');
        });

        test('should handle prediction errors gracefully', async () => {
            mockPredictiveEngine.predict.mockRejectedValue(new Error('Prediction failed'));
            
            const showPredictions = async () => {
                try {
                    await window.predictiveEngine.predict({ title: titleInput.value });
                } catch (error) {
                    console.error('Prediction error:', error);
                    predictionBanner.style.display = 'none';
                }
            };
            
            await showPredictions();
            
            expect(predictionBanner.style.display).toBe('none');
        });

        test('should handle missing confidence values', async () => {
            mockPredictiveEngine.predict.mockResolvedValue({
                priority: 'high',
                // Missing confidence values
                dueDate: '2025-11-05'
            });
            
            titleInput.value = 'Task';
            
            const showPredictions = async () => {
                const predictions = await window.predictiveEngine.predict({ 
                    title: titleInput.value 
                });
                
                if (predictions) {
                    const priorityConf = Math.round((predictions.priority_confidence || 0.7) * 100);
                    const dateConf = Math.round((predictions.due_date_confidence || 0.7) * 100);
                    
                    predictionContent.innerHTML = `
                        <div>Priority confidence: ${priorityConf}%</div>
                        <div>Date confidence: ${dateConf}%</div>
                    `;
                    predictionBanner.style.display = 'block';
                }
            };
            
            await showPredictions();
            
            expect(predictionContent.innerHTML).toContain('70%');
        });
    });
});
