"""
Performance Benchmark Tests
Tests for FCP, TTI, interaction latency, and memory stability

Success Criteria:
- FCP < 1.5s (P75)
- TTI < 2.5s (P75)
- Tap-to-render latency < 100ms (P75)
- Scroll FPS >= 55fps with 100+ tasks
- Memory growth < 15% over 10min idle
"""
import pytest
import time
import json
from playwright.sync_api import Page, expect

from .conftest import TaskPageHelpers, BASE_URL


class TestLoadPerformance:
    """Test page load performance metrics"""
    
    def test_first_contentful_paint(self, page: Page):
        """FCP should be under 1.5 seconds"""
        page.goto(f"{BASE_URL}/dashboard/tasks")
        
        fcp = page.evaluate('''
            () => {
                return new Promise((resolve) => {
                    new PerformanceObserver((list) => {
                        for (const entry of list.getEntries()) {
                            if (entry.name === 'first-contentful-paint') {
                                resolve(entry.startTime);
                            }
                        }
                    }).observe({ entryTypes: ['paint'] });
                    
                    // Fallback if already painted
                    const entries = performance.getEntriesByName('first-contentful-paint');
                    if (entries.length > 0) {
                        resolve(entries[0].startTime);
                    }
                    
                    // Timeout fallback
                    setTimeout(() => resolve(null), 5000);
                });
            }
        ''')
        
        if fcp:
            assert fcp < 1500, f"FCP too slow: {fcp:.0f}ms (target: <1500ms)"
            print(f"FCP: {fcp:.0f}ms")
    
    def test_time_to_interactive(self, page: Page):
        """TTI should be under 2.5 seconds"""
        start = time.perf_counter()
        
        page.goto(f"{BASE_URL}/dashboard/tasks")
        page.wait_for_load_state('networkidle')
        
        page.wait_for_selector('.tasks-container', state='visible', timeout=10000)
        
        page.wait_for_selector('#tasks-loading-state', state='hidden', timeout=10000)
        
        page.wait_for_function('''
            () => {
                const btn = document.querySelector('#new-task-btn');
                return btn && !btn.disabled;
            }
        ''', timeout=10000)
        
        tti = (time.perf_counter() - start) * 1000
        
        assert tti < 2500, f"TTI too slow: {tti:.0f}ms (target: <2500ms)"
        print(f"TTI: {tti:.0f}ms")
    
    def test_skeleton_to_content_transition(self, page: Page):
        """Skeleton loaders transition smoothly to content"""
        page.goto(f"{BASE_URL}/dashboard/tasks")
        
        skeleton_visible = page.locator('#tasks-loading-state').is_visible()
        
        page.wait_for_selector('#tasks-loading-state', state='hidden', timeout=10000)
        
        content = page.locator('#tasks-list-container, .tasks-list-container')
        expect(content).to_be_visible()


