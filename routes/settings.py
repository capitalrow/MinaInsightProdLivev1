"""
Settings management routes for Mina.

This module handles user settings, preferences, and configuration management.
"""

import json
import logging
from typing import Dict, Any, Optional

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user

from models.user import User
from models.workspace import Workspace

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('/')
@login_required
def settings_dashboard():
    """
    Display the main settings dashboard (redirects to preferences).
    
    Returns:
        Redirect to preferences page
    """
    return redirect(url_for('settings.preferences'))


@settings_bp.route('/preferences')
@login_required
def preferences():
    """
    Display the Crown+ preferences page.
    
    Returns:
        Rendered preferences template with current user preferences
    """
    logger.info(f"🔍 Preferences page accessed - User: {current_user.username}")
    
    try:
        return render_template('settings/preferences.html')
    
    except Exception as e:
        logger.error(f"❌ Error loading preferences: {e}", exc_info=True)
        flash('Failed to load preferences. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))


@settings_bp.route('/integrations')
@login_required
def integrations():
    """
    Display the Crown+ integrations page.
    
    Returns:
        Rendered integrations template
    """
    logger.info(f"🔍 Integrations page accessed - User: {current_user.username}")
    
    try:
        return render_template('settings/integrations.html')
    
    except Exception as e:
        logger.error(f"❌ Error loading integrations: {e}", exc_info=True)
        flash('Failed to load integrations. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))


@settings_bp.route('/api/integrations/status', methods=['GET'])
@login_required
def get_integrations_status():
    """
    Get status of all integrations for the current user.
    
    Returns:
        JSON: Integration statuses
    """
    try:
        # Get user preferences to check integration status
        preferences = _get_user_preferences(current_user)
        integrations_prefs = preferences.get('integrations', {})
        
        # Return status for each integration
        return jsonify({
            'success': True,
            'integrations': {
                'google-calendar': integrations_prefs.get('google_calendar', False),
                'outlook': integrations_prefs.get('outlook_calendar', False),
                'slack': integrations_prefs.get('slack_notifications', False),
                'notion': integrations_prefs.get('notion_sync', False),
                'linear': integrations_prefs.get('linear_tasks', False),
                'jira': integrations_prefs.get('jira_integration', False),
                'github': integrations_prefs.get('github_integration', False),
                'zapier': integrations_prefs.get('zapier_integration', False)
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting integration status: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to get integration status'}), 500


@settings_bp.route('/api/integrations/connect', methods=['POST'])
@login_required
def connect_integration():
    """
    Connect an integration (simulated for now).
    
    Request Body:
        {
            "integration": "integration-id"
        }
    
    Returns:
        JSON: Success/error response
    """
    from app import db
    
    try:
        data = request.get_json() or {}
        integration_id = data.get('integration')
        
        if not integration_id:
            return jsonify({'success': False, 'error': 'Integration ID is required'}), 400
        
        # Map integration ID to preference key
        integration_map = {
            'google-calendar': 'google_calendar',
            'outlook': 'outlook_calendar',
            'slack': 'slack_notifications',
            'notion': 'notion_sync',
            'linear': 'linear_tasks',
            'jira': 'jira_integration',
            'github': 'github_integration',
            'zapier': 'zapier_integration'
        }
        
        pref_key = integration_map.get(integration_id)
        if not pref_key:
            return jsonify({'success': False, 'error': 'Invalid integration ID'}), 400
        
        # Update preferences to mark as connected
        preferences = _get_user_preferences(current_user)
        if 'integrations' not in preferences:
            preferences['integrations'] = {}
        
        preferences['integrations'][pref_key] = True
        current_user.preferences = json.dumps(preferences)
        db.session.commit()
        
        logger.info(f"Connected integration {integration_id} for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': f'{integration_id} connected successfully',
            'integration': integration_id
        }), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error connecting integration: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to connect integration'}), 500


@settings_bp.route('/api/integrations/disconnect', methods=['POST'])
@login_required
def disconnect_integration():
    """
    Disconnect an integration.
    
    Request Body:
        {
            "integration": "integration-id"
        }
    
    Returns:
        JSON: Success/error response
    """
    from app import db
    
    try:
        data = request.get_json() or {}
        integration_id = data.get('integration')
        
        if not integration_id:
            return jsonify({'success': False, 'error': 'Integration ID is required'}), 400
        
        # Map integration ID to preference key
        integration_map = {
            'google-calendar': 'google_calendar',
            'outlook': 'outlook_calendar',
            'slack': 'slack_notifications',
            'notion': 'notion_sync',
            'linear': 'linear_tasks',
            'jira': 'jira_integration',
            'github': 'github_integration',
            'zapier': 'zapier_integration'
        }
        
        pref_key = integration_map.get(integration_id)
        if not pref_key:
            return jsonify({'success': False, 'error': 'Invalid integration ID'}), 400
        
        # Update preferences to mark as disconnected
        preferences = _get_user_preferences(current_user)
        if 'integrations' in preferences and pref_key in preferences['integrations']:
            preferences['integrations'][pref_key] = False
            current_user.preferences = json.dumps(preferences)
            db.session.commit()
        
        logger.info(f"Disconnected integration {integration_id} for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': f'{integration_id} disconnected',
            'integration': integration_id
        }), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error disconnecting integration: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to disconnect integration'}), 500


@settings_bp.route('/api/preferences', methods=['GET'])
@login_required
def get_preferences():
    """
    Get user preferences as JSON.
    
    Returns:
        JSON: Current user preferences
    """
    try:
        from app import db
        
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
            
        preferences = _get_user_preferences(current_user)
        
        return jsonify({
            'success': True,
            'preferences': preferences
        }), 200
    
    except Exception as e:
        logger.error(f"Error retrieving preferences for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve preferences'
        }), 500


@settings_bp.route('/api/preferences', methods=['POST'])
@login_required
def update_preferences():
    """
    Update user preferences.
    
    Request Body:
        {
            "category": "transcription|summary|tasks|audio|privacy|integrations|general",
            "settings": {
                "key": "value",
                ...
            }
        }
    
    Returns:
        JSON: Success/error response
    """
    try:
        data = request.get_json() or {}
        category = data.get('category')
        settings = data.get('settings', {})
        
        if not category:
            return jsonify({
                'success': False,
                'error': 'Category is required'
            }), 400
        
        # Validate category
        valid_categories = [
            'transcription', 'summary', 'tasks', 'audio', 
            'privacy', 'integrations', 'general', 'ui'
        ]
        
        if category not in valid_categories:
            return jsonify({
                'success': False,
                'error': f'Invalid category. Must be one of: {", ".join(valid_categories)}'
            }), 400
        
        from app import db
        
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Get current preferences
        current_preferences = _get_user_preferences(current_user)
        
        # Update the specific category
        current_preferences[category] = {
            **current_preferences.get(category, {}),
            **settings
        }
        
        # Save to database
        current_user.preferences = json.dumps(current_preferences)
        db.session.commit()
        
        logger.info(f"Updated {category} preferences for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': f'{category.title()} preferences updated successfully',
            'category': category,
            'updated_settings': settings
        }), 200
    
    except Exception as e:
        logger.error(f"Error updating preferences for user {current_user.id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to update preferences'
        }), 500


