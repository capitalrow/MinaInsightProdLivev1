"""
Email Templates Service for Mina
Clean, refined, personable email templates.
Designed to feel human-written and warm, never robotic or AI-generated.
"""

from typing import Optional, Tuple
from datetime import datetime


# Shared base styles for all emails
BASE_STYLES = """
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #fafafa;
    color: #1a1a2e;
"""

HEADER_GRADIENT = "linear-gradient(135deg, #5b4dc7 0%, #7c3aed 50%, #9333ea 100%)"


def _get_email_wrapper(content: str, preheader: str = "") -> str:
    """Wrap email content in consistent, clean layout."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Mina</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    </style>
</head>
<body style="margin: 0; padding: 0; {BASE_STYLES}">
    <!-- Preheader text (hidden) -->
    <span style="display: none; font-size: 1px; color: #fafafa; line-height: 1px; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
        {preheader}
    </span>
    
    <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; border-collapse: collapse; background: #fafafa;">
        <tr>
            <td align="center" style="padding: 48px 24px;">
                <table role="presentation" cellpadding="0" cellspacing="0" style="max-width: 520px; width: 100%; border-collapse: collapse;">
                    
                    <!-- Logo -->
                    <tr>
                        <td align="center" style="padding: 0 0 32px;">
                            <table role="presentation" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size: 28px; font-weight: 600; color: #5b4dc7; letter-spacing: -0.5px;">
                                        mina
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Card -->
                    <tr>
                        <td style="background: #ffffff; border-radius: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.05);">
                            {content}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td align="center" style="padding: 32px 24px 0;">
                            <p style="margin: 0 0 8px; font-size: 13px; color: #9ca3af; line-height: 1.5;">
                                Questions? Just reply to this email.
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #d1d5db;">
                                Mina by Team Mina &bull; <a href="https://teammina.com" style="color: #9ca3af; text-decoration: none;">teammina.com</a>
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """.strip()


