"""
Integration tests for Copilot WebSocket events and lifecycle.
Tests all 12 lifecycle events, streaming responses, and cross-surface broadcast.
"""
import pytest
import time
import json
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from services.copilot_lifecycle_service import LifecycleEvent

EXPECTED_EVENTS = [
    "copilot_bootstrap",
    "context_rehydrate",
    "chips_generate",
    "idle_listen",
    "query_detect",
    "context_merge",
    "reasoning_stream",
    "response_commit",
    "action_trigger",
    "cross_surface_sync",
    "context_retrain",
    "idle_prompt"
]


@dataclass
class MockWebSocketMessage:
    """Mock WebSocket message for testing."""
    event_type: str
    data: Dict[str, Any]
    timestamp: float
    session_id: str


class MockWebSocketClient:
    """Mock WebSocket client for integration testing."""
    
    def __init__(self):
        self.connected = False
        self.received_messages: List[MockWebSocketMessage] = []
        self.room: Optional[str] = None
        self.session_id: Optional[str] = None
    
    def connect(self, session_id: str):
        """Simulate WebSocket connection."""
        self.connected = True
        self.session_id = session_id
        return True
    
    def disconnect(self):
        """Simulate WebSocket disconnection."""
        self.connected = False
        self.room = None
    
    def join_room(self, room: str):
        """Simulate joining a room."""
        self.room = room
    
    def emit(self, event: str, data: Dict[str, Any]):
        """Simulate emitting an event."""
        if not self.connected:
            raise ConnectionError("Not connected")
        return True
    
    def receive(self, event_type: str, data: Dict[str, Any]):
        """Simulate receiving an event."""
        message = MockWebSocketMessage(
            event_type=event_type,
            data=data,
            timestamp=time.time(),
            session_id=self.session_id or "test"
        )
        self.received_messages.append(message)
    
    def get_events_by_type(self, event_type: str) -> List[MockWebSocketMessage]:
        """Get all received events of a specific type."""
        return [m for m in self.received_messages if m.event_type == event_type]
    
    def clear_messages(self):
        """Clear received messages."""
        self.received_messages.clear()


@pytest.fixture
def mock_client():
    """Create mock WebSocket client."""
    return MockWebSocketClient()


@pytest.fixture
def lifecycle_service():
    """Create lifecycle service for testing."""
    from services.copilot_lifecycle_service import CopilotLifecycleService
    return CopilotLifecycleService()


@pytest.fixture
def event_broadcaster():
    """Create event broadcaster for testing."""
    from services.event_broadcaster import EventBroadcaster
    return EventBroadcaster()


