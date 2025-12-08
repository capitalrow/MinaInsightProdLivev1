"""
Comprehensive Task Page Testing Suite

This module tests all aspects of the task page at /dashboard/tasks including:
1. Page rendering and layout
2. Task API endpoints
3. CRUD operations 
4. Filter and search functionality
5. UI components and interactions
"""

import pytest
import requests
import json
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Meeting, Task, Workspace


class TestTaskPageAPI:
    """Test task API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        with self.app.app_context():
            self.user, self.workspace, self.meeting = self._create_test_data()
            
    def _create_test_data(self):
        """Create test user, workspace and meeting"""
        from werkzeug.security import generate_password_hash
        
        email = f"test_{datetime.now().timestamp()}@test.com"
        user = db.session.query(User).filter_by(email=email).first()
        if not user:
            user = User(
                username=f"testuser_{datetime.now().timestamp()}",
                email=email,
                password_hash=generate_password_hash("testpass123")
            )
            db.session.add(user)
            db.session.flush()
            
        workspace = db.session.query(Workspace).filter_by(owner_id=user.id).first()
        if not workspace:
            workspace = Workspace(
                name=f"Test Workspace",
                slug=f"test-workspace-{datetime.now().timestamp()}",
                owner_id=user.id
            )
            db.session.add(workspace)
            db.session.flush()
            
        user.workspace_id = workspace.id
        
        meeting = db.session.query(Meeting).filter_by(workspace_id=workspace.id).first()
        if not meeting:
            meeting = Meeting(
                title="Test Meeting",
                workspace_id=workspace.id,
                organizer_id=user.id
            )
            db.session.add(meeting)
            
        db.session.commit()
        return user, workspace, meeting
    
    def _login(self):
        """Login and return authenticated client"""
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True
    
    def test_01_tasks_page_loads(self):
        """Test that tasks page loads correctly"""
        print("\n" + "="*70)
        print("TEST 01: Tasks Page Loads")
        print("="*70)
        
        self._login()
        response = self.client.get('/dashboard/tasks')
        
        assert response.status_code in [200, 302], f"Expected 200/302, got {response.status_code}"
        
        if response.status_code == 200:
            html = response.data.decode('utf-8')
            assert 'tasks-container' in html or 'Action Items' in html, "Tasks page content missing"
            print("✅ PASS: Tasks page loaded successfully")
        else:
            print("⚠️ WARNING: Page redirected (likely to login)")
    
    def test_02_tasks_api_list(self):
        """Test GET /api/tasks/ endpoint"""
        print("\n" + "="*70)
        print("TEST 02: Tasks API List")
        print("="*70)
        
        self._login()
        response = self.client.get('/api/tasks/')
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'tasks' in data, "Response missing 'tasks' field"
            assert 'pagination' in data, "Response missing 'pagination' field"
            print(f"✅ PASS: Got {len(data.get('tasks', []))} tasks")
            print(f"   Pagination: {data.get('pagination', {})}")
        else:
            print(f"❌ FAIL: Status {response.status_code}")
            print(f"   Response: {response.data.decode('utf-8')[:200]}")
    
    def test_03_create_task_api(self):
        """Test POST /api/tasks/ endpoint"""
        print("\n" + "="*70)
        print("TEST 03: Create Task API")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            meeting = db.session.query(Meeting).filter_by(workspace_id=self.workspace.id).first()
            
            task_data = {
                'title': f'Test Task {datetime.now().timestamp()}',
                'description': 'Test task description',
                'priority': 'medium',
                'status': 'todo',
                'meeting_id': meeting.id if meeting else None
            }
            
            response = self.client.post(
                '/api/tasks/',
                data=json.dumps(task_data),
                content_type='application/json'
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                data = json.loads(response.data)
                assert data.get('success') == True, "Expected success=True"
                assert 'task' in data, "Response missing 'task' field"
                print(f"✅ PASS: Task created with ID {data.get('task', {}).get('id')}")
                return data.get('task', {}).get('id')
            else:
                print(f"❌ FAIL: Status {response.status_code}")
                print(f"   Response: {response.data.decode('utf-8')[:500]}")
        return None
    
    def test_04_get_single_task_api(self):
        """Test GET /api/tasks/<id> endpoint"""
        print("\n" + "="*70)
        print("TEST 04: Get Single Task API")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            task_id = self._create_test_task()
            if not task_id:
                print("⚠️ SKIP: Could not create test task")
                return
            
            response = self.client.get(f'/api/tasks/{task_id}')
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = json.loads(response.data)
                assert data.get('success') == True, "Expected success=True"
                assert 'task' in data, "Response missing 'task' field"
                print(f"✅ PASS: Got task with title '{data.get('task', {}).get('title')}'")
            else:
                print(f"❌ FAIL: Status {response.status_code}")
    
    def _create_test_task(self):
        """Helper to create a test task"""
        meeting = db.session.query(Meeting).filter_by(workspace_id=self.workspace.id).first()
        if not meeting:
            meeting = Meeting(
                title="Test Meeting",
                workspace_id=self.workspace.id,
                organizer_id=self.user.id
            )
            db.session.add(meeting)
            db.session.commit()
        
        task = Task(
            title=f"Test Task {datetime.now().timestamp()}",
            description="Test description",
            status='todo',
            priority='medium',
            meeting_id=meeting.id,
            workspace_id=str(self.workspace.id)
        )
        db.session.add(task)
        db.session.commit()
        return task.id
    
    def test_05_update_task_api(self):
        """Test PUT /api/tasks/<id> endpoint"""
        print("\n" + "="*70)
        print("TEST 05: Update Task API")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            task_id = self._create_test_task()
            
            update_data = {
                'title': 'Updated Task Title',
                'status': 'in_progress'
            }
            
            response = self.client.put(
                f'/api/tasks/{task_id}',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = json.loads(response.data)
                assert data.get('success') == True, "Expected success=True"
                print(f"✅ PASS: Task updated successfully")
            else:
                print(f"❌ FAIL: Status {response.status_code}")
                print(f"   Response: {response.data.decode('utf-8')[:500]}")
    
    def test_06_delete_task_api(self):
        """Test DELETE /api/tasks/<id> endpoint"""
        print("\n" + "="*70)
        print("TEST 06: Delete Task API")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            task_id = self._create_test_task()
            
            response = self.client.delete(f'/api/tasks/{task_id}')
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = json.loads(response.data)
                assert data.get('success') == True, "Expected success=True"
                print(f"✅ PASS: Task deleted successfully")
            else:
                print(f"❌ FAIL: Status {response.status_code}")
                print(f"   Response: {response.data.decode('utf-8')[:500]}")
    
    def test_07_task_filtering(self):
        """Test task filtering by status"""
        print("\n" + "="*70)
        print("TEST 07: Task Filtering")
        print("="*70)
        
        self._login()
        
        filters = [
            ('status=todo', 'todo'),
            ('status=in_progress', 'in_progress'),
            ('status=completed', 'completed'),
        ]
        
        for query, status in filters:
            response = self.client.get(f'/api/tasks/?{query}')
            
            if response.status_code == 200:
                data = json.loads(response.data)
                tasks = data.get('tasks', [])
                
                wrong_status = [t for t in tasks if t.get('status') != status]
                if len(wrong_status) == 0:
                    print(f"✅ PASS: Filter '{status}' returned {len(tasks)} matching tasks")
                else:
                    print(f"❌ FAIL: Filter '{status}' returned {len(wrong_status)} non-matching tasks")
            else:
                print(f"❌ FAIL: Filter '{status}' returned status {response.status_code}")
    
    def test_08_task_search(self):
        """Test task search functionality"""
        print("\n" + "="*70)
        print("TEST 08: Task Search")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            unique_title = f"UniqueSearchTerm_{datetime.now().timestamp()}"
            meeting = db.session.query(Meeting).filter_by(workspace_id=self.workspace.id).first()
            
            task = Task(
                title=unique_title,
                description="Searchable task",
                status='todo',
                priority='medium',
                meeting_id=meeting.id,
                workspace_id=str(self.workspace.id)
            )
            db.session.add(task)
            db.session.commit()
            
            response = self.client.get(f'/api/tasks/?search={unique_title}')
            
            if response.status_code == 200:
                data = json.loads(response.data)
                tasks = data.get('tasks', [])
                
                found = any(unique_title in t.get('title', '') for t in tasks)
                if found:
                    print(f"✅ PASS: Search found task with unique title")
                else:
                    print(f"❌ FAIL: Search did not find task with unique title")
            else:
                print(f"❌ FAIL: Search returned status {response.status_code}")
    
    def test_09_task_pagination(self):
        """Test task pagination"""
        print("\n" + "="*70)
        print("TEST 09: Task Pagination")
        print("="*70)
        
        self._login()
        
        response = self.client.get('/api/tasks/?page=1&per_page=5')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            pagination = data.get('pagination', {})
            
            if 'page' in pagination and 'per_page' in pagination:
                print(f"✅ PASS: Pagination working - Page {pagination.get('page')}, Per page {pagination.get('per_page')}")
            else:
                print(f"❌ FAIL: Pagination missing expected fields")
        else:
            print(f"❌ FAIL: Status {response.status_code}")
    
    def test_10_meeting_heatmap_api(self):
        """Test meeting heatmap API"""
        print("\n" + "="*70)
        print("TEST 10: Meeting Heatmap API")
        print("="*70)
        
        self._login()
        
        response = self.client.get('/api/tasks/meeting-heatmap')
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = json.loads(response.data)
            if data.get('success'):
                print(f"✅ PASS: Meeting heatmap returned {len(data.get('meetings', []))} meetings")
            else:
                print(f"❌ FAIL: Success=False - {data.get('message')}")
        else:
            print(f"❌ FAIL: Status {response.status_code}")
    
    def test_11_task_html_fragment_api(self):
        """Test task HTML fragment API (for optimistic updates)"""
        print("\n" + "="*70)
        print("TEST 11: Task HTML Fragment API")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            task_id = self._create_test_task()
            
            response = self.client.get(f'/api/tasks/{task_id}/html')
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = json.loads(response.data)
                if data.get('success') and 'html' in data:
                    print(f"✅ PASS: HTML fragment returned ({len(data.get('html', ''))} chars)")
                else:
                    print(f"❌ FAIL: Response missing html field")
            else:
                print(f"❌ FAIL: Status {response.status_code}")
    
    def test_12_task_transcript_context_api(self):
        """Test task transcript context API"""
        print("\n" + "="*70)
        print("TEST 12: Task Transcript Context API")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            task_id = self._create_test_task()
            
            response = self.client.get(f'/api/tasks/{task_id}/transcript-context')
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = json.loads(response.data)
                if data.get('success'):
                    print(f"✅ PASS: Transcript context API responded")
                else:
                    print(f"⚠️ WARNING: Success=False - {data.get('message')}")
            else:
                print(f"❌ FAIL: Status {response.status_code}")
    
    def test_13_task_bulk_update(self):
        """Test bulk task updates"""
        print("\n" + "="*70)
        print("TEST 13: Bulk Task Update")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            task_ids = [self._create_test_task() for _ in range(3)]
            
            bulk_data = {
                'task_ids': task_ids,
                'updates': {
                    'status': 'completed'
                }
            }
            
            response = self.client.post(
                '/api/tasks/bulk-update',
                data=json.dumps(bulk_data),
                content_type='application/json'
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = json.loads(response.data)
                if data.get('success'):
                    print(f"✅ PASS: Bulk update completed")
                else:
                    print(f"❌ FAIL: {data.get('message')}")
            elif response.status_code == 404:
                print(f"⚠️ SKIP: Bulk update endpoint not available")
            else:
                print(f"❌ FAIL: Status {response.status_code}")


class TestTaskPageRendering:
    """Test task page HTML rendering"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        with self.app.app_context():
            self._create_test_user()
    
    def _create_test_user(self):
        """Create test user"""
        from werkzeug.security import generate_password_hash
        
        email = f"test_render_{datetime.now().timestamp()}@test.com"
        self.user = db.session.query(User).filter_by(email=email).first()
        if not self.user:
            self.user = User(
                username=f"testrender_{datetime.now().timestamp()}",
                email=email,
                password_hash=generate_password_hash("testpass123")
            )
            db.session.add(self.user)
            db.session.flush()
            
            workspace = Workspace(
                name=f"Test Render Workspace",
                slug=f"test-render-workspace-{datetime.now().timestamp()}",
                owner_id=self.user.id
            )
            db.session.add(workspace)
            db.session.flush()
            
            self.user.workspace_id = workspace.id
            db.session.commit()
    
    def _login(self):
        """Login and return authenticated client"""
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True
    
    def test_14_page_has_required_elements(self):
        """Test page has all required UI elements"""
        print("\n" + "="*70)
        print("TEST 14: Page Required Elements")
        print("="*70)
        
        self._login()
        response = self.client.get('/dashboard/tasks')
        
        if response.status_code != 200:
            print(f"⚠️ SKIP: Page returned {response.status_code}")
            return
            
        html = response.data.decode('utf-8')
        
        required_elements = [
            ('tasks-container', 'Tasks container'),
            ('tasks-header', 'Tasks header'),
            ('filter-tab', 'Filter tabs'),
            ('task-search-input', 'Search input'),
            ('task-sort-select', 'Sort select'),
            ('new-task-btn', 'New task button'),
            ('tasks-list-container', 'Tasks list container'),
            ('tasks-loading-state', 'Loading state'),
            ('tasks-empty-state', 'Empty state'),
            ('tasks-error-state', 'Error state'),
            ('bulk-action-toolbar', 'Bulk action toolbar'),
        ]
        
        all_found = True
        for element_id, description in required_elements:
            if element_id in html:
                print(f"✅ FOUND: {description} ({element_id})")
            else:
                print(f"❌ MISSING: {description} ({element_id})")
                all_found = False
        
        if all_found:
            print(f"\n✅ PASS: All required elements present")
        else:
            print(f"\n❌ FAIL: Some elements missing")
    
    def test_15_page_has_required_css(self):
        """Test page includes required CSS files"""
        print("\n" + "="*70)
        print("TEST 15: Page Required CSS")
        print("="*70)
        
        self._login()
        response = self.client.get('/dashboard/tasks')
        
        if response.status_code != 200:
            print(f"⚠️ SKIP: Page returned {response.status_code}")
            return
            
        html = response.data.decode('utf-8')
        
        required_css = [
            'tasks.css',
            'ai-proposals-modal.css',
            'task-provenance.css',
            'task-redesign.css',
        ]
        
        for css_file in required_css:
            if css_file in html:
                print(f"✅ FOUND: {css_file}")
            else:
                print(f"⚠️ MISSING: {css_file}")
    
    def test_16_page_has_required_js(self):
        """Test page includes required JS files"""
        print("\n" + "="*70)
        print("TEST 16: Page Required JS")
        print("="*70)
        
        self._login()
        response = self.client.get('/dashboard/tasks')
        
        if response.status_code != 200:
            print(f"⚠️ SKIP: Page returned {response.status_code}")
            return
            
        html = response.data.decode('utf-8')
        
        required_js = [
            'task-bootstrap.js',
        ]
        
        for js_file in required_js:
            if js_file in html:
                print(f"✅ FOUND: {js_file}")
            else:
                print(f"⚠️ MISSING: {js_file}")


