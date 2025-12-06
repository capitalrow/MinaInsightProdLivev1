# routes/websocket.py
import base64
import binascii
import logging
import time
import uuid
from collections import defaultdict
from typing import Dict, Optional
from datetime import datetime

from flask import Blueprint
from flask_socketio import emit

# Import the socketio instance from the consolidated app
from app import socketio

# Import database models for persistence
from models import db, Session, Segment, Participant

from services.openai_whisper_client import transcribe_bytes, QuotaExhaustedError, is_quota_available, get_api_stats
from services.speaker_diarization import SpeakerDiarizationEngine, DiarizationConfig
from services.multi_speaker_diarization import MultiSpeakerDiarization

logger = logging.getLogger(__name__)
ws_bp = Blueprint("ws", __name__)

# Per-session state (dev-grade, in-memory for audio buffering)
_BUFFERS: Dict[str, bytearray] = defaultdict(bytearray)
_LAST_EMIT_AT: Dict[str, float] = {}
_LAST_INTERIM_TEXT: Dict[str, str] = {}

# COST OPTIMIZATION: Track transcribed position to avoid re-transcribing
_TRANSCRIBED_POSITION: Dict[str, int] = defaultdict(int)  # bytes already transcribed
_PENDING_CHUNKS: Dict[str, bytearray] = defaultdict(bytearray)  # new audio not yet transcribed
_CUMULATIVE_TRANSCRIPT: Dict[str, str] = defaultdict(str)  # running transcript text

# DIFFERENTIAL STREAMING: Store WebM headers and track transcription state
_WEBM_HEADERS: Dict[str, bytes] = {}  # First chunk contains WebM header
_LAST_WINDOW_TRANSCRIPT: Dict[str, str] = {}  # Last transcription result for delta detection
_DIFFERENTIAL_MODE: Dict[str, bool] = {}  # Track if session is using differential streaming

# Speaker diarization state (per session)
_SPEAKER_ENGINES: Dict[str, SpeakerDiarizationEngine] = {}
_MULTI_SPEAKER_SYSTEMS: Dict[str, MultiSpeakerDiarization] = {}
_SESSION_SPEAKERS: Dict[str, Dict[str, Dict]] = defaultdict(dict)  # session_id -> speaker_id -> speaker_info

# Tunables - OPTIMIZED FOR COST
_MIN_MS_BETWEEN_INTERIM = 2000.0     # 2 second minimum between API calls (was 400ms!)
_MIN_CHUNK_BYTES = 8000              # Minimum audio bytes before transcribing (~0.5s of audio)
_MAX_INTERIM_WINDOW_SEC = 14.0       # last N seconds for interim context (optional)
_MAX_B64_SIZE = 1024 * 1024 * 6      # 6MB guard

def _now_ms() -> float:
    return time.time() * 1000.0

def _decode_b64(b64: Optional[str]) -> bytes:
    if not b64:
        return b""
    if len(b64) > _MAX_B64_SIZE:
        raise ValueError("audio_data_b64 too large")
    try:
        return base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"base64 decode failed: {e}")

def _normalize_word(word: str) -> str:
    """Normalize a word for comparison: lowercase, strip punctuation."""
    import re
    # Remove all punctuation and convert to lowercase
    return re.sub(r'[^\w\s]', '', word.lower()).strip()

def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    import re
    # Remove punctuation and extra whitespace, lowercase
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return ' '.join(text.split())

