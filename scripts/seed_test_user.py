#!/usr/bin/env python3
"""
Seed test user for CROWN⁴.5 automated testing
Creates a test user that can be used for E2E and integration tests
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, Workspace
from werkzeug.security import generate_password_hash
from sqlalchemy import select

def seed_test_user():
    """Create test user and workspace for automated testing"""
    app = create_app()
    
    with app.app_context():
        # Check if test user already exists
        existing_user = db.session.execute(
            select(User).where(User.email == 'test@mina.ai')
        ).scalar_one_or_none()
        
        if existing_user:
            print(f"✅ Test user already exists (ID: {existing_user.id})")
            print(f"   Email: {existing_user.email}")
            print(f"   Username: {existing_user.username}")
            return existing_user
        
        # Create test user first (without workspace)
        test_user = User(
            email='test@mina.ai',
            username='testuser',
            password_hash=generate_password_hash('TestPassword123!'),
            first_name='Test',
            last_name='User',
            display_name='Test User',
            active=True,
            is_verified=True,
            role='admin'
        )
        
        db.session.add(test_user)
        db.session.flush()  # Get user ID
        
        # Create test workspace with user as owner
        workspace = Workspace(
            name='Test Workspace',
            slug='test-workspace',
            owner_id=test_user.id
        )
        db.session.add(workspace)
        db.session.flush()  # Get workspace ID
        
        # Update user with workspace
        test_user.workspace_id = workspace.id
        
        db.session.add(test_user)
        db.session.commit()
        
        print("✅ Test user created successfully!")
        print(f"   ID: {test_user.id}")
        print(f"   Email: {test_user.email}")
        print(f"   Username: {test_user.username}")
        print(f"   Password: TestPassword123!")
        print(f"   Workspace: {workspace.name} (ID: {workspace.id})")
        
        return test_user

if __name__ == '__main__':
    try:
        seed_test_user()
    except Exception as e:
        print(f"❌ Error seeding test user: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
