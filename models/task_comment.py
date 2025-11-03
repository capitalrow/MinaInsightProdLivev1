"""
TaskComment Model - Comments and collaboration on tasks
CROWN⁴.5 Task 7: Task Detail Modal
"""

from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func
from .base import Base


class TaskComment(Base):
    """
    Comments on tasks for collaboration and discussion.
    
    Features:
    - Multi-user commenting
    - Timestamps for created/updated
    - Soft delete support
    - User attribution
    """
    __tablename__ = "task_comments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Task relationship
    task_id: Mapped[int] = mapped_column(
        ForeignKey('tasks.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Author information
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Comment content
    text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Soft delete
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    # task = relationship('Task', back_populates='comments')
    # user = relationship('User')
    
    def __repr__(self):
        return f'<TaskComment task_id={self.task_id} user_id={self.user_id}>'
    
    def to_dict(self):
        """Convert comment to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user_id': self.user_id,
            'text': self.text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }
