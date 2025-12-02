"""
Test Session CRUD Operations (M2)
Tests for session creation, retrieval, listing, and finalization.
"""

import pytest
from datetime import datetime
from app_refactored import create_app, db
from models.base import Base
from services.session_service import SessionService


@pytest.fixture
def app():
    """Create test Flask app with in-memory database."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        Base.metadata.create_all(bind=db.engine)
        yield app
        db.session.remove()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestSessionService:
    """Test session service CRUD operations."""
    
    def test_create_session(self, app):
        """Test session creation."""
        with app.app_context():
            # Create session with defaults
            session_id = SessionService.create_session()
            assert session_id is not None
            
            # Verify session exists
            session = SessionService.get_session_by_id(session_id)
            assert session is not None
            assert session.title == "Untitled Meeting"
            assert session.status == "active"
            assert session.external_id is not None
            assert len(session.external_id) > 0
    
    def test_create_session_with_params(self, app):
        """Test session creation with custom parameters."""
        with app.app_context():
            # Create session with custom params
            session_id = SessionService.create_session(
                title="Test Meeting",
                external_id="test-external-123",
                locale="en-US",
                device_info={"browser": "Chrome", "os": "Windows"}
            )
            
            # Verify session data
            session = SessionService.get_session_by_id(session_id)
            assert session.title == "Test Meeting"
            assert session.external_id == "test-external-123"
            assert session.locale == "en-US"
            assert session.device_info == {"browser": "Chrome", "os": "Windows"}
    
    def test_get_session_by_external(self, app):
        """Test session retrieval by external ID."""
        with app.app_context():
            # Create session
            session_id = SessionService.create_session(external_id="ext-test-456")
            
            # Retrieve by external ID
            session = SessionService.get_session_by_external("ext-test-456")
            assert session is not None
            assert session.id == session_id
            assert session.external_id == "ext-test-456"
    
    def test_complete_session(self, app):
        """Test session completion."""
        with app.app_context():
            # Create session
            session_id = SessionService.create_session()
            
            # Complete session
            result = SessionService.complete_session(session_id)
            assert result is True
            
            # Verify status changed
            session = SessionService.get_session_by_id(session_id)
            assert session.status == "completed"
            assert session.completed_at is not None
    
    def test_list_sessions(self, app):
        """Test session listing."""
        with app.app_context():
            # Create multiple sessions
            session1_id = SessionService.create_session(title="First Meeting")
            session2_id = SessionService.create_session(title="Second Meeting")
            SessionService.complete_session(session2_id)
            
            # List all sessions
            all_sessions = SessionService.list_sessions()
            assert len(all_sessions) >= 2
            
            # List active sessions only
            active_sessions = SessionService.list_sessions(status="active")
            assert len(active_sessions) >= 1
            
            # List completed sessions only
            completed_sessions = SessionService.list_sessions(status="completed")
            assert len(completed_sessions) >= 1
    
    def test_search_sessions(self, app):
        """Test session search functionality."""
        with app.app_context():
            # Create sessions with different titles
            SessionService.create_session(title="Project Alpha Meeting")
            SessionService.create_session(title="Project Beta Review")
            SessionService.create_session(title="Team Standup")
            
            # Search for "Project" sessions
            project_sessions = SessionService.list_sessions(q="Project")
            assert len(project_sessions) >= 2
            
            # Search for specific title
            alpha_sessions = SessionService.list_sessions(q="Alpha")
            assert len(alpha_sessions) >= 1
    
    def test_create_segment(self, app):
        """Test segment creation."""
        with app.app_context():
            # Create session
            session_id = SessionService.create_session()
            
            # Create interim segment
            segment_id = SessionService.create_segment(
                session_id=session_id,
                kind="interim",
                text="Hello world interim",
                avg_confidence=0.8,
                start_ms=1000,
                end_ms=3000
            )
            assert segment_id is not None
            
            # Create final segment
            final_segment_id = SessionService.create_segment(
                session_id=session_id,
                kind="final",
                text="Hello world final",
                avg_confidence=0.95,
                start_ms=1000,
                end_ms=3000
            )
            assert final_segment_id is not None
    
    def test_get_session_detail(self, app):
        """Test session detail retrieval with segments."""
        with app.app_context():
            # Create session with segments
            session_id = SessionService.create_session(title="Detail Test Meeting")
            
            # Add segments
            SessionService.create_segment(
                session_id=session_id,
                kind="interim",
                text="First interim segment",
                avg_confidence=0.7
            )
            SessionService.create_segment(
                session_id=session_id,
                kind="final",
                text="First final segment", 
                avg_confidence=0.9
            )
            
            # Get session detail
            detail = SessionService.get_session_detail(session_id)
            assert detail is not None
            assert detail['session']['title'] == "Detail Test Meeting"
            assert len(detail['segments']) == 2
            
            # Verify segments data
            segments = detail['segments']
            assert any(s['kind'] == 'interim' for s in segments)
            assert any(s['kind'] == 'final' for s in segments)
    
    def test_session_stats(self, app):
        """Test session statistics."""
        with app.app_context():
            # Create initial sessions
            session1_id = SessionService.create_session()
            session2_id = SessionService.create_session()
            SessionService.complete_session(session2_id)
            
            # Add segments
            SessionService.create_segment(session1_id, "interim", "Test segment 1")
            SessionService.create_segment(session2_id, "final", "Test segment 2")
            
            # Get stats
            stats = SessionService.get_session_stats()
            assert stats['total_sessions'] >= 2
            assert stats['active_sessions'] >= 1
            assert stats['completed_sessions'] >= 1
            assert stats['total_segments'] >= 2


class TestSessionRoutes:
    """Test session REST API routes."""
    
    def test_list_sessions_json(self, client, app):
        """Test sessions list API endpoint."""
        with app.app_context():
            # Create test session
            SessionService.create_session(title="API Test Meeting")
            
            # Test JSON response
            response = client.get('/sessions/?format=json')
            assert response.status_code == 200
            data = response.get_json()
            assert 'sessions' in data
            assert len(data['sessions']) >= 1
    
    def test_create_session_api(self, client, app):
        """Test session creation API endpoint."""
        with app.app_context():
            # Create session via API
            response = client.post('/sessions/', 
                                 json={'title': 'API Created Meeting'})
            assert response.status_code == 201
            data = response.get_json()
            assert data['title'] == 'API Created Meeting'
            assert 'id' in data
            assert 'external_id' in data
    
    def test_get_session_detail_json(self, client, app):
        """Test session detail API endpoint."""
        with app.app_context():
            # Create session with segment
            session_id = SessionService.create_session(title="Detail API Test")
            SessionService.create_segment(session_id, "final", "Test transcript")
            
            # Get session detail
            response = client.get(f'/sessions/{session_id}?format=json')
            assert response.status_code == 200
            data = response.get_json()
            assert data['session']['title'] == "Detail API Test"
            assert len(data['segments']) >= 1
    
    def test_finalize_session_api(self, client, app):
        """Test session finalization API endpoint."""
        with app.app_context():
            # Create session
            session_id = SessionService.create_session()
            
            # Finalize via API
            response = client.post(f'/sessions/{session_id}/finalize')
            assert response.status_code == 200
            data = response.get_json()
            assert 'completed' in data['message']
            
            # Verify session status
            session = SessionService.get_session_by_id(session_id)
            assert session.status == "completed"
    
    def test_session_stats_api(self, client, app):
        """Test session statistics API endpoint."""
        with app.app_context():
            # Get stats via API
            response = client.get('/sessions/stats')
            assert response.status_code == 200
            data = response.get_json()
            assert 'total_sessions' in data
            assert 'active_sessions' in data
            assert 'completed_sessions' in data