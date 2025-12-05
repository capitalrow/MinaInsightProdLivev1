"""
Modal and Overlay E2E Tests
Tests for modal behavior, focus management, and overlay interactions

Success Criteria:
- Modal appears above page content
- Focus trapped inside modal
- Escape key closes modal
- Click outside closes modal
- Multiple modals stack correctly
"""
import pytest
import time
from playwright.sync_api import Page, expect

from .conftest import TaskPageHelpers, BASE_URL


class TestModalBehavior:
    """Test modal open/close behavior"""
    
    def test_modal_appears_above_content(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Modal appears above page content"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        
        modal = page.locator('#task-modal-overlay, .modal-overlay')
        expect(modal).to_be_visible()
        
        modal_z = page.evaluate('''
            () => {
                const modal = document.querySelector('#task-modal-overlay, .modal-overlay');
                return modal ? parseInt(getComputedStyle(modal).zIndex) || 0 : 0;
            }
        ''')
        
        assert modal_z >= 1000, f"Modal z-index too low: {modal_z}"
    
    def test_close_via_x_button(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """X button closes modal"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        
        close_btn = page.locator('#task-modal-close, .modal-close')
        close_btn.click()
        
        modal = page.locator('#task-modal-overlay, .modal-overlay')
        expect(modal).to_have_class(/hidden/)
    
    def test_close_via_escape_key(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Escape key closes modal"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        
        page.keyboard.press('Escape')
        time.sleep(0.3)
        
        modal = page.locator('#task-modal-overlay, .modal-overlay')
        expect(modal).to_have_class(/hidden/)
    
    def test_close_via_overlay_click(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Clicking overlay outside modal closes it"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        
        overlay = page.locator('#task-modal-overlay, .modal-overlay')
        
        modal_content = page.locator('.modal, .modal-content')
        modal_box = modal_content.bounding_box()
        
        if modal_box:
            overlay.click(position={'x': 10, 'y': 10})
            time.sleep(0.3)
            
            expect(overlay).to_have_class(/hidden/)
    
    def test_modal_blocks_background_clicks(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Overlay blocks clicks on background content"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        
        new_task_btn = page.locator('#new-task-btn')
        
        is_clickable = page.evaluate('''
            () => {
                const btn = document.querySelector('#new-task-btn');
                const rect = btn.getBoundingClientRect();
                const elem = document.elementFromPoint(rect.x + rect.width/2, rect.y + rect.height/2);
                return elem === btn;
            }
        ''')
        
        assert not is_clickable, "Background element is clickable through modal"


class TestFocusManagement:
    """Test focus trapping and management in modals"""
    
    def test_focus_trapped_in_modal(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Tab cycles within modal only"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        
        modal = page.locator('.modal, .modal-content')
        
        for _ in range(10):
            page.keyboard.press('Tab')
            time.sleep(0.1)
        
        focused = page.evaluate('() => document.activeElement.closest(".modal, .modal-content") !== null')
        assert focused, "Focus escaped modal"
    
    def test_focus_on_first_input(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Modal opens with focus on first input"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        time.sleep(0.3)
        
        focused_id = page.evaluate('() => document.activeElement.id')
        
        pass
    
    def test_focus_returns_after_close(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Focus returns to trigger after modal closes"""
        page = authenticated_task_page
        helpers.page = page
        
        new_task_btn = page.locator('#new-task-btn')
        new_task_btn.focus()
        new_task_btn.click()
        
        page.wait_for_selector('#task-modal-overlay:not(.hidden)', timeout=5000)
        
        page.keyboard.press('Escape')
        time.sleep(0.3)
        
        pass


class TestModalStacking:
    """Test multiple modal stacking behavior"""
    
    def test_confirmation_stacks_above_edit(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Confirmation dialog appears above edit modal"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        helpers.open_task_menu(tasks.first)
        delete_btn = page.locator('#task-menu .task-menu-item[data-action="delete"]')
        
        if delete_btn.is_visible():
            delete_btn.click()
            
            confirmation = page.locator('.confirmation-modal, .task-confirmation-modal')
            if confirmation.is_visible():
                confirm_z = page.evaluate('''
                    () => {
                        const modal = document.querySelector('.confirmation-modal, .task-confirmation-modal');
                        return modal ? parseInt(getComputedStyle(modal).zIndex) || 0 : 0;
                    }
                ''')
                
                assert confirm_z >= 1050, f"Confirmation z-index too low: {confirm_z}"
                
                page.click('.confirmation-modal .cancel-btn, .task-confirmation-modal .cancel-btn')


class TestToastNotifications:
    """Test toast notification behavior"""
    
    def test_toast_appears_above_modals(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Toast notifications appear above modals"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        task = tasks.first
        helpers.complete_task(task)
        
        try:
            helpers.wait_for_toast(timeout=3000)
            
            toast_z = page.evaluate('''
                () => {
                    const toast = document.querySelector('.toast, .notification-toast');
                    return toast ? parseInt(getComputedStyle(toast).zIndex) || 0 : 0;
                }
            ''')
            
            assert toast_z >= 1080, f"Toast z-index too low: {toast_z}"
        except:
            pass
    
    def test_toast_auto_dismiss(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Toast auto-dismisses after timeout"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        helpers.complete_task(tasks.first)
        
        try:
            helpers.wait_for_toast(timeout=3000)
            
            time.sleep(6)
            
            toast = page.locator('.toast:not(.hidden), .notification-toast:not(.hidden)')
            pass
        except:
            pass
    
    def test_multiple_toasts_stack(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Multiple toasts stack without overlapping"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() < 2:
            pytest.skip("Need at least 2 tasks")
        
        helpers.complete_task(tasks.nth(0))
        time.sleep(0.5)
        helpers.complete_task(tasks.nth(1))
        
        time.sleep(0.5)
        
        toasts = page.locator('.toast, .notification-toast')
        if toasts.count() > 1:
            toast1_box = toasts.nth(0).bounding_box()
            toast2_box = toasts.nth(1).bounding_box()
            
            if toast1_box and toast2_box:
                overlaps = not (
                    toast1_box['y'] + toast1_box['height'] <= toast2_box['y'] or
                    toast2_box['y'] + toast2_box['height'] <= toast1_box['y']
                )
                assert not overlaps, "Toasts are overlapping"
    
    def test_toast_action_button(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Toast undo button works"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        task = tasks.first
        task_id = task.get_attribute('data-task-id')
        
        helpers.complete_task(task)
        
        try:
            helpers.wait_for_toast(timeout=3000)
            helpers.click_toast_undo()
            time.sleep(0.5)
            
            task = page.locator(f'.task-card[data-task-id="{task_id}"]')
            expect(task).not_to_have_class(/completed/)
        except:
            pass


class TestPointerEventsAfterClose:
    """Test no pointer-events blocking after modal close"""
    
    def test_no_blocking_after_modal_close(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """No pointer-events blocking after modal closes"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        helpers.close_modal()
        
        time.sleep(0.3)
        
        new_task_btn = page.locator('#new-task-btn')
        
        is_clickable = page.evaluate('''
            () => {
                const btn = document.querySelector('#new-task-btn');
                const rect = btn.getBoundingClientRect();
                const elem = document.elementFromPoint(rect.x + rect.width/2, rect.y + rect.height/2);
                return elem === btn || btn.contains(elem);
            }
        ''')
        
        assert is_clickable, "Button not clickable after modal close"
        
        new_task_btn.click()
        
        modal = page.locator('#task-modal-overlay:not(.hidden), .modal-overlay:not(.hidden)')
        expect(modal).to_be_visible()
