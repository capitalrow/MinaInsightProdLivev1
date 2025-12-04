# services/openai_whisper_client.py
"""
OpenAI Whisper API Client with Cost Tracking - Phase 2 Optimization

Integrates usage tracking for:
- Per-request cost calculation ($0.006/minute)
- API latency monitoring
- Error tracking and quota management
"""
import io
import os
import time
import logging
from typing import Optional, Tuple

from openai import OpenAI
from openai._exceptions import OpenAIError, RateLimitError, APIError

logger = logging.getLogger(__name__)

_CLIENT: Optional[OpenAI] = None

# COST OPTIMIZATION: Track API usage for quota management
_API_CALL_COUNT = 0
_LAST_QUOTA_ERROR_TIME = 0
_QUOTA_BACKOFF_SECONDS = 60  # Wait 60 seconds after quota error

# Usage tracking context (set by caller)
_CURRENT_USER_ID: Optional[str] = None
_CURRENT_SESSION_ID: Optional[str] = None

class QuotaExhaustedError(Exception):
    """Raised when API quota is exhausted - graceful degradation needed"""
    pass

def _client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OpenAI()  # reads OPENAI_API_KEY from env
    return _CLIENT

def is_quota_available() -> bool:
    """Check if we should attempt API calls (quota not recently exhausted)"""
    global _LAST_QUOTA_ERROR_TIME
    if _LAST_QUOTA_ERROR_TIME == 0:
        return True
    elapsed = time.time() - _LAST_QUOTA_ERROR_TIME
    return elapsed >= _QUOTA_BACKOFF_SECONDS

def get_api_stats() -> dict:
    """Get API usage statistics for monitoring"""
    return {
        "total_calls": _API_CALL_COUNT,
        "quota_available": is_quota_available(),
        "seconds_until_retry": max(0, _QUOTA_BACKOFF_SECONDS - (time.time() - _LAST_QUOTA_ERROR_TIME)) if _LAST_QUOTA_ERROR_TIME else 0
    }


def set_tracking_context(user_id: Optional[str] = None, session_id: Optional[str] = None):
    """Set the current user/session context for usage tracking."""
    global _CURRENT_USER_ID, _CURRENT_SESSION_ID
    _CURRENT_USER_ID = user_id
    _CURRENT_SESSION_ID = session_id


def _track_usage(
    audio_bytes: bytes,
    mime_hint: Optional[str],
    model: str,
    latency_ms: int,
    transcription_type: str = 'final',
    error_occurred: bool = False,
    error_message: Optional[str] = None
):
    """Track API usage in the database."""
    if not _CURRENT_USER_ID:
        logger.debug("📊 Skipping usage tracking - no user context")
        return
    
    try:
        from services.usage_tracking_service import track_transcription
        track_transcription(
            user_id=_CURRENT_USER_ID,
            audio_bytes=audio_bytes,
            session_id=_CURRENT_SESSION_ID,
            transcription_type=transcription_type,
            model_used=model,
            api_latency_ms=latency_ms,
            was_cached=False,
            error_occurred=error_occurred,
            error_message=error_message,
            mime_type=mime_hint
        )
    except Exception as e:
        logger.warning(f"⚠️ Usage tracking failed (non-blocking): {e}")

# Map the mime that comes from MediaRecorder to extensions Whisper accepts
_EXT_FROM_MIME = {
    "audio/webm": "webm",
    "audio/webm;codecs=opus": "webm",
    "audio/ogg": "ogg",
    "audio/ogg;codecs=opus": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/mp4": "m4a",
    "audio/aac": "m4a",
    # fallbacks
    "webm": "webm",
    "ogg": "ogg",
    "mp3": "mp3",
    "wav": "wav",
    "flac": "flac",
    "m4a": "m4a",
}

def _filename_and_mime(mime_hint: Optional[str]) -> Tuple[str, str]:
    mime = (mime_hint or "").split(";")[0].strip().lower()
    ext = _EXT_FROM_MIME.get(mime) or "webm"
    if mime not in _EXT_FROM_MIME:
        mime = "audio/webm"
    return (f"chunk.{ext}", mime)

