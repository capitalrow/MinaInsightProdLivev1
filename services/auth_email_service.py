"""
Authentication Email Service for Mina
Handles welcome emails, password reset, and email verification.
Uses SendGrid via Replit connector for delivery.
"""

import os
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict

from services.email_service import email_service
from services.email_templates import (
    get_welcome_email_html,
    get_password_reset_email_html,
    get_email_verification_html,
    get_password_changed_email_html
)

logger = logging.getLogger(__name__)


class AuthEmailService:
    """Service for authentication-related emails."""
    
    def __init__(self):
        self.password_reset_expiry_hours = 24
        self.verification_token_length = 64
    
    def generate_token(self) -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(self.verification_token_length)
    
    def send_welcome_email(
        self,
        user_email: str,
        first_name: str,
        base_url: str,
        verification_token: Optional[str] = None
    ) -> Dict:
        """
        Send welcome email to new user.
        Includes optional verification link for passive verification.
        """
        if not email_service.is_available():
            logger.warning("Email service not available - skipping welcome email")
            return {'success': False, 'error': 'Email service not configured'}
        
        verification_link = None
        if verification_token:
            verification_link = f"{base_url.rstrip('/')}/auth/verify-email/{verification_token}"
        else:
            verification_link = f"{base_url.rstrip('/')}/dashboard"
        
        subject, html_content = get_welcome_email_html(first_name, verification_link)
        
        try:
            creds = email_service._get_credentials()
            if not creds:
                return {'success': False, 'error': 'Email credentials not available'}
            
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=creds['api_key'])
            
            from_email = Email(creds['from_email'], 'Mina')
            to_email = To(user_email)
            content = Content("text/html", html_content)
            
            mail = Mail(from_email, to_email, subject, content)
            response = sg.send(mail)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Welcome email sent to {user_email}")
                return {'success': True, 'message': 'Welcome email sent'}
            else:
                logger.error(f"❌ Welcome email failed: {response.status_code}")
                return {'success': False, 'error': f'Email failed: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"❌ Welcome email error: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_password_reset_email(
        self,
        user_email: str,
        first_name: str,
        reset_token: str,
        base_url: str
    ) -> Dict:
        """Send password reset email with secure token link."""
        if not email_service.is_available():
            logger.warning("Email service not available - skipping password reset email")
            return {'success': False, 'error': 'Email service not configured'}
        
        reset_link = f"{base_url.rstrip('/')}/auth/reset-password/{reset_token}"
        
        subject, html_content = get_password_reset_email_html(
            first_name,
            reset_link,
            self.password_reset_expiry_hours
        )
        
        try:
            creds = email_service._get_credentials()
            if not creds:
                return {'success': False, 'error': 'Email credentials not available'}
            
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=creds['api_key'])
            
            from_email = Email(creds['from_email'], 'Mina')
            to_email = To(user_email)
            content = Content("text/html", html_content)
            
            mail = Mail(from_email, to_email, subject, content)
            response = sg.send(mail)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Password reset email sent to {user_email}")
                return {'success': True, 'message': 'Password reset email sent'}
            else:
                logger.error(f"❌ Password reset email failed: {response.status_code}")
                return {'success': False, 'error': f'Email failed: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"❌ Password reset email error: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_verification_email(
        self,
        user_email: str,
        first_name: str,
        verification_token: str,
        base_url: str
    ) -> Dict:
        """Send email verification request."""
        if not email_service.is_available():
            logger.warning("Email service not available - skipping verification email")
            return {'success': False, 'error': 'Email service not configured'}
        
        verification_link = f"{base_url.rstrip('/')}/auth/verify-email/{verification_token}"
        
        subject, html_content = get_email_verification_html(first_name, verification_link)
        
        try:
            creds = email_service._get_credentials()
            if not creds:
                return {'success': False, 'error': 'Email credentials not available'}
            
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=creds['api_key'])
            
            from_email = Email(creds['from_email'], 'Mina')
            to_email = To(user_email)
            content = Content("text/html", html_content)
            
            mail = Mail(from_email, to_email, subject, content)
            response = sg.send(mail)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Verification email sent to {user_email}")
                return {'success': True, 'message': 'Verification email sent'}
            else:
                logger.error(f"❌ Verification email failed: {response.status_code}")
                return {'success': False, 'error': f'Email failed: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"❌ Verification email error: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_password_changed_email(
        self,
        user_email: str,
        first_name: str
    ) -> Dict:
        """Send password changed confirmation (security notification)."""
        if not email_service.is_available():
            logger.warning("Email service not available - skipping password changed email")
            return {'success': False, 'error': 'Email service not configured'}
        
        subject, html_content = get_password_changed_email_html(first_name)
        
        try:
            creds = email_service._get_credentials()
            if not creds:
                return {'success': False, 'error': 'Email credentials not available'}
            
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=creds['api_key'])
            
            from_email = Email(creds['from_email'], 'Mina')
            to_email = To(user_email)
            content = Content("text/html", html_content)
            
            mail = Mail(from_email, to_email, subject, content)
            response = sg.send(mail)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Password changed email sent to {user_email}")
                return {'success': True, 'message': 'Password changed email sent'}
            else:
                logger.error(f"❌ Password changed email failed: {response.status_code}")
                return {'success': False, 'error': f'Email failed: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"❌ Password changed email error: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_password_reset_token(self, user) -> str:
        """
        Create password reset token for user.
        Sets token and expiry on user object (caller must commit).
        """
        token = self.generate_token()
        user.password_reset_token = token
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=self.password_reset_expiry_hours)
        return token
    
    def verify_password_reset_token(self, user, token: str) -> bool:
        """Verify password reset token is valid and not expired."""
        if not user.password_reset_token or not user.password_reset_expires:
            return False
        
        if user.password_reset_token != token:
            return False
        
        if datetime.utcnow() > user.password_reset_expires:
            return False
        
        return True
    
    def clear_password_reset_token(self, user):
        """Clear password reset token after use."""
        user.password_reset_token = None
        user.password_reset_expires = None
    
    def create_verification_token(self, user) -> str:
        """
        Create email verification token for user.
        Sets token and timestamp on user object (caller must commit).
        """
        token = self.generate_token()
        user.email_verification_token = token
        user.email_verification_sent_at = datetime.utcnow()
        return token
    
    def verify_email_token(self, user, token: str) -> bool:
        """Verify email verification token is valid."""
        if not user.email_verification_token:
            return False
        
        return user.email_verification_token == token
    
    def mark_email_verified(self, user):
        """Mark user's email as verified and clear token."""
        user.is_verified = True
        user.email_verification_token = None
        user.email_verification_sent_at = None


auth_email_service = AuthEmailService()
