"""
CROWN⁹ Copilot Metrics Collection & Monitoring

Real-time metrics collection for performance tracking and SLA enforcement.

Tracked Metrics:
- Response latency (first token ≤600ms target)
- Sync latency (≤400ms target)
- Cache hit rate (≥90% target)
- Calm score (≥0.95 target)
- Uptime (99.95% target)
- Token throughput
- Error rates
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MetricsSnapshot:
    """Point-in-time metrics snapshot."""
    timestamp: datetime
    response_latency_ms: Optional[float] = None
    sync_latency_ms: Optional[float] = None
    cache_hit_rate: Optional[float] = None
    calm_score: Optional[float] = None
    error_rate: Optional[float] = None
    active_sessions: int = 0
    
    def meets_sla(self) -> bool:
        """Check if snapshot meets all SLA targets."""
        checks = []
        
        if self.response_latency_ms is not None:
            checks.append(self.response_latency_ms <= 600)
        
        if self.sync_latency_ms is not None:
            checks.append(self.sync_latency_ms <= 400)
        
        if self.cache_hit_rate is not None:
            checks.append(self.cache_hit_rate >= 0.90)
        
        if self.calm_score is not None:
            checks.append(self.calm_score >= 0.95)
        
        return all(checks) if checks else True


class CopilotMetricsCollector:
    """
    Real-time metrics collector for CROWN⁹ Copilot.
    
    Features:
    - Rolling window metrics (last 5 minutes)
    - SLA violation detection
    - Performance trend analysis
    - Alert triggering for threshold breaches
    """
    
    def __init__(self, window_minutes: int = 5):
        """Initialize metrics collector."""
        self.window_minutes = window_minutes
        self.window_seconds = window_minutes * 60
        
        # Time-series data (rolling window)
        self.response_latencies = deque(maxlen=1000)
        self.sync_latencies = deque(maxlen=1000)
        self.cache_requests = deque(maxlen=1000)
        self.calm_scores = deque(maxlen=1000)
        self.errors = deque(maxlen=1000)
        
        # Counters
        self.total_requests = 0
        self.total_errors = 0
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Session tracking
        self.active_sessions = set()
        
        # Start time for uptime calculation
        self.start_time = time.time()
        self.downtime_seconds = 0
    
    def record_response_latency(self, latency_ms: float, calm_score: float):
        """Record response latency and calm score."""
        self.response_latencies.append({
            'timestamp': time.time(),
            'latency_ms': latency_ms,
            'calm_score': calm_score
        })
        
        self.calm_scores.append({
            'timestamp': time.time(),
            'score': calm_score
        })
        
        self.total_requests += 1
        
        # Check SLA violation
        if latency_ms > 600:
            logger.warning(f"SLA VIOLATION: Response latency {latency_ms:.0f}ms exceeds 600ms target")
        
        if calm_score < 0.95:
            logger.warning(f"SLA VIOLATION: Calm score {calm_score:.2f} below 0.95 target")
    
    def record_sync_latency(self, latency_ms: float):
        """Record cross-surface sync latency."""
        self.sync_latencies.append({
            'timestamp': time.time(),
            'latency_ms': latency_ms
        })
        
        if latency_ms > 400:
            logger.warning(f"SLA VIOLATION: Sync latency {latency_ms:.0f}ms exceeds 400ms target")
    
    def record_cache_access(self, hit: bool):
        """Record cache hit or miss."""
        self.cache_requests.append({
            'timestamp': time.time(),
            'hit': hit
        })
        
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def record_error(self, error_type: str, severity: str):
        """Record error occurrence."""
        self.errors.append({
            'timestamp': time.time(),
            'type': error_type,
            'severity': severity
        })
        
        self.total_errors += 1
    
    def track_session(self, session_id: str, active: bool = True):
        """Track active session."""
        if active:
            self.active_sessions.add(session_id)
        else:
            self.active_sessions.discard(session_id)
    
    def get_current_metrics(self) -> MetricsSnapshot:
        """Get current metrics snapshot."""
        now = time.time()
        cutoff = now - self.window_seconds
        
        # Calculate average response latency (last 5 minutes)
        recent_latencies = [
            r['latency_ms'] for r in self.response_latencies
            if r['timestamp'] > cutoff
        ]
        avg_response_latency = sum(recent_latencies) / len(recent_latencies) if recent_latencies else None
        
        # Calculate average sync latency
        recent_syncs = [
            s['latency_ms'] for s in self.sync_latencies
            if s['timestamp'] > cutoff
        ]
        avg_sync_latency = sum(recent_syncs) / len(recent_syncs) if recent_syncs else None
        
        # Calculate cache hit rate
        recent_cache = [
            r for r in self.cache_requests
            if r['timestamp'] > cutoff
        ]
        if recent_cache:
            cache_hit_rate = sum(1 for r in recent_cache if r['hit']) / len(recent_cache)
        else:
            cache_hit_rate = None
        
        # Calculate average calm score
        recent_scores = [
            s['score'] for s in self.calm_scores
            if s['timestamp'] > cutoff
        ]
        avg_calm_score = sum(recent_scores) / len(recent_scores) if recent_scores else None
        
        # Calculate error rate
        recent_errors = [
            e for e in self.errors
            if e['timestamp'] > cutoff
        ]
        total_recent = len([r for r in self.response_latencies if r['timestamp'] > cutoff])
        error_rate = len(recent_errors) / total_recent if total_recent > 0 else 0.0
        
        return MetricsSnapshot(
            timestamp=datetime.now(),
            response_latency_ms=avg_response_latency,
            sync_latency_ms=avg_sync_latency,
            cache_hit_rate=cache_hit_rate,
            calm_score=avg_calm_score,
            error_rate=error_rate,
            active_sessions=len(self.active_sessions)
        )
    
    def get_uptime_percentage(self) -> float:
        """Calculate uptime percentage."""
        total_time = time.time() - self.start_time
        uptime = total_time - self.downtime_seconds
        return (uptime / total_time) * 100 if total_time > 0 else 100.0
    
    def get_sla_compliance(self) -> Dict[str, Any]:
        """Get SLA compliance report."""
        metrics = self.get_current_metrics()
        uptime_pct = self.get_uptime_percentage()
        
        return {
            'compliant': metrics.meets_sla() and uptime_pct >= 99.95,
            'metrics': {
                'response_latency_ms': {
                    'value': metrics.response_latency_ms,
                    'target': 600,
                    'compliant': metrics.response_latency_ms <= 600 if metrics.response_latency_ms else True
                },
                'sync_latency_ms': {
                    'value': metrics.sync_latency_ms,
                    'target': 400,
                    'compliant': metrics.sync_latency_ms <= 400 if metrics.sync_latency_ms else True
                },
                'cache_hit_rate': {
                    'value': metrics.cache_hit_rate,
                    'target': 0.90,
                    'compliant': metrics.cache_hit_rate >= 0.90 if metrics.cache_hit_rate else True
                },
                'calm_score': {
                    'value': metrics.calm_score,
                    'target': 0.95,
                    'compliant': metrics.calm_score >= 0.95 if metrics.calm_score else True
                },
                'uptime_pct': {
                    'value': uptime_pct,
                    'target': 99.95,
                    'compliant': uptime_pct >= 99.95
                }
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary."""
        metrics = self.get_current_metrics()
        
        return {
            'timestamp': metrics.timestamp.isoformat(),
            'response_latency_ms': metrics.response_latency_ms,
            'sync_latency_ms': metrics.sync_latency_ms,
            'cache_hit_rate': metrics.cache_hit_rate,
            'calm_score': metrics.calm_score,
            'error_rate': metrics.error_rate,
            'active_sessions': metrics.active_sessions,
            'uptime_pct': self.get_uptime_percentage(),
            'total_requests': self.total_requests,
            'total_errors': self.total_errors,
            'sla_compliant': metrics.meets_sla()
        }


# Global singleton instance
copilot_metrics_collector = CopilotMetricsCollector()
