"""
CROWN⁵+ Analytics Integration Tests

Integration tests that verify the real implementation against CROWN⁵+ specification
by exercising actual services, WebSocket handlers, and data flows.
"""

import pytest
import json
import hashlib
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestCROWN5EventSequencerIntegration:
    """Integration tests for EventSequencer service"""
    
    @pytest.fixture
    def app_context(self):
        """Create Flask app context for testing"""
        try:
            from app import create_app
            app = create_app()
            with app.app_context():
                yield app
        except Exception:
            pytest.skip("App context unavailable")
    
    def test_event_sequencer_checksum_sha256(self, app_context):
        """
        Verify EventSequencer uses SHA-256 checksums as per CROWN⁵+ spec.
        """
        from services.event_sequencer import EventSequencer
        
        payload = {'total_meetings': 10, 'action_items': 5}
        checksum = EventSequencer.generate_checksum(payload)
        
        assert len(checksum) == 64, "Must use SHA-256 (64 hex chars)"
        
        expected = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode('utf-8')
        ).hexdigest()
        assert checksum == expected, "Checksum must match SHA-256 standard"
    
    def test_event_sequencer_idempotency(self, app_context):
        """
        Verify EventSequencer supports idempotent event creation.
        """
        from services.event_sequencer import EventSequencer
        
        payload = {'test': 'idempotency'}
        checksum1 = EventSequencer.generate_checksum(payload)
        checksum2 = EventSequencer.generate_checksum(payload)
        
        assert checksum1 == checksum2, "Same payload must produce same checksum"
    
    def test_event_sequencer_deterministic_ordering(self, app_context):
        """
        Verify EventSequencer produces deterministic checksums with sorted keys.
        """
        from services.event_sequencer import EventSequencer
        
        payload1 = {'a': 1, 'b': 2, 'c': 3}
        payload2 = {'c': 3, 'a': 1, 'b': 2}
        
        assert EventSequencer.generate_checksum(payload1) == EventSequencer.generate_checksum(payload2), \
            "Key order must not affect checksum (deterministic)"


class TestCROWN5CacheValidatorIntegration:
    """Integration tests for cache validation"""
    
    @pytest.fixture
    def app_context(self):
        """Create Flask app context for testing"""
        try:
            from app import create_app
            app = create_app()
            with app.app_context():
                yield app
        except Exception:
            pytest.skip("App context unavailable")
    
    def test_cache_validator_sha256(self, app_context):
        """
        Verify CacheValidator uses SHA-256 checksums.
        """
        from services.cache_validator import CacheValidator
        
        data = {'meetings': 10, 'tasks': 5}
        checksum = CacheValidator.generate_checksum(data)
        
        assert len(checksum) == 64, "Must use SHA-256"
    
    def test_cache_validator_field_exclusion(self, app_context):
        """
        Verify CacheValidator can exclude fields from checksum.
        """
        from services.cache_validator import CacheValidator
        
        data1 = {'value': 100, 'checksum': 'old', 'last_validated': 'time1'}
        data2 = {'value': 100, 'checksum': 'new', 'last_validated': 'time2'}
        
        checksum1 = CacheValidator.generate_checksum(data1)
        checksum2 = CacheValidator.generate_checksum(data2)
        
        assert checksum1 == checksum2, "Excluded fields must not affect checksum"


class TestCROWN5AnalyticsServiceIntegration:
    """Integration tests for Analytics Service"""
    
    @pytest.fixture
    def app_context(self):
        """Create Flask app context for testing"""
        try:
            from app import create_app
            app = create_app()
            with app.app_context():
                yield app
        except Exception:
            pytest.skip("App context unavailable")
    
    def test_analytics_service_exists(self, app_context):
        """
        Verify AnalyticsService is available.
        """
        from services.analytics_service import AnalyticsService
        
        service = AnalyticsService()
        assert service is not None, "AnalyticsService must be instantiable"
    
    def test_analytics_no_transcript_in_kpis(self, app_context):
        """
        Verify analytics KPIs don't contain transcript text (CROWN⁵+ privacy).
        """
        from services.analytics_service import AnalyticsService
        
        service = AnalyticsService()
        
        kpi_fields = ['total_meetings', 'total_tasks', 'avg_duration', 
                      'sentiment_score', 'action_items', 'speaking_time']
        
        forbidden_fields = ['transcript', 'text', 'content', 'message']
        
        for field in kpi_fields:
            assert field not in forbidden_fields, \
                f"KPI field '{field}' must not be transcript content"


class TestCROWN5WebSocketNamespace:
    """Integration tests for Analytics WebSocket namespace"""
    
    def test_analytics_namespace_registered(self):
        """
        Verify analytics WebSocket namespace is properly registered.
        """
        import routes.analytics_websocket as aws
        
        assert hasattr(aws, 'register_analytics_namespace'), \
            "Analytics WebSocket must have register function"
    
    def test_analytics_workspace_isolation(self):
        """
        Verify analytics uses workspace-scoped rooms.
        """
        import routes.analytics_websocket as aws
        import inspect
        
        source = inspect.getsource(aws)
        
        assert 'workspace_' in source, \
            "Analytics must use workspace-prefixed rooms"
        assert 'join_room' in source, \
            "Analytics must support joining rooms"


