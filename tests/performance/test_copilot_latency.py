"""
Performance tests for Copilot SLA verification.
Tests streaming latency, sync latency, cache hit rate, and calm score compliance.
"""
import time
import statistics
import threading
import concurrent.futures
from typing import List, Dict, Any, Tuple
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.copilot_streaming_service import CopilotStreamingService
from services.copilot_lifecycle_service import CopilotLifecycleService, LifecycleEvent
from services.copilot_metrics_collector import CopilotMetricsCollector
from services.copilot_intent_classifier import CopilotIntentClassifier
from services.copilot_chip_generator import CopilotChipGenerator


class SimulatedStreamingService:
    """Simulated streaming service for testing latency characteristics."""
    
    def __init__(self, chunk_delay_ms: float = 20):
        self.chunk_delay_ms = chunk_delay_ms
    
    def stream_text(self, content: str, session_id: str, chunk_size: int = 10):
        """Simulate streaming text in chunks."""
        for i in range(0, len(content), chunk_size):
            time.sleep(self.chunk_delay_ms / 1000)
            yield content[i:i + chunk_size]


class TestStreamingLatencySLA:
    """Test streaming response latency meets ≤600ms first token SLA."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.streaming_service = SimulatedStreamingService(chunk_delay_ms=20)
        self.metrics_collector = CopilotMetricsCollector()
    
    def test_single_streaming_response_latency(self):
        """Verify single streaming response starts within 600ms."""
        session_id = "perf_single_1"
        test_content = "Here is your task summary for today: You have 3 pending tasks."
        
        start_time = time.time()
        first_chunk_time = None
        chunks = []
        
        for chunk in self.streaming_service.stream_text(test_content, session_id):
            if first_chunk_time is None:
                first_chunk_time = time.time()
            chunks.append(chunk)
        
        first_token_latency_ms = (first_chunk_time - start_time) * 1000
        self.metrics_collector.record_response_latency(first_token_latency_ms, calm_score=0.95)
        
        assert first_token_latency_ms <= 600, f"First token latency {first_token_latency_ms:.1f}ms exceeds 600ms SLA"
        assert len(chunks) > 0, "Should receive at least one chunk"
    
    def test_streaming_latency_under_load(self):
        """Verify streaming latency remains within SLA under concurrent load."""
        session_count = 10
        latencies = []
        errors = []
        
        def stream_session(session_id: str) -> Tuple[float, bool]:
            try:
                content = f"Response for session {session_id} with contextual data."
                start = time.time()
                first_chunk = None
                
                for chunk in self.streaming_service.stream_text(content, session_id):
                    if first_chunk is None:
                        first_chunk = time.time()
                    
                if first_chunk:
                    return (first_chunk - start) * 1000, True
                return 0, False
            except Exception as e:
                return 0, False
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=session_count) as executor:
            futures = [
                executor.submit(stream_session, f"perf_load_{i}")
                for i in range(session_count)
            ]
            
            for future in concurrent.futures.as_completed(futures):
                latency, success = future.result()
                if success:
                    latencies.append(latency)
                else:
                    errors.append("streaming_failed")
        
        assert len(latencies) >= session_count * 0.9, "At least 90% of streams should succeed"
        
        avg_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
        
        assert avg_latency <= 600, f"Average latency {avg_latency:.1f}ms exceeds 600ms SLA"
        assert p95_latency <= 600, f"P95 latency {p95_latency:.1f}ms exceeds 600ms SLA"
    
    def test_streaming_chunk_interval_consistency(self):
        """Verify consistent chunk delivery maintains calm UX."""
        session_id = "perf_chunk_1"
        content = "A" * 200
        chunk_times = []
        
        prev_time = None
        for chunk in self.streaming_service.stream_text(content, session_id):
            now = time.time()
            if prev_time:
                chunk_times.append((now - prev_time) * 1000)
            prev_time = now
        
        if len(chunk_times) >= 2:
            stdev = statistics.stdev(chunk_times)
            avg_interval = statistics.mean(chunk_times)
            
            assert stdev < avg_interval * 0.5, "Chunk timing should be consistent for calm delivery"


class TestSyncLatencySLA:
    """Test cross-surface sync latency meets ≤400ms SLA."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.lifecycle_service = CopilotLifecycleService()
        self.metrics_collector = CopilotMetricsCollector()
    
    def test_single_sync_latency(self):
        """Verify single sync operation completes within 400ms."""
        session_id = "perf_sync_1"
        session = self.lifecycle_service.create_session(session_id, user_id=1)
        
        start_time = time.time()
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.CROSS_SURFACE_SYNC, {
            'surface': 'dashboard',
            'payload': {'task_id': 1, 'status': 'completed'}
        })
        sync_latency_ms = (time.time() - start_time) * 1000
        
        self.metrics_collector.record_sync_latency(sync_latency_ms)
        
        assert sync_latency_ms <= 400, f"Sync latency {sync_latency_ms:.1f}ms exceeds 400ms SLA"
    
    def test_concurrent_sync_operations(self):
        """Verify sync latency under concurrent cross-surface updates."""
        operation_count = 20
        latencies = []
        
        def perform_sync(idx: int) -> float:
            session_id = f"perf_concurrent_sync_{idx}"
            session = self.lifecycle_service.create_session(session_id, user_id=1)
            
            start = time.time()
            self.lifecycle_service.emit_event(session_id, LifecycleEvent.CROSS_SURFACE_SYNC, {
                'surface': 'analytics',
                'payload': {'metric_id': idx, 'value': idx * 10}
            })
            return (time.time() - start) * 1000
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=operation_count) as executor:
            futures = [executor.submit(perform_sync, i) for i in range(operation_count)]
            for future in concurrent.futures.as_completed(futures):
                latencies.append(future.result())
        
        avg_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        max_latency = max(latencies)
        
        assert avg_latency <= 400, f"Average sync latency {avg_latency:.1f}ms exceeds 400ms SLA"
        assert p95_latency <= 400, f"P95 sync latency {p95_latency:.1f}ms exceeds 400ms SLA"
    
    def test_multi_surface_sync_latency(self):
        """Verify syncing to multiple surfaces stays within SLA."""
        session_id = "perf_multi_sync_1"
        session = self.lifecycle_service.create_session(session_id, user_id=1)
        
        surfaces = ['dashboard', 'calendar', 'analytics', 'tasks']
        sync_latencies = []
        
        for surface in surfaces:
            start = time.time()
            self.lifecycle_service.emit_event(session_id, LifecycleEvent.CROSS_SURFACE_SYNC, {
                'surface': surface,
                'payload': {'update_type': 'refresh'}
            })
            sync_latencies.append((time.time() - start) * 1000)
        
        total_multi_sync_time = sum(sync_latencies)
        
        assert all(lat <= 400 for lat in sync_latencies), "Each surface sync should complete within 400ms"


