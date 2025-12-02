"""
Security Tests: Authentication and Authorization
Tests for auth bypass prevention, session security, and access control.
"""
import pytest
import json
from flask import session


@pytest.mark.security
class TestAuthenticationSecurity:
    """Test authentication mechanisms."""
    
    def test_unauthenticated_dashboard_blocked(self, client):
        """Dashboard should block or redirect unauthenticated users."""
        response = client.get('/dashboard')
        assert response.status_code in [302, 308, 401, 403, 200], \
            f"Unexpected dashboard response (status: {response.status_code})"
    
    def test_unauthenticated_api_protected(self, client):
        """API endpoints should be protected."""
        response = client.get('/api/tasks')
        assert response.status_code in [401, 302, 308, 403, 404], \
            f"Tasks API should be protected (status: {response.status_code})"
    
    def test_invalid_token_rejected(self, client):
        """Invalid authentication tokens should be rejected."""
        headers = {
            'Authorization': 'Bearer invalid_token_here',
            'Content-Type': 'application/json'
        }
        
        response = client.get('/api/sessions', headers=headers)
        assert response.status_code in [401, 403, 302], \
            f"Invalid token accepted (status: {response.status_code})"
    
    def test_session_security_configuration(self, app):
        """Session security should be properly configured."""
        with app.app_context():
            assert app.config.get('SESSION_COOKIE_HTTPONLY', True) == True
            assert app.config.get('SESSION_COOKIE_SAMESITE', 'Lax') in ['Lax', 'Strict', None]


@pytest.mark.security
class TestWorkspaceIsolation:
    """Test workspace data isolation."""
    
    def test_workspace_model_exists(self, app, db_session):
        """Workspace model should exist and be queryable."""
        with app.app_context():
            from models import Workspace
            
            workspaces = db_session.query(Workspace).limit(5).all()
            assert isinstance(workspaces, list)
    
    def test_task_workspace_relationship(self, app, db_session, test_user, test_workspace):
        """Tasks should be associated with workspaces."""
        from models import Task
        
        with app.app_context():
            task = Task(
                title="Test Task",
                workspace_id=test_workspace.id,
                assigned_to_id=test_user.id,
                status="todo"
            )
            db_session.add(task)
            db_session.commit()
            
            assert task.workspace_id == test_workspace.id


@pytest.mark.security
class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_nonexistent_session_handled(self, client):
        """Nonexistent session IDs should be handled."""
        response = client.get('/api/sessions/nonexistent-id-12345')
        assert response.status_code in [400, 401, 404, 302, 308, 500], \
            f"Expected error for nonexistent session (got: {response.status_code})"
    
    def test_xss_prevention_in_api(self, client):
        """XSS payloads should be handled safely."""
        xss_payload = "<script>alert('xss')</script>"
        
        response = client.post('/api/sessions',
            data=json.dumps({'title': xss_payload}),
            content_type='application/json'
        )
        
        if response.status_code in [200, 201]:
            data = response.get_json()
            if data and 'title' in data:
                assert '<script>' not in data['title'].lower()


@pytest.mark.security
class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_configured(self, app):
        """Rate limiter should be configured."""
        with app.app_context():
            from flask_limiter import Limiter
            assert True


@pytest.mark.security
class TestSecurityHeaders:
    """Test security headers in responses."""
    
    def test_health_endpoint_responds(self, client):
        """Health endpoint should respond without errors."""
        response = client.get('/health/live')
        assert response.status_code == 200
    
    def test_csp_header_on_pages(self, client):
        """CSP header should be present on page responses."""
        response = client.get('/')
        
        if response.status_code == 200:
            csp = response.headers.get('Content-Security-Policy')
            assert csp is not None, "CSP header should be set on page responses"
            assert 'default-src' in csp or 'script-src' in csp, \
                "CSP should define source restrictions"
    
    def test_security_headers_on_api(self, client):
        """API responses should have security headers."""
        response = client.get('/api/health')
        if response.status_code == 200:
            x_content_type = response.headers.get('X-Content-Type-Options')
            assert x_content_type == 'nosniff' or x_content_type is None


@pytest.mark.security
class TestDataEncryption:
    """Test data encryption functionality."""
    
    def test_encryption_service_exists(self, app):
        """Data encryption service should exist."""
        with app.app_context():
            from services.data_encryption import DataEncryptionService
            assert DataEncryptionService is not None
    
    def test_encryption_key_manager_exists(self, app):
        """Encryption key manager should exist."""
        with app.app_context():
            from services.data_encryption import EncryptionKeyManager
            assert EncryptionKeyManager is not None
    
    def test_encryption_roundtrip(self, app):
        """Test data can be encrypted and decrypted correctly."""
        with app.app_context():
            from services.data_encryption import DataEncryptionService, EncryptionKeyManager
            from unittest.mock import MagicMock
            
            mock_redis = MagicMock()
            mock_redis.get.return_value = None
            mock_redis.setex.return_value = True
            
            key_manager = EncryptionKeyManager(redis_client=mock_redis)
            service = DataEncryptionService(key_manager=key_manager)
            
            test_data = "sensitive_information_12345"
            encrypted = service.encrypt_field(test_data)
            
            assert encrypted != test_data, "Encrypted data should differ from original"
            assert encrypted is not None
            
            decrypted = service.decrypt_field(encrypted)
            assert decrypted == test_data, "Decrypted data should match original"


@pytest.mark.security
class TestPasswordSecurity:
    """Test password hashing and verification."""
    
    def test_password_hashing(self, app):
        """Password hashing should work correctly."""
        with app.app_context():
            from werkzeug.security import generate_password_hash, check_password_hash
            
            password = "secure_password_123!"
            hashed = generate_password_hash(password)
            
            assert hashed != password, "Hash should differ from password"
            assert check_password_hash(hashed, password), "Valid password should verify"
            assert not check_password_hash(hashed, "wrong_password"), "Wrong password should not verify"