def _extract_text_delta(previous_text: str, new_text: str) -> str:
    """
    Extract only the NEW words from new_text that don't overlap with previous_text.
    Uses fuzzy word-level matching with normalization to handle:
    - Punctuation differences ("So tomorrow" vs "So, tomorrow")
    - Minor transcription variations
    - Overlapping audio windows
    
    Returns: Only the genuinely new text that wasn't in the previous transcription.
    """
    if not previous_text or not previous_text.strip():
        return new_text.strip() if new_text else ""
    if not new_text or not new_text.strip():
        return ""
    
    # Get original words with case preserved
    original_new_words = new_text.split()
    if not original_new_words:
        return ""
    
    # Normalize for comparison
    prev_normalized = _normalize_text(previous_text)
    new_normalized = _normalize_text(new_text)
    
    prev_words_normalized = prev_normalized.split()
    new_words_normalized = new_normalized.split()
    
    if not prev_words_normalized or not new_words_normalized:
        return new_text.strip()
    
    # Strategy 1: Find longest suffix-prefix overlap (most common case)
    # Check if beginning of new_text overlaps with end of previous_text
    best_overlap = 0
    max_check = min(len(prev_words_normalized), len(new_words_normalized))
    
    for overlap_len in range(1, max_check + 1):
        # Compare last N words of previous with first N words of new
        prev_suffix = prev_words_normalized[-overlap_len:]
        new_prefix = new_words_normalized[:overlap_len]
        
        # Check for exact match after normalization
        if prev_suffix == new_prefix:
            best_overlap = overlap_len
    
    if best_overlap > 0:
        # Found overlap - return only the new content after the overlap
        if best_overlap >= len(original_new_words):
            # Complete overlap - nothing new
            logger.debug(f"[delta] Complete overlap ({best_overlap} words) - no new content")
            return ""
        delta = " ".join(original_new_words[best_overlap:])
        logger.debug(f"[delta] Found {best_overlap}-word overlap, delta: '{delta[:50]}...'")
        return delta
    
    # Strategy 2: Check if new_text is an extension of previous_text
    # (handles case where transcription just got longer with same prefix)
    if new_normalized.startswith(prev_normalized):
        # New text extends previous - extract only the new suffix
        # Find where the extension begins in original text
        prev_word_count = len(prev_words_normalized)
        if prev_word_count < len(original_new_words):
            delta = " ".join(original_new_words[prev_word_count:])
            logger.debug(f"[delta] Extension detected, delta: '{delta[:50]}...'")
            return delta
        return ""
    
    # Strategy 3: Find partial overlap using sequence matching
    # Useful when there's a middle overlap or transcription variations
    from difflib import SequenceMatcher
    
    # Use SequenceMatcher to find common subsequences
    matcher = SequenceMatcher(None, prev_words_normalized, new_words_normalized)
    
    # Find matching blocks
    matching_blocks = matcher.get_matching_blocks()
    
    # Look for a match that starts at the end of previous and beginning of new
    for block in matching_blocks:
        prev_start, new_start, length = block.a, block.b, block.size
        if length == 0:
            continue
            
        # If there's a match at the start of new_text (overlapping content)
        if new_start == 0 and length >= 3:  # Require at least 3 matching words
            # Check if this match connects to near the end of previous
            if prev_start >= len(prev_words_normalized) - length - 5:  # Allow some slack
                # This is overlap - skip these words
                skip_count = length
                if skip_count < len(original_new_words):
                    delta = " ".join(original_new_words[skip_count:])
                    logger.debug(f"[delta] Sequence match found ({length} words), delta: '{delta[:50]}...'")
                    return delta
                return ""
    
    # Strategy 4: Check for significant content overlap using similarity ratio
    # If the texts are very similar, it's likely repeated content
    similarity = matcher.ratio()
    if similarity > 0.8:  # Very similar - likely duplicate
        # Find truly new content by looking for words not in previous
        prev_word_set = set(prev_words_normalized)
        new_words = []
        consecutive_new = 0
        start_collecting = False
        
        for i, (norm_word, orig_word) in enumerate(zip(new_words_normalized, original_new_words)):
            if norm_word not in prev_word_set:
                consecutive_new += 1
                if consecutive_new >= 2:  # Start collecting after 2 consecutive new words
                    start_collecting = True
            else:
                consecutive_new = 0
            
            if start_collecting:
                new_words.append(orig_word)
        
        if new_words:
            delta = " ".join(new_words)
            logger.debug(f"[delta] High similarity ({similarity:.2f}), extracted unique: '{delta[:50]}...'")
            return delta
        
        logger.debug(f"[delta] High similarity ({similarity:.2f}) - treating as duplicate")
        return ""
    
    # If no overlap detected and similarity is low, this is genuinely new content
    # (could be a different topic or significant pause in speech)
    if similarity < 0.3:
        logger.debug(f"[delta] Low similarity ({similarity:.2f}) - treating as new content")
        return new_text.strip()
    
    # Middle ground: Some similarity but not complete overlap
    # Try to find where new content begins using the last matching block
    last_match_in_new = 0
    for block in matching_blocks:
        if block.size > 0:
            end_in_new = block.b + block.size
            if end_in_new > last_match_in_new:
                last_match_in_new = end_in_new
    
    if last_match_in_new > 0 and last_match_in_new < len(original_new_words):
        delta = " ".join(original_new_words[last_match_in_new:])
        if delta:
            logger.debug(f"[delta] Partial match, delta starts at word {last_match_in_new}: '{delta[:50]}...'")
            return delta
    
    # Fallback: Return empty if we can't determine (safer than duplicating)
    logger.debug(f"[delta] Could not determine delta (similarity: {similarity:.2f}) - returning empty")
    return ""

