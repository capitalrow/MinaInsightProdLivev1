"""
Test cases for M3 Summary API endpoints.

Tests the analysis service and summary generation endpoints
with mock analysis engine.
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from app_refactored import create_app, db
from models.session import Session
from models.segment import Segment
from models.summary import Summary
from services.analysis_service import AnalysisService


class TestSummaryAPI:
    """Test summary API endpoints."""
    
    @pytest.fixture
    def app(self):
        """Create test application with in-memory database."""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['ANALYSIS_ENGINE'] = 'mock'  # Use mock for testing
        
        with app.app_context():
            db.create_all()
            
            # Create test session with segments
            session = Session(
                external_id='test-session-123',
                title='Test Meeting for Summary',
                status='completed',
                locale='en-US'
            )
            db.session.add(session)
            db.session.commit()
            
            # Add test segments
            segments = [
                Segment(
                    session_id=session.id,
                    kind='final',
                    text='Welcome everyone to the quarterly planning meeting',
                    avg_confidence=0.85,
                    start_ms=0,
                    end_ms=3000
                ),
                Segment(
                    session_id=session.id,
                    kind='final',
                    text='We need to finalize the budget by next Friday',
                    avg_confidence=0.92,
                    start_ms=3000,
                    end_ms=6000
                ),
                Segment(
                    session_id=session.id,
                    kind='final',
                    text='There is a risk of delays if we don\'t get approval soon',
                    avg_confidence=0.88,
                    start_ms=6000,
                    end_ms=9000
                )
            ]
            
            for segment in segments:
                db.session.add(segment)
            
            db.session.commit()
            
        yield app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    def test_generate_summary_success(self, client, app):
        """Test successful summary generation."""
        with app.app_context():
            # Get the test session
            session = Session.query.filter_by(external_id='test-session-123').first()
            assert session is not None
            
            # Generate summary
            response = client.post(f'/sessions/{session.id}/summarise')
            
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'summary' in data
            assert data['summary']['session_id'] == session.id
            assert data['summary']['engine'] == 'mock'
            
            # Check that summary was persisted
            summary = Summary.query.filter_by(session_id=session.id).first()
            assert summary is not None
            assert summary.engine == 'mock'
            assert len(summary.actions) >= 0  # Mock may generate actions
            assert len(summary.decisions) >= 0
            assert len(summary.risks) >= 0
    
    def test_generate_summary_nonexistent_session(self, client, app):
        """Test summary generation for nonexistent session."""
        response = client.post('/sessions/999999/summarise')
        
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
    
    def test_get_summary_success(self, client, app):
        """Test retrieving existing summary."""
        with app.app_context():
            # Get the test session
            session = Session.query.filter_by(external_id='test-session-123').first()
            
            # First generate a summary
            AnalysisService.generate_summary(session.id)
            
            # Now retrieve it
            response = client.get(f'/sessions/{session.id}/summary')
            
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'summary' in data
            assert data['summary']['session_id'] == session.id
    
    def test_get_summary_not_found(self, client, app):
        """Test retrieving summary that doesn't exist."""
        with app.app_context():
            session = Session.query.filter_by(external_id='test-session-123').first()
            
            response = client.get(f'/sessions/{session.id}/summary')
            
            assert response.status_code == 404
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'not found' in data['error'].lower()
    
    def test_analysis_service_mock_engine(self, app):
        """Test mock analysis engine functionality."""
        with app.app_context():
            session = Session.query.filter_by(external_id='test-session-123').first()
            segments = Segment.query.filter_by(session_id=session.id).all()
            
            # Test mock analysis
            context = "Test meeting with budget discussion and timeline risks"
            result = AnalysisService._analyse_with_mock(context, segments)
            
            # Verify result structure
            assert 'summary_md' in result
            assert 'actions' in result
            assert 'decisions' in result  
            assert 'risks' in result
            
            # Verify types
            assert isinstance(result['actions'], list)
            assert isinstance(result['decisions'], list)
            assert isinstance(result['risks'], list)
            
            # Test with empty context
            empty_result = AnalysisService._analyse_with_mock("", [])
            assert empty_result['summary_md'] is not None
            assert len(empty_result['actions']) == 0  # No actions for empty content
    
    def test_context_building(self, app):
        """Test transcript context building."""
        with app.app_context():
            session = Session.query.filter_by(external_id='test-session-123').first()
            segments = Segment.query.filter_by(session_id=session.id, kind='final').all()
            
            context = AnalysisService._build_context(segments)
            
            assert len(context) > 0
            assert 'quarterly planning meeting' in context.lower()
            assert 'budget' in context.lower()
            assert 'risk' in context.lower()
    
    def test_summary_regeneration(self, client, app):
        """Test that regenerating summary replaces existing one."""
        with app.app_context():
            session = Session.query.filter_by(external_id='test-session-123').first()
            
            # Generate first summary
            response1 = client.post(f'/sessions/{session.id}/summarise')
            assert response1.status_code == 200
            
            first_summary_id = json.loads(response1.data)['summary']['id']
            
            # Generate second summary (should replace first)
            response2 = client.post(f'/sessions/{session.id}/summarise')
            assert response2.status_code == 200
            
            second_summary_id = json.loads(response2.data)['summary']['id']
            
            # Should be different IDs but only one summary in DB
            summaries = Summary.query.filter_by(session_id=session.id).all()
            assert len(summaries) == 1
            assert summaries[0].id == second_summary_id
    
    def test_empty_session_analysis(self, client, app):
        """Test analysis of session with no final segments."""
        with app.app_context():
            # Create session with no segments
            empty_session = Session(
                external_id='empty-session-456',
                title='Empty Meeting',
                status='completed',
                locale='en-US'
            )
            db.session.add(empty_session)
            db.session.commit()
            
            # Generate summary for empty session
            response = client.post(f'/sessions/{empty_session.id}/summarise')
            
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Should still create a summary indicating no content
            summary = data['summary']
            assert 'no transcript' in summary['summary_md'].lower() or 'not available' in summary['summary_md'].lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])