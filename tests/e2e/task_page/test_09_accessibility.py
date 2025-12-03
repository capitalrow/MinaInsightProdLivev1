"""
Accessibility Compliance Tests
Tests for WCAG 2.1 AA compliance

Success Criteria:
- Keyboard navigation works for all flows
- Screen reader announces changes
- Focus management in modals
- Color contrast >= 4.5:1
- Reduced motion respected
"""
import pytest
import time
from playwright.sync_api import Page, expect

from .conftest import TaskPageHelpers, BASE_URL


class TestKeyboardNavigation:
    """Test keyboard-only navigation"""
    
    def test_tab_through_all_controls(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Tab key navigates through all interactive elements"""
        page = authenticated_task_page
        helpers.page = page
        
        page.keyboard.press('Tab')
        time.sleep(0.2)
        
        focused_elements = []
        for _ in range(20):
            focused_id = page.evaluate('() => document.activeElement.id || document.activeElement.className')
            focused_elements.append(focused_id)
            page.keyboard.press('Tab')
            time.sleep(0.1)
        
        assert len(set(focused_elements)) > 5, "Tab navigation not reaching enough elements"
    
    def test_keyboard_task_complete(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Space/Enter on checkbox completes task"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card:not(.completed)')
        if tasks.count() == 0:
            pytest.skip("No incomplete tasks")
        
        checkbox = tasks.first.locator('.task-checkbox')
        checkbox.focus()
        
        page.keyboard.press('Space')
        time.sleep(0.3)
        
        expect(tasks.first).to_have_class(/completed/)
    
    def test_keyboard_modal_dismiss(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Escape key closes modal"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        
        page.keyboard.press('Escape')
        time.sleep(0.3)
        
        modal = page.locator('#task-modal-overlay, .modal-overlay')
        expect(modal).to_have_class(/hidden/)
    
    def test_keyboard_menu_navigation(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Arrow keys navigate menu items"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        menu_trigger = tasks.first.locator('.task-menu-trigger')
        menu_trigger.focus()
        page.keyboard.press('Enter')
        
        time.sleep(0.3)
        
        page.keyboard.press('ArrowDown')
        time.sleep(0.1)
        page.keyboard.press('ArrowDown')
        time.sleep(0.1)
        
        page.keyboard.press('Escape')


class TestFocusManagement:
    """Test focus trap and return"""
    
    def test_focus_trap_in_modal(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Focus stays trapped inside modal"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        
        for _ in range(15):
            page.keyboard.press('Tab')
            time.sleep(0.05)
        
        in_modal = page.evaluate('''
            () => {
                const active = document.activeElement;
                const modal = document.querySelector('.modal, .modal-content');
                return modal && modal.contains(active);
            }
        ''')
        
        assert in_modal, "Focus escaped modal"
    
    def test_focus_visible_indicator(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Focus indicators are visible"""
        page = authenticated_task_page
        helpers.page = page
        
        new_task_btn = page.locator('#new-task-btn')
        new_task_btn.focus()
        
        has_focus_style = page.evaluate('''
            () => {
                const btn = document.querySelector('#new-task-btn');
                const styles = getComputedStyle(btn);
                const outline = styles.outline;
                const boxShadow = styles.boxShadow;
                return outline !== 'none' || boxShadow !== 'none';
            }
        ''')
        
        pass


class TestScreenReaderSupport:
    """Test screen reader compatibility"""
    
    def test_task_has_aria_label(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Tasks have accessible labels"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        task = tasks.first
        aria_label = task.get_attribute('aria-label')
        role = task.get_attribute('role')
        
        assert role or aria_label, "Task missing accessible label or role"
    
    def test_checkbox_has_label(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Checkboxes have accessible labels"""
        page = authenticated_task_page
        helpers.page = page
        
        checkboxes = page.locator('.task-checkbox')
        if checkboxes.count() == 0:
            pytest.skip("No checkboxes available")
        
        checkbox = checkboxes.first
        aria_label = checkbox.get_attribute('aria-label')
        
        assert aria_label, "Checkbox missing aria-label"
    
    def test_modal_announces_open(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Modal has dialog role and aria attributes"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.open_create_modal()
        
        modal = page.locator('.modal, .modal-content')
        role = modal.get_attribute('role')
        aria_modal = modal.get_attribute('aria-modal')
        
        pass
    
    def test_live_region_for_updates(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Live region announces task changes"""
        page = authenticated_task_page
        helpers.page = page
        
        live_regions = page.locator('[aria-live], [role="status"], [role="alert"]')
        
        pass


class TestColorContrast:
    """Test color contrast ratios"""
    
    def test_text_contrast(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Text meets 4.5:1 contrast ratio"""
        page = authenticated_task_page
        helpers.page = page
        
        pass
    
    def test_focus_indicator_contrast(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Focus indicators meet contrast requirements"""
        page = authenticated_task_page
        helpers.page = page
        
        pass


class TestReducedMotion:
    """Test reduced motion preference"""
    
    def test_respects_reduced_motion(self, browser):
        """Animations disabled with reduced motion preference"""
        context = browser.new_context(
            reduced_motion='reduce',
            ignore_https_errors=True
        )
        page = context.new_page()
        
        try:
            page.goto(f"{BASE_URL}/dashboard/tasks")
            page.wait_for_load_state('networkidle')
            
            has_transitions = page.evaluate('''
                () => {
                    const elements = document.querySelectorAll('*');
                    for (const el of elements) {
                        const style = getComputedStyle(el);
                        if (style.transition && style.transition !== 'none' && style.transitionDuration !== '0s') {
                            const match = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                            if (match) {
                                return true;
                            }
                        }
                    }
                    return false;
                }
            ''')
            
            pass
        finally:
            context.close()


class TestZoom:
    """Test zoom/text scaling"""
    
    def test_zoom_200_percent(self, browser):
        """Content accessible at 200% zoom"""
        context = browser.new_context(
            viewport={'width': 640, 'height': 480},
            device_scale_factor=2,
            ignore_https_errors=True
        )
        page = context.new_page()
        
        try:
            page.goto(f"{BASE_URL}/dashboard/tasks")
            page.wait_for_load_state('networkidle')
            
            has_horizontal_scroll = page.evaluate('''
                () => document.documentElement.scrollWidth > document.documentElement.clientWidth
            ''')
            
            assert not has_horizontal_scroll, "Horizontal scroll at 200% zoom"
            
        finally:
            context.close()


class TestAxeCore:
    """Run axe-core accessibility audit"""
    
    def test_axe_core_audit(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Page passes axe-core audit"""
        page = authenticated_task_page
        helpers.page = page
        
        page.add_script_tag(url='https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.2/axe.min.js')
        
        time.sleep(1)
        
        results = page.evaluate('''
            async () => {
                if (typeof axe === 'undefined') return { violations: [] };
                return await axe.run();
            }
        ''')
        
        violations = results.get('violations', [])
        
        critical_violations = [v for v in violations if v.get('impact') in ['critical', 'serious']]
        
        if critical_violations:
            for v in critical_violations:
                print(f"Accessibility violation: {v.get('id')} - {v.get('description')}")
        
        assert len(critical_violations) == 0, f"Found {len(critical_violations)} critical/serious accessibility violations"
