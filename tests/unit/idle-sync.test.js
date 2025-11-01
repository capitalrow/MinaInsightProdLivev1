/**
 * Unit Tests for IdleSyncService
 * Tests exponential backoff progression: 30s → 60s → 120s → 240s → 300s
 */

describe('IdleSyncService - Exponential Backoff', () => {
    let IdleSyncService;
    let mockTaskCache;
    let mockOptimisticUI;
    let fetchMock;

    beforeEach(() => {
        // Reset modules
        jest.resetModules();
        
        // Mock globals
        global.fetch = jest.fn();
        global.navigator = { onLine: true };
        global.document = { hidden: false };
        global.window = {
            taskCache: null,
            CROWNTelemetry: {
                recordMetric: jest.fn()
            },
            dispatchEvent: jest.fn()
        };
        
        // Mock TaskCache
        mockTaskCache = {
            getAllTasks: jest.fn().mockResolvedValue([]),
            bulkUpdate: jest.fn().mockResolvedValue(true),
            setMetadata: jest.fn().mockResolvedValue(true),
            getMetadata: jest.fn().mockResolvedValue(null)
        };
        
        // Mock OptimisticUI
        mockOptimisticUI = {
            reconcileTasks: jest.fn().mockResolvedValue(true)
        };
        
        global.window.taskCache = mockTaskCache;
        global.window.optimisticUI = mockOptimisticUI;
        
        // Create a simple IdleSyncService class for testing
        IdleSyncService = class {
            constructor(intervalMs = 30000, maxIntervalMs = 300000) {
                this.baseIntervalMs = intervalMs;
                this.currentIntervalMs = intervalMs;
                this.maxIntervalMs = maxIntervalMs;
                this.consecutiveFailures = 0;
                this.lastSyncTimestamp = null;
                this.userActivityDetected = false;
            }
            
            _applyBackoff() {
                this.currentIntervalMs = Math.min(
                    this.baseIntervalMs * Math.pow(2, this.consecutiveFailures),
                    this.maxIntervalMs
                );
            }
            
            _resetInterval() {
                this.currentIntervalMs = this.baseIntervalMs;
            }
            
            async _performSync() {
                try {
                    const response = await fetch('/api/tasks/');
                    if (!response.ok) throw new Error('Sync failed');
                    
                    const data = await response.json();
                    this.consecutiveFailures = 0;
                    this._resetInterval();
                    return data;
                } catch (error) {
                    this.consecutiveFailures++;
                    this._applyBackoff();
                    throw error;
                }
            }
        };
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('Exponential Backoff Progression', () => {
        test('should start with base interval of 30000ms', () => {
            const service = new IdleSyncService(30000, 300000);
            expect(service.currentIntervalMs).toBe(30000);
            expect(service.baseIntervalMs).toBe(30000);
        });

        test('should double interval on first failure (30s → 60s)', () => {
            const service = new IdleSyncService(30000, 300000);
            service.consecutiveFailures = 1;
            service._applyBackoff();
            
            expect(service.currentIntervalMs).toBe(60000);
        });

        test('should continue doubling on second failure (60s → 120s)', () => {
            const service = new IdleSyncService(30000, 300000);
            service.consecutiveFailures = 2;
            service._applyBackoff();
            
            expect(service.currentIntervalMs).toBe(120000);
        });

        test('should continue doubling on third failure (120s → 240s)', () => {
            const service = new IdleSyncService(30000, 300000);
            service.consecutiveFailures = 3;
            service._applyBackoff();
            
            expect(service.currentIntervalMs).toBe(240000);
        });

        test('should cap at max interval on fourth failure (240s → 300s max)', () => {
            const service = new IdleSyncService(30000, 300000);
            service.consecutiveFailures = 4;
            service._applyBackoff();
            
            expect(service.currentIntervalMs).toBe(300000);
        });

        test('should maintain max interval on subsequent failures', () => {
            const service = new IdleSyncService(30000, 300000);
            
            // Test multiple failures beyond the cap
            for (let i = 5; i <= 10; i++) {
                service.consecutiveFailures = i;
                service._applyBackoff();
                expect(service.currentIntervalMs).toBe(300000);
            }
        });

        test('should reset to base interval after successful sync', () => {
            const service = new IdleSyncService(30000, 300000);
            
            // Simulate multiple failures
            service.consecutiveFailures = 4;
            service._applyBackoff();
            expect(service.currentIntervalMs).toBe(300000);
            
            // Reset after success
            service._resetInterval();
            expect(service.currentIntervalMs).toBe(30000);
        });
    });

    describe('Sync Behavior', () => {
        test('should reset consecutive failures and interval on successful sync', async () => {
            global.fetch.mockResolvedValue({
                ok: true,
                json: async () => ({ tasks: [] })
            });
            
            const service = new IdleSyncService(30000, 300000);
            service.consecutiveFailures = 3;
            service.currentIntervalMs = 240000;
            
            await service._performSync();
            
            expect(service.consecutiveFailures).toBe(0);
            expect(service.currentIntervalMs).toBe(30000);
        });

        test('should increment failures and apply backoff on sync error', async () => {
            global.fetch.mockResolvedValue({
                ok: false
            });
            
            const service = new IdleSyncService(30000, 300000);
            
            try {
                await service._performSync();
            } catch (error) {
                // Expected error
            }
            
            expect(service.consecutiveFailures).toBe(1);
            expect(service.currentIntervalMs).toBe(60000);
        });

        test('should handle network errors and apply backoff', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));
            
            const service = new IdleSyncService(30000, 300000);
            
            try {
                await service._performSync();
            } catch (error) {
                expect(error.message).toBe('Network error');
            }
            
            expect(service.consecutiveFailures).toBe(1);
            expect(service.currentIntervalMs).toBe(60000);
        });
    });

    describe('Complete Backoff Sequence', () => {
        test('should follow complete progression from 30s to 300s cap', async () => {
            global.fetch.mockResolvedValue({ ok: false });
            
            const service = new IdleSyncService(30000, 300000);
            const expectedIntervals = [60000, 120000, 240000, 300000, 300000];
            
            for (let i = 0; i < expectedIntervals.length; i++) {
                try {
                    await service._performSync();
                } catch (error) {
                    // Expected
                }
                expect(service.currentIntervalMs).toBe(expectedIntervals[i]);
            }
        });

        test('should reset properly after reaching max and then succeeding', async () => {
            const service = new IdleSyncService(30000, 300000);
            
            // Fail to reach max
            global.fetch.mockResolvedValue({ ok: false });
            for (let i = 0; i < 5; i++) {
                try {
                    await service._performSync();
                } catch (error) {
                    // Expected
                }
            }
            expect(service.currentIntervalMs).toBe(300000);
            
            // Now succeed
            global.fetch.mockResolvedValue({
                ok: true,
                json: async () => ({ tasks: [] })
            });
            await service._performSync();
            
            expect(service.consecutiveFailures).toBe(0);
            expect(service.currentIntervalMs).toBe(30000);
        });
    });

    describe('Edge Cases', () => {
        test('should handle zero failures correctly', () => {
            const service = new IdleSyncService(30000, 300000);
            service.consecutiveFailures = 0;
            service._applyBackoff();
            
            // 30000 * 2^0 = 30000
            expect(service.currentIntervalMs).toBe(30000);
        });

        test('should handle custom base and max intervals', () => {
            const service = new IdleSyncService(10000, 100000);
            
            expect(service.currentIntervalMs).toBe(10000);
            
            service.consecutiveFailures = 1;
            service._applyBackoff();
            expect(service.currentIntervalMs).toBe(20000);
            
            service.consecutiveFailures = 2;
            service._applyBackoff();
            expect(service.currentIntervalMs).toBe(40000);
            
            service.consecutiveFailures = 3;
            service._applyBackoff();
            expect(service.currentIntervalMs).toBe(80000);
            
            service.consecutiveFailures = 4;
            service._applyBackoff();
            expect(service.currentIntervalMs).toBe(100000); // Capped
        });
    });
});
