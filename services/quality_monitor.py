# 🔬 **FIX PACK 4: Quality Assurance and Testing Components**

import time
import asyncio
import statistics
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Callable
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class QualityMetric(Enum):
    WER = "word_error_rate"
    CER = "character_error_rate"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    CONFIDENCE_CALIBRATION = "confidence_calibration"
    TEMPORAL_ALIGNMENT = "temporal_alignment"
    LINGUISTIC_QUALITY = "linguistic_quality"

@dataclass
class QualityResult:
    """Comprehensive quality analysis result."""
    overall_score: float
    confidence_interval: Tuple[float, float]
    metrics: Dict[str, float]
    details: Dict[str, Any]
    recommendations: List[str]
    timestamp: float

class AdvancedQualityAnalyzer:
    """ML-powered quality analysis for transcription results."""
    
    def __init__(self):
        self.quality_models = self._load_quality_models()
        self.benchmark_datasets = self._load_benchmarks()
        self.quality_history = defaultdict(lambda: deque(maxlen=1000))
        self.alert_thresholds = {
            QualityMetric.WER: 0.35,
            QualityMetric.CER: 0.25,
            QualityMetric.SEMANTIC_SIMILARITY: 0.8,
            QualityMetric.CONFIDENCE_CALIBRATION: 0.85,
            QualityMetric.TEMPORAL_ALIGNMENT: 0.2  # Max 200ms drift
        }
        
    def analyze_transcription_quality(self, audio_file: Optional[bytes], 
                                    transcript: str, metadata: Dict[str, Any]) -> QualityResult:
        """Multi-dimensional quality analysis of transcription."""
        start_time = time.time()
        
        # Run all quality metrics
        metrics = {}
        details = {}
        
        # 1. Accuracy Metrics (if reference available)
        if metadata.get('reference_transcript'):
            wer = self._calculate_wer(transcript, metadata['reference_transcript'])
            cer = self._calculate_cer(transcript, metadata['reference_transcript'])
            semantic_sim = self._calculate_semantic_similarity(transcript, metadata['reference_transcript'])
            
            metrics.update({
                QualityMetric.WER.value: wer,
                QualityMetric.CER.value: cer,
                QualityMetric.SEMANTIC_SIMILARITY.value: semantic_sim
            })
        
        # 2. Linguistic Quality Analysis
        linguistic_quality = self._analyze_linguistic_quality(transcript)
        metrics[QualityMetric.LINGUISTIC_QUALITY.value] = linguistic_quality['overall_score']
        details['linguistic_analysis'] = linguistic_quality
        
        # 3. Temporal Alignment Analysis
        if metadata.get('timing_info'):
            temporal_metrics = self._analyze_temporal_alignment(transcript, metadata['timing_info'])
            metrics[QualityMetric.TEMPORAL_ALIGNMENT.value] = temporal_metrics['drift_ms']
            details['temporal_analysis'] = temporal_metrics
        
        # 4. Confidence Calibration Analysis
        if metadata.get('confidence_scores'):
            conf_calibration = self._analyze_confidence_calibration(
                transcript, metadata['confidence_scores'], metadata.get('reference_transcript')
            )
            metrics[QualityMetric.CONFIDENCE_CALIBRATION.value] = conf_calibration['correlation']
            details['confidence_analysis'] = conf_calibration
        
        # 5. Robustness Analysis (if audio available)
        if audio_file:
            robustness_metrics = self._analyze_robustness(audio_file, transcript)
            details['robustness_analysis'] = robustness_metrics
        
        # Calculate overall quality score with confidence intervals
        overall_score, confidence_interval = self._calculate_overall_quality(metrics)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, details)
        
        # Record in history
        result = QualityResult(
            overall_score=overall_score,
            confidence_interval=confidence_interval,
            metrics=metrics,
            details=details,
            recommendations=recommendations,
            timestamp=time.time()
        )
        
        self.quality_history['overall'].append(result)
        
        logger.info(f"Quality analysis completed in {(time.time() - start_time)*1000:.1f}ms: {overall_score:.3f}")
        return result
    
    def _calculate_wer(self, hypothesis: str, reference: str) -> float:
        """Calculate Word Error Rate using dynamic programming."""
        hyp_words = hypothesis.strip().lower().split()
        ref_words = reference.strip().lower().split()
        
        # Dynamic programming matrix for edit distance
        d = np.zeros((len(ref_words) + 1, len(hyp_words) + 1))
        
        # Initialize first row and column
        for i in range(len(ref_words) + 1):
            d[i, 0] = i
        for j in range(len(hyp_words) + 1):
            d[0, j] = j
        
        # Fill the matrix
        for i in range(1, len(ref_words) + 1):
            for j in range(1, len(hyp_words) + 1):
                if ref_words[i-1] == hyp_words[j-1]:
                    d[i, j] = d[i-1, j-1]  # No operation needed
                else:
                    d[i, j] = min(
                        d[i-1, j] + 1,    # Deletion
                        d[i, j-1] + 1,    # Insertion
                        d[i-1, j-1] + 1   # Substitution
                    )
        
        # WER is edit distance divided by reference length
        wer = d[len(ref_words), len(hyp_words)] / len(ref_words) if ref_words else 0
        return min(wer, 1.0)  # Cap at 1.0
    
    def _calculate_cer(self, hypothesis: str, reference: str) -> float:
        """Calculate Character Error Rate."""
        hyp_chars = list(hypothesis.lower().replace(' ', ''))
        ref_chars = list(reference.lower().replace(' ', ''))
        
        # Similar DP approach as WER but for characters
        d = np.zeros((len(ref_chars) + 1, len(hyp_chars) + 1))
        
        for i in range(len(ref_chars) + 1):
            d[i, 0] = i
        for j in range(len(hyp_chars) + 1):
            d[0, j] = j
        
        for i in range(1, len(ref_chars) + 1):
            for j in range(1, len(hyp_chars) + 1):
                if ref_chars[i-1] == hyp_chars[j-1]:
                    d[i, j] = d[i-1, j-1]
                else:
                    d[i, j] = min(d[i-1, j] + 1, d[i, j-1] + 1, d[i-1, j-1] + 1)
        
        cer = d[len(ref_chars), len(hyp_chars)] / len(ref_chars) if ref_chars else 0
        return min(cer, 1.0)
    
    def _calculate_semantic_similarity(self, hypothesis: str, reference: str) -> float:
        """Calculate semantic similarity using simple word overlap (can be enhanced with embeddings)."""
        hyp_words = set(hypothesis.lower().split())
        ref_words = set(reference.lower().split())
        
        if not ref_words:
            return 0.0
        
        intersection = hyp_words.intersection(ref_words)
        union = hyp_words.union(ref_words)
        
        # Jaccard similarity as baseline (can be enhanced with word embeddings)
        return len(intersection) / len(union) if union else 0.0
    
    def _analyze_linguistic_quality(self, transcript: str) -> Dict[str, Any]:
        """Analyze linguistic quality of the transcript."""
        words = transcript.strip().split()
        sentences = [s.strip() for s in transcript.split('.') if s.strip()]
        
        # Basic linguistic metrics
        avg_word_length = statistics.mean(len(word) for word in words) if words else 0
        avg_sentence_length = statistics.mean(len(s.split()) for s in sentences) if sentences else 0
        
        # Repetition detection
        word_counts = defaultdict(int)
        for word in words:
            word_counts[word.lower()] += 1
        
        repetition_score = sum(count - 1 for count in word_counts.values()) / len(words) if words else 0
        
        # Fluency indicators
        has_punctuation = any(p in transcript for p in '.!?')
        capitalization_score = sum(1 for s in sentences if s and s[0].isupper()) / len(sentences) if sentences else 0
        
        # Overall linguistic quality score
        quality_factors = [
            1.0 - min(repetition_score, 0.5) * 2,  # Penalize repetition
            1.0 if has_punctuation else 0.7,       # Reward proper punctuation
            capitalization_score,                   # Reward proper capitalization
            min(avg_word_length / 5.0, 1.0),      # Optimal word length around 5 chars
            min(avg_sentence_length / 15.0, 1.0)   # Optimal sentence length around 15 words
        ]
        
        overall_score = statistics.mean(quality_factors)
        
        return {
            'overall_score': overall_score,
            'avg_word_length': avg_word_length,
            'avg_sentence_length': avg_sentence_length,
            'repetition_score': repetition_score,
            'has_punctuation': has_punctuation,
            'capitalization_score': capitalization_score,
            'word_count': len(words),
            'sentence_count': len(sentences)
        }
    
    def _analyze_temporal_alignment(self, transcript: str, timing_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze temporal alignment accuracy."""
        if not timing_info:
            return {'drift_ms': 0, 'alignment_score': 1.0}
        
        # Calculate timestamp drift
        drift_values = []
        for timing in timing_info:
            expected_time = timing.get('expected_timestamp', 0)
            actual_time = timing.get('actual_timestamp', 0)
            drift_ms = abs(expected_time - actual_time) * 1000
            drift_values.append(drift_ms)
        
        avg_drift = statistics.mean(drift_values) if drift_values else 0
        max_drift = max(drift_values) if drift_values else 0
        
        # Alignment score (1.0 = perfect, 0.0 = terrible)
        alignment_score = max(0, 1.0 - (avg_drift / 1000.0))  # 1s = 0 score
        
        return {
            'drift_ms': avg_drift,
            'max_drift_ms': max_drift,
            'alignment_score': alignment_score,
            'timing_points': len(timing_info)
        }
    
    def _analyze_confidence_calibration(self, transcript: str, confidence_scores: List[float], 
                                      reference: Optional[str] = None) -> Dict[str, Any]:
        """Analyze how well confidence scores correlate with actual accuracy."""
        if not confidence_scores:
            return {'correlation': 0.5}
        
        avg_confidence = statistics.mean(confidence_scores)
        confidence_variance = statistics.variance(confidence_scores) if len(confidence_scores) > 1 else 0
        
        calibration_result = {
            'avg_confidence': avg_confidence,
            'confidence_variance': confidence_variance,
            'min_confidence': min(confidence_scores),
            'max_confidence': max(confidence_scores)
        }
        
        # If we have reference, calculate actual accuracy correlation
        if reference:
            # Simple correlation: higher confidence should correlate with lower WER
            words = transcript.split()
            ref_words = reference.split()
            
            if len(confidence_scores) == len(words) and len(words) > 0:
                # Calculate per-word accuracy (simplified)
                word_accuracies = []
                for i, (word, ref_word) in enumerate(zip(words, ref_words[:len(words)])):
                    accuracy = 1.0 if word.lower() == ref_word.lower() else 0.0
                    word_accuracies.append(accuracy)
                
                # Calculate correlation between confidence and accuracy
                if len(word_accuracies) > 1:
                    try:
                        correlation = np.corrcoef(confidence_scores, word_accuracies)[0, 1]
                        correlation = 0 if np.isnan(correlation) else correlation
                    except:
                        correlation = 0.5
                else:
                    correlation = 0.5
                
                calibration_result['correlation'] = max(0, correlation)
        else:
            # Without reference, use heuristics
            calibration_result['correlation'] = 0.5  # Neutral
        
        return calibration_result
    
    def _analyze_robustness(self, audio_file: bytes, transcript: str) -> Dict[str, Any]:
        """Analyze robustness under different audio conditions."""
        # Placeholder for audio quality analysis
        # In a real implementation, you would analyze:
        # - SNR (Signal-to-Noise Ratio)
        # - Audio clarity metrics
        # - Background noise levels
        # - Frequency response
        
        return {
            'audio_quality_score': 0.8,  # Placeholder
            'snr_estimate': 15.0,        # dB
            'noise_level': 0.2,          # 0-1 scale
            'clarity_score': 0.85        # 0-1 scale
        }
    
    def _calculate_overall_quality(self, metrics: Dict[str, float]) -> Tuple[float, Tuple[float, float]]:
        """Calculate overall quality score with confidence intervals."""
        if not metrics:
            return 0.5, (0.4, 0.6)
        
        # Weight different metrics
        weights = {
            QualityMetric.WER.value: 0.3,
            QualityMetric.CER.value: 0.2,
            QualityMetric.SEMANTIC_SIMILARITY.value: 0.2,
            QualityMetric.CONFIDENCE_CALIBRATION.value: 0.15,
            QualityMetric.TEMPORAL_ALIGNMENT.value: 0.1,
            QualityMetric.LINGUISTIC_QUALITY.value: 0.05
        }
        
        # Calculate weighted average
        total_score = 0
        total_weight = 0
        
        for metric, value in metrics.items():
            weight = weights.get(metric, 0.1)  # Default weight
            
            # Convert metrics to 0-1 scale (higher = better)
            if metric in [QualityMetric.WER.value, QualityMetric.CER.value]:
                normalized_value = 1.0 - min(value, 1.0)  # Lower error rate = better
            elif metric == QualityMetric.TEMPORAL_ALIGNMENT.value:
                normalized_value = max(0, 1.0 - (value / 500.0))  # Lower drift = better
            else:
                normalized_value = max(0, min(value, 1.0))  # Use value as-is
            
            total_score += normalized_value * weight
            total_weight += weight
        
        overall_score = total_score / total_weight if total_weight > 0 else 0.5
        
        # Calculate confidence interval (simplified)
        variance = 0.1  # Placeholder for actual variance calculation
        std_error = variance ** 0.5
        confidence_interval = (
            max(0, overall_score - 1.96 * std_error),
            min(1, overall_score + 1.96 * std_error)
        )
        
        return overall_score, confidence_interval
    
    def _generate_recommendations(self, metrics: Dict[str, float], 
                                details: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on quality analysis."""
        recommendations = []
        
        # WER-based recommendations
        if QualityMetric.WER.value in metrics:
            wer = metrics[QualityMetric.WER.value]
            if wer > 0.4:
                recommendations.append("High word error rate detected. Consider improving audio quality or adjusting confidence thresholds.")
            elif wer > 0.2:
                recommendations.append("Moderate word error rate. Monitor for specific problematic words or speakers.")
        
        # Linguistic quality recommendations
        if 'linguistic_analysis' in details:
            ling = details['linguistic_analysis']
            if ling.get('repetition_score', 0) > 0.3:
                recommendations.append("High repetition detected. Consider enhancing repetition filters.")
            if not ling.get('has_punctuation', True):
                recommendations.append("Missing punctuation. Consider improving sentence boundary detection.")
        
        # Confidence calibration recommendations  
        if QualityMetric.CONFIDENCE_CALIBRATION.value in metrics:
            correlation = metrics[QualityMetric.CONFIDENCE_CALIBRATION.value]
            if correlation < 0.7:
                recommendations.append("Poor confidence calibration. Consider retraining confidence estimation.")
        
        # Temporal alignment recommendations
        if QualityMetric.TEMPORAL_ALIGNMENT.value in metrics:
            drift = metrics[QualityMetric.TEMPORAL_ALIGNMENT.value]
            if drift > 200:  # 200ms
                recommendations.append("High temporal drift detected. Consider improving timestamp accuracy.")
        
        if not recommendations:
            recommendations.append("Quality metrics look good. Continue monitoring for consistency.")
        
        return recommendations
    
    def _load_quality_models(self) -> Dict[str, Any]:
        """Load pre-trained quality assessment models."""
        # Placeholder for loading actual ML models
        return {}
    
    def _load_benchmarks(self) -> Dict[str, Any]:
        """Load benchmark datasets for quality comparison."""
        # Placeholder for loading benchmark data
        return {}
    
    def get_quality_trend(self, metric: QualityMetric, window_minutes: int = 60) -> Dict[str, Any]:
        """Get quality trend analysis for a specific metric."""
        current_time = time.time()
        cutoff_time = current_time - (window_minutes * 60)
        
        # Filter recent results
        recent_results = [
            result for result in self.quality_history['overall']
            if result.timestamp >= cutoff_time and metric.value in result.metrics
        ]
        
        if not recent_results:
            return {'trend': 'no_data', 'values': []}
        
        values = [result.metrics[metric.value] for result in recent_results]
        timestamps = [result.timestamp for result in recent_results]
        
        # Calculate trend
        if len(values) > 1:
            # Simple linear trend
            time_diffs = np.array(timestamps) - timestamps[0]
            correlation = np.corrcoef(time_diffs, values)[0, 1] if len(values) > 1 else 0
            
            if correlation > 0.1:
                trend = 'improving'
            elif correlation < -0.1:
                trend = 'degrading'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'values': values,
            'timestamps': timestamps,
            'current_value': values[-1] if values else 0,
            'avg_value': statistics.mean(values) if values else 0,
            'min_value': min(values) if values else 0,
            'max_value': max(values) if values else 0,
            'sample_count': len(values)
        }

