"""
Summary routes (M3) - API endpoints for AI-powered meeting insights.

Provides endpoints for generating and retrieving meeting summaries,
actions, decisions, and risks extracted from session transcripts.
"""

from __future__ import annotations
import os
import logging
from flask import Blueprint, request, jsonify, current_app, abort
# from flask_socketio import emit  # Disabled for native WebSocket testing
from dataclasses import asdict
from services.analysis_service import AnalysisService
from models.summary import SummaryLevel, SummaryStyle
# from app import socketio  # Disabled for native WebSocket testing
from openai import OpenAI
from server.models.memory_store import MemoryStore
from models import db

logger = logging.getLogger(__name__)

# Create summary blueprint
summary_bp = Blueprint('summary', __name__, url_prefix='/sessions')
analysis = AnalysisService()
memory = MemoryStore()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = (
    "You are Mina, an intelligent meeting summarizer. "
    "Summarize discussions clearly, list key decisions and action items, "
    "and keep tone concise and executive."
)

@summary_bp.route('/<int:session_id>/summarise', methods=['POST'])
def generate_summary(session_id: int):
    """
    Generate AI-powered summary for a session.
    
    Analyses the session transcript and extracts:
    - Meeting summary in markdown format
    - Action items with owners and due dates
    - Key decisions made
    - Identified risks with suggested mitigations
    
    Args:
        session_id: ID of the session to analyse
        
    Returns:
        JSON: Generated summary data with metadata
        
    Status Codes:
        200: Summary generated successfully
        404: Session not found
        400: Invalid request or no segments available
        500: Analysis service error
    """
    try:
        logger.info(f"Request to generate summary for session {session_id}")
        
        # Generate summary using analysis service
        summary_data = AnalysisService.generate_summary(session_id)
        
        logger.info(f"Successfully generated summary {summary_data['id']} for session {session_id}")
        
        return jsonify({
            'success': True,
            'message': f'Summary generated for session {session_id}',
            'summary': summary_data
        }), 200
        
    except ValueError as e:
        logger.warning(f"Summary generation failed for session {session_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404 if 'not found' in str(e) else 400
        
    except Exception as e:
        logger.error(f"Summary generation error for session {session_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate summary'
        }), 500


@summary_bp.route('/<int:session_id>/summary', methods=['GET'])
def get_summary(session_id: int):
    """
    Get the latest summary for a session.
    
    Args:
        session_id: ID of the session
        
    Returns:
        JSON: Summary data or 404 if not found
        
    Status Codes:
        200: Summary found and returned
        404: No summary found for session
    """
    try:
        logger.debug(f"Request to get summary for session {session_id}")
        
        summary_data = AnalysisService.get_session_summary(session_id)
        
        if not summary_data:
            return jsonify({
                'success': False,
                'error': f'No summary found for session {session_id}'
            }), 404
        
        return jsonify({
            'success': True,
            'summary': summary_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving summary for session {session_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve summary'
        }), 500


def trigger_auto_summary(session_id: int):
    """
    Trigger automatic summary generation for a session.
    
    This function is called as a background task when AUTO_SUMMARY_ON_FINALIZE
    is enabled and a session is finalized.
    
    Args:
        session_id: ID of the session to analyze
    """
    try:
        logger.info(f"Auto-generating summary for session {session_id}")
        
        # Generate summary in background
        summary_data = AnalysisService.generate_summary(session_id)
        
        # Emit event to notify clients that summary is ready
        # socketio.emit('summary_generated', { 'session_id': session_id, 'summary_id': summary_data['id'] }, room=f'session_{session_id}')  # Disabled
        
        logger.info(f"Auto-summary {summary_data['id']} generated for session {session_id}")
        
    except Exception as e:
        logger.error(f"Auto-summary generation failed for session {session_id}: {e}")
        
        # Emit error event
        # socketio.emit('summary_error', { 'session_id': session_id, 'error': 'Failed to auto-generate summary' }, room=f'session_{session_id}')  # Disabled


@summary_bp.route('/<int:session_id>/generate-summary', methods=['POST'])
def generate_multi_level_summary(session_id: int):
    """
    Generate AI-powered summary with specified level and style.
    
    Request Body:
        {
            "level": "brief|standard|detailed",
            "style": "executive|action|technical|narrative|bullet"
        }
    
    Args:
        session_id: ID of the session to analyse
        
    Returns:
        JSON: Generated summary data with specified level and style
        
    Status Codes:
        200: Summary generated successfully
        400: Invalid level or style parameter
        404: Session not found
        500: Analysis service error
    """
    try:
        data = request.get_json() or {}
        
        # Parse level and style from request
        level_str = data.get('level', 'standard').lower()
        style_str = data.get('style', 'executive').lower()
        
        # Validate and convert level
        try:
            level = SummaryLevel(level_str)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid level: {level_str}. Must be one of: brief, standard, detailed'
            }), 400
        
        # Validate and convert style
        try:
            style = SummaryStyle(style_str)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid style: {style_str}. Must be one of: executive, action, technical, narrative, bullet'
            }), 400
        
        logger.info(f"Request to generate {level.value} {style.value} summary for session {session_id}")
        
        # Generate summary with specified level and style
        summary_data = AnalysisService.generate_summary(session_id, level, style)
        
        logger.info(f"Successfully generated {level.value} {style.value} summary {summary_data['id']} for session {session_id}")
        
        return jsonify({
            'success': True,
            'message': f'{level.value.title()} {style.value} summary generated for session {session_id}',
            'summary': summary_data
        }), 200
        
    except ValueError as e:
        logger.warning(f"Summary generation failed for session {session_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404 if 'not found' in str(e) else 400
        
    except Exception as e:
        logger.error(f"Summary generation error for session {session_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate summary'
        }), 500


