"""
CROWN⁴.5 Phase 1: Task Purge Background Job
Hard-deletes soft-deleted tasks after T+7 days (7-day retention).
"""

import logging
from datetime import datetime, timedelta
from app import db
from models import Task
from sqlalchemy import select, func

logger = logging.getLogger(__name__)


def purge_deleted_tasks():
    """
    Purge tasks that have been soft-deleted for more than 7 days.
    This is a background job that should run daily.
    
    Returns:
        dict: Status with number of tasks purged
    """
    try:
        # Calculate the cutoff date (7 days ago)
        cutoff_date = datetime.now() - timedelta(days=7)
        
        logger.info(f"[TASK_PURGE] Starting purge job. Cutoff date: {cutoff_date.isoformat()}")
        
        # Find tasks deleted more than 7 days ago
        stmt = select(Task).where(
            Task.deleted_at.isnot(None),
            Task.deleted_at < cutoff_date
        )
        
        tasks_to_purge = db.session.execute(stmt).scalars().all()
        purge_count = len(tasks_to_purge)
        
        if purge_count == 0:
            logger.info("[TASK_PURGE] No tasks to purge")
            return {
                'success': True,
                'purged_count': 0,
                'message': 'No tasks to purge'
            }
        
        # Log tasks being purged
        logger.info(f"[TASK_PURGE] Found {purge_count} tasks to purge:")
        for task in tasks_to_purge:
            deleted_time = task.deleted_at.isoformat() if task.deleted_at else 'unknown'
            logger.info(f"  - Task ID {task.id}: '{task.title}' (deleted {deleted_time})")
        
        # Hard delete the tasks
        for task in tasks_to_purge:
            db.session.delete(task)
        
        db.session.commit()
        
        logger.info(f"[TASK_PURGE] Successfully purged {purge_count} tasks")
        
        return {
            'success': True,
            'purged_count': purge_count,
            'message': f'Successfully purged {purge_count} tasks',
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[TASK_PURGE] Error during purge: {str(e)}", exc_info=True)
        return {
            'success': False,
            'purged_count': 0,
            'error': str(e)
        }


def get_purgeable_task_count():
    """
    Get the count of tasks eligible for purging (deleted > 7 days ago).
    Useful for monitoring and alerts.
    
    Returns:
        int: Number of tasks that would be purged
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=7)
        
        stmt = select(Task).where(
            Task.deleted_at.isnot(None),
            Task.deleted_at < cutoff_date
        )
        
        count = db.session.execute(select(func.count()).select_from(stmt.subquery())).scalar()
        return count
        
    except Exception as e:
        logger.error(f"[TASK_PURGE] Error getting purgeable count: {str(e)}")
        return 0


# Example usage in a scheduler (e.g., APScheduler, Celery, cron)
# from services.task_purge_job import purge_deleted_tasks
# scheduler.add_job(purge_deleted_tasks, 'cron', hour=2, minute=0)  # Run daily at 2 AM
