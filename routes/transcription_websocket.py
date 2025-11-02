# routes/transcription_websocket.py
"""
WebSocket handlers specifically for the /transcription namespace
"""
import logging
import time
import uuid
import base64
import requests
import threading
from datetime import datetime
from flask import session, request
from flask_socketio import emit, disconnect, join_room, leave_room
from flask_login import current_user

# Import the socketio instance from the consolidated app
from app import socketio

# Import advanced buffer management
from services.session_buffer_manager import buffer_registry, BufferConfig
from services.transcription_service import TranscriptionService
from services.session_service import SessionService
from services.post_transcription_orchestrator import PostTranscriptionOrchestrator
from flask_login import current_user
# After existing imports
import asyncio
from jobs.analysis_dispatcher import AnalysisDispatcher


logger = logging.getLogger(__name__)

# Session state storage with advanced buffering
active_sessions = {}
buffer_config = BufferConfig(
    max_buffer_ms=30000,
    min_flush_ms=2000,
    max_flush_ms=8000,
    enable_vad=True,
    enable_quality_gating=True
)

# Background processing worker
processing_workers = {}

def _background_processor(session_id: str, buffer_manager):
    """Simple background worker for processing buffered audio chunks"""
    logger.info(f"🔧 Started background processor for session {session_id}")
    
    try:
        while session_id in active_sessions:
            time.sleep(1)  # Simple polling interval
            # Basic background processing - can be enhanced later
            if session_id not in active_sessions:
                break
                
    except Exception as e:
        logger.error(f"Background processor error for session {session_id}: {e}")
    finally:
        logger.info(f"🔧 Background processor stopped for session {session_id}")

@socketio.on('connect', namespace='/transcription')
def on_connect(auth=None):
    """Handle client connection to transcription namespace with authentication"""
    # Check authentication - require valid user session
    if not current_user.is_authenticated:
        logger.warning(f"[transcription] Unauthenticated connection attempt from {request.sid}")
        emit('error', {'message': 'Authentication required'})
        disconnect()
        return False
    
    logger.info(f"[transcription] Authenticated client connected: {request.sid} (user: {current_user.id})")
    join_room(f"user_{current_user.id}")
    emit('status', {
        'status': 'connected', 
        'message': 'Connected to transcription service',
        'user_id': current_user.id
    })

@socketio.on('disconnect', namespace='/transcription')
def on_disconnect():
    """Handle client disconnection with comprehensive cleanup"""
    logger.info(f"[transcription] Client disconnected: {request.sid}")
    # Clean up any active sessions for this client
    sessions_to_remove = []
    for session_id, session_info in active_sessions.items():
        if session_info.get('client_sid') == request.sid:
            sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        # Comprehensive session cleanup
        session_info = active_sessions.get(session_id, {})
        
        # End buffer manager session
        if 'buffer_manager' in session_info:
            buffer_manager = session_info['buffer_manager']
            buffer_manager.end_session()
        
        # Release from buffer registry  
        buffer_registry.release(session_id)
        
        # Terminate processing thread if exists
        if session_id in processing_workers:
            worker = processing_workers[session_id]
            logger.info(f"[transcription] Terminating processing thread for session: {session_id}")
            # The thread will terminate when session is removed from active_sessions
            processing_workers.pop(session_id, None)
        
        # Remove from active sessions
        active_sessions.pop(session_id, None)
        logger.info(f"[transcription] Comprehensive cleanup completed for session: {session_id}")

@socketio.on('start_session', namespace='/transcription')
def on_start_session(data):
    """Start a new transcription session"""
    try:
        session_id = str(uuid.uuid4())
        
        # Store session info with advanced buffer manager
        buffer_manager = buffer_registry.get_or_create_session(session_id)
        
        # 🔒 CROWN¹⁰ Fix: Capture workspace_id and user_id from authenticated user
        workspace_id = current_user.workspace_id if current_user.is_authenticated else None
        user_id = current_user.id if current_user.is_authenticated else None
        
        if not workspace_id:
            logger.error(f"❌ Cannot start session without workspace_id for user {user_id}")
            emit('error', {'message': 'Workspace not found. Please ensure you are logged in.'})
            return
        
        # 🔒 CROWN¹⁰ Fix: Create Session record in database immediately
        try:
            db_session_id = SessionService.create_session(
                external_id=session_id,
                title=data.get('title', 'Live Transcription'),
                workspace_id=workspace_id,
                user_id=user_id
            )
            logger.info(f"✅ [transcription] Created Session in database: db_id={db_session_id}, external_id={session_id}, workspace={workspace_id}")
        except Exception as db_error:
            logger.error(f"❌ [transcription] Failed to create Session in database: {db_error}")
            emit('error', {'message': 'Failed to create session in database'})
            return
        
        active_sessions[session_id] = {
            'client_sid': request.sid,
            'started_at': datetime.utcnow(),
            'language': data.get('language', 'en'),
            'enhance_audio': data.get('enhance_audio', True),
            'buffer_manager': buffer_manager,
            'audio_buffer': bytearray(),
            'webm_header': None,
            'last_process_time': 0,
            'workspace_id': workspace_id,
            'user_id': user_id,
            'db_session_id': db_session_id  # Store database Session.id for later use
        }
        
        # Start background processing worker for this session
        worker = threading.Thread(
            target=_background_processor,
            args=(session_id, buffer_manager),
            daemon=True
        )
        worker.start()
        processing_workers[session_id] = worker
        
        # Join the session room
        join_room(session_id)
        
        logger.info(f"[transcription] Started session: {session_id}")
        
        emit('session_started', {
            'session_id': session_id,
            'status': 'ready',
            'message': 'Transcription session started'
        })
        
    except Exception as e:
        logger.error(f"[transcription] Error starting session: {e}")
        emit('error', {'message': f'Failed to start session: {str(e)}'})

