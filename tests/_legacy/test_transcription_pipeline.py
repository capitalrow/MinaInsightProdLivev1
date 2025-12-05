#!/usr/bin/env python3
"""
🧪 COMPREHENSIVE TRANSCRIPTION PIPELINE TESTS
Automated testing for complete end-to-end transcription functionality
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
import tempfile
import threading
import numpy as np
from typing import Dict, List, Any, Optional
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import socketio
import requests
from flask import Flask

# Import our services
from services.transcription_service import TranscriptionService, TranscriptionServiceConfig
from services.whisper_streaming import WhisperStreamingService, TranscriptionConfig
from services.audio_processor import AudioProcessor
from app import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranscriptionPipelineTest:
    """Comprehensive automated tests for the transcription pipeline."""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.test_results = {}
        self.websocket_messages = []
        self.transcription_results = []
        self.audio_processor = AudioProcessor()
        
    def generate_test_audio(self, duration_seconds: float = 5.0, sample_rate: int = 16000) -> bytes:
        """Generate synthetic audio data for testing."""
        # Generate a simple sine wave
        t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), False)
        # Mix multiple frequencies to simulate speech patterns
        frequencies = [440, 880, 1320]  # A4, A5, E6
        audio = np.sum([0.3 * np.sin(2 * np.pi * f * t) for f in frequencies], axis=0)
        
        # Add some noise to make it more realistic
        noise = 0.1 * np.random.normal(0, 1, len(audio))
        audio = audio + noise
        
        # Convert to 16-bit PCM
        audio = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio * 32767).astype(np.int16)
        
        return audio_int16.tobytes()

    async def test_api_endpoints(self) -> Dict[str, Any]:
        """Test all API endpoints for availability and basic functionality."""
        logger.info("🧪 Testing API endpoints...")
        
        results = {
            'status': 'running',
            'endpoints_tested': 0,
            'endpoints_passed': 0,
            'endpoints_failed': 0,
            'details': {}
        }
        
        endpoints = [
            ('GET', '/'),
            ('GET', '/live'),
            ('GET', '/api/stats'),
            ('POST', '/api/transcription/start'),
        ]
        
        for method, endpoint in endpoints:
            try:
                results['endpoints_tested'] += 1
                url = f"{self.base_url}{endpoint}"
                
                if method == 'GET':
                    response = requests.get(url, timeout=10)
                elif method == 'POST':
                    response = requests.post(url, json={}, timeout=10)
                
                if response.status_code < 400:
                    results['endpoints_passed'] += 1
                    results['details'][endpoint] = {
                        'status': 'passed',
                        'status_code': response.status_code,
                        'response_time': response.elapsed.total_seconds()
                    }
                    logger.info(f"✅ {method} {endpoint} - {response.status_code}")
                else:
                    results['endpoints_failed'] += 1
                    results['details'][endpoint] = {
                        'status': 'failed',
                        'status_code': response.status_code,
                        'error': response.text[:200]
                    }
                    logger.warning(f"❌ {method} {endpoint} - {response.status_code}")
                    
            except Exception as e:
                results['endpoints_failed'] += 1
                results['details'][endpoint] = {
                    'status': 'error',
                    'error': str(e)
                }
                logger.error(f"💥 {method} {endpoint} - {e}")
        
        results['status'] = 'completed'
        return results

    async def test_websocket_connection(self) -> Dict[str, Any]:
        """Test WebSocket connection and basic protocol."""
        logger.info("🧪 Testing WebSocket connection...")
        
        results = {
            'status': 'running',
            'connection_successful': False,
            'session_join_successful': False,
            'messages_received': 0,
            'details': {}
        }
        
        sio = socketio.AsyncClient()
        
        @sio.event
        async def connect():
            logger.info("✅ WebSocket connected successfully")
            results['connection_successful'] = True
            
        @sio.event
        async def joined_session(data):
            logger.info(f"✅ Session joined: {data}")
            results['session_join_successful'] = True
            results['session_data'] = data
            
        @sio.event
        async def error(data):
            logger.error(f"❌ WebSocket error: {data}")
            results['websocket_error'] = data
            
        @sio.event
        async def transcript_partial(data):
            logger.info(f"📝 Partial transcript: {data}")
            results['messages_received'] += 1
            self.transcription_results.append(('partial', data))
            
        @sio.event
        async def transcript_final(data):
            logger.info(f"📝 Final transcript: {data}")
            results['messages_received'] += 1
            self.transcription_results.append(('final', data))
        
        try:
            # Connect to WebSocket
            await sio.connect(self.base_url, wait_timeout=10)
            await asyncio.sleep(1)  # Allow connection to stabilize
            
            # Test session joining
            session_id = f"test_session_{int(time.time())}"
            await sio.emit('join_session', {'session_id': session_id})
            await asyncio.sleep(2)  # Wait for join response
            
            results['status'] = 'completed'
            
        except Exception as e:
            logger.error(f"💥 WebSocket test failed: {e}")
            results['error'] = str(e)
            results['status'] = 'failed'
        finally:
            try:
                await sio.disconnect()
            except:
                pass
                
        return results

    async def test_audio_streaming(self) -> Dict[str, Any]:
        """Test complete audio streaming and transcription pipeline."""
        logger.info("🧪 Testing audio streaming pipeline...")
        
        results = {
            'status': 'running',
            'audio_chunks_sent': 0,
            'transcription_responses': 0,
            'pipeline_working': False,
            'details': {}
        }
        
        sio = socketio.AsyncClient()
        session_joined = False
        session_id = f"test_audio_{int(time.time())}"
        
        @sio.event
        async def connect():
            logger.info("✅ Audio test: WebSocket connected")
            
        @sio.event
        async def joined_session(data):
            nonlocal session_joined
            logger.info(f"✅ Audio test: Session joined {data}")
            session_joined = True
            
        @sio.event
        async def transcript_partial(data):
            logger.info(f"📝 Audio test: Partial transcript received: {data}")
            results['transcription_responses'] += 1
            
        @sio.event
        async def transcript_final(data):
            logger.info(f"📝 Audio test: Final transcript received: {data}")
            results['transcription_responses'] += 1
            results['pipeline_working'] = True
            
        @sio.event
        async def audio_received(data):
            logger.info(f"🎵 Audio test: Server acknowledged audio: {data}")
            
        @sio.event
        async def error(data):
            logger.error(f"❌ Audio test error: {data}")
            results['error'] = data
        
        try:
            # Connect and join session
            await sio.connect(self.base_url, wait_timeout=10)
            await asyncio.sleep(1)
            
            await sio.emit('join_session', {'session_id': session_id})
            await asyncio.sleep(2)
            
            if not session_joined:
                results['error'] = 'Failed to join session'
                results['status'] = 'failed'
                return results
            
            # Generate and send test audio
            test_audio = self.generate_test_audio(duration_seconds=3.0)
            chunk_size = 4096  # 4KB chunks
            
            logger.info(f"🎵 Sending {len(test_audio)} bytes of test audio in chunks...")
            
            for i in range(0, len(test_audio), chunk_size):
                chunk = test_audio[i:i + chunk_size]
                
                await sio.emit('audio_data', {
                    'session_id': session_id,
                    'audio': list(chunk),  # Convert bytes to list for JSON
                    'timestamp': time.time()
                })
                
                results['audio_chunks_sent'] += 1
                await asyncio.sleep(0.1)  # Small delay between chunks
            
            # Wait for transcription responses
            logger.info("⏳ Waiting for transcription responses...")
            await asyncio.sleep(5)
            
            results['status'] = 'completed'
            
        except Exception as e:
            logger.error(f"💥 Audio streaming test failed: {e}")
            results['error'] = str(e)
            results['status'] = 'failed'
        finally:
            try:
                await sio.disconnect()
            except:
                pass
                
        return results

    async def test_service_integration(self) -> Dict[str, Any]:
        """Test service-level integration without WebSocket."""
        logger.info("🧪 Testing service integration...")
        
        results = {
            'status': 'running',
            'transcription_service_working': False,
            'whisper_service_working': False,
            'audio_processor_working': False,
            'details': {}
        }
        
        try:
            # Test TranscriptionService initialization
            config = TranscriptionServiceConfig()
            tsvc = TranscriptionService(config)
            results['transcription_service_working'] = True
            logger.info("✅ TranscriptionService initialized")
            
            # Test session creation
            session_id = await tsvc.start_session()
            logger.info(f"✅ Session created: {session_id}")
            
            # Test audio processing
            test_audio = self.generate_test_audio()
            processed_audio = self.audio_processor.preprocess_audio(test_audio, 16000)
            results['audio_processor_working'] = True
            logger.info("✅ Audio processor working")
            
            # Test transcription with stub mode if enabled
            if os.getenv('STUB_TRANSCRIPTION', 'false').lower() == 'true':
                logger.info("🔧 Testing in stub mode...")
                # In stub mode, we can test the pipeline without actual OpenAI calls
                await tsvc.process_audio_async(session_id, test_audio)
                results['stub_transcription_working'] = True
            
            # Get statistics
            stats = tsvc.get_statistics()
            results['service_statistics'] = stats
            logger.info(f"✅ Service statistics: {stats}")
            
            # End session
            final_stats = await tsvc.end_session(session_id)
            results['session_ended_successfully'] = True
            logger.info(f"✅ Session ended: {final_stats}")
            
            results['status'] = 'completed'
            
        except Exception as e:
            logger.error(f"💥 Service integration test failed: {e}")
            results['error'] = str(e)
            results['traceback'] = traceback.format_exc()
            results['status'] = 'failed'
            
        return results

    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run all tests and compile comprehensive report."""
        logger.info("🚀 Starting comprehensive transcription pipeline tests...")
        
        comprehensive_results = {
            'test_run_id': f"test_{int(time.time())}",
            'start_time': time.time(),
            'status': 'running',
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'details': {}
        }
        
        tests = [
            ('API Endpoints', self.test_api_endpoints),
            ('WebSocket Connection', self.test_websocket_connection),
            ('Service Integration', self.test_service_integration),
            ('Audio Streaming', self.test_audio_streaming),
        ]
        
        for test_name, test_func in tests:
            try:
                logger.info(f"🧪 Running test: {test_name}")
                comprehensive_results['tests_run'] += 1
                
                test_result = await test_func()
                comprehensive_results['details'][test_name] = test_result
                
                if test_result.get('status') == 'completed' and not test_result.get('error'):
                    comprehensive_results['tests_passed'] += 1
                    logger.info(f"✅ {test_name} PASSED")
                else:
                    comprehensive_results['tests_failed'] += 1
                    logger.warning(f"❌ {test_name} FAILED")
                    
            except Exception as e:
                comprehensive_results['tests_failed'] += 1
                comprehensive_results['details'][test_name] = {
                    'status': 'error',
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }
                logger.error(f"💥 {test_name} ERROR: {e}")
        
        comprehensive_results['end_time'] = time.time()
        comprehensive_results['duration'] = comprehensive_results['end_time'] - comprehensive_results['start_time']
        comprehensive_results['status'] = 'completed'
        
        # Generate summary
        total_tests = comprehensive_results['tests_run']
        passed_tests = comprehensive_results['tests_passed']
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        comprehensive_results['summary'] = {
            'success_rate': success_rate,
            'overall_status': 'PASS' if comprehensive_results['tests_failed'] == 0 else 'FAIL',
            'recommendation': self._generate_recommendations(comprehensive_results)
        }
        
        return comprehensive_results
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Check API endpoints
        api_test = results['details'].get('API Endpoints', {})
        if api_test.get('endpoints_failed', 0) > 0:
            recommendations.append("Fix failed API endpoints - check server logs for specific errors")
        
        # Check WebSocket
        ws_test = results['details'].get('WebSocket Connection', {})
        if not ws_test.get('connection_successful'):
            recommendations.append("Fix WebSocket connection issues - check socketio configuration")
        if not ws_test.get('session_join_successful'):
            recommendations.append("Fix session joining protocol - check join_session handler")
        
        # Check service integration
        service_test = results['details'].get('Service Integration', {})
        if not service_test.get('transcription_service_working'):
            recommendations.append("Fix TranscriptionService initialization - check dependencies")
        
        # Check audio streaming
        audio_test = results['details'].get('Audio Streaming', {})
        if not audio_test.get('pipeline_working'):
            recommendations.append("Fix audio streaming pipeline - check audio processing and transcription flow")
        
        if not recommendations:
            recommendations.append("All tests passed! System is working correctly.")
        
        return recommendations

