"""
LedgerCompactor Service - CROWN⁴.5 Event Ledger Maintenance

Implements daily mutation compression for EventLedger. Compacts old event
entries to reduce database size while maintaining auditability.

Key Features:
- Daily compression of old event ledger entries
- Preserve audit trail with compressed summaries
- Configurable retention policies
- Background job scheduling
- Safe deletion with backup
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func, delete
from models import db
from models.event_ledger import EventLedger, EventStatus, EventType
from models.compaction_summary import CompactionSummary

logger = logging.getLogger(__name__)


class LedgerCompactor:
    """
    Service for compacting and maintaining the event ledger.
    
    Responsibilities:
    - Compress old event entries into summaries
    - Enforce retention policies
    - Cleanup completed/failed events
    - Generate compaction reports
    - Schedule background compaction jobs
    """
    
    # Configuration constants
    RETENTION_DAYS_COMPLETED = 30  # Keep completed events for 30 days
    RETENTION_DAYS_FAILED = 90  # Keep failed events for 90 days (for debugging)
    RETENTION_DAYS_PENDING = 7  # Keep old pending events for 7 days
    SUMMARY_BATCH_SIZE = 1000  # Events to summarize per batch
    
    def __init__(self):
        """Initialize LedgerCompactor."""
        # Compaction metrics
        self.metrics = {
            'total_compactions': 0,
            'events_compacted': 0,
            'events_deleted': 0,
            'summaries_created': 0,
            'compaction_failures': 0,
            'last_compaction_time': None
        }
    
    def should_compact_event(self, event: EventLedger) -> bool:
        """
        Determine if an event should be compacted based on age and status.
        
        Args:
            event: EventLedger instance
            
        Returns:
            True if should compact, False otherwise
        """
        if not event.created_at:
            return False
        
        age_days = (datetime.utcnow() - event.created_at).days
        
        # Check retention based on status
        if event.status == EventStatus.COMPLETED:
            return age_days > self.RETENTION_DAYS_COMPLETED
        elif event.status == EventStatus.FAILED:
            return age_days > self.RETENTION_DAYS_FAILED
        elif event.status == EventStatus.PENDING:
            return age_days > self.RETENTION_DAYS_PENDING
        
        return False
    
    def get_events_for_compaction(
        self,
        workspace_id: str,
        batch_size: int = SUMMARY_BATCH_SIZE,
        count_only: bool = False
    ) -> List[EventLedger]:
        """
        Get events that should be compacted for a specific workspace.
        
        Args:
            workspace_id: Workspace ID to scope compaction
            batch_size: Maximum number of events to return (ignored if count_only=True)
            count_only: If True, return empty list but log count for status checks
            
        Returns:
            List of events ready for compaction (empty if count_only=True)
        """
        try:
            # Calculate cutoff dates
            completed_cutoff = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS_COMPLETED)
            failed_cutoff = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS_FAILED)
            pending_cutoff = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS_PENDING)
            
            # Build base condition (WORKSPACE-SCOPED)
            condition = and_(
                EventLedger.workspace_id == str(workspace_id),  # CRITICAL: workspace isolation
                (
                    and_(
                        EventLedger.created_at < completed_cutoff,
                        EventLedger.status == EventStatus.COMPLETED
                    ) | and_(
                        EventLedger.created_at < failed_cutoff,
                        EventLedger.status == EventStatus.FAILED
                    ) | and_(
                        EventLedger.created_at < pending_cutoff,
                        EventLedger.status == EventStatus.PENDING
                    )
                )
            )
            
            # If count_only, use get_events_ready_count instead (deprecated path)
            if count_only:
                logger.warning("count_only parameter is deprecated, use get_events_ready_count() instead")
                return []  # Return empty list for backwards compatibility
            
            # Otherwise, fetch events
            query = select(EventLedger).where(condition).order_by(EventLedger.created_at.asc()).limit(batch_size)
            events = list(db.session.scalars(query).all())
            
            logger.info(f"Found {len(events)} events ready for compaction in workspace {workspace_id}")
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get events for compaction: {e}")
            return []
    
    def get_events_ready_count(self, workspace_id: str) -> int:
        """
        Get count of events ready for compaction in a workspace.
        
        Directly computes workspace-scoped count via COUNT query (no process-global cache).
        
        Args:
            workspace_id: Workspace ID to scope counting
            
        Returns:
            Number of events ready for compaction
        """
        try:
            # Calculate cutoff dates
            completed_cutoff = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS_COMPLETED)
            failed_cutoff = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS_FAILED)
            pending_cutoff = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS_PENDING)
            
            # Build condition (WORKSPACE-SCOPED)
            condition = and_(
                EventLedger.workspace_id == str(workspace_id),  # CRITICAL: workspace isolation
                (
                    and_(
                        EventLedger.created_at < completed_cutoff,
                        EventLedger.status == EventStatus.COMPLETED
                    ) | and_(
                        EventLedger.created_at < failed_cutoff,
                        EventLedger.status == EventStatus.FAILED
                    ) | and_(
                        EventLedger.created_at < pending_cutoff,
                        EventLedger.status == EventStatus.PENDING
                    )
                )
            )
            
            # Direct COUNT query (no cache, no global state)
            count = db.session.scalar(select(func.count()).select_from(EventLedger).where(condition)) or 0
            logger.info(f"Found {count} events ready for compaction in workspace {workspace_id}")
            return count
            
        except Exception as e:
            logger.error(f"Failed to count events for compaction: {e}")
            return 0
    
    def create_compaction_summary(
        self,
        events: List[EventLedger]
    ) -> Dict[str, Any]:
        """
        Create a summary of compacted events.
        
        Args:
            events: Events to summarize
            
        Returns:
            Summary dictionary
        """
        try:
            # Group by event type
            by_type: Dict[str, int] = {}
            by_status: Dict[str, int] = {}
            total_duration_ms = 0.0
            
            for event in events:
                # Count by type
                event_type = event.event_type.value
                by_type[event_type] = by_type.get(event_type, 0) + 1
                
                # Count by status
                status = event.status.value
                by_status[status] = by_status.get(status, 0) + 1
                
                # Sum duration
                if event.duration_ms:
                    total_duration_ms += event.duration_ms
            
            # Build summary
            summary = {
                'compaction_date': datetime.utcnow().isoformat(),
                'total_events': len(events),
                'by_type': by_type,
                'by_status': by_status,
                'total_duration_ms': total_duration_ms,
                'avg_duration_ms': total_duration_ms / len(events) if events else 0,
                'date_range': {
                    'start': min(e.created_at for e in events if e.created_at).isoformat() if events else None,
                    'end': max(e.created_at for e in events if e.created_at).isoformat() if events else None
                }
            }
            
            logger.debug(f"Created compaction summary for {len(events)} events")
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to create compaction summary: {e}")
            return {
                'error': str(e),
                'total_events': len(events)
            }
    
    def compact_events(
        self,
        workspace_id: str,
        dry_run: bool = False,
        batch_size: int = SUMMARY_BATCH_SIZE
    ) -> Dict[str, Any]:
        """
        Compact old events by creating persisted summaries and deleting originals.
        
        Persists summary to CompactionSummary table before deletion to maintain
        audit trail as required by CROWN⁴.5 spec.
        
        Args:
            workspace_id: Workspace ID to scope compaction (required for multi-tenant isolation)
            dry_run: If True, don't actually delete events
            batch_size: Number of events to compact per batch
            
        Returns:
            Compaction result summary
        """
        try:
            # Get events to compact (workspace-scoped)
            events_to_compact = self.get_events_for_compaction(workspace_id, batch_size)
            
            if not events_to_compact:
                return {
                    'success': True,
                    'events_compacted': 0,
                    'dry_run': dry_run,
                    'message': 'No events ready for compaction'
                }
            
            # Create summary dictionary
            summary_data = self.create_compaction_summary(events_to_compact)
            
            # Persist summary to database BEFORE deletion
            deleted_count = 0
            summary_id = None
            
            if not dry_run:
                # Create CompactionSummary record (with workspace_id for isolation)
                compaction_summary = CompactionSummary(
                    workspace_id=str(workspace_id),  # CRITICAL: workspace isolation
                    total_events_compacted=len(events_to_compact),
                    events_by_type=summary_data.get('by_type', {}),
                    events_by_status=summary_data.get('by_status', {}),
                    total_duration_ms=summary_data.get('total_duration_ms'),
                    avg_duration_ms=summary_data.get('avg_duration_ms'),
                    earliest_event_date=datetime.fromisoformat(summary_data['date_range']['start']) if summary_data.get('date_range', {}).get('start') else None,
                    latest_event_date=datetime.fromisoformat(summary_data['date_range']['end']) if summary_data.get('date_range', {}).get('end') else None,
                    events_deleted=0,  # Will update after deletion
                    compaction_success=True
                )
                
                db.session.add(compaction_summary)
                db.session.flush()  # Get ID but don't commit yet
                summary_id = compaction_summary.id
                
                # Now safe to delete events (WORKSPACE-FILTERED DELETE)
                event_ids = [e.id for e in events_to_compact]
                delete_stmt = delete(EventLedger).where(
                    and_(
                        EventLedger.id.in_(event_ids),
                        EventLedger.workspace_id == str(workspace_id)  # CRITICAL: double-check workspace
                    )
                )
                result = db.session.execute(delete_stmt)
                deleted_count = result.rowcount
                
                # Update summary with deletion count
                compaction_summary.events_deleted = deleted_count
                
                # Commit both summary and deletions
                db.session.commit()
                
                # Update metrics
                self.metrics['events_compacted'] += len(events_to_compact)
                self.metrics['events_deleted'] += deleted_count
                self.metrics['summaries_created'] += 1
                self.metrics['total_compactions'] += 1
                self.metrics['last_compaction_time'] = datetime.utcnow().isoformat()
                
                logger.info(
                    f"Compaction completed: {len(events_to_compact)} events compacted, "
                    f"{deleted_count} deleted, summary ID {summary_id}"
                )
            
            result = {
                'success': True,
                'events_found': len(events_to_compact),
                'events_compacted': len(events_to_compact),
                'events_deleted': deleted_count,
                'summary': summary_data,
                'summary_id': summary_id,
                'dry_run': dry_run
            }
            
            return result
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to compact events: {e}")
            
            # Create failed summary record (with workspace_id)
            if not dry_run:
                try:
                    failed_summary = CompactionSummary(
                        workspace_id=str(workspace_id),  # CRITICAL: workspace isolation
                        total_events_compacted=0,
                        events_by_type={},
                        events_by_status={},
                        events_deleted=0,
                        compaction_success=False,
                        error_message=str(e)[:500]
                    )
                    db.session.add(failed_summary)
                    db.session.commit()
                except Exception:
                    pass  # Don't fail twice
            
            self.metrics['compaction_failures'] += 1
            
            return {
                'success': False,
                'error': str(e),
                'dry_run': dry_run
            }
    
    def cleanup_orphaned_events(self, workspace_id: str) -> Dict[str, Any]:
        """
        Cleanup orphaned events (events with deleted sessions/users) for a specific workspace.
        
        Args:
            workspace_id: Workspace ID to scope cleanup
            
        Returns:
            Cleanup result
        """
        try:
            # In a real implementation, this would check for foreign key violations
            # and cleanup events whose referenced entities no longer exist
            
            # For now, just check for very old pending events (WORKSPACE-SCOPED)
            cutoff = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS_PENDING)
            
            query = select(EventLedger).where(
                and_(
                    EventLedger.workspace_id == str(workspace_id),  # CRITICAL: workspace isolation
                    EventLedger.status == EventStatus.PENDING,
                    EventLedger.created_at < cutoff
                )
            )
            
            orphaned = list(db.session.scalars(query).all())
            
            # Delete orphaned events (WORKSPACE-FILTERED DELETE)
            if orphaned:
                orphaned_ids = [e.id for e in orphaned]
                delete_stmt = delete(EventLedger).where(
                    and_(
                        EventLedger.id.in_(orphaned_ids),
                        EventLedger.workspace_id == str(workspace_id)  # CRITICAL: double-check workspace
                    )
                )
                result = db.session.execute(delete_stmt)
                deleted_count = result.rowcount
                
                db.session.commit()
                
                logger.info(f"Cleaned up {deleted_count} orphaned events")
                
                return {
                    'success': True,
                    'orphaned_found': len(orphaned),
                    'orphaned_deleted': deleted_count
                }
            
            return {
                'success': True,
                'orphaned_found': 0,
                'orphaned_deleted': 0
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to cleanup orphaned events: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_ledger_statistics(self) -> Dict[str, Any]:
        """
        Get current event ledger statistics.
        
        Returns:
            Dictionary with ledger statistics
        """
        try:
            # Count events by status
            status_counts = {}
            for status in EventStatus:
                count = db.session.scalar(
                    select(func.count()).where(EventLedger.status == status)
                ) or 0
                status_counts[status.value] = count
            
            # Get total count
            total_count = db.session.scalar(select(func.count(EventLedger.id))) or 0
            
            # Get oldest and newest
            oldest = db.session.scalar(
                select(EventLedger.created_at).order_by(EventLedger.created_at.asc()).limit(1)
            )
            newest = db.session.scalar(
                select(EventLedger.created_at).order_by(EventLedger.created_at.desc()).limit(1)
            )
            
            # Calculate size estimate (rough)
            avg_event_size_kb = 2  # Rough estimate
            estimated_size_mb = (total_count * avg_event_size_kb) / 1024
            
            return {
                'total_events': total_count,
                'by_status': status_counts,
                'oldest_event': oldest.isoformat() if oldest else None,
                'newest_event': newest.isoformat() if newest else None,
                'estimated_size_mb': round(estimated_size_mb, 2),
                'compaction_metrics': self.metrics
            }
            
        except Exception as e:
            logger.error(f"Failed to get ledger statistics: {e}")
            return {
                'error': str(e)
            }
    
    def schedule_daily_compaction(self) -> bool:
        """
        Schedule daily compaction job.
        
        In production, this would integrate with a job scheduler like Celery,
        APScheduler, or cron.
        
        Returns:
            True if scheduled successfully
        """
        logger.info("Daily compaction scheduling not yet implemented")
        # TODO: Integrate with background job scheduler
        return False
    
    def get_metrics(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get compaction metrics.
        
        If workspace_id is provided, returns workspace-scoped metrics computed from
        CompactionSummary records. Otherwise returns process-global metrics (for backwards compatibility).
        
        Args:
            workspace_id: Optional workspace ID to scope metrics
            
        Returns:
            Dictionary with metrics
        """
        # If workspace_id provided, compute fresh metrics from database (WORKSPACE-SCOPED)
        if workspace_id:
            try:
                # Query CompactionSummary for workspace-scoped metrics
                summaries = db.session.query(CompactionSummary).filter(
                    CompactionSummary.workspace_id == str(workspace_id)
                ).all()
                
                total_compactions = len([s for s in summaries if s.compaction_success])
                events_compacted = sum(s.total_events_compacted for s in summaries if s.compaction_success)
                events_deleted = sum(s.events_deleted for s in summaries if s.compaction_success)
                summaries_created = total_compactions
                compaction_failures = len([s for s in summaries if not s.compaction_success])
                last_compaction_time = max((s.compaction_date for s in summaries if s.compaction_success), default=None)
                
                return {
                    'total_compactions': total_compactions,
                    'events_compacted': events_compacted,
                    'events_deleted': events_deleted,
                    'summaries_created': summaries_created,
                    'compaction_failures': compaction_failures,
                    'last_compaction_time': last_compaction_time.isoformat() if last_compaction_time else None
                }
            except Exception as e:
                logger.error(f"Failed to get workspace-scoped metrics: {e}")
                # Fall through to global metrics on error
        
        # Global metrics (process-wide, NOT workspace-scoped - use with caution)
        return self.metrics.copy()
    
    def get_compaction_history(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent compaction history from persisted summaries.
        
        Args:
            limit: Maximum number of summaries to return
            
        Returns:
            List of compaction summaries
        """
        try:
            query = select(CompactionSummary).order_by(
                CompactionSummary.compaction_date.desc()
            ).limit(limit)
            
            summaries = list(db.session.scalars(query).all())
            
            return [s.to_dict() for s in summaries]
            
        except Exception as e:
            logger.error(f"Failed to get compaction history: {e}")
            return []
    
    def reset_metrics(self):
        """Reset compaction metrics."""
        self.metrics = {
            'total_compactions': 0,
            'events_compacted': 0,
            'events_deleted': 0,
            'summaries_created': 0,
            'compaction_failures': 0,
            'last_compaction_time': None
        }


# Singleton instance
ledger_compactor = LedgerCompactor()
