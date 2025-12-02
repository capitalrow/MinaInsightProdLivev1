"""
Google OAuth Authentication Blueprint for Mina
Enables users to sign in with their Google account.

Integration: flask_google_oauth
"""

import json
import os
import logging

import requests
from flask import Blueprint, redirect, request, url_for, flash
from flask_login import login_user
from oauthlib.oauth2 import WebApplicationClient

from models import db, User, Workspace

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

google_auth_bp = Blueprint("google_auth", __name__)

def get_redirect_url():
    """Get the appropriate redirect URL for the current environment."""
    if os.environ.get("REPLIT_DEV_DOMAIN"):
        return f'https://{os.environ["REPLIT_DEV_DOMAIN"]}/google_login/callback'
    elif os.environ.get("REPLIT_DEPLOYMENT"):
        return f'https://{os.environ.get("REPLIT_DEPLOYMENT_URL", "")}/google_login/callback'
    else:
        return request.base_url.replace("http://", "https://") + "/callback"

def is_google_oauth_configured():
    """Check if Google OAuth credentials are configured."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

if is_google_oauth_configured():
    client = WebApplicationClient(GOOGLE_CLIENT_ID)
    
    dev_domain = os.environ.get("REPLIT_DEV_DOMAIN", "your-repl.replit.dev")
    logger.info(f"""
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Google OAuth Configuration
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Add this redirect URI to your Google Cloud Console:
    https://{dev_domain}/google_login/callback
    
    Instructions:
    1. Go to https://console.cloud.google.com/apis/credentials
    2. Select or create your OAuth 2.0 Client ID
    3. Add the above URL to "Authorized redirect URIs"
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)
else:
    client = None
    logger.warning("Google OAuth not configured - GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are required")


@google_auth_bp.route("/google_login")
def google_login():
    """Initiate Google OAuth login flow."""
    if not is_google_oauth_configured():
        flash("Google Sign-In is not configured. Please use email/password login.", "error")
        return redirect(url_for("auth.login"))
    
    try:
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL, timeout=10).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=request.base_url.replace("http://", "https://") + "/callback",
            scope=["openid", "email", "profile"],
        )
        return redirect(request_uri)
    except Exception as e:
        logger.error(f"Google OAuth initialization failed: {e}")
        flash("Unable to connect to Google. Please try again later.", "error")
        return redirect(url_for("auth.login"))


@google_auth_bp.route("/google_login/callback")
def google_callback():
    """Handle Google OAuth callback."""
    if not is_google_oauth_configured():
        flash("Google Sign-In is not configured.", "error")
        return redirect(url_for("auth.login"))
    
    code = request.args.get("code")
    if not code:
        flash("Google authentication failed. Please try again.", "error")
        return redirect(url_for("auth.login"))
    
    try:
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL, timeout=10).json()
        token_endpoint = google_provider_cfg["token_endpoint"]

        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url.replace("http://", "https://"),
            redirect_url=request.base_url.replace("http://", "https://"),
            code=code,
        )
        
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
            timeout=10
        )

        client.parse_request_body_response(json.dumps(token_response.json()))

        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body, timeout=10)

        userinfo = userinfo_response.json()
        
        if not userinfo.get("email_verified"):
            flash("Your Google email is not verified. Please verify it first.", "error")
            return redirect(url_for("auth.login"))

        users_email = userinfo["email"].lower()
        users_name = userinfo.get("given_name", userinfo.get("name", "User"))
        users_full_name = userinfo.get("name", users_name)
        users_picture = userinfo.get("picture", "")

        user = db.session.query(User).filter_by(email=users_email).first()
        
        if not user:
            username = _generate_unique_username(users_name, users_email)
            
            user = User(
                username=username,
                email=users_email,
                first_name=userinfo.get("given_name", ""),
                last_name=userinfo.get("family_name", ""),
                avatar_url=users_picture,
                is_verified=True
            )
            user.set_password(os.urandom(32).hex())
            
            db.session.add(user)
            db.session.flush()
            
            workspace_name = f"{users_name}'s Workspace"
            workspace = Workspace(
                name=workspace_name,
                slug=Workspace.generate_slug(workspace_name),
                owner_id=user.id
            )
            db.session.add(workspace)
            db.session.flush()
            
            user.workspace_id = workspace.id
            db.session.commit()
            
            logger.info(f"New user created via Google OAuth: {users_email}")
            flash(f"Welcome to Mina, {users_name}! Your account has been created.", "success")
        else:
            if users_picture and not user.avatar_url:
                user.avatar_url = users_picture
            if not user.is_verified:
                user.is_verified = True
            user.update_last_login()
            db.session.commit()
            logger.info(f"User logged in via Google OAuth: {users_email}")

        login_user(user)
        return redirect(url_for("dashboard.index"))

    except Exception as e:
        logger.error(f"Google OAuth callback failed: {e}")
        db.session.rollback()
        flash("Google authentication failed. Please try again.", "error")
        return redirect(url_for("auth.login"))


def _generate_unique_username(name: str, email: str) -> str:
    """Generate a unique username from name or email."""
    import re
    
    base_username = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
    if len(base_username) < 3:
        base_username = email.split('@')[0]
        base_username = re.sub(r'[^a-zA-Z0-9]', '', base_username.lower())
    
    username = base_username[:20]
    counter = 1
    
    while db.session.query(User).filter_by(username=username).first():
        username = f"{base_username[:17]}{counter}"
        counter += 1
        if counter > 999:
            username = f"{base_username[:10]}{os.urandom(4).hex()}"
            break
    
    return username
