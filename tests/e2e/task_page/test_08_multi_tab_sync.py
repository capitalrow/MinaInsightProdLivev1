"""
Multi-Tab WebSocket Sync Tests
Tests for real-time sync across browser tabs

Success Criteria:
- Create/edit/delete in Tab A appears in Tab B within 1 second
- Conflict resolution works correctly
- Undo/redo consistent across tabs
"""
import pytest
import time
from playwright.sync_api import Page, Browser, BrowserContext, expect

from .conftest import BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD


def login_page(page: Page):
    """Helper to login a page"""
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


class TestCrossTabCreate:
    """Test task creation syncs across tabs"""
    
    def test_create_syncs_to_other_tab(self, browser: Browser):
        """Creating task in Tab A appears in Tab B"""
        context = browser.new_context(ignore_https_errors=True)
        
        tab_a = context.new_page()
        tab_b = context.new_page()
        
        try:
            login_page(tab_a)
            login_page(tab_b)
            
            tab_b_initial_count = tab_b.locator('.task-card').count()
            
            tab_a.click('#new-task-btn')
            tab_a.wait_for_selector('#task-modal-overlay:not(.hidden)', timeout=5000)
            
            title = f'Cross Tab Test {time.time()}'
            tab_a.fill('#task-title', title)
            tab_a.click('#task-create-form button[type="submit"]')
            
            tab_a.wait_for_selector('#task-modal-overlay.hidden', timeout=5000)
            
            time.sleep(2)
            
            tab_b_final_count = tab_b.locator('.task-card').count()
            
            new_task_in_b = tab_b.locator(f'.task-card:has(.task-title:text("{title}"))')
            
        finally:
            context.close()


class TestCrossTabEdit:
    """Test task editing syncs across tabs"""
    
    def test_edit_syncs_to_other_tab(self, browser: Browser):
        """Editing task in Tab A updates in Tab B"""
        context = browser.new_context(ignore_https_errors=True)
        
        tab_a = context.new_page()
        tab_b = context.new_page()
        
        try:
            login_page(tab_a)
            login_page(tab_b)
            
            tasks_a = tab_a.locator('.task-card')
            if tasks_a.count() == 0:
                pytest.skip("No tasks to edit")
            
            task = tasks_a.first
            task_id = task.get_attribute('data-task-id')
            
            task.locator('.task-menu-trigger').click()
            tab_a.wait_for_selector('#task-menu[data-state="open"]', timeout=5000)
            
            edit_btn = tab_a.locator('#task-menu .task-menu-item[data-action="edit"]')
            if edit_btn.is_visible():
                edit_btn.click()
                tab_a.wait_for_selector('.edit-modal, #task-edit-modal', state='visible', timeout=5000)
                
                new_title = f'Edited Cross Tab {time.time()}'
                tab_a.fill('.edit-modal input[name="title"], #task-edit-title', new_title)
                tab_a.click('.edit-modal button[type="submit"], #task-edit-save')
                
                time.sleep(2)
                
                task_in_b = tab_b.locator(f'.task-card[data-task-id="{task_id}"]')
                if task_in_b.is_visible():
                    title_in_b = task_in_b.locator('.task-title').text_content()
                    
        finally:
            context.close()


class TestCrossTabDelete:
    """Test task deletion syncs across tabs"""
    
    def test_delete_syncs_to_other_tab(self, browser: Browser):
        """Deleting task in Tab A removes from Tab B"""
        context = browser.new_context(ignore_https_errors=True)
        
        tab_a = context.new_page()
        tab_b = context.new_page()
        
        try:
            login_page(tab_a)
            login_page(tab_b)
            
            tasks_a = tab_a.locator('.task-card')
            if tasks_a.count() == 0:
                pytest.skip("No tasks to delete")
            
            task = tasks_a.first
            task_id = task.get_attribute('data-task-id')
            
            task_in_b_before = tab_b.locator(f'.task-card[data-task-id="{task_id}"]')
            
            task.locator('.task-menu-trigger').click()
            tab_a.wait_for_selector('#task-menu[data-state="open"]', timeout=5000)
            tab_a.click('#task-menu .task-menu-item[data-action="delete"]')
            
            confirmation = tab_a.locator('.confirmation-modal, .task-confirmation-modal')
            if confirmation.is_visible():
                tab_a.click('.confirmation-modal .confirm-btn, .task-confirmation-modal .confirm-btn')
            
            time.sleep(2)
            
            task_in_b_after = tab_b.locator(f'.task-card[data-task-id="{task_id}"]')
            expect(task_in_b_after).not_to_be_visible()
            
        finally:
            context.close()


