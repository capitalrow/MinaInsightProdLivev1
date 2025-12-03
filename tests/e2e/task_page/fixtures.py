"""
Deterministic Test Data Fixtures
Provides seeding and cleanup for isolated test execution
"""
import pytest
import time
import json
from datetime import datetime, timedelta
from playwright.sync_api import Page


class TestDataSeeder:
    """Seed and cleanup test data for deterministic tests"""
    
    def __init__(self, page: Page):
        self.page = page
        self.created_task_ids = []
        self.created_proposal_ids = []
    
    def seed_task(self, title: str, priority: str = 'medium', status: str = 'active', 
                  description: str = '', due_date: str = None) -> str:
        """Create a task via API and return its ID"""
        task_data = {
            'title': title,
            'priority': priority,
            'status': status,
            'description': description,
        }
        if due_date:
            task_data['due_date'] = due_date
        
        result = self.page.evaluate(f'''
            async () => {{
                const response = await fetch('/api/tasks', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({json.dumps(task_data)})
                }});
                if (!response.ok) return null;
                const data = await response.json();
                return data.id || data.task?.id || null;
            }}
        ''')
        
        if result:
            self.created_task_ids.append(result)
        
        return result
    
    def seed_multiple_tasks(self, count: int = 5, prefix: str = 'Test Task') -> list:
        """Create multiple tasks with varying priorities"""
        priorities = ['urgent', 'high', 'medium', 'low']
        task_ids = []
        
        for i in range(count):
            priority = priorities[i % len(priorities)]
            task_id = self.seed_task(
                title=f'{prefix} {i+1} - {int(time.time())}',
                priority=priority,
                status='active'
            )
            if task_id:
                task_ids.append(task_id)
        
        return task_ids
    
    def cleanup(self):
        """Delete all created test data"""
        for task_id in self.created_task_ids:
            self.page.evaluate(f'''
                async () => {{
                    await fetch('/api/tasks/{task_id}', {{ method: 'DELETE' }});
                }}
            ''')
        
        self.created_task_ids = []
        self.created_proposal_ids = []
    
    def clear_local_storage(self):
        """Clear localStorage to prevent state leakage"""
        self.page.evaluate('() => localStorage.clear()')
    
    def clear_indexed_db(self):
        """Clear IndexedDB stores"""
        self.page.evaluate('''
            async () => {
                const databases = await indexedDB.databases();
                for (const db of databases) {
                    indexedDB.deleteDatabase(db.name);
                }
            }
        ''')
    
    def full_cleanup(self):
        """Complete cleanup including API data and browser storage"""
        self.cleanup()
        self.clear_local_storage()
        self.clear_indexed_db()


@pytest.fixture(scope="function")
def seeder(page):
    """Provide a test data seeder with automatic cleanup"""
    _seeder = TestDataSeeder(page)
    yield _seeder
    _seeder.full_cleanup()


@pytest.fixture(scope="function") 
def seeded_tasks(authenticated_task_page, seeder):
    """Seed 5 tasks and clean up after test"""
    seeder.page = authenticated_task_page
    task_ids = seeder.seed_multiple_tasks(5, 'Seeded Task')
    authenticated_task_page.reload()
    authenticated_task_page.wait_for_load_state('networkidle')
    time.sleep(0.5)
    return task_ids


@pytest.fixture(scope="function")
def clean_storage(authenticated_task_page):
    """Clear all browser storage before test"""
    authenticated_task_page.evaluate('''
        () => {
            localStorage.clear();
            sessionStorage.clear();
        }
    ''')
    yield
    authenticated_task_page.evaluate('''
        () => {
            localStorage.clear();
            sessionStorage.clear();
        }
    ''')


def assert_toast_appears(page, timeout: int = 3000) -> str:
    """Assert that a toast notification appears and return its text"""
    toast = page.wait_for_selector('.toast:not(.hidden), .notification-toast', timeout=timeout)
    assert toast.is_visible(), "Toast notification did not appear"
    return toast.text_content()


def assert_task_in_list(page, task_id: str = None, title: str = None) -> bool:
    """Assert that a task exists in the list"""
    if task_id:
        task = page.locator(f'.task-card[data-task-id="{task_id}"]')
    elif title:
        task = page.locator(f'.task-card:has(.task-title:text("{title}"))')
    else:
        raise ValueError("Must provide task_id or title")
    
    assert task.count() > 0, f"Task not found: id={task_id}, title={title}"
    return True


def assert_task_not_in_list(page, task_id: str = None, title: str = None) -> bool:
    """Assert that a task does not exist in the list"""
    if task_id:
        task = page.locator(f'.task-card[data-task-id="{task_id}"]')
    elif title:
        task = page.locator(f'.task-card:has(.task-title:text("{title}"))')
    else:
        raise ValueError("Must provide task_id or title")
    
    assert task.count() == 0, f"Task should not exist: id={task_id}, title={title}"
    return True


def assert_performance_metric(value: float, target: float, metric_name: str):
    """Assert a performance metric meets target with detailed message"""
    assert value is not None, f"{metric_name} was not measured"
    assert value <= target, f"{metric_name}: {value:.0f}ms exceeds target {target:.0f}ms"


def measure_and_assert_fcp(page, target_ms: float = 1500) -> float:
    """Measure FCP and assert it meets target"""
    fcp = page.evaluate('''
        () => {
            const entries = performance.getEntriesByName('first-contentful-paint');
            return entries.length > 0 ? entries[0].startTime : null;
        }
    ''')
    
    assert_performance_metric(fcp, target_ms, "FCP")
    return fcp


def measure_and_assert_tti(page, target_ms: float = 2500) -> float:
    """Measure TTI and assert it meets target"""
    start = time.perf_counter()
    
    page.wait_for_selector('.tasks-container', state='visible', timeout=10000)
    page.wait_for_function('''
        () => {
            const btn = document.querySelector('#new-task-btn');
            return btn && !btn.disabled;
        }
    ''', timeout=10000)
    
    tti = (time.perf_counter() - start) * 1000
    assert_performance_metric(tti, target_ms, "TTI")
    return tti
