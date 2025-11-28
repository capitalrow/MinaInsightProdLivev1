"""
Copilot Embedding Model

Stores embeddings for semantic search and context retrieval.
Enables the AI to find related conversations and context intelligently.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime, ARRAY, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import db

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace


class CopilotEmbedding(db.Model):
    """
    Embeddings for semantic similarity search.
    
    Stores vector embeddings of:
    - User queries
    - Task descriptions
    - Meeting summaries
    - Workspace context
    """
    __tablename__ = 'copilot_embeddings'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    workspace_id: Mapped[Optional[int]] = mapped_column(ForeignKey('workspaces.id'), nullable=True)
    
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(ARRAY(Float), nullable=False)
    context_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="copilot_embeddings", foreign_keys=[user_id])
    workspace: Mapped[Optional["Workspace"]] = relationship(back_populates="copilot_embeddings", foreign_keys=[workspace_id])
    
    def __repr__(self) -> str:
        return f"<CopilotEmbedding {self.id} type={self.context_type}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'workspace_id': self.workspace_id,
            'text': self.text,
            'context_type': self.context_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
