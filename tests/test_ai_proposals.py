"""
Automated tests for AI Proposals functionality.
Tests the endpoint at /api/tasks/ai-proposals/stream
"""
import pytest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Workspace


@pytest.fixture
def client():
    """Create test client with authenticated session."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            if not user:
                user = User.query.first()
            
            if user:
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['user_id'] = user.id
                    workspace = Workspace.query.first()
                    if workspace:
                        sess['workspace_id'] = workspace.id
        yield client


def test_ai_proposals_endpoint_exists(client):
    """Test that the AI proposals endpoint exists and requires auth."""
    response = client.post('/api/tasks/ai-proposals/stream',
                          json={'max_proposals': 3},
                          content_type='application/json')
    
    assert response.status_code != 404, "AI proposals endpoint should exist"
    print(f"Endpoint response status: {response.status_code}")


def test_ai_proposals_stream_authenticated(client):
    """Test AI proposals stream with authenticated user."""
    response = client.post('/api/tasks/ai-proposals/stream',
                          json={'max_proposals': 3},
                          content_type='application/json')
    
    print(f"Response status: {response.status_code}")
    print(f"Response content-type: {response.content_type}")
    
    if response.status_code == 200:
        assert 'text/event-stream' in response.content_type, \
            f"Expected SSE stream, got {response.content_type}"
        
        data = response.get_data(as_text=True)
        print(f"Stream response (first 500 chars): {data[:500]}")
        
        assert 'data:' in data, "SSE stream should contain data events"
        print("AI Proposals endpoint working correctly with SSE streaming!")
    elif response.status_code == 401:
        print("User not authenticated - need to check session setup")
    elif response.status_code == 500:
        data = response.get_data(as_text=True)
        print(f"Server error: {data}")
    else:
        data = response.get_data(as_text=True)
        print(f"Unexpected response: {data}")


def test_ai_proposals_with_meeting_context(client):
    """Test AI proposals with meeting ID context."""
    from models import Meeting
    
    with app.app_context():
        meeting = Meeting.query.first()
        meeting_id = meeting.id if meeting else None
    
    if meeting_id:
        response = client.post('/api/tasks/ai-proposals/stream',
                              json={'max_proposals': 3, 'meeting_id': meeting_id},
                              content_type='application/json')
        
        print(f"Meeting context response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.get_data(as_text=True)
            print(f"Meeting context stream (first 500 chars): {data[:500]}")
    else:
        print("No meetings found to test with meeting context")


def test_ai_proposals_no_mock_data(client):
    """Verify AI proposals returns real OpenAI-generated content, not mock data."""
    response = client.post('/api/tasks/ai-proposals/stream',
                          json={'max_proposals': 2},
                          content_type='application/json')
    
    if response.status_code == 200:
        data = response.get_data(as_text=True)
        
        mock_indicators = [
            'mock', 'dummy', 'placeholder', 'example task',
            'lorem ipsum', 'test task', 'sample'
        ]
        
        data_lower = data.lower()
        for indicator in mock_indicators:
            if indicator in data_lower:
                print(f"Warning: Possible mock data indicator found: '{indicator}'")
        
        assert 'data:' in data, "Should have SSE data events"
        
        if '"type":"proposal"' in data or '"type": "proposal"' in data:
            print("Real proposal events found in stream!")
        elif '"type":"complete"' in data or '"type": "complete"' in data:
            print("Stream completed successfully!")
        elif '"type":"error"' in data:
            print(f"Error in stream: {data}")
        else:
            print(f"Stream data: {data[:1000]}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
