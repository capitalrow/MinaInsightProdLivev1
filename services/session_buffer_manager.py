# services/session_buffer_manager.py
"""
Advanced Session Buffer Manager for Real-time Audio Processing

Provides comprehensive buffering, VAD-driven processing, multi-format support,
memory management, and production-grade reliability for audio transcription.
"""
import time
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any, List
import numpy as np
import base64
from queue import Queue, Full, Empty
try:
    import webrtcvad
    WEBRTC_VAD_AVAILABLE = True
except ImportError:
    WEBRTC_VAD_AVAILABLE = False
    webrtcvad = None
    
import struct

logger = logging.getLogger(__name__)

@dataclass
class BufferConfig:
    """Configuration for session buffering - Phase 3 optimized for <2s latency"""
    max_buffer_ms: int = 30000  # 30 seconds max buffer
    max_bytes: int = 5 * 1024 * 1024  # 5MB per session
    min_flush_ms: int = 1500  # Minimum 1.5s between flushes (Phase 3: reduced from 1s)
    max_flush_ms: int = 2500  # Maximum 2.5s before forced flush (Phase 3: reduced from 8s)
    overlap_ms: int = 300  # 300ms overlap for context (Phase 3: reduced from 500ms)
    idle_timeout_ms: int = 15000  # 15s idle timeout
    vad_mode: int = 2  # WebRTC VAD aggressiveness (0-3)
    target_sample_rate: int = 16000  # Normalize to 16kHz
    enable_vad: bool = True
    enable_quality_gating: bool = True
    min_energy_threshold: float = 0.01

@dataclass
class AudioChunk:
    """Structured audio chunk with metadata"""
    data: bytes
    timestamp: float
    mime_type: str
    size: int
    sequence_id: int
    has_speech: Optional[bool] = None
    energy_level: Optional[float] = None

@dataclass
class SessionMetrics:
    """Per-session performance metrics"""
    chunks_received: int = 0
    chunks_processed: int = 0
    chunks_dropped: int = 0
    bytes_ingested: int = 0
    bytes_processed: int = 0
    last_flush_time: float = 0
    avg_flush_interval: float = 0
    speech_ratio: float = 0
    decode_failures: int = 0
    api_failures: int = 0
    backpressure_events: int = 0

class ContainerReconstructor:
    """Advanced container reconstruction for multi-format support"""
    
    def __init__(self):
        self.webm_header: Optional[bytes] = None
        self.ogg_header: Optional[bytes] = None
        self.codec_params: Dict[str, Any] = {}
        
    def detect_format(self, chunk: bytes) -> str:
        """Enhanced format detection with deep inspection"""
        if len(chunk) < 12:
            return 'unknown'
            
        # WebM/Matroska detection
        if chunk[:4] == b'\x1a\x45\xdf\xa3':
            return 'webm'
        # OGG detection
        elif chunk[:4] == b'OggS':
            return 'ogg'  
        # WAV detection
        elif chunk[:4] == b'RIFF' and chunk[8:12] == b'WAVE':
            return 'wav'
        # MP4/M4A detection
        elif chunk[4:8] == b'ftyp' or chunk[:8] == b'ftypmp4\x00':
            return 'mp4'
        # Check for WebM patterns in data
        elif b'webm' in chunk[:100].lower() or b'opus' in chunk[:100].lower():
            return 'webm'
        else:
            return 'unknown'
    
    def capture_header(self, chunk: bytes, format_type: str) -> bool:
        """Capture container headers for reconstruction"""
        try:
            if format_type == 'webm' and not self.webm_header:
                # Capture EBML header + Segment start
                self.webm_header = chunk
                logger.info(f"📦 Captured WebM header: {len(chunk)} bytes")
                return True
            elif format_type == 'ogg' and not self.ogg_header:
                # Capture OGG page header
                self.ogg_header = chunk[:282]  # Standard OGG page size
                logger.info(f"📦 Captured OGG header: {len(self.ogg_header)} bytes")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Header capture failed: {e}")
            return False
    
    def reconstruct_container(self, chunks: List[bytes], format_type: str) -> bytes:
        """Reconstruct proper container from fragments"""
        if not chunks:
            return b''
            
        try:
            if format_type == 'webm' and self.webm_header:
                # Ensure header is present at start
                combined = self.webm_header
                for chunk in chunks:
                    if chunk != self.webm_header:  # Avoid duplicating header
                        combined += chunk
                logger.info(f"🔧 Reconstructed WebM: {len(combined)} bytes")
                return combined
                
            elif format_type == 'ogg' and self.ogg_header:
                # Basic OGG page reconstruction
                combined = self.ogg_header
                for chunk in chunks[1:]:  # Skip first chunk (already header)
                    combined += chunk
                logger.info(f"🔧 Reconstructed OGG: {len(combined)} bytes")
                return combined
                
            else:
                # Fallback: concatenate chunks
                return b''.join(chunks)
                
        except Exception as e:
            logger.error(f"❌ Container reconstruction failed: {e}")
            return b''.join(chunks)  # Fallback to simple concatenation

