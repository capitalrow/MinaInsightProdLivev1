"""
Onboarding Routes for Mina
Multi-step wizard to help new users set up their workspace.
Industry-standard onboarding flow similar to Linear, Notion, and Slack.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, User, Workspace
from services.auth_email_service import auth_email_service
import json
import logging

logger = logging.getLogger(__name__)

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')


def get_user_preferences():
    """Get user preferences as dict."""
    if current_user.preferences:
        try:
            return json.loads(current_user.preferences)
        except json.JSONDecodeError:
            return {}
    return {}


def save_user_preferences(prefs):
    """Save user preferences."""
    current_prefs = get_user_preferences()
    current_prefs.update(prefs)
    current_user.preferences = json.dumps(current_prefs)


@onboarding_bp.route('/')
@login_required
def index():
    """Redirect to appropriate onboarding step."""
    if current_user.onboarding_completed:
        return redirect(url_for('dashboard.index'))
    
    step = current_user.onboarding_step or 1
    return redirect(url_for(f'onboarding.step_{step}'))


@onboarding_bp.route('/step/1', methods=['GET', 'POST'])
@login_required
def step_1():
    """Step 1: Welcome & Workspace Setup."""
    if current_user.onboarding_completed:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        workspace_name = request.form.get('workspace_name', '').strip()
        role = request.form.get('role', '').strip()
        team_size = request.form.get('team_size', '').strip()
        
        if not workspace_name:
            workspace_name = f"{current_user.username}'s Workspace"
        
        try:
            base_slug = Workspace.generate_slug(workspace_name)
            
            if current_user.workspace:
                current_user.workspace.name = workspace_name
                new_slug = base_slug
                existing = Workspace.query.filter(
                    Workspace.slug == new_slug,
                    Workspace.id != current_user.workspace.id
                ).first()
                if existing:
                    import secrets
                    new_slug = f"{base_slug}-{secrets.token_hex(4)}"
                current_user.workspace.slug = new_slug
            else:
                slug = base_slug
                existing = Workspace.query.filter_by(slug=slug).first()
                if existing:
                    import secrets
                    slug = f"{slug}-{secrets.token_hex(4)}"
                
                workspace = Workspace(
                    name=workspace_name,
                    slug=slug,
                    owner_id=current_user.id,
                    plan='free',
                    max_users=5
                )
                db.session.add(workspace)
                db.session.flush()
                
                current_user.workspace_id = workspace.id
            
            prefs = get_user_preferences()
            prefs['role'] = role
            prefs['team_size'] = team_size
            save_user_preferences(prefs)
            
            current_user.onboarding_step = 2
            db.session.commit()
            
            return redirect(url_for('onboarding.step_2'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Onboarding step 1 error: {e}")
            flash('Something went wrong. Please try again.', 'error')
    
    return render_template('onboarding/step_1.html', step=1, total_steps=4)


@onboarding_bp.route('/step/2', methods=['GET', 'POST'])
@login_required
def step_2():
    """Step 2: Invite Team Members."""
    if current_user.onboarding_completed:
        return redirect(url_for('dashboard.index'))
    
    if not current_user.workspace:
        flash('Please set up your workspace first.', 'warning')
        return redirect(url_for('onboarding.step_1'))
    
    if request.method == 'POST':
        emails = request.form.getlist('invite_emails[]')
        emails = [e.strip().lower() for e in emails if e.strip()]
        
        unique_emails = list(dict.fromkeys(emails))
        unique_emails = [e for e in unique_emails if e != current_user.email]
        
        invites_sent = 0
        failed_emails = []
        
        for email in unique_emails[:5]:
            try:
                from services.team_invite_service import create_and_send_invite
                result = create_and_send_invite(
                    inviter=current_user,
                    invitee_email=email,
                    workspace=current_user.workspace
                )
                if result.get('success'):
                    invites_sent += 1
                else:
                    failed_emails.append(email)
                    logger.warning(f"Invite failed for {email}: {result.get('error')}")
            except Exception as e:
                failed_emails.append(email)
                logger.warning(f"Failed to send invite to {email}: {e}")
        
        if invites_sent > 0:
            flash(f'Sent {invites_sent} invitation(s) to your team!', 'success')
        
        if failed_emails:
            logger.info(f"Some invites failed: {failed_emails}")
        
        current_user.onboarding_step = 3
        db.session.commit()
        
        return redirect(url_for('onboarding.step_3'))
    
    return render_template('onboarding/step_2.html', step=2, total_steps=4)


@onboarding_bp.route('/step/3', methods=['GET', 'POST'])
@login_required
def step_3():
    """Step 3: Preferences & Notifications."""
    if current_user.onboarding_completed:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        prefs = get_user_preferences()
        
        prefs['notifications'] = {
            'email_notifications': request.form.get('email_notifications') == 'on',
            'meeting_reminders': request.form.get('meeting_reminders') == 'on',
            'task_updates': request.form.get('task_updates') == 'on',
            'weekly_digest': request.form.get('weekly_digest') == 'on',
            'ai_insights': request.form.get('ai_insights') == 'on'
        }
        
        timezone = request.form.get('timezone', 'UTC')
        current_user.timezone = timezone
        
        save_user_preferences(prefs)
        current_user.onboarding_step = 4
        db.session.commit()
        
        return redirect(url_for('onboarding.step_4'))
    
    return render_template('onboarding/step_3.html', step=3, total_steps=4)


@onboarding_bp.route('/step/4', methods=['GET', 'POST'])
@login_required
def step_4():
    """Step 4: Get Started - Quick Actions."""
    if current_user.onboarding_completed:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        current_user.onboarding_completed = True
        current_user.onboarding_step = 5
        db.session.commit()
        
        flash('You\'re all set! Welcome to Mina.', 'success')
        
        next_action = request.form.get('next_action', 'dashboard')
        if next_action == 'start_meeting':
            return redirect(url_for('session.new'))
        elif next_action == 'explore_tasks':
            return redirect(url_for('tasks.index'))
        else:
            return redirect(url_for('dashboard.index'))
    
    return render_template('onboarding/step_4.html', step=4, total_steps=4)


@onboarding_bp.route('/skip', methods=['POST'])
@login_required
def skip():
    """Skip onboarding and go directly to dashboard."""
    current_user.onboarding_completed = True
    current_user.onboarding_step = 5
    db.session.commit()
    
    flash('You can always update your settings later.', 'info')
    return redirect(url_for('dashboard.index'))


@onboarding_bp.route('/back/<int:step>')
@login_required
def go_back(step):
    """Go back to a previous step."""
    if step >= 1 and step <= 4:
        current_user.onboarding_step = step
        db.session.commit()
        return redirect(url_for(f'onboarding.step_{step}'))
    return redirect(url_for('onboarding.index'))
