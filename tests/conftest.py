"""
Root pytest configuration and fixtures for unit and integration tests.
"""
import pytest
import os
import sys
from pathlib import Path
import types

# Provide a lightweight stub for python-dotenv to avoid optional dependency failures during tests
if 'dotenv' not in sys.modules:
    dotenv_stub = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)
    sys.modules['dotenv'] = dotenv_stub

# Provide a lightweight SocketIO stub to avoid optional async dependencies
if 'flask_socketio' not in sys.modules:
    flask_socketio_stub = types.ModuleType('flask_socketio')

    def _noop(*args, **kwargs):
        return None

    class SocketIO:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

        def init_app(self, app):
            return None

        def on(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def event(self, func):
            return func

        def emit(self, *args, **kwargs):
            return None

        def run(self, *args, **kwargs):
            return None

        def test_client(self, *args, **kwargs):
            return None

    flask_socketio_stub.SocketIO = SocketIO
    flask_socketio_stub.emit = _noop
    flask_socketio_stub.join_room = _noop
    flask_socketio_stub.leave_room = _noop
    flask_socketio_stub.disconnect = _noop
    flask_socketio_stub.SocketIOTestClient = object
    sys.modules['flask_socketio'] = flask_socketio_stub

# Stub memory store to avoid external database and OpenAI dependencies during tests
if 'server.models.memory_store' not in sys.modules:
    memory_store_stub = types.ModuleType('server.models.memory_store')

    class MemoryStore:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

        def add_memory(self, *args, **kwargs):
            return True

        def search_memory(self, *args, **kwargs):
            return []

        def latest_memories(self, *args, **kwargs):
            return []

    memory_store_stub.MemoryStore = MemoryStore
    sys.modules['server.models.memory_store'] = memory_store_stub

# Stub sklearn dependency used by optional diarization service
if 'sklearn' not in sys.modules:
    sklearn_stub = types.ModuleType('sklearn')
    sklearn_cluster_stub = types.ModuleType('sklearn.cluster')

    class DBSCAN:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

    sklearn_cluster_stub.DBSCAN = DBSCAN
    sklearn_stub.cluster = sklearn_cluster_stub

    sys.modules['sklearn'] = sklearn_stub
    sys.modules['sklearn.cluster'] = sklearn_cluster_stub

# Stub feature flag models that rely on PostgreSQL-specific types
if 'models.core_models' not in sys.modules:
    core_models_stub = types.ModuleType('models.core_models')

    class _Placeholder:  # type: ignore
        pass

    core_models_stub.FeatureFlag = _Placeholder
    core_models_stub.FlagAuditLog = _Placeholder
    core_models_stub.Customer = _Placeholder
    core_models_stub.Subscription = _Placeholder

    sys.modules['models.core_models'] = core_models_stub

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test configuration
os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SESSION_SECRET'] = 'test-secret-key-for-testing-only'
os.environ.setdefault('OPENAI_API_KEY', 'test-api-key')

@pytest.fixture(scope='session')
def app():
    """Create and configure a test Flask application."""
    # Set test DATABASE_URL before creating app
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    from app import create_app
    from models import db
    
    # create_app() will initialize db automatically when DATABASE_URL is set
    test_app = create_app()
    test_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
    })
    
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()

@pytest.fixture(scope='function')
def runner(app):
    """Create a CLI test runner."""
    return app.test_cli_runner()

@pytest.fixture(scope='function')
def db_session(app):
    """Create a database session for testing."""
    from models import db
    
    with app.app_context():
        yield db.session
        db.session.rollback()
        db.session.remove()

@pytest.fixture(scope='function')
def authenticated_client(client, test_user):
    """Create an authenticated test client."""
    with client:
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
        yield client

@pytest.fixture(scope='function')
def test_user(db_session):
    """Create a test user."""
    from models import User
    from werkzeug.security import generate_password_hash
    
    # Use unique username/email to avoid conflicts with other tests
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    
    user = User(
        username=f'testuser_{unique_id}',
        email=f'test_{unique_id}@example.com',
        password_hash=generate_password_hash('testpassword123')
    )
    db_session.add(user)
    db_session.commit()
    
    yield user
    
    # Cleanup - use try/except to handle cases where user may already be deleted
    try:
        db_session.rollback()  # Clear any pending state
        # Re-query the user to ensure it's attached to current session
        from models import User
        existing_user = db_session.query(User).filter_by(id=user.id).first()
        if existing_user:
            db_session.delete(existing_user)
            db_session.commit()
    except Exception:
        db_session.rollback()

@pytest.fixture(scope='function')
def test_workspace(db_session, test_user):
    """Create a test workspace."""
    from models import Workspace
    import uuid
    
    unique_id = str(uuid.uuid4())[:8]
    name = f'Test Workspace {unique_id}'
    slug = Workspace.generate_slug(name) + f'-{unique_id}'
    
    workspace = Workspace(
        name=name,
        slug=slug,
        owner_id=test_user.id
    )
    db_session.add(workspace)
    db_session.commit()
    
    yield workspace
    
    try:
        db_session.rollback()
        from models import Workspace
        existing = db_session.query(Workspace).filter_by(id=workspace.id).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()
    except Exception:
        db_session.rollback()

@pytest.fixture(scope='function')
def mock_openai_response(mocker):
    """Mock OpenAI API response."""
    mock_response = {
        'choices': [{
            'message': {
                'content': 'This is a test transcription'
            }
        }]
    }
    return mocker.patch('openai.ChatCompletion.create', return_value=mock_response)

@pytest.fixture(scope='function')
def sample_audio_data():
    """Provide sample audio data for testing."""
    import base64
    # 1 second of silence as base64 encoded PCM16
    silence_base64 = 'UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA='
    return base64.b64decode(silence_base64)
