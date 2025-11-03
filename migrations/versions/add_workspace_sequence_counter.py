"""Add workspace_sequence_counter table for atomic sequence generation - CROWN⁴.5

Revision ID: crown45_counter_table
Revises: crown45_workspace_seq
Create Date: 2025-11-03

Implements atomic workspace sequence counter to eliminate race conditions.
Uses PostgreSQL INSERT ... ON CONFLICT to guarantee first-writer wins without
relying on exception handling or retry logic.

Changes:
- Create workspace_sequence_counter table with (workspace_id PRIMARY KEY, counter INTEGER)
- Initialize counter = 0 for each workspace
- EventSequencer uses INSERT ... ON CONFLICT UPDATE counter = counter + 1 RETURNING counter
- Eliminates empty-workspace race condition completely
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'crown45_counter_table'
down_revision = 'crown45_workspace_seq'
branch_labels = None
depends_on = None


def upgrade():
    """Create workspace_sequence_counter table for atomic counter management."""
    
    # Create dedicated counter table for workspace sequences
    # CROWN⁴.5: Atomic UPSERT operations eliminate all race conditions
    op.create_table(
        'workspace_sequence_counter',
        sa.Column('workspace_id', sa.String(36), primary_key=True, nullable=False,
                  comment='Workspace UUID (primary key)'),
        sa.Column('counter', sa.Integer, nullable=False, default=0,
                  comment='Current sequence counter for this workspace'),
        sa.Column('updated_at', sa.DateTime, nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP'),
                  comment='Last counter increment timestamp')
    )
    
    # Create index on updated_at for monitoring/cleanup
    op.create_index(
        'ix_workspace_sequence_counter_updated',
        'workspace_sequence_counter',
        ['updated_at']
    )
    
    # CRITICAL: Backfill counter table from existing event_ledger data
    # This prevents duplicate sequence numbers after migration
    # For each workspace that already has events, initialize counter to MAX(workspace_sequence_num)
    op.execute("""
        INSERT INTO workspace_sequence_counter (workspace_id, counter, updated_at)
        SELECT 
            workspace_id,
            COALESCE(MAX(workspace_sequence_num), 0) as counter,
            CURRENT_TIMESTAMP as updated_at
        FROM event_ledger
        WHERE workspace_id IS NOT NULL
        GROUP BY workspace_id
        ON CONFLICT (workspace_id) DO NOTHING
    """)


def downgrade():
    """Remove workspace_sequence_counter table."""
    
    op.drop_index('ix_workspace_sequence_counter_updated', table_name='workspace_sequence_counter')
    op.drop_table('workspace_sequence_counter')
