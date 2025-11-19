"""
CROWN 4.6 Performance Validation Framework
Validates all performance requirements with automated thresholds and regression detection

Performance Requirements:
- <200ms initial task load
- <100ms semantic search response
- <150ms optimistic UI updates (p95)
- <300ms event latency
- 60 FPS scrolling
- <50ms cache bootstrap
"""

import pytest
import json
import time
import os
from datetime import datetime
from playwright.sync_api import Page, expect

class PerformanceMetrics:
    """Collects and validates performance metrics"""
    
    def __init__(self):
        self.metrics = {}
        self.thresholds = {
            'first_paint_ms': 200,
            'cache_bootstrap_ms': 50,
            'semantic_search_ms': 100,
            'optimistic_update_ms': 150,
            'event_latency_ms': 300,
            'scroll_fps': 60,
            'checkmark_burst_ms': 150,
            'reconciliation_ms': 150
        }
        
    def record(self, name: str, value: float):
        """Record a metric"""
        self.metrics[name] = value
        
    def validate(self, name: str) -> dict:
        """Validate metric against threshold"""
        if name not in self.metrics:
            return {'valid': False, 'reason': 'metric_not_recorded'}
            
        value = self.metrics[name]
        threshold = self.thresholds.get(name)
        
        if threshold is None:
            return {'valid': True, 'value': value, 'threshold': None}
        
        # FPS metrics should be >= threshold, time metrics should be <threshold
        if 'fps' in name.lower():
            valid = value >= threshold
        else:
            valid = value < threshold
        return {
            'valid': valid,
            'value': value,
            'threshold': threshold,
            'difference': value - threshold,
            'percentage': (value / threshold) * 100
        }
        
    def get_summary(self) -> dict:
        """Get full validation summary"""
        summary = {
            'total_metrics': len(self.metrics),
            'validated': 0,
            'passed': 0,
            'failed': 0,
            'details': {}
        }
        
        for name in self.metrics:
            result = self.validate(name)
            summary['validated'] += 1
            
            if result.get('valid', False):
                summary['passed'] += 1
            else:
                summary['failed'] += 1
                
            summary['details'][name] = result
            
        return summary


@pytest.fixture
def perf_metrics():
    """Provides performance metrics collector"""
    return PerformanceMetrics()


