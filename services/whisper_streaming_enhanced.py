"""
Enhanced Whisper Streaming Service with M1 Quality Improvements
Implements bounded queue, backpressure, deduplication, finalization, and metrics.
"""

import logging
import time
import json
import queue
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, asdict
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import difflib
import threading

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class M1TranscriptionConfig:
    """M1 Enhanced configuration for Whisper streaming transcription."""
    model: str = "whisper-1"
    language: str = "en"
    temperature: float = 0.0
    response_format: str = "json"
    prompt: Optional[str] = None
    max_chunk_ms: int = 640
    min_chunk_ms: int = 100
    max_queue_len: int = 8
    voice_tail_ms: int = 300
    min_confidence: float = 0.6
    dedup_overlap_threshold: float = 0.9
    enable_word_timestamps: bool = True
    metrics_sample_rate: float = 1.0

@dataclass
class M1TranscriptionResult:
    """M1 Enhanced transcription result with metrics."""
    text: str
    avg_confidence: float
    is_final: bool
    language: str
    duration: float
    timestamp: float
    words: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    # M1 additions
    latency_ms: float
    chunk_index: int

@dataclass
class M1SessionMetrics:
    """M1 Session metrics for quality monitoring."""
    session_id: str
    chunks_received: int
    chunks_processed: int
    chunks_dropped: int
    interim_events: int
    final_events: int
    latency_avg_ms: float
    latency_p95_ms: float
    retries: int
    ws_disconnects: int

class BoundedAudioQueue:
    """Bounded queue with drop-oldest policy for backpressure handling."""
    
    def __init__(self, max_size: int = 8):
        self.max_size = max_size
        self.queue = deque(maxlen=max_size)
        self.dropped_count = 0
        self._lock = threading.Lock()
    
    def enqueue(self, item: Dict[str, Any]) -> bool:
        """Enqueue item, returns True if successful, False if dropped."""
        with self._lock:
            if len(self.queue) >= self.max_size:
                # Drop oldest item
                dropped_item = self.queue.popleft()
                self.dropped_count += 1
                logger.debug(f"Dropped oldest chunk {dropped_item.get('chunk_index', 'unknown')} due to backpressure")
            
            self.queue.append(item)
            return True
    
    def dequeue(self) -> Optional[Dict[str, Any]]:
        """Dequeue item, returns None if empty."""
        with self._lock:
            if self.queue:
                return self.queue.popleft()
            return None
    
    def size(self) -> int:
        """Get current queue size."""
        return len(self.queue)
    
    def is_full(self) -> bool:
        """Check if queue is at capacity."""
        return len(self.queue) >= self.max_size

