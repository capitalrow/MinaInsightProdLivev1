"""
Admin Metrics Service - Real-time metrics collection for Cognitive Mission Control
Collects and aggregates system health, pipeline performance, and AI oversight metrics.
"""

import logging
import threading
import time
import psutil
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import deque

logger = logging.getLogger(__name__)


class AdminMetricsService:
    """
    Central service for collecting and aggregating admin dashboard metrics.
    Provides real data from system monitoring, database queries, and pipeline tracking.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.start_time = time.time()
        
        self.system_metrics_buffer = deque(maxlen=1000)
        self.pipeline_metrics_buffer = deque(maxlen=500)
        self.copilot_actions_buffer = deque(maxlen=500)
        
        self.current_metrics = {
            'ws_latency': 0,
            'api_throughput': 0,
            'queue_depth': 0,
            'error_rate': 0.0,
            'sync_drift': 0,
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'disk_usage': 0.0
        }
        
        self.pipeline_stats = {
            'ingest': {'latency_ms': 0, 'error_rate': 0.0, 'count': 0},
            'chunking': {'latency_ms': 0, 'error_rate': 0.0, 'count': 0},
            'whisper': {'latency_ms': 0, 'error_rate': 0.0, 'count': 0},
            'ai_summary': {'latency_ms': 0, 'error_rate': 0.0, 'count': 0},
            'task_extract': {'latency_ms': 0, 'error_rate': 0.0, 'count': 0},
            'sync': {'latency_ms': 0, 'error_rate': 0.0, 'count': 0}
        }
        
        self.copilot_stats = {
            'actions_today': 0,
            'retry_rate': 0.0,
            'override_rate': 0.0,
            'semantic_drift': 0.0,
            'confidence_sum': 0.0,
            'confidence_count': 0
        }
        
        self.api_request_times = deque(maxlen=100)
        self.ws_latencies = deque(maxlen=100)
        
        self._monitoring_active = False
        self._monitor_thread = None
        
        logger.info("✅ AdminMetricsService initialized")
    
    def start_monitoring(self, interval: int = 10):
        """Start background metrics collection."""
        if self._monitoring_active:
            return
            
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(
            target=self._collection_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"✅ Admin metrics monitoring started (interval: {interval}s)")
    
    def stop_monitoring(self):
        """Stop background metrics collection."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Admin metrics monitoring stopped")
    
    def _collection_loop(self, interval: int):
        """Main collection loop running in background thread."""
        while self._monitoring_active:
            try:
                self._collect_system_metrics()
                self._aggregate_pipeline_stats()
                self._aggregate_copilot_stats()
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}", exc_info=True)
            
            time.sleep(interval)
    
    def _collect_system_metrics(self):
        """Collect current system resource metrics."""
        try:
            self.current_metrics['cpu_usage'] = psutil.cpu_percent(interval=None)
            
            memory = psutil.virtual_memory()
            self.current_metrics['memory_usage'] = memory.percent
            
            disk = psutil.disk_usage('/')
            self.current_metrics['disk_usage'] = (disk.used / disk.total) * 100
            
            if self.api_request_times:
                recent_requests = [r for r in self.api_request_times if time.time() - r['timestamp'] < 60]
                self.current_metrics['api_throughput'] = len(recent_requests)
            
            if self.ws_latencies:
                self.current_metrics['ws_latency'] = int(
                    sum(self.ws_latencies) / len(self.ws_latencies)
                )
            
            try:
                from services.health_monitor import HealthMonitor
                health_monitor = HealthMonitor()
                health_status = health_monitor.get_system_health()
                if health_status:
                    self.current_metrics['error_rate'] = getattr(health_status, 'error_rate', 0.0)
                    self.current_metrics['queue_depth'] = getattr(health_status, 'active_sessions', 0)
            except Exception:
                pass
            
            self.system_metrics_buffer.append({
                'timestamp': datetime.utcnow().isoformat(),
                'cpu': round(self.current_metrics['cpu_usage'], 1),
                'memory': round(self.current_metrics['memory_usage'], 1),
                'disk': round(self.current_metrics['disk_usage'], 1),
                'ws_latency': self.current_metrics['ws_latency'],
                'api_throughput': self.current_metrics['api_throughput'],
                'queue_depth': self.current_metrics['queue_depth'],
                'error_rate': self.current_metrics['error_rate']
            })
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def _aggregate_pipeline_stats(self):
        """Aggregate pipeline metrics from buffer."""
        for stage in self.pipeline_stats:
            metrics = [m for m in self.pipeline_metrics_buffer if m.get('stage') == stage]
            if metrics:
                recent = metrics[-50:]
                self.pipeline_stats[stage]['latency_ms'] = int(
                    sum(m['latency_ms'] for m in recent) / len(recent)
                )
                errors = sum(1 for m in recent if m.get('error'))
                self.pipeline_stats[stage]['error_rate'] = round(
                    (errors / len(recent)) * 100, 2
                ) if recent else 0.0
                self.pipeline_stats[stage]['count'] = len(recent)
    
    def _aggregate_copilot_stats(self):
        """Aggregate copilot action metrics."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        today_actions = [
            a for a in self.copilot_actions_buffer 
            if datetime.fromisoformat(a['timestamp']) >= today_start
        ]
        
        self.copilot_stats['actions_today'] = len(today_actions)
        
        if today_actions:
            retries = sum(1 for a in today_actions if a.get('retried'))
            self.copilot_stats['retry_rate'] = round(
                (retries / len(today_actions)) * 100, 2
            )
            
            overrides = sum(1 for a in today_actions if a.get('overridden'))
            self.copilot_stats['override_rate'] = round(
                (overrides / len(today_actions)) * 100, 2
            )
            
            confidences = [a['confidence'] for a in today_actions if a.get('confidence')]
            if confidences:
                self.copilot_stats['confidence_median'] = sorted(confidences)[len(confidences)//2]
    
    def record_pipeline_metric(self, stage: str, latency_ms: float, error: bool = False, 
                               session_id: Optional[int] = None):
        """Record a pipeline stage execution metric."""
        self.pipeline_metrics_buffer.append({
            'stage': stage,
            'latency_ms': latency_ms,
            'error': error,
            'session_id': session_id,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def record_copilot_action(self, action_type: str, confidence: Optional[float] = None,
                              retried: bool = False, overridden: bool = False,
                              user_id: Optional[int] = None, session_id: Optional[int] = None):
        """Record a copilot action for oversight tracking."""
        self.copilot_actions_buffer.append({
            'action_type': action_type,
            'confidence': confidence,
            'retried': retried,
            'overridden': overridden,
            'user_id': user_id,
            'session_id': session_id,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def record_api_request(self, duration_ms: float):
        """Record an API request for throughput calculation."""
        self.api_request_times.append({
            'duration_ms': duration_ms,
            'timestamp': time.time()
        })
    
    def record_ws_latency(self, latency_ms: float):
        """Record WebSocket latency measurement."""
        self.ws_latencies.append(latency_ms)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get current system health metrics."""
        status = 'healthy'
        if self.current_metrics['cpu_usage'] > 90 or self.current_metrics['memory_usage'] > 90:
            status = 'critical'
        elif self.current_metrics['cpu_usage'] > 80 or self.current_metrics['memory_usage'] > 80:
            status = 'degraded'
        
        return {
            'ws_latency': self.current_metrics['ws_latency'],
            'api_throughput': self.current_metrics['api_throughput'],
            'queue_depth': self.current_metrics['queue_depth'],
            'error_rate': self.current_metrics['error_rate'],
            'sync_drift': self.current_metrics['sync_drift'],
            'cpu_usage': round(self.current_metrics['cpu_usage'], 1),
            'memory_usage': round(self.current_metrics['memory_usage'], 1),
            'disk_usage': round(self.current_metrics['disk_usage'], 1),
            'status': status,
            'uptime_seconds': int(time.time() - self.start_time)
        }
    
    def get_pipeline_health(self) -> Dict[str, Dict[str, Any]]:
        """Get current pipeline health metrics."""
        result = {}
        for stage, stats in self.pipeline_stats.items():
            status = 'healthy'
            if stats['error_rate'] > 5:
                status = 'critical'
            elif stats['error_rate'] > 1:
                status = 'degraded'
            
            result[stage] = {
                'status': status,
                'latency_ms': stats['latency_ms'],
                'error_rate': stats['error_rate'],
                'throughput': stats['count']
            }
        return result
    
    def get_copilot_metrics(self) -> Dict[str, Any]:
        """Get AI copilot oversight metrics."""
        return {
            'actions_today': self.copilot_stats['actions_today'],
            'retry_rate': self.copilot_stats['retry_rate'],
            'override_rate': self.copilot_stats['override_rate'],
            'semantic_drift': self.copilot_stats.get('semantic_drift', 0.0),
            'confidence_median': self.copilot_stats.get('confidence_median', 0.87)
        }
    
    def get_system_timeline_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get time-series data for system health chart."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        result = []
        for metric in self.system_metrics_buffer:
            try:
                timestamp = datetime.fromisoformat(metric['timestamp'])
                if timestamp >= cutoff:
                    result.append(metric)
            except:
                continue
        
        return result
    
    def get_confidence_distribution(self) -> Dict[str, int]:
        """Get AI confidence distribution for chart."""
        buckets = {
            '0.5-0.6': 0,
            '0.6-0.7': 0,
            '0.7-0.8': 0,
            '0.8-0.9': 0,
            '0.9-1.0': 0
        }
        
        for action in self.copilot_actions_buffer:
            conf = action.get('confidence')
            if conf is not None:
                if conf < 0.6:
                    buckets['0.5-0.6'] += 1
                elif conf < 0.7:
                    buckets['0.6-0.7'] += 1
                elif conf < 0.8:
                    buckets['0.7-0.8'] += 1
                elif conf < 0.9:
                    buckets['0.8-0.9'] += 1
                else:
                    buckets['0.9-1.0'] += 1
        
        return buckets


admin_metrics_service = AdminMetricsService()


def get_admin_metrics_service() -> AdminMetricsService:
    """Get the singleton admin metrics service instance."""
    return admin_metrics_service