class VADProcessor:
    """Voice Activity Detection processor"""
    
    def __init__(self, config: BufferConfig):
        self.config = config
        self.vad = None
        self.speech_frames = deque(maxlen=50)  # Last 50 frame decisions
        
        if config.enable_vad and WEBRTC_VAD_AVAILABLE and webrtcvad is not None:
            try:
                self.vad = webrtcvad.Vad(config.vad_mode)
            except Exception as e:
                logger.warning(f"⚠️ WebRTC VAD initialization failed: {e}")
        elif config.enable_vad and not WEBRTC_VAD_AVAILABLE:
            logger.warning("⚠️ WebRTC VAD not available, using energy-based detection")
    
    def analyze_chunk(self, audio_data: bytes, sample_rate: int = 16000) -> Tuple[bool, float]:
        """Analyze chunk for speech content and energy"""
        try:
            # Calculate energy level
            if len(audio_data) >= 2:
                # Assume 16-bit samples
                samples = np.frombuffer(audio_data, dtype=np.int16)
                energy = np.sqrt(np.mean(samples.astype(float) ** 2)) / 32767.0
            else:
                energy = 0.0
            
            # Voice activity detection with fallback
            has_speech = False
            if self.vad and len(audio_data) >= 320:  # WebRTC VAD needs >= 10ms at 16kHz
                try:
                    # Ensure proper frame size (10ms, 20ms, or 30ms at 16kHz)
                    frame_size = 320  # 20ms at 16kHz
                    if len(audio_data) >= frame_size:
                        frame = audio_data[:frame_size]
                        has_speech = self.vad.is_speech(frame, sample_rate)
                        self.speech_frames.append(has_speech)
                except Exception as e:
                    logger.debug(f"VAD analysis failed: {e}")
                    # Fallback to energy-based detection
                    has_speech = energy > self.config.min_energy_threshold
            else:
                # Energy-based detection (fallback or when VAD disabled)
                has_speech = energy > self.config.min_energy_threshold
                        
            return has_speech, energy
            
        except Exception as e:
            logger.error(f"❌ Chunk analysis failed: {e}")
            return False, 0.0
    
    def get_speech_ratio(self) -> float:
        """Get recent speech ratio"""
        if not self.speech_frames:
            return 0.0
        return sum(self.speech_frames) / len(self.speech_frames)