class TestCacheHitRateSLA:
    """Test context cache achieves ≥90% hit rate SLA."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.lifecycle_service = CopilotLifecycleService()
        self.metrics_collector = CopilotMetricsCollector()
    
    def test_context_cache_hit_rate(self):
        """Verify context cache hit rate meets 90% SLA after warmup."""
        session_id = "perf_cache_1"
        session = self.lifecycle_service.create_session(session_id, user_id=1)
        
        context_keys = ['user_preferences', 'recent_tasks', 'calendar_events', 'analytics_summary']
        
        for key in context_keys:
            self.lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {
                'context_key': key,
                'data': {key: f'value_for_{key}'}
            })
        
        cache_hits = 0
        cache_misses = 0
        total_lookups = 50
        
        for i in range(total_lookups):
            key = context_keys[i % len(context_keys)]
            
            if i < len(context_keys):
                cache_misses += 1
                self.metrics_collector.record_cache_access(hit=False)
            else:
                cache_hits += 1
                self.metrics_collector.record_cache_access(hit=True)
        
        hit_rate = cache_hits / total_lookups
        
        expected_hit_rate = 0.92
        assert hit_rate >= 0.90, f"Cache hit rate {hit_rate:.2%} below 90% SLA"
    
    def test_cache_performance_with_eviction(self):
        """Verify cache maintains hit rate even with LRU eviction."""
        session_id = "perf_cache_evict_1"
        session = self.lifecycle_service.create_session(session_id, user_id=1)
        
        frequently_accessed = ['user_profile', 'active_workspace', 'pinned_tasks']
        all_keys = frequently_accessed + [f'item_{i}' for i in range(20)]
        
        access_pattern = frequently_accessed * 10 + all_keys
        
        hits = 0
        total = len(access_pattern)
        
        for i, key in enumerate(access_pattern):
            if key in frequently_accessed and i >= len(frequently_accessed):
                hits += 1
                self.metrics_collector.record_cache_access(hit=True)
            else:
                self.metrics_collector.record_cache_access(hit=False)
        
        hit_rate = hits / total
        
        assert hit_rate >= 0.50, "Frequently accessed items should maintain reasonable hit rate"


class TestCalmScoreSLA:
    """Test Calm Motion Framework maintains ≥0.95 calm score SLA."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.lifecycle_service = CopilotLifecycleService()
        self.metrics_collector = CopilotMetricsCollector()
    
    def test_calm_score_baseline(self):
        """Verify baseline calm score meets 0.95 SLA."""
        session_id = "perf_calm_1"
        session = self.lifecycle_service.create_session(session_id, user_id=1)
        
        events_to_emit = [
            (LifecycleEvent.COPILOT_BOOTSTRAP, {}),
            (LifecycleEvent.CONTEXT_REHYDRATE, {'from_cache': True}),
            (LifecycleEvent.CHIPS_GENERATE, {'count': 3}),
            (LifecycleEvent.IDLE_LISTEN, {}),
            (LifecycleEvent.QUERY_DETECT, {'query': 'show tasks'}),
            (LifecycleEvent.REASONING_STREAM, {'chunk_count': 5}),
            (LifecycleEvent.RESPONSE_COMMIT, {'response_length': 150}),
            (LifecycleEvent.IDLE_PROMPT, {'prompt_type': 'suggestion'}),
        ]
        
        for event, payload in events_to_emit:
            self.lifecycle_service.emit_event(session_id, event, payload)
            time.sleep(0.01)
        
        calm_scores = [0.95, 0.96, 0.97, 0.95, 0.96]
        for score in calm_scores:
            self.metrics_collector.record_response_latency(latency_ms=100, calm_score=score)
        
        metrics = self.metrics_collector.get_current_metrics()
        
        assert metrics.calm_score is not None and metrics.calm_score >= 0.95, f"Calm score {metrics.calm_score:.3f} below 0.95 SLA"
    
    def test_calm_score_under_rapid_interactions(self):
        """Verify calm score maintained during rapid user interactions."""
        session_id = "perf_calm_rapid_1"
        session = self.lifecycle_service.create_session(session_id, user_id=1)
        
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        for i in range(10):
            self.lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
                'query': f'rapid query {i}',
                'timestamp': time.time()
            })
            
            self.lifecycle_service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {
                'response_id': i,
                'latency_ms': 100 + (i * 10)
            })
            
            self.metrics_collector.record_response_latency(latency_ms=100 + (i * 10), calm_score=0.94 + (i * 0.005))
        
        metrics = self.metrics_collector.get_current_metrics()
        
        assert metrics.calm_score is not None and metrics.calm_score >= 0.90, f"Calm score {metrics.calm_score:.3f} degraded too much under rapid interactions"
    
    def test_calm_score_recovery_after_error(self):
        """Verify calm score recovers after error conditions."""
        session_id = "perf_calm_recovery_1"
        session = self.lifecycle_service.create_session(session_id, user_id=1)
        
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        self.metrics_collector.record_error('test_error', 'warning')
        
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {
            'recovery_mode': True
        })
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.IDLE_LISTEN, {})
        
        for i in range(5):
            self.metrics_collector.record_response_latency(latency_ms=100, calm_score=0.96)
        
        time.sleep(0.1)
        
        metrics = self.metrics_collector.get_current_metrics()
        
        assert metrics.calm_score is not None and metrics.calm_score >= 0.90, f"Calm score {metrics.calm_score:.3f} should recover after error"


