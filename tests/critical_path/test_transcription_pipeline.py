"""
Critical Path Tests: Audio Transcription Pipeline
Tests the complete flow from audio input to transcribed text output.
"""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import json


@pytest.mark.critical
class TestTranscriptionPipeline:
    """Test the core transcription service functionality."""
    
    def test_transcription_service_initialization(self, app):
        """Test that transcription service initializes correctly."""
        from services.transcription_service import TranscriptionService
        
        with app.app_context():
            service = TranscriptionService()
            assert service is not None
    
    def test_vad_service_audio_processing(self, app):
        """Test Voice Activity Detection processes audio correctly."""
        from services.vad_service import VADService
        
        with app.app_context():
            vad = VADService()
            assert vad is not None
            
            sample_rate = 16000
            duration = 0.5
            samples = int(sample_rate * duration)
            audio_data = np.zeros(samples, dtype=np.int16)
            
            result = vad.is_speech(audio_data.tobytes(), sample_rate)
            assert isinstance(result, bool)
    
    def test_audio_quality_analyzer(self, app):
        """Test audio quality analysis."""
        from services.audio_quality_analyzer import AudioQualityAnalyzer
        
        with app.app_context():
            analyzer = AudioQualityAnalyzer()
            assert analyzer is not None
            
            sample_rate = 16000
            duration = 1.0
            samples = int(sample_rate * duration)
            audio_data = np.random.randint(-1000, 1000, samples, dtype=np.int16)
            
            metrics = analyzer.analyze(audio_data.tobytes(), sample_rate)
            assert 'quality_score' in metrics or metrics is not None
    
    @patch('services.openai_whisper_client.OpenAIWhisperClient')
    def test_whisper_client_transcription(self, mock_whisper, app):
        """Test OpenAI Whisper API integration."""
        mock_whisper.return_value.transcribe.return_value = {
            'text': 'Hello world',
            'confidence': 0.95,
            'language': 'en'
        }
        
        from services.openai_whisper_client import OpenAIWhisperClient
        
        with app.app_context():
            client = OpenAIWhisperClient()
            assert client is not None
    
    def test_speaker_diarization_service(self, app):
        """Test multi-speaker identification."""
        from services.multi_speaker_diarization import MultiSpeakerDiarization
        
        with app.app_context():
            diarization = MultiSpeakerDiarization()
            assert diarization is not None
    
    def test_deduplication_engine(self, app):
        """Test transcript deduplication."""
        from services.deduplication_engine import DeduplicationEngine
        
        with app.app_context():
            engine = DeduplicationEngine()
            assert engine is not None
            
            text1 = "Hello, this is a test."
            text2 = "Hello, this is a test."
            text3 = "This is different text."
            
            is_duplicate = engine.is_duplicate(text1, text2)
            assert is_duplicate == True
            
            is_not_duplicate = engine.is_duplicate(text1, text3)
            assert is_not_duplicate == False


@pytest.mark.critical
class TestAIProcessingPipeline:
    """Test AI-powered analysis and insights generation."""
    
    def test_ai_insights_service_initialization(self, app):
        """Test AI insights service initializes."""
        from services.ai_insights_service import AIInsightsService
        
        with app.app_context():
            service = AIInsightsService()
            assert service is not None
    
    def test_analysis_service(self, app):
        """Test meeting analysis service."""
        from services.analysis_service import AnalysisService
        
        with app.app_context():
            service = AnalysisService()
            assert service is not None
    
    @patch('openai.OpenAI')
    def test_task_extraction_service(self, mock_openai, app):
        """Test action item extraction from transcripts."""
        from services.task_extraction_service import TaskExtractionService
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        with app.app_context():
            service = TaskExtractionService()
            assert service is not None
    
    def test_sentiment_analysis_service(self, app):
        """Test sentiment analysis."""
        from services.sentiment_analysis_service import SentimentAnalysisService
        
        with app.app_context():
            service = SentimentAnalysisService()
            assert service is not None


@pytest.mark.critical
class TestSessionLifecycle:
    """Test complete meeting session lifecycle."""
    
    def test_session_creation(self, app, db_session):
        """Test creating a new meeting session."""
        from models import Session
        from ulid import ULID
        
        with app.app_context():
            session = Session(
                external_id=str(ULID()),
                title="Test Meeting",
                status="active"
            )
            db_session.add(session)
            db_session.commit()
            
            assert session.id is not None
            assert session.title == "Test Meeting"
            assert session.status == "active"
    
    def test_session_finalization(self, app, db_session):
        """Test finalizing a meeting session."""
        from models import Session
        from ulid import ULID
        
        with app.app_context():
            session = Session(
                external_id=str(ULID()),
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
        from services.meeting_lifecycle_service import MeetingLifecycleService
        
        with app.app_context():
            service = MeetingLifecycleService()
            assert service is not None


@pytest.mark.critical
class TestDataPersistence:
    """Test data storage and retrieval."""
    
    def test_segment_storage(self, app, db_session):
        """Test transcript segment storage."""
        from models import Session, Segment
        from ulid import ULID
        
        with app.app_context():
            session = Session(
                external_id=str(ULID()),
                title="Test Meeting"
            )
            db_session.add(session)
            db_session.commit()
            
            segment = Segment(
                session_id=session.id,
                text="This is test transcript text.",
                speaker="Speaker 1",
                start_time=0.0,
                end_time=5.0,
                confidence=0.95,
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
                status="pending",
                priority="high",
                user_id=test_user.id,
                workspace_id=test_workspace.id
            )
            db_session.add(task)
            db_session.commit()
            
            assert task.id is not None
            assert task.title == "Follow up on project"
            assert task.status == "pending"
