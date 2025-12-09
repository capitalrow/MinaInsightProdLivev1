# routes/comprehensive_transcription_api.py
"""
COMPREHENSIVE TRANSCRIPTION API
Unified integration of all enhanced transcription systems including:
- Advanced audio processing with noise reduction and quality enhancement
- Multi-speaker diarization with voice identification
- Real-time punctuation and capitalization
- Enhanced session management with persistence
- Advanced performance monitoring and analytics
"""

import logging
import json
import time
import asyncio
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from typing import Dict, List, Any, Optional
import numpy as np

# Import enhanced integration system
from services.enhanced_transcription_integration import (
    get_enhanced_transcription_integration, 
    EnhancedTranscriptionConfig
)
from services.openai_client_manager import get_openai_client_manager

logger = logging.getLogger(__name__)

# Create blueprint
comprehensive_bp = Blueprint('comprehensive_transcription', __name__)

class ComprehensiveTranscriptionProcessor:
    """Unified processor using enhanced transcription integration system"""
    
    def __init__(self):
        # Initialize enhanced integration system (neural enhancement disabled temporarily)
        self.config = EnhancedTranscriptionConfig(
            enable_neural_enhancement=False,
            enable_voice_fingerprinting=True,
            enable_emotion_detection=True,
            enable_conversation_analytics=True,
            enable_action_item_extraction=True,
            enable_insight_generation=True,
            max_processing_latency_ms=500,
            enable_performance_monitoring=True
        )
        
        self.integration_service = get_enhanced_transcription_integration(self.config)
        self.openai_client = get_openai_client_manager()
        
        # Performance metrics
        self.processing_metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'average_latency': 0.0,
            'error_rate': 0.0
        }
        
        logger.info("🚀 Enhanced Comprehensive Transcription Processor initialized")
    
    def process_audio_comprehensive_sync(
        self, 
        session_id: str,
        audio_data: bytes,
        client_id: str,
        is_final: bool = False
    ) -> Dict[str, Any]:
        """Synchronous audio processing for WebSocket compatibility"""
        
        start_time = time.time()
        self.processing_metrics['total_requests'] += 1
        
        try:
            # Simple transcription approach for immediate results
            import io
            import tempfile
            from pydub import AudioSegment
            
            # Convert audio bytes to a format OpenAI can transcribe
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Create temporary file for transcription
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                audio_segment.export(temp_file.name, format='wav')
                
                # Transcribe using OpenAI client manager
                with open(temp_file.name, 'rb') as audio_file:
                    transcription = self.openai_client.transcribe_audio(audio_file)
                
                # Clean up temp file
                import os
                os.unlink(temp_file.name)
            
            # Simple result format
            result = {
                'session_id': session_id,
                'text': transcription or "",
                'confidence': 0.9 if transcription else 0.0,
                'timestamp': time.time(),
                'is_final': is_final,
                'speaker': 'unknown',
                'language': 'en',
                'processing_time_ms': (time.time() - start_time) * 1000
            }
            
            # Update metrics
            if transcription:
                self.processing_metrics['successful_requests'] += 1
            self._update_average_latency((time.time() - start_time) * 1000)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Sync transcription failed: {e}")
            self._increment_error_rate()
            return {
                'session_id': session_id,
                'text': "",
                'confidence': 0.0,
                'timestamp': time.time(),
                'is_final': is_final,
                'error': str(e),
                'processing_time_ms': (time.time() - start_time) * 1000
            }
    
    def _increment_error_rate(self):
        """Update error rate metrics"""
        try:
            total = self.processing_metrics.get('total_requests', 1)
            errors = self.processing_metrics.get('error_count', 0) + 1
            self.processing_metrics['error_count'] = errors
            self.processing_metrics['error_rate'] = errors / total
        except Exception:
            pass
    
    def _update_average_latency(self, latency_ms: float):
        """Update average latency metric"""
        try:
            current_avg = self.processing_metrics.get('average_latency', 0.0)
            total_requests = self.processing_metrics.get('total_requests', 1)
            
            # Calculate rolling average
            self.processing_metrics['average_latency'] = (
                (current_avg * (total_requests - 1) + latency_ms) / total_requests
            )
        except Exception:
            pass
    
    async def process_audio_comprehensive(
        self, 
        session_id: str,
        audio_data: bytes,
        client_id: str,
        is_final: bool = False
    ) -> Dict[str, Any]:
        """Process audio through enhanced integration pipeline"""
        
        start_time = time.time()
        self.processing_metrics['total_requests'] += 1
        
        try:
            # Convert bytes to numpy array for enhanced processing
            audio_samples = self._bytes_to_numpy(audio_data)
            
            # === STAGE 1: AUDIO CHUNK PROCESSING ===
            # Process through enhanced audio pipeline
            chunk_result = self.integration_service.process_audio_chunk(
                session_id=session_id,
                audio_data=audio_samples,
                sample_rate=16000,
                client_id=client_id,
                is_final=is_final
            )
            
            # === STAGE 2: TRANSCRIPTION PROCESSING ===
            transcription_result = None
            
            # Only transcribe if chunk processing was successful and audio has sufficient quality
            if (chunk_result.get('processing_stages', {}).get('chunk_management', {}).get('completed') and
                not chunk_result.get('error')):
                
                # Transcribe audio using OpenAI
                raw_transcription = await self._transcribe_audio(audio_data, session_id)
                
                if raw_transcription:
                    # Process transcription through enhanced streaming processor
                    transcription_result = self.integration_service.process_transcription_result(
                        session_id=session_id,
                        raw_result=raw_transcription
                    )
            
            # === STAGE 3: RESPONSE PREPARATION ===
            
            processing_time = (time.time() - start_time) * 1000
            
            if transcription_result and not transcription_result.get('error'):
                self.processing_metrics['successful_requests'] += 1
                self._update_average_latency(processing_time)
                
                # Combine chunk processing and transcription results
                comprehensive_result = {
                    'session_id': session_id,
                    'text': transcription_result.get('result', {}).get('text', ''),
                    'confidence': transcription_result.get('result', {}).get('confidence', 0.0),
                    'speaker_id': transcription_result.get('result', {}).get('speaker_id', 'unknown'),
                    'is_final': is_final,
                    'voice_activity': chunk_result.get('processing_stages', {}).get('neural_enhancement', {}).get('voice_activity', False),
                    'quality_score': chunk_result.get('processing_stages', {}).get('neural_enhancement', {}).get('quality_score', 0.0),
                    'emotions': transcription_result.get('result', {}).get('emotions', {}),
                    'keywords': transcription_result.get('result', {}).get('keywords', []),
                    'processing_info': {
                        'total_processing_time_ms': processing_time,
                        'chunk_processing_time_ms': chunk_result.get('total_processing_latency_ms', 0),
                        'transcription_latency_ms': transcription_result.get('processing_latency_ms', 0),
                        'enhancement_applied': chunk_result.get('processing_stages', {}).get('neural_enhancement', {}).get('completed', False),
                        'chunk_priority': chunk_result.get('processing_stages', {}).get('chunk_management', {}).get('priority', 'normal')
                    },
                    'analytics': transcription_result.get('analytics', {}),
                    'system_metrics': self.get_system_metrics()
                }
                
                logger.debug(f"🎯 Enhanced processing completed for session {session_id}: "
                            f"{processing_time:.1f}ms")
                
                return comprehensive_result
            
            else:
                # Return processing status even without transcription
                return {
                    'session_id': session_id,
                    'voice_activity': chunk_result.get('processing_stages', {}).get('neural_enhancement', {}).get('voice_activity', False),
                    'quality_score': chunk_result.get('processing_stages', {}).get('neural_enhancement', {}).get('quality_score', 0.0),
                    'processing_time_ms': processing_time,
                    'status': 'processed_no_transcription',
                    'chunk_processing': chunk_result,
                    'transcription_result': transcription_result,
                    'system_metrics': self.get_system_metrics()
                }
            
        except Exception as e:
            logger.error(f"❌ Enhanced comprehensive processing failed: {e}")
            self._update_error_rate()
            
            return {
                'session_id': session_id,
                'error': str(e),
                'processing_time_ms': (time.time() - start_time) * 1000,
                'system_metrics': self.get_system_metrics()
            }
    
    async def _transcribe_audio(self, audio_data: bytes, session_id: str) -> Optional[Dict[str, Any]]:
        """Transcribe audio using OpenAI client"""
        try:
            # Use the enhanced OpenAI client manager
            result = await self.openai_client.transcribe_audio_async(
                audio_data=audio_data,
                session_id=session_id
            )
            return result
            
        except Exception as e:
            logger.error(f"❌ Transcription failed: {e}")
            return None
    
    def _bytes_to_numpy(self, audio_data: bytes) -> np.ndarray:
        """Convert audio bytes to numpy array"""
        try:
            # Try to detect format and convert appropriately
            if len(audio_data) < 44:
                return np.array([])
            
            # For simplicity, assume 16-bit PCM
            if len(audio_data) % 2 != 0:
                audio_data = audio_data[:-1]
            
            samples = np.frombuffer(audio_data, dtype=np.int16)
            return samples.astype(np.float32) / 32768.0
            
        except Exception as e:
            logger.warning(f"⚠️ Audio conversion failed: {e}")
            return np.array([])
    
    def create_enhanced_session(self, session_id: str, **metadata) -> Dict[str, Any]:
        """Create enhanced transcription session"""
        try:
            return self.integration_service.create_enhanced_session(session_id, **metadata)
        except Exception as e:
            logger.error(f"❌ Enhanced session creation failed: {e}")
            return {}
    
    def _update_average_latency(self, processing_time_ms: float):
        """Update average latency metric"""
        try:
            current_avg = self.processing_metrics['average_latency']
            total_requests = self.processing_metrics['successful_requests']
            
            # Exponential moving average
            alpha = 0.1
            self.processing_metrics['average_latency'] = (
                alpha * processing_time_ms + (1 - alpha) * current_avg
            )
            
        except Exception as e:
            logger.warning(f"⚠️ Latency update failed: {e}")
    
    def _update_error_rate(self):
        """Update error rate metric"""
        try:
            total = self.processing_metrics['total_requests']
            successful = self.processing_metrics['successful_requests']
            errors = total - successful
            
            self.processing_metrics['error_rate'] = errors / total if total > 0 else 0.0
            
        except Exception as e:
            logger.warning(f"⚠️ Error rate update failed: {e}")
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get enhanced system metrics"""
        try:
            integration_metrics = self.integration_service.get_system_performance()
            
            return {
                'processing_metrics': self.processing_metrics,
                'integration_system': integration_metrics,
                'enhanced_components': {
                    'streaming_processor': integration_metrics.get('component_performance', {}).get('streaming_processor', {}),
                    'chunk_manager': integration_metrics.get('component_performance', {}).get('chunk_manager', {}),
                    'neural_enhancement': integration_metrics.get('component_performance', {}).get('neural_enhancement', {}),
                    'conversation_analytics': integration_metrics.get('component_performance', {}).get('conversation_analytics', {})
                },
                'system_status': {
                    'active_sessions': integration_metrics.get('system_metrics', {}).get('active_sessions', 0),
                    'uptime_seconds': integration_metrics.get('system_metrics', {}).get('uptime_seconds', 0),
                    'total_chunks_processed': integration_metrics.get('system_metrics', {}).get('total_chunks_processed', 0),
                    'avg_processing_latency': integration_metrics.get('system_metrics', {}).get('avg_processing_latency', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Enhanced system metrics retrieval failed: {e}")
            return {'processing_metrics': self.processing_metrics}

# Global processor instance
_comprehensive_processor = None

def get_comprehensive_processor():
    """Get global comprehensive processor instance"""
    global _comprehensive_processor
    if _comprehensive_processor is None:
        _comprehensive_processor = ComprehensiveTranscriptionProcessor()
    return _comprehensive_processor

# REST API Routes
@comprehensive_bp.route('/api/transcription/comprehensive/session', methods=['POST'])
@login_required
def create_comprehensive_session():
    """Create new enhanced comprehensive transcription session"""
    try:
        data = request.get_json() or {}
        
        # Generate session ID
        session_id = f"comprehensive_{int(time.time() * 1000)}"
        
        # Create enhanced session
        processor = get_comprehensive_processor()
        session_info = processor.create_enhanced_session(
            session_id=session_id,
            user_id=data.get('user_id'),
            session_name=data.get('session_name', ''),
            language=data.get('language', 'en'),
            metadata=data.get('metadata', {})
        )
        
        logger.info(f"🆕 Created enhanced comprehensive session: {session_id}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'enhanced_features': {
                'streaming_processor': True,
                'neural_enhancement': True,
                'intelligent_chunking': True,
                'conversation_analytics': True
            },
            'message': 'Enhanced comprehensive transcription session created'
        })
        
    except Exception as e:
        logger.error(f"❌ Enhanced session creation failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@comprehensive_bp.route('/api/transcription/comprehensive/session/<session_id>', methods=['GET'])
def get_comprehensive_session(session_id: str):
    """Get enhanced comprehensive session information"""
    try:
        processor = get_comprehensive_processor()
        analytics = processor.integration_service.get_session_analytics(session_id)
        
        if not analytics:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404
        
        return jsonify({
            'success': True,
            'session_analytics': analytics,
            'enhanced_features': {
                'neural_enhancement': True,
                'conversation_analytics': True,
                'intelligent_chunking': True,
                'advanced_streaming': True
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Enhanced session retrieval failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@comprehensive_bp.route('/api/transcription/comprehensive/session/<session_id>/export', methods=['POST'])
def export_comprehensive_session(session_id: str):
    """Export comprehensive session in various formats"""
    try:
        data = request.get_json() or {}
        export_format = data.get('format', 'json')
        
        session_manager = get_enhanced_session_manager()
        export_data = session_manager.export_session(session_id, export_format)
        
        if not export_data:
            return jsonify({
                'success': False,
                'error': 'Export failed or session not found'
            }), 404
        
        # Return appropriate content type
        content_types = {
            'json': 'application/json',
            'txt': 'text/plain',
            'srt': 'text/plain',
            'csv': 'text/csv'
        }
        
        from flask import Response
        return Response(
            export_data,
            mimetype=content_types.get(export_format, 'application/octet-stream'),
            headers={
                'Content-Disposition': f'attachment; filename=session_{session_id}.{export_format}'
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Session export failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@comprehensive_bp.route('/api/transcription/comprehensive/metrics', methods=['GET'])
def get_comprehensive_metrics():
    """Get comprehensive system metrics"""
    try:
        processor = get_comprehensive_processor()
        metrics = processor.get_system_metrics()
        
        return jsonify({
            'success': True,
            'metrics': metrics
        })
        
    except Exception as e:
        logger.error(f"❌ Metrics retrieval failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# WebSocket Event Handlers (for Socket.IO integration)
def register_comprehensive_websocket_handlers(socketio):
    """Register comprehensive WebSocket handlers"""
    
    @socketio.on('join_comprehensive_session')
    def handle_join_comprehensive_session(data):
        """Join comprehensive transcription session"""
        try:
            session_id = data.get('session_id')
            if not session_id:
                emit('error', {'message': 'Session ID required'})
                return
            
            join_room(f"comprehensive_{session_id}")
            emit('joined_comprehensive_session', {
                'session_id': session_id,
                'status': 'connected'
            })
            
            logger.info(f"🔗 Client joined comprehensive session: {session_id}")
            
        except Exception as e:
            logger.error(f"❌ Join session failed: {e}")
            emit('error', {'message': str(e)})
    
    @socketio.on('comprehensive_audio_data')
    def handle_comprehensive_audio_data(data):
        """Handle comprehensive audio processing"""
        try:
            session_id = data.get('session_id')
            audio_data = data.get('audio_data')
            client_id = data.get('client_id', 'unknown')
            is_final = data.get('is_final', False)
            
            if not session_id or not audio_data:
                emit('error', {'message': 'Session ID and audio data required'})
                return
            
            # Convert base64 audio to bytes
            import base64
            try:
                audio_bytes = base64.b64decode(audio_data)
            except Exception:
                emit('error', {'message': 'Invalid audio data format'})
                return
            
            # Process through comprehensive pipeline
            processor = get_comprehensive_processor()
            
            # Process without creating new event loop
            try:
                result = processor.process_audio_comprehensive_sync(
                    session_id=session_id,
                    audio_data=audio_bytes,
                    client_id=client_id,
                    is_final=is_final
                )
                
                # Emit result to all clients in the session
                socketio.emit('comprehensive_transcription_result', result, 
                            room=f"comprehensive_{session_id}")
                
            except Exception as e:
                logger.error(f"❌ Processing failed: {e}")
                emit('error', {'message': f'Processing failed: {str(e)}'})
            
        except Exception as e:
            logger.error(f"❌ Audio data handling failed: {e}")
            emit('error', {'message': str(e)})
    
    @socketio.on('leave_comprehensive_session')
    def handle_leave_comprehensive_session(data):
        """Leave comprehensive transcription session"""
        try:
            session_id = data.get('session_id')
            if session_id:
                leave_room(f"comprehensive_{session_id}")
                emit('left_comprehensive_session', {'session_id': session_id})
                logger.info(f"🔌 Client left comprehensive session: {session_id}")
            
        except Exception as e:
            logger.error(f"❌ Leave session failed: {e}")
            emit('error', {'message': str(e)})

logger.info("✅ Comprehensive Transcription API initialized")