@settings_bp.route('/api/preferences/reset', methods=['POST'])
@login_required
def reset_preferences():
    """
    Reset user preferences to defaults.
    
    Request Body:
        {
            "category": "category_name" (optional - if not provided, resets all)
        }
    
    Returns:
        JSON: Success/error response
    """
    try:
        data = request.get_json() or {}
        category = data.get('category')
        
        # Get default preferences
        default_preferences = _get_default_preferences()
        
        from app import db
        
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        if category:
            # Reset specific category
            current_preferences = _get_user_preferences(current_user)
            current_preferences[category] = default_preferences.get(category, {})
            preferences_to_save = current_preferences
            message = f'{category.title()} preferences reset to defaults'
        else:
            # Reset all preferences
            preferences_to_save = default_preferences
            message = 'All preferences reset to defaults'
        
        # Save to database
        current_user.preferences = json.dumps(preferences_to_save)
        db.session.commit()
        
        logger.info(f"Reset preferences for user {current_user.id}: {category or 'all'}")
        
        return jsonify({
            'success': True,
            'message': message,
            'preferences': preferences_to_save
        }), 200
    
    except Exception as e:
        logger.error(f"Error resetting preferences for user {current_user.id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Failed to reset preferences'
        }), 500


@settings_bp.route('/api/export', methods=['GET'])
@login_required
def export_settings():
    """
    Export user settings as JSON file.
    
    Returns:
        JSON: User settings for export
    """
    try:
        from app import db
        
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
            
        preferences = _get_user_preferences(current_user)
        
        export_data = {
            'user_id': current_user.id,
            'username': current_user.username,
            'export_timestamp': db.func.now(),
            'preferences': preferences,
            'version': '1.0'
        }
        
        logger.info(f"Exported settings for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'data': export_data
        }), 200
    
    except Exception as e:
        logger.error(f"Error exporting settings for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to export settings'
        }), 500


