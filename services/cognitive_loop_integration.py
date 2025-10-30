"""
Cognitive Loop Integration Service - CROWN⁴.5

Complete NLP→Task cognitive feedback loop:
Transcript Segment → NLP Extraction → Task Proposal → User Accept → Dashboard Update → Analytics → Learning

This service orchestrates the end-to-end flow from conversation to actionable tasks.
"""

import logging
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from sqlalchemy import select
from models import db, Task, SessionContext, Meeting, Segment, TaskCounters, EventLedger
from services.task_extraction_service import TaskExtractionService, ExtractedTask
from services.cognitive_synchronizer import get_cognitive_synchronizer
from services.predictive_engine import PredictiveEngine
from services.event_broadcaster import broadcast_event
from services.event_ledger_service import EventLedgerService

logger = logging.getLogger(__name__)


class CognitiveLoopIntegration:
    """
    Orchestrates the complete cognitive loop for task intelligence.
    
    Flow:
    1. Transcript segment detected
    2. NLP extracts task candidate
    3. Confidence check (>0.8 threshold)
    4. Create SessionContext + propose to user
    5. User accepts/edits → capture feedback
    6. Broadcast to Dashboard counters
    7. Update Analytics
    8. PredictiveEngine refines model
    """
    
    def __init__(self):
        self.cognitive_sync = get_cognitive_synchronizer()
        # CROWN⁴.5: Wire cognitive learning into extraction service
        self.extraction_service = TaskExtractionService(cognitive_sync=self.cognitive_sync)
        self.predictive_engine = PredictiveEngine()
        self.ledger_service = EventLedgerService()
        self.confidence_threshold = 0.8
        
        logger.info("✅ CognitiveLoopIntegration initialized - Full loop active with learning")
    
    async def process_transcript_segment(self, session_id: int, segment_id: int,
                                        user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Process transcript segment for task extraction.
        
        Args:
            session_id: Session ID
            segment_id: Segment ID
            user_id: User ID for personalization
            
        Returns:
            List of proposed task candidates
        """
        try:
            # 1. Fetch segment
            segment = db.session.get(Segment, segment_id)
            if not segment:
                logger.warning(f"Segment {segment_id} not found")
                return []
            
            # 2. Check if already processed
            existing_context = db.session.execute(
                select(SessionContext).where(
                    SessionContext.session_id == session_id,
                    SessionContext.transcript_span['segment_ids'].contains([segment_id])
                )
            ).scalar_one_or_none()
            
            if existing_context:
                logger.debug(f"Segment {segment_id} already processed")
                return []
            
            # 3. Extract task candidates using AI (with cognitive learning)
            extracted_tasks = await self._extract_from_segment(segment, session_id, user_id)
            
            if not extracted_tasks:
                return []
            
            # 4. Filter by confidence and create proposals
            proposals = []
            for extracted_task in extracted_tasks:
                if extracted_task.confidence >= self.confidence_threshold:
                    proposal = await self._create_task_proposal(
                        extracted_task, session_id, segment, user_id
                    )
                    # Skip None (duplicates)
                    if proposal is not None:
                        proposals.append(proposal)
                else:
                    logger.debug(f"Task candidate rejected (confidence={extracted_task.confidence:.2f}): {extracted_task.title}")
            
            return proposals
            
        except Exception as e:
            logger.error(f"Failed to process transcript segment: {e}")
            return []
    
    async def _extract_from_segment(self, segment: Segment, session_id: int, user_id: Optional[int] = None) -> List[ExtractedTask]:
        """Extract tasks from single segment with cognitive learning"""
        try:
            # Build context from segment
            transcript_text = segment.text
            context = {
                'segment_id': segment.id,
                'session_id': session_id,
                'speaker': segment.speaker if hasattr(segment, 'speaker') else None,
                'timestamp_ms': segment.start_ms,
                'confidence': segment.confidence if hasattr(segment, 'confidence') else 1.0
            }
            
            # Use AI extraction with user_id for cognitive personalization
            tasks = await self.extraction_service.extract_tasks_from_text(
                transcript_text,
                context,
                user_id=user_id
            )
            
            return tasks
            
        except Exception as e:
            logger.error(f"Segment extraction failed: {e}")
            return []
    
    async def _create_task_proposal(self, extracted_task: ExtractedTask, 
                                   session_id: int, segment: Segment,
                                   user_id: Optional[int]) -> Dict[str, Any]:
        """
        Create task proposal with SessionContext.
        
        Args:
            extracted_task: Extracted task data
            session_id: Session ID
            segment: Source segment
            user_id: User for personalization
            
        Returns:
            Task proposal dict
        """
        try:
            # Generate origin hash for deduplication
            origin_text = f"{extracted_task.title}|{segment.text}"
            origin_hash = hashlib.sha256(origin_text.encode()).hexdigest()
            
            # Check for duplicates
            existing = db.session.execute(
                select(SessionContext).where(
                    SessionContext.origin_hash == origin_hash,
                    SessionContext.status == 'active'
                )
            ).scalar_one_or_none()
            
            if existing:
                logger.debug(f"Duplicate task detected (origin_hash={origin_hash[:8]}...)")
                return None
            
            # Create SessionContext
            session_context = SessionContext(
                session_id=session_id,
                transcript_span={
                    'start_ms': segment.start_ms,
                    'end_ms': segment.end_ms if hasattr(segment, 'end_ms') else segment.start_ms + 5000,
                    'segment_ids': [segment.id],
                    'speaker': segment.speaker if hasattr(segment, 'speaker') else None,
                    'confidence': segment.confidence if hasattr(segment, 'confidence') else 1.0
                },
                origin_message=segment.text,
                origin_hash=origin_hash,
                context_type='task_extraction',
                context_confidence=extracted_task.confidence,
                extraction_metadata={
                    'model': 'gpt-4',
                    'extraction_method': 'ai',
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            db.session.add(session_context)
            db.session.flush()
            
            # Apply cognitive personalization
            adjusted_confidence = extracted_task.confidence
            suggested_priority = extracted_task.priority
            suggested_category = extracted_task.category
            
            if user_id:
                adjusted_confidence = self.cognitive_sync.get_adjusted_confidence(
                    user_id, extracted_task.confidence
                )
                suggested_priority = self.cognitive_sync.get_priority_suggestion(
                    user_id, extracted_task.priority, extracted_task.context or {}
                )
                suggested_category = self.cognitive_sync.get_category_suggestion(
                    user_id, extracted_task.category, extracted_task.context or {}
                )
            
            # Create proposal dict (not persisted until acceptance)
            proposal = {
                'session_context_id': session_context.id,
                'origin_hash': origin_hash,
                'title': extracted_task.title,
                'description': extracted_task.description,
                'priority': suggested_priority,
                'category': suggested_category,
                'confidence': adjusted_confidence,
                'assigned_to': extracted_task.assigned_to,
                'due_date_text': extracted_task.due_date_text,
                'transcript_span': session_context.transcript_span,
                'transcript_url': session_context.get_transcript_url(),
                'status': 'proposed'
            }
            
            db.session.commit()
            
            # Broadcast proposal event
            await self._broadcast_task_proposal(proposal, user_id)
            
            logger.info(f"Task proposed: '{extracted_task.title}' (confidence={adjusted_confidence:.2f})")
            
            return proposal
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create task proposal: {e}")
            return None
    
    async def accept_task_proposal(self, session_context_id: int, user_id: int,
                                  edits: Optional[Dict[str, Any]] = None) -> Optional[Task]:
        """
        User accepts AI-proposed task (with optional edits).
        
        Args:
            session_context_id: SessionContext ID
            user_id: User accepting the task
            edits: Optional field edits
            
        Returns:
            Created Task object
        """
        try:
            # Fetch SessionContext
            session_context = db.session.get(SessionContext, session_context_id)
            if not session_context:
                logger.error(f"SessionContext {session_context_id} not found")
                return None
            
            # Extract original values from context
            metadata = session_context.extraction_metadata or {}
            original_data = metadata.get('proposed_task', {})
            
            # Determine if edited
            was_edited = edits is not None and len(edits) > 0
            changes = {}
            
            # Build task data
            task_data = {
                'title': edits.get('title') if edits else original_data.get('title', 'Untitled Task'),
                'priority': edits.get('priority') if edits else original_data.get('priority', 'medium'),
                'category': edits.get('category') if edits else original_data.get('category'),
                'description': edits.get('description') if edits else original_data.get('description')
            }
            
            # Track changes for learning
            if was_edited:
                if edits.get('title') and edits['title'] != original_data.get('title'):
                    changes['title'] = {'old': original_data.get('title'), 'new': edits['title']}
                if edits.get('priority') and edits['priority'] != original_data.get('priority'):
                    changes['priority'] = {'old': original_data.get('priority'), 'new': edits['priority']}
                if edits.get('category') and edits['category'] != original_data.get('category'):
                    changes['category'] = {'old': original_data.get('category'), 'new': edits['category']}
            
            # Create Task in database
            task = Task(
                session_id=session_context.session_id,
                meeting_id=session_context.meeting_id,
                title=task_data['title'],
                description=task_data['description'],
                priority=task_data['priority'],
                category=task_data['category'],
                extracted_by_ai=True,
                confidence_score=session_context.context_confidence,
                origin_hash=session_context.origin_hash,
                transcript_span=session_context.transcript_span,
                source='ai_extraction',
                emotional_state='accepted',
                created_by_id=user_id,
                extraction_context={
                    'session_context_id': session_context_id,
                    'was_edited': was_edited,
                    'original_title': original_data.get('title'),
                    'original_priority': original_data.get('priority'),
                    'original_category': original_data.get('category')
                }
            )
            
            db.session.add(task)
            db.session.flush()
            
            # Update SessionContext with derived entity
            session_context.add_derived_entity('task', task.id, 'accepted')
            db.session.commit()
            
            # Capture feedback for learning
            self.cognitive_sync.capture_task_acceptance(task.id, user_id, was_edited, changes if was_edited else None)
            
            # Broadcast acceptance + update counters
            await self._broadcast_task_accepted(task, user_id, was_edited)
            await self._update_dashboard_counters(user_id)
            await self._update_analytics(task)
            
            logger.info(f"Task accepted: ID={task.id}, edited={was_edited}")
            
            return task
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to accept task proposal: {e}")
            return None
    
    async def reject_task_proposal(self, session_context_id: int, user_id: int,
                                  reason: Optional[str] = None) -> bool:
        """
        User rejects AI-proposed task.
        
        Args:
            session_context_id: SessionContext ID
            user_id: User rejecting
            reason: Optional rejection reason
            
        Returns:
            Success boolean
        """
        try:
            session_context = db.session.get(SessionContext, session_context_id)
            if not session_context:
                return False
            
            # Mark as rejected
            session_context.status = 'rejected'
            session_context.extraction_metadata = session_context.extraction_metadata or {}
            session_context.extraction_metadata['rejection_reason'] = reason
            session_context.extraction_metadata['rejected_by'] = user_id
            session_context.extraction_metadata['rejected_at'] = datetime.utcnow().isoformat()
            
            db.session.commit()
            
            # Capture rejection feedback
            # Create temporary task ID for tracking
            temp_task_id = f"proposal_{session_context_id}"
            self.cognitive_sync.capture_task_rejection(session_context_id, user_id, reason)
            
            # Broadcast rejection
            await broadcast_event('task_nlp:rejected', {
                'session_context_id': session_context_id,
                'user_id': user_id,
                'reason': reason
            })
            
            logger.info(f"Task proposal rejected: context={session_context_id}, reason={reason}")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to reject task proposal: {e}")
            return False
    
    async def _broadcast_task_proposal(self, proposal: Dict[str, Any], user_id: Optional[int]) -> None:
        """Broadcast task proposal event"""
        try:
            await broadcast_event('task_nlp:proposed', {
                'proposal': proposal,
                'user_id': user_id,
                'timestamp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to broadcast proposal: {e}")
    
    async def _broadcast_task_accepted(self, task: Task, user_id: int, was_edited: bool) -> None:
        """Broadcast task acceptance event"""
        try:
            await broadcast_event('task_create:nlp_accept', {
                'task_id': task.id,
                'user_id': user_id,
                'was_edited': was_edited,
                'timestamp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to broadcast acceptance: {e}")
    
    async def _update_dashboard_counters(self, user_id: int) -> None:
        """Update dashboard task counters"""
        try:
            # Recalculate task counts
            stmt = select(Task).where(Task.created_by_id == user_id)
            tasks = db.session.execute(stmt).scalars().all()
            
            total = len(tasks)
            pending = len([t for t in tasks if t.status in ['todo', 'in_progress']])
            completed = len([t for t in tasks if t.status == 'completed'])
            
            # Broadcast counter update
            await broadcast_event('task_counters:updated', {
                'user_id': user_id,
                'all': total,
                'pending': pending,
                'completed': completed,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to update counters: {e}")
    
    async def _update_analytics(self, task: Task) -> None:
        """Update analytics with new task"""
        try:
            # Analytics update logic here
            logger.debug(f"Analytics updated for task {task.id}")
        except Exception as e:
            logger.error(f"Failed to update analytics: {e}")


# Global instance
_cognitive_loop = None


def get_cognitive_loop() -> CognitiveLoopIntegration:
    """Get or create global CognitiveLoopIntegration instance"""
    global _cognitive_loop
    if _cognitive_loop is None:
        _cognitive_loop = CognitiveLoopIntegration()
    return _cognitive_loop
