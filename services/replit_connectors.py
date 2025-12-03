"""
Replit Connector Integration Services

This module provides Python implementations for fetching credentials from Replit's
connector API for Stripe, Google Calendar, and SendGrid integrations.

These services use the Replit connector infrastructure for secure credential management
with automatic token refresh and environment-aware configuration.
"""
import os
import logging
import aiohttp
from typing import Optional, Any
from functools import lru_cache
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ReplitConnectorError(Exception):
    """Error fetching credentials from Replit connector"""
    pass


async def _get_replit_token() -> str:
    """Get the X-Replit-Token for connector API authentication"""
    if os.environ.get("REPL_IDENTITY"):
        return f"repl {os.environ['REPL_IDENTITY']}"
    elif os.environ.get("WEB_REPL_RENEWAL"):
        return f"depl {os.environ['WEB_REPL_RENEWAL']}"
    else:
        raise ReplitConnectorError("X_REPLIT_TOKEN not found for repl/depl")


async def _fetch_connection_settings(connector_name: str, environment: Optional[str] = None) -> dict:
    """
    Fetch connection settings from Replit connector API.
    
    Args:
        connector_name: Name of the connector (e.g., 'stripe', 'google-calendar', 'sendgrid')
        environment: Optional environment ('development' or 'production')
    
    Returns:
        Connection settings dict from the API
    """
    hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME")
    if not hostname:
        raise ReplitConnectorError("REPLIT_CONNECTORS_HOSTNAME not set")
    
    token = await _get_replit_token()
    
    url = f"https://{hostname}/api/v2/connection"
    params = {
        "include_secrets": "true",
        "connector_names": connector_name
    }
    
    if environment:
        params["environment"] = environment
    
    headers = {
        "Accept": "application/json",
        "X_REPLIT_TOKEN": token
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status != 200:
                raise ReplitConnectorError(f"Failed to fetch {connector_name} connection: {response.status}")
            
            data = await response.json()
            items = data.get("items", [])
            
            if not items:
                raise ReplitConnectorError(f"{connector_name} connection not found")
            
            return items[0]


class StripeConnector:
    """
    Stripe connector for Replit integration.
    
    Provides access to Stripe API credentials from Replit's connector system.
    """
    _cached_settings: Optional[dict] = None
    _cache_expires_at: Optional[datetime] = None
    
    @classmethod
    async def get_credentials(cls) -> dict:
        """
        Get Stripe API credentials.
        
        Returns:
            dict with 'publishable_key' and 'secret_key'
        """
        is_production = os.environ.get("REPLIT_DEPLOYMENT") == "1"
        environment = "production" if is_production else "development"
        
        try:
            settings = await _fetch_connection_settings("stripe", environment)
            
            publishable = settings.get("settings", {}).get("publishable")
            secret = settings.get("settings", {}).get("secret")
            
            if not publishable or not secret:
                raise ReplitConnectorError(f"Stripe {environment} credentials incomplete")
            
            return {
                "publishable_key": publishable,
                "secret_key": secret,
                "environment": environment
            }
        except ReplitConnectorError:
            # Fallback to environment variables if connector not available
            secret_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_TEST_API_KEY")
            publishable_key = os.environ.get("STRIPE_PUBLISHABLE_KEY")
            
            if secret_key:
                logger.info("Using Stripe credentials from environment variables")
                return {
                    "publishable_key": publishable_key or "",
                    "secret_key": secret_key,
                    "environment": "fallback"
                }
            raise
    
    @classmethod
    async def get_stripe_client(cls):
        """
        Get a configured Stripe client.
        
        Returns:
            stripe module configured with the secret key
        """
        import stripe
        
        credentials = await cls.get_credentials()
        stripe.api_key = credentials["secret_key"]
        stripe.api_version = "2024-11-20.acacia"
        
        return stripe


class GoogleCalendarConnector:
    """
    Google Calendar connector for Replit integration.
    
    Provides access to Google Calendar OAuth tokens from Replit's connector system.
    """
    _cached_settings: Optional[dict] = None
    _cache_expires_at: Optional[datetime] = None
    
    @classmethod
    async def get_access_token(cls) -> str:
        """
        Get a fresh Google Calendar access token.
        
        Note: Tokens expire - always call this to get a fresh token.
        
        Returns:
            OAuth access token string
        """
        # Check cache first
        if cls._cached_settings and cls._cache_expires_at:
            expires_at = cls._cache_expires_at
            if datetime.now(timezone.utc) < expires_at:
                return cls._cached_settings.get("access_token", "")
        
        settings = await _fetch_connection_settings("google-calendar")
        
        settings_data = settings.get("settings", {})
        access_token = (
            settings_data.get("access_token") or 
            settings_data.get("oauth", {}).get("credentials", {}).get("access_token")
        )
        
        if not access_token:
            raise ReplitConnectorError("Google Calendar access token not found")
        
        # Cache with expiry
        expires_at_str = settings_data.get("expires_at")
        if expires_at_str:
            cls._cache_expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        cls._cached_settings = {"access_token": access_token}
        
        return access_token
    
    @classmethod
    async def get_calendar_service(cls):
        """
        Get a configured Google Calendar service.
        
        Returns:
            Google Calendar API resource
        """
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        
        access_token = await cls.get_access_token()
        
        credentials = Credentials(token=access_token)
        service = build("calendar", "v3", credentials=credentials)
        
        return service


class SendGridConnector:
    """
    SendGrid connector for Replit integration.
    
    Provides access to SendGrid API credentials from Replit's connector system.
    """
    
    @classmethod
    async def get_credentials(cls) -> dict:
        """
        Get SendGrid API credentials.
        
        Returns:
            dict with 'api_key' and 'from_email'
        """
        try:
            settings = await _fetch_connection_settings("sendgrid")
            
            api_key = settings.get("settings", {}).get("api_key")
            from_email = settings.get("settings", {}).get("from_email")
            
            if not api_key or not from_email:
                raise ReplitConnectorError("SendGrid credentials incomplete")
            
            return {
                "api_key": api_key,
                "from_email": from_email
            }
        except ReplitConnectorError:
            # Fallback to environment variables
            api_key = os.environ.get("SENDGRID_API_KEY")
            from_email = os.environ.get("SENDGRID_FROM_EMAIL")
            
            if api_key:
                logger.info("Using SendGrid credentials from environment variables")
                return {
                    "api_key": api_key,
                    "from_email": from_email or "noreply@example.com"
                }
            raise
    
    @classmethod
    async def send_email(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email via SendGrid.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body content
            text_content: Optional plain text content
        
        Returns:
            True if sent successfully
        """
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content
        
        credentials = await cls.get_credentials()
        
        message = Mail(
            from_email=Email(credentials["from_email"]),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        
        if text_content:
            message.add_content(Content("text/plain", text_content))
        
        sg = SendGridAPIClient(api_key=credentials["api_key"])
        response = sg.send(message)
        
        return response.status_code in (200, 201, 202)


# Synchronous wrappers for use in Flask routes
def get_stripe_credentials_sync() -> dict:
    """Synchronous wrapper for getting Stripe credentials"""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(StripeConnector.get_credentials())
    finally:
        loop.close()


def get_sendgrid_credentials_sync() -> dict:
    """Synchronous wrapper for getting SendGrid credentials"""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(SendGridConnector.get_credentials())
    finally:
        loop.close()


def send_email_sync(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
    """Synchronous wrapper for sending email"""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(SendGridConnector.send_email(to_email, subject, html_content, text_content))
    finally:
        loop.close()
