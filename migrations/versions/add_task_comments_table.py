"""Add task_comments table for CROWN⁴.5 Task 7

Revision ID: task_comments_v1
Revises: 
Create Date: 2025-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'task_comments_v1'
down_revision = 'crown45_merge_heads'
branch_labels = None
depends_on = None


def upgrade():
    # Create task_comments table
    op.create_table(
        'task_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('ix_task_comments_task_id', 'task_comments', ['task_id'])
    op.create_index('ix_task_comments_user_id', 'task_comments', ['user_id'])
    op.create_index('ix_task_comments_created_at', 'task_comments', ['created_at'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_task_comments_created_at', table_name='task_comments')
    op.drop_index('ix_task_comments_user_id', table_name='task_comments')
    op.drop_index('ix_task_comments_task_id', table_name='task_comments')
    
    # Drop table
    op.drop_table('task_comments')
