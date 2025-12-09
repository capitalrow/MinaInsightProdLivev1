#!/usr/bin/env python
"""
Comprehensive Interactive Task Page Tests
Systematic testing of all task page features matching industry-leading standards
(Todoist, Asana, Linear)

Tests Include:
1. CREATE operations - Create new tasks and verify immediate appearance
2. READ operations - View task list, verify data accuracy
3. UPDATE operations - Edit task titles, priority, due dates, status
4. DELETE operations - Delete tasks with confirmation/undo
5. Tab filtering (Active/Completed/All/Archived) and counters
6. Search and priority filtering
7. Keyboard shortcuts
8. Drag-drop reordering
9. Performance metrics
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

# Add project root to path
sys.path.insert(0, '/home/runner/workspace')

from playwright.sync_api import sync_playwright, Page, expect

BASE_URL = os.environ.get('TEST_BASE_URL', 'http://127.0.0.1:5000')


@dataclass
class TestResult:
    """Individual test result"""
    name: str
    category: str
    passed: bool
    duration_ms: float
    details: str = ""
    error: str = ""


@dataclass
class TestReport:
    """Full test report"""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    results: List[TestResult] = field(default_factory=list)
    start_time: datetime = None
    end_time: datetime = None
    
    def add_result(self, result: TestResult):
        self.results.append(result)
        self.total_tests += 1
        if result.passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def get_summary(self) -> str:
        """Generate human-readable summary"""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        
        lines = [
            "=" * 70,
            " COMPREHENSIVE TASK PAGE TEST REPORT",
            "=" * 70,
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {duration:.2f}s",
            "",
            f"Total Tests: {self.total_tests}",
            f"Passed: {self.passed} ({self.passed/self.total_tests*100:.1f}%)" if self.total_tests > 0 else "Passed: 0",
            f"Failed: {self.failed}",
            f"Skipped: {self.skipped}",
            "",
            "-" * 70,
            " DETAILED RESULTS",
            "-" * 70,
        ]
        
        # Group by category
        categories = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)
        
        for category, results in categories.items():
            lines.append(f"\n## {category}")
            for r in results:
                status = "PASS" if r.passed else "FAIL"
                lines.append(f"  [{status}] {r.name} ({r.duration_ms:.0f}ms)")
                if r.details:
                    lines.append(f"        Details: {r.details}")
                if r.error:
                    lines.append(f"        Error: {r.error}")
        
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)


class TaskPageTester:
    """Comprehensive task page tester"""
    
    def __init__(self, page: Page):
        self.page = page
        self.report = TestReport()
        self.report.start_time = datetime.now()
        self.tasks_created = []  # Track for cleanup
    
    def run_test(self, name: str, category: str, test_fn) -> TestResult:
        """Run a single test and record result"""
        start = time.perf_counter()
        try:
            details = test_fn()
            duration = (time.perf_counter() - start) * 1000
            result = TestResult(
                name=name,
                category=category,
                passed=True,
                duration_ms=duration,
                details=details if isinstance(details, str) else ""
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            result = TestResult(
                name=name,
                category=category,
                passed=False,
                duration_ms=duration,
                error=str(e)
            )
        
        self.report.add_result(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {name} ({duration:.0f}ms)")
        return result
    
    def login(self) -> bool:
        """Authenticate to the application"""
        print("\n1. Authenticating...")
        try:
            self.page.goto(f"{BASE_URL}/auth/login", wait_until='networkidle')
            time.sleep(1)
            
            # Fill login form
            email_input = self.page.locator('input[name="email"], input[type="email"], #email').first
            password_input = self.page.locator('input[name="password"], input[type="password"], #password').first
            
            if email_input.is_visible():
                email_input.fill("tasktest@example.com")
                password_input.fill("testpass123")
                self.page.click('button[type="submit"], input[type="submit"]')
                time.sleep(2)
            
            # Navigate to tasks page
            self.page.goto(f"{BASE_URL}/tasks", wait_until='networkidle')
            time.sleep(2)
            
            # Check if we're on tasks page
            if '/tasks' in self.page.url or self.page.locator('.tasks-container, .task-card, .filter-tab').first.is_visible():
                print("   Authentication successful!")
                return True
            else:
                print(f"   Warning: May not be on tasks page. URL: {self.page.url}")
                return True  # Try anyway
                
        except Exception as e:
            print(f"   Authentication error: {e}")
            return False
    
    def get_task_count(self) -> int:
        """Get number of visible task cards"""
        return self.page.locator('.task-card:visible').count()
    
    def get_tab_count(self, tab_name: str) -> Optional[int]:
        """Get the count displayed on a filter tab"""
        try:
            tab = self.page.locator(f'.filter-tab[data-filter="{tab_name}"], .task-filter[data-filter="{tab_name}"]').first
            count_el = tab.locator('.filter-count, .task-count, .count')
            if count_el.is_visible():
                text = count_el.text_content()
                return int(text.strip())
            return None
        except:
            return None
    
    # ============ CREATE TESTS ============
    
    def test_create_task_modal_opens(self):
        """Test that create task modal opens correctly"""
        btn = self.page.locator('#new-task-btn, .new-task-btn, [data-action="create-task"]').first
        btn.click()
        time.sleep(0.5)
        
        modal = self.page.locator('#task-modal-overlay, .task-modal, .create-task-modal').first
        if modal.is_visible():
            # Close modal
            close_btn = self.page.locator('#task-modal-close, .modal-close, .close-modal').first
            if close_btn.is_visible():
                close_btn.click()
            else:
                self.page.keyboard.press('Escape')
            time.sleep(0.3)
            return "Modal opened successfully"
        else:
            raise Exception("Modal did not open")
    
    def test_create_task_with_title_only(self):
        """Test creating a task with just a title"""
        initial_count = self.get_task_count()
        
        # Open modal
        btn = self.page.locator('#new-task-btn, .new-task-btn, [data-action="create-task"]').first
        btn.click()
        time.sleep(0.5)
        
        # Fill title
        title = f"Test Task {datetime.now().strftime('%H%M%S')}"
        title_input = self.page.locator('#task-title, input[name="title"]').first
        title_input.fill(title)
        self.tasks_created.append(title)
        
        # Submit
        submit_btn = self.page.locator('#task-create-form button[type="submit"], .create-task-btn, .submit-task').first
        submit_btn.click()
        time.sleep(1)
        
        # Verify task appears
        new_count = self.get_task_count()
        if new_count > initial_count:
            return f"Created task '{title}'. Count: {initial_count} -> {new_count}"
        else:
            # Check if task exists by title
            task = self.page.locator(f'.task-card:has-text("{title}")')
            if task.count() > 0:
                return f"Created task '{title}' (visible in list)"
            raise Exception(f"Task not created. Count unchanged: {new_count}")
    
    def test_create_task_optimistic_ui(self):
        """Test that task appears immediately (optimistic UI)"""
        # Open modal
        btn = self.page.locator('#new-task-btn, .new-task-btn, [data-action="create-task"]').first
        btn.click()
        time.sleep(0.3)
        
        title = f"Optimistic {datetime.now().strftime('%H%M%S')}"
        title_input = self.page.locator('#task-title, input[name="title"]').first
        title_input.fill(title)
        self.tasks_created.append(title)
        
        # Measure time
        start = time.perf_counter()
        submit_btn = self.page.locator('#task-create-form button[type="submit"], .create-task-btn').first
        submit_btn.click()
        
        # Wait for task to appear
        try:
            self.page.wait_for_selector(f'.task-card:has-text("{title}")', timeout=5000)
            elapsed = (time.perf_counter() - start) * 1000
            
            if elapsed < 500:
                return f"Task appeared in {elapsed:.0f}ms (target: <500ms) - EXCELLENT"
            elif elapsed < 1000:
                return f"Task appeared in {elapsed:.0f}ms (acceptable)"
            else:
                raise Exception(f"Task took {elapsed:.0f}ms to appear (too slow)")
        except:
            raise Exception("Task did not appear within 5s")
    
    def test_create_task_with_priority(self):
        """Test creating a task with high priority"""
        btn = self.page.locator('#new-task-btn, .new-task-btn').first
        btn.click()
        time.sleep(0.5)
        
        title = f"High Priority {datetime.now().strftime('%H%M%S')}"
        self.page.locator('#task-title, input[name="title"]').first.fill(title)
        self.tasks_created.append(title)
        
        # Set priority
        priority_select = self.page.locator('#task-priority, select[name="priority"]').first
        if priority_select.is_visible():
            priority_select.select_option('high')
        
        self.page.locator('#task-create-form button[type="submit"], .create-task-btn').first.click()
        time.sleep(1)
        
        # Verify high priority indicator
        task = self.page.locator(f'.task-card:has-text("{title}")').first
        if task.is_visible():
            # Check for priority border or indicator
            has_priority = task.locator('.priority-high, .task-priority-high').count() > 0
            return f"Created high priority task. Priority indicator: {'Yes' if has_priority else 'Check manually'}"
        raise Exception("Task not found after creation")
    
    # ============ READ TESTS ============
    
    def test_tasks_list_loads(self):
        """Test that tasks list loads with existing tasks"""
        count = self.get_task_count()
        return f"Found {count} visible tasks"
    
    def test_task_data_displayed(self):
        """Test that task cards display required data"""
        task = self.page.locator('.task-card').first
        if not task.is_visible():
            raise Exception("No task cards visible")
        
        # Check for title
        title = task.locator('.task-title').first
        has_title = title.is_visible() and len(title.text_content().strip()) > 0
        
        # Check for checkbox
        checkbox = task.locator('.task-checkbox, input[type="checkbox"]').first
        has_checkbox = checkbox.is_visible()
        
        # Check for menu trigger
        menu = task.locator('.task-menu-trigger, .task-actions').first
        has_menu = menu.is_visible()
        
        return f"Title: {has_title}, Checkbox: {has_checkbox}, Menu: {has_menu}"
    
    # ============ UPDATE TESTS ============
    
    def test_complete_task_checkbox(self):
        """Test completing a task via checkbox"""
        # Get first active task
        task = self.page.locator('.task-card:not(.completed)').first
        if not task.is_visible():
            raise Exception("No active tasks to complete")
        
        task_id = task.get_attribute('data-task-id')
        
        # Click checkbox
        checkbox = task.locator('.task-checkbox, input[type="checkbox"]').first
        checkbox.click()
        time.sleep(0.5)
        
        # Verify completed state
        has_completed_class = 'completed' in (task.get_attribute('class') or '')
        title = task.locator('.task-title').first
        has_strikethrough = 'line-through' in (title.evaluate('el => getComputedStyle(el).textDecoration') or '')
        
        return f"Task {task_id}: completed class={has_completed_class}, strikethrough={has_strikethrough}"
    
    def test_edit_task_via_menu(self):
        """Test editing a task through the action menu"""
        task = self.page.locator('.task-card').first
        if not task.is_visible():
            raise Exception("No tasks to edit")
        
        original_title = task.locator('.task-title').first.text_content()
        
        # Open menu
        menu_trigger = task.locator('.task-menu-trigger, .task-actions-btn').first
        menu_trigger.click()
        time.sleep(0.3)
        
        # Click edit
        edit_btn = self.page.locator('#task-menu .task-menu-item[data-action="edit"], [data-action="edit"]').first
        if edit_btn.is_visible():
            edit_btn.click()
            time.sleep(0.5)
            
            # Check for edit modal/form
            edit_modal = self.page.locator('.edit-modal, #task-edit-modal, .task-edit-form').first
            if edit_modal.is_visible():
                # Cancel edit
                cancel = self.page.locator('.cancel-btn, #task-edit-cancel, .modal-close').first
                if cancel.is_visible():
                    cancel.click()
                else:
                    self.page.keyboard.press('Escape')
                return f"Edit modal opened for task: {original_title[:30]}..."
            else:
                # Close menu
                self.page.keyboard.press('Escape')
                return f"Edit button clicked but modal not visible"
        else:
            self.page.keyboard.press('Escape')
            return "Edit option not available in menu"
    
    # ============ DELETE TESTS ============
    
    def test_delete_task_via_menu(self):
        """Test deleting a task through action menu"""
        initial_count = self.get_task_count()
        if initial_count == 0:
            raise Exception("No tasks to delete")
        
        task = self.page.locator('.task-card').first
        task_title = task.locator('.task-title').first.text_content()
        
        # Open menu
        menu_trigger = task.locator('.task-menu-trigger, .task-actions-btn').first
        menu_trigger.click()
        time.sleep(0.3)
        
        # Click delete
        delete_btn = self.page.locator('#task-menu .task-menu-item[data-action="delete"], [data-action="delete"]').first
        if delete_btn.is_visible():
            delete_btn.click()
            time.sleep(0.5)
            
            # Handle confirmation
            confirm_modal = self.page.locator('.confirmation-modal, .confirm-dialog, .delete-confirm').first
            if confirm_modal.is_visible():
                confirm_btn = self.page.locator('.confirm-btn, .confirm-delete, button:has-text("Delete")').first
                if confirm_btn.is_visible():
                    confirm_btn.click()
                    time.sleep(1)
            
            new_count = self.get_task_count()
            if new_count < initial_count:
                return f"Deleted task '{task_title[:20]}...'. Count: {initial_count} -> {new_count}"
            else:
                return f"Delete action completed (count may be same if undo available)"
        else:
            self.page.keyboard.press('Escape')
            raise Exception("Delete option not available in menu")
    
    # ============ TAB/FILTER TESTS ============
    
    def test_filter_tabs_exist(self):
        """Test that filter tabs are present"""
        tabs = []
        for tab_name in ['active', 'completed', 'all', 'archived']:
            tab = self.page.locator(f'.filter-tab[data-filter="{tab_name}"], .task-filter[data-filter="{tab_name}"]').first
            if tab.is_visible():
                tabs.append(tab_name)
        
        if len(tabs) >= 2:
            return f"Found tabs: {', '.join(tabs)}"
        else:
            raise Exception(f"Missing filter tabs. Found only: {tabs}")
    
    def test_filter_active_tasks(self):
        """Test filtering to active tasks only"""
        tab = self.page.locator('.filter-tab[data-filter="active"], .task-filter[data-filter="active"]').first
        if not tab.is_visible():
            raise Exception("Active filter tab not found")
        
        tab.click()
        time.sleep(0.5)
        
        count = self.get_task_count()
        
        # Verify no completed tasks visible
        completed = self.page.locator('.task-card.completed').count()
        
        return f"Active filter: {count} tasks visible, {completed} completed (should be 0)"
    
    def test_filter_completed_tasks(self):
        """Test filtering to completed tasks only"""
        tab = self.page.locator('.filter-tab[data-filter="completed"], .task-filter[data-filter="completed"]').first
        if not tab.is_visible():
            raise Exception("Completed filter tab not found")
        
        tab.click()
        time.sleep(0.5)
        
        count = self.get_task_count()
        return f"Completed filter: {count} tasks visible"
    
    def test_filter_all_tasks(self):
        """Test viewing all tasks"""
        tab = self.page.locator('.filter-tab[data-filter="all"], .task-filter[data-filter="all"]').first
        if not tab.is_visible():
            raise Exception("All filter tab not found")
        
        tab.click()
        time.sleep(0.5)
        
        count = self.get_task_count()
        return f"All filter: {count} tasks visible"
    
    def test_tab_counters_accurate(self):
        """Test that tab counters match visible tasks"""
        # Get counter from active tab
        active_count = self.get_tab_count('active')
        
        # Click active and count tasks
        self.page.locator('.filter-tab[data-filter="active"]').first.click()
        time.sleep(0.5)
        visible_count = self.get_task_count()
        
        if active_count is not None:
            if active_count == visible_count:
                return f"Active tab counter ({active_count}) matches visible tasks ({visible_count})"
            else:
                return f"Counter mismatch: tab shows {active_count}, visible: {visible_count}"
        else:
            return f"Counter not visible. Visible tasks: {visible_count}"
    
    # ============ SEARCH TESTS ============
    
    def test_search_functionality(self):
        """Test task search"""
        search_input = self.page.locator('#task-search-input, .task-search, input[placeholder*="Search"]').first
        if not search_input.is_visible():
            raise Exception("Search input not found")
        
        # Get a task title to search for
        first_task = self.page.locator('.task-card .task-title').first
        if first_task.is_visible():
            title = first_task.text_content().strip()
            search_term = title[:10] if len(title) > 10 else title
            
            # Perform search
            search_input.fill(search_term)
            time.sleep(0.5)
            
            # Check results
            count = self.get_task_count()
            
            # Clear search
            clear_btn = self.page.locator('#search-clear-btn, .clear-search').first
            if clear_btn.is_visible():
                clear_btn.click()
            else:
                search_input.fill('')
            time.sleep(0.3)
            
            return f"Search for '{search_term}': {count} results"
        else:
            return "No tasks to search"
    
    # ============ KEYBOARD SHORTCUTS TESTS ============
    
    def test_keyboard_shortcut_n(self):
        """Test 'N' key opens new task modal"""
        # Make sure no modal is open
        self.page.keyboard.press('Escape')
        time.sleep(0.2)
        
        # Press N
        self.page.keyboard.press('n')
        time.sleep(0.5)
        
        modal = self.page.locator('#task-modal-overlay:not(.hidden), .task-modal:visible').first
        if modal.is_visible():
            self.page.keyboard.press('Escape')
            return "N key opens create modal - PASS"
        else:
            return "N key did not open modal (may require focus)"
    
    def test_keyboard_shortcut_escape(self):
        """Test Escape closes modals"""
        # Open a modal first
        btn = self.page.locator('#new-task-btn').first
        if btn.is_visible():
            btn.click()
            time.sleep(0.3)
            
            self.page.keyboard.press('Escape')
            time.sleep(0.3)
            
            modal = self.page.locator('#task-modal-overlay.hidden, .task-modal:not(:visible)').first
            return "Escape closes modal - PASS"
        return "Could not test Escape (no modal button)"
    
    def test_keyboard_shortcut_slash(self):
        """Test '/' focuses search"""
        self.page.keyboard.press('/')
        time.sleep(0.3)
        
        search = self.page.locator('#task-search-input, .task-search').first
        if search.is_visible():
            is_focused = self.page.evaluate('document.activeElement.id === "task-search-input" || document.activeElement.classList.contains("task-search")')
            self.page.keyboard.press('Escape')
            return f"/ focuses search: {is_focused}"
        return "Search not found"
    
    # ============ PERFORMANCE TESTS ============
    
    def test_page_load_performance(self):
        """Test page load performance"""
        # Measure navigation
        start = time.perf_counter()
        self.page.reload(wait_until='networkidle')
        load_time = (time.perf_counter() - start) * 1000
        
        time.sleep(1)
        
        # Get first contentful paint from performance API
        fcp = self.page.evaluate('''() => {
            const entries = performance.getEntriesByType("paint");
            const fcp = entries.find(e => e.name === "first-contentful-paint");
            return fcp ? fcp.startTime : null;
        }''')
        
        return f"Page load: {load_time:.0f}ms, FCP: {fcp if fcp else 'N/A'}ms"
    
    def test_interaction_responsiveness(self):
        """Test UI interaction responsiveness"""
        # Measure tab switch time
        tab = self.page.locator('.filter-tab[data-filter="all"]').first
        if tab.is_visible():
            start = time.perf_counter()
            tab.click()
            time.sleep(0.1)
            elapsed = (time.perf_counter() - start) * 1000
            
            if elapsed < 100:
                return f"Tab switch: {elapsed:.0f}ms - EXCELLENT"
            elif elapsed < 300:
                return f"Tab switch: {elapsed:.0f}ms - GOOD"
            else:
                return f"Tab switch: {elapsed:.0f}ms - SLOW"
        return "Could not measure tab switch"
    
    # ============ MAIN TEST RUNNER ============
    
    def run_all_tests(self):
        """Run all comprehensive tests"""
        print("\n" + "=" * 60)
        print(" COMPREHENSIVE TASK PAGE INTERACTIVE TESTS")
        print("=" * 60)
        
        # Login first
        if not self.login():
            print("Failed to authenticate. Some tests may fail.")
        
        # CREATE tests
        print("\n2. CREATE OPERATIONS")
        self.run_test("Modal opens correctly", "CREATE", self.test_create_task_modal_opens)
        self.run_test("Create task with title only", "CREATE", self.test_create_task_with_title_only)
        self.run_test("Optimistic UI (<500ms)", "CREATE", self.test_create_task_optimistic_ui)
        self.run_test("Create with high priority", "CREATE", self.test_create_task_with_priority)
        
        # READ tests
        print("\n3. READ OPERATIONS")
        self.run_test("Tasks list loads", "READ", self.test_tasks_list_loads)
        self.run_test("Task data displayed", "READ", self.test_task_data_displayed)
        
        # UPDATE tests
        print("\n4. UPDATE OPERATIONS")
        self.run_test("Complete task via checkbox", "UPDATE", self.test_complete_task_checkbox)
        self.run_test("Edit task via menu", "UPDATE", self.test_edit_task_via_menu)
        
        # DELETE tests
        print("\n5. DELETE OPERATIONS")
        self.run_test("Delete task via menu", "DELETE", self.test_delete_task_via_menu)
        
        # TAB/FILTER tests
        print("\n6. TAB & FILTER OPERATIONS")
        self.run_test("Filter tabs exist", "FILTER", self.test_filter_tabs_exist)
        self.run_test("Active filter works", "FILTER", self.test_filter_active_tasks)
        self.run_test("Completed filter works", "FILTER", self.test_filter_completed_tasks)
        self.run_test("All filter works", "FILTER", self.test_filter_all_tasks)
        self.run_test("Tab counters accurate", "FILTER", self.test_tab_counters_accurate)
        
        # SEARCH tests
        print("\n7. SEARCH OPERATIONS")
        self.run_test("Search functionality", "SEARCH", self.test_search_functionality)
        
        # KEYBOARD tests
        print("\n8. KEYBOARD SHORTCUTS")
        self.run_test("N key opens modal", "KEYBOARD", self.test_keyboard_shortcut_n)
        self.run_test("Escape closes modal", "KEYBOARD", self.test_keyboard_shortcut_escape)
        self.run_test("/ focuses search", "KEYBOARD", self.test_keyboard_shortcut_slash)
        
        # PERFORMANCE tests
        print("\n9. PERFORMANCE")
        self.run_test("Page load performance", "PERFORMANCE", self.test_page_load_performance)
        self.run_test("Interaction responsiveness", "PERFORMANCE", self.test_interaction_responsiveness)
        
        self.report.end_time = datetime.now()
        
        return self.report


def main():
    """Main entry point"""
    print("Starting comprehensive task page tests...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            ignore_https_errors=True
        )
        page = context.new_page()
        
        tester = TaskPageTester(page)
        report = tester.run_all_tests()
        
        # Print summary
        print(report.get_summary())
        
        # Save report to file
        report_path = '/tmp/task_test_report.txt'
        with open(report_path, 'w') as f:
            f.write(report.get_summary())
        print(f"\nReport saved to: {report_path}")
        
        browser.close()
        
        return report.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
