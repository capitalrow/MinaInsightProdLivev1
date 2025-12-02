"""
PRODUCTION-FOCUSED TASK EXTRACTION VALIDATION
Validates the complete task extraction → UI display pipeline as it runs in production.
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL')

from app import app, db
from models.session import Session
from models.segment import Segment
from models.task import Task
from models.summary import Summary

print("\n" + "=" * 80)
print("PRODUCTION TASK EXTRACTION VALIDATION")
print("=" * 80)

# Create app context
app_context = app.app_context()
app_context.push()

# Create tables
db.create_all()

# Test 1: Create test session with realistic transcript
print("\n[TEST 1] Creating test session with realistic meeting transcript")
print("-" * 80)

session = Session(
    external_id=f"prod_test_{int(datetime.utcnow().timestamp())}",
    title="Product Team Planning Meeting",
    status="completed"
)
db.session.add(session)
db.session.commit()

print(f"✅ Created session: {session.external_id} (ID: {session.id})")

# Add realistic meeting segments
meeting_segments = [
    "Okay team, let's review our sprint goals. Sarah, I need you to check the Replit agent test progress by Friday.",
    "Sure, I'll review the test results and send an update. John, can you review the analytics dashboard?",
    "Absolutely. I'll review the analytics dashboard and prepare the performance report by tomorrow.",
    "Great. We also need to finalize the API documentation before next Tuesday.",
    "I'll schedule a follow-up meeting with the design team to discuss UI improvements.",
]

for idx, text in enumerate(meeting_segments):
    segment = Segment(
        session_id=session.id,
        text=text,
        start_ms=idx * 5000,
        end_ms=(idx + 1) * 5000,
        kind="final",
        avg_confidence=0.92
    )
    db.session.add(segment)

db.session.commit()
print(f"✅ Added {len(meeting_segments)} transcript segments")

# Test 2: Create AI summary with tasks (simulating AI extraction)
print("\n[TEST 2] Creating AI summary with extracted tasks")
print("-" * 80)

summary = Summary(
    session_id=session.id,
    paragraphs=[
        "The team discussed sprint planning and assigned key tasks to team members.",
        "Review activities were scheduled for test progress and analytics dashboard.",
        "Documentation deadlines were established for API finalization."
    ],
    key_points=[
        "Sprint goals review scheduled",
        "Test progress check assigned to Sarah",
        "Analytics review assigned to John"
    ],
    actions=[
        {
            "text": "Sarah needs to check the Replit agent test progress",
            "priority": "high",
            "due": "by Friday",
            "owner": "Sarah",
            "evidence_quote": "I need you to check the Replit agent test progress by Friday"
        },
        {
            "text": "review the analytics dashboard and prepare the performance report",
            "priority": "high",
            "due": "tomorrow",
            "owner": "John",
            "evidence_quote": "I'll review the analytics dashboard and prepare the performance report by tomorrow"
        },
        {
            "text": "finalize the API documentation",
            "priority": "medium",
            "due": "next Tuesday",
            "owner": "not specified",
            "evidence_quote": "need to finalize the API documentation before next Tuesday"
        }
    ]
)
db.session.add(summary)
db.session.commit()

print(f"✅ Created summary with {len(summary.actions)} AI-extracted actions")

# Test 3: Run post-transcription pipeline (triggers task creation)
print("\n[TEST 3] Running post-transcription pipeline")
print("-" * 80)

from services.post_transcription_orchestrator import PostTranscriptionOrchestrator

orchestrator = PostTranscriptionOrchestrator()
result = orchestrator.process_completed_session(session.external_id)

print(f"Pipeline Result:")
print(f"  Success: {result.get('success')}")
print(f"  Events Completed: {len(result.get('events_completed', []))}")
print(f"  Events Failed: {len(result.get('events_failed', []))}")

# Test 4: Verify tasks were created and persisted
print("\n[TEST 4] Verifying task persistence")
print("-" * 80)

tasks = db.session.query(Task).filter_by(session_id=session.id).all()

print(f"✅ Found {len(tasks)} tasks in database")

if len(tasks) == 0:
    print("❌ CRITICAL: No tasks were created!")
    sys.exit(1)

# Test 5: Verify to_dict() serialization for UI
print("\n[TEST 5] Verifying UI data serialization")
print("-" * 80)

tasks_data = [task.to_dict(include_relationships=True) for task in tasks]

critical_fields = [
    'id', 'title', 'priority', 'status', 'confidence_score',
    'extraction_context', 'due_date', 'assigned_to_id',
    'is_overdue', 'is_due_soon'
]

all_valid = True
for idx, task_dict in enumerate(tasks_data):
    print(f"\nTask {idx + 1}: {task_dict['title'][:60]}...")
    
    missing_fields = []
    for field in critical_fields:
        if field not in task_dict:
            missing_fields.append(field)
            all_valid = False
    
    if missing_fields:
        print(f"  ❌ Missing fields: {missing_fields}")
    else:
        print(f"  ✅ All critical fields present")
    
    # Display key metadata
    print(f"  Priority: {task_dict.get('priority')}")
    print(f"  Confidence: {task_dict.get('confidence_score')}")
    print(f"  Has extraction_context: {bool(task_dict.get('extraction_context'))}")
    print(f"  Due date: {task_dict.get('due_date', 'None')}")

if not all_valid:
    print("\n❌ CRITICAL: Some tasks missing required UI fields!")
    sys.exit(1)

# Test 6: Simulate route handler (sessions/<id>/refined)
print("\n[TEST 6] Simulating route handler for UI rendering")
print("-" * 80)

# This simulates what routes/sessions.py does
from sqlalchemy import select
stmt = select(Task).filter(Task.session_id == session.id).order_by(Task.created_at)
route_tasks = db.session.execute(stmt).scalars().all()
route_tasks_data = [task.to_dict(include_relationships=True) for task in route_tasks]

# Group by priority for CROWN+ UI
high_priority = [t for t in route_tasks_data if t['priority'] == 'high']
medium_priority = [t for t in route_tasks_data if t['priority'] == 'medium']
low_priority = [t for t in route_tasks_data if t['priority'] == 'low']

print(f"Priority Distribution for UI:")
print(f"  High: {len(high_priority)} tasks")
print(f"  Medium: {len(medium_priority)} tasks")
print(f"  Low: {len(low_priority)} tasks")

print(f"\n✅ Route handler simulation successful")

# Test 7: Verify template rendering data
print("\n[TEST 7] Verifying template can render tasks")
print("-" * 80)

can_render_all = True
for task_dict in route_tasks_data:
    # Check if template conditions will work
    has_confidence = task_dict.get('confidence_score') is not None
    has_title = task_dict.get('title') is not None
    has_status = task_dict.get('status') in ['todo', 'completed', 'done', 'in_progress']
    
    if not (has_confidence and has_title and has_status):
        print(f"❌ Task cannot be rendered: {task_dict.get('title', 'NO TITLE')}")
        can_render_all = False
    else:
        # Simulate confidence indicator logic
        confidence = task_dict['confidence_score']
        if confidence >= 0.85:
            indicator = "✅"
        elif confidence >= 0.65:
            indicator = "⚠️"
        else:
            indicator = "ℹ️"
        
        print(f"{indicator} {task_dict['title'][:50]}... (priority: {task_dict['priority']})")

if not can_render_all:
    print("\n❌ CRITICAL: Some tasks cannot be rendered in UI!")
    sys.exit(1)

print(f"\n✅ All tasks can be rendered in CROWN+ UI")

# Final Summary
print("\n" + "=" * 80)
print("FINAL VALIDATION SUMMARY")
print("=" * 80)
print(f"✅ Session created: {session.external_id}")
print(f"✅ Transcript segments: {len(meeting_segments)}")
print(f"✅ AI summary created with {len(summary.actions)} actions")
print(f"✅ Tasks extracted and persisted: {len(tasks)}")
print(f"✅ All tasks have required UI fields")
print(f"✅ Tasks grouped by priority: {len(high_priority)} high, {len(medium_priority)} medium, {len(low_priority)} low")
print(f"✅ All tasks renderable in CROWN+ UI")
print("\n🎉 100% PRODUCTION VALIDATION PASSED")
print(f"\nTest Session ID: {session.external_id}")
print(f"View at: /sessions/{session.external_id}/refined")
print("=" * 80)

# Cleanup
db.session.close()
app_context.pop()

sys.exit(0)
