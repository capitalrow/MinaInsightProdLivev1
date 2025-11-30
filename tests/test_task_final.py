"""
Final automated test for task page JavaScript module initialization and functionality.
"""

import time
from playwright.sync_api import sync_playwright


BASE_URL = "http://localhost:5000"


def run_test():
    """Complete test of task page module initialization."""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        console_logs = []
        
        def handle_console(msg):
            console_logs.append(f"[{msg.type}] {msg.text}")
            
        page.on("console", handle_console)
        
        try:
            # Register a new test user
            print("\n=== Registering new test user ===")
            page.goto(f"{BASE_URL}/auth/register")
            page.wait_for_load_state("networkidle")
            
            ts = int(time.time())
            test_username = f"finaltest_{ts}"
            test_email = f"finaltest_{ts}@example.com"
            
            page.fill('input[name="username"]', test_username)
            page.fill('input[name="email"]', test_email)
            page.fill('input[name="password"]', "TestPass123!")
            page.fill('input[name="confirm_password"]', "TestPass123!")
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            
            print(f"Registered: {test_email}")
            
            # Navigate to tasks page
            print("\n=== Navigating to tasks page ===")
            page.goto(f"{BASE_URL}/dashboard/tasks")
            page.wait_for_load_state("networkidle")
            time.sleep(3)  # Wait for orchestrator
            
            # Test 1: Check module initialization
            print("\n=== TEST 1: Module Initialization ===")
            modules = page.evaluate("""
                () => ({
                    taskCache: typeof window.taskCache !== 'undefined' && window.taskCache !== null,
                    optimisticUI: typeof window.optimisticUI !== 'undefined' && window.optimisticUI !== null,
                    taskMenuController: typeof window.taskMenuController !== 'undefined' && window.taskMenuController !== null,
                    taskActionsMenu: typeof window.taskActionsMenu !== 'undefined' && window.taskActionsMenu !== null,
                    tasksOrchestrator: typeof window.tasksOrchestrator !== 'undefined' && window.tasksOrchestrator !== null,
                    orchestratorInitialized: window.tasksOrchestrator && window.tasksOrchestrator.initialized === true
                })
            """)
            
            print("Module Status:")
            all_pass = True
            for name, status in modules.items():
                icon = "✅" if status else "❌"
                print(f"  {icon} {name}: {status}")
                if not status:
                    all_pass = False
            
            # Test 2: Check OptimisticUI core methods
            print("\n=== TEST 2: OptimisticUI Methods ===")
            methods = page.evaluate("""
                () => {
                    const ui = window.optimisticUI;
                    if (!ui) return { error: 'OptimisticUI is null' };
                    return {
                        completeTask: typeof ui.completeTask === 'function',
                        toggleTaskStatus: typeof ui.toggleTaskStatus === 'function',
                        updatePriority: typeof ui.updatePriority === 'function',
                        deleteTask: typeof ui.deleteTask === 'function',
                        createTask: typeof ui.createTask === 'function',
                        archiveTask: typeof ui.archiveTask === 'function'
                    };
                }
            """)
            
            if 'error' in methods:
                print(f"  ❌ {methods['error']}")
                all_pass = False
            else:
                for name, exists in methods.items():
                    icon = "✅" if exists else "❌"
                    print(f"  {icon} {name}: {exists}")
                    if not exists:
                        all_pass = False
            
            # Test 3: Check TaskMenuController methods
            print("\n=== TEST 3: TaskMenuController Methods ===")
            menu_methods = page.evaluate("""
                () => {
                    const ctrl = window.taskMenuController;
                    if (!ctrl) return { error: 'TaskMenuController is null' };
                    return {
                        executeAction: typeof ctrl.executeAction === 'function',
                        closeMenu: typeof ctrl.closeMenu === 'function',
                        handleToggleStatus: typeof ctrl.handleToggleStatus === 'function',
                        handlePriority: typeof ctrl.handlePriority === 'function',
                        handleDelete: typeof ctrl.handleDelete === 'function'
                    };
                }
            """)
            
            if 'error' in menu_methods:
                print(f"  ❌ {menu_methods['error']}")
                all_pass = False
            else:
                for name, exists in menu_methods.items():
                    icon = "✅" if exists else "❌"
                    print(f"  {icon} {name}: {exists}")
                    if not exists:
                        all_pass = False
            
            # Test 4: Check Orchestrator registered modules
            print("\n=== TEST 4: Orchestrator Modules ===")
            ready_event = page.evaluate("""
                () => {
                    return {
                        orchestratorModules: window.tasksOrchestrator ? 
                            Object.keys(window.tasksOrchestrator.modules || {}) : [],
                        initPromiseExists: window.tasksReady !== undefined
                    };
                }
            """)
            
            print(f"  Registered modules: {ready_event['orchestratorModules']}")
            print(f"  tasksReady promise exists: {ready_event['initPromiseExists']}")
            
            expected_modules = ['taskBootstrap', 'optimisticUI', 'taskMenuController', 'taskActionsMenu']
            for mod in expected_modules:
                if mod in ready_event['orchestratorModules']:
                    print(f"  ✅ {mod} registered")
                else:
                    print(f"  ❌ {mod} NOT registered")
                    all_pass = False
            
            # Print orchestrator console logs
            print("\n=== Orchestrator Console Logs ===")
            orch_logs = [log for log in console_logs if 'Orchestrator' in log]
            for log in orch_logs:
                print(f"  {log}")
            
            # Final verdict
            print("\n" + "="*60)
            if all_pass:
                print("✅ ALL TESTS PASSED!")
                print("   Module initialization race condition has been FIXED!")
                print("   All 4 core modules are properly initialized and ready.")
                return True
            else:
                print("❌ SOME TESTS FAILED - Check the output above")
                return False
            
        finally:
            browser.close()


if __name__ == "__main__":
    success = run_test()
    exit(0 if success else 1)
