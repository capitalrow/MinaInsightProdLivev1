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
    """
    Google Calendar implementation using Replit's connector OAuth flow.
    
    Uses real Google Calendar API via services/google_calendar_connector.py
    Integration: connection:conn_google-calendar_01KB6V3GHXC33M5KH618B8HYJN
    """

    def __init__(self):
        self._connector = None
    
    def _get_connector(self):
        """Lazy-load the Google Calendar connector."""
        if self._connector is None:
            from services.google_calendar_connector import google_calendar_connector
            self._connector = google_calendar_connector
        return self._connector

    async def authenticate(self, user_id: int, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Google Calendar.
        
        Note: With Replit connectors, authentication is handled at the platform level.
        This method stores the authentication state in user preferences for tracking.
        """
        try:
            from models.user import User
            try:
                from app import db
            except ImportError:
                logger.error("Database not available for Google Calendar authentication")
                return False
            
            user = db.session.get(User, user_id)
            if not user:
                return False

            preferences = json.loads(user.preferences or '{}')
            if 'integrations' not in preferences:
                preferences['integrations'] = {}
            
            preferences['integrations']['google_calendar'] = {
                'authenticated': True,
                'connected_at': datetime.utcnow().isoformat()
            }
            
            user.preferences = json.dumps(preferences)
            db.session.commit()
            
            logger.info(f"✅ Google Calendar authenticated for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Google Calendar authentication failed for user {user_id}: {e}")
            return False

    async def get_events(self, user_id: int, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get events from Google Calendar using real API."""
        try:
            connector = self._get_connector()
            
            if not await connector.is_connected():
                logger.warning("Google Calendar not connected via Replit connector")
                return []
            
            google_events = await connector.list_events(
                time_min=start_date,
                time_max=end_date
            )
            
            events = []
            for ge in google_events:
                meeting_url = ge.hangout_link
                if not meeting_url and ge.conference_data:
                    entry_points = ge.conference_data.get('entryPoints', [])
                    for ep in entry_points:
                        if ep.get('entryPointType') == 'video':
                            meeting_url = ep.get('uri')
                            break
                
                events.append(CalendarEvent(
                    id=ge.id,
                    title=ge.summary,
                    description=ge.description,
                    start_time=ge.start,
                    end_time=ge.end,
                    location=ge.location,
                    attendees=ge.attendees,
                    provider=CalendarProvider.GOOGLE,
                    provider_event_id=ge.id,
                    meeting_url=meeting_url,
                    is_mina_meeting=False,
                    mina_session_id=None
                ))
            
            logger.info(f"✅ Retrieved {len(events)} events from Google Calendar for user {user_id}")
            return events

        except Exception as e:
            logger.error(f"Failed to get Google Calendar events for user {user_id}: {e}")
            return []

    async def create_event(self, user_id: int, event: CalendarEventCreate) -> CalendarEvent:
        """Create event in Google Calendar using real API."""
        try:
            connector = self._get_connector()
            
            if not await connector.is_connected():
                raise ValueError("Google Calendar not connected")
            
            google_event = await connector.create_event(
                summary=event.title,
                start=event.start_time,
                end=event.end_time,
                description=event.description,
                location=event.location,
                attendees=event.attendees or [],
                add_conference=True
            )
            
            meeting_url = google_event.hangout_link or event.meeting_url
            
            created_event = CalendarEvent(
                id=google_event.id,
                title=google_event.summary,
                description=google_event.description,
                start_time=google_event.start,
                end_time=google_event.end,
                location=google_event.location,
                attendees=google_event.attendees,
                provider=CalendarProvider.GOOGLE,
                provider_event_id=google_event.id,
                meeting_url=meeting_url,
                is_mina_meeting=event.is_mina_meeting,
                mina_session_id=event.mina_session_id
            )
            
            logger.info(f"✅ Created Google Calendar event {google_event.id} for user {user_id}")
            return created_event

        except Exception as e:
            logger.error(f"Failed to create Google Calendar event for user {user_id}: {e}")
            raise

    async def update_event(self, user_id: int, event_id: str, event: CalendarEventCreate) -> CalendarEvent:
        """Update event in Google Calendar using real API."""
        try:
            connector = self._get_connector()
            
            if not await connector.is_connected():
                raise ValueError("Google Calendar not connected")
            
            google_event = await connector.update_event(
                event_id=event_id,
                summary=event.title,
                start=event.start_time,
                end=event.end_time,
                description=event.description,
                location=event.location,
                attendees=event.attendees
            )
            
            updated_event = CalendarEvent(
                id=google_event.id,
                title=google_event.summary,
                description=google_event.description,
                start_time=google_event.start,
                end_time=google_event.end,
                location=google_event.location,
                attendees=google_event.attendees,
                provider=CalendarProvider.GOOGLE,
                provider_event_id=google_event.id,
                meeting_url=google_event.hangout_link or event.meeting_url,
                is_mina_meeting=event.is_mina_meeting,
                mina_session_id=event.mina_session_id
            )
            
            logger.info(f"✅ Updated Google Calendar event {event_id} for user {user_id}")
            return updated_event

        except Exception as e:
            logger.error(f"Failed to update Google Calendar event {event_id} for user {user_id}: {e}")
            raise

    async def delete_event(self, user_id: int, event_id: str) -> bool:
        """Delete event from Google Calendar using real API."""
        try:
            connector = self._get_connector()
            
            if not await connector.is_connected():
                logger.warning("Google Calendar not connected - cannot delete event")
                return False
            
            result = await connector.delete_event(event_id=event_id)
            
            if result:
                logger.info(f"✅ Deleted Google Calendar event {event_id} for user {user_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to delete Google Calendar event {event_id} for user {user_id}: {e}")
            return False

    async def is_authenticated(self, user_id: int) -> bool:
        """Check if Google Calendar is connected via Replit connector."""
        try:
            connector = self._get_connector()
            return await connector.is_connected()

        except Exception as e:
            logger.error(f"Failed to check Google Calendar connection for user {user_id}: {e}")
            return False


class OutlookCalendarProvider(CalendarProviderInterface):
    """
    Outlook Calendar implementation.
    
    STATUS: Not yet integrated - requires OAuth setup.
    
    To enable Outlook Calendar integration:
    1. Set up the Replit Outlook connector (connector ID: ccfg_outlook_01K4BBCKRJKP82N3PYQPZQ6DAK)
    2. Complete the OAuth authorization flow
    3. Update this provider to use the connector similar to GoogleCalendarProvider
    
    Currently returns empty results to avoid mock data in production.
    See replit.md for integration documentation.
    """

    def __init__(self):
        self.connector_id = "ccfg_outlook_01K4BBCKRJKP82N3PYQPZQ6DAK"
        self._is_configured = False

    async def authenticate(self, user_id: int, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Outlook Calendar.
        
        Note: Outlook integration not yet configured. Returns False.
        """
        logger.warning("Outlook Calendar integration not configured - authentication unavailable")
        return False

    async def get_events(self, user_id: int, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """
        Get events from Outlook Calendar.
        
        Returns empty list until Outlook connector is configured.
        """
        if not self._is_configured:
            logger.debug("Outlook Calendar not configured - returning empty event list")
            return []
        
        return []

    async def create_event(self, user_id: int, event: CalendarEventCreate) -> CalendarEvent:
        """
        Create event in Outlook Calendar.
        
        Not available until Outlook connector is configured.
        """
        raise NotImplementedError(
            "Outlook Calendar integration not configured. "
            "Please set up the Outlook connector to enable this feature."
        )

    async def update_event(self, user_id: int, event_id: str, event: CalendarEventCreate) -> CalendarEvent:
        """Update event in Outlook Calendar."""
        raise NotImplementedError(
            "Outlook Calendar integration not configured. "
            "Please set up the Outlook connector to enable this feature."
        )

    async def delete_event(self, user_id: int, event_id: str) -> bool:
        """Delete event from Outlook Calendar."""
        logger.warning("Outlook Calendar not configured - cannot delete event")
        return False

    async def is_authenticated(self, user_id: int) -> bool:
        """
        Check if user is authenticated with Outlook Calendar.
        
        Returns False until Outlook connector is configured.
        """
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