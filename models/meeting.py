"""
Enhanced Meeting Model for Comprehensive Meeting Management
SQLAlchemy 2.0-safe model extending Session with rich metadata, participants, and collaboration features.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Text, JSON, Boolean, ForeignKey, func, Index
from .base import Base

# Forward reference for type checking
if TYPE_CHECKING:
    from .user import User
    from .workspace import Workspace
    from .session import Session
    from .participant import Participant
    from .task import Task
    from .calendar_event import CalendarEvent
    from .analytics import Analytics


class Meeting(Base):
    """
    Enhanced meeting model with rich metadata, participant management, and collaboration features.
    Extends the basic Session model with comprehensive meeting information.
    """
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Core meeting information
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    meeting_type: Mapped[str] = mapped_column(String(64), default="general")  # general, standup, retrospective, planning
    status: Mapped[str] = mapped_column(String(32), default="scheduled")  # scheduled, live, completed, cancelled
    
    # Meeting scheduling
    scheduled_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    scheduled_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    
    # Meeting metadata
    agenda: Mapped[Optional[dict]] = mapped_column(JSON)  # Structured agenda with items
    tags: Mapped[Optional[list]] = mapped_column(JSON)  # Meeting tags for categorization
    priority: Mapped[str] = mapped_column(String(16), default="medium")  # low, medium, high, urgent
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring_pattern: Mapped[Optional[dict]] = mapped_column(JSON)  # Recurrence rules
    
    # Relationships
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    organizer: Mapped["User"] = relationship(back_populates="meetings", foreign_keys=[organizer_id])
    
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    workspace: Mapped["Workspace"] = relationship(back_populates="meetings")
    
    # Link to transcription session (one-to-one relationship)
    # Note: Session has meeting_id FK, so this is the back reference
    session: Mapped[Optional["Session"]] = relationship(back_populates="meeting")
    
    # Meeting participants
    participants: Mapped[list["Participant"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")
    
    # Action items and tasks
    tasks: Mapped[list["Task"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")
    
    # Calendar integration
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")
    
    # Analytics and insights
    analytics: Mapped[Optional["Analytics"]] = relationship(back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    
    # Meeting settings
    recording_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    transcription_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_insights_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Privacy and sharing
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    sharing_settings: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Archive functionality (CROWN⁴ Phase 4)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    archived_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Database indexes for query optimization
    __table_args__ = (
        # Composite index for workspace meetings list (workspace + status + sort)
        Index('ix_meetings_workspace_status_created', 'workspace_id', 'status', 'created_at'),
        # Composite index for calendar queries (workspace + date range)
        Index('ix_meetings_workspace_scheduled', 'workspace_id', 'scheduled_start'),
        # Single column indexes for filtering
        Index('ix_meetings_organizer', 'organizer_id'),
    )

    def __repr__(self):
        return f'<Meeting {self.id}: {self.title}>'

    @property
    def duration_minutes(self) -> Optional[int]:
        """Calculate meeting duration in minutes."""
        if self.actual_start and self.actual_end:
            duration = self.actual_end - self.actual_start
            return int(duration.total_seconds() / 60)
        elif self.scheduled_start and self.scheduled_end:
            duration = self.scheduled_end - self.scheduled_start
            return int(duration.total_seconds() / 60)
        return None

    @property
    def is_live(self) -> bool:
        """Check if meeting is currently live."""
        return self.status == "live"

    @property
    def is_completed(self) -> bool:
        """Check if meeting is completed."""
        return self.status == "completed"

    @property
    def participant_count(self) -> int:
        """Get number of participants."""
        return len(self.participants) if self.participants else 0

    @property
    def task_count(self) -> int:
        """Get number of tasks/action items."""
        return len(self.tasks) if self.tasks else 0

    @property
    def open_task_count(self) -> int:
        """Get number of open tasks."""
        if not self.tasks:
            return 0
        return len([task for task in self.tasks if task.status != "completed"])

    def start_meeting(self):
        """Mark meeting as started."""
        self.status = "live"
        self.actual_start = datetime.utcnow()

    def end_meeting(self):
        """Mark meeting as completed."""
        self.status = "completed"
        self.actual_end = datetime.utcnow()

    def add_participant(self, user_id: int, role: str = "participant"):
        """Add a participant to the meeting."""
        from .participant import Participant
        participant = Participant(
            meeting_id=self.id,
            user_id=user_id,
            role=role
        )
        self.participants.append(participant)
        return participant

    def archive(self, user_id: int):
        """Archive this meeting (CROWN⁴ Phase 4)."""
        self.archived = True
        self.archived_at = datetime.utcnow()
        self.archived_by_user_id = user_id

    def restore(self):
        """Restore this meeting from archive (CROWN⁴ Phase 4)."""
        self.archived = False
        self.archived_at = None
        self.archived_by_user_id = None

    def to_dict(self, include_participants=False, include_tasks=False):
        """Convert meeting to dictionary for JSON serialization."""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'meeting_type': self.meeting_type,
            'status': self.status,
            'scheduled_start': self.scheduled_start.isoformat() if self.scheduled_start else None,
            'scheduled_end': self.scheduled_end.isoformat() if self.scheduled_end else None,
            'actual_start': self.actual_start.isoformat() if self.actual_start else None,
            'actual_end': self.actual_end.isoformat() if self.actual_end else None,
            'timezone': self.timezone,
            'agenda': self.agenda,
            'tags': self.tags,
            'priority': self.priority,
            'is_recurring': self.is_recurring,
            'organizer_id': self.organizer_id,
            'workspace_id': self.workspace_id,
            'session_id': self.session.id if self.session else None,
            'duration_minutes': self.duration_minutes,
            'participant_count': self.participant_count,
            'task_count': self.task_count,
            'open_task_count': self.open_task_count,
            'recording_enabled': self.recording_enabled,
            'transcription_enabled': self.transcription_enabled,
            'ai_insights_enabled': self.ai_insights_enabled,
            'is_private': self.is_private,
            'archived': self.archived,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_participants and self.participants:
            data['participants'] = [p.to_dict() for p in self.participants]
            
        if include_tasks and self.tasks:
            data['tasks'] = [t.to_dict() for t in self.tasks]
            
        return data