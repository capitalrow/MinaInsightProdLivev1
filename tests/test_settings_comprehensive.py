"""
Comprehensive Settings Page Test Suite
Tests all settings functionality: Preferences, Profile, Workspace, Integrations
"""
import pytest
import json
from flask import url_for
from app import app, db
from models import User, Workspace


@pytest.fixture
def client():
    """Create test client with test database."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


@pytest.fixture
def authenticated_client(client):
    """Create authenticated test client with test user."""
    with app.app_context():
        from werkzeug.security import generate_password_hash
        
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=generate_password_hash('testpassword'),
            role='admin'
        )
        db.session.add(user)
        db.session.flush()
        
        workspace = Workspace(
            name='Test Workspace',
            slug='test-workspace',
            owner_id=user.id
        )
        db.session.add(workspace)
        db.session.flush()
        
        user.workspace_id = workspace.id
        db.session.commit()
        
        client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpassword'
        }, follow_redirects=True)
        
        yield client


class TestPreferencesAPI:
    """Test Preferences API endpoints."""
    
    def test_get_preferences_unauthenticated(self, client):
        """Test that unauthenticated users are redirected."""
        response = client.get('/settings/api/preferences')
        assert response.status_code == 302
        assert 'login' in response.location.lower()
    
    def test_get_preferences_authenticated(self, authenticated_client):
        """Test getting user preferences."""
        response = authenticated_client.get('/settings/api/preferences')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'preferences' in data
    
    def test_update_preferences(self, authenticated_client):
        """Test updating user preferences."""
        response = authenticated_client.patch(
            '/settings/api/preferences',
            data=json.dumps({
                'category': 'notifications',
                'key': 'email_digest',
                'value': True
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
    
    def test_reset_preferences(self, authenticated_client):
        """Test resetting preferences to defaults."""
        response = authenticated_client.post(
            '/settings/api/preferences/reset',
            data=json.dumps({'category': 'notifications'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
    
    def test_export_settings(self, authenticated_client):
        """Test exporting user settings."""
        response = authenticated_client.get('/settings/api/export')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'data' in data


class TestWorkspaceAPI:
    """Test Workspace API endpoints."""
    
    def test_get_workspace_stats_unauthenticated(self, client):
        """Test that unauthenticated users are redirected."""
        response = client.get('/settings/api/workspace/stats')
        assert response.status_code == 302
    
    def test_get_workspace_stats_authenticated(self, authenticated_client):
        """Test getting workspace statistics."""
        response = authenticated_client.get('/settings/api/workspace/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'stats' in data
        stats = data['stats']
        assert 'total_meetings' in stats
        assert 'hours_recorded' in stats
        assert 'team_members' in stats
    
    def test_invite_member(self, authenticated_client):
        """Test inviting a new member."""
        response = authenticated_client.post(
            '/settings/workspace/invite',
            data=json.dumps({
                'email': 'newuser@example.com',
                'role': 'member'
            }),
            content_type='application/json'
        )
        assert response.status_code in [200, 201, 400]


class TestProfileAPI:
    """Test Profile API endpoints."""
    
    def test_profile_page_loads(self, authenticated_client):
        """Test that profile page loads correctly."""
        response = authenticated_client.get('/settings/profile')
        assert response.status_code == 200
        assert b'Profile' in response.data or b'profile' in response.data
    
    def test_profile_page_includes_settings_js(self, authenticated_client):
        """Test that profile page includes settings.js."""
        response = authenticated_client.get('/settings/profile')
        assert response.status_code == 200
        assert b'settings.js' in response.data


class TestIntegrationsAPI:
    """Test Integrations API endpoints."""
    
    def test_integrations_page_loads(self, authenticated_client):
        """Test that integrations page loads correctly."""
        response = authenticated_client.get('/settings/integrations')
        assert response.status_code == 200
        assert b'Integrations' in response.data or b'integrations' in response.data
    
    def test_integrations_page_includes_settings_js(self, authenticated_client):
        """Test that integrations page includes settings.js."""
        response = authenticated_client.get('/settings/integrations')
        assert response.status_code == 200
        assert b'settings.js' in response.data


class TestSettingsPages:
    """Test Settings page rendering."""
    
    def test_preferences_page_loads(self, authenticated_client):
        """Test that preferences page loads correctly."""
        response = authenticated_client.get('/settings/preferences')
        assert response.status_code == 200
        assert b'Preferences' in response.data or b'preferences' in response.data
    
    def test_workspace_page_loads(self, authenticated_client):
        """Test that workspace page loads correctly."""
        response = authenticated_client.get('/settings/workspace')
        assert response.status_code == 200
        assert b'Workspace' in response.data or b'workspace' in response.data
    
    def test_all_pages_include_settings_js(self, authenticated_client):
        """Test that all settings pages include settings.js."""
        pages = ['/settings/preferences', '/settings/profile', 
                 '/settings/integrations', '/settings/workspace']
        for page in pages:
            response = authenticated_client.get(page)
            assert response.status_code == 200, f"Page {page} failed to load"
            assert b'settings.js' in response.data, f"Page {page} missing settings.js"


class TestDataAttributes:
    """Test that templates have proper data attributes for JS binding."""
    
    def test_preferences_has_data_attributes(self, authenticated_client):
        """Test that preferences page has data-preference attributes."""
        response = authenticated_client.get('/settings/preferences')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'data-preference' in html or 'data-category' in html
    
    def test_workspace_has_data_stat_attributes(self, authenticated_client):
        """Test that workspace page has data-stat attributes."""
        response = authenticated_client.get('/settings/workspace')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'data-stat' in html


class TestErrorHandling:
    """Test error handling in settings APIs."""
    
    def test_invalid_preference_category(self, authenticated_client):
        """Test updating invalid preference category."""
        response = authenticated_client.patch(
            '/settings/api/preferences',
            data=json.dumps({
                'category': 'invalid_category',
                'key': 'some_key',
                'value': True
            }),
            content_type='application/json'
        )
        assert response.status_code in [200, 400]
    
    def test_missing_request_body(self, authenticated_client):
        """Test API with missing request body."""
        response = authenticated_client.patch(
            '/settings/api/preferences',
            data='',
            content_type='application/json'
        )
        assert response.status_code in [200, 400]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
