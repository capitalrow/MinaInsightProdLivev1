"""
Google Calendar Connector for Mina.

Uses Replit's connector infrastructure for OAuth token management.
Provides real API integration with Google Calendar.

Integration: connection:conn_google-calendar_01KB6V3GHXC33M5KH618B8HYJN
"""

import os
import logging
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


@dataclass
class GoogleCalendarEvent:
    """Google Calendar event representation."""
    id: str
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    location: Optional[str]
    attendees: List[str]
    html_link: Optional[str]
    hangout_link: Optional[str]
    conference_data: Optional[Dict[str, Any]]


class GoogleCalendarConnector:
    """
    Real Google Calendar API integration using Replit's connector OAuth flow.
    
    This replaces the mock implementation with actual API calls.
    """
    
    def __init__(self):
        self._connection_settings: Optional[Dict[str, Any]] = None
        self._connector_hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
    
    async def _get_access_token(self) -> str:
        """
        Fetch access token from Replit connector infrastructure.
        Handles token refresh automatically.
        """
        if (self._connection_settings and 
            self._connection_settings.get('settings', {}).get('expires_at')):
            expires_at = self._connection_settings['settings']['expires_at']
            if datetime.fromisoformat(expires_at.replace('Z', '+00:00')) > datetime.now():
                access_token = (
                    self._connection_settings.get('settings', {}).get('access_token') or
                    self._connection_settings.get('settings', {}).get('oauth', {}).get('credentials', {}).get('access_token')
                )
                if access_token:
                    return access_token
        
        if not self._connector_hostname:
            raise ValueError("REPLIT_CONNECTORS_HOSTNAME not configured")
        
        x_replit_token = None
        if os.environ.get('REPL_IDENTITY'):
            x_replit_token = f"repl {os.environ['REPL_IDENTITY']}"
        elif os.environ.get('WEB_REPL_RENEWAL'):
            x_replit_token = f"depl {os.environ['WEB_REPL_RENEWAL']}"
        
        if not x_replit_token:
            raise ValueError("X_REPLIT_TOKEN not found for repl/depl")
        
        async with aiohttp.ClientSession() as session:
            url = f"https://{self._connector_hostname}/api/v2/connection?include_secrets=true&connector_names=google-calendar"
            headers = {
                'Accept': 'application/json',
                'X_REPLIT_TOKEN': x_replit_token
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to get Google Calendar connection: {error_text}")
                    raise ValueError(f"Google Calendar connection failed: {response.status}")
                
                data = await response.json()
                items = data.get('items', [])
                
                if not items:
                    raise ValueError("Google Calendar not connected")
                
                self._connection_settings = items[0]
        
        access_token = (
            self._connection_settings.get('settings', {}).get('access_token') or
            self._connection_settings.get('settings', {}).get('oauth', {}).get('credentials', {}).get('access_token')
        )
        
        if not access_token:
            raise ValueError("No access token found in Google Calendar connection")
        
        logger.info("✅ Google Calendar access token retrieved successfully")
        return access_token
    
    async def is_connected(self) -> bool:
        """Check if Google Calendar is connected via Replit connector."""
        try:
            await self._get_access_token()
            return True
        except Exception as e:
            logger.debug(f"Google Calendar not connected: {e}")
            return False
    
    async def list_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 50,
        single_events: bool = True
    ) -> List[GoogleCalendarEvent]:
        """
        List events from Google Calendar.
        
        Args:
            calendar_id: Calendar ID (default: "primary")
            time_min: Start time filter
            time_max: End time filter
            max_results: Maximum number of events to return
            single_events: Expand recurring events
            
        Returns:
            List of GoogleCalendarEvent objects
        """
        access_token = await self._get_access_token()
        
        params = {
            'maxResults': str(max_results),
            'singleEvents': str(single_events).lower(),
            'orderBy': 'startTime'
        }
        
        if time_min:
            params['timeMin'] = time_min.isoformat() + 'Z'
        if time_max:
            params['timeMax'] = time_max.isoformat() + 'Z'
        
        url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{calendar_id}/events"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to list Google Calendar events: {error_text}")
                    raise ValueError(f"Failed to list events: {response.status}")
                
                data = await response.json()
        
        events = []
        for item in data.get('items', []):
            start_data = item.get('start', {})
            end_data = item.get('end', {})
            
            start_str = start_data.get('dateTime') or start_data.get('date')
            end_str = end_data.get('dateTime') or end_data.get('date')
            
            try:
                if 'T' in start_str:
                    start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    start = datetime.strptime(start_str, '%Y-%m-%d')
                    
                if 'T' in end_str:
                    end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                else:
                    end = datetime.strptime(end_str, '%Y-%m-%d')
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse event times: {e}")
                continue
            
            attendees = [
                a.get('email', '')
                for a in item.get('attendees', [])
                if a.get('email')
            ]
            
            conference_data = item.get('conferenceData')
            hangout_link = item.get('hangoutLink')
            
            if conference_data and not hangout_link:
                entry_points = conference_data.get('entryPoints', [])
                for ep in entry_points:
                    if ep.get('entryPointType') == 'video':
                        hangout_link = ep.get('uri')
                        break
            
            events.append(GoogleCalendarEvent(
                id=item.get('id', ''),
                summary=item.get('summary', 'Untitled Event'),
                description=item.get('description'),
                start=start,
                end=end,
                location=item.get('location'),
                attendees=attendees,
                html_link=item.get('htmlLink'),
                hangout_link=hangout_link,
                conference_data=conference_data
            ))
        
        logger.info(f"✅ Retrieved {len(events)} events from Google Calendar")
        return events
    
    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        calendar_id: str = "primary",
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        send_notifications: bool = True,
        add_conference: bool = False
    ) -> GoogleCalendarEvent:
        """
        Create a new event in Google Calendar.
        
        Args:
            summary: Event title
            start: Start datetime
            end: End datetime
            calendar_id: Calendar ID (default: "primary")
            description: Event description
            location: Event location
            attendees: List of attendee email addresses
            send_notifications: Send email notifications to attendees
            add_conference: Add Google Meet video conference
            
        Returns:
            Created GoogleCalendarEvent
        """
        access_token = await self._get_access_token()
        
        event_body = {
            'summary': summary,
            'start': {'dateTime': start.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end.isoformat(), 'timeZone': 'UTC'}
        }
        
        if description:
            event_body['description'] = description
        if location:
            event_body['location'] = location
        if attendees:
            event_body['attendees'] = [{'email': email} for email in attendees]
        if add_conference:
            event_body['conferenceData'] = {
                'createRequest': {
                    'requestId': f"mina-{datetime.utcnow().timestamp()}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            }
        
        url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{calendar_id}/events"
        params = {'sendUpdates': 'all' if send_notifications else 'none'}
        
        if add_conference:
            params['conferenceDataVersion'] = '1'
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            async with session.post(url, headers=headers, params=params, json=event_body) as response:
                if response.status not in (200, 201):
                    error_text = await response.text()
                    logger.error(f"Failed to create Google Calendar event: {error_text}")
                    raise ValueError(f"Failed to create event: {response.status}")
                
                data = await response.json()
        
        start_data = data.get('start', {})
        end_data = data.get('end', {})
        
        start_str = start_data.get('dateTime') or start_data.get('date')
        end_str = end_data.get('dateTime') or end_data.get('date')
        
        created_start = datetime.fromisoformat(start_str.replace('Z', '+00:00')) if 'T' in start_str else datetime.strptime(start_str, '%Y-%m-%d')
        created_end = datetime.fromisoformat(end_str.replace('Z', '+00:00')) if 'T' in end_str else datetime.strptime(end_str, '%Y-%m-%d')
        
        event = GoogleCalendarEvent(
            id=data.get('id', ''),
            summary=data.get('summary', summary),
            description=data.get('description'),
            start=created_start,
            end=created_end,
            location=data.get('location'),
            attendees=[a.get('email', '') for a in data.get('attendees', [])],
            html_link=data.get('htmlLink'),
            hangout_link=data.get('hangoutLink'),
            conference_data=data.get('conferenceData')
        )
        
        logger.info(f"✅ Created Google Calendar event: {event.id}")
        return event
    
    async def update_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        summary: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        send_notifications: bool = True
    ) -> GoogleCalendarEvent:
        """
        Update an existing event in Google Calendar.
        
        Args:
            event_id: ID of the event to update
            calendar_id: Calendar ID
            summary: New event title
            start: New start datetime
            end: New end datetime
            description: New description
            location: New location
            attendees: New list of attendee emails
            send_notifications: Send update notifications
            
        Returns:
            Updated GoogleCalendarEvent
        """
        access_token = await self._get_access_token()
        
        get_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with session.get(get_url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to get event for update: {error_text}")
                    raise ValueError(f"Event not found: {response.status}")
                
                existing_event = await response.json()
        
        if summary:
            existing_event['summary'] = summary
        if start:
            existing_event['start'] = {'dateTime': start.isoformat(), 'timeZone': 'UTC'}
        if end:
            existing_event['end'] = {'dateTime': end.isoformat(), 'timeZone': 'UTC'}
        if description is not None:
            existing_event['description'] = description
        if location is not None:
            existing_event['location'] = location
        if attendees is not None:
            existing_event['attendees'] = [{'email': email} for email in attendees]
        
        update_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}"
        params = {'sendUpdates': 'all' if send_notifications else 'none'}
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            async with session.put(update_url, headers=headers, params=params, json=existing_event) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to update Google Calendar event: {error_text}")
                    raise ValueError(f"Failed to update event: {response.status}")
                
                data = await response.json()
        
        start_data = data.get('start', {})
        end_data = data.get('end', {})
        start_str = start_data.get('dateTime') or start_data.get('date')
        end_str = end_data.get('dateTime') or end_data.get('date')
        
        updated_start = datetime.fromisoformat(start_str.replace('Z', '+00:00')) if 'T' in start_str else datetime.strptime(start_str, '%Y-%m-%d')
        updated_end = datetime.fromisoformat(end_str.replace('Z', '+00:00')) if 'T' in end_str else datetime.strptime(end_str, '%Y-%m-%d')
        
        event = GoogleCalendarEvent(
            id=data.get('id', ''),
            summary=data.get('summary', ''),
            description=data.get('description'),
            start=updated_start,
            end=updated_end,
            location=data.get('location'),
            attendees=[a.get('email', '') for a in data.get('attendees', [])],
            html_link=data.get('htmlLink'),
            hangout_link=data.get('hangoutLink'),
            conference_data=data.get('conferenceData')
        )
        
        logger.info(f"✅ Updated Google Calendar event: {event.id}")
        return event
    
    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        send_notifications: bool = True
    ) -> bool:
        """
        Delete an event from Google Calendar.
        
        Args:
            event_id: ID of the event to delete
            calendar_id: Calendar ID
            send_notifications: Send cancellation notifications
            
        Returns:
            True if deleted successfully
        """
        access_token = await self._get_access_token()
        
        url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}"
        params = {'sendUpdates': 'all' if send_notifications else 'none'}
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }
            
            async with session.delete(url, headers=headers, params=params) as response:
                if response.status not in (200, 204):
                    error_text = await response.text()
                    logger.error(f"Failed to delete Google Calendar event: {error_text}")
                    return False
        
        logger.info(f"✅ Deleted Google Calendar event: {event_id}")
        return True
    
    async def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary"
    ) -> Optional[GoogleCalendarEvent]:
        """
        Get a single event by ID.
        
        Args:
            event_id: Event ID
            calendar_id: Calendar ID
            
        Returns:
            GoogleCalendarEvent or None if not found
        """
        access_token = await self._get_access_token()
        
        url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status == 404:
                    return None
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to get Google Calendar event: {error_text}")
                    raise ValueError(f"Failed to get event: {response.status}")
                
                data = await response.json()
        
        start_data = data.get('start', {})
        end_data = data.get('end', {})
        start_str = start_data.get('dateTime') or start_data.get('date')
        end_str = end_data.get('dateTime') or end_data.get('date')
        
        start = datetime.fromisoformat(start_str.replace('Z', '+00:00')) if 'T' in start_str else datetime.strptime(start_str, '%Y-%m-%d')
        end = datetime.fromisoformat(end_str.replace('Z', '+00:00')) if 'T' in end_str else datetime.strptime(end_str, '%Y-%m-%d')
        
        return GoogleCalendarEvent(
            id=data.get('id', ''),
            summary=data.get('summary', 'Untitled Event'),
            description=data.get('description'),
            start=start,
            end=end,
            location=data.get('location'),
            attendees=[a.get('email', '') for a in data.get('attendees', [])],
            html_link=data.get('htmlLink'),
            hangout_link=data.get('hangoutLink'),
            conference_data=data.get('conferenceData')
        )


google_calendar_connector = GoogleCalendarConnector()