def get_welcome_email(
    first_name: str,
    verification_link: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Generate welcome email for new users.
    Returns (subject, html_content, plain_text_content).
    """
    name = first_name.strip().title() if first_name else "there"
    
    subject = f"Welcome to Mina, {name}"
    
    plain_text = f"""Hi {name},

Thanks for joining Mina! We're glad you're here.

Getting started takes about 30 seconds:

1. Open Mina and click "Live"
2. Hit the microphone button
3. Start talking - we'll do the rest

Your meetings become searchable transcripts with key moments highlighted automatically. No setup, no learning curve.

{f"Get started: {verification_link}" if verification_link else ""}

If you have any questions, just reply to this email. We read and respond to every message.

Best,
The Mina Team
"""
    
    cta_button = ""
    if verification_link:
        cta_button = f"""
                            <tr>
                                <td align="center" style="padding: 8px 0 24px;">
                                    <a href="{verification_link}" style="display: inline-block; padding: 14px 32px; background: {HEADER_GRADIENT}; color: #ffffff; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px; letter-spacing: 0.2px;">
                                        Get Started
                                    </a>
                                </td>
                            </tr>
        """
    
    content = f"""
                            <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%;">
                                <!-- Header accent -->
                                <tr>
                                    <td style="height: 4px; background: {HEADER_GRADIENT}; border-radius: 16px 16px 0 0;"></td>
                                </tr>
                                
                                <!-- Main content -->
                                <tr>
                                    <td style="padding: 40px 40px 32px;">
                                        <h1 style="margin: 0 0 24px; font-size: 24px; font-weight: 600; color: #1a1a2e; line-height: 1.3;">
                                            Hi {name}, welcome!
                                        </h1>
                                        
                                        <p style="margin: 0 0 20px; font-size: 16px; color: #4b5563; line-height: 1.7;">
                                            Thanks for joining Mina. We're glad you're here.
                                        </p>
                                        
                                        <p style="margin: 0 0 24px; font-size: 15px; color: #6b7280; line-height: 1.7;">
                                            Getting started takes about 30 seconds:
                                        </p>
                                        
                                        <!-- Steps -->
                                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; margin: 0 0 24px;">
                                            <tr>
                                                <td style="padding: 12px 16px; background: #f9fafb; border-radius: 8px; border-left: 3px solid #5b4dc7;">
                                                    <p style="margin: 0; font-size: 14px; color: #374151; line-height: 1.8;">
                                                        <strong style="color: #5b4dc7;">1.</strong> Open Mina and click "Live"<br>
                                                        <strong style="color: #5b4dc7;">2.</strong> Hit the microphone button<br>
                                                        <strong style="color: #5b4dc7;">3.</strong> Start talking - we'll do the rest
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                        
                                        <p style="margin: 0 0 28px; font-size: 15px; color: #6b7280; line-height: 1.7;">
                                            Your meetings become searchable transcripts with key moments highlighted automatically. No setup, no learning curve.
                                        </p>
                                    </td>
                                </tr>
                                
                                {cta_button}
                            </table>
    """
    
    html = _get_email_wrapper(content, f"Welcome to Mina, {name}! Get started in 30 seconds.")
    
    return subject, html, plain_text.strip()


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
    name = first_name.strip().title() if first_name else "there"
    
    subject = "Reset your Mina password"
    
    plain_text = f"""Hi {name},

Someone requested a password reset for your Mina account. If that was you, click the link below to set a new password.

Reset your password: {reset_link}

This link will expire in {expires_in_hours} hours for security.

If you didn't request this, you can safely ignore this email. Your password won't change unless you click the link above.

Best,
The Mina Team
"""
    
    content = f"""
                            <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%;">
                                <!-- Header accent -->
                                <tr>
                                    <td style="height: 4px; background: {HEADER_GRADIENT}; border-radius: 16px 16px 0 0;"></td>
                                </tr>
                                
                                <!-- Main content -->
                                <tr>
                                    <td style="padding: 40px 40px 32px;">
                                        <h1 style="margin: 0 0 24px; font-size: 24px; font-weight: 600; color: #1a1a2e; line-height: 1.3;">
                                            Reset your password
                                        </h1>
                                        
                                        <p style="margin: 0 0 20px; font-size: 16px; color: #4b5563; line-height: 1.7;">
                                            Hi {name},
                                        </p>
                                        
                                        <p style="margin: 0 0 28px; font-size: 15px; color: #6b7280; line-height: 1.7;">
                                            Someone requested a password reset for your Mina account. If that was you, click the button below to choose a new password.
                                        </p>
                                    </td>
                                </tr>
                                
                                <!-- CTA Button -->
                                <tr>
                                    <td align="center" style="padding: 0 40px 32px;">
                                        <a href="{reset_link}" style="display: inline-block; padding: 14px 32px; background: {HEADER_GRADIENT}; color: #ffffff; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px; letter-spacing: 0.2px;">
                                            Reset Password
                                        </a>
                                    </td>
                                </tr>
                                
                                <!-- Security note -->
                                <tr>
                                    <td style="padding: 0 40px 40px;">
                                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%;">
                                            <tr>
                                                <td style="padding: 16px; background: #fef3c7; border-radius: 8px; border-left: 3px solid #f59e0b;">
                                                    <p style="margin: 0; font-size: 13px; color: #92400e; line-height: 1.6;">
                                                        <strong>This link expires in {expires_in_hours} hours.</strong><br>
                                                        If you didn't request this, ignore this email. Your password won't change.
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
    """
    
    html = _get_email_wrapper(content, "Reset your Mina password")
    
    return subject, html, plain_text.strip()


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
    name = first_name.strip().title() if first_name else "there"
    
    subject = "Verify your email address"
    
    plain_text = f"""Hi {name},

Thanks for signing up for Mina! Please verify your email address by clicking the link below.

Verify email: {verification_link}

If you didn't create a Mina account, you can ignore this email.

Best,
The Mina Team
"""
    
    content = f"""
                            <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%;">
                                <!-- Header accent -->
                                <tr>
                                    <td style="height: 4px; background: {HEADER_GRADIENT}; border-radius: 16px 16px 0 0;"></td>
                                </tr>
                                
                                <!-- Main content -->
                                <tr>
                                    <td style="padding: 40px 40px 32px;">
                                        <h1 style="margin: 0 0 24px; font-size: 24px; font-weight: 600; color: #1a1a2e; line-height: 1.3;">
                                            Verify your email
                                        </h1>
                                        
                                        <p style="margin: 0 0 20px; font-size: 16px; color: #4b5563; line-height: 1.7;">
                                            Hi {name},
                                        </p>
                                        
                                        <p style="margin: 0 0 28px; font-size: 15px; color: #6b7280; line-height: 1.7;">
                                            Thanks for signing up for Mina! Click the button below to verify your email address and get started.
                                        </p>
                                    </td>
                                </tr>
                                
                                <!-- CTA Button -->
                                <tr>
                                    <td align="center" style="padding: 0 40px 32px;">
                                        <a href="{verification_link}" style="display: inline-block; padding: 14px 32px; background: {HEADER_GRADIENT}; color: #ffffff; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px; letter-spacing: 0.2px;">
                                            Verify Email
                                        </a>
                                    </td>
                                </tr>
                                
                                <!-- Note -->
                                <tr>
                                    <td style="padding: 0 40px 40px;">
                                        <p style="margin: 0; font-size: 14px; color: #9ca3af; line-height: 1.6;">
                                            If you didn't create a Mina account, you can safely ignore this email.
                                        </p>
                                    </td>
                                </tr>
                            </table>
    """
    
    html = _get_email_wrapper(content, f"Please verify your email, {name}")
    
    return subject, html, plain_text.strip()


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
    name = first_name.strip().title() if first_name else "there"
    now = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
    
    subject = "Your password was changed"
    
    plain_text = f"""Hi {name},

Your Mina password was successfully changed on {now}.

If you made this change, no action is needed.

If you didn't change your password, please reset it immediately and contact us by replying to this email.

Best,
The Mina Team
"""
    
    content = f"""
                            <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%;">
                                <!-- Header accent -->
                                <tr>
                                    <td style="height: 4px; background: {HEADER_GRADIENT}; border-radius: 16px 16px 0 0;"></td>
                                </tr>
                                
                                <!-- Main content -->
                                <tr>
                                    <td style="padding: 40px 40px 32px;">
                                        <h1 style="margin: 0 0 24px; font-size: 24px; font-weight: 600; color: #1a1a2e; line-height: 1.3;">
                                            Password changed
                                        </h1>
                                        
                                        <p style="margin: 0 0 20px; font-size: 16px; color: #4b5563; line-height: 1.7;">
                                            Hi {name},
                                        </p>
                                        
                                        <p style="margin: 0 0 24px; font-size: 15px; color: #6b7280; line-height: 1.7;">
                                            Your Mina password was successfully changed on {now}.
                                        </p>
                                        
                                        <!-- Success indicator -->
                                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; margin: 0 0 24px;">
                                            <tr>
                                                <td style="padding: 16px; background: #ecfdf5; border-radius: 8px; border-left: 3px solid #10b981;">
                                                    <p style="margin: 0; font-size: 14px; color: #065f46; line-height: 1.6;">
                                                        <strong>If you made this change</strong>, no action is needed.
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                        
                                        <!-- Warning -->
                                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%;">
                                            <tr>
                                                <td style="padding: 16px; background: #fef2f2; border-radius: 8px; border-left: 3px solid #ef4444;">
                                                    <p style="margin: 0; font-size: 14px; color: #991b1b; line-height: 1.6;">
                                                        <strong>If you didn't make this change</strong>, please reset your password immediately and reply to this email to let us know.
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
    """
    
    html = _get_email_wrapper(content, "Your Mina password was changed")
    
    return subject, html, plain_text.strip()


def get_password_changed_email_html(first_name: str) -> Tuple[str, str]:
    """Legacy function - returns (subject, html_content) for backwards compatibility."""
    subject, html, _ = get_password_changed_email(first_name)
    return subject, html


def get_task_reminder_email(
    first_name: str,
    task_title: str,
    task_due_date: str,
    meeting_title: str,
    task_link: str
) -> Tuple[str, str, str]:
    """
    Generate task reminder email.
    Returns (subject, html_content, plain_text_content).
    """
    name = first_name.strip().title() if first_name else "there"
    
    subject = f"Reminder: {task_title}"
    
    plain_text = f"""Hi {name},

Just a quick reminder about a task from your meeting "{meeting_title}":

Task: {task_title}
Due: {task_due_date}

View task: {task_link}

Best,
The Mina Team
"""
    
    content = f"""
                            <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%;">
                                <!-- Header accent -->
                                <tr>
                                    <td style="height: 4px; background: {HEADER_GRADIENT}; border-radius: 16px 16px 0 0;"></td>
                                </tr>
                                
                                <!-- Main content -->
                                <tr>
                                    <td style="padding: 40px 40px 32px;">
                                        <h1 style="margin: 0 0 24px; font-size: 24px; font-weight: 600; color: #1a1a2e; line-height: 1.3;">
                                            Task reminder
                                        </h1>
                                        
                                        <p style="margin: 0 0 20px; font-size: 16px; color: #4b5563; line-height: 1.7;">
                                            Hi {name},
                                        </p>
                                        
                                        <p style="margin: 0 0 24px; font-size: 15px; color: #6b7280; line-height: 1.7;">
                                            Just a quick reminder about a task from your meeting.
                                        </p>
                                        
                                        <!-- Task card -->
                                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; margin: 0 0 28px;">
                                            <tr>
                                                <td style="padding: 20px; background: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb;">
                                                    <p style="margin: 0 0 8px; font-size: 11px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px;">
                                                        From: {meeting_title}
                                                    </p>
                                                    <p style="margin: 0 0 12px; font-size: 17px; font-weight: 600; color: #1a1a2e; line-height: 1.4;">
                                                        {task_title}
                                                    </p>
                                                    <p style="margin: 0; font-size: 14px; color: #f59e0b; font-weight: 500;">
                                                        Due: {task_due_date}
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                
                                <!-- CTA Button -->
                                <tr>
                                    <td align="center" style="padding: 0 40px 40px;">
                                        <a href="{task_link}" style="display: inline-block; padding: 14px 32px; background: {HEADER_GRADIENT}; color: #ffffff; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px; letter-spacing: 0.2px;">
                                            View Task
                                        </a>
                                    </td>
                                </tr>
                            </table>
    """
    
    html = _get_email_wrapper(content, f"Reminder: {task_title} is due {task_due_date}")
    
    return subject, html, plain_text.strip()


def get_meeting_summary_email(
    first_name: str,
    meeting_title: str,
    meeting_date: str,
    summary_points: list,
    task_count: int,
    meeting_link: str
) -> Tuple[str, str, str]:
    """
    Generate meeting summary email.
    Returns (subject, html_content, plain_text_content).
    """
    name = first_name.strip().title() if first_name else "there"
    
    subject = f"Meeting Summary: {meeting_title}"
    
    points_text = "\n".join([f"- {point}" for point in summary_points[:5]])
    
    plain_text = f"""Hi {name},

Here's a summary of your meeting "{meeting_title}" from {meeting_date}:

Key Points:
{points_text}

{f"Tasks extracted: {task_count}" if task_count > 0 else ""}

View full meeting: {meeting_link}

Best,
The Mina Team
"""
    
    points_html = "".join([
        f'<li style="margin: 0 0 8px; font-size: 14px; color: #4b5563; line-height: 1.6;">{point}</li>'
        for point in summary_points[:5]
    ])
    
    task_badge = ""
    if task_count > 0:
        task_badge = f"""
                                        <p style="margin: 20px 0 0; padding: 10px 16px; background: #f3e8ff; border-radius: 8px; font-size: 14px; color: #7c3aed; display: inline-block;">
                                            {task_count} task{"s" if task_count != 1 else ""} extracted
                                        </p>
        """
    
    content = f"""
                            <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%;">
                                <!-- Header accent -->
                                <tr>
                                    <td style="height: 4px; background: {HEADER_GRADIENT}; border-radius: 16px 16px 0 0;"></td>
                                </tr>
                                
                                <!-- Main content -->
                                <tr>
                                    <td style="padding: 40px 40px 32px;">
                                        <p style="margin: 0 0 8px; font-size: 12px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px;">
                                            Meeting Summary
                                        </p>
                                        <h1 style="margin: 0 0 8px; font-size: 22px; font-weight: 600; color: #1a1a2e; line-height: 1.3;">
                                            {meeting_title}
                                        </h1>
                                        <p style="margin: 0 0 28px; font-size: 14px; color: #9ca3af;">
                                            {meeting_date}
                                        </p>
                                        
                                        <p style="margin: 0 0 16px; font-size: 15px; font-weight: 600; color: #1a1a2e;">
                                            Key Points
                                        </p>
                                        
                                        <ul style="margin: 0 0 8px; padding: 0 0 0 20px;">
                                            {points_html}
                                        </ul>
                                        
                                        {task_badge}
                                    </td>
                                </tr>
                                
                                <!-- CTA Button -->
                                <tr>
                                    <td align="center" style="padding: 0 40px 40px;">
                                        <a href="{meeting_link}" style="display: inline-block; padding: 14px 32px; background: {HEADER_GRADIENT}; color: #ffffff; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px; letter-spacing: 0.2px;">
                                            View Full Meeting
                                        </a>
                                    </td>
                                </tr>
                            </table>
    """
    
    html = _get_email_wrapper(content, f"Summary of {meeting_title} - {len(summary_points)} key points")
    
    return subject, html, plain_text.strip()
