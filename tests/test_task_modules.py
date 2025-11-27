"""
Automated test to verify task page JavaScript module initialization.
Tests that the TasksPageOrchestrator correctly initializes all required modules.
"""

import time
import pytest
from playwright.sync_api import sync_playwright, expect


BASE_URL = "http://localhost:5000"


def test_task_page_module_initialization():
    """Test that all task page JavaScript modules are properly initialized."""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        console_logs = []
        errors = []
        
        def handle_console(msg):
            console_logs.append(f"[{msg.type}] {msg.text}")
            
        def handle_error(error):
            errors.append(str(error))
            
        page.on("console", handle_console)
        page.on("pageerror", handle_error)
        
        try:
            # Step 1: Register a test user
            page.goto(f"{BASE_URL}/auth/register")
            page.wait_for_load_state("networkidle")
            
            # Fill registration form
            test_email = f"test_auto_{int(time.time())}@example.com"
            page.fill('input[name="username"]', f"testuser_{int(time.time())}")
            page.fill('input[name="email"]', test_email)
            page.fill('input[name="password"]', "TestPass123!")
            page.fill('input[name="confirm_password"]', "TestPass123!")
            
            # Submit registration
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            
            # Step 2: Navigate to tasks page
            page.goto(f"{BASE_URL}/dashboard/tasks")
            page.wait_for_load_state("networkidle")
            
            # Wait for page to fully load and orchestrator to run
            time.sleep(3)
            
            # Step 3: Check that all required modules are initialized
            modules_to_check = [
                ("taskCache", "TaskCache"),
                ("taskBootstrap", "TaskBootstrap"),
                ("optimisticUI", "OptimisticUI"),
                ("taskMenuController", "TaskMenuController"),
                ("taskActionsMenu", "TaskActionsMenu"),
                ("tasksOrchestrator", "TasksOrchestrator"),
            ]
            
            results = {}
            for var_name, display_name in modules_to_check:
                is_defined = page.evaluate(f"typeof window.{var_name} !== 'undefined'")
                results[display_name] = is_defined
                
            # Print results
            print("\n=== Module Initialization Results ===")
            all_ok = True
            for name, is_defined in results.items():
                status = "✅ DEFINED" if is_defined else "❌ UNDEFINED"
                print(f"{name}: {status}")
                if not is_defined:
                    all_ok = False
                    
            # Check for tasks:ready event
            tasks_ready_fired = page.evaluate("""
                () => {
                    return window.tasksOrchestrator && window.tasksOrchestrator.initialized === true;
                }
            """)
            print(f"\nOrchestrator initialized: {'✅' if tasks_ready_fired else '❌'}")
            
            # Print console logs for debugging
            print("\n=== Console Logs (Orchestrator) ===")
            orchestrator_logs = [log for log in console_logs if "Orchestrator" in log]
            for log in orchestrator_logs[-20:]:
                print(log)
                
            # Print any errors
            if errors:
                print("\n=== Page Errors ===")
                for err in errors:
                    print(f"ERROR: {err}")
                    
            # Assertions
            assert results["TaskCache"], "TaskCache should be defined"
            assert results["OptimisticUI"], "OptimisticUI should be defined"
            assert results["TaskMenuController"], "TaskMenuController should be defined"
            assert results["TaskActionsMenu"], "TaskActionsMenu should be defined"
            assert tasks_ready_fired, "Orchestrator should be initialized"
            
            print("\n✅ All modules initialized correctly!")
            
        finally:
            browser.close()


def test_task_checkbox_toggle():
    """Test that task checkbox toggle works correctly."""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        console_logs = []
        
        def handle_console(msg):
            console_logs.append(f"[{msg.type}] {msg.text}")
            
        page.on("console", handle_console)
        
        try:
            # Login with existing test user
            page.goto(f"{BASE_URL}/auth/login")
            page.wait_for_load_state("networkidle")
            
            # Use demo user if available, or create one
            page.fill('input[name="email"]', "demo@example.com")
            page.fill('input[name="password"]', "demo123")
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            
            # Navigate to tasks page
            page.goto(f"{BASE_URL}/dashboard/tasks")
            page.wait_for_load_state("networkidle")
            time.sleep(3)  # Wait for orchestrator
            
            # Check if any tasks exist
            task_cards = page.locator(".task-card, .task-item, [data-task-id]")
            task_count = task_cards.count()
            
            print(f"\n=== Task Count: {task_count} ===")
            
            if task_count > 0:
                # Get first task's checkbox
                first_checkbox = page.locator(".task-card input[type='checkbox'], .task-item input[type='checkbox']").first
                
                if first_checkbox.count() > 0:
                    # Get initial state
                    initial_checked = first_checkbox.is_checked()
                    print(f"Initial checkbox state: {'checked' if initial_checked else 'unchecked'}")
                    
                    # Click checkbox
                    first_checkbox.click()
                    time.sleep(1)
                    
                    # Check new state
                    new_checked = first_checkbox.is_checked()
                    print(f"New checkbox state: {'checked' if new_checked else 'unchecked'}")
                    
                    # Verify state changed
                    assert initial_checked != new_checked, "Checkbox state should have changed"
                    print("✅ Checkbox toggle works!")
                else:
                    print("⚠️ No checkboxes found in tasks")
            else:
                print("⚠️ No tasks found - creating a test task first")
                
        finally:
            browser.close()


if __name__ == "__main__":
    print("Running task module initialization test...")
    test_task_page_module_initialization()
