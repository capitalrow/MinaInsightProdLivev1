"""
CRITICAL: Working Live Transcription API Implementation
This replaces all non-functional transcription endpoints with a WORKING solution
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from flask_socketio import emit
from werkzeug.utils import secure_filename
import os
import tempfile
import time
import logging
from datetime import datetime
from openai import OpenAI
import json

# Import socketio instance
from app import socketio
from services.subscription_service import subscription_service
from services import openai_whisper_client

logger = logging.getLogger(__name__)

# Create blueprint
live_transcription_bp = Blueprint('live_transcription_working', __name__)

# Initialize OpenAI client
try:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print(f"[LIVE-API] ✅ OpenAI client initialized successfully")
    else:
        openai_client = None
        print(f"[LIVE-API] ❌ OpenAI API key not found")
except Exception as e:
    openai_client = None
    print(f"[LIVE-API] ❌ OpenAI initialization failed: {e}")

@live_transcription_bp.route('/api/transcribe_chunk_streaming', methods=['POST', 'GET', 'OPTIONS'])
@login_required
def transcribe_chunk_streaming():
    """
    CRITICAL: The main transcription endpoint that actually works
    Processes audio chunks and returns real transcription results
    
    TIER GATING:
    - Free/Pro: Only process final chunks (is_final=true), queue others
    - Business: Process all chunks with live streaming
    """
    
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        return jsonify({'message': 'CORS preflight successful'}), 200
    
    # Check user's tier for live streaming access
    has_live = subscription_service.has_live_transcription(current_user.id)
    tier = subscription_service.get_user_tier(current_user.id)
    
    # Handle GET request for testing
    if request.method == 'GET':
        return jsonify({
            'message': 'Transcription streaming endpoint is operational',
            'methods': ['POST', 'GET', 'OPTIONS'],
            'openai_configured': openai_client is not None,
            'endpoint': '/api/transcribe_chunk_streaming',
            'status': 'ready',
            'tier': tier,
            'live_streaming_enabled': has_live
        })
    
    start_time = time.time()
    
    # Initialize variables early to avoid LSP errors
    chunk_id = '1'
    session_id = f'session_{int(time.time())}'
    
    # Set usage tracking context for cost monitoring
    openai_whisper_client.set_tracking_context(
        user_id=str(current_user.id),
        session_id=session_id
    )
    
    try:
        print(f"[LIVE-API] 🎵 Received transcription request")
        
        # Get form data
        audio_file = request.files.get('audio')
        session_id = request.form.get('session_id', session_id)
        chunk_id = request.form.get('chunk_id', chunk_id)
        is_final = request.form.get('is_final', 'false').lower() == 'true'
        
        # TIER GATING: Non-Business users only get final transcription
        if not has_live and not is_final:
            logger.info(f"[TIER] Non-Business user {current_user.id} (tier={tier}) - queueing chunk for final processing")
            return jsonify({
                'text': '',
                'confidence': 0,
                'processing_time': 0,
                'chunk_id': chunk_id,
                'session_id': session_id,
                'type': 'queued',
                'message': 'Live streaming requires Business plan. Audio queued for final transcription.',
                'tier': tier,
                'live_streaming_enabled': False
            })
        
        # Check if OpenAI is available
        if not openai_client:
            return jsonify({
                'error': 'OpenAI API not configured',
                'text': '',
                'confidence': 0,
                'processing_time': time.time() - start_time,
                'chunk_id': chunk_id,
                'type': 'error'
            }), 500
        
        print(f"[LIVE-API] 📊 Request details: audio_file={bool(audio_file)}, session_id={session_id}, chunk_id={chunk_id}")
        
        # Enhanced request logging
        if audio_file:
            print(f"[LIVE-API] 🎵 Audio file: {audio_file.filename}, size: {audio_file.content_length or 'unknown'}")
        
        # Log all form data for debugging
        print(f"[LIVE-API] 📋 Form data: {dict(request.form)}")
        print(f"[LIVE-API] 📂 Files: {list(request.files.keys())}")
        
        if not audio_file:
            return jsonify({
                'error': 'No audio file provided',
                'text': '',
                'confidence': 0,
                'processing_time': time.time() - start_time,
                'chunk_id': chunk_id,
                'type': 'error'
            }), 400
        
        print(f"[LIVE-API] 📁 Processing chunk {chunk_id}: {audio_file.filename} ({audio_file.content_length} bytes)")
        
        # Validate file size (minimum 1KB, maximum 25MB)
        if hasattr(audio_file, 'content_length') and audio_file.content_length:
            if audio_file.content_length < 1000:
                print(f"[LIVE-API] ⚠️ Chunk {chunk_id} too small: {audio_file.content_length} bytes")
                return jsonify({
                    'text': '',
                    'confidence': 0,
                    'processing_time': time.time() - start_time,
                    'chunk_id': chunk_id,
                    'type': 'partial',
                    'message': 'Audio chunk too small'
                })
            
            if audio_file.content_length > 25 * 1024 * 1024:  # 25MB limit
                return jsonify({
                    'error': 'Audio file too large (max 25MB)',
                    'text': '',
                    'confidence': 0,
                    'processing_time': time.time() - start_time,
                    'chunk_id': chunk_id,
                    'type': 'error'
                }), 413
        
        # PHASE 2: Optimize audio payload before API call
        original_audio_bytes = audio_file.read()
        audio_file.seek(0)
        
        try:
            from services.audio_payload_optimizer import optimize_for_whisper
            optimized_audio, opt_stats = optimize_for_whisper(original_audio_bytes)
            
            if opt_stats.get('skipped'):
                logger.debug(f"[LIVE-API] 🔇 Chunk {chunk_id} skipped (silence detected)")
                return jsonify({
                    'text': '',
                    'confidence': 0,
                    'processing_time': time.time() - start_time,
                    'chunk_id': chunk_id,
                    'type': 'silence',
                    'message': 'No speech detected in audio chunk'
                })
            
            if opt_stats.get('compression_ratio', 0) > 0:
                logger.info(f"[LIVE-API] 📉 Audio optimized: {opt_stats['compression_ratio']:.1f}% smaller")
            
            audio_to_process = optimized_audio if len(optimized_audio) > 0 else original_audio_bytes
        except Exception as opt_error:
            logger.warning(f"[LIVE-API] ⚠️ Audio optimization failed, using original: {opt_error}")
            audio_to_process = original_audio_bytes
        
        # Create temporary file for OpenAI processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            temp_file.write(audio_to_process)
            temp_file_path = temp_file.name
        
        try:
            # Call OpenAI Whisper API
            print(f"[LIVE-API] 🤖 Sending chunk {chunk_id} to OpenAI Whisper...")
            
            with open(temp_file_path, 'rb') as audio_data:
                transcription = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_data,
                    response_format="verbose_json",
                    language="en"  # Can be made dynamic
                )
            
            # Extract text and confidence
            text = transcription.text.strip() if transcription.text else ""
            
            # Calculate confidence from segments if available
            confidence = 0.0
            if hasattr(transcription, 'segments') and transcription.segments:
                confidences = []
                for segment in transcription.segments:
                    if hasattr(segment, 'avg_logprob'):
                        # Convert log probability to confidence (0-1)
                        conf = min(1.0, max(0.0, (segment.avg_logprob + 1.5) / 1.5))
                        confidences.append(conf)
                
                if confidences:
                    confidence = sum(confidences) / len(confidences)
                else:
                    confidence = 0.5 if text else 0.0
            else:
                confidence = 0.5 if text else 0.0
            
            processing_time = time.time() - start_time
            
            # PHASE 2: Track API usage for cost monitoring
            try:
                from services.usage_tracking_service import track_transcription
                
                # Get file size for tracking
                audio_file.seek(0, 2)  # Seek to end
                audio_size = audio_file.tell()
                audio_file.seek(0)  # Reset position
                
                track_transcription(
                    user_id=str(current_user.id),
                    audio_bytes=b'',  # We already processed it, use size instead
                    session_id=session_id,
                    transcription_type='final' if is_final else 'interim',
                    model_used='whisper-1',
                    api_latency_ms=int(processing_time * 1000),
                    was_cached=False,
                    error_occurred=False,
                    mime_type='audio/wav',
                    actual_duration=getattr(transcription, 'duration', None)
                )
                logger.debug(f"📊 Usage tracked for user {current_user.id}: {processing_time:.2f}s latency")
            except Exception as tracking_error:
                logger.warning(f"⚠️ Usage tracking failed (non-blocking): {tracking_error}")
            
            print(f"[LIVE-API] ✅ Chunk {chunk_id} transcribed successfully:")

            from services.transcription_service import TranscriptionService
            from app import socketio
            from flask_login import current_user

            transcription_service = TranscriptionService()
            
            # 🔒 CROWN¹⁰ Fix: Pass workspace_id and user_id for proper data scoping
            workspace_id = current_user.workspace_id if current_user.is_authenticated else None
            user_id = current_user.id if current_user.is_authenticated else None
            
            transcription_service._save_transcription_text(
                session_id, 
                text, 
                confidence,
                workspace_id=workspace_id,
                user_id=user_id
            )
            socketio.emit('update_dashboard', {'session_id': session_id, 'text': text})

            print(f"[LIVE-API]    Text: '{text[:100]}{'...' if len(text) > 100 else ''}'")
            print(f"[LIVE-API]    Confidence: {confidence:.3f}")
            print(f"[LIVE-API]    Processing time: {processing_time:.3f}s")
            
            # Prepare response
            response_data = {
                'text': text,
                'confidence': confidence,
                'processing_time': processing_time,
                'chunk_id': chunk_id,
                'session_id': session_id,
                'timestamp': datetime.utcnow().isoformat(),
                'type': 'success' if text else 'partial',
                'segments': []
            }
            
            # Add segment data if available
            if hasattr(transcription, 'segments') and transcription.segments:
                for segment in transcription.segments:
                    response_data['segments'].append({
                        'start': getattr(segment, 'start', 0),
                        'end': getattr(segment, 'end', 0),
                        'text': getattr(segment, 'text', ''),
                        'confidence': min(1.0, max(0.0, (getattr(segment, 'avg_logprob', -1) + 1.5) / 1.5))
                    })
            
            # Emit to WebSocket for real-time updates (if client connected)
            try:
                if text and confidence > 0.1:  # Only emit meaningful results
                    socketio.emit('transcription_result', response_data)
                    print(f"[LIVE-API] 📡 Emitted transcription result via WebSocket")
            except Exception as e:
                print(f"[LIVE-API] ⚠️ WebSocket emit failed: {e}")
            
            return jsonify(response_data)
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                print(f"[LIVE-API] ⚠️ Failed to delete temp file: {e}")
    
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = str(e)
        
        print(f"[LIVE-API] ❌ Transcription error for chunk {chunk_id}: {error_msg}")
        
        # PHASE 2: Track failed transcription for cost monitoring
        try:
            from services.usage_tracking_service import track_transcription
            track_transcription(
                user_id=str(current_user.id),
                audio_bytes=b'',
                session_id=session_id,
                transcription_type='final' if request.form.get('is_final', 'false').lower() == 'true' else 'interim',
                model_used='whisper-1',
                api_latency_ms=int(processing_time * 1000),
                was_cached=False,
                error_occurred=True,
                error_message=error_msg[:500],
                mime_type='audio/wav'
            )
        except Exception as tracking_error:
            logger.warning(f"⚠️ Error tracking failed: {tracking_error}")
        
        # Handle specific OpenAI errors
        if "rate_limit" in error_msg.lower():
            return jsonify({
                'error': 'Rate limit exceeded. Please wait a moment.',
                'text': '',
                'confidence': 0,
                'processing_time': processing_time,
                'chunk_id': chunk_id,
                'type': 'rate_limit'
            }), 429
        
        elif "quota" in error_msg.lower():
            return jsonify({
                'error': 'API quota exceeded. Please check your OpenAI account.',
                'text': '',
                'confidence': 0,
                'processing_time': processing_time,
                'chunk_id': chunk_id,
                'type': 'quota_exceeded'
            }), 402
        
        else:
            return jsonify({
                'error': f'Transcription failed: {error_msg}',
                'text': '',
                'confidence': 0,
                'processing_time': processing_time,
                'chunk_id': chunk_id,
                'type': 'error'
            }), 500

@live_transcription_bp.route('/api/transcription/optimization-stats', methods=['GET'])
@login_required
def transcription_optimization_stats():
    """Get audio optimization and VAD statistics (Phase 2)"""
    try:
        from services.audio_payload_optimizer import get_optimization_stats
        from services.voice_activity_detector import get_vad_stats
        
        opt_stats = get_optimization_stats()
        vad_stats = get_vad_stats()
        
        return jsonify({
            'success': True,
            'optimization': opt_stats,
            'vad': vad_stats,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@live_transcription_bp.route('/api/transcription/health', methods=['GET'])
def transcription_health():
    """Health check for transcription service"""
    try:
        health_data = {
            'status': 'healthy',
            'openai_configured': openai_client is not None,
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        }
        
        # Test OpenAI connection if available
        if openai_client:
            try:
                # Quick test - list models (doesn't count against quota)
                models = openai_client.models.list()
                health_data['openai_status'] = 'connected'
                health_data['available_models'] = [m.id for m in models.data if 'whisper' in m.id]
            except Exception as e:
                health_data['openai_status'] = f'error: {str(e)}'
        
        return jsonify(health_data)
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Tier status endpoint for frontend
@live_transcription_bp.route('/api/transcription/tier-status', methods=['GET'])
@login_required
def transcription_tier_status():
    """Check user's subscription tier and live streaming access"""
    from models.core_models import SubscriptionTier
    
    tier = subscription_service.get_user_tier(current_user.id)
    has_live = subscription_service.has_live_transcription(current_user.id)
    
    # Get tier config directly from SubscriptionTier.TIERS using the tier string
    tier_config = SubscriptionTier.TIERS.get(tier, SubscriptionTier.TIERS.get('free', {}))
    
    return jsonify({
        'tier': tier,
        'tier_name': tier_config.get('name', 'Free'),
        'has_live_transcription': has_live,
        'hours_per_month': tier_config.get('hours_per_month'),
        'features': tier_config.get('features', []),
        'upgrade_url': '/ui/billing' if not has_live else None
    })

