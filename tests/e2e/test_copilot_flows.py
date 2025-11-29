"""
E2E Tests for Copilot User Flows.

Tests the complete narrative flow:
1. greeting → query → streaming → action → sync → idle prompt

Each test validates the emotional coherence and SLA compliance of the full journey.
"""
import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class FlowStep:
    """Represents a step in the E2E flow."""
    name: str
    event_type: str
    expected_duration_ms: float
    data: Dict[str, Any]
    passed: bool = False


class TestCopilotE2EFlows:
    """End-to-end tests for Copilot user flows."""

    @pytest.fixture
    def lifecycle_service(self):
        """Create lifecycle service for testing."""
        from services.copilot_lifecycle_service import CopilotLifecycleService
        return CopilotLifecycleService()

    @pytest.fixture
    def metrics_collector(self):
        """Create metrics collector for testing."""
        from services.copilot_metrics_collector import CopilotMetricsCollector
        return CopilotMetricsCollector()

    @pytest.fixture
    def intent_classifier(self):
        """Create intent classifier for testing."""
        from services.copilot_intent_classifier import CopilotIntentClassifier
        return CopilotIntentClassifier()

    @pytest.fixture
    def chip_generator(self):
        """Create chip generator for testing."""
        from services.copilot_chip_generator import CopilotChipGenerator
        return CopilotChipGenerator()

    def test_complete_task_creation_flow(self, lifecycle_service, metrics_collector, intent_classifier, chip_generator):
        """Test complete flow: greeting → query → task creation → sync."""
        from services.copilot_lifecycle_service import LifecycleEvent
        
        session_id = "e2e_task_flow_1"
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        flow_metrics = {
            'total_duration_ms': 0,
            'steps': []
        }
        flow_start = time.time()
        
        step_1_start = time.time()
        lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {
            'page': 'copilot_chat',
            'context_loaded': True
        })
        step_1_duration = (time.time() - step_1_start) * 1000
        flow_metrics['steps'].append({'step': 'bootstrap', 'duration_ms': step_1_duration})
        
        step_2_start = time.time()
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {
            'time_of_day': 'morning',
            'pending_tasks': 5,
            'greeting_displayed': True
        })
        step_2_duration = (time.time() - step_2_start) * 1000
        flow_metrics['steps'].append({'step': 'greeting', 'duration_ms': step_2_duration})
        
        step_3_start = time.time()
        chips = chip_generator.generate_chips(user_id=1, context={'user_has_tasks': True})
        lifecycle_service.emit_event(session_id, LifecycleEvent.CHIPS_GENERATE, {
            'chips': [{'id': c.chip_id, 'label': c.label} for c in chips[:3]],
            'render_time_ms': (time.time() - step_3_start) * 1000
        })
        step_3_duration = (time.time() - step_3_start) * 1000
        flow_metrics['steps'].append({'step': 'chips_rendered', 'duration_ms': step_3_duration})
        
        step_4_start = time.time()
        user_query = "Create a task to review the quarterly report"
        classification = intent_classifier.classify(user_query)
        lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
            'query': user_query,
            'intent': classification.intent.value,
            'confidence': classification.confidence,
            'entities': classification.entities
        })
        step_4_duration = (time.time() - step_4_start) * 1000
        flow_metrics['steps'].append({'step': 'query_detect', 'duration_ms': step_4_duration})
        
        step_5_start = time.time()
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_MERGE, {
            'sources': ['tasks', 'calendar', 'memory'],
            'merge_complete': True
        })
        step_5_duration = (time.time() - step_5_start) * 1000
        flow_metrics['steps'].append({'step': 'context_merge', 'duration_ms': step_5_duration})
        
        step_6_start = time.time()
        response_chunks = ["I'll ", "create ", "a ", "task ", "to ", "review ", "the ", "quarterly ", "report."]
        for i, chunk in enumerate(response_chunks):
            lifecycle_service.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {
                'chunk_index': i,
                'content': chunk,
                'is_first': i == 0,
                'is_last': i == len(response_chunks) - 1
            })
        step_6_duration = (time.time() - step_6_start) * 1000
        flow_metrics['steps'].append({'step': 'streaming', 'duration_ms': step_6_duration})
        
        step_7_start = time.time()
        metrics_collector.record_response_latency(latency_ms=step_6_duration, calm_score=0.97)
        lifecycle_service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {
            'message_id': 'msg_e2e_1',
            'total_chunks': len(response_chunks),
            'latency_ms': step_6_duration,
            'calm_score': 0.97
        })
        step_7_duration = (time.time() - step_7_start) * 1000
        flow_metrics['steps'].append({'step': 'response_commit', 'duration_ms': step_7_duration})
        
        step_8_start = time.time()
        lifecycle_service.emit_event(session_id, LifecycleEvent.ACTION_TRIGGER, {
            'action_type': 'create_task',
            'action_data': {'task_name': 'Review quarterly report', 'priority': 'medium'},
            'success': True,
            'task_id': 12345
        })
        step_8_duration = (time.time() - step_8_start) * 1000
        flow_metrics['steps'].append({'step': 'action_trigger', 'duration_ms': step_8_duration})
        
        step_9_start = time.time()
        lifecycle_service.emit_event(session_id, LifecycleEvent.CROSS_SURFACE_SYNC, {
            'surfaces': ['dashboard', 'tasks_page', 'calendar'],
            'sync_type': 'task_created',
            'task_id': 12345
        })
        metrics_collector.record_sync_latency(latency_ms=(time.time() - step_9_start) * 1000)
        step_9_duration = (time.time() - step_9_start) * 1000
        flow_metrics['steps'].append({'step': 'cross_surface_sync', 'duration_ms': step_9_duration})
        
        step_10_start = time.time()
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_RETRAIN, {
            'embeddings_updated': True,
            'interaction_recorded': True
        })
        step_10_duration = (time.time() - step_10_start) * 1000
        flow_metrics['steps'].append({'step': 'context_retrain', 'duration_ms': step_10_duration})
        
        flow_metrics['total_duration_ms'] = (time.time() - flow_start) * 1000
        
        assert session.event_history, "Event history should not be empty"
        assert len(session.event_history) >= 10, f"Expected at least 10 events, got {len(session.event_history)}"
        
        events_captured = [e['event'] for e in session.event_history]
        expected_events = [
            'copilot_bootstrap', 'context_rehydrate', 'chips_generate',
            'query_detect', 'context_merge', 'reasoning_stream', 'response_commit',
            'action_trigger', 'cross_surface_sync', 'context_retrain'
        ]
        
        for expected in expected_events:
            assert expected in events_captured, f"Missing event: {expected}"
        
        metrics = metrics_collector.get_current_metrics()
        assert metrics.response_latency_ms is not None
        assert metrics.sync_latency_ms is not None

    def test_query_to_streaming_response_flow(self, lifecycle_service, intent_classifier, metrics_collector):
        """Test flow: query detection → streaming response → commit."""
        from services.copilot_lifecycle_service import LifecycleEvent
        
        session_id = "e2e_streaming_flow_1"
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        query = "What meetings do I have today?"
        classification = intent_classifier.classify(query)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
            'query': query,
            'intent': classification.intent.value,
            'confidence': classification.confidence
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_MERGE, {
            'sources': ['calendar', 'memory']
        })
        
        streaming_start = time.time()
        response = "You have 3 meetings today: Team standup at 9am, Design review at 2pm, and Sprint planning at 4pm."
        chunks = response.split()
        
        for i, chunk in enumerate(chunks):
            lifecycle_service.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {
                'chunk': chunk + " ",
                'is_first': i == 0,
                'is_last': i == len(chunks) - 1
            })
        
        streaming_duration = (time.time() - streaming_start) * 1000
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {
            'full_response': response,
            'latency_ms': streaming_duration,
            'calm_score': 0.98
        })
        
        metrics_collector.record_response_latency(latency_ms=streaming_duration, calm_score=0.98)
        
        assert len(session.event_history) >= 3 + len(chunks)
        
        reasoning_events = [e for e in session.event_history if e['event'] == 'reasoning_stream']
        assert len(reasoning_events) == len(chunks)

    def test_idle_to_prompt_flow(self, lifecycle_service):
        """Test flow: user goes idle → idle prompt triggered."""
        from services.copilot_lifecycle_service import LifecycleEvent
        
        session_id = "e2e_idle_flow_1"
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {
            'page': 'copilot_chat'
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {
            'greeting_displayed': True
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.IDLE_LISTEN, {
            'idle_seconds': 5,
            'listening_active': True
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.IDLE_PROMPT, {
            'idle_duration_s': 60,
            'prompt_type': 'suggestion',
            'prompt_text': 'Would you like me to help with anything?'
        })
        
        idle_prompt_events = [e for e in session.event_history if e['event'] == 'idle_prompt']
        assert len(idle_prompt_events) == 1
        assert idle_prompt_events[0]['data']['prompt_type'] == 'suggestion'

    def test_multi_turn_conversation_flow(self, lifecycle_service, intent_classifier, metrics_collector):
        """Test multi-turn conversation with context preservation."""
        from services.copilot_lifecycle_service import LifecycleEvent
        
        session_id = "e2e_multi_turn_1"
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {})
        
        turn_1_query = "Show me my tasks"
        classification_1 = intent_classifier.classify(turn_1_query)
        lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
            'query': turn_1_query,
            'intent': classification_1.intent.value,
            'turn': 1
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_MERGE, {'turn': 1})
        lifecycle_service.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {
            'content': "Here are your tasks for today.",
            'turn': 1
        })
        lifecycle_service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {'turn': 1})
        
        turn_2_query = "Mark the first one as complete"
        classification_2 = intent_classifier.classify(turn_2_query)
        lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
            'query': turn_2_query,
            'intent': classification_2.intent.value,
            'turn': 2
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_MERGE, {'turn': 2})
        lifecycle_service.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {
            'content': "I've marked the task as complete.",
            'turn': 2
        })
        lifecycle_service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {'turn': 2})
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.ACTION_TRIGGER, {
            'action_type': 'complete_task',
            'task_id': 1,
            'turn': 2
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.CROSS_SURFACE_SYNC, {
            'sync_type': 'task_completed',
            'turn': 2
        })
        
        query_events = [e for e in session.event_history if e['event'] == 'query_detect']
        assert len(query_events) == 2
        
        action_events = [e for e in session.event_history if e['event'] == 'action_trigger']
        assert len(action_events) == 1


