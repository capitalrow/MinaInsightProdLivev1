# routes/enhanced_transcription_websocket.py
"""
ADVANCED TRANSCRIPTION WEBSOCKET HANDLERS
Comprehensive and extensive transcription processing with advanced buffering,
real-time quality monitoring, adaptive processing, and sophisticated error handling.
"""
import logging
import time
import uuid
import base64
import requests
import threading
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from queue import Queue, Empty
from threading import Event

from flask_socketio import emit, disconnect, join_room, leave_room
from flask import request
import flask_socketio
from typing import Dict
from jobs.analysis_dispatcher import AnalysisDispatcher

# Import the socketio instance from the consolidated app
from app import socketio

# Import advanced buffer management and services
from services.session_buffer_manager import buffer_registry, BufferConfig, SessionBufferManager
from services.streaming_transcription_service import streaming_transcription_service, TranscriptionChunk
from services.usage_tracking_service import enforce_usage_limits, can_use_streaming, get_enforcement_status

logger = logging.getLogger(__name__)

# Phase 3: Direct transcription using streaming service for faster delivery
def _transcribe_direct(session_id: str, audio_data: bytes, metadata: Dict, processing_state: Dict) -> Optional[Dict]:
    """Direct transcription using streaming service for <2s latency (Phase 3)"""
    try:
        chunk = TranscriptionChunk(
            chunk_id=int(time.time() * 1000),
            session_id=session_id,
            audio_data=audio_data,
            timestamp=time.time(),
            duration_ms=metadata.get('duration_ms', 2500),
            sequence=processing_state.get('sequence', 0),
            is_final=False
        )
        
        processing_state['sequence'] = processing_state.get('sequence', 0) + 1
        
        result = streaming_transcription_service.process_chunk(chunk)
        
        if result and result.text:
            return {
                'success': True,
                'text': result.text,
                'confidence': result.confidence,
                'is_final': result.is_interim == False,
                'chunk_id': str(result.chunk_id),
                'processing_time': result.latency_ms,
                'audio_quality': 'high' if result.confidence > 0.8 else 'medium',
                'speech_ratio': metadata.get('speech_ratio', 0.5)
            }
        return None
    except Exception as e:
        logger.error(f"Direct transcription failed: {e}")
        return None

