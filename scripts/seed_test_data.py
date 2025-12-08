#!/usr/bin/env python3
"""
Comprehensive Test Data Seeder for End-to-End Testing
Creates realistic meeting data with transcripts, insights, tasks, and analytics.
"""

import os
import sys
import random
from datetime import datetime, timedelta, date
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from werkzeug.security import generate_password_hash

TEST_USER_EMAIL = "test@minaapp.com"
TEST_USER_PASSWORD = "TestUser123!"

MEETING_DATA = [
    {
        "title": "Q4 Product Roadmap Planning",
        "meeting_type": "planning",
        "description": "Quarterly planning session to define product priorities and resource allocation for Q4.",
        "duration_minutes": 45,
        "transcript_segments": [
            {"speaker": "Sarah (Product Lead)", "text": "Welcome everyone to our Q4 planning session. Let's start by reviewing our current velocity and what we accomplished in Q3.", "confidence": 0.95},
            {"speaker": "Mike (Engineering)", "text": "We shipped the real-time transcription feature which increased user engagement by 34%. The WebSocket infrastructure is now stable.", "confidence": 0.92},
            {"speaker": "Sarah (Product Lead)", "text": "That's excellent progress. For Q4, I want to focus on three main areas: AI insights improvements, mobile experience, and enterprise features.", "confidence": 0.94},
            {"speaker": "Lisa (Design)", "text": "I've been working on the mobile mockups. The key challenge is maintaining feature parity while optimizing for smaller screens.", "confidence": 0.89},
            {"speaker": "Mike (Engineering)", "text": "We should prioritize the offline-first architecture for mobile. Users expect meetings to work even with spotty connections.", "confidence": 0.93},
            {"speaker": "David (Data Science)", "text": "The sentiment analysis model is ready for production. We've achieved 87% accuracy on our test dataset.", "confidence": 0.96},
            {"speaker": "Sarah (Product Lead)", "text": "Let's make that a priority for the first sprint. David, can you work with Mike to integrate it into the pipeline?", "confidence": 0.91},
            {"speaker": "David (Data Science)", "text": "Absolutely. We'll need about two weeks for integration and testing. I'll create the API endpoints this week.", "confidence": 0.94},
            {"speaker": "Lisa (Design)", "text": "For the enterprise features, I think we need a dedicated admin dashboard. Current analytics aren't sufficient for large teams.", "confidence": 0.88},
            {"speaker": "Mike (Engineering)", "text": "Agreed. We should also add role-based access control. Many enterprise clients have requested this.", "confidence": 0.95},
            {"speaker": "Sarah (Product Lead)", "text": "Okay, let me summarize our Q4 priorities: sentiment analysis integration, mobile app development, and enterprise admin features. Any objections?", "confidence": 0.97},
            {"speaker": "Team", "text": "No objections. Sounds like a solid plan.", "confidence": 0.85},
            {"speaker": "Sarah (Product Lead)", "text": "Great. Let's schedule a follow-up next week to review the detailed sprint plans. Meeting adjourned.", "confidence": 0.96},
        ],
        "summary": """## Q4 Product Roadmap Planning Summary

The team aligned on three major priorities for Q4: AI sentiment analysis integration, mobile app development with offline-first architecture, and enterprise features including admin dashboards and RBAC.

### Key Achievements from Q3
- Real-time transcription feature launched with 34% engagement increase
- WebSocket infrastructure stabilized

### Q4 Priorities
1. **Sentiment Analysis Integration** (Sprint 1-2)
   - 87% accuracy model ready for production
   - David and Mike to collaborate on pipeline integration

2. **Mobile Experience** (Sprint 2-4)
   - Offline-first architecture prioritized
   - Feature parity with web while optimizing for mobile

3. **Enterprise Features** (Sprint 3-4)
   - Admin dashboard for large team analytics
   - Role-based access control (RBAC)""",
        "actions": [
            {"title": "Integrate sentiment analysis model into transcription pipeline", "assignee": "David", "priority": "high", "due_days": 14},
            {"title": "Create API endpoints for sentiment analysis", "assignee": "David", "priority": "high", "due_days": 7},
            {"title": "Design mobile offline-first architecture", "assignee": "Mike", "priority": "high", "due_days": 10},
            {"title": "Complete mobile app mockups", "assignee": "Lisa", "priority": "medium", "due_days": 14},
            {"title": "Document RBAC requirements for enterprise", "assignee": "Sarah", "priority": "medium", "due_days": 7},
        ],
        "decisions": [
            "Q4 will focus on sentiment analysis, mobile, and enterprise features",
            "Offline-first architecture is the priority for mobile development",
            "Follow-up meeting scheduled for next week to review sprint plans",
        ],
        "sentiment": {"positive": 0.75, "neutral": 0.20, "negative": 0.05},
        "tags": ["planning", "q4", "roadmap", "product"],
    },
    {
        "title": "Customer Success Weekly Sync",
        "meeting_type": "standup",
        "description": "Weekly sync to review customer feedback, support tickets, and success metrics.",
        "duration_minutes": 30,
        "transcript_segments": [
            {"speaker": "Jennifer (CS Lead)", "text": "Good morning team. Let's start with our weekly customer health check. How are our key accounts doing?", "confidence": 0.94},
            {"speaker": "Tom (Account Manager)", "text": "Acme Corp renewed their annual subscription last week. They're really happy with the transcription accuracy improvements.", "confidence": 0.91},
            {"speaker": "Rachel (Support)", "text": "We did have a support spike on Monday. About 15 tickets came in regarding the calendar sync feature.", "confidence": 0.93},
            {"speaker": "Jennifer (CS Lead)", "text": "What was the issue? Is it resolved?", "confidence": 0.96},
            {"speaker": "Rachel (Support)", "text": "Google Calendar OAuth tokens were expiring too quickly. Engineering pushed a fix yesterday and tickets have dropped.", "confidence": 0.92},
            {"speaker": "Tom (Account Manager)", "text": "I have a demo scheduled with TechStart Inc tomorrow. They're evaluating us against Otter and Fireflies.", "confidence": 0.90},
            {"speaker": "Jennifer (CS Lead)", "text": "Great opportunity. Make sure to highlight our action item extraction - that's where we really stand out.", "confidence": 0.95},
            {"speaker": "Rachel (Support)", "text": "Also, the sentiment analysis feature if it's ready. Competitors don't have that yet.", "confidence": 0.88},
            {"speaker": "Jennifer (CS Lead)", "text": "Perfect. Tom, send me the prep materials and I'll join the demo. Any other updates?", "confidence": 0.94},
            {"speaker": "Tom (Account Manager)", "text": "NPS survey results came in. We're at 72, up from 68 last quarter.", "confidence": 0.97},
            {"speaker": "Jennifer (CS Lead)", "text": "Excellent improvement! Let's aim for 75 by end of Q4. Keep up the great work everyone.", "confidence": 0.96},
        ],
        "summary": """## Customer Success Weekly Sync Summary

The customer success team reviewed account health, support metrics, and upcoming opportunities.

### Highlights
- **Acme Corp** renewed annual subscription, citing improved transcription accuracy
- **NPS Score** improved from 68 to 72 quarter-over-quarter
- Support spike resolved: Calendar OAuth token expiration fix deployed

### Key Issues
- Calendar sync feature generated 15 support tickets on Monday (now resolved)

### Upcoming
- TechStart Inc demo scheduled - competitive evaluation against Otter and Fireflies
- Focus points: Action item extraction and sentiment analysis features""",
        "actions": [
            {"title": "Prepare demo materials for TechStart Inc", "assignee": "Tom", "priority": "high", "due_days": 1},
            {"title": "Join TechStart demo to support competitive positioning", "assignee": "Jennifer", "priority": "high", "due_days": 2},
            {"title": "Monitor calendar sync tickets post-fix", "assignee": "Rachel", "priority": "medium", "due_days": 3},
            {"title": "Create NPS improvement plan for Q4 target of 75", "assignee": "Jennifer", "priority": "medium", "due_days": 14},
        ],
        "decisions": [
            "Highlight action item extraction as key differentiator in demos",
            "Target NPS of 75 by end of Q4",
        ],
        "sentiment": {"positive": 0.68, "neutral": 0.27, "negative": 0.05},
        "tags": ["customer-success", "weekly", "nps", "support"],
    },
    {
        "title": "Incident Retrospective - API Outage Dec 5",
        "meeting_type": "retrospective",
        "description": "Post-incident review of the API outage that occurred on December 5th, lasting 23 minutes.",
        "duration_minutes": 60,
        "transcript_segments": [
            {"speaker": "Alex (SRE Lead)", "text": "Let's begin our incident retrospective. On December 5th at 14:32 UTC, our API experienced a 23-minute outage affecting approximately 12,000 users.", "confidence": 0.98},
            {"speaker": "Chris (Backend)", "text": "The root cause was a database connection pool exhaustion. A new query in the analytics service was holding connections too long.", "confidence": 0.95},
            {"speaker": "Alex (SRE Lead)", "text": "How did we detect the issue? I noticed we were alerted 8 minutes after users started experiencing problems.", "confidence": 0.94},
            {"speaker": "Maya (DevOps)", "text": "Our current alerting thresholds for connection pool usage were set too high. We only alert at 90% - that's too late.", "confidence": 0.93},
            {"speaker": "Chris (Backend)", "text": "I take responsibility for the query. I didn't anticipate the connection hold time under load. We need better load testing.", "confidence": 0.91},
            {"speaker": "Alex (SRE Lead)", "text": "This isn't about blame - it's about learning. What can we do to prevent this in the future?", "confidence": 0.97},
            {"speaker": "Maya (DevOps)", "text": "I propose we lower the connection pool alert threshold to 70% and add a rate-of-change alert.", "confidence": 0.94},
            {"speaker": "Chris (Backend)", "text": "We should also implement connection timeouts in the ORM layer. Currently there's no hard limit.", "confidence": 0.96},
            {"speaker": "Alex (SRE Lead)", "text": "Good suggestions. What about the query itself? Can we optimize it?", "confidence": 0.95},
            {"speaker": "Chris (Backend)", "text": "Yes, I've already rewritten it to use a cursor-based approach. Query time dropped from 4.2 seconds to 180 milliseconds.", "confidence": 0.98},
            {"speaker": "Maya (DevOps)", "text": "Impressive. We should also consider adding a circuit breaker for the analytics service.", "confidence": 0.92},
            {"speaker": "Alex (SRE Lead)", "text": "Agreed. Let me summarize our action items: lower alert thresholds, add connection timeouts, implement circuit breaker, and require load testing for database-heavy changes.", "confidence": 0.97},
            {"speaker": "Team", "text": "Sounds comprehensive. When do we want these completed?", "confidence": 0.88},
            {"speaker": "Alex (SRE Lead)", "text": "Alert changes should be done today. Circuit breaker and timeouts by end of week. Load testing process documentation by next Monday.", "confidence": 0.96},
        ],
        "summary": """## Incident Retrospective - API Outage Dec 5

### Incident Summary
- **Duration**: 23 minutes (14:32 - 14:55 UTC)
- **Impact**: ~12,000 users affected
- **Root Cause**: Database connection pool exhaustion from unoptimized analytics query

### What Went Wrong
1. Analytics query holding connections for 4.2 seconds under load
2. Alert thresholds set too high (90%) - delayed detection by 8 minutes
3. No connection timeouts configured in ORM layer

### What Went Right
- Quick identification of root cause once alerted
- Fast mitigation through query optimization (4.2s → 180ms)
- Blameless culture maintained during retrospective

### Action Items
1. Lower connection pool alert to 70% + add rate-of-change alert
2. Implement connection timeouts in ORM
3. Add circuit breaker for analytics service
4. Require load testing for database-heavy PRs""",
        "actions": [
            {"title": "Lower connection pool alert threshold to 70%", "assignee": "Maya", "priority": "urgent", "due_days": 0},
            {"title": "Add rate-of-change alert for connection usage", "assignee": "Maya", "priority": "urgent", "due_days": 0},
            {"title": "Implement connection timeouts in ORM layer", "assignee": "Chris", "priority": "high", "due_days": 5},
            {"title": "Add circuit breaker for analytics service", "assignee": "Chris", "priority": "high", "due_days": 5},
            {"title": "Document load testing requirements for PRs", "assignee": "Alex", "priority": "medium", "due_days": 7},
        ],
        "decisions": [
            "All database-heavy changes require load testing before merge",
            "Circuit breaker pattern will be standard for external service calls",
            "Connection pool alert threshold reduced from 90% to 70%",
        ],
        "sentiment": {"positive": 0.35, "neutral": 0.50, "negative": 0.15},
        "tags": ["incident", "retrospective", "database", "sre"],
    },
]


