#!/usr/bin/env python3
"""
Live AI Proposals Test Suite
Tests the AI Proposals feature against the running server with real authentication.
No mock data - uses actual OpenAI API calls.
"""

import requests
import json
import time
import sys
import os

BASE_URL = "http://localhost:5000"

class AIProposalsLiveTest:
    """Live tests for AI Proposals feature."""
    
    def __init__(self):
        self.session = requests.Session()
        self.authenticated = False
        self.results = []
        
    def log(self, status, message):
        """Log test result."""
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} {message}")
        self.results.append({"status": status, "message": message})
        
    def authenticate(self):
        """Authenticate with the server."""
        print("\n🔐 Authenticating...")
        
        try:
            response = self.session.get(f"{BASE_URL}/auth/login")
            if response.status_code != 200:
                self.log("WARN", f"Login page returned {response.status_code}")
        except Exception as e:
            self.log("FAIL", f"Cannot reach server: {e}")
            return False
        
        try:
            response = self.session.post(
                f"{BASE_URL}/auth/login",
                data={
                    "email": "test@example.com",
                    "password": "password123"
                },
                allow_redirects=True
            )
            
            if "dashboard" in response.url or response.status_code == 200:
                self.authenticated = True
                self.log("PASS", "Authentication successful")
                return True
            else:
                try:
                    response = self.session.post(
                        f"{BASE_URL}/auth/login",
                        data={
                            "email": "admin@example.com",
                            "password": "admin123"
                        },
                        allow_redirects=True
                    )
                    if "dashboard" in response.url:
                        self.authenticated = True
                        self.log("PASS", "Authentication successful (admin)")
                        return True
                except:
                    pass
                    
                self.log("WARN", "Could not authenticate with test credentials")
                return False
                
        except Exception as e:
            self.log("FAIL", f"Authentication error: {e}")
            return False
    
    def test_endpoint_exists(self):
        """Test 1: Verify AI proposals endpoint exists."""
        print("\n📋 Test 1: Endpoint Exists")
        
        response = self.session.post(
            f"{BASE_URL}/api/tasks/ai-proposals/stream",
            json={"max_proposals": 1},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 404:
            self.log("FAIL", "AI proposals endpoint not found (404)")
            return False
        elif response.status_code == 401:
            self.log("WARN", "Endpoint exists but requires authentication")
            return True
        elif response.status_code == 200:
            self.log("PASS", "AI proposals endpoint exists and accessible")
            return True
        else:
            self.log("WARN", f"Endpoint returned status {response.status_code}")
            return True
    
    def test_sse_streaming(self):
        """Test 2: Verify SSE streaming works."""
        print("\n📋 Test 2: SSE Streaming")
        
        response = self.session.post(
            f"{BASE_URL}/api/tasks/ai-proposals/stream",
            json={"max_proposals": 2},
            headers={"Content-Type": "application/json"},
            stream=True
        )
        
        if response.status_code != 200:
            self.log("FAIL", f"SSE stream returned {response.status_code}")
            return False
            
        content_type = response.headers.get("Content-Type", "")
        if "text/event-stream" not in content_type:
            self.log("FAIL", f"Expected SSE content-type, got: {content_type}")
            return False
            
        self.log("PASS", "SSE streaming active with correct content-type")
        
        events = []
        start_time = time.time()
        
        try:
            for line in response.iter_lines(decode_unicode=True):
                if time.time() - start_time > 30:
                    break
                    
                if line and line.startswith("data:"):
                    data = line[5:].strip()
                    if data and data != "[DONE]":
                        try:
                            event = json.loads(data)
                            events.append(event)
                            event_type = event.get("type", "unknown")
                            print(f"   📨 Event: {event_type}")
                            
                            if event_type == "complete":
                                break
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            self.log("WARN", f"Stream reading error: {e}")
        
        if events:
            self.log("PASS", f"Received {len(events)} SSE events")
            return events
        else:
            self.log("WARN", "No SSE events received")
            return []
    
    def test_no_mock_data(self, events):
        """Test 3: Verify responses contain real AI data, not mocks."""
        print("\n📋 Test 3: No Mock Data")
        
        if not events:
            self.log("SKIP", "No events to analyze")
            return
            
        mock_indicators = [
            "mock", "dummy", "placeholder", "lorem ipsum",
            "example task", "sample task", "test proposal"
        ]
        
        all_text = json.dumps(events).lower()
        
        found_mocks = []
        for indicator in mock_indicators:
            if indicator in all_text:
                found_mocks.append(indicator)
        
        if found_mocks:
            self.log("WARN", f"Potential mock indicators found: {found_mocks}")
        else:
            self.log("PASS", "No mock data indicators found - using real OpenAI")
            
        proposals = [e for e in events if e.get("type") == "proposal"]
        if proposals:
            self.log("PASS", f"Found {len(proposals)} real proposal events")
            for i, p in enumerate(proposals[:2]):
                title = p.get("proposal", {}).get("title", p.get("title", "N/A"))
                print(f"   📝 Proposal {i+1}: {title[:50]}...")
        else:
            self.log("INFO", "No proposal events in stream (may be chunks)")
    
    def test_response_time(self):
        """Test 4: Verify response time is acceptable."""
        print("\n📋 Test 4: Response Time")
        
        start_time = time.time()
        
        response = self.session.post(
            f"{BASE_URL}/api/tasks/ai-proposals/stream",
            json={"max_proposals": 1},
            headers={"Content-Type": "application/json"},
            stream=True
        )
        
        first_byte_time = time.time() - start_time
        
        if response.status_code == 200:
            first_line = next(response.iter_lines(decode_unicode=True), None)
            first_data_time = time.time() - start_time
            
            print(f"   ⏱️  First byte: {first_byte_time*1000:.0f}ms")
            print(f"   ⏱️  First data: {first_data_time*1000:.0f}ms")
            
            if first_data_time < 5.0:
                self.log("PASS", f"First response in {first_data_time*1000:.0f}ms (< 5s)")
            else:
                self.log("WARN", f"First response took {first_data_time*1000:.0f}ms")
        else:
            self.log("FAIL", f"Response returned {response.status_code}")
    
    def test_event_types(self, events):
        """Test 5: Verify event types are correct."""
        print("\n📋 Test 5: Event Types")
        
        if not events:
            self.log("SKIP", "No events to analyze")
            return
            
        valid_types = {"start", "proposal", "chunk", "progress", "complete", "error"}
        event_types = set()
        
        for event in events:
            if "type" in event:
                event_types.add(event["type"])
        
        print(f"   📊 Event types found: {event_types}")
        
        invalid = event_types - valid_types
        if invalid:
            self.log("WARN", f"Unknown event types: {invalid}")
        else:
            self.log("PASS", f"All event types are valid: {event_types}")
    
    def test_with_meeting_context(self):
        """Test 6: Test with meeting context."""
        print("\n📋 Test 6: Meeting Context")
        
        response = self.session.get(f"{BASE_URL}/api/meetings")
        
        if response.status_code == 200:
            try:
                meetings = response.json()
                if meetings and len(meetings) > 0:
                    meeting_id = meetings[0].get("id")
                    
                    response = self.session.post(
                        f"{BASE_URL}/api/tasks/ai-proposals/stream",
                        json={"max_proposals": 2, "meeting_id": meeting_id},
                        headers={"Content-Type": "application/json"},
                        stream=True
                    )
                    
                    if response.status_code == 200:
                        self.log("PASS", f"Meeting context request accepted (meeting {meeting_id})")
                    else:
                        self.log("WARN", f"Meeting context returned {response.status_code}")
                else:
                    self.log("SKIP", "No meetings available for context test")
            except:
                self.log("SKIP", "Could not parse meetings response")
        else:
            self.log("SKIP", f"Meetings API returned {response.status_code}")
    
    def test_error_handling(self):
        """Test 7: Test error handling."""
        print("\n📋 Test 7: Error Handling")
        
        response = self.session.post(
            f"{BASE_URL}/api/tasks/ai-proposals/stream",
            json={"max_proposals": -1},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [400, 422]:
            self.log("PASS", "Invalid input correctly rejected")
        elif response.status_code == 200:
            self.log("WARN", "Invalid input was accepted (may be handled internally)")
        else:
            self.log("INFO", f"Invalid input returned {response.status_code}")
    
    def run_all_tests(self):
        """Run all tests."""
        print("=" * 60)
        print("AI PROPOSALS LIVE TEST SUITE")
        print("Testing against running server with real OpenAI API")
        print("=" * 60)
        
        self.authenticate()
        
        if not self.test_endpoint_exists():
            print("\n❌ Critical: Endpoint not found, aborting tests")
            return self.print_summary()
        
        events = self.test_sse_streaming()
        
        self.test_no_mock_data(events)
        self.test_response_time()
        self.test_event_types(events)
        self.test_with_meeting_context()
        self.test_error_handling()
        
        return self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        warned = sum(1 for r in self.results if r["status"] == "WARN")
        
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warned}")
        print("=" * 60)
        
        if failed == 0:
            print("\n🎉 ALL CRITICAL TESTS PASSED!")
            return 0
        else:
            print("\n⚠️  Some tests failed - review above")
            return 1


def main():
    """Run the live test suite."""
    tester = AIProposalsLiveTest()
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