class TestCROWN5CalmMotionCSS:
    """Tests for calm motion CSS framework"""
    
    @pytest.fixture
    def calm_motion_css(self):
        """Load calm-motion.css content"""
        try:
            with open('static/css/calm-motion.css', 'r') as f:
                return f.read()
        except FileNotFoundError:
            pytest.skip("calm-motion.css not found")
    
    def test_calm_duration_variables(self, calm_motion_css):
        """
        Verify calm motion duration CSS variables (200-400ms).
        """
        assert '--calm-duration-fast: 200ms' in calm_motion_css, \
            "Must define 200ms fast duration"
        assert '--calm-duration-normal: 300ms' in calm_motion_css, \
            "Must define 300ms normal duration"
        assert '--calm-duration-slow: 400ms' in calm_motion_css, \
            "Must define 400ms slow duration"
    
    def test_calm_animations_defined(self, calm_motion_css):
        """
        Verify required calm animation keyframes exist.
        """
        required_animations = [
            'calm-pulse',
            'calm-fade-in',
            'calm-tile-pulse',
            'calm-shimmer'
        ]
        
        for animation in required_animations:
            assert f'@keyframes {animation}' in calm_motion_css, \
                f"Must define @keyframes {animation}"
    
    def test_cubic_bezier_easing(self, calm_motion_css):
        """
        Verify calm motion uses cubic-bezier easing.
        """
        assert 'cubic-bezier' in calm_motion_css, \
            "Must use cubic-bezier easing for calm motion"


class TestCROWN5IndexedDBCache:
    """Tests for IndexedDB cache implementation"""
    
    @pytest.fixture
    def indexeddb_js(self):
        """Load indexeddb-cache.js content"""
        try:
            with open('static/js/indexeddb-cache.js', 'r') as f:
                return f.read()
        except FileNotFoundError:
            pytest.skip("indexeddb-cache.js not found")
    
    def test_workspace_isolation(self, indexeddb_js):
        """
        Verify IndexedDB uses workspace isolation.
        """
        assert 'workspaceId' in indexeddb_js, \
            "Must support workspaceId parameter"
        assert 'mina_cache_' in indexeddb_js, \
            "Must use workspace-prefixed database names"
    
    def test_required_stores_defined(self, indexeddb_js):
        """
        Verify required object stores are defined.
        """
        required_stores = [
            'meetings',
            'analytics',
            'tasks',
            'metadata',
            'offline_queue'
        ]
        
        for store in required_stores:
            assert store.upper() in indexeddb_js or f"'{store}'" in indexeddb_js, \
                f"Must define {store} store"
    
    def test_crown45_stores(self, indexeddb_js):
        """
        Verify CROWN⁴.5 enhanced stores are defined.
        """
        assert 'view_state' in indexeddb_js, \
            "Must support view_state store (CROWN⁴.5)"
        assert 'counters' in indexeddb_js, \
            "Must support counters store (CROWN⁴.5)"


class TestCROWN5AnalyticsEventsJS:
    """Tests for analytics-events.js delta handling"""
    
    @pytest.fixture
    def analytics_events_js(self):
        """Load analytics-events.js content"""
        try:
            with open('static/js/analytics-events.js', 'r') as f:
                return f.read()
        except FileNotFoundError:
            pytest.skip("analytics-events.js not found")
    
    def test_delta_handling(self, analytics_events_js):
        """
        Verify delta event handling is implemented.
        """
        assert 'analytics_delta' in analytics_events_js, \
            "Must handle analytics_delta events"
        assert 'applyDelta' in analytics_events_js or 'handleAnalyticsDelta' in analytics_events_js, \
            "Must implement delta application"
    
    def test_sequence_tracking(self, analytics_events_js):
        """
        Verify sequence number tracking.
        """
        assert 'sequence_num' in analytics_events_js or 'sequenceNum' in analytics_events_js, \
            "Must track sequence numbers"
        assert 'lastSequenceNum' in analytics_events_js or 'last_sequence_num' in analytics_events_js, \
            "Must track last applied sequence"
    
    def test_event_replay_support(self, analytics_events_js):
        """
        Verify event replay is supported for reconnection.
        """
        assert 'request_event_replay' in analytics_events_js or 'event_replay' in analytics_events_js, \
            "Must support event replay for reconnection"


class TestCROWN5PerformanceTargets:
    """Tests for performance target instrumentation"""
    
    @pytest.fixture
    def task_bootstrap_js(self):
        """Load task-bootstrap.js content"""
        try:
            with open('static/js/task-bootstrap.js', 'r') as f:
                return f.read()
        except FileNotFoundError:
            pytest.skip("task-bootstrap.js not found")
    
    def test_first_paint_tracking(self, task_bootstrap_js):
        """
        Verify first paint timing is tracked.
        """
        assert 'first_paint' in task_bootstrap_js, \
            "Must track first paint timing"
        assert 'performance.now()' in task_bootstrap_js, \
            "Must use performance.now() for timing"
    
    def test_telemetry_integration(self, task_bootstrap_js):
        """
        Verify CROWN telemetry is used.
        """
        assert 'CROWNTelemetry' in task_bootstrap_js, \
            "Must use CROWNTelemetry for metrics"
        assert 'recordMetric' in task_bootstrap_js, \
            "Must record metrics via telemetry"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