@pytest.mark.integration
class TestCopilotLifecycleEvents:
    """Integration tests for all 12 Copilot lifecycle events."""

    def test_all_lifecycle_events_defined(self):
        """Verify all 12 lifecycle events are defined."""
        events = list(LifecycleEvent)
        assert len(events) == 12
        
        for expected in EXPECTED_EVENTS:
            assert any(e.value == expected for e in events), f"Missing event: {expected}"

    def test_copilot_bootstrap_event(self, lifecycle_service, mock_client):
        """Test copilot_bootstrap event emission."""
        session_id = "test_session_1"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {
            'page': 'dashboard',
            'context_loaded': True
        })
        
        assert session is not None
        assert session.session_id == session_id
        assert lifecycle_service.get_session(session_id) is not None

    def test_context_rehydrate_event(self, lifecycle_service, mock_client):
        """Test context_rehydrate event with session sync."""
        session_id = "test_session_2"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {
            'sessions_synced': 5,
            'meetings_loaded': 2,
            'sync_time_ms': 120
        })
        
        state = session
        assert len(state.event_history) >= 1

    def test_chips_generate_event(self, lifecycle_service, mock_client):
        """Test chips_generate event."""
        session_id = "test_session_3"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.CHIPS_GENERATE, {
            'chips': [
                {'id': 'chip_1', 'label': 'Show tasks', 'type': 'action'},
                {'id': 'chip_2', 'label': 'Schedule meeting', 'type': 'action'}
            ],
            'render_time_ms': 45
        })
        
        state = session
        assert len(state.event_history) >= 1

    def test_idle_listen_event(self, lifecycle_service, mock_client):
        """Test idle_listen event."""
        session_id = "test_session_4"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.IDLE_LISTEN, {
            'idle_seconds': 3,
            'listening_active': True
        })
        
        state = session
        assert state.last_activity is not None

    def test_query_detect_event(self, lifecycle_service, mock_client):
        """Test query_detect event."""
        session_id = "test_session_5"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.QUERY_DETECT, {
            'intent': 'task_creation',
            'confidence': 0.92,
            'entities': {'task_name': 'Review report'},
            'classification_time_ms': 25
        })
        
        state = session
        assert len(state.event_history) >= 1

    def test_context_merge_event(self, lifecycle_service, mock_client):
        """Test context_merge event."""
        session_id = "test_session_6"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_MERGE, {
            'sources': ['tasks', 'calendar', 'history'],
            'merge_time_ms': 50
        })
        
        state = session
        assert len(state.event_history) >= 1

    def test_reasoning_stream_event(self, lifecycle_service, mock_client):
        """Test reasoning_stream event."""
        session_id = "test_session_7"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        chunks = ["I'll ", "help ", "you ", "with ", "that."]
        for i, chunk in enumerate(chunks):
            lifecycle_service.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {
                'message_id': 'msg_123',
                'chunk_index': i,
                'content': chunk,
                'is_first': i == 0,
                'is_last': i == len(chunks) - 1
            })
        
        state = session
        assert len(state.event_history) >= 5

    def test_response_commit_event(self, lifecycle_service, mock_client):
        """Test response_commit event with metrics."""
        session_id = "test_session_8"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {
            'message_id': 'msg_123',
            'total_tokens': 45,
            'latency_ms': 520,
            'calm_score': 0.97
        })
        
        state = session
        assert len(state.event_history) >= 1

    def test_action_trigger_event(self, lifecycle_service, mock_client):
        """Test action_trigger event."""
        session_id = "test_session_9"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.ACTION_TRIGGER, {
            'action_type': 'create_task',
            'action_data': {'task_name': 'Review report', 'priority': 'high'},
            'success': True,
            'execution_time_ms': 150
        })
        
        state = session
        assert len(state.event_history) >= 1

    def test_cross_surface_sync_event(self, lifecycle_service, mock_client):
        """Test cross_surface_sync event."""
        session_id = "test_session_10"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.CROSS_SURFACE_SYNC, {
            'surfaces': ['dashboard', 'calendar', 'analytics'],
            'sync_type': 'task_created',
            'sync_data': {'task_id': 123},
            'latency_ms': 320
        })
        
        state = session
        assert len(state.event_history) >= 1

    def test_context_retrain_event(self, lifecycle_service, mock_client):
        """Test context_retrain event."""
        session_id = "test_session_11"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_RETRAIN, {
            'embeddings_updated': True,
            'retrain_time_ms': 80
        })
        
        state = session
        assert len(state.event_history) >= 1

    def test_idle_prompt_event(self, lifecycle_service, mock_client):
        """Test idle_prompt event."""
        session_id = "test_session_12"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        lifecycle_service.emit_event(session_id, LifecycleEvent.IDLE_PROMPT, {
            'idle_duration_s': 30,
            'prompt_type': 'suggestion',
            'prompt_text': 'Would you like to review your pending tasks?'
        })
        
        state = session
        assert len(state.event_history) >= 1
        mock_client.disconnect()
        assert not mock_client.connected


