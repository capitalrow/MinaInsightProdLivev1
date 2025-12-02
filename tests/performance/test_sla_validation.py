"""
SLA Validation Tests
Tests to verify performance meets Service Level Agreement targets.
"""
import pytest
import time
import psutil
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed


@pytest.mark.performance
class TestTranscriptionSLA:
    """Test transcription latency meets SLA targets."""
    
    def test_transcription_latency_under_400ms(self, app):
        """Verify transcription processing latency is under 400ms SLA."""
        with app.app_context():
            from services.deduplication_engine import AdvancedDeduplicationEngine, TranscriptionResult
            
            engine = AdvancedDeduplicationEngine()
            latencies = []
            
            for i in range(20):
                result = TranscriptionResult(
                    text=f"Test transcription number {i} for latency measurement.",
                    start_time=float(i),
                    end_time=float(i + 1),
                    confidence=0.92,
                    chunk_id=f"latency_chunk_{i}",
                    is_final=True
                )
                
                start = time.time()
                engine.process_transcription_result(f"sla_session_{i}", result)
                latency_ms = (time.time() - start) * 1000
                latencies.append(latency_ms)
            
            avg_latency = statistics.mean(latencies)
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
            
            assert avg_latency < 100, f"Average latency {avg_latency:.1f}ms exceeds 100ms"
            assert p95_latency < 400, f"P95 latency {p95_latency:.1f}ms exceeds 400ms SLA"
    
    def test_vad_processing_speed(self, app):
        """Verify VAD processes audio faster than real-time."""
        import numpy as np
        
        with app.app_context():
            from services.vad_service import VADService
            
            vad = VADService()
            
            sample_rate = 16000
            audio_duration_seconds = 1.0
            samples = int(sample_rate * audio_duration_seconds)
            audio = np.random.randint(-32768, 32767, size=samples, dtype=np.int16)
            audio_bytes = audio.tobytes()
            
            start = time.time()
            for _ in range(10):
                vad.is_voiced(audio_bytes)
            processing_time = time.time() - start
            
            audio_total_seconds = audio_duration_seconds * 10
            rtf = processing_time / audio_total_seconds
            
            assert rtf < 1.0, f"VAD Real-Time Factor {rtf:.2f} exceeds 1.0 (not real-time)"


@pytest.mark.performance
class TestDashboardSLA:
    """Test dashboard meets Time-To-Interactive SLA."""
    
    def test_health_endpoint_response_time(self, client):
        """Verify health endpoints respond within 100ms."""
        endpoints = ['/health/live', '/health/ready']
        
        for endpoint in endpoints:
            latencies = []
            for _ in range(10):
                start = time.time()
                response = client.get(endpoint)
                latency_ms = (time.time() - start) * 1000
                latencies.append(latency_ms)
                assert response.status_code == 200
            
            avg_latency = statistics.mean(latencies)
            assert avg_latency < 100, f"{endpoint} average latency {avg_latency:.1f}ms exceeds 100ms"
    
    def test_api_bootstrap_time(self, client):
        """Test API response time for dashboard bootstrap."""
        start = time.time()
        
        responses = []
        responses.append(client.get('/api/health'))
        responses.append(client.get('/health/ready'))
        
        total_time = (time.time() - start) * 1000
        
        assert total_time < 500, f"API bootstrap took {total_time:.1f}ms, exceeds 500ms"