class SessionBufferManager:
    """Advanced session buffer manager with VAD and quality gating"""
    
    def __init__(self, session_id: str, config: Optional[BufferConfig] = None):
        self.session_id = session_id
        self.config = config or BufferConfig()
        self.chunks: deque = deque(maxlen=100)  # Reduced from 1000 to prevent memory bloat
        self.raw_buffer = bytearray()
        self.last_activity = time.time()
        self.last_flush = 0.0
        self.sequence_id = 0
        self.metrics = SessionMetrics()
        
        # Advanced components
        self.reconstructor = ContainerReconstructor()
        self.vad_processor = VADProcessor(self.config)
        self.processing_queue: Queue = Queue(maxsize=10)  # Bounded processing queue
        self.lock = threading.RLock()
        
        # State management
        self.is_active = True
        self.format_detected: Optional[str] = None
        
    def ingest_chunk(self, chunk_data: bytes, mime_type: str) -> bool:
        """Ingest new audio chunk with comprehensive processing"""
        with self.lock:
            try:
                if not self.is_active:
                    return False
                
                current_time = time.time()
                self.last_activity = current_time
                
                # Create structured chunk
                chunk = AudioChunk(
                    data=chunk_data,
                    timestamp=current_time,
                    mime_type=mime_type,
                    size=len(chunk_data),
                    sequence_id=self.sequence_id
                )
                self.sequence_id += 1
                
                # Format detection and header capture
                if not self.format_detected:
                    detected_format = self.reconstructor.detect_format(chunk_data)
                    if detected_format != 'unknown':
                        self.format_detected = detected_format
                        self.reconstructor.capture_header(chunk_data, detected_format)
                        logger.info(f"🎯 Session {self.session_id}: Format detected as {detected_format}")
                
                # Memory management - enforce limits
                if self.metrics.bytes_ingested > self.config.max_bytes:
                    self.metrics.backpressure_events += 1
                    logger.warning(f"⚠️ Session {self.session_id}: Memory limit reached, dropping chunk")
                    self.metrics.chunks_dropped += 1
                    return False
                
                # Quality analysis
                has_speech, energy = self.vad_processor.analyze_chunk(chunk_data)
                chunk.has_speech = has_speech
                chunk.energy_level = energy
                
                # Quality gating
                if self.config.enable_quality_gating:
                    if energy < self.config.min_energy_threshold and len(self.chunks) > 5:
                        logger.debug(f"🔇 Session {self.session_id}: Low energy chunk dropped ({energy:.4f})")
                        self.metrics.chunks_dropped += 1
                        return False
                
                # Buffer management
                self.chunks.append(chunk)
                self.raw_buffer.extend(chunk_data)
                
                # Update metrics
                self.metrics.chunks_received += 1
                self.metrics.bytes_ingested += len(chunk_data)
                
                # Add to processing queue for background processing
                try:
                    self.processing_queue.put_nowait(chunk)
                except Full:
                    logger.warning(f"⚠️ Session {self.session_id}: Processing queue full")
                    self.metrics.backpressure_events += 1
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Session {self.session_id} chunk ingestion failed: {e}")
                return False
    
    def should_flush(self) -> bool:
        """Determine if buffer should be flushed using adaptive logic"""
        with self.lock:
            if not self.chunks:
                return False
            
            current_time = time.time()
            time_since_last_flush = (current_time - self.last_flush) * 1000
            
            # Forced flush conditions
            if time_since_last_flush > self.config.max_flush_ms:
                logger.debug(f"🕒 Session {self.session_id}: Forced flush (timeout)")
                return True
            
            if len(self.raw_buffer) > self.config.max_bytes // 2:
                logger.debug(f"📦 Session {self.session_id}: Forced flush (size limit)")
                return True
            
            # Minimum flush interval
            if time_since_last_flush < self.config.min_flush_ms:
                return False
            
            # VAD-driven adaptive flushing
            speech_ratio = self.vad_processor.get_speech_ratio()
            
            # End of speech detection
            if speech_ratio > 0.3:  # Had recent speech
                recent_chunks = list(self.chunks)[-5:]  # Last 5 chunks
                if recent_chunks and all(not chunk.has_speech for chunk in recent_chunks[-3:]):
                    logger.debug(f"🎤 Session {self.session_id}: End of speech detected")
                    return True
            
            # Silence-driven flush
            if speech_ratio < 0.1 and time_since_last_flush > self.config.min_flush_ms * 2:
                logger.debug(f"🔇 Session {self.session_id}: Silence-driven flush")
                return True
            
            return False
    
    def assemble_flush_payload(self) -> Tuple[bytes, str, Dict]:
        """Assemble optimized payload for transcription"""
        with self.lock:
            if not self.chunks:
                return b'', 'unknown', {}
            
            try:
                # Get chunks for processing
                flush_chunks = list(self.chunks)
                chunk_data = [chunk.data for chunk in flush_chunks]
                
                # Reconstruct container
                if self.format_detected:
                    payload_bytes = self.reconstructor.reconstruct_container(
                        chunk_data, self.format_detected
                    )
                else:
                    payload_bytes = b''.join(chunk_data)
                
                # Metadata for API
                metadata = {
                    'chunk_count': len(flush_chunks),
                    'total_bytes': len(payload_bytes),
                    'speech_ratio': self.vad_processor.get_speech_ratio(),
                    'avg_energy': sum(c.energy_level or 0 for c in flush_chunks) / len(flush_chunks),
                    'sequence_range': f"{flush_chunks[0].sequence_id}-{flush_chunks[-1].sequence_id}",
                    'format': self.format_detected or 'unknown'
                }
                
                # Update metrics
                self.metrics.chunks_processed += len(flush_chunks)
                self.metrics.bytes_processed += len(payload_bytes)
                self.last_flush = time.time()
                
                return payload_bytes, self.format_detected or 'webm', metadata
                
            except Exception as e:
                logger.error(f"❌ Session {self.session_id} payload assembly failed: {e}")
                return b'', 'unknown', {}
    
    def reset_with_overlap(self):
        """Reset buffer while preserving overlap for context"""
        with self.lock:
            try:
                if not self.chunks:
                    return
                
                # Calculate overlap
                overlap_chunks = []
                overlap_bytes = 0
                target_overlap_bytes = (self.config.overlap_ms * 16000 * 2) // 1000  # 16kHz 16-bit
                
                # Keep recent chunks for overlap
                for chunk in reversed(list(self.chunks)):
                    if overlap_bytes < target_overlap_bytes:
                        overlap_chunks.insert(0, chunk)
                        overlap_bytes += chunk.size
                    else:
                        break
                
                # Reset buffers
                self.chunks.clear()
                self.raw_buffer.clear()
                
                # Re-add overlap chunks
                for chunk in overlap_chunks:
                    self.chunks.append(chunk)
                    self.raw_buffer.extend(chunk.data)
                
                logger.info(f"🔄 Session {self.session_id}: Buffer reset with {len(overlap_chunks)} overlap chunks")
                
            except Exception as e:
                logger.error(f"❌ Session {self.session_id} buffer reset failed: {e}")
    
    def get_metrics(self) -> Dict:
        """Get comprehensive session metrics"""
        with self.lock:
            current_time = time.time()
            idle_time = (current_time - self.last_activity) * 1000
            
            # Update computed metrics
            self.metrics.speech_ratio = self.vad_processor.get_speech_ratio()
            if self.metrics.chunks_processed > 0:
                self.metrics.avg_flush_interval = (
                    (current_time - self.last_flush) * 1000 / max(1, self.metrics.chunks_processed)
                )
            
            return {
                'session_id': self.session_id,
                'format_detected': self.format_detected,
                'active_chunks': len(self.chunks),
                'buffer_bytes': len(self.raw_buffer),
                'idle_time_ms': idle_time,
                'is_active': self.is_active,
                **self.metrics.__dict__
            }
    
    def should_timeout(self) -> bool:
        """Check if session should timeout due to inactivity"""
        current_time = time.time()
        idle_time_ms = (current_time - self.last_activity) * 1000
        return idle_time_ms > self.config.idle_timeout_ms
    
    def end_session(self):
        """Clean session termination"""
        with self.lock:
            self.is_active = False
            self.chunks.clear()
            self.raw_buffer.clear()
            logger.info(f"🔚 Session {self.session_id} ended")