@summary_bp.route('/levels', methods=['GET'])
def get_summary_levels():
    """
    Get available summary levels and styles.
    
    Returns:
        JSON: Available levels and styles with descriptions
    """
    return jsonify({
        'success': True,
        'levels': {
            'brief': {
                'value': 'brief',
                'name': 'Brief Summary',
                'description': 'Executive summary in 2-3 sentences, focusing on key decisions and outcomes'
            },
            'standard': {
                'value': 'standard',
                'name': 'Standard Summary',
                'description': 'Comprehensive 1-2 paragraph summary with actions, decisions, and risks'
            },
            'detailed': {
                'value': 'detailed',
                'name': 'Detailed Analysis',
                'description': 'Multi-section comprehensive analysis covering all aspects of the meeting'
            }
        },
        'styles': {
            'executive': {
                'value': 'executive',
                'name': 'Executive Focus',
                'description': 'Strategic decisions, business impact, and high-level outcomes'
            },
            'action': {
                'value': 'action',
                'name': 'Action-Oriented',
                'description': 'Task-focused with clear action items, owners, and deadlines'
            },
            'technical': {
                'value': 'technical',
                'name': 'Technical Details',
                'description': 'Implementation specifics, architecture decisions, and technical choices'
            },
            'narrative': {
                'value': 'narrative',
                'name': 'Narrative Flow',
                'description': 'Story-like chronological summary of meeting progression'
            },
            'bullet': {
                'value': 'bullet',
                'name': 'Bullet Points',
                'description': 'Structured bullet-point format for easy scanning'
            }
        }
    })


@summary_bp.route('/<int:session_id>/summaries', methods=['GET'])
def get_session_summaries(session_id: int):
    """
    Get all summaries for a session (different levels and styles).
    
    Args:
        session_id: ID of the session
        
    Returns:
        JSON: All summaries for the session grouped by level and style
    """
    try:
        from sqlalchemy import select
        from models.summary import Summary
        from app import db
        
        logger.debug(f"Request to get all summaries for session {session_id}")
        
        # Get all summaries for this session
        stmt = select(Summary).filter(
            Summary.session_id == session_id
        ).order_by(Summary.created_at.desc())
        summaries = db.session.execute(stmt).scalars().all()
        
        if not summaries:
            return jsonify({
                'success': False,
                'error': f'No summaries found for session {session_id}'
            }), 404
        
        # Group summaries by level and style
        grouped_summaries = {}
        for summary in summaries:
            level_key = summary.level.value if summary.level else 'standard'
            style_key = summary.style.value if summary.style else 'executive'
            
            if level_key not in grouped_summaries:
                grouped_summaries[level_key] = {}
            
            grouped_summaries[level_key][style_key] = summary.to_dict()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'summaries': grouped_summaries,
            'total_count': len(summaries)
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving summaries for session {session_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve summaries'
        }), 500


