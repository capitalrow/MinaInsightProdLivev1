"""Add soft delete fields to tasks table (CROWN⁴.5 Phase 1)

Revision ID: crown45_soft_delete
Revises: crown45_task_fields
Create Date: 2025-11-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'crown45_soft_delete'
down_revision = 'crown45_task_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Add soft delete fields to tasks table for CROWN⁴.5 Phase 1: Task Deletion."""
    
    # Add CROWN⁴.5 Phase 1: Soft delete fields
    op.add_column('tasks', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('tasks', sa.Column('deleted_by_user_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint for deleted_by_user_id
    op.create_foreign_key(
        'fk_tasks_deleted_by_user_id',
        'tasks', 'users',
        ['deleted_by_user_id'], ['id']
    )
    
    # Create index for soft delete filtering (critical for performance)
    op.create_index('ix_tasks_deleted_at', 'tasks', ['deleted_at'])


def downgrade():
    """Remove soft delete fields from tasks table."""
    
    # Drop index
    op.drop_index('ix_tasks_deleted_at', table_name='tasks')
    
    # Drop foreign key constraint
    op.drop_constraint('fk_tasks_deleted_by_user_id', 'tasks', type_='foreignkey')
    
    # Drop columns
    op.drop_column('tasks', 'deleted_by_user_id')
    op.drop_column('tasks', 'deleted_at')
