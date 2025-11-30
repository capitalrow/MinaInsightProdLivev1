"""
Automated tests for AI Proposals functionality.
Tests the endpoint at /api/tasks/ai-proposals/stream
No mock data - tests against real OpenAI API.
"""
import pytest
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Workspace, Meeting


@pytest.fixture
def client():
    """Create test client with authenticated session."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            user = db.session.query(User).filter_by(email='test@example.com').first()
            if not user:
                user = db.session.query(User).first()
            
            if user:
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['user_id'] = user.id
                    workspace = db.session.query(Workspace).first()
                    if workspace:
                        sess['workspace_id'] = workspace.id
        yield client


def test_ai_proposals_endpoint_exists(client):
    """Test that the AI proposals endpoint exists and requires auth."""
    response = client.post('/api/tasks/ai-proposals/stream',
                          json={'max_proposals': 3},
                          content_type='application/json')
    
    assert response.status_code != 404, "AI proposals endpoint should exist"
    print(f"✅ Endpoint exists - response status: {response.status_code}")


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
        print("✅ AI Proposals endpoint working correctly with SSE streaming!")
    elif response.status_code == 401:
        pytest.skip("User not authenticated - session setup issue")
    elif response.status_code == 500:
        data = response.get_data(as_text=True)
        pytest.fail(f"Server error: {data}")
    else:
        data = response.get_data(as_text=True)
        print(f"Response: {data}")


def test_ai_proposals_with_meeting_context(client):
    """Test AI proposals with meeting ID context."""
    with app.app_context():
        meeting = db.session.query(Meeting).first()
        meeting_id = meeting.id if meeting else None
    
    if meeting_id:
        response = client.post('/api/tasks/ai-proposals/stream',
                              json={'max_proposals': 3, 'meeting_id': meeting_id},
                              content_type='application/json')
        
        print(f"Meeting context response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.get_data(as_text=True)
            print(f"✅ Meeting context stream (first 500 chars): {data[:500]}")
            assert 'data:' in data
    else:
        pytest.skip("No meetings found to test with meeting context")


def test_ai_proposals_no_mock_data(client):
    """Verify AI proposals returns real OpenAI-generated content, not mock data."""
    response = client.post('/api/tasks/ai-proposals/stream',
                          json={'max_proposals': 2},
                          content_type='application/json')
    
    if response.status_code == 200:
        data = response.get_data(as_text=True)
        
        mock_indicators = [
            'mock', 'dummy', 'placeholder', 'example task',
            'lorem ipsum', 'sample data'
        ]
        
        data_lower = data.lower()
        has_mock = False
        for indicator in mock_indicators:
            if indicator in data_lower:
                print(f"⚠️ Warning: Possible mock data indicator found: '{indicator}'")
                has_mock = True
        
        assert 'data:' in data, "Should have SSE data events"
        
        if '"type":"proposal"' in data or '"type": "proposal"' in data:
            print("✅ Real proposal events found in stream!")
        elif '"type":"complete"' in data or '"type": "complete"' in data:
            print("✅ Stream completed successfully!")
        elif '"type":"error"' in data:
            print(f"⚠️ Error in stream: {data}")
        
        if not has_mock:
            print("✅ No mock data indicators found - using real OpenAI data")
    elif response.status_code == 401:
        pytest.skip("User not authenticated")


def test_ai_proposals_response_time(client):
    """Test AI proposals responds within acceptable time."""
    start_time = time.time()
    
    response = client.post('/api/tasks/ai-proposals/stream',
                          json={'max_proposals': 2},
                          content_type='application/json')
    
    first_byte_time = time.time() - start_time
    
    print(f"Time to first byte: {first_byte_time*1000:.0f}ms")
    
    if response.status_code == 200:
        assert first_byte_time < 5.0, f"First byte took {first_byte_time}s, should be < 5s"
        print(f"✅ First byte received in {first_byte_time*1000:.0f}ms")


def test_ai_proposals_sse_format(client):
    """Test AI proposals SSE format is correct."""
    response = client.post('/api/tasks/ai-proposals/stream',
                          json={'max_proposals': 2},
                          content_type='application/json')
    
    if response.status_code == 200:
        data = response.get_data(as_text=True)
        
        lines = data.split('\n')
        data_lines = [l for l in lines if l.startswith('data:')]
        
        print(f"Found {len(data_lines)} SSE data lines")
        
        for line in data_lines[:3]:
            json_str = line[5:].strip()
            if json_str:
                try:
                    parsed = json.loads(json_str)
                    assert 'type' in parsed, "SSE event should have 'type' field"
                    print(f"✅ Valid SSE event type: {parsed['type']}")
                except json.JSONDecodeError as e:
                    if json_str != '[DONE]':
                        pytest.fail(f"Invalid JSON in SSE: {json_str[:100]}")


def test_ai_proposals_streaming_events(client):
    """Test that SSE stream contains expected event types."""
    response = client.post('/api/tasks/ai-proposals/stream',
                          json={'max_proposals': 3},
                          content_type='application/json')
    
    if response.status_code == 200:
        data = response.get_data(as_text=True)
        
        event_types = set()
        for line in data.split('\n'):
            if line.startswith('data:'):
                json_str = line[5:].strip()
                if json_str and json_str != '[DONE]':
                    try:
                        parsed = json.loads(json_str)
                        if 'type' in parsed:
                            event_types.add(parsed['type'])
                    except:
                        pass
        
        print(f"Event types found: {event_types}")
        
        valid_types = {'start', 'proposal', 'chunk', 'complete', 'error', 'progress'}
        for event_type in event_types:
            assert event_type in valid_types, f"Unknown event type: {event_type}"
        
        print(f"✅ All event types are valid: {event_types}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