def _background_processor(session_id: str, buffer_manager: SessionBufferManager):
    """Enhanced background worker with event-driven processing and dynamic backoff"""
    logger.info(f"🔧 Started optimized background processor for session {session_id}")
    
    processing_state = {
        'consecutive_failures': 0,
        'last_success_time': time.time(),
        'adaptive_flush_interval': 2.0,  # Start with 2 second intervals
        'quality_score': 1.0,
        'speech_segments': [],
        'interim_transcript': '',
        'pending_results': [],
        'idle_time': 0,
        'last_activity': time.time()
    }
    
    # Event-driven processing setup
    processing_queue = Queue(maxsize=50)
    flush_event = Event()
    
    # Dynamic backoff configuration
    min_sleep = 0.5  # Minimum 500ms instead of 50ms
    max_sleep = 5.0  # Maximum 5 seconds
    idle_threshold = 10.0  # Consider idle after 10 seconds
    
    while buffer_manager.is_active:
        try:
            current_time = time.time()
            
            # Calculate idle time for dynamic backoff
            time_since_activity = current_time - processing_state['last_activity']
            is_idle = time_since_activity > idle_threshold
            
            # Adaptive quality monitoring
            if current_time - processing_state['last_success_time'] > 10:
                processing_state['quality_score'] *= 0.9  # Degrade quality score
                processing_state['adaptive_flush_interval'] = min(10, processing_state['adaptive_flush_interval'] * 1.2)
            
            # Check if we should flush with adaptive timing
            should_process = buffer_manager.should_flush() or _should_adaptive_flush(buffer_manager, processing_state)
            
            if should_process:
                processing_state['last_activity'] = current_time
                
                # Assemble enhanced payload
                payload_bytes, format_type, metadata = buffer_manager.assemble_flush_payload()
                
                if payload_bytes:
                    # Enhanced transcription request processing
                    success = _process_enhanced_transcription_request(
                        session_id, payload_bytes, format_type, metadata, processing_state
                    )
                    
                    if success:
                        processing_state['consecutive_failures'] = 0
                        processing_state['last_success_time'] = current_time
                        processing_state['quality_score'] = min(1.0, processing_state['quality_score'] * 1.1)
                        processing_state['adaptive_flush_interval'] = max(1.0, processing_state['adaptive_flush_interval'] * 0.9)
                        
                        # Reset buffer with intelligent overlap
                        buffer_manager.reset_with_overlap()
                    else:
                        processing_state['consecutive_failures'] += 1
                        # Exponential backoff on failures
                        failure_backoff = min(5, 0.5 * (2 ** processing_state['consecutive_failures']))
                        time.sleep(failure_backoff)
            
            # Emit real-time processing metrics (less frequently)
            if current_time % 10 < 0.5:  # Every 10 seconds instead of 5
                _emit_processing_metrics(session_id, buffer_manager, processing_state)
            
            # Dynamic backoff based on activity and quality
            if is_idle:
                # Long sleep when idle to reduce CPU usage
                sleep_time = max_sleep
                processing_state['idle_time'] += 1
            elif processing_state['consecutive_failures'] > 0:
                # Moderate sleep when having issues
                sleep_time = min_sleep * (1 + processing_state['consecutive_failures'])
            elif processing_state['quality_score'] > 0.8:
                # Normal sleep for good quality
                sleep_time = min_sleep
            else:
                # Slightly longer sleep for degraded quality
                sleep_time = min_sleep * 1.5
            
            # Cap the sleep time
            sleep_time = min(max_sleep, max(min_sleep, sleep_time))
            time.sleep(sleep_time)
            
        except Exception as e:
            logger.error(f"❌ Enhanced processor error for session {session_id}: {e}")
            processing_state['consecutive_failures'] += 1
            # Use dynamic backoff even for exceptions
            error_sleep = min(max_sleep, max(min_sleep, processing_state['consecutive_failures']))
            time.sleep(error_sleep)
    
    logger.info(f"🔚 Enhanced background processor ended for session {session_id}")

def _should_adaptive_flush(buffer_manager: SessionBufferManager, processing_state: Dict) -> bool:
    """Determine if adaptive flushing should occur based on advanced criteria"""
    current_time = time.time()
    
    # Time-based adaptive flush
    time_since_last = current_time - buffer_manager.last_flush
    if time_since_last > processing_state['adaptive_flush_interval']:
        return True
    
    # Speech pattern based flush
    if len(processing_state['speech_segments']) > 3:
        # Check for natural speech breaks
        recent_silence = sum(1 for seg in processing_state['speech_segments'][-3:] if not seg.get('has_speech', True))
        if recent_silence >= 2:  # At least 2 silent segments
            return True
    
    # Quality-based flush
    if processing_state['quality_score'] < 0.5 and time_since_last > 1.0:
        return True
    
    return False

def _process_enhanced_transcription_request(
    session_id: str, 
    audio_data: bytes, 
    format_type: str, 
    metadata: Dict,
    processing_state: Dict
) -> bool:
    """Process transcription request with comprehensive enhancements (Phase 3: direct transcription)"""
    try:
        # Phase 3: Try direct transcription first for lower latency
        response = _transcribe_direct(session_id, audio_data, metadata, processing_state)
        
        if response and response.get('success'):
            # Advanced result processing
            _process_enhanced_transcription_result(session_id, response, processing_state)
            logger.debug(f"✅ Direct transcription succeeded in {response.get('processing_time', 0):.0f}ms")
            return True
        
        # Fallback to API request if direct fails
        enhanced_payload = _prepare_enhanced_payload(session_id, audio_data, metadata, processing_state)
        response = _make_resilient_api_request(enhanced_payload, processing_state)
        
        if response and response.get('success'):
            _process_enhanced_transcription_result(session_id, response, processing_state)
            return True
        else:
            logger.warning(f"⚠️ Enhanced transcription failed for session {session_id}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Enhanced transcription processing failed for session {session_id}: {e}")
        return False

