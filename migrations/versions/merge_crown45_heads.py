"""Merge CROWN⁴.5 migration heads

Revision ID: crown45_merge_heads
Revises: crown45_workspace_seq, crown45_soft_delete
Create Date: 2025-11-03

Merge migration to collapse multiple migration heads into a single linear history.
This merge resolves the branching that occurred when multiple CROWN⁴.5 features
were developed in parallel.

Branches being merged:
1. crown45_workspace_seq - Per-workspace event sequencing
2. crown45_soft_delete - Soft delete for tasks

After this merge, all future migrations should revise 'crown45_merge_heads'
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'crown45_merge_heads'
down_revision = ('crown45_workspace_seq', 'crown45_soft_delete')  # Tuple merges multiple heads
branch_labels = None
depends_on = None


def upgrade():
    """
    No operations needed - this is a pure merge migration.
    All schema changes are in the parent migrations.
    """
    pass


def downgrade():
    """
    No operations needed - this is a pure merge migration.
    Downgrading will split back into the two parent branches.
    """
    pass