# Test endpoint for debugging
@live_transcription_bp.route('/api/transcription/test', methods=['GET', 'POST'])
def transcription_test():
    """Test endpoint for debugging transcription issues"""
    if request.method == 'GET':
        return jsonify({
            'message': 'Transcription test endpoint is working',
            'openai_configured': openai_client is not None,
            'methods': ['GET', 'POST'],
            'timestamp': datetime.utcnow().isoformat()
        })
    
    else:  # POST
        return jsonify({
            'message': 'Test POST received',
            'form_data': dict(request.form),
            'files': list(request.files.keys()),
            'openai_ready': openai_client is not None
        })


# ============================================================================
# PHASE 2: Usage Tracking API Endpoints
# ============================================================================

@live_transcription_bp.route('/api/transcription/usage', methods=['GET'])
@login_required
def get_user_transcription_usage():
    """Get current user's transcription usage for the billing period."""
    try:
        from services.usage_tracking_service import get_user_usage, get_usage_alerts
        
        usage = get_user_usage(str(current_user.id))
        alerts = get_usage_alerts(str(current_user.id))
        
        return jsonify({
            'success': True,
            'usage': usage,
            'alerts': alerts
        })
    except Exception as e:
        logger.error(f"Failed to get usage: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@live_transcription_bp.route('/api/transcription/usage/check', methods=['GET'])
@login_required
def check_transcription_quota():
    """Check if user has remaining transcription quota."""
    try:
        from services.usage_tracking_service import check_usage_limit
        
        can_transcribe, usage_info = check_usage_limit(str(current_user.id))
        
        return jsonify({
            'success': True,
            'can_transcribe': can_transcribe,
            'usage': usage_info
        })
    except Exception as e:
        logger.error(f"Failed to check quota: {e}")
        return jsonify({
            'success': False,
            'can_transcribe': True,
            'error': str(e)
        }), 500


@live_transcription_bp.route('/api/admin/transcription/usage-stats', methods=['GET'])
@login_required
def get_admin_usage_stats():
    """Get aggregate usage statistics for admin dashboard."""
    try:
        if not getattr(current_user, 'is_admin', False):
            return jsonify({'error': 'Admin access required'}), 403
        
        from services.usage_tracking_service import get_admin_usage_stats
        
        stats = get_admin_usage_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Failed to get admin stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500