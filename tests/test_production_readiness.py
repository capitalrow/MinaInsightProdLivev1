"""
Production Readiness Smoke Tests

Critical path tests following Google SRE PRR standards.
These tests verify the application is ready for production traffic.

Run with: pytest tests/test_production_readiness.py -v
"""

import os
import pytest
import json
from unittest.mock import patch, MagicMock


class TestHealthEndpoints:
    """Test health check endpoints follow Kubernetes standards."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        os.environ.setdefault("SESSION_SECRET", "test-session-secret-for-testing-only")
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_liveness_probe_returns_200(self, client):
        """Liveness probe should always return 200 if process is alive."""
        response = client.get('/health/live')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'alive'
        assert 'uptime_seconds' in data
    
    def test_readiness_probe_checks_dependencies(self, client):
        """Readiness probe should check critical dependencies."""
        response = client.get('/health/ready')
        data = json.loads(response.data)
        
        assert 'status' in data
        assert 'checks' in data
        assert 'database' in data['checks']
        assert 'timestamp' in data
    
    def test_startup_probe_returns_status(self, client):
        """Startup probe should indicate initialization status."""
        response = client.get('/health/startup')
        data = json.loads(response.data)
        
        assert response.status_code in [200, 503]
        assert 'status' in data
        assert data['status'] in ['started', 'starting']
    
    def test_detailed_health_includes_system_metrics(self, client):
        """Detailed health should include system metrics."""
        response = client.get('/health/detailed')
        data = json.loads(response.data)
        
        assert 'status' in data
        assert 'dependencies' in data
        assert 'system' in data
        assert 'environment' in data
    
    def test_healthz_fallback_works(self, client):
        """Legacy /healthz endpoint should work."""
        response = client.get('/healthz')
        assert response.status_code == 200


class TestSecurityHeaders:
    """Test security headers are properly set."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        os.environ.setdefault("SESSION_SECRET", "test-session-secret-for-testing-only")
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_csrf_token_endpoint_exists(self, client):
        """CSRF token refresh endpoint should be available."""
        response = client.get('/api/csrf-token')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'token' in data


class TestErrorHandling:
    """Test error handlers return proper responses."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        os.environ.setdefault("SESSION_SECRET", "test-session-secret-for-testing-only")
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_404_returns_json_for_api(self, client):
        """404 for API routes should return JSON."""
        response = client.get('/api/nonexistent-endpoint-12345')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error'] == 'not_found'


class TestStartupValidation:
    """Test startup validation module."""
    
    def test_validation_detects_missing_env_vars(self):
        """Validator should detect missing required env vars."""
        from utils.startup_validation import StartupValidator
        
        with patch.dict(os.environ, {'SESSION_SECRET': '', 'DATABASE_URL': ''}, clear=False):
            validator = StartupValidator()
            validator.validate_required_env_vars()
            
            failed = [v for v in validator.report.validations if not v.passed]
            assert len(failed) >= 1
    
    def test_validation_passes_with_valid_config(self):
        """Validator should pass with valid configuration."""
        from utils.startup_validation import StartupValidator
        
        with patch.dict(os.environ, {
            'SESSION_SECRET': 'a-very-long-session-secret-for-testing-purposes',
            'DATABASE_URL': 'postgresql://test:test@localhost/test'
        }, clear=False):
            validator = StartupValidator()
            validator.validate_required_env_vars()
            
            required_validations = [v for v in validator.report.validations 
                                   if v.name.startswith('env:')]
            passed = [v for v in required_validations if v.passed]
            assert len(passed) >= 2


class TestDatabaseConnection:
    """Test database connectivity."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        os.environ.setdefault("SESSION_SECRET", "test-session-secret-for-testing-only")
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_database_health_check(self, client):
        """Database health check should work."""
        response = client.get('/health/ready')
        data = json.loads(response.data)
        
        assert 'checks' in data
        assert 'database' in data['checks']
        db_check = data['checks']['database']
        assert 'healthy' in db_check or 'status' in db_check


class TestCriticalRoutes:
    """Test critical routes are accessible."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        os.environ.setdefault("SESSION_SECRET", "test-session-secret-for-testing-only")
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_root_accessible(self, client):
        """Root route should be accessible."""
        response = client.get('/')
        assert response.status_code in [200, 302, 404]
    
    def test_login_page_accessible(self, client):
        """Login page should be accessible."""
        response = client.get('/auth/login')
        assert response.status_code in [200, 302]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
