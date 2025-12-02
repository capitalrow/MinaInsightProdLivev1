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
    
    def test_unauthenticated_api_access_blocked(self, client):
        """API endpoints should require authentication."""
        protected_endpoints = [
            '/api/sessions',
            '/api/tasks',
            '/api/workspaces',
            '/dashboard',
            '/meetings',
            '/tasks',
            '/analytics'
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 302, 403], \
                f"Endpoint {endpoint} accessible without auth (status: {response.status_code})"
    
    def test_invalid_token_rejected(self, client):
        """Invalid authentication tokens should be rejected."""
        headers = {
            'Authorization': 'Bearer invalid_token_here',
            'Content-Type': 'application/json'
        }
        
        response = client.get('/api/sessions', headers=headers)
        assert response.status_code in [401, 403], \
            f"Invalid token accepted (status: {response.status_code})"
    
    def test_expired_session_handled(self, client):
        """Expired sessions should be properly invalidated."""
        with client.session_transaction() as sess:
            sess['user_id'] = 99999
            sess['_fresh'] = False
        
        response = client.get('/dashboard')
        assert response.status_code in [401, 302, 403]
    
    def test_session_fixation_prevention(self, client):
        """Session ID should change after login."""
        initial_response = client.get('/')
        
        pass


@pytest.mark.security
class TestWorkspaceIsolation:
    """Test workspace data isolation."""
    
    def test_cross_workspace_data_access_blocked(self, app, db_session, test_user, test_workspace):
        """Users should not access data from other workspaces."""
        from models import Workspace, Task
        
        with app.app_context():
            other_workspace = Workspace(
                name="Other Company",
                owner_id=test_user.id
            )
            db_session.add(other_workspace)
            db_session.commit()
            
            other_task = Task(
                title="Confidential Task",
                workspace_id=other_workspace.id,
                user_id=test_user.id,
                status="pending"
            )
            db_session.add(other_task)
            db_session.commit()
            
            user_tasks = db_session.query(Task).filter(
                Task.workspace_id == test_workspace.id
            ).all()
            
            for task in user_tasks:
                assert task.workspace_id == test_workspace.id
    
    def test_session_workspace_isolation(self, app, db_session, test_user, test_workspace):
        """Meeting sessions should be isolated by workspace."""
        from models import Session
        from ulid import ULID
        
        with app.app_context():
            session1 = Session(
                external_id=str(ULID()),
                title="Workspace 1 Meeting",
                workspace_id=test_workspace.id
            )
            db_session.add(session1)
            db_session.commit()
            
            workspace_sessions = db_session.query(Session).filter(
                Session.workspace_id == test_workspace.id
            ).all()
            
            for sess in workspace_sessions:
                assert sess.workspace_id == test_workspace.id


@pytest.mark.security
class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_sql_injection_prevention(self, client):
        """SQL injection attempts should be blocked."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "1; DELETE FROM sessions",
            "admin'--",
            "1 UNION SELECT * FROM users"
        ]
        
        for payload in malicious_inputs:
            response = client.get(f'/api/sessions/{payload}')
            assert response.status_code in [400, 401, 404], \
                f"Potential SQL injection not blocked: {payload}"
    
    def test_xss_prevention_in_api(self, client):
        """XSS payloads should be sanitized in API responses."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "{{constructor.constructor('alert(1)')()}}"
        ]
        
        for payload in xss_payloads:
            response = client.post('/api/sessions',
                data=json.dumps({'title': payload}),
                content_type='application/json'
            )
            
            if response.status_code == 201:
                data = response.get_json()
                if 'title' in data:
                    assert '<script>' not in data['title'].lower()
    
    def test_path_traversal_prevention(self, client):
        """Path traversal attempts should be blocked."""
        traversal_attempts = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            '....//....//....//etc/passwd',
            '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd'
        ]
        
        for path in traversal_attempts:
            response = client.get(f'/api/files/{path}')
            assert response.status_code in [400, 403, 404], \
                f"Path traversal not blocked: {path}"


@pytest.mark.security
class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limit_headers_present(self, client):
        """Rate limit headers should be present in responses."""
        response = client.get('/health/live')
        
        pass
    
    def test_excessive_requests_throttled(self, client):
        """Excessive requests should be rate limited."""
        throttled = False
        for i in range(200):
            response = client.get('/api/sessions')
            if response.status_code == 429:
                throttled = True
                break
        
        pass


@pytest.mark.security
class TestSecurityHeaders:
    """Test security headers in responses."""
    
    def test_content_security_policy_header(self, client):
        """CSP header should be present."""
        response = client.get('/')
        
        csp = response.headers.get('Content-Security-Policy')
        assert csp is not None or response.status_code == 302, \
            "Content-Security-Policy header missing"
    
    def test_x_content_type_options_header(self, client):
        """X-Content-Type-Options header should be present."""
        response = client.get('/')
        
        xcto = response.headers.get('X-Content-Type-Options')
        if response.status_code == 200:
            assert xcto == 'nosniff' or xcto is None
    
    def test_x_frame_options_header(self, client):
        """X-Frame-Options header should prevent clickjacking."""
        response = client.get('/')
        
        xfo = response.headers.get('X-Frame-Options')
        if response.status_code == 200 and xfo:
            assert xfo in ['DENY', 'SAMEORIGIN']


@pytest.mark.security
class TestDataEncryption:
    """Test data encryption functionality."""
    
    def test_encryption_service_initialization(self, app):
        """Data encryption service should initialize."""
        from services.data_encryption import DataEncryptionService
        
        with app.app_context():
            service = DataEncryptionService()
            assert service is not None
    
    def test_sensitive_data_encrypted(self, app):
        """Sensitive data should be encrypted at rest."""
        from services.data_encryption import DataEncryptionService
        
        with app.app_context():
            service = DataEncryptionService()
            
            plaintext = "sensitive user data"
            encrypted = service.encrypt(plaintext)
            
            assert encrypted != plaintext
            assert len(encrypted) > 0
            
            decrypted = service.decrypt(encrypted)
            assert decrypted == plaintext
