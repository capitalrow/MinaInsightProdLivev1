"""
Email Service for Mina - Phase 2 Group 4 (T2.27)
Handles sending transcripts via email with summary and optional attachments.
"""

import os
import logging
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending meeting transcripts via email."""
    
    def __init__(self):
        self.sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
        self.from_email = os.environ.get('FROM_EMAIL', 'noreply@mina.app')
        self.from_name = os.environ.get('FROM_NAME', 'Mina')
        self.is_configured = bool(self.sendgrid_api_key)
        
        if self.is_configured:
            logger.info("✅ Email service initialized with SendGrid")
        else:
            logger.warning("⚠️ Email service not configured - SENDGRID_API_KEY not found")
    
    def is_available(self) -> bool:
        """Check if email service is available."""
        return self.is_configured
    
    def send_transcript_email(
        self,
        to_emails: List[str],
        session_title: str,
        session_date: datetime,
        summary: Optional[str] = None,
        share_link: Optional[str] = None,
        sender_name: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> Dict:
        """
        Send transcript via email.
        
        Args:
            to_emails: List of recipient email addresses
            session_title: Meeting/session title
            session_date: Date of the meeting
            summary: Optional meeting summary
            share_link: Optional link to full transcript
            sender_name: Name of the person sharing
            custom_message: Optional personal message from sender
            
        Returns:
            Dict with success status and message
        """
        if not self.is_configured:
            return {
                'success': False,
                'error': 'Email service not configured. Please set up SendGrid integration.'
            }
        
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=self.sendgrid_api_key)
            
            subject = f"Meeting Transcript: {session_title}"
            
            html_content = self._generate_email_html(
                session_title=session_title,
                session_date=session_date,
                summary=summary,
                share_link=share_link,
                sender_name=sender_name,
                custom_message=custom_message
            )
            
            from_email = Email(self.from_email, self.from_name)
            to_list = [To(email) for email in to_emails]
            content = Content("text/html", html_content)
            
            mail = Mail(from_email, to_list[0], subject, content)
            
            if len(to_list) > 1:
                for to_email in to_list[1:]:
                    mail.add_to(to_email)
            
            response = sg.send(mail)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Email sent successfully to {len(to_emails)} recipients")
                return {
                    'success': True,
                    'message': f'Email sent to {len(to_emails)} recipient(s)'
                }
            else:
                logger.error(f"❌ SendGrid API error: {response.status_code}")
                return {
                    'success': False,
                    'error': f'Email sending failed with status {response.status_code}'
                }
                
        except ImportError:
            logger.error("❌ SendGrid library not installed")
            return {
                'success': False,
                'error': 'SendGrid library not installed. Please install sendgrid package.'
            }
        except Exception as e:
            logger.error(f"❌ Email sending error: {str(e)}")
            return {
                'success': False,
                'error': f'Email sending failed: {str(e)}'
            }
    
    def _generate_email_html(
        self,
        session_title: str,
        session_date: datetime,
        summary: Optional[str] = None,
        share_link: Optional[str] = None,
        sender_name: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> str:
        """Generate HTML email template."""
        
        date_str = session_date.strftime('%B %d, %Y at %I:%M %p') if session_date else 'Unknown date'
        sender_text = f"{sender_name} has" if sender_name else "Someone has"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{session_title} - Mina Transcript</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f1e; color: #e4e4e7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; width: 100%; border-collapse: collapse;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); border-radius: 16px 16px 0 0;">
                            <h1 style="margin: 0; color: white; font-size: 28px; font-weight: 700;">
                                Meeting Transcript
                            </h1>
                            <p style="margin: 8px 0 0; color: rgba(255,255,255,0.9); font-size: 16px;">
                                {sender_text} shared a meeting transcript with you
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px; background: rgba(255,255,255,0.03); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); border-top: none;">
                            
                            <!-- Meeting Title -->
                            <h2 style="margin: 0 0 16px; color: #e4e4e7; font-size: 24px; font-weight: 600;">
                                {session_title}
                            </h2>
                            
                            <!-- Meeting Date -->
                            <p style="margin: 0 0 24px; color: #a1a1aa; font-size: 14px;">
                                📅 {date_str}
                            </p>
                            
                            <!-- Custom Message -->
                            {f'''
                            <div style="margin: 0 0 24px; padding: 16px; background: rgba(99,102,241,0.1); border-left: 3px solid #6366f1; border-radius: 8px;">
                                <p style="margin: 0; color: #e4e4e7; line-height: 1.6;">
                                    {custom_message}
                                </p>
                            </div>
                            ''' if custom_message else ''}
                            
                            <!-- Summary -->
                            {f'''
                            <div style="margin: 0 0 24px;">
                                <h3 style="margin: 0 0 12px; color: #e4e4e7; font-size: 18px; font-weight: 600;">
                                    📝 Summary
                                </h3>
                                <p style="margin: 0; color: #a1a1aa; line-height: 1.7;">
                                    {summary}
                                </p>
                            </div>
                            ''' if summary else ''}
                            
                            <!-- View Transcript Button -->
                            {f'''
                            <div style="margin: 32px 0; text-align: center;">
                                <a href="{share_link}" style="display: inline-block; padding: 14px 32px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
                                    View Full Transcript →
                                </a>
                            </div>
                            ''' if share_link else ''}
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 32px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.1); border-top: none; border-radius: 0 0 16px 16px;">
                            <p style="margin: 0 0 8px; color: #71717a; font-size: 14px;">
                                Powered by <strong style="color: #a1a1aa;">Mina</strong>
                            </p>
                            <p style="margin: 0; color: #52525b; font-size: 12px;">
                                Transform your meetings into actionable moments with AI-powered transcription and insights.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """
        
        return html.strip()


email_service = EmailService()
