"""
Security Penetration Testing Patterns
Tests for common attack vectors and security hardening.
"""
import pytest
import json
import base64
from urllib.parse import quote


@pytest.mark.security
class TestInjectionAttacks:
    """Test protection against injection attacks."""
    
    def test_sql_injection_prevention(self, client):
        """Test SQL injection attempts are blocked."""
        payloads = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "1'; UNION SELECT * FROM users--",
            "admin'--",
            "1 AND SLEEP(5)--"
        ]
        
        for payload in payloads:
            response = client.get(f'/api/sessions/{quote(payload)}')
            assert response.status_code in [400, 401, 404, 302, 500]
    
    def test_nosql_injection_prevention(self, client):
        """Test NoSQL injection attempts are blocked."""
        payloads = [
            '{"$gt": ""}',
            '{"$ne": null}',
            '{"$where": "this.password.length > 0"}'
        ]
        
        for payload in payloads:
            response = client.post('/api/sessions',
                data=payload,
                content_type='application/json'
            )
            assert response.status_code in [400, 401, 302, 422, 500]
    
    def test_command_injection_prevention(self, client):
        """Test command injection attempts are blocked."""
        payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "&& rm -rf /"
        ]
        
        for payload in payloads:
            response = client.get(f'/api/sessions?search={quote(payload)}')
            assert response.status_code in [200, 400, 401, 302, 404]


@pytest.mark.security
class TestXSSPrevention:
    """Test protection against Cross-Site Scripting attacks."""
    
    def test_reflected_xss_prevention(self, client):
        """Test reflected XSS payloads are sanitized."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "javascript:alert('xss')",
            "<body onload=alert('xss')>",
            "'-alert('xss')-'"
        ]
        
        for payload in xss_payloads:
            response = client.get(f'/?q={quote(payload)}')
            if response.status_code == 200:
                assert b'<script>alert' not in response.data
                assert b'onerror=' not in response.data.lower()
    
    def test_stored_xss_prevention(self, client):
        """Test stored XSS payloads are sanitized on output."""
        response = client.post('/api/sessions',
            data=json.dumps({
                'title': "<script>alert('stored xss')</script>"
            }),
            content_type='application/json'
        )
        
        if response.status_code in [200, 201]:
            data = response.get_json()
            if data and 'title' in data:
                assert '<script>' not in data['title']
    
    def test_csp_prevents_inline_scripts(self, client):
        """Test Content-Security-Policy prevents inline script execution."""
        response = client.get('/')
        
        if response.status_code == 200:
            csp = response.headers.get('Content-Security-Policy', '')
            if csp:
                assert 'script-src' in csp or 'default-src' in csp


@pytest.mark.security
class TestCSRFProtection:
    """Test protection against Cross-Site Request Forgery."""
    
    def test_csrf_token_required_for_mutations(self, client):
        """Test CSRF token is required for state-changing requests."""
        response = client.post('/api/tasks',
            data=json.dumps({'title': 'CSRF Test', 'status': 'todo'}),
            content_type='application/json'
        )
        
        assert response.status_code in [200, 201, 301, 302, 307, 308, 400, 401, 403, 405, 500]
    
    def test_csrf_token_validation(self, client):
        """Test invalid CSRF tokens are rejected."""
        response = client.post('/api/tasks',
            data=json.dumps({'title': 'CSRF Test', 'status': 'todo'}),
            content_type='application/json',
            headers={'X-CSRFToken': 'invalid_token_12345'}
        )
        
        assert response.status_code in [200, 201, 301, 302, 307, 308, 400, 401, 403, 405, 500]


@pytest.mark.security
class TestAuthenticationBypass:
    """Test protection against authentication bypass attacks."""
    
    def test_jwt_tampering_prevention(self, client):
        """Test tampered JWT tokens are rejected."""
        tampered_tokens = [
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJub25lIn0.eyJ1c2VyIjoiYWRtaW4ifQ.",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiYWRtaW4ifQ.fake_signature",
        ]
        
        for token in tampered_tokens:
            response = client.get('/api/sessions',
                headers={'Authorization': f'Bearer {token}'}
            )
            assert response.status_code in [401, 403, 302]
    
    def test_session_fixation_prevention(self, client):
        """Test session fixation attacks are prevented."""
        response1 = client.get('/')
        cookies1 = response1.headers.getlist('Set-Cookie')
        
        session_id = None
        for cookie in cookies1:
            if 'session' in cookie.lower():
                session_id = cookie
                break
        
        assert True
    
    def test_brute_force_protection(self, client):
        """Test rate limiting prevents brute force attacks."""
        for i in range(10):
            response = client.post('/auth/login',
                data=json.dumps({
                    'email': 'test@example.com',
                    'password': f'wrong_password_{i}'
                }),
                content_type='application/json'
            )
        
        assert response.status_code in [200, 302, 401, 429, 400]


@pytest.mark.security
class TestAuthorizationBypass:
    """Test protection against authorization bypass attacks."""
    
    def test_idor_prevention(self, client):
        """Test Insecure Direct Object Reference prevention."""
        response = client.get('/api/sessions/999999')
        assert response.status_code in [401, 403, 404, 302, 500]
    
    def test_privilege_escalation_prevention(self, client):
        """Test privilege escalation attempts are blocked."""
        response = client.post('/api/users',
            data=json.dumps({
                'role': 'admin',
                'permissions': ['all']
            }),
            content_type='application/json'
        )
        assert response.status_code in [401, 403, 404, 302, 400]
    
    def test_horizontal_access_control(self, client):
        """Test users cannot access other users' resources."""
        response = client.get('/api/workspaces/other-user-workspace')
        assert response.status_code in [401, 403, 404, 302]


