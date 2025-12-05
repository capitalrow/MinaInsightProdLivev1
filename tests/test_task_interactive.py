"""
Interactive Task Page Testing Suite

Tests all interactive features on the task page including:
- Task creation
- Task editing
- Status toggling (completion)
- Task deletion
- Filtering and search
- Bulk operations
- Modal interactions
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Task, Meeting, Workspace
from werkzeug.security import generate_password_hash
from flask_login import login_user
import json
from datetime import datetime, date, timedelta
import time


class InteractiveTaskTester:
    """Test all interactive task page features"""
    
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['LOGIN_DISABLED'] = False
        self.client = None
        self.test_user = None
        self.test_workspace = None
        self.test_meeting = None
        self.created_tasks = []
        self.test_results = []
        
    def setup(self):
        """Set up test environment with authenticated user"""
        print("\n" + "="*70)
        print("SETTING UP TEST ENVIRONMENT")
        print("="*70)
        
        self.client = self.app.test_client(use_cookies=True)
        
        with self.app.app_context():
            unique_id = int(time.time() * 1000)
            
            # Create test user first (without workspace)
            self.test_user = User(
                username=f"interactive_tester_{unique_id}",
                email=f"interactive_{unique_id}@test.com",
                password_hash=generate_password_hash("testpass123"),
                active=True,
                is_verified=True,
                onboarding_completed=True,
                onboarding_step=5
            )
            db.session.add(self.test_user)
            db.session.flush()
            
            # Create test workspace with owner
            self.test_workspace = Workspace(
                name=f"Interactive Test Workspace {unique_id}",
                slug=f"interactive-test-{unique_id}",
                owner_id=self.test_user.id,
                created_at=datetime.utcnow()
            )
            db.session.add(self.test_workspace)
            db.session.flush()
            
            # Update user with workspace
            self.test_user.workspace_id = self.test_workspace.id
            
            # Create test meeting to link tasks
            self.test_meeting = Meeting(
                title=f"Interactive Test Meeting {unique_id}",
                workspace_id=self.test_workspace.id,
                organizer_id=self.test_user.id,
                status='scheduled',
                meeting_type='general',
                created_at=datetime.utcnow()
            )
            db.session.add(self.test_meeting)
            db.session.commit()
            
            # Store IDs for later use
            self.user_id = self.test_user.id
            self.workspace_id = self.test_workspace.id
            self.meeting_id = self.test_meeting.id
            self.test_email = self.test_user.email
            
            print(f"   Created User: {self.test_user.username} (ID: {self.user_id})")
            print(f"   Created Workspace: {self.test_workspace.name}")
            print(f"   Created Meeting: {self.test_meeting.title}")
    
    def login(self):
        """Log in the test user via form submission"""
        print("\n   Logging in test user...")
        
        # Login via the actual auth endpoint
        response = self.client.post(
            '/auth/login',
            data={
                'email': self.test_email,
                'password': 'testpass123'
            },
            follow_redirects=False
        )
        
        if response.status_code in [200, 302]:
            print(f"   ✅ User logged in (status: {response.status_code})")
            return True
        else:
            print(f"   ⚠️ Login returned status: {response.status_code}")
            # Try session-based login as fallback
            with self.client.session_transaction() as sess:
                sess['_user_id'] = str(self.user_id)
                sess['_fresh'] = True
            print("   ✅ User logged in via session fallback")
            return True
    
    def log_result(self, test_name, passed, details=""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {"test": test_name, "passed": passed, "details": details}
        self.test_results.append(result)
        print(f"{status}: {test_name}")
        if details:
            print(f"   {details}")
    
    def test_01_create_task(self):
        """Test creating a new task"""
        print("\n" + "="*70)
        print("TEST 01: Create Task")
        print("="*70)
        
        try:
            task_data = {
                'title': 'Test Interactive Task',
                'description': 'This task was created by the interactive test suite',
                'priority': 'high',
                'status': 'todo',
                'due_date': (date.today() + timedelta(days=7)).isoformat(),
                'meeting_id': self.meeting_id
            }
            
            response = self.client.post(
                '/api/tasks/',
                data=json.dumps(task_data),
                content_type='application/json'
            )
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.get_json()
                if data.get('success') or data.get('task'):
                    task = data.get('task', {})
                    task_id = task.get('id')
                    if task_id:
                        self.created_tasks.append(task_id)
                        self.log_result("Create Task", True, f"Created task ID: {task_id}")
                        return task_id
                    else:
                        self.log_result("Create Task", False, "No task ID in response")
                else:
                    self.log_result("Create Task", False, f"Response: {data}")
            else:
                self.log_result("Create Task", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Create Task", False, f"Error: {str(e)}")
        return None
    
    def test_02_read_task(self, task_id):
        """Test reading a task"""
        print("\n" + "="*70)
        print("TEST 02: Read Task")
        print("="*70)
        
        if not task_id:
            self.log_result("Read Task", False, "No task ID provided")
            return False
        
        try:
            response = self.client.get(f'/api/tasks/{task_id}')
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success') and data.get('task'):
                    task = data['task']
                    self.log_result("Read Task", True, f"Title: {task.get('title')}")
                    return True
                else:
                    self.log_result("Read Task", False, f"Response: {data}")
            else:
                self.log_result("Read Task", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Read Task", False, f"Error: {str(e)}")
        return False
    
    def test_03_update_task_title(self, task_id):
        """Test updating a task's title"""
        print("\n" + "="*70)
        print("TEST 03: Update Task Title")
        print("="*70)
        
        if not task_id:
            self.log_result("Update Task Title", False, "No task ID provided")
            return False
        
        try:
            update_data = {
                'title': 'Updated Interactive Task Title'
            }
            
            response = self.client.put(
                f'/api/tasks/{task_id}',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    task = data.get('task', {})
                    new_title = task.get('title', '')
                    if 'Updated' in new_title:
                        self.log_result("Update Task Title", True, f"New title: {new_title}")
                        return True
                    else:
                        self.log_result("Update Task Title", False, f"Title not updated: {new_title}")
                else:
                    self.log_result("Update Task Title", False, f"Response: {data}")
            else:
                self.log_result("Update Task Title", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Update Task Title", False, f"Error: {str(e)}")
        return False
    
    def test_04_update_task_priority(self, task_id):
        """Test updating a task's priority"""
        print("\n" + "="*70)
        print("TEST 04: Update Task Priority")
        print("="*70)
        
        if not task_id:
            self.log_result("Update Task Priority", False, "No task ID provided")
            return False
        
        try:
            update_data = {
                'priority': 'medium'
            }
            
            response = self.client.put(
                f'/api/tasks/{task_id}',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    task = data.get('task', {})
                    new_priority = task.get('priority', '')
                    if new_priority == 'medium':
                        self.log_result("Update Task Priority", True, f"New priority: {new_priority}")
                        return True
                    else:
                        self.log_result("Update Task Priority", False, f"Priority not updated: {new_priority}")
                else:
                    self.log_result("Update Task Priority", False, f"Response: {data}")
            else:
                self.log_result("Update Task Priority", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Update Task Priority", False, f"Error: {str(e)}")
        return False
    
    def test_05_update_task_description(self, task_id):
        """Test updating a task's description"""
        print("\n" + "="*70)
        print("TEST 05: Update Task Description")
        print("="*70)
        
        if not task_id:
            self.log_result("Update Task Description", False, "No task ID provided")
            return False
        
        try:
            new_description = "Updated description: This task has been modified by the test suite."
            update_data = {
                'description': new_description
            }
            
            response = self.client.put(
                f'/api/tasks/{task_id}',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    task = data.get('task', {})
                    task_desc = task.get('description', '')
                    if 'Updated description' in (task_desc or ''):
                        self.log_result("Update Task Description", True, f"Description updated")
                        return True
                    else:
                        self.log_result("Update Task Description", False, f"Description not updated")
                else:
                    self.log_result("Update Task Description", False, f"Response: {data}")
            else:
                self.log_result("Update Task Description", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Update Task Description", False, f"Error: {str(e)}")
        return False
    
    def test_06_toggle_task_complete(self, task_id):
        """Test marking a task as completed"""
        print("\n" + "="*70)
        print("TEST 06: Toggle Task Complete (todo -> completed)")
        print("="*70)
        
        if not task_id:
            self.log_result("Toggle Task Complete", False, "No task ID provided")
            return False
        
        try:
            update_data = {
                'status': 'completed'
            }
            
            response = self.client.put(
                f'/api/tasks/{task_id}/status',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    task = data.get('task', {})
                    new_status = task.get('status', '')
                    if new_status == 'completed':
                        self.log_result("Toggle Task Complete", True, f"Status: {new_status}")
                        return True
                    else:
                        self.log_result("Toggle Task Complete", False, f"Status not updated: {new_status}")
                else:
                    self.log_result("Toggle Task Complete", False, f"Response: {data}")
            else:
                self.log_result("Toggle Task Complete", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Toggle Task Complete", False, f"Error: {str(e)}")
        return False
    
    def test_07_toggle_task_incomplete(self, task_id):
        """Test marking a task back to todo"""
        print("\n" + "="*70)
        print("TEST 07: Toggle Task Incomplete (completed -> todo)")
        print("="*70)
        
        if not task_id:
            self.log_result("Toggle Task Incomplete", False, "No task ID provided")
            return False
        
        try:
            update_data = {
                'status': 'todo'
            }
            
            response = self.client.put(
                f'/api/tasks/{task_id}/status',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    task = data.get('task', {})
                    new_status = task.get('status', '')
                    if new_status == 'todo':
                        self.log_result("Toggle Task Incomplete", True, f"Status: {new_status}")
                        return True
                    else:
                        self.log_result("Toggle Task Incomplete", False, f"Status not updated: {new_status}")
                else:
                    self.log_result("Toggle Task Incomplete", False, f"Response: {data}")
            else:
                self.log_result("Toggle Task Incomplete", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Toggle Task Incomplete", False, f"Error: {str(e)}")
        return False
    
    def test_08_set_in_progress(self, task_id):
        """Test setting a task to in_progress"""
        print("\n" + "="*70)
        print("TEST 08: Set Task In Progress")
        print("="*70)
        
        if not task_id:
            self.log_result("Set Task In Progress", False, "No task ID provided")
            return False
        
        try:
            update_data = {
                'status': 'in_progress'
            }
            
            response = self.client.put(
                f'/api/tasks/{task_id}/status',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    task = data.get('task', {})
                    new_status = task.get('status', '')
                    if new_status == 'in_progress':
                        self.log_result("Set Task In Progress", True, f"Status: {new_status}")
                        return True
                    else:
                        self.log_result("Set Task In Progress", False, f"Status not updated: {new_status}")
                else:
                    self.log_result("Set Task In Progress", False, f"Response: {data}")
            else:
                self.log_result("Set Task In Progress", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Set Task In Progress", False, f"Error: {str(e)}")
        return False
    
    def test_09_update_due_date(self, task_id):
        """Test updating a task's due date"""
        print("\n" + "="*70)
        print("TEST 09: Update Task Due Date")
        print("="*70)
        
        if not task_id:
            self.log_result("Update Task Due Date", False, "No task ID provided")
            return False
        
        try:
            new_due_date = (date.today() + timedelta(days=14)).isoformat()
            update_data = {
                'due_date': new_due_date
            }
            
            response = self.client.put(
                f'/api/tasks/{task_id}',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    task = data.get('task', {})
                    task_due_date = task.get('due_date', '')
                    if task_due_date and new_due_date in task_due_date:
                        self.log_result("Update Task Due Date", True, f"Due date: {task_due_date}")
                        return True
                    else:
                        self.log_result("Update Task Due Date", False, f"Due date not updated: {task_due_date}")
                else:
                    self.log_result("Update Task Due Date", False, f"Response: {data}")
            else:
                self.log_result("Update Task Due Date", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Update Task Due Date", False, f"Error: {str(e)}")
        return False
    
    def test_10_list_tasks_filtering(self):
        """Test task list filtering"""
        print("\n" + "="*70)
        print("TEST 10: Task List Filtering")
        print("="*70)
        
        try:
            # Test status filter
            response = self.client.get('/api/tasks/?status=in_progress')
            
            if response.status_code == 200:
                data = response.get_json()
                if 'tasks' in data:
                    tasks = data['tasks']
                    all_in_progress = all(t.get('status') == 'in_progress' for t in tasks) if tasks else True
                    if all_in_progress:
                        self.log_result("Task List Filtering", True, f"Found {len(tasks)} in_progress tasks")
                        return True
                    else:
                        self.log_result("Task List Filtering", False, "Filter not applied correctly")
                else:
                    self.log_result("Task List Filtering", False, f"Response: {data}")
            else:
                self.log_result("Task List Filtering", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Task List Filtering", False, f"Error: {str(e)}")
        return False
    
    def test_11_task_search(self):
        """Test task search functionality"""
        print("\n" + "="*70)
        print("TEST 11: Task Search")
        print("="*70)
        
        try:
            response = self.client.get('/api/tasks/?search=Interactive')
            
            if response.status_code == 200:
                data = response.get_json()
                if 'tasks' in data:
                    tasks = data['tasks']
                    self.log_result("Task Search", True, f"Found {len(tasks)} matching tasks")
                    return True
                else:
                    self.log_result("Task Search", False, f"Response: {data}")
            else:
                self.log_result("Task Search", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Task Search", False, f"Error: {str(e)}")
        return False
    
    def test_12_create_multiple_tasks_for_bulk(self):
        """Create multiple tasks for bulk operations testing"""
        print("\n" + "="*70)
        print("TEST 12: Create Multiple Tasks for Bulk Operations")
        print("="*70)
        
        try:
            bulk_task_ids = []
            for i in range(3):
                task_data = {
                    'title': f'Bulk Test Task {i+1}',
                    'description': f'Task {i+1} for bulk testing',
                    'priority': 'low',
                    'status': 'todo',
                    'meeting_id': self.meeting_id
                }
                
                response = self.client.post(
                    '/api/tasks/',
                    data=json.dumps(task_data),
                    content_type='application/json'
                )
                
                if response.status_code in [200, 201]:
                    data = response.get_json()
                    if data.get('task', {}).get('id'):
                        task_id = data['task']['id']
                        bulk_task_ids.append(task_id)
                        self.created_tasks.append(task_id)
            
            if len(bulk_task_ids) == 3:
                self.log_result("Create Bulk Tasks", True, f"Created tasks: {bulk_task_ids}")
                return bulk_task_ids
            else:
                self.log_result("Create Bulk Tasks", False, f"Only created {len(bulk_task_ids)} tasks")
        except Exception as e:
            self.log_result("Create Bulk Tasks", False, f"Error: {str(e)}")
        return []
    
    def test_13_bulk_complete_tasks(self, task_ids):
        """Test bulk completing tasks"""
        print("\n" + "="*70)
        print("TEST 13: Bulk Complete Tasks")
        print("="*70)
        
        if not task_ids or len(task_ids) < 2:
            self.log_result("Bulk Complete Tasks", False, "Not enough task IDs")
            return False
        
        try:
            response = self.client.post(
                '/api/tasks/bulk/complete',
                data=json.dumps({'task_ids': task_ids[:2]}),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    count = data.get('count', 0)
                    self.log_result("Bulk Complete Tasks", True, f"Completed {count} tasks")
                    return True
                else:
                    self.log_result("Bulk Complete Tasks", False, f"Response: {data}")
            else:
                self.log_result("Bulk Complete Tasks", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Bulk Complete Tasks", False, f"Error: {str(e)}")
        return False
    
    def test_14_bulk_add_label(self, task_ids):
        """Test bulk adding labels to tasks"""
        print("\n" + "="*70)
        print("TEST 14: Bulk Add Label")
        print("="*70)
        
        if not task_ids:
            self.log_result("Bulk Add Label", False, "No task IDs")
            return False
        
        try:
            response = self.client.post(
                '/api/tasks/bulk/label',
                data=json.dumps({'task_ids': task_ids, 'label': 'test-label'}),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    label = data.get('label', '')
                    count = data.get('count', 0)
                    self.log_result("Bulk Add Label", True, f"Added '{label}' to {count} tasks")
                    return True
                else:
                    self.log_result("Bulk Add Label", False, f"Response: {data}")
            else:
                self.log_result("Bulk Add Label", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Bulk Add Label", False, f"Error: {str(e)}")
        return False
    
    def test_15_delete_task(self, task_id):
        """Test soft-deleting a task"""
        print("\n" + "="*70)
        print("TEST 15: Delete Task (Soft Delete)")
        print("="*70)
        
        if not task_id:
            self.log_result("Delete Task", False, "No task ID provided")
            return False
        
        try:
            response = self.client.delete(f'/api/tasks/{task_id}')
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    self.log_result("Delete Task", True, f"Deleted task {task_id}")
                    return True
                else:
                    self.log_result("Delete Task", False, f"Response: {data}")
            else:
                self.log_result("Delete Task", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Delete Task", False, f"Error: {str(e)}")
        return False
    
    def test_16_undo_delete_task(self, task_id):
        """Test undoing a task deletion within the undo window"""
        print("\n" + "="*70)
        print("TEST 16: Undo Delete Task")
        print("="*70)
        
        if not task_id:
            self.log_result("Undo Delete Task", False, "No task ID provided")
            return False
        
        try:
            response = self.client.post(f'/api/tasks/{task_id}/undo-delete')
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    self.log_result("Undo Delete Task", True, f"Restored task {task_id}")
                    return True
                else:
                    self.log_result("Undo Delete Task", False, f"Response: {data}")
            else:
                self.log_result("Undo Delete Task", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Undo Delete Task", False, f"Error: {str(e)}")
        return False
    
    def test_17_bulk_delete_tasks(self, task_ids):
        """Test bulk deleting tasks"""
        print("\n" + "="*70)
        print("TEST 17: Bulk Delete Tasks")
        print("="*70)
        
        if not task_ids:
            self.log_result("Bulk Delete Tasks", False, "No task IDs")
            return False
        
        try:
            response = self.client.post(
                '/api/tasks/bulk/delete',
                data=json.dumps({'task_ids': task_ids}),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    count = data.get('count', 0)
                    self.log_result("Bulk Delete Tasks", True, f"Deleted {count} tasks")
                    return True
                else:
                    self.log_result("Bulk Delete Tasks", False, f"Response: {data}")
            else:
                self.log_result("Bulk Delete Tasks", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Bulk Delete Tasks", False, f"Error: {str(e)}")
        return False
    
    def test_18_meeting_heatmap_api(self):
        """Test the meeting heatmap API"""
        print("\n" + "="*70)
        print("TEST 18: Meeting Heatmap API")
        print("="*70)
        
        try:
            response = self.client.get('/api/tasks/meeting-heatmap')
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    meetings = data.get('meetings', [])
                    self.log_result("Meeting Heatmap API", True, f"Found {len(meetings)} meetings")
                    return True
                else:
                    self.log_result("Meeting Heatmap API", False, f"Response: {data}")
            else:
                self.log_result("Meeting Heatmap API", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Meeting Heatmap API", False, f"Error: {str(e)}")
        return False
    
    def test_19_task_page_render(self):
        """Test that the task page renders correctly"""
        print("\n" + "="*70)
        print("TEST 19: Task Page Render")
        print("="*70)
        
        try:
            response = self.client.get('/dashboard/tasks')
            
            if response.status_code == 200:
                html = response.data.decode('utf-8')
                required_elements = [
                    'task',
                    'Tasks',
                ]
                
                found = [elem for elem in required_elements if elem in html]
                
                if len(found) >= 1:
                    self.log_result("Task Page Render", True, f"Page contains expected content")
                    return True
                else:
                    self.log_result("Task Page Render", False, "Missing expected content")
            else:
                self.log_result("Task Page Render", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Task Page Render", False, f"Error: {str(e)}")
        return False
    
    def test_20_priority_filter(self):
        """Test priority filtering"""
        print("\n" + "="*70)
        print("TEST 20: Priority Filter")
        print("="*70)
        
        try:
            response = self.client.get('/api/tasks/?priority=high')
            
            if response.status_code == 200:
                data = response.get_json()
                if 'tasks' in data:
                    tasks = data['tasks']
                    all_high = all(t.get('priority') == 'high' for t in tasks) if tasks else True
                    if all_high:
                        self.log_result("Priority Filter", True, f"Found {len(tasks)} high-priority tasks")
                        return True
                    else:
                        self.log_result("Priority Filter", False, "Filter not applied correctly")
                else:
                    self.log_result("Priority Filter", False, f"Response: {data}")
            else:
                self.log_result("Priority Filter", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Priority Filter", False, f"Error: {str(e)}")
        return False
    
    def cleanup(self):
        """Clean up test data"""
        print("\n" + "="*70)
        print("CLEANING UP TEST DATA")
        print("="*70)
        
        with self.app.app_context():
            try:
                # Delete test tasks
                for task_id in self.created_tasks:
                    task = db.session.get(Task, task_id)
                    if task:
                        db.session.delete(task)
                
                # Delete test meeting
                if self.meeting_id:
                    meeting = db.session.get(Meeting, self.meeting_id)
                    if meeting:
                        # Delete any remaining tasks linked to this meeting
                        Task.query.filter_by(meeting_id=self.meeting_id).delete()
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
                print("   ✅ Test data cleaned up successfully")
            except Exception as e:
                db.session.rollback()
                print(f"   ⚠️ Cleanup warning: {str(e)}")
    
    def generate_report(self):
        """Generate final test report"""
        print("\n" + "="*70)
        print("FINAL INTERACTIVE TEST REPORT")
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
        """Run all interactive tests"""
        print("="*70)
        print("INTERACTIVE TASK PAGE TESTING SUITE")
        print("="*70)
        print(f"Started: {datetime.now().isoformat()}")
        print("="*70)
        
        try:
            # Setup
            self.setup()
            self.login()
            
            # Run tests
            task_id = self.test_01_create_task()
            self.test_02_read_task(task_id)
            self.test_03_update_task_title(task_id)
            self.test_04_update_task_priority(task_id)
            self.test_05_update_task_description(task_id)
            self.test_06_toggle_task_complete(task_id)
            self.test_07_toggle_task_incomplete(task_id)
            self.test_08_set_in_progress(task_id)
            self.test_09_update_due_date(task_id)
            self.test_10_list_tasks_filtering()
            self.test_11_task_search()
            
            # Bulk operations
            bulk_task_ids = self.test_12_create_multiple_tasks_for_bulk()
            self.test_13_bulk_complete_tasks(bulk_task_ids)
            self.test_14_bulk_add_label(bulk_task_ids)
            
            # Delete operations
            if task_id:
                self.test_15_delete_task(task_id)
                self.test_16_undo_delete_task(task_id)
            
            if bulk_task_ids:
                self.test_17_bulk_delete_tasks(bulk_task_ids)
            
            # Additional tests
            self.test_18_meeting_heatmap_api()
            self.test_19_task_page_render()
            self.test_20_priority_filter()
            
            # Generate report
            success = self.generate_report()
            
            return success
            
        finally:
            # Cleanup
            self.cleanup()


if __name__ == '__main__':
    tester = InteractiveTaskTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
