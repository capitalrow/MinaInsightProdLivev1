#!/usr/bin/env python3
"""
AI Proposals Verification Script
Direct verification of AI Proposals endpoint functionality.
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("=" * 60)
    print("AI PROPOSALS VERIFICATION")
    print("=" * 60)
    
    from app import app, db
    from models import User, Workspace, Meeting, Task
    from flask_login import login_user, FlaskLoginClient
    
    results = {
        'passed': 0,
        'failed': 0,
        'details': []
    }
    
    def log_result(test_name, passed, message):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        print(f"   {message}")
        results['details'].append({
            'test': test_name,
            'passed': passed,
            'message': message
        })
        if passed:
            results['passed'] += 1
        else:
            results['failed'] += 1
    
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['LOGIN_DISABLED'] = False
    app.test_client_class = FlaskLoginClient
    
    with app.app_context():
        user = db.session.query(User).first()
        workspace = db.session.query(Workspace).first()
    
    with app.test_client() as client:
        with app.app_context():
            print("\n📋 Test 1: Endpoint Exists")
            response = client.post(
                '/api/tasks/ai-proposals/stream',
                json={'max_proposals': 1}
            )
            log_result(
                "Endpoint Exists",
                response.status_code != 404,
                f"Status: {response.status_code}"
            )
            
            print("\n📋 Test 2: Authentication Required")
            log_result(
                "Auth Required",
                response.status_code in [401, 302, 403],
                f"Unauthenticated request returns {response.status_code}"
            )
    
    if user and workspace:
        print(f"\n🔐 Using test user: {user.email}")
        
        with app.test_client(user=user) as auth_client:
            with app.app_context():
                print("\n📋 Test 3: Authenticated SSE Stream")
                start_time = time.time()
                response = auth_client.post(
                    '/api/tasks/ai-proposals/stream',
                    json={'max_proposals': 2}
                )
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    content_type = response.content_type or ""
                    is_sse = 'text/event-stream' in content_type
                    log_result(
                        "SSE Stream",
                        is_sse,
                        f"Content-Type: {content_type}, Time: {elapsed*1000:.0f}ms"
                    )
                    
                    data = response.get_data(as_text=True)
                    
                    print("\n📋 Test 4: Valid SSE Events")
                    events = []
                    for line in data.split('\n'):
                        if line.startswith('data:'):
                            json_str = line[5:].strip()
                            if json_str and json_str != '[DONE]':
                                try:
                                    events.append(json.loads(json_str))
                                except:
                                    pass
                    
                    log_result(
                        "SSE Events",
                        len(events) > 0,
                        f"Received {len(events)} events"
                    )
                    
                    print("\n📋 Test 5: Event Types")
                    event_types = set(e.get('type', 'unknown') for e in events)
                    valid_types = {'start', 'proposal', 'chunk', 'progress', 'complete', 'error'}
                    invalid_types = event_types - valid_types
                    log_result(
                        "Event Types",
                        len(invalid_types) == 0,
                        f"Types: {event_types}"
                    )
                    
                    print("\n📋 Test 6: No Mock Data")
                    mock_indicators = ['mock', 'dummy', 'placeholder', 'lorem ipsum']
                    data_lower = data.lower()
                    found_mocks = [ind for ind in mock_indicators if ind in data_lower]
                    log_result(
                        "No Mock Data",
                        len(found_mocks) == 0,
                        f"Mock indicators found: {found_mocks}" if found_mocks else "Clean - no mocks"
                    )
                    
                    print("\n📋 Test 7: Response Time")
                    log_result(
                        "Response Time",
                        elapsed < 30.0,
                        f"Total time: {elapsed*1000:.0f}ms (limit: 30s)"
                    )
                    
                    proposals = [e for e in events if e.get('type') == 'proposal']
                    if proposals:
                        print("\n📝 Sample Proposals:")
                        for i, p in enumerate(proposals[:3]):
                            title = p.get('proposal', {}).get('title', 
                                   p.get('title', 'N/A'))
                            print(f"   {i+1}. {title[:60]}...")
                    
                else:
                    log_result(
                        "SSE Stream",
                        False,
                        f"Status {response.status_code}: {response.get_data(as_text=True)[:100]}"
                    )
                
                print("\n📋 Test 8: Meeting Context")
                meeting = db.session.query(Meeting).first()
                if meeting:
                    response = auth_client.post(
                        '/api/tasks/ai-proposals/stream',
                        json={'max_proposals': 1, 'meeting_id': meeting.id}
                    )
                    log_result(
                        "Meeting Context",
                        response.status_code == 200,
                        f"Meeting {meeting.id}: Status {response.status_code}"
                    )
                else:
                    log_result("Meeting Context", True, "Skipped - no meetings")
    else:
        log_result("Database Setup", False, "No user/workspace found")
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print("=" * 60)
    
    if results['failed'] == 0:
        print("\n🎉 ALL TESTS PASSED - AI Proposals verified working!")
        return 0
    else:
        print("\n⚠️ Some tests failed - review details above")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
