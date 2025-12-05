"""
Test Export Service (M2.5)
Tests for session export functionality, particularly Markdown export.
"""

import pytest
from app_refactored import create_app, db
from models.base import Base
from services.session_service import SessionService
from services.export_service import ExportService


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


class TestExportService:
    """Test export service functionality."""
    
    def test_session_to_markdown_basic(self, app):
        """Test basic session to Markdown export."""
        with app.app_context():
            # Create session
            session_id = SessionService.create_session(
                title="Export Test Meeting",
                external_id="export-test-123",
                locale="en-US"
            )
            
            # Add segments
            SessionService.create_segment(
                session_id=session_id,
                kind="final",
                text="Hello, this is the first segment.",
                avg_confidence=0.95,
                start_ms=1000,
                end_ms=4000
            )
            SessionService.create_segment(
                session_id=session_id,
                kind="final",
                text="This is the second segment.",
                avg_confidence=0.88,
                start_ms=5000,
                end_ms=8000
            )
            
            # Complete session
            SessionService.complete_session(session_id)
            
            # Export to Markdown
            markdown = ExportService.session_to_markdown(session_id)
            assert markdown is not None
            
            # Verify content
            assert "# Export Test Meeting" in markdown
            assert "export-test-123" in markdown
            assert "Hello, this is the first segment." in markdown
            assert "This is the second segment." in markdown
            assert "Final Transcript" in markdown
            assert "confidence: 95.0%" in markdown
            assert "confidence: 88.0%" in markdown
    
    def test_session_to_markdown_with_metadata(self, app):
        """Test Markdown export with session metadata."""
        with app.app_context():
            # Create session with metadata
            session_id = SessionService.create_session(
                title="Metadata Test Meeting",
                external_id="meta-test-456",
                locale="en-US",
                device_info={
                    "browser": "Chrome", 
                    "os": "macOS",
                    "microphone": "Built-in"
                }
            )
            
            # Export to Markdown
            markdown = ExportService.session_to_markdown(session_id)
            assert markdown is not None
            
            # Verify metadata inclusion
            assert "Browser: Chrome" in markdown
            assert "Os: macOS" in markdown
            assert "Microphone: Built-in" in markdown
            assert "Language:** en-US" in markdown
    
    def test_session_to_markdown_interim_only(self, app):
        """Test Markdown export with only interim segments."""
        with app.app_context():
            # Create session
            session_id = SessionService.create_session(title="Interim Only Meeting")
            
            # Add only interim segments
            for i in range(3):
                SessionService.create_segment(
                    session_id=session_id,
                    kind="interim",
                    text=f"Interim segment {i+1}",
                    avg_confidence=0.7 + (i * 0.1)
                )
            
            # Export to Markdown
            markdown = ExportService.session_to_markdown(session_id)
            assert markdown is not None
            
            # Should contain interim results section
            assert "Interim Results" in markdown
            assert "interim transcription results" in markdown
            assert "Interim segment 1" in markdown
    
    def test_session_to_markdown_no_segments(self, app):
        """Test Markdown export with no segments."""
        with app.app_context():
            # Create empty session
            session_id = SessionService.create_session(title="Empty Meeting")
            SessionService.complete_session(session_id)
            
            # Export to Markdown
            markdown = ExportService.session_to_markdown(session_id)
            assert markdown is not None
            
            # Should handle empty transcript
            assert "# Empty Meeting" in markdown
            assert "No transcript available" in markdown
    
    def test_session_to_markdown_nonexistent(self, app):
        """Test Markdown export with nonexistent session."""
        with app.app_context():
            # Try to export nonexistent session
            markdown = ExportService.session_to_markdown(99999)
            assert markdown is None
    
    def test_get_export_filename(self, app):
        """Test export filename generation."""
        with app.app_context():
            # Create session with title
            session_id = SessionService.create_session(
                title="My Important Meeting 2024!"
            )
            
            # Generate filename
            filename = ExportService.get_export_filename(session_id, 'md')
            assert filename.endswith('.md')
            assert 'mina-' in filename
            assert str(session_id) in filename
            
            # Should sanitize title
            assert 'important-meeting' in filename.lower()
            assert '!' not in filename  # Special chars removed
    
    def test_get_export_filename_nonexistent(self, app):
        """Test filename generation for nonexistent session."""
        with app.app_context():
            # Generate filename for nonexistent session
            filename = ExportService.get_export_filename(99999, 'md')
            assert filename == 'mina-session-99999.md'


class TestExportRoutes:
    """Test export API routes."""
    
    def test_export_markdown_route(self, client, app):
        """Test Markdown export route."""
        with app.app_context():
            # Create session with content
            session_id = SessionService.create_session(title="Route Test Meeting")
            SessionService.create_segment(
                session_id=session_id,
                kind="final",
                text="Test transcript for export",
                avg_confidence=0.9
            )
            SessionService.complete_session(session_id)
            
            # Request Markdown export
            response = client.get(f'/sessions/{session_id}/export.md')
            assert response.status_code == 200
            assert response.mimetype == 'text/markdown'
            
            # Verify content
            markdown = response.get_data(as_text=True)
            assert "# Route Test Meeting" in markdown
            assert "Test transcript for export" in markdown
            
            # Verify download headers
            assert 'attachment' in response.headers.get('Content-Disposition', '')
            assert '.md' in response.headers.get('Content-Disposition', '')
    
    def test_export_markdown_route_nonexistent(self, client, app):
        """Test Markdown export route for nonexistent session."""
        with app.app_context():
            # Request export for nonexistent session
            response = client.get('/sessions/99999/export.md')
            assert response.status_code == 404
    
    def test_export_markdown_from_detail_page(self, client, app):
        """Test export link integration with detail page."""
        with app.app_context():
            # Create completed session
            session_id = SessionService.create_session(title="Integration Test")
            SessionService.create_segment(
                session_id=session_id,
                kind="final", 
                text="Integration test transcript"
            )
            SessionService.complete_session(session_id)
            
            # Load session detail page
            response = client.get(f'/sessions/{session_id}')
            assert response.status_code == 200
            
            # Verify export link is present
            html = response.get_data(as_text=True)
            assert f'/sessions/{session_id}/export.md' in html
            assert 'Export Markdown' in html