class SessionBufferRegistry:
    """Global registry for managing all session buffers"""
    
    def __init__(self, default_config: Optional[BufferConfig] = None):
        self.sessions: Dict[str, SessionBufferManager] = {}
        self.default_config = default_config or BufferConfig()
        self.lock = threading.RLock()
        
        # Background cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
    
    def get_or_create_session(self, session_id: str) -> SessionBufferManager:
        """Get existing session buffer or create new one"""
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = SessionBufferManager(session_id, self.default_config)
                logger.info(f"📝 Created buffer manager for session {session_id}")
            return self.sessions[session_id]
    
    def remove_session(self, session_id: str):
        """Remove session buffer"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].end_session()
                del self.sessions[session_id]
                logger.info(f"🗑️ Removed buffer manager for session {session_id}")
    
    def release(self, session_id: str):
        """Release session buffer (alias for remove_session for compatibility)"""
        self.remove_session(session_id)
    
    def get_all_metrics(self) -> Dict:
        """Get metrics for all active sessions"""
        with self.lock:
            return {
                'total_sessions': len(self.sessions),
                'sessions': {sid: manager.get_metrics() for sid, manager in self.sessions.items()}
            }
    
    def _cleanup_worker(self):
        """Background worker to clean up timed-out sessions"""
        while True:
            try:
                time.sleep(30)  # Check every 30 seconds
                with self.lock:
                    timed_out = []
                    for session_id, manager in self.sessions.items():
                        if manager.should_timeout():
                            timed_out.append(session_id)
                    
                    for session_id in timed_out:
                        logger.info(f"⏰ Session {session_id} timed out")
                        self.remove_session(session_id)
                        
            except Exception as e:
                logger.error(f"❌ Cleanup worker error: {e}")

# Global registry instance
buffer_registry = SessionBufferRegistry()

def get_session_buffer_manager(session_id: str) -> SessionBufferManager:
    """Get session buffer manager instance for the given session ID"""
    return buffer_registry.get_or_create_session(session_id)

logger.info("✅ Session Buffer Manager module initialized")