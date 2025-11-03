"""Add per-workspace event sequencing to EventLedger - CROWN⁴.5

Revision ID: crown45_workspace_seq
Revises: crown45_task_fields
Create Date: 2025-11-03

Implements CROWN⁴.5 per-workspace event sequencing to resolve the critical
limitation where concurrent workspace updates share global sequence numbers,
causing spurious forward gaps and excessive reconciliation.

Changes:
- Add workspace_id (String(36), indexed) - UUID workspace identifier
- Add workspace_sequence_num (Integer, indexed) - Per-workspace event counter
- Create composite index (workspace_id, workspace_sequence_num) for efficient queries
- Keep global sequence_num for backward compatibility

Post-migration: EventSequencer.get_next_sequence_num() must be updated to accept workspace_id
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'crown45_workspace_seq'
down_revision = 'add_meeting_archive_crown4'  # Latest head revision
branch_labels = None
depends_on = None


def upgrade():
    """Add per-workspace sequencing fields to event_ledger table."""
    
    # Add workspace_id column (nullable initially to handle existing data)
    # CROWN⁴.5: Use String(36) for UUID compatibility
    op.add_column('event_ledger', sa.Column(
        'workspace_id',
        sa.String(36),
        nullable=True,  # Nullable for existing events
        comment='Workspace UUID for per-workspace event sequencing'
    ))
    
    # Add workspace_sequence_num column (nullable initially)
    # CROWN⁴.5: Per-workspace monotonic counter
    op.add_column('event_ledger', sa.Column(
        'workspace_sequence_num',
        sa.Integer,
        nullable=True,  # Nullable for existing events
        comment='Monotonic sequence number within workspace for deterministic ordering'
    ))
    
    # Create index on workspace_id for efficient filtering
    op.create_index(
        'ix_event_ledger_workspace_id',
        'event_ledger',
        ['workspace_id']
    )
    
    # Create composite index on (workspace_id, workspace_sequence_num) for ordered queries
    # CROWN⁴.5: Critical for efficient event replay and gap detection
    op.create_index(
        'ix_event_ledger_workspace_sequence',
        'event_ledger',
        ['workspace_id', 'workspace_sequence_num']
    )
    
    # Create composite index on (workspace_id, created_at) for time-based queries
    op.create_index(
        'ix_event_ledger_workspace_created',
        'event_ledger',
        ['workspace_id', 'created_at']
    )
    
    # CROWN⁴.5 CRITICAL: Add unique constraint to prevent duplicate workspace sequences
    # PostgreSQL unique constraints allow multiple NULLs (NULL != NULL), so this is safe
    # for existing records while enforcing uniqueness for new workspace-scoped events
    op.create_unique_constraint(
        'uq_event_ledger_workspace_sequence',
        'event_ledger',
        ['workspace_id', 'workspace_sequence_num']
    )


def downgrade():
    """Remove per-workspace sequencing fields from event_ledger table."""
    
    # Drop unique constraint
    op.drop_constraint('uq_event_ledger_workspace_sequence', 'event_ledger', type_='unique')
    
    # Drop indexes
    op.drop_index('ix_event_ledger_workspace_created', table_name='event_ledger')
    op.drop_index('ix_event_ledger_workspace_sequence', table_name='event_ledger')
    op.drop_index('ix_event_ledger_workspace_id', table_name='event_ledger')
    
    # Drop columns
    op.drop_column('event_ledger', 'workspace_sequence_num')
    op.drop_column('event_ledger', 'workspace_id')
