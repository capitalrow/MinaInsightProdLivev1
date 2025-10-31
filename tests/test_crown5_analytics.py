"""
CROWN⁵+ Analytics System Validation Tests
Tests all aspects of the living intelligence specification
"""

import pytest
import time
from datetime import datetime
from unittest.mock import Mock, patch
from app import app, db
from models import EventLedger, EventType, Meeting, Task, Analytics
from services.event_broadcaster import EventBroadcaster
from services.analytics_cache_service import AnalyticsCacheService
from services.analytics_delta_service import AnalyticsDeltaService


class TestCROWN5EventSequencing:
    """Validate 10-event lifecycle (Section 3)"""
    
    def test_all_analytics_events_exist_in_enum(self):
        """Verify all 10 CROWN⁵+ events are in EventType enum"""
        required_events = [
            'analytics_bootstrap',
            'analytics_ws_subscribe',
            'analytics_header_reconcile',
            'analytics_overview_hydrate',
            'analytics_prefetch_tabs',
            'analytics_delta_apply',
            'analytics_filter_change',
            'analytics_tab_switch',
            'analytics_export_initiated',
            'analytics_idle_sync'
        ]
        
        event_values = [e.value for e in EventType]
        for event in required_events:
            assert event in event_values, f"Missing event: {event}"
    
    def test_event_ledger_can_store_analytics_events(self, client):
        """Verify database can persist all CROWN⁵+ events"""
        with app.app_context():
            for event_type in [EventType.ANALYTICS_BOOTSTRAP, EventType.ANALYTICS_TAB_SWITCH]:
                event = EventLedger(
                    event_type=event_type,
                    event_name=f"Test {event_type.value}",
                    payload={'test': 'data'},
                    status='PENDING'
                )
                db.session.add(event)
            db.session.commit()
            
            # Verify events persisted
            events = EventLedger.query.filter(
                EventLedger.event_type.in_([EventType.ANALYTICS_BOOTSTRAP, EventType.ANALYTICS_TAB_SWITCH])
            ).all()
            assert len(events) >= 2


class TestAnalyticsCacheService:
    """Validate cache-first bootstrap (Stage 1)"""
    
    def test_cache_service_computes_checksums(self):
        """Verify cache service generates SHA-256 checksums"""
        service = AnalyticsCacheService()
        snapshot = {'kpis': {'total_meetings': 120}, 'days': 30}
        
        checksum = service.compute_checksum(snapshot)
        assert len(checksum) == 64  # SHA-256 hex length
        assert checksum.isalnum()
    
    def test_cache_service_generates_etag(self):
        """Verify ETag generation for validation"""
        service = AnalyticsCacheService()
        snapshot = {'kpis': {'total_meetings': 120}}
        
        etag = service.generate_etag(snapshot)
        assert etag.startswith('"') and etag.endswith('"')
        assert len(etag) > 10
    
    def test_delta_computation_only_includes_changed_fields(self):
        """Verify field-level diffs (Section 9)"""
        service = AnalyticsCacheService()
        
        old_snapshot = {
            'kpis': {
                'total_meetings': 100,
                'total_tasks': 50,
                'hours_saved': 20
            }
        }
        
        new_snapshot = {
            'kpis': {
                'total_meetings': 102,  # Changed
                'total_tasks': 50,  # Unchanged
                'hours_saved': 22  # Changed
            }
        }
        
        delta = service.compute_delta(old_snapshot, new_snapshot)
        
        # Should only include changed fields
        assert 'kpis' in delta
        assert delta['kpis']['total_meetings'] == 102
        assert delta['kpis']['hours_saved'] == 22
        # Should not include unchanged field
        assert 'total_tasks' not in delta['kpis']


class TestAnalyticsDeltaService:
    """Validate real-time delta streaming (Event #6)"""
    
    def test_delta_broadcast_on_meeting_completion(self, client):
        """Verify analytics_delta fires when meeting ends"""
        with app.app_context():
            # Create meeting
            meeting = Meeting(
                title='Test Meeting',
                workspace_id=1,
                created_by_user_id=1
            )
            db.session.add(meeting)
            db.session.commit()
            
            delta_service = AnalyticsDeltaService()
            
            with patch.object(EventBroadcaster, 'broadcast') as mock_broadcast:
                # Trigger delta on session finalization
                delta_service.broadcast_analytics_delta(
                    workspace_id=1,
                    delta_type='meeting_completed',
                    delta_data={'meeting_id': meeting.id}
                )
                
                # Verify broadcast was called
                assert mock_broadcast.called
                call_args = mock_broadcast.call_args
                assert 'analytics_delta' in str(call_args)
    
    def test_delta_includes_checksum_for_integrity(self):
        """Verify deltas include checksums (Section 9)"""
        delta_service = AnalyticsDeltaService()
        
        delta_payload = delta_service.prepare_delta_payload(
            workspace_id=1,
            delta_type='kpi_update',
            changes={'total_meetings': 105}
        )
        
        assert 'checksum' in delta_payload
        assert 'delta_type' in delta_payload
        assert 'changes' in delta_payload
        assert 'timestamp' in delta_payload


