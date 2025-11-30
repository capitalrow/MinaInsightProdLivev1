"""
Organization and Team models for Mina.

This module defines the data models for organizations, teams, and user memberships
to support role-based access control and team collaboration features.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
import enum
from . import db


class OrganizationStatus(enum.Enum):
    """Organization status enumeration."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class Organization(db.Model):
    """Organization model for multi-tenancy support."""
    __tablename__ = 'organizations'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    logo_url = Column(String(500))
    website = Column(String(255))
    
    # Organization settings
    status = Column(Enum(OrganizationStatus), default=OrganizationStatus.ACTIVE, nullable=False)
    max_users = Column(Integer, default=50)
    max_storage_gb = Column(Integer, default=100)
    
    # Subscription and billing
    plan_type = Column(String(50), default='free')
    billing_email = Column(String(255))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Settings JSON
    settings = Column(JSON, default={})
    
    # Relationships
    teams = relationship("Team", back_populates="organization", cascade="all, delete-orphan")
    memberships = relationship("OrganizationMembership", back_populates="organization", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Organization {self.name}>'
    
    def to_dict(self):
        """Convert organization to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'logo_url': self.logo_url,
            'website': self.website,
            'status': self.status.value,
            'max_users': self.max_users,
            'max_storage_gb': self.max_storage_gb,
            'plan_type': self.plan_type,
            'billing_email': self.billing_email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'settings': self.settings or {}
        }


class TeamType(enum.Enum):
    """Team type enumeration."""
    DEPARTMENT = "department"
    PROJECT = "project"
    CROSS_FUNCTIONAL = "cross_functional"
    TEMPORARY = "temporary"


class Team(db.Model):
    """Team model for organizing users within organizations."""
    __tablename__ = 'teams'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(7), default='#3B82F6')  # Hex color
    
    # Team configuration
    type = Column(Enum(TeamType), default=TeamType.PROJECT, nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)
    max_members = Column(Integer, default=50)
    
    # Foreign keys
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Settings JSON
    settings = Column(JSON, default={})
    
    # Relationships
    organization = relationship("Organization", back_populates="teams")
    memberships = relationship("TeamMembership", back_populates="team", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    
    def __repr__(self):
        return f'<Team {self.name}>'
    
    def to_dict(self):
        """Convert team to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'type': self.type.value,
            'is_private': self.is_private,
            'max_members': self.max_members,
            'organization_id': self.organization_id,
            'created_by_user_id': self.created_by_user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'settings': self.settings or {}
        }


class UserRole(enum.Enum):
    """User role enumeration for organizations."""
    SUPER_ADMIN = "super_admin"
    ORGANIZATION_ADMIN = "organization_admin"
    TEAM_ADMIN = "team_admin"
    MANAGER = "manager"
    MEMBER = "member"
    GUEST = "guest"


class OrganizationMembership(db.Model):
    """Organization membership model for user-organization relationships."""
    __tablename__ = 'organization_memberships'
    
    id = Column(Integer, primary_key=True)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    
    # Role and permissions
    role = Column(Enum(UserRole), default=UserRole.MEMBER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Invitation and joining
    invited_by_user_id = Column(Integer, ForeignKey('user.id'))
    invitation_token = Column(String(255), unique=True)
    invitation_expires_at = Column(DateTime)
    joined_at = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", back_populates="memberships")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('user_id', 'organization_id', name='unique_user_organization'),
    )
    
    def __repr__(self):
        return f'<OrganizationMembership user_id={self.user_id} org_id={self.organization_id} role={self.role.value}>'
    
    def to_dict(self):
        """Convert membership to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'organization_id': self.organization_id,
            'role': self.role.value,
            'is_active': self.is_active,
            'invited_by_user_id': self.invited_by_user_id,
            'invitation_token': self.invitation_token,
            'invitation_expires_at': self.invitation_expires_at.isoformat() if self.invitation_expires_at else None,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class TeamRole(enum.Enum):
    """Team role enumeration."""
    TEAM_LEAD = "team_lead"
    ADMIN = "admin"
    MEMBER = "member"
    CONTRIBUTOR = "contributor"
    OBSERVER = "observer"


class TeamMembership(db.Model):
    """Team membership model for user-team relationships."""
    __tablename__ = 'team_memberships'
    
    id = Column(Integer, primary_key=True)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    
    # Role and permissions
    role = Column(Enum(TeamRole), default=TeamRole.MEMBER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Invitation and joining
    invited_by_user_id = Column(Integer, ForeignKey('user.id'))
    invitation_token = Column(String(255), unique=True)
    invitation_expires_at = Column(DateTime)
    joined_at = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    team = relationship("Team", back_populates="memberships")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('user_id', 'team_id', name='unique_user_team'),
    )
    
    def __repr__(self):
        return f'<TeamMembership user_id={self.user_id} team_id={self.team_id} role={self.role.value}>'
    
    def to_dict(self):
        """Convert membership to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'team_id': self.team_id,
            'role': self.role.value,
            'is_active': self.is_active,
            'invited_by_user_id': self.invited_by_user_id,
            'invitation_token': self.invitation_token,
            'invitation_expires_at': self.invitation_expires_at.isoformat() if self.invitation_expires_at else None,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Permission(db.Model):
    """Permission model for defining granular access controls."""
    __tablename__ = 'permissions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    category = Column(String(50), nullable=False)  # e.g., 'meetings', 'tasks', 'settings'
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<Permission {self.name}>'
    
    def to_dict(self):
        """Convert permission to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class RolePermission(db.Model):
    """Role permission mapping for flexible RBAC."""
    __tablename__ = 'role_permissions'
    
    id = Column(Integer, primary_key=True)
    role = Column(String(50), nullable=False)  # Role name
    permission_id = Column(Integer, ForeignKey('permissions.id'), nullable=False)
    granted = Column(Boolean, default=True, nullable=False)
    
    # Context constraints (optional)
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    team_id = Column(Integer, ForeignKey('teams.id'))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    permission = relationship("Permission")
    organization = relationship("Organization")
    team = relationship("Team")
    
    def __repr__(self):
        return f'<RolePermission role={self.role} permission_id={self.permission_id} granted={self.granted}>'
    
    def to_dict(self):
        """Convert role permission to dictionary."""
        return {
            'id': self.id,
            'role': self.role,
            'permission_id': self.permission_id,
            'granted': self.granted,
            'organization_id': self.organization_id,
            'team_id': self.team_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }