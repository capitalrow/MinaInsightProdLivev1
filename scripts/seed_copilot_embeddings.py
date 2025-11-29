"""
Seed Copilot Embeddings Script

Generates OpenAI embeddings from real meetings and tasks in the database.
Uses raw SQL to avoid ORM relationship issues.
"""

import os
import sys
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
engine = create_engine(DATABASE_URL)

def generate_embedding(text_content: str) -> list:
    """Generate embedding using OpenAI's text-embedding-3-large model."""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-large",
            input=text_content[:8000],
            dimensions=1536
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None

def format_vector(embedding: list) -> str:
    """Format embedding list as pgvector string."""
    return f"[{','.join(str(x) for x in embedding)}]"

def seed_task_embeddings():
    """Generate embeddings for all tasks."""
    with engine.connect() as conn:
        tasks = conn.execute(text("""
            SELECT id, title, description, status, priority, due_date, workspace_id, created_by_id
            FROM tasks WHERE deleted_at IS NULL
        """)).fetchall()
        
        logger.info(f"Found {len(tasks)} tasks to embed")
        
        count = 0
        for task in tasks:
            task_id, title, description, status, priority, due_date, workspace_id, created_by_id = task
            
            text_content = f"Task: {title}"
            if description:
                text_content += f" - {description}"
            text_content += f" | Status: {status} | Priority: {priority}"
            if due_date:
                text_content += f" | Due: {due_date.isoformat() if hasattr(due_date, 'isoformat') else str(due_date)}"
            
            existing = conn.execute(text("""
                SELECT id FROM copilot_embeddings 
                WHERE text = :text AND context_type = 'task'
            """), {"text": text_content}).fetchone()
            
            if existing:
                continue
            
            embedding = generate_embedding(text_content)
            if embedding:
                vector_str = format_vector(embedding)
                conn.execute(text("""
                    INSERT INTO copilot_embeddings (user_id, workspace_id, text, embedding, context_type, created_at)
                    VALUES (:user_id, :workspace_id, :text, CAST(:embedding AS vector), :context_type, :created_at)
                """), {
                    "user_id": created_by_id if created_by_id else 1,
                    "workspace_id": workspace_id,
                    "text": text_content,
                    "embedding": vector_str,
                    "context_type": "task",
                    "created_at": datetime.utcnow()
                })
                conn.commit()
                count += 1
                logger.info(f"Embedded task: {title[:50]}...")
        
        logger.info(f"Created {count} task embeddings")
        return count

def seed_meeting_embeddings():
    """Generate embeddings for meeting transcripts."""
    with engine.connect() as conn:
        sessions = conn.execute(text("""
            SELECT id, title, user_id, workspace_id FROM sessions WHERE status = 'completed'
        """)).fetchall()
        
        logger.info(f"Found {len(sessions)} completed sessions")
        
        count = 0
        for session in sessions:
            session_id, title, user_id, workspace_id = session
            
            segments = conn.execute(text("""
                SELECT text FROM segments 
                WHERE session_id = :session_id AND text IS NOT NULL
                ORDER BY id
            """), {"session_id": session_id}).fetchall()
            
            if not segments:
                continue
            
            full_transcript = " ".join([s[0] for s in segments if s[0]])
            if len(full_transcript) < 50:
                continue
            
            text_content = f"Meeting: {title} | Transcript: {full_transcript[:2000]}"
            
            existing = conn.execute(text("""
                SELECT id FROM copilot_embeddings 
                WHERE context_type = 'meeting' AND text LIKE :pattern
            """), {"pattern": f"Meeting: {title}%"}).fetchone()
            
            if existing:
                continue
            
            embedding = generate_embedding(text_content)
            if embedding:
                vector_str = format_vector(embedding)
                conn.execute(text("""
                    INSERT INTO copilot_embeddings (user_id, workspace_id, text, embedding, context_type, created_at)
                    VALUES (:user_id, :workspace_id, :text, CAST(:embedding AS vector), :context_type, :created_at)
                """), {
                    "user_id": user_id if user_id else 1,
                    "workspace_id": workspace_id,
                    "text": text_content,
                    "embedding": vector_str,
                    "context_type": "meeting",
                    "created_at": datetime.utcnow()
                })
                conn.commit()
                count += 1
                logger.info(f"Embedded meeting: {title} (id={session_id})")
        
        logger.info(f"Created {count} meeting embeddings")
        return count

def seed_segment_embeddings():
    """Generate embeddings for individual transcript segments."""
    with engine.connect() as conn:
        segments = conn.execute(text("""
            SELECT seg.id, seg.session_id, seg.text, s.user_id, s.workspace_id
            FROM segments seg
            JOIN sessions s ON seg.session_id = s.id
            WHERE seg.text IS NOT NULL AND LENGTH(seg.text) > 30
            ORDER BY seg.id DESC
            LIMIT 30
        """)).fetchall()
        
        logger.info(f"Found {len(segments)} segments to embed")
        
        count = 0
        for segment in segments:
            seg_id, session_id, seg_text, user_id, workspace_id = segment
            
            text_content = f"Transcript segment: {seg_text}"
            
            existing = conn.execute(text("""
                SELECT id FROM copilot_embeddings 
                WHERE text = :text AND context_type = 'segment'
            """), {"text": text_content}).fetchone()
            
            if existing:
                continue
            
            embedding = generate_embedding(text_content)
            if embedding:
                vector_str = format_vector(embedding)
                conn.execute(text("""
                    INSERT INTO copilot_embeddings (user_id, workspace_id, text, embedding, context_type, created_at)
                    VALUES (:user_id, :workspace_id, :text, CAST(:embedding AS vector), :context_type, :created_at)
                """), {
                    "user_id": user_id if user_id else 1,
                    "workspace_id": workspace_id,
                    "text": text_content,
                    "embedding": vector_str,
                    "context_type": "segment",
                    "created_at": datetime.utcnow()
                })
                conn.commit()
                count += 1
        
        logger.info(f"Created {count} segment embeddings")
        return count

def main():
    """Run all embedding seeders."""
    logger.info("Starting copilot embeddings seeding...")
    
    with engine.connect() as conn:
        initial_count = conn.execute(text("SELECT COUNT(*) FROM copilot_embeddings")).scalar()
        logger.info(f"Initial embedding count: {initial_count}")
    
    task_count = seed_task_embeddings()
    meeting_count = seed_meeting_embeddings()
    segment_count = seed_segment_embeddings()
    
    with engine.connect() as conn:
        final_count = conn.execute(text("SELECT COUNT(*) FROM copilot_embeddings")).scalar()
        logger.info(f"Final embedding count: {final_count}")
    
    print(f"\n=== Embedding Seeding Complete ===")
    print(f"Tasks embedded: {task_count}")
    print(f"Meetings embedded: {meeting_count}")
    print(f"Segments embedded: {segment_count}")
    print(f"Total embeddings in DB: {final_count}")

if __name__ == "__main__":
    main()
