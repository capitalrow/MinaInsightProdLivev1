#!/usr/bin/env python3
"""
Browser Simulation E2E Test
Tests the WebAudio-based simulation system through UI automation
"""

import pytest
import asyncio
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import requests

class TestBrowserSimulation:
    """Browser-based E2E tests for audio file simulation"""
    
    @pytest.fixture
    def driver(self):
        """Setup Chrome driver with audio support"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--use-fake-ui-for-media-stream')
        chrome_options.add_argument('--use-fake-device-for-media-stream')
        chrome_options.add_argument('--autoplay-policy=no-user-gesture-required')
        
        driver = webdriver.Chrome(options=chrome_options)
        yield driver
        driver.quit()
    
    @pytest.fixture
    def server_url(self):
        return "http://localhost:5000"
    
    def test_browser_simulation_ui_integration(self, driver, server_url):
        """Test browser simulation via UI automation"""
        print("\n🎬 Browser Simulation UI Test")
        
        try:
            # Navigate to live page
            live_url = f"{server_url}/live"
            driver.get(live_url)
            print(f"   📄 Navigated to: {live_url}")
            
            # Wait for page to load
            wait = WebDriverWait(driver, 20)
            
            # Wait for WebSocket connection
            wait.until(EC.presence_of_element_located((By.ID, "wsStatus")))
            time.sleep(3)  # Allow WebSocket to stabilize
            
            # Check if simulate button exists
            simulate_btn = wait.until(EC.element_to_be_clickable((By.ID, "simulateFromFileBtn")))
            print("   ✅ Simulate button found and clickable")
            
            # Click simulate button
            driver.execute_script("arguments[0].click();", simulate_btn)
            print("   🎬 Clicked simulate button")
            
            # Wait for simulation to start (look for debug info)
            time.sleep(3)
            
            # Check for interim transcripts appearing (within 5 seconds)
            start_time = time.time()
            interim_found = False
            
            while time.time() - start_time < 10:  # Wait up to 10 seconds
                try:
                    # Look for interim transcript elements
                    interim_elements = driver.find_elements(By.CLASS_NAME, "interim-text")
                    if interim_elements and len(interim_elements) > 0:
                        interim_text = interim_elements[0].text
                        if interim_text.strip():
                            print(f"   📝 First interim found: '{interim_text[:50]}...'")
                            interim_found = True
                            break
                except Exception:
                    pass
                time.sleep(0.5)
            
            assert interim_found, "No interim transcripts appeared within 10 seconds"
            
            # Wait for more transcripts
            time.sleep(5)
            
            # Check for final transcripts
            final_elements = driver.find_elements(By.CLASS_NAME, "final-text")
            final_count = len(final_elements)
            print(f"   ✅ Final transcripts found: {final_count}")
            
            # Stop simulation
            simulate_btn = driver.find_element(By.ID, "simulateFromFileBtn")
            if "Stop" in simulate_btn.text:
                driver.execute_script("arguments[0].click();", simulate_btn)
                print("   ⏹️ Stopped simulation")
            
            print("   ✅ Browser simulation test PASSED!")
            
        except Exception as e:
            print(f"   ❌ Browser simulation test FAILED: {e}")
            # Take screenshot for debugging
            driver.save_screenshot("/tmp/browser_simulation_error.png")
            raise

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])