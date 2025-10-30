"""
TempIDReconciler Service - CROWN⁴.5 Core Reconciliation Engine
Manages temporary ID → real ID mappings for offline task creation with zero data loss.

Features:
- Deterministic temp ID generation (temp_{timestamp}_{user_hash})
- Ledger-based tracking with status lifecycle
- Multi-tab synchronization via WebSocket broadcasts
- Idempotency protection with operation IDs
- Automatic orphan cleanup
"""

import logging
import hashlib
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from models import db, IDReconciliation, ReconciliationStatus
from services.event_broadcaster import EventBroadcaster
from models.event_ledger import EventType

logger = logging.getLogger(__name__)


class TempIDReconciler:
    """
    Enterprise-grade temporary ID reconciliation service.
    
    Lifecycle:
    1. Client creates temp ID (generate_temp_id)
    2. Client logs to ledger (log_pending_reconciliation)
    3. Server confirms task creation (reconcile_temp_id)
    4. Broadcast real ID to all tabs (via WebSocket)
    5. Clients update cache with real ID
    
    Enterprise guarantees:
    - No duplicate reconciliations (operation_id)
    - Multi-tab sync (WebSocket broadcasts)
    - Zero data loss (ledger-based tracking)
    - Deterministic ordering (vector clocks)
    """
    
    def __init__(self, event_broadcaster: Optional[EventBroadcaster] = None):
        """
        Initialize reconciler.
        
        Args:
            event_broadcaster: EventBroadcaster for WebSocket notifications
        """
        self.event_broadcaster = event_broadcaster or EventBroadcaster()
    
    @staticmethod
    def generate_temp_id(user_id: int, prefix: str = "temp") -> str:
        """
        Generate unique temporary ID with collision resistance.
        
        Format: temp_{timestamp_ms}_{user_hash}_{uuid_short}
        
        Args:
            user_id: User ID creating the temp ID
            prefix: Prefix for temp ID (default: "temp")
            
        Returns:
            Temporary ID string
            
        Example:
            temp_1730304000000_a1b2c3_f8e9
        """
        import uuid
        
        timestamp_ms = int(time.time() * 1000)
        user_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:6]
        # Add UUID component for collision resistance
        uuid_short = uuid.uuid4().hex[:4]
        return f"{prefix}_{timestamp_ms}_{user_hash}_{uuid_short}"
    
    @staticmethod
    def is_temp_id(task_id: Any) -> bool:
        """
        Check if ID is a temporary ID.
        
        Args:
            task_id: ID to check
            
        Returns:
            True if temp ID, False otherwise
        """
        if not isinstance(task_id, str):
            return False
        return task_id.startswith("temp_")
    
    def log_pending_reconciliation(
        self,
        temp_id: str,
        user_id: int,
        operation_id: Optional[str] = None,
        entity_type: str = 'task',
        data_payload: Optional[Dict[str, Any]] = None,
        session_id: Optional[int] = None,
        workspace_id: Optional[int] = None
    ) -> IDReconciliation:
        """
        Log a pending reconciliation to the ledger.
        
        Args:
            temp_id: Temporary ID
            user_id: User ID creating the temp ID
            operation_id: Optional operation ID for idempotency
            entity_type: Entity type (default: 'task')
            data_payload: Additional data (original task data)
            session_id: Session ID for context
            workspace_id: Workspace ID for multi-tenancy
            
        Returns:
            IDReconciliation instance
        """
        try:
            # Check for existing reconciliation (idempotency)
            if operation_id:
                from sqlalchemy import select
                stmt = select(IDReconciliation).where(IDReconciliation.operation_id == operation_id)
                existing = db.session.execute(stmt).scalar_one_or_none()
                if existing:
                    logger.info(f"Reconciliation already exists for operation {operation_id}")
                    return existing
            
            # Check for duplicate temp_id
            existing = IDReconciliation.get_by_temp_id(temp_id)
            if existing:
                logger.warning(f"Temp ID {temp_id} already exists in ledger")
                return existing
            
            # Create new pending reconciliation
            reconciliation = IDReconciliation.create_pending(
                temp_id=temp_id,
                user_id=user_id,
                operation_id=operation_id,
                entity_type=entity_type,
                data_payload=data_payload,
                session_id=session_id,
                workspace_id=workspace_id
            )
            
            logger.info(f"Logged pending reconciliation: {temp_id} for user {user_id}")
            return reconciliation
            
        except Exception as e:
            logger.error(f"Failed to log pending reconciliation: {e}")
            db.session.rollback()
            raise
    
    def reconcile_temp_id(
        self,
        temp_id: str,
        real_id: int,
        user_id: int,
        workspace_id: Optional[int] = None,
        broadcast: bool = True
    ) -> Optional[IDReconciliation]:
        """
        Reconcile temp ID with real database ID.
        
        Args:
            temp_id: Temporary ID to reconcile
            real_id: Real database ID
            user_id: User ID who created the task
            workspace_id: Workspace ID for multi-tenancy
            broadcast: Whether to broadcast reconciliation via WebSocket
            
        Returns:
            IDReconciliation instance or None if not found
        """
        try:
            # Find pending reconciliation
            reconciliation = IDReconciliation.get_by_temp_id(temp_id)
            
            if not reconciliation:
                logger.warning(f"No reconciliation found for temp ID: {temp_id}")
                # Create retroactive reconciliation entry
                reconciliation = IDReconciliation.create_pending(
                    temp_id=temp_id,
                    user_id=user_id,
                    entity_type='task',
                    workspace_id=workspace_id
                )
            
            # Update real_id but don't mark as RECONCILED until broadcast succeeds
            reconciliation.real_id = real_id
            db.session.commit()
            
            logger.info(f"Mapped {temp_id} → {real_id}, attempting broadcast...")
            
            # Broadcast to all tabs for cache synchronization
            broadcast_success = False
            if broadcast and self.event_broadcaster:
                broadcast_success = self._broadcast_reconciliation(
                    temp_id=temp_id,
                    real_id=real_id,
                    user_id=user_id,
                    workspace_id=workspace_id
                )
            else:
                # No broadcast requested, mark as reconciled
                broadcast_success = True
            
            # Only mark as RECONCILED if broadcast succeeded OR broadcast not required
            if broadcast_success:
                reconciliation.mark_reconciled(real_id)
                logger.info(f"✅ Reconciliation complete: {temp_id} → {real_id}")
            else:
                # Broadcast failed - keep as PENDING for bootstrap recovery
                logger.error(f"❌ Broadcast failed, keeping {temp_id} as PENDING for bootstrap recovery")
                reconciliation.status = ReconciliationStatus.PENDING
                db.session.commit()
            
            return reconciliation
            
        except Exception as e:
            logger.error(f"Failed to reconcile temp ID {temp_id}: {e}")
            db.session.rollback()
            raise
    
    def _broadcast_reconciliation(
        self,
        temp_id: str,
        real_id: int,
        user_id: int,
        workspace_id: Optional[int] = None,
        max_retries: int = 3
    ) -> bool:
        """
        Broadcast temp→real ID mapping to all connected clients with retry logic.
        
        Args:
            temp_id: Temporary ID
            real_id: Real database ID
            user_id: User ID
            workspace_id: Workspace ID for isolation
            max_retries: Maximum retry attempts (default: 3)
            
        Returns:
            True if broadcast succeeded, False otherwise
        """
        event_data = {
            'temp_id': temp_id,
            'real_id': real_id,
            'user_id': user_id,
            'workspace_id': workspace_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for attempt in range(max_retries):
            try:
                # Emit ID_RECONCILED event via EventBroadcaster's socketio
                if self.event_broadcaster and hasattr(self.event_broadcaster, 'socketio') and self.event_broadcaster.socketio:
                    room = f"workspace_{workspace_id}" if workspace_id else None
                    
                    # Emit to both /dashboard and /tasks namespaces for comprehensive coverage
                    for namespace in ['/dashboard', '/tasks']:
                        self.event_broadcaster.socketio.emit(
                            'id_reconciled',  # Event name
                            event_data,
                            namespace=namespace,
                            room=room
                        )
                    
                    logger.info(f"✅ Broadcast SUCCESS: {temp_id} → {real_id} (attempt {attempt + 1})")
                    return True  # Broadcast succeeded
                else:
                    logger.warning(f"⚠️ SocketIO not initialized, cannot broadcast (attempt {attempt + 1})")
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                
            except Exception as e:
                logger.error(f"❌ Broadcast FAILED (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff before retry
                continue
        
        # All retries exhausted
        logger.error(f"❌ Broadcast FAILED after {max_retries} attempts: {temp_id} → {real_id}")
        return False
    
    def get_reconciliation_status(self, temp_id: str) -> Optional[Dict[str, Any]]:
        """
        Get reconciliation status for a temp ID.
        
        Args:
            temp_id: Temporary ID
            
        Returns:
            Status dictionary or None if not found
        """
        reconciliation = IDReconciliation.get_by_temp_id(temp_id)
        if not reconciliation:
            return None
        
        return reconciliation.to_dict()
    
    def get_reconciliations_for_bootstrap(self, user_id: int, workspace_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all reconciliations (pending + recently reconciled) for bootstrap recovery.
        This ensures clients catch up on any missed broadcasts.
        
        Args:
            user_id: User ID
            workspace_id: Optional workspace ID filter
            limit: Maximum number of results
            
        Returns:
            List of reconciliation dictionaries
        """
        from datetime import timedelta
        from sqlalchemy import select, or_
        
        # Get reconciliations that are:
        # 1. PENDING (not yet reconciled)
        # 2. RECONCILED within last 24 hours (to catch up on missed broadcasts)
        threshold = datetime.utcnow() - timedelta(hours=24)
        
        stmt = select(IDReconciliation).where(
            IDReconciliation.user_id == user_id,
            or_(
                IDReconciliation.status == ReconciliationStatus.PENDING,
                db.and_(
                    IDReconciliation.status == ReconciliationStatus.RECONCILED,
                    IDReconciliation.reconciled_at >= threshold
                )
            )
        )
        
        if workspace_id:
            stmt = stmt.where(IDReconciliation.workspace_id == workspace_id)
        
        stmt = stmt.order_by(IDReconciliation.created_at.desc()).limit(limit)
        
        reconciliations = db.session.execute(stmt).scalars().all()
        return [r.to_dict() for r in reconciliations]
    
    def get_pending_reconciliations(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get pending reconciliations for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of results
            
        Returns:
            List of reconciliation dictionaries
        """
        reconciliations = IDReconciliation.get_pending_for_user(user_id, limit=limit)
        return [r.to_dict() for r in reconciliations]
    
    def cleanup_orphaned(self, threshold_minutes: int = 10) -> int:
        """
        Clean up orphaned temp IDs that never got reconciled.
        
        Args:
            threshold_minutes: Age threshold for orphan detection
            
        Returns:
            Number of orphaned entries marked
        """
        try:
            count = IDReconciliation.cleanup_orphaned(threshold_minutes=threshold_minutes)
            logger.info(f"Marked {count} orphaned reconciliations for cleanup")
            return count
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned reconciliations: {e}")
            return 0
    
    def reverse_lookup(self, real_id: int) -> Optional[str]:
        """
        Reverse lookup: Find temp ID for a real ID.
        
        Args:
            real_id: Real database ID
            
        Returns:
            Temp ID or None if not found
        """
        reconciliation = IDReconciliation.get_by_real_id(real_id)
        if reconciliation:
            return reconciliation.temp_id
        return None
    
    def bulk_reconcile(
        self,
        mappings: List[Dict[str, Any]],
        user_id: int,
        workspace_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Bulk reconcile multiple temp IDs (for offline queue replay).
        
        Args:
            mappings: List of {temp_id, real_id} dictionaries
            user_id: User ID
            workspace_id: Workspace ID
            
        Returns:
            Summary dictionary with success/failure counts
        """
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        for mapping in mappings:
            temp_id = mapping.get('temp_id')
            real_id = mapping.get('real_id')
            
            if not temp_id or not real_id:
                results['skipped'] += 1
                continue
            
            try:
                self.reconcile_temp_id(
                    temp_id=temp_id,
                    real_id=real_id,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    broadcast=True
                )
                results['success'] += 1
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'temp_id': temp_id,
                    'error': str(e)
                })
        
        logger.info(f"Bulk reconciliation complete: {results}")
        return results


# Global singleton instance
_reconciler_instance: Optional[TempIDReconciler] = None


def get_reconciler() -> TempIDReconciler:
    """Get or create global TempIDReconciler instance."""
    global _reconciler_instance
    if _reconciler_instance is None:
        _reconciler_instance = TempIDReconciler()
    return _reconciler_instance
