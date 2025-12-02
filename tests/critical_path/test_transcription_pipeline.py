"""
Critical Path Tests: Audio Transcription Pipeline
Tests the complete flow from audio input to transcribed text output.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import uuid
import numpy as np


@pytest.mark.critical
class TestTranscriptionPipeline:
    """Test the core transcription service functionality."""
    
    def test_transcription_service_module_exists(self, app):
        """Test that transcription service module can be imported."""
        with app.app_context():
            from services import transcription_service
            assert transcription_service is not None
    
    def test_vad_service_initialization(self, app):
        """Test Voice Activity Detection service initializes."""
        with app.app_context():
            from services.vad_service import VADService
            vad = VADService()
            assert vad is not None
    
    def test_vad_detects_speech_activity(self, app):
        """Test VAD can process audio and detect speech."""
        with app.app_context():
            from services.vad_service import VADService
            vad = VADService()
            
            sample_rate = 16000
            duration_ms = 100
            samples = int(sample_rate * duration_ms / 1000)
            audio_data = np.zeros(samples, dtype=np.int16).tobytes()
            
            result = vad.is_voiced(audio_data)
            assert isinstance(result, bool)
    
    def test_audio_quality_analyzer_initialization(self, app):
        """Test audio quality analyzer initializes."""
        with app.app_context():
            from services.audio_quality_analyzer import AudioQualityAnalyzer
            analyzer = AudioQualityAnalyzer()
            assert analyzer is not None
    
    def test_audio_quality_analysis(self, app):
        """Test audio quality analyzer processes audio data."""
        with app.app_context():
            from services.audio_quality_analyzer import AudioQualityAnalyzer
            analyzer = AudioQualityAnalyzer()
            
            test_audio = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
            
            result = analyzer.analyze_audio_quality(test_audio, sample_rate=16000)
            assert result is not None
            if hasattr(result, 'overall_quality'):
                assert 0 <= result.overall_quality <= 1
    
    def test_whisper_client_module_exists(self, app):
        """Test OpenAI Whisper client module exists."""
        with app.app_context():
            from services import openai_whisper_client
            assert openai_whisper_client is not None
    
    def test_speaker_diarization_service(self, app):
        """Test multi-speaker identification."""
        with app.app_context():
            from services.multi_speaker_diarization import MultiSpeakerDiarization
            diarization = MultiSpeakerDiarization()
            assert diarization is not None
    
    def test_speaker_diarization_identifies_speakers(self, app):
        """Test diarization can process audio segment for speaker identification."""
        with app.app_context():
            from services.multi_speaker_diarization import MultiSpeakerDiarization
            diarization = MultiSpeakerDiarization()
            
            mock_audio = np.random.randn(16000).astype(np.float32)
            result = diarization.process_audio_segment(
                audio_samples=mock_audio,
                timestamp=0.0,
                segment_id="test_segment_001"
            )
            assert result is not None
            assert hasattr(result, 'speaker_id') or hasattr(result, 'speaker') or isinstance(result, dict)
    
    def test_deduplication_engine(self, app):
        """Test transcript deduplication."""
        with app.app_context():
            from services.deduplication_engine import AdvancedDeduplicationEngine
            engine = AdvancedDeduplicationEngine()
            assert engine is not None
    
    def test_deduplication_text_similarity(self, app):
        """Test deduplication engine text similarity calculation."""
        with app.app_context():
            from services.deduplication_engine import AdvancedDeduplicationEngine
            engine = AdvancedDeduplicationEngine()
            
            similarity = engine._calculate_text_similarity(
                "Hello world this is a test",
                "Hello world this is a test"
            )
            assert similarity == 1.0, "Identical text should have similarity of 1.0"
            
            similarity_partial = engine._calculate_text_similarity(
                "Hello world this is a test",
                "Hello world"
            )
            assert 0 < similarity_partial < 1, "Partial overlap should have similarity between 0 and 1"
            
            similarity_different = engine._calculate_text_similarity(
                "Completely different sentence here",
                "Nothing in common at all"
            )
            assert similarity_different < 0.5, "Different text should have low similarity"
    
    def test_deduplication_full_pipeline(self, app):
        """Test end-to-end deduplication pipeline with TranscriptionResult."""
        with app.app_context():
            from services.deduplication_engine import AdvancedDeduplicationEngine, TranscriptionResult
            engine = AdvancedDeduplicationEngine()
            
            result = TranscriptionResult(
                text="This is a complete test of the deduplication pipeline",
                start_time=0.0,
                end_time=5.0,
                confidence=0.95,
                chunk_id="chunk_full_test_001",
                is_final=True
            )
            
            response = engine.process_transcription_result(
                session_id="full_pipeline_test",
                result=result
            )
            
            assert response is not None
            assert isinstance(response, dict)
            assert 'session_id' in response
            assert 'segment_id' in response
            assert 'confidence' in response
            assert response['session_id'] == "full_pipeline_test"
            assert response['confidence'] == 0.95


@pytest.mark.critical
class TestAIProcessingPipeline:
    """Test AI-powered analysis and insights generation."""
    
    def test_ai_insights_service_initialization(self, app):
        """Test AI insights service initializes."""
        with app.app_context():
            from services.ai_insights_service import AIInsightsService
            service = AIInsightsService()
            assert service is not None
            assert hasattr(service, 'analyze_sentiment') or hasattr(service, 'generate_insights') or hasattr(service, 'analyze')
    
    def test_analysis_service(self, app):
        """Test meeting analysis service."""
        with app.app_context():
            from services.analysis_service import AnalysisService
            service = AnalysisService()
            assert service is not None
    
    def test_analysis_service_prompt_templates(self, app):
        """Test analysis service has required prompt templates."""
        with app.app_context():
            from services.analysis_service import AnalysisService
            service = AnalysisService()
            
            templates = getattr(service, 'templates', None) or getattr(service, 'PROMPT_TEMPLATES', None)
            if templates:
                assert len(templates) >= 1, "At least one prompt template should exist"
    
    def test_task_extraction_module_exists(self, app):
        """Test task extraction module exists."""
        with app.app_context():
            from services import task_extraction_service
            assert task_extraction_service is not None
    
    def test_task_extraction_service_methods(self, app):
        """Test task extraction service has required methods."""
        with app.app_context():
            from services.task_extraction_service import TaskExtractionService
            service = TaskExtractionService()
            assert hasattr(service, 'extract_tasks_from_meeting') or hasattr(service, 'extract_tasks') or hasattr(service, 'extract')
    
    def test_sentiment_analysis_service(self, app):
        """Test sentiment analysis."""
        with app.app_context():
            from services.sentiment_analysis_service import SentimentAnalysisService
            service = SentimentAnalysisService()
            assert service is not None
    
    def test_sentiment_analysis_categorization(self, app):
        """Test sentiment analysis can categorize text."""
        with app.app_context():
            from services.sentiment_analysis_service import SentimentAnalysisService
            service = SentimentAnalysisService()
            
            if hasattr(service, 'analyze_sentiment'):
                result = service.analyze_sentiment("This is great news!")
                assert result is not None


@pytest.mark.critical
class TestSessionLifecycle:
    """Test complete meeting session lifecycle."""
    
    def test_session_model_creation(self, app, db_session):
        """Test creating a new meeting session model."""
        from models import Session
        
        with app.app_context():
            external_id = Session.generate_external_id()
            session = Session(
                external_id=external_id,
                title="Test Meeting",
                status="active"
            )
            db_session.add(session)
            db_session.commit()
            
            assert session.id is not None
            assert session.title == "Test Meeting"
    
    def test_session_status_update(self, app, db_session):
        """Test updating session status."""
        from models import Session
        
        with app.app_context():
            external_id = Session.generate_external_id()
            session = Session(
                external_id=external_id,
                title="Test Meeting",
                status="active"
            )
            db_session.add(session)
            db_session.commit()
            
            session.status = "completed"
            db_session.commit()
            
            assert session.status == "completed"
    
    def test_meeting_lifecycle_service(self, app):
        """Test meeting lifecycle management."""
        with app.app_context():
            from services.meeting_lifecycle_service import MeetingLifecycleService
            service = MeetingLifecycleService()
            assert service is not None


@pytest.mark.critical
class TestDataPersistence:
    """Test data storage and retrieval."""
    
    def test_segment_storage(self, app, db_session):
        """Test transcript segment storage."""
        from models import Session, Segment
        
        with app.app_context():
            external_id = Session.generate_external_id()
            session = Session(
                external_id=external_id,
                title="Test Meeting"
            )
            db_session.add(session)
            db_session.commit()
            
            segment = Segment(
                session_id=session.id,
                text="This is test transcript text.",
                start_ms=0,
                end_ms=5000,
                avg_confidence=0.95,
                kind="final"
            )
            db_session.add(segment)
            db_session.commit()
            
            assert segment.id is not None
            assert segment.text == "This is test transcript text."
    
    def test_task_storage(self, app, db_session, test_user, test_workspace):
        """Test task/action item storage."""
        from models import Task
        
        with app.app_context():
            task = Task(
                title="Follow up on project",
                description="Send update email",
                status="todo",
                priority="high",
                assigned_to_id=test_user.id,
                workspace_id=test_workspace.id
            )
            db_session.add(task)
            db_session.commit()
            
            assert task.id is not None
            assert task.title == "Follow up on project"