def transcribe_bytes(
    audio_bytes: bytes,
    mime_hint: Optional[str] = None,
    language: Optional[str] = None,
    model: Optional[str] = None,
    max_retries: int = 3,
    retry_backoff: float = 1.0,
    transcription_type: str = 'final',
) -> str:
    """
    Send a self-contained audio file (e.g., a small webm blob) to Whisper and return text.
    This is used for both interim (small) chunks and the final full buffer.
    
    COST OPTIMIZATION: Includes quota-aware error handling with graceful degradation.
    PHASE 2: Includes usage tracking for cost monitoring.
    """
    global _API_CALL_COUNT, _LAST_QUOTA_ERROR_TIME
    
    if not audio_bytes:
        return ""
    
    # COST OPTIMIZATION: Check if we should skip due to recent quota error
    if not is_quota_available():
        logger.warning("⏸️ Skipping transcription - quota exhausted, backing off")
        raise QuotaExhaustedError("API quota temporarily exhausted. Retrying in 60 seconds.")

    client = _client()
    model = model or os.getenv("WHISPER_MODEL", "whisper-1")
    filename, mime = _filename_and_mime(mime_hint)
    file_tuple = (filename, io.BytesIO(audio_bytes), mime)

    attempt = 0
    start_time = time.time()
    
    while True:
        attempt += 1
        try:
            create_kwargs = {
                "file": file_tuple,
                "model": model,
            }
            lang = language or os.getenv("LANGUAGE_HINT")
            if lang:
                create_kwargs["language"] = lang
            
            _API_CALL_COUNT += 1
            logger.debug(f"📤 API call #{_API_CALL_COUNT}: transcribing {len(audio_bytes)} bytes")
            
            resp = client.audio.transcriptions.create(**create_kwargs)
            result_text = getattr(resp, "text", "") or ""
            
            latency_ms = int((time.time() - start_time) * 1000)
            _track_usage(
                audio_bytes=audio_bytes,
                mime_hint=mime_hint,
                model=model,
                latency_ms=latency_ms,
                transcription_type=transcription_type,
                error_occurred=False
            )
            
            return result_text
            
        except RateLimitError as e:
            _LAST_QUOTA_ERROR_TIME = time.time()
            error_msg = str(e)
            
            if "quota" in error_msg.lower() or "rate" in error_msg.lower():
                logger.error(f"🚫 Quota exhausted! Backing off for {_QUOTA_BACKOFF_SECONDS}s. Error: {error_msg}")
                latency_ms = int((time.time() - start_time) * 1000)
                _track_usage(
                    audio_bytes=audio_bytes,
                    mime_hint=mime_hint,
                    model=model,
                    latency_ms=latency_ms,
                    transcription_type=transcription_type,
                    error_occurred=True,
                    error_message=f"Quota exhausted: {error_msg[:200]}"
                )
                raise QuotaExhaustedError(f"API quota exhausted. Will retry in {_QUOTA_BACKOFF_SECONDS} seconds.")
            
            if attempt >= max_retries:
                latency_ms = int((time.time() - start_time) * 1000)
                _track_usage(
                    audio_bytes=audio_bytes,
                    mime_hint=mime_hint,
                    model=model,
                    latency_ms=latency_ms,
                    transcription_type=transcription_type,
                    error_occurred=True,
                    error_message=f"Rate limit exceeded after {max_retries} retries"
                )
                raise
            wait_time = retry_backoff * (2 ** (attempt - 1))
            logger.warning(f"⚠️ Rate limited, waiting {wait_time:.1f}s before retry {attempt}/{max_retries}")
            time.sleep(wait_time)
            
        except OpenAIError as e:
            error_msg = str(e)
            
            if "insufficient_quota" in error_msg.lower() or "quota" in error_msg.lower():
                _LAST_QUOTA_ERROR_TIME = time.time()
                logger.error(f"🚫 Quota exhausted! Error: {error_msg}")
                latency_ms = int((time.time() - start_time) * 1000)
                _track_usage(
                    audio_bytes=audio_bytes,
                    mime_hint=mime_hint,
                    model=model,
                    latency_ms=latency_ms,
                    transcription_type=transcription_type,
                    error_occurred=True,
                    error_message=f"Quota exhausted: {error_msg[:200]}"
                )
                raise QuotaExhaustedError("API quota exhausted. Please check your OpenAI billing.")
            
            if attempt >= max_retries:
                logger.error(f"❌ Transcription failed after {max_retries} retries: {error_msg}")
                latency_ms = int((time.time() - start_time) * 1000)
                _track_usage(
                    audio_bytes=audio_bytes,
                    mime_hint=mime_hint,
                    model=model,
                    latency_ms=latency_ms,
                    transcription_type=transcription_type,
                    error_occurred=True,
                    error_message=f"API error: {error_msg[:200]}"
                )
                raise
                
            wait_time = retry_backoff * (2 ** (attempt - 1))
            logger.warning(f"⚠️ API error, waiting {wait_time:.1f}s before retry {attempt}/{max_retries}: {error_msg}")
            time.sleep(wait_time)
