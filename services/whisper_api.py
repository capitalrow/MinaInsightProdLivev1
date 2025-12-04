import io
import os
import logging
import time
from typing import Optional, Tuple, Dict, Any
from openai import OpenAI, APIError, RateLimitError, APIConnectionError

logger = logging.getLogger(__name__)

_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
_USE_LOCAL_FALLBACK = os.getenv("WHISPER_LOCAL_FALLBACK", "true").lower() == "true"

_client = None
_fallback_stats = {
    'openai_calls': 0,
    'openai_successes': 0,
    'openai_failures': 0,
    'fallback_calls': 0,
    'fallback_successes': 0,
}

def _client_ok() -> Optional[OpenAI]:
    global _client
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    if _client is None:
        _client = OpenAI(api_key=api_key)
    return _client

def _ext_from_mime(mime: str) -> str:
    if not mime:
        return "webm"
    m = mime.lower()
    if "ogg" in m: return "ogg"
    if "webm" in m: return "webm"
    if "wav" in m: return "wav"
    if "mp3" in m: return "mp3"
    return "webm"

def _transcribe_openai(audio_bytes: bytes, mime_type: str) -> str:
    """Internal OpenAI transcription call."""
    client = _client_ok()
    if not client:
        return ""
    ext = _ext_from_mime(mime_type)
    fname = f"chunk.{ext}"
    fileobj = io.BytesIO(audio_bytes)
    fileobj.name = fname
    resp = client.audio.transcriptions.create(
        model=_MODEL,
        file=(fname, fileobj, mime_type or "application/octet-stream"),
    )
    return (getattr(resp, "text", "") or "").strip()

def _transcribe_local(audio_bytes: bytes, mime_type: str) -> Tuple[str, bool]:
    """
    Fallback to local Whisper transcription.
    Returns (text, success_flag).
    """
    try:
        from services.local_whisper_service import get_local_whisper_service
        service = get_local_whisper_service()
        if not service.is_available:
            return "", False
        text, metadata = service.transcribe_bytes(audio_bytes, mime_type)
        return text, bool(text)
    except Exception as e:
        logger.warning(f"Local Whisper fallback failed: {e}")
        return "", False

def transcribe_bytes(audio_bytes: bytes, mime_type: str) -> str:
    """
    Returns text from OpenAI Whisper when API key present.
    Falls back to local Whisper if OpenAI fails or returns empty.
    """
    global _fallback_stats
    
    client = _client_ok()
    use_fallback = False
    
    if client:
        _fallback_stats['openai_calls'] += 1
        try:
            text = _transcribe_openai(audio_bytes, mime_type)
            if text:
                _fallback_stats['openai_successes'] += 1
                return text
            else:
                logger.warning("OpenAI returned empty transcription, trying fallback")
                use_fallback = True
        except (APIError, RateLimitError, APIConnectionError) as e:
            logger.warning(f"OpenAI Whisper API error: {e}")
            _fallback_stats['openai_failures'] += 1
            use_fallback = True
        except Exception as e:
            logger.error(f"Unexpected OpenAI error: {e}")
            _fallback_stats['openai_failures'] += 1
            use_fallback = True
    else:
        use_fallback = True
    
    if use_fallback and _USE_LOCAL_FALLBACK:
        _fallback_stats['fallback_calls'] += 1
        text, success = _transcribe_local(audio_bytes, mime_type)
        if success:
            _fallback_stats['fallback_successes'] += 1
            logger.info("Used local Whisper fallback successfully")
            return text
    
    return ""

def transcribe_bytes_with_metadata(
    audio_bytes: bytes, 
    mime_type: str
) -> Tuple[str, Dict[str, Any]]:
    """
    Transcribe with full metadata including fallback information.
    
    Returns:
        Tuple of (transcribed_text, metadata_dict)
    """
    global _fallback_stats
    
    metadata = {
        'model': _MODEL,
        'used_fallback': False,
        'processing_time_ms': 0,
    }
    
    start_time = time.time()
    client = _client_ok()
    
    if client:
        _fallback_stats['openai_calls'] += 1
        try:
            text = _transcribe_openai(audio_bytes, mime_type)
            if text:
                _fallback_stats['openai_successes'] += 1
                metadata['processing_time_ms'] = (time.time() - start_time) * 1000
                return text, metadata
        except (APIError, RateLimitError, APIConnectionError) as e:
            logger.warning(f"OpenAI Whisper API error, trying fallback: {e}")
            _fallback_stats['openai_failures'] += 1
            metadata['openai_error'] = str(e)
        except Exception as e:
            logger.error(f"Unexpected OpenAI error: {e}")
            _fallback_stats['openai_failures'] += 1
            metadata['openai_error'] = str(e)
    
    if _USE_LOCAL_FALLBACK:
        _fallback_stats['fallback_calls'] += 1
        try:
            from services.local_whisper_service import get_local_whisper_service
            service = get_local_whisper_service()
            if service.is_available:
                text, local_meta = service.transcribe_bytes(audio_bytes, mime_type)
                if text:
                    _fallback_stats['fallback_successes'] += 1
                    metadata.update(local_meta)
                    metadata['used_fallback'] = True
                    logger.info("Used local Whisper fallback successfully")
                    return text, metadata
        except Exception as e:
            logger.warning(f"Local fallback also failed: {e}")
            metadata['fallback_error'] = str(e)
    
    metadata['processing_time_ms'] = (time.time() - start_time) * 1000
    return "", metadata

def get_fallback_stats() -> Dict[str, Any]:
    """Get transcription fallback statistics."""
    stats = _fallback_stats.copy()
    
    total_calls = stats['openai_calls'] + stats['fallback_calls']
    if total_calls > 0:
        stats['openai_success_rate'] = (
            stats['openai_successes'] / stats['openai_calls'] * 100
            if stats['openai_calls'] > 0 else 0
        )
        stats['fallback_success_rate'] = (
            stats['fallback_successes'] / stats['fallback_calls'] * 100
            if stats['fallback_calls'] > 0 else 0
        )
        stats['fallback_usage_rate'] = stats['fallback_calls'] / total_calls * 100
    else:
        stats['openai_success_rate'] = 0
        stats['fallback_success_rate'] = 0
        stats['fallback_usage_rate'] = 0
    
    stats['local_fallback_enabled'] = _USE_LOCAL_FALLBACK
    
    try:
        from services.local_whisper_service import get_local_whisper_service
        service = get_local_whisper_service()
        stats['local_whisper_available'] = service.is_available
        stats['local_whisper_model_loaded'] = service.is_model_loaded
        stats['local_whisper_stats'] = service.get_stats()
    except:
        stats['local_whisper_available'] = False
        stats['local_whisper_model_loaded'] = False
        stats['local_whisper_stats'] = {}
    
    return stats

def preload_local_whisper():
    """Preload local Whisper model for faster fallback."""
    if not _USE_LOCAL_FALLBACK:
        logger.info("Local fallback disabled, skipping preload")
        return False
    
    try:
        from services.local_whisper_service import get_local_whisper_service
        service = get_local_whisper_service()
        if service.is_available:
            service.preload_model()
            return True
    except Exception as e:
        logger.error(f"Failed to preload local Whisper: {e}")
    return False