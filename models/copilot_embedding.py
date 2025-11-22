"""
Copilot Embedding Model

Stores embeddings for semantic search and context retrieval.
Enables the AI to find related conversations and context intelligently.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, ARRAY, Float
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from app import db


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
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=True)
    
    text = Column(Text, nullable=False)
    embedding = Column(ARRAY(Float), nullable=False)
    context_type = Column(String(50), nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship('User', backref='copilot_embeddings')
    workspace = relationship('Workspace', backref='copilot_embeddings')
    
    def __repr__(self):
        return f"<CopilotEmbedding {self.id} type={self.context_type}>"
    
    def to_dict(self):
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'workspace_id': self.workspace_id,
            'text': self.text,
            'context_type': self.context_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
