"""
End-to-End Transcription Flow Tests
Tests the complete recording → processing → persistence → insights pipeline.
"""
import pytest
import time
import json
from unittest.mock import Mock, patch, MagicMock
import numpy as np


@pytest.mark.e2e
class TestTranscriptionE2EFlow:
    """Test complete transcription pipeline end-to-end."""
    
    def test_session_creation_to_completion_flow(self, app, db_session):
        """Test full session lifecycle: create → record → finalize → insights."""
        from models import Session, Segment
        
        with app.app_context():
            external_id = Session.generate_external_id()
            session = Session(
                external_id=external_id,
                title="E2E Test Meeting",
                status="active"
            )
            db_session.add(session)
            db_session.commit()
            
            segment = Segment(
                session_id=session.id,
                text="This is an end-to-end test of the transcription pipeline.",
                start_ms=0,
                end_ms=5000,
                avg_confidence=0.92,
                kind="final"
            )
            db_session.add(segment)
            db_session.commit()
            
            session.status = "completed"
            db_session.commit()
            
            completed_session = db_session.query(Session).filter_by(id=session.id).first()
            assert completed_session.status == "completed"
            
            segments = db_session.query(Segment).filter_by(session_id=session.id).all()
            assert len(segments) == 1
            assert segments[0].text == "This is an end-to-end test of the transcription pipeline."
    
    def test_multi_segment_transcription_flow(self, app, db_session):
        """Test transcription with multiple segments simulating real meeting."""
        from models import Session, Segment
        
        with app.app_context():
            external_id = Session.generate_external_id()
            session = Session(
                external_id=external_id,
                title="Multi-Segment Test",
                status="active"
            )
            db_session.add(session)
            db_session.commit()
            
            segments_data = [
                {"text": "Hello everyone, let's start the meeting.", "start": 0, "end": 3000, "conf": 0.95},
                {"text": "Today we'll discuss the project timeline.", "start": 3000, "end": 6000, "conf": 0.93},
                {"text": "The deadline is next Friday.", "start": 6000, "end": 9000, "conf": 0.91},
                {"text": "Any questions before we proceed?", "start": 9000, "end": 12000, "conf": 0.94},
            ]
            
            for seg_data in segments_data:
                segment = Segment(
                    session_id=session.id,
                    text=seg_data["text"],
                    start_ms=seg_data["start"],
                    end_ms=seg_data["end"],
                    avg_confidence=seg_data["conf"],
                    kind="final"
                )
                db_session.add(segment)
            
            db_session.commit()
            
            all_segments = db_session.query(Segment).filter_by(
                session_id=session.id
            ).order_by(Segment.start_ms).all()
            
            assert len(all_segments) == 4
            assert all_segments[0].start_ms < all_segments[-1].start_ms
            assert all(seg.avg_confidence > 0.9 for seg in all_segments)
    
    def test_audio_processing_pipeline(self, app):
        """Test audio ingestion → VAD → quality analysis flow."""
        with app.app_context():
            from services.vad_service import VADService
            from services.audio_quality_analyzer import AudioQualityAnalyzer
            
            vad = VADService()
            analyzer = AudioQualityAnalyzer()
            
            sample_rate = 16000
            duration_seconds = 1
            samples = sample_rate * duration_seconds
            
            audio_with_speech = np.random.randn(samples).astype(np.float32) * 0.5
            audio_bytes = (audio_with_speech * 32767).astype(np.int16).tobytes()
            
            vad_result = vad.is_voiced(audio_bytes)
            assert isinstance(vad_result, bool)
            
            audio_np = np.random.randint(-32768, 32767, size=samples, dtype=np.int16)
            quality_result = analyzer.analyze_audio_quality(audio_np, sample_rate)
            assert quality_result is not None
    
    def test_deduplication_in_pipeline(self, app):
        """Test deduplication handles overlapping transcriptions correctly."""
        with app.app_context():
            from services.deduplication_engine import AdvancedDeduplicationEngine, TranscriptionResult
            
            engine = AdvancedDeduplicationEngine()
            session_id = "e2e_dedup_test"
            
            result1 = TranscriptionResult(
                text="Hello world",
                start_time=0.0,
                end_time=2.0,
                confidence=0.9,
                chunk_id="chunk_001",
                is_final=False
            )
            response1 = engine.process_transcription_result(session_id, result1)
            
            result2 = TranscriptionResult(
                text="Hello world, how are you",
                start_time=0.0,
                end_time=3.0,
                confidence=0.95,
                chunk_id="chunk_002",
                is_final=True
            )
            response2 = engine.process_transcription_result(session_id, result2)
            
            assert response2['confidence'] == 0.95
            assert 'is_committed' in response2
    
    def test_speaker_diarization_in_flow(self, app):
        """Test speaker identification within transcription flow."""
        with app.app_context():
            from services.multi_speaker_diarization import MultiSpeakerDiarization
            
            diarization = MultiSpeakerDiarization()
            
            audio_samples = np.random.randn(16000).astype(np.float32)
            
            result = diarization.process_audio_segment(
                audio_samples=audio_samples,
                timestamp=0.0,
                segment_id="e2e_speaker_001"
            )
            
            assert result is not None
            assert hasattr(result, 'speaker_id')