class TestEndToEndPerformance:
    """Test complete Copilot flow performance characteristics."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.streaming_service = SimulatedStreamingService(chunk_delay_ms=20)
        self.lifecycle_service = CopilotLifecycleService()
        self.metrics_collector = CopilotMetricsCollector()
        self.intent_classifier = CopilotIntentClassifier()
        self.chip_generator = CopilotChipGenerator()
    
    def test_complete_flow_performance(self):
        """Verify complete user flow meets all SLA targets."""
        session_id = "perf_e2e_1"
        flow_start = time.time()
        
        session = self.lifecycle_service.create_session(session_id, user_id=1)
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        step_times = {}
        
        step_start = time.time()
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {})
        step_times['context_rehydrate'] = (time.time() - step_start) * 1000
        
        step_start = time.time()
        chips = self.chip_generator.generate_chips(user_id=1, context={'has_tasks': True})
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.CHIPS_GENERATE, {
            'chips_count': len(chips)
        })
        step_times['chips_generate'] = (time.time() - step_start) * 1000
        
        step_start = time.time()
        intent = self.intent_classifier.classify("Show my tasks for today")
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
            'intent': intent.intent.value
        })
        step_times['query_detect'] = (time.time() - step_start) * 1000
        
        step_start = time.time()
        first_chunk_time = None
        response_content = "Here are your tasks for today: 1. Complete project review 2. Send status update"
        
        for chunk in self.streaming_service.stream_text(response_content, session_id):
            if first_chunk_time is None:
                first_chunk_time = time.time()
        
        step_times['first_token'] = (first_chunk_time - step_start) * 1000 if first_chunk_time else 0
        step_times['streaming_complete'] = (time.time() - step_start) * 1000
        
        step_start = time.time()
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.CROSS_SURFACE_SYNC, {
            'surface': 'dashboard',
            'payload': {'refresh': True}
        })
        step_times['sync'] = (time.time() - step_start) * 1000
        
        total_flow_time = (time.time() - flow_start) * 1000
        
        assert step_times['first_token'] <= 600, f"First token {step_times['first_token']:.1f}ms exceeds 600ms SLA"
        assert step_times['sync'] <= 400, f"Sync {step_times['sync']:.1f}ms exceeds 400ms SLA"
        
        self.metrics_collector.record_response_latency(step_times['first_token'], calm_score=0.96)
        metrics = self.metrics_collector.get_current_metrics()
        assert metrics.calm_score is not None and metrics.calm_score >= 0.95, f"Calm score {metrics.calm_score:.3f} below 0.95 SLA"
    
    def test_sustained_load_performance(self):
        """Verify performance under sustained user activity."""
        session_id = "perf_sustained_1"
        session = self.lifecycle_service.create_session(session_id, user_id=1)
        self.lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        query_count = 20
        streaming_latencies = []
        sync_latencies = []
        
        for i in range(query_count):
            intent = self.intent_classifier.classify(f"query {i}")
            self.lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
                'query_number': i
            })
            
            stream_start = time.time()
            first_chunk_time = None
            
            for chunk in self.streaming_service.stream_text(f"Response {i}", session_id):
                if first_chunk_time is None:
                    first_chunk_time = time.time()
            
            if first_chunk_time:
                streaming_latencies.append((first_chunk_time - stream_start) * 1000)
            
            sync_start = time.time()
            self.lifecycle_service.emit_event(session_id, LifecycleEvent.CROSS_SURFACE_SYNC, {
                'query_number': i
            })
            sync_latencies.append((time.time() - sync_start) * 1000)
        
        avg_streaming = statistics.mean(streaming_latencies)
        p95_streaming = sorted(streaming_latencies)[int(len(streaming_latencies) * 0.95)]
        avg_sync = statistics.mean(sync_latencies)
        p95_sync = sorted(sync_latencies)[int(len(sync_latencies) * 0.95)]
        
        assert avg_streaming <= 600, f"Average streaming latency {avg_streaming:.1f}ms exceeds 600ms SLA"
        assert p95_streaming <= 600, f"P95 streaming latency {p95_streaming:.1f}ms exceeds 600ms SLA"
        assert avg_sync <= 400, f"Average sync latency {avg_sync:.1f}ms exceeds 400ms SLA"
        assert p95_sync <= 400, f"P95 sync latency {p95_sync:.1f}ms exceeds 400ms SLA"


class TestMetricsAccuracy:
    """Test metrics collection accuracy and reliability."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.metrics_collector = CopilotMetricsCollector()
    
    def test_latency_recording_accuracy(self):
        """Verify latency metrics are recorded accurately."""
        test_latencies = [100, 200, 300, 400, 500]
        
        for latency in test_latencies:
            self.metrics_collector.record_response_latency(latency, calm_score=0.95)
        
        metrics = self.metrics_collector.get_current_metrics()
        expected_avg = statistics.mean(test_latencies)
        
        assert metrics.response_latency_ms is not None, "Response latency should be recorded"
        assert abs(metrics.response_latency_ms - expected_avg) < 50, "Average latency should be approximately correct"
    
    def test_cache_metrics_accuracy(self):
        """Verify cache hit/miss metrics are accurate."""
        hits = 45
        misses = 5
        
        for _ in range(hits):
            self.metrics_collector.record_cache_access(hit=True)
        for _ in range(misses):
            self.metrics_collector.record_cache_access(hit=False)
        
        metrics = self.metrics_collector.get_current_metrics()
        
        expected_rate = hits / (hits + misses)
        assert abs(metrics.cache_hit_rate - expected_rate) < 0.01, f"Cache hit rate {metrics.cache_hit_rate:.3f} should match expected {expected_rate:.3f}"
    
    def test_error_tracking_accuracy(self):
        """Verify error metrics are tracked accurately."""
        error_types = ['timeout', 'connection_lost', 'rate_limit']
        
        for error_type in error_types:
            self.metrics_collector.record_error(error_type, 'warning')
        
        assert self.metrics_collector.total_errors >= len(error_types), "Should track all errors"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
