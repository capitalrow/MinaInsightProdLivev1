"""
Email Templates Service for Mina
Natural, human-written email templates - no robotic AI-speak.
Includes both HTML and plain text for better deliverability.
"""

from typing import Optional, Tuple
from datetime import datetime


def get_welcome_email(
    first_name: str,
    verification_link: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Generate welcome email for new users.
    Returns (subject, html_content, plain_text_content).
    """
    name = first_name if first_name else "there"
    
    subject = f"Welcome to Mina, {name}!"
    
    plain_text = f"""Hey {name}!

Welcome to Mina! You're all set to start capturing your meetings.

Here's the quick version: hit record, talk, and we'll turn your conversation into a searchable transcript with AI-powered insights. No complicated setup needed.

Getting started is simple:
1. Click "Live" in the sidebar
2. Hit the record button
3. That's it - we handle the rest

{f"Go to Mina: {verification_link}" if verification_link else ""}

Questions? Just reply to this email - a real person reads these.

--
Mina - Turn meetings into moments that matter.
"""
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f1e; color: #e4e4e7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 560px; width: 100%; border-collapse: collapse;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); border-radius: 16px 16px 0 0;">
                            <h1 style="margin: 0; color: white; font-size: 26px; font-weight: 600;">
                                Hey {name}! 👋
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-top: none;">
                            
                            <p style="margin: 0 0 20px; color: #e4e4e7; font-size: 16px; line-height: 1.7;">
                                Welcome to Mina! You're all set to start capturing your meetings.
                            </p>
                            
                            <p style="margin: 0 0 24px; color: #a1a1aa; font-size: 15px; line-height: 1.7;">
                                Here's the quick version: hit record, talk, and we'll turn your conversation into a searchable transcript with AI-powered insights. No complicated setup needed.
                            </p>
                            
                            <!-- Quick Start -->
                            <div style="margin: 24px 0; padding: 20px; background: rgba(99,102,241,0.1); border-radius: 12px; border-left: 3px solid #6366f1;">
                                <p style="margin: 0 0 12px; color: #e4e4e7; font-size: 15px; font-weight: 600;">
                                    Getting started is simple:
                                </p>
                                <p style="margin: 0; color: #a1a1aa; font-size: 14px; line-height: 1.8;">
                                    1. Click "Live" in the sidebar<br>
                                    2. Hit the record button<br>
                                    3. That's it — we handle the rest
                                </p>
                            </div>
                            
                            {f'''
                            <div style="margin: 28px 0; text-align: center;">
                                <a href="{verification_link}" style="display: inline-block; padding: 14px 28px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
                                    Go to Mina →
                                </a>
                            </div>
                            ''' if verification_link else ''}
                            
                            <p style="margin: 24px 0 0; color: #71717a; font-size: 14px; line-height: 1.6;">
                                Questions? Just reply to this email — a real person reads these.
                            </p>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 32px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.1); border-top: none; border-radius: 0 0 16px 16px;">
                            <p style="margin: 0; color: #52525b; font-size: 13px;">
                                Mina — Turn meetings into moments that matter.
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
    
    return subject, html.strip(), plain_text.strip()


def get_welcome_email_html(
    first_name: str,
    verification_link: Optional[str] = None
) -> Tuple[str, str]:
    """Legacy function - returns (subject, html_content) for backwards compatibility."""
    subject, html, _ = get_welcome_email(first_name, verification_link)
    return subject, html


def get_password_reset_email(
    first_name: str,
    reset_link: str,
    expires_in_hours: int = 24
) -> Tuple[str, str, str]:
    """
    Generate password reset email.
    Returns (subject, html_content, plain_text_content).
    """
    name = first_name if first_name else "there"
    
    subject = "Reset your Mina password"
    
    plain_text = f"""Hey {name},

We got a request to reset your password. If that was you, click the link below to choose a new one.

Reset your password: {reset_link}

This link expires in {expires_in_hours} hours.

Didn't request this? No worries - just ignore this email and your password stays the same.

--
Mina - Turn meetings into moments that matter.
"""
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f1e; color: #e4e4e7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 560px; width: 100%; border-collapse: collapse;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); border-radius: 16px 16px 0 0;">
                            <h1 style="margin: 0; color: white; font-size: 24px; font-weight: 600;">
                                Password Reset
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-top: none;">
                            
                            <p style="margin: 0 0 20px; color: #e4e4e7; font-size: 16px; line-height: 1.7;">
                                Hey {name},
                            </p>
                            
                            <p style="margin: 0 0 24px; color: #a1a1aa; font-size: 15px; line-height: 1.7;">
                                We got a request to reset your password. If that was you, click the button below to choose a new one.
                            </p>
                            
                            <div style="margin: 28px 0; text-align: center;">
                                <a href="{reset_link}" style="display: inline-block; padding: 14px 28px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
                                    Reset Password
                                </a>
                            </div>
                            
                            <p style="margin: 0 0 16px; color: #71717a; font-size: 14px; line-height: 1.6;">
                                This link expires in {expires_in_hours} hours.
                            </p>
                            
                            <p style="margin: 0; color: #71717a; font-size: 14px; line-height: 1.6;">
                                Didn't request this? No worries — just ignore this email and your password stays the same.
                            </p>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 32px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.1); border-top: none; border-radius: 0 0 16px 16px;">
                            <p style="margin: 0; color: #52525b; font-size: 13px;">
                                Mina — Turn meetings into moments that matter.
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
    
    return subject, html.strip(), plain_text.strip()


def get_password_reset_email_html(
    first_name: str,
    reset_link: str,
    expires_in_hours: int = 24
) -> Tuple[str, str]:
    """Legacy function - returns (subject, html_content) for backwards compatibility."""
    subject, html, _ = get_password_reset_email(first_name, reset_link, expires_in_hours)
    return subject, html


def get_email_verification(
    first_name: str,
    verification_link: str
) -> Tuple[str, str, str]:
    """
    Generate email verification request.
    Returns (subject, html_content, plain_text_content).
    """
    name = first_name if first_name else "there"
    
    subject = "Quick thing - verify your email"
    
    plain_text = f"""Hey {name},

We just need to make sure this email actually reaches you. Click the link below and you're all set.

Verify your email: {verification_link}

Didn't sign up for Mina? Someone might have typed your email by mistake. Feel free to ignore this.

--
Mina - Turn meetings into moments that matter.
"""
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f1e; color: #e4e4e7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 560px; width: 100%; border-collapse: collapse;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); border-radius: 16px 16px 0 0;">
                            <h1 style="margin: 0; color: white; font-size: 24px; font-weight: 600;">
                                One quick click
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-top: none;">
                            
                            <p style="margin: 0 0 20px; color: #e4e4e7; font-size: 16px; line-height: 1.7;">
                                Hey {name},
                            </p>
                            
                            <p style="margin: 0 0 24px; color: #a1a1aa; font-size: 15px; line-height: 1.7;">
                                We just need to make sure this email actually reaches you. Click below and you're all set.
                            </p>
                            
                            <div style="margin: 28px 0; text-align: center;">
                                <a href="{verification_link}" style="display: inline-block; padding: 14px 28px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px;">
                                    Verify Email
                                </a>
                            </div>
                            
                            <p style="margin: 0; color: #71717a; font-size: 14px; line-height: 1.6;">
                                Didn't sign up for Mina? Someone might have typed your email by mistake. Feel free to ignore this.
                            </p>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 32px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.1); border-top: none; border-radius: 0 0 16px 16px;">
                            <p style="margin: 0; color: #52525b; font-size: 13px;">
                                Mina — Turn meetings into moments that matter.
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
    
    return subject, html.strip(), plain_text.strip()


def get_email_verification_html(
    first_name: str,
    verification_link: str
) -> Tuple[str, str]:
    """Legacy function - returns (subject, html_content) for backwards compatibility."""
    subject, html, _ = get_email_verification(first_name, verification_link)
    return subject, html


def get_password_changed_email(first_name: str) -> Tuple[str, str, str]:
    """
    Generate password changed confirmation email.
    Returns (subject, html_content, plain_text_content).
    """
    name = first_name if first_name else "there"
    now = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
    
    subject = "Your password was changed"
    
    plain_text = f"""Hey {name},

Just a heads up - your Mina password was changed on {now}.

If that was you, you're all set. If not, please reset your password immediately and contact us.

Questions? Reply to this email anytime.

--
Mina - Turn meetings into moments that matter.
"""
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f1e; color: #e4e4e7;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 560px; width: 100%; border-collapse: collapse;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); border-radius: 16px 16px 0 0;">
                            <h1 style="margin: 0; color: white; font-size: 24px; font-weight: 600;">
                                Password Updated
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 32px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-top: none;">
                            
                            <p style="margin: 0 0 20px; color: #e4e4e7; font-size: 16px; line-height: 1.7;">
                                Hey {name},
                            </p>
                            
                            <p style="margin: 0 0 16px; color: #a1a1aa; font-size: 15px; line-height: 1.7;">
                                Just a heads up — your Mina password was changed on {now}.
                            </p>
                            
                            <p style="margin: 0 0 24px; color: #a1a1aa; font-size: 15px; line-height: 1.7;">
                                If that was you, you're all set. If not, please reset your password immediately and contact us.
                            </p>
                            
                            <p style="margin: 0; color: #71717a; font-size: 14px; line-height: 1.6;">
                                Questions? Reply to this email anytime.
                            </p>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 32px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.1); border-top: none; border-radius: 0 0 16px 16px;">
                            <p style="margin: 0; color: #52525b; font-size: 13px;">
                                Mina — Turn meetings into moments that matter.
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
    
    return subject, html.strip(), plain_text.strip()


def get_password_changed_email_html(first_name: str) -> Tuple[str, str]:
    """Legacy function - returns (subject, html_content) for backwards compatibility."""
    subject, html, _ = get_password_changed_email(first_name)
    return subject, html