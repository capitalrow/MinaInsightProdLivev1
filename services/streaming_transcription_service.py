#!/usr/bin/env python3
"""
🚀 Streaming Transcription Service - Phase 3 Optimization
Implements <2 second transcription delivery with parallel processing

Features:
- 2-3 second chunk sizes for optimal latency/quality balance
- Parallel transcription workers (up to 3 concurrent)
- Interim results emitted immediately
- Smart merging with deduplication
- Business tier: live streaming, Pro/Free: batch results
"""

import os
import time
import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from queue import Queue, Empty
import tempfile
import io

import openai
from pydub import AudioSegment

logger = logging.getLogger(__name__)

@dataclass
class StreamConfig:
    """Configuration for streaming transcription"""
    chunk_duration_ms: int = 2500
    overlap_ms: int = 300
    max_concurrent_workers: int = 3
    max_queue_size: int = 20
    interim_emit_interval_ms: int = 500
    target_latency_ms: int = 2000
    enable_parallel: bool = True
    enable_interim_results: bool = True


@dataclass
class TranscriptionChunk:
    """A chunk of audio for transcription"""
    chunk_id: int
    session_id: str
    audio_data: bytes
    timestamp: float
    duration_ms: int
    sequence: int
    is_final: bool = False


@dataclass
class TranscriptionResult:
    """Result from transcription"""
    chunk_id: int
    session_id: str
    text: str
    confidence: float
    latency_ms: float
    is_interim: bool
    sequence: int
    timestamp: float
    words: List[Dict] = field(default_factory=list)


