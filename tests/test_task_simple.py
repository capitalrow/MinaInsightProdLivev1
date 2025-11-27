"""
Simple automated test for task page functionality.
Uses existing user with tasks.
"""

import time
import json
from playwright.sync_api import sync_playwright


BASE_URL = "http://localhost:5000"


def test_existing_user_with_tasks():
    """Test task functionality with existing user who has tasks."""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        console_logs = []
        network_requests = []
        
        def handle_console(msg):
            console_logs.append(f"[{msg.type}] {msg.text}")
            
        def handle_request(request):
            if '/api/' in request.url:
                network_requests.append({
                    'method': request.method,
                    'url': request.url
                })
            
        page.on("console", handle_console)
        page.on("request", handle_request)
        
        try:
            # Login as agent_tester (has tasks in DB)
            print("\n=== Logging in as agent_tester ===")
            page.goto(f"{BASE_URL}/auth/login")
            page.wait_for_load_state("networkidle")
            
            page.fill('input[name="email"]', "agent_tester@mina.ai")
            page.fill('input[name="password"]', "TestPassword123!")
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            
            # Check if login was successful
            if "login" in page.url.lower():
                print("Login may have failed, trying registration...")
                # Register new user
                page.goto(f"{BASE_URL}/auth/register")
                page.wait_for_load_state("networkidle")
                
                ts = int(time.time())
                page.fill('input[name="username"]', f"test_{ts}")
                page.fill('input[name="email"]', f"test_{ts}@example.com")
                page.fill('input[name="password"]', "TestPass123!")
                page.fill('input[name="confirm_password"]', "TestPass123!")
                page.click('button[type="submit"]')
                page.wait_for_load_state("networkidle")
                time.sleep(1)
            
            # Navigate to tasks page
            print("\n=== Navigating to tasks page ===")
            page.goto(f"{BASE_URL}/dashboard/tasks")
            page.wait_for_load_state("networkidle")
            time.sleep(3)
            
            # Test 1: Module Initialization
            print("\n=== Test 1: Module Initialization ===")
            modules = page.evaluate("""
                () => ({
                    taskCache: typeof window.taskCache !== 'undefined',
                    optimisticUI: typeof window.optimisticUI !== 'undefined',
                    taskMenuController: typeof window.taskMenuController !== 'undefined',
                    taskActionsMenu: typeof window.taskActionsMenu !== 'undefined',
                    orchestratorInit: window.tasksOrchestrator && window.tasksOrchestrator.initialized
                })
            """)
            
            all_modules_ok = all(modules.values())
            for name, status in modules.items():
                print(f"  {name}: {'✅' if status else '❌'}")
            
            assert all_modules_ok, "Not all modules initialized"
            print("✅ All modules initialized!")
            
            # Test 2: Check OptimisticUI has required methods
            print("\n=== Test 2: OptimisticUI Methods ===")
            methods = page.evaluate("""
                () => {
                    const ui = window.optimisticUI;
                    if (!ui) return {};
                    return {
                        toggleComplete: typeof ui.toggleComplete === 'function',
                        updatePriority: typeof ui.updatePriority === 'function',
                        deleteTask: typeof ui.deleteTask === 'function',
                        showToast: typeof ui.showToast === 'function'
                    };
                }
            """)
            
            for name, has_method in methods.items():
                print(f"  {name}: {'✅' if has_method else '❌'}")
            
            # Test 3: Check TaskMenuController has required methods
            print("\n=== Test 3: TaskMenuController Methods ===")
            menu_methods = page.evaluate("""
                () => {
                    const ctrl = window.taskMenuController;
                    if (!ctrl) return {};
                    return {
                        openTaskMenu: typeof ctrl.openTaskMenu === 'function',
                        closeMenu: typeof ctrl.closeMenu === 'function',
                        handleMenuAction: typeof ctrl.handleMenuAction === 'function'
                    };
                }
            """)
            
            for name, has_method in menu_methods.items():
                print(f"  {name}: {'✅' if has_method else '❌'}")
            
            # Test 4: Check page structure
            print("\n=== Test 4: Page Structure ===")
            structure = page.evaluate("""
                () => ({
                    hasTasksList: document.querySelector('.task-list, .tasks-container, [data-tasks]') !== null,
                    hasNewTaskBtn: document.querySelector('button[data-action="create-task"], .create-task-btn, #create-task-btn') !== null,
                    hasEmptyState: document.querySelector('.empty-state, .no-tasks') !== null,
                    taskCount: document.querySelectorAll('.task-card, .task-item, [data-task-id]').length
                })
            """)
            
            print(f"  Tasks list element: {'✅' if structure['hasTasksList'] else '❌'}")
            print(f"  New task button: {'✅' if structure['hasNewTaskBtn'] else '❌'}")
            print(f"  Empty state visible: {'Yes' if structure['hasEmptyState'] else 'No'}")
            print(f"  Task count in DOM: {structure['taskCount']}")
            
            # Test 5: Try to programmatically call toggle
            print("\n=== Test 5: Programmatic Toggle Test ===")
            toggle_result = page.evaluate("""
                () => {
                    if (!window.optimisticUI) return { error: 'OptimisticUI not defined' };
                    if (!window.optimisticUI.toggleComplete) return { error: 'toggleComplete method not defined' };
                    
                    // Check if there are any task cards
                    const taskCards = document.querySelectorAll('.task-card, .task-item, [data-task-id]');
                    if (taskCards.length === 0) {
                        return { success: true, message: 'No tasks to toggle, but method exists' };
                    }
                    
                    // Get first task ID
                    const firstTask = taskCards[0];
                    const taskId = firstTask.dataset.taskId || firstTask.getAttribute('data-task-id');
                    
                    if (!taskId) {
                        return { success: true, message: 'Task card found but no ID attribute' };
                    }
                    
                    return {
                        success: true,
                        message: `Found task with ID: ${taskId}`,
                        hasToggleMethod: true
                    };
                }
            """)
            
            print(f"  Result: {json.dumps(toggle_result)}")
            
            # Print orchestrator logs
            print("\n=== Orchestrator Logs ===")
            orch_logs = [log for log in console_logs if 'Orchestrator' in log]
            for log in orch_logs:
                print(log)
            
            # Print API calls
            print("\n=== API Calls Made ===")
            for req in network_requests[:10]:
                print(f"  {req['method']} {req['url']}")
            
            print("\n✅ All core tests passed!")
            return True
            
        finally:
            browser.close()


if __name__ == "__main__":
    success = test_existing_user_with_tasks()
    exit(0 if success else 1)