class TestCopilotEmotionalCoherence:
    """Tests for emotional coherence in Copilot responses."""

    @pytest.fixture
    def metrics_collector(self):
        """Create metrics collector for testing."""
        from services.copilot_metrics_collector import CopilotMetricsCollector
        return CopilotMetricsCollector()

    def test_calm_score_maintained_throughout_flow(self, metrics_collector):
        """Test that calm score stays high throughout a flow."""
        calm_scores = [0.97, 0.96, 0.98, 0.95, 0.97]
        
        for score in calm_scores:
            metrics_collector.record_response_latency(latency_ms=500, calm_score=score)
        
        final_metrics = metrics_collector.get_current_metrics()
        
        assert final_metrics.calm_score >= 0.95, f"Calm score {final_metrics.calm_score} below threshold"

    def test_response_latency_within_sla(self, metrics_collector):
        """Test that response latency stays within SLA."""
        latencies = [450, 520, 380, 550, 480]
        
        for latency in latencies:
            metrics_collector.record_response_latency(latency_ms=latency, calm_score=0.97)
        
        final_metrics = metrics_collector.get_current_metrics()
        
        assert final_metrics.response_latency_ms <= 600, f"Latency {final_metrics.response_latency_ms}ms exceeds SLA"

    def test_sync_latency_within_sla(self, metrics_collector):
        """Test that sync latency stays within SLA."""
        sync_latencies = [320, 280, 350, 300, 380]
        
        for latency in sync_latencies:
            metrics_collector.record_sync_latency(latency_ms=latency)
        
        final_metrics = metrics_collector.get_current_metrics()
        
        assert final_metrics.sync_latency_ms <= 400, f"Sync latency {final_metrics.sync_latency_ms}ms exceeds SLA"


