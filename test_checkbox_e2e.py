"""
End-to-end test for checkbox persistence using Playwright.
Tests the complete flow: click checkbox → WebSocket update → database persistence.
"""
import asyncio
import os
from playwright.async_api import async_playwright
from sqlalchemy import create_engine, text
import time

async def run_e2e_test():
    """Run end-to-end checkbox test."""
    print("\n" + "="*60)
    print("🧪 END-TO-END CHECKBOX PERSISTENCE TEST")
    print("="*60 + "\n")
    
    # Database setup
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    engine = create_engine(database_url)
    
    # Get a task to test
    print("Step 1: Finding a task to test...")
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT id, title, status FROM tasks WHERE status = 'todo' LIMIT 1"
        ))
        task = result.fetchone()
        
        if not task:
            print("❌ No 'todo' tasks found to test with")
            return False
        
        task_id, title, original_status = task[0], task[1], task[2]
        print(f"✅ Found task: ID={task_id}")
        print(f"   Title: '{title[:50]}...'")
        print(f"   Original status: '{original_status}'")
    
    # Launch browser
    print("\nStep 2: Launching browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Enable console logging
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        
        # Navigate to login page
        print("\nStep 3: Logging in...")
        await page.goto('http://localhost:5000/login')
        await page.wait_for_load_state('networkidle')
        
        # Fill login form (using test credentials)
        await page.fill('input[name="email"]', 'test@example.com')
        await page.fill('input[name="password"]', 'password123')
        await page.click('button[type="submit"]')
        await page.wait_for_load_state('networkidle')
        
        # Check if logged in
        current_url = page.url
        if '/login' in current_url:
            print("❌ Login failed - still on login page")
            print(f"   Current URL: {current_url}")
            # Try to find error message
            error = await page.query_selector('.error, .alert-danger')
            if error:
                error_text = await error.inner_text()
                print(f"   Error: {error_text}")
            await browser.close()
            return False
        
        print(f"✅ Logged in successfully")
        print(f"   Current URL: {current_url}")
        
        # Navigate to tasks page
        print("\nStep 4: Navigating to tasks page...")
        await page.goto('http://localhost:5000/dashboard/tasks')
        await page.wait_for_load_state('networkidle')
        
        # Wait for tasks to load
        await page.wait_for_selector('.task-item, [data-task-id]', timeout=10000)
        print("✅ Tasks page loaded")
        
        # Find the checkbox for our task
        print(f"\nStep 5: Finding checkbox for task {task_id}...")
        checkbox_selector = f'[data-task-id="{task_id}"] input[type="checkbox"]'
        checkbox = await page.query_selector(checkbox_selector)
        
        if not checkbox:
            # Try alternative selectors
            checkbox_selector = f'input[data-task-id="{task_id}"]'
            checkbox = await page.query_selector(checkbox_selector)
        
        if not checkbox:
            print(f"❌ Checkbox not found for task {task_id}")
            print("   Available task IDs on page:")
            tasks = await page.query_selector_all('[data-task-id]')
            for task_elem in tasks[:5]:
                tid = await task_elem.get_attribute('data-task-id')
                print(f"   - {tid}")
            await browser.close()
            return False
        
        print(f"✅ Found checkbox for task {task_id}")
        
        # Check if already checked
        is_checked = await checkbox.is_checked()
        print(f"   Current state: {'checked' if is_checked else 'unchecked'}")
        
        # Click the checkbox
        print(f"\nStep 6: Clicking checkbox...")
        await checkbox.click()
        print("✅ Checkbox clicked")
        
        # Wait for WebSocket update
        print("\nStep 7: Waiting for WebSocket update...")
        await asyncio.sleep(2)  # Give time for WebSocket round-trip
        
        # Check console for WebSocket messages
        ws_messages = [msg for msg in console_messages if 'websocket' in msg.lower() or 'task' in msg.lower()]
        if ws_messages:
            print("📨 WebSocket-related console messages:")
            for msg in ws_messages[-10:]:
                print(f"   {msg}")
        
        # Verify database was updated
        print("\nStep 8: Verifying database update...")
        with engine.connect() as conn:
            result = conn.execute(text(
                f"SELECT status FROM tasks WHERE id = {task_id}"
            ))
            task = result.fetchone()
            
            if task:
                new_status = task[0]
                print(f"📊 Database status: '{new_status}'")
                
                # Expected status is opposite of original
                expected_status = 'completed' if original_status == 'todo' else 'todo'
                
                if new_status == expected_status:
                    print(f"✅ Database updated correctly to '{new_status}'!")
                    persistence_ok = True
                else:
                    print(f"❌ Database not updated. Expected '{expected_status}', got '{new_status}'")
                    persistence_ok = False
            else:
                print("❌ Task not found in database")
                persistence_ok = False
        
        # Revert for next test
        print(f"\nStep 9: Reverting task back to '{original_status}'...")
        with engine.begin() as conn:
            conn.execute(text(
                f"UPDATE tasks SET status = '{original_status}' WHERE id = {task_id}"
            ))
            print(f"✅ Reverted to original status")
        
        # Close browser
        await browser.close()
    
    # Results
    print("\n" + "="*60)
    if persistence_ok:
        print("🎉 END-TO-END CHECKBOX TEST PASSED!")
    else:
        print("❌ END-TO-END CHECKBOX TEST FAILED")
    print("="*60 + "\n")
    
    return persistence_ok

if __name__ == '__main__':
    success = asyncio.run(run_e2e_test())
    exit(0 if success else 1)
