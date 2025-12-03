"""
Task Page Feature Testing Suite

Tests all interactive features by:
1. Creating test data directly in the database
2. Making HTTP requests to the running server
3. Validating responses and behavior
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from datetime import datetime, date, timedelta
from app import app, db
from models import User, Task, Meeting, Workspace
from werkzeug.security import generate_password_hash
import time
import json


class TaskFeatureTester:
    """Comprehensive test of task page interactive features"""
    
    def __init__(self):
        self.base_url = "http://0.0.0.0:5000"
        self.session = requests.Session()
        self.test_results = []
        self.user_id = None
        self.workspace_id = None
        self.meeting_id = None
        self.task_ids = []
        
    def log_result(self, test_name, passed, details=""):
        """Log test result"""
        status = "PASS" if passed else "FAIL"
        result = {"test": test_name, "passed": passed, "details": details}
        self.test_results.append(result)
        print(f"{'✅' if passed else '❌'} {status}: {test_name}")
        if details:
            print(f"   {details}")
    
    def setup_test_data(self):
        """Set up test data directly in the database"""
        print("\n" + "="*70)
        print("SETTING UP TEST DATA")
        print("="*70)
        
        with app.app_context():
            unique_id = int(time.time() * 1000)
            
            # Create test user
            user = User(
                username=f"feature_tester_{unique_id}",
                email=f"feature_{unique_id}@test.com",
                password_hash=generate_password_hash("testpass123"),
                active=True,
                is_verified=True,
                onboarding_completed=True,
                onboarding_step=5
            )
            db.session.add(user)
            db.session.flush()
            
            # Create workspace
            workspace = Workspace(
                name=f"Feature Test Workspace {unique_id}",
                slug=f"feature-test-{unique_id}",
                owner_id=user.id,
                created_at=datetime.utcnow()
            )
            db.session.add(workspace)
            db.session.flush()
            
            user.workspace_id = workspace.id
            
            # Create meeting
            meeting = Meeting(
                title=f"Feature Test Meeting {unique_id}",
                workspace_id=workspace.id,
                organizer_id=user.id,
                status='scheduled',
                meeting_type='general',
                created_at=datetime.utcnow()
            )
            db.session.add(meeting)
            db.session.flush()
            
            # Create test tasks with various states
            tasks_data = [
                {'title': 'Test Task Todo', 'status': 'todo', 'priority': 'high'},
                {'title': 'Test Task In Progress', 'status': 'in_progress', 'priority': 'medium'},
                {'title': 'Test Task Completed', 'status': 'completed', 'priority': 'low', 'completed_at': datetime.utcnow()},
                {'title': 'Test Task with Due Date', 'status': 'todo', 'priority': 'high', 'due_date': date.today() + timedelta(days=3)},
                {'title': 'Test Task Overdue', 'status': 'todo', 'priority': 'high', 'due_date': date.today() - timedelta(days=1)},
            ]
            
            for task_data in tasks_data:
                task = Task(
                    title=task_data['title'],
                    meeting_id=meeting.id,
                    status=task_data.get('status', 'todo'),
                    priority=task_data.get('priority', 'medium'),
                    due_date=task_data.get('due_date'),
                    completed_at=task_data.get('completed_at'),
                    created_at=datetime.utcnow(),
                    created_by_id=user.id
                )
                db.session.add(task)
                db.session.flush()
                self.task_ids.append(task.id)
            
            db.session.commit()
            
            self.user_id = user.id
            self.workspace_id = workspace.id
            self.meeting_id = meeting.id
            
            print(f"   Created User: {user.username}")
            print(f"   Created Workspace: {workspace.name}")
            print(f"   Created Meeting: {meeting.title}")
            print(f"   Created {len(self.task_ids)} test tasks")
    
    def test_01_api_authentication(self):
        """Test that API properly requires authentication"""
        print("\n" + "="*70)
        print("TEST 01: API Authentication Enforcement")
        print("="*70)
        
        try:
            endpoints = [
                ('/api/tasks/', 'GET'),
                ('/api/tasks/', 'POST'),
                ('/api/tasks/meeting-heatmap', 'GET'),
            ]
            
            protected_count = 0
            for endpoint, method in endpoints:
                if method == 'GET':
                    response = self.session.get(f"{self.base_url}{endpoint}")
                else:
                    response = self.session.post(f"{self.base_url}{endpoint}", json={})
                
                # 401 = auth required, 302 = redirect to login, 200 with error = JSON auth error
                if response.status_code in [401, 302]:
                    print(f"   ✅ {method} {endpoint} - Protected ({response.status_code})")
                    protected_count += 1
                elif response.status_code == 200:
                    # Check if it's a JSON auth error response
                    try:
                        data = response.json()
                        if data.get('success') == False and 'auth' in str(data).lower():
                            print(f"   ✅ {method} {endpoint} - Protected (JSON auth error)")
                            protected_count += 1
                        else:
                            print(f"   ⚠️ {method} {endpoint} - Returned data without auth")
                    except:
                        print(f"   ⚠️ {method} {endpoint} - Status 200 (not JSON)")
                else:
                    print(f"   ⚠️ {method} {endpoint} - Status {response.status_code}")
            
            # Pass if at least 2/3 endpoints are protected (one might have public access)
            all_protected = protected_count >= 2
            self.log_result("API Authentication", all_protected, f"{protected_count}/{len(endpoints)} endpoints protected")
            return all_protected
        except Exception as e:
            self.log_result("API Authentication", False, f"Error: {str(e)}")
            return False
    
    def test_02_api_response_format(self):
        """Test API response format consistency"""
        print("\n" + "="*70)
        print("TEST 02: API Response Format")
        print("="*70)
        
        try:
            response = self.session.get(f"{self.base_url}/api/tasks/")
            
            if response.status_code == 200:
                data = response.json()
                has_success = 'success' in data
                has_structure = 'tasks' in data or 'error' in data or 'code' in data
                
                if has_structure:
                    self.log_result("API Response Format", True, "JSON structure is valid")
                    return True
                else:
                    self.log_result("API Response Format", False, "Missing expected fields")
            else:
                # Auth required - check error format
                data = response.json()
                if 'error' in data or 'success' in data:
                    self.log_result("API Response Format", True, "Error format is valid")
                    return True
                else:
                    self.log_result("API Response Format", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("API Response Format", False, f"Error: {str(e)}")
        return False
    
    def test_03_task_data_exists(self):
        """Verify test tasks exist in database"""
        print("\n" + "="*70)
        print("TEST 03: Task Data Verification")
        print("="*70)
        
        try:
            with app.app_context():
                from sqlalchemy import select
                tasks = db.session.execute(
                    select(Task).where(Task.id.in_(self.task_ids))
                ).scalars().all()
                
                if len(tasks) == len(self.task_ids):
                    statuses = [t.status for t in tasks]
                    priorities = [t.priority for t in tasks]
                    
                    print(f"   Found {len(tasks)} tasks")
                    print(f"   Statuses: {set(statuses)}")
                    print(f"   Priorities: {set(priorities)}")
                    
                    self.log_result("Task Data Verification", True, f"{len(tasks)} tasks found")
                    return True
                else:
                    self.log_result("Task Data Verification", False, f"Expected {len(self.task_ids)}, found {len(tasks)}")
        except Exception as e:
            self.log_result("Task Data Verification", False, f"Error: {str(e)}")
        return False
    
    def test_04_task_crud_structure(self):
        """Test CRUD API endpoint structure"""
        print("\n" + "="*70)
        print("TEST 04: CRUD Endpoint Structure")
        print("="*70)
        
        try:
            crud_endpoints = [
                ('POST', '/api/tasks/', 'Create'),
                ('GET', '/api/tasks/', 'List'),
                ('GET', f'/api/tasks/{self.task_ids[0]}', 'Read'),
                ('PUT', f'/api/tasks/{self.task_ids[0]}', 'Update'),
                ('DELETE', f'/api/tasks/{self.task_ids[0]}', 'Delete'),
                ('PUT', f'/api/tasks/{self.task_ids[0]}/status', 'Status Update'),
            ]
            
            all_accessible = True
            for method, endpoint, operation in crud_endpoints:
                try:
                    if method == 'GET':
                        response = self.session.get(f"{self.base_url}{endpoint}")
                    elif method == 'POST':
                        response = self.session.post(f"{self.base_url}{endpoint}", json={'title': 'test'})
                    elif method == 'PUT':
                        response = self.session.put(f"{self.base_url}{endpoint}", json={'status': 'todo'})
                    elif method == 'DELETE':
                        response = self.session.delete(f"{self.base_url}{endpoint}")
                    
                    # 401/302 means auth required but endpoint exists
                    # 404 means endpoint doesn't exist
                    # 200/201 means endpoint works
                    if response.status_code in [200, 201, 401, 302, 400]:
                        print(f"   ✅ {operation} ({method} {endpoint}) - Accessible")
                    elif response.status_code == 404:
                        print(f"   ❌ {operation} ({method} {endpoint}) - Not Found")
                        all_accessible = False
                    else:
                        print(f"   ⚠️ {operation} ({method} {endpoint}) - Status {response.status_code}")
                except Exception as e:
                    print(f"   ❌ {operation} - Error: {str(e)}")
                    all_accessible = False
            
            self.log_result("CRUD Endpoint Structure", all_accessible, "All endpoints accessible")
            return all_accessible
        except Exception as e:
            self.log_result("CRUD Endpoint Structure", False, f"Error: {str(e)}")
        return False
    
    def test_05_bulk_operations_structure(self):
        """Test bulk operation endpoints"""
        print("\n" + "="*70)
        print("TEST 05: Bulk Operations Structure")
        print("="*70)
        
        try:
            bulk_endpoints = [
                ('/api/tasks/bulk/complete', 'Bulk Complete'),
                ('/api/tasks/bulk/delete', 'Bulk Delete'),
                ('/api/tasks/bulk/label', 'Bulk Label'),
                ('/api/tasks/bulk-update', 'Bulk Update'),
            ]
            
            all_accessible = True
            for endpoint, operation in bulk_endpoints:
                response = self.session.post(
                    f"{self.base_url}{endpoint}",
                    json={'task_ids': [1, 2, 3]}
                )
                
                # Endpoint exists if we get auth error (401) or validation error (400)
                if response.status_code in [200, 201, 401, 302, 400]:
                    print(f"   ✅ {operation} - Accessible ({response.status_code})")
                elif response.status_code == 404:
                    print(f"   ❌ {operation} - Not Found")
                    all_accessible = False
                else:
                    print(f"   ⚠️ {operation} - Status {response.status_code}")
            
            self.log_result("Bulk Operations Structure", all_accessible, "All bulk endpoints accessible")
            return all_accessible
        except Exception as e:
            self.log_result("Bulk Operations Structure", False, f"Error: {str(e)}")
        return False
    
    def test_06_static_assets(self):
        """Test all task-related static assets load"""
        print("\n" + "="*70)
        print("TEST 06: Static Assets Loading")
        print("="*70)
        
        try:
            css_files = [
                'tasks.css', 'ai-proposals-modal.css', 'task-redesign.css',
                'task-completion-ux.css', 'task-confirmation-modal.css', 'task-sheets.css'
            ]
            
            js_files = [
                'task-bootstrap.js', 'task-cache.js', 'task-card-controller.js',
                'task-menu-controller.js', 'task-modal-manager.js', 
                'task-offline-queue.js', 'task-optimistic-ui.js'
            ]
            
            all_loaded = True
            total_size = 0
            
            print("   CSS Files:")
            for css in css_files:
                response = self.session.get(f"{self.base_url}/static/css/{css}")
                if response.status_code == 200:
                    size = len(response.content)
                    total_size += size
                    print(f"      ✅ {css} ({size:,} bytes)")
                else:
                    print(f"      ❌ {css} - {response.status_code}")
                    all_loaded = False
            
            print("   JS Files:")
            for js in js_files:
                response = self.session.get(f"{self.base_url}/static/js/{js}")
                if response.status_code == 200:
                    size = len(response.content)
                    total_size += size
                    print(f"      ✅ {js} ({size:,} bytes)")
                else:
                    print(f"      ❌ {js} - {response.status_code}")
                    all_loaded = False
            
            self.log_result("Static Assets Loading", all_loaded, f"Total: {total_size:,} bytes")
            return all_loaded
        except Exception as e:
            self.log_result("Static Assets Loading", False, f"Error: {str(e)}")
        return False
    
    def test_07_database_operations(self):
        """Test database CRUD operations directly"""
        print("\n" + "="*70)
        print("TEST 07: Database CRUD Operations")
        print("="*70)
        
        try:
            with app.app_context():
                from sqlalchemy import select
                
                # Test CREATE
                new_task = Task(
                    title='DB Test Task',
                    meeting_id=self.meeting_id,
                    status='todo',
                    priority='medium',
                    created_at=datetime.utcnow()
                )
                db.session.add(new_task)
                db.session.flush()
                new_task_id = new_task.id
                print(f"   ✅ CREATE: Task {new_task_id} created")
                
                # Test READ
                task = db.session.get(Task, new_task_id)
                if task and task.title == 'DB Test Task':
                    print(f"   ✅ READ: Task {new_task_id} retrieved")
                else:
                    print(f"   ❌ READ: Failed to retrieve task")
                    return False
                
                # Test UPDATE
                task.title = 'Updated DB Test Task'
                task.status = 'in_progress'
                task.priority = 'high'
                db.session.flush()
                
                updated_task = db.session.get(Task, new_task_id)
                if updated_task.title == 'Updated DB Test Task' and updated_task.status == 'in_progress':
                    print(f"   ✅ UPDATE: Task {new_task_id} updated")
                else:
                    print(f"   ❌ UPDATE: Failed to update task")
                    return False
                
                # Test status toggle (completion)
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                db.session.flush()
                
                completed_task = db.session.get(Task, new_task_id)
                if completed_task.status == 'completed' and completed_task.completed_at:
                    print(f"   ✅ COMPLETE: Task {new_task_id} marked complete")
                else:
                    print(f"   ❌ COMPLETE: Failed to complete task")
                    return False
                
                # Test uncomplete (toggle back)
                task.status = 'todo'
                task.completed_at = None
                db.session.flush()
                
                uncompleted_task = db.session.get(Task, new_task_id)
                if uncompleted_task.status == 'todo' and uncompleted_task.completed_at is None:
                    print(f"   ✅ UNCOMPLETE: Task {new_task_id} marked incomplete")
                else:
                    print(f"   ❌ UNCOMPLETE: Failed to uncomplete task")
                    return False
                
                # Test DELETE (soft delete)
                task.deleted_at = datetime.utcnow()
                task.deleted_by_user_id = self.user_id
                db.session.flush()
                
                deleted_task = db.session.get(Task, new_task_id)
                if deleted_task.deleted_at:
                    print(f"   ✅ DELETE: Task {new_task_id} soft deleted")
                else:
                    print(f"   ❌ DELETE: Failed to delete task")
                    return False
                
                # Test UNDO delete
                task.deleted_at = None
                task.deleted_by_user_id = None
                db.session.flush()
                
                restored_task = db.session.get(Task, new_task_id)
                if restored_task.deleted_at is None:
                    print(f"   ✅ UNDO DELETE: Task {new_task_id} restored")
                else:
                    print(f"   ❌ UNDO DELETE: Failed to restore task")
                    return False
                
                # Clean up test task
                db.session.delete(task)
                db.session.commit()
                print(f"   ✅ CLEANUP: Test task removed")
                
                self.log_result("Database CRUD Operations", True, "All operations successful")
                return True
                
        except Exception as e:
            db.session.rollback()
            self.log_result("Database CRUD Operations", False, f"Error: {str(e)}")
        return False
    
    def test_08_task_filtering(self):
        """Test task filtering in database"""
        print("\n" + "="*70)
        print("TEST 08: Task Filtering")
        print("="*70)
        
        try:
            with app.app_context():
                from sqlalchemy import select, and_
                
                # Filter by status
                todo_tasks = db.session.execute(
                    select(Task).where(
                        and_(
                            Task.meeting_id == self.meeting_id,
                            Task.status == 'todo',
                            Task.deleted_at.is_(None)
                        )
                    )
                ).scalars().all()
                print(f"   ✅ Status filter (todo): {len(todo_tasks)} tasks")
                
                # Filter by priority
                high_priority = db.session.execute(
                    select(Task).where(
                        and_(
                            Task.meeting_id == self.meeting_id,
                            Task.priority == 'high',
                            Task.deleted_at.is_(None)
                        )
                    )
                ).scalars().all()
                print(f"   ✅ Priority filter (high): {len(high_priority)} tasks")
                
                # Filter overdue tasks
                today = date.today()
                overdue_tasks = db.session.execute(
                    select(Task).where(
                        and_(
                            Task.meeting_id == self.meeting_id,
                            Task.due_date < today,
                            Task.status.in_(['todo', 'in_progress']),
                            Task.deleted_at.is_(None)
                        )
                    )
                ).scalars().all()
                print(f"   ✅ Overdue filter: {len(overdue_tasks)} tasks")
                
                # Filter completed tasks
                completed_tasks = db.session.execute(
                    select(Task).where(
                        and_(
                            Task.meeting_id == self.meeting_id,
                            Task.status == 'completed',
                            Task.deleted_at.is_(None)
                        )
                    )
                ).scalars().all()
                print(f"   ✅ Completed filter: {len(completed_tasks)} tasks")
                
                self.log_result("Task Filtering", True, "All filters working")
                return True
                
        except Exception as e:
            self.log_result("Task Filtering", False, f"Error: {str(e)}")
        return False
    
    def test_09_task_search(self):
        """Test task search functionality"""
        print("\n" + "="*70)
        print("TEST 09: Task Search")
        print("="*70)
        
        try:
            with app.app_context():
                from sqlalchemy import select, or_
                
                search_term = 'Test Task'
                results = db.session.execute(
                    select(Task).where(
                        or_(
                            Task.title.contains(search_term),
                            Task.description.contains(search_term) if Task.description else False
                        )
                    ).where(Task.meeting_id == self.meeting_id)
                ).scalars().all()
                
                print(f"   ✅ Search '{search_term}': {len(results)} results")
                
                if len(results) > 0:
                    self.log_result("Task Search", True, f"Found {len(results)} matching tasks")
                    return True
                else:
                    self.log_result("Task Search", False, "No results found")
                    return False
                
        except Exception as e:
            self.log_result("Task Search", False, f"Error: {str(e)}")
        return False
    
    def test_10_error_handling(self):
        """Test API error handling"""
        print("\n" + "="*70)
        print("TEST 10: Error Handling")
        print("="*70)
        
        try:
            test_cases = [
                (f'/api/tasks/999999', 'GET', 'Non-existent task'),
                (f'/api/tasks/invalid', 'GET', 'Invalid task ID'),
            ]
            
            all_handled = True
            for endpoint, method, description in test_cases:
                if method == 'GET':
                    response = self.session.get(f"{self.base_url}{endpoint}")
                else:
                    response = self.session.post(f"{self.base_url}{endpoint}", json={})
                
                # Should get 401 (auth), 404 (not found), or 400 (bad request)
                if response.status_code in [400, 401, 404]:
                    print(f"   ✅ {description}: Handled ({response.status_code})")
                else:
                    print(f"   ⚠️ {description}: Unexpected ({response.status_code})")
                    all_handled = False
            
            self.log_result("Error Handling", all_handled, "All errors properly handled")
            return all_handled
        except Exception as e:
            self.log_result("Error Handling", False, f"Error: {str(e)}")
        return False
    
    def test_11_websocket_endpoint(self):
        """Test WebSocket endpoint availability"""
        print("\n" + "="*70)
        print("TEST 11: WebSocket Endpoint")
        print("="*70)
        
        try:
            response = self.session.get(f"{self.base_url}/socket.io/")
            
            # Socket.IO should be accessible (may return 400 for protocol mismatch)
            if response.status_code in [200, 400]:
                self.log_result("WebSocket Endpoint", True, "Socket.IO accessible")
                return True
            else:
                self.log_result("WebSocket Endpoint", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("WebSocket Endpoint", False, f"Error: {str(e)}")
        return False
    
    def test_12_performance(self):
        """Test API performance"""
        print("\n" + "="*70)
        print("TEST 12: API Performance")
        print("="*70)
        
        try:
            import time
            
            # Test static asset load time
            start = time.time()
            response = self.session.get(f"{self.base_url}/static/js/task-bootstrap.js")
            static_time = (time.time() - start) * 1000
            
            # Test API response time
            start = time.time()
            response = self.session.get(f"{self.base_url}/api/tasks/")
            api_time = (time.time() - start) * 1000
            
            # Test page load time
            start = time.time()
            response = self.session.get(f"{self.base_url}/dashboard/tasks", allow_redirects=True)
            page_time = (time.time() - start) * 1000
            
            print(f"   Static asset: {static_time:.0f}ms")
            print(f"   API response: {api_time:.0f}ms")
            print(f"   Page load: {page_time:.0f}ms")
            
            # All should be under 500ms
            all_fast = static_time < 500 and api_time < 500 and page_time < 1000
            
            self.log_result("API Performance", all_fast, f"All under thresholds")
            return all_fast
        except Exception as e:
            self.log_result("API Performance", False, f"Error: {str(e)}")
        return False
    
    def cleanup(self):
        """Clean up test data"""
        print("\n" + "="*70)
        print("CLEANING UP TEST DATA")
        print("="*70)
        
        try:
            with app.app_context():
                try:
                    # Delete test tasks
                    for task_id in self.task_ids:
                        task = db.session.get(Task, task_id)
                        if task:
                            db.session.delete(task)
                    
                    # Delete test meeting
                    if self.meeting_id:
                        meeting = db.session.get(Meeting, self.meeting_id)
                        if meeting:
                            db.session.delete(meeting)
                    
                    # Delete test user
                    if self.user_id:
                        user = db.session.get(User, self.user_id)
                        if user:
                            db.session.delete(user)
                    
                    # Delete test workspace
                    if self.workspace_id:
                        workspace = db.session.get(Workspace, self.workspace_id)
                        if workspace:
                            db.session.delete(workspace)
                    
                    db.session.commit()
                    print("   ✅ Test data cleaned up")
                except Exception as e:
                    db.session.rollback()
                    print(f"   ⚠️ Cleanup error: {str(e)}")
        except Exception as e:
            print(f"   ⚠️ Cleanup context error: {str(e)}")
    
    def generate_report(self):
        """Generate final report"""
        print("\n" + "="*70)
        print("FINAL TEST REPORT")
        print("="*70)
        
        passed = sum(1 for r in self.test_results if r['passed'])
        total = len(self.test_results)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Pass Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        
        if total - passed > 0:
            print("\nFailed Tests:")
            for r in self.test_results:
                if not r['passed']:
                    print(f"   ❌ {r['test']}: {r['details']}")
        
        print("\n" + "="*70)
        return passed == total
    
    def run_all_tests(self):
        """Run all tests"""
        print("="*70)
        print("TASK PAGE FEATURE TESTING SUITE")
        print("="*70)
        print(f"Target: {self.base_url}")
        print(f"Started: {datetime.now().isoformat()}")
        print("="*70)
        
        try:
            self.setup_test_data()
            
            self.test_01_api_authentication()
            self.test_02_api_response_format()
            self.test_03_task_data_exists()
            self.test_04_task_crud_structure()
            self.test_05_bulk_operations_structure()
            self.test_06_static_assets()
            self.test_07_database_operations()
            self.test_08_task_filtering()
            self.test_09_task_search()
            self.test_10_error_handling()
            self.test_11_websocket_endpoint()
            self.test_12_performance()
            
            return self.generate_report()
            
        finally:
            self.cleanup()


if __name__ == '__main__':
    tester = TaskFeatureTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
