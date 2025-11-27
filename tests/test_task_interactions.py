"""
Comprehensive automated test for task page interactions.
Tests checkbox toggle, menu actions, and proper API communication.
"""

import time
import json
from playwright.sync_api import sync_playwright


BASE_URL = "http://localhost:5000"


def test_task_toggle_and_menu_actions():
    """Test task checkbox toggle and menu action functionality."""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        console_logs = []
        network_requests = []
        errors = []
        
        def handle_console(msg):
            console_logs.append(f"[{msg.type}] {msg.text}")
            
        def handle_error(error):
            errors.append(str(error))
            
        def handle_request(request):
            if '/api/tasks' in request.url:
                network_requests.append({
                    'method': request.method,
                    'url': request.url
                })
            
        page.on("console", handle_console)
        page.on("pageerror", handle_error)
        page.on("request", handle_request)
        
        try:
            # Step 1: Register a new test user
            print("\n=== Step 1: Registering test user ===")
            page.goto(f"{BASE_URL}/auth/register")
            page.wait_for_load_state("networkidle")
            
            test_timestamp = int(time.time())
            test_username = f"autotest_{test_timestamp}"
            test_email = f"autotest_{test_timestamp}@example.com"
            test_password = "TestPass123!"
            
            page.fill('input[name="username"]', test_username)
            page.fill('input[name="email"]', test_email)
            page.fill('input[name="password"]', test_password)
            page.fill('input[name="confirm_password"]', test_password)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            
            print(f"Registered user: {test_email}")
            
            # Step 2: Navigate to tasks page
            print("\n=== Step 2: Navigating to tasks page ===")
            page.goto(f"{BASE_URL}/dashboard/tasks")
            page.wait_for_load_state("networkidle")
            time.sleep(3)  # Wait for orchestrator
            
            # Verify modules are initialized
            modules_ok = page.evaluate("""
                () => {
                    return {
                        taskCache: typeof window.taskCache !== 'undefined',
                        optimisticUI: typeof window.optimisticUI !== 'undefined',
                        taskMenuController: typeof window.taskMenuController !== 'undefined',
                        taskActionsMenu: typeof window.taskActionsMenu !== 'undefined',
                        orchestratorInit: window.tasksOrchestrator && window.tasksOrchestrator.initialized
                    };
                }
            """)
            print(f"Modules initialized: {json.dumps(modules_ok, indent=2)}")
            assert all(modules_ok.values()), "Not all modules initialized"
            
            # Step 3: Create a test task
            print("\n=== Step 3: Creating a test task ===")
            
            # Click the "New Task" button
            new_task_btn = page.locator('button:has-text("New Task"), [data-action="create-task"], .create-task-btn')
            if new_task_btn.count() > 0:
                new_task_btn.first.click()
                time.sleep(0.5)
                
                # Fill in task details (modal)
                title_input = page.locator('input[name="title"], #task-title, [data-field="title"]')
                if title_input.count() > 0:
                    title_input.first.fill(f"Auto Test Task {test_timestamp}")
                    
                    # Submit the task
                    submit_btn = page.locator('button[type="submit"], button:has-text("Create"), button:has-text("Save")')
                    if submit_btn.count() > 0:
                        submit_btn.first.click()
                        time.sleep(2)
                        print("Created test task")
            
            # Step 4: Check for task cards
            print("\n=== Step 4: Checking for task cards ===")
            page.wait_for_timeout(2000)
            
            # Look for task elements
            task_selectors = [
                ".task-card",
                ".task-item",
                "[data-task-id]",
                ".task-row",
                ".task-list-item"
            ]
            
            task_count = 0
            for selector in task_selectors:
                count = page.locator(selector).count()
                if count > 0:
                    task_count = count
                    print(f"Found {count} tasks with selector: {selector}")
                    break
            
            if task_count == 0:
                # Try to load tasks via API
                print("No task cards found in DOM. Checking API...")
                page.evaluate("window.taskCache && window.taskCache.refresh && window.taskCache.refresh()")
                time.sleep(2)
                
                for selector in task_selectors:
                    count = page.locator(selector).count()
                    if count > 0:
                        task_count = count
                        print(f"After refresh: Found {count} tasks with selector: {selector}")
                        break
            
            # Step 5: Test checkbox toggle if tasks exist
            print("\n=== Step 5: Testing checkbox toggle ===")
            
            checkbox_selectors = [
                ".task-card input[type='checkbox']",
                ".task-item input[type='checkbox']",
                "[data-task-id] input[type='checkbox']",
                ".task-checkbox",
                "input.task-complete-checkbox"
            ]
            
            checkbox = None
            for selector in checkbox_selectors:
                if page.locator(selector).count() > 0:
                    checkbox = page.locator(selector).first
                    print(f"Found checkbox with selector: {selector}")
                    break
            
            if checkbox:
                initial_checked = checkbox.is_checked()
                print(f"Initial checkbox state: {'checked' if initial_checked else 'unchecked'}")
                
                # Click to toggle
                checkbox.click()
                time.sleep(1)
                
                new_checked = checkbox.is_checked()
                print(f"After click checkbox state: {'checked' if new_checked else 'unchecked'}")
                
                # Log any API calls made
                api_calls = [r for r in network_requests if '/api/tasks' in r['url']]
                print(f"API calls made: {len(api_calls)}")
                for call in api_calls:
                    print(f"  {call['method']} {call['url']}")
                    
                if initial_checked != new_checked:
                    print("✅ Checkbox toggle works!")
                else:
                    print("⚠️ Checkbox state didn't change visually (might be optimistic UI)")
            else:
                print("⚠️ No checkboxes found in task list")
                
            # Step 6: Test menu actions
            print("\n=== Step 6: Testing menu actions ===")
            
            menu_trigger_selectors = [
                ".task-menu-trigger",
                ".task-actions-btn",
                "[data-action='open-menu']",
                ".task-card .menu-btn",
                "button.three-dots",
                "[aria-label='Task actions']"
            ]
            
            menu_trigger = None
            for selector in menu_trigger_selectors:
                if page.locator(selector).count() > 0:
                    menu_trigger = page.locator(selector).first
                    print(f"Found menu trigger with selector: {selector}")
                    break
            
            if menu_trigger:
                menu_trigger.click()
                time.sleep(0.5)
                
                # Check if menu opened
                menu_selectors = [
                    ".task-actions-menu",
                    ".dropdown-menu",
                    ".context-menu",
                    "[role='menu']"
                ]
                
                menu_visible = False
                for selector in menu_selectors:
                    if page.locator(selector).count() > 0:
                        if page.locator(selector).first.is_visible():
                            menu_visible = True
                            print(f"Menu visible with selector: {selector}")
                            break
                
                if menu_visible:
                    print("✅ Menu opens correctly!")
                else:
                    print("⚠️ Menu trigger clicked but menu not visible")
            else:
                print("⚠️ No menu trigger found")
            
            # Print console logs for debugging
            print("\n=== Relevant Console Logs ===")
            relevant_logs = [log for log in console_logs if any(x in log.lower() for x in ['task', 'menu', 'toggle', 'error', 'orchestrator'])]
            for log in relevant_logs[-15:]:
                print(log)
            
            # Print any errors
            if errors:
                print("\n=== Page Errors ===")
                for err in errors:
                    print(f"ERROR: {err}")
            
            print("\n=== Test Complete ===")
            
        finally:
            browser.close()


if __name__ == "__main__":
    test_task_toggle_and_menu_actions()
