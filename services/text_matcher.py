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
        """Initialize TextMatcher with STRICT anti-hallucination configuration."""
        self.min_fuzzy_ratio = 0.75  # Minimum similarity ratio (0-1) - STRICT
        self.min_keyword_matches = 1  # Minimum keywords that must match
        self.min_evidence_quote_similarity = 0.80  # STRICT: Quote must be 80%+ similar to transcript
    
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
        
        # Weighted confidence score - STRICT anti-hallucination scoring
        # - Fuzzy match is primary signal (does similar text exist in transcript?)
        # - Evidence quote is strong confirming signal
        # - Keywords are just supporting signal
        confidence_score = (
            fuzzy_score * 0.7 +      # 70% weight: fuzzy text similarity (PRIMARY)
            quote_score * 0.2 +      # 20% weight: found evidence quote (SUPPORTING)
            keyword_score * 0.1      # 10% weight: keyword presence (MINOR)
        )
        
        # STRICT validation with EXPLICIT minimum threshold enforcement
        # Gate 1: Fuzzy match MUST exceed minimum ratio (hard requirement)
        fuzzy_ratio = fuzzy_score / 100.0
        meets_fuzzy_minimum = fuzzy_ratio >= self.min_fuzzy_ratio
        
        # Gate 2: Confidence score must meet threshold
        meets_confidence = confidence_score >= 60
        
        # BOTH gates must pass
        is_valid = meets_fuzzy_minimum and meets_confidence
        
        if not meets_fuzzy_minimum:
            logger.debug(f"[FUZZY_GATE_FAIL] Fuzzy ratio {fuzzy_ratio:.2f} < minimum {self.min_fuzzy_ratio}")
        
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
            # No action keywords in task - LOW score (tasks should have action language)
            # This penalizes vague/generic tasks without commitment language
            return 20.0
        
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
    
    def validate_evidence_quote(self, evidence_quote: str, transcript: str) -> Dict:
        """
        Validate that an AI-provided evidence quote actually appears in the transcript.
        
        This is CRITICAL for anti-hallucination: the AI must provide REAL quotes,
        not fabricated ones. Prefers exact substring matches.
        
        Args:
            evidence_quote: The quote the AI claims is from the transcript
            transcript: The actual source transcript
            
        Returns:
            Dictionary with:
            - is_valid: bool indicating if quote appears in transcript
            - similarity_score: 0-100 score
            - best_match: closest matching text from transcript
        """
        if not evidence_quote or not transcript:
            return {'is_valid': False, 'similarity_score': 0, 'best_match': None, 'match_type': 'missing'}
        
        quote_clean = self._normalize_text(evidence_quote)
        transcript_clean = self._normalize_text(transcript)
        
        # Check 1: EXACT substring match (PREFERRED - highest confidence)
        if quote_clean in transcript_clean:
            return {
                'is_valid': True,
                'similarity_score': 100.0,
                'best_match': evidence_quote,
                'match_type': 'exact'
            }
        
        # Check 2: Key phrase exact match (check if main words appear as substring)
        # This handles minor punctuation/casing differences
        quote_words = quote_clean.split()
        if len(quote_words) >= 4:
            # Check if core phrase (middle 80%) appears exactly
            core_start = len(quote_words) // 5
            core_end = len(quote_words) - core_start
            core_phrase = ' '.join(quote_words[core_start:core_end])
            
            if core_phrase in transcript_clean:
                return {
                    'is_valid': True,
                    'similarity_score': 95.0,
                    'best_match': evidence_quote,
                    'match_type': 'core_exact'
                }
        
        # Check 3: Fuzzy match with sliding window (STRICT - only for minor variations)
        transcript_words = transcript_clean.split()
        
        best_similarity = 0.0
        best_match = None
        
        # Slide through transcript looking for best match
        window_size = len(quote_words) + 3  # Allow some flexibility
        
        for i in range(max(1, len(transcript_words) - window_size + 1)):
            window = ' '.join(transcript_words[i:i + window_size])
            similarity = SequenceMatcher(None, quote_clean, window).ratio()
            
            if similarity > best_similarity:
                best_similarity = similarity
                # Get original text from transcript (preserve case)
                original_words = transcript.split()
                if i < len(original_words):
                    best_match = ' '.join(original_words[i:i + window_size])
        
        # STRICT threshold: 90% similarity required for fuzzy matches
        # (Only allows minor punctuation/word order differences)
        is_valid = best_similarity >= 0.90  # VERY STRICT
        
        return {
            'is_valid': is_valid,
            'similarity_score': round(best_similarity * 100, 2),
            'best_match': best_match,
            'match_type': 'fuzzy_high' if is_valid else 'no_match'
        }
    
    def validate_task_list(self, tasks: List[Dict], transcript: str) -> List[Dict]:
        """
        Validate a list of extracted tasks against transcript with STRICT evidence checking.
        
        Uses TWO-LAYER validation:
        1. Task text must have evidence in transcript (fuzzy match)
        2. AI-provided evidence_quote must actually appear in transcript (quote validation)
        
        Args:
            tasks: List of task dictionaries with 'text' or 'action' field
            transcript: Source transcript
            
        Returns:
            Filtered list containing only validated tasks with validation metadata
        """
        validated_tasks = []
        rejected_count = 0
        
        for i, task in enumerate(tasks):
            # Extract task text (handle different field names)
            task_text = task.get('text') or task.get('action') or task.get('title', '')
            evidence_quote = task.get('evidence_quote', '')
            
            if not task_text:
                logger.warning(f"[HALLUCINATION_CHECK] Task {i} has no text field, skipping")
                continue
            
            # LAYER 1: Validate task text against transcript
            text_validation = self.validate_extraction(task_text, transcript, 'action')
            
            # LAYER 2: Validate AI-provided evidence_quote (REQUIRED for anti-hallucination)
            if not evidence_quote:
                # STRICT: Require evidence quote - tasks without quotes are suspicious
                logger.warning(f"[NO_EVIDENCE_QUOTE] Task has no evidence quote - flagging as suspicious")
                quote_validation = {'is_valid': False, 'similarity_score': 0, 'match_type': 'missing'}
            else:
                quote_validation = self.validate_evidence_quote(evidence_quote, transcript)
                
                if not quote_validation['is_valid']:
                    logger.warning(f"[HALLUCINATION_DETECTED] Quote not found in transcript!")
                    logger.warning(f"   AI claimed: \"{evidence_quote[:80]}...\"")
                    logger.warning(f"   Best match: \"{quote_validation.get('best_match', 'None')[:80] if quote_validation.get('best_match') else 'None'}...\"")
                    logger.warning(f"   Similarity: {quote_validation['similarity_score']}%")
            
            # COMBINED VALIDATION: Both layers must pass
            # STRICT: Evidence quote is REQUIRED - reject if missing or invalid
            combined_valid = text_validation['is_valid'] and quote_validation['is_valid']
            
            if not quote_validation['is_valid']:
                if not evidence_quote:
                    logger.warning(f"[HALLUCINATION_REJECTED] Task rejected - no evidence quote provided (REQUIRED)")
                else:
                    logger.warning(f"[HALLUCINATION_REJECTED] Task rejected due to fabricated evidence quote")
            
            if combined_valid:
                # Add validation metadata to task
                task_with_validation = task.copy()
                task_with_validation['validation'] = {
                    'confidence_score': text_validation['confidence_score'],
                    'evidence_quote': text_validation['evidence_quote'] or evidence_quote,
                    'quote_verified': quote_validation['is_valid'],
                    'validated': True
                }
                validated_tasks.append(task_with_validation)
                
                logger.info(f"✅ [VALIDATED] Task (score: {text_validation['confidence_score']}): {task_text[:60]}...")
            else:
                rejected_count += 1
                logger.warning(f"❌ [REJECTED] Task (score: {text_validation['confidence_score']}): {task_text[:60]}...")
                logger.warning(f"   Evidence match: {quote_validation['similarity_score']}%")
        
        logger.info(f"[VALIDATION_SUMMARY] {len(validated_tasks)}/{len(tasks)} tasks passed, {rejected_count} rejected as hallucinations")
        return validated_tasks
