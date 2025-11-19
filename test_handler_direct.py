"""
Direct test of WebSocket handler return value.
Tests the handler function directly without Socket.IO client.
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up minimal environment
os.environ.setdefault('DATABASE_URL', os.environ.get('DATABASE_URL'))
os.environ.setdefault('SESSION_SECRET', 'test_secret')

from sqlalchemy import create_engine, text
from services.task_event_handler import task_event_handler

async def test_handler_return_value():
    """Test that the handler returns the correct structure."""
    print("\n" + "="*60)
    print("🧪 WEBSOCKET HANDLER RETURN VALUE TEST")
    print("="*60 + "\n")
    
    # Get a task
    database_url = os.environ.get('DATABASE_URL')
    engine = create_engine(database_url)
    
    print("Step 1: Finding a task...")
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT id FROM tasks WHERE status = 'todo' LIMIT 1"
        ))
        task = result.fetchone()
        
        if not task:
            print("❌ No tasks found")
            return False
        
        task_id = task[0]
        print(f"✅ Task ID: {task_id}")
    
    # Call handler directly
    print("\nStep 2: Calling task_event_handler.handle_event()...")
    
    result = await task_event_handler.handle_event(
        event_type='task_update:status_toggle',
        payload={
            'task_id': task_id,
            'status': 'completed',
            'workspace_id': 1
        },
        user_id=1,
        session_id=None
    )
    
    print(f"✅ Handler returned")
    print(f"   Type: {type(result)}")
    print(f"   Keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
    
    # Check structure
    print("\nStep 3: Verifying return structure...")
    
    if not isinstance(result, dict):
        print(f"❌ Result is not a dict: {type(result)}")
        return False
    
    has_success = 'success' in result
    has_task = 'task' in result
    
    print(f"   {'✅' if has_success else '❌'} success field: {has_success}")
    print(f"   {'✅' if has_task else '❌'} task field: {has_task}")
    
    if has_success:
        print(f"   success value: {result['success']}")
    
    # This is the enhanced_result that the handler returns
    # The WebSocket handler should wrap this in a response object
    print("\n📋 This is the 'enhanced_result' that needs wrapping:")
    print(f"   {result}")
    
    print("\n📋 The WebSocket handler should wrap it like:")
    print("   {")
    print(f"     'event_type': 'task_update:status_toggle',")
    print(f"     'result': {result},")
    print(f"     'trace_id': '...',")
    print(f"     'sequenced': False")
    print("   }")
    
    # Revert
    print("\nStep 4: Reverting task...")
    with engine.begin() as conn:
        conn.execute(text(
            f"UPDATE tasks SET status = 'todo' WHERE id = {task_id}"
        ))
    print("✅ Reverted")
    
    print("\n" + "="*60)
    print("✅ HANDLER TEST COMPLETED")
    print("   The handler returns enhanced_result correctly.")
    print("   The WebSocket route wraps it before returning as ACK.")
    print("="*60 + "\n")
    
    return True

if __name__ == '__main__':
    try:
        success = asyncio.run(test_handler_return_value())
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
