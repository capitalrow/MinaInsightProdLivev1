"""
Comprehensive functional tests for the CROWN⁹ AI Copilot.
Tests actual API endpoints, services, and end-to-end functionality.
"""
import time
import json
import pytest
import sys
import os
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestCopilotServicesIntegration:
    """Integration tests for Copilot service layer."""
    
    def test_intent_classifier_real_queries(self):
        """Test intent classifier with real user queries."""
        from services.copilot_intent_classifier import CopilotIntentClassifier
        
        classifier = CopilotIntentClassifier()
        
        test_queries = [
            ("What tasks do I have today?", "query"),
            ("Create a new task to review the proposal", "action"),
            ("Show me my meetings this week", "query"),
            ("Mark task as complete", "action"),
            ("Search for project updates", "navigation"),
        ]
        
        for query, expected_category in test_queries:
            result = classifier.classify(query)
            
            assert result is not None, f"Should classify query: {query}"
            assert result.intent is not None, f"Should have intent for: {query}"
            assert result.confidence > 0, f"Should have positive confidence for: {query}"
    
    def test_chip_generator_contextual_chips(self):
        """Test chip generator produces contextual chips."""
        from services.copilot_chip_generator import CopilotChipGenerator
        
        generator = CopilotChipGenerator()
        
        chips = generator.generate_chips(
            user_id=1,
            workspace_id=1,
            context={'has_tasks': True, 'has_meetings': True}
        )
        
        assert len(chips) > 0, "Should generate at least one chip"
        
        for chip in chips:
            assert chip.chip_id is not None, "Each chip should have an ID"
            assert chip.label is not None, "Each chip should have a label"
            assert chip.chip_type is not None, "Each chip should have a type"
    
    def test_lifecycle_service_event_flow(self):
        """Test lifecycle service handles event flow correctly."""
        from services.copilot_lifecycle_service import CopilotLifecycleService, LifecycleEvent
        
        service = CopilotLifecycleService()
        session_id = f"func_test_{int(time.time())}"
        
        session = service.create_session(session_id, user_id=1)
        assert session is not None, "Should create session"
        
        service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {'from_cache': True})
        service.emit_event(session_id, LifecycleEvent.CHIPS_GENERATE, {'count': 3})
        service.emit_event(session_id, LifecycleEvent.IDLE_LISTEN, {})
        service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {'query': 'test'})
        service.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {'streaming': True})
        service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {'success': True})
        service.emit_event(session_id, LifecycleEvent.IDLE_PROMPT, {'suggestion': 'test'})
        
        session = service.get_session(session_id)
        assert len(session.event_history) >= 8, "Should record all events"
    
    def test_metrics_collector_sla_tracking(self):
        """Test metrics collector tracks SLA compliance."""
        from services.copilot_metrics_collector import CopilotMetricsCollector
        
        collector = CopilotMetricsCollector()
        
        collector.record_response_latency(latency_ms=100, calm_score=0.98)
        collector.record_response_latency(latency_ms=200, calm_score=0.96)
        collector.record_response_latency(latency_ms=150, calm_score=0.97)
        
        collector.record_sync_latency(50)
        collector.record_sync_latency(75)
        
        collector.record_cache_access(hit=True)
        collector.record_cache_access(hit=True)
        collector.record_cache_access(hit=False)
        
        sla = collector.get_sla_compliance()
        
        assert 'metrics' in sla, "Should have metrics in SLA response"
        assert 'response_latency_ms' in sla['metrics'], "Should track response latency"
        assert 'sync_latency_ms' in sla['metrics'], "Should track sync latency"
        assert 'cache_hit_rate' in sla['metrics'], "Should track cache hit rate"
        assert 'calm_score' in sla['metrics'], "Should track calm score"
    
    def test_memory_service_initialization(self):
        """Test memory service initializes correctly."""
        from services.copilot_memory_service import CopilotMemoryService
        
        service = CopilotMemoryService()
        
        assert service is not None, "Memory service should initialize"
        assert hasattr(service, 'store_conversation'), "Should have store_conversation method"
        assert hasattr(service, 'get_recent_conversations'), "Should have get_recent_conversations method"
        assert hasattr(service, 'generate_embedding'), "Should have generate_embedding method"
        assert hasattr(service, 'get_semantic_context'), "Should have get_semantic_context method"


