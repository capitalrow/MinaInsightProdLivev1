"""
Load Test for Concurrent Transcription with ThreadPoolExecutor
Tests 15+ concurrent transcription requests to validate non-blocking async behavior
"""

import asyncio
import logging
import time
from typing import List, Dict, Any
from io import BytesIO
import wave

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_audio_file(duration_ms: int = 1000) -> BytesIO:
    """
    Create a test WAV audio file in memory.
    
    Args:
        duration_ms: Duration in milliseconds
        
    Returns:
        BytesIO object containing WAV audio
    """
    import numpy as np
    
    sample_rate = 16000
    duration_sec = duration_ms / 1000.0
    num_samples = int(sample_rate * duration_sec)
    
    # Generate simple sine wave audio
    frequency = 440.0  # A4 note
    t = np.linspace(0, duration_sec, num_samples, False)
    audio_data = np.sin(frequency * 2 * np.pi * t)
    
    # Convert to 16-bit PCM
    audio_data = (audio_data * 32767).astype(np.int16)
    
    # Create WAV file in memory
    wav_buffer = BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())
    
    wav_buffer.seek(0)
    wav_buffer.name = "test_audio.wav"  # Required by OpenAI API
    return wav_buffer


async def transcribe_single(manager, request_id: int, audio_file: BytesIO) -> Dict[str, Any]:
    """
    Execute a single transcription request.
    
    Args:
        manager: OpenAIClientManager instance
        request_id: Unique request identifier
        audio_file: Audio file to transcribe
        
    Returns:
        Dictionary with request results
    """
    start_time = time.perf_counter()
    
    try:
        logger.info(f"  Request {request_id}: Starting transcription...")
        result = await manager.transcribe_audio_async(audio_file, model="whisper-1")
        
        end_time = time.perf_counter()
        duration = (end_time - start_time) * 1000  # Convert to ms
        
        success = result is not None
        logger.info(f"  Request {request_id}: {'✅ SUCCESS' if success else '❌ FAILED'} ({duration:.0f}ms)")
        
        return {
            'request_id': request_id,
            'success': success,
            'duration_ms': duration,
            'text_length': len(result) if result else 0
        }
    except Exception as e:
        end_time = time.perf_counter()
        duration = (end_time - start_time) * 1000
        
        logger.error(f"  Request {request_id}: ❌ EXCEPTION ({duration:.0f}ms): {e}")
        
        return {
            'request_id': request_id,
            'success': False,
            'duration_ms': duration,
            'error': str(e)
        }


