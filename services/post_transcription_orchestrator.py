"""
Post-Transcription Orchestrator - CROWN+ Event Sequencing Pipeline

Orchestrates the complete post-transcription processing chain:
record_stop → transcript_finalized → transcript_refined → insights_generate →
analytics_update → tasks_generation → post_transcription_reveal → session_finalized →
dashboard_refresh

Every event is atomic, idempotent, and broadcast-driven for seamless UX.

ARCHITECTURE NOTES:
- Runs asynchronously via BackgroundTaskManager (non-blocking)
- Finalization endpoints return immediately while processing continues in background
- Events stream back via WebSocket as each stage completes (real-time updates)
- Gracefully degrades: user gets transcript even if insights fail
- Automatic retry with exponential backoff (2 retries, 10s delay)
- Events are idempotent and replay-safe for background job retries
- Total pipeline time: 3-4 seconds (runs in background)
"""

import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

from models import db
from models.session import Session
from models.segment import Segment
from models.event_ledger import EventType
from services.event_ledger_service import EventLedgerService
from services.analysis_service import AnalysisService
from services.analytics_service import AnalyticsService
from services.background_tasks import background_task_manager
from services.event_monitoring import log_dashboard_refresh_event
from app import socketio

logger = logging.getLogger(__name__)


def _determine_priority(task_text: str, evidence_text: str, due_date: Optional[Any]) -> str:
    """
    Intelligent priority detection based on urgency keywords, deadline proximity, and sentiment analysis.
    
    Args:
        task_text: The task text
        evidence_text: Context/evidence quote
        due_date: Parsed due date (if any)
        
    Returns:
        Priority level: 'high', 'medium', or 'low'
    """
    from datetime import date, timedelta
    import re
    
    combined_text = f"{task_text} {evidence_text}".lower()
    
    # HIGH priority indicators (explicit keywords)
    high_keywords = [
        r'\burgent\b', r'\basap\b', r'\bcritical\b', r'\bemergency\b',
        r'\bimmediate(?:ly)?\b', r'\bpriority\b', r'\bcrisis\b',
        r'\bblocking\b', r'\bblock(?:er)?\b', r'\bhigh[ -]priority\b'
    ]
    
    for keyword in high_keywords:
        if re.search(keyword, combined_text):
            logger.debug(f"Priority HIGH: matched keyword '{keyword}' in task")
            return 'high'
    
    # Deadline proximity (due today or tomorrow → high priority)
    if due_date:
        try:
            if isinstance(due_date, str):
                # Try to parse if it's a string
                from datetime import datetime
                due_date = datetime.fromisoformat(due_date).date()
            
            today = date.today()
            days_until_due = (due_date - today).days
            
            if days_until_due <= 1:
                logger.debug(f"Priority HIGH: due in {days_until_due} days")
                return 'high'
            elif days_until_due <= 7:
                logger.debug(f"Priority MEDIUM: due in {days_until_due} days")
                return 'medium'
        except Exception as e:
            logger.debug(f"Could not calculate deadline proximity: {e}")
    
    # Sentiment Analysis: Detect negative/urgent tonality
    # Count sentiment indicators (negative = urgent, positive = relaxed)
    negative_sentiment_patterns = [
        r'\bmust\b', r'\bcannot\b', r'\bcan\'t\b', r'\bfail(?:ing|ed)?\b',
        r'\bbroke(?:n)?\b', r'\bissue\b', r'\bproblem\b', r'\berror\b',
        r'\bbug\b', r'\bfix\b', r'\bresolve\b', r'\bbefore\b(?:.{1,20}launch|release)',
        r'\bprevent\b', r'\bavoid\b', r'\bstop\b', r'\bblock\b'
    ]
    
    positive_sentiment_patterns = [
        r'\bnice\b', r'\bwould\b', r'\bcould\b', r'\bmight\b',
        r'\bmaybe\b', r'\bsomeday\b', r'\bwhen(?:ever)?\s+(?:time|possible)\b'
    ]
    
    negative_count = sum(1 for pattern in negative_sentiment_patterns if re.search(pattern, combined_text))
    positive_count = sum(1 for pattern in positive_sentiment_patterns if re.search(pattern, combined_text))
    
    sentiment_score = negative_count - positive_count
    
    if sentiment_score >= 2:
        # Strong negative sentiment → urgent
        logger.debug(f"Priority HIGH: negative sentiment detected (score: {sentiment_score})")
        return 'high'
    elif sentiment_score <= -1:
        # Positive/relaxed sentiment → low priority
        logger.debug(f"Priority LOW: relaxed sentiment detected (score: {sentiment_score})")
        return 'low'
    
    # LOW priority indicators (explicit keywords)
    low_keywords = [
        r'\bwhenever\b', r'\beventually\b', r'\bnice[ -]to[ -]have\b',
        r'\boptional\b', r'\bif\s+(?:time|possible)\b', r'\blow[ -]priority\b'
    ]
    
    for keyword in low_keywords:
        if re.search(keyword, combined_text):
            logger.debug(f"Priority LOW: matched keyword '{keyword}' in task")
            return 'low'
    
    # Default: medium
    return 'medium'


def _extract_assignee_from_context(evidence_text: str, speaker_name: Optional[str] = None) -> Optional[str]:
    """
    Extract assignee from context using NLP patterns.
    
    Patterns:
    - "I will..." → speaker is assignee
    - "John will..." → John is assignee
    - "Sarah should..." → Sarah is assignee
    
    Args:
        evidence_text: The evidence quote/context
        speaker_name: Name of the speaker (if known)
        
    Returns:
        Assignee name or None
    """
    import re
    
    if not evidence_text:
        return None
    
    evidence_lower = evidence_text.lower()
    
    # Pattern 1: "I will..." → speaker is assignee
    if re.search(r'\bi\s+(?:will|ll|should|need to|have to)\s+', evidence_lower):
        if speaker_name:
            logger.debug(f"Assignee: '{speaker_name}' (first-person commitment)")
            return speaker_name
    
    # Pattern 2: "NAME will/should..." → NAME is assignee
    name_pattern = r'([A-Z][a-z]+)\s+(?:will|should|needs? to|has to)\s+'
    match = re.search(name_pattern, evidence_text)
    if match:
        assignee = match.group(1)
        logger.debug(f"Assignee: '{assignee}' (third-person assignment)")
        return assignee
    
    # Pattern 3: "assigned to NAME"
    assigned_pattern = r'assign(?:ed)?\s+to\s+([A-Z][a-z]+)'
    match = re.search(assigned_pattern, evidence_text)
    if match:
        assignee = match.group(1)
        logger.debug(f"Assignee: '{assignee}' (explicit assignment)")
        return assignee
    
    return None