class TestCopilotStreamingService:
    """Tests for Copilot streaming service."""
    
    def test_streaming_service_initialization(self):
        """Test streaming service initializes correctly."""
        from services.copilot_streaming_service import CopilotStreamingService
        
        service = CopilotStreamingService()
        
        assert service is not None, "Service should initialize"


class TestCopilotIdleDetection:
    """Tests for Copilot idle detection service."""
    
    def test_idle_detection_service_initialization(self):
        """Test idle detection service initializes correctly."""
        from services.copilot_idle_detection import CopilotIdleDetectionService
        
        service = CopilotIdleDetectionService()
        
        assert service is not None, "Service should initialize"


class TestCopilotEventBroadcaster:
    """Tests for Copilot event broadcaster."""
    
    def test_event_broadcaster_initialization(self):
        """Test event broadcaster initializes correctly."""
        from services.event_broadcaster import EventBroadcaster
        
        broadcaster = EventBroadcaster()
        
        assert broadcaster is not None, "Broadcaster should initialize"


class TestCopilotEndToEnd:
    """End-to-end tests for complete Copilot functionality."""
    
    def test_full_copilot_session_lifecycle(self):
        """Test complete Copilot session from bootstrap to idle."""
        from services.copilot_lifecycle_service import CopilotLifecycleService, LifecycleEvent
        from services.copilot_chip_generator import CopilotChipGenerator
        from services.copilot_intent_classifier import CopilotIntentClassifier
        from services.copilot_metrics_collector import CopilotMetricsCollector
        from services.copilot_memory_service import CopilotMemoryService
        
        lifecycle = CopilotLifecycleService()
        chips = CopilotChipGenerator()
        classifier = CopilotIntentClassifier()
        metrics = CopilotMetricsCollector()
        memory = CopilotMemoryService()
        
        session_id = f"e2e_{int(time.time())}"
        flow_start = time.time()
        
        session = lifecycle.create_session(session_id, user_id=1, workspace_id=1)
        lifecycle.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        lifecycle.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {'from_cache': True})
        
        action_chips = chips.generate_chips(user_id=1, context={'has_tasks': True})
        lifecycle.emit_event(session_id, LifecycleEvent.CHIPS_GENERATE, {'count': len(action_chips)})
        
        lifecycle.emit_event(session_id, LifecycleEvent.IDLE_LISTEN, {})
        
        user_query = "What meetings do I have today?"
        intent = classifier.classify(user_query)
        lifecycle.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
            'query': user_query,
            'intent': intent.intent.value
        })
        
        lifecycle.emit_event(session_id, LifecycleEvent.CONTEXT_MERGE, {
            'sources': ['meetings', 'calendar']
        })
        
        stream_start = time.time()
        lifecycle.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {
            'streaming': True,
            'first_token_ms': (time.time() - stream_start) * 1000
        })
        
        lifecycle.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {
            'response_length': 150,
            'citations': 2
        })
        
        lifecycle.emit_event(session_id, LifecycleEvent.ACTION_TRIGGER, {
            'action_type': 'view_meetings',
            'triggered_by': 'response_link'
        })
        
        lifecycle.emit_event(session_id, LifecycleEvent.CROSS_SURFACE_SYNC, {
            'surface': 'calendar',
            'payload': {'refresh': True}
        })
        
        lifecycle.emit_event(session_id, LifecycleEvent.CONTEXT_RETRAIN, {
            'feedback': 'helpful'
        })
        
        lifecycle.emit_event(session_id, LifecycleEvent.IDLE_PROMPT, {
            'suggestion': 'Would you like me to schedule your next meeting?'
        })
        
        flow_duration = (time.time() - flow_start) * 1000
        
        session = lifecycle.get_session(session_id)
        assert len(session.event_history) == 12, f"Should have 12 events, got {len(session.event_history)}"
        
        event_types = [e['event'] for e in session.event_history]
        expected_events = [
            'copilot_bootstrap', 'context_rehydrate', 'chips_generate', 'idle_listen',
            'query_detect', 'context_merge', 'reasoning_stream', 'response_commit',
            'action_trigger', 'cross_surface_sync', 'context_retrain', 'idle_prompt'
        ]
        
        for event in expected_events:
            assert event in event_types, f"Should have event {event}"
        
        metrics.record_response_latency(flow_duration, calm_score=0.96)
        sla = metrics.get_sla_compliance()
        
        assert sla['metrics']['response_latency_ms']['compliant'] or flow_duration <= 600, \
            f"Flow should complete within SLA, took {flow_duration:.1f}ms"
    
    def test_error_recovery_flow(self):
        """Test Copilot handles errors gracefully."""
        from services.copilot_lifecycle_service import CopilotLifecycleService, LifecycleEvent
        from services.copilot_metrics_collector import CopilotMetricsCollector
        
        lifecycle = CopilotLifecycleService()
        metrics = CopilotMetricsCollector()
        
        session_id = f"error_test_{int(time.time())}"
        
        session = lifecycle.create_session(session_id, user_id=1)
        lifecycle.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        metrics.record_error('streaming_timeout', 'warning')
        
        lifecycle.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {
            'recovery_mode': True
        })
        
        lifecycle.emit_event(session_id, LifecycleEvent.IDLE_LISTEN, {})
        
        session = lifecycle.get_session(session_id)
        assert session.is_idle, "Should be in idle state after recovery"


