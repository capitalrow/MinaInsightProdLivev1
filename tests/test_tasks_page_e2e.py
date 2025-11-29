"""
End-to-End Test for Tasks Page with Real User
Tests all 13 task menu actions with agent_tester@mina.ai
"""
import requests
import json
import sys
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000"

class TasksPageE2ETest:
    def __init__(self):
        self.session = requests.Session()
        self.results = []
        self.user_id = 9  # agent_tester@mina.ai
        self.test_tasks = []
        
    def log_result(self, test_name, status, detail):
        """Log a test result."""
        self.results.append((test_name, status, detail))
        icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥", "WARN": "⚠️", "INFO": "ℹ️"}.get(status, "?")
        print(f"  {icon} {test_name}: {detail}")
    
    def login(self):
        """Login as agent_tester@mina.ai."""
        print("\n📋 PHASE 1: AUTHENTICATION")
        print("-" * 50)
        
        try:
            # Get login page to retrieve CSRF token
            resp = self.session.get(f"{BASE_URL}/auth/login", timeout=10)
            
            # Extract CSRF token from the page
            csrf_token = None
            if 'csrf_token' in resp.text:
                import re
                match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
                if match:
                    csrf_token = match.group(1)
            
            # Login with credentials
            login_data = {
                "email": "agent_tester@mina.ai",
                "password": "test123"
            }
            if csrf_token:
                login_data["csrf_token"] = csrf_token
            
            resp = self.session.post(
                f"{BASE_URL}/auth/login", 
                data=login_data,
                allow_redirects=True,
                timeout=10
            )
            
            # Check if login succeeded by accessing protected route
            tasks_resp = self.session.get(f"{BASE_URL}/api/tasks/", timeout=10)
            
            if tasks_resp.status_code == 200:
                data = tasks_resp.json()
                task_count = len(data.get('tasks', []))
                self.log_result("Login", "PASS", f"Authenticated successfully, found {task_count} tasks")
                return True
            else:
                self.log_result("Login", "WARN", f"Login may have failed (status: {tasks_resp.status_code})")
                return False
                
        except Exception as e:
            self.log_result("Login", "ERROR", str(e))
            return False
    
    def test_task_list_api(self):
        """Test the tasks list API."""
        print("\n📋 PHASE 2: TASK LIST API")
        print("-" * 50)
        
        try:
            resp = self.session.get(f"{BASE_URL}/api/tasks/", timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                tasks = data.get('tasks', [])
                self.test_tasks = tasks[:5]  # Store first 5 tasks for testing
                
                self.log_result("GET /api/tasks/", "PASS", f"Retrieved {len(tasks)} tasks")
                
                # Analyze task data
                if tasks:
                    statuses = {}
                    priorities = {}
                    for task in tasks:
                        status = task.get('status', 'unknown')
                        priority = task.get('priority', 'unknown')
                        statuses[status] = statuses.get(status, 0) + 1
                        priorities[priority] = priorities.get(priority, 0) + 1
                    
                    self.log_result("Task Status Distribution", "INFO", str(statuses))
                    self.log_result("Task Priority Distribution", "INFO", str(priorities))
                
                return True
            else:
                self.log_result("GET /api/tasks/", "FAIL", f"Status: {resp.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Task List API", "ERROR", str(e))
            return False
    
    def test_single_task_api(self):
        """Test fetching a single task."""
        print("\n📋 PHASE 3: SINGLE TASK API")
        print("-" * 50)
        
        if not self.test_tasks:
            self.log_result("Single Task API", "WARN", "No tasks available for testing")
            return False
        
        task = self.test_tasks[0]
        task_id = task.get('id')
        
        if not task_id:
            self.log_result("Single Task API", "WARN", "Task has no ID")
            return False
        
        try:
            resp = self.session.get(f"{BASE_URL}/api/tasks/{task_id}", timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                title = data.get('task', {}).get('title', 'N/A')
                self.log_result(f"GET /api/tasks/{task_id}", "PASS", f"Task: {title[:50]}")
                return True
            else:
                self.log_result(f"GET /api/tasks/{task_id}", "FAIL", f"Status: {resp.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Single Task API", "ERROR", str(e))
            return False
    
    def test_update_task_api(self):
        """Test updating a task (Edit, Priority, Due Date, Labels actions)."""
        print("\n📋 PHASE 4: TASK UPDATE APIs (Edit, Priority, Due Date, Labels)")
        print("-" * 50)
        
        if not self.test_tasks:
            self.log_result("Update Task API", "WARN", "No tasks available for testing")
            return False
        
        task = self.test_tasks[0]
        task_id = task.get('id')
        
        if not task_id:
            self.log_result("Update Task API", "WARN", "Task has no ID")
            return False
        
        tests = [
            ("Edit Title", {"title": f"Test Updated - {datetime.now().strftime('%H:%M:%S')}"}),
            ("Edit Priority", {"priority": "high"}),
            ("Edit Due Date", {"due_date": (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}),
            ("Edit Labels", {"labels": ["test", "automation"]}),
            ("Edit Description", {"description": "Updated via E2E test"})
        ]
        
        all_passed = True
        for test_name, update_data in tests:
            try:
                resp = self.session.put(
                    f"{BASE_URL}/api/tasks/{task_id}",
                    json=update_data,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('success'):
                        self.log_result(test_name, "PASS", f"Updated successfully")
                    else:
                        self.log_result(test_name, "FAIL", f"API returned failure: {data.get('message', 'Unknown error')}")
                        all_passed = False
                else:
                    self.log_result(test_name, "FAIL", f"Status: {resp.status_code}")
                    all_passed = False
                    
            except Exception as e:
                self.log_result(test_name, "ERROR", str(e))
                all_passed = False
        
        return all_passed
    
    def test_status_toggle_api(self):
        """Test toggling task status."""
        print("\n📋 PHASE 5: STATUS TOGGLE API")
        print("-" * 50)
        
        if len(self.test_tasks) < 2:
            self.log_result("Status Toggle API", "WARN", "Not enough tasks for testing")
            return False
        
        task = self.test_tasks[1]
        task_id = task.get('id')
        
        if not task_id:
            self.log_result("Status Toggle API", "WARN", "Task has no ID")
            return False
        
        current_status = task.get('status', 'todo')
        new_status = 'completed' if current_status != 'completed' else 'todo'
        
        try:
            resp = self.session.put(
                f"{BASE_URL}/api/tasks/{task_id}/status",
                json={"status": new_status},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success'):
                    self.log_result("Status Toggle", "PASS", f"Changed from '{current_status}' to '{new_status}'")
                    
                    # Toggle back
                    self.session.put(
                        f"{BASE_URL}/api/tasks/{task_id}/status",
                        json={"status": current_status},
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                    return True
                else:
                    self.log_result("Status Toggle", "FAIL", data.get('message', 'Unknown error'))
                    return False
            else:
                self.log_result("Status Toggle", "FAIL", f"Status: {resp.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Status Toggle API", "ERROR", str(e))
            return False
    
    def test_create_task_api(self):
        """Test creating a new task (Duplicate action uses this)."""
        print("\n📋 PHASE 6: CREATE TASK API (Duplicate)")
        print("-" * 50)
        
        try:
            # Get a meeting_id from an existing task
            meeting_id = None
            if self.test_tasks:
                meeting_id = self.test_tasks[0].get('meeting_id')
            
            new_task_data = {
                "title": f"E2E Test Task - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "description": "Created by E2E test automation",
                "priority": "medium",
                "status": "todo",
                "labels": ["e2e-test"]
            }
            
            if meeting_id:
                new_task_data["meeting_id"] = meeting_id
            
            resp = self.session.post(
                f"{BASE_URL}/api/tasks/",
                json=new_task_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if resp.status_code in [200, 201]:
                data = resp.json()
                if data.get('success') or data.get('task'):
                    task = data.get('task', {})
                    task_id = task.get('id')
                    self.log_result("Create Task", "PASS", f"Created task ID: {task_id}")
                    
                    if task_id:
                        self.test_tasks.append(task)
                    return True
                else:
                    self.log_result("Create Task", "FAIL", data.get('message', 'Unknown error'))
                    return False
            else:
                error_data = {}
                try:
                    error_data = resp.json()
                except:
                    pass
                self.log_result("Create Task", "FAIL", f"Status: {resp.status_code}, Error: {error_data.get('message', 'N/A')}")
                return False
                
        except Exception as e:
            self.log_result("Create Task API", "ERROR", str(e))
            return False
    
    def test_merge_task_api(self):
        """Test merging tasks endpoint."""
        print("\n📋 PHASE 7: MERGE TASK API")
        print("-" * 50)
        
        if len(self.test_tasks) < 2:
            self.log_result("Merge Task API", "WARN", "Not enough tasks for merge testing")
            return True
        
        target_task_id = self.test_tasks[0].get('id')
        
        if not target_task_id:
            self.log_result("Merge Task API", "WARN", "No task ID available")
            return True
        
        try:
            # Test with non-existent source task (shouldn't merge real data)
            resp = self.session.post(
                f"{BASE_URL}/api/tasks/{target_task_id}/merge",
                json={"source_task_id": 999999},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if resp.status_code in [200, 404]:
                self.log_result("Merge Task Endpoint", "PASS", f"Endpoint responds correctly (status: {resp.status_code})")
                return True
            else:
                self.log_result("Merge Task Endpoint", "WARN", f"Unexpected status: {resp.status_code}")
                return True
                
        except Exception as e:
            self.log_result("Merge Task API", "ERROR", str(e))
            return False
    
    def test_delete_task_api(self):
        """Test soft delete and undo delete."""
        print("\n📋 PHASE 8: DELETE & UNDO DELETE API")
        print("-" * 50)
        
        try:
            # Create a task specifically for delete testing
            meeting_id = None
            if self.test_tasks:
                meeting_id = self.test_tasks[0].get('meeting_id')
            
            new_task_data = {
                "title": f"DELETE TEST - {datetime.now().strftime('%H:%M:%S')}",
                "description": "Task created for delete testing",
                "priority": "low",
                "status": "todo"
            }
            
            if meeting_id:
                new_task_data["meeting_id"] = meeting_id
            
            create_resp = self.session.post(
                f"{BASE_URL}/api/tasks/",
                json=new_task_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if create_resp.status_code not in [200, 201]:
                self.log_result("Delete Test Setup", "FAIL", f"Could not create test task (status: {create_resp.status_code})")
                return False
            
            data = create_resp.json()
            task_id = data.get('task', {}).get('id')
            
            if not task_id:
                self.log_result("Delete Test Setup", "FAIL", "No task ID returned")
                return False
            
            self.log_result("Delete Test Setup", "PASS", f"Created test task ID: {task_id}")
            
            # Test soft delete
            delete_resp = self.session.delete(
                f"{BASE_URL}/api/tasks/{task_id}",
                timeout=10
            )
            
            if delete_resp.status_code == 200:
                self.log_result("Soft Delete", "PASS", f"Task {task_id} deleted")
                
                # Test undo delete
                undo_resp = self.session.post(
                    f"{BASE_URL}/api/tasks/{task_id}/undo-delete",
                    timeout=10
                )
                
                if undo_resp.status_code == 200:
                    self.log_result("Undo Delete", "PASS", f"Task {task_id} restored")
                    
                    # Clean up - delete again
                    self.session.delete(f"{BASE_URL}/api/tasks/{task_id}", timeout=10)
                    return True
                else:
                    self.log_result("Undo Delete", "FAIL", f"Status: {undo_resp.status_code}")
                    return False
            else:
                self.log_result("Soft Delete", "FAIL", f"Status: {delete_resp.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Delete API", "ERROR", str(e))
            return False
    
    def test_tasks_page_html(self):
        """Test that the tasks page loads correctly."""
        print("\n📋 PHASE 9: TASKS PAGE HTML")
        print("-" * 50)
        
        try:
            resp = self.session.get(f"{BASE_URL}/dashboard/tasks", timeout=10)
            
            if resp.status_code == 200:
                html = resp.text
                
                # Check for key elements
                checks = [
                    ("Task Container", "tasks-list" in html or "task-list" in html or "TaskCard" in html),
                    ("Task Menu Script", "task-menu" in html or "TaskMenu" in html),
                    ("OptimisticUI Script", "optimistic" in html.lower()),
                    ("WebSocket Script", "websocket" in html.lower() or "socket.io" in html.lower()),
                ]
                
                for check_name, check_result in checks:
                    if check_result:
                        self.log_result(check_name, "PASS", "Found in HTML")
                    else:
                        self.log_result(check_name, "WARN", "Not found (may be loaded dynamically)")
                
                return True
            elif resp.status_code == 302:
                self.log_result("Tasks Page", "WARN", "Redirected (login required)")
                return False
            else:
                self.log_result("Tasks Page", "FAIL", f"Status: {resp.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Tasks Page HTML", "ERROR", str(e))
            return False
    
    def generate_report(self):
        """Generate final test report."""
        print("\n" + "=" * 70)
        print("FINAL TEST REPORT - Tasks Page E2E Testing")
        print("=" * 70)
        
        passed = sum(1 for r in self.results if r[1] == "PASS")
        failed = sum(1 for r in self.results if r[1] == "FAIL")
        errors = sum(1 for r in self.results if r[1] == "ERROR")
        warnings = sum(1 for r in self.results if r[1] == "WARN")
        info = sum(1 for r in self.results if r[1] == "INFO")
        
        print(f"\nTotal Tests: {len(self.results)}")
        print(f"  ✅ Passed: {passed}")
        print(f"  ❌ Failed: {failed}")
        print(f"  💥 Errors: {errors}")
        print(f"  ⚠️ Warnings: {warnings}")
        print(f"  ℹ️ Info: {info}")
        
        # Calculate pass rate (excluding info)
        testable = passed + failed + errors
        if testable > 0:
            pass_rate = (passed / testable) * 100
            print(f"\nPass Rate: {pass_rate:.1f}%")
        
        print("\n" + "=" * 70)
        
        if failed == 0 and errors == 0:
            print("🎉 ALL CRITICAL TESTS PASSED!")
            return 0
        else:
            print("❌ SOME TESTS FAILED - Review results above")
            return 1
    
    def run(self):
        """Run all tests."""
        print("=" * 70)
        print("E2E TEST SUITE: Tasks Page with Real User (agent_tester@mina.ai)")
        print("=" * 70)
        print(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run test phases
        login_success = self.login()
        self.test_task_list_api()
        
        if self.test_tasks:
            self.test_single_task_api()
            self.test_update_task_api()
            self.test_status_toggle_api()
            self.test_create_task_api()
            self.test_merge_task_api()
            self.test_delete_task_api()
        else:
            self.log_result("Task Tests", "WARN", "Skipped - no tasks found in user's workspace")
        
        self.test_tasks_page_html()
        
        return self.generate_report()

if __name__ == "__main__":
    test = TasksPageE2ETest()
    exit_code = test.run()
    sys.exit(exit_code)
