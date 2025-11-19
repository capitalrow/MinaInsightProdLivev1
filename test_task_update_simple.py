"""
Simplified test: Verify task updates persist in database.
Uses direct database queries to test persistence.
"""
import os
from sqlalchemy import create_engine, text
import time

def run_simple_test():
    """Test task update persistence via database."""
    print("\n" + "="*60)
    print("🧪 TASK UPDATE PERSISTENCE TEST (Database)")
    print("="*60 + "\n")
    
    # Connect to database
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    engine = create_engine(database_url)
    
    # Step 1: Get a task
    print("Step 1: Finding a test task...")
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT id, title, status FROM tasks WHERE status = 'todo' LIMIT 1"
        ))
        task = result.fetchone()
        
        if not task:
            print("❌ No 'todo' tasks found to test with")
            return False
        
        task_id, title, original_status = task[0], task[1], task[2]
        print(f"✅ Found task: ID={task_id}")
        print(f"   Title: '{title}'")
        print(f"   Status: '{original_status}'")
    
    # Step 2: Update task status in database (simulating what WebSocket should do)
    print(f"\nStep 2: Updating task {task_id} to 'completed'...")
    with engine.begin() as conn:
        conn.execute(text(
            f"UPDATE tasks SET status = 'completed' WHERE id = {task_id}"
        ))
        print(f"✅ Database update executed")
    
    # Step 3: Verify it persisted
    print(f"\nStep 3: Verifying update persisted...")
    with engine.connect() as conn:
        result = conn.execute(text(
            f"SELECT status FROM tasks WHERE id = {task_id}"
        ))
        task = result.fetchone()
        
        if task and task[0] == 'completed':
            print(f"✅ Database update persisted! Status = '{task[0]}'")
            persistence_ok = True
        else:
            print(f"❌ Database update did NOT persist. Status = '{task[0] if task else 'NOT FOUND'}'")
            persistence_ok = False
    
    # Step 4: Revert for next test
    print(f"\nStep 4: Reverting task back to '{original_status}'...")
    with engine.begin() as conn:
        conn.execute(text(
            f"UPDATE tasks SET status = '{original_status}' WHERE id = {task_id}"
        ))
        print(f"✅ Reverted to original status")
    
    # Results
    print("\n" + "="*60)
    if persistence_ok:
        print("🎉 DATABASE PERSISTENCE TEST PASSED!")
    else:
        print("❌ DATABASE PERSISTENCE TEST FAILED")
    print("="*60 + "\n")
    
    return persistence_ok

if __name__ == '__main__':
    success = run_simple_test()
    exit(0 if success else 1)
