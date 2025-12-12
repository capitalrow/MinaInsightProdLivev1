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
    """Find the BEST matching segment for the quote and return span info.
    
    Uses a scoring system to find the most specific match, not just the first match.
    """
    if not quote or len(quote) < 10:
        return None, None
    
    quote_lower = quote.lower()
    quote_words = set(word.lower() for word in quote.split() if len(word) > 3)
    
    best_segment = None
    best_score = 0
    
    for segment in segments:
        if not segment.text:
            continue
        segment_text = segment.text.lower()
        
        score = 0
        
        # Exact substring match - highest score
        if quote_lower in segment_text:
            score = 100
        elif segment_text in quote_lower:
            score = 90
        else:
            # Calculate word overlap score
            segment_words = set(word.lower() for word in segment_text.split() if len(word) > 3)
            if quote_words and segment_words:
                intersection = quote_words.intersection(segment_words)
                overlap_ratio = len(intersection) / len(quote_words)
                # Scale 0-1 overlap to 0-80 score
                score = int(overlap_ratio * 80)
        
        # Update best match if this is better
        if score > best_score:
            best_score = score
            best_segment = segment
    
    # Require minimum 50% match (score >= 40)
    if not best_segment or best_score < 40:
        return None, None
    
    transcript_span = {
        "start_ms": best_segment.start_ms,
        "end_ms": best_segment.end_ms,
        "segment_ids": [best_segment.id]
    }
    
    speaker = getattr(best_segment, 'speaker', None) or getattr(best_segment, 'speaker_id', None)
    
    return transcript_span, speaker


def backfill_transcript_spans(dry_run: bool = True, limit: int = None):
    """Backfill transcript_span for tasks that have evidence_quote but no span."""
    
    # Note: JSONB null checks can be tricky - get all tasks and filter in Python
    stmt = select(Task).where(Task.deleted_at.is_(None))
    all_tasks = db.session.execute(stmt).scalars().all()
    
    # Filter in Python to avoid JSONB null comparison issues
    tasks = [
        t for t in all_tasks 
        if t.extraction_context is not None and t.transcript_span is None
    ]
    
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
        
        # Fallback: use first segment if no match found (still links to transcript start)
        used_fallback = False
        if not transcript_span or transcript_span.get("start_ms") is None:
            first_seg = segments[0] if segments else None
            if first_seg and first_seg.start_ms is not None:
                transcript_span = {
                    "start_ms": first_seg.start_ms,
                    "end_ms": first_seg.end_ms,
                    "segment_ids": [first_seg.id],
                    "match_type": "fallback_first_segment"
                }
                speaker = getattr(first_seg, 'speaker', None) or getattr(first_seg, 'speaker_id', None)
                used_fallback = True
            else:
                skipped_no_match += 1
                if not dry_run:
                    print(f"  Task {task.id}: No match for '{evidence_quote[:60]}...'")
                continue
        
        match_type = "(fallback to start)" if used_fallback else "(matched)"
        print(f"\nTask {task.id}: '{task.title[:50]}...'")
        print(f"  Quote: '{evidence_quote[:80]}...'")
        print(f"  Span: {transcript_span['start_ms']}ms - {transcript_span['end_ms']}ms {match_type}")
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
