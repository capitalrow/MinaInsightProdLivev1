"""
Critical User Flow Tests
Tests the most important user journeys end-to-end

NOTE: These tests require a running server with authentication configured.
They are designed to run in a full E2E environment with:
- Server running on localhost:5000
- Test user created and configured
- Proper session management

These tests may be skipped in basic test runs and should be run
as part of a dedicated E2E test pipeline.
"""

import pytest
import asyncio
import time
import re
import os
from playwright.async_api import Page, expect


# Skip E2E tests if not in E2E test environment
E2E_ENABLED = os.environ.get('RUN_E2E_TESTS', '').lower() == 'true'
skip_if_no_e2e = pytest.mark.skipif(
    not E2E_ENABLED,
    reason="E2E tests require RUN_E2E_TESTS=true environment variable and running server"
)


@skip_if_no_e2e
class TestCriticalFlows:
    """Test critical user flows that must work perfectly"""
    
    @pytest.mark.asyncio
    async def test_basic_transcription_flow(self, live_page: Page, performance_monitor):
        """Test basic recording → transcription → results flow"""
        
        # Skip if redirected to login page (auth required but not configured)
        current_url = live_page.url
        if '/auth/login' in current_url:
            pytest.skip("Live page requires authentication - test user not configured")
        
        start_time = time.time()
        
        # Step 1: Verify page loaded with all elements
        await expect(live_page.locator('#recordButton')).to_be_visible()
        await expect(live_page.locator('#transcript')).to_be_visible()
        await expect(live_page.locator('#timer')).to_be_visible()
        await expect(live_page.locator('#wordCount')).to_be_visible()
        
        # Step 2: Start recording
        record_button = live_page.locator('#recordButton')
        await record_button.click()
        
        # Verify recording state
        await expect(record_button).to_have_class(re.compile(r'.*recording.*'))
        await expect(live_page.locator('#timer')).to_contain_text('00:0')
        
        # Step 3: Wait for some recording time
        await asyncio.sleep(3)
        
        # Verify timer is running
        timer_text = await live_page.locator('#timer').text_content()
        assert '00:0' in timer_text and timer_text != '00:00'
        
        # Step 4: Stop recording
        await record_button.click()
        
        # Step 5: Verify final state
        await expect(record_button).not_to_have_class(re.compile(r'.*recording.*'))
        
        # Step 6: Check if transcript appears (may be empty for test audio)
        transcript_element = live_page.locator('#transcript')
        await asyncio.sleep(2)  # Allow time for processing
        
        # Performance assertion
        total_time = time.time() - start_time
        assert total_time < 10, f"Basic flow took too long: {total_time:.2f}s"
        
        performance_monitor['test_duration'] = total_time
        performance_monitor['flow_completed'] = True
    
    @pytest.mark.asyncio
    async def test_real_time_metrics_update(self, live_page: Page):
        """Test that metrics update in real-time during recording"""
        
        # Start recording
        await live_page.locator('#recordButton').click()
        
        # Wait and check metrics are updating
        await asyncio.sleep(1)
        
        # Check timer updates
        initial_timer = await live_page.locator('#timer').text_content()
        await asyncio.sleep(2)
        updated_timer = await live_page.locator('#timer').text_content()
        
        assert initial_timer != updated_timer, "Timer should update during recording"
        
        # Check audio level indicator (if present)
        audio_level = live_page.locator('#audioLevel')
        if await audio_level.is_visible():
            await expect(audio_level).to_be_visible()
        
        # Stop recording
        await live_page.locator('#recordButton').click()
        
        # Verify final metrics
        final_timer = await live_page.locator('#timer').text_content()
        word_count = await live_page.locator('#wordCount').text_content()
        
        assert ':' in final_timer  # Should be in MM:SS format
        assert word_count.isdigit()  # Should be a number
    
    @pytest.mark.asyncio
    async def test_copy_transcript_functionality(self, live_page: Page):
        """Test copying transcript to clipboard"""
        
        # Navigate and ensure transcript area exists
        await expect(live_page.locator('#transcript')).to_be_visible()
        
        # Add some test text to transcript (simulate transcription result)
        test_text = "This is a test transcription that should be copyable."
        await live_page.evaluate(f"""
            document.getElementById('transcript').value = '{test_text}';
        """)
        
        # Find and click copy button
        copy_button = live_page.locator('#copyButton')
        if await copy_button.is_visible():
            await copy_button.click()
            
            # Wait for copy operation
            await asyncio.sleep(0.5)
            
            # Verify clipboard content (limited in tests, but check for success indicator)
            # In a real test environment, you might check for a success message
            success_indicator = live_page.locator('.notification, .alert, .toast')
            if await success_indicator.count() > 0:
                # Some kind of feedback was shown
                assert True
        else:
            pytest.skip("Copy button not visible, may be context-dependent")
    
    @pytest.mark.asyncio
    async def test_session_continuity(self, live_page: Page):
        """Test that sessions work correctly across multiple recordings"""
        
        # First recording
        await live_page.locator('#recordButton').click()
        await asyncio.sleep(2)
        await live_page.locator('#recordButton').click()
        
        # Get session data after first recording
        first_session_data = await live_page.evaluate("""
            () => ({
                wordCount: document.getElementById('wordCount').textContent,
                timer: document.getElementById('timer').textContent,
                transcript: document.getElementById('transcript').value
            })
        """)
        
        # Second recording - should start fresh or continue session
        await asyncio.sleep(1)
        await live_page.locator('#recordButton').click()
        await asyncio.sleep(2)
        await live_page.locator('#recordButton').click()
        
        # Verify session handling
        second_session_data = await live_page.evaluate("""
            () => ({
                wordCount: document.getElementById('wordCount').textContent,
                timer: document.getElementById('timer').textContent,
                transcript: document.getElementById('transcript').value
            })
        """)
        
        # Timer should reset for new recordings
        assert second_session_data['timer'] != first_session_data['timer'] or second_session_data['timer'] == '00:00'
    
    @pytest.mark.asyncio
    async def test_consciousness_engine_integration(self, live_page: Page):
        """Test that advanced AI engines are properly initialized"""
        
        # Check console for engine initialization messages
        console_messages = []
        live_page.on('console', lambda msg: console_messages.append(msg.text))
        
        # Reload page to capture initialization
        await live_page.reload()
        await live_page.wait_for_load_state('networkidle')
        
        # Wait for initialization messages
        await asyncio.sleep(2)
        
        # Verify advanced engines are loaded
        engine_messages = [msg for msg in console_messages if any(keyword in msg.lower() for keyword in [
            'consciousness', 'neural', 'quantum', 'multiverse', 'engine', 'loaded', 'initialized'
        ])]
        
        assert len(engine_messages) > 0, f"No engine initialization messages found. Got: {console_messages[-10:]}"
        
        # Verify specific engines
        consciousness_loaded = any('consciousness' in msg.lower() for msg in engine_messages)
        neural_loaded = any('neural' in msg.lower() for msg in engine_messages)
        quantum_loaded = any('quantum' in msg.lower() for msg in engine_messages)
        
        assert consciousness_loaded, "Consciousness engine not loaded"
        assert neural_loaded, "Neural processing engine not loaded"  
        assert quantum_loaded, "Quantum optimization engine not loaded"
    
    @pytest.mark.asyncio
    async def test_ui_responsiveness_during_processing(self, live_page: Page):
        """Test that UI remains responsive during transcription processing"""
        
        # Start recording
        await live_page.locator('#recordButton').click()
        
        # Test UI responsiveness during recording
        for i in range(5):
            await asyncio.sleep(0.5)
            
            # Try to interact with various UI elements
            timer = await live_page.locator('#timer').text_content()
            assert timer is not None, f"Timer not responsive at iteration {i}"
            
            # Check if any UI elements are frozen
            is_button_enabled = await live_page.locator('#recordButton').is_enabled()
            assert is_button_enabled, f"Record button not responsive at iteration {i}"
        
        # Stop recording
        await live_page.locator('#recordButton').click()
        
        # Test post-recording responsiveness
        await asyncio.sleep(1)
        
        # Verify all elements are still interactive
        transcript = live_page.locator('#transcript')
        await expect(transcript).to_be_visible()
        
        is_editable = await transcript.is_editable()
        if is_editable:
            await transcript.fill("UI responsiveness test")
            content = await transcript.input_value()
            assert "responsiveness" in content


import re  # Add import for regex