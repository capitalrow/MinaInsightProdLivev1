"""
Copilot Embedding Model

Stores embeddings for semantic search and context retrieval.
Enables the AI to find related conversations and context intelligently.

Uses pgvector extension for efficient cosine similarity search.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, Any
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import TypeDecorator

from . import db

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace


class Vector(TypeDecorator):
    """Custom type for pgvector vector columns."""
    impl = Text
    cache_ok = True
    
    def __init__(self, dimensions: int = 1536):
        super().__init__()
        self.dimensions = dimensions
    
    def load_dialect_impl(self, dialect):
        """Load dialect-specific implementation."""
        return dialect.type_descriptor(Text())
    
    def process_bind_param(self, value, dialect):
        """Convert Python list to vector string."""
        if value is None:
            return None
        if isinstance(value, list):
            return f"[{','.join(str(x) for x in value)}]"
        return value
    
    def process_result_value(self, value, dialect):
        """Convert vector string back to Python list."""
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip('[]')
            return [float(x) for x in value.split(',')] if value else []
        return value


class CopilotEmbedding(db.Model):
    """
    Embeddings for semantic similarity search.
    
    Stores vector embeddings of:
    - User queries
    - Task descriptions
    - Meeting summaries
    - Workspace context
    
    Uses pgvector for efficient cosine similarity search with <=> operator.
    """
    __tablename__ = 'copilot_embeddings'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    workspace_id: Mapped[Optional[int]] = mapped_column(ForeignKey('workspaces.id'), nullable=True)
    
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=False)
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
