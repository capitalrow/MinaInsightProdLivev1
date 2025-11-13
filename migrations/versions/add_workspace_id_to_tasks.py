"""Add workspace_id to tasks for multi-tenant isolation

Revision ID: task_workspace_v1
Revises: compaction_workspace_v1
Create Date: 2025-11-13 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'task_workspace_v1'
down_revision = 'compaction_workspace_v1'
branch_labels = None
depends_on = None


def upgrade():
    # Add workspace_id column (nullable initially for backfill)
    op.add_column('tasks', sa.Column('workspace_id', sa.String(length=36), nullable=True))
    
    # Backfill workspace_id from related tables with priority:
    # 1. From meeting.workspace_id (if task has meeting)
    # 2. From session.workspace_id (if task has session)
    # 3. From assigned_to user's workspace_id
    # 4. From created_by user's workspace_id
    # 5. Default to workspace '1' as fallback
    
    # Priority 1: Tasks with meetings
    op.execute("""
        UPDATE tasks t
        SET workspace_id = CAST(m.workspace_id AS VARCHAR)
        FROM meetings m
        WHERE t.meeting_id = m.id AND t.workspace_id IS NULL
    """)
    
    # Priority 2: Tasks with sessions (but no meeting)
    op.execute("""
        UPDATE tasks t
        SET workspace_id = CAST(s.workspace_id AS VARCHAR)
        FROM sessions s
        WHERE t.session_id = s.id 
        AND s.workspace_id IS NOT NULL 
        AND t.workspace_id IS NULL
    """)
    
    # Priority 3: Tasks assigned to users (fallback)
    op.execute("""
        UPDATE tasks t
        SET workspace_id = CAST(u.workspace_id AS VARCHAR)
        FROM users u
        WHERE t.assigned_to_id = u.id 
        AND u.workspace_id IS NOT NULL 
        AND t.workspace_id IS NULL
    """)
    
    # Priority 4: Tasks created by users (fallback)
    op.execute("""
        UPDATE tasks t
        SET workspace_id = CAST(u.workspace_id AS VARCHAR)
        FROM users u
        WHERE t.created_by_id = u.id 
        AND u.workspace_id IS NOT NULL 
        AND t.workspace_id IS NULL
    """)
    
    # Priority 5: Default fallback for any remaining tasks
    op.execute("""
        UPDATE tasks
        SET workspace_id = '1'
        WHERE workspace_id IS NULL
    """)
    
    # Make workspace_id NOT NULL after backfill
    op.alter_column('tasks', 'workspace_id', nullable=False)
    
    # Create index for workspace filtering (critical for multi-tenant queries)
    op.create_index('ix_tasks_workspace_id', 'tasks', ['workspace_id'])


def downgrade():
    # Drop index
    op.drop_index('ix_tasks_workspace_id', table_name='tasks')
    
    # Drop column
    op.drop_column('tasks', 'workspace_id')