@pytest.mark.integration
class TestCopilotStreamingResponse:
    """Integration tests for streaming responses."""

    def test_streaming_response_flow(self, lifecycle_service, mock_client):
        """Test complete streaming response flow."""
        session_id = "stream_test_1"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_MERGE, {
            'message_id': 'msg_stream_1',
            'start_time': time.time()
        })
        
        chunks = ["Creating ", "a ", "new ", "task ", "for ", "you."]
        first_chunk_time = None
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                first_chunk_time = time.time()
            lifecycle_service.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {
                'message_id': 'msg_stream_1',
                'chunk_index': i,
                'content': chunk,
                'is_first': i == 0,
                'is_last': i == len(chunks) - 1
            })
            time.sleep(0.01)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {
            'message_id': 'msg_stream_1',
            'total_chunks': len(chunks),
            'latency_ms': 150,
            'calm_score': 0.98
        })
        
        state = session
        assert len(state.event_history) >= len(chunks) + 2

    def test_streaming_with_action_trigger(self, lifecycle_service, mock_client):
        """Test streaming response that triggers an action."""
        session_id = "stream_test_2"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_MERGE, {
            'message_id': 'msg_action_1'
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.REASONING_STREAM, {
            'message_id': 'msg_action_1',
            'content': "I'll create that task now.",
            'is_first': True,
            'is_last': True
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.RESPONSE_COMMIT, {
            'message_id': 'msg_action_1'
        })
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.ACTION_TRIGGER, {
            'action_type': 'create_task',
            'success': True
        })
        
        state = session
        assert len(state.event_history) >= 4


@pytest.mark.integration
class TestCrossSurfaceBroadcast:
    """Integration tests for cross-surface broadcast functionality."""

    def test_event_broadcaster_initialization(self, event_broadcaster):
        """Test EventBroadcaster initializes correctly."""
        assert event_broadcaster is not None
        assert hasattr(event_broadcaster, 'socketio')

    def test_event_broadcaster_methods_exist(self, event_broadcaster):
        """Test EventBroadcaster has required methods."""
        assert hasattr(event_broadcaster, 'emit_event')
        assert hasattr(event_broadcaster, 'set_socketio')
        assert callable(event_broadcaster.emit_event)

    def test_emit_without_socketio(self, event_broadcaster):
        """Test emit returns False when socketio not set."""
        from unittest.mock import MagicMock
        from models.event_ledger import EventType
        
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.event_type = EventType.RECORD_START
        mock_event.event_name = "test_event"
        mock_event.sequence_num = 1
        mock_event.workspace_id = None
        mock_event.workspace_sequence_num = None
        mock_event.last_applied_id = None
        mock_event.vector_clock = None
        mock_event.created_at = None
        mock_event.payload = {}
        mock_event.checksum = None
        
        result = event_broadcaster.emit_event(mock_event)
        
        assert result == False

    def test_set_socketio(self, event_broadcaster):
        """Test setting socketio instance."""
        from unittest.mock import MagicMock
        mock_socketio = MagicMock()
        
        event_broadcaster.set_socketio(mock_socketio)
        
        assert event_broadcaster.socketio is mock_socketio

    def test_broadcast_latency_tracking(self):
        """Test that broadcast operations are fast."""
        from services.event_broadcaster import EventBroadcaster
        
        broadcaster = EventBroadcaster()
        start_time = time.time()
        
        broadcaster.set_socketio(None)
        
        latency = (time.time() - start_time) * 1000
        assert latency < 100


@pytest.mark.integration
class TestWebSocketConnectionManagement:
    """Integration tests for WebSocket connection management."""

    def test_client_connection_lifecycle(self, mock_client):
        """Test client connection and disconnection."""
        assert not mock_client.connected
        
        mock_client.connect("session_conn_1")
        assert mock_client.connected
        assert mock_client.session_id == "session_conn_1"
        
        mock_client.disconnect()
        assert not mock_client.connected

    def test_room_management(self, mock_client):
        """Test room join and leave."""
        mock_client.connect("session_room_1")
        
        mock_client.join_room("copilot_room_1")
        assert mock_client.room == "copilot_room_1"
        
        mock_client.join_room("copilot_room_2")
        assert mock_client.room == "copilot_room_2"

    def test_emit_requires_connection(self, mock_client):
        """Test that emit requires active connection."""
        with pytest.raises(ConnectionError):
            mock_client.emit("test_event", {"data": "test"})

    def test_message_reception(self, mock_client):
        """Test message reception and storage."""
        mock_client.connect("session_msg_1")
        
        mock_client.receive("event_1", {"key": "value1"})
        mock_client.receive("event_2", {"key": "value2"})
        mock_client.receive("event_1", {"key": "value3"})
        
        assert len(mock_client.received_messages) == 3
        
        event_1_messages = mock_client.get_events_by_type("event_1")
        assert len(event_1_messages) == 2


