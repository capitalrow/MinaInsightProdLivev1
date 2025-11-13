#!/usr/bin/env python3
"""
CROWN⁴.5 Flask Test Client Validation
Uses Flask's test_client for reliable in-process testing.
Bypasses CSRF naturally while testing actual application logic.
"""

import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Task

# Configure app for testing (disable CSRF)
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

def create_test_session():
    """Create authenticated test client session."""
    client = app.test_client()
    
    # Login with test user
    response = client.post('/auth/login', data={
        'email_or_username': 'test@mina.ai',
        'password': 'TestPassword123!'
    }, follow_redirects=False)
    
    return client, response

def test_01_authentication():
    """Test: Can we authenticate?"""
    print("\n1️⃣  Testing Authentication...")
    
    client, response = create_test_session()
    
    if response.status_code == 302 and '/dashboard' in response.location:
        print(f"✅ Login successful (redirects to dashboard)")
        return {'success': True, 'client': client}
    elif response.status_code == 200:
        print(f"⚠️  Login returned 200 (check for errors in response)")
        return {'success': False, 'client': client}
    else:
        print(f"❌ Login failed: HTTP {response.status_code}")
        return {'success': False, 'client': None}

def test_02_tasks_page(client):
    """Test: Can we load tasks page?"""
    print("\n2️⃣  Testing Tasks Page...")
    
    if not client:
        print("⏭️  Skipped (no authenticated client)")
        return None
    
    start = time.time()
    response = client.get('/dashboard/tasks')
    latency_ms = (time.time() - start) * 1000
    
    if response.status_code == 200:
        print(f"✅ Tasks page loaded")
        print(f"   Latency: {latency_ms:.1f}ms")
        print(f"   Target <200ms: {'✅ PASS' if latency_ms < 200 else '❌ FAIL'}")
        
        # Check for key HTML elements
        html = response.data.decode('utf-8')
        has_task_container = 'id="taskList"' in html or 'class="task-' in html
        has_websocket = 'websocket-manager.js' in html or 'socket.io' in html
        
        print(f"   Task container: {'✅' if has_task_container else '❌'}")
        print(f"   WebSocket client: {'✅' if has_websocket else '❌'}")
        
        return {
            'success': True,
            'latency_ms': latency_ms,
            'meets_200ms_target': latency_ms < 200,
            'has_task_container': has_task_container,
            'has_websocket': has_websocket
        }
    else:
        print(f"❌ Tasks page failed: HTTP {response.status_code}")
        return None

def test_03_tasks_api_list(client):
    """Test: Does tasks API return data?"""
    print("\n3️⃣  Testing Tasks API (GET /api/tasks)...")
    
    if not client:
        print("⏭️  Skipped (no authenticated client)")
        return None
    
    start = time.time()
    response = client.get('/api/tasks')
    latency_ms = (time.time() - start) * 1000
    
    if response.status_code == 200:
        try:
            data = json.loads(response.data)
            print(f"✅ Tasks API works")
            print(f"   Latency: {latency_ms:.1f}ms")
            print(f"   Type: {type(data).__name__}")
            print(f"   Count: {len(data) if isinstance(data, list) else 'N/A'}")
            
            # Check for CROWN metadata on first task if available
            crown_metadata = {}
            if isinstance(data, list) and len(data) > 0:
                first_task = data[0]
                crown_metadata = {
                    '_crown_event_id': '_crown_event_id' in first_task,
                    '_crown_checksum': '_crown_checksum' in first_task,
                    '_crown_sequence_num': '_crown_sequence_num' in first_task
                }
                print(f"   CROWN metadata (first task):")
                for field, exists in crown_metadata.items():
                    icon = "✅" if exists else "❌"
                    print(f"     {icon} {field}")
            
            return {
                'success': True,
                'latency_ms': latency_ms,
                'task_count': len(data) if isinstance(data, list) else 0,
                'crown_metadata': crown_metadata,
                'has_all_crown': all(crown_metadata.values()) if crown_metadata else False
            }
        except json.JSONDecodeError:
            print(f"⚠️  API returned non-JSON")
            return None
    else:
        print(f"❌ Tasks API failed: HTTP {response.status_code}")
        return None

