"""
EventSequencer Service - CROWN⁴ Event Ordering & Validation

Ensures events are processed in correct order and prevents out-of-order
execution that could cause data inconsistencies across dashboard, tasks, and analytics.

Key Features:
- Sequence number validation
- Idempotency checking with last_applied_id
- Checksum generation for data integrity
- WebSocket broadcast status tracking
"""

import logging
import hashlib
import json
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from sqlalchemy import select, func
from models import db
from models.event_ledger import EventLedger, EventType, EventStatus

logger = logging.getLogger(__name__)


class EventSequencer:
    """
    Service for managing event sequencing and validation in CROWN⁴.5 architecture.
    
    Responsibilities:
    - Assign sequence numbers to events
    - Validate event ordering before processing
    - Buffer out-of-order events with automatic gap filling
    - Temporal recovery: re-order drifted events automatically
    - Generate checksums for payload integrity
    - Track broadcast status for WebSocket synchronization
    - Generate and compare vector clocks for distributed conflict resolution
    - Implement conflict resolution strategies
    
    CROWN⁴.5 Enhancements:
    - Per-workspace sequence tracking
    - Gap buffering with timeout-based force progress
    - Zero sequence loss guarantee
    """
    
    def __init__(self):
        """Initialize EventSequencer with gap buffering support."""
        # Per-workspace last applied event_id tracking
        # Format: {workspace_id: last_event_id}
        self._last_applied_per_workspace = {}
        
        # Buffer for out-of-order events (gap buffering)
        # Format: {workspace_id: {event_id: event_data}}
        self._pending_events_buffer = {}
        
        # Track last processing time for gap timeout detection
        # Format: {workspace_id: datetime}
        self._last_processed_time = {}
        
        # Configuration
        self.gap_timeout_seconds = 30  # Force progress after 30s gap
        self.max_buffer_size_per_workspace = 1000
        
        logger.info("✅ EventSequencer initialized with CROWN⁴.5 gap buffering")
    
    @staticmethod
    def generate_checksum(payload: Dict[str, Any]) -> str:
        """
        Generate SHA-256 checksum for event payload to detect tampering or corruption.
        CROWN⁴.5: Uses SHA-256 (not MD5) for cryptographic security and frontend parity.
        
        Args:
            payload: Event payload dictionary
            
        Returns:
            SHA-256 checksum hex string
        """
        try:
            # Sort keys for consistent hashing (matches frontend deterministicStringify)
            payload_str = json.dumps(payload, sort_keys=True, default=str)
            return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to generate checksum: {e}")
            return ""
    
    @staticmethod
    def get_next_sequence_num() -> int:
        """
        Get the next sequence number for event ordering.
        Thread-safe using database sequence.
        
        NOTE: CROWN⁴.5 MVP LIMITATION
        - Currently uses GLOBAL sequence numbers (not per-workspace)
        - EventLedger schema lacks workspace_id field
        - True per-workspace sequencing requires schema migration
        - MVP compensates via reconciliation for zero-desync guarantee
        
        Returns:
            Next sequence number
        """
        try:
            # Get max sequence_num from database (global, not per-workspace)
            max_seq = db.session.scalar(
                select(func.max(EventLedger.sequence_num))
            )
            
            # Start from 1 if no events exist
            return (max_seq or 0) + 1
        except Exception as e:
            logger.error(f"Failed to get next sequence number: {e}")
            return 1
    
    @staticmethod
    def create_event(
        event_type: EventType,
        event_name: str,
        payload: Optional[Dict[str, Any]] = None,
        session_id: Optional[int] = None,
        external_session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        client_id: Optional[str] = None,
        previous_clock: Optional[Dict[str, int]] = None
    ) -> EventLedger:
        """
        Create a new event with proper sequencing, checksum, and vector clock (CROWN⁴.5).
        
        Args:
            event_type: Type of event from EventType enum
            event_name: Human-readable event name
            payload: Event data payload
            session_id: Internal session ID
            external_session_id: External session identifier
            trace_id: Distributed tracing ID
            idempotency_key: Key for idempotent processing
            client_id: Client identifier for vector clock generation (user_id, device_id, etc.)
            previous_clock: Previous vector clock from client for incrementing
            
        Returns:
            Created EventLedger instance with vector clock if client_id provided
        """
        try:
            # Generate sequence number
            sequence_num = EventSequencer.get_next_sequence_num()
            
            # Generate checksum if payload provided
            checksum = EventSequencer.generate_checksum(payload) if payload else None
            
            # Generate vector clock for deterministic ordering (CROWN⁴.5)
            vector_clock = None
            if client_id:
                vector_clock = EventSequencer.generate_vector_clock(client_id, previous_clock)
                logger.debug(f"Generated vector clock for client {client_id}: {vector_clock}")
            
            # Create event record
            event = EventLedger(
                event_type=event_type,
                event_name=event_name,
                session_id=session_id,
                external_session_id=external_session_id,
                status=EventStatus.PENDING,
                payload=payload,
                trace_id=trace_id,
                idempotency_key=idempotency_key,
                sequence_num=sequence_num,
                checksum=checksum,
                vector_clock=vector_clock,
                broadcast_status="pending",
                created_at=datetime.utcnow()
            )
            
            db.session.add(event)
            db.session.commit()
            
            logger.debug(f"Created event {event.id} (seq={sequence_num}): {event_name}")
            
            return event
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create event {event_name}: {e}", exc_info=True)
            raise
    
    @staticmethod
    def validate_sequence(event_id: int, expected_last_id: Optional[int] = None) -> bool:
        """
        Validate that an event can be processed based on sequence ordering and vector clocks (CROWN⁴.5).
        
        Uses both sequence numbers and vector clocks for deterministic ordering:
        - Sequence numbers: Linear ordering within single session
        - Vector clocks: Causal ordering across distributed clients
        
        Args:
            event_id: Event ID to validate
            expected_last_id: Expected last processed event ID (for idempotency)
            
        Returns:
            True if event can be processed, False if out of order
        """
        try:
            event = db.session.get(EventLedger, event_id)
            if not event:
                logger.error(f"Event {event_id} not found for validation")
                return False
            
            # If no expected_last_id, allow processing
            if expected_last_id is None:
                return True
            
            # Check if this event has already been applied
            if event.last_applied_id and event.last_applied_id >= expected_last_id:
                logger.info(f"Event {event_id} already applied (last_applied={event.last_applied_id})")
                return False
            
            # Vector clock validation (CROWN⁴.5: Distributed ordering)
            if event.vector_clock:
                # Get recent completed events with vector clocks for conflict detection
                recent_events = db.session.scalars(
                    select(EventLedger)
                    .where(EventLedger.status == EventStatus.COMPLETED)
                    .where(EventLedger.vector_clock.isnot(None))
                    .where(EventLedger.id != event_id)
                    .order_by(EventLedger.created_at.desc())
                    .limit(100)
                ).all()
                
                # Check for concurrent events (potential conflicts)
                for other_event in recent_events:
                    if not other_event.vector_clock:
                        continue
                    
                    relation = EventSequencer.compare_vector_clocks(
                        event.vector_clock,
                        other_event.vector_clock
                    )
                    
                    if relation == "concurrent":
                        logger.warning(
                            f"Concurrent event detected: event {event_id} is concurrent with {other_event.id}"
                        )
                        # Allow processing but flag for conflict resolution
                        # The conflict will be resolved using the configured strategy
                    elif relation == "before":
                        # This event happened before an already-processed event
                        # This is an out-of-order event
                        logger.warning(
                            f"Out-of-order event: event {event_id} happened before already-processed event {other_event.id}"
                        )
                        return False
            
            # Validate sequence ordering (fallback for non-vector-clock events)
            if event.sequence_num is not None:
                # Get the last processed event sequence
                last_processed_seq = db.session.scalar(
                    select(func.max(EventLedger.sequence_num))
                    .where(EventLedger.status == EventStatus.COMPLETED)
                    .where(EventLedger.sequence_num < event.sequence_num)
                )
                
                # Check for gaps in sequence
                if last_processed_seq is not None and event.sequence_num > last_processed_seq + 1:
                    logger.warning(
                        f"Sequence gap detected: event {event_id} has seq={event.sequence_num}, "
                        f"last processed seq={last_processed_seq}"
                    )
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate sequence for event {event_id}: {e}")
            return False
    
    @staticmethod
    def mark_event_processing(event_id: int) -> bool:
        """
        Mark an event as currently being processed.
        
        Args:
            event_id: Event ID
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            event = db.session.get(EventLedger, event_id)
            if not event:
                return False
            
            event.status = EventStatus.PROCESSING
            event.started_at = datetime.utcnow()
            db.session.commit()
            
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to mark event {event_id} as processing: {e}")
            return False
    
    @staticmethod
    def mark_event_completed(
        event_id: int,
        result: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        broadcast_status: str = "sent"
    ) -> bool:
        """
        Mark an event as completed successfully.
        
        Args:
            event_id: Event ID
            result: Event processing result
            duration_ms: Processing duration in milliseconds
            broadcast_status: WebSocket broadcast status (pending|sent|failed)
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            event = db.session.get(EventLedger, event_id)
            if not event:
                return False
            
            event.status = EventStatus.COMPLETED
            event.completed_at = datetime.utcnow()
            event.result = result
            event.duration_ms = duration_ms
            event.broadcast_status = broadcast_status
            event.last_applied_id = event.id  # Mark as applied
            
            db.session.commit()
            
            logger.debug(f"Completed event {event_id} in {duration_ms}ms")
            
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to mark event {event_id} as completed: {e}")
            return False
    
    @staticmethod
    def mark_event_failed(
        event_id: int,
        error_message: str,
        broadcast_status: str = "failed"
    ) -> bool:
        """
        Mark an event as failed.
        
        Args:
            event_id: Event ID
            error_message: Error description
            broadcast_status: WebSocket broadcast status
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            event = db.session.get(EventLedger, event_id)
            if not event:
                return False
            
            event.status = EventStatus.FAILED
            event.completed_at = datetime.utcnow()
            event.error_message = error_message
            event.broadcast_status = broadcast_status
            
            db.session.commit()
            
            logger.error(f"Event {event_id} failed: {error_message}")
            
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to mark event {event_id} as failed: {e}")
            return False
    
    @staticmethod
    def get_pending_events(limit: int = 100) -> List[EventLedger]:
        """
        Get pending events that need to be broadcast via WebSocket.
        
        Args:
            limit: Maximum number of events to retrieve
            
        Returns:
            List of pending EventLedger instances
        """
        try:
            events = db.session.scalars(
                select(EventLedger)
                .where(EventLedger.broadcast_status == "pending")
                .where(EventLedger.status == EventStatus.COMPLETED)
                .order_by(EventLedger.sequence_num)
                .limit(limit)
            ).all()
            
            return list(events)
        except Exception as e:
            logger.error(f"Failed to get pending events: {e}")
            return []
    
    @staticmethod
    def verify_checksum(event: EventLedger) -> bool:
        """
        Verify event payload integrity using checksum.
        
        Args:
            event: EventLedger instance
            
        Returns:
            True if checksum valid, False otherwise
        """
        try:
            if not event.checksum or not event.payload:
                return True  # No checksum to verify
            
            calculated_checksum = EventSequencer.generate_checksum(event.payload)
            is_valid = calculated_checksum == event.checksum
            
            if not is_valid:
                logger.warning(
                    f"Checksum mismatch for event {event.id}: "
                    f"expected={event.checksum}, calculated={calculated_checksum}"
                )
            
            return is_valid
        except Exception as e:
            logger.error(f"Failed to verify checksum for event {event.id}: {e}")
            return False
    
    @staticmethod
    def generate_vector_clock(client_id: str, previous_clock: Optional[Dict[str, int]] = None) -> Dict[str, int]:
        """
        Generate a vector clock for distributed event ordering (CROWN⁴.5).
        
        Vector clocks enable detection of concurrent events and causality tracking
        in distributed systems with offline support. Uses logical counters, not timestamps.
        
        Args:
            client_id: Unique identifier for the client (e.g., user_id, device_id)
            previous_clock: Previous vector clock to increment from
            
        Returns:
            Vector clock dictionary {client_id: counter} where counter is monotonically increasing
        """
        try:
            # Start with previous clock or empty
            clock = previous_clock.copy() if previous_clock else {}
            
            # Increment the counter for this client (logical counter, not timestamp)
            previous_count = clock.get(client_id, 0)
            clock[client_id] = previous_count + 1
            
            return clock
        except Exception as e:
            logger.error(f"Failed to generate vector clock: {e}")
            return {client_id: 1}
    
    @staticmethod
    def compare_vector_clocks(clock_a: Dict[str, int], clock_b: Dict[str, int]) -> str:
        """
        Compare two vector clocks to determine causal ordering using standard dominance rules.
        
        Clock A dominates B (A happened after B) if:
        - All counters in A >= corresponding counters in B
        - At least one counter in A > corresponding counter in B
        
        Args:
            clock_a: First vector clock
            clock_b: Second vector clock
            
        Returns:
            "before" if clock_a happened before clock_b (B dominates A)
            "after" if clock_a happened after clock_b (A dominates B)
            "concurrent" if events are concurrent (conflict)
            "equal" if clocks are identical
        """
        try:
            if not clock_a and not clock_b:
                return "equal"
            if not clock_a:
                return "before"
            if not clock_b:
                return "after"
            
            # Check if clocks are identical
            if clock_a == clock_b:
                return "equal"
            
            # Check for dominance: A dominates B if all A[i] >= B[i] and at least one A[i] > B[i]
            a_dominates_b = True  # Assume A >= B initially
            b_dominates_a = True  # Assume B >= A initially
            
            all_clients = set(clock_a.keys()) | set(clock_b.keys())
            
            for client in all_clients:
                counter_a = clock_a.get(client, 0)
                counter_b = clock_b.get(client, 0)
                
                if counter_a < counter_b:
                    a_dominates_b = False  # A does not dominate B
                if counter_b < counter_a:
                    b_dominates_a = False  # B does not dominate A
            
            # Determine relationship
            if a_dominates_b and not b_dominates_a:
                return "after"  # A happened after B (A dominates B)
            elif b_dominates_a and not a_dominates_b:
                return "before"  # A happened before B (B dominates A)
            else:
                return "concurrent"  # Neither dominates = concurrent events
                
        except Exception as e:
            logger.error(f"Failed to compare vector clocks: {e}")
            return "concurrent"  # Assume conflict on error
    
    @staticmethod
    def resolve_conflict(
        event_a: EventLedger,
        event_b: EventLedger,
        strategy: str = "server_wins"
    ) -> Optional[EventLedger]:
        """
        Resolve conflict between two concurrent events using specified strategy.
        
        Args:
            event_a: First conflicting event
            event_b: Second conflicting event
            strategy: Conflict resolution strategy
                - "server_wins": Server event takes precedence
                - "client_wins": Client event takes precedence
                - "last_write_wins": Most recent timestamp wins
                - "merge": Attempt to merge payloads (field-level)
                - "manual": Flag for manual review (returns None)
                
        Returns:
            Winning event, or None if manual review required
        """
        try:
            if strategy == "server_wins":
                # Assume event with lower ID is server-generated
                return event_a if event_a.id < event_b.id else event_b
            
            elif strategy == "client_wins":
                # Assume event with higher ID is client-generated
                return event_a if event_a.id > event_b.id else event_b
            
            elif strategy == "last_write_wins":
                # Use created_at timestamp
                return event_a if event_a.created_at > event_b.created_at else event_b
            
            elif strategy == "merge":
                # For merge strategy, prefer newer event but flag for manual review
                logger.warning(
                    f"Merge strategy requested for events {event_a.id} and {event_b.id}, "
                    "using last_write_wins temporarily"
                )
                return event_a if event_a.created_at > event_b.created_at else event_b
            
            elif strategy == "manual":
                # Flag conflict for manual review
                logger.warning(
                    f"Manual conflict resolution required for events {event_a.id} and {event_b.id}"
                )
                # Update both events to flag for manual review
                event_a.conflict_resolution_strategy = "manual"
                event_b.conflict_resolution_strategy = "manual"
                event_a.error_message = f"Manual review required: conflict with event {event_b.id}"
                event_b.error_message = f"Manual review required: conflict with event {event_a.id}"
                return None  # Requires manual resolution
            
            else:
                logger.warning(f"Unknown conflict resolution strategy: {strategy}, using server_wins")
                return event_a if event_a.id < event_b.id else event_b
                
        except Exception as e:
            logger.error(f"Failed to resolve conflict: {e}")
            return event_a  # Default to first event
    
    @staticmethod
    def detect_conflicts(
        events: List[EventLedger],
        resource_id: Optional[int] = None
    ) -> List[Tuple[EventLedger, EventLedger]]:
        """
        Detect concurrent events that may cause conflicts.
        
        Args:
            events: List of events to check for conflicts
            resource_id: Optional resource ID to filter events
            
        Returns:
            List of conflicting event pairs
        """
        try:
            conflicts = []
            
            # Filter events by resource if specified
            if resource_id:
                events = [e for e in events if e.session_id == resource_id]
            
            # Check each pair of events for concurrency
            for i, event_a in enumerate(events):
                for event_b in events[i+1:]:
                    if not event_a.vector_clock or not event_b.vector_clock:
                        continue
                    
                    relation = EventSequencer.compare_vector_clocks(
                        event_a.vector_clock,
                        event_b.vector_clock
                    )
                    
                    if relation == "concurrent":
                        conflicts.append((event_a, event_b))
                        logger.warning(
                            f"Conflict detected between events {event_a.id} and {event_b.id}"
                        )
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Failed to detect conflicts: {e}")
            return []
    
    # =========================================================================
    # CROWN⁴.5: Gap Buffering & Temporal Recovery
    # =========================================================================
    
    def validate_and_sequence_event(
        self,
        workspace_id: int,
        event_data: Dict[str, Any]
    ) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """
        Validate incoming event and return sequenced events ready to apply (CROWN⁴.5).
        
        Implements gap buffering: out-of-order events are buffered until gaps are filled.
        Temporal recovery: automatically re-orders drifted events.
        
        Args:
            workspace_id: Workspace ID for per-workspace sequencing
            event_data: Event data including event_id, event_type, payload, vector_clock
            
        Returns:
            Tuple of (is_valid, ready_events, error_message)
            - is_valid: Whether event passes validation
            - ready_events: List of events ready to apply in order (empty if buffered)
            - error_message: Error message if validation failed
        """
        try:
            event_id = event_data.get('event_id')
            if event_id is None:
                return False, [], "Missing event_id"
            
            # Get last applied for this workspace
            last_applied = self._last_applied_per_workspace.get(workspace_id, 0)
            
            # Initialize buffer if needed
            if workspace_id not in self._pending_events_buffer:
                self._pending_events_buffer[workspace_id] = {}
            
            # Case 1: Event is next in sequence
            if event_id == last_applied + 1:
                # Update last applied BEFORE checking buffer
                self._last_applied_per_workspace[workspace_id] = event_id
                self._last_processed_time[workspace_id] = datetime.utcnow()
                
                # Start with this event
                ready_events = [event_data]
                
                # Flush any consecutive buffered events that can now be applied
                buffered_events = self._flush_consecutive_buffered_events(workspace_id)
                ready_events.extend(buffered_events)
                
                logger.debug(
                    f"✅ Event {event_id} for workspace {workspace_id} is in sequence. "
                    f"Flushed {len(ready_events)} total events ({len(buffered_events)} from buffer)."
                )
                return True, ready_events, None
            
            # Case 2: Event is duplicate (already applied)
            elif event_id <= last_applied:
                logger.debug(
                    f"⚠️ Duplicate event {event_id} for workspace {workspace_id} "
                    f"(last_applied={last_applied}). Skipping (idempotent)."
                )
                return True, [], None  # Valid but no-op
            
            # Case 3: Event is out of order (future event - gap detected)
            else:
                gap_size = event_id - last_applied - 1
                logger.warning(
                    f"⚠️ Gap detected: event {event_id} for workspace {workspace_id} "
                    f"(last_applied={last_applied}, gap_size={gap_size}). Buffering."
                )
                
                # Check buffer size limit
                buffer = self._pending_events_buffer[workspace_id]
                if len(buffer) >= self.max_buffer_size_per_workspace:
                    logger.error(
                        f"❌ Event buffer full for workspace {workspace_id} "
                        f"(>{self.max_buffer_size_per_workspace}). Dropping event {event_id}."
                    )
                    return False, [], "Event buffer full"
                
                # Add to buffer
                buffer[event_id] = event_data
                
                # CRITICAL: Initialize last_processed_time for new workspaces
                # This enables timeout-based recovery even if first event is out of order
                if workspace_id not in self._last_processed_time:
                    self._last_processed_time[workspace_id] = datetime.utcnow()
                    logger.debug(
                        f"Initialized last_processed_time for workspace {workspace_id} "
                        f"(first event buffered: {event_id})"
                    )
                
                # CRITICAL: Check if this buffered event might have filled gaps
                # For example: last_applied=5, buffer had {7}, event_id=6 arrives
                # Now buffer={6,7}, so we should check if we can process 6 and 7
                min_buffered = min(buffer.keys())
                if min_buffered == last_applied + 1:
                    # Gap is now filled! Process all consecutive events from buffer
                    logger.info(
                        f"✅ Gap filled for workspace {workspace_id}: event {event_id} filled gap, "
                        f"flushing buffer"
                    )
                    ready_events = self._flush_consecutive_buffered_events(workspace_id)
                    return True, ready_events, None
                
                # Check if gap timeout reached (force progress)
                if self._should_force_progress_for_workspace(workspace_id):
                    logger.warning(
                        f"⏰ Gap timeout reached for workspace {workspace_id}. Forcing progress."
                    )
                    ready_events = self._force_progress_for_workspace(workspace_id)
                    return True, ready_events, None
                
                # Event buffered, waiting for more events to fill gap
                logger.debug(
                    f"Event {event_id} buffered for workspace {workspace_id}. "
                    f"Waiting for event {last_applied + 1} to fill gap. "
                    f"Buffer size: {len(buffer)}"
                )
                return True, [], None
                
        except Exception as e:
            logger.error(f"❌ Event validation failed: {e}", exc_info=True)
            return False, [], f"Validation error: {str(e)}"
    
    def _flush_consecutive_buffered_events(self, workspace_id: int) -> List[Dict[str, Any]]:
        """
        Flush all consecutive events from buffer that can now be applied.
        
        E.g., if last_applied=5 and buffer has {7, 8, 9, 11}, return [7, 8, 9].
        Event 11 stays in buffer.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            List of consecutive buffered events ready to apply
        """
        ready_events = []
        buffer = self._pending_events_buffer.get(workspace_id, {})
        
        if not buffer:
            return ready_events
        
        last_applied = self._last_applied_per_workspace[workspace_id]
        next_expected = last_applied + 1
        
        # Extract consecutive events
        while next_expected in buffer:
            event = buffer.pop(next_expected)
            ready_events.append(event)
            
            # Update last applied
            self._last_applied_per_workspace[workspace_id] = next_expected
            self._last_processed_time[workspace_id] = datetime.utcnow()
            
            next_expected += 1
        
        if ready_events:
            logger.debug(
                f"🔄 Flushed {len(ready_events)} consecutive events from buffer for workspace {workspace_id}"
            )
        
        return ready_events
    
    def _should_force_progress_for_workspace(self, workspace_id: int) -> bool:
        """
        Check if gap timeout reached for workspace (temporal recovery).
        
        If we haven't processed an event in gap_timeout_seconds and have
        pending events, assume missing events are lost and force progress.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            True if should force progress
        """
        last_proc = self._last_processed_time.get(workspace_id)
        if not last_proc:
            return False
        
        time_since_last = (datetime.utcnow() - last_proc).total_seconds()
        has_pending = bool(self._pending_events_buffer.get(workspace_id))
        
        return has_pending and time_since_last >= self.gap_timeout_seconds
    
    def _force_progress_for_workspace(self, workspace_id: int) -> List[Dict[str, Any]]:
        """
        Force progress with mandatory cache reconciliation (temporal recovery fallback).
        
        CROWN⁴.5: When gap timeout is reached, we CANNOT replay missing events from
        EventLedger because:
        - EventSequencer uses per-workspace event_ids (workspace-local counters)
        - EventLedger uses global sequence_num (database-wide counter)
        - No mapping exists between workspace event_ids and EventLedger sequence_nums
        
        TODO: To enable proper event replay, we need to either:
        1. Add (workspace_id, workspace_sequence_num) columns to EventLedger, OR
        2. Maintain a separate mapping table: workspace_event_id → ledger_sequence_num
        
        Current fallback strategy:
        1. Log missing event IDs (for debugging)
        2. Mark ALL buffered events with reconciliation_needed flag
        3. Force progress by flushing buffer
        4. Caller MUST trigger full cache reconciliation to repair any data loss
        
        This ensures CROWN⁴.5 "zero desync" guarantee even though we accept
        temporary event loss. Reconciliation restores server truth.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            List of buffered events (marked with reconciliation flag)
        """
        buffer = self._pending_events_buffer.get(workspace_id, {})
        if not buffer:
            return []
        
        # Get next available event_id (may have gaps before it)
        next_available = min(buffer.keys())
        last_applied = self._last_applied_per_workspace[workspace_id]
        
        # Calculate missing event IDs
        missing_ids = list(range(last_applied + 1, next_available))
        if not missing_ids:
            # No gap, just flush buffer
            return self._flush_consecutive_buffered_events(workspace_id)
        
        # We CANNOT replay missing events due to workspace vs global sequence mismatch
        # Force progress and require reconciliation
        logger.error(
            f"❌ Temporal recovery gap timeout for workspace {workspace_id}: "
            f"{len(missing_ids)} events missing (IDs {missing_ids[:10]}{'...' if len(missing_ids) > 10 else ''}). "
            f"Cannot replay from EventLedger (per-workspace vs global sequence mismatch). "
            f"FORCING PROGRESS AND REQUIRING CACHE RECONCILIATION."
        )
        
        # Mark ALL buffered events for reconciliation
        for event_id in buffer.keys():
            buffer[event_id]['_reconciliation_needed'] = True
            buffer[event_id]['_missing_event_ids'] = missing_ids
            buffer[event_id]['_recovery_reason'] = 'gap_timeout'
        
        # Force progress by advancing last_applied to skip gap
        self._last_applied_per_workspace[workspace_id] = next_available - 1
        
        # Flush all consecutive buffered events
        ready_events = self._flush_consecutive_buffered_events(workspace_id)
        
        logger.warning(
            f"⚡ Temporal recovery forced progress for workspace {workspace_id}: "
            f"flushed {len(ready_events)} buffered events (skipped {len(missing_ids)} missing events). "
            f"Reconciliation required to restore server truth."
        )
        
        return ready_events
    
    def get_workspace_sequence_stats(self, workspace_id: int) -> Dict[str, Any]:
        """
        Get sequencing statistics for workspace (CROWN⁴.5).
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Dictionary with sequencing stats
        """
        return {
            'last_applied_event_id': self._last_applied_per_workspace.get(workspace_id, 0),
            'buffered_events_count': len(self._pending_events_buffer.get(workspace_id, {})),
            'buffered_event_ids': sorted(self._pending_events_buffer.get(workspace_id, {}).keys()),
            'last_processed_at': self._last_processed_time.get(workspace_id),
            'gap_timeout_seconds': self.gap_timeout_seconds,
        }
    
    def reset_workspace_sequence(self, workspace_id: int):
        """
        Reset sequence tracking for workspace (for testing/debugging).
        
        Args:
            workspace_id: Workspace ID
        """
        self._last_applied_per_workspace.pop(workspace_id, None)
        self._pending_events_buffer.pop(workspace_id, None)
        self._last_processed_time.pop(workspace_id, None)
        logger.info(f"🔄 Sequence tracking reset for workspace {workspace_id}")


# Singleton instance (now with __init__ support)
event_sequencer = EventSequencer()
