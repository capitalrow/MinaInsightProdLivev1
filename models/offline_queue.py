from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, ForeignKey, Index, JSON, UniqueConstraint
from .base import Base


class OfflineQueue(Base):
    """
    Store offline queue entries for backup and recovery.
    Allows frontend to persist its offline queue to server.
    """
    __tablename__ = 'offline_queues'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    
    queue_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_offline_queue_user_session', 'user_id', 'session_id'),
        UniqueConstraint('user_id', 'session_id', name='uq_offline_queue_user_session'),
    )
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'queue_data': self.queue_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
