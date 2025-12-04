"""
Audio Payload Optimizer - Phase 2 Cost Optimization

Reduces API costs by optimizing audio payloads before sending to Whisper:
- Stereo to mono conversion (50% size reduction)
- Downsample to 16kHz (Whisper's native rate)
- Voice Activity Detection to skip silence
- Efficient format conversion
"""

import logging
import struct
from io import BytesIO
from typing import Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

WHISPER_OPTIMAL_SAMPLE_RATE = 16000
WHISPER_CHANNELS = 1
WHISPER_SAMPLE_WIDTH = 2


class AudioPayloadOptimizer:
    """
    Optimizes audio payloads to reduce OpenAI Whisper API costs.
    
    Key optimizations:
    1. Stereo → Mono: 50% size reduction
    2. Downsample to 16kHz: Whisper's native rate
    3. Skip silence: Reduce API calls with VAD
    """
    
    def __init__(self):
        self.stats = {
            'total_input_bytes': 0,
            'total_output_bytes': 0,
            'chunks_processed': 0,
            'chunks_skipped_silence': 0
        }
    
    def optimize_audio(self, audio_data: bytes, 
                       source_sample_rate: int = 48000,
                       source_channels: int = 2) -> Tuple[bytes, dict]:
        """
        Optimize audio payload for Whisper API.
        
        Args:
            audio_data: Raw audio bytes (WAV format preferred)
            source_sample_rate: Original sample rate
            source_channels: Original channel count
            
        Returns:
            Tuple of (optimized_wav_bytes, optimization_stats)
        """
        try:
            input_size = len(audio_data)
            self.stats['total_input_bytes'] += input_size
            
            if not self._is_valid_wav(audio_data):
                logger.debug("⚠️ Non-WAV format detected, skipping optimization (passthrough)")
                self.stats['total_output_bytes'] += input_size
                self.stats['chunks_processed'] += 1
                return audio_data, {
                    'skipped': False,
                    'optimizations': [],
                    'input_size': input_size,
                    'output_size': input_size,
                    'compression_ratio': 0,
                    'format': 'non-wav-passthrough',
                    'reason': 'Non-WAV format detected, optimization bypassed for safety'
                }
            
            pcm_data, detected_rate, detected_channels = self._parse_wav(audio_data)
            
            if detected_rate:
                source_sample_rate = detected_rate
            if detected_channels:
                source_channels = detected_channels
            
            optimizations_applied = []
            
            if source_channels == 2:
                pcm_data = self._stereo_to_mono(pcm_data)
                optimizations_applied.append('stereo_to_mono')
            
            if source_sample_rate != WHISPER_OPTIMAL_SAMPLE_RATE:
                pcm_data = self._resample(pcm_data, source_sample_rate, WHISPER_OPTIMAL_SAMPLE_RATE)
                optimizations_applied.append(f'resample_{source_sample_rate}_to_16000')
            
            has_speech = self._quick_vad_check(pcm_data)
            
            if not has_speech:
                self.stats['chunks_skipped_silence'] += 1
                return b'', {
                    'skipped': True,
                    'reason': 'silence_detected',
                    'input_size': input_size,
                    'output_size': 0,
                    'compression_ratio': 0
                }
            
            optimized_wav = self._create_optimized_wav(pcm_data)
            
            output_size = len(optimized_wav)
            self.stats['total_output_bytes'] += output_size
            self.stats['chunks_processed'] += 1
            
            compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
            
            return optimized_wav, {
                'skipped': False,
                'optimizations': optimizations_applied,
                'input_size': input_size,
                'output_size': output_size,
                'compression_ratio': compression_ratio,
                'sample_rate': WHISPER_OPTIMAL_SAMPLE_RATE,
                'channels': WHISPER_CHANNELS
            }
            
        except Exception as e:
            logger.error(f"❌ Audio optimization failed: {e}")
            return audio_data, {
                'skipped': False,
                'optimizations': [],
                'error': str(e),
                'fallback': True
            }
    
    def _is_valid_wav(self, audio_data: bytes) -> bool:
        """
        Check if audio data is a valid WAV file with PCM encoding.
        
        Returns False for:
        - Too short data
        - Non-RIFF/WAVE format (e.g., WebM, Opus, MP3)
        - Compressed WAV (non-PCM like MP3, ADPCM)
        
        Handles WAV files with extra chunks (JUNK, LIST) before fmt.
        """
        if len(audio_data) < 44:
            return False
        
        if audio_data[:4] != b'RIFF':
            return False
        
        if audio_data[8:12] != b'WAVE':
            return False
        
        try:
            fmt_offset = self._find_chunk(audio_data, b'fmt ')
            if fmt_offset == -1:
                return False
            
            if fmt_offset + 16 > len(audio_data):
                return False
            
            audio_format = struct.unpack('<H', audio_data[fmt_offset + 8:fmt_offset + 10])[0]
            if audio_format != 1:
                logger.debug(f"⚠️ Non-PCM WAV detected (format={audio_format})")
                return False
            
            bits_per_sample = struct.unpack('<H', audio_data[fmt_offset + 22:fmt_offset + 24])[0]
            if bits_per_sample not in (8, 16, 24, 32):
                logger.debug(f"⚠️ Unsupported bits per sample: {bits_per_sample}")
                return False
            
            return True
        except Exception as e:
            logger.debug(f"⚠️ WAV validation error: {e}")
            return False
    
    def _find_chunk(self, wav_data: bytes, chunk_id: bytes) -> int:
        """Find a chunk in WAV data by its 4-byte ID. Returns offset or -1."""
        offset = 12
        while offset + 8 <= len(wav_data):
            current_id = wav_data[offset:offset + 4]
            if current_id == chunk_id:
                return offset
            chunk_size = struct.unpack('<I', wav_data[offset + 4:offset + 8])[0]
            offset += 8 + chunk_size
            if chunk_size % 2 == 1:
                offset += 1
        return -1
    
    def _parse_wav(self, wav_data: bytes) -> Tuple[bytes, Optional[int], Optional[int]]:
        """Parse WAV header and extract PCM data."""
        if len(wav_data) < 44:
            return wav_data, None, None
        
        if wav_data[:4] != b'RIFF' or wav_data[8:12] != b'WAVE':
            return wav_data, None, None
        
        try:
            channels = struct.unpack('<H', wav_data[22:24])[0]
            sample_rate = struct.unpack('<I', wav_data[24:28])[0]
            
            data_start = 44
            for i in range(12, len(wav_data) - 8):
                if wav_data[i:i+4] == b'data':
                    data_start = i + 8
                    break
            
            return wav_data[data_start:], sample_rate, channels
            
        except Exception as e:
            logger.warning(f"⚠️ WAV parsing error: {e}")
            return wav_data[44:], None, None
    
    def _stereo_to_mono(self, pcm_data: bytes) -> bytes:
        """Convert stereo PCM to mono by averaging channels."""
        if len(pcm_data) % 4 != 0:
            padding = 4 - (len(pcm_data) % 4)
            pcm_data += b'\x00' * padding
        
        samples = np.frombuffer(pcm_data, dtype=np.int16)
        
        left = samples[0::2]
        right = samples[1::2]
        
        mono = ((left.astype(np.int32) + right.astype(np.int32)) // 2).astype(np.int16)
        
        logger.debug(f"🔊 Stereo→Mono: {len(pcm_data)} → {len(mono.tobytes())} bytes")
        return mono.tobytes()
    
    def _resample(self, pcm_data: bytes, source_rate: int, target_rate: int) -> bytes:
        """Resample audio to target sample rate using linear interpolation."""
        if source_rate == target_rate:
            return pcm_data
        
        samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
        
        ratio = target_rate / source_rate
        new_length = int(len(samples) * ratio)
        
        indices = np.linspace(0, len(samples) - 1, new_length)
        resampled = np.interp(indices, np.arange(len(samples)), samples)
        
        resampled = np.clip(resampled, -32768, 32767).astype(np.int16)
        
        logger.debug(f"🔊 Resample: {source_rate}Hz → {target_rate}Hz")
        return resampled.tobytes()
    
    def _quick_vad_check(self, pcm_data: bytes, threshold_db: float = -40) -> bool:
        """Quick Voice Activity Detection check."""
        if len(pcm_data) < 320:
            return False
        
        samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
        
        if len(samples) < 100:
            return False
        
        rms = np.sqrt(np.mean(samples ** 2))
        
        if rms < 1:
            return False
        
        db = 20 * np.log10(rms / 32768)
        
        return db > threshold_db
    
    def _create_optimized_wav(self, pcm_data: bytes) -> bytes:
        """Create optimized WAV file with proper header."""
        header = BytesIO()
        
        data_size = len(pcm_data)
        file_size = data_size + 36
        byte_rate = WHISPER_OPTIMAL_SAMPLE_RATE * WHISPER_CHANNELS * WHISPER_SAMPLE_WIDTH
        block_align = WHISPER_CHANNELS * WHISPER_SAMPLE_WIDTH
        
        header.write(b'RIFF')
        header.write(struct.pack('<I', file_size))
        header.write(b'WAVE')
        
        header.write(b'fmt ')
        header.write(struct.pack('<I', 16))
        header.write(struct.pack('<H', 1))
        header.write(struct.pack('<H', WHISPER_CHANNELS))
        header.write(struct.pack('<I', WHISPER_OPTIMAL_SAMPLE_RATE))
        header.write(struct.pack('<I', byte_rate))
        header.write(struct.pack('<H', block_align))
        header.write(struct.pack('<H', WHISPER_SAMPLE_WIDTH * 8))
        
        header.write(b'data')
        header.write(struct.pack('<I', data_size))
        
        header.write(pcm_data)
        
        return header.getvalue()
    
    def get_stats(self) -> dict:
        """Get optimization statistics."""
        total_savings = self.stats['total_input_bytes'] - self.stats['total_output_bytes']
        savings_percent = (total_savings / self.stats['total_input_bytes'] * 100 
                          if self.stats['total_input_bytes'] > 0 else 0)
        
        return {
            **self.stats,
            'total_bytes_saved': total_savings,
            'savings_percent': savings_percent
        }


audio_optimizer = AudioPayloadOptimizer()


def optimize_for_whisper(audio_data: bytes, 
                         sample_rate: int = 48000, 
                         channels: int = 2) -> Tuple[bytes, dict]:
    """
    Convenience function to optimize audio for Whisper API.
    
    Returns:
        Tuple of (optimized_bytes, stats_dict)
    """
    return audio_optimizer.optimize_audio(audio_data, sample_rate, channels)


def get_optimization_stats() -> dict:
    """Get cumulative optimization statistics."""
    return audio_optimizer.get_stats()
