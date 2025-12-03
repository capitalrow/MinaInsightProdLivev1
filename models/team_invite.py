"""
Team Invite Model for Onboarding and Team Collaboration
SQLAlchemy 2.0-safe model for managing team invitations.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, func
from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace


class TeamInvite(Base):
    """
    Model for tracking team invitations with secure token validation.
    Supports onboarding flow and workspace membership management.
    """
    __tablename__ = "team_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    inviter: Mapped["User"] = relationship(foreign_keys=[inviter_id])
    
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    workspace: Mapped["Workspace"] = relationship(foreign_keys=[workspace_id])
    
    role: Mapped[str] = mapped_column(String(32), default="member")
    
    status: Mapped[str] = mapped_column(String(32), default="pending")
    
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    accepted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    accepted_by: Mapped[Optional["User"]] = relationship(foreign_keys=[accepted_by_id])
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f'<TeamInvite {self.email} -> {self.workspace_id} ({self.status})>'

    @property
    def is_valid(self) -> bool:
        """Check if invite is still valid (pending and not expired)."""
        return (
            self.status == "pending" and
            self.expires_at > datetime.utcnow()
        )

    @property
    def is_expired(self) -> bool:
        """Check if invite has expired."""
        return self.expires_at <= datetime.utcnow()

    def accept(self, user: "User"):
        """Mark invite as accepted by a user."""
        self.status = "accepted"
        self.accepted_at = datetime.utcnow()
        self.accepted_by_id = user.id
        user.workspace_id = self.workspace_id

    def reject(self):
        """Mark invite as rejected."""
        self.status = "rejected"

    def expire(self):
        """Mark invite as expired."""
        self.status = "expired"

    def resend(self):
        """Reset invite for resending (extends expiration)."""
        self.expires_at = datetime.utcnow() + timedelta(days=7)
        self.status = "pending"

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'email': self.email,
            'inviter_id': self.inviter_id,
            'workspace_id': self.workspace_id,
            'role': self.role,
            'status': self.status,
            'is_valid': self.is_valid,
            'is_expired': self.is_expired,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token for the invite."""
        import secrets
        return secrets.token_urlsafe(48)

    @staticmethod
    def get_default_expiry() -> datetime:
        """Get default expiration date (7 days from now)."""
        return datetime.utcnow() + timedelta(days=7)