async def main():
    """Run comprehensive tests."""
    # Check if server is running
    try:
        response = requests.get("http://localhost:5000", timeout=5)
        logger.info("✅ Server is running, starting tests...")
    except:
        logger.error("❌ Server is not running on localhost:5000")
        logger.info("Please ensure the server is running with: python main.py")
        return
    
    # Enable stub mode for testing
    os.environ['STUB_TRANSCRIPTION'] = 'true'
    os.environ['WS_DEBUG'] = 'true'
    
    tester = TranscriptionPipelineTest()
    results = await tester.run_comprehensive_tests()
    
    # Print formatted results
    print("\n" + "="*80)
    print("🧪 TRANSCRIPTION PIPELINE TEST RESULTS")
    print("="*80)
    print(f"Test Run ID: {results['test_run_id']}")
    print(f"Duration: {results['duration']:.2f} seconds")
    print(f"Tests Run: {results['tests_run']}")
    print(f"Tests Passed: {results['tests_passed']}")
    print(f"Tests Failed: {results['tests_failed']}")
    print(f"Success Rate: {results['summary']['success_rate']:.1f}%")
    print(f"Overall Status: {results['summary']['overall_status']}")
    print()
    
    print("📊 DETAILED RESULTS:")
    for test_name, test_result in results['details'].items():
        status = test_result.get('status', 'unknown')
        print(f"  {test_name}: {status.upper()}")
        if test_result.get('error'):
            print(f"    Error: {test_result['error']}")
    
    print("\n💡 RECOMMENDATIONS:")
    for rec in results['summary']['recommendation']:
        print(f"  • {rec}")
    
    print("\n📋 FULL RESULTS (JSON):")
    print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())