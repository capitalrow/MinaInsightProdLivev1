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
    data: { session_id, audio_data, settings }
    Frontend sends audio_data as array of bytes from MediaRecorder.
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

    # Append to full buffer for the eventual final pass
    _BUFFERS[session_id].extend(chunk)
    
    # COST OPTIMIZATION: Accumulate new chunks for incremental transcription
    _PENDING_CHUNKS[session_id].extend(chunk)

    # Only process if we have enough new audio data (cost optimization)
    pending_size = len(_PENDING_CHUNKS[session_id])
    if pending_size < _MIN_CHUNK_BYTES:
        emit("ack", {"ok": True})
        return
    
    # Rate-limit interim requests (2 second minimum between API calls)
    now = _now_ms()
    if (now - _LAST_EMIT_AT.get(session_id, 0)) < _MIN_MS_BETWEEN_INTERIM:
        emit("ack", {"ok": True})
        return

    _LAST_EMIT_AT[session_id] = now

    # COST OPTIMIZATION: Only transcribe NEW audio, not the full buffer!
    # This prevents quadratic API usage (was re-transcribing entire recording each time)
    new_audio_bytes = bytes(_PENDING_CHUNKS[session_id])
    _PENDING_CHUNKS[session_id] = bytearray()  # Clear pending after taking
    
    logger.info(f"[ws] 💰 Cost-optimized: transcribing {len(new_audio_bytes)} new bytes (not {len(_BUFFERS[session_id])} total)")
    
    try:
        text = transcribe_bytes(new_audio_bytes, mime_hint=mime_type)
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
        # Store pending audio for later processing
        _PENDING_CHUNKS[session_id].extend(new_audio_bytes)
        emit("ack", {"ok": True, "quota_paused": True})
        return
    except Exception as e:
        logger.warning(f"[ws] interim transcription error: {e}")
        emit("socket_error", {"message": "Transcription temporarily unavailable. Recording continues."})
        # Keep the audio for retry
        _PENDING_CHUNKS[session_id].extend(new_audio_bytes)
        return

    text = (text or "").strip()
    
    # COST OPTIMIZATION: Append to cumulative transcript
    if text:
        if _CUMULATIVE_TRANSCRIPT[session_id]:
            _CUMULATIVE_TRANSCRIPT[session_id] += " " + text
        else:
            _CUMULATIVE_TRANSCRIPT[session_id] = text
    
    # Enhanced: Process with speaker diarization
    speaker_info = None
    if text and session_id in _MULTI_SPEAKER_SYSTEMS:
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
    if text:
        _LAST_INTERIM_TEXT[session_id] = text
        
        # Emit enhanced transcription_result with speaker information
        # COST OPTIMIZATION: Send cumulative transcript for seamless display
        result = {
            "text": cumulative,  # Send full cumulative transcript
            "new_text": text,    # New text from this chunk
            "is_final": False,
            "confidence": 0.8,  # Default confidence for interim
            "session_id": session_id,
            "timestamp": int(_now_ms()),
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
    