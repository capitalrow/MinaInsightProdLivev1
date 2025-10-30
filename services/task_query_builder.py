"""
Task Query Builder - Shared query logic for workspace task filtering

Ensures template routes and API endpoints return identical task sets.
CROWN⁴.5 compliance: Deterministic data layer for cache consistency.
"""

from sqlalchemy import select, or_, and_
from models import Task, Meeting, User


class TaskQueryBuilder:
    """
    Builds consistent task queries for workspace-based filtering.
    Used by both template routes and API endpoints to ensure cache matches DOM.
    """
    
    @staticmethod
    def get_workspace_tasks_query(workspace_id, include_archived=False):
        """
        Get all tasks for a workspace (meeting-linked AND manually created).
        
        Args:
            workspace_id: Workspace ID to filter by
            include_archived: Whether to include archived tasks
            
        Returns:
            SQLAlchemy select statement for tasks in workspace
        """
        # CROWN⁴.5: Use LEFT OUTER JOIN to include tasks without meetings
        # Tasks belong to workspace through either:
        # 1. Meeting's workspace (for AI-extracted tasks)
        # 2. Creator's workspace (for manually created tasks)
        stmt = select(Task).outerjoin(
            Meeting, Task.meeting_id == Meeting.id
        ).outerjoin(
            User, Task.created_by_id == User.id
        ).where(
            or_(
                Meeting.workspace_id == workspace_id,
                and_(Task.meeting_id.is_(None), User.workspace_id == workspace_id)
            )
        )
        
        return stmt
    
    @staticmethod
    def get_ordered_tasks_query(workspace_id, order_by='due_date'):
        """
        Get workspace tasks with default ordering.
        
        Args:
            workspace_id: Workspace ID to filter by
            order_by: Ordering strategy ('due_date', 'priority', 'created_at')
            
        Returns:
            SQLAlchemy select statement with ordering
        """
        stmt = TaskQueryBuilder.get_workspace_tasks_query(workspace_id)
        
        # Apply ordering
        if order_by == 'due_date':
            stmt = stmt.order_by(
                Task.due_date.asc().nullslast(),
                Task.priority.desc(),
                Task.created_at.desc()
            )
        elif order_by == 'priority':
            stmt = stmt.order_by(Task.priority.desc(), Task.created_at.desc())
        elif order_by == 'created_at':
            stmt = stmt.order_by(Task.created_at.desc())
        
        return stmt
