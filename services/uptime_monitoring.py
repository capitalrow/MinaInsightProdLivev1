"""
Uptime monitoring service.
Provides health check endpoints and integrates with external monitoring.
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any
import psutil

logger = logging.getLogger(__name__)


class UptimeMonitor:
    """Monitor application uptime and health."""
    
    def __init__(self):
        self.start_time = datetime.utcnow()
        self.health_checks = []
    
    def get_uptime_seconds(self) -> float:
        """Get application uptime in seconds."""
        delta = datetime.utcnow() - self.start_time
        return delta.total_seconds()
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system resource statistics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_mb': memory.available / (1024 * 1024),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024 * 1024 * 1024)
            }
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {}
    
    def check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            from models import db
            db.session.execute('SELECT 1')
            
            return {
                'status': 'healthy',
                'connected': True
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': str(e)
            }
    
    def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis connectivity."""
        redis_url = os.environ.get('REDIS_URL')
        if not redis_url:
            return {
                'status': 'not_configured',
                'connected': False
            }
        
        try:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            
            return {
                'status': 'healthy',
                'connected': True
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': str(e)
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        database = self.check_database_health()
        redis = self.check_redis_health()
        system = self.get_system_stats()
        
        overall_healthy = (
            database.get('connected', False) and
            (redis.get('connected', True) or redis.get('status') == 'not_configured')
        )
        
        return {
            'status': 'healthy' if overall_healthy else 'unhealthy',
            'uptime_seconds': self.get_uptime_seconds(),
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'database': database,
                'redis': redis
            },
            'system': system
        }


uptime_monitor = UptimeMonitor()