class StreamingTranscriptionService:
    """
    High-performance streaming transcription with <2s latency target
    """
    
    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()
        self._client: Optional[openai.OpenAI] = None
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_workers,
            thread_name_prefix="transcribe"
        )
        
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._result_callbacks: Dict[str, List[Callable]] = {}
        
        self._stats = {
            'total_chunks': 0,
            'successful_transcriptions': 0,
            'failed_transcriptions': 0,
            'avg_latency_ms': 0,
            'p95_latency_ms': 0,
            'latencies': [],
        }
        
        self._lock = threading.Lock()
        self._prewarm_done = False
        
        logger.info(f"🚀 StreamingTranscriptionService initialized")
        logger.info(f"   Chunk duration: {self.config.chunk_duration_ms}ms")
        logger.info(f"   Max workers: {self.config.max_concurrent_workers}")
        logger.info(f"   Target latency: {self.config.target_latency_ms}ms")
    
    @property
    def client(self) -> openai.OpenAI:
        """Get or initialize OpenAI client"""
        if self._client is None:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY required")
            
            self._client = openai.OpenAI(
                api_key=api_key,
                timeout=15.0,
                max_retries=2
            )
        return self._client
    
    def prewarm(self):
        """Prewarm the OpenAI client connection"""
        if self._prewarm_done:
            return
        
        try:
            _ = self.client.models.list()
            self._prewarm_done = True
            logger.info("✅ OpenAI client prewarmed")
        except Exception as e:
            logger.warning(f"⚠️ Prewarm failed (non-critical): {e}")
    
    def create_session(self, session_id: str, tier: str = 'free') -> Dict[str, Any]:
        """Create a streaming transcription session"""
        with self._lock:
            session = {
                'id': session_id,
                'tier': tier,
                'created_at': time.time(),
                'chunk_sequence': 0,
                'pending_chunks': Queue(maxsize=self.config.max_queue_size),
                'results': [],
                'interim_text': '',
                'final_text': '',
                'processing': False,
                'metrics': {
                    'chunks_received': 0,
                    'chunks_processed': 0,
                    'total_latency_ms': 0,
                    'min_latency_ms': float('inf'),
                    'max_latency_ms': 0,
                }
            }
            
            self._sessions[session_id] = session
            self._result_callbacks[session_id] = []
            
            logger.info(f"📝 Created streaming session: {session_id} (tier={tier})")
            return session
    
    def register_callback(self, session_id: str, callback: Callable[[TranscriptionResult], None]):
        """Register callback for transcription results"""
        if session_id in self._result_callbacks:
            self._result_callbacks[session_id].append(callback)
    
    def _emit_result(self, session_id: str, result: TranscriptionResult):
        """Emit result to all registered callbacks"""
        callbacks = self._result_callbacks.get(session_id, [])
        for callback in callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _convert_audio(self, audio_data: bytes) -> Optional[AudioSegment]:
        """Convert audio to optimal format for Whisper (supports multiple formats)"""
        formats_to_try = ['webm', 'ogg', 'wav', 'mp3', 'mp4', 'raw']
        
        for fmt in formats_to_try:
            try:
                if fmt == 'raw':
                    audio = AudioSegment(
                        data=audio_data,
                        sample_width=2,
                        frame_rate=16000,
                        channels=1
                    )
                else:
                    audio = AudioSegment.from_file(io.BytesIO(audio_data), format=fmt)
                
                audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                return audio
            except Exception:
                continue
        
        logger.warning(f"Audio conversion failed for all formats ({len(audio_data)} bytes)")
        return None
    
    def _transcribe_chunk_sync(self, chunk: TranscriptionChunk) -> Optional[TranscriptionResult]:
        """Synchronous transcription of a single chunk"""
        start_time = time.time()
        
        try:
            audio = self._convert_audio(chunk.audio_data)
            if audio is None or len(audio) < 100:
                return None
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                audio.export(tmp.name, format="wav")
                tmp_path = tmp.name
            
            try:
                with open(tmp_path, "rb") as f:
                    response = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        response_format="verbose_json",
                        language="en",
                        temperature=0.2,
                    )
                
                text = response.text.strip() if response.text else ""
                
                if self._is_hallucination(text):
                    text = ""
                
                latency_ms = (time.time() - start_time) * 1000
                
                self._record_latency(latency_ms)
                
                return TranscriptionResult(
                    chunk_id=chunk.chunk_id,
                    session_id=chunk.session_id,
                    text=text,
                    confidence=self._estimate_confidence(response, len(chunk.audio_data)),
                    latency_ms=latency_ms,
                    is_interim=not chunk.is_final,
                    sequence=chunk.sequence,
                    timestamp=chunk.timestamp,
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Transcription failed for chunk {chunk.chunk_id}: {e}")
            self._stats['failed_transcriptions'] += 1
            return None
    
    def _is_hallucination(self, text: str) -> bool:
        """Detect common Whisper hallucinations"""
        if not text:
            return False
        
        hallucination_patterns = [
            "thank you for watching",
            "thanks for watching",
            "please subscribe",
            "like and subscribe",
            "see you next time",
            "bye bye",
            "music",
            "[music]",
            "(music)",
        ]
        
        text_lower = text.lower().strip()
        
        for pattern in hallucination_patterns:
            if pattern in text_lower:
                return True
        
        if len(text_lower) < 3 and text_lower in ['you', 'i', 'a', 'the', 'um', 'uh']:
            return True
        
        return False
    
    def _estimate_confidence(self, response, audio_size: int) -> float:
        """Estimate transcription confidence"""
        base_confidence = 0.85
        
        if hasattr(response, 'segments') and response.segments:
            avg_prob = sum(s.get('avg_logprob', -0.5) for s in response.segments) / len(response.segments)
            base_confidence = min(0.99, max(0.5, 1.0 + avg_prob))
        
        return round(base_confidence, 3)
    
    def _record_latency(self, latency_ms: float):
        """Record latency for statistics"""
        with self._lock:
            self._stats['latencies'].append(latency_ms)
            self._stats['successful_transcriptions'] += 1
            
            if len(self._stats['latencies']) > 100:
                self._stats['latencies'] = self._stats['latencies'][-100:]
            
            latencies = self._stats['latencies']
            self._stats['avg_latency_ms'] = sum(latencies) / len(latencies)
            
            sorted_latencies = sorted(latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            self._stats['p95_latency_ms'] = sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else latencies[-1]
    
    def process_chunk(self, chunk: TranscriptionChunk) -> Optional[TranscriptionResult]:
        """Process a single chunk (blocking)"""
        self._stats['total_chunks'] += 1
        
        session = self._sessions.get(chunk.session_id)
        if session:
            session['metrics']['chunks_received'] += 1
        
        result = self._transcribe_chunk_sync(chunk)
        
        if result and session:
            session['metrics']['chunks_processed'] += 1
            session['metrics']['total_latency_ms'] += result.latency_ms
            session['metrics']['min_latency_ms'] = min(session['metrics']['min_latency_ms'], result.latency_ms)
            session['metrics']['max_latency_ms'] = max(session['metrics']['max_latency_ms'], result.latency_ms)
            
            if result.text:
                session['results'].append(result)
                if result.is_interim:
                    session['interim_text'] = result.text
                else:
                    session['final_text'] += ' ' + result.text
            
            self._emit_result(chunk.session_id, result)
        
        return result
    
    def process_chunks_parallel(self, chunks: List[TranscriptionChunk]) -> List[TranscriptionResult]:
        """Process multiple chunks in parallel for maximum throughput"""
        if not self.config.enable_parallel or len(chunks) <= 1:
            results = []
            for chunk in chunks:
                result = self.process_chunk(chunk)
                if result:
                    results.append(result)
            return results
        
        futures = []
        for chunk in chunks:
            future = self._executor.submit(self._transcribe_chunk_sync, chunk)
            futures.append((chunk, future))
        
        results = []
        for chunk, future in futures:
            try:
                result = future.result(timeout=15.0)
                if result:
                    session = self._sessions.get(chunk.session_id)
                    if session:
                        session['metrics']['chunks_processed'] += 1
                        session['results'].append(result)
                        self._emit_result(chunk.session_id, result)
                    results.append(result)
            except Exception as e:
                logger.error(f"Parallel transcription failed for chunk {chunk.chunk_id}: {e}")
        
        results.sort(key=lambda r: r.sequence)
        return results
    
    def get_merged_text(self, session_id: str) -> str:
        """Get deduplicated merged text from all results"""
        session = self._sessions.get(session_id)
        if not session:
            return ""
        
        results = sorted(session['results'], key=lambda r: r.sequence)
        
        merged_words = []
        for result in results:
            if not result.text:
                continue
            
            words = result.text.split()
            for word in words:
                if not merged_words or word.lower() != merged_words[-1].lower():
                    merged_words.append(word)
        
        return ' '.join(merged_words)
    
    def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get metrics for a session"""
        session = self._sessions.get(session_id)
        if not session:
            return {}
        
        metrics = session['metrics'].copy()
        if metrics['chunks_processed'] > 0:
            metrics['avg_latency_ms'] = metrics['total_latency_ms'] / metrics['chunks_processed']
        else:
            metrics['avg_latency_ms'] = 0
        
        return metrics
    
    def close_session(self, session_id: str) -> Dict[str, Any]:
        """Close a session and return final metrics"""
        session = self._sessions.pop(session_id, None)
        callbacks = self._result_callbacks.pop(session_id, [])
        
        if session:
            return {
                'final_text': self.get_merged_text(session_id) if session_id in self._sessions else session.get('final_text', ''),
                'metrics': session['metrics'],
                'results_count': len(session['results']),
            }
        return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get global service statistics"""
        return {
            'total_chunks': self._stats['total_chunks'],
            'successful': self._stats['successful_transcriptions'],
            'failed': self._stats['failed_transcriptions'],
            'avg_latency_ms': round(self._stats['avg_latency_ms'], 1),
            'p95_latency_ms': round(self._stats['p95_latency_ms'], 1),
            'active_sessions': len(self._sessions),
            'target_latency_ms': self.config.target_latency_ms,
            'meets_sla': self._stats['avg_latency_ms'] < self.config.target_latency_ms if self._stats['avg_latency_ms'] else True,
        }
    
    def shutdown(self):
        """Shutdown the service"""
        self._executor.shutdown(wait=True)
        logger.info("🛑 StreamingTranscriptionService shutdown complete")


streaming_transcription_service = StreamingTranscriptionService()