def _prepare_enhanced_payload(session_id: str, audio_data: bytes, metadata: Dict, processing_state: Dict) -> Dict:
    """Prepare enhanced payload with comprehensive metadata"""
    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
    
    return {
        'session_id': session_id,
        'audio_data': audio_b64,
        'chunk_id': f"{session_id}_{int(time.time() * 1000)}",
        'is_interim': True,
        'enhanced_metadata': {
            **metadata,
            'quality_score': processing_state['quality_score'],
            'consecutive_failures': processing_state['consecutive_failures'],
            'adaptive_interval': processing_state['adaptive_flush_interval'],
            'speech_history': processing_state['speech_segments'][-5:],  # Last 5 segments
            'processing_timestamp': time.time(),
            'confidence_threshold': 0.7 if processing_state['quality_score'] > 0.8 else 0.5
        },
        'processing_hints': {
            'expected_language': 'en',
            'audio_quality': _assess_audio_quality(metadata),
            'context_available': len(processing_state['interim_transcript']) > 0,
            'previous_text': processing_state['interim_transcript'][-200:] if processing_state['interim_transcript'] else ''
        }
    }

def _assess_audio_quality(metadata: Dict) -> str:
    """Assess audio quality based on metadata"""
    speech_ratio = metadata.get('speech_ratio', 0.5)
    avg_energy = metadata.get('avg_energy', 0.1)
    
    if speech_ratio > 0.7 and avg_energy > 0.3:
        return 'high'
    elif speech_ratio > 0.4 and avg_energy > 0.1:
        return 'medium'
    else:
        return 'low'

