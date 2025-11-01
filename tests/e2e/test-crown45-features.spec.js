/**
 * End-to-End Tests for CROWN⁴.5 Features
 * Tests actual production code in real browser environment:
 * - Idle Sync with Exponential Backoff
 * - Predictive Engine with visible UI
 * - Emotional Animations
 */

const { test, expect } = require('@playwright/test');

test.describe('CROWN⁴.5 Features E2E Tests', () => {
    let page;

    test.beforeEach(async ({ page: p }) => {
        page = p;
        // Navigate to tasks page
        await page.goto('/dashboard/tasks');
        
        // Wait for page to load
        await page.waitForLoadState('networkidle');
        
        // Wait for CROWN modules to initialize
        await page.waitForFunction(() => {
            return window.predictiveEngine && 
                   window.idleSyncService && 
                   window.emotionalAnimations;
        }, { timeout: 10000 });
    });

    test.describe('Idle Sync Exponential Backoff', () => {
        test('should initialize with 30s base interval', async () => {
            const baseInterval = await page.evaluate(() => {
                return window.idleSyncService.baseIntervalMs;
            });
            
            expect(baseInterval).toBe(30000);
        });

        test('should have current interval equal to base interval initially', async () => {
            const currentInterval = await page.evaluate(() => {
                return window.idleSyncService.currentIntervalMs;
            });
            
            expect(currentInterval).toBe(30000);
        });

        test('should have max interval of 300s', async () => {
            const maxInterval = await page.evaluate(() => {
                return window.idleSyncService.maxIntervalMs;
            });
            
            expect(maxInterval).toBe(300000);
        });

        test('should double interval on first failure (30s → 60s)', async () => {
            const result = await page.evaluate(() => {
                window.idleSyncService.consecutiveFailures = 1;
                window.idleSyncService._applyBackoff();
                return window.idleSyncService.currentIntervalMs;
            });
            
            expect(result).toBe(60000);
        });

        test('should continue doubling on second failure (60s → 120s)', async () => {
            const result = await page.evaluate(() => {
                window.idleSyncService.consecutiveFailures = 2;
                window.idleSyncService._applyBackoff();
                return window.idleSyncService.currentIntervalMs;
            });
            
            expect(result).toBe(120000);
        });

        test('should continue doubling on third failure (120s → 240s)', async () => {
            const result = await page.evaluate(() => {
                window.idleSyncService.consecutiveFailures = 3;
                window.idleSyncService._applyBackoff();
                return window.idleSyncService.currentIntervalMs;
            });
            
            expect(result).toBe(240000);
        });

        test('should cap at 300s on fourth failure', async () => {
            const result = await page.evaluate(() => {
                window.idleSyncService.consecutiveFailures = 4;
                window.idleSyncService._applyBackoff();
                return window.idleSyncService.currentIntervalMs;
            });
            
            expect(result).toBe(300000);
        });

        test('should maintain 300s max on further failures', async () => {
            const result = await page.evaluate(() => {
                window.idleSyncService.consecutiveFailures = 10;
                window.idleSyncService._applyBackoff();
                return window.idleSyncService.currentIntervalMs;
            });
            
            expect(result).toBe(300000);
        });

        test('should reset to base interval after successful sync', async () => {
            const result = await page.evaluate(() => {
                // Simulate failures
                window.idleSyncService.consecutiveFailures = 4;
                window.idleSyncService._applyBackoff();
                
                // Reset on success
                window.idleSyncService._resetInterval();
                
                return window.idleSyncService.currentIntervalMs;
            });
            
            expect(result).toBe(30000);
        });
    });

    test.describe('Predictive Engine', () => {
        test('should be initialized', async () => {
            const isInitialized = await page.evaluate(() => {
                return window.predictiveEngine.initialized;
            });
            
            expect(isInitialized).toBe(true);
        });

        test('should predict URGENT for critical keywords', async () => {
            const prediction = await page.evaluate(async () => {
                return await window.predictiveEngine.predict({
                    title: 'URGENT: Fix critical production bug',
                    description: 'System is down ASAP'
                });
            });
            
            expect(prediction.priority).toBe('urgent');
            expect(prediction.priority_confidence).toBeGreaterThan(0.7);
        });

        test('should predict HIGH for important keywords', async () => {
            const prediction = await page.evaluate(async () => {
                return await window.predictiveEngine.predict({
                    title: 'Important bug fix needed',
                    description: 'High priority issue'
                });
            });
            
            expect(prediction.priority).toBe('high');
            expect(prediction.priority_confidence).toBeGreaterThan(0.6);
        });

        test('should predict LOW for minor keywords', async () => {
            const prediction = await page.evaluate(async () => {
                return await window.predictiveEngine.predict({
                    title: 'Minor UI tweak',
                    description: 'Nice to have'
                });
            });
            
            expect(prediction.priority).toBe('low');
        });

        test('should extract bug label', async () => {
            const prediction = await page.evaluate(async () => {
                return await window.predictiveEngine.predict({
                    title: 'Fix login bug',
                    description: 'Error in authentication'
                });
            });
            
            expect(prediction.labels).toContain('bug');
        });

        test('should return null for empty title', async () => {
            const prediction = await page.evaluate(async () => {
                return await window.predictiveEngine.predict({
                    title: '',
                    description: 'Some description'
                });
            });
            
            expect(prediction).toBeNull();
        });
    });

    test.describe('AI Prediction Banner UI', () => {
        test('should show prediction banner when typing task title', async () => {
            // Open task creation modal
            await page.click('text=New Task');
            
            // Wait for modal
            await page.waitForSelector('#task-modal-overlay.active');
            
            // Type urgent task
            await page.fill('#task-title', 'URGENT: Fix critical bug ASAP');
            
            // Wait for debounced prediction (500ms + buffer)
            await page.waitForTimeout(700);
            
            // Check if prediction banner is visible
            const bannerVisible = await page.evaluate(() => {
                const banner = document.getElementById('ai-prediction-banner');
                return banner && banner.style.display === 'block';
            });
            
            expect(bannerVisible).toBe(true);
        });

        test('should render priority suggestion in banner', async () => {
            await page.click('text=New Task');
            await page.waitForSelector('#task-modal-overlay.active');
            
            await page.fill('#task-title', 'URGENT: Critical issue');
            await page.waitForTimeout(700);
            
            const bannerContent = await page.textContent('#ai-prediction-content');
            
            expect(bannerContent).toContain('Priority');
            expect(bannerContent).toContain('URGENT');
        });

        test('should apply priority when Apply button clicked', async () => {
            await page.click('text=New Task');
            await page.waitForSelector('#task-modal-overlay.active');
            
            await page.fill('#task-title', 'HIGH priority task');
            await page.waitForTimeout(700);
            
            // Click Apply button for priority
            await page.click('#ai-prediction-content button:has-text("Apply")');
            
            // Check if priority was set
            const priorityValue = await page.inputValue('#task-priority');
            
            expect(['high', 'urgent']).toContain(priorityValue);
        });

        test('should hide banner when input is cleared', async () => {
            await page.click('text=New Task');
            await page.waitForSelector('#task-modal-overlay.active');
            
            await page.fill('#task-title', 'URGENT task');
            await page.waitForTimeout(700);
            
            // Clear input
            await page.fill('#task-title', '');
            await page.waitForTimeout(100);
            
            const bannerVisible = await page.evaluate(() => {
                const banner = document.getElementById('ai-prediction-banner');
                return banner && banner.style.display === 'block';
            });
            
            expect(bannerVisible).toBe(false);
        });
    });

    test.describe('Emotional Animations', () => {
        test('should have EmotionalAnimations instance available', async () => {
            const hasAnimations = await page.evaluate(() => {
                return typeof window.emotionalAnimations !== 'undefined';
            });
            
            expect(hasAnimations).toBe(true);
        });

        test('should have injected animation styles', async () => {
            const hasStyles = await page.evaluate(() => {
                return document.getElementById('emotional-animations-styles') !== null;
            });
            
            expect(hasStyles).toBe(true);
        });

        test('should have pulse animation defined in styles', async () => {
            const hasPulseAnimation = await page.evaluate(() => {
                const styles = document.getElementById('emotional-animations-styles');
                return styles && styles.textContent.includes('@keyframes pulse');
            });
            
            expect(hasPulseAnimation).toBe(true);
        });

        test('should have popIn animation defined in styles', async () => {
            const hasPopInAnimation = await page.evaluate(() => {
                const styles = document.getElementById('emotional-animations-styles');
                return styles && styles.textContent.includes('@keyframes popIn');
            });
            
            expect(hasPopInAnimation).toBe(true);
        });

        test('should have glow animation defined in styles', async () => {
            const hasGlowAnimation = await page.evaluate(() => {
                const styles = document.getElementById('emotional-animations-styles');
                return styles && styles.textContent.includes('@keyframes glow');
            });
            
            expect(hasGlowAnimation).toBe(true);
        });

        test('should have gradientPulse animation defined in styles', async () => {
            const hasGradientPulseAnimation = await page.evaluate(() => {
                const styles = document.getElementById('emotional-animations-styles');
                return styles && styles.textContent.includes('@keyframes gradientPulse');
            });
            
            expect(hasGradientPulseAnimation).toBe(true);
        });
    });

    test.describe('Telemetry Integration', () => {
        test('should record prediction telemetry when banner shown', async () => {
            // Listen for telemetry events
            const telemetryEvents = [];
            await page.exposeFunction('captureMetric', (metric, value) => {
                telemetryEvents.push({ metric, value });
            });
            
            await page.evaluate(() => {
                const originalRecordMetric = window.CROWNTelemetry?.recordMetric;
                if (originalRecordMetric) {
                    window.CROWNTelemetry.recordMetric = (metric, value) => {
                        window.captureMetric(metric, value);
                        return originalRecordMetric.call(window.CROWNTelemetry, metric, value);
                    };
                }
            });
            
            // Trigger prediction
            await page.click('text=New Task');
            await page.waitForSelector('#task-modal-overlay.active');
            await page.fill('#task-title', 'URGENT task');
            await page.waitForTimeout(700);
            
            // Check for prediction telemetry
            const hasPredictionMetric = telemetryEvents.some(e => 
                e.metric === 'prediction_shown_in_ui'
            );
            
            expect(hasPredictionMetric).toBe(true);
        });
    });
});
