#!/usr/bin/env python3
"""
CROWN⁴.6 Demo Data Seeder
Creates comprehensive test data to activate all dormant features:
- Spoken Provenance (speaker badges, confidence scores)
- Meeting Heatmap (multiple meetings with varying heat intensity)
- Emotional UI (different meeting types triggering different moods)
- Impact Score (high-effectiveness meetings)
- AI Partner Nudges (tasks with patterns triggering suggestions)
"""

import sys
import os
from datetime import datetime, date, timedelta
from hashlib import sha256

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Workspace, Meeting, Task, Analytics


def create_demo_data():
    """Create comprehensive demo data for CROWN⁴.6 feature testing."""
    
    with app.app_context():
        print("🚀 Starting CROWN⁴.6 Demo Data Seeder...")
        
        # Find existing user or create test user (SQLAlchemy 2.0 syntax)
        user = db.session.query(User).filter_by(email='test@mina.ai').first()
        if not user:
            user = db.session.query(User).first()
        
        if not user:
            print("❌ No users found. Please create a user first via the web interface.")
            return False
        
        print(f"✅ Using user: {user.username} (ID: {user.id})")
        
        # Get or create workspace
        workspace = user.workspace
        if not workspace:
            workspace = db.session.query(Workspace).first()
            if not workspace:
                workspace = Workspace(
                    name="Demo Workspace",
                    slug="demo-workspace",
                    owner_id=user.id
                )
                db.session.add(workspace)
                db.session.flush()
                user.workspace_id = workspace.id
                print(f"✅ Created workspace: {workspace.name}")
            else:
                user.workspace_id = workspace.id
        
        print(f"✅ Using workspace: {workspace.name} (ID: {workspace.id})")
        
        # ═══════════════════════════════════════════════════════════════════
        # MEETING 1: High-Impact Strategy Session (Energizing / High Heat)
        # ═══════════════════════════════════════════════════════════════════
        meeting1 = Meeting(
            title="Q1 Product Strategy Workshop",
            description="High-energy planning session for next quarter initiatives",
            meeting_type="planning",
            status="completed",
            organizer_id=user.id,
            workspace_id=workspace.id,
            scheduled_start=datetime.utcnow() - timedelta(hours=2),
            scheduled_end=datetime.utcnow() - timedelta(hours=1),
            actual_start=datetime.utcnow() - timedelta(hours=2),
            actual_end=datetime.utcnow() - timedelta(hours=1),
            priority="high",
            tags=["strategy", "planning", "q1"],
            created_at=datetime.utcnow() - timedelta(hours=3)
        )
        db.session.add(meeting1)
        db.session.flush()
        
        # High-impact analytics for Meeting 1
        analytics1 = Analytics(
            meeting_id=meeting1.id,
            total_duration_minutes=60,
            participant_count=5,
            overall_engagement_score=0.92,
            overall_sentiment_score=0.78,
            meeting_effectiveness_score=0.89,
            action_items_created=4,
            decisions_made_count=3,
            analysis_status="completed"
        )
        db.session.add(analytics1)
        
        # Tasks from Meeting 1 with spoken provenance
        task1_1 = Task(
            title="Finalize Q1 roadmap priorities",
            description="Review and prioritize all feature requests for Q1 based on customer feedback",
            meeting_id=meeting1.id,
            workspace_id=str(workspace.id),
            assigned_to_id=user.id,
            created_by_id=user.id,
            priority="urgent",
            status="todo",
            due_date=date.today() + timedelta(days=3),
            extracted_by_ai=True,
            confidence_score=0.94,
            source="ai_extraction",
            emotional_state="accepted",
            extraction_context={
                "speaker": "Sarah Chen",
                "evidence_quote": "We absolutely need to finalize the Q1 roadmap by end of week. This is our top priority.",
                "meeting_title": meeting1.title,
                "emotion_type": "energizing"
            },
            transcript_span={
                "start_ms": 145000,
                "end_ms": 152000,
                "segment_ids": [1, 2]
            },
            origin_hash=sha256(f"task1_1_{meeting1.id}".encode()).hexdigest()[:64],
            position=0
        )
        
        task1_2 = Task(
            title="Schedule customer interviews for feedback collection",
            description="Reach out to top 10 customers for product feedback sessions",
            meeting_id=meeting1.id,
            workspace_id=str(workspace.id),
            assigned_to_id=user.id,
            created_by_id=user.id,
            priority="high",
            status="in_progress",
            due_date=date.today() + timedelta(days=5),
            extracted_by_ai=True,
            confidence_score=0.87,
            source="ai_extraction",
            emotional_state="accepted",
            extraction_context={
                "speaker": "Marcus Johnson",
                "evidence_quote": "I'll take ownership of scheduling the customer interviews. We should aim for at least 10 sessions.",
                "meeting_title": meeting1.title,
                "emotion_type": "energizing"
            },
            transcript_span={
                "start_ms": 320000,
                "end_ms": 335000,
                "segment_ids": [5, 6]
            },
            origin_hash=sha256(f"task1_2_{meeting1.id}".encode()).hexdigest()[:64],
            position=1
        )
        
        task1_3 = Task(
            title="Prepare competitive analysis presentation",
            description="Research competitor moves and prepare executive summary",
            meeting_id=meeting1.id,
            workspace_id=str(workspace.id),
            assigned_to_id=user.id,
            created_by_id=user.id,
            priority="medium",
            status="todo",
            due_date=date.today() + timedelta(days=7),
            extracted_by_ai=True,
            confidence_score=0.72,
            source="ai_extraction",
            emotional_state="pending_suggest",
            extraction_context={
                "speaker": "Alex Rivera",
                "evidence_quote": "Someone should probably look at what our competitors announced last week. Could be relevant for our planning.",
                "meeting_title": meeting1.title,
                "emotion_type": "neutral"
            },
            transcript_span={
                "start_ms": 890000,
                "end_ms": 905000,
                "segment_ids": [15, 16]
            },
            origin_hash=sha256(f"task1_3_{meeting1.id}".encode()).hexdigest()[:64],
            position=2
        )
        
        db.session.add_all([task1_1, task1_2, task1_3])
        print(f"✅ Created Meeting 1: '{meeting1.title}' with 3 tasks (HIGH impact, ENERGIZING)")
        
        # ═══════════════════════════════════════════════════════════════════
        # MEETING 2: Incident Review (Calming / Medium Heat)
        # ═══════════════════════════════════════════════════════════════════
        meeting2 = Meeting(
            title="Production Incident Post-Mortem",
            description="Review of last week's service outage and prevention measures",
            meeting_type="retrospective",
            status="completed",
            organizer_id=user.id,
            workspace_id=workspace.id,
            scheduled_start=datetime.utcnow() - timedelta(days=1, hours=4),
            scheduled_end=datetime.utcnow() - timedelta(days=1, hours=3),
            actual_start=datetime.utcnow() - timedelta(days=1, hours=4),
            actual_end=datetime.utcnow() - timedelta(days=1, hours=3),
            priority="high",
            tags=["incident", "postmortem", "reliability"],
            created_at=datetime.utcnow() - timedelta(days=1, hours=5)
        )
        db.session.add(meeting2)
        db.session.flush()
        
        # Medium-impact analytics for Meeting 2
        analytics2 = Analytics(
            meeting_id=meeting2.id,
            total_duration_minutes=60,
            participant_count=4,
            overall_engagement_score=0.85,
            overall_sentiment_score=-0.15,
            meeting_effectiveness_score=0.76,
            action_items_created=3,
            decisions_made_count=2,
            analysis_status="completed"
        )
        db.session.add(analytics2)
        
        task2_1 = Task(
            title="Implement circuit breaker pattern",
            description="Add circuit breaker to prevent cascade failures in the payment service",
            meeting_id=meeting2.id,
            workspace_id=str(workspace.id),
            assigned_to_id=user.id,
            created_by_id=user.id,
            priority="urgent",
            status="todo",
            due_date=date.today() + timedelta(days=2),
            extracted_by_ai=True,
            confidence_score=0.96,
            source="ai_extraction",
            emotional_state="accepted",
            extraction_context={
                "speaker": "David Kim",
                "evidence_quote": "The root cause was clear - we need circuit breakers immediately. This should be our top engineering priority.",
                "meeting_title": meeting2.title,
                "emotion_type": "calming"
            },
            transcript_span={
                "start_ms": 450000,
                "end_ms": 468000,
                "segment_ids": [8, 9, 10]
            },
            origin_hash=sha256(f"task2_1_{meeting2.id}".encode()).hexdigest()[:64],
            position=3,
            labels=["engineering", "reliability", "urgent"]
        )
        
        task2_2 = Task(
            title="Update runbook with new escalation procedures",
            description="Document the improved on-call escalation process we agreed upon",
            meeting_id=meeting2.id,
            workspace_id=str(workspace.id),
            assigned_to_id=user.id,
            created_by_id=user.id,
            priority="high",
            status="todo",
            due_date=date.today() + timedelta(days=4),
            extracted_by_ai=True,
            confidence_score=0.88,
            source="ai_extraction",
            emotional_state="accepted",
            extraction_context={
                "speaker": "Emily Watson",
                "evidence_quote": "I volunteer to update the runbook. We clearly need better documentation for the on-call team.",
                "meeting_title": meeting2.title,
                "emotion_type": "calming"
            },
            transcript_span={
                "start_ms": 1200000,
                "end_ms": 1215000,
                "segment_ids": [22, 23]
            },
            origin_hash=sha256(f"task2_2_{meeting2.id}".encode()).hexdigest()[:64],
            position=4,
            labels=["documentation", "on-call"]
        )
        
        db.session.add_all([task2_1, task2_2])
        print(f"✅ Created Meeting 2: '{meeting2.title}' with 2 tasks (MEDIUM impact, CALMING)")
        
        # ═══════════════════════════════════════════════════════════════════
        # MEETING 3: Quick Standup (Neutral / Low Heat)
        # ═══════════════════════════════════════════════════════════════════
        meeting3 = Meeting(
            title="Daily Engineering Standup",
            description="Quick sync on current sprint progress",
            meeting_type="standup",
            status="completed",
            organizer_id=user.id,
            workspace_id=workspace.id,
            scheduled_start=datetime.utcnow() - timedelta(days=3, hours=1),
            scheduled_end=datetime.utcnow() - timedelta(days=3, minutes=45),
            actual_start=datetime.utcnow() - timedelta(days=3, hours=1),
            actual_end=datetime.utcnow() - timedelta(days=3, minutes=45),
            priority="medium",
            tags=["standup", "sprint"],
            created_at=datetime.utcnow() - timedelta(days=3, hours=2)
        )
        db.session.add(meeting3)
        db.session.flush()
        
        analytics3 = Analytics(
            meeting_id=meeting3.id,
            total_duration_minutes=15,
            participant_count=3,
            overall_engagement_score=0.70,
            overall_sentiment_score=0.25,
            meeting_effectiveness_score=0.65,
            action_items_created=1,
            decisions_made_count=0,
            analysis_status="completed"
        )
        db.session.add(analytics3)
        
        task3_1 = Task(
            title="Review pull request #247",
            description="Code review needed for the new authentication flow",
            meeting_id=meeting3.id,
            workspace_id=str(workspace.id),
            assigned_to_id=user.id,
            created_by_id=user.id,
            priority="medium",
            status="todo",
            due_date=date.today(),
            extracted_by_ai=True,
            confidence_score=0.82,
            source="ai_extraction",
            emotional_state="accepted",
            extraction_context={
                "speaker": "Team Member",
                "evidence_quote": "I'm blocked on PR 247, could someone take a look today?",
                "meeting_title": meeting3.title,
                "emotion_type": "neutral"
            },
            transcript_span={
                "start_ms": 120000,
                "end_ms": 128000,
                "segment_ids": [3]
            },
            origin_hash=sha256(f"task3_1_{meeting3.id}".encode()).hexdigest()[:64],
            position=5,
            labels=["code-review"]
        )
        
        db.session.add(task3_1)
        print(f"✅ Created Meeting 3: '{meeting3.title}' with 1 task (LOW impact, NEUTRAL)")
        
        # ═══════════════════════════════════════════════════════════════════
        # Manual task without meeting (for comparison)
        # ═══════════════════════════════════════════════════════════════════
        manual_task = Task(
            title="Update team wiki documentation",
            description="General documentation update - no meeting associated",
            workspace_id=str(workspace.id),
            assigned_to_id=user.id,
            created_by_id=user.id,
            priority="low",
            status="todo",
            due_date=date.today() + timedelta(days=14),
            extracted_by_ai=False,
            source="manual",
            position=6
        )
        db.session.add(manual_task)
        print(f"✅ Created manual task (no meeting origin)")
        
        # ═══════════════════════════════════════════════════════════════════
        # Task with snooze pattern (for AI nudge triggers)
        # ═══════════════════════════════════════════════════════════════════
        snoozed_task = Task(
            title="Prepare monthly metrics report",
            description="Compile performance metrics for stakeholder review",
            meeting_id=meeting1.id,
            workspace_id=str(workspace.id),
            assigned_to_id=user.id,
            created_by_id=user.id,
            priority="medium",
            status="todo",
            due_date=date.today() - timedelta(days=2),  # Overdue!
            extracted_by_ai=True,
            confidence_score=0.79,
            source="ai_extraction",
            emotional_state="accepted",
            extraction_context={
                "speaker": "Manager",
                "evidence_quote": "Don't forget we need the monthly metrics report soon.",
                "meeting_title": meeting1.title,
                "emotion_type": "neutral"
            },
            transcript_span={
                "start_ms": 2100000,
                "end_ms": 2108000,
                "segment_ids": [35]
            },
            origin_hash=sha256(f"snoozed_task_{meeting1.id}".encode()).hexdigest()[:64],
            position=7,
            snoozed_until=datetime.utcnow() - timedelta(hours=12)  # Was snoozed, now active
        )
        db.session.add(snoozed_task)
        print(f"✅ Created overdue task (triggers AI nudge suggestion)")
        
        # Commit all changes
        db.session.commit()
        
        print("\n" + "═" * 60)
        print("✅ CROWN⁴.6 Demo Data Seeding Complete!")
        print("═" * 60)
        print(f"""
Summary:
  - 3 Meetings created with varying heat intensities
  - 8 Tasks created total:
    • 6 AI-extracted with spoken provenance
    • 1 manual task (no meeting)
    • 1 overdue task (triggers AI nudges)
  
Features Now Active:
  ✅ Spoken Provenance badges (speaker names, confidence)
  ✅ Meeting Heatmap (3 meetings with different heat levels)
  ✅ Emotional UI (energizing, calming, neutral moods)
  ✅ Impact Score (high-effectiveness meeting analytics)
  ✅ Jump to Transcript links (transcript_span data)
  ✅ AI Nudge triggers (overdue task pattern)

Visit /dashboard/tasks to see all features in action!
""")
        return True


if __name__ == "__main__":
    success = create_demo_data()
    sys.exit(0 if success else 1)
