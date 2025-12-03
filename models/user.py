"""
User Model for Mina Authentication System
SQLAlchemy 2.0-safe model for user management with workspace support.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Boolean, Text, func, ForeignKey
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .base import Base

# Forward reference for type checking
if TYPE_CHECKING:
    from .workspace import Workspace
    from .meeting import Meeting
    from .task import Task, TaskAssignee
    from .marker import Marker
    from .comment import Comment
    from .session import Session
    from .copilot_template import CopilotTemplate
    from .copilot_conversation import CopilotConversation
    from .task_view_state import TaskViewState
    from .task_counters import TaskCounters


class User(UserMixin, Base):
    """
    User model for authentication and profile management.
    Integrates with Flask-Login for session management.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    
    # Profile information
    first_name: Mapped[Optional[str]] = mapped_column(String(64))
    last_name: Mapped[Optional[str]] = mapped_column(String(64))
    display_name: Mapped[Optional[str]] = mapped_column(String(128))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(256))
    
    # Account settings
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(String(32), default="user")  # user, admin, owner
    timezone: Mapped[Optional[str]] = mapped_column(String(64), default="UTC")
    
    # Email verification & password reset tokens
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    email_verification_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Workspace relationship
    workspace_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    workspace: Mapped[Optional["Workspace"]] = relationship(back_populates="members", foreign_keys=[workspace_id])
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Preferences
    preferences: Mapped[Optional[str]] = mapped_column(Text)  # JSON string for user preferences
    
    # Onboarding tracking
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_step: Mapped[int] = mapped_column(Integer, default=0)  # 0=not started, 1-4=steps, 5=complete
    
    # Relationships
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", foreign_keys="Session.user_id")
    meetings: Mapped[list["Meeting"]] = relationship(back_populates="organizer", foreign_keys="Meeting.organizer_id")
    assigned_tasks: Mapped[list["Task"]] = relationship(back_populates="assigned_to", foreign_keys="Task.assigned_to_id")
    # CROWN⁴.5: Many-to-many tasks assigned (multi-assignee support)
    tasks_assigned_multi: Mapped[list["Task"]] = relationship(
        secondary="task_assignees",
        primaryjoin="User.id==foreign(TaskAssignee.user_id)",
        secondaryjoin="Task.id==foreign(TaskAssignee.task_id)",
        back_populates="assignees",
        viewonly=True  # Prevent circular updates
    )
    markers: Mapped[list["Marker"]] = relationship(back_populates="user")
    comments: Mapped[list["Comment"]] = relationship(back_populates="user")
    copilot_templates: Mapped[list["CopilotTemplate"]] = relationship(back_populates="user", foreign_keys="CopilotTemplate.user_id")
    copilot_conversations: Mapped[list["CopilotConversation"]] = relationship(back_populates="user", foreign_keys="CopilotConversation.user_id")
    
    # CROWN⁴.5: Task system relationships
    task_view_state: Mapped[Optional["TaskViewState"]] = relationship(back_populates="user", uselist=False)
    task_counters: Mapped[Optional["TaskCounters"]] = relationship(back_populates="user", uselist=False)

    def __repr__(self):
        return f'<User {self.username}: {self.email}>'

    def set_password(self, password: str):
        """Set password hash using werkzeug."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        """Get full name or display name."""
        if self.display_name:
            return self.display_name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role in ["admin", "owner"]

    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login = datetime.utcnow()

    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary for JSON serialization."""
        data = {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'display_name': self.display_name,
            'full_name': self.full_name,
            'avatar_url': self.avatar_url,
            'is_active': self.active,
            'is_verified': self.is_verified,
            'role': self.role,
            'timezone': self.timezone,
            'workspace_id': self.workspace_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_sensitive:
            data['preferences'] = self.preferences
        
        data['onboarding_completed'] = self.onboarding_completed
        data['onboarding_step'] = self.onboarding_step
            
        return data
    
    @property
    def needs_onboarding(self) -> bool:
        """Check if user needs to complete onboarding."""
        return not self.onboarding_completed

    # Flask-Login required methods
    def get_id(self):
        """Return user ID as string for Flask-Login."""
        return str(self.id)

    @property
    def is_authenticated(self):
        """Always return True for authenticated users."""
        return True

    @property
    def is_anonymous(self):
        """Always return False for registered users."""
        return False