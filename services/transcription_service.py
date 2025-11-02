"""
Transcription Service Orchestrator
High-level orchestration service that coordinates VAD, audio processing, and Whisper streaming.
Consolidates superior orchestration logic from real-time transcription improvements.
"""

import logging
import asyncio
import time
import uuid
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, asdict
from enum import Enum

# 🔧 FIXED: Use TYPE_CHECKING imports to prevent circular import issues
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .vad_service import VADService, VADConfig
    from .whisper_streaming import WhisperStreamingService, TranscriptionConfig, TranscriptionResult  
    from .audio_processor import AudioProcessor
    from .audio_quality_monitor import AudioQualityMonitor, AudioQualityConfig, AGCConfig
    from .confidence_scoring import AdvancedConfidenceScorer, ConfidenceConfig
    from .audio_quality_analyzer import AudioQualityAnalyzer, QualityEnhancementConfig
    from .performance_optimizer import PerformanceOptimizer, ResourceLimits
# FIXED: Import models properly
from models import Session, Segment
from app import db
from services.session_service import SessionService
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

class SessionState(Enum):
    """Session state enumeration."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class TranscriptionServiceConfig:
    """Configuration for transcription service."""
    # VAD configuration
    vad_sensitivity: float = 0.5
    vad_min_speech_duration: int = 300  # ms - ITERATION 2: Further optimized for faster response
    vad_min_silence_duration: int = 400  # ms
    
    # Audio processing
    sample_rate: int = 16000
    chunk_size: int = 1024
    audio_format: str = "webm"
    
    # Transcription settings
    language: str = "en"
    min_confidence: float = 0.75  # 🔥 ACCURACY FIX: Increased for Google Recorder quality
    enable_speaker_detection: bool = True
    enable_sentiment_analysis: bool = False
    
    # Processing limits
    max_chunk_duration: float = 30.0  # seconds
    min_chunk_duration: float = 0.1   # seconds
    max_concurrent_sessions: int = 10
    
    # Real-time settings
    enable_realtime: bool = True
    interim_results: bool = True
    backpressure_threshold: int = 5  # max queued audio chunks
    
    # 🔥 PHASE 2: Advanced streaming optimization
    adaptive_streaming: bool = True
    streaming_mode: str = "realtime"  # realtime, batch, adaptive
    quality_monitoring: bool = True
    bandwidth_adaptation: bool = True
    latency_target_ms: int = 150  # ITERATION 2: More aggressive latency target
    transmission_optimization: bool = True
    buffer_size_adaptation: bool = True
    
    # 🔥 INT-LIVE-I3: Interim throttling and endpointing
    interim_throttle_ms: int = 150  # Throttle interims to ~150ms - ITERATION 2: More aggressive
    min_token_diff: int = 5  # Minimum token difference to emit interim
    punctuation_boundary_chars: str = '.!?;:'
    min_tokens_for_punctuation_final: int = 3  # Min tokens before punctuation triggers final
    vad_tail_silence_ms: int = 1500  # VAD silence duration to trigger final

class TranscriptionService:
    """
    High-level transcription service that orchestrates VAD, audio processing, and Whisper streaming.
    Provides a unified interface for real-time meeting transcription with enhanced coordination.
    🔥 INT-LIVE-I3: Enhanced with interim throttling, endpointing, and metrics.
    """
    
    def __init__(self, config: Optional[TranscriptionServiceConfig] = None):
        # 🔧 FIXED: Import services here to avoid circular imports
        from .vad_service import VADService, VADConfig
        from .whisper_streaming import WhisperStreamingService, TranscriptionConfig
        from .audio_processor import AudioProcessor
        from .audio_quality_analyzer import AudioQualityAnalyzer, QualityEnhancementConfig
        from .performance_optimizer import PerformanceOptimizer, ResourceLimits
        
        # Import app and db for database operations with context management
        from app import db
        
        # Initialize memory management
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
        
        self.config = config or TranscriptionServiceConfig()
        
        # 🔥 INT-LIVE-I3: Session-level interim throttling and metrics
        self.session_interim_state = {}  # {session_id: {last_interim_time, last_text, metrics}}
        
        # Import and initialize interim throttler
        try:
            from interim_throttling import get_interim_throttler
            self.interim_throttler = get_interim_throttler(self.config)
        except ImportError:
            self.interim_throttler = None  # Fallback if module doesn't exist
        
        # Initialize sub-services
        vad_config = VADConfig(
            sensitivity=self.config.vad_sensitivity,
            min_speech_duration=self.config.vad_min_speech_duration,
            min_silence_duration=self.config.vad_min_silence_duration,
            sample_rate=self.config.sample_rate
        )
        self.vad_service = VADService(vad_config)
        
        transcription_config = TranscriptionConfig(
            language=self.config.language,
            max_chunk_duration=self.config.max_chunk_duration,
            min_chunk_duration=self.config.min_chunk_duration,
            confidence_threshold=self.config.min_confidence
        )
        self.whisper_service = WhisperStreamingService(transcription_config)
        
        self.audio_processor = AudioProcessor()
        
        # 🔥 PHASE 3: Initialize audio quality analyzer
        quality_config = QualityEnhancementConfig(
            enable_noise_reduction=True,
            enable_dynamic_range_compression=True,
            enable_spectral_enhancement=True,
            target_snr_db=20.0,
            quality_threshold=0.7
        )
        self.quality_analyzer = AudioQualityAnalyzer(quality_config)
        
        # 🔥 PHASE 4: Initialize performance optimizer
        resource_limits = ResourceLimits(
            max_cpu_usage=80.0,
            max_memory_usage=85.0,
            max_concurrent_sessions=self.config.max_concurrent_sessions,
            latency_threshold_ms=self.config.latency_target_ms
        )
        self.performance_optimizer = PerformanceOptimizer(resource_limits)
        self.performance_optimizer.start_monitoring()
        
        # Session management
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_callbacks: Dict[str, List[Callable]] = {}
        
        # Processing queues and stats
        self.processing_queue_size = 0
        self.total_sessions = 0
        self.total_segments = 0
        self.average_processing_time = 0.0
        
        # 🔥 PHASE 2: Advanced streaming metrics and adaptive state
        self.streaming_metrics = {
            'total_bytes_processed': 0,
            'average_chunk_latency': 0.0,
            'quality_score': 1.0,
            'bandwidth_utilization': 0.0,
            'transmission_efficiency': 1.0,
            'adaptive_adjustments': 0,
            'buffer_optimization_events': 0
        }
        
        self.adaptive_state = {
            'target_latency': self.config.latency_target_ms,
            'current_buffer_strategy': 'aggressive',  # OPTIMIZED: aggressive for faster first interim
            'quality_trend': 'stable',  # improving, stable, degrading
            'last_adaptation': 0
        }
        
        # Set up Whisper service callback
        self.whisper_service.set_result_callback(self._on_transcription_result)
        
        # 🔥 CRITICAL FIX: Much less aggressive quality control to fix 92.3% WER
        self.dedup_buffer_size = 200  # Characters
        self.min_word_variety_ratio = 0.1  # 🔥 REDUCED: Much less aggressive - was 0.2
        
        logger.info("Transcription service initialized with all phases (1-4) enabled")
        self.max_repetition_threshold = 6  # 🔥 INCREASED: Allow more repetition - was 4
        self.min_meaningful_length = 1  # Allow single words
        
        # 🔥 INT-LIVE-I2: Adaptive confidence gating with hysteresis
        import os
        self.base_confidence = float(os.environ.get('MIN_CONFIDENCE', '0.6'))
        self.hysteresis_window = []  # Track recent confidence decisions
        self.hysteresis_size = 2  # Require 2 consecutive frames for state change
        self.suppression_active = False  # Current suppression state
        
        # 🔥 INT-LIVE-I2: Interim throttling and punctuation boundary detection
        self.interim_throttle_ms = 200  # OPTIMIZED: 200ms for faster first interim response
        self.min_interim_diff_chars = 5  # Minimum character difference for interim emit
        self.punctuation_marks = {'.', '!', '?', ';', ':'}  # Marks that trigger boundaries
        
        # Initialize performance monitoring and QA pipeline
        try:
            from .performance_monitor import performance_monitor
            from .qa_pipeline import qa_pipeline
            self.performance_monitor = performance_monitor
            self.qa_pipeline = qa_pipeline
            logger.info("Performance monitoring and QA pipeline initialized")
        except ImportError as e:
            logger.warning(f"Could not initialize monitoring services: {e}")
            self.performance_monitor = None
            self.qa_pipeline = None
        
        logger.info(f"Transcription service initialized with config: {asdict(self.config)}")
    
    def _compute_adaptive_confidence(self, vad_result: Optional[Dict[str, Any]]) -> float:
        """
        🔥 INT-LIVE-I2: Compute adaptive confidence threshold based on VAD quality.
        
        Args:
            vad_result: VAD analysis result with confidence/SNR metrics
            
        Returns:
            Adaptive confidence threshold (0.4 to 0.8 range)
        """
        # Start with base confidence from config
        base = self.base_confidence
        
        # Adjust based on VAD confidence if available
        if vad_result and 'confidence' in vad_result:
            vad_conf = vad_result['confidence']
            # If VAD confidence is low (poor signal), raise the threshold
            # If VAD confidence is high (clear signal), lower the threshold
            adjustment = 0.15 * (0.6 - vad_conf)
            adaptive = base + adjustment
        else:
            # No VAD info, use base threshold
            adaptive = base
        
        # Clamp to reasonable range
        return max(0.4, min(0.8, adaptive))
    
    def _create_wav_from_chunks(self, audio_chunks: List[bytes]) -> bytes:
        """Create a proper WAV file from buffered audio chunks."""
        try:
            import wave
            from io import BytesIO
            
            # Extract raw audio data from chunks
            raw_audio_data = b''
            for chunk in audio_chunks:
                if chunk.startswith(b'RIFF'):
                    # Skip WAV header (44 bytes) and get audio data
                    raw_audio_data += chunk[44:]
                else:
                    # Assume raw PCM data
                    raw_audio_data += chunk
            
            if not raw_audio_data:
                return b''
                
            # Create proper WAV file
            wav_buffer = BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(16000)  # 16kHz
                wav_file.writeframes(raw_audio_data)
            
            wav_buffer.seek(0)
            return wav_buffer.getvalue()
            
        except Exception as e:
            logger.warning(f"Failed to create WAV from buffer: {e}")
            # Fallback: just concatenate chunks
            return b''.join(audio_chunks)
    
    def _apply_hysteresis_gating(self, confidence: float, threshold: float) -> bool:
        """
        🔥 INT-LIVE-I2: Apply hysteresis gating - require 2 consecutive frames for state change.
        
        Args:
            confidence: Current transcription confidence
            threshold: Adaptive confidence threshold
            
        Returns:
            True if should suppress, False if should allow
        """
        # Determine if this frame would be suppressed based on confidence
        would_suppress = confidence < threshold
        
        # Add to hysteresis window
        self.hysteresis_window.append(would_suppress)
        
        # Keep only recent decisions
        if len(self.hysteresis_window) > self.hysteresis_size:
            self.hysteresis_window.pop(0)
        
        # Need at least 2 frames to make a decision
        if len(self.hysteresis_window) < self.hysteresis_size:
            return self.suppression_active  # Use current state
        
        # Check if all recent frames agree on the decision
        all_suppress = all(self.hysteresis_window)
        all_allow = not any(self.hysteresis_window)
        
        if all_suppress and not self.suppression_active:
            # Switch to suppression mode
            self.suppression_active = True
            return True
        elif all_allow and self.suppression_active:
            # Switch to allow mode
            self.suppression_active = False
            return False
        else:
            # No consensus or no change needed, maintain current state
            return self.suppression_active
    
    def _should_emit_interim(self, text: str, now: float, last_emit: float, state: Dict[str, Any]) -> bool:
        """
        🔥 INT-LIVE-I2: Intelligent interim emission with throttling and punctuation boundaries.
        
        Args:
            text: Current transcription text buffer
            now: Current timestamp
            last_emit: Last interim emission timestamp  
            state: Session state
            
        Returns:
            True if should emit interim transcript
        """
        if not text or len(text.strip()) == 0:
            return False
        
        # Get last emitted text for diff comparison
        last_text = state.get('last_interim_text', '')
        
        # Check time-based throttling (300-500ms range)
        time_threshold = (now - last_emit) >= (self.interim_throttle_ms / 1000.0)
        
        # Check if there's meaningful new content (≥5 chars or punctuation)
        char_diff = len(text) - len(last_text)
        has_meaningful_diff = char_diff >= self.min_interim_diff_chars
        
        # Check if punctuation boundary was hit
        has_punctuation = any(p in text[-10:] for p in self.punctuation_marks)  # Check last 10 chars
        
        # Emit if time passed AND (meaningful diff OR punctuation boundary)
        should_emit = time_threshold and (has_meaningful_diff or has_punctuation)
        
        if should_emit:
            state['last_interim_text'] = text  # Update for next diff
            # 🔥 INT-LIVE-I2: Track punctuation boundaries
            if has_punctuation:
                state.get('stats', {})['punctuation_boundaries'] = state.get('stats', {}).get('punctuation_boundaries', 0) + 1
        
        return should_emit
    
    # Sync wrapper methods for Flask routes (avoids asyncio.run() in request handlers)
    def start_session_sync(self, session_id: Optional[str] = None, 
                          user_config: Optional[Dict[str, Any]] = None) -> str:
        """Synchronous wrapper for start_session."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we can't use asyncio.run
                # For now, we'll create the session synchronously
                return self._start_session_sync_impl(session_id, user_config)
            else:
                return asyncio.run(self.start_session(session_id, user_config))
        except RuntimeError:
            # No event loop running
            return asyncio.run(self.start_session(session_id, user_config))
    
    def _start_session_sync_impl(self, session_id: Optional[str] = None, 
                                user_config: Optional[Dict[str, Any]] = None) -> str:
        """Direct synchronous implementation for start_session."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if len(self.active_sessions) >= self.config.max_concurrent_sessions:
            raise Exception(f"Maximum concurrent sessions ({self.config.max_concurrent_sessions}) reached")
        
        # Create database session - FIXED model fields
        def get_session_model():
            from models.session import Session
            return Session
        
        db_session = get_session_model()(
            external_id=session_id,  # FIXED: Use external_id instead of session_id
            title="Transcription Session",
            status='active',  # FIXED: Use 'active' instead of 'created'  
            locale=self.config.language,
            meta={
                'enable_realtime': self.config.enable_realtime,
                'enable_speaker_detection': self.config.enable_speaker_detection,
                'enable_sentiment_analysis': self.config.enable_sentiment_analysis,
                'sample_rate': self.config.sample_rate,
                'min_confidence': self.config.min_confidence,
                'vad_sensitivity': self.config.vad_sensitivity,
                'vad_min_speech_duration': self.config.vad_min_speech_duration,
                'vad_min_silence_duration': self.config.vad_min_silence_duration
            }
        )
        
        # Apply user configuration overrides
        if user_config:
            for key, value in user_config.items():
                if hasattr(db_session, key):
                    setattr(db_session, key, value)
        
        db.session.add(db_session)
        db.session.commit()
        
        # Initialize session state
        self.active_sessions[session_id] = {
            'state': SessionState.IDLE,
            'created_at': time.time(),
            'last_activity': time.time(),
            'sequence_number': 0,
            'audio_chunks': [],
            'pending_processing': 0,
            'stats': {
                'total_audio_duration': 0.0,
                'speech_duration': 0.0,
                'silence_duration': 0.0,
                'total_segments': 0,
                'average_confidence': 0.0
            }
        }
        
        self.session_callbacks[session_id] = []
        
        # Initialize sub-services for this session
        self.vad_service.reset_state()
        # Note: whisper_service.start_session is async, but for sync mode we'll defer this
        
        self.total_sessions += 1
        logger.info(f"Started transcription session (sync): {session_id}")
        
        return session_id
    
    def end_session_sync(self, session_id: str) -> Dict[str, Any]:
        """Synchronous wrapper for end_session."""
        return self._end_session_sync_impl(session_id)
    
    def _end_session_sync_impl(self, session_id: str) -> Dict[str, Any]:
        """Direct synchronous implementation for end_session."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session_data = self.active_sessions[session_id]
        
        # Update database session
        from sqlalchemy import select
        stmt = select(Session).filter_by(external_id=session_id)
        db_session = db.session.execute(stmt).scalar_one_or_none()
        if db_session:
            db_session.status = 'completed'
            db.session.commit()
            
            # Update final statistics
            stats = session_data['stats']
            db_session.total_segments = stats['total_segments']
            db_session.average_confidence = stats['average_confidence']
            db_session.total_duration = stats['total_audio_duration']
            db.session.commit()
        
        # Get final statistics
        final_stats = self._get_session_statistics(session_id)
        
        # Cleanup
        del self.active_sessions[session_id]
        del self.session_callbacks[session_id]
        
        # 🔥 PHASE 4: Unregister session from performance optimizer
        try:
            self.performance_optimizer.unregister_session(session_id)
        except Exception as e:
            logger.warning(f"Failed to unregister session from performance optimizer: {e}")
        
        logger.info(f"Ended transcription session (sync): {session_id}")
        return final_stats

    def _save_transcription_text(self, session_id: str, text: str, confidence: float = 0.0, workspace_id: int = None, user_id: int = None) -> None:
        """
        Save transcription text into the database and update session statistics.
        
        Args:
            session_id: External session identifier
            text: Transcribed text
            confidence: Transcription confidence score
            workspace_id: Required workspace ID for proper data scoping
            user_id: Required user ID for session ownership
        """
        try:
            from models.session import Session
            from models.segment import Segment  # or Transcript, depending on your model naming
            from datetime import datetime
            from sqlalchemy import select
            from app import db
            import logging

            logger = logging.getLogger(__name__)

            # ✅ 1. Retrieve existing session or create one
            stmt = select(Session).filter_by(external_id=session_id)
            db_session = db.session.execute(stmt).scalar_one_or_none()
            if not db_session:
                # 🔒 CROWN¹⁰ Fix: Require workspace_id for proper data scoping
                if workspace_id is None:
                    logger.error(f"❌ Cannot create session without workspace_id: {session_id}")
                    raise ValueError("workspace_id is required when creating new sessions")
                if user_id is None:
                    logger.warning(f"⚠️ Creating session without user_id: {session_id}")
                
                db_session = Session(
                    external_id=session_id,
                    title="Live Transcription Session",
                    status="active",
                    workspace_id=workspace_id,  # ✅ Always set workspace
                    user_id=user_id,  # ✅ Track session owner
                    started_at=datetime.utcnow(),
                )
                db.session.add(db_session)
                db.session.commit()
                logger.info(f"✅ Created session {session_id} in workspace {workspace_id} for user {user_id}")

            # ✅ 2. Create new segment/transcript entry
            segment = Segment(
                session_id=db_session.id,
                text=text,
                confidence=confidence,
                created_at=datetime.utcnow(),
            )
            db.session.add(segment)

            # ✅ 3. Update session summary stats
            db_session.total_segments = (db_session.total_segments or 0) + 1
            db_session.average_confidence = (
                (db_session.average_confidence or 0) + confidence
            ) / db_session.total_segments
            db_session.last_updated = datetime.utcnow()

            # ✅ 4. Commit all changes
            db.session.commit()
            logger.info(f"[DB] ✅ Saved transcript for session {session_id}")

        except Exception as e:
            db.session.rollback()
            logger.error(f"[DB] ❌ Failed to save transcript: {e}")

    async def start_session(self, session_id: Optional[str] = None, 
                           user_config: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a new transcription session.
        
        Args:
            session_id: Optional session ID, will generate if None
            user_config: Optional user-specific configuration overrides
            
        Returns:
            Session ID
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if len(self.active_sessions) >= self.config.max_concurrent_sessions:
            raise Exception(f"Maximum concurrent sessions ({self.config.max_concurrent_sessions}) reached")
        
        # Create database session - FIXED model fields
        def get_session_model():
            from models.session import Session
            return Session
        
        db_session = get_session_model()(
            external_id=session_id,  # FIXED: Use external_id instead of session_id
            title="Transcription Session",
            status='active',  # FIXED: Use 'active' instead of 'created'  
            locale=self.config.language,
            meta={
                'enable_realtime': self.config.enable_realtime,
                'enable_speaker_detection': self.config.enable_speaker_detection,
                'enable_sentiment_analysis': self.config.enable_sentiment_analysis,
                'sample_rate': self.config.sample_rate,
                'min_confidence': self.config.min_confidence,
                'vad_sensitivity': self.config.vad_sensitivity,
                'vad_min_speech_duration': self.config.vad_min_speech_duration,
                'vad_min_silence_duration': self.config.vad_min_silence_duration
            }
        )
        
        # Apply user configuration overrides
        if user_config:
            for key, value in user_config.items():
                if hasattr(db_session, key):
                    setattr(db_session, key, value)
        
        db.session.add(db_session)
        db.session.commit()
        
        # Initialize session state
        self.active_sessions[session_id] = {
            'state': SessionState.IDLE,
            'created_at': time.time(),
            'last_activity': time.time(),
            'sequence_number': 0,
            'audio_chunks': [],
            'pending_processing': 0,
            'stats': {
                'total_audio_duration': 0.0,
                'speech_duration': 0.0,
                'silence_duration': 0.0,
                'total_segments': 0,
                'average_confidence': 0.0
            }
        }
        
        self.session_callbacks[session_id] = []
        
        # Initialize sub-services for this session
        self.vad_service.reset_state()
        self.whisper_service.start_session(session_id)
        
        # 🔥 PHASE 4: Register session with performance optimizer
        self.performance_optimizer.register_session(session_id, {
            'config': user_config or {},
            'start_time': time.time()
        })
        
        self.total_sessions += 1
        # 🔥 PHASE 2: Initialize adaptive streaming for session
        if self.config.adaptive_streaming:
            self._initialize_session_streaming_optimization(session_id)
        
        logger.info(f"Started transcription session: {session_id}")
        
        return session_id
    
    # 🔥 PHASE 2: Session-level streaming optimization
    def _initialize_session_streaming_optimization(self, session_id: str):
        """Initialize adaptive streaming optimization for session."""
        session_data = self.active_sessions[session_id]
        session_data['streaming_state'] = {
            'buffer_strategy': self.adaptive_state['current_buffer_strategy'],
            'quality_measurements': [],
            'latency_history': [],
            'transmission_efficiency': 1.0,
            'last_optimization': time.time()
        }
        self.streaming_metrics['adaptive_adjustments'] += 1
    
    # 🔥 PHASE 2: Adaptive streaming optimization
    def optimize_streaming_performance(self, session_id: str, metrics: Dict[str, Any]):
        """Optimize streaming performance based on real-time metrics."""
        if not self.config.adaptive_streaming or session_id not in self.active_sessions:
            return
        
        session_data = self.active_sessions[session_id]
        streaming_state = session_data.get('streaming_state', {})
        
        # Analyze current performance
        current_latency = metrics.get('latency', 0)
        quality_score = metrics.get('quality_score', 1.0)
        transmission_efficiency = metrics.get('transmission_efficiency', 1.0)
        
        # Update streaming metrics
        self.streaming_metrics['average_chunk_latency'] = (
            self.streaming_metrics['average_chunk_latency'] * 0.9 + current_latency * 0.1
        )
        self.streaming_metrics['quality_score'] = quality_score
        self.streaming_metrics['transmission_efficiency'] = transmission_efficiency
        
        # Adaptive optimization logic
        if current_latency > self.adaptive_state['target_latency'] * 1.5:
            self._optimize_for_latency(session_id, streaming_state)
        elif quality_score < 0.7:
            self._optimize_for_quality(session_id, streaming_state)
        
        streaming_state['last_optimization'] = time.time()
    
    def _optimize_for_latency(self, session_id: str, streaming_state: Dict[str, Any]):
        """Optimize streaming for lower latency."""
        if streaming_state.get('buffer_strategy') != 'aggressive':
            streaming_state['buffer_strategy'] = 'aggressive'
            self.streaming_metrics['buffer_optimization_events'] += 1
            logger.info(f"Optimized session {session_id} for latency (aggressive buffering)")
    
    def _optimize_for_quality(self, session_id: str, streaming_state: Dict[str, Any]):
        """Optimize streaming for better quality."""
        if streaming_state.get('buffer_strategy') != 'conservative':
            streaming_state['buffer_strategy'] = 'conservative'
            self.streaming_metrics['buffer_optimization_events'] += 1
            logger.info(f"Optimized session {session_id} for quality (conservative buffering)")
    
    # 🔥 PHASE 3: Enhanced audio quality analysis and improvement
    def _enhance_audio_with_quality_analysis(self, audio_data: bytes, session_id: str) -> bytes:
        """Apply quality analysis and enhancement to audio data."""
        try:
            # Convert bytes to numpy array for analysis
            import numpy as np
            
            # Convert audio bytes to numpy array (assuming 16-bit PCM)
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Analyze audio quality
            quality_metrics = self.quality_analyzer.analyze_audio_quality(audio_array)
            
            # Update session quality tracking
            session_data = self.active_sessions.get(session_id, {})
            streaming_state = session_data.get('streaming_state', {})
            if 'quality_measurements' not in streaming_state:
                streaming_state['quality_measurements'] = []
            
            streaming_state['quality_measurements'].append({
                'timestamp': quality_metrics.timestamp,
                'overall_quality': quality_metrics.overall_quality,
                'snr_db': quality_metrics.snr_db,
                'noise_level': quality_metrics.noise_level
            })
            
            # Keep only recent measurements
            streaming_state['quality_measurements'] = streaming_state['quality_measurements'][-10:]
            
            # Apply enhancement if quality is below threshold
            if quality_metrics.overall_quality < self.quality_analyzer.config.quality_threshold:
                enhanced_array = self.quality_analyzer.enhance_audio_quality(audio_array, quality_metrics)
                
                # Convert back to bytes
                enhanced_audio = (enhanced_array * 32767).astype(np.int16).tobytes()
                
                logger.debug(f"Enhanced audio quality for session {session_id}: "
                           f"{quality_metrics.overall_quality:.2f} -> improved")
                return enhanced_audio
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Error in audio quality enhancement: {e}")
            return audio_data  # Return original on error
    
    # 🔥 PHASE 4: Get comprehensive service statistics
    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all service components."""
        base_stats = {
            'total_sessions': self.total_sessions,
            'active_sessions': len(self.active_sessions),
            'total_segments': self.total_segments,
            'average_processing_time': self.average_processing_time,
            'processing_queue_size': self.processing_queue_size
        }
        
        # Add streaming metrics
        base_stats['streaming_metrics'] = self.streaming_metrics.copy()
        base_stats['adaptive_state'] = self.adaptive_state.copy()
        
        # Add quality analyzer statistics
        if hasattr(self, 'quality_analyzer') and hasattr(self.quality_analyzer, 'get_quality_statistics'):
            base_stats['quality_statistics'] = self.quality_analyzer.get_quality_statistics()
        
        # Add performance optimizer statistics
        if hasattr(self, 'performance_optimizer') and hasattr(self.performance_optimizer, 'get_performance_statistics'):
            base_stats['performance_statistics'] = self.performance_optimizer.get_performance_statistics()
        
        return base_stats
    
    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """
        End a transcription session and return statistics.
        
        Args:
            session_id: Session ID to end
            
        Returns:
            Session statistics and metadata
        """
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session_data = self.active_sessions[session_id]
        
        # Process any remaining audio
        if session_data['audio_chunks']:
            # Process remaining chunks synchronously
            for chunk_data in session_data['audio_chunks']:
                try:
                    self.process_audio_sync(session_id, chunk_data['data'], is_final_signal=True)
                except Exception as e:
                    logger.error(f"Error processing pending audio: {e}")
            session_data['audio_chunks'].clear()
        
        # Update database session
        from sqlalchemy import select
        stmt = select(Session).filter_by(external_id=session_id)
        db_session = db.session.execute(stmt).scalar_one_or_none()
        if db_session:
            db_session.status = 'completed'
            db.session.commit()
            
            # Update final statistics
            stats = session_data['stats']
            db_session.total_segments = stats['total_segments']
            db_session.average_confidence = stats['average_confidence']
            db_session.total_duration = stats['total_audio_duration']
            db.session.commit()
        
        # End Whisper service session
        self.whisper_service.end_session()
        
        # Get final statistics
        final_stats = self._get_session_statistics(session_id)
        
        # Cleanup
        del self.active_sessions[session_id]
        del self.session_callbacks[session_id]
        
        logger.info(f"Ended transcription session: {session_id}")
        return final_stats
    
    async def process_audio(self, session_id: str, audio_data: bytes, 
                           timestamp: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Process audio chunk for real-time transcription.
        
        Args:
            session_id: Session ID
            audio_data: Raw audio bytes
            timestamp: Optional timestamp
            
        Returns:
            Processing result with interim/final transcription if available
        """
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        if timestamp is None:
            timestamp = time.time()
        
        session_data = self.active_sessions[session_id]
        
        # Check backpressure
        if session_data['pending_processing'] >= self.config.backpressure_threshold:
            logger.warning(f"Backpressure limit reached for session {session_id}")
            return None
        
        # Update session activity
        session_data['last_activity'] = timestamp
        session_data['state'] = SessionState.RECORDING
        
        # Process audio through pipeline
        result = await self._process_audio_pipeline(session_id, audio_data, timestamp)
        
        return result
    
    async def _process_audio_pipeline(self, session_id: str, audio_data: bytes, 
                                     timestamp: float) -> Optional[Dict[str, Any]]:
        """Process audio through the complete pipeline."""
        session_data = self.active_sessions[session_id]
        
        try:
            # Step 1: Audio preprocessing
            processed_audio = self.audio_processor.normalize_audio(audio_data)
            processed_audio = self.audio_processor.apply_noise_gate(processed_audio, threshold=0.005)
            
            # Convert back to bytes for further processing
            audio_bytes = (processed_audio * 32767).astype(np.int16).tobytes()
            
            # Step 2: Voice Activity Detection
            vad_result = self.vad_service.process_audio_chunk(audio_bytes, timestamp)
            
            # Update statistics
            audio_duration = len(audio_data) / (self.config.sample_rate * 2)  # 16-bit audio
            session_data['stats']['total_audio_duration'] += audio_duration
            
            if vad_result.is_speech:
                session_data['stats']['speech_duration'] += audio_duration
            else:
                session_data['stats']['silence_duration'] += audio_duration
            
            # Step 3: Conditional transcription (only if speech detected or buffer full)
            transcription_result = None
            if self.config.enable_realtime and (vad_result.is_speech or vad_result.confidence > 0.3):
                session_data['pending_processing'] += 1
                try:
                    transcription_result = await self.whisper_service.process_audio_chunk(
                        audio_bytes, timestamp, is_final=False
                    )
                finally:
                    session_data['pending_processing'] -= 1
            
            # Prepare result
            result = {
                'session_id': session_id,
                'timestamp': timestamp,
                'vad': {
                    'is_speech': vad_result.is_speech,
                    'confidence': vad_result.confidence,
                    'energy': vad_result.energy
                },
                'audio_duration': audio_duration,
                'transcription': None
            }
            
            if transcription_result:
                result['transcription'] = self._format_transcription_result(transcription_result)
                
                # Store in database if final
                if transcription_result.is_final:
                    await self._store_segment(session_id, transcription_result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in audio pipeline for session {session_id}: {e}")
            session_data['state'] = SessionState.ERROR
            return None
    
    async def _store_segment(self, session_id: str, transcription_result: 'TranscriptionResult'):
        """Store transcription segment in database."""
        session_data = self.active_sessions[session_id]
        sequence_number = session_data['sequence_number']
        session_data['sequence_number'] += 1
        
        # Get database session ID from external ID
        from sqlalchemy import select
        from models.session import Session as DbSession
        
        stmt = select(DbSession).filter_by(external_id=session_id)
        db_session_obj = db.session.execute(stmt).scalar_one_or_none()
        
        if not db_session_obj:
            logger.error(f"Database session not found for external_id: {session_id}")
            return
            
        # Create segment using correct database schema
        from models.segment import Segment
        
        segment = Segment(
            session_id=db_session_obj.id,  # Use database ID, not external ID
            kind='final' if transcription_result.is_final else 'interim',
            text=transcription_result.text,
            avg_confidence=transcription_result.confidence,  # Correct field name
            start_ms=int((transcription_result.timestamp - transcription_result.duration) * 1000),
            end_ms=int(transcription_result.timestamp * 1000)
        )
        
        db.session.add(segment)
        db.session.commit()
        
        # Update session statistics
        self.total_segments += 1
        session_data['stats']['total_segments'] += 1
        
        # Update average confidence
        total_segments = session_data['stats']['total_segments']
        current_avg = session_data['stats']['average_confidence']
        new_avg = (current_avg * (total_segments - 1) + transcription_result.confidence) / total_segments
        session_data['stats']['average_confidence'] = new_avg
        
        # Update database session (using already retrieved db_session_obj)
        if db_session_obj:
            db_session_obj.total_segments = (db_session_obj.total_segments or 0) + 1
            db.session.commit()
        
        logger.debug(f"Stored segment {sequence_number} for session {session_id}")
    
    def _is_repetitive_text(self, text: str) -> bool:
        """
        Enhanced quality filter: Detect repetitive text patterns like 'You You You'.
        
        Args:
            text: Text to analyze
            
        Returns:
            True if text appears to be repetitive garbage
        """
        if not text or len(text.strip()) < 1:
            return True
            
        words = text.strip().lower().split()
        if len(words) < 1:
            return True
            
        # 🔥 CRITICAL FIX: Only block if 3+ consecutive identical words (was blocking after 2)
        consecutive_count = 1
        for i in range(len(words) - 1):
            if words[i] == words[i + 1] and len(words[i]) > 1:
                consecutive_count += 1
                if consecutive_count >= 3:  # 🔥 Changed from 2 to 3 - less aggressive
                    logger.warning(f"BLOCKED excessive repetition: '{text}' ({consecutive_count} consecutive '{words[i]}')")
                    return True
            else:
                consecutive_count = 1
        
        # Enhanced repetition detection for edge cases
        if len(words) >= 2:
            # Check for excessive repetition of same word
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
                
            # 🔥 CRITICAL FIX: Only flag if word appears 3+ times in short texts
            max_word_count = max(word_counts.values()) if word_counts else 0
            if len(words) <= 3 and max_word_count >= 3:  # 🔥 Changed from >1 to >=3
                most_common_word = max(word_counts, key=lambda k: word_counts[k]) if word_counts else ''
                logger.warning(f"BLOCKED short repetitive text: '{text}' ('{most_common_word}' appears {max_word_count} times)")
                return True
                
            # For longer texts, use threshold
            if len(words) > 3 and max_word_count > getattr(self, 'max_repetition_threshold', 2):
                most_common_word = max(word_counts, key=lambda k: word_counts[k]) if word_counts else ''
                logger.warning(f"BLOCKED repetitive text: '{text}' ('{most_common_word}' appears {max_word_count} times)")
                return True
                
            # Check word variety ratio for longer texts
            if len(words) > 3:
                unique_words = len(set(words))
                variety_ratio = unique_words / len(words)
                min_variety = getattr(self, 'min_word_variety_ratio', 0.6)
                
                if variety_ratio < min_variety:
                    logger.warning(f"BLOCKED low variety text: '{text}' (variety ratio: {variety_ratio:.2f})")
                    return True
            
        return False
    
    def _is_duplicate_of_recent(self, text: str, session_id: str) -> bool:
        """
        Check if text is substantially similar to recent transcription.
        
        Args:
            text: New text to check
            session_id: Session identifier
            
        Returns:
            True if text is likely a duplicate
        """
        if session_id not in self.active_sessions:
            return False
            
        session_data = self.active_sessions[session_id]
        rolling_text = session_data.get('rolling_text', '')
        
        if not rolling_text or not text:
            return False
            
        # 🔥 INT-LIVE-I2: Rolling Jaccard similarity on last ~80 chars with character n-grams
        WINDOW_SIZE = 80
        JACCARD_THRESHOLD = 0.85
        
        # Take last 80 chars of rolling buffer for comparison
        rolling_window = rolling_text[-WINDOW_SIZE:].lower().strip()
        text_lower = text.lower().strip()
        
        if not rolling_window or not text_lower:
            return False
        
        # Compute Jaccard similarity using character bigrams (more precise than word-level)
        jaccard_sim = self._jaccard_similarity_ngrams(text_lower, rolling_window, n=2)
        
        # Flag as duplicate if >85% similarity  
        if jaccard_sim > JACCARD_THRESHOLD:
            logger.debug(f"Rejected duplicate text: '{text}' (Jaccard similarity: {jaccard_sim:.3f})")
            return True
            
        return False
    
    def _format_transcription_result(self, result: 'TranscriptionResult') -> Dict[str, Any]:
        """Format transcription result for API response."""
        return {
            'text': result.text,
            'confidence': result.confidence,
            'is_final': result.is_final,
            'language': result.language,
            'duration': result.duration,
            'timestamp': result.timestamp,
            'words': result.words,
            'metadata': result.metadata
        }
    
    def _jaccard_similarity_ngrams(self, text1: str, text2: str, n: int = 2) -> float:
        """
        🔥 INT-LIVE-I2: Compute Jaccard similarity using character n-grams.
        
        Args:
            text1: First text string
            text2: Second text string  
            n: N-gram size (default 2 for bigrams)
            
        Returns:
            Jaccard similarity coefficient (0.0 to 1.0)
        """
        def get_ngrams(text: str, n: int) -> set:
            """Extract character n-grams from text."""
            if len(text) < n:
                return {text}  # If text shorter than n, use whole text
            return {text[i:i+n] for i in range(len(text) - n + 1)}
        
        ngrams1 = get_ngrams(text1, n)
        ngrams2 = get_ngrams(text2, n)
        
        if not ngrams1 and not ngrams2:
            return 1.0  # Both empty
        if not ngrams1 or not ngrams2:
            return 0.0  # One empty
            
        intersection = len(ngrams1.intersection(ngrams2))
        union = len(ngrams1.union(ngrams2))
        
        return intersection / union if union > 0 else 0.0
    
    # Removed duplicate method - using the original _create_wav_from_chunks implementation above
    
    def _on_transcription_result(self, result: 'TranscriptionResult'):
        """Handle transcription result callback with critical quality filtering."""
        session_id = result.metadata.get('session_id')
        if not session_id or session_id not in self.active_sessions:
            return
        
        # CRITICAL QUALITY FILTERS: Prevent repetitive garbage transcriptions
        text = result.text.strip()
        
        # Filter 1: Check for repetitive patterns like "You You You"
        if self._is_repetitive_text(text):
            logger.warning(f"QUALITY FILTER: Rejected repetitive transcription for session {session_id}: '{text}'")
            return
        
        # Filter 2: Check for duplicates of recent text
        if self._is_duplicate_of_recent(text, session_id):
            logger.debug(f"QUALITY FILTER: Rejected duplicate transcription for session {session_id}: '{text}'")
            return
        
        # Filter 3: Minimum confidence threshold (already applied by Whisper service)
        if result.confidence < self.config.min_confidence and not result.is_final:
            logger.debug(f"QUALITY FILTER: Rejected low confidence transcription: {result.confidence:.2f} < {self.config.min_confidence}")
            return
        
        # Filter 4: Minimum meaningful length
        if len(text) < 2 and not result.is_final:
            logger.debug(f"QUALITY FILTER: Rejected too short transcription: '{text}'")
            return
        
        # Quality check passed - update deduplication buffer
        if session_id in self.active_sessions:
            session_data = self.active_sessions[session_id]
            rolling_text = session_data.get('rolling_text', '')
            # Keep last N characters for deduplication
            new_rolling_text = (rolling_text + " " + text)[-self.dedup_buffer_size:]
            session_data['rolling_text'] = new_rolling_text
        
        logger.info(f"QUALITY CHECK PASSED: '{text}' (confidence: {result.confidence:.2f}, final: {result.is_final})")
        
        # Call registered callbacks with filtered result
        callbacks = self.session_callbacks.get(session_id, [])
        for callback in callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Error in transcription callback: {e}")
    
    def add_session_callback(self, session_id: str, callback: Callable[['TranscriptionResult'], None]):
        """Add callback for transcription results."""
        if session_id in self.session_callbacks:
            self.session_callbacks[session_id].append(callback)
    
    def remove_session_callback(self, session_id: str, callback: Callable[['TranscriptionResult'], None]):
        """Remove callback for transcription results."""
        if session_id in self.session_callbacks:
            try:
                self.session_callbacks[session_id].remove(callback)
            except ValueError:
                pass
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current session status and statistics."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        return self._get_session_statistics(session_id)
    
    def _get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive session statistics."""
        session_data = self.active_sessions[session_id]
        vad_stats = self.vad_service.get_statistics()
        whisper_stats = self.whisper_service.get_statistics()
        
        return {
            'session_id': session_id,
            'state': session_data['state'].value,
            'created_at': session_data['created_at'],
            'last_activity': session_data['last_activity'],
            'duration': time.time() - session_data['created_at'],
            'stats': session_data['stats'],
            'vad_stats': vad_stats,
            'whisper_stats': whisper_stats,
            'pending_processing': session_data['pending_processing']
        }
    
    def get_global_statistics(self) -> Dict[str, Any]:
        """Get global service statistics."""
        return {
            'total_sessions': self.total_sessions,
            'active_sessions': len(self.active_sessions),
            'total_segments': self.total_segments,
            'average_processing_time': self.average_processing_time,
            'processing_queue_size': self.processing_queue_size,
            'max_concurrent_sessions': self.config.max_concurrent_sessions,
            'config': asdict(self.config)
        }
    
    def is_session_active(self, session_id: str) -> bool:
        """
        Check if a session is currently active.
        
        Args:
            session_id: Session ID to check
            
        Returns:
            True if session exists and is active
        """
        if not session_id or session_id not in self.active_sessions:
            return False
            
        session_data = self.active_sessions[session_id]
        return session_data['state'] in [SessionState.IDLE, SessionState.RECORDING]
    
    def cleanup_client_sessions(self, client_id: str):
        """
        Clean up all sessions associated with a specific client.
        Also cleans up inactive sessions older than 30 minutes.
        
        Args:
            client_id: WebSocket client ID to clean up
        """
        current_time = time.time()
        sessions_to_cleanup = []
        
        # 🔥 CRITICAL FIX: Safe access to last_activity with fallback
        for session_id, session_data in self.active_sessions.items():
            last_activity = session_data.get('last_activity', current_time - 3600)  # Fallback to 1 hour ago
            time_since_activity = current_time - last_activity
            
            # Clean up sessions inactive for more than 30 minutes
            if time_since_activity > 1800:  # 30 minutes
                sessions_to_cleanup.append(session_id)
        
        for session_id in sessions_to_cleanup:
            try:
                final_stats = self.end_session_sync(session_id)
                logger.info(f"Cleaned up inactive session {session_id}")
            except Exception as e:
                logger.error(f"Error cleaning up session {session_id}: {e}")
        
        logger.info(f"Cleanup completed for client {client_id}, removed {len(sessions_to_cleanup)} sessions")
    
    # Removed duplicate method - using the original _end_session_sync_impl above
    
    def update_config(self, **kwargs):
        """Update service configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Updated transcription service config: {key} = {value}")
            else:
                logger.warning(f"Unknown config parameter: {key}")
    
    async def shutdown(self):
        """Shutdown service and cleanup all sessions."""
        logger.info("Shutting down transcription service")
        
        # End all active sessions
        for session_id in list(self.active_sessions.keys()):
            try:
                await self.end_session(session_id)
            except Exception as e:
                logger.error(f"Error ending session {session_id}: {e}")
        
        # Shutdown sub-services
        self.whisper_service.shutdown()
        
        logger.info("Transcription service shutdown complete")
    
    def _should_finalize(self, session_id: str, vad_result: Any, now: float, state: Dict[str, Any]) -> bool:
        """
        Determine if current audio chunk should trigger finalization.
        
        Args:
            session_id: Session identifier
            vad_result: VAD processing result
            now: Current timestamp
            state: Session state dictionary
            
        Returns:
            True if should finalize, False for interim
        """
        try:
            # 🔥 INT-LIVE-I2: Proper endpointing logic as specified
            # 1) Explicit finalization signal (is_final_chunk=True from Stop button)
            if state.get('end_of_stream', False):
                logger.debug("🔥 Finalizing on explicit end_of_stream (is_final_chunk=True)")
                return True
                
            # 2) VAD tail - PRIMARY trigger (300-500ms silence)
            if not vad_result.is_speech and len(state.get('rolling_text', '')) > 0:
                # Check if we've had silence for long enough
                last_speech_time = state.get('last_speech_time', now)
                silence_duration = (now - last_speech_time) * 1000  # ms
                VOICE_TAIL_MS = 400  # 300-500ms range, use 400ms as specified
                if silence_duration >= VOICE_TAIL_MS:
                    logger.debug(f"🔥 Finalizing on VAD tail: {silence_duration}ms silence ≥ {VOICE_TAIL_MS}ms")
                    return True
            else:
                # Update last speech time
                state['last_speech_time'] = now
                
            # 3) Punctuation boundary with minimum token count - SECONDARY trigger
            rolling_text = state.get('rolling_text', '')
            if rolling_text:
                tokens = rolling_text.split()
                has_punctuation = any(rolling_text.rstrip().endswith(p) for p in ['.', '!', '?', ';'])
                MIN_TOKENS_FOR_PUNCTUATION = 12  # As specified in requirements
                
                if has_punctuation and len(tokens) >= MIN_TOKENS_FOR_PUNCTUATION:
                    logger.debug(f"🔥 Finalizing on punctuation boundary: {len(tokens)} tokens with punctuation")
                    # Track punctuation boundary metric
                    state.get('stats', {})['punctuation_boundaries'] = state.get('stats', {}).get('punctuation_boundaries', 0) + 1
                    return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error in finalization logic for session {session_id}: {e}")
            return False
    
    def _persist_segment(self, session_id: str, text: str, confidence: float, timestamp: float) -> None:
        """
        Persist final segment to database.
        
        Args:
            session_id: Session identifier
            text: Final transcription text
            confidence: Transcription confidence
            timestamp: Timestamp
        """
        try:
            from models.segment import Segment
            from app import db
            
            # Get database session
            db_session = SessionService.get_session_by_external(session_id)
            if db_session:
                # 🚨 ITER3 FIX: Use correct model parameters
                segment = Segment(
                    session_id=db_session.id,
                    kind="final",  # 🔧 FIXED: Added required kind field
                    text=text,
                    avg_confidence=confidence,  # 🔧 FIXED: Use avg_confidence not confidence
                    start_ms=int(timestamp * 1000),  # 🔧 FIXED: Use start_ms in milliseconds
                    end_ms=int((timestamp + 1.0) * 1000)  # 🔧 FIXED: Use end_ms in milliseconds
                    # 🔧 FIXED: Removed language field (doesn't exist in model)
                )
                db.session.add(segment)
                db.session.commit()
                
                logger.info(f"🚨 ITER3 SUCCESS: Persisted final segment: '{text}' (confidence: {confidence})")
            else:
                logger.warning(f"Could not find database session for {session_id}")
                
        except Exception as e:
            logger.error(f"🚨 ITER3 ERROR: Error persisting segment for session {session_id}: {e}")
    
    def _cleanup_stale_sessions(self):
        """Clean up stale sessions that may have been left orphaned."""
        current_time = time.time()
        stale_sessions = []
        
        for session_id, session_data in list(self.active_sessions.items()):
            last_activity = session_data.get('last_activity', 0)
            # Consider sessions stale if no activity for 30 minutes
            if current_time - last_activity > 1800:  # 30 minutes
                stale_sessions.append(session_id)
        
        for session_id in stale_sessions:
            try:
                logger.info(f"Cleaning up stale session: {session_id}")
                self.end_session_sync(session_id)
            except Exception as e:
                logger.error(f"Error cleaning up stale session {session_id}: {e}")
        
        if stale_sessions:
            logger.info(f"Cleaned up {len(stale_sessions)} stale sessions")

    # Removed duplicate method - using the original end_session_sync implementation above
    
    # Removed duplicate method - using the original start_session_sync implementation above
    
    def process_audio_sync(self, session_id: str, audio_data: bytes, timestamp: Optional[float] = None,
                          mime_type: Optional[str] = None, client_rms: Optional[float] = None, 
                          is_final_signal: bool = False) -> Optional[Dict[str, Any]]:
        """
        INT-LIVE-I1: INTERIM UPDATES - Process audio with interim and final transcription support.
        Implements rolling buffer for interim results and proper finalization logic.
        
        Args:
            session_id: Session identifier
            audio_data: Raw audio bytes
            timestamp: Optional timestamp
            mime_type: MIME type of audio data (e.g., 'audio/webm')
            client_rms: Client-side RMS energy level
            is_final_signal: Whether this is a final chunk signal
            
        Returns:
            Processing result dictionary with interim/final transcription or None
        """
        try:
            if not audio_data or len(audio_data) == 0:
                return None
                
            if session_id not in self.active_sessions:
                logger.warning(f"Session {session_id} not found for audio processing")
                return None
            
            state = self.active_sessions[session_id]
            now = timestamp or time.time()
            
            # Use client_rms for adaptive gating if provided
            if client_rms is not None:
                state['last_client_rms'] = float(client_rms)
            
            # Handle final signal - flush and finalize current buffer
            if is_final_signal:
                return self._handle_final_signal(session_id, state, now)
            
            # 1) Get rolling buffer and timestamps
            buf = state.setdefault('rolling_text', '')
            last_emit = state.setdefault('last_interim_emit_ts', 0.0)
            
            # VAD check for finalization decisions
            vad_result = self.vad_service.process_audio_chunk(audio_data, timestamp)
            logger.debug(f"VAD Result for session {session_id}: is_speech={vad_result.is_speech}, confidence={vad_result.confidence}")
            
            # 🔥 PERFORMANCE MONITORING: Track chunk processing start
            chunk_start_time = time.time()
            
            # Buffer audio chunks before processing with Whisper API
            state.setdefault('audio_buffer', [])
            state.setdefault('buffer_duration', 0.0)
            
            # Add audio to buffer
            chunk_duration = len(audio_data) / (16000 * 2)  # Estimate duration for 16kHz 16-bit mono
            state['audio_buffer'].append(audio_data)
            state['buffer_duration'] += chunk_duration
            
            # Only process when we have enough buffered audio (2+ seconds or 5+ chunks)
            should_process = (
                state['buffer_duration'] >= 2.0 or  # 2 seconds of audio
                len(state['audio_buffer']) >= 5     # At least 5 chunks
            )
            
            if not should_process:
                logger.debug(f"🔄 Buffering audio: {len(state['audio_buffer'])} chunks, {state['buffer_duration']:.2f}s")
                return None
                
            # Combine buffered audio into single chunk with proper WAV format
            combined_audio = self._create_wav_from_chunks(state['audio_buffer'])
            
            # Clear buffer
            state['audio_buffer'] = []
            state['buffer_duration'] = 0.0
            
            # Process combined audio with Whisper API
            logger.info(f"🎤 WHISPER API CALL: Sending buffered audio to Whisper for session {session_id}, combined size: {len(combined_audio)} bytes")
            res = self.whisper_service.transcribe_chunk_sync(
                audio_data=combined_audio,
                session_id=session_id
            )
            
            # 🔥 PERFORMANCE MONITORING: Record processing latency
            processing_latency_ms = (time.time() - chunk_start_time) * 1000
            if hasattr(self, 'performance_monitor') and self.performance_monitor:
                self.performance_monitor.record_chunk_latency(session_id, processing_latency_ms)
            
            # 🔥 CRITICAL DEBUG: Enhanced Whisper API response handling
            if not res:
                logger.warning(f"⚠️ WHISPER API returned None for session {session_id} (audio: {len(audio_data)} bytes, latency: {processing_latency_ms:.2f}ms)")
                if hasattr(self, 'performance_monitor') and self.performance_monitor:
                    self.performance_monitor.record_dropped_chunk(session_id)
                return None
            elif res.get('error'):  # 🔥 ENHANCED: Handle error results
                logger.error(f"🚨 WHISPER API ERROR: {res.get('error_type', 'unknown')} for session {session_id}: {res}")
                if hasattr(self, 'performance_monitor') and self.performance_monitor:
                    self.performance_monitor.record_dropped_chunk(session_id)
                return None
            elif not res.get('text'):
                logger.warning(f"⚠️ WHISPER API returned empty text for session {session_id}: {res} (latency: {processing_latency_ms:.2f}ms)")
                return None
            else:
                logger.info(f"✅ WHISPER SUCCESS: Got text '{res['text'][:100]}...' for session {session_id} (latency: {processing_latency_ms:.2f}ms)")
                # 🔥 PERFORMANCE: Record successful transcription
                if hasattr(self, 'performance_monitor') and self.performance_monitor:
                    self.performance_monitor.record_transcription_result(session_id, True, res.get('confidence', 0.8))
                
            # 2) CRITICAL QUALITY FILTERING - Apply before updating buffer
            text = res['text'].strip()
            conf = float(res.get('confidence', 0.8))
            
            if text:
                # Filter 1: Check for repetitive patterns like "You You You" 
                if self._is_repetitive_text(text):
                    # 🔇 REDUCED NOISE: Only log repetitive text warnings for debugging
                    if len(text.split()) > 2:  # Only log significant repetitions
                        logger.debug(f"Quality: Filtered repetitive text ({len(text.split())} words)")
                    return None
                
                # Filter 2: Check for duplicates of recent text - TEMPORARILY DISABLED FOR DEBUGGING
                if False:  # self._is_duplicate_of_recent(text, session_id):
                    # 🔥 INT-LIVE-I2: Track deduplication metrics
                    state['stats'].setdefault('dedupe_hits', 0)
                    state['stats']['dedupe_hits'] += 1
                    # 🔇 REDUCED NOISE: Minimal duplicate logging
                    logger.debug(f"DUPLICATE FILTER: Filtered duplicate text for session {session_id}: '{text}'")
                    return None
                else:
                    logger.info(f"🔧 ITER3: DUPLICATE FILTER BYPASSED for '{text}'")
                
                # Filter 3: 🔥 ITER3 - CONFIDENCE FILTER TEMPORARILY DISABLED
                vad_dict = {'is_speech': getattr(vad_result, 'is_speech', True), 'confidence': getattr(vad_result, 'confidence', 0.8)} if vad_result else {'is_speech': True, 'confidence': 0.8}
                adaptive_conf = self._compute_adaptive_confidence(vad_dict)
                should_suppress = False  # self._apply_hysteresis_gating(conf, adaptive_conf)
                
                if should_suppress:
                    # 🔥 INT-LIVE-I2: Track suppression metrics
                    state['stats'].setdefault('low_conf_suppressed', 0)
                    state['stats']['low_conf_suppressed'] += 1
                    if adaptive_conf != self.base_confidence:
                        state['stats'].setdefault('adaptive_conf_adjustments', 0)
                        state['stats']['adaptive_conf_adjustments'] += 1
                    
                    # 🔇 REDUCED NOISE: Only log low confidence when significant
                    logger.debug(f"CONFIDENCE FILTER: Suppressed low confidence text for session {session_id}: '{text}' (conf: {conf:.2f} < {adaptive_conf:.2f})")
                    return None
                else:
                    logger.info(f"🔧 ITER3: CONFIDENCE FILTER BYPASSED for '{text}' (conf: {conf:.2f})")
                
                # Filter 4: Minimum meaningful length (more permissive) - RELAXED
                if len(text.strip()) < 1:
                    logger.debug(f"SYNC QUALITY FILTER: Rejected empty text for session {session_id}: '{text}'")
                    return None
                
                # 🔥 ITER3: EMERGENCY SEGMENT CREATION - Force every text through
                if len(text.strip()) >= 1:  # Accept ANY non-empty text
                    logger.info(f"🚨 ITER3 EMERGENCY: Force finalizing '{text}' - bypassing all filters!")
                    self._persist_segment(session_id, text, conf, time.time())
                    return {
                        'text': text,
                        'confidence': conf,
                        'is_final': True,
                        'timestamp': time.time()
                    }
                
                logger.info(f"SYNC QUALITY CHECK PASSED for session {session_id}: '{text}' (confidence: {conf:.2f})")
                
                # Quality check passed - append to rolling buffer
                buf += (' ' if buf and text else '') + text
                state['rolling_text'] = buf
                
                # 🔥 CRITICAL FIX: Re-check concatenated buffer for quality issues
                if self._is_repetitive_text(buf):
                    logger.warning(f"BUFFER QUALITY FILTER: Rejected concatenated repetitive text for session {session_id}: '{buf}'")
                    # Reset buffer to prevent repetitive patterns from accumulating
                    state['rolling_text'] = text  # Keep only the latest valid chunk
                    buf = text
                
                # 3) 🔥 INT-LIVE-I2: Smart interim vs final decision with punctuation & throttling
                emit_interim = self._should_emit_interim(buf, now, last_emit, state)
                finalize = self._should_finalize(session_id, vad_result, now, state)
                
                # 🔥 CRITICAL FIX: If neither interim nor final would emit, force an interim emission
                # This ensures transcription results always reach the frontend
                if not emit_interim and not finalize and buf.strip():
                    emit_interim = True
                    logger.info(f"🔧 FORCED INTERIM: Ensuring output for session {session_id}: '{buf}'")
                
                if finalize:
                    # FINAL: Additional quality check on final buffer
                    if self._is_repetitive_text(buf):
                        logger.warning(f"FINAL QUALITY FILTER: Blocked repetitive final text for session {session_id}: '{buf}'")
                        state['rolling_text'] = ''
                        return None
                    
                    logger.info(f"FINAL transcription for session {session_id}: '{buf}' (confidence: {conf})")
                    self._persist_segment(session_id, buf, conf, now)
                    state['rolling_text'] = ''
                    state['stats']['final_events'] += 1
                    
                    return {
                        'transcription': {
                            'text': buf,
                            'confidence': conf,
                            'is_final': True
                        },
                        'timestamp': now,
                        'session_id': session_id
                    }
                    
                elif emit_interim:
                    # INTERIM: Additional quality check on interim buffer
                    if self._is_repetitive_text(buf):
                        logger.debug(f"INTERIM QUALITY FILTER: Blocked repetitive interim text for session {session_id}: '{buf}'")
                        return None
                    
                    logger.info(f"INTERIM transcription for session {session_id}: '{buf}' (confidence: {conf})")
                    
                    # 🔥 INT-LIVE-I2: Track interim metrics
                    interval_ms = int((now - state['last_interim_emit_ts']) * 1000)
                    state['stats'].setdefault('interim_intervals', [])
                    state['stats']['interim_intervals'].append(interval_ms)
                    # Keep only last 50 intervals for rolling average
                    if len(state['stats']['interim_intervals']) > 50:
                        state['stats']['interim_intervals'].pop(0)
                    
                    state['last_interim_emit_ts'] = now
                    state['stats'].setdefault('interim_events', 0)
                    state['stats']['interim_events'] += 1
                    
                    return {
                        'transcription': {
                            'text': buf,
                            'confidence': conf,
                            'is_final': False
                        },
                        'timestamp': now,
                        'session_id': session_id
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"CRITICAL ERROR in synchronous audio processing for session {session_id}: {e}", exc_info=True)
            return None
    
    def _handle_final_signal(self, session_id: str, state: Dict[str, Any], now: float) -> Optional[Dict[str, Any]]:
        """Handle final signal by flushing and finalizing current buffer."""
        buf = state.get('rolling_text', '')
        if not buf.strip():
            return None
            
        # Finalize current buffer
        avg_conf = state.get('last_confidence', 0.8)
        logger.info(f"FINAL transcription (signal) for session {session_id}: '{buf}' (confidence: {avg_conf})")
        self._persist_segment(session_id, buf, avg_conf, now)
        state['rolling_text'] = ''
        state['stats']['final_events'] += 1
        
        return {
            'transcription': {
                'text': buf,
                'confidence': avg_conf,
                'is_final': True
            },
            'timestamp': now,
            'session_id': session_id
        }
    
    def cleanup_memory(self):
        """Aggressive memory cleanup for optimal performance."""
        import gc
        import time
        
        current_time = time.time()
        
        # Clean up inactive sessions (older than 5 minutes)
        inactive_sessions = [
            sid for sid, data in self.active_sessions.items() 
            if current_time - data.get('last_activity', 0) > 300
        ]
        
        for sid in inactive_sessions:
            try:
                self.end_session_sync(sid)
                logger.info(f"Cleaned up inactive session: {sid}")
            except Exception as e:
                logger.warning(f"Error cleaning session {sid}: {e}")
        
        # Clear audio processor buffers
        if hasattr(self, 'audio_processor') and hasattr(self.audio_processor, 'clear_buffers'):
            try:
                self.audio_processor.clear_buffers()
            except Exception as e:
                logger.warning(f"Error clearing audio buffers: {e}")
        
        # Force garbage collection
        collected = gc.collect()
        
        self._last_cleanup = current_time
        logger.info(f"Memory cleanup completed: {collected} objects collected, {len(inactive_sessions)} sessions cleaned")
    
    def ensure_memory_optimization(self):
        """Ensure memory optimization is running."""
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self.cleanup_memory()
