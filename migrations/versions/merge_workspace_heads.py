"""Merge workspace isolation heads

Revision ID: merge_workspace_heads_v1
Revises: 20251103_192944, task_comments_v1
Create Date: 2025-11-13 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_workspace_heads_v1'
down_revision = ('20251103_192944', 'task_comments_v1')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no schema changes needed
    pass


def downgrade():
    # This is a merge migration - no downgrade needed
    pass
