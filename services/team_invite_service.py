"""
Team Invite Service for Mina
Handles sending team invitations via email using SendGrid.
Persists invitations to database for proper token validation.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from services.email_service import email_service
from models import db, TeamInvite, User, Workspace

logger = logging.getLogger(__name__)


def create_and_send_invite(
    inviter: User, 
    invitee_email: str, 
    workspace: Workspace,
    custom_message: str = None,
    role: str = "member"
) -> Dict:
    """
    Create a team invitation record and send email.
    
    Args:
        inviter: User sending the invite
        invitee_email: Email of person to invite
        workspace: Workspace to invite them to
        custom_message: Optional custom message from inviter
        role: Role to assign when invite is accepted
    
    Returns:
        Dict with success status, message, and invite details
    """
    if not workspace:
        logger.error("Cannot send invite - no workspace provided")
        return {'success': False, 'error': 'No workspace specified'}
    
    invitee_email = invitee_email.strip().lower()
    
    if not _is_valid_email(invitee_email):
        return {'success': False, 'error': 'Invalid email address'}
    
    existing_user = User.query.filter_by(email=invitee_email).first()
    if existing_user and existing_user.workspace_id == workspace.id:
        return {'success': False, 'error': 'User is already a member of this workspace'}
    
    existing_invite = TeamInvite.query.filter_by(
        email=invitee_email,
        workspace_id=workspace.id,
        status='pending'
    ).first()
    
    if existing_invite:
        if existing_invite.is_valid:
            existing_invite.resend()
            db.session.commit()
            
            send_result = _send_invite_email(
                invite=existing_invite,
                inviter=inviter,
                workspace=workspace,
                custom_message=custom_message
            )
            
            if send_result['success']:
                return {'success': True, 'message': 'Invitation resent', 'invite_id': existing_invite.id}
            return send_result
        else:
            existing_invite.expire()
    
    try:
        invite = TeamInvite(
            token=TeamInvite.generate_token(),
            email=invitee_email,
            inviter_id=inviter.id,
            workspace_id=workspace.id,
            role=role,
            status='pending',
            expires_at=TeamInvite.get_default_expiry()
        )
        db.session.add(invite)
        db.session.commit()
        
        send_result = _send_invite_email(
            invite=invite,
            inviter=inviter,
            workspace=workspace,
            custom_message=custom_message
        )
        
        if not send_result['success']:
            invite.status = 'email_failed'
            db.session.commit()
            return send_result
        
        logger.info(f"Team invite created and sent: {inviter.email} -> {invitee_email} for workspace {workspace.slug}")
        return {
            'success': True, 
            'message': 'Invitation sent successfully',
            'invite_id': invite.id
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create team invite: {e}")
        return {'success': False, 'error': 'Failed to create invitation'}


def accept_invite(token: str, user: User) -> Dict:
    """
    Accept a team invitation and add user to workspace.
    
    Args:
        token: The invite token from the registration URL
        user: The user accepting the invitation
    
    Returns:
        Dict with success status and workspace details
    """
    invite = TeamInvite.query.filter_by(token=token).first()
    
    if not invite:
        return {'success': False, 'error': 'Invalid invitation'}
    
    if invite.is_expired:
        invite.status = 'expired'
        db.session.commit()
        return {'success': False, 'error': 'Invitation has expired'}
    
    if invite.status != 'pending':
        return {'success': False, 'error': f'Invitation has already been {invite.status}'}
    
    if invite.email.lower() != user.email.lower():
        return {'success': False, 'error': 'This invitation was sent to a different email address'}
    
    try:
        invite.accept(user)
        
        user.role = invite.role
        
        db.session.commit()
        
        logger.info(f"Invite accepted: {user.email} joined workspace {invite.workspace_id}")
        return {
            'success': True,
            'message': 'Welcome to the team!',
            'workspace': invite.workspace.to_dict() if invite.workspace else None
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to accept invite: {e}")
        return {'success': False, 'error': 'Failed to join workspace'}


def validate_invite_token(token: str) -> Dict:
    """
    Validate an invite token without accepting it.
    Used during registration to pre-fill workspace info.
    
    Args:
        token: The invite token to validate
    
    Returns:
        Dict with validity status and invite details
    """
    invite = TeamInvite.query.filter_by(token=token).first()
    
    if not invite:
        return {'valid': False, 'error': 'Invalid invitation'}
    
    if invite.is_expired:
        return {'valid': False, 'error': 'Invitation has expired'}
    
    if invite.status != 'pending':
        return {'valid': False, 'error': f'Invitation has already been {invite.status}'}
    
    return {
        'valid': True,
        'email': invite.email,
        'workspace_name': invite.workspace.name if invite.workspace else None,
        'inviter_name': invite.inviter.full_name if invite.inviter else None,
        'role': invite.role
    }


def get_pending_invites_for_workspace(workspace_id: int) -> List[Dict]:
    """Get all pending invites for a workspace."""
    invites = TeamInvite.query.filter_by(
        workspace_id=workspace_id,
        status='pending'
    ).all()
    
    return [invite.to_dict() for invite in invites if invite.is_valid]


def cancel_invite(invite_id: int, user: User) -> Dict:
    """Cancel a pending invitation."""
    invite = TeamInvite.query.get(invite_id)
    
    if not invite:
        return {'success': False, 'error': 'Invitation not found'}
    
    if invite.inviter_id != user.id and user.role not in ['admin', 'owner']:
        return {'success': False, 'error': 'Not authorized to cancel this invitation'}
    
    invite.status = 'cancelled'
    db.session.commit()
    
    return {'success': True, 'message': 'Invitation cancelled'}


def _is_valid_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _send_invite_email(
    invite: TeamInvite,
    inviter: User,
    workspace: Workspace,
    custom_message: str = None
) -> Dict:
    """Send the invitation email."""
    if not email_service.is_available():
        logger.warning("Email service not available - team invite not sent")
        return {'success': False, 'error': 'Email service not configured'}
    
    try:
        inviter_name = inviter.full_name or inviter.username
        workspace_name = workspace.name if workspace else "Mina"
        
        base_url = os.environ.get('REPLIT_DEV_DOMAIN', 'teammina.com')
        if base_url.startswith('http'):
            invite_url = f"{base_url}/auth/register?invite={invite.token}"
        else:
            invite_url = f"https://{base_url}/auth/register?invite={invite.token}"
        
        subject = f"{inviter_name} invited you to join {workspace_name} on Mina"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
            <div style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); padding: 40px 20px; border-radius: 16px 16px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 28px;">You're Invited!</h1>
            </div>
            
            <div style="background: white; padding: 32px; border-radius: 0 0 16px 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                <p style="font-size: 18px; color: #1f2937; margin-bottom: 16px;">Hi there,</p>
                
                <p style="color: #4b5563; margin-bottom: 24px;">
                    <strong>{inviter_name}</strong> has invited you to join <strong>{workspace_name}</strong> on Mina - 
                    the AI-powered meeting assistant that transforms your meetings into actionable moments.
                </p>
                
                {f'<div style="background: #f3f4f6; padding: 16px; border-radius: 8px; margin-bottom: 24px; border-left: 4px solid #6366f1;"><p style="margin: 0; color: #4b5563; font-style: italic;">"{custom_message}"</p></div>' if custom_message else ''}
                
                <div style="text-align: center; margin: 32px 0;">
                    <a href="{invite_url}" 
                       style="display: inline-block; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                        Accept Invitation
                    </a>
                </div>
                
                <div style="background: #f9fafb; padding: 20px; border-radius: 8px; margin-top: 24px;">
                    <h3 style="margin: 0 0 12px 0; color: #1f2937; font-size: 14px;">What you'll get with Mina:</h3>
                    <ul style="margin: 0; padding-left: 20px; color: #4b5563; font-size: 14px;">
                        <li>Real-time meeting transcription with speaker identification</li>
                        <li>AI-powered summaries and action item extraction</li>
                        <li>Searchable meeting archive</li>
                        <li>Task tracking and follow-up management</li>
                    </ul>
                </div>
                
                <p style="margin-top: 24px; font-size: 13px; color: #6b7280;">
                    This invitation expires in 7 days. If you don't know {inviter_name}, you can safely ignore this email.
                </p>
            </div>
            
            <p style="text-align: center; margin-top: 20px; font-size: 12px; color: #9ca3af;">
                Mina - Transform meetings into actionable moments
            </p>
        </body>
        </html>
        """
        
        plain_text = f"""You're Invited to {workspace_name} on Mina!

Hi there,

{inviter_name} has invited you to join {workspace_name} on Mina - the AI-powered meeting assistant that transforms your meetings into actionable moments.

{f'Message from {inviter_name}: "{custom_message}"' if custom_message else ''}

Accept the invitation: {invite_url}

What you'll get with Mina:
- Real-time meeting transcription with speaker identification
- AI-powered summaries and action item extraction
- Searchable meeting archive
- Task tracking and follow-up management

This invitation expires in 7 days. If you don't know {inviter_name}, you can safely ignore this email.

---
Mina - Transform meetings into actionable moments
"""
        
        result = email_service.send_email(
            to_email=invite.email,
            subject=subject,
            html_content=html_content,
            plain_text=plain_text
        )
        
        if result.get('success'):
            logger.info(f"Team invite email sent to {invite.email}")
            return {'success': True, 'message': 'Email sent'}
        else:
            return {'success': False, 'error': result.get('error', 'Failed to send email')}
            
    except Exception as e:
        logger.error(f"Failed to send team invite email: {e}")
        return {'success': False, 'error': str(e)}


def send_team_invite(inviter, invitee_email: str, workspace, custom_message: str = None) -> Dict:
    """
    Legacy function for backwards compatibility.
    Use create_and_send_invite for new code.
    """
    return create_and_send_invite(inviter, invitee_email, workspace, custom_message)