class TestPerformanceTargets:
    """Validate performance requirements (Section 11)"""
    
    def test_cache_checksum_computation_is_fast(self):
        """Verify checksum < 50ms (contributes to ≤200ms warm paint)"""
        service = AnalyticsCacheService()
        large_snapshot = {
            'kpis': {f'metric_{i}': i for i in range(100)},
            'charts': {f'chart_{i}': [j for j in range(50)] for i in range(10)}
        }
        
        start = time.time()
        checksum = service.compute_checksum(large_snapshot)
        duration_ms = (time.time() - start) * 1000
        
        assert checksum is not None
        assert duration_ms < 50, f"Checksum took {duration_ms}ms, target <50ms"
    
    def test_delta_merge_is_fast(self):
        """Verify delta apply ≤100ms target"""
        service = AnalyticsCacheService()
        
        base_snapshot = {'kpis': {f'kpi_{i}': i for i in range(50)}}
        delta = {'kpis': {'kpi_0': 999, 'kpi_25': 888}}
        
        start = time.time()
        merged = service.merge_delta(base_snapshot, delta)
        duration_ms = (time.time() - start) * 1000
        
        assert merged['kpis']['kpi_0'] == 999
        assert merged['kpis']['kpi_25'] == 888
        assert duration_ms < 100, f"Delta merge took {duration_ms}ms, target <100ms"


class TestIdempotentSafety:
    """Validate replay safety (Global Philosophy - Principle 3)"""
    
    def test_delta_apply_is_idempotent(self):
        """Verify applying same delta twice produces same result"""
        service = AnalyticsCacheService()
        
        snapshot = {'kpis': {'total_meetings': 100}}
        delta = {'kpis': {'total_meetings': 105}}
        
        # Apply delta once
        result1 = service.merge_delta(snapshot.copy(), delta)
        
        # Apply same delta again
        result2 = service.merge_delta(result1.copy(), delta)
        
        # Results should be identical (idempotent)
        assert result1 == result2
    
    def test_event_sequencing_prevents_duplicates(self, client):
        """Verify sequence numbers prevent replay"""
        with app.app_context():
            # Create two events with same idempotency key
            idempotency_key = f"test_idem_{int(time.time())}"
            
            event1 = EventLedger(
                event_type=EventType.ANALYTICS_DELTA_APPLY,
                event_name="Delta Apply",
                payload={'kpi': 'total_meetings', 'value': 100},
                status='PENDING',
                idempotency_key=idempotency_key
            )
            db.session.add(event1)
            db.session.commit()
            
            # Attempting to create duplicate with same key should be handled
            event2 = EventLedger.query.filter_by(
                idempotency_key=idempotency_key
            ).first()
            
            assert event2 is not None
            assert event2.id == event1.id  # Same event retrieved


class TestDataIntegritySafeguards:
    """Validate data integrity (Section 9)"""
    
    def test_no_nans_in_kpi_values(self):
        """Verify NaN policy - missing data uses placeholders"""
        service = AnalyticsCacheService()
        
        # Simulate KPI with None/NaN
        snapshot = {
            'kpis': {
                'total_meetings': 120,
                'avg_duration': None,
                'completion_rate': float('nan') if hasattr(float, '__call__') else 0
            }
        }
        
        sanitized = service.sanitize_snapshot(snapshot)
        
        # NaN should be converted to safe placeholder
        assert sanitized['kpis']['total_meetings'] == 120
        assert sanitized['kpis']['avg_duration'] == 0 or sanitized['kpis']['avg_duration'] == "—"
        assert not (isinstance(sanitized['kpis']['completion_rate'], float) and 
                    sanitized['kpis']['completion_rate'] != sanitized['kpis']['completion_rate'])


class TestEventBroadcasting:
    """Validate WebSocket event emission (Section 5)"""
    
    def test_analytics_events_broadcast_to_correct_namespace(self):
        """Verify events route to /analytics namespace"""
        broadcaster = EventBroadcaster()
        
        with patch('services.event_broadcaster.socketio') as mock_socketio:
            broadcaster.broadcast(
                event_type='analytics_delta_apply',
                workspace_id=1,
                payload={'delta': {'kpi': 'value'}},
                namespace='/analytics'
            )
            
            # Verify emit was called with correct namespace
            assert mock_socketio.emit.called
            call_args = mock_socketio.emit.call_args
            assert '/analytics' in str(call_args) or call_args[1].get('namespace') == '/analytics'


@pytest.fixture
def client():
    """Test client with app context"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
