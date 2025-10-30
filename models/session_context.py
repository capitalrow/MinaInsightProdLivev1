"""
SessionContext Model - CROWN⁴.5 Shared Cross-Domain Link

Connects tasks, transcripts, and AI insights with unified context tracking.
Enables bidirectional navigation between tasks and transcript spans.
"""

from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func, JSON, Float, Index
from sqlalchemy.ext.mutable import MutableDict, MutableList
from .base import Base

if TYPE_CHECKING:
    from .meeting import Meeting
    from .task import Task


class SessionContext(Base):
    """
    SessionContext provides shared context linking tasks to transcript moments.
    
    Key Features:
    - Links AI-extracted tasks to their source transcript segments
    - Stores origin message and extraction confidence
    - Tracks all derived entities (tasks, insights, decisions)
    - Enables "Jump to transcript" functionality
    - Supports deduplication via origin_hash
    """
    __tablename__ = "session_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Session linkage
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    meeting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("meetings.id"), nullable=True)
    
    # Transcript span (precise moment in conversation) - MUTABLE for SQLAlchemy tracking
    transcript_span: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), nullable=False)
    # Format: {
    #   "start_ms": int,
    #   "end_ms": int,
    #   "segment_ids": [int, int, ...],
    #   "speaker": str (optional),
    #   "confidence": float (optional)
    # }
    
    # Origin tracking
    origin_message: Mapped[str] = mapped_column(Text, nullable=False)  # Original transcript text
    origin_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # SHA-256 for deduplication
    
    # Context metadata
    context_type: Mapped[str] = mapped_column(String(32), default="task_extraction")
    # Types: task_extraction, insight_generation, decision_capture, question_raised
    
    context_confidence: Mapped[float] = mapped_column(Float, default=0.0)  # AI confidence 0-1
    
    # Derived entities (JSON array of references) - MUTABLE for in-place append tracking
    derived_entities: Mapped[list] = mapped_column(MutableList.as_mutable(JSON), default=list)
    # Format: [
    #   {"type": "task", "id": 123, "status": "accepted"},
    #   {"type": "insight", "id": 456, "status": "generated"},
    # ]
    
    # Additional context - MUTABLE for SQLAlchemy tracking
    extraction_metadata: Mapped[Optional[dict]] = mapped_column(MutableDict.as_mutable(JSON))
    # Stores AI model used, prompt version, processing time, etc.
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(32), default="active")
    # active, archived, merged, superseded
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    meeting: Mapped[Optional["Meeting"]] = relationship(back_populates="session_contexts")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_session_contexts_session', 'session_id'),
        Index('ix_session_contexts_origin_hash', 'origin_hash'),
        Index('ix_session_contexts_type_status', 'context_type', 'status'),
    )

    def __repr__(self):
        return f'<SessionContext {self.id}: {self.context_type} @ session={self.session_id}>'
    
    def add_derived_entity(self, entity_type: str, entity_id: int, status: str = "active") -> None:
        """Add a derived entity reference"""
        if self.derived_entities is None:
            self.derived_entities = []
        
        self.derived_entities.append({
            "type": entity_type,
            "id": entity_id,
            "status": status,
            "created_at": datetime.utcnow().isoformat()
        })
    
    def get_transcript_url(self) -> Optional[str]:
        """Generate URL to jump to transcript span"""
        if not self.session_id or not self.transcript_span:
            return None
        
        start_ms = self.transcript_span.get('start_ms')
        if start_ms is None:
            return None
        
        return f"/sessions/{self.session_id}/transcript?t={start_ms}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'meeting_id': self.meeting_id,
            'transcript_span': self.transcript_span,
            'origin_message': self.origin_message,
            'origin_hash': self.origin_hash,
            'context_type': self.context_type,
            'context_confidence': self.context_confidence,
            'derived_entities': self.derived_entities,
            'status': self.status,
            'transcript_url': self.get_transcript_url(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
