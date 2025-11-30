"""
CROWN⁴.6 Task Embedding Service
Manages OpenAI embeddings for semantic task search.
"""

import logging
import os
from typing import List, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskEmbeddingService:
    """Service for generating and managing task embeddings for semantic search."""
    
    def __init__(self):
        """Initialize embedding service with OpenAI."""
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.client = None
        self.model = "text-embedding-3-small"  # 1536 dimensions
        
        # Check if using Replit AI proxy (doesn't support embeddings)
        base_url = os.environ.get('OPENAI_BASE_URL', '')
        if 'modelfarm' in base_url or 'replit' in base_url.lower():
            logger.info("⚠️ Embeddings disabled: Replit AI Integrations does not support embeddings API")
            return
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"✅ TaskEmbeddingService initialized with {self.model}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OpenAI: {e}")
        else:
            logger.debug("⚠️ OPENAI_API_KEY not set - semantic search disabled")
    
    def is_available(self) -> bool:
        """Check if embedding service is available."""
        return self.client is not None
    
    def get_task_text(self, task) -> str:
        """
        Get combined text for task embedding.
        
        Args:
            task: Task model instance or dict with 'title' and 'description'
            
        Returns:
            Combined text for embedding
        """
        if isinstance(task, dict):
            title = task.get('title', '')
            description = task.get('description', '')
        else:
            title = task.title or ''
            description = task.description or ''
        
        # Combine title and description with delimiter
        return f"{title}. {description}".strip()
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if service unavailable
        """
        if not self.client or not text:
            return None
        
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    def generate_task_embedding(self, task) -> Optional[List[float]]:
        """
        Generate embedding for a task.
        
        Args:
            task: Task model instance or dict
            
        Returns:
            Embedding vector or None if service unavailable
        """
        text = self.get_task_text(task)
        return self.generate_embedding(text)
    
    def update_task_embedding(self, task_orm) -> bool:
        """
        Update embedding for a task ORM instance.
        
        Args:
            task_orm: SQLAlchemy Task instance
            
        Returns:
            True if embedding updated, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            embedding = self.generate_task_embedding(task_orm)
            if embedding:
                # pgvector.sqlalchemy.Vector accepts Python lists directly
                task_orm.embedding = embedding if isinstance(embedding, list) else list(embedding)
                task_orm.embedding_model = self.model
                task_orm.embedding_updated_at = datetime.utcnow()
                return True
        except Exception as e:
            logger.error(f"Failed to update task embedding: {e}")
        
        return False
    
    def batch_generate_embeddings(self, texts: List[str], batch_size: int = 100) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (max 2048)
            
        Returns:
            List of embedding vectors
        """
        if not self.client:
            return [None] * len(texts)
        
        embeddings = []
        
        try:
            # Process in batches to avoid API limits
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
            
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            return [None] * len(texts)
    
    def backfill_task_embeddings(self, tasks, batch_size: int = 50) -> Dict[str, int]:
        """
        Backfill embeddings for tasks that don't have them.
        
        Args:
            tasks: List of Task ORM instances
            batch_size: Number of tasks to process per batch
            
        Returns:
            Dict with 'updated' and 'failed' counts
        """
        if not self.is_available():
            logger.warning("Cannot backfill - embedding service unavailable")
            return {'updated': 0, 'failed': 0}
        
        updated = 0
        failed = 0
        
        # Filter tasks that need embeddings
        tasks_to_update = [
            t for t in tasks 
            if t.embedding is None or t.embedding_updated_at is None
        ]
        
        if not tasks_to_update:
            logger.info("No tasks need embedding updates")
            return {'updated': 0, 'failed': 0}
        
        logger.info(f"Backfilling embeddings for {len(tasks_to_update)} tasks...")
        
        try:
            # Get texts for all tasks
            texts = [self.get_task_text(t) for t in tasks_to_update]
            
            # Generate embeddings in batches
            embeddings = self.batch_generate_embeddings(texts, batch_size)
            
            # Update tasks
            for task, embedding in zip(tasks_to_update, embeddings):
                if embedding:
                    # pgvector.sqlalchemy.Vector accepts Python lists directly
                    task.embedding = embedding if isinstance(embedding, list) else list(embedding)
                    task.embedding_model = self.model
                    task.embedding_updated_at = datetime.utcnow()
                    updated += 1
                else:
                    failed += 1
                    logger.warning(f"Failed to generate embedding for task {task.id}")
        
        except Exception as e:
            logger.error(f"Backfill failed: {e}")
            failed = len(tasks_to_update)
        
        logger.info(f"Backfill complete: {updated} updated, {failed} failed")
        return {'updated': updated, 'failed': failed}
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Similarity score (0-1)
        """
        import math
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)


# Singleton instance
_embedding_service = None


def get_embedding_service() -> TaskEmbeddingService:
    """Get singleton instance of TaskEmbeddingService."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = TaskEmbeddingService()
    return _embedding_service
