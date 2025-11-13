"""Add task position field for drag-drop reordering

Revision ID: 20251103_192944
Revises: add_task_assignees_multi_assignee
Create Date: 2025-11-03 19:29:44

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251103_192944'
down_revision = 'add_task_assignees_multi_assignee'
branch_labels = None
depends_on = None


def upgrade():
    # Add position column with default value 0
    op.add_column('tasks', sa.Column('position', sa.Integer(), nullable=False, server_default='0'))
    
    # Create index for position ordering
    op.create_index('ix_tasks_position', 'tasks', ['position'])
    
    # Initialize positions for existing tasks (ordered by created_at)
    # This ensures existing tasks maintain their current order
    op.execute("""
        UPDATE tasks
        SET position = sub.row_num
        FROM (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) - 1 as row_num
            FROM tasks
        ) AS sub
        WHERE tasks.id = sub.id
    """)


def downgrade():
    # Drop index
    op.drop_index('ix_tasks_position', table_name='tasks')
    
    # Drop column
    op.drop_column('tasks', 'position')
