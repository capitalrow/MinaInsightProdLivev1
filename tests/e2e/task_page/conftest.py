"""
Task Page E2E Test Fixtures
Provides authenticated sessions, test data, and helper utilities
"""
import pytest
import os
import time
import json
from datetime import datetime, timedelta
from playwright.sync_api import Page, Browser, BrowserContext, expect

BASE_URL = os.environ.get('TEST_BASE_URL', 'http://localhost:5000')
TEST_USER_EMAIL = os.environ.get('TEST_USER_EMAIL', 'tasktest@example.com')
TEST_USER_PASSWORD = os.environ.get('TEST_USER_PASSWORD', 'testpass123')


class TaskPageHelpers:
    """Helper methods for task page interactions"""
    
    def __init__(self, page: Page):
        self.page = page
        self.base_url = BASE_URL
    
    def wait_for_tasks_loaded(self, timeout: int = 10000):
        """Wait for task list to finish loading"""
        self.page.wait_for_selector('.tasks-list-container', state='visible', timeout=timeout)
        self.page.wait_for_selector('#tasks-loading-state', state='hidden', timeout=timeout)
    
    def get_task_count(self) -> int:
        """Get number of visible tasks"""
        return self.page.locator('.task-card').count()
    
    def get_task_by_index(self, index: int):
        """Get task card by index"""
        return self.page.locator('.task-card').nth(index)
    
    def get_task_by_title(self, title: str):
        """Get task card by title text"""
        return self.page.locator(f'.task-card:has(.task-title:text("{title}"))')
    
    def open_create_modal(self):
        """Open the create task modal"""
        self.page.click('#new-task-btn')
        self.page.wait_for_selector('#task-modal-overlay:not(.hidden)', timeout=5000)
    
    def close_modal(self):
        """Close any open modal"""
        self.page.click('#task-modal-close')
        self.page.wait_for_selector('#task-modal-overlay.hidden', timeout=5000)
    
    def create_task(self, title: str, description: str = '', priority: str = 'medium', due_date: str = None):
        """Create a new task via modal"""
        self.open_create_modal()
        
        self.page.fill('#task-title', title)
        if description:
            self.page.fill('#task-description', description)
        
        if priority != 'medium':
            self.page.select_option('#task-priority', priority)
        
        if due_date:
            self.page.fill('#task-due-date', due_date)
        
        self.page.click('#task-create-form button[type="submit"]')
        self.page.wait_for_selector('#task-modal-overlay.hidden', timeout=10000)
        time.sleep(0.5)
    
    def open_task_menu(self, task_locator):
        """Open the three-dot menu for a task"""
        task_locator.locator('.task-menu-trigger').click()
        self.page.wait_for_selector('#task-menu[data-state="open"]', timeout=5000)
    
    def close_task_menu(self):
        """Close task menu by clicking outside"""
        self.page.mouse.click(10, 10)
        self.page.wait_for_selector('#task-menu[data-state="open"]', state='hidden', timeout=3000)
    
    def complete_task(self, task_locator):
        """Mark a task as complete via checkbox"""
        checkbox = task_locator.locator('.task-checkbox')
        checkbox.click()
        time.sleep(0.3)
    
    def delete_task_via_menu(self, task_locator):
        """Delete a task via action menu"""
        self.open_task_menu(task_locator)
        self.page.click('#task-menu .task-menu-item[data-action="delete"]')
        self.page.wait_for_selector('.confirmation-modal, .task-confirmation-modal', timeout=5000)
        self.page.click('.confirmation-modal button.confirm, .task-confirmation-modal .confirm-btn')
        time.sleep(0.5)
    
    def filter_by(self, filter_name: str):
        """Click a filter tab (all, active, archived)"""
        self.page.click(f'.filter-tab[data-filter="{filter_name}"]')
        time.sleep(0.3)
    
    def search(self, query: str):
        """Search for tasks"""
        self.page.fill('#task-search-input', query)
        time.sleep(0.5)
    
    def clear_search(self):
        """Clear search input"""
        self.page.click('#search-clear-btn')
        time.sleep(0.3)
    
    def sort_by(self, sort_value: str):
        """Change sort order"""
        self.page.select_option('#task-sort-select', sort_value)
        time.sleep(0.3)
    
    def get_toast_message(self) -> str:
        """Get the current toast notification message"""
        toast = self.page.locator('.toast, .notification-toast').first
        if toast.is_visible():
            return toast.text_content()
        return ''
    
    def wait_for_toast(self, timeout: int = 5000):
        """Wait for a toast notification to appear"""
        self.page.wait_for_selector('.toast:not(.hidden), .notification-toast', timeout=timeout)
    
    def click_toast_undo(self):
        """Click the undo button on a toast"""
        self.page.click('.toast .undo-btn, .notification-toast .undo-action')
    
    def measure_interaction_time(self, action_fn, description: str = '') -> float:
        """Measure time for an interaction"""
        start = time.perf_counter()
        action_fn()
        end = time.perf_counter()
        return (end - start) * 1000


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context"""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 800},
        "ignore_https_errors": True,
        "locale": "en-US",
        "timezone_id": "America/New_York",
    }


@pytest.fixture(scope="function")
def task_page(page: Page) -> Page:
    """Navigate to tasks page (unauthenticated - for public tests)"""
    page.goto(f"{BASE_URL}/dashboard/tasks")
    page.wait_for_load_state('networkidle')
    return page


@pytest.fixture(scope="function")
def authenticated_task_page(page: Page) -> Page:
    """Provide an authenticated page at the tasks dashboard"""
    page.goto(f"{BASE_URL}/auth/login")
    page.wait_for_load_state('networkidle')
    
    page.fill('input[name="email"], input[type="email"], #email', TEST_USER_EMAIL)
    page.fill('input[name="password"], input[type="password"], #password', TEST_USER_PASSWORD)
    page.click('button[type="submit"], input[type="submit"]')
    
    try:
        page.wait_for_url(f"{BASE_URL}/dashboard**", timeout=15000)
    except:
        pass
    
    page.goto(f"{BASE_URL}/dashboard/tasks")
    page.wait_for_load_state('networkidle')
    
    try:
        page.wait_for_selector('.tasks-container', timeout=10000)
    except:
        pass
    
    return page


@pytest.fixture(scope="function")
def helpers(page: Page) -> TaskPageHelpers:
    """Provide helper methods for task page interactions"""
    return TaskPageHelpers(page)


@pytest.fixture(scope="function")
def performance_metrics():
    """Collect performance metrics during test"""
    metrics = {
        'fcp': None,
        'tti': None,
        'interaction_times': [],
        'memory_samples': [],
        'start_time': time.perf_counter()
    }
    yield metrics
    metrics['total_duration'] = time.perf_counter() - metrics['start_time']


@pytest.fixture(scope="function")
def test_task_data():
    """Provide test task data"""
    return {
        'title': f'Test Task {datetime.now().strftime("%H%M%S")}',
        'description': 'This is a test task created by automated tests',
        'priority': 'high',
        'due_date': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    }


@pytest.fixture(scope="function")
def multiple_test_tasks():
    """Provide multiple test tasks for bulk operations"""
    base_time = datetime.now().strftime("%H%M%S")
    return [
        {'title': f'Bulk Test Task 1 - {base_time}', 'priority': 'high'},
        {'title': f'Bulk Test Task 2 - {base_time}', 'priority': 'medium'},
        {'title': f'Bulk Test Task 3 - {base_time}', 'priority': 'low'},
    ]
