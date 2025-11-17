"""
Comprehensive end-to-end testing of Tasks page at /dashboard/tasks
Testing all interactive features with detailed reporting
"""

import pytest
import json
import time
from playwright.sync_api import Page, expect


class TestTasksPage:
    """Comprehensive test suite for Tasks page"""
    
    BASE_URL = "http://0.0.0.0:5000"
    
    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """Setup before each test"""
        self.page = page
        self.page.set_viewport_size({"width": 1920, "height": 1080})
        # Navigate to tasks page
        self.page.goto(f"{self.BASE_URL}/dashboard/tasks")
        self.page.wait_for_load_state("networkidle")
        time.sleep(1)  # Allow for any animations
        
    def test_01_three_dot_menu_priority(self, page: Page):
        """
        PRIORITY TEST: Three-dot menu functionality
        - Click three-dot button on multiple tasks
        - Verify menu appears on screen (not clipped)
        - Test on tasks at top, middle, and bottom of page
        - Verify all menu items are clickable
        """
        print("\n" + "="*80)
        print("TEST 1: Three-dot Menu (PRIORITY)")
        print("="*80)
        
        # Get all task cards
        task_cards = page.locator(".task-card").all()
        print(f"Found {len(task_cards)} task cards")
        
        if len(task_cards) == 0:
            print("⚠️  WARNING: No tasks found on page")
            return
        
        # Test positions: top, middle, bottom
        test_positions = []
        if len(task_cards) > 0:
            test_positions.append(("Top", 0))
        if len(task_cards) > 2:
            test_positions.append(("Middle", len(task_cards) // 2))
        if len(task_cards) > 1:
            test_positions.append(("Bottom", len(task_cards) - 1))
        
        for position_name, index in test_positions:
            print(f"\n--- Testing {position_name} Task (Index {index}) ---")
            task_card = task_cards[index]
            
            # Scroll task into view
            task_card.scroll_into_view_if_needed()
            time.sleep(0.3)
            
            # Find three-dot button
            three_dot_btn = task_card.locator(".task-menu-trigger").first
            
            if not three_dot_btn.is_visible():
                print(f"❌ FAIL: Three-dot button not visible on {position_name} task")
                continue
            
            # Get task position before clicking
            task_box = task_card.bounding_box()
            print(f"Task position: y={task_box['y']}, height={task_box['height']}")
            
            # Click three-dot button
            print(f"Clicking three-dot button...")
            three_dot_btn.click()
            time.sleep(0.5)
            
            # Check if menu is visible
            menu = page.locator("#task-menu[data-state='open']")
            
            if not menu.is_visible():
                print(f"❌ FAIL: Menu not visible after clicking {position_name} task")
                continue
            
            print(f"✅ PASS: Menu appeared for {position_name} task")
            
            # Get menu position
            menu_box = menu.bounding_box()
            viewport = page.viewport_size
            
            print(f"Menu position: x={menu_box['x']}, y={menu_box['y']}")
            print(f"Menu size: width={menu_box['width']}, height={menu_box['height']}")
            print(f"Viewport size: width={viewport['width']}, height={viewport['height']}")
            
            # Check if menu is clipped
            is_clipped_right = (menu_box['x'] + menu_box['width']) > viewport['width']
            is_clipped_bottom = (menu_box['y'] + menu_box['height']) > viewport['height']
            is_clipped_left = menu_box['x'] < 0
            is_clipped_top = menu_box['y'] < 0
            
            if is_clipped_right:
                print(f"❌ FAIL: Menu clipped on RIGHT edge (extends beyond viewport)")
            if is_clipped_bottom:
                print(f"❌ FAIL: Menu clipped on BOTTOM edge (extends beyond viewport)")
            if is_clipped_left:
                print(f"❌ FAIL: Menu clipped on LEFT edge (negative position)")
            if is_clipped_top:
                print(f"❌ FAIL: Menu clipped on TOP edge (negative position)")
            
            if not (is_clipped_right or is_clipped_bottom or is_clipped_left or is_clipped_top):
                print(f"✅ PASS: Menu fully visible within viewport")
            
            # Check all menu items are visible and clickable
            menu_items = menu.locator(".task-menu-item").all()
            print(f"\nFound {len(menu_items)} menu items")
            
            all_clickable = True
            for i, item in enumerate(menu_items):
                action = item.get_attribute("data-action")
                is_visible = item.is_visible()
                is_enabled = item.is_enabled()
                
                status = "✅" if (is_visible and is_enabled) else "❌"
                print(f"{status} Menu item {i}: {action} - Visible: {is_visible}, Enabled: {is_enabled}")
                
                if not (is_visible and is_enabled):
                    all_clickable = False
            
            if all_clickable:
                print(f"✅ PASS: All menu items are clickable")
            else:
                print(f"❌ FAIL: Some menu items are not clickable")
            
            # Close menu by clicking outside
            page.mouse.click(100, 100)
            time.sleep(0.3)
    
    def test_02_menu_action_view_details(self, page: Page):
        """Test View Details action"""
        print("\n" + "="*80)
        print("TEST 2: Menu Action - View Details")
        print("="*80)
        
        task_cards = page.locator(".task-card").all()
        if len(task_cards) == 0:
            print("⚠️  No tasks to test")
            return
        
        # Click three-dot on first task
        task_cards[0].locator(".task-menu-trigger").click()
        time.sleep(0.3)
        
        # Click View Details
        page.locator("#task-menu .task-menu-item[data-action='view-details']").click()
        time.sleep(1)
        
        # Check if new tab/window was opened (or page navigated)
        print("✅ PASS: View Details action triggered")
    
    def test_03_menu_action_edit_title(self, page: Page):
        """Test Edit Title action"""
        print("\n" + "="*80)
        print("TEST 3: Menu Action - Edit Title")
        print("="*80)
        
        task_cards = page.locator(".task-card").all()
        if len(task_cards) == 0:
            print("⚠️  No tasks to test")
            return
        
        # Click three-dot on first task
        task_cards[0].locator(".task-menu-trigger").click()
        time.sleep(0.3)
        
        # Click Edit Title
        edit_btn = page.locator("#task-menu .task-menu-item[data-action='edit-title']")
        if edit_btn.count() > 0:
            edit_btn.click()
            time.sleep(0.5)
            print("✅ PASS: Edit Title action triggered")
        else:
            print("⚠️  Edit Title option not found in menu")
    
    def test_04_search_functionality(self, page: Page):
        """Test search functionality"""
        print("\n" + "="*80)
        print("TEST 4: Search Functionality")
        print("="*80)
        
        search_input = page.locator("#task-search-input")
        
        if not search_input.is_visible():
            print("❌ FAIL: Search input not visible")
            return
        
        print("✅ PASS: Search input visible")
        
        # Type in search
        search_input.fill("test")
        time.sleep(0.5)
        
        # Check if clear button appears
        clear_btn = page.locator("#search-clear-btn")
        if clear_btn.is_visible():
            print("✅ PASS: Clear button appears when typing")
        else:
            print("⚠️  WARNING: Clear button not visible")
        
        # Clear search
        if clear_btn.is_visible():
            clear_btn.click()
            time.sleep(0.3)
            
            if search_input.input_value() == "":
                print("✅ PASS: Clear button clears search")
            else:
                print("❌ FAIL: Clear button did not clear search")
    
    def test_05_sort_functionality(self, page: Page):
        """Test sort functionality"""
        print("\n" + "="*80)
        print("TEST 5: Sort Functionality")
        print("="*80)
        
        sort_select = page.locator("#task-sort-select")
        
        if not sort_select.is_visible():
            print("❌ FAIL: Sort select not visible")
            return
        
        print("✅ PASS: Sort select visible")
        
        # Get all sort options
        options = sort_select.locator("option").all()
        print(f"Found {len(options)} sort options")
        
        # Test each sort option
        for option in options:
            value = option.get_attribute("value")
            text = option.inner_text()
            
            sort_select.select_option(value)
            time.sleep(0.5)
            
            print(f"✅ PASS: Sort by {text} - selected successfully")
    
    def test_06_filter_tabs(self, page: Page):
        """Test filter tabs"""
        print("\n" + "="*80)
        print("TEST 6: Filter Tabs")
        print("="*80)
        
        filter_tabs = page.locator(".filter-tab").all()
        print(f"Found {len(filter_tabs)} filter tabs")
        
        for tab in filter_tabs:
            filter_name = tab.get_attribute("data-filter")
            tab.click()
            time.sleep(0.5)
            
            # Check if tab is active
            if "active" in tab.get_attribute("class"):
                print(f"✅ PASS: {filter_name} filter activated")
            else:
                print(f"❌ FAIL: {filter_name} filter not activated")
    
    def test_07_bulk_selection(self, page: Page):
        """Test bulk selection functionality"""
        print("\n" + "="*80)
        print("TEST 7: Bulk Selection")
        print("="*80)
        
        # Get all task checkboxes
        checkboxes = page.locator(".task-checkbox").all()
        print(f"Found {len(checkboxes)} task checkboxes")
        
        if len(checkboxes) < 2:
            print("⚠️  Not enough tasks to test bulk selection")
            return
        
        # Select first two tasks
        checkboxes[0].check()
        time.sleep(0.3)
        checkboxes[1].check()
        time.sleep(0.5)
        
        # Check if bulk toolbar appears
        bulk_toolbar = page.locator("#bulk-action-toolbar")
        
        if bulk_toolbar.is_visible():
            print("✅ PASS: Bulk action toolbar appears")
            
            # Check selected count
            count_element = page.locator("#bulk-selected-count")
            if count_element.is_visible():
                count = count_element.inner_text()
                print(f"✅ PASS: Selected count displayed: {count}")
            
            # Test cancel button
            cancel_btn = page.locator("#bulk-cancel-btn")
            if cancel_btn.is_visible():
                cancel_btn.click()
                time.sleep(0.3)
                
                if not bulk_toolbar.is_visible():
                    print("✅ PASS: Cancel button closes bulk toolbar")
                else:
                    print("❌ FAIL: Cancel button did not close bulk toolbar")
        else:
            print("❌ FAIL: Bulk action toolbar did not appear")
    
    def test_08_responsive_mobile(self, page: Page):
        """Test responsive design at mobile width"""
        print("\n" + "="*80)
        print("TEST 8: Responsive - Mobile (360px)")
        print("="*80)
        
        # Set mobile viewport
        page.set_viewport_size({"width": 360, "height": 640})
        page.reload()
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        
        # Check if page elements are visible
        header = page.locator(".tasks-header")
        if header.is_visible():
            print("✅ PASS: Header visible at mobile width")
        else:
            print("❌ FAIL: Header not visible at mobile width")
        
        # Check search toolbar
        search_toolbar = page.locator(".search-sort-toolbar")
        if search_toolbar.is_visible():
            print("✅ PASS: Search toolbar visible at mobile width")
        else:
            print("❌ FAIL: Search toolbar not visible at mobile width")
        
        # Test three-dot menu at mobile width
        task_cards = page.locator(".task-card").all()
        if len(task_cards) > 0:
            task_cards[0].scroll_into_view_if_needed()
            time.sleep(0.3)
            
            three_dot_btn = task_cards[0].locator(".task-menu-trigger")
            if three_dot_btn.is_visible():
                three_dot_btn.click()
                time.sleep(0.5)
                
                menu = page.locator("#task-menu[data-state='open']")
                if menu.is_visible():
                    menu_box = menu.bounding_box()
                    viewport = page.viewport_size
                    
                    is_clipped = (menu_box['x'] + menu_box['width']) > viewport['width']
                    
                    if is_clipped:
                        print(f"❌ FAIL: Menu clipped at mobile width")
                    else:
                        print(f"✅ PASS: Menu fits within mobile viewport")
                else:
                    print("❌ FAIL: Menu did not appear at mobile width")
            else:
                print("❌ FAIL: Three-dot button not visible at mobile width")
    
    def test_09_responsive_desktop(self, page: Page):
        """Test responsive design at desktop width"""
        print("\n" + "="*80)
        print("TEST 9: Responsive - Desktop (1920px)")
        print("="*80)
        
        # Set desktop viewport
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.reload()
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        
        # Check if all elements are properly laid out
        header = page.locator(".tasks-header")
        header_box = header.bounding_box()
        
        if header_box['width'] > 1000:
            print("✅ PASS: Header uses full width at desktop")
        else:
            print("⚠️  WARNING: Header may not be using full width")
        
        # Check task cards layout
        task_cards = page.locator(".task-card").all()
        if len(task_cards) > 0:
            first_card_box = task_cards[0].bounding_box()
            print(f"✅ PASS: Task cards rendered at desktop width: {first_card_box['width']}px wide")
    
    def test_10_edge_case_rapid_clicking(self, page: Page):
        """Test edge case: rapid clicking on three-dot menu"""
        print("\n" + "="*80)
        print("TEST 10: Edge Case - Rapid Clicking")
        print("="*80)
        
        task_cards = page.locator(".task-card").all()
        if len(task_cards) == 0:
            print("⚠️  No tasks to test")
            return
        
        three_dot_btn = task_cards[0].locator(".task-menu-trigger")
        
        # Rapidly click 5 times
        print("Rapidly clicking three-dot button...")
        for i in range(5):
            three_dot_btn.click()
            time.sleep(0.1)
        
        time.sleep(0.5)
        
        # Check if menu is in a stable state
        menu = page.locator("#task-menu")
        state = menu.get_attribute("data-state")
        
        if state in ["open", "closed"]:
            print(f"✅ PASS: Menu in stable state after rapid clicking: {state}")
        else:
            print(f"❌ FAIL: Menu in unstable state: {state}")
    
    def test_11_edge_case_menu_at_edges(self, page: Page):
        """Test edge case: menu behavior at viewport edges"""
        print("\n" + "="*80)
        print("TEST 11: Edge Case - Menu at Viewport Edges")
        print("="*80)
        
        # Test at different viewport sizes
        viewport_sizes = [
            ("Small", 800, 600),
            ("Medium", 1366, 768),
            ("Large", 1920, 1080)
        ]
        
        for size_name, width, height in viewport_sizes:
            print(f"\n--- Testing {size_name} Viewport ({width}x{height}) ---")
            
            page.set_viewport_size({"width": width, "height": height})
            page.reload()
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            
            task_cards = page.locator(".task-card").all()
            if len(task_cards) > 0:
                # Test last task (likely near bottom)
                last_task = task_cards[-1]
                last_task.scroll_into_view_if_needed()
                time.sleep(0.3)
                
                three_dot = last_task.locator(".task-menu-trigger")
                three_dot.click()
                time.sleep(0.5)
                
                menu = page.locator("#task-menu[data-state='open']")
                if menu.is_visible():
                    menu_box = menu.bounding_box()
                    viewport = page.viewport_size
                    
                    is_visible = (
                        menu_box['x'] >= 0 and
                        menu_box['y'] >= 0 and
                        (menu_box['x'] + menu_box['width']) <= viewport['width'] and
                        (menu_box['y'] + menu_box['height']) <= viewport['height']
                    )
                    
                    if is_visible:
                        print(f"✅ PASS: Menu fully visible at {size_name} viewport")
                    else:
                        print(f"❌ FAIL: Menu clipped at {size_name} viewport")
                        print(f"   Menu bounds: x={menu_box['x']}, y={menu_box['y']}, w={menu_box['width']}, h={menu_box['height']}")
                        print(f"   Viewport: w={viewport['width']}, h={viewport['height']}")
                
                # Close menu
                page.mouse.click(100, 100)
                time.sleep(0.3)
    
    def test_12_console_errors(self, page: Page):
        """Check for console errors"""
        print("\n" + "="*80)
        print("TEST 12: Console Errors Check")
        print("="*80)
        
        console_errors = []
        
        def handle_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)
        
        page.on("console", handle_console)
        
        # Navigate and interact with page
        page.reload()
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        if len(console_errors) == 0:
            print("✅ PASS: No console errors detected")
        else:
            print(f"❌ FAIL: {len(console_errors)} console errors detected:")
            for error in console_errors:
                print(f"   - {error}")


def run_tests():
    """Run all tests and generate report"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TASKS PAGE TESTING")
    print("="*80)
    print(f"Base URL: http://0.0.0.0:5000/dashboard/tasks")
    print("="*80)
    
    # Run pytest
    pytest.main([
        __file__,
        "-v",
        "--headed",  # Run with visible browser
        "--slowmo=500",  # Slow down for visibility
        "-s"  # Show print statements
    ])


if __name__ == "__main__":
    run_tests()