def _make_resilient_api_request(payload: Dict, processing_state: Dict) -> Optional[Dict]:
    """Make API request with enhanced resilience and circuit breaker pattern"""
    max_retries = 3
    backoff_factor = 1.5
    timeout = 15
    
    for attempt in range(max_retries):
        try:
            # Exponential backoff on retries
            if attempt > 0:
                wait_time = backoff_factor ** attempt
                time.sleep(wait_time)
                logger.info(f"🔄 Retry attempt {attempt + 1} after {wait_time:.1f}s wait")
            
            response = requests.post(
                'http://127.0.0.1:5000/api/transcribe-audio-enhanced',
                json=payload,
                timeout=timeout,
                headers={
                    'Content-Type': 'application/json',
                    'X-Processing-Attempt': str(attempt + 1),
                    'X-Session-Quality': str(processing_state['quality_score'])
                }
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limit
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                logger.warning(f"⚠️ API returned status {response.status_code}")
                
        except requests.Timeout:
            logger.warning(f"⏱️ Request timeout on attempt {attempt + 1}")
            timeout = min(30, timeout * 1.5)  # Increase timeout
        except requests.RequestException as e:
            logger.warning(f"🌐 Network error on attempt {attempt + 1}: {e}")
    
    return None

def _process_enhanced_transcription_result(session_id: str, result: Dict, processing_state: Dict):
    """Process transcription result with advanced enhancements (Phase 3: latency tracking)"""
    try:
        text = result.get('text', '').strip()
        confidence = result.get('confidence', 0.0)
        is_final = result.get('is_final', False)
        processing_time = result.get('processing_time', 0)
        
        # Phase 3: Track and emit latency metrics
        processing_state.setdefault('latency_samples', [])
        if processing_time > 0:
            processing_state['latency_samples'].append(processing_time)
            if len(processing_state['latency_samples']) > 100:
                processing_state['latency_samples'] = processing_state['latency_samples'][-100:]
            
            avg_latency = sum(processing_state['latency_samples']) / len(processing_state['latency_samples'])
            samples = sorted(processing_state['latency_samples'])
            p95_idx = int(len(samples) * 0.95)
            p95_latency = samples[min(p95_idx, len(samples) - 1)]
            
            if len(processing_state['latency_samples']) % 5 == 0:
                socketio.emit('latency_metrics', {
                    'session_id': session_id,
                    'current_latency_ms': processing_time,
                    'avg_latency_ms': round(avg_latency, 1),
                    'p95_latency_ms': round(p95_latency, 1),
                    'target_latency_ms': 2000,
                    'meets_target': avg_latency < 2000,
                    'sample_count': len(processing_state['latency_samples'])
                }, room=session_id, namespace='/transcription')
        
        # Enhanced confidence filtering
        min_confidence = processing_state.get('confidence_threshold', 0.6)
        if confidence < min_confidence and len(text) < 10:
            logger.debug(f"🔇 Low confidence result filtered: {confidence:.2f}")
            return
        
        # Advanced result processing
        enhanced_result = {
            'transcript': text,
            'interim_transcript': text if not is_final else '',
            'final_transcript': text if is_final else '',
            'confidence': confidence,
            'is_final': is_final,
            'session_id': session_id,
            'segment_id': result.get('chunk_id', str(uuid.uuid4())),
            'latency_ms': result.get('processing_time', 0),
            'word_count': len(text.split()) if text else 0,
            'quality_indicators': {
                'confidence_score': confidence,
                'audio_quality': result.get('audio_quality', 'unknown'),
                'processing_quality': processing_state['quality_score'],
                'speech_ratio': result.get('speech_ratio', 0.0)
            },
            'advanced_features': {
                'context_aware': len(processing_state['interim_transcript']) > 0,
                'adaptive_processing': True,
                'quality_gated': True,
                'real_time_optimized': True
            },
            'timestamp': time.time()
        }
        
        # Update processing state
        if not is_final:
            processing_state['interim_transcript'] = text
        else:
            processing_state['interim_transcript'] = ''
            
        # Update speech segments history
        processing_state['speech_segments'].append({
            'text': text,
            'confidence': confidence,
            'timestamp': time.time(),
            'has_speech': len(text) > 0,
            'is_final': is_final
        })
        
        # Keep only recent segments
        if len(processing_state['speech_segments']) > 20:
            processing_state['speech_segments'] = processing_state['speech_segments'][-15:]
        
        # Emit enhanced result to client
        socketio.emit('enhanced_transcription_result', enhanced_result, 
                     to=session_id, namespace='/transcription')
        
        # Also emit compatible result for existing frontend
        socketio.emit('transcription_result', {
            'transcript': text,
            'is_final': is_final,
            'confidence': confidence,
            'segment_id': enhanced_result['segment_id'],
            'latency_ms': enhanced_result['latency_ms']
        }, to=session_id, namespace='/transcription')
        
        logger.info(f"✅ Enhanced result delivered for session {session_id}: '{text[:50]}...'")
        
    except Exception as e:
        logger.error(f"❌ Enhanced result processing failed for session {session_id}: {e}")

def _emit_processing_metrics(session_id: str, buffer_manager: SessionBufferManager, processing_state: Dict):
    """Emit comprehensive real-time processing metrics"""
    try:
        metrics = buffer_manager.get_metrics()
        
        enhanced_metrics = {
            **metrics,
            'processing_state': {
                'quality_score': processing_state['quality_score'],
                'adaptive_interval': processing_state['adaptive_flush_interval'],
                'consecutive_failures': processing_state['consecutive_failures'],
                'speech_segments_count': len(processing_state['speech_segments']),
                'interim_length': len(processing_state['interim_transcript'])
            },
            'performance_indicators': {
                'avg_latency': _calculate_avg_latency(processing_state['speech_segments']),
                'processing_efficiency': processing_state['quality_score'],
                'error_rate': processing_state['consecutive_failures'] / max(1, metrics.get('chunks_processed', 1)),
                'throughput_score': _calculate_throughput_score(metrics)
            }
        }
        
        socketio.emit('enhanced_processing_metrics', enhanced_metrics, 
                     to=session_id, namespace='/transcription')
                     
    except Exception as e:
        logger.error(f"❌ Metrics emission failed for session {session_id}: {e}")

def _calculate_avg_latency(segments: List[Dict]) -> float:
    """Calculate average processing latency from segments"""
    if not segments:
        return 0.0
    
    latencies = [seg.get('latency', 0) for seg in segments[-10:]]  # Last 10 segments
    return sum(latencies) / len(latencies) if latencies else 0.0

def _calculate_throughput_score(metrics: Dict) -> float:
    """Calculate processing throughput score"""
    chunks_processed = metrics.get('chunks_processed', 0)
    chunks_received = metrics.get('chunks_received', 1)
    
    if chunks_received == 0:
        return 1.0
    
    return min(1.0, chunks_processed / chunks_received)

# Enhanced session state storage with advanced features
enhanced_active_sessions = {}
enhanced_buffer_config = BufferConfig(
    max_buffer_ms=25000,      # Reduced for lower latency
    min_flush_ms=1500,        # Faster minimum flush (Phase 3: unchanged)
    max_flush_ms=2500,        # Phase 3: Reduced from 6000 to 2500 for <2s latency
    overlap_ms=300,           # Phase 3: Reduced from 750 to 300 for faster processing
    enable_vad=True,
    enable_quality_gating=True,
    min_energy_threshold=0.005,  # More sensitive threshold
    vad_mode=1               # Less aggressive VAD
)

# Enhanced WebSocket handlers
@socketio.on('connect', namespace='/transcription')
def on_enhanced_connect():
    """Enhanced client connection handler"""
    client_id = flask_socketio.request.sid
    logger.info(f"🔌 Enhanced transcription client connected: {client_id}")
    
    # Send enhanced connection status
    emit('enhanced_status', {
        'status': 'connected',
        'message': 'Connected to enhanced transcription service',
        'features': {
            'adaptive_processing': True,
            'quality_monitoring': True,
            'real_time_metrics': True,
            'advanced_buffering': True,
            'vad_processing': True,
            'multi_format_support': True
        },
        'client_id': client_id,
        'timestamp': time.time()
    })

@socketio.on('start_enhanced_session', namespace='/transcription')
def on_start_enhanced_session(data):
    """Start enhanced transcription session with advanced features"""
    try:
        from flask_login import current_user
        from flask import session as flask_session
        
        session_id = str(uuid.uuid4())
        client_id = flask_socketio.request.sid
        
        # Phase 3 Security Fix: Get authenticated user from server-side session
        # NEVER trust client-supplied user_id for enforcement
        user_id = None
        
        # Try Flask-Login current_user first
        try:
            if current_user and current_user.is_authenticated:
                user_id = str(current_user.id)
                logger.debug(f"🔐 Using authenticated user: {user_id}")
        except Exception:
            pass
        
        # Fallback to Flask session user_id
        if not user_id:
            user_id = flask_session.get('user_id')
        
        # Final fallback to anonymous (will be subject to Free tier limits)
        if not user_id:
            user_id = 'anonymous'
            logger.debug(f"⚠️ Anonymous user - applying Free tier limits")
        
        # Phase 3: Enforce usage limits before starting session (server-verified user)
        allowed, error_msg, usage_info = enforce_usage_limits(user_id)
        if not allowed:
            logger.warning(f"⛔ Usage limit reached for authenticated user {user_id}")
            emit('enhanced_error', {
                'code': 'USAGE_LIMIT_EXCEEDED',
                'message': error_msg,
                'usage': usage_info,
                'action': 'upgrade'
            })
            return
        
        # Check streaming permission for real-time features (server-verified user)
        can_stream, stream_reason = can_use_streaming(user_id)
        
        # Create enhanced buffer manager
        buffer_manager = buffer_registry.get_or_create_session(session_id)
        
        # Enhanced session configuration
        session_config = {
            'language': data.get('language', 'en'),
            'quality_mode': data.get('quality_mode', 'balanced'),  # high, balanced, fast
            'enable_real_time_processing': can_stream,  # Only Business tier
            'confidence_threshold': data.get('confidence_threshold', 0.7),
            'enable_context_awareness': data.get('enable_context_awareness', True),
            'audio_enhancement': data.get('audio_enhancement', True),
            'streaming_enabled': can_stream,
            'user_id': user_id
        }
        
        # Store enhanced session info
        enhanced_active_sessions[session_id] = {
            'client_sid': client_id,
            'started_at': datetime.utcnow(),
            'buffer_manager': buffer_manager,
            'config': session_config,
            'metrics': {
                'total_audio_processed': 0,
                'total_transcription_time': 0,
                'session_quality_score': 1.0
            }
        }
        
        # Start enhanced background processing worker
        worker = threading.Thread(
            target=_background_processor,
            args=(session_id, buffer_manager),
            daemon=True,
            name=f"EnhancedProcessor-{session_id[:8]}"
        )
        worker.start()
        
        # Join session room
        join_room(session_id)
        
        logger.info(f"🚀 Enhanced session started: {session_id} with config: {session_config}")
        
        emit('enhanced_session_started', {
            'session_id': session_id,
            'status': 'ready',
            'message': 'Enhanced transcription session started',
            'configuration': session_config,
            'capabilities': {
                'max_audio_length': enhanced_buffer_config.max_buffer_ms,
                'min_processing_interval': enhanced_buffer_config.min_flush_ms,
                'vad_enabled': enhanced_buffer_config.enable_vad,
                'quality_gating': enhanced_buffer_config.enable_quality_gating,
                'streaming_enabled': can_stream
            },
            'usage': {
                'hours_used': usage_info.get('hours_used', 0),
                'hours_limit': usage_info.get('hours_limit', 5),
                'percent_used': usage_info.get('percent_used', 0),
                'tier': usage_info.get('tier', 'free')
            },
            'streaming': {
                'enabled': can_stream,
                'reason': stream_reason
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Enhanced session start failed: {e}")
        emit('enhanced_error', {'message': f'Failed to start enhanced session: {str(e)}'})

@socketio.on('enhanced_audio_data', namespace='/transcription')
def on_enhanced_audio_data(data):
    """Enhanced audio data handler with comprehensive processing"""
    try:
        # Find active session for this client
        session_id = None
        for sid, session_info in enhanced_active_sessions.items():
            if session_info.get('client_sid') == flask_socketio.request.sid:
                session_id = sid
                break
        
        if not session_id:
            emit('enhanced_error', {'message': 'No enhanced session found'})
            return
        
        # Enhanced audio data processing
        audio_bytes, mime_type = _process_enhanced_audio_input(data)
        
        if not audio_bytes:
            return
        
        # Use advanced buffer manager
        session_info = enhanced_active_sessions[session_id]
        buffer_manager = session_info['buffer_manager']
        
        # Enhanced ingestion with quality monitoring
        success = buffer_manager.ingest_chunk(audio_bytes, mime_type)
        
        if not success:
            logger.warning(f"⚠️ Enhanced chunk ingestion failed for session {session_id}")
            
            # Check for backpressure and emit enhanced warning
            metrics = buffer_manager.get_metrics()
            if metrics['backpressure_events'] > 0:
                emit('enhanced_backpressure_warning', {
                    'message': 'Enhanced audio processing is experiencing backpressure',
                    'buffer_usage': f"{metrics['buffer_bytes']} bytes",
                    'dropped_chunks': metrics['chunks_dropped'],
                    'recommended_action': 'Reduce audio input rate or improve network connection',
                    'severity': 'warning' if metrics['chunks_dropped'] < 5 else 'critical'
                })
            return
        
        # Update session metrics
        session_info['metrics']['total_audio_processed'] += len(audio_bytes)
        
        # Emit periodic enhanced status
        if buffer_manager.metrics.chunks_received % 25 == 0:
            metrics = buffer_manager.get_metrics()
            emit('enhanced_ingestion_status', {
                'session_id': session_id,
                'chunks_processed': metrics['chunks_received'],
                'buffer_health': 'good' if metrics['buffer_bytes'] < 1024*1024 else 'warning',
                'processing_quality': session_info['metrics']['session_quality_score'],
                'audio_analysis': {
                    'speech_ratio': metrics.get('speech_ratio', 0.0),
                    'avg_confidence': 0.85,  # Would be calculated from recent results
                    'format_detected': metrics.get('format_detected', 'webm')
                }
            })
        
    except Exception as e:
        logger.error(f"❌ Enhanced audio processing error: {e}")
        emit('enhanced_error', {'message': f'Enhanced audio processing failed: {str(e)}'})

def _process_enhanced_audio_input(data) -> tuple:
    """Process enhanced audio input with comprehensive format handling"""
    try:
        # Enhanced structured format handling
        if isinstance(data, dict):
            if 'audioData' in data:
                audio_bytes = base64.b64decode(data['audioData'])
                mime_type = data.get('mimeType', 'audio/webm')
                
                # Enhanced metadata extraction
                metadata = data.get('metadata', {})
                sample_rate = metadata.get('sampleRate', 48000)
                channels = metadata.get('channels', 1)
                
                logger.debug(f"🎵 Enhanced audio: {len(audio_bytes)}B, {mime_type}, {sample_rate}Hz, {channels}ch")
                
                return audio_bytes, mime_type
                
            elif 'data' in data:
                # Legacy format support
                audio_bytes = base64.b64decode(data['data'])
                return audio_bytes, data.get('mimeType', 'audio/webm')
                
        elif isinstance(data, str):
            # Base64 string format
            audio_bytes = base64.b64decode(data)
            return audio_bytes, 'audio/webm'
            
        elif isinstance(data, (bytes, bytearray)):
            # Raw bytes
            return bytes(data), 'audio/webm'
            
    except Exception as e:
        logger.error(f"❌ Enhanced audio input processing failed: {e}")
    
    return None, None

@socketio.on('disconnect', namespace='/transcription')
def on_enhanced_disconnect():
    """Enhanced disconnection handler with comprehensive cleanup"""
    client_id = flask_socketio.request.sid
    logger.info(f"🔌 Enhanced client disconnected: {client_id}")
    
    # Enhanced cleanup for this client
    sessions_to_remove = []
    for session_id, session_info in enhanced_active_sessions.items():
        if session_info.get('client_sid') == client_id:
            sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        # Comprehensive session cleanup
        if 'buffer_manager' in enhanced_active_sessions[session_id]:
            buffer_manager = enhanced_active_sessions[session_id]['buffer_manager']
            
            # Get final metrics before cleanup
            final_metrics = buffer_manager.get_metrics()
            logger.info(f"📊 Final session metrics for {session_id}: {final_metrics}")
            
            buffer_manager.end_session()
        
        # Release from buffer registry
        buffer_registry.release(session_id)
        enhanced_active_sessions.pop(session_id, None)
        
        logger.info(f"🧹 Enhanced session cleanup completed: {session_id}")

@socketio.on('end_enhanced_session', namespace='/transcription')
def on_end_enhanced_session(data=None):
    """Gracefully end an enhanced transcription session and trigger post-processing analysis"""
    try:
        client_id = flask_socketio.request.sid
        sessions_to_end = [
            sid for sid, s in enhanced_active_sessions.items() if s.get('client_sid') == client_id
        ]

        if not sessions_to_end:
            logger.warning(f"⚠️ No enhanced session found for client {client_id}")
            emit('enhanced_error', {'message': 'No enhanced session found to end'})
            return

        for session_id in sessions_to_end:
            session_info = enhanced_active_sessions.pop(session_id, None)
            buffer_manager = session_info.get('buffer_manager')
            logger.info(f"🧩 Ending enhanced session {session_id} for client {client_id}")

            # 🗂️ Persist final transcript
            final_transcript = None
            try:
                if buffer_manager:
                    final_transcript = buffer_manager.flush_and_finalize(session_id=session_id)
                    logger.info(f"📝 Final transcript stored for {session_id} ({len(final_transcript)} chars)")
                else:
                    logger.warning(f"⚠️ No buffer manager found for session {session_id}")
            except Exception as e:
                logger.error(f"❌ Error during final transcript flush for {session_id}: {e}")

            # 🚀 Trigger downstream analysis asynchronously
            try:
                meeting_id = session_info.get("meeting_id", str(uuid.uuid4()))
                asyncio.create_task(
                    AnalysisDispatcher.run_full_analysis(
                        session_id=session_id,
                        meeting_id=meeting_id
                    )
                )
                logger.info(f"🚀 Dispatched background analytics for {session_id} ({meeting_id})")
            except Exception as e:
                logger.error(f"❌ Failed to dispatch analysis for {session_id}: {e}")

            # 🧹 Clean up buffer manager and release resources
            try:
                if buffer_manager:
                    buffer_manager.end_session()
                buffer_registry.release(session_id)
            except Exception as e:
                logger.warning(f"⚠️ Cleanup warning for session {session_id}: {e}")

            # ✅ Emit completion event
            emit('enhanced_session_ended', {
                'session_id': session_id,
                'status': 'completed',
                'message': 'Enhanced transcription completed. Analysis started in background.'
            })

    except Exception as e:
        logger.error(f"❌ Enhanced session end error: {e}")
        emit('enhanced_error', {'message': f'Failed to end enhanced session: {str(e)}'})

@socketio.on('get_enhanced_session_metrics', namespace='/transcription')
def on_get_enhanced_session_metrics(data=None):
    """Get comprehensive enhanced session metrics"""
    try:
        client_sessions = []
        for session_id, session_info in enhanced_active_sessions.items():
            if session_info.get('client_sid') == flask_socketio.request.sid:
                buffer_manager = session_info['buffer_manager']
                metrics = buffer_manager.get_metrics()
                
                # Add enhanced session metrics
                enhanced_metrics = {
                    **metrics,
                    'session_config': session_info['config'],
                    'session_metrics': session_info['metrics'],
                    'uptime_seconds': (datetime.utcnow() - session_info['started_at']).total_seconds()
                }
                
                client_sessions.append(enhanced_metrics)
        
        emit('enhanced_session_metrics', {
            'client_sessions': client_sessions,
            'total_enhanced_sessions': len(enhanced_active_sessions),
            'system_metrics': buffer_registry.get_all_metrics(),
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"❌ Enhanced metrics retrieval failed: {e}")
        emit('enhanced_error', {'message': f'Failed to get enhanced metrics: {str(e)}'})

logger.info("✅ Enhanced Transcription WebSocket handlers registered with comprehensive features")

def register_enhanced_websocket_handlers(socketio_instance):
    """Register enhanced websocket handlers with the provided socketio instance"""
    try:
        logger.info("🔧 Registering enhanced websocket handlers...")
        # The handlers are already registered via the @socketio.on decorators
        # This function provides compatibility for manual registration
        logger.info("✅ Enhanced websocket handlers registration completed")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to register enhanced websocket handlers: {e}")
        return False