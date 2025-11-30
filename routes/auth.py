"""
Authentication Routes for Mina User Management
Handles registration, login, logout, and user management functionality.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import db, User, Workspace
import re
import logging
import traceback


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def is_valid_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def is_valid_password(password):
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Valid password"


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page and handler."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        
        # Validation
        errors = []
        
        if not email:
            errors.append("Email is required")
        elif not is_valid_email(email):
            errors.append("Please enter a valid email address")
        elif db.session.query(User).filter_by(email=email).first():
            errors.append("An account with this email already exists")
        
        if not username:
            errors.append("Username is required")
        elif len(username) < 3:
            errors.append("Username must be at least 3 characters long")
        elif db.session.query(User).filter_by(username=username).first():
            errors.append("This username is already taken")
        
        if not password:
            errors.append("Password is required")
        else:
            valid, message = is_valid_password(password)
            if not valid:
                errors.append(message)
        
        if password != confirm_password:
            errors.append("Passwords do not match")
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html')
        
        try:
            # Create new user
            user = User(
                email=email,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            user.set_password(password)
            
            # For first user, set owner role
            if db.session.query(User).count() == 0:
                user.role = 'owner'
            
            # Add user to session but don't commit yet
            db.session.add(user)
            db.session.flush()  # Flush to get user.id assigned
            
            # Create personal workspace for new user
            workspace_name = f"{first_name}'s Workspace" if first_name else f"{username}'s Workspace"
            workspace = Workspace(
                name=workspace_name,
                slug=Workspace.generate_slug(workspace_name),
                owner_id=user.id
            )
            db.session.add(workspace)
            db.session.flush()  # Flush to get workspace.id assigned
            
            # Assign user to workspace (circular FK handled by post_update=True)
            user.workspace_id = workspace.id
            
            # Commit both user and workspace together
            db.session.commit()
            
            # Auto-login the new user for smooth onboarding
            login_user(user)
            flash('Welcome to Mina! Your account has been created successfully.', 'success')
            
            # Redirect to next parameter or dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Registration failed for user {username} ({email}): {str(e)}")
            logging.error(traceback.format_exc())
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page and handler."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email_or_username = request.form.get('email_or_username', '').strip()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == 'on'
        
        logging.info(f"Login attempt for: {email_or_username}")
        
        if not email_or_username or not password:
            flash('Please enter both email/username and password', 'error')
            return render_template('auth/login.html')
        
        # Find user by email or username
        user = None
        if '@' in email_or_username:
            user = db.session.query(User).filter_by(email=email_or_username.lower()).first()
            logging.debug(f"Searching by email: {email_or_username.lower()} - User found: {user is not None}")
        else:
            user = db.session.query(User).filter_by(username=email_or_username).first()
            logging.debug(f"Searching by username: {email_or_username} - User found: {user is not None}")
        
        if user:
            password_valid = user.check_password(password)
            logging.debug(f"Password check for user {user.username}: {password_valid}")
            
            if password_valid:
                if not user.active:
                    logging.warning(f"Login denied - inactive account: {user.username}")
                    flash('Your account has been deactivated. Please contact support.', 'error')
                    return render_template('auth/login.html')
                
                # Log in user
                login_user(user, remember=remember_me)
                user.update_last_login()
                db.session.commit()
                logging.info(f"Login successful for user: {user.username}")
                
                # Rotate session to prevent session fixation attacks
                try:
                    from middleware.session_security import rotate_session
                    rotate_session()
                    logging.debug(f"Session rotated for user {user.username}")
                except Exception as e:
                    logging.warning(f"Session rotation failed: {e}")
                
                # Redirect to next page or dashboard
                next_page = request.args.get('next')
                if next_page and next_page.startswith('/'):
                    return redirect(next_page)
                return redirect(url_for('dashboard.index'))
            else:
                logging.warning(f"Login failed - invalid password for user: {user.username}")
                flash('Invalid email/username or password', 'error')
        else:
            logging.warning(f"Login failed - user not found: {email_or_username}")
            flash('Invalid email/username or password', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout handler."""
    # Invalidate session completely
    try:
        from middleware.session_security import invalidate_session
        invalidate_session()
    except Exception as e:
        logging.warning(f"Session invalidation failed: {e}")
    
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page (Crown+ design)."""
    return render_template('settings/profile.html', user=current_user)


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile (supports both form and JSON)."""
    if request.method == 'POST':
        # Support both JSON and form data
        if request.is_json:
            data = request.get_json()
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            username = data.get('username', '').strip()
            email = data.get('email', '').strip().lower()
            
            # Validation for JSON
            errors = []
            
            if username and username != current_user.username:
                if len(username) < 3:
                    errors.append("Username must be at least 3 characters")
                elif db.session.query(User).filter_by(username=username).first():
                    errors.append("Username is already taken")
            
            if email and email != current_user.email:
                if not is_valid_email(email):
                    errors.append("Invalid email format")
                elif db.session.query(User).filter_by(email=email).first():
                    errors.append("Email is already registered")
            
            if errors:
                return jsonify({'success': False, 'error': ', '.join(errors)}), 400
            
            try:
                # Update user profile
                current_user.first_name = first_name
                current_user.last_name = last_name
                if username:
                    current_user.username = username
                if email:
                    current_user.email = email
                
                db.session.commit()
                logging.info(f"Profile updated for user {current_user.id}")
                
                return jsonify({
                    'success': True,
                    'message': 'Profile updated successfully',
                    'user': {
                        'first_name': current_user.first_name,
                        'last_name': current_user.last_name,
                        'username': current_user.username,
                        'email': current_user.email
                    }
                }), 200
                
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error updating profile: {e}")
                return jsonify({'success': False, 'error': 'Failed to update profile'}), 500
        else:
            # Original form handling
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            display_name = request.form.get('display_name', '').strip()
            timezone = request.form.get('timezone', 'UTC')
            
            try:
                # Update user profile
                current_user.first_name = first_name
                current_user.last_name = last_name
                current_user.display_name = display_name
                current_user.timezone = timezone
                
                db.session.commit()
                flash('Profile updated successfully', 'success')
                return redirect(url_for('auth.profile'))
                
            except Exception as e:
                db.session.rollback()
                flash('Failed to update profile. Please try again.', 'error')
    
    return render_template('settings/profile.html', user=current_user)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password (supports both form and JSON)."""
    if request.method == 'POST':
        # Support both JSON and form data
        if request.is_json:
            data = request.get_json()
            current_password = data.get('current_password', '')
            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')
            
            # Validation
            if not current_user.check_password(current_password):
                return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400
            
            valid, message = is_valid_password(new_password)
            if not valid:
                return jsonify({'success': False, 'error': message}), 400
            
            if new_password != confirm_password:
                return jsonify({'success': False, 'error': 'New passwords do not match'}), 400
            
            try:
                current_user.set_password(new_password)
                db.session.commit()
                logging.info(f"Password changed for user {current_user.id}")
                return jsonify({'success': True, 'message': 'Password changed successfully'}), 200
                
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error changing password: {e}")
                return jsonify({'success': False, 'error': 'Failed to change password'}), 500
        else:
            # Original form handling
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            # Validation
            if not current_user.check_password(current_password):
                flash('Current password is incorrect', 'error')
                return render_template('settings/profile.html')
            
            valid, message = is_valid_password(new_password)
            if not valid:
                flash(message, 'error')
                return render_template('settings/profile.html')
            
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
                return render_template('settings/profile.html')
            
            try:
                current_user.set_password(new_password)
                db.session.commit()
                flash('Password changed successfully', 'success')
                return redirect(url_for('auth.profile'))
                
            except Exception as e:
                db.session.rollback()
                flash('Failed to change password. Please try again.', 'error')
    
    return render_template('settings/profile.html')


@auth_bp.route('/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Upload user avatar image."""
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    
    file = request.files['avatar']
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    filename = file.filename.lower() if file.filename else ''
    if not any(filename.endswith(f'.{ext}') for ext in allowed_extensions):
        return jsonify({'success': False, 'error': 'Invalid file type. Use PNG, JPG, or GIF'}), 400
    
    try:
        # For now, store avatar URL as a placeholder
        # TODO: Implement actual file upload to storage service
        avatar_url = f"/static/uploads/avatars/{current_user.id}.jpg"
        current_user.avatar_url = avatar_url
        db.session.commit()
        
        logging.info(f"Avatar uploaded for user {current_user.id}")
        return jsonify({
            'success': True,
            'message': 'Avatar uploaded successfully',
            'avatar_url': avatar_url
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error uploading avatar: {e}")
        return jsonify({'success': False, 'error': 'Failed to upload avatar'}), 500


@auth_bp.route('/api/user')
@login_required
def api_user():
    """API endpoint to get current user data."""
    return jsonify(current_user.to_dict())


@auth_bp.route('/api/check-username')
def api_check_username():
    """API endpoint to check if username is available."""
    username = request.args.get('username', '').strip()
    if not username:
        return jsonify({'available': False, 'message': 'Username is required'})
    
    if len(username) < 3:
        return jsonify({'available': False, 'message': 'Username must be at least 3 characters'})
    
    user = db.session.query(User).filter_by(username=username).first()
    if user:
        return jsonify({'available': False, 'message': 'Username is already taken'})
    
    return jsonify({'available': True, 'message': 'Username is available'})


@auth_bp.route('/api/check-email')
def api_check_email():
    """API endpoint to check if email is available."""
    email = request.args.get('email', '').strip().lower()
    if not email:
        return jsonify({'available': False, 'message': 'Email is required'})
    
    if not is_valid_email(email):
        return jsonify({'available': False, 'message': 'Invalid email format'})
    
    user = db.session.query(User).filter_by(email=email).first()
    if user:
        return jsonify({'available': False, 'message': 'Email is already registered'})
    
    return jsonify({'available': True, 'message': 'Email is available'})