class M1WhisperStreamingService:
    """
    M1 Enhanced Whisper streaming service with quality improvements.
    Implements bounded queues, backpressure, deduplication, and comprehensive metrics.
    """
    
    def __init__(self, config: Optional[M1TranscriptionConfig] = None):
        self.config = config or M1TranscriptionConfig()
        self.client = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # M1 Bounded queue for backpressure
        self.processing_queue = BoundedAudioQueue(max_size=self.config.max_queue_len)
        
        # Session state
        self.active_sessions: Dict[str, Dict] = {}
        self.current_session_id = None
        self.chunk_index = 0
        
        # M1 Metrics tracking
        self.session_metrics: Dict[str, M1SessionMetrics] = {}
        self.latency_samples = deque(maxlen=100)
        
        # Deduplication buffer
        self.last_text_buffer = ""
        self.buffer_size_chars = 80
        
        # Initialize OpenAI client
        self._initialize_client()
        
        logger.info(f"M1 Whisper Service initialized with config: max_queue_len={self.config.max_queue_len}, max_chunk_ms={self.config.max_chunk_ms}")
    
    def _initialize_client(self):
        """Initialize OpenAI client if available."""
        import os
        if OPENAI_AVAILABLE and os.environ.get('OPENAI_API_KEY'):
            try:
                self.client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
                logger.info("OpenAI Whisper client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            if not OPENAI_AVAILABLE:
                logger.warning("OpenAI package not available, using mock transcription")
            else:
                logger.warning("OpenAI API key not found, using mock transcription")
            self.client = None
    
    def start_session(self, session_id: str) -> None:
        """Start a new transcription session with M1 tracking."""
        self.current_session_id = session_id
        self.chunk_index = 0
        
        # Initialize session state
        self.active_sessions[session_id] = {
            'start_time': time.time(),
            'pending_chunks': deque(),
            'last_finalization': None
        }
        
        # Initialize metrics
        self.session_metrics[session_id] = M1SessionMetrics(
            session_id=session_id,
            chunks_received=0,
            chunks_processed=0,
            chunks_dropped=0,
            interim_events=0,
            final_events=0,
            latency_avg_ms=0.0,
            latency_p95_ms=0.0,
            retries=0,
            ws_disconnects=0
        )
        
        logger.info(f"M1 session started: {session_id}")
    
    def enqueue_audio_chunk(self, session_id: str, audio_data: bytes, timestamp: float, is_voiced: bool) -> bool:
        """
        Enqueue audio chunk with VAD gating and backpressure handling.
        
        Args:
            session_id: Session identifier
            audio_data: Raw audio bytes
            timestamp: Timestamp for the chunk
            is_voiced: Whether chunk passed VAD gating
            
        Returns:
            bool: True if enqueued successfully, False if dropped
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Attempt to enqueue chunk for inactive session: {session_id}")
            return False
        
        # Update metrics
        metrics = self.session_metrics.get(session_id)
        if metrics:
            metrics.chunks_received += 1
        
        # VAD gating - only process voiced chunks
        if not is_voiced:
            logger.debug(f"Chunk {self.chunk_index} filtered out by VAD gating")
            return True  # Not an error, just filtered
        
        # Prepare chunk for queue
        chunk_data = {
            'session_id': session_id,
            'audio_data': audio_data,
            'timestamp': timestamp,
            'chunk_index': self.chunk_index,
            'enqueue_time': time.time()
        }
        
        # Attempt to enqueue with backpressure handling
        success = self.processing_queue.enqueue(chunk_data)
        
        if not success and metrics:
            metrics.chunks_dropped += 1
        elif success:
            self.chunk_index += 1
        
        # Log queue state
        queue_size = self.processing_queue.size()
        if queue_size > 0:
            logger.debug(f"Queue state: {queue_size}/{self.config.max_queue_len}, dropped: {self.processing_queue.dropped_count}")
        
        return success
    
    def process_queue(self, result_callback: Callable[[M1TranscriptionResult], None]):
        """Process chunks from the bounded queue."""
        chunk_data = self.processing_queue.dequeue()
        if not chunk_data:
            return
        
        session_id = chunk_data['session_id']
        metrics = self.session_metrics.get(session_id)
        
        if metrics:
            metrics.chunks_processed += 1
        
        # Process chunk
        try:
            start_time = time.time()
            result = self._transcribe_chunk(chunk_data)
            
            if result:
                # Calculate latency
                latency_ms = (time.time() - chunk_data['enqueue_time']) * 1000
                result.latency_ms = latency_ms
                
                # Update latency tracking
                self.latency_samples.append(latency_ms)
                if metrics:
                    metrics.latency_avg_ms = sum(self.latency_samples) / len(self.latency_samples)
                    metrics.latency_p95_ms = np.percentile(list(self.latency_samples), 95) if self.latency_samples else 0
                
                # Apply deduplication
                if not self._is_duplicate(result.text):
                    # Update deduplication buffer
                    self._update_dedup_buffer(result.text)
                    
                    # Count event type
                    if result.is_final:
                        if metrics:
                            metrics.final_events += 1
                    else:
                        if metrics:
                            metrics.interim_events += 1
                    
                    # Call result callback
                    result_callback(result)
                else:
                    logger.debug(f"Filtered duplicate text: {result.text[:50]}...")
        
        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            if metrics:
                metrics.retries += 1
    
    def finalize_session(self, session_id: str, result_callback: Callable[[M1TranscriptionResult], None]) -> M1SessionMetrics:
        """
        Finalize session: flush pending audio and emit final transcript.
        
        Args:
            session_id: Session to finalize
            result_callback: Callback for final transcript
            
        Returns:
            Session metrics
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Attempt to finalize inactive session: {session_id}")
            return None
        
        logger.info(f"Finalizing session: {session_id}")
        
        # Process any remaining chunks in queue
        while self.processing_queue.size() > 0:
            self.process_queue(result_callback)
        
        # Force final transcription with any pending audio
        session_data = self.active_sessions[session_id]
        if session_data.get('pending_chunks'):
            # Combine pending chunks and force final transcription
            combined_audio = b''.join([chunk for chunk in session_data['pending_chunks']])
            if combined_audio:
                final_chunk = {
                    'session_id': session_id,
                    'audio_data': combined_audio,
                    'timestamp': time.time(),
                    'chunk_index': self.chunk_index,
                    'enqueue_time': time.time(),
                    'force_final': True
                }
                
                result = self._transcribe_chunk(final_chunk)
                if result:
                    result.is_final = True
                    result_callback(result)
        
        # Get final metrics
        metrics = self.session_metrics.get(session_id, M1SessionMetrics(
            session_id=session_id,
            chunks_received=0,
            chunks_processed=0,
            chunks_dropped=self.processing_queue.dropped_count,
            interim_events=0,
            final_events=0,
            latency_avg_ms=0,
            latency_p95_ms=0,
            retries=0,
            ws_disconnects=0
        ))
        
        # Clean up session
        del self.active_sessions[session_id]
        if session_id in self.session_metrics:
            del self.session_metrics[session_id]
        
        # Log final metrics
        logger.info(f"Session {session_id} finalized - Processed: {metrics.chunks_processed}, "
                   f"Dropped: {metrics.chunks_dropped}, Avg Latency: {metrics.latency_avg_ms:.1f}ms")
        
        return metrics
    
    def _transcribe_chunk(self, chunk_data: Dict[str, Any]) -> Optional[M1TranscriptionResult]:
        """Transcribe audio chunk with confidence filtering."""
        try:
            audio_data = chunk_data['audio_data']
            is_force_final = chunk_data.get('force_final', False)
            
            if not self.client:
                return self._mock_transcription_m1(chunk_data)
            
            # OpenAI Whisper API call
            import io
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "chunk.wav"
            
            params = {
                "model": self.config.model,
                "file": audio_file,
                "response_format": "verbose_json",
                "temperature": self.config.temperature,
                "language": self.config.language,
            }
            
            if self.config.enable_word_timestamps:
                params["timestamp_granularities"] = ["word"]
            
            response = self.client.audio.transcriptions.create(**params)
            
            text = response.text.strip()
            confidence = self._estimate_confidence(text, len(audio_data))
            
            # Apply confidence filtering
            if confidence < self.config.min_confidence and not is_force_final:
                logger.debug(f"Filtered low confidence result: {confidence:.2f} < {self.config.min_confidence}")
                return None
            
            # Extract words with timestamps
            words = []
            if hasattr(response, 'words') and response.words:
                words = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "confidence": confidence  # Use estimated confidence
                    }
                    for word in response.words
                ]
            
            return M1TranscriptionResult(
                text=text,
                avg_confidence=confidence,
                is_final=is_force_final,
                language=response.language if hasattr(response, 'language') else self.config.language,
                duration=response.duration if hasattr(response, 'duration') else 0.0,
                timestamp=time.time(),
                words=words,
                metadata={
                    "session_id": chunk_data['session_id'],
                    "chunk_index": chunk_data['chunk_index'],
                    "audio_size": len(audio_data),
                    "model": self.config.model,
                    "queue_size": self.processing_queue.size()
                },
                latency_ms=0,  # Will be calculated by caller
                chunk_index=chunk_data['chunk_index']
            )
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    def _mock_transcription_m1(self, chunk_data: Dict[str, Any]) -> M1TranscriptionResult:
        """Mock transcription for testing with M1 format."""
        import random
        time.sleep(0.05 + random.random() * 0.1)  # Simulate API latency
        
        audio_length = len(chunk_data['audio_data']) / (16000 * 2)
        words_count = max(1, int(audio_length * 3))  # ~3 words per second
        
        mock_words = [
            "hello", "world", "this", "is", "a", "test", "transcription",
            "with", "mock", "audio", "processing", "and", "voice", "detection"
        ]
        
        text = " ".join(random.choices(mock_words, k=words_count))
        confidence = 0.7 + random.random() * 0.3
        
        # Mock word-level timestamps
        words = []
        current_time = 0.0
        for i, word in enumerate(text.split()):
            word_duration = 0.3 + random.random() * 0.4
            words.append({
                "word": word,
                "start": current_time,
                "end": current_time + word_duration,
                "confidence": confidence + random.uniform(-0.1, 0.1)
            })
            current_time += word_duration
        
        return M1TranscriptionResult(
            text=text,
            avg_confidence=confidence,
            is_final=chunk_data.get('force_final', False),
            language=self.config.language,
            duration=audio_length,
            timestamp=time.time(),
            words=words,
            metadata={
                "session_id": chunk_data['session_id'],
                "chunk_index": chunk_data['chunk_index'],
                "audio_size": len(chunk_data['audio_data']),
                "model": "mock",
                "queue_size": self.processing_queue.size()
            },
            latency_ms=0,  # Will be calculated by caller
            chunk_index=chunk_data['chunk_index']
        )
    
    def _estimate_confidence(self, text: str, audio_size: int) -> float:
        """Estimate confidence score based on text and audio characteristics."""
        if not text.strip():
            return 0.0
        
        # Base confidence on text length vs audio size ratio
        text_density = len(text.split()) / max(1, audio_size / 1000)  # Words per KB
        base_confidence = min(0.9, 0.3 + text_density * 0.1)
        
        # Boost confidence for common words
        common_words = {"the", "and", "is", "a", "to", "of", "in", "that", "have", "for"}
        word_boost = sum(0.05 for word in text.lower().split() if word in common_words)
        
        return min(0.95, base_confidence + word_boost)
    
    def _is_duplicate(self, text: str) -> bool:
        """Check if text is substantially duplicate of recent text."""
        if not text.strip() or not self.last_text_buffer.strip():
            return False
        
        # Calculate similarity ratio
        similarity = difflib.SequenceMatcher(None, 
                                           self.last_text_buffer.lower(), 
                                           text.lower()).ratio()
        
        return similarity > self.config.dedup_overlap_threshold
    
    def _update_dedup_buffer(self, text: str):
        """Update the deduplication buffer with recent text."""
        self.last_text_buffer = (self.last_text_buffer + " " + text)[-self.buffer_size_chars:]
    
    def get_session_metrics(self, session_id: str) -> Optional[M1SessionMetrics]:
        """Get current metrics for a session."""
        return self.session_metrics.get(session_id)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status for monitoring."""
        return {
            "queue_size": self.processing_queue.size(),
            "max_queue_size": self.config.max_queue_len,
            "dropped_chunks": self.processing_queue.dropped_count,
            "utilization": self.processing_queue.size() / self.config.max_queue_len
        }