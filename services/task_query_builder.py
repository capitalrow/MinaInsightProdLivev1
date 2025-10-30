"""
Task Query Builder - Shared query logic for workspace task filtering

Ensures template routes and API endpoints return identical task sets.
CROWN⁴.5 compliance: Deterministic data layer for cache consistency.
"""


def get_workspace_tasks_query(workspace_id):
    """
    Get all tasks for a workspace (meeting-linked AND manually created).
    
    CROWN⁴.5: Shared query builder used by both template routes and API endpoints
    to ensure cache consistency. Uses LEFT OUTER JOIN to include tasks with and
    without meeting associations.
    
    Args:
        workspace_id: Workspace ID to filter by
        
    Returns:
        SQLAlchemy select statement for tasks in workspace
    """
    # Import at runtime to avoid circular dependency deadlock
    from sqlalchemy import select, or_, and_
    from models import Task, Meeting, User
    
    # Use LEFT OUTER JOIN to include tasks without meetings
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
