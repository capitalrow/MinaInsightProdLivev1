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
        """Health endpoint should respond under 100ms."""
        times = []
        for _ in range(10):
            latency, status = self.measure_response_time(client, 'GET', '/health/live')
            if status == 200:
                times.append(latency)
        
        if times:
            avg_latency = statistics.mean(times)
            p95_latency = sorted(times)[int(len(times) * 0.95)] if len(times) >= 20 else max(times)
            
            assert avg_latency < 100, f"Health check avg latency {avg_latency:.2f}ms exceeds 100ms"
            assert p95_latency < 200, f"Health check p95 latency {p95_latency:.2f}ms exceeds 200ms"
    
    def test_dashboard_endpoint_latency(self, client):
        """Dashboard should load under SLA threshold."""
        times = []
        for _ in range(5):
            latency, status = self.measure_response_time(client, 'GET', '/dashboard')
            if status in [200, 302]:
                times.append(latency)
        
        if times:
            avg_latency = statistics.mean(times)
            assert avg_latency < self.SLA_THRESHOLD_MS, f"Dashboard avg latency {avg_latency:.2f}ms exceeds SLA"
    
    def test_api_sessions_list_latency(self, client):
        """Sessions list API should respond quickly."""
        times = []
        for _ in range(5):
            latency, status = self.measure_response_time(client, 'GET', '/api/sessions')
            if status in [200, 401, 302]:
                times.append(latency)
        
        if times:
            avg_latency = statistics.mean(times)
            assert avg_latency < self.SLA_THRESHOLD_MS, f"Sessions API avg latency {avg_latency:.2f}ms exceeds SLA"


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
            assert query_time_ms < 100, f"Session query took {query_time_ms:.2f}ms, exceeds 100ms"
    
    def test_user_lookup_performance(self, app, db_session):
        """Test user lookup performance."""
        from models import User
        
        with app.app_context():
            start = time.perf_counter()
            users = db_session.query(User).limit(10).all()
            end = time.perf_counter()
            
            query_time_ms = (end - start) * 1000
            assert query_time_ms < 50, f"User query took {query_time_ms:.2f}ms, exceeds 50ms"


@pytest.mark.performance
class TestConcurrentLoad:
    """Concurrent request handling tests."""
    
    def test_concurrent_health_checks(self, client):
        """Test handling multiple concurrent health check requests."""
        num_requests = 20
        max_workers = 5
        
        def make_request():
            start = time.perf_counter()
            response = client.get('/health/live')
            end = time.perf_counter()
            return {
                'status': response.status_code,
                'latency_ms': (end - start) * 1000
            }
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            for future in as_completed(futures):
                results.append(future.result())
        
        successful = [r for r in results if r['status'] == 200]
        success_rate = len(successful) / len(results) * 100
        
        assert success_rate >= 95, f"Success rate {success_rate:.1f}% below 95%"
        
        if successful:
            avg_latency = statistics.mean([r['latency_ms'] for r in successful])
            assert avg_latency < 500, f"Concurrent avg latency {avg_latency:.2f}ms exceeds 500ms"
    
    def test_concurrent_api_requests(self, client):
        """Test handling concurrent API requests."""
        endpoints = ['/health/live', '/api/health', '/health/ready']
        num_requests_per_endpoint = 5
        
        def make_request(endpoint):
            start = time.perf_counter()
            response = client.get(endpoint)
            end = time.perf_counter()
            return {
                'endpoint': endpoint,
                'status': response.status_code,
                'latency_ms': (end - start) * 1000
            }
        
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for endpoint in endpoints:
                for _ in range(num_requests_per_endpoint):
                    futures.append(executor.submit(make_request, endpoint))
            
            for future in as_completed(futures):
                results.append(future.result())
        
        error_count = sum(1 for r in results if r['status'] >= 500)
        error_rate = error_count / len(results) * 100
        
        assert error_rate < 5, f"Error rate {error_rate:.1f}% exceeds 5%"


@pytest.mark.performance
class TestMemoryUsage:
    """Memory usage and resource consumption tests."""
    
    def test_service_initialization_memory(self, app):
        """Test that services don't consume excessive memory on init."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        with app.app_context():
            from services.transcription_service import TranscriptionService
            from services.ai_insights_service import AIInsightsService
            from services.analysis_service import AnalysisService
            
            TranscriptionService()
            AIInsightsService()
            AnalysisService()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        assert memory_increase < 100, f"Service init consumed {memory_increase:.1f}MB, exceeds 100MB limit"
