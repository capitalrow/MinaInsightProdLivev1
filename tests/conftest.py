"""
Root pytest configuration and fixtures for unit and integration tests.
"""
import pytest
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test configuration
os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SESSION_SECRET'] = 'test-secret-key-for-testing-only'

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
    
    user = User(
        username='testuser',
        email='test@example.com',
        password_hash=generate_password_hash('testpassword123')
    )
    db_session.add(user)
    db_session.commit()
    
    yield user
    
    db_session.delete(user)
    db_session.commit()

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