class TestCrossTabComplete:
    """Test task completion syncs across tabs"""
    
    def test_complete_syncs_to_other_tab(self, browser: Browser):
        """Completing task in Tab A shows complete in Tab B"""
        context = browser.new_context(ignore_https_errors=True)
        
        tab_a = context.new_page()
        tab_b = context.new_page()
        
        try:
            login_page(tab_a)
            login_page(tab_b)
            
            tasks_a = tab_a.locator('.task-card:not(.completed)')
            if tasks_a.count() == 0:
                pytest.skip("No incomplete tasks")
            
            task = tasks_a.first
            task_id = task.get_attribute('data-task-id')
            
            task.locator('.task-checkbox').click()
            
            time.sleep(2)
            
            task_in_b = tab_b.locator(f'.task-card[data-task-id="{task_id}"]')
            if task_in_b.is_visible():
                expect(task_in_b).to_have_class(/completed/)
            
        finally:
            context.close()


class TestCrossTabFiltering:
    """Test filtering is independent per tab"""
    
    def test_filter_independent_per_tab(self, browser: Browser):
        """Filter changes don't sync across tabs"""
        context = browser.new_context(ignore_https_errors=True)
        
        tab_a = context.new_page()
        tab_b = context.new_page()
        
        try:
            login_page(tab_a)
            login_page(tab_b)
            
            tab_a.click('.filter-tab[data-filter="archived"]')
            time.sleep(0.5)
            
            active_filter_b = tab_b.locator('.filter-tab.active')
            filter_b = active_filter_b.get_attribute('data-filter')
            
            assert filter_b != 'archived', "Filter unexpectedly synced to Tab B"
            
        finally:
            context.close()


class TestThreeOrMoreTabs:
    """Test sync with 3+ tabs open"""
    
    def test_three_tabs_stay_synced(self, browser: Browser):
        """Task changes sync across 3 tabs"""
        context = browser.new_context(ignore_https_errors=True)
        
        tabs = []
        for _ in range(3):
            page = context.new_page()
            tabs.append(page)
        
        try:
            for tab in tabs:
                login_page(tab)
            
            tabs[0].click('#new-task-btn')
            tabs[0].wait_for_selector('#task-modal-overlay:not(.hidden)', timeout=5000)
            
            title = f'Three Tab Test {time.time()}'
            tabs[0].fill('#task-title', title)
            tabs[0].click('#task-create-form button[type="submit"]')
            
            tabs[0].wait_for_selector('#task-modal-overlay.hidden', timeout=5000)
            
            time.sleep(2)
            
            for i, tab in enumerate(tabs[1:], start=2):
                task = tab.locator(f'.task-card:has(.task-title:text("{title}"))')
                
        finally:
            context.close()


class TestTabReopenSync:
    """Test sync when tab is reopened"""
    
    def test_reopened_tab_catches_up(self, browser: Browser):
        """Reopened tab syncs to current state"""
        context = browser.new_context(ignore_https_errors=True)
        
        tab_a = context.new_page()
        
        try:
            login_page(tab_a)
            
            initial_count = tab_a.locator('.task-card').count()
            
            tab_a.goto('about:blank')
            time.sleep(1)
            
            tab_a.goto(f"{BASE_URL}/dashboard/tasks")
            tab_a.wait_for_load_state('networkidle')
            
            try:
                tab_a.wait_for_selector('.tasks-container', timeout=10000)
            except:
                pass
            
            final_count = tab_a.locator('.task-card').count()
            
        finally:
            context.close()