class RealTimeQualityMonitor:
    """Real-time quality monitoring during live transcription sessions."""
    
    def __init__(self, quality_analyzer: AdvancedQualityAnalyzer):
        self.quality_analyzer = quality_analyzer
        self.active_sessions = {}
        self.alert_callbacks = []
        
    def start_monitoring_session(self, session_id: str, quality_thresholds: Dict[str, float] = None):
        """Start quality monitoring for a session."""
        self.active_sessions[session_id] = {
            'start_time': time.time(),
            'quality_samples': deque(maxlen=100),
            'alert_count': 0,
            'thresholds': quality_thresholds or {},
            'last_alert': 0
        }
        
        logger.info(f"Started quality monitoring for session {session_id}")
    
    def record_quality_sample(self, session_id: str, transcript: str, 
                            metadata: Dict[str, Any]):
        """Record a quality sample for real-time analysis."""
        if session_id not in self.active_sessions:
            return
        
        session_data = self.active_sessions[session_id]
        
        # Quick quality assessment (lighter than full analysis)
        quality_score = self._quick_quality_assessment(transcript, metadata)
        
        quality_sample = {
            'timestamp': time.time(),
            'quality_score': quality_score,
            'transcript_length': len(transcript.split()),
            'confidence': metadata.get('avg_confidence', 0),
            'transcript': transcript[:100]  # First 100 chars for debugging
        }
        
        session_data['quality_samples'].append(quality_sample)
        
        # Check for quality alerts
        self._check_quality_alerts(session_id, quality_sample)
    
    def _quick_quality_assessment(self, transcript: str, metadata: Dict[str, Any]) -> float:
        """Quick quality assessment for real-time monitoring."""
        if not transcript.strip():
            return 0.0
        
        # Basic quality indicators
        factors = []
        
        # 1. Confidence score
        confidence = metadata.get('avg_confidence', 0.5)
        factors.append(confidence)
        
        # 2. Repetition check
        words = transcript.lower().split()
        if len(words) > 1:
            consecutive_same = sum(1 for i in range(len(words)-1) 
                                 if words[i] == words[i+1])
            repetition_factor = 1.0 - min(consecutive_same / len(words), 0.5)
            factors.append(repetition_factor)
        
        # 3. Length reasonableness
        if 5 <= len(words) <= 50:  # Reasonable transcript length
            factors.append(1.0)
        else:
            factors.append(0.7)
        
        # 4. Character diversity
        if len(set(transcript.lower().replace(' ', ''))) > len(transcript) * 0.3:
            factors.append(1.0)
        else:
            factors.append(0.5)
        
        return statistics.mean(factors) if factors else 0.5
    
    def _check_quality_alerts(self, session_id: str, quality_sample: Dict[str, Any]):
        """Check if quality sample triggers any alerts."""
        session_data = self.active_sessions[session_id]
        current_time = time.time()
        
        # Don't alert too frequently
        if current_time - session_data['last_alert'] < 30:  # 30 second cooldown
            return
        
        quality_score = quality_sample['quality_score']
        confidence = quality_sample['confidence']
        
        # Quality degradation alert
        if quality_score < 0.3:
            self._trigger_alert(session_id, 'low_quality', {
                'quality_score': quality_score,
                'confidence': confidence,
                'transcript_sample': quality_sample['transcript']
            })
            session_data['last_alert'] = current_time
            session_data['alert_count'] += 1
        
        # Confidence alert
        elif confidence < 0.2:
            self._trigger_alert(session_id, 'low_confidence', {
                'quality_score': quality_score,
                'confidence': confidence,
                'transcript_sample': quality_sample['transcript']
            })
            session_data['last_alert'] = current_time
            session_data['alert_count'] += 1
    
    def _trigger_alert(self, session_id: str, alert_type: str, alert_data: Dict[str, Any]):
        """Trigger quality alert."""
        alert = {
            'session_id': session_id,
            'alert_type': alert_type,
            'timestamp': time.time(),
            'data': alert_data
        }
        
        logger.warning(f"Quality alert for session {session_id}: {alert_type} - {alert_data}")
        
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Quality alert callback failed: {e}")
    
    def add_alert_callback(self, callback: Callable):
        """Add callback for quality alerts."""
        self.alert_callbacks.append(callback)
    
    def get_session_quality_summary(self, session_id: str) -> Dict[str, Any]:
        """Get quality summary for a session."""
        if session_id not in self.active_sessions:
            return {}
        
        session_data = self.active_sessions[session_id]
        samples = list(session_data['quality_samples'])
        
        if not samples:
            return {'status': 'no_data'}
        
        quality_scores = [s['quality_score'] for s in samples]
        confidence_scores = [s['confidence'] for s in samples]
        
        return {
            'session_id': session_id,
            'duration_minutes': (time.time() - session_data['start_time']) / 60,
            'sample_count': len(samples),
            'avg_quality': statistics.mean(quality_scores),
            'min_quality': min(quality_scores),
            'max_quality': max(quality_scores),
            'avg_confidence': statistics.mean(confidence_scores),
            'alert_count': session_data['alert_count'],
            'quality_trend': 'improving' if len(quality_scores) > 5 and 
                           quality_scores[-3:] > quality_scores[:3] else 'stable',
            'last_sample_time': samples[-1]['timestamp']
        }