def test_04_create_task(client):
    """Test: Can we create a task?"""
    print("\n4️⃣  Testing Task Creation (POST /api/tasks)...")
    
    if not client:
        print("⏭️  Skipped (no authenticated client)")
        return None
    
    payload = {
        'title': f'Test Task {int(time.time())}',
        'status': 'pending'
    }
    
    start = time.time()
    response = client.post(
        '/api/tasks',
        data=json.dumps(payload),
        content_type='application/json'
    )
    latency_ms = (time.time() - start) * 1000
    
    if response.status_code in [200, 201]:
        try:
            data = json.loads(response.data)
            print(f"✅ Task created")
            print(f"   Latency: {latency_ms:.1f}ms")
            print(f"   Task ID: {data.get('id', 'N/A')}")
            
            # Check for CROWN metadata
            crown_metadata = {
                '_crown_event_id': '_crown_event_id' in data,
                '_crown_checksum': '_crown_checksum' in data,
                '_crown_sequence_num': '_crown_sequence_num' in data
            }
            
            print(f"   CROWN metadata:")
            for field, exists in crown_metadata.items():
                icon = "✅" if exists else "❌"
                print(f"     {icon} {field}")
            
            return {
                'success': True,
                'latency_ms': latency_ms,
                'task_id': data.get('id'),
                'crown_metadata': crown_metadata,
                'has_all_crown': all(crown_metadata.values())
            }
        except json.JSONDecodeError:
            print(f"⚠️  Task created but response not JSON")
            return None
    else:
        print(f"❌ Create failed: HTTP {response.status_code}")
        try:
            error = response.data.decode('utf-8')
            print(f"   Error: {error[:200]}")
        except:
            pass
        return None

def test_05_update_task(client, task_id):
    """Test: Can we update a task?"""
    print("\n5️⃣  Testing Task Update (PUT /api/tasks/{id})...")
    
    if not client or not task_id:
        print("⏭️  Skipped (no authenticated client or task_id)")
        return None
    
    payload = {
        'title': f'Updated Task {int(time.time())}',
        'status': 'completed'
    }
    
    start = time.time()
    response = client.put(
        f'/api/tasks/{task_id}',
        data=json.dumps(payload),
        content_type='application/json'
    )
    latency_ms = (time.time() - start) * 1000
    
    if response.status_code == 200:
        try:
            data = json.loads(response.data)
            print(f"✅ Task updated")
            print(f"   Latency: {latency_ms:.1f}ms")
            print(f"   Target <50ms: {'✅ PASS' if latency_ms < 50 else '❌ FAIL'}")
            
            return {
                'success': True,
                'latency_ms': latency_ms,
                'meets_50ms_target': latency_ms < 50
            }
        except json.JSONDecodeError:
            print(f"⚠️  Task updated but response not JSON")
            return None
    else:
        print(f"❌ Update failed: HTTP {response.status_code}")
        return None

def test_06_subsystem_endpoints(client):
    """Test: Do subsystem API endpoints exist?"""
    print("\n6️⃣  Testing Subsystem Endpoints...")
    
    if not client:
        print("⏭️  Skipped (no authenticated client)")
        return None
    
    endpoints = {
        'EventSequencer': '/api/tasks/events',
        'Telemetry': '/api/tasks/telemetry',
        'PredictiveEngine': '/api/tasks/predict',
        'TemporalRecovery': '/api/tasks/events/recover',
        'LedgerCompactor': '/api/tasks/ledger/status'
    }
    
    results = {}
    for name, endpoint in endpoints.items():
        response = client.get(endpoint)
        exists = response.status_code != 404
        icon = "✅" if exists else "❌"
        status = response.status_code if exists else "NOT FOUND"
        print(f"   {icon} {name}: {status}")
        results[name] = {'exists': exists, 'status_code': response.status_code}
    
    return results

def test_07_database_models():
    """Test: Are database models correct?"""
    print("\n7️⃣  Testing Database Models...")
    
    with app.app_context():
        # Check Task model
        try:
            from models import Task, EventLedger
            
            # Check Task columns
            task_columns = [c.name for c in Task.__table__.columns]
            has_origin_hash = 'origin_hash' in task_columns
            has_workspace_id = 'workspace_id' in task_columns
            
            print(f"   Task model:")
            print(f"     {'✅' if has_origin_hash else '❌'} origin_hash (for deduplication)")
            print(f"     {'✅' if has_workspace_id else '❌'} workspace_id (for isolation)")
            
            # Check EventLedger
            try:
                ledger_columns = [c.name for c in EventLedger.__table__.columns]
                has_event_type = 'event_type' in ledger_columns
                has_sequence_num = 'sequence_num' in ledger_columns
                has_checksum = 'checksum' in ledger_columns
                
                print(f"   EventLedger model:")
                print(f"     {'✅' if has_event_type else '❌'} event_type")
                print(f"     {'✅' if has_sequence_num else '❌'} sequence_num")
                print(f"     {'✅' if has_checksum else '❌'} checksum")
                
                return {
                    'task_model': {
                        'origin_hash': has_origin_hash,
                        'workspace_id': has_workspace_id
                    },
                    'event_ledger': {
                        'event_type': has_event_type,
                        'sequence_num': has_sequence_num,
                        'checksum': has_checksum
                    }
                }
            except:
                print(f"   ⚠️  EventLedger model not found")
                return {
                    'task_model': {
                        'origin_hash': has_origin_hash,
                        'workspace_id': has_workspace_id
                    },
                    'event_ledger': None
                }
        except Exception as e:
            print(f"   ❌ Error checking models: {e}")
            return None