def clear_test_data():
    """Remove existing test data."""
    from models.user import User
    from models.workspace import Workspace
    from models.meeting import Meeting
    from models.session import Session
    from models.segment import Segment
    from models.task import Task
    from models.summary import Summary
    from models.analytics import Analytics
    
    print("Clearing existing test data...")
    
    user = db.session.query(User).filter_by(email=TEST_USER_EMAIL).first()
    if user:
        workspace = db.session.query(Workspace).filter_by(owner_id=user.id).first()
        if workspace:
            db.session.query(Meeting).filter_by(workspace_id=workspace.id).delete()
            db.session.query(Session).filter_by(workspace_id=workspace.id).delete()
            db.session.query(Task).filter_by(workspace_id=workspace.id).delete()
            db.session.delete(workspace)
        db.session.delete(user)
        db.session.commit()
    print("✅ Test data cleared")


def create_test_user():
    """Create test user with workspace."""
    from models.user import User
    from models.workspace import Workspace
    
    print(f"Creating test user: {TEST_USER_EMAIL}")
    
    user = User(
        email=TEST_USER_EMAIL,
        username="testuser",
        password_hash=generate_password_hash(TEST_USER_PASSWORD),
        first_name="Test",
        last_name="User",
        display_name="Test User",
        active=True,
        is_verified=True,
        role="admin",
        timezone="America/New_York",
        onboarding_completed=True,
        onboarding_step=5,
    )
    db.session.add(user)
    db.session.flush()
    
    workspace = Workspace(
        name="Test Workspace",
        slug=f"test-workspace-{uuid4().hex[:8]}",
        description="Workspace for end-to-end testing",
        owner_id=user.id,
        is_active=True,
        plan="pro",
        max_users=10,
    )
    db.session.add(workspace)
    db.session.flush()
    
    user.workspace_id = workspace.id
    db.session.commit()
    
    print(f"✅ Created user ID: {user.id}, workspace ID: {workspace.id}")
    return user, workspace


