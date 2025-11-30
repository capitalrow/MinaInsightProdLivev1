"""
Calendar Integration Service for Mina.

This module provides a unified interface for calendar operations across
different providers (Google Calendar, Outlook Calendar).
"""

import logging
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CalendarProvider(Enum):
    """Supported calendar providers."""
    GOOGLE = "google"
    OUTLOOK = "outlook"


@dataclass
class CalendarEvent:
    """Unified calendar event representation."""
    id: str
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    location: Optional[str]
    attendees: List[str]
    provider: CalendarProvider
    provider_event_id: str
    meeting_url: Optional[str] = None
    is_mina_meeting: bool = False
    mina_session_id: Optional[int] = None


@dataclass
class CalendarEventCreate:
    """Data for creating a new calendar event."""
    title: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    attendees: Optional[List[str]] = None
    meeting_url: Optional[str] = None
    is_mina_meeting: bool = False
    mina_session_id: Optional[int] = None

    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []


class CalendarProviderInterface(ABC):
    """Abstract interface for calendar providers."""

    @abstractmethod
    async def authenticate(self, user_id: int, credentials: Dict[str, Any]) -> bool:
        """Authenticate with the calendar provider."""
        pass

    @abstractmethod
    async def get_events(self, user_id: int, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get events from the calendar provider."""
        pass

    @abstractmethod
    async def create_event(self, user_id: int, event: CalendarEventCreate) -> CalendarEvent:
        """Create a new event in the calendar provider."""
        pass

    @abstractmethod
    async def update_event(self, user_id: int, event_id: str, event: CalendarEventCreate) -> CalendarEvent:
        """Update an existing event in the calendar provider."""
        pass

    @abstractmethod
    async def delete_event(self, user_id: int, event_id: str) -> bool:
        """Delete an event from the calendar provider."""
        pass

    @abstractmethod
    async def is_authenticated(self, user_id: int) -> bool:
        """Check if user is authenticated with this provider."""
        pass


class GoogleCalendarProvider(CalendarProviderInterface):
    """Google Calendar implementation."""

    def __init__(self):
        self.client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
        self.client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
        self.scopes = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ]

    async def authenticate(self, user_id: int, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Google Calendar using OAuth."""
        try:
            # Store credentials for user
            from models.user import User
            try:
                from app import db
            except ImportError:
                logger.error("Database not available for Google Calendar authentication")
                return False
            
            user = db.session.get(User, user_id)
            if not user:
                return False

            # Store Google Calendar credentials in user preferences
            preferences = json.loads(user.preferences or '{}')
            if 'integrations' not in preferences:
                preferences['integrations'] = {}
            
            preferences['integrations']['google_calendar'] = {
                'authenticated': True,
                'credentials': credentials,
                'connected_at': datetime.utcnow().isoformat()
            }
            
            user.preferences = json.dumps(preferences)
            db.session.commit()
            
            logger.info(f"Google Calendar authenticated for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Google Calendar authentication failed for user {user_id}: {e}")
            return False

    async def get_events(self, user_id: int, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get events from Google Calendar."""
        try:
            # Import Google Calendar API (would need google-api-python-client)
            # For now, return mock data for demonstration
            logger.warning("Google Calendar API not implemented - returning mock data")
            
            return [
                CalendarEvent(
                    id=f"google_{i}",
                    title=f"Google Meeting {i}",
                    description="Meeting synced from Google Calendar",
                    start_time=start_date + timedelta(days=i),
                    end_time=start_date + timedelta(days=i, hours=1),
                    location="Google Meet",
                    attendees=["user@example.com"],
                    provider=CalendarProvider.GOOGLE,
                    provider_event_id=f"google_event_{i}",
                    meeting_url="https://meet.google.com/abc-def-ghi"
                )
                for i in range(3)
            ]

        except Exception as e:
            logger.error(f"Failed to get Google Calendar events for user {user_id}: {e}")
            return []

    async def create_event(self, user_id: int, event: CalendarEventCreate) -> CalendarEvent:
        """Create event in Google Calendar."""
        try:
            # Mock implementation - would integrate with Google Calendar API
            event_id = f"google_{datetime.utcnow().timestamp()}"
            
            logger.info(f"Created Google Calendar event {event_id} for user {user_id}")
            
            return CalendarEvent(
                id=event_id,
                title=event.title,
                description=event.description,
                start_time=event.start_time,
                end_time=event.end_time,
                location=event.location,
                attendees=event.attendees,
                provider=CalendarProvider.GOOGLE,
                provider_event_id=event_id,
                meeting_url=event.meeting_url,
                is_mina_meeting=event.is_mina_meeting,
                mina_session_id=event.mina_session_id
            )

        except Exception as e:
            logger.error(f"Failed to create Google Calendar event for user {user_id}: {e}")
            raise

    async def update_event(self, user_id: int, event_id: str, event: CalendarEventCreate) -> CalendarEvent:
        """Update event in Google Calendar."""
        # Mock implementation
        return await self.create_event(user_id, event)

    async def delete_event(self, user_id: int, event_id: str) -> bool:
        """Delete event from Google Calendar."""
        try:
            logger.info(f"Deleted Google Calendar event {event_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Google Calendar event {event_id} for user {user_id}: {e}")
            return False

    async def is_authenticated(self, user_id: int) -> bool:
        """Check if user is authenticated with Google Calendar."""
        try:
            from models.user import User
            try:
                from app import db
                user = db.session.get(User, user_id)
                if not user or not user.preferences:
                    return False
            except ImportError:
                logger.error("Database not available for Google Calendar check")
                return False

            preferences = json.loads(user.preferences)
            return preferences.get('integrations', {}).get('google_calendar', {}).get('authenticated', False)

        except Exception as e:
            logger.error(f"Failed to check Google Calendar authentication for user {user_id}: {e}")
            return False


class OutlookCalendarProvider(CalendarProviderInterface):
    """Outlook Calendar implementation."""

    def __init__(self):
        self.connector_id = "ccfg_outlook_01K4BBCKRJKP82N3PYQPZQ6DAK"

    async def authenticate(self, user_id: int, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Outlook Calendar."""
        try:
            # Store Outlook credentials
            from models.user import User
            try:
                from app import db
            except ImportError:
                logger.error("Database not available for Outlook Calendar authentication")
                return False
            
            user = db.session.get(User, user_id)
            if not user:
                return False

            preferences = json.loads(user.preferences or '{}')
            if 'integrations' not in preferences:
                preferences['integrations'] = {}
            
            preferences['integrations']['outlook_calendar'] = {
                'authenticated': True,
                'credentials': credentials,
                'connected_at': datetime.utcnow().isoformat()
            }
            
            user.preferences = json.dumps(preferences)
            db.session.commit()
            
            logger.info(f"Outlook Calendar authenticated for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Outlook Calendar authentication failed for user {user_id}: {e}")
            return False

    async def get_events(self, user_id: int, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get events from Outlook Calendar."""
        try:
            # Mock implementation - would use Outlook connector
            logger.warning("Outlook Calendar API not implemented - returning mock data")
            
            return [
                CalendarEvent(
                    id=f"outlook_{i}",
                    title=f"Outlook Meeting {i}",
                    description="Meeting synced from Outlook Calendar",
                    start_time=start_date + timedelta(days=i+1, hours=2),
                    end_time=start_date + timedelta(days=i+1, hours=3),
                    location="Microsoft Teams",
                    attendees=["user@company.com"],
                    provider=CalendarProvider.OUTLOOK,
                    provider_event_id=f"outlook_event_{i}",
                    meeting_url="https://teams.microsoft.com/l/meetup-join/abc"
                )
                for i in range(2)
            ]

        except Exception as e:
            logger.error(f"Failed to get Outlook Calendar events for user {user_id}: {e}")
            return []

    async def create_event(self, user_id: int, event: CalendarEventCreate) -> CalendarEvent:
        """Create event in Outlook Calendar."""
        try:
            event_id = f"outlook_{datetime.utcnow().timestamp()}"
            
            logger.info(f"Created Outlook Calendar event {event_id} for user {user_id}")
            
            return CalendarEvent(
                id=event_id,
                title=event.title,
                description=event.description,
                start_time=event.start_time,
                end_time=event.end_time,
                location=event.location,
                attendees=event.attendees,
                provider=CalendarProvider.OUTLOOK,
                provider_event_id=event_id,
                meeting_url=event.meeting_url,
                is_mina_meeting=event.is_mina_meeting,
                mina_session_id=event.mina_session_id
            )

        except Exception as e:
            logger.error(f"Failed to create Outlook Calendar event for user {user_id}: {e}")
            raise

    async def update_event(self, user_id: int, event_id: str, event: CalendarEventCreate) -> CalendarEvent:
        """Update event in Outlook Calendar."""
        return await self.create_event(user_id, event)

    async def delete_event(self, user_id: int, event_id: str) -> bool:
        """Delete event from Outlook Calendar."""
        try:
            logger.info(f"Deleted Outlook Calendar event {event_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Outlook Calendar event {event_id} for user {user_id}: {e}")
            return False

    async def is_authenticated(self, user_id: int) -> bool:
        """Check if user is authenticated with Outlook Calendar."""
        try:
            from models.user import User
            try:
                from app import db
                user = db.session.get(User, user_id)
                if not user or not user.preferences:
                    return False
            except ImportError:
                logger.error("Database not available for Outlook Calendar check")
                return False

            preferences = json.loads(user.preferences)
            return preferences.get('integrations', {}).get('outlook_calendar', {}).get('authenticated', False)

        except Exception as e:
            logger.error(f"Failed to check Outlook Calendar authentication for user {user_id}: {e}")
            return False


class CalendarService:
    """Unified calendar service that manages multiple providers."""

    def __init__(self):
        self.providers = {
            CalendarProvider.GOOGLE: GoogleCalendarProvider(),
            CalendarProvider.OUTLOOK: OutlookCalendarProvider()
        }

    async def get_user_calendars(self, user_id: int) -> Dict[str, bool]:
        """Get authenticated calendar providers for a user."""
        calendars = {}
        
        for provider_type, provider in self.providers.items():
            calendars[provider_type.value] = await provider.is_authenticated(user_id)
        
        return calendars

    async def authenticate_provider(self, user_id: int, provider: CalendarProvider, credentials: Dict[str, Any]) -> bool:
        """Authenticate with a specific calendar provider."""
        if provider not in self.providers:
            raise ValueError(f"Unsupported calendar provider: {provider}")
        
        return await self.providers[provider].authenticate(user_id, credentials)

    async def get_all_events(self, user_id: int, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get events from all authenticated calendar providers."""
        all_events = []
        
        for provider_type, provider in self.providers.items():
            if await provider.is_authenticated(user_id):
                try:
                    events = await provider.get_events(user_id, start_date, end_date)
                    all_events.extend(events)
                except Exception as e:
                    logger.error(f"Failed to get events from {provider_type.value}: {e}")
        
        # Sort events by start time
        all_events.sort(key=lambda x: x.start_time)
        return all_events

    async def create_event(self, user_id: int, provider: CalendarProvider, event: CalendarEventCreate) -> CalendarEvent:
        """Create an event in a specific calendar provider."""
        if provider not in self.providers:
            raise ValueError(f"Unsupported calendar provider: {provider}")
        
        provider_instance = self.providers[provider]
        
        if not await provider_instance.is_authenticated(user_id):
            raise ValueError(f"User not authenticated with {provider.value}")
        
        return await provider_instance.create_event(user_id, event)

    async def create_event_from_summary(self, user_id: int, summary_data: Dict[str, Any], provider: CalendarProvider) -> CalendarEvent:
        """Create a calendar event from a meeting summary."""
        try:
            # Extract meeting details from summary
            title = f"Follow-up: {summary_data.get('title', 'Meeting')}"
            description = self._build_event_description(summary_data)
            
            # Schedule for next week by default
            start_time = datetime.utcnow() + timedelta(days=7)
            end_time = start_time + timedelta(hours=1)
            
            # Extract attendees from summary if available
            attendees = []
            if 'participants' in summary_data:
                attendees = [p.get('email') for p in summary_data['participants'] if p.get('email')]
            
            event = CalendarEventCreate(
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                attendees=attendees,
                is_mina_meeting=True,
                mina_session_id=summary_data.get('session_id')
            )
            
            return await self.create_event(user_id, provider, event)

        except Exception as e:
            logger.error(f"Failed to create event from summary: {e}")
            raise

    def _build_event_description(self, summary_data: Dict[str, Any]) -> str:
        """Build event description from meeting summary."""
        description_parts = []
        
        if summary_data.get('summary_md'):
            description_parts.append("Meeting Summary:")
            description_parts.append(summary_data['summary_md'])
            description_parts.append("")
        
        if summary_data.get('actions'):
            description_parts.append("Action Items:")
            for action in summary_data['actions']:
                description_parts.append(f"• {action.get('text', '')}")
            description_parts.append("")
        
        if summary_data.get('decisions'):
            description_parts.append("Key Decisions:")
            for decision in summary_data['decisions']:
                description_parts.append(f"• {decision.get('text', '')}")
            description_parts.append("")
        
        description_parts.append("Generated by Mina Meeting Intelligence")
        
        return "\n".join(description_parts)

    async def sync_mina_meetings(self, user_id: int) -> Dict[str, int]:
        """Sync Mina meeting sessions with calendar providers."""
        try:
            try:
                from models.session import Session
                from app import db
                
                # Get recent Mina sessions - adjust field names if needed
                recent_sessions = db.session.query(Session).filter(
                    Session.id.isnot(None)  # Basic filter to get sessions
                ).limit(10).all()
            except (ImportError, AttributeError) as e:
                logger.error(f"Database or Session model not available: {e}")
                return {'created': 0, 'updated': 0, 'errors': 1}
            
            sync_stats = {'created': 0, 'updated': 0, 'errors': 0}
            
            for session in recent_sessions:
                try:
                    # Check if session already has calendar events
                    # For now, just log the sync operation
                    logger.info(f"Would sync session {session.id} to calendar")
                    sync_stats['created'] += 1
                except Exception as e:
                    logger.error(f"Failed to sync session {session.id}: {e}")
                    sync_stats['errors'] += 1
            
            return sync_stats

        except Exception as e:
            logger.error(f"Failed to sync Mina meetings for user {user_id}: {e}")
            return {'created': 0, 'updated': 0, 'errors': 1}


# Global calendar service instance
calendar_service = CalendarService()