def _get_user_preferences(user: User) -> Dict[str, Any]:
    """
    Get user preferences with defaults for missing values.
    
    Args:
        user: User object
        
    Returns:
        Dictionary of user preferences with defaults
    """
    try:
        if user.preferences:
            preferences = json.loads(user.preferences)
        else:
            preferences = {}
        
        # Merge with defaults to ensure all categories exist
        default_preferences = _get_default_preferences()
        
        for category, defaults in default_preferences.items():
            if category not in preferences:
                preferences[category] = defaults
            else:
                # Merge with defaults to ensure all keys exist
                preferences[category] = {**defaults, **preferences[category]}
        
        return preferences
    
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Invalid preferences JSON for user {user.id}: {e}")
        return _get_default_preferences()


def _get_workspace_settings(user: User) -> Optional[Dict[str, Any]]:
    """
    Get workspace settings for the user.
    
    Args:
        user: User object
        
    Returns:
        Dictionary of workspace settings or None
    """
    try:
        # For now, return None as workspace functionality is not fully implemented
        # In the future, this would query the user's workspace
        return None
    
    except Exception as e:
        logger.warning(f"Error retrieving workspace settings for user {user.id}: {e}")
        return None


def _get_default_preferences() -> Dict[str, Any]:
    """
    Get default user preferences.
    
    Returns:
        Dictionary of default preferences organized by category
    """
    return {
        'transcription': {
            'language': 'auto',
            'quality': 'high',
            'speaker_detection': True,
            'confidence_threshold': 0.8,
            'punctuation': True,
            'profanity_filter': False,
            'auto_save': True,
            'real_time_display': True
        },
        'summary': {
            'default_level': 'standard',
            'default_style': 'executive',
            'auto_generate': True,
            'auto_generate_delay': 30,  # seconds after session ends
            'include_actions': True,
            'include_decisions': True,
            'include_risks': True,
            'email_summary': False
        },
        'tasks': {
            'default_priority': 'medium',
            'auto_assign': False,
            'due_date_suggestions': True,
            'notification_reminders': True,
            'calendar_integration': False,
            'task_categories': ['action', 'follow-up', 'research', 'decision']
        },
        'audio': {
            'quality': 'high',
            'noise_reduction': True,
            'echo_cancellation': True,
            'auto_gain_control': True,
            'voice_activity_detection': True,
            'buffer_size': 'medium',
            'format': 'webm'
        },
        'privacy': {
            'data_retention_days': 365,
            'share_analytics': False,
            'recording_consent': True,
            'delete_on_export': False,
            'encrypt_storage': True,
            'anonymous_usage_stats': True
        },
        'integrations': {
            'google_calendar': False,
            'outlook_calendar': False,
            'slack_notifications': False,
            'teams_integration': False,
            'notion_sync': False,
            'linear_tasks': False,
            'jira_integration': False
        },
        'ui': {
            'theme': 'dark',
            'sidebar_collapsed': False,
            'auto_refresh': True,
            'keyboard_shortcuts': True,
            'tooltips': True,
            'animations': True,
            'compact_mode': False,
            'language': 'en'
        },
        'general': {
            'timezone': 'auto',
            'date_format': 'MM/DD/YYYY',
            'time_format': '12h',
            'first_day_of_week': 'monday',
            'notifications': True,
            'email_notifications': True,
            'browser_notifications': True
        }
    }