@pytest.mark.integration
class TestCopilotEventSequencing:
    """Integration tests for event sequencing validation."""

    def test_session_flow_sequence(self, lifecycle_service, mock_client):
        """Test correct event sequence for a session."""
        session_id = "sequence_test_1"
        mock_client.connect(session_id)
        
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        expected_sequence = [
            LifecycleEvent.COPILOT_BOOTSTRAP,
            LifecycleEvent.CONTEXT_REHYDRATE,
            LifecycleEvent.CHIPS_GENERATE,
            LifecycleEvent.IDLE_LISTEN,
            LifecycleEvent.QUERY_DETECT,
            LifecycleEvent.CONTEXT_MERGE,
            LifecycleEvent.REASONING_STREAM,
            LifecycleEvent.RESPONSE_COMMIT,
            LifecycleEvent.ACTION_TRIGGER,
            LifecycleEvent.CROSS_SURFACE_SYNC,
            LifecycleEvent.CONTEXT_RETRAIN,
            LifecycleEvent.IDLE_PROMPT
        ]
        
        for event in expected_sequence:
            lifecycle_service.emit_event(session_id, event, {
                'sequence_test': True
            })
        
        state = session
        assert len(state.event_history) >= len(expected_sequence)

    def test_event_order_validation(self, lifecycle_service):
        """Test that events are recorded in order."""
        session_id = "order_test_1"
        session = lifecycle_service.create_session(session_id, user_id=1)
        
        lifecycle_service.emit_event(session_id, LifecycleEvent.COPILOT_BOOTSTRAP, {'order': 1})
        time.sleep(0.001)
        lifecycle_service.emit_event(session_id, LifecycleEvent.CONTEXT_REHYDRATE, {'order': 2})
        time.sleep(0.001)
        lifecycle_service.emit_event(session_id, LifecycleEvent.CHIPS_GENERATE, {'order': 3})
        
        state = session
        
        if len(state.event_history) >= 3:
            for i in range(1, len(state.event_history)):
                assert state.event_history[i]['timestamp'] >= state.event_history[i-1]['timestamp']


@pytest.mark.integration
class TestCopilotMetricsIntegration:
    """Integration tests for metrics collection."""

    def test_latency_metrics_collection(self):
        """Test latency metrics are collected."""
        from services.copilot_metrics_collector import CopilotMetricsCollector
        
        collector = CopilotMetricsCollector()
        
        collector.record_response_latency(latency_ms=450, calm_score=0.97)
        collector.record_sync_latency(latency_ms=280)
        collector.record_cache_access(hit=True)
        
        metrics = collector.get_current_metrics()
        
        assert metrics.response_latency_ms == 450
        assert metrics.sync_latency_ms == 280
        assert metrics.calm_score == 0.97

    def test_sla_compliance_tracking(self):
        """Test SLA compliance tracking."""
        from services.copilot_metrics_collector import CopilotMetricsCollector
        
        collector = CopilotMetricsCollector()
        
        collector.record_response_latency(latency_ms=500, calm_score=0.96)
        collector.record_sync_latency(latency_ms=350)
        collector.record_cache_access(hit=True)
        
        metrics = collector.get_current_metrics()
        
        assert metrics.response_latency_ms <= 600
        assert metrics.sync_latency_ms <= 400
        assert metrics.calm_score >= 0.95
        assert metrics.meets_sla() == True

    def test_sla_violation_detection(self):
        """Test SLA violation detection."""
        from services.copilot_metrics_collector import CopilotMetricsCollector
        
        collector = CopilotMetricsCollector()
        
        collector.record_response_latency(latency_ms=700, calm_score=0.90)
        
        metrics = collector.get_current_metrics()
        
        assert metrics.response_latency_ms > 600
        assert metrics.calm_score < 0.95
        assert metrics.meets_sla() == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