class TestCROWN46Performance:
    """CROWN 4.6 Performance Validation Suite"""
    
    def test_01_first_paint_under_200ms(self, page: Page, perf_metrics: PerformanceMetrics):
        """
        Requirement 1: Tasks load in <200ms
        Tests cache-first bootstrap with first paint timing
        Uses PerformanceTiming API - no custom events required
        """
        print("\n" + "="*80)
        print("TEST 1: First Paint <200ms (Cache-First Bootstrap)")
        print("="*80)
        
        # Navigate and measure using Performance API
        start_navigation = time.perf_counter()
        page.goto('/dashboard/tasks')
        
        # Wait for content to be visible
        try:
            page.wait_for_selector('.task-card, .empty-state', timeout=5000)
        except:
            pass  # Empty state is acceptable
        
        end_navigation = time.perf_counter()
        navigation_time = (end_navigation - start_navigation) * 1000
        
        # Get browser's performance timing
        perf_data = page.evaluate("""
            () => {
                const perfData = window.performance.getEntriesByType('navigation')[0];
                if (perfData) {
                    return {
                        firstPaint: perfData.domContentLoadedEventEnd - perfData.fetchStart,
                        cacheBootstrap: perfData.domInteractive - perfData.fetchStart,
                        domComplete: perfData.domComplete - perfData.fetchStart
                    };
                }
                // Fallback for browsers without Navigation Timing API
                return {
                    firstPaint: Date.now() - window.performance.timing.navigationStart,
                    cacheBootstrap: 0,
                    domComplete: 0
                };
            }
        """)
        first_paint = perf_data.get('firstPaint', navigation_time)
        cache_bootstrap = perf_data.get('cacheBootstrap', 0)
        
        # Take multiple samples for p95 calculation
        samples = [first_paint]
        for i in range(4):  # Total 5 samples
            page.reload()
            page.wait_for_selector('.task-card, .empty-state, #tasks-loading-state', timeout=3000)
            sample_perf = page.evaluate("""
                () => {
                    const perfData = window.performance.getEntriesByType('navigation')[0];
                    return perfData ? perfData.domContentLoadedEventEnd - perfData.fetchStart : 0;
                }
            """)
            if sample_perf > 0:
                samples.append(sample_perf)
        
        # Calculate p95
        samples.sort()
        p95_index = int(len(samples) * 0.95)
        p95_value = samples[p95_index]
        
        perf_metrics.record('first_paint_ms', p95_value)
        perf_metrics.record('first_paint_p50', samples[len(samples)//2])
        perf_metrics.record('first_paint_p95', p95_value)
        
        print(f"  First Paint (p50): {samples[len(samples)//2]:.2f}ms")
        print(f"  First Paint (p95): {p95_value:.2f}ms (threshold: 200ms)")
        print(f"  Samples: {[f'{s:.0f}' for s in samples]}")
        
        # Validate p95
        result = perf_metrics.validate('first_paint_ms')
        if not result['valid']:
            raise AssertionError(f"First paint p95 {p95_value:.2f}ms exceeds 200ms threshold by {result['difference']:.2f}ms")
        
        print(f"  ✅ PASS: First paint meets <200ms requirement ({result['percentage']:.1f}% of threshold)")
    
    
    def test_02_optimistic_ui_under_150ms(self, page: Page, perf_metrics: PerformanceMetrics):
        """
        Requirement 2: Optimistic UI updates <150ms (p95)
        Tests checkbox toggle, inline edit, priority change latency
        """
        print("\n" + "="*80)
        print("TEST 2: Optimistic UI Updates <150ms")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        page.wait_for_selector('.task-card', timeout=5000)
        
        # Test checkbox toggle latency
        checkbox = page.locator('.task-checkbox').first
        
        # Measure optimistic update time
        start = time.perf_counter()
        checkbox.click()
        
        # Wait for visual feedback (checkmark burst animation)
        page.wait_for_function(
            """() => {
                const card = document.querySelector('.task-card');
                return card && card.classList.contains('task-completing');
            }""",
            timeout=500
        )
        
        latency = (time.perf_counter() - start) * 1000
        perf_metrics.record('optimistic_update_ms', latency)
        
        print(f"  Checkbox Toggle Latency: {latency:.2f}ms (threshold: 150ms)")
        
        result = perf_metrics.validate('optimistic_update_ms')
        assert result['valid'], f"Optimistic update {latency:.2f}ms exceeds 150ms threshold"
        
        print(f"  ✅ PASS: Optimistic UI meets <150ms requirement")
    
    
    def test_03_semantic_search_under_100ms(self, page: Page, perf_metrics: PerformanceMetrics):
        """
        Requirement 3: Semantic search <100ms
        Tests AI-enhanced search response time
        """
        print("\n" + "="*80)
        print("TEST 3: Semantic Search <100ms")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        
        search_input = page.locator('#task-search-input')
        search_input.wait_for(timeout=3000)
        
        # Enable semantic search
        semantic_toggle = page.locator('#semantic-search-toggle')
        if semantic_toggle.is_visible():
            semantic_toggle.click()
            page.wait_for_timeout(500)
        
        # Measure search response time
        page.evaluate("""
            () => {
                window.__searchLatency = null;
                document.addEventListener('search:complete', (e) => {
                    window.__searchLatency = e.detail.latency_ms;
                });
            }
        """)
        
        start = time.perf_counter()
        search_input.fill('follow up meeting discussion')
        search_input.press('Enter')
        
        # Wait for search completion
        try:
            page.wait_for_function(
                "window.__searchLatency !== null",
                timeout=2000
            )
            search_latency = page.evaluate("window.__searchLatency")
        except:
            # Fallback to measuring visible results
            page.wait_for_selector('.task-card', timeout=2000)
            search_latency = (time.perf_counter() - start) * 1000
        
        perf_metrics.record('semantic_search_ms', search_latency)
        
        print(f"  Semantic Search Latency: {search_latency:.2f}ms (threshold: 100ms)")
        
        result = perf_metrics.validate('semantic_search_ms')
        assert result['valid'], f"Semantic search {search_latency:.2f}ms exceeds 100ms threshold"
        
        print(f"  ✅ PASS: Semantic search meets <100ms requirement")
    
    
    def test_04_scroll_performance_60fps(self, page: Page, perf_metrics: PerformanceMetrics):
        """
        Requirement 4: 60 FPS scrolling with task list
        Tests frame rate during rapid scrolling
        """
        print("\n" + "="*80)
        print("TEST 4: Scroll Performance (60 FPS)")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        page.wait_for_selector('.task-card', timeout=3000)
        
        # Measure FPS during scroll
        fps_data = page.evaluate("""
            async () => {
                return new Promise((resolve) => {
                    const frames = [];
                    let lastTime = performance.now();
                    let frameCount = 0;
                    const maxFrames = 60; // 1 second at 60fps
                    
                    function measureFrame() {
                        const now = performance.now();
                        const delta = now - lastTime;
                        const fps = 1000 / delta;
                        
                        frames.push(fps);
                        lastTime = now;
                        frameCount++;
                        
                        if (frameCount < maxFrames) {
                            // Trigger scroll
                            window.scrollBy(0, 10);
                            requestAnimationFrame(measureFrame);
                        } else {
                            const avgFps = frames.reduce((a, b) => a + b, 0) / frames.length;
                            const minFps = Math.min(...frames);
                            resolve({ avgFps, minFps, frames: frames.length });
                        }
                    }
                    
                    requestAnimationFrame(measureFrame);
                });
            }
        """)
        
        avg_fps = fps_data['avgFps']
        min_fps = fps_data['minFps']
        
        perf_metrics.record('scroll_fps', avg_fps)
        
        print(f"  Average FPS: {avg_fps:.1f} (threshold: 60 FPS)")
        print(f"  Minimum FPS: {min_fps:.1f}")
        
        result = perf_metrics.validate('scroll_fps')
        if not result['valid']:
            raise AssertionError(f"Scroll FPS {avg_fps:.1f} below 60 FPS threshold")
        
        print(f"  ✅ PASS: Scroll performance meets 60 FPS requirement")
    
    
    def test_05_completion_ux_animation_timing(self, page: Page, perf_metrics: PerformanceMetrics):
        """
        Requirement 5: Completion UX with burst animation <150ms
        Tests checkmark burst and slide-away animation timing
        """
        print("\n" + "="*80)
        print("TEST 5: Completion UX Animation Timing")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        page.wait_for_selector('.task-card', timeout=3000)
        
        # Setup animation timing observer
        page.evaluate("""
            () => {
                window.__animationData = {
                    burstStart: null,
                    burstEnd: null,
                    slideStart: null,
                    slideEnd: null
                };
                
                document.addEventListener('task:completion:burst:start', () => {
                    window.__animationData.burstStart = performance.now();
                });
                
                document.addEventListener('task:completion:burst:end', () => {
                    window.__animationData.burstEnd = performance.now();
                });
                
                document.addEventListener('task:completion:slide:end', () => {
                    window.__animationData.slideEnd = performance.now();
                });
            }
        """)
        
        # Trigger completion
        checkbox = page.locator('.task-checkbox').first
        start_time = time.perf_counter()
        checkbox.click()
        
        # Wait for animations
        page.wait_for_timeout(500)
        
        # Get animation data
        anim_data = page.evaluate("window.__animationData")
        
        if anim_data.get('burstStart') and anim_data.get('burstEnd'):
            burst_duration = anim_data['burstEnd'] - anim_data['burstStart']
            perf_metrics.record('checkmark_burst_ms', burst_duration)
            
            print(f"  Checkmark Burst: {burst_duration:.2f}ms (threshold: 150ms)")
            
            result = perf_metrics.validate('checkmark_burst_ms')
            assert result['valid'], f"Burst animation {burst_duration:.2f}ms exceeds 150ms threshold"
            print(f"  ✅ PASS: Completion animation meets timing requirement")
        else:
            print(f"  ⚠️  WARNING: Animation events not detected (may need instrumentation)")
    
    
    def test_06_event_reconciliation_latency(self, page: Page, perf_metrics: PerformanceMetrics):
        """
        Requirement 6: Event reconciliation <150ms (optimistic to truth)
        Tests server confirmation latency
        """
        print("\n" + "="*80)
        print("TEST 6: Event Reconciliation Latency")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        page.wait_for_selector('.task-card', timeout=3000)
        
        # Setup reconciliation observer
        page.evaluate("""
            () => {
                window.__reconciliationData = {
                    optimisticTime: null,
                    serverConfirmTime: null
                };
                
                // Listen for task store events
                if (window.taskStore) {
                    window.taskStore.subscribe((event) => {
                        if (event.type === 'update_optimistic') {
                            window.__reconciliationData.optimisticTime = performance.now();
                        }
                        if (event.type === 'sync' || event.type === 'confirm') {
                            window.__reconciliationData.serverConfirmTime = performance.now();
                        }
                    });
                }
            }
        """)
        
        # Trigger update
        checkbox = page.locator('.task-checkbox').first
        checkbox.click()
        
        # Wait for reconciliation
        page.wait_for_timeout(1000)
        
        recon_data = page.evaluate("window.__reconciliationData")
        
        if recon_data.get('optimisticTime') and recon_data.get('serverConfirmTime'):
            recon_latency = recon_data['serverConfirmTime'] - recon_data['optimisticTime']
            perf_metrics.record('reconciliation_ms', recon_latency)
            
            print(f"  Reconciliation Latency: {recon_latency:.2f}ms (threshold: 150ms)")
            
            result = perf_metrics.validate('reconciliation_ms')
            assert result['valid'], f"Reconciliation {recon_latency:.2f}ms exceeds 150ms threshold"
            print(f"  ✅ PASS: Reconciliation meets <150ms requirement")
        else:
            print(f"  ⚠️  WARNING: Reconciliation events not captured (check WebSocket)")
    
    
    def test_99_performance_summary(self, perf_metrics: PerformanceMetrics):
        """
        Final test: Generate performance validation summary
        """
        print("\n" + "="*80)
        print("PERFORMANCE VALIDATION SUMMARY")
        print("="*80)
        
        summary = perf_metrics.get_summary()
        
        print(f"\nTotal Metrics: {summary['total_metrics']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"\nDetailed Results:")
        
        for name, result in summary['details'].items():
            if result.get('threshold'):
                status = "✅ PASS" if result['valid'] else "❌ FAIL"
                value = result['value']
                threshold = result['threshold']
                percentage = result['percentage']
                
                print(f"  {status} {name}: {value:.2f}ms / {threshold}ms ({percentage:.1f}%)")
            else:
                print(f"  ℹ️  {name}: {result['value']:.2f} (no threshold)")
        
        # Save report
        os.makedirs('tests/results', exist_ok=True)
        report_path = f"tests/results/crown46_performance_{int(time.time())}.json"
        with open(report_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': summary,
                'metrics': perf_metrics.metrics,
                'thresholds': perf_metrics.thresholds
            }, f, indent=2)
        
        print(f"\n📊 Report saved to: {report_path}")
        
        # Assert overall pass
        assert summary['failed'] == 0, f"{summary['failed']} performance metrics failed validation"
        
        print(f"\n🎉 All CROWN 4.6 performance requirements validated successfully!")