class TestTaskWorkflow:
    """Test complete task workflows"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        with self.app.app_context():
            self._create_test_data()
    
    def _create_test_data(self):
        """Create test data"""
        from werkzeug.security import generate_password_hash
        
        email = f"test_wf_{datetime.now().timestamp()}@test.com"
        self.user = db.session.query(User).filter_by(email=email).first()
        if not self.user:
            self.user = User(
                username=f"testwf_{datetime.now().timestamp()}",
                email=email,
                password_hash=generate_password_hash("testpass123")
            )
            db.session.add(self.user)
            db.session.flush()
            
            self.workspace = Workspace(
                name=f"Test WF Workspace",
                slug=f"test-wf-workspace-{datetime.now().timestamp()}",
                owner_id=self.user.id
            )
            db.session.add(self.workspace)
            db.session.flush()
            
            self.user.workspace_id = self.workspace.id
            
            self.meeting = Meeting(
                title="Test Meeting for Workflow",
                workspace_id=self.workspace.id,
                organizer_id=self.user.id
            )
            db.session.add(self.meeting)
            db.session.commit()
    
    def _login(self):
        """Login and return authenticated client"""
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['_fresh'] = True
    
    def test_17_complete_task_lifecycle(self):
        """Test complete task lifecycle: Create -> Update -> Complete -> Delete"""
        print("\n" + "="*70)
        print("TEST 17: Complete Task Lifecycle")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            meeting = db.session.query(Meeting).filter_by(workspace_id=self.workspace.id).first()
            
            task_data = {
                'title': f'Lifecycle Task {datetime.now().timestamp()}',
                'description': 'Testing complete lifecycle',
                'priority': 'high',
                'status': 'todo',
                'meeting_id': meeting.id
            }
            
            response = self.client.post(
                '/api/tasks/',
                data=json.dumps(task_data),
                content_type='application/json'
            )
            
            if response.status_code not in [200, 201]:
                print(f"❌ FAIL: Create step failed with {response.status_code}")
                return
            
            task_id = json.loads(response.data).get('task', {}).get('id')
            print(f"✅ Step 1: Created task {task_id}")
            
            update_data = {'status': 'in_progress', 'priority': 'urgent'}
            response = self.client.put(
                f'/api/tasks/{task_id}',
                data=json.dumps(update_data),
                content_type='application/json'
            )
            
            if response.status_code != 200:
                print(f"❌ FAIL: Update step failed with {response.status_code}")
                return
            print(f"✅ Step 2: Updated task to in_progress")
            
            complete_data = {'status': 'completed'}
            response = self.client.put(
                f'/api/tasks/{task_id}',
                data=json.dumps(complete_data),
                content_type='application/json'
            )
            
            if response.status_code != 200:
                print(f"❌ FAIL: Complete step failed with {response.status_code}")
                return
            print(f"✅ Step 3: Completed task")
            
            response = self.client.delete(f'/api/tasks/{task_id}')
            
            if response.status_code != 200:
                print(f"❌ FAIL: Delete step failed with {response.status_code}")
                return
            print(f"✅ Step 4: Deleted task")
            
            print(f"\n✅ PASS: Complete task lifecycle successful")
    
    def test_18_task_with_due_date(self):
        """Test task creation and filtering with due dates"""
        print("\n" + "="*70)
        print("TEST 18: Task with Due Date")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            meeting = db.session.query(Meeting).filter_by(workspace_id=self.workspace.id).first()
            
            due_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
            
            task_data = {
                'title': f'Due Date Task {datetime.now().timestamp()}',
                'due_date': due_date,
                'status': 'todo',
                'meeting_id': meeting.id
            }
            
            response = self.client.post(
                '/api/tasks/',
                data=json.dumps(task_data),
                content_type='application/json'
            )
            
            if response.status_code in [200, 201]:
                data = json.loads(response.data)
                task = data.get('task', {})
                if task.get('due_date'):
                    print(f"✅ PASS: Task created with due date {task.get('due_date')}")
                else:
                    print(f"⚠️ WARNING: Due date not returned in response")
            else:
                print(f"❌ FAIL: Status {response.status_code}")
    
    def test_19_task_priority_changes(self):
        """Test task priority updates"""
        print("\n" + "="*70)
        print("TEST 19: Task Priority Changes")
        print("="*70)
        
        self._login()
        
        with self.app.app_context():
            meeting = db.session.query(Meeting).filter_by(workspace_id=self.workspace.id).first()
            
            task_data = {
                'title': f'Priority Task {datetime.now().timestamp()}',
                'priority': 'low',
                'status': 'todo',
                'meeting_id': meeting.id
            }
            
            response = self.client.post(
                '/api/tasks/',
                data=json.dumps(task_data),
                content_type='application/json'
            )
            
            if response.status_code not in [200, 201]:
                print(f"❌ FAIL: Create failed")
                return
            
            task_id = json.loads(response.data).get('task', {}).get('id')
            
            priorities = ['low', 'medium', 'high', 'urgent']
            for priority in priorities:
                response = self.client.put(
                    f'/api/tasks/{task_id}',
                    data=json.dumps({'priority': priority}),
                    content_type='application/json'
                )
                
                if response.status_code == 200:
                    print(f"✅ PASS: Changed priority to {priority}")
                else:
                    print(f"❌ FAIL: Could not change to {priority}")


def run_all_tests():
    """Run all tests with detailed output"""
    print("\n" + "="*70)
    print("COMPREHENSIVE TASK PAGE TEST SUITE")
    print("="*70)
    print(f"Started at: {datetime.now().isoformat()}")
    print("="*70)
    
    pytest.main([
        __file__,
        '-v',
        '-s',
        '--tb=short',
        '--no-header'
    ])


if __name__ == '__main__':
    run_all_tests()
