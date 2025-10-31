#!/usr/bin/env python3
"""
Debug script for analytics service
Tests the analytics snapshot generation to identify issues
"""

import os
import sys
from app import app, db
from models import User, Meeting, Task, Analytics, Participant
from services.analytics_cache_service import AnalyticsCacheService
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import traceback

def create_test_data():
    """Create test data for analytics"""
    with app.app_context():
        print("Creating test data...")
        
        # Check if test user exists
        user = db.session.query(User).filter_by(email='analytics_test@example.com').first()
        if not user:
            user = User(
                username='analytics_test',
                email='analytics_test@example.com',
                password_hash=generate_password_hash('test123'),
                workspace_id=1
            )
            db.session.add(user)
            db.session.commit()
            print(f"✅ Created test user: {user.id}")
        else:
            print(f"✅ User exists: {user.id}")
        
        # Check if test meetings exist
        meeting_count = db.session.query(Meeting).filter_by(workspace_id=1).count()
        print(f"📊 Existing meetings for workspace 1: {meeting_count}")
        
        if meeting_count < 5:
            # Create some test meetings
            for i in range(5):
                meeting = Meeting(
                    title=f'Test Meeting {i+1}',
                    workspace_id=1,
                    created_by_user_id=user.id,
                    status='completed',
                    actual_start=datetime.now() - timedelta(days=i, hours=1),
                    actual_end=datetime.now() - timedelta(days=i),
                    created_at=datetime.now() - timedelta(days=i)
                )
                db.session.add(meeting)
            
            db.session.commit()
            print(f"✅ Created 5 test meetings")
        
        # Create some test tasks
        meetings = db.session.query(Meeting).filter_by(workspace_id=1).limit(3).all()
        for meeting in meetings:
            task_count = db.session.query(Task).filter_by(meeting_id=meeting.id).count()
            if task_count == 0:
                for i in range(3):
                    task = Task(
                        meeting_id=meeting.id,
                        title=f'Test Task {i+1} for Meeting {meeting.id}',
                        status='completed' if i % 2 == 0 else 'pending',
                        priority='high' if i == 0 else 'medium',
                        created_at=datetime.now() - timedelta(hours=i)
                    )
                    db.session.add(task)
        
        db.session.commit()
        print("✅ Created test tasks")
        
        # Summary
        final_meeting_count = db.session.query(Meeting).filter_by(workspace_id=1).count()
        final_task_count = db.session.query(Task).join(Meeting).filter(Meeting.workspace_id == 1).count()
        print(f"\n📊 Test Data Summary:")
        print(f"   Meetings: {final_meeting_count}")
        print(f"   Tasks: {final_task_count}")
        print(f"   Workspace ID: 1")

def test_analytics_service():
    """Test the analytics service snapshot generation"""
    with app.app_context():
        print("\n" + "="*60)
        print("Testing Analytics Cache Service")
        print("="*60 + "\n")
        
        try:
            # Test 1: Checksum generation
            print("Test 1: Checksum Generation")
            test_data = {'kpis': {'total_meetings': 100}}
            checksum = AnalyticsCacheService.generate_checksum(test_data)
            print(f"✅ Checksum: {checksum[:16]}... (length: {len(checksum)})")
            
            # Test 2: Get analytics snapshot
            print("\nTest 2: Get Analytics Snapshot")
            print("Fetching snapshot for workspace_id=1, days=30...")
            snapshot = AnalyticsCacheService.get_analytics_snapshot(workspace_id=1, days=30)
            
            if snapshot:
                print("✅ Snapshot generated successfully!")
                print(f"\nSnapshot structure:")
                print(f"  - workspace_id: {snapshot.get('workspace_id')}")
                print(f"  - days: {snapshot.get('days')}")
                print(f"  - timestamp: {snapshot.get('timestamp')}")
                
                if 'kpis' in snapshot:
                    print(f"\n  KPIs:")
                    for key, value in snapshot['kpis'].items():
                        print(f"    - {key}: {value}")
                
                if 'charts' in snapshot:
                    print(f"\n  Charts:")
                    for key, value in snapshot['charts'].items():
                        print(f"    - {key}: {len(value) if isinstance(value, list) else value}")
                
                if 'checksums' in snapshot:
                    print(f"\n  Checksums:")
                    for key, value in snapshot['checksums'].items():
                        print(f"    - {key}: {value[:16]}..." if value else f"    - {key}: None")
                
                print("\n✅ All tests passed!")
                return True
            else:
                print("❌ Snapshot is empty!")
                return False
                
        except Exception as e:
            print(f"\n❌ Error during analytics test:")
            print(f"   {type(e).__name__}: {str(e)}")
            print(f"\nFull traceback:")
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("Analytics Service Debugger")
    print("="*60 + "\n")
    
    # Step 1: Create test data
    try:
        create_test_data()
    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    # Step 2: Test analytics service
    try:
        success = test_analytics_service()
        if success:
            print("\n" + "="*60)
            print("✅ All tests completed successfully!")
            print("="*60)
            sys.exit(0)
        else:
            print("\n" + "="*60)
            print("❌ Tests failed - see errors above")
            print("="*60)
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)
