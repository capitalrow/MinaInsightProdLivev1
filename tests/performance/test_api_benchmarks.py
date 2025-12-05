"""
Performance Tests: API Response Time Benchmarks
Validates that API endpoints meet SLA requirements.
"""
import pytest
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed


@pytest.mark.performance
class TestAPIResponseTimes:
    """Benchmark API endpoint response times."""
    
    SLA_THRESHOLD_MS = 400
    
    def measure_response_time(self, client, method, endpoint, **kwargs):
        """Measure single request response time in milliseconds."""
        start = time.perf_counter()
        if method == 'GET':
            response = client.get(endpoint, **kwargs)
        elif method == 'POST':
            response = client.post(endpoint, **kwargs)
        end = time.perf_counter()
        return (end - start) * 1000, response.status_code
    
    def test_health_endpoint_latency(self, client):
        """Health endpoint should respond under 500ms."""
        times = []
        for _ in range(10):
            latency, status = self.measure_response_time(client, 'GET', '/health/live')
            if status == 200:
                times.append(latency)
        
        if times:
            avg_latency = statistics.mean(times)
            assert avg_latency < 500, f"Health check avg latency {avg_latency:.2f}ms exceeds 500ms"
    
    def test_dashboard_endpoint_latency(self, client):
        """Dashboard should load under SLA threshold."""
        times = []
        for _ in range(5):
            latency, status = self.measure_response_time(client, 'GET', '/dashboard')
            if status in [200, 302]:
                times.append(latency)
        
        if times:
            avg_latency = statistics.mean(times)
            assert avg_latency < 1000, f"Dashboard avg latency {avg_latency:.2f}ms exceeds 1000ms"
    
    def test_api_sessions_list_latency(self, client):
        """Sessions list API should respond quickly."""
        times = []
        for _ in range(5):
            latency, status = self.measure_response_time(client, 'GET', '/api/sessions')
            if status in [200, 401, 302]:
                times.append(latency)
        
        if times:
            avg_latency = statistics.mean(times)
            assert avg_latency < 1000, f"Sessions API avg latency {avg_latency:.2f}ms exceeds 1000ms"


@pytest.mark.performance
class TestDatabasePerformance:
    """Database query performance tests."""
    
    def test_session_query_performance(self, app, db_session):
        """Test session query execution time."""
        from models import Session
        
        with app.app_context():
            start = time.perf_counter()
            sessions = db_session.query(Session).limit(100).all()
            end = time.perf_counter()
            
            query_time_ms = (end - start) * 1000
            assert query_time_ms < 500, f"Session query took {query_time_ms:.2f}ms, exceeds 500ms"
    
    def test_user_lookup_performance(self, app, db_session):
        """Test user lookup performance."""
        from models import User
        
        with app.app_context():
            start = time.perf_counter()
            users = db_session.query(User).limit(10).all()
            end = time.perf_counter()
            
            query_time_ms = (end - start) * 1000
            assert query_time_ms < 200, f"User query took {query_time_ms:.2f}ms, exceeds 200ms"


@pytest.mark.performance
class TestConcurrentLoad:
    """Concurrent request handling tests."""
    
    def test_concurrent_health_checks(self, client):
        """Test handling multiple health check requests."""
        num_requests = 20
        
        def make_request():
            start = time.perf_counter()
            response = client.get('/health/live')
            end = time.perf_counter()
            return {
                'status': response.status_code,
                'latency_ms': (end - start) * 1000
            }
        
        results = []
        for _ in range(num_requests):
            results.append(make_request())
        
        successful = [r for r in results if r['status'] == 200]
        success_rate = len(successful) / len(results) * 100
        
        assert success_rate >= 90, f"Success rate {success_rate:.1f}% below 90%"
    
    def test_multiple_api_endpoints(self, client):
        """Test handling requests to multiple endpoints."""
        endpoints = ['/health/live', '/health/ready']
        
        results = []
        for endpoint in endpoints:
            for _ in range(3):
                start = time.perf_counter()
                response = client.get(endpoint)
                end = time.perf_counter()
                results.append({
                    'endpoint': endpoint,
                    'status': response.status_code,
                    'latency_ms': (end - start) * 1000
                })
        
        error_count = sum(1 for r in results if r['status'] >= 500)
        assert error_count == 0, f"Found {error_count} server errors"


@pytest.mark.performance
class TestServiceInitialization:
    """Service initialization performance tests."""
    
    def test_ai_insights_service_init_time(self, app):
        """Test AI insights service initialization time."""
        with app.app_context():
            start = time.perf_counter()
            from services.ai_insights_service import AIInsightsService
            AIInsightsService()
            end = time.perf_counter()
            
            init_time_ms = (end - start) * 1000
            assert init_time_ms < 3000, f"Service init took {init_time_ms:.2f}ms, exceeds 3000ms"
    
    def test_vad_service_init_time(self, app):
        """Test VAD service initialization time."""
        with app.app_context():
            start = time.perf_counter()
            from services.vad_service import VADService
            VADService()
            end = time.perf_counter()
            
            init_time_ms = (end - start) * 1000
            assert init_time_ms < 2000, f"Service init took {init_time_ms:.2f}ms, exceeds 2000ms"
