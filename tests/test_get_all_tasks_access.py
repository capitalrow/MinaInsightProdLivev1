import os
import sys
import types
from uuid import uuid4

import pytest

from models import User, Workspace, Session, Summary

# Some optional dependencies are not installed in the lightweight test environment.
# Stub dotenv to prevent import errors when initializing the app during tests.
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda: None))

# Provide a dummy OpenAI API key so the OpenAI client initialization doesn't fail during tests.
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SOCKETIO_ASYNC_MODE", "threading")


class _FakeMemoryStore:
    def __init__(self):
        pass

    def add_memory(self, *_, **__):
        return True

    def search_memory(self, *_, **__):
        return []

    def latest_memories(self, *_args, **_kwargs):
        return []


# Stub the heavy memory store dependency so app creation doesn't attempt a real DB connection.
sys.modules.setdefault(
    "server.models.memory_store", types.SimpleNamespace(MemoryStore=_FakeMemoryStore)
)

# Stub optional heavy ML dependency used during websocket import.
_fake_cluster = types.SimpleNamespace(DBSCAN=object)
sys.modules.setdefault("sklearn", types.SimpleNamespace(cluster=_fake_cluster))
sys.modules.setdefault("sklearn.cluster", types.SimpleNamespace(DBSCAN=object))


@pytest.fixture(scope="session")
def app():
    """Lightweight Flask app fixture that only creates the tables needed for access tests."""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from app import create_app
    from models import db

    test_app = create_app()
    test_app.config.update(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        }
    )

    with test_app.app_context():
        db.metadata.create_all(
            bind=db.engine,
            tables=[
                db.metadata.tables["users"],
                db.metadata.tables["workspaces"],
                db.metadata.tables["segments"],
                db.metadata.tables["shared_links"],
                db.metadata.tables["meetings"],
                db.metadata.tables["sessions"],
                db.metadata.tables["summaries"],
            ],
        )

        yield test_app

        db.metadata.drop_all(
            bind=db.engine,
            tables=[
                db.metadata.tables["summaries"],
                db.metadata.tables["sessions"],
                db.metadata.tables["segments"],
                db.metadata.tables["shared_links"],
                db.metadata.tables["meetings"],
                db.metadata.tables["workspaces"],
                db.metadata.tables["users"],
            ],
        )


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app):
    from models import db

    with app.app_context():
        yield db.session
        db.session.rollback()
        db.session.remove()


@pytest.fixture
def user_workspaces(db_session):
    """Create two users with distinct workspaces and sessions with summaries."""
    # Workspace A setup
    test_password = "test-pass"

    user_a = User(
        username=f"alice-{uuid4()}",
        email=f"alice-{uuid4()}@example.com",
    )
    user_a.set_password(test_password)
    db_session.add(user_a)
    db_session.commit()

    workspace_a = Workspace(
        name="Workspace A",
        slug=f"workspace-a-{uuid4()}",
        owner_id=user_a.id,
    )
    db_session.add(workspace_a)
    db_session.commit()

    user_a.workspace_id = workspace_a.id
    db_session.commit()

    session_a = Session(
        title="Session A",
        external_id=str(uuid4()),
        workspace_id=workspace_a.id,
        user_id=user_a.id,
    )
    db_session.add(session_a)
    db_session.commit()

    summary_a = Summary(
        session_id=session_a.id,
        actions=[{"text": "Task A", "completed": False}],
    )
    db_session.add(summary_a)
    db_session.commit()

    # Workspace B setup
    user_b = User(
        username=f"bob-{uuid4()}",
        email=f"bob-{uuid4()}@example.com",
    )
    user_b.set_password(test_password)
    db_session.add(user_b)
    db_session.commit()

    workspace_b = Workspace(
        name="Workspace B",
        slug=f"workspace-b-{uuid4()}",
        owner_id=user_b.id,
    )
    db_session.add(workspace_b)
    db_session.commit()

    user_b.workspace_id = workspace_b.id
    db_session.commit()

    session_b = Session(
        title="Session B",
        external_id=str(uuid4()),
        workspace_id=workspace_b.id,
        user_id=user_b.id,
    )
    db_session.add(session_b)
    db_session.commit()

    summary_b = Summary(
        session_id=session_b.id,
        actions=[{"text": "Task B", "completed": False}],
    )
    db_session.add(summary_b)
    db_session.commit()

    yield {
        "user_a": user_a,
        "user_b": user_b,
        "session_a": session_a,
        "session_b": session_b,
        "password": test_password,
    }

    # Leave data in place for the duration of the session-scoped database; it will be
    # cleaned up when the in-memory database is torn down after the test session.


def authenticate(client, user, password):
    """Authenticate via the login endpoint to mirror real sessions."""
    response = client.post(
        "/auth/login",
        data={"email_or_username": user.username, "password": password},
        follow_redirects=False,
    )

    if response.status_code not in (200, 302):
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True


def test_get_all_tasks_requires_auth(client):
    response = client.get("/api/tasks")
    assert response.status_code == 401
    body = response.get_json()
    assert body["success"] is False
    assert body["error"] == "Authentication required"


def test_get_all_tasks_scoped_to_workspace(client, user_workspaces):
    authenticate(client, user_workspaces["user_a"], user_workspaces["password"])

    response = client.get("/api/tasks")
    assert response.status_code == 200

    tasks = response.get_json()["tasks"]
    assert all(task["text"] == "Task A" for task in tasks)
    assert len(tasks) == 1


def test_cross_workspace_access_is_rejected(client, user_workspaces):
    authenticate(client, user_workspaces["user_a"], user_workspaces["password"])

    response = client.get(f"/api/tasks?session_id={user_workspaces['session_b'].id}")
    assert response.status_code == 403
    body = response.get_json()
    assert body["success"] is False
    assert "Not authorized" in body["error"]
