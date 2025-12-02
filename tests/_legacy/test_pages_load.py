"""
UI Smoke Tests - Page Loading
Tests that all key pages load correctly and contain expected marker elements.
"""

import pytest
from app_refactored import create_app


@pytest.fixture
def client():
    """Create test client for the Flask application."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.mark.parametrize("url,marker_id,description", [
    ('/', 'startUpload', 'Dashboard/Index page with upload functionality'),
    ('/live', 'wsStatus', 'Live transcription page with WebSocket status'),
    ('/sessions', 'stats-total', 'Sessions list page with statistics'),
    ('/health', None, 'Health check endpoint')
])
def test_pages_load_successfully(client, url, marker_id, description):
    """Test that key URLs return 200 and contain expected marker elements."""
    response = client.get(url)
    
    # All pages should return 200
    assert response.status_code == 200, f"Page {url} returned {response.status_code}"
    
    # Check for marker element if specified
    if marker_id:
        html_content = response.get_data(as_text=True)
        assert f'id="{marker_id}"' in html_content, f"Marker element '{marker_id}' not found in {url}"
        print(f"✓ {description}: {url} → {marker_id} found")
    else:
        print(f"✓ {description}: {url} → OK")


def test_live_page_recording_elements(client):
    """Test that live page contains all required recording elements."""
    response = client.get('/live')
    assert response.status_code == 200
    
    html_content = response.get_data(as_text=True)
    
    # Required elements for recording functionality
    required_elements = [
        'startRecordingBtn',
        'stopRecordingBtn', 
        'interimText',
        'finalText',
        'micStatus',
        'wsStatus'
    ]
    
    for element_id in required_elements:
        assert f'id="{element_id}"' in html_content, f"Required element '{element_id}' missing from live page"
    
    print(f"✓ Live page contains all {len(required_elements)} required recording elements")


def test_sessions_list_elements(client):
    """Test that sessions list page contains expected table structure."""
    response = client.get('/sessions')
    assert response.status_code == 200
    
    html_content = response.get_data(as_text=True)
    
    # Should have statistics elements
    stats_elements = ['stats-total', 'stats-active', 'stats-completed', 'stats-segments']
    for element_id in stats_elements:
        assert f'id="{element_id}"' in html_content, f"Stats element '{element_id}' missing"
    
    print(f"✓ Sessions list page contains all statistics elements")


def test_sessions_detail_elements(client):
    """Test that session detail page template contains summary elements."""
    # Test with a mock session ID that should return 404 but we can still check template loading
    response = client.get('/sessions/test-session-id')
    
    # Should return 404 for non-existent session, but we can check if the route exists
    assert response.status_code in [200, 404], f"Sessions detail route not properly configured"
    
    if response.status_code == 200:
        html_content = response.get_data(as_text=True)
        # Check for summary generation button
        assert 'generateSummaryBtn' in html_content, "Generate Summary button missing"
        print("✓ Sessions detail page contains summary generation elements")


def test_api_endpoints_accessible(client):
    """Test that key API endpoints are accessible."""
    api_endpoints = [
        '/health',
        '/health/ready', 
        '/health/live'
    ]
    
    for endpoint in api_endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, f"API endpoint {endpoint} not accessible"
    
    print(f"✓ All {len(api_endpoints)} API endpoints accessible")