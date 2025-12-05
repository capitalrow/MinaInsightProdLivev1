"""
Local Whisper Fallback Service

Uses faster-whisper for local transcription when OpenAI API is unavailable.
Provides cost-free fallback with slightly lower accuracy but instant availability.
"""

import os
import io
import time
import logging
import tempfile
import threading
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class LocalWhisperConfig:
    """Configuration for local Whisper service."""
    model_size: str = "tiny"
    device: str = "cpu"
    compute_type: str = "int8"
    beam_size: int = 5
    language: Optional[str] = None
    vad_filter: bool = True
    vad_parameters: Dict[str, Any] = field(default_factory=lambda: {
        "threshold": 0.5,
        "min_speech_duration_ms": 250,
        "min_silence_duration_ms": 100,
    })

class LocalWhisperService:
    """
    Local Whisper transcription using faster-whisper.
    
    Designed as a fallback when OpenAI API is:
    - Unavailable (rate limits, outages)
    - Too slow (high latency)
    - Cost optimization needed
    
    Uses the 'tiny' model by default for fast processing.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[LocalWhisperConfig] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.config = config or LocalWhisperConfig()
        self._model = None
        self._model_loading = False
        self._model_loaded = threading.Event()
        self._initialized = True
        
        self._stats = {
            'total_transcriptions': 0,
            'successful_transcriptions': 0,
            'failed_transcriptions': 0,
            'total_audio_seconds': 0.0,
            'total_processing_time': 0.0,
            'model_load_time': 0.0,
        }
        
        logger.info(f"LocalWhisperService initialized with model: {self.config.model_size}")
    
    @property
    def is_available(self) -> bool:
        """Check if local Whisper is available."""
        try:
            from faster_whisper import WhisperModel
            return True
        except ImportError:
            return False
    
    @property
    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None
    
    def _load_model(self) -> bool:
        """
        Lazy load the Whisper model.
        Returns True if model is loaded successfully.
        """
        if self._model is not None:
            return True
            
        if self._model_loading:
            self._model_loaded.wait(timeout=120)
            return self._model is not None
        
        try:
            self._model_loading = True
            
            from faster_whisper import WhisperModel
            
            logger.info(f"Loading local Whisper model: {self.config.model_size}...")
            start_time = time.time()
            
            self._model = WhisperModel(
                self.config.model_size,
                device=self.config.device,
                compute_type=self.config.compute_type,
            )
            
            load_time = time.time() - start_time
            self._stats['model_load_time'] = load_time
            
            logger.info(f"Local Whisper model loaded in {load_time:.2f}s")
            self._model_loaded.set()
            return True
            
        except Exception as e:
            logger.error(f"Failed to load local Whisper model: {e}")
            self._model_loading = False
            return False
    
    def transcribe_bytes(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> Tuple[str, Dict[str, Any]]:
        """
        Transcribe audio bytes using local Whisper.
        
        Args:
            audio_bytes: Raw audio data
            mime_type: Audio MIME type
            
        Returns:
            Tuple of (transcribed_text, metadata)
        """
        self._stats['total_transcriptions'] += 1
        start_time = time.time()
        
        metadata = {
            'model': f'local-whisper-{self.config.model_size}',
            'is_fallback': True,
            'processing_time_ms': 0,
            'audio_duration_seconds': 0,
            'language': None,
            'language_probability': 0,
        }
        
        if not self.is_available:
            logger.warning("faster-whisper not available")
            self._stats['failed_transcriptions'] += 1
            return "", metadata
        
        if not self._load_model():
            self._stats['failed_transcriptions'] += 1
            return "", metadata
        
        try:
            ext = self._get_extension(mime_type)
            
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            try:
                segments, info = self._model.transcribe(
                    tmp_path,
                    beam_size=self.config.beam_size,
                    language=self.config.language,
                    vad_filter=self.config.vad_filter,
                    vad_parameters=self.config.vad_parameters if self.config.vad_filter else None,
                )
                
                text_parts = []
                for segment in segments:
                    text_parts.append(segment.text.strip())
                
                transcribed_text = " ".join(text_parts)
                
                processing_time = (time.time() - start_time) * 1000
                
                metadata.update({
                    'processing_time_ms': processing_time,
                    'audio_duration_seconds': info.duration,
                    'language': info.language,
                    'language_probability': info.language_probability,
                })
                
                self._stats['successful_transcriptions'] += 1
                self._stats['total_audio_seconds'] += info.duration
                self._stats['total_processing_time'] += processing_time / 1000
                
                logger.debug(
                    f"Local transcription: {len(transcribed_text)} chars, "
                    f"{processing_time:.0f}ms, lang={info.language}"
                )
                
                return transcribed_text.strip(), metadata
                
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Local Whisper transcription failed: {e}")
            self._stats['failed_transcriptions'] += 1
            metadata['error'] = str(e)
            return "", metadata
    
    def transcribe_file(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Transcribe audio file using local Whisper.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (transcribed_text, metadata)
        """
        with open(file_path, 'rb') as f:
            audio_bytes = f.read()
        
        ext = os.path.splitext(file_path)[1].lstrip('.')
        mime_type = f"audio/{ext}" if ext else "audio/wav"
        
        return self.transcribe_bytes(audio_bytes, mime_type)
    
    def preload_model(self):
        """
        Preload the model in background thread.
        Call this at app startup for faster first transcription.
        """
        def _load():
            self._load_model()
        
        thread = threading.Thread(target=_load, daemon=True)
        thread.start()
        logger.info("Started background model preload")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        stats = self._stats.copy()
        
        if stats['successful_transcriptions'] > 0:
            stats['avg_processing_time'] = (
                stats['total_processing_time'] / stats['successful_transcriptions']
            )
            stats['real_time_factor'] = (
                stats['total_processing_time'] / stats['total_audio_seconds']
                if stats['total_audio_seconds'] > 0 else 0
            )
        else:
            stats['avg_processing_time'] = 0
            stats['real_time_factor'] = 0
        
        stats['model_loaded'] = self.is_model_loaded
        stats['model_size'] = self.config.model_size
        
        return stats
    
    def _get_extension(self, mime_type: str) -> str:
        """Get file extension from MIME type."""
        mime_map = {
            'audio/wav': 'wav',
            'audio/wave': 'wav',
            'audio/x-wav': 'wav',
            'audio/webm': 'webm',
            'audio/mp3': 'mp3',
            'audio/mpeg': 'mp3',
            'audio/ogg': 'ogg',
            'audio/flac': 'flac',
            'audio/m4a': 'm4a',
            'audio/mp4': 'm4a',
        }
        return mime_map.get(mime_type.lower(), 'wav')


_service_instance = None

def get_local_whisper_service(config: Optional[LocalWhisperConfig] = None) -> LocalWhisperService:
    """Get singleton instance of LocalWhisperService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = LocalWhisperService(config)
    return _service_instance


def transcribe_with_local_fallback(
    audio_bytes: bytes,
    mime_type: str = "audio/wav",
    openai_transcribe_fn = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Transcribe audio with OpenAI API, falling back to local Whisper on failure.
    
    Args:
        audio_bytes: Raw audio data
        mime_type: Audio MIME type
        openai_transcribe_fn: Optional OpenAI transcription function
        
    Returns:
        Tuple of (transcribed_text, metadata)
    """
    metadata = {'used_fallback': False}
    
    if openai_transcribe_fn:
        try:
            text = openai_transcribe_fn(audio_bytes, mime_type)
            if text:
                metadata['model'] = 'whisper-1'
                metadata['used_fallback'] = False
                return text, metadata
        except Exception as e:
            logger.warning(f"OpenAI transcription failed, falling back to local: {e}")
    
    service = get_local_whisper_service()
    text, local_metadata = service.transcribe_bytes(audio_bytes, mime_type)
    
    metadata.update(local_metadata)
    metadata['used_fallback'] = True
    
    return text, metadata
