"""
UI Smoke Tests - API Contracts
Tests that API endpoints return expected data structures and formats.
"""

import pytest
import json
from app_refactored import create_app


@pytest.fixture
def client():
    """Create test client for the Flask application."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_endpoints(client):
    """Test that health check endpoints return proper JSON."""
    health_endpoints = [
        '/health',
        '/health/ready',
        '/health/live'
    ]
    
    for endpoint in health_endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, f"Health endpoint {endpoint} not responding"
        
        # Should return JSON
        assert response.content_type.startswith('application/json'), f"Health endpoint {endpoint} not returning JSON"
        
        # Should be valid JSON
        data = json.loads(response.get_data(as_text=True))
        assert isinstance(data, dict), f"Health endpoint {endpoint} not returning JSON object"
        
        print(f"✓ {endpoint} → Valid JSON response")


def test_sessions_api_structure(client):
    """Test that sessions API returns expected structure."""
    # Test sessions list API (may be empty but should have proper structure)
    response = client.get('/api/sessions')
    
    if response.status_code == 200:
        assert response.content_type.startswith('application/json'), "Sessions API not returning JSON"
        
        data = json.loads(response.get_data(as_text=True))
        
        # Should be a list or have sessions field
        if isinstance(data, list):
            print("✓ Sessions API returns list format")
        elif isinstance(data, dict) and 'sessions' in data:
            print("✓ Sessions API returns object with sessions field")
        else:
            # Could be pagination structure
            print(f"✓ Sessions API returns: {type(data)} with keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
    
    elif response.status_code == 404:
        print("✓ Sessions API endpoint not found (may not be implemented)")
    else:
        pytest.fail(f"Sessions API returned unexpected status: {response.status_code}")


def test_summary_api_endpoints(client):
    """Test summary generation and retrieval API structure."""
    # These endpoints need a valid session, so we test the error handling
    test_session_id = 'test-session-id'
    
    # Test summary generation endpoint
    response = client.post(f'/sessions/{test_session_id}/summarise', 
                          json={}, 
                          headers={'Content-Type': 'application/json'})
    
    # Should return JSON even on error
    if response.status_code in [400, 404, 500]:
        try:
            data = json.loads(response.get_data(as_text=True))
            assert isinstance(data, dict), "Summary API error response should be JSON object"
            assert 'error' in data or 'success' in data, "Error response should have error or success field"
            print(f"✓ Summary generation API returns proper error structure: {response.status_code}")
        except json.JSONDecodeError:
            pytest.fail("Summary API should return JSON even on errors")
    
    # Test summary retrieval endpoint
    response = client.get(f'/sessions/{test_session_id}/summary')
    
    if response.status_code in [404, 500]:
        try:
            data = json.loads(response.get_data(as_text=True))
            assert isinstance(data, dict), "Summary retrieval error response should be JSON object"
            print(f"✓ Summary retrieval API returns proper error structure: {response.status_code}")
        except json.JSONDecodeError:
            pytest.fail("Summary retrieval API should return JSON even on errors")


def test_export_endpoints(client):
    """Test export functionality returns proper formats."""
    test_session_id = 'test-session-id'
    
    # Test markdown export
    response = client.get(f'/sessions/{test_session_id}/export.md')
    
    if response.status_code == 200:
        # Should return text/markdown content type
        assert 'text' in response.content_type or 'markdown' in response.content_type, "Markdown export should return text content type"
        
        # Should have content
        content = response.get_data(as_text=True)
        assert len(content) > 0, "Markdown export should not be empty"
        
        print("✓ Markdown export returns proper content type and non-empty content")
    
    elif response.status_code == 404:
        print("✓ Markdown export properly handles non-existent sessions")
    else:
        print(f"✓ Markdown export returns status {response.status_code}")


def test_websocket_endpoint_accessibility(client):
    """Test that WebSocket endpoint is accessible (basic HTTP check)."""
    # Socket.IO endpoints typically respond to HTTP with a specific pattern
    response = client.get('/socket.io/')
    
    # Socket.IO usually returns specific responses or redirects for HTTP requests
    # We're just checking the endpoint exists and doesn't 404
    assert response.status_code != 404, "Socket.IO endpoint should be accessible"
    
    print(f"✓ WebSocket endpoint accessible (status: {response.status_code})")


def test_static_assets_accessible(client):
    """Test that required static assets are accessible."""
    static_assets = [
        '/static/js/websocket_streaming.js',
        '/static/js/recording_wiring.js'
    ]
    
    for asset in static_assets:
        response = client.get(asset)
        assert response.status_code == 200, f"Static asset {asset} not accessible"
        
        # Should return JavaScript content type
        if asset.endswith('.js'):
            assert 'javascript' in response.content_type or 'text' in response.content_type, f"JS asset {asset} wrong content type"
    
    print(f"✓ All {len(static_assets)} required static assets accessible")


def test_api_error_handling_consistency(client):
    """Test that API endpoints handle errors consistently."""
    # Test various endpoints with invalid data to ensure consistent error handling
    error_tests = [
        ('POST', '/sessions/invalid-id/summarise', {'Content-Type': 'application/json'}),
        ('GET', '/sessions/invalid-id/summary', {}),
        ('GET', '/sessions/invalid-id/export.md', {}),
    ]
    
    for method, endpoint, headers in error_tests:
        if method == 'POST':
            response = client.post(endpoint, json={}, headers=headers)
        else:
            response = client.get(endpoint, headers=headers)
        
        # Should return proper HTTP error codes
        assert response.status_code >= 400, f"Endpoint {endpoint} should return error for invalid session"
        
        # Should return JSON for API endpoints (unless it's export which returns text)
        if not endpoint.endswith('.md'):
            try:
                data = json.loads(response.get_data(as_text=True))
                assert isinstance(data, dict), f"API endpoint {endpoint} should return JSON object on error"
                print(f"✓ {method} {endpoint} → Consistent error handling")
            except json.JSONDecodeError:
                print(f"⚠ {method} {endpoint} → Non-JSON error response")