"""
Voice Activity Detection Service - Phase 2 Cost Optimization

Uses WebRTC VAD for accurate speech detection to skip silent audio chunks,
reducing unnecessary OpenAI Whisper API calls and costs.

Key features:
- Multiple aggressiveness levels (0-3)
- Frame-based analysis for accuracy
- Integration with audio optimizer
"""

import logging
from typing import Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    logger.warning("⚠️ webrtcvad not available, using fallback energy-based VAD")


class VoiceActivityDetector:
    """
    WebRTC-based Voice Activity Detection for cost optimization.
    
    Aggressiveness levels:
    - 0: Least aggressive (more speech detected, fewer false negatives)
    - 1: Medium-low aggressiveness
    - 2: Medium-high aggressiveness
    - 3: Most aggressive (less speech detected, fewer false positives)
    
    For transcription, level 1-2 is recommended to avoid missing quiet speech.
    """
    
    SUPPORTED_SAMPLE_RATES = {8000, 16000, 32000, 48000}
    FRAME_DURATIONS_MS = {10, 20, 30}
    
    def __init__(self, aggressiveness: int = 2, sample_rate: int = 16000):
        """
        Initialize VAD with specified aggressiveness.
        
        Args:
            aggressiveness: VAD aggressiveness level (0-3)
            sample_rate: Audio sample rate in Hz
        """
        self.aggressiveness = min(3, max(0, aggressiveness))
        self.sample_rate = sample_rate
        self.vad = None
        
        if VAD_AVAILABLE and webrtcvad is not None:
            try:
                self.vad = webrtcvad.Vad(self.aggressiveness)
                logger.info(f"✅ WebRTC VAD initialized (aggressiveness={self.aggressiveness})")
            except Exception as e:
                logger.warning(f"⚠️ WebRTC VAD init failed: {e}")
        
        self.stats = {
            'total_chunks_analyzed': 0,
            'speech_chunks': 0,
            'silence_chunks': 0,
            'api_calls_saved': 0
        }
    
    def detect_speech(self, pcm_data: bytes, 
                      sample_rate: int = 16000,
                      frame_duration_ms: int = 30,
                      speech_threshold: float = 0.3) -> Tuple[bool, dict]:
        """
        Detect if audio contains speech.
        
        Args:
            pcm_data: 16-bit PCM audio data
            sample_rate: Sample rate in Hz
            frame_duration_ms: Frame duration (10, 20, or 30ms)
            speech_threshold: Ratio of speech frames required (0.0-1.0)
            
        Returns:
            Tuple of (has_speech: bool, analysis_details: dict)
        """
        self.stats['total_chunks_analyzed'] += 1
        
        if len(pcm_data) < 320:
            return False, {'reason': 'audio_too_short', 'bytes': len(pcm_data)}
        
        if self.vad and sample_rate in self.SUPPORTED_SAMPLE_RATES:
            result, details = self._webrtc_vad(pcm_data, sample_rate, frame_duration_ms, speech_threshold)
        else:
            result, details = self._energy_vad(pcm_data, sample_rate)
        
        if result:
            self.stats['speech_chunks'] += 1
        else:
            self.stats['silence_chunks'] += 1
            self.stats['api_calls_saved'] += 1
        
        return result, details
    
    def _webrtc_vad(self, pcm_data: bytes, 
                    sample_rate: int, 
                    frame_duration_ms: int,
                    speech_threshold: float) -> Tuple[bool, dict]:
        """WebRTC VAD analysis with frame-by-frame detection."""
        try:
            bytes_per_frame = int(sample_rate * 2 * frame_duration_ms / 1000)
            
            total_frames = len(pcm_data) // bytes_per_frame
            if total_frames == 0:
                return self._energy_vad(pcm_data, sample_rate)
            
            speech_frames = 0
            for i in range(total_frames):
                frame = pcm_data[i * bytes_per_frame:(i + 1) * bytes_per_frame]
                try:
                    if self.vad is not None and self.vad.is_speech(frame, sample_rate):
                        speech_frames += 1
                except Exception:
                    continue
            
            speech_ratio = speech_frames / total_frames if total_frames > 0 else 0
            has_speech = speech_ratio >= speech_threshold
            
            return has_speech, {
                'method': 'webrtc_vad',
                'total_frames': total_frames,
                'speech_frames': speech_frames,
                'speech_ratio': speech_ratio,
                'threshold': speech_threshold,
                'aggressiveness': self.aggressiveness
            }
            
        except Exception as e:
            logger.warning(f"⚠️ WebRTC VAD error, using fallback: {e}")
            return self._energy_vad(pcm_data, sample_rate)
    
    def _energy_vad(self, pcm_data: bytes, sample_rate: int) -> Tuple[bool, dict]:
        """Energy-based VAD fallback."""
        try:
            samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
            
            if len(samples) < 100:
                return False, {'reason': 'too_few_samples', 'count': len(samples)}
            
            rms = np.sqrt(np.mean(samples ** 2))
            peak = np.max(np.abs(samples))
            
            if rms < 1:
                return False, {'reason': 'near_silence', 'rms': float(rms)}
            
            db = 20 * np.log10(rms / 32768)
            
            zcr = np.sum(np.abs(np.diff(np.sign(samples)))) / (2 * len(samples))
            
            speech_threshold_db = -40
            has_speech = db > speech_threshold_db and zcr > 0.02 and zcr < 0.5
            
            return has_speech, {
                'method': 'energy_zcr',
                'rms': float(rms),
                'db': float(db),
                'peak': float(peak),
                'zcr': float(zcr),
                'threshold_db': speech_threshold_db
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Energy VAD error: {e}")
            return True, {'method': 'fallback', 'reason': str(e)}
    
    def get_stats(self) -> dict:
        """Get VAD statistics."""
        return {
            **self.stats,
            'webrtc_available': VAD_AVAILABLE,
            'aggressiveness': self.aggressiveness,
            'sample_rate': self.sample_rate
        }


voice_activity_detector = VoiceActivityDetector(aggressiveness=2)


def detect_speech(pcm_data: bytes, sample_rate: int = 16000) -> Tuple[bool, dict]:
    """Convenience function for speech detection."""
    return voice_activity_detector.detect_speech(pcm_data, sample_rate)


def get_vad_stats() -> dict:
    """Get VAD statistics."""
    return voice_activity_detector.get_stats()