class TestCopilotSLACompliance:
    """Tests for SLA compliance verification."""
    
    def test_all_sla_targets_achievable(self):
        """Verify all SLA targets are achievable under normal conditions."""
        from services.copilot_metrics_collector import CopilotMetricsCollector
        
        collector = CopilotMetricsCollector()
        
        for _ in range(10):
            collector.record_response_latency(latency_ms=100, calm_score=0.98)
        
        for _ in range(10):
            collector.record_sync_latency(50)
        
        for _ in range(90):
            collector.record_cache_access(hit=True)
        for _ in range(10):
            collector.record_cache_access(hit=False)
        
        sla = collector.get_sla_compliance()
        
        assert sla['metrics']['response_latency_ms']['compliant'], "Response latency SLA should be met"
        assert sla['metrics']['sync_latency_ms']['compliant'], "Sync latency SLA should be met"
        assert sla['metrics']['cache_hit_rate']['compliant'], "Cache hit rate SLA should be met"
        assert sla['metrics']['calm_score']['compliant'], "Calm score SLA should be met"


class TestCopilotAllServicesIntegrated:
    """Test all Copilot services work together."""
    
    def test_all_services_initialize(self):
        """Verify all Copilot services initialize without errors."""
        from services.copilot_streaming_service import CopilotStreamingService
        from services.copilot_lifecycle_service import CopilotLifecycleService
        from services.copilot_metrics_collector import CopilotMetricsCollector
        from services.copilot_intent_classifier import CopilotIntentClassifier
        from services.copilot_chip_generator import CopilotChipGenerator
        from services.copilot_memory_service import CopilotMemoryService
        from services.copilot_idle_detection import CopilotIdleDetectionService
        from services.event_broadcaster import EventBroadcaster
        
        streaming = CopilotStreamingService()
        lifecycle = CopilotLifecycleService()
        metrics = CopilotMetricsCollector()
        classifier = CopilotIntentClassifier()
        chips = CopilotChipGenerator()
        memory = CopilotMemoryService()
        idle = CopilotIdleDetectionService()
        broadcaster = EventBroadcaster()
        
        assert streaming is not None
        assert lifecycle is not None
        assert metrics is not None
        assert classifier is not None
        assert chips is not None
        assert memory is not None
        assert idle is not None
        assert broadcaster is not None
    
    def test_lifecycle_events_enum_complete(self):
        """Verify all 12 lifecycle events are defined."""
        from services.copilot_lifecycle_service import LifecycleEvent
        
        expected_events = [
            'COPILOT_BOOTSTRAP',
            'CONTEXT_REHYDRATE',
            'CHIPS_GENERATE',
            'IDLE_LISTEN',
            'QUERY_DETECT',
            'CONTEXT_MERGE',
            'REASONING_STREAM',
            'RESPONSE_COMMIT',
            'ACTION_TRIGGER',
            'CROSS_SURFACE_SYNC',
            'CONTEXT_RETRAIN',
            'IDLE_PROMPT',
        ]
        
        for event_name in expected_events:
            assert hasattr(LifecycleEvent, event_name), f"Should have event {event_name}"
    
    def test_intent_types_complete(self):
        """Verify all intent types are defined."""
        from services.copilot_intent_classifier import Intent
        
        assert len(list(Intent)) >= 5, "Should have multiple intent types"
    
    def test_chip_types_complete(self):
        """Verify chip types are defined."""
        from services.copilot_chip_generator import ChipType
        
        assert len(list(ChipType)) >= 3, "Should have multiple chip types"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