def run_validation():
    """Run complete validation suite."""
    print("=" * 70)
    print("🎯 CROWN⁴.5 Flask Test Client Validation")
    print("=" * 70)
    print("Using Flask test_client for reliable in-process testing")
    print("=" * 70)
    
    results = {}
    
    # Test 1: Authentication
    auth_result = test_01_authentication()
    results['authentication'] = auth_result
    client = auth_result.get('client') if auth_result else None
    
    if not auth_result.get('success'):
        print("\n❌ AUTHENTICATION FAILED - Cannot proceed with other tests")
        print("=" * 70)
        return results
    
    # Test 2: Tasks page
    results['tasks_page'] = test_02_tasks_page(client)
    
    # Test 3: Tasks API list
    results['tasks_api_list'] = test_03_tasks_api_list(client)
    
    # Test 4: Create task
    create_result = test_04_create_task(client)
    results['task_creation'] = create_result
    task_id = create_result.get('task_id') if create_result else None
    
    # Test 5: Update task
    results['task_update'] = test_05_update_task(client, task_id)
    
    # Test 6: Subsystem endpoints
    results['subsystems'] = test_06_subsystem_endpoints(client)
    
    # Test 7: Database models
    results['database_models'] = test_07_database_models()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 VALIDATION SUMMARY")
    print("=" * 70)
    
    # Calculate scores
    tests_run = 7
    
    # For subsystems, only count as pass if at least 50% endpoints work correctly (HTTP 200)
    subsystems_pass = False
    if results.get('subsystems'):
        working = sum(1 for s in results['subsystems'].values() if s.get('exists') and s.get('status_code') == 200)
        total = len(results['subsystems'])
        subsystems_pass = working >= (total / 2)
    
    tests_passed = sum([
        1 if results.get('authentication', {}).get('success') else 0,
        1 if results.get('tasks_page') and results['tasks_page'].get('success') else 0,
        1 if results.get('tasks_api_list') and results['tasks_api_list'].get('success') else 0,
        1 if results.get('task_creation') and results['task_creation'].get('success') else 0,
        1 if results.get('task_update') and results['task_update'].get('success') else 0,
        1 if subsystems_pass else 0,
        1 if results.get('database_models') else 0
    ])
    
    print(f"\n✅ Tests Passed: {tests_passed}/{tests_run}")
    
    # Performance summary
    print(f"\n⚡ Performance:")
    if results.get('tasks_page'):
        latency = results['tasks_page'].get('latency_ms', 0)
        target = "✅ PASS" if latency < 200 else "❌ FAIL"
        print(f"   First paint: {latency:.1f}ms (target <200ms) {target}")
    
    if results.get('task_update'):
        latency = results['task_update'].get('latency_ms', 0)
        target = "✅ PASS" if latency < 50 else "❌ FAIL"
        print(f"   Mutation: {latency:.1f}ms (target <50ms) {target}")
    
    # CROWN metadata summary
    print(f"\n👑 CROWN Metadata:")
    has_crown_on_list = results.get('tasks_api_list') and results['tasks_api_list'].get('has_all_crown', False)
    has_crown_on_create = results.get('task_creation') and results['task_creation'].get('has_all_crown', False)
    
    print(f"   List response: {'✅ Complete' if has_crown_on_list else '❌ Missing'}")
    print(f"   Create response: {'✅ Complete' if has_crown_on_create else '❌ Missing'}")
    
    # Subsystem summary
    print(f"\n🔧 Subsystems:")
    if results.get('subsystems'):
        for name, data in results['subsystems'].items():
            icon = "✅" if data.get('exists') else "❌"
            print(f"   {icon} {name}")
    
    # Save results
    report_file = f'crown45_flask_validation_{int(time.time())}.json'
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Full report: {report_file}")
    print("=" * 70)
    
    return results

if __name__ == '__main__':
    run_validation()