@settings_bp.route('/profile')
@login_required
def profile():
    """
    Display user profile settings page.
    
    Returns:
        Rendered profile template
    """
    logger.info(f"🔍 Profile page accessed - User: {current_user.username}")
    
    try:
        return render_template('settings/profile.html', user=current_user)
    
    except Exception as e:
        logger.error(f"❌ Error loading profile: {e}", exc_info=True)
        flash('Failed to load profile. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))


@settings_bp.route('/workspace')
@login_required
def workspace_management():
    """
    Display workspace management page with team members and settings.
    
    Returns:
        Rendered workspace management template
    """
    from models import db, Meeting
    
    try:
        workspace = None
        workspace_members = []
        workspace_meetings_count = 0
        workspace_hours = 0
        
        # Try to get workspace if user has one
        if current_user.workspace_id:
            try:
                workspace = current_user.workspace
                if workspace and hasattr(workspace, 'members'):
                    workspace_members = list(workspace.members) if workspace.members else []
                    
                # Count meetings for workspace
                workspace_meetings_count = db.session.query(Meeting).filter_by(
                    workspace_id=current_user.workspace_id
                ).count()
            except Exception as e:
                logger.warning(f"Could not load workspace: {e}")
        
        # If no workspace or failed to load, show single user view
        if not workspace:
            workspace_members = [current_user]
            # Count meetings for current user
            workspace_meetings_count = db.session.query(Meeting).join(Meeting.organizer).filter(
                Meeting.organizer.has(id=current_user.id)
            ).count()
        
        # Calculate total hours (placeholder: 30 min per meeting)
        workspace_hours = int(workspace_meetings_count * 0.5)
        
        return render_template('settings/workspace.html',
                             workspace=workspace,
                             workspace_members=workspace_members,
                             workspace_meetings_count=workspace_meetings_count,
                             workspace_hours=workspace_hours)
    
    except Exception as e:
        logger.error(f"Error loading workspace management: {e}", exc_info=True)
        flash('Failed to load workspace management. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))


@settings_bp.route('/workspace/invite', methods=['POST'])
@login_required
def invite_member():
    """
    Invite a new member to the workspace.
    
    Request Body:
        {
            "email": "user@example.com",
            "role": "member|admin"
        }
    
    Returns:
        JSON: Success/error response
    """
    from app import db
    
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        role = data.get('role', 'member').lower()
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        if role not in ['member', 'admin']:
            return jsonify({'success': False, 'error': 'Invalid role'}), 400
        
        workspace = current_user.workspace
        if not workspace:
            return jsonify({'success': False, 'error': 'No workspace found'}), 404
        
        # Check if workspace can add more users
        if not workspace.can_add_user():
            return jsonify({'success': False, 'error': 'Workspace user limit reached'}), 400
        
        # TODO: Implement actual invitation system with email
        # For now, just return success
        logger.info(f"Invitation sent to {email} for workspace {workspace.id}")
        
        return jsonify({
            'success': True,
            'message': f'Invitation sent to {email}',
            'email': email,
            'role': role
        }), 200
    
    except Exception as e:
        logger.error(f"Error inviting member: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to send invitation'}), 500


@settings_bp.route('/workspace/member/<int:member_id>/role', methods=['PUT'])
@login_required
def update_member_role(member_id):
    """
    Update a member's role in the workspace.
    
    Args:
        member_id: ID of the member to update
    
    Request Body:
        {
            "role": "member|admin|owner"
        }
    
    Returns:
        JSON: Success/error response
    """
    from app import db
    
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    
    try:
        data = request.get_json() or {}
        new_role = data.get('role', '').lower()
        
        if new_role not in ['member', 'admin', 'owner']:
            return jsonify({'success': False, 'error': 'Invalid role'}), 400
        
        # Only workspace owner can assign/transfer owner role
        workspace = current_user.workspace
        if new_role == 'owner':
            if not workspace or current_user.id != workspace.owner_id:
                return jsonify({'success': False, 'error': 'Only workspace owner can assign owner role'}), 403
        
        # Get member
        member = db.session.query(User).filter_by(id=member_id).first()
        if not member:
            return jsonify({'success': False, 'error': 'Member not found'}), 404
        
        # Check if member is in same workspace
        if member.workspace_id != current_user.workspace_id:
            return jsonify({'success': False, 'error': 'Member not in workspace'}), 403
        
        # If transferring owner role, demote current owner to admin
        if new_role == 'owner' and workspace:
            current_owner = db.session.query(User).filter_by(id=workspace.owner_id).first()
            if current_owner and current_owner.id != member_id:
                current_owner.role = 'admin'
            workspace.owner_id = member_id
        
        # Update role
        member.role = new_role
        db.session.commit()
        
        logger.info(f"Updated role for user {member_id} to {new_role}")
        
        return jsonify({
            'success': True,
            'message': f'Role updated to {new_role}',
            'member_id': member_id,
            'new_role': new_role
        }), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating member role: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to update role'}), 500


@settings_bp.route('/workspace/member/<int:member_id>', methods=['DELETE'])
@login_required
def remove_member(member_id):
    """
    Remove a member from the workspace.
    
    Args:
        member_id: ID of the member to remove
    
    Returns:
        JSON: Success/error response
    """
    from app import db
    
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    
    try:
        # Get member
        member = db.session.query(User).filter_by(id=member_id).first()
        if not member:
            return jsonify({'success': False, 'error': 'Member not found'}), 404
        
        # Check if member is in same workspace
        if member.workspace_id != current_user.workspace_id:
            return jsonify({'success': False, 'error': 'Member not in workspace'}), 403
        
        # Cannot remove workspace owner
        workspace = current_user.workspace
        if workspace and member.id == workspace.owner_id:
            return jsonify({'success': False, 'error': 'Cannot remove workspace owner'}), 403
        
        # Remove member from workspace
        member.workspace_id = None
        member.role = 'user'
        db.session.commit()
        
        logger.info(f"Removed user {member_id} from workspace {workspace.id if workspace else 'N/A'}")
        
        return jsonify({
            'success': True,
            'message': 'Member removed from workspace',
            'member_id': member_id
        }), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing member: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to remove member'}), 500


@settings_bp.route('/workspace/permissions', methods=['POST'])
@login_required
def update_workspace_permissions():
    """
    Update workspace permissions.
    
    Request Body:
        {
            "permission": "permission_name",
            "enabled": true|false
        }
    
    Returns:
        JSON: Success/error response
    """
    from app import db
    
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    
    try:
        data = request.get_json() or {}
        permission = data.get('permission')
        enabled = data.get('enabled', False)
        
        if not permission:
            return jsonify({'success': False, 'error': 'Permission name is required'}), 400
        
        workspace = current_user.workspace
        if not workspace:
            return jsonify({'success': False, 'error': 'No workspace found'}), 404
        
        # TODO: Implement actual permission storage
        # For now, just return success
        logger.info(f"Updated permission {permission} to {enabled} for workspace {workspace.id}")
        
        return jsonify({
            'success': True,
            'message': 'Permission updated',
            'permission': permission,
            'enabled': enabled
        }), 200
    
    except Exception as e:
        logger.error(f"Error updating permissions: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to update permissions'}), 500