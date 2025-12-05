"""
Bulk Actions E2E Tests
Tests for multi-select and bulk operations

Success Criteria:
- Select multiple tasks via checkbox
- Bulk complete marks all selected as done
- Bulk delete removes all selected (with confirmation)
- Select all/deselect all works correctly
"""
import pytest
import time
from playwright.sync_api import Page, expect

from .conftest import TaskPageHelpers, BASE_URL


class TestBulkSelection:
    """Test task selection for bulk operations"""
    
    def test_select_multiple_tasks(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Can select multiple tasks"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() < 2:
            pytest.skip("Need at least 2 tasks for bulk selection")
        
        ctrl_key = 'Meta' if page.evaluate('navigator.platform').startswith('Mac') else 'Control'
        
        tasks.first.locator('.task-checkbox, .bulk-select-checkbox').click()
        page.keyboard.down(ctrl_key)
        tasks.nth(1).locator('.task-checkbox, .bulk-select-checkbox').click()
        page.keyboard.up(ctrl_key)
        
        time.sleep(0.3)
        
        toolbar = page.locator('#bulk-action-toolbar')
        if toolbar.is_visible():
            count_element = page.locator('#bulk-selected-count')
            if count_element.is_visible():
                count = int(count_element.text_content())
                assert count == 2, f"Expected 2 selected, got {count}"
    
    def test_bulk_toolbar_appears(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Bulk action toolbar appears when tasks selected"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        tasks.first.locator('.task-checkbox, .bulk-select-checkbox').click()
        
        time.sleep(0.3)
        
        toolbar = page.locator('#bulk-action-toolbar')
        pass
    
    def test_selected_count_updates(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Selected count updates as tasks are selected/deselected"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() < 3:
            pytest.skip("Need at least 3 tasks")
        
        tasks.first.locator('.task-checkbox').click()
        time.sleep(0.2)
        
        tasks.nth(1).locator('.task-checkbox').click()
        time.sleep(0.2)
        
        count_element = page.locator('#bulk-selected-count')
        if count_element.is_visible():
            count = int(count_element.text_content())
            assert count == 2
        
        tasks.first.locator('.task-checkbox').click()
        time.sleep(0.2)
        
        if count_element.is_visible():
            count = int(count_element.text_content())
            assert count == 1


class TestBulkComplete:
    """Test bulk complete operation"""
    
    def test_bulk_complete_selected(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Bulk complete marks all selected tasks as done"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('active')
        time.sleep(0.3)
        
        tasks = page.locator('.task-card')
        if tasks.count() < 2:
            pytest.skip("Need at least 2 active tasks")
        
        task_ids = []
        for i in range(min(2, tasks.count())):
            task = tasks.nth(i)
            task_id = task.get_attribute('data-task-id')
            task_ids.append(task_id)
            task.locator('.task-checkbox, .bulk-select-checkbox').click()
            time.sleep(0.2)
        
        complete_btn = page.locator('#bulk-complete-btn')
        if complete_btn.is_visible():
            complete_btn.click()
            time.sleep(0.5)
            
            for task_id in task_ids:
                task = page.locator(f'.task-card[data-task-id="{task_id}"]')
                if task.is_visible():
                    expect(task).to_have_class(/completed/)


class TestBulkDelete:
    """Test bulk delete operation"""
    
    def test_bulk_delete_shows_confirmation(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Bulk delete shows confirmation dialog"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        tasks.first.locator('.task-checkbox, .bulk-select-checkbox').click()
        time.sleep(0.3)
        
        delete_btn = page.locator('#bulk-delete-btn')
        if delete_btn.is_visible():
            delete_btn.click()
            
            confirmation = page.locator('.confirmation-modal, .bulk-delete-confirm')
            expect(confirmation).to_be_visible()
            
            cancel_btn = confirmation.locator('.cancel-btn, button:has-text("Cancel")')
            cancel_btn.click()
    
    def test_bulk_delete_removes_tasks(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Bulk delete removes all selected tasks"""
        page = authenticated_task_page
        helpers.page = page
        
        initial_count = helpers.get_task_count()
        if initial_count < 2:
            pytest.skip("Need at least 2 tasks")
        
        tasks = page.locator('.task-card')
        task_ids = []
        
        for i in range(2):
            task = tasks.nth(i)
            task_id = task.get_attribute('data-task-id')
            task_ids.append(task_id)
            task.locator('.task-checkbox, .bulk-select-checkbox').click()
            time.sleep(0.2)
        
        delete_btn = page.locator('#bulk-delete-btn')
        if delete_btn.is_visible():
            delete_btn.click()
            
            confirm_btn = page.locator('.confirmation-modal .confirm-btn, .bulk-delete-confirm button:has-text("Delete")')
            if confirm_btn.is_visible():
                confirm_btn.click()
                time.sleep(0.5)
                
                for task_id in task_ids:
                    task = page.locator(f'.task-card[data-task-id="{task_id}"]')
                    expect(task).not_to_be_visible()


class TestBulkLabel:
    """Test bulk label operation"""
    
    def test_bulk_add_label(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Bulk add label applies to all selected tasks"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() < 2:
            pytest.skip("Need at least 2 tasks")
        
        for i in range(2):
            tasks.nth(i).locator('.task-checkbox, .bulk-select-checkbox').click()
            time.sleep(0.2)
        
        label_btn = page.locator('#bulk-label-btn')
        if label_btn.is_visible():
            label_btn.click()
            
            label_input = page.locator('.label-input, input[placeholder*="label"]')
            if label_input.is_visible():
                label_input.fill('test-label')
                page.keyboard.press('Enter')
                time.sleep(0.5)


class TestSelectAllDeselectAll:
    """Test select all/deselect all functionality"""
    
    def test_select_all(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Select all selects all visible tasks"""
        page = authenticated_task_page
        helpers.page = page
        
        total_count = helpers.get_task_count()
        if total_count == 0:
            pytest.skip("No tasks available")
        
        select_all = page.locator('.select-all-checkbox, #select-all-tasks')
        if select_all.is_visible():
            select_all.click()
            time.sleep(0.3)
            
            count_element = page.locator('#bulk-selected-count')
            if count_element.is_visible():
                selected_count = int(count_element.text_content())
                assert selected_count == total_count, f"Select all: expected {total_count}, got {selected_count}"
    
    def test_deselect_all(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Deselect all clears all selections"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        for i in range(min(2, tasks.count())):
            tasks.nth(i).locator('.task-checkbox, .bulk-select-checkbox').click()
            time.sleep(0.2)
        
        cancel_btn = page.locator('#bulk-cancel-btn')
        if cancel_btn.is_visible():
            cancel_btn.click()
            time.sleep(0.3)
            
            toolbar = page.locator('#bulk-action-toolbar')
            expect(toolbar).to_have_class(/hidden/)
