"""
Calendar integration routes for Mina.

This module handles calendar operations, provider authentication,
and calendar event management.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db
from models.user import User
from services.calendar_service import calendar_service, CalendarProvider, CalendarEventCreate

logger = logging.getLogger(__name__)

calendar_bp = Blueprint('calendar', __name__, url_prefix='/calendar')


@calendar_bp.route('/')
@login_required
def calendar_dashboard():
    """
    Display the calendar integration dashboard.
    
    Returns:
        Rendered calendar template with user's calendar data
    """
    try:
        # Type check current_user
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        logger.debug(f"Loading calendar dashboard for user {current_user.id}")
        
        return render_template('calendar/dashboard.html',
                             page_title="Calendar Integration")
    
    except Exception as e:
        logger.error(f"Error loading calendar dashboard: {e}")
        flash('Failed to load calendar. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))


@calendar_bp.route('/api/providers', methods=['GET'])
@login_required
def get_calendar_providers():
    """
    Get available calendar providers and authentication status.
    
    Returns:
        JSON: Available providers and their authentication status
    """
    try:
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        # Get authentication status for all providers
        providers_status = {}
        for provider in CalendarProvider:
            providers_status[provider.value] = {
                'name': provider.value.title(),
                'authenticated': False,  # Will be updated by async call
                'available': True
            }
        
        return jsonify({
            'success': True,
            'providers': providers_status
        }), 200
    
    except Exception as e:
        logger.error(f"Error retrieving calendar providers for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve calendar providers'
        }), 500


@calendar_bp.route('/api/providers/status', methods=['GET'])
@login_required  
def get_providers_status():
    """
    Get authentication status for all calendar providers.
    
    Returns:
        JSON: Authentication status for each provider
    """
    try:
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        # This would be async in a real implementation
        # For now, return mock status based on user preferences
        user = db.session.get(User, current_user.id)
        preferences = json.loads(user.preferences or '{}')
        integrations = preferences.get('integrations', {})
        
        status = {
            'google': integrations.get('google_calendar', {}).get('authenticated', False),
            'outlook': integrations.get('outlook_calendar', {}).get('authenticated', False)
        }
        
        return jsonify({
            'success': True,
            'status': status
        }), 200
    
    except Exception as e:
        logger.error(f"Error checking provider status for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to check provider status'
        }), 500


@calendar_bp.route('/api/authenticate/<provider>', methods=['POST'])
@login_required
def authenticate_provider(provider: str):
    """
    Authenticate with a calendar provider.
    
    Args:
        provider: Calendar provider name (google/outlook)
        
    Request Body:
        {
            "credentials": {...}  # Provider-specific credentials
        }
    
    Returns:
        JSON: Authentication result
    """
    try:
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        # Validate provider
        try:
            provider_enum = CalendarProvider(provider.lower())
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid provider: {provider}. Must be one of: google, outlook'
            }), 400
        
        data = request.get_json() or {}
        credentials = data.get('credentials', {})
        
        if not credentials:
            return jsonify({
                'success': False,
                'error': 'Credentials are required'
            }), 400
        
        # For demo purposes, mark as authenticated
        # In real implementation, this would use the calendar service
        user = db.session.get(User, current_user.id)
        preferences = json.loads(user.preferences or '{}')
        
        if 'integrations' not in preferences:
            preferences['integrations'] = {}
        
        preferences['integrations'][f'{provider}_calendar'] = {
            'authenticated': True,
            'connected_at': datetime.utcnow().isoformat(),
            'provider': provider
        }
        
        user.preferences = json.dumps(preferences)
        db.session.commit()
        
        logger.info(f"{provider.title()} Calendar authenticated for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': f'{provider.title()} Calendar connected successfully',
            'provider': provider
        }), 200
    
    except Exception as e:
        logger.error(f"Error authenticating {provider} for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to authenticate with {provider}'
        }), 500


@calendar_bp.route('/api/disconnect/<provider>', methods=['POST'])
@login_required
def disconnect_provider(provider: str):
    """
    Disconnect from a calendar provider.
    
    Args:
        provider: Calendar provider name (google/outlook)
    
    Returns:
        JSON: Disconnection result
    """
    try:
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        # Validate provider
        try:
            CalendarProvider(provider.lower())
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid provider: {provider}'
            }), 400
        
        # Remove authentication from user preferences
        user = db.session.get(User, current_user.id)
        preferences = json.loads(user.preferences or '{}')
        
        if 'integrations' in preferences and f'{provider}_calendar' in preferences['integrations']:
            del preferences['integrations'][f'{provider}_calendar']
            user.preferences = json.dumps(preferences)
            db.session.commit()
        
        logger.info(f"{provider.title()} Calendar disconnected for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': f'{provider.title()} Calendar disconnected successfully',
            'provider': provider
        }), 200
    
    except Exception as e:
        logger.error(f"Error disconnecting {provider} for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to disconnect from {provider}'
        }), 500


@calendar_bp.route('/api/events', methods=['GET'])
@login_required
def get_calendar_events():
    """
    Get calendar events from all connected providers.
    
    Query Parameters:
        - start_date: Start date (ISO format, default: today)
        - end_date: End date (ISO format, default: 7 days from today)
        - provider: Filter by specific provider (optional)
    
    Returns:
        JSON: Calendar events
    """
    try:
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        # Parse query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        provider_filter = request.args.get('provider')
        
        # Set default date range
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        else:
            end_date = start_date + timedelta(days=7)
        
        # For demo purposes, return mock events
        # In real implementation, this would use calendar_service.get_all_events()
        mock_events = []
        
        # Check which providers are authenticated
        user = db.session.get(User, current_user.id)
        preferences = json.loads(user.preferences or '{}')
        integrations = preferences.get('integrations', {})
        
        if integrations.get('google_calendar', {}).get('authenticated'):
            mock_events.extend([
                {
                    'id': 'google_1',
                    'title': 'Team Standup',
                    'description': 'Daily team synchronization meeting',
                    'start_time': (start_date + timedelta(days=1, hours=9)).isoformat(),
                    'end_time': (start_date + timedelta(days=1, hours=9, minutes=30)).isoformat(),
                    'location': 'Google Meet',
                    'provider': 'google',
                    'attendees': ['team@company.com'],
                    'meeting_url': 'https://meet.google.com/abc-def-ghi'
                },
                {
                    'id': 'google_2', 
                    'title': 'Product Review',
                    'description': 'Monthly product review and planning',
                    'start_time': (start_date + timedelta(days=3, hours=14)).isoformat(),
                    'end_time': (start_date + timedelta(days=3, hours=15)).isoformat(),
                    'location': 'Conference Room A',
                    'provider': 'google',
                    'attendees': ['product@company.com', 'dev@company.com'],
                    'is_mina_meeting': True
                }
            ])
        
        if integrations.get('outlook_calendar', {}).get('authenticated'):
            mock_events.extend([
                {
                    'id': 'outlook_1',
                    'title': 'Client Call',
                    'description': 'Weekly check-in with key client',
                    'start_time': (start_date + timedelta(days=2, hours=11)).isoformat(),
                    'end_time': (start_date + timedelta(days=2, hours=12)).isoformat(),
                    'location': 'Microsoft Teams',
                    'provider': 'outlook',
                    'attendees': ['client@bigcorp.com'],
                    'meeting_url': 'https://teams.microsoft.com/l/meetup-join/abc'
                }
            ])
        
        # Filter by provider if specified
        if provider_filter:
            mock_events = [e for e in mock_events if e['provider'] == provider_filter]
        
        # Sort events by start time
        mock_events.sort(key=lambda x: x['start_time'])
        
        return jsonify({
            'success': True,
            'events': mock_events,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total_count': len(mock_events)
        }), 200
    
    except Exception as e:
        logger.error(f"Error retrieving calendar events for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve calendar events'
        }), 500


@calendar_bp.route('/api/events', methods=['POST'])
@login_required
def create_calendar_event():
    """
    Create a new calendar event.
    
    Request Body:
        {
            "provider": "google|outlook",
            "title": "Event title",
            "description": "Event description",
            "start_time": "ISO datetime",
            "end_time": "ISO datetime",
            "location": "Event location",
            "attendees": ["email1", "email2"],
            "meeting_url": "Meeting URL (optional)",
            "is_mina_meeting": true/false
        }
    
    Returns:
        JSON: Created event data
    """
    try:
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['provider', 'title', 'start_time', 'end_time']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Validate provider
        try:
            provider = CalendarProvider(data['provider'].lower())
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid provider: {data["provider"]}'
            }), 400
        
        # Parse datetime strings
        try:
            start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid datetime format: {e}'
            }), 400
        
        # For demo purposes, create a mock event
        # In real implementation, this would use calendar_service.create_event()
        event_id = f"{data['provider']}_{datetime.utcnow().timestamp()}"
        
        created_event = {
            'id': event_id,
            'title': data['title'],
            'description': data.get('description', ''),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'location': data.get('location', ''),
            'provider': data['provider'],
            'attendees': data.get('attendees', []),
            'meeting_url': data.get('meeting_url'),
            'is_mina_meeting': data.get('is_mina_meeting', False),
            'created_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Created calendar event {event_id} for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Calendar event created successfully',
            'event': created_event
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating calendar event for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to create calendar event'
        }), 500


@calendar_bp.route('/api/events/from-summary', methods=['POST'])
@login_required
def create_event_from_summary():
    """
    Create a calendar event from a meeting summary.
    
    Request Body:
        {
            "summary_id": 123,
            "provider": "google|outlook",
            "title": "Custom title (optional)",
            "start_time": "ISO datetime (optional)",
            "attendees": ["email1", "email2"] (optional)
        }
    
    Returns:
        JSON: Created event data
    """
    try:
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        data = request.get_json() or {}
        
        summary_id = data.get('summary_id')
        if not summary_id:
            return jsonify({
                'success': False,
                'error': 'summary_id is required'
            }), 400
        
        # Validate provider
        provider_str = data.get('provider', 'google')
        try:
            provider = CalendarProvider(provider_str.lower())
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid provider: {provider_str}'
            }), 400
        
        # Get summary data (mock for demo)
        # In real implementation, this would query the Summary model
        summary_data = {
            'id': summary_id,
            'title': 'Project Planning Meeting',
            'summary_md': 'Discussed Q4 roadmap and resource allocation',
            'actions': [
                {'text': 'Update project timeline'},
                {'text': 'Schedule follow-up with stakeholders'}
            ],
            'decisions': [
                {'text': 'Approved budget increase for Q4'}
            ],
            'session_id': 123
        }
        
        # Create event from summary
        title = data.get('title', f"Follow-up: {summary_data['title']}")
        description = f"""Meeting Summary:
{summary_data['summary_md']}

