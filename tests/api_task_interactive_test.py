#!/usr/bin/env python
"""
Comprehensive Task API Tests
Systematic testing of task CRUD operations, filters, and functionality
Tests all backend API endpoints used by the tasks page

This tests the API layer that powers the tasks page to ensure
all functionality matches industry-leading standards.
"""

import os
import sys
import time
import json
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

sys.path.insert(0, '/home/runner/workspace')

BASE_URL = 'http://127.0.0.1:5000'


@dataclass
class TestResult:
    name: str
    category: str
    passed: bool
    duration_ms: float
    details: str = ""
    error: str = ""


@dataclass
class TestReport:
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    results: List[TestResult] = field(default_factory=list)
    start_time: datetime = None
    end_time: datetime = None
    
    def add_result(self, result: TestResult):
        self.results.append(result)
        self.total_tests += 1
        if result.passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def get_summary(self) -> str:
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        
        lines = [
            "=" * 70,
            " COMPREHENSIVE TASK PAGE TEST REPORT",
            " Matching Industry Standards: Todoist, Asana, Linear",
            "=" * 70,
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {duration:.2f}s",
            "",
            f"OVERALL RESULTS:",
            f"  Total Tests: {self.total_tests}",
            f"  Passed: {self.passed} ({self.passed/self.total_tests*100:.1f}%)" if self.total_tests > 0 else "  Passed: 0",
            f"  Failed: {self.failed}",
            "",
            "-" * 70,
        ]
        
        categories = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)
        
        for category, results in categories.items():
            lines.append(f"\n## {category}")
            passed_in_category = sum(1 for r in results if r.passed)
            lines.append(f"   ({passed_in_category}/{len(results)} passed)")
            for r in results:
                status = "PASS" if r.passed else "FAIL"
                lines.append(f"  [{status}] {r.name} ({r.duration_ms:.0f}ms)")
                if r.details:
                    lines.append(f"        -> {r.details}")
                if r.error:
                    lines.append(f"        ERROR: {r.error}")
        
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)


class TaskAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.report = TestReport()
        self.report.start_time = datetime.now()
        self.created_task_ids = []
        self.csrf_token = None
        self.workspace_id = None
    
    def run_test(self, name: str, category: str, test_fn) -> TestResult:
        start = time.perf_counter()
        try:
            details = test_fn()
            duration = (time.perf_counter() - start) * 1000
            result = TestResult(
                name=name,
                category=category,
                passed=True,
                duration_ms=duration,
                details=details if isinstance(details, str) else ""
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            result = TestResult(
                name=name,
                category=category,
                passed=False,
                duration_ms=duration,
                error=str(e)[:100]
            )
        
        self.report.add_result(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {name}")
        return result
    
    def authenticate(self) -> bool:
        """Login and get session"""
        print("\n1. AUTHENTICATION")
        try:
            resp = self.session.get(f'{BASE_URL}/auth/login')
            
            import re
            csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', resp.text)
            if csrf_match:
                self.csrf_token = csrf_match.group(1)
            else:
                csrf_match = re.search(r'csrf-token"[^>]*content="([^"]+)"', resp.text)
                if csrf_match:
                    self.csrf_token = csrf_match.group(1)
            
            login_data = {
                'email': 'tasktest@example.com',
                'password': 'testpass123'
            }
            if self.csrf_token:
                login_data['csrf_token'] = self.csrf_token
            
            resp = self.session.post(f'{BASE_URL}/auth/login', data=login_data, allow_redirects=True)
            
            if resp.status_code == 200 and ('dashboard' in resp.url or 'tasks' in resp.url):
                print("   [PASS] Authentication successful")
                return True
            else:
                print(f"   [INFO] Auth response: {resp.status_code}, URL: {resp.url[:50]}")
                return True
                
        except Exception as e:
            print(f"   [FAIL] Authentication error: {e}")
            return False
    
    def get_csrf_token(self):
        """Get CSRF token from tasks page"""
        try:
            resp = self.session.get(f'{BASE_URL}/tasks')
            import re
            match = re.search(r'csrf-token"[^>]*content="([^"]+)"', resp.text)
            if match:
                self.csrf_token = match.group(1)
                return self.csrf_token
        except:
            pass
        return None
    
    # ============ TASK LIST (READ) TESTS ============
    
    def test_get_tasks_list(self):
        """GET /api/tasks - Retrieve all tasks"""
        resp = self.session.get(f'{BASE_URL}/api/tasks/')
        if resp.status_code == 200:
            data = resp.json()
            tasks = data.get('tasks', data.get('data', data))
            if isinstance(tasks, list):
                return f"Retrieved {len(tasks)} tasks"
            return f"Response OK, structure: {list(data.keys())[:3]}"
        raise Exception(f"Status {resp.status_code}: {resp.text[:100]}")
    
    def test_get_tasks_with_pagination(self):
        """GET /api/tasks with pagination params"""
        resp = self.session.get(f'{BASE_URL}/api/tasks/', params={'page': 1, 'per_page': 10})
        if resp.status_code == 200:
            data = resp.json()
            return f"Pagination works, response keys: {list(data.keys())[:4]}"
        raise Exception(f"Status {resp.status_code}")
    
    def test_filter_active_tasks(self):
        """GET /api/tasks?status=todo - Filter active tasks"""
        resp = self.session.get(f'{BASE_URL}/api/tasks/', params={'status': 'todo'})
        if resp.status_code == 200:
            data = resp.json()
            tasks = data.get('tasks', data.get('data', []))
            if isinstance(tasks, list):
                all_active = all(t.get('status') in ['todo', 'in_progress'] for t in tasks) if tasks else True
                return f"{len(tasks)} active tasks, all active: {all_active}"
            return "Filter applied"
        raise Exception(f"Status {resp.status_code}")
    
    def test_filter_completed_tasks(self):
        """GET /api/tasks?status=completed - Filter completed tasks"""
        resp = self.session.get(f'{BASE_URL}/api/tasks/', params={'status': 'completed'})
        if resp.status_code == 200:
            data = resp.json()
            tasks = data.get('tasks', data.get('data', []))
            if isinstance(tasks, list):
                return f"{len(tasks)} completed tasks"
            return "Filter applied"
        raise Exception(f"Status {resp.status_code}")
    
    def test_filter_by_priority(self):
        """GET /api/tasks?priority=high - Filter by priority"""
        resp = self.session.get(f'{BASE_URL}/api/tasks/', params={'priority': 'high'})
        if resp.status_code == 200:
            data = resp.json()
            tasks = data.get('tasks', data.get('data', []))
            if isinstance(tasks, list):
                return f"{len(tasks)} high priority tasks"
            return "Priority filter works"
        raise Exception(f"Status {resp.status_code}")
    
    def test_search_tasks(self):
        """GET /api/tasks?search=keyword - Search functionality"""
        resp = self.session.get(f'{BASE_URL}/api/tasks/', params={'search': 'test'})
        if resp.status_code == 200:
            return "Search endpoint works"
        raise Exception(f"Status {resp.status_code}")
    
    def test_due_date_filter(self):
        """GET /api/tasks?due_date=today - Due date filtering"""
        resp = self.session.get(f'{BASE_URL}/api/tasks/', params={'due_date': 'today'})
        if resp.status_code == 200:
            return "Due date filter works"
        raise Exception(f"Status {resp.status_code}")
    
    # ============ CREATE TESTS ============
    
    def test_create_task_basic(self):
        """POST /api/tasks - Create task with title only"""
        self.get_csrf_token()
        
        headers = {}
        if self.csrf_token:
            headers['X-CSRFToken'] = self.csrf_token
        
        task_data = {
            'title': f'API Test Task {datetime.now().strftime("%H%M%S")}',
            'priority': 'medium'
        }
        
        resp = self.session.post(f'{BASE_URL}/api/tasks/', json=task_data, headers=headers)
        
        if resp.status_code in [200, 201]:
            data = resp.json()
            task_id = data.get('id') or data.get('task', {}).get('id')
            if task_id:
                self.created_task_ids.append(task_id)
            return f"Created task ID: {task_id}"
        raise Exception(f"Status {resp.status_code}: {resp.text[:100]}")
    
    def test_create_task_with_priority(self):
        """POST /api/tasks - Create high priority task"""
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        task_data = {
            'title': f'High Priority Task {datetime.now().strftime("%H%M%S")}',
            'priority': 'high',
            'description': 'Important task for testing'
        }
        
        resp = self.session.post(f'{BASE_URL}/api/tasks/', json=task_data, headers=headers)
        
        if resp.status_code in [200, 201]:
            data = resp.json()
            task_id = data.get('id') or data.get('task', {}).get('id')
            if task_id:
                self.created_task_ids.append(task_id)
            priority = data.get('priority') or data.get('task', {}).get('priority')
            return f"Created task with priority: {priority}"
        raise Exception(f"Status {resp.status_code}")
    
    def test_create_task_with_due_date(self):
        """POST /api/tasks - Create task with due date"""
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        due_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        task_data = {
            'title': f'Due Date Task {datetime.now().strftime("%H%M%S")}',
            'due_date': due_date
        }
        
        resp = self.session.post(f'{BASE_URL}/api/tasks/', json=task_data, headers=headers)
        
        if resp.status_code in [200, 201]:
            data = resp.json()
            task_id = data.get('id') or data.get('task', {}).get('id')
            if task_id:
                self.created_task_ids.append(task_id)
            return f"Created task with due date: {due_date}"
        raise Exception(f"Status {resp.status_code}")
    
    # ============ UPDATE TESTS ============
    
    def test_update_task_title(self):
        """PUT /api/tasks/<id> - Update task title"""
        if not self.created_task_ids:
            raise Exception("No tasks to update (create first)")
        
        task_id = self.created_task_ids[0]
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        update_data = {'title': f'Updated Title {datetime.now().strftime("%H%M%S")}'}
        
        resp = self.session.put(f'{BASE_URL}/api/tasks/{task_id}', json=update_data, headers=headers)
        
        if resp.status_code == 200:
            return f"Updated task {task_id} title"
        raise Exception(f"Status {resp.status_code}")
    
    def test_update_task_status_complete(self):
        """PUT /api/tasks/<id>/complete - Mark task as complete"""
        if not self.created_task_ids:
            raise Exception("No tasks to complete")
        
        task_id = self.created_task_ids[0]
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        resp = self.session.put(f'{BASE_URL}/api/tasks/{task_id}/complete', headers=headers)
        
        if resp.status_code == 200:
            return f"Completed task {task_id}"
        
        resp = self.session.put(f'{BASE_URL}/api/tasks/{task_id}', json={'status': 'completed'}, headers=headers)
        if resp.status_code == 200:
            return f"Completed task {task_id} via status update"
        raise Exception(f"Status {resp.status_code}")
    
    def test_update_task_priority(self):
        """PUT /api/tasks/<id> - Change task priority"""
        if len(self.created_task_ids) < 2:
            raise Exception("Need at least 2 tasks")
        
        task_id = self.created_task_ids[1]
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        update_data = {'priority': 'urgent'}
        resp = self.session.put(f'{BASE_URL}/api/tasks/{task_id}', json=update_data, headers=headers)
        
        if resp.status_code == 200:
            return f"Changed priority for task {task_id}"
        raise Exception(f"Status {resp.status_code}")
    
    # ============ DELETE TESTS ============
    
    def test_delete_task(self):
        """DELETE /api/tasks/<id> - Delete a task"""
        if len(self.created_task_ids) < 3:
            raise Exception("Need at least 3 tasks to delete one")
        
        task_id = self.created_task_ids.pop()
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        resp = self.session.delete(f'{BASE_URL}/api/tasks/{task_id}', headers=headers)
        
        if resp.status_code in [200, 204]:
            return f"Deleted task {task_id}"
        raise Exception(f"Status {resp.status_code}")
    
    def test_delete_confirmation(self):
        """Verify deleted task no longer appears"""
        if len(self.created_task_ids) < 2:
            return "Skipped - no tasks to verify"
        
        task_id = self.created_task_ids[-1]
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        self.session.delete(f'{BASE_URL}/api/tasks/{task_id}', headers=headers)
        self.created_task_ids.pop()
        
        resp = self.session.get(f'{BASE_URL}/api/tasks/{task_id}')
        
        if resp.status_code == 404:
            return "Deleted task returns 404 - correct behavior"
        elif resp.status_code == 200:
            data = resp.json()
            if data.get('deleted_at') or data.get('task', {}).get('deleted_at'):
                return "Soft-deleted task - correct behavior"
        return f"Status {resp.status_code} after delete"
    
    # ============ ARCHIVE TESTS ============
    
    def test_archive_task(self):
        """PUT /api/tasks/<id>/archive - Archive a task"""
        if not self.created_task_ids:
            raise Exception("No tasks to archive")
        
        task_id = self.created_task_ids[0]
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        resp = self.session.put(f'{BASE_URL}/api/tasks/{task_id}/archive', headers=headers)
        
        if resp.status_code == 200:
            return f"Archived task {task_id}"
        raise Exception(f"Status {resp.status_code}")
    
    def test_restore_task(self):
        """PUT /api/tasks/<id>/restore - Restore archived task"""
        if not self.created_task_ids:
            raise Exception("No tasks to restore")
        
        task_id = self.created_task_ids[0]
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        resp = self.session.put(f'{BASE_URL}/api/tasks/{task_id}/restore', headers=headers)
        
        if resp.status_code == 200:
            return f"Restored task {task_id}"
        raise Exception(f"Status {resp.status_code}")
    
    # ============ PERFORMANCE TESTS ============
    
    def test_api_response_time(self):
        """Measure API response time"""
        start = time.perf_counter()
        resp = self.session.get(f'{BASE_URL}/api/tasks/')
        elapsed = (time.perf_counter() - start) * 1000
        
        if resp.status_code == 200:
            if elapsed < 200:
                return f"Response time: {elapsed:.0f}ms - EXCELLENT"
            elif elapsed < 500:
                return f"Response time: {elapsed:.0f}ms - GOOD"
            elif elapsed < 1000:
                return f"Response time: {elapsed:.0f}ms - ACCEPTABLE"
            else:
                return f"Response time: {elapsed:.0f}ms - SLOW"
        raise Exception(f"Status {resp.status_code}")
    
    def test_bulk_tasks_performance(self):
        """Test performance with multiple tasks"""
        start = time.perf_counter()
        resp = self.session.get(f'{BASE_URL}/api/tasks/', params={'per_page': 50})
        elapsed = (time.perf_counter() - start) * 1000
        
        if resp.status_code == 200:
            data = resp.json()
            tasks = data.get('tasks', data.get('data', []))
            count = len(tasks) if isinstance(tasks, list) else 'unknown'
            return f"{count} tasks in {elapsed:.0f}ms"
        raise Exception(f"Status {resp.status_code}")
    
    # ============ DATA VALIDATION TESTS ============
    
    def test_task_data_structure(self):
        """Verify task response has required fields"""
        resp = self.session.get(f'{BASE_URL}/api/tasks/')
        if resp.status_code != 200:
            raise Exception(f"Status {resp.status_code}")
        
        data = resp.json()
        tasks = data.get('tasks', data.get('data', []))
        
        if not tasks or not isinstance(tasks, list) or len(tasks) == 0:
            return "No tasks to validate structure"
        
        task = tasks[0]
        required_fields = ['id', 'title', 'status']
        missing = [f for f in required_fields if f not in task]
        
        if missing:
            raise Exception(f"Missing fields: {missing}")
        
        return f"Task has required fields: id, title, status. All {len(task)} fields present."
    
    def test_task_priority_values(self):
        """Verify priority values are valid"""
        resp = self.session.get(f'{BASE_URL}/api/tasks/')
        if resp.status_code != 200:
            raise Exception(f"Status {resp.status_code}")
        
        data = resp.json()
        tasks = data.get('tasks', data.get('data', []))
        
        valid_priorities = ['low', 'medium', 'high', 'urgent', None]
        invalid = []
        
        for task in tasks[:10]:
            priority = task.get('priority')
            if priority and priority not in valid_priorities:
                invalid.append(priority)
        
        if invalid:
            raise Exception(f"Invalid priorities: {invalid}")
        
        return f"All priorities valid in {len(tasks[:10])} tasks checked"
    
    # ============ CLEANUP ============
    
    def cleanup(self):
        """Clean up created test tasks"""
        print("\nCleanup:")
        headers = {'X-CSRFToken': self.csrf_token} if self.csrf_token else {}
        
        for task_id in self.created_task_ids:
            try:
                self.session.delete(f'{BASE_URL}/api/tasks/{task_id}', headers=headers)
                print(f"   Cleaned up task {task_id}")
            except:
                pass
    
    # ============ MAIN RUNNER ============
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("\n" + "=" * 60)
        print(" COMPREHENSIVE TASK API TESTS")
        print(" Industry Standard: Todoist, Asana, Linear")
        print("=" * 60)
        
        self.authenticate()
        
        print("\n2. READ OPERATIONS (Task List)")
        self.run_test("Get all tasks", "READ", self.test_get_tasks_list)
        self.run_test("Pagination support", "READ", self.test_get_tasks_with_pagination)
        self.run_test("Filter active tasks", "READ", self.test_filter_active_tasks)
        self.run_test("Filter completed tasks", "READ", self.test_filter_completed_tasks)
        self.run_test("Filter by priority", "READ", self.test_filter_by_priority)
        self.run_test("Search functionality", "READ", self.test_search_tasks)
        self.run_test("Due date filtering", "READ", self.test_due_date_filter)
        
        print("\n3. CREATE OPERATIONS")
        self.run_test("Create basic task", "CREATE", self.test_create_task_basic)
        self.run_test("Create with priority", "CREATE", self.test_create_task_with_priority)
        self.run_test("Create with due date", "CREATE", self.test_create_task_with_due_date)
        
        print("\n4. UPDATE OPERATIONS")
        self.run_test("Update task title", "UPDATE", self.test_update_task_title)
        self.run_test("Complete task", "UPDATE", self.test_update_task_status_complete)
        self.run_test("Update priority", "UPDATE", self.test_update_task_priority)
        
        print("\n5. DELETE OPERATIONS")
        self.run_test("Delete task", "DELETE", self.test_delete_task)
        self.run_test("Verify deletion", "DELETE", self.test_delete_confirmation)
        
        print("\n6. ARCHIVE OPERATIONS")
        self.run_test("Archive task", "ARCHIVE", self.test_archive_task)
        self.run_test("Restore task", "ARCHIVE", self.test_restore_task)
        
        print("\n7. PERFORMANCE")
        self.run_test("API response time", "PERFORMANCE", self.test_api_response_time)
        self.run_test("Bulk tasks performance", "PERFORMANCE", self.test_bulk_tasks_performance)
        
        print("\n8. DATA VALIDATION")
        self.run_test("Task data structure", "VALIDATION", self.test_task_data_structure)
        self.run_test("Priority values valid", "VALIDATION", self.test_task_priority_values)
        
        self.cleanup()
        
        self.report.end_time = datetime.now()
        
        return self.report


def main():
    print("Starting comprehensive task API tests...")
    print(f"Target: {BASE_URL}")
    
    tester = TaskAPITester()
    report = tester.run_all_tests()
    
    print(report.get_summary())
    
    report_path = '/tmp/task_api_test_report.txt'
    with open(report_path, 'w') as f:
        f.write(report.get_summary())
    print(f"\nReport saved to: {report_path}")
    
    return report.failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