class TestCopilotErrorRecovery:
    """Tests for error recovery in Copilot flows."""

    @pytest.fixture
    def lifecycle_service(self):
        """Create lifecycle service for testing."""
        from services.copilot_lifecycle_service import CopilotLifecycleService
        return CopilotLifecycleService()

    @pytest.fixture
    def metrics_collector(self):
        """Create metrics collector for testing."""
        from services.copilot_metrics_collector import CopilotMetricsCollector
        return CopilotMetricsCollector()

    def test_session_recovery_after_error(self, lifecycle_service, metrics_collector):
        """Test that sessions can recover after an error."""
        from services.copilot_lifecycle_service import LifecycleEvent
        
        session_id = "e2e_recovery_1"
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        metrics_collector.record_error(error_type='streaming_error', severity='warning')
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {
            'recovery_mode': True
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
            'query': 'Continue where we left off'
        })
        
        assert session.event_history
        assert metrics_collector.total_errors == 1

    def test_graceful_degradation_on_service_failure(self, lifecycle_service, metrics_collector):
        """Test graceful degradation when services fail."""
        from services.copilot_lifecycle_service import LifecycleEvent
        
        session_id = "e2e_degradation_1"
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
            'query': 'What are my tasks?'
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_MERGE, {
            'fallback_mode': True,
            'cached_data': True
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {
            'content': 'Using cached data due to service unavailability.',
            'degraded_mode': True
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {
            'degraded_mode': True
        })
        
        degraded_events = [e for e in session.event_history 
                         if e.get('data', {}).get('degraded_mode') or 
                            e.get('data', {}).get('fallback_mode')]
        
        assert len(degraded_events) >= 2


class TestCopilotChipInteractions:
    """Tests for chip-based interactions."""

    @pytest.fixture
    def chip_generator(self):
        """Create chip generator for testing."""
        from services.copilot_chip_generator import CopilotChipGenerator
        return CopilotChipGenerator()

    @pytest.fixture
    def lifecycle_service(self):
        """Create lifecycle service for testing."""
        from services.copilot_lifecycle_service import CopilotLifecycleService
        return CopilotLifecycleService()

    def test_chip_click_triggers_action(self, chip_generator, lifecycle_service):
        """Test that clicking a chip triggers the expected action."""
        from services.copilot_lifecycle_service import LifecycleEvent
        
        session_id = "e2e_chip_click_1"
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        chips = chip_generator.generate_chips(user_id=1, context={'user_has_tasks': True})
        lifecycle_service.emit_event(session_id, LifecycleEvent.CHIPS_GENERATE, {
            'chips': [{'id': c.chip_id, 'label': c.label} for c in chips]
        })
        
        selected_chip = chips[0] if chips else None
        if selected_chip:
            lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
                'source': 'chip_click',
                'chip_id': selected_chip.chip_id,
                'chip_label': selected_chip.label
            })
            
            lifecycle_service.emit_event(session_id, LifecycleEvent.ACTION_TRIGGER, {
                'action_type': selected_chip.chip_type.value if hasattr(selected_chip.chip_type, 'value') else str(selected_chip.chip_type),
                'triggered_by': 'chip'
            })
        
        chip_events = [e for e in session.event_history if e['event'] == 'chips_generate']
        assert len(chip_events) == 1

    def test_chips_regenerate_after_action(self, chip_generator, lifecycle_service):
        """Test that chips regenerate after an action is completed."""
        from services.copilot_lifecycle_service import LifecycleEvent
        
        session_id = "e2e_chip_regen_1"
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {})
        
        initial_chips = chip_generator.generate_chips(user_id=1, context={'tasks_count': 5})
        lifecycle_service.emit_event(session_id, LifecycleEvent.CHIPS_GENERATE, {
            'chips': [{'id': c.chip_id, 'label': c.label} for c in initial_chips],
            'generation': 1
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.ACTION_TRIGGER, {
            'action_type': 'complete_task',
            'task_id': 1
        })
        
        updated_chips = chip_generator.generate_chips(user_id=1, context={'tasks_count': 4})
        lifecycle_service.emit_event(session_id, LifecycleEvent.CHIPS_GENERATE, {
            'chips': [{'id': c.chip_id, 'label': c.label} for c in updated_chips],
            'generation': 2
        })
        
        chip_events = [e for e in session.event_history if e['event'] == 'chips_generate']
        assert len(chip_events) == 2
        assert chip_events[0]['data']['generation'] == 1
        assert chip_events[1]['data']['generation'] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