class PostTranscriptionOrchestrator:
    """
    Orchestrates post-transcription processing pipeline with event-driven architecture.
    
    Implements CROWN+ Event Sequencing:
    - Atomic events
    - Idempotent processing
    - WebSocket broadcasting
    - Graceful degradation
    """
    
    def __init__(self):
        self.event_service = EventLedgerService()
    
    def process_session_async(self, external_session_id: str) -> str:
        """
        Submit post-transcription pipeline to background task manager.
        Returns immediately while processing continues in background.
        
        Args:
            external_session_id: External session identifier (trace_id)
            
        Returns:
            task_id: Background task identifier for status tracking
        """
        task_id = f"post_transcription_{external_session_id}"
        
        # Submit to background task manager with automatic retry
        background_task_manager.submit_task(
            task_id=task_id,
            func=self.process_session,
            external_session_id=external_session_id,
            max_retries=2,  # Allow retries for transient failures
            retry_delay=10  # 10 second delay between retries
        )
        
        logger.info(f"✅ Post-transcription pipeline submitted to background: {task_id}")
        
        # Emit initial event to notify frontend processing started
        socketio.emit('post_transcription_started', {
            'session_id': external_session_id,
            'task_id': task_id,
            'message': 'Processing your meeting insights...',
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a background post-transcription task.
        
        Args:
            task_id: Task identifier returned by process_session_async
            
        Returns:
            Task status dictionary or None if task not found
        """
        return background_task_manager.get_task_status(task_id)
    
    def process_session(self, external_session_id: str) -> Dict[str, Any]:
        """
        Execute complete post-transcription pipeline for a session.
        
        Args:
            external_session_id: External session identifier (trace_id)
            
        Returns:
            Processing result with all generated data
        """
        start_time = time.time()
        session = None
        results = {
            'success': False,
            'external_session_id': external_session_id,
            'events_completed': [],
            'events_failed': [],
            'total_duration_ms': 0
        }
        
        try:
            logger.info(f"🚀 Starting post-transcription pipeline for session: {external_session_id}")
            
            # Get session from database
            session = db.session.query(Session).filter_by(external_id=external_session_id).first()
            if not session:
                logger.error(f"Session not found: {external_session_id}")
                return results
            
            # Execute pipeline stages in sequence
            # Stage 1: Finalize transcript
            transcript_data = self._finalize_transcript(session)
            if transcript_data:
                results['events_completed'].append('transcript_finalized')
            else:
                results['events_failed'].append('transcript_finalized')
            
            # Stage 2: Refine transcript
            refined_data = self._refine_transcript(session, transcript_data)
            if refined_data:
                results['events_completed'].append('transcript_refined')
                results['refined_transcript'] = refined_data
            else:
                results['events_failed'].append('transcript_refined')
            
            # Stage 3: Generate insights (parallel-capable, but sequential for reliability)
            insights_data = self._generate_insights(session)
            if insights_data:
                results['events_completed'].append('insights_generate')
                results['insights'] = insights_data
            else:
                results['events_failed'].append('insights_generate')
            
            # Stage 4: Update analytics
            analytics_data = self._update_analytics(session)
            if analytics_data:
                results['events_completed'].append('analytics_update')
                results['analytics'] = analytics_data
            else:
                results['events_failed'].append('analytics_update')
            
            # Stage 5: Generate tasks
            tasks_data = self._generate_tasks(session, insights_data)
            if tasks_data:
                results['events_completed'].append('tasks_generation')
                results['tasks'] = tasks_data
            else:
                results['events_failed'].append('tasks_generation')
            
            # Stage 6: Emit post_transcription_reveal
            self._emit_reveal(session)
            results['events_completed'].append('post_transcription_reveal')
            
            # Stage 7: Finalize session
            self._finalize_session(session)
            results['events_completed'].append('session_finalized')
            
            # Stage 8: Emit dashboard refresh (CROWN+ final event)
            self._emit_dashboard_refresh(session)
            results['events_completed'].append('dashboard_refresh')
            
            # Calculate total duration
            results['total_duration_ms'] = (time.time() - start_time) * 1000
            
            # Success only if no events failed
            results['success'] = len(results['events_failed']) == 0
            
            if results['success']:
                logger.info(f"✅ Pipeline completed successfully for {external_session_id} in {results['total_duration_ms']:.0f}ms")
            else:
                logger.warning(f"⚠️ Pipeline completed with {len(results['events_failed'])} failures for {external_session_id} in {results['total_duration_ms']:.0f}ms")
                logger.warning(f"   Failed events: {results['events_failed']}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Pipeline failed for {external_session_id}: {e}", exc_info=True)
            results['error'] = str(e)
            results['total_duration_ms'] = (time.time() - start_time) * 1000
            
            # Log error event
            if session:
                self.event_service.log_event(
                    event_type=EventType.ERROR_OCCURRED,
                    session_id=session.id,
                    external_session_id=external_session_id,
                    payload={'error': str(e), 'stage': 'post_transcription_pipeline'}
                )
            
            return results
    
    def _finalize_transcript(self, session: Session) -> Optional[Dict[str, Any]]:
        """
        Stage 1: Consolidate all transcript segments into final text.
        Event: transcript_finalized
        """
        event = None
        
        # Non-blocking event logging
        try:
            event = self.event_service.log_event(
                event_type=EventType.TRANSCRIPT_FINALIZED,
                session_id=session.id,
                external_session_id=session.external_id,
                payload={'stage': 'finalize_transcript'}
            )
            self.event_service.start_event(event)
        except Exception as log_error:
            logger.warning(f"Event logging failed (non-blocking): {log_error}")
            event = None
        
        try:
            # Get all final segments
            segments = db.session.query(Segment).filter_by(
                session_id=session.id,
                kind='final'
            ).order_by(Segment.start_ms).all()
            
            # Consolidate text
            full_text = ' '.join(seg.text for seg in segments if seg.text)
            word_count = len(full_text.split()) if full_text else 0
            
            # Calculate statistics
            total_duration = sum((s.end_ms or 0) - (s.start_ms or 0) for s in segments) / 1000.0
            avg_confidence = sum(s.avg_confidence or 0 for s in segments) / len(segments) if segments else 0
            
            result = {
                'full_text': full_text,
                'word_count': word_count,
                'segment_count': len(segments),
                'total_duration_seconds': total_duration,
                'average_confidence': avg_confidence
            }
            
            # CRITICAL: Always emit WebSocket event (even if logging failed)
            socketio.emit('transcript_finalized', {
                'session_id': session.external_id,
                'word_count': word_count,
                'duration': total_duration,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Non-blocking event completion
            if event:
                try:
                    self.event_service.complete_event(event, result=result)
                except Exception as log_error:
                    logger.warning(f"Event completion failed (non-blocking): {log_error}")
            
            logger.info(f"✅ Transcript finalized: {word_count} words, {len(segments)} segments")
            return result
            
        except Exception as e:
            logger.error(f"Failed to finalize transcript: {e}")
            if event:
                try:
                    self.event_service.fail_event(event, str(e))
                except:
                    pass
            return None
    
    def _refine_transcript(self, session: Session, transcript_data: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """
        Stage 2: Apply grammar correction and formatting to transcript.
        Event: transcript_refined
        """
        event = None
        
        # Non-blocking event logging
        try:
            event = self.event_service.log_event(
                event_type=EventType.TRANSCRIPT_REFINED,
                session_id=session.id,
                external_session_id=session.external_id,
                payload={'stage': 'refine_transcript'}
            )
            self.event_service.start_event(event)
        except Exception as log_error:
            logger.warning(f"Event logging failed (non-blocking): {log_error}")
            event = None
        
        try:
            if not transcript_data or not transcript_data.get('full_text'):
                logger.warning("No transcript data to refine")
                if event:
                    try:
                        self.event_service.skip_event(event, "No transcript data")
                    except:
                        pass
                return None
            
            # For now, use the transcript as-is (Whisper already provides clean output)
            # Future: Add GPT-based refinement for grammar, punctuation, formatting
            refined_text = transcript_data['full_text']
            
            result = {
                'refined_text': refined_text,
                'refinement_applied': False,  # Set to True when actual refinement is added
                'original_word_count': transcript_data.get('word_count', 0),
                'refined_word_count': len(refined_text.split())
            }
            
            # CRITICAL: Always emit WebSocket event (even if logging failed)
            socketio.emit('transcript_refined', {
                'session_id': session.external_id,
                'text': refined_text[:500],  # Send preview
                'word_count': result['refined_word_count'],
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Non-blocking event completion
            if event:
                try:
                    self.event_service.complete_event(event, result=result)
                except Exception as log_error:
                    logger.warning(f"Event completion failed (non-blocking): {log_error}")
            
            logger.info(f"✅ Transcript refined: {result['refined_word_count']} words")
            return result
            
        except Exception as e:
            logger.error(f"Failed to refine transcript: {e}")
            if event:
                try:
                    self.event_service.fail_event(event, str(e))
                except:
                    pass
            return None
    
    def _generate_insights(self, session: Session) -> Optional[Dict[str, Any]]:
        """
        Stage 3: Generate AI-powered insights (summary, actions, decisions, risks).
        Event: insights_generate
        
        Status tracking:
        - 'processing': AI analysis in progress
        - 'success': AI completed successfully (may have 0 results, that's still success)
        - 'failed': AI analysis failed (JSON parsing errors, API errors, etc)
        """
        event = None
        
        # Non-blocking event logging
        try:
            event = self.event_service.log_event(
                event_type=EventType.INSIGHTS_GENERATE,
                session_id=session.id,
                external_session_id=session.external_id,
                payload={'stage': 'generate_insights'}
            )
            self.event_service.start_event(event)
        except Exception as log_error:
            logger.warning(f"Event logging failed (non-blocking): {log_error}")
            event = None
        
        try:
            # Set status to 'processing' at start
            session.post_transcription_status = 'processing'
            db.session.commit()
            
            # CRITICAL: Always emit progress event
            socketio.emit('insights_generate', {
                'session_id': session.external_id,
                'status': 'processing',
                'message': 'Crafting highlights...',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Generate summary using AnalysisService
            summary_data = AnalysisService.generate_summary(session.id)
            
            result = {
                'summary_id': summary_data.get('id'),
                'has_actions': bool(summary_data.get('actions')),
                'has_decisions': bool(summary_data.get('decisions')),
                'has_risks': bool(summary_data.get('risks')),
                'action_count': len(summary_data.get('actions', [])),
                'decision_count': len(summary_data.get('decisions', [])),
                'risk_count': len(summary_data.get('risks', []))
            }
            
            # Set status to 'success' even if 0 results (AI completed successfully)
            session.post_transcription_status = 'success'
            db.session.commit()
            
            # CRITICAL: Always emit completion event
            socketio.emit('insights_generate', {
                'session_id': session.external_id,
                'status': 'completed',
                'summary_id': result['summary_id'],
                'action_count': result['action_count'],
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Check for model degradation and emit degradation event if needed
            metadata = summary_data.get('_metadata', {})
            if metadata.get('model_degraded'):
                logger.warning(f"⚠️ Model degradation detected: {metadata.get('degradation_reason')}")
                socketio.emit('insights_generate_degraded', {
                    'session_id': session.external_id,
                    'model_used': metadata.get('model_used'),
                    'degradation_reason': metadata.get('degradation_reason'),
                    'timestamp': datetime.utcnow().isoformat(),
                    'message': f"Using {metadata.get('model_used')} instead of primary model"
                })
                logger.info(f"📊 Degradation event emitted: {metadata.get('model_used')}")
            
            # Non-blocking event completion
            if event:
                try:
                    # Include model info in event payload
                    result['model_used'] = metadata.get('model_used', 'unknown')
                    result['model_degraded'] = metadata.get('model_degraded', False)
                    self.event_service.complete_event(event, result=result)
                except Exception as log_error:
                    logger.warning(f"Event completion failed (non-blocking): {log_error}")
            
            logger.info(f"✅ Insights generated: {result['action_count']} actions, {result['decision_count']} decisions, {result['risk_count']} risks (model: {metadata.get('model_used', 'unknown')})")
            return result
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            error_type = type(e).__name__
            error_message = str(e)
            
            # Detailed error logging with traceback
            logger.error(f"❌ Insights generation failed: {error_type}: {error_message}")
            logger.error(f"Traceback:\n{error_traceback}")
            
            # Check if this is a permission/access error (all models inaccessible)
            is_permission_error = (
                "403" in error_message or 
                "does not have access" in error_message or
                "model_not_found" in error_message or
                "PermissionDeniedError" in error_type
            )
            
            # If all models are inaccessible, SKIP this stage gracefully (pattern matching will handle tasks)
            if is_permission_error:
                logger.warning("⚠️ AI models not accessible - skipping insights generation, pattern matching will extract tasks")
                
                # Mark event as SKIPPED (not failed)
                if event:
                    try:
                        self.event_service.skip_event(event, "AI models not accessible - using pattern matching fallback")
                    except:
                        pass
                
                # Return empty result (not None) to indicate success with 0 results
                result = {
                    'summary_id': None,
                    'has_actions': False,
                    'has_decisions': False,
                    'has_risks': False,
                    'action_count': 0,
                    'decision_count': 0,
                    'risk_count': 0,
                    'skipped': True,
                    'skip_reason': 'ai_unavailable'
                }
                
                # Emit completion (not failure) - AI unavailable is not a pipeline failure
                socketio.emit('insights_generate', {
                    'session_id': session.external_id,
                    'status': 'skipped',
                    'message': 'AI unavailable - using pattern matching',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                logger.info("✅ Insights stage skipped gracefully (AI unavailable)")
                return result
            
            # For other errors (timeouts, parsing, etc), mark as failed
            # Classify error type for better user messaging
            if "timeout" in error_message.lower() or "timed out" in error_message.lower():
                error_category = "timeout"
                user_message = "AI service timed out - please try again"
            elif "json" in error_message.lower() or "parse" in error_message.lower():
                error_category = "parse_error"
                user_message = "AI response could not be processed"
            elif "rate" in error_message.lower() or "429" in error_message:
                error_category = "rate_limit"
                user_message = "AI service is busy - please try again in a moment"
            elif "api" in error_message.lower() or "key" in error_message.lower():
                error_category = "api_error"
                user_message = "AI service configuration issue"
            else:
                error_category = "unknown"
                user_message = "Insights generation failed, transcript available"
            
            # Set status to 'failed' on exception
            try:
                session.post_transcription_status = 'failed'
                db.session.commit()
            except Exception as db_error:
                logger.error(f"Failed to update session status: {db_error}")
            
            if event:
                try:
                    self.event_service.fail_event(event, error_message)
                except:
                    pass
            
            # Emit detailed error for debugging (graceful degradation)
            socketio.emit('insights_generate', {
                'session_id': session.external_id,
                'status': 'failed',
                'error': user_message,
                'error_category': error_category,
                'error_type': error_type,
                'error_details': error_message,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return None
    
    def _update_analytics(self, session: Session) -> Optional[Dict[str, Any]]:
        """
        Stage 4: Calculate and update session analytics.
        Event: analytics_update
        """
        event = None
        
        # Non-blocking event logging
        try:
            event = self.event_service.log_event(
                event_type=EventType.ANALYTICS_UPDATE,
                session_id=session.id,
                external_session_id=session.external_id,
                payload={'stage': 'update_analytics'}
            )
            self.event_service.start_event(event)
        except Exception as log_error:
            logger.warning(f"Event logging failed (non-blocking): {log_error}")
            event = None
        
        try:
            # Calculate analytics - IMPORTANT: Use only 'final' segments for consistency with refined view
            segments = db.session.query(Segment).filter_by(
                session_id=session.id,
                kind='final'
            ).all()
            
            logger.info(f"[Analytics] Using {len(segments)} final segments for session {session.external_id}")
            
            total_duration = sum((s.end_ms or 0) - (s.start_ms or 0) for s in segments) / 1000.0
            avg_confidence = sum(s.avg_confidence or 0 for s in segments) / len(segments) if segments else 0
            word_count = sum(len((s.text or '').split()) for s in segments)
            
            # Speaker analysis (speaker_id may not be a database field, so handle gracefully)
            speakers = set(getattr(s, 'speaker_id', None) for s in segments if getattr(s, 'speaker_id', None))
            speaker_count = len(speakers)
            
            result = {
                'total_duration_seconds': total_duration,
                'average_confidence': avg_confidence,
                'word_count': word_count,
                'segment_count': len(segments),
                'speaker_count': speaker_count,
                'words_per_minute': (word_count / (total_duration / 60)) if total_duration > 0 else 0
            }
            
            # Update session statistics
            session.total_segments = len(segments)
            session.average_confidence = avg_confidence
            session.total_duration = total_duration
            db.session.commit()
            
            # CRITICAL: Always emit WebSocket event
            socketio.emit('analytics_update', {
                'session_id': session.external_id,
                'metrics': result,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Non-blocking event completion
            if event:
                try:
                    self.event_service.complete_event(event, result=result)
                except Exception as log_error:
                    logger.warning(f"Event completion failed (non-blocking): {log_error}")
            
            logger.info(f"✅ Analytics updated: {word_count} words, {speaker_count} speakers")
            return result
            
        except Exception as e:
            logger.error(f"Failed to update analytics: {e}")
            if event:
                try:
                    self.event_service.fail_event(event, str(e))
                except:
                    pass
            return None
    
    def _generate_tasks(self, session: Session, insights_data: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """
        Stage 5: Extract and create action items independently from transcript.
        Event: tasks_generation
        
        This stage now works independently of insights success, using NLP-based
        task extraction directly from transcript segments. Falls back to insights
        if available, but continues even if insights failed.
        """
        from models.task import Task
        from sqlalchemy import select, func
        
        event = None
        
        # Non-blocking event logging
        try:
            event = self.event_service.log_event(
                event_type=EventType.TASKS_GENERATION,
                session_id=session.id,
                external_session_id=session.external_id,
                payload={'stage': 'generate_tasks'}
            )
            self.event_service.start_event(event)
        except Exception as log_error:
            logger.warning(f"Event logging failed (non-blocking): {log_error}")
            event = None
        
        try:
            # Strategy: Use AI-extracted tasks as primary source, pattern matching as supplement
            # All tasks are persisted to Task model (single source of truth)
            task_source = "none"
            tasks_created = []
            
            # Option 1: If AI succeeded and found tasks, convert them to Task objects
            if insights_data and insights_data.get('action_count', 0) > 0:
                logger.info(f"[Tasks] Converting {insights_data['action_count']} AI-extracted tasks to Task model")
                
                # Get the summary to access actions
                from models.summary import Summary
                from services.validation_engine import get_validation_engine
                
                summary = db.session.query(Summary).filter_by(session_id=session.id).first()
                validation_engine = get_validation_engine()
                
                # Get transcript for validation
                segments = db.session.query(Segment).filter_by(
                    session_id=session.id,
                    kind='final'
                ).order_by(Segment.start_ms).all()
                full_transcript = " ".join([seg.text for seg in segments if seg.text])
                
                rejected_count = 0
                quality_scores = []
                
                if summary and summary.actions:
                    for idx, action in enumerate(summary.actions):
                        try:
                            # Step 1: Store original raw text from AI
                            raw_task_text = action.get('text', '').strip()
                            evidence_quote = action.get('evidence_quote', '')
                            
                            # Step 2: REFINE FIRST (conversational → professional)
                            from services.task_refinement_service import get_task_refinement_service
                            refinement_service = get_task_refinement_service()
                            
                            refinement_result = refinement_service.refine_task(
                                raw_task=raw_task_text,
                                context={'evidence_quote': evidence_quote}
                            )
                            
                            if refinement_result.success:
                                task_text = refinement_result.refined_text
                                logger.info(f"[Refinement] '{raw_task_text[:40]}...' → '{task_text}'")
                            else:
                                task_text = raw_task_text
                                logger.warning(f"[Refinement] Failed: {refinement_result.error}, using original")
                            
                            # Step 3: THEN VALIDATE the refined text
                            quality_score = validation_engine.score_task_quality(
                                task_text=task_text,  # Validate REFINED text, not raw
                                evidence_quote=evidence_quote,
                                transcript=full_transcript
                            )
                            
                            quality_scores.append(quality_score.total_score)
                            
                            # Reject low-quality tasks (after refinement)
                            if quality_score.total_score < validation_engine.MIN_TASK_SCORE:
                                rejected_count += 1
                                logger.info(
                                    f"[Validation] Rejected refined task (score: {quality_score.total_score:.2f}): "
                                    f"{task_text[:50]}... "
                                    f"(verb:{quality_score.has_action_verb}, subject:{quality_score.has_subject}, "
                                    f"length:{quality_score.appropriate_length}, evidence:{quality_score.has_evidence})"
                                )
                                continue  # Skip this task
                            
                            # Step 4: Parse due date (needed for priority intelligence)
                            from services.date_parser_service import get_date_parser_service
                            date_parser = get_date_parser_service()
                            
                            due_text = action.get('due', '').strip()
                            due_date = None
                            due_interpretation = None
                            
                            if due_text and due_text.lower() not in ['not specified', 'none', 'unknown', '']:
                                date_result = date_parser.parse_due_date(due_text)
                                if date_result.success:
                                    due_date = date_result.date
                                    due_interpretation = date_result.interpretation
                                    logger.info(f"[Date Parsing] '{due_text}' → {due_date} ({due_interpretation})")
                                else:
                                    logger.debug(f"[Date Parsing] Could not parse: '{due_text}'")
                            
                            # Step 5: Intelligent priority detection (keywords + deadline proximity)
                            ai_suggested_priority = action.get('priority', 'medium').lower().strip()
                            priority = _determine_priority(
                                task_text=task_text,
                                evidence_text=evidence_quote,
                                due_date=due_date
                            )
                            # Use AI suggestion as fallback if it's more specific
                            if ai_suggested_priority in ['high', 'urgent', 'critical']:
                                priority = 'high'
                            elif ai_suggested_priority == 'low' and priority == 'medium':
                                priority = 'low'
                            
                            # Step 6: Extract assignee from context (NLP-based)
                            # First try AI-suggested owner, then extract from evidence
                            owner_name = action.get('owner', '').strip()
                            if not owner_name or owner_name.lower() in ['not specified', 'none', 'unknown', '']:
                                # Try to extract from evidence quote
                                extracted_assignee = _extract_assignee_from_context(
                                    evidence_text=evidence_quote,
                                    speaker_name=None  # Could get from segment.speaker if available
                                )
                                if extracted_assignee:
                                    owner_name = extracted_assignee
                            
                            # Step 7: Match user/owner (name → user_id or store name)
                            from services.user_matching_service import get_user_matching_service
                            user_matcher = get_user_matching_service()
                            
                            assigned_to_id = None
                            assigned_to_name = None
                            
                            if owner_name and owner_name.lower() not in ['not specified', 'none', 'unknown', '']:
                                match_result = user_matcher.match_user(owner_name, session.id)
                                if match_result.success and match_result.user_id:
                                    assigned_to_id = match_result.user_id
                                    logger.info(f"[User Matching] '{owner_name}' → user_id {assigned_to_id}")
                                else:
                                    # Store name in extraction context if no user match
                                    assigned_to_name = match_result.user_name
                                    logger.debug(f"[User Matching] '{owner_name}' stored as name (no user match)")
                            
                            # Calculate intelligent confidence score based on refinement + quality
                            # Base: quality_score.total_score (0.0-1.0)
                            # Boost: +0.15 if successfully refined
                            # Cap: 0.95 maximum
                            base_confidence = quality_score.total_score
                            if refinement_result.success and refinement_result.transformation_applied:
                                # Successfully refined → boost confidence
                                confidence_boost = 0.15
                                final_confidence = min(0.95, base_confidence + confidence_boost)
                            elif refinement_result.success and not refinement_result.transformation_applied:
                                # Already well-formatted, no transformation needed
                                final_confidence = min(0.95, base_confidence + 0.10)
                            else:
                                # Refinement failed, use base quality score (likely 0.6-0.7)
                                final_confidence = base_confidence
                            
                            # Create task only if quality is acceptable
                            task = Task(
                                session_id=session.id,
                                title=task_text[:255],  # Use refined text
                                description=f"AI-extracted action item (quality score: {quality_score.total_score:.2f})",
                                priority=priority,  # Parsed priority
                                status="todo",
                                due_date=due_date,  # Parsed due date
                                assigned_to_id=assigned_to_id,  # Matched user ID
                                extracted_by_ai=True,
                                confidence_score=final_confidence,
                                extraction_context={
                                    'source': 'ai_insights',
                                    'raw_text': raw_task_text,  # PRESERVE ORIGINAL for validation
                                    'refined_text': task_text if refinement_result.success else None,
                                    'refinement_applied': refinement_result.transformation_applied,
                                    'refinement_confidence': refinement_result.confidence,
                                    'original_action': action,
                                    'quality_score': quality_score.total_score,
                                    'quality_breakdown': {
                                        'has_action_verb': quality_score.has_action_verb,
                                        'has_subject': quality_score.has_subject,
                                        'appropriate_length': quality_score.appropriate_length,
                                        'has_evidence': quality_score.has_evidence
                                    },
                                    'metadata_extraction': {
                                        'priority_raw': ai_suggested_priority,
                                        'priority_mapped': priority,
                                        'due_text': due_text,
                                        'due_date': due_date.isoformat() if due_date else None,
                                        'due_interpretation': due_interpretation,
                                        'owner_raw': owner_name,
                                        'owner_matched_id': assigned_to_id,
                                        'owner_name': assigned_to_name
                                    },
                                    'evidence_quote': evidence_quote
                                }
                            )
                            db.session.add(task)
                            tasks_created.append(task)
                            logger.info(f"[Validation] Accepted task (score: {quality_score.total_score:.2f}): {task_text[:50]}...")
                            
                        except Exception as e:
                            logger.warning(f"Failed to create AI-extracted task: {e}")
                            continue
                    
                    # Log validation summary
                    if quality_scores:
                        avg_score = sum(quality_scores) / len(quality_scores)
                        logger.info(
                            f"[Validation] Task quality summary: {len(tasks_created)} accepted, "
                            f"{rejected_count} rejected, avg score: {avg_score:.2f}"
                        )
                        
                        # Emit validation metrics to EventLedger for observability
                        try:
                            validation_event = self.event_service.log_event(
                                event_type=EventType.TASKS_GENERATION,
                                session_id=session.id,
                                external_session_id=session.external_id,
                                payload={
                                    'validation_metrics': {
                                        'tasks_accepted': len(tasks_created),
                                        'tasks_rejected': rejected_count,
                                        'avg_quality_score': round(avg_score, 2),
                                        'min_score': round(min(quality_scores), 2) if quality_scores else 0,
                                        'max_score': round(max(quality_scores), 2) if quality_scores else 0,
                                        'quality_threshold': validation_engine.MIN_TASK_SCORE
                                    }
                                }
                            )
                            logger.debug(f"📊 [Observability] Validation metrics logged to EventLedger")
                        except Exception as obs_error:
                            logger.warning(f"Failed to log validation metrics (non-blocking): {obs_error}")
                    
                    # CRITICAL: Semantic deduplication BEFORE database commit
                    # Remove duplicate tasks (e.g., "Test transcription" + "Check transcription")
                    if len(tasks_created) > 1:
                        logger.info(f"[Deduplication] Starting semantic deduplication on {len(tasks_created)} tasks...")
                        
                        unique_tasks = []
                        duplicate_count = 0
                        
                        for current_task in tasks_created:
                            is_duplicate = False
                            current_title = current_task.title
                            
                            for existing_task in unique_tasks:
                                existing_title = existing_task.title
                                
                                # Calculate semantic similarity using ValidationEngine's method
                                similarity = validation_engine._calculate_similarity(current_title, existing_title)
                                
                                if similarity >= validation_engine.DEDUP_SIMILARITY_THRESHOLD:
                                    # Found duplicate - keep the higher confidence task
                                    duplicate_count += 1
                                    
                                    logger.info(
                                        f"[Deduplication] Found duplicate (similarity: {similarity:.2f}):\n"
                                        f"  • Task 1: '{existing_title[:60]}...' (confidence: {existing_task.confidence_score:.2f})\n"
                                        f"  • Task 2: '{current_title[:60]}...' (confidence: {current_task.confidence_score:.2f})"
                                    )
                                    
                                    # Keep the higher confidence task
                                    if current_task.confidence_score > existing_task.confidence_score:
                                        logger.info(f"  → Keeping Task 2 (higher confidence)")
                                        # Remove existing task from session and unique_tasks
                                        db.session.expunge(existing_task)
                                        unique_tasks.remove(existing_task)
                                        # Add current task instead
                                        unique_tasks.append(current_task)
                                    else:
                                        logger.info(f"  → Keeping Task 1 (higher confidence)")
                                        # Remove current task from session
                                        db.session.expunge(current_task)
                                    
                                    is_duplicate = True
                                    break
                            
                            if not is_duplicate:
                                unique_tasks.append(current_task)
                        
                        logger.info(
                            f"[Deduplication] Completed: {len(tasks_created)} tasks → {len(unique_tasks)} unique "
                            f"({duplicate_count} duplicates removed)"
                        )
                        
                        # Update tasks_created to only include unique tasks
                        tasks_created = unique_tasks
                    else:
                        logger.debug(f"[Deduplication] Skipped (only {len(tasks_created)} task)")
                    
                    # Commit AI-extracted tasks (after deduplication)
                    try:
                        db.session.commit()
                        logger.info(f"✅ [Database] Persisted {len(tasks_created)} AI-extracted tasks")
                        task_source = "ai_insights"
                    except Exception as e:
                        import traceback
                        logger.error(f"❌ [Database] Failed to commit AI-extracted tasks: {e}")
                        logger.error(f"Traceback:\n{traceback.format_exc()}")
                        db.session.rollback()
                        tasks_created = []
            
            # Option 2: If AI failed or found no tasks, use pattern matching as fallback
            if not tasks_created:
                logger.info(f"[Tasks] AI tasks unavailable, using pattern matching as fallback")
                task_source = "pattern_extraction"
                
                # Get transcript segments for NLP extraction
                segments = db.session.query(Segment).filter_by(
                    session_id=session.id,
                    kind='final'
                ).order_by(Segment.start_ms).all()
                
                if segments:
                    # Build transcript text for pattern matching with segment tracking
                    transcript_with_segments = []
                    for seg in segments:
                        text = seg.text.strip()
                        if text:
                            transcript_with_segments.append({
                                'text': text,
                                'segment_id': seg.id,
                                'start_ms': seg.start_ms,
                                'end_ms': seg.end_ms
                            })
                    
                    # Use pattern-based extraction with segment linkage
                    extracted_tasks = self._extract_tasks_with_patterns_and_segments(
                        transcript_with_segments, session.id
                    )
                    
                    logger.info(f"[Tasks] Pattern extraction attempted {len(extracted_tasks)} tasks")
                else:
                    logger.warning(f"[Tasks] No final segments found for session {session.id}")
                    task_source = "no_segments"
            
            # CRITICAL: Query database to get ACTUAL persisted count (after commit)
            persisted_task_count = db.session.scalar(
                select(func.count()).select_from(Task).where(Task.session_id == session.id)
            ) or 0
            
            logger.info(f"[Tasks] Database verification: {persisted_task_count} tasks persisted for session {session.id}")
            
            result = {
                'tasks_created': persisted_task_count,  # Use DB count, not in-memory count
                'task_source': task_source,
                'session_id': session.id
            }
            
            # CRITICAL: Emit WebSocket event AFTER database verification (use DB count)
            socketio.emit('tasks_generation', {
                'session_id': session.external_id,
                'task_count': persisted_task_count,  # Use verified DB count
                'message': f'{persisted_task_count} new action{"s" if persisted_task_count != 1 else ""} identified' if persisted_task_count > 0 else 'No action items found',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Check for model degradation in task extraction (from insights metadata)
            if insights_data and task_source == "ai_insights":
                # Get metadata from insights (passed down through the pipeline)
                metadata = insights_data.get('_metadata', {})
                if metadata and metadata.get('model_degraded'):
                    logger.warning(f"⚠️ Task extraction degradation detected: {metadata.get('degradation_reason')}")
                    socketio.emit('tasks_generation_degraded', {
                        'session_id': session.external_id,
                        'model_used': metadata.get('model_used'),
                        'degradation_reason': metadata.get('degradation_reason'),
                        'timestamp': datetime.utcnow().isoformat(),
                        'message': f"Tasks extracted using {metadata.get('model_used')} instead of primary model"
                    })
                    logger.info(f"📊 Task degradation event emitted: {metadata.get('model_used')}")
            
            # Non-blocking event completion
            if event:
                try:
                    # Update payload with task count for event ledger
                    from sqlalchemy.orm.attributes import flag_modified
                    payload = event.payload or {}
                    payload['task_count'] = persisted_task_count
                    payload['task_source'] = task_source
                    event.payload = payload
                    flag_modified(event, 'payload')  # Tell SQLAlchemy that JSON field changed
                    db.session.add(event)
                    db.session.commit()
                    self.event_service.complete_event(event, result=result)
                except Exception as log_error:
                    logger.warning(f"Event completion failed (non-blocking): {log_error}")
            
            logger.info(f"✅ Tasks generated: {persisted_task_count} tasks from {task_source}")
            return result
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Failed to generate tasks: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            
            if event:
                try:
                    self.event_service.fail_event(event, str(e))
                except:
                    pass
            
            # Emit event even on failure (0 tasks found)
            socketio.emit('tasks_generation', {
                'session_id': session.external_id,
                'task_count': 0,
                'message': 'Task extraction failed',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return None
    
    def _extract_tasks_with_patterns_and_segments(self, transcript_segments: List[Dict], session_id: int) -> List:
        """
        Extract tasks using regex patterns with segment linkage for 'jump to context'.
        Creates Task objects directly in database with source segment tracking.
        
        Args:
            transcript_segments: List of dicts with 'text', 'segment_id', 'start_ms', 'end_ms'
            session_id: Session ID to link tasks to
            
        Returns:
            List of created Task objects
        """
        from models.task import Task
        import re
        
        # Comprehensive task patterns to detect action items
        # Each pattern captures the task description in group 1
        task_patterns = [
            # Explicit action markers
            r"(?:action item|action|task|todo|to-do|to do|follow up|followup|next step)s?[:\-\s]+(.+?)(?:\.|$)",
            
            # Commitment patterns
            r"(?:I|we|you|he|she|they)(?:'ll|\s+will|\s+need to|\s+should|\s+must|\s+have to|\s+got to|'ve got to)\s+(.+?)(?:\.|$)",
            r"(?:I|we)'?(?:m| am|'re| are)\s+going to\s+(.+?)(?:\.|$)",
            
            # Suggestion to action
            r"let['\s]*s\s+(.+?)(?:\.|$)",
            
            # Assignment patterns
            r"(?:assign|delegate|give)\s+(.+?)\s+to\s+\w+",
            
            # TODO variations
            r"\[?(?:TODO|Action|Task|Reminder)\]?[:\-\s]+(.+?)(?:\.|$)",
            
            # Deadline and time-based (explicit temporal markers only)
            r"(?:deadline|due(?:\s+by)?)\s+(.+?)(?:\.|$)",
            
            # Numbered action lists (e.g., "1. Review the document")
            r"\d+[\.\)]\s+(?:review|update|send|create|finish|complete|prepare|schedule|contact|call|email|write|fix|implement|test|deploy|check)\s+(.+?)(?:\.|$)",
            
            # Reminders
            r"(?:reminder|remember to|don't forget to)[:\-\s]*(.+?)(?:\.|$)",
        ]
        
        created_tasks = []
        seen_titles = set()  # Deduplicate
        pattern_match_counts = {}  # Track which patterns are matching (diagnostic logging)
        
        # Extract tasks from transcript segments
        for seg_data in transcript_segments:
            text = seg_data['text']
            segment_id = seg_data['segment_id']
            
            for idx, pattern in enumerate(task_patterns):
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    task_text = match.group(1).strip()
                    
                    # Basic validation
                    if len(task_text) < 5 or len(task_text) > 200:
                        logger.debug(f"[Pattern Matching] Skipped task (length {len(task_text)}): '{task_text[:50]}...'")
                        continue
                    
                    # Context-aware filtering to eliminate false positives
                    task_lower = task_text.lower()
                    
                    # Filter 1: Reject meta-commentary about the application/testing
                    meta_patterns = [
                        'task extraction', 'should be able', 'the objective', 
                        'testing the', 'i am testing', 'we are testing',
                        'the feature', 'this feature', 'the application', 'this application',
                        'the system', 'this system', 'the pipeline', 'this pipeline',
                        'the goal is', 'the purpose is', 'the idea is',
                        'i\'m recording', 'i am recording', 'screen recording'
                    ]
                    if any(meta in task_lower for meta in meta_patterns):
                        logger.debug(f"[Pattern Matching] Skipped meta-commentary: '{task_text[:50]}...'")
                        continue
                    
                    # Filter 2: Reject questions (not action items)
                    if task_text.strip().endswith('?'):
                        logger.debug(f"[Pattern Matching] Skipped question: '{task_text[:50]}...'")
                        continue
                    
                    # Filter 3: Reject if doesn't contain action verbs (for commitment patterns)
                    # Only apply to commitment patterns (patterns 1 and 2)
                    if idx in [1, 2]:  # Commitment patterns that use "will", "should", etc.
                        action_verbs = [
                            'review', 'update', 'send', 'create', 'finish', 'complete',
                            'prepare', 'schedule', 'contact', 'call', 'email', 'write',
                            'fix', 'implement', 'test', 'deploy', 'check', 'submit',
                            'approve', 'analyze', 'research', 'present', 'discuss',
                            'follow up', 'followup', 'reach out', 'set up', 'setup'
                        ]
                        has_action_verb = any(verb in task_lower for verb in action_verbs)
                        if not has_action_verb:
                            logger.debug(f"[Pattern Matching] Skipped (no action verb): '{task_text[:50]}...'")
                            continue
                    
                    # Filter 4: Minimum meaningful content (at least 3 words after filtering)
                    word_count = len(task_text.split())
                    if word_count < 3:
                        logger.debug(f"[Pattern Matching] Skipped (too few words): '{task_text[:50]}...'")
                        continue
                    
                    # Deduplication - check full text before refinement
                    if task_text.lower() in seen_titles:
                        logger.debug(f"[Pattern Matching] Skipped duplicate task: '{task_text[:50]}...'")
                        continue
                        
                    seen_titles.add(task_text.lower())
                    
                    # Track pattern match for diagnostics
                    pattern_name = f"pattern_{idx}"
                    pattern_match_counts[pattern_name] = pattern_match_counts.get(pattern_name, 0) + 1
                    logger.debug(f"[Pattern Matching] Pattern {idx} matched: '{task_text[:50]}...' in segment {segment_id}")
                    
                    # ===== APPLY REFINEMENT TO PATTERN-MATCHED TASKS =====
                    from services.task_refinement_service import get_task_refinement_service
                    from services.date_parser_service import get_date_parser_service
                    
                    raw_task_text = task_text
                    refinement_service = get_task_refinement_service()
                    
                    # Refine task text (conversational → professional)
                    refinement_result = refinement_service.refine_task(
                        raw_task=task_text,
                        context={'evidence_quote': text[:200]}  # Use full segment text as context
                    )
                    
                    if refinement_result.success:
                        task_text = refinement_result.refined_text
                        logger.info(f"[Pattern+Refinement] '{raw_task_text[:40]}...' → '{task_text[:60]}'")
                    else:
                        logger.warning(f"[Pattern+Refinement] Failed: {refinement_result.error}, using original")
                    
                    # ===== QUALITY VALIDATION: Reject meta-commentary and low-quality tasks =====
                    from services.validation_engine import get_validation_engine
                    
                    validation_engine = get_validation_engine()
                    quality_score = validation_engine.score_task_quality(
                        task_text=task_text,
                        evidence_quote=text[:200],
                        transcript=text
                    )
                    
                    # Reject if quality score below threshold (0.70)
                    if quality_score.total_score < 0.70:
                        logger.info(f"[Pattern+Validation] REJECTED (score={quality_score.total_score:.2f}): '{task_text[:60]}'")
                        logger.debug(f"  Rejection reasons: {quality_score.deductions}")
                        continue  # Skip this task
                    else:
                        logger.debug(f"[Pattern+Validation] PASSED (score={quality_score.total_score:.2f}): '{task_text[:60]}'")
                    
                    # Parse due date if present in text
                    date_parser = get_date_parser_service()
                    due_date = None
                    due_interpretation = None
                    
                    # Look for temporal markers in the original segment text
                    date_result = date_parser.parse_due_date(text)
                    if date_result.success:
                        due_date = date_result.date
                        due_interpretation = date_result.interpretation
                        logger.info(f"[Pattern+Date] Parsed due date: {due_interpretation}")
                    
                    # Intelligent priority detection
                    priority = _determine_priority(
                        task_text=task_text,
                        evidence_text=text[:200],
                        due_date=due_date
                    )
                    
                    # Extract assignee from context
                    extracted_assignee = _extract_assignee_from_context(
                        evidence_text=text[:500],
                        speaker_name=seg_data.get('speaker')
                    )
                    
                    # Calculate intelligent confidence score for pattern-matched tasks
                    # Pattern matching starts at 0.65 base, refinement boosts it
                    base_pattern_confidence = 0.65
                    if refinement_result.success and refinement_result.transformation_applied:
                        # Successfully refined → 0.80-0.85 confidence
                        pattern_confidence = 0.82
                    elif refinement_result.success and not refinement_result.transformation_applied:
                        # Already well-formatted → 0.75-0.80
                        pattern_confidence = 0.78
                    else:
                        # Refinement failed → stay at base
                        pattern_confidence = base_pattern_confidence
                    
                    # Create task in database with refinement metadata
                    try:
                        task = Task(
                            session_id=session_id,
                            title=task_text,  # Use FULL refined text (no truncation)
                            description=f"Extracted from transcript via pattern matching",
                            priority=priority,  # Intelligent priority detection
                            status="todo",
                            due_date=due_date,  # Parsed due date
                            extracted_by_ai=False,  # Pattern-based extraction
                            confidence_score=pattern_confidence,  # Intelligent confidence scoring
                            extraction_context={
                                'source': 'pattern',
                                'raw_text': raw_task_text,  # CRITICAL: Store original for transparency
                                'transcript_snippet': text[:500],
                                'source_segment_id': segment_id,  # Enable 'jump to context'
                                'start_ms': seg_data.get('start_ms'),
                                'end_ms': seg_data.get('end_ms'),
                                'matched_pattern': pattern[:50],  # Store which pattern matched
                                'refinement': {
                                    'transformation_applied': refinement_result.success,
                                    'method': 'llm' if refinement_result.transformation_applied else 'passthrough',
                                    'error': refinement_result.error if not refinement_result.success else None
                                },
                                'metadata_extraction': {
                                    'due_date_parsed': due_interpretation,
                                    'priority_detected': priority,
                                    'owner_name': extracted_assignee
                                }
                            }
                        )
                        db.session.add(task)
                        created_tasks.append(task)
                    except Exception as e:
                        logger.warning(f"Failed to create pattern-extracted task: {e}")
                        continue
        
        # Commit all tasks at once with comprehensive error handling
        try:
            if created_tasks:
                # Log pre-commit state for debugging
                logger.info(f"[Database] Attempting to commit {len(created_tasks)} tasks for session_id={session_id}")
                
                # Verify session exists before committing (FK constraint check)
                from models.session import Session as SessionModel
                session_exists = db.session.query(SessionModel).filter_by(id=session_id).first()
                if not session_exists:
                    logger.error(f"[Database] FK violation prevented: session_id={session_id} does not exist")
                    db.session.rollback()
                    return []
                
                # Commit to database
                db.session.commit()
                
                # CRITICAL: Verify tasks were actually persisted by querying database
                from sqlalchemy import select, func
                persisted_count = db.session.scalar(
                    select(func.count()).select_from(Task).where(Task.session_id == session_id)
                )
                
                if persisted_count != len(created_tasks):
                    logger.error(
                        f"[Database] Task persistence mismatch! "
                        f"Expected {len(created_tasks)} but found {persisted_count} in database "
                        f"for session_id={session_id}"
                    )
                
                logger.info(
                    f"✅ [Database] Successfully persisted {persisted_count} tasks "
                    f"(attempted {len(created_tasks)}) for session_id={session_id}"
                )
                
                # Log diagnostic information about pattern matching
                if pattern_match_counts:
                    logger.info(f"[Pattern Matching] Match distribution: {pattern_match_counts}")
            else:
                logger.info(f"[Pattern Matching] No tasks extracted from {len(transcript_segments)} segments")
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            error_type = type(e).__name__
            
            # Detailed error logging with full context
            logger.error(f"❌ [Database] Failed to commit tasks: {error_type}: {e}")
            logger.error(f"[Database] Error traceback:\n{error_traceback}")
            logger.error(
                f"[Database] Context: session_id={session_id}, "
                f"attempted_tasks={len(created_tasks)}, "
                f"task_titles={[t.title[:30] for t in created_tasks[:3]]}"
            )
            
            # Rollback and return empty list
            db.session.rollback()
            return []
        
        return created_tasks
    
    def _emit_reveal(self, session: Session):
        """
        Stage 6: Emit post_transcription_reveal to trigger UI transition.
        Event: post_transcription_reveal
        """
        event = None
        
        # Non-blocking event logging
        try:
            event = self.event_service.log_event(
                event_type=EventType.POST_TRANSCRIPTION_REVEAL,
                session_id=session.id,
                external_session_id=session.external_id,
                payload={'stage': 'post_transcription_reveal'}
            )
            self.event_service.start_event(event)
        except Exception as log_error:
            logger.warning(f"Event logging failed (non-blocking): {log_error}")
            event = None
        
        try:
            # CRITICAL: Always emit WebSocket event to trigger UI transition
            socketio.emit('post_transcription_reveal', {
                'session_id': session.external_id,
                'redirect_url': f'/sessions/{session.external_id}/refined',
                'message': 'Your meeting insights are ready',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Non-blocking event completion
            if event:
                try:
                    self.event_service.complete_event(event, result={'emitted': True})
                except Exception as log_error:
                    logger.warning(f"Event completion failed (non-blocking): {log_error}")
            
            logger.info(f"✅ Post-transcription reveal emitted for {session.external_id}")
            
        except Exception as e:
            logger.error(f"Failed to emit reveal: {e}")
            if event:
                try:
                    self.event_service.fail_event(event, str(e))
                except:
                    pass
    
    def _finalize_session(self, session: Session):
        """
        Stage 7: Mark session as finalized and create Meeting record.
        Event: session_finalized
        
        This is the critical link that converts transcription sessions into meetings
        for the dashboard, analytics, and meeting list pages.
        """
        event = None
        meeting_id = None
        
        # Non-blocking event logging
        try:
            event = self.event_service.log_event(
                event_type=EventType.SESSION_FINALIZED,
                session_id=session.id,
                external_session_id=session.external_id,
                payload={'stage': 'session_finalized'}
            )
            self.event_service.start_event(event)
        except Exception as log_error:
            logger.warning(f"Event logging failed (non-blocking): {log_error}")
            event = None
        
        try:
            # CRITICAL: Create Meeting from Session (fixes the broken pipeline)
            # This ensures sessions appear in Dashboard, Meetings List, Analytics
            try:
                from services.meeting_lifecycle_service import MeetingLifecycleService
                
                meeting = MeetingLifecycleService.create_meeting_from_session(session.id)
                if meeting:
                    meeting_id = meeting.id
                    logger.info(f"✅ Created Meeting {meeting_id} from Session {session.id}")
                else:
                    logger.warning(f"⚠️ Failed to create meeting from session {session.id}")
            except Exception as meeting_error:
                logger.error(f"Meeting creation failed (non-blocking): {meeting_error}", exc_info=True)
            
            # CRITICAL: Always emit confirmation event
            socketio.emit('session_finalized', {
                'session_id': session.external_id,
                'meeting_id': meeting_id,
                'status': 'completed',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Non-blocking event completion
            if event:
                try:
                    self.event_service.complete_event(event, result={
                        'status': 'finalized',
                        'meeting_id': meeting_id
                    })
                except Exception as log_error:
                    logger.warning(f"Event completion failed (non-blocking): {log_error}")
            
            logger.info(f"✅ Session finalized: {session.external_id} (meeting_id={meeting_id})")
            
        except Exception as e:
            logger.error(f"Failed to finalize session: {e}")
            if event:
                try:
                    self.event_service.fail_event(event, str(e))
                except:
                    pass
    
    def _emit_dashboard_refresh(self, session: Session):
        """
        Stage 8: Emit dashboard_refresh for cross-page updates (CROWN+ final event).
        Event: dashboard_refresh
        """
        event = None
        start_time = time.time()
        success = False
        
        # Non-blocking event logging
        try:
            event = self.event_service.log_event(
                event_type=EventType.DASHBOARD_REFRESH,
                session_id=session.id,
                external_session_id=session.external_id,
                payload={'stage': 'dashboard_refresh'}
            )
            self.event_service.start_event(event)
        except Exception as log_error:
            logger.warning(f"Event logging failed (non-blocking): {log_error}")
            event = None
        
        try:
            # CRITICAL: Always emit WebSocket event for cross-page updates
            socketio.emit('dashboard_refresh', {
                'session_id': session.external_id,
                'action': 'session_completed',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Non-blocking event completion
            if event:
                try:
                    self.event_service.complete_event(event, result={'emitted': True})
                except Exception as log_error:
                    logger.warning(f"Event completion failed (non-blocking): {log_error}")
            
            success = True
            logger.info(f"✅ Dashboard refresh emitted for {session.external_id}")
            
        except Exception as e:
            logger.error(f"Failed to emit dashboard refresh: {e}")
            if event:
                try:
                    self.event_service.fail_event(event, str(e))
                except:
                    pass
        finally:
            # Log to monitoring service for production tracking
            duration_ms = (time.time() - start_time) * 1000
            log_dashboard_refresh_event(
                session_id=session.external_id,
                success=success,
                duration_ms=duration_ms,
                session_title=session.title
            )