@socketio.on("join_session")
def on_join_session(data):
    from flask_login import current_user
    
    session_id = (data or {}).get("session_id")
    if not session_id:
        emit("error", {"message": "Missing session_id"})
        return
    
    # 🔒 CROWN¹⁰ Fix: Get workspace_id and user_id from authenticated user
    workspace_id = current_user.workspace_id if current_user.is_authenticated else None
    user_id = current_user.id if current_user.is_authenticated else None
    
    logger.info(f"🔑 [CROWN¹⁰] join_session - User: {user_id}, Workspace: {workspace_id}, Authenticated: {current_user.is_authenticated}")
    
    if not workspace_id:
        logger.error(f"❌ [CROWN¹⁰] CRITICAL: Cannot join session without workspace_id for user {user_id}")
        emit('error', {'message': 'Workspace not found. Please ensure you are logged in.'})
        return
    
    # Create or get existing session in database
    try:
        session = db.session.query(Session).filter_by(external_id=session_id).first()
        if not session:
            session = Session(
                external_id=session_id,
                title="Live Transcription Session",
                status="active",
                started_at=datetime.utcnow(),
                user_id=user_id,
                workspace_id=workspace_id,
                trace_id=uuid.uuid4(),
                version=1
            )
            db.session.add(session)
            db.session.commit()
            logger.info(f"✅ [CROWN¹⁰] Session created in DB - external_id={session_id}, workspace={workspace_id}, user={user_id}")
        else:
            logger.info(f"[ws] Using existing session: {session_id}")
    except Exception as e:
        logger.error(f"❌ [ws] Database error creating session: {e}", exc_info=True)
        # Continue with in-memory only
    
    # init/clear in-memory buffers
    _BUFFERS[session_id] = bytearray()
    _LAST_EMIT_AT[session_id] = 0
    _LAST_INTERIM_TEXT[session_id] = ""
    
    # COST OPTIMIZATION: Reset incremental transcription state
    _TRANSCRIBED_POSITION[session_id] = 0
    _PENDING_CHUNKS[session_id] = bytearray()
    _CUMULATIVE_TRANSCRIPT[session_id] = ""
    
    # Initialize speaker diarization for this session
    try:
        # Initialize speaker diarization engine
        diarization_config = DiarizationConfig(
            max_speakers=6,  # Support up to 6 speakers for meetings
            min_segment_duration=0.5,
            enable_voice_features=True,
            auto_label_speakers=True
        )
        _SPEAKER_ENGINES[session_id] = SpeakerDiarizationEngine(diarization_config)
        _SPEAKER_ENGINES[session_id].initialize_session(session_id)
        
        # Initialize multi-speaker system
        _MULTI_SPEAKER_SYSTEMS[session_id] = MultiSpeakerDiarization(max_speakers=6)
        
        # Initialize session speakers dictionary
        _SESSION_SPEAKERS[session_id] = {}
        
        logger.info(f"🎤 Speaker diarization initialized for session: {session_id}")
    except Exception as e:
        logger.warning(f"⚠️ Speaker diarization initialization failed: {e}")
    
    emit("server_hello", {"msg": "connected", "t": int(_now_ms())})
    logger.info(f"[ws] join_session {session_id}")

