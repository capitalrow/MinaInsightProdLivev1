"""
API endpoints for task clustering
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, Task
from services.task_clustering_service import task_clustering_service
import logging

logger = logging.getLogger(__name__)

api_tasks_clustering_bp = Blueprint('api_tasks_clustering', __name__, url_prefix='/api/tasks')


@api_tasks_clustering_bp.route('/clusters', methods=['GET'])
@login_required
def get_task_clusters():
    """
    Get semantic clusters of user's tasks.
    Query params:
        - status: Filter by status (optional)
        - num_clusters: Number of clusters (optional, auto-detected if not provided)
    """
    try:
        # Get query parameters
        status_filter = request.args.get('status')
        num_clusters = request.args.get('num_clusters', type=int)
        
        # Query tasks for current user
        query = db.session.query(Task).filter_by(
            workspace_id=current_user.workspace_id
        )
        
        # Apply status filter if provided
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        tasks = query.all()
        
        if not tasks:
            return jsonify({
                'success': True,
                'clusters': [],
                'metadata': {
                    'method': 'none',
                    'num_clusters': 0,
                    'total_tasks': 0
                }
            })
        
        # Convert tasks to dict format
        tasks_data = []
        for task in tasks:
            tasks_data.append({
                'id': task.id,
                'title': task.title or '',
                'description': task.description or '',
                'priority': task.priority or 'medium',
                'status': task.status or 'todo',
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'labels': task.labels or [],
                'assigned_to': {
                    'id': task.assigned_to.id,
                    'username': task.assigned_to.username
                } if task.assigned_to else None
            })
        
        # Cluster tasks
        result = task_clustering_service.cluster_tasks(tasks_data, num_clusters)
        
        logger.info(f"✅ Clustered {len(tasks_data)} tasks into {result['metadata']['num_clusters']} clusters")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ Failed to cluster tasks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_tasks_clustering_bp.route('/clusters/preview', methods=['POST'])
@login_required
def preview_clustering():
    """
    Preview clustering with specific number of clusters.
    Body: { "task_ids": [...], "num_clusters": 3 }
    """
    try:
        data = request.get_json()
        task_ids = data.get('task_ids', [])
        num_clusters = data.get('num_clusters', None)
        
        if not task_ids:
            return jsonify({
                'success': False,
                'error': 'task_ids required'
            }), 400
        
        # Query specified tasks
        tasks = db.session.query(Task).filter(
            Task.id.in_(task_ids),
            Task.workspace_id == current_user.workspace_id
        ).all()
        
        # Convert to dict format
        tasks_data = []
        for task in tasks:
            tasks_data.append({
                'id': task.id,
                'title': task.title or '',
                'description': task.description or '',
                'priority': task.priority or 'medium',
                'status': task.status or 'todo'
            })
        
        # Cluster
        result = task_clustering_service.cluster_tasks(tasks_data, num_clusters)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ Failed to preview clustering: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
