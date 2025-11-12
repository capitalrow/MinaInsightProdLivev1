"""
Authentication and authorization utilities.

Provides decorators and helpers for protecting routes with role-based access control.
"""

from functools import wraps
from flask import jsonify
from flask_login import login_required, current_user


def admin_required(f):
    """
    Decorator to protect routes requiring admin privileges.
    
    Ensures:
    1. User is authenticated (via login_required)
    2. User is active
    3. User has admin or owner role
    
    Returns 403 Forbidden if user doesn't have admin privileges.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # Check if user is active
        if not current_user.active:
            return jsonify({
                'success': False,
                'message': 'Account is inactive'
            }), 403
        
        # Check if user has admin privileges
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'Admin privileges required'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function