@socketio.on("audio_chunk")  
def on_audio_chunk(data):
    """
    data: { session_id, audio_data, settings, is_differential, window_audio }
    
    DIFFERENTIAL STREAMING MODE (is_differential=True):
    - Frontend sends a sliding window of audio (last ~5 seconds)
    - Backend transcribes the window and extracts only NEW text
    - Provides consistent <2s latency regardless of recording length
    
    ACCUMULATED MODE (is_accumulated=True):
    - Frontend sends full accumulated audio (legacy mode)
    - Growing latency as recording lengthens
    """
    session_id = (data or {}).get("session_id")
    if not session_id:
        emit("error", {"message": "Missing session_id in audio_chunk"})
        return

    # Get settings from frontend
    settings = (data or {}).get("settings", {})
    mime_type = settings.get("mimeType", "audio/webm")
    
    # Handle audio data - frontend sends as array of bytes
    audio_data = (data or {}).get("audio_data")
    if not audio_data:
        emit("error", {"message": "Missing audio_data in audio_chunk"})
        return
    
    try:
        # Convert array of bytes to bytes object
        if isinstance(audio_data, list):
            chunk = bytes(audio_data)
        elif isinstance(audio_data, str):
            # Fallback: try base64 decode
            chunk = _decode_b64(audio_data)
        else:
            chunk = bytes(audio_data)
    except (ValueError, TypeError) as e:
        emit("error", {"message": f"bad_audio: {e}"})
        return

    if not chunk:
        return

    # Check streaming mode
    is_differential = (data or {}).get("is_differential", False)
    is_accumulated = (data or {}).get("is_accumulated", False)
    now = _now_ms()
    
    if is_differential:
        # DIFFERENTIAL STREAMING MODE: Sliding window for consistent latency
        _DIFFERENTIAL_MODE[session_id] = True
        
        # Store full buffer for final transcription
        _BUFFERS[session_id] = bytearray(chunk)
        
        # Rate-limit: 1.5 second minimum for differential mode (faster than accumulated)
        DIFFERENTIAL_MIN_MS = 1500.0
        if (now - _LAST_EMIT_AT.get(session_id, 0)) < DIFFERENTIAL_MIN_MS:
            emit("ack", {"ok": True})
            return
        
        _LAST_EMIT_AT[session_id] = now
        
        # Transcribe the sliding window
        audio_to_transcribe = chunk
        audio_size_kb = len(chunk) / 1024
        logger.info(f"[ws] ⚡ Differential mode: transcribing {audio_size_kb:.1f}KB sliding window")
        
    elif is_accumulated:
        # ACCUMULATED MODE: Full audio each time (legacy)
        _BUFFERS[session_id] = bytearray(chunk)
        
        # Rate-limit interim requests (2 second minimum between API calls)
        if (now - _LAST_EMIT_AT.get(session_id, 0)) < _MIN_MS_BETWEEN_INTERIM:
            emit("ack", {"ok": True})
            return
        
        _LAST_EMIT_AT[session_id] = now
        
        # Transcribe the full accumulated audio
        audio_to_transcribe = chunk
        logger.info(f"[ws] 🚀 Accumulated mode: transcribing {len(audio_to_transcribe)} bytes")
    else:
        # LEGACY/INCREMENTAL MODE: Append to buffer for eventual final pass
        _BUFFERS[session_id].extend(chunk)
        
        # COST OPTIMIZATION: Accumulate new chunks for incremental transcription
        _PENDING_CHUNKS[session_id].extend(chunk)

        # Only process if we have enough new audio data (cost optimization)
        pending_size = len(_PENDING_CHUNKS[session_id])
        if pending_size < _MIN_CHUNK_BYTES:
            emit("ack", {"ok": True})
            return
        
        # Rate-limit interim requests (2 second minimum between API calls)
        if (now - _LAST_EMIT_AT.get(session_id, 0)) < _MIN_MS_BETWEEN_INTERIM:
            emit("ack", {"ok": True})
            return

        _LAST_EMIT_AT[session_id] = now

        # COST OPTIMIZATION: Only transcribe NEW audio, not the full buffer!
        audio_to_transcribe = bytes(_PENDING_CHUNKS[session_id])
        _PENDING_CHUNKS[session_id] = bytearray()  # Clear pending after taking
        
        logger.info(f"[ws] 💰 Cost-optimized: transcribing {len(audio_to_transcribe)} new bytes (not {len(_BUFFERS[session_id])} total)")
    
    try:
        text = transcribe_bytes(audio_to_transcribe, mime_hint=mime_type)
    except QuotaExhaustedError as e:
        # GRACEFUL DEGRADATION: Quota exhausted - notify user with friendly message
        logger.warning(f"[ws] 🚫 Quota exhausted: {e}")
        stats = get_api_stats()
        emit("quota_warning", {
            "message": "Transcription is temporarily paused. Your recording is still being saved.",
            "retry_in_seconds": int(stats["seconds_until_retry"]),
            "action": "Your transcript will update when the service resumes.",
            "session_id": session_id
        })
        # Store pending audio for later processing (only for non-accumulated mode)
        if not is_accumulated:
            _PENDING_CHUNKS[session_id].extend(audio_to_transcribe)
        emit("ack", {"ok": True, "quota_paused": True})
        return
    except Exception as e:
        logger.warning(f"[ws] interim transcription error: {e}")
        emit("socket_error", {"message": "Transcription temporarily unavailable. Recording continues."})
        # Keep the audio for retry (only for non-accumulated mode)
        if not is_accumulated:
            _PENDING_CHUNKS[session_id].extend(audio_to_transcribe)
        return

    text = (text or "").strip()
    
    # DIFFERENTIAL MODE: Extract only NEW text using delta detection
    delta_text = text
    if is_differential and text:
        previous_text = _LAST_WINDOW_TRANSCRIPT.get(session_id, "")
        delta_text = _extract_text_delta(previous_text, text)
        _LAST_WINDOW_TRANSCRIPT[session_id] = text
        
        if delta_text:
            logger.info(f"[ws] ⚡ Delta extracted: '{delta_text[:50]}...' (from window: '{text[:30]}...')")
        else:
            logger.debug(f"[ws] ⚡ No new text in this window (overlap with previous)")
    
    # Update cumulative transcript with DELTA only (or full text for legacy modes)
    if delta_text:
        if _CUMULATIVE_TRANSCRIPT[session_id]:
            _CUMULATIVE_TRANSCRIPT[session_id] += " " + delta_text
        else:
            _CUMULATIVE_TRANSCRIPT[session_id] = delta_text
    
    # Enhanced: Process with speaker diarization
    speaker_info = None
    if delta_text and session_id in _MULTI_SPEAKER_SYSTEMS:
        try:
            # Convert audio bytes to numpy array for speaker processing
            import numpy as np
            audio_array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Process with speaker diarization
            segment_id = f"{session_id}_interim_{int(now)}"
            speaker_segment = _MULTI_SPEAKER_SYSTEMS[session_id].process_audio_segment(
                audio_array, now / 1000.0, segment_id, text
            )
            
            speaker_info = {
                "speaker_id": speaker_segment.speaker_id,
                "speaker_confidence": speaker_segment.speaker_confidence,
                "overlap_detected": speaker_segment.overlap_detected,
                "background_speakers": speaker_segment.background_speakers
            }
            
            # Update session speakers
            if speaker_segment.speaker_id not in _SESSION_SPEAKERS[session_id]:
                _SESSION_SPEAKERS[session_id][speaker_segment.speaker_id] = {
                    "id": speaker_segment.speaker_id,
                    "name": f"Speaker {len(_SESSION_SPEAKERS[session_id]) + 1}",
                    "first_seen": now,
                    "total_segments": 0,
                    "last_activity": now
                }
            
            _SESSION_SPEAKERS[session_id][speaker_segment.speaker_id]["last_activity"] = now
            _SESSION_SPEAKERS[session_id][speaker_segment.speaker_id]["total_segments"] += 1
            
            logger.debug(f"🎤 Speaker identified: {speaker_segment.speaker_id} (confidence: {speaker_segment.speaker_confidence:.2f})")
            
        except Exception as e:
            logger.warning(f"⚠️ Speaker diarization failed for interim: {e}")
    
    # Emit if we have new text (use cumulative transcript for display)
    cumulative = _CUMULATIVE_TRANSCRIPT.get(session_id, "")
    if delta_text:
        _LAST_INTERIM_TEXT[session_id] = delta_text
        
        # Emit enhanced transcription_result with speaker information
        # For differential mode: new_text is the DELTA only
        result = {
            "text": cumulative,       # Send full cumulative transcript
            "new_text": delta_text,   # New text from this chunk (delta for differential mode)
            "is_final": False,
            "confidence": 0.8,  # Default confidence for interim
            "session_id": session_id,
            "timestamp": int(_now_ms()),
            "is_differential": is_differential,  # Flag for frontend
            "cost_optimized": True  # Flag for debugging
        }
        
        # Add speaker information if available
        if speaker_info:
            result.update({
                "speaker_id": speaker_info["speaker_id"],
                "speaker_confidence": speaker_info["speaker_confidence"],
                "speaker_name": _SESSION_SPEAKERS[session_id][speaker_info["speaker_id"]]["name"],
                "overlap_detected": speaker_info["overlap_detected"],
                "background_speakers": speaker_info["background_speakers"]
            })
        
        emit("transcription_result", result)
        logger.debug(f"[ws] Emitted: '{delta_text[:50]}...' (cumulative: {len(cumulative)} chars)")

    emit("ack", {"ok": True})

