"""
Automated test to verify checkbox persistence via WebSocket and database.
Tests the complete flow: WebSocket event → server acknowledgement → database persistence.
"""
import socketio
import time
import os
from sqlalchemy import create_engine, text

# Initialize Socket.IO client
sio = socketio.Client()

# Track test results
test_results = {
    'websocket_connection': False,
    'task_update_sent': False,
    'acknowledgement_received': False,
    'ack_has_correct_structure': False,
    'database_updated': False,
    'task_id': None,
    'original_status': None,
    'new_status': None,
    'ack_payload': None
}

@sio.on('connected', namespace='/tasks')
def on_connected(data):
    print(f"✅ Connected to /tasks namespace: {data}")
    test_results['websocket_connection'] = True

@sio.on('task_event_result', namespace='/tasks')
def on_task_event_result(data):
    print(f"📨 Received task_event_result: {data}")

def run_test():
    """Run automated checkbox persistence test."""
    print("\n" + "="*60)
    print("🧪 AUTOMATED CHECKBOX PERSISTENCE TEST")
    print("="*60 + "\n")
    
    # Step 1: Connect to database
    print("Step 1: Connecting to database...")
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    engine = create_engine(database_url)
    
    # Get a task to test with
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT id, title, status FROM tasks WHERE status = 'todo' LIMIT 1"
        ))
        task = result.fetchone()
        
        if not task:
            print("❌ No 'todo' tasks found to test with")
            return False
        
        test_results['task_id'] = task[0]
        test_results['original_status'] = task[2]
        print(f"✅ Found task to test: ID={task[0]}, Title='{task[1]}', Status='{task[2]}'")
    
    # Step 2: Connect to WebSocket
    print("\nStep 2: Connecting to WebSocket...")
    try:
        sio.connect('http://localhost:5000', namespaces=['/tasks'])
        time.sleep(1)  # Wait for connection
        
        if not test_results['websocket_connection']:
            print("❌ WebSocket connection failed")
            return False
        
    except Exception as e:
        print(f"❌ WebSocket connection error: {e}")
        return False
    
    # Step 3: Join workspace
    print("\nStep 3: Joining workspace...")
    sio.emit('join_workspace', {'workspace_id': 1}, namespace='/tasks')
    time.sleep(0.5)
    
    # Step 4: Send task update event (toggle status to completed)
    print(f"\nStep 4: Sending task_update event (toggle status for task {test_results['task_id']})...")
    
    event_data = {
        'event_type': 'task_update:status_toggle',
        'payload': {
            'task_id': test_results['task_id'],
            'status': 'completed',
            'user_id': 1,
            'workspace_id': 1
        },
        'trace_id': f'test_{int(time.time())}'
    }
    
    try:
        # Use emitWithAck equivalent - pass callback
        def ack_callback(ack_data):
            print(f"\n✅ Server acknowledged task update!")
            print(f"📦 Acknowledgement payload: {ack_data}")
            test_results['acknowledgement_received'] = True
            test_results['ack_payload'] = ack_data
            
            # Verify structure
            if isinstance(ack_data, dict):
                has_event_type = 'event_type' in ack_data
                has_result = 'result' in ack_data
                has_trace_id = 'trace_id' in ack_data
                has_sequenced = 'sequenced' in ack_data
                
                if has_event_type and has_result and has_trace_id and has_sequenced:
                    print("✅ Acknowledgement has correct wrapper structure!")
                    test_results['ack_has_correct_structure'] = True
                    
                    # Check if result.success is true
                    result = ack_data.get('result', {})
                    if result.get('success'):
                        print("✅ Task update reported as successful!")
                    else:
                        print(f"⚠️ Task update failed: {result.get('message', 'Unknown error')}")
                else:
                    print(f"❌ Acknowledgement missing expected fields:")
                    print(f"   - event_type: {has_event_type}")
                    print(f"   - result: {has_result}")
                    print(f"   - trace_id: {has_trace_id}")
                    print(f"   - sequenced: {has_sequenced}")
        
        sio.emit('task_event', event_data, callback=ack_callback, namespace='/tasks')
        test_results['task_update_sent'] = True
        
        # Wait for acknowledgement
        time.sleep(2)
        
    except Exception as e:
        print(f"❌ Error sending task update: {e}")
        return False
    
    # Step 5: Verify database was updated
    print(f"\nStep 5: Verifying database update...")
    
    with engine.connect() as conn:
        result = conn.execute(text(
            f"SELECT status FROM tasks WHERE id = {test_results['task_id']}"
        ))
        task = result.fetchone()
        
        if task:
            test_results['new_status'] = task[0]
            print(f"📊 Database status: '{task[0]}'")
            
            if task[0] == 'completed':
                print("✅ Database successfully updated to 'completed'!")
                test_results['database_updated'] = True
            else:
                print(f"❌ Database not updated. Expected 'completed', got '{task[0]}'")
        else:
            print("❌ Task not found in database")
    
    # Cleanup: Disconnect
    sio.disconnect()
    
    # Print results
    print("\n" + "="*60)
    print("📊 TEST RESULTS")
    print("="*60)
    
    for test_name, result in test_results.items():
        if test_name in ['task_id', 'original_status', 'new_status', 'ack_payload']:
            continue
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*60)
    
    all_passed = all([
        test_results['websocket_connection'],
        test_results['task_update_sent'],
        test_results['acknowledgement_received'],
        test_results['ack_has_correct_structure'],
        test_results['database_updated']
    ])
    
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    
    print("="*60 + "\n")
    
    return all_passed

if __name__ == '__main__':
    success = run_test()
    exit(0 if success else 1)
