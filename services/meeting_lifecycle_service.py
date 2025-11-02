"""
Meeting Lifecycle Service
Handles the atomic conversion of completed Sessions into Meetings with Analytics and Tasks.
This is the critical bridge that fixes the broken data pipeline.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select
from models import db
from models.session import Session
from models.meeting import Meeting
from models.analytics import Analytics
from models.task import Task
from models.segment import Segment
from models.participant import Participant

logger = logging.getLogger(__name__)


class MeetingLifecycleService:
    """
    Service that manages the complete lifecycle of converting a transcription session
    into a full meeting with analytics, tasks, and participants.
    
    This ensures data consistency across all dashboard views.
    """
    
    @staticmethod
    def create_meeting_from_session(session_id: int) -> Optional[Meeting]:
        """
        Create a Meeting record from a completed Session.
        This is the critical missing link in the data pipeline.
        
        Args:
            session_id: The completed session ID
            
        Returns:
            Created Meeting instance or None if session not found/invalid
        """
        try:
            # Get session with segments
            session = db.session.get(Session, session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return None
            
            # Skip if already has a meeting
            if session.meeting_id:
                logger.info(f"Session {session_id} already has meeting {session.meeting_id}")
                existing_meeting = db.session.get(Meeting, session.meeting_id)
                return existing_meeting
            
            # 🔒 CROWN¹⁰ Fix: Require workspace_id - no silent fallbacks!
            workspace_id = session.workspace_id
            if not workspace_id:
                error_msg = f"Session {session_id} missing workspace_id - cannot create meeting. Sessions must be created with workspace_id."
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            # Calculate meeting duration from segments
            segments = db.session.scalars(
                select(Segment).where(Segment.session_id == session_id)
            ).all()
            
            duration_minutes = None
            if segments:
                # Find first and last segment with timestamps
                segments_with_time = [s for s in segments if s.start_ms is not None and s.end_ms is not None]
                if segments_with_time:
                    first_segment = min(segments_with_time, key=lambda s: s.start_ms or 0)
                    last_segment = max(segments_with_time, key=lambda s: s.end_ms or 0)
                    if first_segment.start_ms and last_segment.end_ms:
                        duration_ms = last_segment.end_ms - first_segment.start_ms
                        duration_minutes = duration_ms / (1000 * 60)
            
            # Create Meeting record
            meeting = Meeting(
                title=session.title or "Untitled Meeting",
                description=f"Transcribed meeting from {session.started_at.strftime('%B %d, %Y at %I:%M %p')}",
                meeting_type="general",
                status="completed",  # Session is already completed
                organizer_id=session.user_id or 1,  # Default to user 1 if no user
                workspace_id=workspace_id,
                actual_start=session.started_at,
                actual_end=session.completed_at,
                recording_enabled=True,
                transcription_enabled=True,
                ai_insights_enabled=True,
                is_private=False
            )
            
            db.session.add(meeting)
            db.session.flush()  # Get meeting.id without committing
            
            # Link session to meeting
            session.meeting_id = meeting.id
            
            # Create basic Analytics record
            analytics = Analytics(
                meeting_id=meeting.id,
                total_duration_minutes=duration_minutes,
                participant_count=len(segments) if segments else 1,  # Rough estimate
                word_count=sum(len(s.text.split()) if s.text else 0 for s in segments),
                analysis_status="pending",  # Will be processed later
                created_at=datetime.utcnow()
            )
            
            db.session.add(analytics)
            
            # Commit atomically - meeting + analytics + session link
            db.session.commit()
            
            logger.info(f"✅ Created Meeting {meeting.id} from Session {session_id}")
            
            # Broadcast session_update:created event via WebSocket
            try:
                from services.event_broadcaster import event_broadcaster
                
                meeting_data = {
                    'id': meeting.id,
                    'title': meeting.title,
                    'status': meeting.status,
                    'actual_start': meeting.actual_start.isoformat() if meeting.actual_start else None,
                    'actual_end': meeting.actual_end.isoformat() if meeting.actual_end else None,
                    'workspace_id': meeting.workspace_id,
                    'session_id': session_id
                }
                
                event_broadcaster.broadcast_session_created(
                    session_id=session_id,
                    meeting_data=meeting_data,
                    workspace_id=workspace_id
                )
                
                logger.info(f"📡 Broadcast session_update:created for Meeting {meeting.id}")
                
                # Also broadcast dashboard_refresh to update statistics
                try:
                    stats = MeetingLifecycleService.get_meeting_statistics(workspace_id, days=365)
                    event_broadcaster.broadcast_dashboard_refresh(
                        workspace_id=workspace_id,
                        stats={
                            'total_meetings': stats['total_meetings'],
                            'total_tasks': stats['total_tasks'],
                            'hours_saved': round(stats['total_duration_hours'], 1)
                        }
                    )
                    logger.info(f"📡 Broadcast dashboard_refresh for workspace {workspace_id}")
                except Exception as de:
                    logger.warning(f"Failed to broadcast dashboard_refresh: {de}")
                    
            except Exception as e:
                logger.warning(f"Failed to broadcast session_created event: {e}")
            
            # Trigger async task extraction using existing service
            try:
                from app import socketio
                from services.task_extraction_service import task_extraction_service
                
                # Schedule background task using SocketIO
                def extract_tasks_background():
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            task_extraction_service.process_meeting_for_tasks(meeting.id)
                        )
                        logger.info(f"Task extraction result: {result}")
                    finally:
                        loop.close()
                
                socketio.start_background_task(extract_tasks_background)
                logger.info(f"Scheduled task extraction for meeting {meeting.id}")
            except Exception as e:
                logger.warning(f"Failed to trigger task extraction: {e}")
            
            return meeting
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to create meeting from session {session_id}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def finalize_session_with_meeting(session_id: int) -> Dict[str, Any]:
        """
        Complete wrapper that finalizes session AND creates meeting atomically.
        This should be called instead of SessionService.complete_session().
        
        Args:
            session_id: Session to finalize
            
        Returns:
            Result dictionary with meeting_id and status
        """
        try:
            # Mark session as completed
            session = db.session.get(Session, session_id)
            if not session:
                return {'success': False, 'error': 'Session not found'}
            
            if session.status != 'completed':
                session.status = 'completed'
                session.completed_at = datetime.utcnow()
                db.session.commit()
            
            # Create meeting from session
            meeting = MeetingLifecycleService.create_meeting_from_session(session_id)
            
            if meeting:
                # Emit WebSocket event for real-time dashboard update
                try:
                    from app import socketio
                    socketio.emit('session_update:created', {
                        'session_id': session.external_id,
                        'meeting_id': meeting.id,
                        'title': meeting.title,
                        'status': 'completed',
                        'timestamp': datetime.utcnow().isoformat()
                    }, namespace='/dashboard')
                    logger.info(f"📡 Broadcast session_update:created for meeting {meeting.id}")
                except Exception as e:
                    logger.warning(f"Failed to broadcast WebSocket event: {e}")
                
                return {
                    'success': True,
                    'session_id': session_id,
                    'meeting_id': meeting.id,
                    'message': 'Session finalized and meeting created'
                }
            else:
                return {
                    'success': False,
                    'session_id': session_id,
                    'error': 'Failed to create meeting from session'
                }
                
        except Exception as e:
            logger.error(f"Error finalizing session {session_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_meeting_statistics(workspace_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get accurate meeting statistics for a workspace.
        This replaces the broken dashboard queries.
        
        Args:
            workspace_id: Workspace to query
            days: Number of days to look back
            
        Returns:
            Dictionary with meeting counts and statistics
        """
        from datetime import timedelta
        from sqlalchemy import func
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            # Total meetings in workspace
            total_meetings = db.session.scalar(
                select(func.count()).select_from(Meeting).where(
                    Meeting.workspace_id == workspace_id
                )
            ) or 0
            
            # Recent meetings
            recent_meetings = db.session.scalar(
                select(func.count()).select_from(Meeting).where(
                    Meeting.workspace_id == workspace_id,
                    Meeting.created_at >= cutoff_date
                )
            ) or 0
            
            # Completed meetings
            completed_meetings = db.session.scalar(
                select(func.count()).select_from(Meeting).where(
                    Meeting.workspace_id == workspace_id,
                    Meeting.status == 'completed'
                )
            ) or 0
            
            # Total tasks from meetings
            meeting_ids = db.session.scalars(
                select(Meeting.id).where(Meeting.workspace_id == workspace_id)
            ).all()
            
            if meeting_ids:
                total_tasks = db.session.scalar(
                    select(func.count()).select_from(Task).where(
                        Task.meeting_id.in_(meeting_ids)
                    )
                ) or 0
                
                completed_tasks = db.session.scalar(
                    select(func.count()).select_from(Task).where(
                        Task.meeting_id.in_(meeting_ids),
                        Task.status == 'completed'
                    )
                ) or 0
            else:
                total_tasks = 0
                completed_tasks = 0
            
            return {
                'total_meetings': total_meetings,
                'recent_meetings': recent_meetings,
                'completed_meetings': completed_meetings,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'task_completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting meeting statistics: {e}")
            return {
                'total_meetings': 0,
                'recent_meetings': 0,
                'completed_meetings': 0,
                'total_tasks': 0,
                'completed_tasks': 0,
                'task_completion_rate': 0
            }
