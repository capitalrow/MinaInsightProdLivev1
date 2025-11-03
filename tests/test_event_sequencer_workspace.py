"""
Test Suite for CROWN⁴.5 Per-Workspace Event Sequencing

Tests the EventSequencer service's per-workspace sequencing capabilities:
- Per-workspace monotonic sequence numbers
- Concurrent workspace update isolation
- Vector clock generation and comparison
- Sequence collision prevention
- Gap detection and buffering
"""

import pytest
from datetime import datetime
from unittest.mock import patch
from typing import Dict, Any
from sqlalchemy import select
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from models import db
from models.event_ledger import EventLedger, EventType, EventStatus
from services.event_sequencer import EventSequencer


class TestPerWorkspaceSequencing:
    """Test CROWN⁴.5 per-workspace event sequencing"""
    
    @pytest.fixture(autouse=True)
    def setup(self, app):
        """Set up test environment"""
        self.app = app
        with app.app_context():
            db.create_all()
            
            self.workspace_a = "ws-a1b2c3d4"
            self.workspace_b = "ws-e5f6g7h8"
            
            yield
            
            db.session.remove()
            db.drop_all()
    
    def test_get_next_sequence_num_without_workspace(self, app):
        """Test sequence number generation without workspace_id (backward compatibility)"""
        with app.app_context():
            global_seq, workspace_seq = EventSequencer.get_next_sequence_num()
            
            assert global_seq == 1
            assert workspace_seq is None
    
    def test_get_next_sequence_num_with_workspace(self, app):
        """Test sequence number generation with workspace_id"""
        with app.app_context():
            global_seq, workspace_seq = EventSequencer.get_next_sequence_num(self.workspace_a)
            
            assert global_seq == 1
            assert workspace_seq == 1
    
    def test_monotonic_workspace_sequence(self, app):
        """Test that workspace sequence numbers increment monotonically"""
        with app.app_context():
            sequences = []
            
            for i in range(5):
                global_seq, workspace_seq = EventSequencer.get_next_sequence_num(self.workspace_a)
                sequences.append((global_seq, workspace_seq))
            
            assert sequences == [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
    
    def test_concurrent_workspace_isolation(self, app):
        """Test that different workspaces have independent sequence numbers"""
        with app.app_context():
            EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Workspace A Task 1",
                workspace_id=self.workspace_a
            )
            EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Workspace A Task 2",
                workspace_id=self.workspace_a
            )
            
            EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Workspace B Task 1",
                workspace_id=self.workspace_b
            )
            
            events_a = db.session.execute(
                select(EventLedger).where(EventLedger.workspace_id == self.workspace_a).order_by(EventLedger.id)
            ).scalars().all()
            events_b = db.session.execute(
                select(EventLedger).where(EventLedger.workspace_id == self.workspace_b).order_by(EventLedger.id)
            ).scalars().all()
            
            assert len(events_a) == 2
            assert len(events_b) == 1
            
            assert events_a[0].workspace_sequence_num == 1
            assert events_a[1].workspace_sequence_num == 2
            
            assert events_b[0].workspace_sequence_num == 1
    
    def test_no_sequence_collisions_across_workspaces(self, app):
        """Test that concurrent workspace updates don't cause sequence gaps"""
        with app.app_context():
            for i in range(10):
                workspace = self.workspace_a if i % 2 == 0 else self.workspace_b
                EventSequencer.create_event(
                    event_type=EventType.TASK_UPDATE,
                    event_name=f"Task {i}",
                    workspace_id=workspace
                )
            
            events_a = db.session.execute(
                select(EventLedger).where(EventLedger.workspace_id == self.workspace_a).order_by(EventLedger.workspace_sequence_num)
            ).scalars().all()
            events_b = db.session.execute(
                select(EventLedger).where(EventLedger.workspace_id == self.workspace_b).order_by(EventLedger.workspace_sequence_num)
            ).scalars().all()
            
            assert len(events_a) == 5
            assert len(events_b) == 5
            
            for i, event in enumerate(events_a, 1):
                assert event.workspace_sequence_num == i, f"Gap in workspace A sequence at {i}"
            
            for i, event in enumerate(events_b, 1):
                assert event.workspace_sequence_num == i, f"Gap in workspace B sequence at {i}"
    
    def test_global_sequence_still_increments(self, app):
        """Test that global sequence numbers still increment across all workspaces"""
        with app.app_context():
            event1 = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Event 1",
                workspace_id=self.workspace_a
            )
            
            event2 = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Event 2",
                workspace_id=self.workspace_b
            )
            
            event3 = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Event 3",
                workspace_id=self.workspace_a
            )
            
            assert event1.sequence_num == 1
            assert event2.sequence_num == 2
            assert event3.sequence_num == 3
            
            assert event1.workspace_sequence_num == 1
            assert event2.workspace_sequence_num == 1
            assert event3.workspace_sequence_num == 2