def create_meeting_with_data(user, workspace, meeting_data, days_ago):
    """Create a meeting with session, segments, summary, and tasks."""
    from models.meeting import Meeting
    from models.session import Session
    from models.segment import Segment
    from models.task import Task
    from models.summary import Summary, SummaryLevel, SummaryStyle
    from models.analytics import Analytics
    
    meeting_date = datetime.utcnow() - timedelta(days=days_ago)
    duration = meeting_data["duration_minutes"]
    
    meeting = Meeting(
        title=meeting_data["title"],
        description=meeting_data["description"],
        meeting_type=meeting_data["meeting_type"],
        status="completed",
        scheduled_start=meeting_date,
        scheduled_end=meeting_date + timedelta(minutes=duration),
        actual_start=meeting_date,
        actual_end=meeting_date + timedelta(minutes=duration),
        organizer_id=user.id,
        workspace_id=workspace.id,
        tags=meeting_data["tags"],
        priority="medium",
        recording_enabled=True,
        transcription_enabled=True,
        ai_insights_enabled=True,
    )
    db.session.add(meeting)
    db.session.flush()
    
    session = Session(
        external_id=f"session-{uuid4().hex[:12]}",
        title=meeting_data["title"],
        status="completed",
        started_at=meeting_date,
        completed_at=meeting_date + timedelta(minutes=duration),
        user_id=user.id,
        workspace_id=workspace.id,
        meeting_id=meeting.id,
        total_segments=len(meeting_data["transcript_segments"]),
        average_confidence=sum(s["confidence"] for s in meeting_data["transcript_segments"]) / len(meeting_data["transcript_segments"]),
        total_duration=duration * 60.0,
    )
    db.session.add(session)
    db.session.flush()
    
    segment_duration_ms = (duration * 60 * 1000) // len(meeting_data["transcript_segments"])
    for i, seg_data in enumerate(meeting_data["transcript_segments"]):
        segment = Segment(
            session_id=session.id,
            kind="final",
            text=f"[{seg_data['speaker']}] {seg_data['text']}",
            avg_confidence=seg_data["confidence"],
            start_ms=i * segment_duration_ms,
            end_ms=(i + 1) * segment_duration_ms,
        )
        db.session.add(segment)
    
    summary = Summary(
        session_id=session.id,
        level=SummaryLevel.STANDARD,
        style=SummaryStyle.EXECUTIVE,
        summary_md=meeting_data["summary"],
        brief_summary=meeting_data["summary"].split("\n\n")[0],
        detailed_summary=meeting_data["summary"],
        actions=meeting_data["actions"],
        decisions=meeting_data["decisions"],
        risks=[],
        engine="gpt-4o-mini",
    )
    db.session.add(summary)
    
    statuses = ["todo", "in_progress", "completed"]
    for action in meeting_data["actions"]:
        status = random.choice(statuses)
        task = Task(
            title=action["title"],
            description=f"Action item from: {meeting_data['title']}",
            task_type="action_item",
            priority=action["priority"],
            status=status,
            due_date=date.today() + timedelta(days=action["due_days"]),
            meeting_id=meeting.id,
            session_id=session.id,
            workspace_id=workspace.id,
            assigned_to_id=user.id,
            source="ai_extracted",
            confidence_score=random.uniform(0.85, 0.98),
            completion_percentage=100 if status == "completed" else (50 if status == "in_progress" else 0),
            completed_at=datetime.utcnow() if status == "completed" else None,
        )
        db.session.add(task)
    
    sentiment = meeting_data["sentiment"]
    analytics = Analytics(
        meeting_id=meeting.id,
        participant_count=len(set(s["speaker"] for s in meeting_data["transcript_segments"])),
        total_duration_minutes=float(duration),
        word_count=sum(len(s["text"].split()) for s in meeting_data["transcript_segments"]),
        overall_engagement_score=random.uniform(0.7, 0.95),
        overall_sentiment_score=sentiment["positive"] - sentiment["negative"],
        action_items_created=len(meeting_data["actions"]),
        decisions_made_count=len(meeting_data["decisions"]),
        question_count=random.randint(2, 8),
        talk_time_distribution={s["speaker"].split()[0]: random.randint(10, 30) for s in meeting_data["transcript_segments"][:5]},
        key_topics=meeting_data["tags"],
        analysis_status="completed",
    )
    db.session.add(analytics)
    
    print(f"  ✅ Created meeting: {meeting_data['title']}")
    return meeting


