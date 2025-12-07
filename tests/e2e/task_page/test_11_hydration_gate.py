"""
Hydration Gate Tests - CROWN⁴.10
Validates that task card animations only play once on initial render,
preventing flicker during subsequent re-renders/reconciliation.

Success Criteria:
- `tasks-hydrated` class added to container after first render
- Task cards under hydrated container have `animation: none`
- No flicker on simulated WebSocket updates
- New tasks created post-hydration still behave correctly
"""
import pytest
import time
from playwright.sync_api import Page, expect

from .conftest import TaskPageHelpers, BASE_URL


class TestHydrationGate:
    """Test that hydration gate prevents animation replay flicker"""
    
    def test_hydration_class_added_after_load(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """
        After initial render, the container should have 'tasks-hydrated' class
        which disables entrance animations for subsequent renders.
        """
        page = authenticated_task_page
        helpers.page = page
        
        helpers.wait_for_tasks_loaded()
        
        page.wait_for_function('''
            () => window.taskHydrationReady === true
        ''', timeout=10000)
        
        has_hydrated_class = page.evaluate('''
            () => {
                const container = document.getElementById('tasks-list-container');
                return container && container.classList.contains('tasks-hydrated');
            }
        ''')
        
        assert has_hydrated_class, "Container missing 'tasks-hydrated' class after hydration"
        print("✅ tasks-hydrated class present on container")
    
    def test_animations_disabled_after_hydration(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """
        After hydration, task cards should have animation: none computed style,
        preventing re-render flicker.
        """
        page = authenticated_task_page
        helpers.page = page
        
        helpers.wait_for_tasks_loaded()
        
        page.wait_for_function('''
            () => window.taskHydrationReady === true
        ''', timeout=10000)
        
        task_count = helpers.get_task_count()
        if task_count == 0:
            pytest.skip("No tasks to check animation on")
        
        animation_info = page.evaluate('''
            () => {
                const cards = document.querySelectorAll('.task-card');
                const results = [];
                
                for (const card of cards) {
                    const style = getComputedStyle(card);
                    results.push({
                        animationName: style.animationName,
                        animationDuration: style.animationDuration,
                        hasAnimateEntrance: card.classList.contains('animate-entrance')
                    });
                }
                
                return results;
            }
        ''')
        
        for i, info in enumerate(animation_info):
            assert info['animationName'] == 'none', \
                f"Task {i} has animation '{info['animationName']}' (expected 'none')"
            assert not info['hasAnimateEntrance'], \
                f"Task {i} still has animate-entrance class"
        
        print(f"✅ All {len(animation_info)} task cards have animation: none")
    
    def test_no_flicker_on_simulated_rerender(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """
        Simulate a re-render by triggering renderTasks again and verify
        no animation classes are applied.
        """
        page = authenticated_task_page
        helpers.page = page
        
        helpers.wait_for_tasks_loaded()
        
        page.wait_for_function('''
            () => window.taskHydrationReady === true
        ''', timeout=10000)
        
        initial_count = helpers.get_task_count()
        if initial_count == 0:
            pytest.skip("No tasks to test re-render with")
        
        page.evaluate('''
            () => {
                if (window.TaskBootstrap && window.TaskBootstrap.renderTasks) {
                    const tasks = window.__currentTasks || [];
                    window.TaskBootstrap.renderTasks(tasks, { force: true });
                }
            }
        ''')
        
        time.sleep(0.5)
        
        animation_info = page.evaluate('''
            () => {
                const cards = document.querySelectorAll('.task-card');
                const results = [];
                
                for (const card of cards) {
                    const style = getComputedStyle(card);
                    results.push({
                        animationName: style.animationName,
                        opacity: style.opacity
                    });
                }
                
                return results;
            }
        ''')
        
        for i, info in enumerate(animation_info):
            assert info['animationName'] == 'none', \
                f"Task {i} has animation after re-render: '{info['animationName']}'"
            assert float(info['opacity']) >= 0.9, \
                f"Task {i} has reduced opacity {info['opacity']} (possible flicker)"
        
        print(f"✅ Re-render completed without animation replay on {len(animation_info)} tasks")
    
    def test_tasks_hydrated_event_fires(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """
        Verify that the 'tasks:hydrated' custom event is fired after hydration.
        """
        page = authenticated_task_page
        helpers.page = page
        
        page.evaluate('''
            () => {
                window.__hydrationEventFired = false;
                window.__hydrationEventDetail = null;
                
                document.addEventListener('tasks:hydrated', (e) => {
                    window.__hydrationEventFired = true;
                    window.__hydrationEventDetail = e.detail;
                });
            }
        ''')
        
        page.reload()
        helpers.wait_for_tasks_loaded()
        
        page.wait_for_function('''
            () => window.taskHydrationReady === true
        ''', timeout=10000)
        
        event_result = page.evaluate('''
            () => ({
                fired: window.__hydrationEventFired,
                detail: window.__hydrationEventDetail
            })
        ''')
        
        assert event_result['fired'], "tasks:hydrated event was not fired"
        assert event_result['detail'] is not None, "Event detail missing"
        assert 'timestamp' in event_result['detail'], "Event missing timestamp"
        
        print(f"✅ tasks:hydrated event fired with detail: {event_result['detail']}")


class TestHydrationPerformance:
    """Test hydration timing and performance"""
    
    def test_hydration_completes_quickly(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """
        Hydration should complete within acceptable time bounds.
        """
        page = authenticated_task_page
        helpers.page = page
        
        page.evaluate('''
            () => {
                window.__hydrationStartTime = performance.now();
            }
        ''')
        
        page.reload()
        helpers.wait_for_tasks_loaded()
        
        page.wait_for_function('''
            () => window.taskHydrationReady === true
        ''', timeout=10000)
        
        hydration_time = page.evaluate('''
            () => {
                return performance.now() - window.__hydrationStartTime;
            }
        ''')
        
        assert hydration_time < 3000, f"Hydration too slow: {hydration_time:.0f}ms (target: <3000ms)"
        print(f"✅ Hydration completed in {hydration_time:.0f}ms")
    
    def test_no_duplicate_task_renders(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """
        Task count should remain stable after hydration (no duplicate renders).
        """
        page = authenticated_task_page
        helpers.page = page
        
        helpers.wait_for_tasks_loaded()
        
        page.wait_for_function('''
            () => window.taskHydrationReady === true
        ''', timeout=10000)
        
        initial_count = helpers.get_task_count()
        
        time.sleep(1.0)
        
        final_count = helpers.get_task_count()
        
        assert final_count == initial_count, \
            f"Task count changed from {initial_count} to {final_count} (possible duplicate render)"
        
        print(f"✅ Task count stable at {final_count} (no duplicate renders)")


class TestPostHydrationBehavior:
    """Test that normal functionality works after hydration gate is applied"""
    
    def test_new_task_creation_works(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """
        Creating a new task after hydration should work correctly.
        """
        page = authenticated_task_page
        helpers.page = page
        
        helpers.wait_for_tasks_loaded()
        
        page.wait_for_function('''
            () => window.taskHydrationReady === true
        ''', timeout=10000)
        
        initial_count = helpers.get_task_count()
        
        test_title = f"Hydration Test Task {int(time.time())}"
        helpers.create_task(test_title, description="Test task created post-hydration")
        
        page.wait_for_selector(f'.task-card:has(.task-title:text("{test_title}"))', timeout=10000)
        
        final_count = helpers.get_task_count()
        assert final_count == initial_count + 1, \
            f"Task count didn't increase: {initial_count} -> {final_count}"
        
        print(f"✅ New task created successfully post-hydration")
    
    def test_task_completion_works(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """
        Completing a task after hydration should work correctly.
        """
        page = authenticated_task_page
        helpers.page = page
        
        helpers.wait_for_tasks_loaded()
        
        page.wait_for_function('''
            () => window.taskHydrationReady === true
        ''', timeout=10000)
        
        incomplete_tasks = page.locator('.task-card:not(.completed)')
        if incomplete_tasks.count() == 0:
            pytest.skip("No incomplete tasks to test completion")
        
        task = incomplete_tasks.first
        helpers.complete_task(task)
        
        expect(task).to_have_class("completed")
        
        print("✅ Task completion works post-hydration")
