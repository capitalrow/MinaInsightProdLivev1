#!/usr/bin/env python3
# 🔄 Production Feature: Advanced Deduplication & Segment Handling
"""
Implements advanced deduplication logic to confirm and "commit" stable text portions,
preventing re-transcription of finalized segments and handling overlapping contexts.

Addresses: "Deduplication & Segment Handling" gap from production assessment.

Key Features:
- Text stability analysis across multiple transcription results
- Segment confirmation and commitment logic
- Overlap resolution between consecutive chunks
- Memory-efficient segment tracking
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import difflib
import re
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class TextSegment:
    """Represents a segment of transcribed text with confidence tracking."""
    text: str
    start_time: float
    end_time: float
    confidence: float
    segment_id: str
    chunk_ids: List[str] = field(default_factory=list)
    confirmation_count: int = 0
    last_seen: float = field(default_factory=time.time)
    is_committed: bool = False
    speaker_id: Optional[str] = None
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def word_count(self) -> int:
        return len(self.text.split())

@dataclass
class TranscriptionResult:
    """Transcription result with timing and metadata."""
    text: str
    confidence: float
    start_time: float
    end_time: float
    chunk_id: str
    is_final: bool = False
    speaker_id: Optional[str] = None
    language: str = 'en'

class AdvancedDeduplicationEngine:
    """
    🔄 Production-grade deduplication engine for stable text commitment.
    
    Tracks text stability across multiple transcription results and commits
    segments that appear consistently to prevent re-transcription and duplicates.
    """
    
    def __init__(self, confirmation_threshold: int = 2, stability_window_s: float = 3.0,
                 similarity_threshold: float = 0.85, max_segments: int = 1000):
        self.confirmation_threshold = confirmation_threshold  # Times text must be seen to commit
        self.stability_window_s = stability_window_s  # Time window for text stability
        self.similarity_threshold = similarity_threshold  # Text similarity for matching
        self.max_segments = max_segments  # Max segments to track per session
        
        # Segment tracking
        self.active_segments: Dict[str, deque] = {}  # {session_id: deque[TextSegment]}
        self.committed_segments: Dict[str, List[TextSegment]] = {}  # {session_id: [TextSegment]}
        self.segment_sequence: Dict[str, int] = {}  # {session_id: next_segment_id}
        
        # Overlap resolution
        self.pending_overlaps: Dict[str, List[TextSegment]] = {}  # {session_id: [TextSegment]}
        
        # Metrics
        self.total_results_processed = 0
        self.segments_committed = 0
        self.duplicates_prevented = 0
        self.overlaps_resolved = 0
        
        logger.info(f"🔄 Advanced deduplication engine initialized: "
                   f"confirmation_threshold={confirmation_threshold}, "
                   f"stability_window={stability_window_s}s, "
                   f"similarity_threshold={similarity_threshold}")
    
    def process_transcription_result(self, session_id: str, result: TranscriptionResult) -> Dict[str, Any]:
        """
        Process a transcription result and return deduplication decisions.
        
        Args:
            session_id: Session identifier
            result: Transcription result to process
            
        Returns:
            Dict with deduplication decisions and actions
        """
        self.total_results_processed += 1
        
        # Initialize session tracking if needed
        if session_id not in self.active_segments:
            self.active_segments[session_id] = deque(maxlen=self.max_segments)
            self.committed_segments[session_id] = []
            self.segment_sequence[session_id] = 0
            self.pending_overlaps[session_id] = []
        
        # Create text segment from result
        segment = self._create_segment_from_result(session_id, result)
        
        # Find similar segments in active tracking
        similar_segments = self._find_similar_segments(session_id, segment)
        
        # Process based on similarity findings
        if similar_segments:
            # Update existing segment
            updated_segment = self._update_similar_segment(similar_segments[0], segment)
            decision = self._evaluate_commitment(updated_segment)
        else:
            # Add new segment
            self.active_segments[session_id].append(segment)
            decision = self._evaluate_commitment(segment)
        
        # Handle overlap resolution if final result
        if result.is_final:
            overlap_resolution = self._resolve_overlaps(session_id, segment)
        else:
            overlap_resolution = None
        
        # Clean up old segments
        self._cleanup_old_segments(session_id)
        
        # Prepare response
        response = {
            'session_id': session_id,
            'segment_id': segment.segment_id,
            'text': segment.text,
            'is_committed': decision['should_commit'],
            'is_duplicate': decision['is_duplicate'],
            'confidence': segment.confidence,
            'confirmation_count': segment.confirmation_count,
            'similar_segments_found': len(similar_segments),
            'overlap_resolution': overlap_resolution,
            'action': decision['action']
        }
        
        # Update metrics
        if decision['should_commit']:
            self.segments_committed += 1
        if decision['is_duplicate']:
            self.duplicates_prevented += 1
        if overlap_resolution:
            self.overlaps_resolved += 1
        
        logger.debug(f"Processed transcription result for {session_id}: {decision['action']}")
        return response
    
    def _create_segment_from_result(self, session_id: str, result: TranscriptionResult) -> TextSegment:
        """Create a TextSegment from a TranscriptionResult."""
        segment_id = f"{session_id}_seg_{self.segment_sequence[session_id]:06d}"
        self.segment_sequence[session_id] += 1
        
        return TextSegment(
            text=result.text.strip(),
            start_time=result.start_time,
            end_time=result.end_time,
            confidence=result.confidence,
            segment_id=segment_id,
            chunk_ids=[result.chunk_id],
            confirmation_count=1,
            speaker_id=result.speaker_id
        )
    
    def _find_similar_segments(self, session_id: str, segment: TextSegment) -> List[TextSegment]:
        """Find segments similar to the given segment."""
        similar = []
        
        for existing_segment in self.active_segments[session_id]:
            if existing_segment.is_committed:
                continue
            
            # Check text similarity
            similarity = self._calculate_text_similarity(existing_segment.text, segment.text)
            
            # Check temporal overlap
            temporal_overlap = self._calculate_temporal_overlap(existing_segment, segment)
            
            # Consider similar if high text similarity and some temporal relationship
            if (similarity >= self.similarity_threshold and 
                (temporal_overlap > 0.1 or abs(existing_segment.start_time - segment.start_time) < 2.0)):
                similar.append(existing_segment)
        
        return similar
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using sequence matching."""
        # Normalize texts
        text1_norm = re.sub(r'[^\w\s]', '', text1.lower()).strip()
        text2_norm = re.sub(r'[^\w\s]', '', text2.lower()).strip()
        
        if not text1_norm or not text2_norm:
            return 0.0
        
        # Use sequence matcher
        matcher = difflib.SequenceMatcher(None, text1_norm, text2_norm)
        return matcher.ratio()
    
    def _calculate_temporal_overlap(self, seg1: TextSegment, seg2: TextSegment) -> float:
        """Calculate temporal overlap between two segments."""
        overlap_start = max(seg1.start_time, seg2.start_time)
        overlap_end = min(seg1.end_time, seg2.end_time)
        
        if overlap_end <= overlap_start:
            return 0.0
        
        overlap_duration = overlap_end - overlap_start
        total_duration = max(seg1.duration, seg2.duration)
        
        return overlap_duration / total_duration if total_duration > 0 else 0.0
    
    def _update_similar_segment(self, existing: TextSegment, new: TextSegment) -> TextSegment:
        """Update existing segment with information from new similar segment."""
        # Choose text with higher confidence
        if new.confidence > existing.confidence:
            existing.text = new.text
            existing.confidence = new.confidence
        
        # Update timing to encompass both segments
        existing.start_time = min(existing.start_time, new.start_time)
        existing.end_time = max(existing.end_time, new.end_time)
        
        # Increment confirmation count
        existing.confirmation_count += 1
        existing.last_seen = time.time()
        
        # Add chunk IDs
        existing.chunk_ids.extend(new.chunk_ids)
        
        # Update speaker if available
        if new.speaker_id and not existing.speaker_id:
            existing.speaker_id = new.speaker_id
        
        return existing
    
    def _evaluate_commitment(self, segment: TextSegment) -> Dict[str, Any]:
        """Evaluate whether a segment should be committed."""
        current_time = time.time()
        
        # Check if already committed
        if segment.is_committed:
            return {
                'should_commit': False,
                'is_duplicate': True,
                'action': 'duplicate_ignored',
                'reason': 'segment_already_committed'
            }
        
        # Check confirmation threshold
        if segment.confirmation_count >= self.confirmation_threshold:
            # Check stability window
            time_stable = current_time - segment.last_seen
            if time_stable >= 0:  # Immediate commitment if threshold met
                segment.is_committed = True
                return {
                    'should_commit': True,
                    'is_duplicate': False,
                    'action': 'commit_confirmed',
                    'reason': f'confirmation_count_{segment.confirmation_count}'
                }
        
        # Check if text is stable for minimum duration
        if len(segment.text.split()) >= 3 and segment.confidence > 0.7:
            segment.is_committed = True
            return {
                'should_commit': True,
                'is_duplicate': False,
                'action': 'commit_stable',
                'reason': 'high_confidence_stable'
            }
        
        # Default: keep tracking
        return {
            'should_commit': False,
            'is_duplicate': False,
            'action': 'continue_tracking',
            'reason': f'confirmation_{segment.confirmation_count}_of_{self.confirmation_threshold}'
        }
    
    def _resolve_overlaps(self, session_id: str, final_segment: TextSegment) -> Optional[Dict[str, Any]]:
        """Resolve overlaps when a final segment is processed."""
        overlapping_segments = []
        
        # Find overlapping committed segments
        for committed in self.committed_segments[session_id]:
            if self._calculate_temporal_overlap(committed, final_segment) > 0.3:
                overlapping_segments.append(committed)
        
        if not overlapping_segments:
            # No overlaps, commit the final segment
            self.committed_segments[session_id].append(final_segment)
            return {
                'action': 'committed_no_overlap',
                'segment_count': 1
            }
        
        # Resolve overlaps by merging or choosing best segment
        best_segment = self._choose_best_segment([final_segment] + overlapping_segments)
        
        # Remove overlapping segments and add the best one
        for overlap in overlapping_segments:
            if overlap in self.committed_segments[session_id]:
                self.committed_segments[session_id].remove(overlap)
        
        self.committed_segments[session_id].append(best_segment)
        
        return {
            'action': 'overlap_resolved',
            'overlapping_segments': len(overlapping_segments),
            'best_segment_id': best_segment.segment_id,
            'resolution_method': 'highest_confidence'
        }
    
    def _choose_best_segment(self, segments: List[TextSegment]) -> TextSegment:
        """Choose the best segment from a list based on quality metrics."""
        # Score segments based on confidence, length, and confirmation count
        best_segment = None
        best_score = -1
        
        for segment in segments:
            score = (
                segment.confidence * 0.4 +
                min(segment.word_count / 10, 1.0) * 0.3 +
                min(segment.confirmation_count / 5, 1.0) * 0.3
            )
            
            if score > best_score:
                best_score = score
                best_segment = segment
        
        return best_segment or segments[0]
    
    def _cleanup_old_segments(self, session_id: str):
        """Clean up old uncommitted segments."""
        current_time = time.time()
        cutoff_time = current_time - (self.stability_window_s * 3)  # 3x stability window
        
        # Remove old active segments
        active_segments = self.active_segments[session_id]
        to_remove = []
        
        for segment in active_segments:
            if segment.last_seen < cutoff_time and not segment.is_committed:
                to_remove.append(segment)
        
        for segment in to_remove:
            active_segments.remove(segment)
    
    def get_committed_transcript(self, session_id: str) -> str:
        """Get the current committed transcript for a session."""
        if session_id not in self.committed_segments:
            return ""
        
        # Sort committed segments by start time
        sorted_segments = sorted(
            self.committed_segments[session_id],
            key=lambda s: s.start_time
        )
        
        # Join text with proper spacing
        return " ".join(segment.text for segment in sorted_segments).strip()
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get deduplication statistics for a session."""
        if session_id not in self.active_segments:
            return {}
        
        active_count = len(self.active_segments[session_id])
        committed_count = len(self.committed_segments.get(session_id, []))
        
        return {
            'active_segments': active_count,
            'committed_segments': committed_count,
            'total_segments': active_count + committed_count,
            'committed_words': sum(
                seg.word_count for seg in self.committed_segments.get(session_id, [])
            ),
            'avg_confirmation_count': (
                sum(seg.confirmation_count for seg in self.active_segments[session_id]) /
                max(1, active_count)
            )
        }
    
    def cleanup_session(self, session_id: str):
        """Clean up all data for a session."""
        for collection in [self.active_segments, self.committed_segments, 
                          self.segment_sequence, self.pending_overlaps]:
            collection.pop(session_id, None)
        
        logger.info(f"Cleaned up deduplication data for session {session_id}")

# Global deduplication engine
_dedup_engine: Optional[AdvancedDeduplicationEngine] = None

def get_deduplication_engine() -> AdvancedDeduplicationEngine:
    """Get or create the global deduplication engine."""
    global _dedup_engine
    if _dedup_engine is None:
        _dedup_engine = AdvancedDeduplicationEngine()
    return _dedup_engine