# (Addition to server/routes/summary.py)
@summary_bp.route('/<int:session_id>/summary', methods=['PUT'])
def update_summary(session_id: int):
    """
    Update the latest summary for a session (e.g., after user edits the summary text).
    Expects JSON body with 'summary_md' (edited markdown text).
    """
    data = request.get_json(force=True)
    if not data or 'summary_md' not in data:
        return jsonify({'success': False, 'error': 'No summary content provided'}), 400
    new_text = data['summary_md']
    try:
        from sqlalchemy import select
        stmt = select(Summary).filter(Summary.session_id == session_id).order_by(Summary.created_at.desc())
        summary_obj = db.session.execute(stmt).scalar_one_or_none()
        if not summary_obj:
            return jsonify({'success': False, 'error': f'No summary found for session {session_id}'}), 404
        summary_obj.summary_md = new_text
        db.session.commit()
        logger.info(f"Summary for session {session_id} updated by user")
        return jsonify({'success': True, 'summary': summary_obj.to_dict()}), 200
    except Exception as e:
        logger.error(f"Error updating summary for session {session_id}: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to update summary'}), 500


@summary_bp.route('/summaries', methods=['GET'])
def get_all_summaries():
    """
    Get all summaries across all sessions (admin/overview endpoint).
    
    Query Parameters:
        - limit: Number of summaries to return (default: 50)
        - session_id: Filter by specific session ID
        - level: Filter by summary level
        - style: Filter by summary style
        
    Returns:
        JSON: All summaries with filtering options
    """
    try:
        from sqlalchemy import select
        from models.summary import Summary
        from app import db
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        session_id_filter = request.args.get('session_id', type=int)
        level_filter = request.args.get('level')
        style_filter = request.args.get('style')
        
        logger.debug(f"Request to get all summaries with filters: session_id={session_id_filter}, level={level_filter}, style={style_filter}")
        
        # Build query
        stmt = select(Summary)
        
        # Apply filters
        if session_id_filter:
            stmt = stmt.filter(Summary.session_id == session_id_filter)
        
        if level_filter:
            try:
                level_enum = SummaryLevel(level_filter.lower())
                stmt = stmt.filter(Summary.level == level_enum)
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': f'Invalid level filter: {level_filter}'
                }), 400
        
        if style_filter:
            try:
                style_enum = SummaryStyle(style_filter.lower())
                stmt = stmt.filter(Summary.style == style_enum)
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': f'Invalid style filter: {style_filter}'
                }), 400
        
        # Order and limit
        stmt = stmt.order_by(Summary.created_at.desc()).limit(limit)
        summaries = db.session.execute(stmt).scalars().all()
        
        return jsonify({
            'success': True,
            'summaries': [summary.to_dict() for summary in summaries],
            'count': len(summaries),
            'filters': {
                'session_id': session_id_filter,
                'level': level_filter,
                'style': style_filter,
                'limit': limit
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving all summaries: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve summaries'
        }), 500


# (Additions to server/routes/summary.py for tasks/decisions/risks)
@summary_bp.route('/<int:session_id>/actions', methods=['GET'])
def get_actions(session_id: int):
    """Get extracted action items for the session."""
    try:
        from sqlalchemy import select
        stmt = select(Summary).filter(Summary.session_id == session_id).order_by(Summary.created_at.desc())
        summary_obj = db.session.execute(stmt).scalar_one_or_none()
        if not summary_obj or summary_obj.actions is None:
            return jsonify({'success': False, 'error': f'No action items found for session {session_id}'}), 404
        return jsonify({'success': True, 'actions': summary_obj.actions}), 200
    except Exception as e:
        logger.error(f"Error retrieving actions for session {session_id}: {e}")
        return jsonify({'success': False, 'error': 'Failed to retrieve actions'}), 500

@summary_bp.route('/<int:session_id>/decisions', methods=['GET'])
def get_decisions(session_id: int):
    """Get extracted decisions for the session."""
    try:
        stmt = select(Summary).filter(Summary.session_id == session_id).order_by(Summary.created_at.desc())
        summary_obj = db.session.execute(stmt).scalar_one_or_none()
        if not summary_obj or summary_obj.decisions is None:
            return jsonify({'success': False, 'error': f'No decisions found for session {session_id}'}), 404
        return jsonify({'success': True, 'decisions': summary_obj.decisions}), 200
    except Exception as e:
        logger.error(f"Error retrieving decisions for session {session_id}: {e}")
        return jsonify({'success': False, 'error': 'Failed to retrieve decisions'}), 500

@summary_bp.route('/<int:session_id>/risks', methods=['GET'])
def get_risks(session_id: int):
    """Get extracted risks for the session."""
    try:
        stmt = select(Summary).filter(Summary.session_id == session_id).order_by(Summary.created_at.desc())
        summary_obj = db.session.execute(stmt).scalar_one_or_none()
        if not summary_obj or summary_obj.risks is None:
            return jsonify({'success': False, 'error': f'No risks found for session {session_id}'}), 404
        return jsonify({'success': True, 'risks': summary_obj.risks}), 200
    except Exception as e:
        logger.error(f"Error retrieving risks for session {session_id}: {e}")
        return jsonify({'success': False, 'error': 'Failed to retrieve risks'}), 500

@summary_bp.route('/<int:session_id>/actions/<int:index>', methods=['PUT'])
def update_action_item(session_id: int, index: int):
    """
    Update an action item by index (e.g., mark as completed or edit text).
    Expects JSON fields to update (like {"completed": true}).
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    try:
        stmt = select(Summary).filter(Summary.session_id == session_id).order_by(Summary.created_at.desc())
        summary_obj = db.session.execute(stmt).scalar_one_or_none()
        if not summary_obj or not summary_obj.actions or index >= len(summary_obj.actions):
            return jsonify({'success': False, 'error': 'Action item not found'}), 404
        action = summary_obj.actions[index]
        # Update allowed fields
        if 'text' in data: action['text'] = data['text']
        if 'owner' in data: action['owner'] = data['owner']
        if 'due' in data: action['due'] = data['due']
        if 'completed' in data: action['completed'] = bool(data['completed'])
        # Save changes
        summary_obj.actions = summary_obj.actions  # reassign to flag JSON field as changed
        db.session.commit()
        logger.info(f"Action item {index} for session {session_id} updated: {data}")
        return jsonify({'success': True, 'action': action}), 200
    except Exception as e:
        logger.error(f"Error updating action item for session {session_id}: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to update action item'}), 500
        