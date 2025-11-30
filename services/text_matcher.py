"""
Text Matcher Utility - Evidence-Based Task Validation

Validates that extracted tasks/insights actually exist in the source transcript
using fuzzy matching, keyword detection, and confidence scoring to prevent AI hallucination.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class TextMatcher:
    """
    Utility for validating extracted content against source transcript.
    Prevents AI hallucination by requiring evidence of extracted claims.
    """
    
    # Keywords that indicate task/action commitment
    ACTION_KEYWORDS = [
        'need to', 'needs to', 'have to', 'has to', 'must', 'should',
        'will', "i'll", "we'll", "you'll", 'going to', 'gonna',
        'action item', 'action:', 'task:', 'todo:', 'follow up',
        'assigned to', 'responsible for', 'take care of',
        'make sure', 'ensure', 'check', 'review', 'update',
        'create', 'build', 'implement', 'fix', 'resolve'
    ]
    
    # Keywords that indicate decisions
    DECISION_KEYWORDS = [
        'decided', 'decision', 'agreed', 'chose', 'selected',
        'going with', 'approved', 'confirmed', 'settled on',
        'concluded', 'determined', 'resolved to'
    ]
    
    # Keywords that indicate risks/concerns
    RISK_KEYWORDS = [
        'risk', 'concern', 'worried', 'problem', 'issue',
        'challenge', 'obstacle', 'blocker', 'threat',
        'might fail', 'could break', 'potential issue'
    ]
    
    def __init__(self):
        """Initialize TextMatcher with default configuration."""
        self.min_fuzzy_ratio = 0.6  # Minimum similarity ratio (0-1)
        self.min_keyword_matches = 1  # Minimum keywords that must match
    
    def validate_extraction(self, extracted_text: str, transcript: str, 
                          extraction_type: str = 'action') -> Dict:
        """
        Validate that extracted text has evidence in the transcript.
        
        Args:
            extracted_text: The text extracted by AI (task, decision, etc.)
            transcript: The full source transcript
            extraction_type: Type of extraction ('action', 'decision', 'risk')
            
        Returns:
            Dictionary with:
            - is_valid: bool indicating if extraction is validated
            - confidence_score: 0-100 score
            - evidence_quote: best matching quote from transcript
            - match_details: breakdown of what matched
        """
        # Normalize texts
        extracted_clean = self._normalize_text(extracted_text)
        transcript_clean = self._normalize_text(transcript)
        
        # Calculate confidence score (0-100)
        fuzzy_score = self._calculate_fuzzy_match(extracted_clean, transcript_clean)
        keyword_score = self._calculate_keyword_score(extracted_clean, transcript_clean, extraction_type)
        evidence_quote = self._find_best_evidence(extracted_clean, transcript)
        quote_score = 40 if evidence_quote else 0
        
        # Weighted confidence score (FIXED: More weight on fuzzy match)
        # - Fuzzy match is primary signal (does similar text exist in transcript?)
        # - Evidence quote is strong confirming signal
        # - Keywords are just supporting signal
        confidence_score = (
            fuzzy_score * 0.6 +      # 60% weight: fuzzy text similarity (PRIMARY)
            quote_score * 0.3 +      # 30% weight: found evidence quote (STRONG)
            keyword_score * 0.1      # 10% weight: keyword presence (SUPPORTING)
        )
        
        # Validation threshold: 50/100 (FIXED: More realistic threshold)
        # With new weighting:
        # - Perfect fuzzy match (100) alone = 60 points
        # - Good fuzzy (80) + evidence quote (40) = 48 + 12 = 60 points
        # - Hallucination (fuzzy 20, no quote) = 12 points (REJECTED)
        is_valid = confidence_score >= 50
        
        result = {
            'is_valid': is_valid,
            'confidence_score': round(confidence_score, 2),
            'evidence_quote': evidence_quote,
            'match_details': {
                'fuzzy_score': round(fuzzy_score, 2),
                'keyword_score': round(keyword_score, 2),
                'quote_score': quote_score,
                'extracted_length': len(extracted_text.split()),
                'has_evidence': bool(evidence_quote)
            }
        }
        
        logger.debug(f"Validation result for '{extracted_text[:50]}...': {result}")
        return result
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison: lowercase, remove extra whitespace."""
        if not text:
            return ""
        # Lowercase and normalize whitespace
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        return normalized
    
    def _calculate_fuzzy_match(self, extracted: str, transcript: str) -> float:
        """
        Calculate fuzzy match score using sliding window.
        
        Returns:
            Score 0-100 based on best substring match
        """
        if not extracted or not transcript:
            return 0.0
        
        # Extract key words (ignore common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        key_words = [w for w in extracted.split() if w not in stop_words and len(w) > 2]
        
        if not key_words:
            return 0.0
        
        # Check if key words appear in transcript
        words_found = sum(1 for word in key_words if word in transcript)
        word_match_ratio = words_found / len(key_words)
        
        # Sliding window to find best matching substring
        window_size = len(extracted)
        words = transcript.split()
        best_ratio = 0.0
        
        for i in range(len(words) - len(key_words) + 1):
            window = ' '.join(words[i:i + len(key_words) + 5])  # Allow some extra context
            ratio = SequenceMatcher(None, extracted, window).ratio()
            best_ratio = max(best_ratio, ratio)
        
        # Combine word presence and sequence matching
        fuzzy_score = (word_match_ratio * 0.7 + best_ratio * 0.3) * 100
        return min(fuzzy_score, 100.0)
    
    def _calculate_keyword_score(self, extracted: str, transcript: str, 
                                 extraction_type: str) -> float:
        """
        Calculate score based on presence of relevant keywords.
        
        Returns:
            Score 0-100 based on keyword matches
        """
        # Select relevant keywords based on type
        if extraction_type == 'action':
            keywords = self.ACTION_KEYWORDS
        elif extraction_type == 'decision':
            keywords = self.DECISION_KEYWORDS
        elif extraction_type == 'risk':
            keywords = self.RISK_KEYWORDS
        else:
            keywords = self.ACTION_KEYWORDS
        
        # Count keywords in extracted text
        extracted_keywords = [kw for kw in keywords if kw in extracted]
        
        if not extracted_keywords:
            # No action keywords in task - neutral score (not all tasks have keywords)
            return 50.0
        
        # FIXED: Score based on percentage of EXTRACTED keywords found in transcript
        # (Not percentage of entire keyword catalog)
        matching_keywords = [kw for kw in extracted_keywords if kw in transcript]
        
        if not matching_keywords:
            # Extracted text has keywords but none appear in transcript - suspicious
            return 0.0
        
        # Score = percentage of task's keywords that appear in transcript
        keyword_score = (len(matching_keywords) / len(extracted_keywords)) * 100
        return min(keyword_score, 100.0)
    
    def _find_best_evidence(self, extracted: str, transcript: str) -> Optional[str]:
        """
        Find the best matching quote from transcript as evidence.
        
        Returns:
            Best matching sentence/phrase from transcript, or None
        """
        if not extracted or not transcript:
            return None
        
        # Split transcript into sentences
        sentences = re.split(r'[.!?]+', transcript)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if not sentences:
            return None
        
        # Find sentence with highest similarity
        best_match = None
        best_ratio = 0.0
        
        extracted_words = set(self._normalize_text(extracted).split())
        
        for sentence in sentences:
            sentence_clean = self._normalize_text(sentence)
            sentence_words = set(sentence_clean.split())
            
            # Calculate word overlap
            if not sentence_words:
                continue
                
            overlap = len(extracted_words & sentence_words)
            overlap_ratio = overlap / len(extracted_words) if extracted_words else 0
            
            # Also check sequence similarity
            seq_ratio = SequenceMatcher(None, 
                                       self._normalize_text(extracted), 
                                       sentence_clean).ratio()
            
            # Combined score
            combined_ratio = overlap_ratio * 0.6 + seq_ratio * 0.4
            
            if combined_ratio > best_ratio and combined_ratio > 0.3:  # Minimum threshold
                best_ratio = combined_ratio
                best_match = sentence.strip()
        
        return best_match if best_ratio > 0.3 else None
    
    def validate_task_list(self, tasks: List[Dict], transcript: str) -> List[Dict]:
        """
        Validate a list of extracted tasks against transcript.
        
        Args:
            tasks: List of task dictionaries with 'text' or 'action' field
            transcript: Source transcript
            
        Returns:
            Filtered list containing only validated tasks with validation metadata
        """
        validated_tasks = []
        
        for i, task in enumerate(tasks):
            # Extract task text (handle different field names)
            task_text = task.get('text') or task.get('action') or task.get('title', '')
            
            if not task_text:
                logger.warning(f"Task {i} has no text field, skipping validation")
                continue
            
            # Validate against transcript
            validation = self.validate_extraction(task_text, transcript, 'action')
            
            # Only keep tasks that pass validation
            if validation['is_valid']:
                # Add validation metadata to task
                task_with_validation = task.copy()
                task_with_validation['validation'] = {
                    'confidence_score': validation['confidence_score'],
                    'evidence_quote': validation['evidence_quote'],
                    'validated': True
                }
                validated_tasks.append(task_with_validation)
                
                logger.info(f"✅ Task validated (score: {validation['confidence_score']}): {task_text[:60]}...")
            else:
                logger.warning(f"❌ Task REJECTED (score: {validation['confidence_score']}): {task_text[:60]}...")
                logger.debug(f"   Reason: No sufficient evidence in transcript")
        
        logger.info(f"Task validation: {len(validated_tasks)}/{len(tasks)} tasks passed")
        return validated_tasks
