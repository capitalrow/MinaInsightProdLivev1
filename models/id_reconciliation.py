"""
ID Reconciliation Ledger Model - CROWN⁴.5 TempIDReconciler
Tracks temporary ID → real ID mappings for offline task creation
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, Enum as SQLEnum, JSON, ForeignKey, func
from .base import Base
import enum


class ReconciliationStatus(enum.Enum):
    """Status of ID reconciliation"""
    PENDING = "pending"           # Temp ID created, waiting for server confirmation
    RECONCILED = "reconciled"     # Successfully mapped temp→real ID
    FAILED = "failed"             # Reconciliation failed (e.g., validation error)
    ORPHANED = "orphaned"         # Temp ID never reconciled, marked for cleanup


class IDReconciliation(Base):
    """
    Ledger for tracking temporary ID → real ID mappings.
    
    Lifecycle:
    1. PENDING: Client creates temp_xxx ID, logs to ledger
    2. RECONCILED: Server confirms creation with real ID, updates ledger
    3. Broadcast real ID to all tabs/cache for synchronization
    
    Enterprise features:
    - Idempotency: operation_id prevents duplicate reconciliations
    - Multi-tab sync: All tabs get notified of temp→real mapping
    - Audit trail: Created/reconciled timestamps for debugging
    - Cleanup: Orphaned temp IDs (>10 min, not reconciled) flagged for deletion
    """
    __tablename__ = 'id_reconciliation'
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Temporary ID (e.g., temp_1234567890_abc123)
    temp_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    
    # Real ID from database (null until reconciled)
    real_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    
    # Status of reconciliation
    status: Mapped[ReconciliationStatus] = mapped_column(
        SQLEnum(ReconciliationStatus), 
        nullable=False, 
        default=ReconciliationStatus.PENDING, 
        index=True
    )
    
    # Entity type (e.g., 'task', 'comment', etc.)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, default='task')
    
    # User who created the temp ID
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    
    # Operation ID for idempotency (prevents duplicate reconciliations)
    operation_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    
    # Session/workspace for multi-tenant isolation
    session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    workspace_id: Mapped[Optional[int]] = mapped_column(ForeignKey('workspaces.id'), nullable=True, index=True)
    
    # Data payload (original task data, error details, etc.)
    data_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    def __repr__(self):
        return f'<IDReconciliation {self.temp_id} → {self.real_id} ({self.status.value})>'
    
    def to_dict(self):
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'temp_id': self.temp_id,
            'real_id': self.real_id,
            'status': self.status.value,
            'entity_type': self.entity_type,
            'user_id': self.user_id,
            'operation_id': self.operation_id,
            'session_id': self.session_id,
            'workspace_id': self.workspace_id,
            'metadata': self.data_payload,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reconciled_at': self.reconciled_at.isoformat() if self.reconciled_at else None
        }
    
    @classmethod
    def create_pending(cls, temp_id, user_id, operation_id=None, entity_type='task', data_payload=None, session_id=None, workspace_id=None):
        """
        Create a new pending reconciliation entry.
        
        Args:
            temp_id: Temporary ID (e.g., temp_1234567890_abc123)
            user_id: User ID who created the temp ID
            operation_id: Optional operation ID for idempotency
            entity_type: Type of entity (default: 'task')
            data_payload: Additional data (original task data, etc.)
            session_id: Session ID for context
            workspace_id: Workspace ID for multi-tenancy
            
        Returns:
            IDReconciliation instance
        """
        from models import db
        
        reconciliation = cls(
            temp_id=temp_id,
            user_id=user_id,
            operation_id=operation_id,
            entity_type=entity_type,
            data_payload=data_payload,
            session_id=session_id,
            workspace_id=workspace_id,
            status=ReconciliationStatus.PENDING
        )
        db.session.add(reconciliation)
        db.session.commit()
        return reconciliation
    
    def mark_reconciled(self, real_id):
        """
        Mark reconciliation as complete with real ID.
        
        Args:
            real_id: Real database ID
        """
        from models import db
        
        self.real_id = real_id
        self.status = ReconciliationStatus.RECONCILED
        self.reconciled_at = datetime.utcnow()
        db.session.commit()
    
    def mark_failed(self, error_message=None):
        """
        Mark reconciliation as failed.
        
        Args:
            error_message: Optional error details
        """
        from models import db
        
        self.status = ReconciliationStatus.FAILED
        if error_message:
            if not self.data_payload:
                self.data_payload = {}
            self.data_payload['error'] = error_message
        db.session.commit()
    
    def mark_orphaned(self):
        """Mark as orphaned (cleanup candidate)"""
        from models import db
        
        self.status = ReconciliationStatus.ORPHANED
        db.session.commit()
    
    @classmethod
    def get_by_temp_id(cls, temp_id):
        """Get reconciliation by temp ID"""
        from models import db
        from sqlalchemy import select
        
        stmt = select(cls).where(cls.temp_id == temp_id)
        return db.session.execute(stmt).scalar_one_or_none()
    
    @classmethod
    def get_by_real_id(cls, real_id):
        """Get reconciliation by real ID"""
        from models import db
        from sqlalchemy import select
        
        stmt = select(cls).where(
            cls.real_id == real_id,
            cls.status == ReconciliationStatus.RECONCILED
        )
        return db.session.execute(stmt).scalar_one_or_none()
    
    @classmethod
    def get_pending_for_user(cls, user_id, limit=100):
        """Get pending reconciliations for a user"""
        from models import db
        from sqlalchemy import select
        
        stmt = select(cls).where(
            cls.user_id == user_id,
            cls.status == ReconciliationStatus.PENDING
        ).order_by(cls.created_at.desc()).limit(limit)
        return db.session.execute(stmt).scalars().all()
    
    @classmethod
    def cleanup_orphaned(cls, threshold_minutes=10):
        """
        Find and mark orphaned temp IDs for cleanup.
        
        Args:
            threshold_minutes: Age threshold for orphaned detection
            
        Returns:
            Number of orphaned entries marked
        """
        from datetime import timedelta
        from models import db
        from sqlalchemy import select
        
        threshold = datetime.utcnow() - timedelta(minutes=threshold_minutes)
        
        stmt = select(cls).where(
            cls.status == ReconciliationStatus.PENDING,
            cls.created_at < threshold
        )
        orphaned = db.session.execute(stmt).scalars().all()
        
        for entry in orphaned:
            entry.mark_orphaned()
        
        return len(orphaned)
