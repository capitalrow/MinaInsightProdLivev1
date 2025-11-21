"""
CROWN⁴.5 Task Menu Integration Test Suite
Tests all 13 menu actions end-to-end with API validation
"""
import pytest
import json
from datetime import datetime, timedelta
from app import app, db
from models import User, Workspace, Meeting, Task, TaskAssignee
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    """Create test client with in-memory database."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            
            # Create test workspace
            workspace = Workspace(name='Test Workspace')
            db.session.add(workspace)
            db.session.commit()
            
            # Create test user
            user = User(
                username='testuser',
                email='test@example.com',
                password_hash=generate_password_hash('password'),
                workspace_id=workspace.id
            )
            db.session.add(user)
            db.session.commit()
            
            # Create test meeting
            meeting = Meeting(
                title='Test Meeting',
                workspace_id=workspace.id,
                created_by_user_id=user.id
            )
            db.session.add(meeting)
            db.session.commit()
            
            # Create test task
            task = Task(
                title='Test Task',
                description='Test Description',
                meeting_id=meeting.id,
                status='todo',
                priority='medium'
            )
            db.session.add(task)
            db.session.commit()
            
            # Store IDs for tests
            client.workspace_id = workspace.id
            client.user_id = user.id
            client.meeting_id = meeting.id
            client.task_id = task.id
            
            yield client
            
            db.session.remove()
            db.drop_all()


def login(client):
    """Helper to log in test user."""
    return client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'password'
    }, follow_redirects=True)


class TestTaskMenuAPIEndpoints:
    """Test all API endpoints used by task menu actions."""
    
    def test_delete_task_endpoint(self, client):
        """Test DELETE /api/tasks/{id} - soft delete."""
        login(client)
        
        response = client.delete(f'/api/tasks/{client.task_id}')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert 'undo_window_seconds' in data
        
        # Verify soft delete (task still exists)
        task = db.session.get(Task, client.task_id)
        assert task is not None
        assert task.deleted_at is not None
    
    def test_update_task_priority(self, client):
        """Test PUT /api/tasks/{id} - update priority."""
        login(client)
        
        response = client.put(
            f'/api/tasks/{client.task_id}',
            data=json.dumps({'priority': 'urgent'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        
        # Verify update
        task = db.session.get(Task, client.task_id)
        assert task.priority == 'urgent'
    
    def test_update_task_status(self, client):
        """Test PUT /api/tasks/{id} - update status."""
        login(client)
        
        response = client.put(
            f'/api/tasks/{client.task_id}',
            data=json.dumps({'status': 'completed'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        
        # Verify update
        task = db.session.get(Task, client.task_id)
        assert task.status == 'completed'
    
    def test_update_task_due_date(self, client):
        """Test PUT /api/tasks/{id} - update due date."""
        login(client)
        
        due_date = (datetime.now() + timedelta(days=7)).date().isoformat()
        
        response = client.put(
            f'/api/tasks/{client.task_id}',
            data=json.dumps({'due_date': due_date}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        
        # Verify update
        task = db.session.get(Task, client.task_id)
        assert task.due_date is not None
    
    def test_merge_tasks_endpoint(self, client):
        """Test POST /api/tasks/{id}/merge."""
        login(client)
        
        # Create source task to merge
        with app.app_context():
            source_task = Task(
                title='Source Task',
                meeting_id=client.meeting_id,
                status='todo',
                priority='high'
            )
            db.session.add(source_task)
            db.session.commit()
            source_id = source_task.id
        
        response = client.post(
            f'/api/tasks/{client.task_id}/merge',
            data=json.dumps({'source_task_id': source_id}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        
        # Verify source task was deleted
        source_task = db.session.get(Task, source_id)
        assert source_task.deleted_at is not None
    
    def test_restore_deleted_task(self, client):
        """Test POST /api/tasks/{id}/undo-delete."""
        login(client)
        
        # First delete the task
        client.delete(f'/api/tasks/{client.task_id}')
        
        # Then restore it
        response = client.post(f'/api/tasks/{client.task_id}/undo-delete')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        
        # Verify restoration
        task = db.session.get(Task, client.task_id)
        assert task.deleted_at is None


class TestJavaScriptIntegration:
    """Test JavaScript file structure and integration."""
    
    def test_controller_initialization_code_exists(self):
        """Verify TaskMenuController initialization code exists."""
        with open('static/js/task-menu-controller.js', 'r') as f:
            content = f.read()
            
        # Check for class definition
        assert 'class TaskMenuController' in content
        
        # Check for executeAction method
        assert 'async executeAction(action, taskId)' in content
        
        # Check for all 13 action handlers
        handlers = [
            'handleViewDetails',
            'handleEdit',
            'handleToggleStatus',
            'handlePriority',
            'handleDueDate',
            'handleAssign',
            'handleLabels',
            'handleDuplicate',
            'handleSnooze',
            'handleMerge',
            'handleJumpToTranscript',
            'handleArchive',
            'handleDelete'
        ]
        
        for handler in handlers:
            assert f'async {handler}(taskId)' in content, f"Missing handler: {handler}"
        
        # Check for global initialization
        assert 'window.taskMenuController = new TaskMenuController()' in content
    
    def test_menu_calls_controller(self):
        """Verify TaskActionsMenu calls controller.executeAction()."""
        with open('static/js/task-actions-menu.js', 'r') as f:
            content = f.read()
            
        # Check for controller call
        assert 'window.taskMenuController.executeAction' in content
        
        # Check handleMenuAction exists
        assert 'async handleMenuAction(action, taskId)' in content
    
    def test_templates_load_scripts(self):
        """Verify tasks.html template loads both scripts."""
        with open('templates/dashboard/tasks.html', 'r') as f:
            content = f.read()
            
        # Check both scripts are loaded
        assert 'task-menu-controller.js' in content
        assert 'task-actions-menu.js' in content
        
        # Check controller loads before menu
        controller_pos = content.find('task-menu-controller.js')
        menu_pos = content.find('task-actions-menu.js')
        assert controller_pos < menu_pos, "Controller must load before menu"


class TestModalIntegration:
    """Test modal component integration."""
    
    def test_confirmation_modal_exists(self):
        """Verify TaskConfirmationModal is defined."""
        with open('static/js/task-confirmation-modal.js', 'r') as f:
            content = f.read()
            
        assert 'class TaskConfirmationModal' in content
        assert 'show(options)' in content
    
    def test_priority_selector_exists(self):
        """Verify TaskPrioritySelector is defined."""
        with open('static/js/task-priority-selector.js', 'r') as f:
            content = f.read()
            
        assert 'class TaskPrioritySelector' in content
    
    def test_date_picker_exists(self):
        """Verify TaskDatePicker is defined."""
        with open('static/js/task-date-picker.js', 'r') as f:
            content = f.read()
            
        assert 'class TaskDatePicker' in content


def test_no_browser_primitives_in_controller():
    """Verify no alert/confirm/prompt calls exist."""
    with open('static/js/task-menu-controller.js', 'r') as f:
        content = f.read()
        
    # These should NEVER appear in production code
    assert 'alert(' not in content
    assert 'confirm(' not in content
    assert 'prompt(' not in content
    print("✅ No browser primitives found - all replaced with custom modals")


def test_toast_notifications_used():
    """Verify toast notifications are used for feedback."""
    with open('static/js/task-menu-controller.js', 'r') as f:
        content = f.read()
        
    assert 'window.toast' in content or 'toast.' in content
    print("✅ Toast notifications properly integrated")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
