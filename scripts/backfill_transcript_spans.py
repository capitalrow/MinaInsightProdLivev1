#!/usr/bin/env python
"""
Backfill Transcript Spans Script

Links existing tasks to their source transcript segments by matching
evidence_quote text to segment content. This enables the "Jump to Transcript"
feature and spoken provenance display.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models.task import Task
from models.meeting import Meeting
from models.segment import Segment
from sqlalchemy import select


def fuzzy_match_quote(quote: str, segment_text: str, threshold: float = 0.6) -> bool:
    """Check if quote words significantly overlap with segment text."""
    stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 
                  'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 
                  'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 
                  'who', 'that', 'this', 'with', 'have', 'from', 'they', 'will',
                  'need', 'just', 'also', 'been', 'some', 'what', 'when', 'your'}
    
    quote_words = set(word.lower() for word in quote.split() 
                      if len(word) > 3 and word.lower() not in stop_words)
    segment_words = set(word.lower() for word in segment_text.split() 
                        if len(word) > 3 and word.lower() not in stop_words)
    
    if not quote_words or not segment_words:
        return False
    
    intersection = quote_words.intersection(segment_words)
    overlap_ratio = len(intersection) / len(quote_words)
    
    return overlap_ratio >= threshold


def get_evidence_quote(task: Task) -> str:
    """Extract evidence quote from task extraction context."""
    if not task.extraction_context:
        return ""
    
    ctx = task.extraction_context
    
    quote = ctx.get("evidence_quote", "")
    if not quote and ctx.get("original_action"):
        quote = ctx["original_action"].get("evidence_quote", "")
    if not quote:
        quote = ctx.get("quote", "")
    
    return quote.strip() if quote else ""


def find_matching_segment(quote: str, segments) -> tuple:
    """Find segment(s) matching the quote and return span info."""
    if not quote or len(quote) < 10:
        return None, None
    
    quote_lower = quote.lower()
    matched_segments = []
    
    for segment in segments:
        if not segment.text:
            continue
        segment_text = segment.text.lower()
        
        if quote_lower in segment_text:
            matched_segments.append(segment)
        elif fuzzy_match_quote(quote_lower, segment_text):
            matched_segments.append(segment)
    
    if not matched_segments:
        return None, None
    
    first_seg = matched_segments[0]
    last_seg = matched_segments[-1] if len(matched_segments) > 1 else first_seg
    
    if last_seg.start_ms and first_seg.start_ms:
        if (last_seg.start_ms - first_seg.start_ms) > 10000:
            last_seg = first_seg
            matched_segments = [first_seg]
    
    transcript_span = {
        "start_ms": first_seg.start_ms,
        "end_ms": last_seg.end_ms,
        "segment_ids": [seg.id for seg in matched_segments]
    }
    
    speaker = getattr(first_seg, 'speaker', None) or getattr(first_seg, 'speaker_id', None)
    
    return transcript_span, speaker


def backfill_transcript_spans(dry_run: bool = True, limit: int = None):
    """Backfill transcript_span for tasks that have evidence_quote but no span."""
    
    stmt = select(Task).where(
        Task.extraction_context.isnot(None),
        Task.transcript_span.is_(None),
        Task.deleted_at.is_(None)
    )
    tasks = db.session.execute(stmt).scalars().all()
    
    if limit:
        tasks = tasks[:limit]
    
    print(f"Found {len(tasks)} tasks with extraction_context but no transcript_span")
    
    updated = 0
    skipped_no_quote = 0
    skipped_no_match = 0
    skipped_no_meeting = 0
    speakers_added = 0
    
    meeting_segments_cache = {}
    
    for task in tasks:
        evidence_quote = get_evidence_quote(task)
        
        if not evidence_quote or len(evidence_quote) < 15:
            skipped_no_quote += 1
            continue
        
        if not task.meeting or not task.meeting.session:
            skipped_no_meeting += 1
            continue
        
        session_id = task.meeting.session.id
        
        if session_id not in meeting_segments_cache:
            seg_stmt = select(Segment).where(
                Segment.session_id == session_id,
                Segment.kind == 'final'
            ).order_by(Segment.start_ms)
            segments = db.session.execute(seg_stmt).scalars().all()
            
            if not segments:
                seg_stmt = select(Segment).where(
                    Segment.session_id == session_id
                ).order_by(Segment.start_ms)
                segments = db.session.execute(seg_stmt).scalars().all()
            
            meeting_segments_cache[session_id] = segments
        
        segments = meeting_segments_cache[session_id]
        
        if not segments:
            skipped_no_meeting += 1
            continue
        
        transcript_span, speaker = find_matching_segment(evidence_quote, segments)
        
        if not transcript_span or transcript_span.get("start_ms") is None:
            skipped_no_match += 1
            if not dry_run:
                print(f"  Task {task.id}: No match for '{evidence_quote[:60]}...'")
            continue
        
        print(f"\nTask {task.id}: '{task.title[:50]}...'")
        print(f"  Quote: '{evidence_quote[:80]}...'")
        print(f"  Span: {transcript_span['start_ms']}ms - {transcript_span['end_ms']}ms")
        if speaker:
            print(f"  Speaker: {speaker}")
        
        if not dry_run:
            task.transcript_span = transcript_span
            
            if speaker and task.extraction_context:
                if not task.extraction_context.get("speaker"):
                    task.extraction_context["speaker"] = speaker
                    speakers_added += 1
            
            db.session.add(task)
        
        updated += 1
    
    if not dry_run:
        db.session.commit()
    
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Updated with transcript_span: {updated}")
    print(f"  Speakers added: {speakers_added}")
    print(f"  Skipped (no quote): {skipped_no_quote}")
    print(f"  Skipped (no match): {skipped_no_match}")
    print(f"  Skipped (no meeting/session): {skipped_no_meeting}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'APPLIED'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill transcript spans for tasks")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    parser.add_argument("--limit", type=int, help="Limit number of tasks to process")
    args = parser.parse_args()
    
    print("="*60)
    print("Transcript Span Backfill Script")
    print("="*60)
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    if args.limit:
        print(f"Limit: {args.limit} tasks")
    print()
    
    with app.app_context():
        backfill_transcript_spans(dry_run=not args.apply, limit=args.limit)
