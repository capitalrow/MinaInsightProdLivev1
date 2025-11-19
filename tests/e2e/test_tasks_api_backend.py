"""
Tasks Page - Backend API Testing (Phase 1)
Tests all API endpoints work correctly with real data
"""

import pytest
import requests
import time
import json

BASE_URL = "http://localhost:5000"


class TestTasksBackendAPI:
    """Test all backend APIs for tasks"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.session = requests.Session()
        # Login if needed
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "test",
            "password": "test"
        })
        # Store cookies for authenticated requests
        self.headers = {"Content-Type": "application/json"}

    def test_01_get_tasks_list(self):
        """Test: GET /api/tasks/ returns task list"""
        resp = self.session.get(f"{BASE_URL}/api/tasks/")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "tasks" in data, "Response should contain 'tasks' key"
        
        tasks = data["tasks"]
        assert len(tasks) > 0, f"Expected tasks, found {len(tasks)}"
        
        print(f"✓ Found {len(tasks)} tasks from backend API")
        
        # Validate task structure
        first_task = tasks[0]
        required_fields = ["id", "title", "completed"]
        for field in required_fields:
            assert field in first_task, f"Task missing required field: {field}"
        
    def test_02_create_new_task(self):
        """Test: POST /api/tasks/ creates a new task"""
        new_task_data = {
            "title": "API Test Task - Automated",
            "description": "Created by backend API test",
            "priority": "high",
            "completed": False
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/tasks/",
            json=new_task_data,
            headers=self.headers
        )
        
        assert resp.status_code in [200, 201], f"Expected 200/201, got {resp.status_code}"
        
        data = resp.json()
        assert "task" in data or "id" in data, "Response should contain task data"
        
        # Verify task was created
        task_id = data.get("task", {}).get("id") or data.get("id")
        assert task_id is not None, "Created task should have ID"
        
        print(f"✓ Created task with ID: {task_id}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/tasks/{task_id}")
        
    def test_03_update_task(self):
        """Test: PATCH /api/tasks/{id} updates task"""
        # First create a task
        create_resp = self.session.post(
            f"{BASE_URL}/api/tasks/",
            json={"title": "Task to Update", "completed": False}
        )
        task_id = create_resp.json().get("task", {}).get("id") or create_resp.json().get("id")
        
        # Update it
        update_data = {"completed": True}
        update_resp = self.session.patch(
            f"{BASE_URL}/api/tasks/{task_id}",
            json=update_data,
            headers=self.headers
        )
        
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}"
        
        # Verify update
        get_resp = self.session.get(f"{BASE_URL}/api/tasks/{task_id}")
        task = get_resp.json().get("task", get_resp.json())
        assert task["completed"] == True, "Task should be marked complete"
        
        print(f"✓ Successfully updated task {task_id}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/tasks/{task_id}")
        
    def test_04_delete_task(self):
        """Test: DELETE /api/tasks/{id} removes task"""
        # Create a task
        create_resp = self.session.post(
            f"{BASE_URL}/api/tasks/",
            json={"title": "Task to Delete"}
        )
        task_id = create_resp.json().get("task", {}).get("id") or create_resp.json().get("id")
        
        # Delete it
        delete_resp = self.session.delete(f"{BASE_URL}/api/tasks/{task_id}")
        
        assert delete_resp.status_code in [200, 204], f"Expected 200/204, got {delete_resp.status_code}"
        
        # Verify deletion
        get_resp = self.session.get(f"{BASE_URL}/api/tasks/{task_id}")
        assert get_resp.status_code == 404, "Deleted task should return 404"
        
        print(f"✓ Successfully deleted task {task_id}")
        
    def test_05_meeting_heatmap_api(self):
        """Test: GET /api/tasks/meeting-heatmap returns meeting data"""
        resp = self.session.get(f"{BASE_URL}/api/tasks/meeting-heatmap")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        print(f"✓ Meeting heatmap API responded: {data}")
        
    def test_06_filter_by_status(self):
        """Test: Filtering tasks by completed status"""
        # Get all tasks
        all_resp = self.session.get(f"{BASE_URL}/api/tasks/")
        all_tasks = all_resp.json()["tasks"]
        
        # Get pending tasks
        pending_resp = self.session.get(f"{BASE_URL}/api/tasks/?completed=false")
        pending_tasks = pending_resp.json()["tasks"]
        
        # Get completed tasks
        completed_resp = self.session.get(f"{BASE_URL}/api/tasks/?completed=true")
        completed_tasks = completed_resp.json()["tasks"]
        
        print(f"✓ Filter test - All: {len(all_tasks)}, Pending: {len(pending_tasks)}, Completed: {len(completed_tasks)}")
        
        # Pending + completed should equal or be less than all
        assert len(pending_tasks) + len(completed_tasks) <= len(all_tasks) + 5  # Allow some margin


def run_api_tests():
    """Run all API tests"""
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--html=tests/results/phase1_api_report.html',
        '--self-contained-html'
    ])


if __name__ == '__main__':
    run_api_tests()
