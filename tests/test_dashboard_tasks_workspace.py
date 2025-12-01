"""Regression tests for /dashboard/tasks workspace filtering."""

from flask_login import login_user
from werkzeug.security import generate_password_hash


def test_workspace_only_task_is_listed(app, db_session):
    """Ensure tasks linked only to a workspace appear in the dashboard list."""
    from models import Task, User, Workspace

    with app.app_context():
        user = User(
            username="workspaceuser",
            email="workspace@example.com",
            password_hash=generate_password_hash("testpassword123"),
        )
        db_session.add(user)
        db_session.commit()

        workspace = Workspace(
            name="Test Workspace",
            slug="test-workspace",
            description="Workspace-only tasks",
            owner_id=user.id,
        )
        db_session.add(workspace)
        db_session.commit()

        user.workspace_id = workspace.id
        db_session.commit()

        task = Task(
            title="Workspace Only Task",
            description="Task without meeting or session",
            workspace_id=workspace.id,
            created_by_id=user.id,
        )
        db_session.add(task)
        db_session.commit()

        with app.test_request_context("/dashboard/tasks"):
            login_user(user)
            response = app.view_functions["dashboard.tasks"]()

        html = response if isinstance(response, str) else response.get_data(as_text=True)

        assert "Workspace Only Task" in html