@pytest.mark.performance
class TestWebSocketSLA:
    """Test WebSocket performance meets SLA targets."""
    
    def test_event_sequencer_throughput(self, app):
        """Test event sequencer can handle expected throughput."""
        with app.app_context():
            from services.event_sequencer import EventSequencer
            
            sequencer = EventSequencer()
            num_events = 500
            
            start = time.time()
            for i in range(num_events):
                event_data = {
                    'event_id': i + 1,
                    'type': 'segment',
                    'text': f'Event {i}'
                }
                sequencer.validate_and_sequence_event(
                    workspace_id=(i % 10) + 1,
                    event_data=event_data
                )
            elapsed = time.time() - start
            
            events_per_second = num_events / elapsed if elapsed > 0 else num_events
            
            assert events_per_second > 100, f"Throughput {events_per_second:.1f} events/s below 100"
    
    def test_buffer_manager_latency(self, app):
        """Test buffer manager operations are fast."""
        with app.app_context():
            from services.session_buffer_manager import SessionBufferRegistry
            
            registry = SessionBufferRegistry()
            latencies = []
            
            for i in range(20):
                session_id = f"buffer_sla_{i}"
                
                start = time.time()
                registry.get_or_create_session(session_id)
                latency_ms = (time.time() - start) * 1000
                latencies.append(latency_ms)
            
            avg_latency = statistics.mean(latencies)
            assert avg_latency < 10, f"Buffer operations average {avg_latency:.1f}ms exceeds 10ms"


@pytest.mark.performance
class TestDatabaseSLA:
    """Test database operations meet performance targets."""
    
    def test_query_latency(self, app, db_session):
        """Test database queries complete within SLA."""
        from models import Session
        
        with app.app_context():
            latencies = []
            
            for _ in range(20):
                start = time.time()
                db_session.query(Session).limit(10).all()
                latency_ms = (time.time() - start) * 1000
                latencies.append(latency_ms)
            
            avg_latency = statistics.mean(latencies)
            p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
            
            assert avg_latency < 50, f"Average query latency {avg_latency:.1f}ms exceeds 50ms"
            assert p99_latency < 200, f"P99 query latency {p99_latency:.1f}ms exceeds 200ms"
    
    def test_write_latency(self, app, db_session):
        """Test database writes complete within SLA."""
        from models import Session
        
        with app.app_context():
            latencies = []
            
            for i in range(10):
                external_id = Session.generate_external_id()
                session = Session(
                    external_id=external_id,
                    title=f"SLA Write Test {i}",
                    status="active"
                )
                
                start = time.time()
                db_session.add(session)
                db_session.commit()
                latency_ms = (time.time() - start) * 1000
                latencies.append(latency_ms)
            
            avg_latency = statistics.mean(latencies)
            assert avg_latency < 100, f"Average write latency {avg_latency:.1f}ms exceeds 100ms"


@pytest.mark.performance
class TestResourceUtilization:
    """Test resource usage stays within bounds."""
    
    def test_memory_usage_baseline(self, app):
        """Test memory usage is reasonable at baseline."""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        assert memory_mb < 500, f"Baseline memory {memory_mb:.1f}MB exceeds 500MB"
    
    def test_cpu_usage_idle(self, app):
        """Test CPU usage is low when idle."""
        process = psutil.Process()
        
        cpu_samples = []
        for _ in range(5):
            cpu_samples.append(process.cpu_percent(interval=0.1))
        
        avg_cpu = statistics.mean(cpu_samples)
        assert avg_cpu < 50, f"Idle CPU usage {avg_cpu:.1f}% exceeds 50%"
    
    def test_disk_usage(self):
        """Test disk usage is within acceptable limits."""
        disk = psutil.disk_usage('/')
        
        assert disk.percent < 90, f"Disk usage {disk.percent}% exceeds 90%"


@pytest.mark.performance
class TestConcurrencySLA:
    """Test concurrent operation performance."""
    
    def test_sequential_session_queries(self, app, db_session):
        """Test sequential queries maintain acceptable latency."""
        from models import Session
        
        latencies = []
        num_queries = 10
        
        with app.app_context():
            for _ in range(num_queries):
                start = time.time()
                db_session.query(Session).limit(5).all()
                latency_ms = (time.time() - start) * 1000
                latencies.append(latency_ms)
        
        avg_latency = statistics.mean(latencies) if latencies else 0
        
        assert avg_latency < 200, f"Query average {avg_latency:.1f}ms exceeds 200ms"
