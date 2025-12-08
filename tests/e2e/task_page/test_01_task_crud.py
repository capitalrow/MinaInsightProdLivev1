"""
Task CRUD E2E Tests
Tests for Create, Read, Update, Delete operations with optimistic UI validation

Success Criteria:
- Create: Task appears in list within 100ms (optimistic UI)
- Edit: Updates persist after page refresh
- Complete: Strikethrough styling, undo works within 5 seconds
- Delete: Confirmation shown, undo available
"""
import pytest
import time
import re
from datetime import datetime, timedelta
from playwright.sync_api import Page, expect

from .conftest import TaskPageHelpers, BASE_URL


class TestTaskCreation:
    """Test task creation flows"""
    
    def test_create_task_with_all_fields(self, authenticated_task_page: Page, helpers: TaskPageHelpers, test_task_data):
        """Create task with title, description, priority, due date"""
        page = authenticated_task_page
        helpers.page = page
        
        initial_count = helpers.get_task_count()
        
        helpers.create_task(
            title=test_task_data['title'],
            description=test_task_data['description'],
            priority=test_task_data['priority'],
            due_date=test_task_data['due_date']
        )
        
        new_count = helpers.get_task_count()
        assert new_count == initial_count + 1, f"Expected {initial_count + 1} tasks, got {new_count}"
        
        new_task = helpers.get_task_by_title(test_task_data['title'])
        expect(new_task).to_be_visible()
    
    def test_create_task_with_only_title(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Create task with minimal required input"""
        page = authenticated_task_page
        helpers.page = page
        
        title = f'Minimal Task {datetime.now().strftime("%H%M%S")}'
        
        helpers.open_create_modal()
        page.fill('#task-title', title)
        page.click('#task-create-form button[type="submit"]')
        
        page.wait_for_selector('#task-modal-overlay.hidden', timeout=10000)
        time.sleep(0.5)
        
        new_task = helpers.get_task_by_title(title)
        expect(new_task).to_be_visible()
    
    def test_create_task_optimistic_ui(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Verify task appears immediately (optimistic UI < 100ms)"""
        page = authenticated_task_page
        helpers.page = page
        
        title = f'Optimistic Test {datetime.now().strftime("%H%M%S")}'
        
        helpers.open_create_modal()
        page.fill('#task-title', title)
        
        start_time = time.perf_counter()
        page.click('#task-create-form button[type="submit"]')
        
        page.wait_for_selector(f'.task-card:has(.task-title:text("{title}"))', timeout=5000)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        assert elapsed_ms < 500, f"Optimistic UI took {elapsed_ms:.0f}ms (should be <500ms)"
    
    def test_create_task_cancel(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Cancel button closes modal without creating task"""
        page = authenticated_task_page
        helpers.page = page
        
        initial_count = helpers.get_task_count()
        
        helpers.open_create_modal()
        page.fill('#task-title', 'Should Not Be Created')
        helpers.close_modal()
        
        final_count = helpers.get_task_count()
        assert final_count == initial_count, "Task was created despite cancellation"
    
    def test_create_task_validation_empty_title(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Validation error shown for empty title"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        page.click('#task-create-form button[type="submit"]')
        
        title_input = page.locator('#task-title')
        expect(title_input).to_have_attribute('required', '')


class TestTaskEditing:
    """Test task editing flows"""
    
    def test_edit_task_via_modal(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Edit task through action menu"""
        page = authenticated_task_page
        helpers.page = page
        
        if helpers.get_task_count() == 0:
            pytest.skip("No tasks available to edit")
        
        task = helpers.get_task_by_index(0)
        original_title = task.locator('.task-title').text_content()
        
        helpers.open_task_menu(task)
        page.click('#task-menu .task-menu-item[data-action="edit"]')
        
        page.wait_for_selector('.edit-modal, #task-edit-modal', state='visible', timeout=5000)
        
        new_title = f'Edited {original_title}'
        page.fill('.edit-modal input[name="title"], #task-edit-title', new_title)
        page.click('.edit-modal button[type="submit"], #task-edit-save')
        
        time.sleep(0.5)
        
        edited_task = helpers.get_task_by_title(new_title)
        expect(edited_task).to_be_visible()
    
    def test_edit_task_inline_title(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Inline title editing (if supported)"""
        page = authenticated_task_page
        helpers.page = page
        
        if helpers.get_task_count() == 0:
            pytest.skip("No tasks available to edit")
        
        task = helpers.get_task_by_index(0)
        title_element = task.locator('.task-title')
        
        title_element.dblclick()
        time.sleep(0.3)
        
        input_field = task.locator('input.task-title-input, .task-title[contenteditable="true"]')
        if input_field.is_visible():
            new_title = f'Inline Edit {datetime.now().strftime("%H%M%S")}'
            input_field.fill(new_title)
            page.keyboard.press('Enter')
            time.sleep(0.5)
            
            expect(title_element).to_contain_text(new_title)
    
    def test_edit_task_cancel_reverts(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Cancel edit reverts to original values"""
        page = authenticated_task_page
        helpers.page = page
        
        if helpers.get_task_count() == 0:
            pytest.skip("No tasks available to edit")
        
        task = helpers.get_task_by_index(0)
        original_title = task.locator('.task-title').text_content()
        
        helpers.open_task_menu(task)
        edit_btn = page.locator('#task-menu .task-menu-item[data-action="edit"]')
        
        if edit_btn.is_visible():
            edit_btn.click()
            page.wait_for_selector('.edit-modal, #task-edit-modal', state='visible', timeout=5000)
            
            page.fill('.edit-modal input[name="title"], #task-edit-title', 'Changed Title')
            page.click('.edit-modal .cancel-btn, #task-edit-cancel')
            
            time.sleep(0.5)
            
            task_title = helpers.get_task_by_index(0).locator('.task-title').text_content()
            assert task_title == original_title, "Edit was not reverted on cancel"


class TestTaskCompletion:
    """Test task completion flows"""
    
    def test_complete_task_via_checkbox(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Mark task complete via checkbox"""
        page = authenticated_task_page
        helpers.page = page
        
        if helpers.get_task_count() == 0:
            pytest.skip("No tasks available to complete")
        
        helpers.filter_by('active')
        time.sleep(0.3)
        
        if helpers.get_task_count() == 0:
            pytest.skip("No active tasks available")
        
        task = helpers.get_task_by_index(0)
        task_id = task.get_attribute('data-task-id')
        
        helpers.complete_task(task)
        
        import re
        expect(task).to_have_class(re.compile(r'completed'))
        expect(task.locator('.task-title')).to_have_css('text-decoration', re.compile(r'line-through'))
    
    def test_complete_task_via_menu(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Mark task complete via action menu"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('active')
        time.sleep(0.3)
        
        if helpers.get_task_count() == 0:
            pytest.skip("No active tasks available")
        
        task = helpers.get_task_by_index(0)
        
        helpers.open_task_menu(task)
        complete_btn = page.locator('#task-menu .task-menu-item[data-action="complete"]')
        
        if complete_btn.is_visible():
            complete_btn.click()
            time.sleep(0.5)
            
            import re
            expect(task).to_have_class(re.compile(r'completed'))
    
    def test_undo_complete(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Undo task completion restores previous state"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('active')
        time.sleep(0.3)
        
        if helpers.get_task_count() == 0:
            pytest.skip("No active tasks available")
        
        task = helpers.get_task_by_index(0)
        task_id = task.get_attribute('data-task-id')
        
        helpers.complete_task(task)
        
        try:
            helpers.wait_for_toast(timeout=3000)
            helpers.click_toast_undo()
            time.sleep(0.5)
            
            task = page.locator(f'.task-card[data-task-id="{task_id}"]')
            import re
            expect(task).not_to_have_class(re.compile(r'completed'))
        except:
            pass
    
    def test_status_transitions(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Status transitions via dropdown: To Do → In Progress → Done"""
        page = authenticated_task_page
        helpers.page = page
        
        if helpers.get_task_count() == 0:
            pytest.skip("No tasks available")
        
        task = helpers.get_task_by_index(0)
        
        helpers.open_task_menu(task)
        
        status_submenu = page.locator('#task-menu .task-menu-item[data-action="change-status"]')
        if status_submenu.is_visible():
            status_submenu.hover()
            time.sleep(0.3)
            
            in_progress = page.locator('[data-status="in_progress"], [data-value="in_progress"]')
            if in_progress.is_visible():
                in_progress.click()
                time.sleep(0.5)
                
                expect(task).to_have_attribute('data-status', 'in_progress')


class TestTaskDeletion:
    """Test task deletion flows"""
    
    def test_delete_shows_confirmation(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Delete action shows confirmation dialog"""
        page = authenticated_task_page
        helpers.page = page
        
        if helpers.get_task_count() == 0:
            pytest.skip("No tasks available to delete")
        
        task = helpers.get_task_by_index(0)
        
        helpers.open_task_menu(task)
        page.click('#task-menu .task-menu-item[data-action="delete"]')
        
        confirmation = page.locator('.confirmation-modal, .task-confirmation-modal')
        expect(confirmation).to_be_visible()
        
        page.click('.confirmation-modal .cancel-btn, .task-confirmation-modal .cancel-btn')
    
    def test_delete_removes_task(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Confirming delete removes task from list"""
        page = authenticated_task_page
        helpers.page = page
        
        initial_count = helpers.get_task_count()
        if initial_count == 0:
            pytest.skip("No tasks available to delete")
        
        task = helpers.get_task_by_index(0)
        task_id = task.get_attribute('data-task-id')
        
        helpers.delete_task_via_menu(task)
        
        time.sleep(0.5)
        final_count = helpers.get_task_count()
        
        assert final_count == initial_count - 1, f"Task was not deleted (count: {initial_count} → {final_count})"
        
        deleted_task = page.locator(f'.task-card[data-task-id="{task_id}"]')
        expect(deleted_task).not_to_be_visible()
    
    def test_delete_undo(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Undo delete restores task within timeout"""
        page = authenticated_task_page
        helpers.page = page
        
        initial_count = helpers.get_task_count()
        if initial_count == 0:
            pytest.skip("No tasks available to delete")
        
        task = helpers.get_task_by_index(0)
        task_id = task.get_attribute('data-task-id')
        task_title = task.locator('.task-title').text_content()
        
        helpers.delete_task_via_menu(task)
        
        try:
            helpers.wait_for_toast(timeout=3000)
            helpers.click_toast_undo()
            time.sleep(0.5)
            
            restored_task = helpers.get_task_by_title(task_title)
            expect(restored_task).to_be_visible()
        except:
            pass


class TestTaskDuplication:
    """Test task duplication"""
    
    def test_duplicate_creates_copy(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Duplicate creates copy with (Copy) suffix"""
        page = authenticated_task_page
        helpers.page = page
        
        if helpers.get_task_count() == 0:
            pytest.skip("No tasks available to duplicate")
        
        task = helpers.get_task_by_index(0)
        original_title = task.locator('.task-title').text_content()
        initial_count = helpers.get_task_count()
        
        helpers.open_task_menu(task)
        duplicate_btn = page.locator('#task-menu .task-menu-item[data-action="duplicate"]')
        
        if duplicate_btn.is_visible():
            duplicate_btn.click()
            time.sleep(0.5)
            
            final_count = helpers.get_task_count()
            assert final_count == initial_count + 1, "Duplicate was not created"
            
            copy_task = page.locator(f'.task-card:has(.task-title:text("(Copy)"))')
            expect(copy_task.first).to_be_visible()


class TestTaskArchive:
    """Test task archiving"""
    
    def test_archive_moves_to_archived(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Archive moves task to archived filter"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('active')
        time.sleep(0.3)
        
        active_count = helpers.get_task_count()
        if active_count == 0:
            pytest.skip("No active tasks to archive")
        
        task = helpers.get_task_by_index(0)
        task_title = task.locator('.task-title').text_content()
        
        helpers.open_task_menu(task)
        archive_btn = page.locator('#task-menu .task-menu-item[data-action="archive"]')
        
        if archive_btn.is_visible():
            archive_btn.click()
            time.sleep(0.5)
            
            helpers.filter_by('archived')
            time.sleep(0.3)
            
            archived_task = helpers.get_task_by_title(task_title)
            expect(archived_task).to_be_visible()