class TestVectorClockOrdering:
    """Test CROWN⁴.5 vector clock generation and comparison"""
    
    @pytest.fixture(autouse=True)
    def setup(self, app):
        """Set up test environment"""
        self.app = app
        with app.app_context():
            db.create_all()
            yield
            db.session.remove()
            db.drop_all()
    
    def test_generate_vector_clock_initial(self, app):
        """Test generating initial vector clock"""
        with app.app_context():
            clock = EventSequencer.generate_vector_clock("client_123")
            
            assert clock == {"client_123": 1}
    
    def test_generate_vector_clock_increment(self, app):
        """Test incrementing vector clock"""
        with app.app_context():
            clock1 = EventSequencer.generate_vector_clock("client_123")
            clock2 = EventSequencer.generate_vector_clock("client_123", clock1)
            clock3 = EventSequencer.generate_vector_clock("client_123", clock2)
            
            assert clock1 == {"client_123": 1}
            assert clock2 == {"client_123": 2}
            assert clock3 == {"client_123": 3}
    
    def test_compare_vector_clocks_equal(self, app):
        """Test comparing identical vector clocks"""
        with app.app_context():
            clock_a = {"client_1": 5, "client_2": 3}
            clock_b = {"client_1": 5, "client_2": 3}
            
            result = EventSequencer.compare_vector_clocks(clock_a, clock_b)
            assert result == "equal"
    
    def test_compare_vector_clocks_before(self, app):
        """Test detecting clock_a happened before clock_b"""
        with app.app_context():
            clock_a = {"client_1": 3, "client_2": 2}
            clock_b = {"client_1": 5, "client_2": 4}
            
            result = EventSequencer.compare_vector_clocks(clock_a, clock_b)
            assert result == "before"
    
    def test_compare_vector_clocks_after(self, app):
        """Test detecting clock_a happened after clock_b"""
        with app.app_context():
            clock_a = {"client_1": 7, "client_2": 6}
            clock_b = {"client_1": 5, "client_2": 4}
            
            result = EventSequencer.compare_vector_clocks(clock_a, clock_b)
            assert result == "after"
    
    def test_compare_vector_clocks_concurrent(self, app):
        """Test detecting concurrent events (conflict)"""
        with app.app_context():
            clock_a = {"client_1": 5, "client_2": 2}
            clock_b = {"client_1": 3, "client_2": 7}
            
            result = EventSequencer.compare_vector_clocks(clock_a, clock_b)
            assert result == "concurrent"
    
    def test_vector_clock_in_event_creation(self, app):
        """Test that vector clocks are stored in events"""
        with app.app_context():
            event = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Test Event",
                client_id="user_123"
            )
            
            assert event.vector_clock is not None
            assert "user_123" in event.vector_clock
            assert event.vector_clock["user_123"] == 1


class TestChecksumGeneration:
    """Test CROWN⁴.5 SHA-256 checksum generation"""
    
    @pytest.fixture(autouse=True)
    def setup(self, app):
        """Set up test environment"""
        self.app = app
        with app.app_context():
            db.create_all()
            yield
            db.session.remove()
            db.drop_all()
    
    def test_generate_checksum(self, app):
        """Test SHA-256 checksum generation"""
        with app.app_context():
            payload = {"task_id": 123, "title": "Test Task", "status": "pending"}
            checksum = EventSequencer.generate_checksum(payload)
            
            assert checksum is not None
            assert len(checksum) == 64
    
    def test_checksum_deterministic(self, app):
        """Test that same payload produces same checksum"""
        with app.app_context():
            payload1 = {"task_id": 123, "title": "Test", "status": "pending"}
            payload2 = {"task_id": 123, "title": "Test", "status": "pending"}
            
            checksum1 = EventSequencer.generate_checksum(payload1)
            checksum2 = EventSequencer.generate_checksum(payload2)
            
            assert checksum1 == checksum2
    
    def test_checksum_different_for_different_payloads(self, app):
        """Test that different payloads produce different checksums"""
        with app.app_context():
            payload1 = {"task_id": 123, "title": "Test 1"}
            payload2 = {"task_id": 123, "title": "Test 2"}
            
            checksum1 = EventSequencer.generate_checksum(payload1)
            checksum2 = EventSequencer.generate_checksum(payload2)
            
            assert checksum1 != checksum2
    
    def test_checksum_stored_in_event(self, app):
        """Test that checksum is stored when creating event"""
        with app.app_context():
            event = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Test Event",
                payload={"task_id": 123, "title": "Test Task"}
            )
            
            assert event.checksum is not None
            assert len(event.checksum) == 64
    
    def test_checksum_order_independence(self, app):
        """Test that checksum is same regardless of key order (sorted internally)"""
        with app.app_context():
            payload1 = {"task_id": 123, "title": "Test", "status": "pending"}
            payload2 = {"status": "pending", "title": "Test", "task_id": 123}
            
            checksum1 = EventSequencer.generate_checksum(payload1)
            checksum2 = EventSequencer.generate_checksum(payload2)
            
            assert checksum1 == checksum2