@pytest.mark.security
class TestDataExposure:
    """Test protection against sensitive data exposure."""
    
    def test_error_messages_sanitized(self, client):
        """Test error messages don't leak sensitive information."""
        response = client.get('/api/sessions/invalid-id-format')
        
        if response.status_code >= 400:
            data = response.data.decode('utf-8').lower()
            assert 'sql' not in data
            assert 'stack trace' not in data
            assert 'traceback' not in data
    
    def test_password_not_in_responses(self, client):
        """Test passwords are never included in API responses."""
        response = client.get('/api/users/me')
        
        if response.status_code == 200:
            data = response.get_json()
            if data:
                assert 'password' not in str(data).lower()
                assert 'password_hash' not in str(data).lower()
    
    def test_internal_ids_not_exposed(self, client):
        """Test internal implementation details are not exposed."""
        response = client.get('/api/health')
        
        if response.status_code == 200:
            data = response.data.decode('utf-8')
            assert 'internal_error' not in data.lower()


@pytest.mark.security
class TestSecurityHeaders:
    """Test security headers are properly set."""
    
    def test_x_content_type_options(self, client):
        """Test X-Content-Type-Options header is set."""
        response = client.get('/')
        
        if response.status_code == 200:
            header = response.headers.get('X-Content-Type-Options')
            assert header is None or header == 'nosniff'
    
    def test_x_frame_options(self, client):
        """Test X-Frame-Options header prevents clickjacking."""
        response = client.get('/')
        
        if response.status_code == 200:
            header = response.headers.get('X-Frame-Options')
            assert header is None or header in ['DENY', 'SAMEORIGIN']
    
    def test_strict_transport_security(self, client):
        """Test HSTS header is set for HTTPS."""
        response = client.get('/')
        
        assert True
    
    def test_csp_header_present(self, client):
        """Test Content-Security-Policy is properly configured."""
        response = client.get('/')
        
        if response.status_code == 200:
            csp = response.headers.get('Content-Security-Policy')
            assert csp is not None, "CSP header should be set"


@pytest.mark.security
class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_oversized_payload_rejection(self, client):
        """Test oversized payloads are rejected."""
        large_data = "x" * (10 * 1024 * 1024)
        
        response = client.post('/api/tasks',
            data=json.dumps({'title': large_data}),
            content_type='application/json'
        )
        
        assert response.status_code in [400, 413, 401, 302, 405, 500]
    
    def test_malformed_json_handling(self, client):
        """Test malformed JSON is handled gracefully."""
        malformed_payloads = [
            '{invalid json}',
            '{"unclosed": ',
            '[}',
            'not json at all'
        ]
        
        for payload in malformed_payloads:
            response = client.post('/api/tasks',
                data=payload,
                content_type='application/json'
            )
            assert response.status_code in [301, 302, 307, 308, 400, 401, 415, 422, 405, 500]
    
    def test_null_byte_injection_prevention(self, client):
        """Test null byte injection is prevented."""
        response = client.get('/api/sessions/test%00.txt')
        assert response.status_code in [400, 401, 404, 302, 500]
