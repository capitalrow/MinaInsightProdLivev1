"""
Unit Test for ThreadPoolExecutor Concurrent Transcription
Mocks OpenAI API calls to validate non-blocking async behavior without API costs
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO


def create_mock_audio():
    """Create a mock audio file."""
    audio = BytesIO(b"fake audio data")
    audio.name = "test.wav"
    audio.seek(0)
    return audio


@pytest.mark.asyncio
async def test_concurrent_transcription_with_executor():
    """
    Test that multiple concurrent transcriptions run in parallel without blocking.
    
    This test validates that:
    1. Multiple transcriptions can run concurrently
    2. Event loop remains responsive (total time < serial time)
    3. Executor statistics are tracked correctly
    4. No task leakage occurs
    """
    from services.openai_client_manager import OpenAIClientManager
    
    # Create a fresh manager instance for testing
    manager = OpenAIClientManager()
    
    # Mock the OpenAI API call to return after a simulated delay
    def mock_transcribe(*args, **kwargs):
        """Simulate OpenAI API call with 100ms delay."""
        time.sleep(0.1)  # Simulate network latency
        return "Mocked transcription result"
    
    # Patch the transcription method
    with patch.object(manager, '_transcribe_with_retry', side_effect=mock_transcribe):
        # Get initial stats
        initial_stats = manager.get_executor_stats()
        print(f"\n📊 Initial Stats: {initial_stats}")
        
        # Create 15 concurrent transcription tasks
        num_requests = 15
        audio_files = [create_mock_audio() for _ in range(num_requests)]
        
        print(f"\n🚀 Launching {num_requests} concurrent transcription requests...")
        start_time = time.perf_counter()
        
        # Launch all tasks concurrently
        tasks = [
            manager.transcribe_audio_async(audio_files[i], model="whisper-1")
            for i in range(num_requests)
        ]
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks)
        
        end_time = time.perf_counter()
        total_duration = (end_time - start_time) * 1000  # Convert to ms
        
        # Get final stats
        final_stats = manager.get_executor_stats()
        print(f"\n📊 Final Stats: {final_stats}")
        
        # Validate results
        print(f"\n✅ Results:")
        print(f"  Total Duration: {total_duration:.0f}ms")
        print(f"  Successful: {sum(1 for r in results if r is not None)}")
        print(f"  Failed: {sum(1 for r in results if r is None)}")
        
        # ASSERTIONS
        
        # 1. All requests should succeed
        assert all(r is not None for r in results), "Some transcriptions failed"
        print("✅ All transcriptions succeeded")
        
        # 2. Concurrent execution should be much faster than serial
        expected_serial_time = num_requests * 100  # 100ms per request
        assert total_duration < expected_serial_time * 0.5, \
            f"Execution not concurrent: {total_duration:.0f}ms >= {expected_serial_time*0.5:.0f}ms"
        print(f"✅ Concurrent execution verified: {total_duration:.0f}ms << {expected_serial_time:.0f}ms")
        
        # 3. No active tasks should remain
        assert final_stats['active_tasks'] == 0, \
            f"Task leakage detected: {final_stats['active_tasks']} tasks still active"
        print("✅ No task leakage (active_tasks = 0)")
        
        # 4. Stats should be tracked correctly
        tasks_submitted = final_stats['total_submitted'] - initial_stats['total_submitted']
        tasks_completed = final_stats['total_completed'] - initial_stats['total_completed']
        
        assert tasks_submitted == num_requests, \
            f"Incorrect submitted count: {tasks_submitted} != {num_requests}"
        assert tasks_completed == num_requests, \
            f"Incorrect completed count: {tasks_completed} != {num_requests}"
        print(f"✅ Executor stats tracked correctly ({tasks_submitted} submitted, {tasks_completed} completed)")
        
        # 5. Success rate should be 100%
        assert final_stats['success_rate'] >= 0.99, \
            f"Success rate too low: {final_stats['success_rate']*100:.1f}%"
        print(f"✅ Success rate: {final_stats['success_rate']*100:.1f}%")
    
    print("\n🎉 CONCURRENT TRANSCRIPTION TEST PASSED!")


@pytest.mark.asyncio
async def test_executor_handles_failures_gracefully():
    """
    Test that executor handles failures gracefully and tracks them correctly.
    """
    from services.openai_client_manager import OpenAIClientManager
    
    manager = OpenAIClientManager()
    
    # Mock API to fail every other request with a simple exception
    call_count = [0]
    def mock_transcribe_with_failures(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] % 2 == 0:
            raise Exception("Simulated API failure")
        return "Success"
    
    with patch.object(manager, '_transcribe_with_retry', side_effect=mock_transcribe_with_failures):
        initial_stats = manager.get_executor_stats()
        
        # Run 10 concurrent requests (5 should fail, 5 should succeed)
        num_requests = 10
        audio_files = [create_mock_audio() for _ in range(num_requests)]
        
        tasks = [
            manager.transcribe_audio_async(audio_files[i])
            for i in range(num_requests)
        ]
        
        results = await asyncio.gather(*tasks)
        
        final_stats = manager.get_executor_stats()
        
        # Count successes and failures
        successes = sum(1 for r in results if r is not None)
        failures = sum(1 for r in results if r is None)
        
        print(f"\n📊 Failure Handling Test:")
        print(f"  Successes: {successes}")
        print(f"  Failures: {failures}")
        print(f"  Stats - Completed: {final_stats['total_completed'] - initial_stats['total_completed']}")
        print(f"  Stats - Failed: {final_stats['total_failed'] - initial_stats['total_failed']}")
        
        # Assertions
        assert failures > 0, "Expected some failures"
        assert successes > 0, "Expected some successes"
        assert final_stats['active_tasks'] == 0, "Task leakage detected"
        
        print("✅ Executor handles failures gracefully")


if __name__ == "__main__":
    # Run tests
    print("="*80)
    print("THREADPOOLEXECUTOR CONCURRENT TRANSCRIPTION TESTS")
    print("="*80)
    
    asyncio.run(test_concurrent_transcription_with_executor())
    asyncio.run(test_executor_handles_failures_gracefully())
    
    print("\n" + "="*80)
    print("ALL TESTS PASSED ✅")
    print("="*80)
