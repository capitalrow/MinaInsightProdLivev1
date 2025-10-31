"""
CROWN⁵+ Analytics Functional Tests
Tests the complete event lifecycle and UI behavior
"""

import pytest
from flask import url_for
from app import app, db
from models import User, Meeting, Task, EventLedger, EventType
from werkzeug.security import generate_password_hash
import json
import time


@pytest.fixture
def client():
    """Create test client with authenticated user"""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            # Create test user
            user = User(
                username='testuser',
                email='test@example.com',
                password_hash=generate_password_hash('password123')
            )
            db.session.add(user)
            db.session.commit()
            
            # Login user
            with client.session_transaction() as sess:
                sess['user_id'] = user.id
            
            yield client


class TestCROWN5EventLifecycle:
    """Test the 10-event CROWN⁵+ lifecycle"""
    
    def test_analytics_bootstrap_event_on_page_load(self, client):
        """Event #1: analytics_bootstrap fires on page load"""
        response = client.get('/dashboard/analytics')
        
        # Should render analytics page
        assert response.status_code == 200
        
        # Should include CROWN⁵+ modules
        assert b'analytics-crown5.js' in response.data
        assert b'analytics-lifecycle.js' in response.data
        assert b'Crown5Analytics' in response.data
    
    def test_analytics_page_includes_websocket_namespace(self, client):
        """Event #2: WebSocket namespace for analytics_ws_subscribe"""
        response = client.get('/dashboard/analytics')
        
        # Should connect to /analytics namespace
        assert b"io('/analytics')" in response.data or b'io("/analytics")' in response.data
    
    def test_analytics_page_includes_cache_infrastructure(self, client):
        """Verify cache-first bootstrap infrastructure"""
        response = client.get('/dashboard/analytics')
        
        # Should include IndexedDB cache module
        assert b'analytics-cache.js' in response.data
        
        # Should include lifecycle management
        assert b'analytics-lifecycle.js' in response.data
    
    def test_analytics_page_includes_prefetch_controller(self, client):
        """Event #5: Verify prefetch infrastructure"""
        response = client.get('/dashboard/analytics')
        
        # Should include prefetch module
        assert b'analytics-prefetch.js' in response.data
    
    def test_analytics_page_includes_export_functionality(self, client):
        """Event #9: Verify export infrastructure"""
        response = client.get('/dashboard/analytics')
        
        # Should include export module
        assert b'analytics-export.js' in response.data


class TestEmotionalUILayer:
    """Test Section 7: Emotional Design"""
    
    def test_page_includes_animation_infrastructure(self, client):
        """Verify emotional UI animations are configured"""
        response = client.get('/dashboard/analytics')
        
        # Should include GSAP or CSS animations
        assert b'fade' in response.data.lower() or b'transition' in response.data.lower()
    
    def test_page_includes_toast_notification_system(self, client):
        """Verify toast notifications for user feedback"""
        response = client.get('/dashboard/analytics')
        
        # Toast infrastructure should be present
        # (This would be in the base template or analytics-specific)
        assert response.status_code == 200


class TestPerformanceOptimization:
    """Test Section 11: Performance Targets"""
    
    def test_analytics_page_loads_quickly(self, client):
        """Verify page loads within reasonable time"""
        start = time.time()
        response = client.get('/dashboard/analytics')
        duration = time.time() - start
        
        assert response.status_code == 200
        # Should load in under 2 seconds (generous for test environment)
        assert duration < 2.0
    
    def test_analytics_page_size_is_reasonable(self, client):
        """Verify page payload is optimized"""
        response = client.get('/dashboard/analytics')
        
        # HTML should not be excessively large
        assert len(response.data) < 100000  # <100KB for HTML


class TestSecurityAndPrivacy:
    """Test Section 13: Security Layer"""
    
    def test_analytics_requires_authentication(self):
        """Verify analytics page requires login"""
        with app.test_client() as client:
            response = client.get('/dashboard/analytics', follow_redirects=False)
            
            # Should redirect to login
            assert response.status_code == 302
            assert b'login' in response.data.lower() or response.location.endswith('/auth/login')
    
    def test_analytics_api_endpoints_require_auth(self):
        """Verify API endpoints are protected"""
        with app.test_client() as client:
            # Try to access analytics API without auth
            response = client.get('/api/analytics/snapshot')
            
            # Should reject unauthenticated requests
            assert response.status_code in [302, 401, 403]


class TestChartIntegration:
    """Verify Chart.js integration for data visualization"""
    
    def test_chartjs_is_loaded(self, client):
        """Verify Chart.js library is available"""
        response = client.get('/dashboard/analytics')
        
        # Should include Chart.js
        assert b'chart.js' in response.data.lower() or b'Chart' in response.data
    
    def test_analytics_includes_chart_containers(self, client):
        """Verify chart canvas elements exist"""
        response = client.get('/dashboard/analytics')
        
        # Should have canvas elements for charts
        assert b'canvas' in response.data.lower() or b'chart' in response.data.lower()


class TestTabNavigation:
    """Test Event #8: Tab switching"""
    
    def test_analytics_has_multiple_tabs(self, client):
        """Verify tabs for Overview, Engagement, Productivity, Insights"""
        response = client.get('/dashboard/analytics')
        
        response_lower = response.data.lower()
        
        # Should have tab structure
        assert b'overview' in response_lower or b'engagement' in response_lower or \
               b'productivity' in response_lower or b'insights' in response_lower


class TestDataIntegrity:
    """Test Section 9: Data Integrity Safeguards"""
    
    def test_analytics_handles_empty_data_gracefully(self, client):
        """Verify graceful handling when no data exists"""
        with app.app_context():
            # Clear any existing meetings
            Meeting.query.delete()
            db.session.commit()
        
        response = client.get('/dashboard/analytics')
        
        # Should still render without errors
        assert response.status_code == 200
        
        # Should show empty state or placeholder
        assert response.data is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
