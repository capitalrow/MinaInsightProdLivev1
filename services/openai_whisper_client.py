# services/openai_whisper_client.py
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
) -> str:
    """
    Send a self-contained audio file (e.g., a small webm blob) to Whisper and return text.
    This is used for both interim (small) chunks and the final full buffer.
    
    COST OPTIMIZATION: Includes quota-aware error handling with graceful degradation.
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
    while True:
        attempt += 1
        try:
            # Only pass language if it's actually a string
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
            return getattr(resp, "text", "") or ""
            
        except RateLimitError as e:
            # COST OPTIMIZATION: Quota exhausted - trigger backoff
            _LAST_QUOTA_ERROR_TIME = time.time()
            error_msg = str(e)
            
            if "quota" in error_msg.lower() or "rate" in error_msg.lower():
                logger.error(f"🚫 Quota exhausted! Backing off for {_QUOTA_BACKOFF_SECONDS}s. Error: {error_msg}")
                raise QuotaExhaustedError(f"API quota exhausted. Will retry in {_QUOTA_BACKOFF_SECONDS} seconds.")
            
            if attempt >= max_retries:
                raise
            wait_time = retry_backoff * (2 ** (attempt - 1))  # Exponential backoff
            logger.warning(f"⚠️ Rate limited, waiting {wait_time:.1f}s before retry {attempt}/{max_retries}")
            time.sleep(wait_time)
            
        except OpenAIError as e:
            error_msg = str(e)
            
            # Check if this is a quota-related error
            if "insufficient_quota" in error_msg.lower() or "quota" in error_msg.lower():
                _LAST_QUOTA_ERROR_TIME = time.time()
                logger.error(f"🚫 Quota exhausted! Error: {error_msg}")
                raise QuotaExhaustedError("API quota exhausted. Please check your OpenAI billing.")
            
            if attempt >= max_retries:
                logger.error(f"❌ Transcription failed after {max_retries} retries: {error_msg}")
                raise
                
            wait_time = retry_backoff * (2 ** (attempt - 1))  # Exponential backoff
            logger.warning(f"⚠️ API error, waiting {wait_time:.1f}s before retry {attempt}/{max_retries}: {error_msg}")
            time.sleep(wait_time)