Action Items:
• {', '.join([a['text'] for a in summary_data['actions']])}

Key Decisions:
• {', '.join([d['text'] for d in summary_data['decisions']])}

Generated by Mina Meeting Intelligence"""
        
        # Set default time (1 week from now)
        if data.get('start_time'):
            start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
        else:
            start_time = datetime.utcnow() + timedelta(days=7)
        
        end_time = start_time + timedelta(hours=1)
        
        event_id = f"{provider_str}_{datetime.utcnow().timestamp()}"
        
        created_event = {
            'id': event_id,
            'title': title,
            'description': description,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'provider': provider_str,
            'attendees': data.get('attendees', []),
            'is_mina_meeting': True,
            'mina_session_id': summary_data['session_id'],
            'created_from_summary': summary_id
        }
        
        logger.info(f"Created calendar event from summary {summary_id} for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Calendar event created from summary successfully',
            'event': created_event,
            'summary_id': summary_id
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating event from summary for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to create event from summary'
        }), 500


@calendar_bp.route('/api/sync', methods=['POST'])
@login_required
def sync_calendar():
    """
    Manually trigger calendar synchronization.
    
    Returns:
        JSON: Sync results
    """
    try:
        # Type check current_user
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        # Mock sync operation
        # In real implementation, this would use calendar_service.sync_mina_meetings()
        sync_results = {
            'google': {'synced': 3, 'errors': 0},
            'outlook': {'synced': 2, 'errors': 0},
            'total_synced': 5,
            'last_sync': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Calendar sync completed for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Calendar synchronization completed',
            'results': sync_results
        }), 200
    
    except Exception as e:
        logger.error(f"Error syncing calendar for user {current_user.id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to sync calendar'
        }), 500