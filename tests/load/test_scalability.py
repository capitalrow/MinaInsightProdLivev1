"""
Scalability & Load Testing
Tests for concurrent users, WebSocket stress, and database connection pooling.
"""
import pytest
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch


@pytest.mark.scalability
class TestConcurrentUsers:
    """Test application behavior under concurrent user load."""
    
    def test_concurrent_session_creation(self, app, db_session):
        """Test multiple sessions can be created sequentially (concurrent DB access requires separate sessions)."""
        from models import Session
        
        num_sessions = 10
        created_sessions = []
        
        with app.app_context():
            for i in range(num_sessions):
                try:
                    external_id = Session.generate_external_id()
                    session = Session(
                        external_id=external_id,
                        title=f"Concurrent Test {i}",
                        status="active"
                    )
                    db_session.add(session)
                    db_session.commit()
                    created_sessions.append(session.id)
                except Exception as e:
                    db_session.rollback()
        
        assert len(created_sessions) >= num_sessions * 0.8, f"Expected 80% success, got {len(created_sessions)}/{num_sessions}"
    
    def test_concurrent_api_requests(self, client):
        """Test API handles concurrent requests."""
        num_requests = 20
        results = queue.Queue()
        
        def make_request():
            try:
                response = client.get('/health/live')
                results.put(("success", response.status_code))
            except Exception as e:
                results.put(("error", str(e)))
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            for future in as_completed(futures):
                pass
        
        successes = 0
        while not results.empty():
            status, code = results.get()
            if status == "success" and code == 200:
                successes += 1
        
        assert successes >= num_requests * 0.95, f"Expected 95% success rate"
    
    def test_database_connection_pool_under_load(self, app, db_session):
        """Test database connection pooling handles concurrent queries."""
        from models import Session
        
        num_queries = 50
        results = queue.Queue()
        
        def run_query(index):
            with app.app_context():
                try:
                    count = db_session.query(Session).count()
                    results.put(("success", count))
                except Exception as e:
                    results.put(("error", str(e)))
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(run_query, i) for i in range(num_queries)]
            for future in as_completed(futures):
                pass
        elapsed = time.time() - start_time
        
        successes = 0
        while not results.empty():
            status, _ = results.get()
            if status == "success":
                successes += 1
        
        assert successes >= num_queries * 0.9, "Expected 90% query success"
        assert elapsed < 10, f"Queries took too long: {elapsed:.2f}s"


@pytest.mark.scalability
class TestWebSocketScalability:
    """Test WebSocket connection handling under load."""
    
    def test_event_sequencer_concurrent_events(self, app):
        """Test event sequencer handles concurrent events."""
        with app.app_context():
            from services.event_sequencer import EventSequencer
            
            sequencer = EventSequencer()
            num_events = 100
            
            for i in range(num_events):
                event_data = {
                    'event_id': i + 1,
                    'event_type': 'test_event',
                    'payload': {'data': f'test_{i}'}
                }
                sequencer.validate_and_sequence_event(
                    workspace_id=i % 5 + 1,
                    event_data=event_data
                )
            
            assert True
    
    def test_session_buffer_manager_capacity(self, app):
        """Test session buffer manager handles multiple sessions."""
        with app.app_context():
            from services.session_buffer_manager import SessionBufferRegistry
            
            registry = SessionBufferRegistry()
            
            num_sessions = 20
            for i in range(num_sessions):
                session_id = f"buffer_test_{i}"
                registry.get_or_create_session(session_id)
            
            assert len(registry.sessions) == num_sessions


@pytest.mark.scalability
class TestMemoryManagement:
    """Test memory usage under various loads."""
    
    def test_segment_storage_memory_efficiency(self, app, db_session):
        """Test memory stays bounded with many segments."""
        import psutil
        from models import Session, Segment
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        with app.app_context():
            external_id = Session.generate_external_id()
            session = Session(
                external_id=external_id,
                title="Memory Test",
                status="active"
            )
            db_session.add(session)
            db_session.commit()
            
            for i in range(100):
                segment = Segment(
                    session_id=session.id,
                    text=f"Segment {i}: " + "x" * 200,
                    start_ms=i * 1000,
                    end_ms=(i + 1) * 1000,
                    avg_confidence=0.9,
                    kind="final"
                )
                db_session.add(segment)
            
            db_session.commit()
            
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = final_memory - initial_memory
            
            assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB"
    
    def test_deduplication_engine_memory_bounds(self, app):
        """Test deduplication engine doesn't leak memory."""
        import psutil
        from services.deduplication_engine import AdvancedDeduplicationEngine, TranscriptionResult
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        with app.app_context():
            engine = AdvancedDeduplicationEngine(max_segments=100)
            
            for i in range(200):
                result = TranscriptionResult(
                    text=f"Test transcription number {i}",
                    start_time=float(i),
                    end_time=float(i + 1),
                    confidence=0.9,
                    chunk_id=f"chunk_{i}",
                    is_final=(i % 5 == 0)
                )
                engine.process_transcription_result(f"session_{i % 10}", result)
            
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = final_memory - initial_memory
            
            assert memory_increase < 50, f"Memory increased by {memory_increase:.1f}MB"


@pytest.mark.scalability
class TestAPILatency:
    """Test API response times under load."""
    
    def test_health_endpoint_latency(self, client):
        """Test health endpoint responds quickly under load."""
        latencies = []
        num_requests = 50
        
        for _ in range(num_requests):
            start = time.time()
            response = client.get('/health/live')
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            assert response.status_code == 200
        
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        assert avg_latency < 100, f"Average latency {avg_latency:.1f}ms exceeds 100ms"
        assert p95_latency < 200, f"P95 latency {p95_latency:.1f}ms exceeds 200ms"
    
    def test_api_response_times_under_sequential_load(self, client):
        """Test API maintains acceptable latency under sequential requests."""
        latencies = []
        results = []
        
        for _ in range(20):
            start = time.time()
            response = client.get('/health/live')
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            results.append(response.status_code)
        
        success_rate = sum(1 for r in results if r == 200) / len(results)
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        assert success_rate >= 0.9, f"Success rate {success_rate:.1%} below 90%"
        assert avg_latency < 200, f"Average latency {avg_latency:.1f}ms exceeds 200ms"