def create_standalone_tasks(user, workspace):
    """Create additional standalone tasks not linked to meetings."""
    from models.task import Task
    
    standalone_tasks = [
        {"title": "Review Q3 performance metrics", "priority": "medium", "status": "completed", "due_days": -3},
        {"title": "Update documentation for API v2", "priority": "low", "status": "todo", "due_days": 7},
        {"title": "Schedule 1:1 with new team member", "priority": "high", "status": "in_progress", "due_days": 2},
        {"title": "Prepare quarterly business review slides", "priority": "high", "status": "todo", "due_days": 5},
        {"title": "Review and approve budget proposal", "priority": "urgent", "status": "todo", "due_days": 1},
    ]
    
    for task_data in standalone_tasks:
        task = Task(
            title=task_data["title"],
            description="Manually created task for testing",
            task_type="action_item",
            priority=task_data["priority"],
            status=task_data["status"],
            due_date=date.today() + timedelta(days=task_data["due_days"]),
            workspace_id=workspace.id,
            assigned_to_id=user.id,
            source="manual",
            completion_percentage=100 if task_data["status"] == "completed" else (50 if task_data["status"] == "in_progress" else 0),
            completed_at=datetime.utcnow() if task_data["status"] == "completed" else None,
        )
        db.session.add(task)
    
    print(f"  ✅ Created {len(standalone_tasks)} standalone tasks")


def main():
    """Run the test data seeder."""
    print("\n" + "="*60)
    print("MINA TEST DATA SEEDER")
    print("="*60 + "\n")
    
    with app.app_context():
        clear_test_data()
        
        user, workspace = create_test_user()
        
        print("\nCreating meetings with transcripts and insights...")
        for i, meeting_data in enumerate(MEETING_DATA):
            days_ago = (len(MEETING_DATA) - i) * 2
            create_meeting_with_data(user, workspace, meeting_data, days_ago)
        
        print("\nCreating standalone tasks...")
        create_standalone_tasks(user, workspace)
        
        db.session.commit()
        
        print("\n" + "="*60)
        print("TEST DATA SEEDING COMPLETE")
        print("="*60)
        print(f"\n📧 Test User Email: {TEST_USER_EMAIL}")
        print(f"🔑 Test User Password: {TEST_USER_PASSWORD}")
        print(f"🏢 Workspace ID: {workspace.id}")
        print(f"📊 Created {len(MEETING_DATA)} meetings with transcripts")
        print(f"✅ Created {sum(len(m['actions']) for m in MEETING_DATA) + 5} tasks total")
        print("\nYou can now log in and test all features!\n")


if __name__ == "__main__":
    main()
