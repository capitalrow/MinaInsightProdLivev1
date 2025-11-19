"""
Test WebSocket acknowledgement structure using Flask-SocketIO test client.
Verifies that the acknowledgement has the correct wrapper structure.
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_socketio import SocketIOTestClient
from app import app, socketio
from sqlalchemy import create_engine, text
import json

def test_websocket_acknowledgement():
    """Test WebSocket acknowledgement structure."""
    print("\n" + "="*60)
    print("🧪 WEBSOCKET ACKNOWLEDGEMENT STRUCTURE TEST")
    print("="*60 + "\n")
    
    # Get a task to test
    database_url = os.environ.get('DATABASE_URL')
    engine = create_engine(database_url)
    
    print("Step 1: Finding a task to test...")
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT id, title, status FROM tasks WHERE status = 'todo' LIMIT 1"
        ))
        task = result.fetchone()
        
        if not task:
            print("❌ No 'todo' tasks found")
            return False
        
        task_id, title, original_status = task[0], task[1], task[2]
        print(f"✅ Found task: ID={task_id}")
        print(f"   Title: '{title[:50]}...'")
        print(f"   Original status: '{original_status}'")
    
    # Create Flask test client
    print("\nStep 2: Creating Flask-SocketIO test client...")
    with app.test_client() as http_client:
        # Create SocketIO test client
        sio_client = socketio.test_client(app, namespace='/tasks')
        
        if not sio_client.is_connected(namespace='/tasks'):
            print("❌ WebSocket client not connected")
            return False
        
        print("✅ WebSocket test client connected")
        
        # Join workspace
        print("\nStep 3: Joining workspace...")
        sio_client.emit('join_workspace', {'workspace_id': 1}, namespace='/tasks')
        
        # Get received events
        received = sio_client.get_received(namespace='/tasks')
        print(f"✅ Received {len(received)} events after join")
        for event in received:
            print(f"   - {event['name']}: {event['args']}")
        
        # Send task update event
        print(f"\nStep 4: Sending task_update event for task {task_id}...")
        
        event_data = {
            'event_type': 'task_update:status_toggle',
            'payload': {
                'task_id': task_id,
                'status': 'completed',
                'user_id': 1,
                'workspace_id': 1
            },
            'trace_id': 'test_trace_12345'
        }
        
        # Emit with callback to get acknowledgement
        ack_result = sio_client.emit('task_event', event_data, namespace='/tasks', callback=True)
        
        print(f"✅ Event sent")
        
        # Check acknowledgement
        print(f"\nStep 5: Verifying acknowledgement structure...")
        
        if ack_result is None:
            print("❌ No acknowledgement received")
            return False
        
        print(f"📦 Acknowledgement received:")
        print(f"   Type: {type(ack_result)}")
        print(f"   Content: {json.dumps(ack_result, indent=2) if isinstance(ack_result, dict) else ack_result}")
        
        # Verify structure
        if not isinstance(ack_result, dict):
            print(f"❌ Acknowledgement is not a dict: {type(ack_result)}")
            return False
        
        # Check for expected fields
        has_event_type = 'event_type' in ack_result
        has_result = 'result' in ack_result
        has_trace_id = 'trace_id' in ack_result
        has_sequenced = 'sequenced' in ack_result
        
        print("\n📋 Field validation:")
        print(f"   ✅ event_type: {has_event_type} = {ack_result.get('event_type')}" if has_event_type else "   ❌ event_type: missing")
        print(f"   ✅ result: {has_result}" if has_result else "   ❌ result: missing")
        print(f"   ✅ trace_id: {has_trace_id} = {ack_result.get('trace_id')}" if has_trace_id else "   ❌ trace_id: missing")
        print(f"   ✅ sequenced: {has_sequenced} = {ack_result.get('sequenced')}" if has_sequenced else "   ❌ sequenced: missing")
        
        if has_result:
            result_obj = ack_result.get('result', {})
            has_success = 'success' in result_obj
            print(f"   ✅ result.success: {has_success} = {result_obj.get('success')}" if has_success else "   ❌ result.success: missing")
        
        structure_ok = has_event_type and has_result and has_trace_id and has_sequenced
        
        if structure_ok:
            print("\n✅ Acknowledgement has correct wrapper structure!")
        else:
            print("\n❌ Acknowledgement missing expected fields")
            return False
        
        # Verify database update
        print(f"\nStep 6: Verifying database update...")
        with engine.connect() as conn:
            result = conn.execute(text(
                f"SELECT status FROM tasks WHERE id = {task_id}"
            ))
            task = result.fetchone()
            
            if task and task[0] == 'completed':
                print(f"✅ Database updated to 'completed'!")
                db_ok = True
            else:
                print(f"❌ Database not updated. Status = '{task[0] if task else 'NOT FOUND'}'")
                db_ok = False
        
        # Revert
        print(f"\nStep 7: Reverting task...")
        with engine.begin() as conn:
            conn.execute(text(
                f"UPDATE tasks SET status = '{original_status}' WHERE id = {task_id}"
            ))
        print("✅ Reverted")
        
        # Disconnect
        sio_client.disconnect(namespace='/tasks')
    
    # Results
    print("\n" + "="*60)
    if structure_ok and db_ok:
        print("🎉 ALL TESTS PASSED!")
        print("   ✅ Acknowledgement structure correct")
        print("   ✅ Database persistence working")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*60 + "\n")
    
    return structure_ok and db_ok

if __name__ == '__main__':
    try:
        success = test_websocket_acknowledgement()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