@socketio.on("finalize_session")
def on_finalize(data):
    session_id = (data or {}).get("session_id")
    if not session_id:
        emit("error", {"message": "Missing session_id in finalize_session"})
        return

    # Get settings from frontend
    settings = (data or {}).get("settings", {})
    mime_type = settings.get("mimeType", "audio/webm")
    
    # FINAL-ONLY MODE: Get audio from the finalize event (sent as complete blob)
    audio_data = (data or {}).get("audio_data")
    if audio_data:
        # Audio sent directly in finalize_session
        if isinstance(audio_data, list):
            full_audio = bytes(audio_data)
        else:
            full_audio = bytes(audio_data)
        logger.info(f"[ws] 🎤 Final-only mode: received {len(full_audio)} bytes for transcription")
    else:
        # Fallback to buffered audio (for backwards compatibility)
        full_audio = bytes(_BUFFERS.get(session_id, b""))
    
    if not full_audio:
        emit("final_transcript", {"text": ""})
        emit("transcription_result", {
            "text": "",
            "is_final": True,
            "session_id": session_id,
            "timestamp": int(_now_ms())
        })
        return

    try:
        final_text = transcribe_bytes(full_audio, mime_hint=mime_type)
    except Exception as e:
        logger.error(f"[ws] final transcription error: {e}")
        emit("error", {"message": "Transcription failed (final)."})
        return

    final_text = (final_text or "").strip()
    
    # Save final segment to database
    try:
        session = db.session.query(Session).filter_by(external_id=session_id).first()
        if session and final_text:
            segment = Segment(
                session_id=session.id,
                text=final_text,
                kind="final",
                start_ms=0,  # Could be calculated from audio duration
                end_ms=int(len(full_audio) / 16000 * 1000),  # Convert to milliseconds
                avg_confidence=0.9  # Correct field name
            )
            db.session.add(segment)
            
            # Update session status
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            session.total_segments = 1
            session.total_duration = len(full_audio) / 16000
            
            db.session.commit()
            logger.info(f"[ws] Saved final segment to DB for session: {session_id}")
            
            # 🚀 CROWN+ Event Sequencing: Trigger post-transcription pipeline
            try:
                from services.post_transcription_orchestrator import PostTranscriptionOrchestrator
                orchestrator = PostTranscriptionOrchestrator()
                logger.info(f"[ws] 🎬 Starting post-transcription pipeline for: {session_id}")
                
                # Submit to background task manager (non-blocking)
                # Events will stream back via WebSocket as each stage completes
                task_id = orchestrator.process_session_async(session_id)
                
                logger.info(f"[ws] ✅ Pipeline submitted to background (task_id={task_id})")
                    
            except Exception as pipeline_error:
                # Graceful degradation - log error but don't fail the finalization
                logger.error(f"[ws] ❌ Post-transcription pipeline failed for {session_id}: {pipeline_error}", exc_info=True)
                # User still gets transcript even if pipeline fails
            
    except Exception as e:
        logger.error(f"[ws] Database error saving segment: {e}")

    # Emit transcription_result that frontend expects
    emit("transcription_result", {
        "text": final_text,
        "is_final": True,
        "confidence": 0.9,  # Higher confidence for final
        "session_id": session_id,
        "timestamp": int(_now_ms())
    })
    
    # clear session memory
    _BUFFERS.pop(session_id, None)
    _LAST_EMIT_AT.pop(session_id, None)
    _LAST_INTERIM_TEXT.pop(session_id, None)
    
    # Clear speaker diarization state
    _SPEAKER_ENGINES.pop(session_id, None)
    _MULTI_SPEAKER_SYSTEMS.pop(session_id, None)
    _SESSION_SPEAKERS.pop(session_id, None)
    
    logger.info(f"🎤 Cleared speaker diarization state for session: {session_id}")

@socketio.on("get_session_speakers")
def on_get_session_speakers(data):
    """Get current speakers for a session."""
    session_id = (data or {}).get("session_id")
    if not session_id:
        emit("error", {"message": "Missing session_id"})
        return
    
    speakers = _SESSION_SPEAKERS.get(session_id, {})
    speaker_list = []
    
    for speaker_id, speaker_info in speakers.items():
        speaker_list.append({
            "id": speaker_id,
            "name": speaker_info["name"],
            "first_seen": speaker_info["first_seen"],
            "last_activity": speaker_info["last_activity"],
            "total_segments": speaker_info["total_segments"],
            "is_active": (time.time() * 1000 - speaker_info["last_activity"]) < 10000  # Active within last 10 seconds
        })
    
    # Sort by last activity (most recent first)
    speaker_list.sort(key=lambda x: x["last_activity"], reverse=True)
    
    emit("session_speakers", {
        "session_id": session_id,
        "speakers": speaker_list,
        "total_speakers": len(speaker_list),
        "timestamp": int(_now_ms())
    })
    
    logger.debug(f"🎤 Sent speaker list for session {session_id}: {len(speaker_list)} speakers")
    