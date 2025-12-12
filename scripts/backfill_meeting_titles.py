#!/usr/bin/env python
"""
Backfill Meeting Titles Script

Regenerates meaningful titles for existing meetings that have placeholder names
like "Live Transcription Session" using AI analysis of transcript content.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models.meeting import Meeting
from models.session import Session
from models.segment import Segment
from sqlalchemy import select


def get_transcript_for_meeting(meeting_id: int) -> str:
    """Get transcript text from meeting's session segments."""
    meeting = db.session.get(Meeting, meeting_id)
    if not meeting or not meeting.session:
        return ""
    
    stmt = select(Segment).where(
        Segment.session_id == meeting.session.id,
        Segment.kind == 'final'
    ).order_by(Segment.start_ms)
    
    segments = db.session.execute(stmt).scalars().all()
    
    if not segments:
        stmt = select(Segment).where(
            Segment.session_id == meeting.session.id
        ).order_by(Segment.start_ms)
        segments = db.session.execute(stmt).scalars().all()
    
    return " ".join(s.text.strip() for s in segments[:50] if s.text)


async def backfill_meeting_titles(dry_run: bool = True, limit: int = None):
    """Backfill placeholder meeting titles with AI-generated ones."""
    from services.meeting_title_generator import get_title_generator
    
    generator = get_title_generator()
    
    stmt = select(Meeting)
    meetings = db.session.execute(stmt).scalars().all()
    
    poor_title_keywords = ['discussion', 'yeah', 'need', 'here', 'showing', 'give', 'know', 
                            'happening', 'pick', 'tomorrow', 'today', 'regards', 'doing']
    
    def has_poor_title(title: str) -> bool:
        """Check if title is a placeholder or keyword-based fallback."""
        if generator.is_placeholder_title(title):
            return True
        title_lower = title.lower()
        word_count = len(title.split())
        if word_count <= 3 and any(kw in title_lower for kw in poor_title_keywords):
            return True
        return False
    
    placeholder_meetings = [
        m for m in meetings 
        if has_poor_title(m.title)
    ]
    
    if limit:
        placeholder_meetings = placeholder_meetings[:limit]
    
    print(f"Found {len(placeholder_meetings)} meetings with placeholder titles")
    
    updated = 0
    failed = 0
    skipped = 0
    
    for meeting in placeholder_meetings:
        print(f"\n--- Meeting {meeting.id}: '{meeting.title}' ---")
        
        transcript = get_transcript_for_meeting(meeting.id)
        
        if not transcript or len(transcript.strip()) < 30:
            print(f"  ⚠️ Skipped: Insufficient transcript content ({len(transcript)} chars)")
            skipped += 1
            continue
        
        print(f"  Transcript: {transcript[:100]}...")
        
        try:
            new_title = await generator.generate_title(transcript)
            
            if new_title:
                print(f"  ✅ New title: {new_title}")
                
                if not dry_run:
                    meeting.title = new_title
                    db.session.commit()
                    print(f"  💾 Saved to database")
                else:
                    print(f"  (dry run - not saved)")
                
                updated += 1
            else:
                print(f"  ⚠️ AI returned no title")
                skipped += 1
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'APPLIED'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill meeting titles with AI-generated names")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry run)")
    parser.add_argument("--limit", type=int, help="Limit number of meetings to process")
    args = parser.parse_args()
    
    print("="*60)
    print("Meeting Title Backfill Script")
    print("="*60)
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    if args.limit:
        print(f"Limit: {args.limit} meetings")
    print()
    
    with app.app_context():
        asyncio.run(backfill_meeting_titles(dry_run=not args.apply, limit=args.limit))
