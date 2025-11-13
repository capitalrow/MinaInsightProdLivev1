#!/usr/bin/env python3
"""
CROWN⁴.5 Evidence-Based Validation
Tests ONLY what's actually implemented. No assumptions.
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = 'http://localhost:5000'

def test_01_login():
    """Test: Can we login with test user?"""
    print("\n1️⃣  Testing Login Endpoint...")
    
    session = requests.Session()
    
    # First, get the login page to get any CSRF token if needed
    session.get(f'{BASE_URL}/auth/login')
    
    # Now attempt login with correct field names
    response = session.post(
        f'{BASE_URL}/auth/login',
        data={
            'email_or_username': 'test@mina.ai',
            'password': 'TestPassword123!'
        },
        allow_redirects=False
    )
    
    if response.status_code in [200, 302]:
        print(f"✅ Login works (HTTP {response.status_code})")
        # Check if we got a session cookie
        if 'session' in session.cookies:
            print(f"✅ Session cookie received")
            return session
        else:
            print(f"⚠️  Login succeeded but no session cookie")
            return session
    else:
        print(f"❌ Login failed: HTTP {response.status_code}")
        return None

def test_02_tasks_page_loads(session):
    """Test: Can we load /dashboard/tasks?"""
    print("\n2️⃣  Testing Tasks Page Load...")
    
    if not session:
        print("⏭️  Skipped (no session)")
        return None
    
    start = time.time()
    response = session.get(f'{BASE_URL}/dashboard/tasks')
    latency_ms = (time.time() - start) * 1000
    
    if 'login' in response.url.lower():
        print(f"❌ Redirected to login (auth failed)")
        return None
    elif response.status_code == 200:
        print(f"✅ Tasks page loaded ({latency_ms:.1f}ms)")
        print(f"   Target: <200ms - {'PASS' if latency_ms < 200 else 'FAIL'}")
        return {
            'loaded': True,
            'latency_ms': latency_ms,
            'meets_target': latency_ms < 200
        }
    else:
        print(f"❌ Tasks page failed: HTTP {response.status_code}")
        return None

def test_03_tasks_api_list(session):
    """Test: Does GET /api/tasks work?"""
    print("\n3️⃣  Testing Tasks API List...")
    
    if not session:
        print("⏭️  Skipped (no session)")
        return None
    
    response = session.get(f'{BASE_URL}/api/tasks')
    
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"✅ Tasks API works")
            print(f"   Returned: {type(data)}")
            if isinstance(data, list):
                print(f"   Tasks count: {len(data)}")
            return {'works': True, 'data': data}
        except:
            print(f"⚠️  Tasks API returned non-JSON")
            return None
    elif response.status_code == 401:
        print(f"❌ Tasks API requires auth (HTTP 401)")
        return None
    elif response.status_code == 404:
        print(f"❌ Tasks API not found (HTTP 404)")
        return None
    else:
        print(f"❌ Tasks API failed: HTTP {response.status_code}")
        return None

def test_04_create_task(session):
    """Test: Can we create a task?"""
    print("\n4️⃣  Testing Task Creation...")
    
    if not session:
        print("⏭️  Skipped (no session)")
        return None
    
    payload = {
        'title': f'Test Task {int(time.time())}',
        'status': 'pending'
    }
    
    start = time.time()
    response = session.post(
        f'{BASE_URL}/api/tasks',
        json=payload,
        headers={'Content-Type': 'application/json'}
    )
    latency_ms = (time.time() - start) * 1000
    
    if response.status_code in [200, 201]:
        try:
            data = response.json()
            print(f"✅ Task created ({latency_ms:.1f}ms)")
            
            # Check for CROWN metadata (not assuming it exists)
            crown_fields = {
                '_crown_event_id': '_crown_event_id' in data,
                '_crown_checksum': '_crown_checksum' in data,
                '_crown_sequence_num': '_crown_sequence_num' in data
            }
            
            print(f"   CROWN metadata:")
            for field, exists in crown_fields.items():
                icon = "✅" if exists else "❌"
                print(f"     {icon} {field}: {exists}")
            
            return {
                'works': True,
                'latency_ms': latency_ms,
                'task_id': data.get('id'),
                'crown_metadata': crown_fields,
                'has_all_crown': all(crown_fields.values())
            }
        except:
            print(f"⚠️  Task created but response not JSON")
            return None
    elif response.status_code == 401:
        print(f"❌ Create requires auth (HTTP 401)")
        return None
    else:
        print(f"❌ Create failed: HTTP {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return None

def test_05_websocket_available():
    """Test: Is Socket.IO available?"""
    print("\n5️⃣  Testing Socket.IO Availability...")
    
    try:
        response = requests.get(f'{BASE_URL}/socket.io/')
        
        if response.status_code == 200:
            print(f"✅ Socket.IO server running")
            return {'available': True}
        else:
            print(f"⚠️  Socket.IO unexpected status: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Socket.IO error: {e}")
        return None

def test_06_event_sequencer_exists():
    """Test: Does EventSequencer have any API?"""
    print("\n6️⃣  Testing EventSequencer API...")
    
    # Try common patterns
    endpoints = [
        '/api/tasks/events',
        '/api/events',
        '/api/tasks/events/status'
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f'{BASE_URL}{endpoint}')
            if response.status_code != 404:
                print(f"✅ Found endpoint: {endpoint} (HTTP {response.status_code})")
                return {'endpoint': endpoint, 'status': response.status_code}
        except:
            pass
    
    print(f"⚠️  No EventSequencer API endpoints found")
    return None

def test_07_telemetry_exists():
    """Test: Does Telemetry API exist?"""
    print("\n7️⃣  Testing Telemetry API...")
    
    try:
        response = requests.get(f'{BASE_URL}/api/tasks/telemetry')
        
        if response.status_code == 200:
            print(f"✅ Telemetry API exists")
            try:
                data = response.json()
                print(f"   Response keys: {list(data.keys())}")
                return {'exists': True, 'data': data}
            except:
                return {'exists': True}
        elif response.status_code == 404:
            print(f"⚠️  Telemetry API not found (HTTP 404)")
            return None
        else:
            print(f"⚠️  Telemetry API status: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Telemetry error: {e}")
        return None

def run_validation():
    """Run all validation tests"""
    print("=" * 60)
    print("🎯 CROWN⁴.5 Evidence-Based Validation")
    print("=" * 60)
    print("Testing only what's actually implemented.")
    print("No assumptions. No speculation.")
    print("=" * 60)
    
    results = {}
    
    # Test login
    session = test_01_login()
    results['login'] = session is not None
    
    # Test tasks page
    results['tasks_page'] = test_02_tasks_page_loads(session)
    
    # Test tasks API
    results['tasks_api'] = test_03_tasks_api_list(session)
    
    # Test task creation
    results['task_creation'] = test_04_create_task(session)
    
    # Test WebSocket
    results['websocket'] = test_05_websocket_available()
    
    # Test EventSequencer
    results['event_sequencer'] = test_06_event_sequencer_exists()
    
    # Test Telemetry
    results['telemetry'] = test_07_telemetry_exists()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nTests Passed: {passed}/{total}")
    print("\nEvidence:")
    for test_name, result in results.items():
        icon = "✅" if result else "❌"
        print(f"  {icon} {test_name}")
    
    # Save results
    report_file = f'crown45_evidence_{int(time.time())}.json'
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {report_file}")
    print("=" * 60)

if __name__ == '__main__':
    run_validation()