@socketio.on('audio_data', namespace='/transcription')
def on_audio_data(data):
    """Handle incoming audio data"""
    try:
        # Enhanced audio data handling with robust format detection
        if isinstance(data, dict) and 'data' in data:
            # Structured format with metadata
            try:
                audio_bytes = base64.b64decode(data['data'])
                mime_type = data.get('mimeType', 'audio/webm')
                data_size = data.get('size', len(audio_bytes))
                
                logger.info(f"[transcription] Received {mime_type} audio: {len(audio_bytes)} bytes (reported: {data_size})")
                
                # Validate audio data integrity
                if len(audio_bytes) < 100:
                    logger.warning(f"[transcription] Audio chunk too small: {len(audio_bytes)} bytes")
                    return  # Skip small chunks silently
                    
                # Detect format discrepancies
                if abs(len(audio_bytes) - data_size) > 100:
                    logger.warning(f"[transcription] Size mismatch: actual={len(audio_bytes)}, reported={data_size}")
                    
            except Exception as e:
                logger.error(f"[transcription] Failed to decode structured audio: {e}")
                emit('error', {'message': 'Invalid audio data format'})
                return
                
        elif isinstance(data, str):
            # Legacy base64 string format
            try:
                audio_bytes = base64.b64decode(data)
                mime_type = 'audio/webm'
                logger.info(f"[transcription] Legacy format: {len(audio_bytes)} bytes")
            except Exception as e:
                logger.error(f"[transcription] Invalid base64 audio data: {e}")
                emit('error', {'message': 'Invalid base64 audio data'})
                return
                
        elif isinstance(data, (bytes, bytearray)):
            # Raw bytes format
            audio_bytes = bytes(data)
            mime_type = 'audio/webm'
            logger.info(f"[transcription] Raw bytes: {len(audio_bytes)} bytes")
        else:
            logger.error(f"[transcription] Unsupported data type: {type(data)}")
            emit('error', {'message': 'Unsupported audio data format'})
            return
        
        # Find the current session for this client
        session_id = None
        for sid, session_info in active_sessions.items():
            if session_info.get('client_sid') == request.sid:
                session_id = sid
                break
        
        if not session_id:
            emit('error', {'message': 'No active session found'})
            return
        
        # 🔥 CRITICAL FIX: Buffer chunks and reconstruct proper WebM containers
        session_info = active_sessions[session_id]
        
        # Initialize WebM reconstruction data
        if 'webm_header' not in session_info:
            session_info['webm_header'] = None
            session_info['last_process_time'] = 0
            
        # Detect and store EBML header from first chunk
        if session_info['webm_header'] is None and len(audio_bytes) > 12:
            if audio_bytes[:4] == b'\x1a\x45\xdf\xa3':  # EBML signature
                session_info['webm_header'] = audio_bytes
                logger.info(f"🎯 [transcription] Captured WebM header chunk: {len(audio_bytes)} bytes")
            
        # Buffer the audio chunk
        session_info['audio_buffer'].extend(audio_bytes)
        buffer_size = len(session_info['audio_buffer'])
        
        # Process buffered audio more frequently for real-time transcription
        current_time = time.time()
        should_process = (
            buffer_size > 30000 or 
            (buffer_size > 5000 and current_time - session_info['last_process_time'] > 2)
        )
        
        if should_process:
            # Reconstruct proper WebM container
            if session_info['webm_header'] and len(session_info['audio_buffer']) > len(session_info['webm_header']):
                # Create proper WebM by ensuring EBML header is present
                if session_info['audio_buffer'][:4] != b'\x1a\x45\xdf\xa3':
                    reconstructed_audio = session_info['webm_header'] + bytes(session_info['audio_buffer'])
                    logger.info(f"🔧 [transcription] Reconstructed WebM with header: {len(reconstructed_audio)} bytes")
                else:
                    reconstructed_audio = bytes(session_info['audio_buffer'])
            else:
                reconstructed_audio = bytes(session_info['audio_buffer'])
        
            try:
                # Send reconstructed audio to transcription API
                file_extension = '.wav' if 'wav' in mime_type else '.webm'
                
                # 🔒 CROWN¹⁰ Fix: Pass workspace_id and user_id to transcription endpoint
                post_data = {
                    'session_id': session_id,
                    'is_interim': 'true',
                    'chunk_id': str(int(time.time() * 1000)),
                    'workspace_id': str(session_info.get('workspace_id')),
                    'user_id': str(session_info.get('user_id'))
                }
                
                response = requests.post(
                    'http://localhost:5000/api/transcribe-audio',
                    files={'audio': (f'audio{file_extension}', reconstructed_audio, mime_type)},
                    data=post_data,
                    timeout=10
                )
            
                if response.status_code == 200:
                    result = response.json()
                    text = result.get('final_text', '') or result.get('text', '')
                    if text and text.strip():
                        # 🔒 CROWN¹⁰ Fix: Save transcription to database with workspace_id and user_id
                        try:
                            transcription_service = TranscriptionService()
                            transcription_service._save_transcription_text(
                                session_id=session_id,
                                text=text,
                                confidence=result.get('confidence', 0.9),
                                workspace_id=session_info.get('workspace_id'),
                                user_id=session_info.get('user_id')
                            )
                            logger.info(f"✅ [transcription] Saved to database: session={session_id}, workspace={session_info.get('workspace_id')}")
                        except Exception as db_error:
                            logger.error(f"❌ [transcription] Failed to save to database: {db_error}")
                        
                        # Emit properly formatted transcription result
                        emit('transcription_result', {
                            'text': text,
                            'is_final': result.get('is_final', True),
                            'confidence': result.get('confidence', 0.9),
                            'timestamp': int(time.time() * 1000),
                            'speaker_id': result.get('speaker_id', 'Speaker 1'),
                            'processing_time_ms': result.get('processing_time_ms', 100)
                        })
                        logger.info(f"✅ [transcription] Emitted result: '{text[:50]}...'")
                    else:
                        logger.debug(f"📝 [transcription] Empty result, skipping emission")
                        pass
                else:
                    logger.warning(f"[transcription] API error: {response.status_code}")
                    
            except requests.RequestException as e:
                logger.error(f"[transcription] API request failed: {e}")
                # Don't emit error for network issues, just log them
            
            # Reset buffer with some overlap for context continuity
            overlap_size = min(5000, len(session_info['audio_buffer']) // 3)
            session_info['audio_buffer'] = session_info['audio_buffer'][-overlap_size:]
            session_info['last_process_time'] = current_time
            logger.info(f"🔄 [transcription] Buffer reset, kept {overlap_size} bytes overlap")
        
    except Exception as e:
        logger.error(f"[transcription] Error processing audio: {e}")
        emit('error', {'message': f'Audio processing error: {str(e)}'})

@socketio.on('end_session', namespace='/transcription')
def on_end_session(data=None):
    """End the current transcription session and trigger post-meeting analysis"""
    try:
        sessions_to_end = []
        for session_id, session_info in active_sessions.items():
            if session_info.get('client_sid') == request.sid:
                sessions_to_end.append(session_id)

        for session_id in sessions_to_end:
            # 🧹 Clean up WebSocket rooms and local buffers
            leave_room(session_id)
            session_info = active_sessions.pop(session_id, None)
            logger.info(f"[transcription] Ended session: {session_id}")

            # 🗂️ Optional: persist final transcript before triggering analysis
            try:
                buffer_manager = session_info.get("buffer_manager")
                if buffer_manager:
                    final_transcript = buffer_manager.flush_and_finalize(session_id=session_id)
                    logger.info(f"[transcription] Final transcript stored for session {session_id} ({len(final_transcript)} chars)")
                else:
                    logger.warning(f"[transcription] No buffer manager found for session {session_id}")
            except Exception as e:
                logger.error(f"[transcription] Error finalizing transcript: {e}")

            # 🚀 CROWN¹⁰: Finalize session and trigger post-transcription pipeline directly
            try:
                # Get the Session object from database
                from models.core_models import Session
                db_session = Session.query.filter_by(external_id=session_id).first()
                
                if db_session:
                    # Directly trigger PostTranscriptionOrchestrator
                    orchestrator = PostTranscriptionOrchestrator()
                    orchestrator.trigger_post_processing(db_session)
                    logger.info(f"✅ [transcription] Session {session_id} finalized, post-transcription pipeline started")
                else:
                    logger.warning(f"⚠️ [transcription] Session {session_id} not found in database for finalization")
            except Exception as finalize_error:
                logger.error(f"❌ [transcription] Failed to finalize session: {finalize_error}", exc_info=True)

            # ✅ Notify the client that the session is done
            emit('session_ended', {
                'session_id': session_id,
                'status': 'completed',
                'message': 'Transcription session ended. Analysis started in background.'
            })

    except Exception as e:
        logger.error(f"[transcription] Error ending session: {e}")
        emit('error', {'message': f'Failed to end session: {str(e)}'})

logger.info("✅ Transcription WebSocket namespace handlers registered")