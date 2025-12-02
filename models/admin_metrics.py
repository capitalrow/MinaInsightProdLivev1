"""
Admin Dashboard Database Models
Stores system metrics, audit logs, and incidents for the Cognitive Mission Control dashboard.
"""

from datetime import datetime
from sqlalchemy import Integer, String, Float, Text, DateTime, Boolean, JSON, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app import db


class SystemMetric(db.Model):
    """
    Time-series storage for system health metrics.
    Enables historical charting and trend analysis.
    """
    __tablename__ = "admin_system_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="")
    
    component: Mapped[str] = mapped_column(String(64), default="system")
    status: Mapped[str] = mapped_column(String(32), default="normal")
    
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.now(),
        index=True
    )

    __table_args__ = (
        Index('ix_admin_metrics_type_time', 'metric_type', 'recorded_at'),
        Index('ix_admin_metrics_component', 'component', 'recorded_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'metric_type': self.metric_type,
            'value': self.value,
            'unit': self.unit,
            'component': self.component,
            'status': self.status,
            'metadata': self.metadata_json,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }


class PipelineMetric(db.Model):
    """
    Tracks meeting pipeline stage performance.
    Records latency and error rates for each processing stage.
    """
    __tablename__ = "admin_pipeline_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    error_rate: Mapped[float] = mapped_column(Float, default=0.0)
    throughput: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="healthy")
    
    session_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True
    )

    __table_args__ = (
        Index('ix_pipeline_stage_time', 'stage', 'recorded_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'stage': self.stage,
            'latency_ms': self.latency_ms,
            'error_rate': self.error_rate,
            'throughput': self.throughput,
            'status': self.status,
            'session_id': self.session_id,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }


class AuditLog(db.Model):
    """
    Immutable audit trail for compliance and debugging.
    Records all significant system and user actions.
    """
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_name: Mapped[str] = mapped_column(String(128), nullable=True)
    
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=True)
    
    before_state: Mapped[dict] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    ai_lineage: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    ip_address: Mapped[str] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(512), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True
    )

    __table_args__ = (
        Index('ix_audit_actor_time', 'actor_id', 'created_at'),
        Index('ix_audit_action_time', 'action', 'created_at'),
        Index('ix_audit_entity', 'entity_type', 'entity_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'trace_id': self.trace_id,
            'actor': f"{self.actor_type}:{self.actor_id}",
            'actor_name': self.actor_name,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'before': self.before_state,
            'after': self.after_state,
            'ai_lineage': self.ai_lineage,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Incident(db.Model):
    """
    System incidents and anomalies with AI-generated narratives.
    Tracks operational issues for the admin dashboard.
    """
    __tablename__ = "admin_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    incident_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    narrative: Mapped[str] = mapped_column(Text, nullable=True)
    
    component: Mapped[str] = mapped_column(String(64), nullable=True)
    root_cause: Mapped[str] = mapped_column(Text, nullable=True)
    resolution: Mapped[str] = mapped_column(Text, nullable=True)
    
    metrics_snapshot: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    detected_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True
    )
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    acknowledged_by: Mapped[int] = mapped_column(Integer, nullable=True)
    resolved_by: Mapped[int] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index('ix_incident_severity_status', 'severity', 'status'),
        Index('ix_incident_detected', 'detected_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'severity': self.severity,
            'status': self.status,
            'title': self.title,
            'description': self.description,
            'narrative': self.narrative,
            'component': self.component,
            'root_cause': self.root_cause,
            'resolution': self.resolution,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_time': self._calculate_resolution_time()
        }

    def _calculate_resolution_time(self):
        if self.resolved_at and self.detected_at:
            delta = self.resolved_at - self.detected_at
            minutes = int(delta.total_seconds() / 60)
            if minutes < 60:
                return f"{minutes} minutes"
            hours = minutes // 60
            return f"{hours} hours {minutes % 60} minutes"
        return None


class CopilotAction(db.Model):
    """
    Tracks AI Copilot actions for oversight and analysis.
    Records confidence, retries, and user overrides.
    """
    __tablename__ = "admin_copilot_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    retried: Mapped[bool] = mapped_column(Boolean, default=False)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True
    )

    __table_args__ = (
        Index('ix_copilot_action_time', 'action_type', 'created_at'),
        Index('ix_copilot_user_time', 'user_id', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'action_type': self.action_type,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'confidence': self.confidence,
            'success': self.success,
            'retried': self.retried,
            'overridden': self.overridden,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'latency_ms': self.latency_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