async def run_concurrent_load_test(num_requests: int = 15, audio_duration_ms: int = 1000):
    """
    Run concurrent transcription load test.
    
    Args:
        num_requests: Number of concurrent requests to send
        audio_duration_ms: Duration of test audio in milliseconds
    """
    from services.openai_client_manager import get_openai_client_manager
    
    logger.info("="*80)
    logger.info(f"CONCURRENT TRANSCRIPTION LOAD TEST")
    logger.info(f"Requests: {num_requests} concurrent | Audio Duration: {audio_duration_ms}ms")
    logger.info("="*80)
    
    # Get OpenAI client manager
    manager = get_openai_client_manager()
    
    # Check if client is available
    if not manager.is_available():
        logger.error("❌ OpenAI client not available - cannot run load test")
        logger.error(f"Error: {manager.get_initialization_error()}")
        return
    
    # Get initial executor stats
    initial_stats = manager.get_executor_stats()
    logger.info(f"\n📊 Initial Executor Stats:")
    logger.info(f"  Max Workers: {initial_stats['max_workers']}")
    logger.info(f"  Active Tasks: {initial_stats['active_tasks']}")
    logger.info(f"  Total Submitted: {initial_stats['total_submitted']}")
    logger.info(f"  Total Completed: {initial_stats['total_completed']}")
    logger.info(f"  Total Failed: {initial_stats['total_failed']}")
    
    # Create test audio files
    logger.info(f"\n🎵 Creating {num_requests} test audio files...")
    audio_files = [create_test_audio_file(audio_duration_ms) for _ in range(num_requests)]
    logger.info(f"✅ Test audio files created")
    
    # Launch all concurrent requests
    logger.info(f"\n🚀 Launching {num_requests} concurrent transcription requests...")
    start_time = time.perf_counter()
    
    tasks = [
        transcribe_single(manager, i+1, audio_files[i])
        for i in range(num_requests)
    ]
    
    # Wait for all requests to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.perf_counter()
    total_duration = (end_time - start_time) * 1000
    
    # Analyze results
    logger.info("\n" + "="*80)
    logger.info("LOAD TEST RESULTS")
    logger.info("="*80)
    
    successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
    failed_results = [r for r in results if isinstance(r, dict) and not r.get('success')]
    exception_results = [r for r in results if not isinstance(r, dict)]
    
    logger.info(f"\n📈 Summary:")
    logger.info(f"  Total Requests: {num_requests}")
    logger.info(f"  Successful: {len(successful_results)}")
    logger.info(f"  Failed: {len(failed_results)}")
    logger.info(f"  Exceptions: {len(exception_results)}")
    logger.info(f"  Success Rate: {(len(successful_results) / num_requests * 100):.1f}%")
    logger.info(f"  Total Duration: {total_duration:.0f}ms")
    
    if successful_results:
        durations = [r['duration_ms'] for r in successful_results]
        durations.sort()
        
        logger.info(f"\n⏱️  Latency Statistics (successful requests):")
        logger.info(f"  Min: {min(durations):.0f}ms")
        logger.info(f"  Max: {max(durations):.0f}ms")
        logger.info(f"  Mean: {sum(durations) / len(durations):.0f}ms")
        logger.info(f"  P50: {durations[len(durations)//2]:.0f}ms")
        logger.info(f"  P95: {durations[int(len(durations)*0.95)]:.0f}ms")
    
    # Get final executor stats
    final_stats = manager.get_executor_stats()
    logger.info(f"\n📊 Final Executor Stats:")
    logger.info(f"  Active Tasks: {final_stats['active_tasks']}")
    logger.info(f"  Total Submitted: {final_stats['total_submitted']} (+{final_stats['total_submitted'] - initial_stats['total_submitted']})")
    logger.info(f"  Total Completed: {final_stats['total_completed']} (+{final_stats['total_completed'] - initial_stats['total_completed']})")
    logger.info(f"  Total Failed: {final_stats['total_failed']} (+{final_stats['total_failed'] - initial_stats['total_failed']})")
    logger.info(f"  Success Rate: {final_stats['success_rate']*100:.1f}%")
    
    # Validation
    logger.info("\n" + "="*80)
    logger.info("VALIDATION")
    logger.info("="*80)
    
    validation_passed = True
    
    # Check 1: All requests completed
    if len(results) == num_requests:
        logger.info("✅ All requests completed")
    else:
        logger.error(f"❌ Missing results: expected {num_requests}, got {len(results)}")
        validation_passed = False
    
    # Check 2: Success rate > 80%
    success_rate = len(successful_results) / num_requests
    if success_rate >= 0.8:
        logger.info(f"✅ Success rate acceptable: {success_rate*100:.1f}% >= 80%")
    else:
        logger.error(f"❌ Success rate too low: {success_rate*100:.1f}% < 80%")
        validation_passed = False
    
    # Check 3: No active tasks remaining
    if final_stats['active_tasks'] == 0:
        logger.info("✅ No tasks leaked (active_tasks = 0)")
    else:
        logger.error(f"❌ Task leakage detected: {final_stats['active_tasks']} tasks still active")
        validation_passed = False
    
    # Check 4: Concurrent execution (total time should be << serial time)
    expected_serial_time = num_requests * 5000  # Assume ~5s per request serially
    if total_duration < expected_serial_time * 0.3:  # Should be < 30% of serial time
        logger.info(f"✅ Concurrent execution verified: {total_duration:.0f}ms << {expected_serial_time:.0f}ms")
    else:
        logger.warning(f"⚠️  Execution may not be truly concurrent: {total_duration:.0f}ms vs expected <{expected_serial_time*0.3:.0f}ms")
    
    if validation_passed:
        logger.info("\n🎉 LOAD TEST PASSED - Concurrent transcription working correctly!")
    else:
        logger.error("\n❌ LOAD TEST FAILED - Issues detected")
    
    return validation_passed


if __name__ == "__main__":
    # Run load test with 20 concurrent requests
    success = asyncio.run(run_concurrent_load_test(num_requests=20, audio_duration_ms=500))
    exit(0 if success else 1)