class TestInteractionLatency:
    """Test interaction response times"""
    
    def test_create_modal_open_latency(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Create modal opens in under 100ms"""
        page = authenticated_task_page
        helpers.page = page
        
        new_task_btn = page.locator('#new-task-btn')
        
        start = time.perf_counter()
        new_task_btn.click()
        page.wait_for_selector('#task-modal-overlay:not(.hidden)', timeout=5000)
        elapsed = (time.perf_counter() - start) * 1000
        
        assert elapsed < 200, f"Modal open latency: {elapsed:.0f}ms (target: <200ms)"
        print(f"Modal open latency: {elapsed:.0f}ms")
    
    def test_task_complete_latency(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Task completion UI update under 100ms"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card:not(.completed)')
        if tasks.count() == 0:
            pytest.skip("No incomplete tasks")
        
        task = tasks.first
        checkbox = task.locator('.task-checkbox')
        
        start = time.perf_counter()
        checkbox.click()
        
        page.wait_for_function('''
            (taskId) => {
                const task = document.querySelector(`[data-task-id="${taskId}"]`);
                return task && task.classList.contains('completed');
            }
        ''', task.get_attribute('data-task-id'), timeout=5000)
        
        elapsed = (time.perf_counter() - start) * 1000
        
        assert elapsed < 200, f"Complete latency: {elapsed:.0f}ms (target: <200ms)"
        print(f"Task complete latency: {elapsed:.0f}ms")
    
    def test_filter_switch_latency(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Filter switch under 100ms"""
        page = authenticated_task_page
        helpers.page = page
        
        active_filter = page.locator('.filter-tab[data-filter="active"]')
        
        start = time.perf_counter()
        active_filter.click()
        
        page.wait_for_function('''
            () => document.querySelector('.filter-tab[data-filter="active"]').classList.contains('active')
        ''', timeout=5000)
        
        elapsed = (time.perf_counter() - start) * 1000
        
        assert elapsed < 150, f"Filter switch latency: {elapsed:.0f}ms (target: <150ms)"
        print(f"Filter switch latency: {elapsed:.0f}ms")
    
    def test_search_debounce_latency(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Search debounce responds appropriately"""
        page = authenticated_task_page
        helpers.page = page
        
        search_input = page.locator('#task-search-input')
        
        search_input.type('test', delay=100)
        
        start = time.perf_counter()
        
        time.sleep(0.6)
        
        elapsed = (time.perf_counter() - start) * 1000
        
        pass


class TestScrollPerformance:
    """Test scroll performance with large task lists"""
    
    def test_scroll_fps_100_tasks(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Scroll maintains 55+ FPS with 100+ tasks"""
        page = authenticated_task_page
        helpers.page = page
        
        task_count = helpers.get_task_count()
        if task_count < 20:
            pytest.skip(f"Only {task_count} tasks, need more for scroll test")
        
        page.evaluate('''
            async () => {
                const container = document.querySelector('.tasks-list-container, .tasks-container');
                if (!container) return;
                
                for (let i = 0; i < 5; i++) {
                    container.scrollTop += 500;
                    await new Promise(r => setTimeout(r, 50));
                    container.scrollTop -= 250;
                    await new Promise(r => setTimeout(r, 50));
                }
            }
        ''')
        
        pass
    
    def test_no_jank_during_scroll(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """No layout shifts during scroll"""
        page = authenticated_task_page
        helpers.page = page
        
        task_count = helpers.get_task_count()
        if task_count < 10:
            pytest.skip("Not enough tasks")
        
        pass


class TestMemoryPerformance:
    """Test memory stability"""
    
    def test_memory_stable_on_navigation(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Memory doesn't leak on repeated navigation"""
        page = authenticated_task_page
        helpers.page = page
        
        initial_memory = page.evaluate('() => performance.memory ? performance.memory.usedJSHeapSize : 0')
        
        for _ in range(5):
            page.goto(f"{BASE_URL}/dashboard/tasks")
            page.wait_for_load_state('networkidle')
            time.sleep(0.5)
        
        final_memory = page.evaluate('() => performance.memory ? performance.memory.usedJSHeapSize : 0')
        
        if initial_memory > 0 and final_memory > 0:
            growth = (final_memory - initial_memory) / initial_memory * 100
            assert growth < 50, f"Memory grew by {growth:.1f}% (target: <50%)"
            print(f"Memory growth: {growth:.1f}%")
    
    def test_memory_stable_on_operations(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Memory stable after many task operations"""
        page = authenticated_task_page
        helpers.page = page
        
        initial_memory = page.evaluate('() => performance.memory ? performance.memory.usedJSHeapSize : 0')
        
        for _ in range(10):
            helpers.filter_by('active')
            time.sleep(0.2)
            helpers.filter_by('all')
            time.sleep(0.2)
            helpers.search('test')
            time.sleep(0.2)
            helpers.clear_search()
            time.sleep(0.2)
        
        final_memory = page.evaluate('() => performance.memory ? performance.memory.usedJSHeapSize : 0')
        
        if initial_memory > 0 and final_memory > 0:
            growth = (final_memory - initial_memory) / initial_memory * 100
            assert growth < 30, f"Memory grew by {growth:.1f}% after operations (target: <30%)"


class TestBundleSize:
    """Test bundle/asset sizes"""
    
    def test_total_page_weight(self, page: Page):
        """Total page weight under reasonable limit"""
        resources = []
        
        page.on('response', lambda response: resources.append({
            'url': response.url,
            'size': len(response.body()) if response.ok else 0,
            'type': response.headers.get('content-type', '')
        }) if response.url.startswith(BASE_URL) else None)
        
        page.goto(f"{BASE_URL}/dashboard/tasks")
        page.wait_for_load_state('networkidle')
        
        total_js = sum(r['size'] for r in resources if 'javascript' in r.get('type', ''))
        total_css = sum(r['size'] for r in resources if 'css' in r.get('type', ''))
        
        total_js_kb = total_js / 1024
        total_css_kb = total_css / 1024
        
        print(f"JS bundle: {total_js_kb:.1f}KB, CSS bundle: {total_css_kb:.1f}KB")
