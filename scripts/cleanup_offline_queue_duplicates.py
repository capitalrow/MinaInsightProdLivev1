#!/usr/bin/env python3
"""
One-time cleanup script to remove duplicate offline_queue records.
Run this before applying the UNIQUE constraint to the database.

Usage:
    python scripts/cleanup_offline_queue_duplicates.py
"""

import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models.offline_queue import OfflineQueue
from sqlalchemy import func, select


def cleanup_duplicates():
    """Remove duplicate offline_queue records, keeping only the most recent."""
    
    with app.app_context():
        print("🔍 Scanning for duplicate offline_queue records...")
        
        # Find all (user_id, session_id) combinations that have duplicates
        stmt = (
            select(OfflineQueue.user_id, OfflineQueue.session_id, func.count(OfflineQueue.id).label('count'))
            .group_by(OfflineQueue.user_id, OfflineQueue.session_id)
            .having(func.count(OfflineQueue.id) > 1)
        )
        
        duplicates = db.session.execute(stmt).all()
        
        if not duplicates:
            print("✅ No duplicates found! Database is clean.")
            return
        
        print(f"⚠️  Found {len(duplicates)} duplicate combinations")
        
        total_deleted = 0
        
        for user_id, session_id, count in duplicates:
            print(f"\n📋 Processing user_id={user_id}, session_id={session_id} ({count} records)")
            
            # Get all records for this combination
            records_stmt = select(OfflineQueue).filter_by(
                user_id=user_id,
                session_id=session_id
            ).order_by(OfflineQueue.updated_at.desc())
            
            records = db.session.execute(records_stmt).scalars().all()
            
            if len(records) > 1:
                # Keep the first (most recent), delete the rest
                keep_record = records[0]
                delete_records = records[1:]
                
                print(f"   ✅ Keeping record ID {keep_record.id} (updated: {keep_record.updated_at})")
                
                for record in delete_records:
                    print(f"   🗑️  Deleting record ID {record.id} (updated: {record.updated_at})")
                    db.session.delete(record)
                    total_deleted += 1
        
        # Commit all deletions
        print(f"\n💾 Committing changes...")
        db.session.commit()
        
        print(f"\n✅ Cleanup complete! Deleted {total_deleted} duplicate records.")
        print(f"✅ Ready to apply UNIQUE constraint.")


if __name__ == '__main__':
    try:
        cleanup_duplicates()
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
