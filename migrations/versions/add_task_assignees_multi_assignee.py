"""Add task_assignees junction table for multi-assignee support - CROWN⁴.5

Revision ID: crown45_multi_assignee
Revises: crown45_merge_heads
Create Date: 2025-11-03

Implements multi-assignee support for tasks through a many-to-many relationship.
This enables collaborative task management where multiple users can be assigned
to a single task, addressing a key limitation of the single assigned_to_id FK.

Changes:
- Create task_assignees junction table with (task_id, user_id) composite key
- Add metadata columns: assigned_at, assigned_by_user_id, role
- Cascade deletes when tasks or users are deleted
- Composite unique index prevents duplicate assignments
- Backfill existing assigned_to_id relationships into junction table

Migration Path:
1. Create task_assignees table
2. Backfill from tasks.assigned_to_id (preserves existing assignments)
3. Keep tasks.assigned_to_id for backward compatibility (dual-write pattern)
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'crown45_multi_assignee'
down_revision = 'crown45_merge_heads'
branch_labels = None
depends_on = None


def upgrade():
    """Create task_assignees junction table and backfill existing assignments."""
    
    # Create junction table for many-to-many Task <-> User relationship
    op.create_table(
        'task_assignees',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('assigned_by_user_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.String(32), nullable=False, server_default='assignee'),
        
        # Foreign key constraints with CASCADE delete
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )
    
    # Create indexes for performance
    op.create_index('ix_task_assignees_task_id', 'task_assignees', ['task_id'])
    op.create_index('ix_task_assignees_user_id', 'task_assignees', ['user_id'])
    
    # Composite unique constraint to prevent duplicate assignments
    op.create_index(
        'ix_task_assignees_composite',
        'task_assignees',
        ['task_id', 'user_id'],
        unique=True
    )
    
    # CRITICAL: Backfill junction table from existing tasks.assigned_to_id
    # This preserves all current task assignments during migration
    op.execute("""
        INSERT INTO task_assignees (task_id, user_id, assigned_at, role)
        SELECT 
            id as task_id,
            assigned_to_id as user_id,
            COALESCE(created_at, CURRENT_TIMESTAMP) as assigned_at,
            'assignee' as role
        FROM tasks
        WHERE assigned_to_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    """Remove task_assignees table (WARNING: loses multi-assignee data)."""
    
    # Drop indexes first
    op.drop_index('ix_task_assignees_composite', table_name='task_assignees')
    op.drop_index('ix_task_assignees_user_id', table_name='task_assignees')
    op.drop_index('ix_task_assignees_task_id', table_name='task_assignees')
    
    # Drop junction table
    # WARNING: This loses multi-assignee data, but tasks.assigned_to_id is preserved
    op.drop_table('task_assignees')
