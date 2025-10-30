"""
EventLedger Model - Atomic event tracking for CROWN+ Event Sequencing

Every event in Mina is tracked for auditability, replay, and debugging.
Ensures atomic, idempotent, and traceable event history.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, JSON, Enum as SQLEnum, Index, ForeignKey, Text, func
import enum
from .base import Base


class EventStatus(enum.Enum):
    """Event processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventType(enum.Enum):
    """CROWN⁴ Event Types - Complete event sequencing for living memory layer"""
    # Recording Phase
    RECORD_START = "record_start"
    AUDIO_CHUNK_SENT = "audio_chunk_sent"
    TRANSCRIPT_PARTIAL = "transcript_partial"
    RECORD_STOP = "record_stop"
    
    # Post-Transcription Phase
    TRANSCRIPT_FINALIZED = "transcript_finalized"
    TRANSCRIPT_REFINED = "transcript_refined"
    INSIGHTS_GENERATE = "insights_generate"
    POST_TRANSCRIPTION_REVEAL = "post_transcription_reveal"
    
    # Reflection Phase
    SESSION_REFINED_READY = "session_refined_ready"
    ANALYTICS_UPDATE = "analytics_update"
    TASKS_GENERATION = "tasks_generation"
    SESSION_FINALIZED = "session_finalized"
    
    # User Interactions
    EDIT_COMMIT = "edit_commit"
    DASHBOARD_REFRESH = "dashboard_refresh"
    REPLAY_ENGAGE = "replay_engage"
    TASK_COMPLETE = "task_complete"
    
    # System Events
    ERROR_OCCURRED = "error_occurred"
    RECOVERY_ATTEMPTED = "recovery_attempted"
    
    # CROWN⁴ Real-time Synchronization Events (Phase 2)
    DASHBOARD_BOOTSTRAP = "dashboard_bootstrap"  # Initial dashboard load with cache
    SESSION_UPDATE_CREATED = "session_update:created"  # New session/meeting created
    SESSION_PREFETCH = "session_prefetch"  # Prefetch meeting metadata on hover
    TASK_UPDATE = "task_update"  # Task status changed
    ANALYTICS_REFRESH = "analytics_refresh"  # Analytics data updated
    DASHBOARD_IDLE_SYNC = "dashboard_idle_sync"  # Background sync every 30s
    FILTER_APPLY = "filter_apply"  # Dashboard filter changed
    SESSION_CARD_CLICK = "session_card_click"  # User clicked meeting card
    SESSION_REFINED_LOAD = "session_refined_load"  # Detailed session page loaded
    SESSION_ARCHIVE = "session_archive"  # Meeting archived
    ARCHIVE_REVEAL = "archive_reveal"  # Show archived meetings
    INSIGHT_REMINDER = "insight_reminder"  # AI-generated reminder displayed
    SEARCH_QUERY = "search_query"  # User performed search query
    UI_STATE_SYNC = "ui_state_sync"  # UI state synchronized across tabs
    MEETING_UPDATE = "meeting_update"  # Meeting data changed
    PARTICIPANT_UPDATE = "participant_update"  # Participant joined/left
    WORKSPACE_SWITCH = "workspace_switch"  # User switched workspace
    CACHE_INVALIDATE = "cache_invalidate"  # Force cache refresh


class EventLedger(Base):
    """
    Event Ledger for tracking all system events.
    
    Implements CROWN+ philosophy:
    - Atomic: Each event is a single unit of truth
    - Idempotent: Can be replayed safely
    - Traceable: Full audit trail for debugging and compliance
    """
    __tablename__ = "event_ledger"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Event identification
    event_type: Mapped[EventType] = mapped_column(SQLEnum(EventType), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)  # Human-readable name
    
    # Session linkage
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('sessions.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    external_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    # Event metadata
    status: Mapped[EventStatus] = mapped_column(
        SQLEnum(EventStatus),
        default=EventStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Timing
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Event data and context
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Event input data
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)   # Event output data
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Tracing and correlation
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # For distributed tracing
    parent_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('event_ledger.id'),
        nullable=True
    )
    
    # Performance tracking
    duration_ms: Mapped[Optional[float]] = mapped_column(nullable=True)  # Event processing time
    
    # Versioning for idempotency
    event_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    
    # CROWN⁴ Event Sequencing fields
    sequence_num: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)  # Global event ordering
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # MD5 hash for data integrity
    broadcast_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # pending|sent|failed
    last_applied_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Last processed event ID for idempotency
    
    # CROWN⁴.5: Vector clock for distributed conflict resolution
    vector_clock: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # {client_id: timestamp, ...}
    conflict_resolution_strategy: Mapped[str] = mapped_column(String(32), default="server_wins")  # server_wins, client_wins, merge, manual
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_event_ledger_session_created', 'session_id', 'created_at'),
        Index('ix_event_ledger_type_status', 'event_type', 'status'),
        Index('ix_event_ledger_trace_created', 'trace_id', 'created_at'),
        Index('ix_event_ledger_sequence', 'sequence_num'),
    )
    
    def __repr__(self):
        return f'<EventLedger {self.event_type.value} session={self.external_session_id} status={self.status.value}>'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'event_type': self.event_type.value,
            'event_name': self.event_name,
            'session_id': self.session_id,
            'external_session_id': self.external_session_id,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'payload': self.payload,
            'result': self.result,
            'error_message': self.error_message,
            'trace_id': self.trace_id,
            'duration_ms': self.duration_ms,
            'event_version': self.event_version,
            'sequence_num': self.sequence_num,
            'checksum': self.checksum,
            'broadcast_status': self.broadcast_status,
            'vector_clock': self.vector_clock,
            'conflict_resolution_strategy': self.conflict_resolution_strategy
        }
    
    @property
    def is_completed(self) -> bool:
        """Check if event completed successfully"""
        return self.status == EventStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Check if event failed"""
        return self.status == EventStatus.FAILED
    
    @property
    def processing_time_seconds(self) -> Optional[float]:
        """Get processing time in seconds"""
        return self.duration_ms / 1000.0 if self.duration_ms else None
