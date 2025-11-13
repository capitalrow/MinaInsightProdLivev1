-- Add semantic search embeddings to tasks table
-- CROWN⁴.6: AI Semantic Search for context-aware task discovery

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Handle embedding column: create or convert from TEXT to VECTOR
DO $$
BEGIN
    -- Check if column exists
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tasks' AND column_name='embedding') THEN
        -- Column exists - check if it's TEXT and convert to VECTOR
        IF (SELECT data_type FROM information_schema.columns WHERE table_name='tasks' AND column_name='embedding') = 'text' THEN
            -- Drop any indexes on the TEXT column first
            DROP INDEX IF EXISTS tasks_embedding_idx;
            
            -- Convert TEXT to VECTOR (handles string format '[1.0,2.0,...]')
            ALTER TABLE tasks ALTER COLUMN embedding TYPE VECTOR(1536) USING COALESCE(embedding::VECTOR, NULL);
            RAISE NOTICE 'Converted tasks.embedding from TEXT to VECTOR(1536)';
        END IF;
    ELSE
        -- Column doesn't exist - create it as VECTOR
        ALTER TABLE tasks ADD COLUMN embedding VECTOR(1536);
        RAISE NOTICE 'Created tasks.embedding as VECTOR(1536)';
    END IF;
END $$;

-- Add embedding metadata columns (safe IF NOT EXISTS)
ALTER TABLE tasks 
ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(64) DEFAULT 'text-embedding-3-small',
ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMP WITH TIME ZONE;

-- Create index for fast cosine similarity searches
-- IVFFLAT index for approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS tasks_embedding_idx 
ON tasks USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Add comment for documentation
COMMENT ON COLUMN tasks.embedding IS 'OpenAI embedding vector for semantic search (text-embedding-3-small, 1536 dimensions)';
COMMENT ON COLUMN tasks.embedding_model IS 'Embedding model used (for version tracking and re-embedding triggers)';
COMMENT ON COLUMN tasks.embedding_updated_at IS 'Last time embedding was computed (NULL indicates needs refresh)';