class TestEventSequenceValidation:
    """Test event sequence validation and gap detection"""
    
    @pytest.fixture(autouse=True)
    def setup(self, app):
        """Set up test environment"""
        self.app = app
        with app.app_context():
            db.create_all()
            yield
            db.session.remove()
            db.drop_all()
    
    def test_validate_sequence_with_no_gaps(self, app):
        """Test sequence validation when events are in order"""
        with app.app_context():
            event1 = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Event 1"
            )
            EventSequencer.mark_event_completed(event1.id)
            
            event2 = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Event 2"
            )
            
            is_valid = EventSequencer.validate_sequence(event2.id, expected_last_id=event1.id)
            assert is_valid is True
    
    def test_detect_sequence_gap(self, app):
        """Test detection of gaps in event sequence"""
        with app.app_context():
            event1 = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Event 1"
            )
            EventSequencer.mark_event_completed(event1.id)
            
            event2 = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Event 2 (skipped)"
            )
            
            event3 = EventSequencer.create_event(
                event_type=EventType.TASK_UPDATE,
                event_name="Event 3"
            )
            
            is_valid = EventSequencer.validate_sequence(event3.id, expected_last_id=event1.id)
            assert is_valid is False


class TestWorkspaceConcurrency:
    """Test concurrent workspace updates and race condition prevention"""
    
    @pytest.fixture(autouse=True)
    def setup(self, app):
        """Set up test environment"""
        self.app = app
        with app.app_context():
            db.create_all()
            yield
            db.session.remove()
            db.drop_all()
    
    def test_interleaved_workspace_events(self, app):
        """Test that interleaved events from different workspaces maintain correct order per workspace"""
        with app.app_context():
            ws_a = "workspace_alpha"
            ws_b = "workspace_beta"
            
            events = [
                (ws_a, "A1"),
                (ws_b, "B1"),
                (ws_a, "A2"),
                (ws_b, "B2"),
                (ws_a, "A3"),
                (ws_b, "B3"),
            ]
            
            for workspace_id, name in events:
                EventSequencer.create_event(
                    event_type=EventType.TASK_UPDATE,
                    event_name=name,
                    workspace_id=workspace_id
                )
            
            events_a = db.session.execute(
                select(EventLedger).where(EventLedger.workspace_id == ws_a).order_by(EventLedger.workspace_sequence_num)
            ).scalars().all()
            events_b = db.session.execute(
                select(EventLedger).where(EventLedger.workspace_id == ws_b).order_by(EventLedger.workspace_sequence_num)
            ).scalars().all()
            
            assert [e.event_name for e in events_a] == ["A1", "A2", "A3"]
            assert [e.event_name for e in events_b] == ["B1", "B2", "B3"]
            
            for i, event in enumerate(events_a, 1):
                assert event.workspace_sequence_num == i
            
            for i, event in enumerate(events_b, 1):
                assert event.workspace_sequence_num == i
    
    def test_high_volume_concurrent_writes(self, app):
        """Test that many concurrent events maintain sequence integrity"""
        with app.app_context():
            workspace_count = 3
            events_per_workspace = 20
            
            workspaces = [f"workspace_{i}" for i in range(workspace_count)]
            
            for i in range(events_per_workspace):
                for workspace_id in workspaces:
                    EventSequencer.create_event(
                        event_type=EventType.TASK_UPDATE,
                        event_name=f"{workspace_id}_event_{i}",
                        workspace_id=workspace_id
                    )
            
            for workspace_id in workspaces:
                events = db.session.execute(
                    select(EventLedger).where(EventLedger.workspace_id == workspace_id).order_by(EventLedger.workspace_sequence_num)
                ).scalars().all()
                
                assert len(events) == events_per_workspace
                
                for i, event in enumerate(events, 1):
                    assert event.workspace_sequence_num == i, f"Gap in {workspace_id} at position {i}"
    
    def test_concurrent_writes_no_duplicates(self, app):
        """
        Test that concurrent threads creating events for the same workspace don't produce duplicate sequence numbers.
        This validates the SELECT FOR UPDATE locking mechanism.
        """
        with app.app_context():
            workspace_id = "concurrent_test_ws"
            num_threads = 5
            events_per_thread = 10
            
            errors = []
            
            def create_events_in_thread(thread_id):
                """Worker function to create events concurrently"""
                try:
                    # Each thread creates events with small random delays
                    for i in range(events_per_thread):
                        EventSequencer.create_event(
                            event_type=EventType.TASK_UPDATE,
                            event_name=f"Thread{thread_id}_Event{i}",
                            workspace_id=workspace_id
                        )
                        # Small delay to increase chance of contention
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(f"Thread {thread_id} error: {e}")
            
            # Run concurrent threads
            threads = []
            for thread_id in range(num_threads):
                thread = threading.Thread(target=create_events_in_thread, args=(thread_id,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Check for errors
            assert len(errors) == 0, f"Concurrent write errors: {errors}"
            
            # Verify all events were created
            events = db.session.execute(
                select(EventLedger).where(EventLedger.workspace_id == workspace_id).order_by(EventLedger.workspace_sequence_num)
            ).scalars().all()
            
            expected_count = num_threads * events_per_thread
            assert len(events) == expected_count, f"Expected {expected_count} events, got {len(events)}"
            
            # CRITICAL: Verify no duplicate workspace sequence numbers
            sequence_nums = [e.workspace_sequence_num for e in events if e.workspace_sequence_num is not None]
            assert len(sequence_nums) == expected_count, \
                f"Some events have NULL workspace_sequence_num"
            
            unique_sequences = set(sequence_nums)
            assert len(sequence_nums) == len(unique_sequences), \
                f"Duplicate sequence numbers detected! Sequences: {sorted(sequence_nums)}"
            
            # Verify sequences are contiguous (1, 2, 3, ..., N)
            expected_sequences = list(range(1, expected_count + 1))
            assert sorted(sequence_nums) == expected_sequences, \
                f"Non-contiguous sequences: expected {expected_sequences}, got {sorted(sequence_nums)}"
    
    def test_empty_workspace_race_condition(self, app):
        """
        Test the critical race condition where multiple threads try to create the first event
        for a brand new workspace simultaneously. This validates the retry logic handles
        IntegrityError on unique constraint violations.
        """
        with app.app_context():
            workspace_id = "brand_new_workspace"
            num_threads = 10
            
            # Verify workspace is empty
            initial_count = db.session.execute(
                select(EventLedger).where(EventLedger.workspace_id == workspace_id)
            ).scalars().all()
            assert len(initial_count) == 0, "Workspace should start empty"
            
            errors = []
            
            def create_first_event(thread_id):
                """Try to create the first event - all threads race to create sequence #1"""
                try:
                    EventSequencer.create_event(
                        event_type=EventType.TASK_UPDATE,
                        event_name=f"Thread{thread_id}_FirstEvent",
                        workspace_id=workspace_id
                    )
                except Exception as e:
                    errors.append(f"Thread {thread_id} error: {e}")
            
            # Launch all threads simultaneously to maximize contention
            threads = []
            for thread_id in range(num_threads):
                thread = threading.Thread(target=create_first_event, args=(thread_id,))
                threads.append(thread)
            
            # Start all threads at once
            for thread in threads:
                thread.start()
            
            # Wait for all to complete
            for thread in threads:
                thread.join()
            
            # CRITICAL: All threads should succeed despite the race
            assert len(errors) == 0, \
                f"Threads failed with errors (retry logic should handle this): {errors}"
            
            # Verify all events were created
            events = db.session.execute(
                select(EventLedger).where(EventLedger.workspace_id == workspace_id).order_by(EventLedger.workspace_sequence_num)
            ).scalars().all()
            
            assert len(events) == num_threads, \
                f"Expected {num_threads} events, got {len(events)}"
            
            # Verify no duplicate sequences (critical!)
            sequence_nums = [e.workspace_sequence_num for e in events if e.workspace_sequence_num is not None]
            unique_sequences = set(sequence_nums)
            assert len(sequence_nums) == len(unique_sequences), \
                f"Duplicate sequence numbers after empty-workspace race! Sequences: {sorted(sequence_nums)}"
            
            # Verify sequences are contiguous from 1 to N
            expected_sequences = list(range(1, num_threads + 1))
            assert sorted(sequence_nums) == expected_sequences, \
                f"Non-contiguous sequences after race: expected {expected_sequences}, got {sorted(sequence_nums)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
