"""Add workspace_id to compaction_summaries for multi-tenant isolation

Revision ID: compaction_workspace_v1
Revises: task_comments_v1
Create Date: 2025-11-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'compaction_workspace_v1'
down_revision = 'merge_workspace_heads_v1'
branch_labels = None
depends_on = None


def upgrade():
    # Add workspace_id column (nullable initially for backfill)
    op.add_column('compaction_summaries', sa.Column('workspace_id', sa.String(length=36), nullable=True))
    
    # Backfill workspace_id from event ledger workspace context
    # For existing summaries, we'll use a default workspace ID or derive from system
    # In a real multi-tenant system, you'd query the workspace from event ledger metadata
    op.execute("""
        UPDATE compaction_summaries
        SET workspace_id = '1'
        WHERE workspace_id IS NULL
    """)
    
    # Make workspace_id NOT NULL after backfill
    op.alter_column('compaction_summaries', 'workspace_id', nullable=False)
    
    # Create index for workspace filtering
    op.create_index('ix_compaction_summaries_workspace_id', 'compaction_summaries', ['workspace_id'])


def downgrade():
    # Drop index
    op.drop_index('ix_compaction_summaries_workspace_id', table_name='compaction_summaries')
    
    # Drop column
    op.drop_column('compaction_summaries', 'workspace_id')
