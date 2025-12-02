"""
Integration tests for database operations and models.
"""
import pytest
from datetime import datetime


@pytest.mark.integration
class TestUserDatabaseOperations:
    """Test User model database operations."""
    
    def test_create_user(self, db_session):
        """Test creating a user in the database."""
        from models import User
        from werkzeug.security import generate_password_hash
        
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=generate_password_hash('password123')
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
    
    def test_query_user_by_username(self, db_session, test_user):
        """Test querying user by username."""
        from models import User
        
        found_user = db_session.query(User).filter_by(username=test_user.username).first()
        assert found_user is not None
        assert found_user.id == test_user.id
    
    def test_query_user_by_email(self, db_session, test_user):
        """Test querying user by email."""
        from models import User
        
        found_user = db_session.query(User).filter_by(email=test_user.email).first()
        assert found_user is not None
        assert found_user.id == test_user.id
    
    def test_update_user(self, db_session, test_user):
        """Test updating user data."""
        test_user.email = 'newemail@example.com'
        db_session.commit()
        
        db_session.refresh(test_user)
        assert test_user.email == 'newemail@example.com'
    
    def test_delete_user(self, db_session):
        """Test deleting a user."""
        from models import User
        from werkzeug.security import generate_password_hash
        
        user = User(
            username='tempuser',
            email='temp@example.com',
            password_hash=generate_password_hash('password123')
        )
        db_session.add(user)
        db_session.commit()
        user_id = user.id
        
        db_session.delete(user)
        db_session.commit()
        
        from models import User
        deleted_user = db_session.query(User).filter_by(id=user_id).first()
        assert deleted_user is None


@pytest.mark.integration
class TestSessionDatabaseOperations:
    """Test Session model database operations."""
    
    def test_create_session(self, db_session, test_user):
        """Test creating a session."""
        try:
            from models import Session
            import uuid
            
            session = Session(
                external_id=str(uuid.uuid4())[:32],
                user_id=test_user.id,
                title='Test Session',
                status='active'
            )
            db_session.add(session)
            db_session.commit()
            
            assert session.id is not None
            assert session.user_id == test_user.id
        except ImportError:
            pytest.skip("Session model not implemented yet")
    
    def test_query_sessions_by_user(self, db_session, test_user):
        """Test querying sessions by user."""
        try:
            from models import Session
            
            sessions = db_session.query(Session).filter_by(user_id=test_user.id).all()
            assert isinstance(sessions, list)
        except ImportError:
            pytest.skip("Session model not implemented yet")
    
    def test_update_session_status(self, db_session, test_user):
        """Test updating session status."""
        try:
            from models import Session
            import uuid
            
            session = Session(
                external_id=str(uuid.uuid4())[:32],
                user_id=test_user.id,
                title='Test Session',
                status='active'
            )
            db_session.add(session)
            db_session.commit()
            
            session.status = 'completed'
            db_session.commit()
            
            db_session.refresh(session)
            assert session.status == 'completed'
        except ImportError:
            pytest.skip("Session model not implemented yet")


@pytest.mark.integration
class TestDatabaseRelationships:
    """Test database relationships between models."""
    
    def test_user_sessions_relationship(self, db_session, test_user):
        """Test user to sessions relationship."""
        try:
            from models import Session
            import uuid
            
            session1 = Session(external_id=str(uuid.uuid4())[:32], user_id=test_user.id, title='Session 1', status='active')
            session2 = Session(external_id=str(uuid.uuid4())[:32], user_id=test_user.id, title='Session 2', status='active')
            db_session.add(session1)
            db_session.add(session2)
            db_session.commit()
            
            db_session.refresh(test_user)
            if hasattr(test_user, 'sessions'):
                assert len(test_user.sessions) >= 2
        except ImportError:
            pytest.skip("Session model or relationship not implemented yet")


@pytest.mark.integration
class TestDatabaseTransactions:
    """Test database transaction handling."""
    
    def test_transaction_commit(self, db_session):
        """Test successful transaction commit."""
        from models import User
        from werkzeug.security import generate_password_hash
        
        user = User(
            username='txuser',
            email='tx@example.com',
            password_hash=generate_password_hash('password123')
        )
        db_session.add(user)
        db_session.commit()
        
        from models import User
        found = db_session.query(User).filter_by(username='txuser').first()
        assert found is not None
    
    def test_transaction_rollback(self, db_session):
        """Test transaction rollback on error."""
        from models import User
        from werkzeug.security import generate_password_hash
        
        user1 = User(
            username='rollback1',
            email='rollback1@example.com',
            password_hash=generate_password_hash('password123')
        )
        db_session.add(user1)
        
        try:
            user2 = User(
                username='rollback1',
                email='rollback2@example.com',
                password_hash=generate_password_hash('password123')
            )
            db_session.add(user2)
            db_session.commit()
        except Exception:
            db_session.rollback()
        
        from models import User
        users = db_session.query(User).filter_by(username='rollback1').all()
        assert len(users) <= 1