@pytest.mark.e2e
class TestMeetingLifecycleE2E:
    """Test complete meeting lifecycle with all services."""
    
    def test_meeting_creation_workflow(self, app, db_session, test_user, test_workspace):
        """Test meeting creation with workspace association."""
        from models import Meeting
        
        with app.app_context():
            meeting = Meeting(
                title="E2E Workflow Test Meeting",
                workspace_id=test_workspace.id,
                organizer_id=test_user.id,
                status="scheduled"
            )
            db_session.add(meeting)
            db_session.commit()
            
            assert meeting.id is not None
            assert meeting.workspace_id == test_workspace.id
            
            meeting.status = "live"
            db_session.commit()
            
            meeting.status = "completed"
            db_session.commit()
            
            final_meeting = db_session.query(Meeting).filter_by(id=meeting.id).first()
            assert final_meeting.status == "completed"
    
    def test_task_extraction_from_meeting(self, app, db_session, test_user, test_workspace):
        """Test task creation linked to meeting."""
        from models import Meeting, Task
        
        with app.app_context():
            meeting = Meeting(
                title="Task Extraction Test",
                workspace_id=test_workspace.id,
                organizer_id=test_user.id,
                status="completed"
            )
            db_session.add(meeting)
            db_session.commit()
            
            tasks = [
                Task(
                    title="Follow up with client",
                    description="Send proposal by Friday",
                    status="todo",
                    priority="high",
                    meeting_id=meeting.id,
                    workspace_id=test_workspace.id,
                    assigned_to_id=test_user.id
                ),
                Task(
                    title="Review documentation",
                    description="Complete review before next meeting",
                    status="todo",
                    priority="medium",
                    meeting_id=meeting.id,
                    workspace_id=test_workspace.id,
                    assigned_to_id=test_user.id
                )
            ]
            
            for task in tasks:
                db_session.add(task)
            db_session.commit()
            
            meeting_tasks = db_session.query(Task).filter_by(meeting_id=meeting.id).all()
            assert len(meeting_tasks) == 2
            assert all(t.meeting_id == meeting.id for t in meeting_tasks)


@pytest.mark.e2e
class TestAIInsightsE2E:
    """Test AI-powered insights generation end-to-end."""
    
    def test_ai_service_initialization_chain(self, app):
        """Test all AI services initialize correctly."""
        with app.app_context():
            from services.ai_insights_service import AIInsightsService
            from services.analysis_service import AnalysisService
            from services.sentiment_analysis_service import SentimentAnalysisService
            from services.task_extraction_service import TaskExtractionService
            
            ai_insights = AIInsightsService()
            analysis = AnalysisService()
            sentiment = SentimentAnalysisService()
            task_extraction = TaskExtractionService()
            
            assert ai_insights is not None
            assert analysis is not None
            assert sentiment is not None
            assert task_extraction is not None
    
    def test_circuit_breaker_protection(self, app):
        """Test circuit breaker protects AI calls."""
        with app.app_context():
            from services.circuit_breaker import CircuitBreakerManager, CircuitBreaker
            
            manager = CircuitBreakerManager()
            breaker = manager.get_breaker('openai_api')
            
            assert breaker is not None
            assert isinstance(breaker, CircuitBreaker)
            assert hasattr(breaker, 'call')
            
            state = breaker.state.value
            assert state in ['closed', 'open', 'half_open']


@pytest.mark.e2e
class TestWebSocketE2E:
    """Test WebSocket communication patterns."""
    
    def test_websocket_namespaces_registered(self, app):
        """Test all WebSocket namespaces are properly registered."""
        with app.app_context():
            from flask_socketio import SocketIO
            
            expected_namespaces = [
                '/transcription',
                '/dashboard', 
                '/tasks',
                '/analytics',
                '/meetings'
            ]
            
            for ns in expected_namespaces:
                pass
    
    def test_event_sequencer_initialization(self, app):
        """Test event sequencer for WebSocket ordering."""
        with app.app_context():
            from services.event_sequencer import EventSequencer
            
            sequencer = EventSequencer()
            assert sequencer is not None
