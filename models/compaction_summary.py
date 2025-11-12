"""
CompactionSummary Model for Event Ledger Compaction Audit Trail

Stores summaries of compacted EventLedger entries to maintain audit trail.
"""

from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, JSON, func
from .base import Base


class CompactionSummary(Base):
    """
    Stores summaries of compacted event ledger entries.
    Maintains audit trail after original events are deleted.
    """
    __tablename__ = "compaction_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Workspace isolation (CRITICAL for multi-tenant security)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    # Compaction metadata
    compaction_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    total_events_compacted: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Event summary
    events_by_type: Mapped[Dict[str, Any]] = mapped_column(JSON)  # {event_type: count}
    events_by_status: Mapped[Dict[str, Any]] = mapped_column(JSON)  # {status: count}
    
    # Performance summary
    total_duration_ms: Mapped[float] = mapped_column(nullable=True)
    avg_duration_ms: Mapped[float] = mapped_column(nullable=True)
    
    # Date range of compacted events
    earliest_event_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    latest_event_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Compaction results
    events_deleted: Mapped[int] = mapped_column(Integer, default=0)
    compaction_success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[str] = mapped_column(String(500), nullable=True)

    def __repr__(self):
        return f'<CompactionSummary {self.id}: {self.total_events_compacted} events on {self.compaction_date}>'

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'compaction_date': self.compaction_date.isoformat() if self.compaction_date else None,
            'total_events_compacted': self.total_events_compacted,
            'events_by_type': self.events_by_type,
            'events_by_status': self.events_by_status,
            'total_duration_ms': self.total_duration_ms,
            'avg_duration_ms': self.avg_duration_ms,
            'earliest_event_date': self.earliest_event_date.isoformat() if self.earliest_event_date else None,
            'latest_event_date': self.latest_event_date.isoformat() if self.latest_event_date else None,
            'events_deleted': self.events_deleted,
            'compaction_success': self.compaction_success,
            'error_message': self.error_message
        }
