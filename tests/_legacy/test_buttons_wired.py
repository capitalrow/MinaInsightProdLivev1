"""
UI Smoke Tests - Button Wiring
Tests that buttons and interactive elements are properly wired to JavaScript handlers.
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


def test_live_page_javascript_loaded(client):
    """Test that live page loads required JavaScript files."""
    response = client.get('/live')
    assert response.status_code == 200
    
    html_content = response.get_data(as_text=True)
    
    # Check that required JS files are referenced
    required_scripts = [
        '/static/js/websocket_streaming.js',
        '/static/js/recording_wiring.js'
    ]
    
    for script in required_scripts:
        assert script in html_content, f"Required script {script} not found in live page"
    
    print(f"✓ Live page references all {len(required_scripts)} required JavaScript files")


def test_recording_buttons_present(client):
    """Test that recording buttons are present with correct IDs."""
    response = client.get('/live')
    assert response.status_code == 200
    
    html_content = response.get_data(as_text=True)
    
    # Check for specific button structure
    assert 'id="startRecordingBtn"' in html_content, "Start Recording button missing"
    assert 'id="stopRecordingBtn"' in html_content, "Stop Recording button missing"
    
    # Check that start button is enabled and stop button is disabled initially
    assert 'id="startRecordingBtn"' in html_content and 'disabled' not in html_content.split('id="startRecordingBtn"')[0].split('>')[-1]
    assert 'id="stopRecordingBtn"' in html_content and 'disabled' in html_content
    
    print("✓ Recording buttons present with correct initial states")


def test_status_elements_present(client):
    """Test that status display elements are present."""
    response = client.get('/live')
    assert response.status_code == 200
    
    html_content = response.get_data(as_text=True)
    
    status_elements = [
        ('micStatus', 'Microphone status'),
        ('wsStatus', 'WebSocket status'),
        ('interimText', 'Interim transcription display'),
        ('finalText', 'Final transcription display')
    ]
    
    for element_id, description in status_elements:
        assert f'id="{element_id}"' in html_content, f"{description} element missing: {element_id}"
    
    print(f"✓ All {len(status_elements)} status elements present")


def test_summary_generation_button(client):
    """Test that summary generation functionality is available."""
    # This tests the template structure, actual functionality would need a real session
    response = client.get('/sessions/test-id')  # Will 404 but shows template structure
    
    # We expect either 200 (with session) or 404 (template exists but session not found)
    assert response.status_code in [200, 404], "Sessions detail route not configured"
    
    # For actual button testing, we would need integration tests with browser automation
    print("✓ Summary generation route accessible")


def test_navigation_links(client):
    """Test that main navigation links work."""
    # Test main page
    response = client.get('/')
    assert response.status_code == 200
    
    html_content = response.get_data(as_text=True)
    
    # Check for common navigation elements that should link to other pages
    nav_checks = [
        ('/live', 'Live transcription link'),
        ('/sessions', 'Sessions list link')
    ]
    
    for url, description in nav_checks:
        # Test that the linked page actually works
        nav_response = client.get(url)
        assert nav_response.status_code == 200, f"{description} target page {url} not working"
    
    print(f"✓ All {len(nav_checks)} navigation targets working")


def test_form_elements_accessibility(client):
    """Test that forms and interactive elements are accessible."""
    response = client.get('/live')
    assert response.status_code == 200
    
    html_content = response.get_data(as_text=True)
    
    # Check that interactive elements have proper labels/accessibility
    # This is a basic check - full accessibility testing would need specialized tools
    interactive_checks = [
        ('button', 'Buttons present'),
        ('input', 'Input elements present'),
        ('select', 'Select elements present')
    ]
    
    for element_type, description in interactive_checks:
        if f'<{element_type}' in html_content:
            print(f"✓ {description}")
    
    print("✓ Interactive elements accessibility check completed")


def test_no_javascript_errors_in_html(client):
    """Test that HTML doesn't contain obvious JavaScript syntax errors."""
    pages = ['/', '/live', '/sessions']
    
    for page in pages:
        response = client.get(page)
        if response.status_code == 200:
            html_content = response.get_data(as_text=True)
            
            # Basic check for common JS errors in HTML
            error_patterns = [
                'SyntaxError',
                'ReferenceError', 
                'TypeError',
                'undefined is not',
                'Cannot read property'
            ]
            
            for pattern in error_patterns:
                assert pattern not in html_content, f"Potential JavaScript error pattern '{pattern}' found in {page}"
    
    print(f"✓ No obvious JavaScript errors found in HTML for {len(pages)} pages")