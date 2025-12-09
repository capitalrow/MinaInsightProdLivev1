"""
Task Model for AI-Extracted Action Items and Task Management
SQLAlchemy 2.0-safe model for action items extracted from meetings with full task management capabilities.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Date, Text, Boolean, ForeignKey, func, JSON, Float, Index
from pgvector.sqlalchemy import Vector
from .base import Base

# Forward reference for type checking
if TYPE_CHECKING:
    from .meeting import Meeting
    from .user import User


class TaskAssignee(Base):
    """
    Junction table for many-to-many relationship between tasks and users.
    CROWN⁴.5: Enables multi-assignee support for collaborative task management.
    """
    __tablename__ = "task_assignees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Metadata for assignee relationship
    assigned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="assignee")  # assignee, reviewer, collaborator
    
    # Composite unique constraint to prevent duplicate assignments
    __table_args__ = (
        Index('ix_task_assignees_composite', 'task_id', 'user_id', unique=True),
    )

    def __repr__(self):
        return f'<TaskAssignee task_id={self.task_id} user_id={self.user_id}>'


class Task(Base):
    """
    Task model for action items extracted from meetings with comprehensive task management.
    Supports AI extraction, assignment, status tracking, and collaboration.
    """
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Task content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Task classification
    task_type: Mapped[str] = mapped_column(String(32), default="action_item")  # action_item, follow_up, decision, research
    priority: Mapped[str] = mapped_column(String(16), default="medium")  # low, medium, high, urgent
    category: Mapped[Optional[str]] = mapped_column(String(64))  # Custom categorization
    
    # Task status and lifecycle
    status: Mapped[str] = mapped_column(String(32), default="todo")  # todo, in_progress, blocked, completed, cancelled
    completion_percentage: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    
    # Scheduling and deadlines
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    reminder_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(DateTime)  # CROWN⁴.5: Task snooze support
    
    # Workspace relationship (CROWN⁴.5: Multi-workspace support)
    workspace_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workspaces.id"), nullable=True, index=True)
    
    # Relationships
    meeting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("meetings.id"), nullable=True)
    meeting: Mapped[Optional["Meeting"]] = relationship(back_populates="tasks")
    
    # Session relationship (for tasks created directly from session transcripts)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_to: Mapped[Optional["User"]] = relationship(back_populates="assigned_tasks", foreign_keys=[assigned_to_id])
    
    # CROWN⁴.5: Many-to-many assignees relationship for multi-assignee support
    assignees: Mapped[list["User"]] = relationship(
        secondary="task_assignees",
        primaryjoin="Task.id==TaskAssignee.task_id",
        secondaryjoin="User.id==TaskAssignee.user_id",
        back_populates="tasks_assigned_multi",
        lazy="selectin"  # Eager load assignees to avoid N+1 queries
    )
    
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_id])
    
    # AI extraction metadata
    extracted_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)  # AI confidence (0-1)
    extraction_context: Mapped[Optional[dict]] = mapped_column(JSON)  # Context from transcript
    
    # CROWN⁴.5: Deduplication and origin tracking
    origin_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)  # SHA-256 hash for deduplication
    source: Mapped[str] = mapped_column(String(32), default="manual")  # manual, ai_extraction, import, voice, email
    
    # CROWN⁴.5: Event sequencing and conflict resolution
    vector_clock_token: Mapped[Optional[dict]] = mapped_column(JSON)  # Vector clock for distributed ordering
    reconciliation_status: Mapped[str] = mapped_column(String(32), default="synced")  # synced, pending, conflict, reconciled
    
    # CROWN⁴.5: Transcript linking
    transcript_span: Mapped[Optional[dict]] = mapped_column(JSON)  # {start_ms: int, end_ms: int, segment_ids: []}
    
    # CROWN⁴.5: Emotional architecture
    emotional_state: Mapped[Optional[str]] = mapped_column(String(32))  # pending_suggest, accepted, editing, completed
    
    # Task details
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float)
    actual_hours: Mapped[Optional[float]] = mapped_column(Float)
    tags: Mapped[Optional[list]] = mapped_column(JSON)  # Task tags (legacy)
    labels: Mapped[Optional[list]] = mapped_column(JSON)  # CROWN⁴.5: Task labels for organization
    
    # CROWN⁴.5 Phase 3: Task ordering/positioning for drag-drop
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Display order (lower = higher priority)
    
    # CROWN⁴.6: Semantic search embeddings
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536), nullable=True)  # OpenAI embedding vector (1536-dim)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(64), default="text-embedding-3-small")
    embedding_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Dependencies and relationships
    depends_on_task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    depends_on_task: Mapped[Optional["Task"]] = relationship(remote_side="Task.id")
    
    # Collaboration and comments
    is_collaborative: Mapped[bool] = mapped_column(Boolean, default=False)
    watchers: Mapped[Optional[list]] = mapped_column(JSON)  # User IDs watching this task
    
    # CROWN⁴.5 Phase 1: Soft delete fields
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_by: Mapped[Optional["User"]] = relationship(foreign_keys=[deleted_by_user_id])
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Database indexes for query optimization
    __table_args__ = (
        # Composite index for user task list (assigned + status + due date)
        Index('ix_tasks_assigned_status_due', 'assigned_to_id', 'status', 'due_date'),
        # Composite index for meeting tasks (meeting + status)
        Index('ix_tasks_meeting_status', 'meeting_id', 'status'),
        # Single column indexes for filtering
        Index('ix_tasks_created_by', 'created_by_id'),
        Index('ix_tasks_depends_on', 'depends_on_task_id'),
        # CROWN⁴.5: Index for reconciliation queries
        Index('ix_tasks_reconciliation', 'reconciliation_status'),
        # CROWN⁴.5: Index for source filtering
        Index('ix_tasks_source', 'source'),
        # CROWN⁴.5 Phase 1: Index for soft delete filtering
        Index('ix_tasks_deleted_at', 'deleted_at'),
        # CROWN⁴.5 Phase 3: Index for task ordering/positioning
        Index('ix_tasks_position', 'position'),
    )

    def __repr__(self):
        return f'<Task {self.id}: {self.title}>'

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.due_date or self.status == "completed":
            return False
        return date.today() > self.due_date

    @property
    def is_due_soon(self, days: int = 3) -> bool:
        """Check if task is due within specified days."""
        if not self.due_date or self.status == "completed":
            return False
        days_until_due = (self.due_date - date.today()).days
        return 0 <= days_until_due <= days

    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status == "completed"

    @property
    def is_in_progress(self) -> bool:
        """Check if task is in progress."""
        return self.status == "in_progress"

    @property
    def days_until_due(self) -> Optional[int]:
        """Get number of days until due date."""
        if not self.due_date:
            return None
        return (self.due_date - date.today()).days

    def complete_task(self):
        """Mark task as completed."""
        self.status = "completed"
        self.completion_percentage = 100
        self.completed_at = datetime.utcnow()

    def start_task(self):
        """Mark task as in progress."""
        if self.status == "todo":
            self.status = "in_progress"

    def block_task(self, reason: Optional[str] = None):
        """Mark task as blocked."""
        self.status = "blocked"
        if reason and self.extraction_context:
            self.extraction_context["blocked_reason"] = reason

    def update_progress(self, percentage: int):
        """Update task completion percentage."""
        self.completion_percentage = max(0, min(100, percentage))
        if percentage == 100:
            self.complete_task()
        elif percentage > 0 and self.status == "todo":
            self.start_task()

    def assign_to_user(self, user_id: int):
        """Assign task to a user."""
        self.assigned_to_id = user_id

    def add_watcher(self, user_id: int):
        """Add a user to watch this task."""
        if not self.watchers:
            self.watchers = []
        if user_id not in self.watchers:
            self.watchers.append(user_id)

    def remove_watcher(self, user_id: int):
        """Remove a user from watching this task."""
        if self.watchers and user_id in self.watchers:
            self.watchers.remove(user_id)

    def to_dict_ssr(self):
        """CROWN⁴.13: Optimized serialization for SSR First Paint (<200ms target).
        Includes fields essential for hydration + modal display, excludes expensive computed fields.
        ~25 fields vs 45+ in full to_dict (50% reduction).
        """
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'assigned_to_id': self.assigned_to_id,
            'assignee_ids': sorted([user.id for user in self.assignees]) if self.assignees else [],
            'meeting_id': self.meeting_id,
            'session_id': self.session_id,
            'labels': self.labels,
            'tags': self.tags,
            'position': self.position,
            'extracted_by_ai': self.extracted_by_ai,
            'snoozed_until': self.snoozed_until.isoformat() if self.snoozed_until else None,
            'is_overdue': self.is_overdue,
            'is_due_soon': self.is_due_soon,
        }
        
        if self.assigned_to:
            data['assigned_to'] = {
                'id': self.assigned_to.id,
                'username': self.assigned_to.username,
                'display_name': getattr(self.assigned_to, 'display_name', None),
            }
        
        return data

    def to_dict(self, include_relationships=False):
        """Convert task to dictionary for JSON serialization.
        
        Note: Embedding fields (embedding, embedding_model, embedding_updated_at) are intentionally 
        excluded from serialization to avoid pgvector.Vector JSON serialization issues and reduce 
        payload size (1536-dim vectors are large). Embeddings are only used for backend similarity search.
        """
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'task_type': self.task_type,
            'priority': self.priority,
            'category': self.category,
            'status': self.status,
            'completion_percentage': self.completion_percentage,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'reminder_date': self.reminder_date.isoformat() if self.reminder_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'snoozed_until': self.snoozed_until.isoformat() if self.snoozed_until else None,
            'meeting_id': self.meeting_id,
            'session_id': self.session_id,
            'assigned_to_id': self.assigned_to_id,
            # CROWN⁴.8: Sort assignee_ids by ID for consistent ordering between client and server
            'assignee_ids': sorted([user.id for user in self.assignees]) if self.assignees else [],
            'created_by_id': self.created_by_id,
            'extracted_by_ai': self.extracted_by_ai,
            'confidence_score': self.confidence_score,
            'extraction_context': self.extraction_context,
            'transcript_span': self.transcript_span,
            'estimated_hours': self.estimated_hours,
            'actual_hours': self.actual_hours,
            'tags': self.tags,
            'labels': self.labels,
            'position': self.position,
            'depends_on_task_id': self.depends_on_task_id,
            'is_collaborative': self.is_collaborative,
            'watchers': self.watchers,
            'is_overdue': self.is_overdue,
            'is_due_soon': self.is_due_soon,
            'is_completed': self.is_completed,
            'is_in_progress': self.is_in_progress,
            'days_until_due': self.days_until_due,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'origin_hash': self.origin_hash,
            'source': self.source,
            'vector_clock_token': self.vector_clock_token,
            'reconciliation_status': self.reconciliation_status,
            'emotional_state': self.emotional_state,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'deleted_by_user_id': self.deleted_by_user_id,
            # CROWN⁴.6: embedding, embedding_model, embedding_updated_at intentionally excluded
        }
        
        # CROWN⁴.7: Always include assigned_to user object for UI hydration
        # This fixes the bug where assignee names disappear after page reload
        # because cache bootstrap/idle sync needs user data to render badges correctly
        if self.assigned_to:
            data['assigned_to'] = {
                'id': self.assigned_to.id,
                'username': self.assigned_to.username,
                'display_name': getattr(self.assigned_to, 'display_name', None),
                'email': self.assigned_to.email
            }
        
        if include_relationships:
            
            # CROWN⁴.8: Multi-assignee support with sorted order for consistency
            if self.assignees:
                sorted_assignees = sorted(self.assignees, key=lambda u: u.id)
                data['assignees'] = [{
                    'id': user.id,
                    'username': user.username,
                    'display_name': user.display_name,
                    'full_name': user.full_name,
                    'avatar_url': user.avatar_url
                } for user in sorted_assignees]
            
            if self.created_by:
                data['created_by'] = self.created_by.to_dict()
            if self.meeting:
                data['meeting'] = {
                    'id': self.meeting.id,
                    'title': self.meeting.title,
                    'scheduled_start': self.meeting.scheduled_start.isoformat() if self.meeting.scheduled_start else None
                }
                
        return data

    @staticmethod
    def create_from_ai_extraction(meeting_id: int, title: str, description: Optional[str] = None, 
                                 confidence: Optional[float] = None, context: Optional[dict] = None) -> "Task":
        """Create a task from AI extraction with metadata."""
        task = Task(
            meeting_id=meeting_id,
            title=title,
            description=description,
            extracted_by_ai=True,
            confidence_score=confidence,
            extraction_context=context
        )
        return task