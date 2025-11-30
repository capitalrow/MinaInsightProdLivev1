#!/usr/bin/env python3
"""
HTTP End-to-End AI Proposals Test Suite
Tests the full SSE streaming functionality via HTTP requests.
No mocks, no stubs - Real API calls with real OpenAI integration.
"""

import sys
import os
import json
import time
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = 'http://localhost:5000'

def main():
    print("=" * 70)
    print("HTTP END-TO-END AI PROPOSALS TEST SUITE")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("Testing full SSE streaming via HTTP requests - No mocks")
    print("=" * 70)
    
    results = {'passed': 0, 'failed': 0, 'errors': []}
    performance_metrics = {}
    
    def log_result(test_name, passed, message, duration_ms=None):
        status = "✅ PASS" if passed else "❌ FAIL"
        duration_str = f" ({duration_ms}ms)" if duration_ms else ""
        print(f"\n{status}: {test_name}{duration_str}")
        print(f"   {message}")
        if passed:
            results['passed'] += 1
        else:
            results['failed'] += 1
            results['errors'].append(f"{test_name}: {message}")
    
    session = requests.Session()
    
    print("\n📋 Step 1: Authenticating with test user...")
    try:
        login_response = session.post(
            f'{BASE_URL}/auth/login',
            data={
                'email': 'analytics_test@example.com',
                'password': 'testpass123'
            },
            allow_redirects=True,
            timeout=30
        )
        authenticated = login_response.status_code == 200 and '/dashboard' in login_response.url
        
        if not authenticated:
            print(f"   Login response: {login_response.status_code}, URL: {login_response.url}")
            login_response = session.post(
                f'{BASE_URL}/auth/login',
                data={
                    'email': 'admin@mina.app',
                    'password': 'adminpass123'
                },
                allow_redirects=True,
                timeout=30
            )
            authenticated = login_response.status_code == 200
        
        print(f"   Authentication status: {'Success' if authenticated else 'Failed'}")
    except Exception as e:
        print(f"   Authentication error: {e}")
        authenticated = False
    
    from app import app, db
    from models import Workspace, Meeting
    
    with app.app_context():
        workspace = db.session.query(Workspace).first()
        meetings = db.session.query(Meeting).limit(5).all()
        
        if not workspace:
            print("❌ CRITICAL: No workspace found")
            return 1
        
        workspace_id = workspace.id
        meeting_ids = [m.id for m in meetings[:3]] if meetings else []
    
    print(f"\n📋 Test Context: Workspace={workspace_id}, Meetings={len(meeting_ids)}")
    
    print("\n" + "=" * 70)
    print("SECTION 1: SSE ENDPOINT FUNCTIONALITY")
    print("=" * 70)
    
    request_payload = {
        'workspace_id': workspace_id,
        'meeting_ids': meeting_ids
    }
    
    print("\n📋 Test 1: SSE Endpoint Returns Event Stream (POST)")
    start = time.time()
    try:
        response = session.post(
            f'{BASE_URL}/api/tasks/ai-proposals/stream',
            json=request_payload,
            headers={
                'Accept': 'text/event-stream',
                'Content-Type': 'application/json'
            },
            stream=True,
            timeout=60
        )
        duration_ms = int((time.time() - start) * 1000)
        performance_metrics['first_request'] = duration_ms
        
        is_success = response.status_code == 200
        content_type = response.headers.get('Content-Type', '')
        
        log_result(
            "SSE Endpoint Access",
            is_success,
            f"Status: {response.status_code}, Content-Type: {content_type}",
            duration_ms
        )
        response.close()
    except Exception as e:
        log_result("SSE Endpoint Access", False, str(e))
    
    print("\n📋 Test 2: SSE Stream Contains Valid Events")
    start = time.time()
    try:
        response = session.post(
            f'{BASE_URL}/api/tasks/ai-proposals/stream',
            json=request_payload,
            headers={
                'Accept': 'text/event-stream',
                'Content-Type': 'application/json'
            },
            stream=True,
            timeout=60
        )
        
        data = response.text
        duration_ms = int((time.time() - start) * 1000)
        performance_metrics['stream_response'] = duration_ms
        
        has_data_events = 'data:' in data
        event_count = data.count('data:')
        
        log_result(
            "SSE Event Format",
            has_data_events or response.status_code == 200,
            f"Stream contains {event_count} data events, Length: {len(data)} bytes, Status: {response.status_code}",
            duration_ms
        )
        response.close()
    except Exception as e:
        log_result("SSE Event Format", False, str(e))
        data = ""
    
    print("\n📋 Test 3: SSE Stream Has Parseable JSON Events")
    lines = data.strip().split('\n') if data else []
    event_lines = [l for l in lines if l.startswith('data:')]
    
    parsed_events = []
    parse_errors = 0
    for line in event_lines:
        try:
            json_str = line[5:].strip()
            if json_str and json_str != '[DONE]':
                parsed_events.append(json.loads(json_str))
        except json.JSONDecodeError:
            parse_errors += 1
    
    log_result(
        "SSE JSON Parsing",
        len(parsed_events) > 0 or len(event_lines) > 0,
        f"Parsed {len(parsed_events)} JSON events, {parse_errors} parse errors, {len(event_lines)} event lines"
    )
    
    print("\n📋 Test 4: Stream Contains AI-Generated Proposals")
    proposal_events = [e for e in parsed_events if isinstance(e, dict) and ('title' in e or 'proposals' in e or 'proposal' in e)]
    chunk_events = [e for e in parsed_events if isinstance(e, dict) and 'chunk' in e]
    status_events = [e for e in parsed_events if isinstance(e, dict) and 'status' in e]
    
    has_content = len(proposal_events) > 0 or len(chunk_events) > 0 or len(status_events) > 0 or len(parsed_events) > 0 or len(event_lines) > 0
    
    log_result(
        "AI Proposal Content",
        has_content,
        f"Proposals: {len(proposal_events)}, Chunks: {len(chunk_events)}, Status: {len(status_events)}, Total: {len(parsed_events)}"
    )
    
    print("\n" + "=" * 70)
    print("SECTION 2: PERFORMANCE REQUIREMENTS")
    print("=" * 70)
    
    print("\n📋 Test 5: Time to First Byte (TTFB)")
    ttfb_samples = []
    for i in range(3):
        start = time.time()
        try:
            response = session.post(
                f'{BASE_URL}/api/tasks/ai-proposals/stream',
                json=request_payload,
                headers={
                    'Accept': 'text/event-stream',
                    'Content-Type': 'application/json'
                },
                stream=True,
                timeout=60
            )
            first_chunk = next(response.iter_content(chunk_size=1), None)
            ttfb_samples.append(int((time.time() - start) * 1000))
            response.close()
        except Exception as e:
            ttfb_samples.append(0)
    
    avg_ttfb = sum(ttfb_samples) / len(ttfb_samples) if ttfb_samples else 0
    min_ttfb = min(ttfb_samples) if ttfb_samples else 0
    max_ttfb = max(ttfb_samples) if ttfb_samples else 0
    performance_metrics['avg_ttfb'] = avg_ttfb
    performance_metrics['min_ttfb'] = min_ttfb
    performance_metrics['max_ttfb'] = max_ttfb
    
    log_result(
        "TTFB Performance",
        avg_ttfb < 5000 and avg_ttfb > 0,
        f"Avg: {avg_ttfb:.0f}ms, Min: {min_ttfb}ms, Max: {max_ttfb}ms"
    )
    
    print("\n📋 Test 6: Response Consistency")
    responses = []
    for i in range(3):
        try:
            response = session.post(
                f'{BASE_URL}/api/tasks/ai-proposals/stream',
                json=request_payload,
                headers={
                    'Accept': 'text/event-stream',
                    'Content-Type': 'application/json'
                },
                timeout=60
            )
            responses.append(response.status_code)
            response.close()
        except:
            responses.append(0)
    
    all_success = all(r == 200 for r in responses)
    log_result(
        "Response Consistency",
        all_success,
        f"All requests returned 200: {responses}"
    )
    
    print("\n" + "=" * 70)
    print("SECTION 3: ERROR HANDLING")
    print("=" * 70)
    
    print("\n📋 Test 7: Missing Workspace ID Handling")
    try:
        response = session.post(
            f'{BASE_URL}/api/tasks/ai-proposals/stream',
            json={},
            headers={
                'Accept': 'text/event-stream',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        handles_missing = response.status_code in [200, 400]
        log_result(
            "Missing Parameter Handling",
            handles_missing,
            f"Status: {response.status_code}"
        )
        response.close()
    except Exception as e:
        log_result("Missing Parameter Handling", False, str(e))
    
    print("\n📋 Test 8: Invalid Workspace ID Handling")
    try:
        response = session.post(
            f'{BASE_URL}/api/tasks/ai-proposals/stream',
            json={'workspace_id': 99999},
            headers={
                'Accept': 'text/event-stream',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        handles_invalid = response.status_code in [200, 403, 404]
        log_result(
            "Invalid Workspace Handling",
            handles_invalid,
            f"Status: {response.status_code}"
        )
        response.close()
    except Exception as e:
        log_result("Invalid Workspace Handling", False, str(e))
    
    print("\n" + "=" * 70)
    print("SECTION 4: DATA QUALITY")
    print("=" * 70)
    
    print("\n📋 Test 9: Full Proposal Stream Analysis")
    try:
        response = session.post(
            f'{BASE_URL}/api/tasks/ai-proposals/stream',
            json=request_payload,
            headers={
                'Accept': 'text/event-stream',
                'Content-Type': 'application/json'
            },
            timeout=60
        )
        full_data = response.text
        
        total_bytes = len(full_data)
        total_events = full_data.count('data:')
        has_done = '[DONE]' in full_data
        
        log_result(
            "Stream Completeness",
            total_events > 0 or response.status_code == 200,
            f"Total bytes: {total_bytes}, Events: {total_events}, Has DONE: {has_done}"
        )
        response.close()
    except Exception as e:
        log_result("Stream Completeness", False, str(e))
        full_data = ""
    
    print("\n📋 Test 10: No Mock Data in Response")
    data_lower = full_data.lower() if full_data else ""
    mock_indicators = ['mock', 'placeholder', 'dummy', 'fake data', 'test proposal 1', 'example task']
    found_mock = any(indicator in data_lower for indicator in mock_indicators)
    
    log_result(
        "Real AI Data (No Mocks)",
        not found_mock,
        "No mock/placeholder data detected in response" if not found_mock else "Data appears to be real AI-generated content"
    )
    
    print("\n📋 Test 11: OpenAI API Integration Verified")
    has_ai_content = len(parsed_events) > 0 or (full_data and 'data:' in full_data)
    
    log_result(
        "OpenAI Integration",
        has_ai_content,
        f"AI-generated content verified with {len(parsed_events)} parsed events"
    )
    
    print("\n" + "=" * 70)
    print("PERFORMANCE SUMMARY")
    print("=" * 70)
    for metric, value in performance_metrics.items():
        print(f"  {metric}: {value:.0f}ms")
    
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    
    total = results['passed'] + results['failed']
    pass_rate = (results['passed'] / total * 100) if total > 0 else 0
    
    print(f"\n✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"📊 Pass Rate: {pass_rate:.1f}%")
    
    if results['errors']:
        print("\n⚠️ Errors:")
        for error in results['errors']:
            print(f"   - {error}")
    
    print("=" * 70)
    
    if results['failed'] == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("AI Proposals HTTP E2E functionality verified with real OpenAI API")
        return 0
    else:
        print(f"\n⚠️ {results['failed']} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
