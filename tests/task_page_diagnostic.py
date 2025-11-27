"""
CROWN⁴.6 Task Page Diagnostic Test
Comprehensive automated diagnosis of the tasks page functionality.
"""

import asyncio
import json
import time
from playwright.async_api import async_playwright, Page, ConsoleMessage

class TaskPageDiagnostic:
    def __init__(self):
        self.console_logs = []
        self.console_errors = []
        self.network_errors = []
        self.results = {
            'js_errors': [],
            'console_logs': [],
            'initialization': {},
            'elements_found': {},
            'elements_missing': [],
            'api_responses': {},
            'performance': {}
        }
    
    def handle_console(self, msg: ConsoleMessage):
        """Capture all console messages"""
        text = msg.text
        msg_type = msg.type
        
        if msg_type == 'error':
            self.console_errors.append(text)
            self.results['js_errors'].append(text)
        else:
            self.console_logs.append(f"[{msg_type}] {text}")
            
        # Track specific initialization messages
        if '[Orchestrator]' in text:
            self.results['initialization']['orchestrator'] = text
        if '[TaskCache]' in text or 'TaskCache' in text:
            self.results['initialization']['task_cache'] = text
        if 'OptimisticUI' in text:
            self.results['initialization']['optimistic_ui'] = text
        if 'TaskActionsMenu' in text:
            self.results['initialization']['actions_menu'] = text
        if 'CROWN⁴.6' in text:
            self.results['initialization']['crown46'] = text
    
    async def run_diagnostic(self):
        """Run full diagnostic on tasks page"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Capture console messages
            page.on('console', self.handle_console)
            
            # Capture network failures
            page.on('requestfailed', lambda req: self.network_errors.append({
                'url': req.url,
                'failure': req.failure
            }))
            
            try:
                # Step 1: Login
                print("🔐 Step 1: Logging in...")
                await page.goto('http://127.0.0.1:5000/auth/login', timeout=30000)
                await page.wait_for_load_state('domcontentloaded')
                
                # Fill login form - form field names are email_or_username and password
                await page.fill('[name="email_or_username"]', 'agent_tester@mina.ai')
                await page.fill('[name="password"]', 'TestPassword123!')
                await page.click('button[type="submit"]')
                
                # Wait for navigation
                await page.wait_for_load_state('networkidle', timeout=10000)
                print(f"  ✓ Logged in, current URL: {page.url}")
                
                # Step 2: Navigate to Tasks page
                print("\n📋 Step 2: Navigating to Tasks page...")
                start_time = time.time()
                await page.goto('http://127.0.0.1:5000/dashboard/tasks', timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=15000)
                load_time = (time.time() - start_time) * 1000
                self.results['performance']['page_load_ms'] = round(load_time)
                print(f"  ✓ Page loaded in {round(load_time)}ms")
                
                # Give scripts time to initialize
                await asyncio.sleep(2)
                
                # Step 3: Check for JavaScript errors
                print("\n🔍 Step 3: Checking for JavaScript errors...")
                if self.console_errors:
                    print(f"  ❌ Found {len(self.console_errors)} JS errors:")
                    for err in self.console_errors[:10]:
                        print(f"     • {err[:200]}")
                else:
                    print("  ✓ No JavaScript errors detected")
                
                # Step 4: Check element presence
                print("\n🧩 Step 4: Checking required elements...")
                elements_to_check = [
                    ('#tasks-list-container', 'Task list container'),
                    ('.task-card', 'Task cards'),
                    ('.task-checkbox', 'Task checkboxes'),
                    ('#task-search-input', 'Search input'),
                    ('.filter-tab', 'Filter tabs'),
                    ('#task-sort-select', 'Sort dropdown'),
                    ('#new-task-btn', 'New Task button'),
                    ('.btn-generate-proposals', 'AI Proposals button'),
                    ('#bulk-action-toolbar', 'Bulk action toolbar'),
                    ('.task-menu-trigger', 'Menu triggers (kebab)'),
                    ('#task-menu', 'Task menu template'),
                    ('#connection-banner', 'Connection banner'),
                    ('#meeting-heatmap-container', 'Heatmap container'),
                    ('#ai-proposals-container', 'AI proposals container'),
                ]
                
                for selector, name in elements_to_check:
                    try:
                        elements = await page.query_selector_all(selector)
                        count = len(elements)
                        if count > 0:
                            self.results['elements_found'][name] = count
                            print(f"  ✓ {name}: {count} found")
                        else:
                            self.results['elements_missing'].append(name)
                            print(f"  ❌ {name}: NOT FOUND")
                    except Exception as e:
                        self.results['elements_missing'].append(f"{name} (error: {str(e)})")
                        print(f"  ❌ {name}: ERROR - {str(e)}")
                
                # Step 5: Check module initialization
                print("\n🔧 Step 5: Checking JavaScript module initialization...")
                modules = [
                    'window.taskCache',
                    'window.optimisticUI', 
                    'window.taskActionsMenu',
                    'window.taskMenuController',
                    'window.tasksOrchestrator',
                    'window.taskBootstrap',
                    'window.taskStore',
                ]
                
                for module in modules:
                    try:
                        exists = await page.evaluate(f'typeof {module} !== "undefined" && {module} !== null')
                        self.results['initialization'][module] = exists
                        status = '✓' if exists else '❌'
                        print(f"  {status} {module}: {'initialized' if exists else 'NOT INITIALIZED'}")
                    except Exception as e:
                        self.results['initialization'][module] = f"Error: {str(e)}"
                        print(f"  ❌ {module}: ERROR - {str(e)}")
                
                # Step 6: Test checkbox click
                print("\n🖱️ Step 6: Testing checkbox interaction...")
                
                # Debug: Check task card visibility info
                visibility_info = await page.evaluate('''() => {
                    const card = document.querySelector('.task-card');
                    if (!card) return { exists: false };
                    const style = window.getComputedStyle(card);
                    const rect = card.getBoundingClientRect();
                    return {
                        exists: true,
                        display: style.display,
                        visibility: style.visibility,
                        opacity: style.opacity,
                        height: style.height,
                        rect: { top: rect.top, left: rect.left, width: rect.width, height: rect.height }
                    };
                }''')
                print(f"  Debug: Task card visibility = {visibility_info}")
                
                # Use JavaScript click instead of Playwright hover (avoids visibility issues)
                checkbox_clicked = await page.evaluate('''() => {
                    const checkbox = document.querySelector('.task-checkbox');
                    if (!checkbox) return { success: false, error: 'No checkbox found' };
                    
                    const taskCard = checkbox.closest('.task-card');
                    const initialClass = taskCard ? taskCard.className : '';
                    
                    // Dispatch click event
                    checkbox.click();
                    
                    // Wait a tick and check
                    return new Promise(resolve => {
                        setTimeout(() => {
                            const afterClass = taskCard ? taskCard.className : '';
                            resolve({
                                success: true,
                                initialClass,
                                afterClass,
                                changed: initialClass !== afterClass
                            });
                        }, 500);
                    });
                }''')
                
                if checkbox_clicked.get('success'):
                    if checkbox_clicked.get('changed'):
                        print(f"  ✓ Checkbox click triggered class change")
                        self.results['initialization']['checkbox_works'] = True
                    else:
                        print(f"  ⚠️ Checkbox click may not have visual effect (class unchanged)")
                        self.results['initialization']['checkbox_works'] = 'no_visual_change'
                else:
                    print(f"  ❌ {checkbox_clicked.get('error')}")
                    self.results['initialization']['checkbox_works'] = False
                
                # Step 7: Test menu trigger
                print("\n🖱️ Step 7: Testing menu trigger...")
                
                # Use JavaScript to click menu trigger (avoids visibility issues)
                menu_result = await page.evaluate('''() => {
                    const trigger = document.querySelector('.task-menu-trigger');
                    if (!trigger) return { success: false, error: 'No menu trigger found' };
                    
                    // Get task ID from the trigger's data attribute or parent
                    const taskCard = trigger.closest('.task-card');
                    const taskId = taskCard ? taskCard.dataset.taskId : null;
                    
                    // Click the trigger
                    trigger.click();
                    
                    // Wait and check if menu appeared
                    return new Promise(resolve => {
                        setTimeout(() => {
                            const menu = document.getElementById('task-menu');
                            if (!menu) {
                                resolve({ success: false, error: 'No menu element found after click' });
                                return;
                            }
                            
                            const style = window.getComputedStyle(menu);
                            const isVisible = style.display !== 'none' && 
                                            style.visibility !== 'hidden' &&
                                            parseFloat(style.opacity) > 0;
                            
                            resolve({
                                success: true,
                                menuVisible: isVisible,
                                menuDisplay: style.display,
                                menuOpacity: style.opacity,
                                taskId: taskId
                            });
                        }, 500);
                    });
                }''')
                
                if menu_result.get('success'):
                    if menu_result.get('menuVisible'):
                        print(f"  ✓ Menu opened on click (taskId: {menu_result.get('taskId')})")
                        self.results['initialization']['menu_works'] = True
                    else:
                        print(f"  ❌ Menu did NOT open (display: {menu_result.get('menuDisplay')}, opacity: {menu_result.get('menuOpacity')})")
                        self.results['initialization']['menu_works'] = False
                else:
                    print(f"  ❌ {menu_result.get('error')}")
                    self.results['initialization']['menu_works'] = False
                
                # Step 8: Capture all console output
                print("\n📝 Step 8: Capturing console logs...")
                self.results['console_logs'] = self.console_logs[-50:]  # Last 50 logs
                
                # Step 9: Summary
                print("\n" + "="*60)
                print("DIAGNOSTIC SUMMARY")
                print("="*60)
                
                total_elements = len(elements_to_check)
                found_elements = len(self.results['elements_found'])
                missing_elements = len(self.results['elements_missing'])
                
                print(f"Elements: {found_elements}/{total_elements} found, {missing_elements} missing")
                print(f"JS Errors: {len(self.console_errors)}")
                print(f"Page Load: {self.results['performance'].get('page_load_ms', 'N/A')}ms")
                
                # Key findings
                print("\n🔑 KEY FINDINGS:")
                
                if not self.results['initialization'].get('window.tasksOrchestrator'):
                    print("  ❌ CRITICAL: TasksPageOrchestrator NOT initialized")
                
                if not self.results['initialization'].get('window.optimisticUI'):
                    print("  ❌ CRITICAL: OptimisticUI NOT initialized - no click handlers!")
                
                if not self.results['initialization'].get('window.taskMenuController'):
                    print("  ❌ CRITICAL: TaskMenuController NOT initialized - menus broken!")
                
                if not self.results['initialization'].get('checkbox_works', True):
                    print("  ❌ CRITICAL: Checkbox clicks have NO EFFECT")
                
                if not self.results['initialization'].get('menu_works', True):
                    print("  ❌ CRITICAL: Menu clicks have NO EFFECT")
                
                # Check for specific initialization logs
                orchestrator_init = any('[Orchestrator]' in log for log in self.console_logs)
                if orchestrator_init:
                    print("  ✓ Orchestrator initialization logs found")
                else:
                    print("  ❌ NO Orchestrator initialization logs - script may not be loading")
                
            except Exception as e:
                print(f"\n❌ DIAGNOSTIC FAILED: {str(e)}")
                self.results['error'] = str(e)
            finally:
                await browser.close()
        
        return self.results


async def main():
    print("="*60)
    print("CROWN⁴.6 TASK PAGE DIAGNOSTIC")
    print("="*60)
    print()
    
    diagnostic = TaskPageDiagnostic()
    results = await diagnostic.run_diagnostic()
    
    # Save results
    with open('reports/task_page_diagnostic_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n📄 Full results saved to: reports/task_page_diagnostic_results.json")
    return results


if __name__ == '__main__':
    asyncio.run(main())
