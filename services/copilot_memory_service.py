"""
CROWN⁹ Copilot Memory Service

Manages persistent memory, embeddings, and context retraining.
Implements Event #11: context_retrain for post-interaction learning.

Features:
- Conversation history persistence
- Embedding generation for semantic search
- Context memory graph
- User preference learning
- Workspace state caching
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy import desc

logger = logging.getLogger(__name__)


class CopilotMemoryService:
    """
    Service for managing copilot memory, embeddings, and learning.
    
    Responsibilities:
    - Store conversation history
    - Generate embeddings for semantic context
    - Build user preference profiles
    - Cache workspace state
    - Event #11: Retrain context after interactions
    """
    
    def __init__(self):
        """Initialize memory service."""
        self.embedding_cache = {}
        logger.info("Copilot Memory Service initialized")
    
    def store_conversation(
        self,
        user_id: int,
        workspace_id: Optional[int],
        message: str,
        response: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> int:
        """
        Store conversation in database for memory persistence.
        Stores as two separate messages (user + assistant).
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            message: User query
            response: AI response
            context: Additional context data
            session_id: Session identifier
            
        Returns:
            Last message ID
        """
        from models import db
        from models.copilot_conversation import CopilotConversation
        
        try:
            # Store user message
            user_msg = CopilotConversation()
            user_msg.user_id = user_id
            user_msg.role = 'user'
            user_msg.message = message
            user_msg.session_id = session_id
            db.session.add(user_msg)
            
            # Store assistant response
            assistant_msg = CopilotConversation()
            assistant_msg.user_id = user_id
            assistant_msg.role = 'assistant'
            assistant_msg.message = response
            assistant_msg.session_id = session_id
            db.session.add(assistant_msg)
            
            db.session.commit()
            
            logger.debug(f"Stored conversation pair for user {user_id}, session {session_id}")
            return assistant_msg.id  # type: ignore[return-value]
            
        except Exception as e:
            logger.error(f"Failed to store conversation: {e}", exc_info=True)
            db.session.rollback()
            return -1
    
    def get_recent_conversations(
        self,
        user_id: int,
        workspace_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent conversations for context building.
        
        Args:
            user_id: User ID
            workspace_id: Optional workspace filter
            limit: Number of messages to retrieve
            
        Returns:
            List of conversation message dicts
        """
        from models import db
        from models.copilot_conversation import CopilotConversation
        
        try:
            query = db.session.query(CopilotConversation)\
                .filter(CopilotConversation.user_id == user_id)
            
            conversations = query\
                .order_by(desc(CopilotConversation.created_at))\
                .limit(limit)\
                .all()
            
            return [
                {
                    'id': c.id,
                    'role': c.role,
                    'message': c.message,
                    'session_id': c.session_id,
                    'created_at': c.created_at.isoformat() if c.created_at else None
                }
                for c in conversations
            ]
            
        except Exception as e:
            logger.error(f"Failed to retrieve conversations: {e}", exc_info=True)
            return []
    
    def generate_embedding(
        self,
        text: str,
        use_cache: bool = True
    ) -> Optional[List[float]]:
        """
        Generate embedding vector for text using OpenAI embeddings.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings
            
        Returns:
            Embedding vector or None if failed
        """
        import os
        
        # Check cache first
        if use_cache:
            cache_key = hashlib.md5(text.encode()).hexdigest()
            if cache_key in self.embedding_cache:
                logger.debug(f"Embedding cache hit for {cache_key[:8]}")
                return self.embedding_cache[cache_key]
        
        try:
            # Connect directly to OpenAI for embeddings
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                logger.debug("Embeddings disabled: OPENAI_API_KEY not configured")
                return None
            
            from openai import OpenAI
            
            # Direct connection to api.openai.com (no base_url override)
            client = OpenAI(api_key=api_key)
            
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            
            embedding = response.data[0].embedding
            
            # Cache the result
            if use_cache:
                cache_key = hashlib.md5(text.encode()).hexdigest()
                self.embedding_cache[cache_key] = embedding
            
            logger.debug(f"Generated embedding with {len(embedding)} dimensions")
            return embedding
            
        except Exception as e:
            logger.debug(f"Embeddings unavailable: {e}")
            return None
    
    def store_embedding(
        self,
        user_id: int,
        workspace_id: Optional[int],
        text: str,
        embedding: List[float],
        context_type: str = "conversation"
    ) -> int:
        """
        Store embedding in database for semantic search.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            text: Original text
            embedding: Embedding vector
            context_type: Type of context (conversation, task, meeting, etc.)
            
        Returns:
            Embedding ID
        """
        from models import db
        from models.copilot_embedding import CopilotEmbedding
        
        try:
            emb = CopilotEmbedding()
            emb.user_id = user_id
            emb.workspace_id = workspace_id
            emb.text = text
            emb.embedding = embedding
            emb.context_type = context_type
            emb.created_at = datetime.utcnow()
            
            db.session.add(emb)
            db.session.commit()
            
            logger.debug(f"Stored embedding {emb.id} for user {user_id}")
            return emb.id  # type: ignore[return-value]
            
        except Exception as e:
            logger.error(f"Failed to store embedding: {e}", exc_info=True)
            db.session.rollback()
            return -1
    
    def retrain_context(
        self,
        user_id: int,
        workspace_id: Optional[int],
        interaction_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Event #11: context_retrain
        
        Adjust embeddings and memory after interaction.
        Learns from user patterns, preferences, and successful queries.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            interaction_data: {
                'message': str,
                'response': str,
                'action': Optional[str],
                'success': bool
            }
            
        Returns:
            Retrain result with stats
        """
        logger.info(f"Context retrain for user {user_id}, workspace {workspace_id}")
        
        try:
            message = interaction_data.get('message', '')
            response = interaction_data.get('response', '')
            action = interaction_data.get('action')
            success = interaction_data.get('success', True)
            
            result = {
                'embeddings_generated': 0,
                'conversations_stored': 0,
                'success': True
            }
            
            # Store conversation for history
            if message and response:
                conv_id = self.store_conversation(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    message=message,
                    response=response,
                    context={'action': action, 'success': success}
                )
                if conv_id > 0:
                    result['conversations_stored'] = 1
            
            # Generate and store embeddings for successful interactions
            if success and message:
                embedding = self.generate_embedding(message)
                if embedding:
                    emb_id = self.store_embedding(
                        user_id=user_id,
                        workspace_id=workspace_id,
                        text=message,
                        embedding=embedding,
                        context_type='query'
                    )
                    if emb_id > 0:
                        result['embeddings_generated'] = 1
            
            logger.debug(f"Context retrain result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Context retrain failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def get_semantic_context(
        self,
        query: str,
        user_id: int,
        workspace_id: Optional[int],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve semantically similar context using vector similarity search (RAG).
        
        CROWN⁹ Enhanced RAG:
        - Uses pgvector for cosine similarity search
        - Falls back to recent conversations if embeddings unavailable
        - Combines embeddings with conversation history
        
        Args:
            query: User query
            user_id: User ID
            workspace_id: Workspace ID
            limit: Number of similar contexts to return
            
        Returns:
            List of similar contexts with similarity scores
        """
        from models import db
        
        results = []
        
        try:
            # Generate embedding for query
            query_embedding = self.generate_embedding(query)
            
            if query_embedding:
                # Use pgvector cosine similarity search
                try:
                    from models.copilot_embedding import CopilotEmbedding
                    from sqlalchemy import text
                    
                    # Build similarity search query using pgvector
                    # Uses cosine distance: 1 - (a <=> b) gives similarity score
                    embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
                    
                    sql_query = text("""
                        SELECT 
                            id,
                            text,
                            context_type,
                            created_at,
                            1 - (embedding <=> :query_embedding::vector) as similarity
                        FROM copilot_embeddings
                        WHERE user_id = :user_id
                        AND (workspace_id = :workspace_id OR workspace_id IS NULL)
                        ORDER BY embedding <=> :query_embedding::vector
                        LIMIT :limit
                    """)
                    
                    result = db.session.execute(sql_query, {
                        'query_embedding': embedding_str,
                        'user_id': user_id,
                        'workspace_id': workspace_id,
                        'limit': limit
                    })
                    
                    for row in result:
                        similarity_score = float(row.similarity) if row.similarity else 0.0
                        
                        # Only include results with reasonable similarity (> 0.5)
                        if similarity_score > 0.5:
                            results.append({
                                'id': row.id,
                                'text': row.text,
                                'context_type': row.context_type,
                                'created_at': row.created_at.isoformat() if row.created_at else None,
                                'similarity': round(similarity_score, 3),
                                'source': 'embedding'
                            })
                    
                    logger.debug(f"RAG search found {len(results)} similar contexts for query")
                    
                except Exception as embed_error:
                    logger.warning(f"Vector similarity search failed, using fallback: {embed_error}")
            
            # Supplement with recent conversations if needed
            if len(results) < limit:
                remaining = limit - len(results)
                conversations = self.get_recent_conversations(user_id, workspace_id, remaining)
                
                for conv in conversations:
                    # Check if already in results to avoid duplicates
                    if not any(r.get('text') == conv.get('message') for r in results):
                        results.append({
                            'text': conv.get('message', ''),
                            'context_type': 'conversation',
                            'created_at': conv.get('created_at'),
                            'similarity': 0.3,  # Lower score for non-semantic matches
                            'source': 'conversation_history'
                        })
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Semantic context retrieval failed: {e}", exc_info=True)
            # Fallback to recent conversations
            return self.get_recent_conversations(user_id, workspace_id, limit)
    
    def clear_cache(self):
        """Clear embedding cache."""
        self.embedding_cache.clear()
        logger.debug("Embedding cache cleared")


# Singleton instance
copilot_memory_service = CopilotMemoryService()
