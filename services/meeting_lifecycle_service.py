"""
Meeting Lifecycle Service
Handles the atomic conversion of completed Sessions into Meetings with Analytics and Tasks.
This is the critical bridge that fixes the broken data pipeline.
"""

import logging
import re
from typing import Optional, Dict, Any, List, Sequence
from datetime import datetime
from dataclasses import dataclass
from sqlalchemy import select, update
from models import db
from models.session import Session
from models.meeting import Meeting
from models.analytics import Analytics
from models.task import Task
from models.segment import Segment
from models.participant import Participant

logger = logging.getLogger(__name__)

def _build_transcript_for_title(segments) -> str:
    """Build transcript text from segments for title generation."""
    if not segments:
        return ""
    final_segments = [s for s in segments if s.kind == 'final' and s.text]
    if not final_segments:
        final_segments = [s for s in segments if s.text]
    sorted_segments = sorted(final_segments, key=lambda s: s.start_ms or 0)
    return " ".join(s.text.strip() for s in sorted_segments[:50] if s.text)


@dataclass
class ParticipantMetrics:
    """DTO for speaker participation metrics extracted from transcripts."""
    speaker_id: str
    display_name: str
    talk_time_seconds: float
    word_count: int
    question_count: int
    segment_count: int
    confidence_score: float = 0.85


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
            
            # 🔒 CROWN¹⁰ Fix: Backfill meeting_id on existing tasks
            # Tasks created during post-processing have session_id but no meeting_id
            # Update them now that the meeting exists
            task_update_count = db.session.execute(
                update(Task).where(Task.session_id == session_id).values(meeting_id=meeting.id)
            ).rowcount
            
            if task_update_count > 0:
                logger.info(f"✅ Updated {task_update_count} tasks with meeting_id={meeting.id}")
            
            # Extract and persist participant data from segments
            participant_metrics = MeetingLifecycleService._extract_participant_metrics(segments, duration_minutes)
            participant_count = len(participant_metrics) if participant_metrics else 1
            
            if participant_metrics:
                MeetingLifecycleService._persist_participants(meeting.id, participant_metrics, duration_minutes)
                logger.info(f"✅ Created {len(participant_metrics)} participant records for meeting {meeting.id}")
            
            # Create Analytics record with accurate participant count
            analytics = Analytics(
                meeting_id=meeting.id,
                total_duration_minutes=duration_minutes,
                participant_count=participant_count,
                unique_speakers=participant_count,
                word_count=sum(len(s.text.split()) if s.text else 0 for s in segments),
                analysis_status="pending",  # Will be processed later
                created_at=datetime.utcnow()
            )
            
            db.session.add(analytics)
            
            # Commit atomically - meeting + analytics + session link + participants
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
            
            # Trigger async title generation + task extraction using existing services
            try:
                from app import socketio
                from services.task_extraction_service import task_extraction_service
                from services.meeting_title_generator import get_title_generator
                
                # Build transcript for title generation
                transcript_text = _build_transcript_for_title(segments)
                meeting_id_for_bg = meeting.id
                session_id_for_bg = session_id  # Capture session_id for background task
                session_title = session.title
                workspace_id_for_bg = workspace_id
                
                # Schedule background task using SocketIO
                def enrich_meeting_background():
                    import asyncio
                    from app import app, db as bg_db
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # Generate AI title if current title is placeholder
                        title_generator = get_title_generator()
                        if title_generator.is_placeholder_title(session_title):
                            generated_title = loop.run_until_complete(
                                title_generator.generate_title(transcript_text)
                            )
                            if generated_title:
                                with app.app_context():
                                    # Update BOTH Meeting and Session titles for consistency
                                    bg_meeting = bg_db.session.get(Meeting, meeting_id_for_bg)
                                    bg_session = bg_db.session.get(Session, session_id_for_bg)
                                    
                                    if bg_meeting:
                                        bg_meeting.title = generated_title
                                    if bg_session:
                                        bg_session.title = generated_title
                                    
                                    bg_db.session.commit()
                                    logger.info(f"✅ AI-generated title synced to meeting {meeting_id_for_bg} and session {session_id_for_bg}: {generated_title}")
                                        
                                    # Broadcast title update
                                    try:
                                        from services.event_broadcaster import event_broadcaster
                                        event_broadcaster.broadcast_meeting_updated(
                                            meeting_id=meeting_id_for_bg,
                                            changes={'title': generated_title},
                                            workspace_id=workspace_id_for_bg
                                        )
                                    except Exception as be:
                                        logger.warning(f"Failed to broadcast title update: {be}")
                        
                        # Extract tasks
                        result = loop.run_until_complete(
                            task_extraction_service.process_meeting_for_tasks(meeting_id_for_bg)
                        )
                        logger.info(f"Task extraction result: {result}")
                    finally:
                        loop.close()
                
                socketio.start_background_task(enrich_meeting_background)
                logger.info(f"Scheduled title generation + task extraction for meeting {meeting.id}")
            except Exception as e:
                logger.warning(f"Failed to trigger meeting enrichment: {e}")
            
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
            
            # Calculate total duration hours from linked sessions
            # Sessions have total_duration in seconds, which is more accurate for live transcriptions
            from models.session import Session
            
            total_duration_seconds = 0
            if meeting_ids:
                sessions = db.session.scalars(
                    select(Session).where(Session.meeting_id.in_(meeting_ids))
                ).all()
                
                logger.debug(f"📊 Found {len(sessions)} sessions for {len(meeting_ids)} meetings")
                for session in sessions:
                    if session.total_duration:
                        logger.debug(f"  Session {session.external_id}: {session.total_duration} seconds")
                        total_duration_seconds += session.total_duration
            
            total_duration_minutes = round(total_duration_seconds / 60, 1)
            logger.debug(f"📊 Total duration: {total_duration_seconds} seconds = {total_duration_minutes} minutes")
            
            return {
                'total_meetings': total_meetings,
                'recent_meetings': recent_meetings,
                'completed_meetings': completed_meetings,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'task_completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
                'total_duration_minutes': total_duration_minutes
            }
            
        except Exception as e:
            logger.error(f"Error getting meeting statistics: {e}")
            return {
                'total_meetings': 0,
                'recent_meetings': 0,
                'completed_meetings': 0,
                'total_tasks': 0,
                'completed_tasks': 0,
                'task_completion_rate': 0,
                'total_duration_minutes': 0
            }
    
    @staticmethod
    def _extract_participant_metrics(segments: Sequence[Segment], duration_minutes: Optional[float]) -> List[ParticipantMetrics]:
        """
        Extract participant metrics from transcript segments.
        Analyzes text patterns to identify speakers and calculate their participation.
        
        Args:
            segments: List of transcript segments
            duration_minutes: Total meeting duration in minutes
            
        Returns:
            List of ParticipantMetrics DTOs
        """
        if not segments:
            return []
        
        speaker_data: Dict[str, Dict[str, Any]] = {}
        
        # Common speaker label patterns in transcripts
        speaker_patterns = [
            r'^(Speaker\s*\d+)\s*[:\-]',  # "Speaker 1:", "Speaker 2:"
            r'^\[(Speaker\s*\d+)\]',       # "[Speaker 1]"
            r'^(Participant\s*\d+)\s*[:\-]',  # "Participant 1:"
            r'^\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\]',  # "[John]", "[Jane Doe]"
        ]
        
        for segment in segments:
            if not segment.text or segment.kind != 'final':
                continue
            
            text = segment.text.strip()
            speaker_id = None
            
            # Try to extract speaker from text patterns
            for pattern in speaker_patterns:
                match = re.match(pattern, text)
                if match:
                    speaker_id = match.group(1).strip()
                    break
            
            # Default speaker if no pattern matched
            if not speaker_id:
                speaker_id = "Primary Speaker"
            
            # Normalize speaker ID
            speaker_id = speaker_id.lower().replace(' ', '_')
            
            # Initialize speaker data if new
            if speaker_id not in speaker_data:
                speaker_data[speaker_id] = {
                    'display_name': speaker_id.replace('_', ' ').title(),
                    'word_count': 0,
                    'segment_count': 0,
                    'talk_time_ms': 0,
                    'question_count': 0
                }
            
            # Update metrics
            words = len(text.split())
            speaker_data[speaker_id]['word_count'] += words
            speaker_data[speaker_id]['segment_count'] += 1
            
            # Count questions
            if '?' in text:
                speaker_data[speaker_id]['question_count'] += text.count('?')
            
            # Calculate talk time from segment duration if available
            if segment.start_ms is not None and segment.end_ms is not None:
                speaker_data[speaker_id]['talk_time_ms'] += (segment.end_ms - segment.start_ms)
        
        # Convert to ParticipantMetrics DTOs
        metrics = []
        total_words = sum(s['word_count'] for s in speaker_data.values())
        
        for speaker_id, data in speaker_data.items():
            # Estimate talk time from word count if not available from timestamps
            if data['talk_time_ms'] > 0:
                talk_time_seconds = data['talk_time_ms'] / 1000
            elif duration_minutes and total_words > 0:
                # Estimate based on word proportion of meeting duration
                word_proportion = data['word_count'] / total_words
                talk_time_seconds = word_proportion * duration_minutes * 60
            else:
                # Rough estimate: 150 words per minute speaking rate
                talk_time_seconds = (data['word_count'] / 150) * 60
            
            metrics.append(ParticipantMetrics(
                speaker_id=speaker_id,
                display_name=data['display_name'],
                talk_time_seconds=talk_time_seconds,
                word_count=data['word_count'],
                question_count=data['question_count'],
                segment_count=data['segment_count'],
                confidence_score=0.85
            ))
        
        logger.info(f"📊 Extracted metrics for {len(metrics)} participants from {len(segments)} segments")
        return metrics
    
    @staticmethod
    def _persist_participants(meeting_id: int, metrics: List[ParticipantMetrics], duration_minutes: Optional[float]) -> List[Participant]:
        """
        Persist participant metrics to the database.
        
        Args:
            meeting_id: The meeting to associate participants with
            metrics: List of ParticipantMetrics DTOs
            duration_minutes: Total meeting duration for calculating percentages
            
        Returns:
            List of created Participant records
        """
        participants = []
        total_talk_time = sum(m.talk_time_seconds for m in metrics)
        
        for i, metric in enumerate(metrics):
            # Calculate participation percentage
            if total_talk_time > 0:
                participation_pct = (metric.talk_time_seconds / total_talk_time) * 100
            elif duration_minutes and duration_minutes > 0:
                participation_pct = (metric.talk_time_seconds / (duration_minutes * 60)) * 100
            else:
                participation_pct = 100 / len(metrics) if metrics else 0
            
            participant = Participant(
                meeting_id=meeting_id,
                name=metric.display_name,
                speaker_id=metric.speaker_id,
                role='organizer' if i == 0 else 'participant',
                talk_time_seconds=metric.talk_time_seconds,
                word_count=metric.word_count,
                question_count=metric.question_count,
                confidence_score=metric.confidence_score,
                participation_percentage=min(100.0, participation_pct),
                is_present=True,
                joined_at=datetime.utcnow()
            )
            
            db.session.add(participant)
            participants.append(participant)
        
        logger.info(f"💾 Persisted {len(participants)} participants for meeting {meeting_id}")
        return participants
    
    @staticmethod
    def backfill_participants_for_meeting(meeting_id: int) -> Dict[str, Any]:
        """
        Backfill participant data for an existing meeting that has no participants.
        Used to populate historical meetings with participation data.
        
        Args:
            meeting_id: The meeting to backfill
            
        Returns:
            Result dictionary with status and count
        """
        try:
            meeting = db.session.get(Meeting, meeting_id)
            if not meeting:
                return {'success': False, 'error': 'Meeting not found'}
            
            # Check if participants already exist
            existing_count = db.session.scalar(
                select(db.func.count()).select_from(Participant).where(
                    Participant.meeting_id == meeting_id
                )
            )
            
            if existing_count and existing_count > 0:
                return {'success': True, 'message': f'Meeting already has {existing_count} participants', 'count': existing_count}
            
            # Find linked session
            session = db.session.scalar(
                select(Session).where(Session.meeting_id == meeting_id)
            )
            
            if not session:
                return {'success': False, 'error': 'No linked session found for meeting'}
            
            # Get segments
            segments = db.session.scalars(
                select(Segment).where(Segment.session_id == session.id)
            ).all()
            
            if not segments:
                return {'success': False, 'error': 'No segments found for session'}
            
            # Calculate duration
            duration_minutes = None
            segments_with_time = [s for s in segments if s.start_ms is not None and s.end_ms is not None]
            if segments_with_time:
                first = min(segments_with_time, key=lambda s: s.start_ms or 0)
                last = max(segments_with_time, key=lambda s: s.end_ms or 0)
                if first.start_ms and last.end_ms:
                    duration_minutes = (last.end_ms - first.start_ms) / (1000 * 60)
            
            # Extract and persist
            metrics = MeetingLifecycleService._extract_participant_metrics(list(segments), duration_minutes)
            if metrics:
                MeetingLifecycleService._persist_participants(meeting_id, metrics, duration_minutes)
                db.session.commit()
                return {'success': True, 'message': f'Created {len(metrics)} participants', 'count': len(metrics)}
            else:
                return {'success': False, 'error': 'No participant data could be extracted'}
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error backfilling participants for meeting {meeting_id}: {e}")
            return {'success': False, 'error': str(e)}
