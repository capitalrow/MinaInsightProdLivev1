"""
Production Health Check Endpoints

Implements industry-standard health endpoints following Google SRE / Kubernetes patterns:

1. /health/live - Liveness probe (is the process alive?)
2. /health/ready - Readiness probe (can it serve traffic?)
3. /health/startup - Startup probe (has it finished initializing?)
4. /health/detailed - Full diagnostic info (protected, for dashboards)

Reference: 
- Google SRE Book: Production Services Best Practices
- Kubernetes probe patterns: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from flask import Blueprint, jsonify, request, current_app

logger = logging.getLogger(__name__)

health_production_bp = Blueprint('health_production', __name__, url_prefix='/health')

# Track startup time for uptime calculation
_startup_time = time.time()
_startup_complete = False


def mark_startup_complete():
    """Call this after all initialization is done."""
    global _startup_complete
    _startup_complete = True
    logger.info("✅ Startup marked complete - application ready for traffic")


def get_uptime_seconds() -> float:
    """Get application uptime in seconds."""
    return time.time() - _startup_time


def check_database_health() -> Dict[str, Any]:
    """
    Check PostgreSQL database connectivity.
    
    Returns dict with:
    - healthy: bool
    - latency_ms: response time
    - error: error message if unhealthy
    """
    start = time.time()
    try:
        from models import db
        from sqlalchemy import text
        
        result = db.session.execute(text("SELECT 1"))
        result.fetchone()
        db.session.rollback()  # Don't leave open transaction
        
        latency_ms = (time.time() - start) * 1000
        return {
            "healthy": True,
            "latency_ms": round(latency_ms, 2),
            "type": "postgresql"
        }
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        logger.warning(f"Database health check failed: {e}")
        return {
            "healthy": False,
            "latency_ms": round(latency_ms, 2),
            "error": str(e)[:100],
            "type": "postgresql"
        }


def check_redis_health() -> Dict[str, Any]:
    """
    Check Redis connectivity (if configured).
    
    Returns dict with health status.
    """
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return {
            "healthy": True,
            "status": "not_configured",
            "message": "Redis not configured - using fallback"
        }
    
    start = time.time()
    try:
        import redis
        r = redis.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
        latency_ms = (time.time() - start) * 1000
        
        return {
            "healthy": True,
            "latency_ms": round(latency_ms, 2),
            "type": "redis"
        }
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        logger.warning(f"Redis health check failed: {e}")
        return {
            "healthy": False,
            "latency_ms": round(latency_ms, 2),
            "error": str(e)[:50],
            "type": "redis"
        }


def check_openai_health() -> Dict[str, Any]:
    """
    Check OpenAI API configuration (not connectivity - too slow for health checks).
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "healthy": True,
            "status": "not_configured",
            "message": "OpenAI API not configured"
        }
    
    return {
        "healthy": True,
        "status": "configured",
        "key_prefix": api_key[:8] + "..." if len(api_key) > 8 else "short"
    }


@health_production_bp.route('/live')
@health_production_bp.route('/liveness')
def liveness():
    """
    Liveness probe - is the process alive?
    
    Returns 200 if the Flask process is running.
    Kubernetes uses this to know when to restart the container.
    
    Should be FAST and have NO external dependencies.
    """
    return jsonify({
        "status": "alive",
        "uptime_seconds": round(get_uptime_seconds(), 2)
    }), 200


@health_production_bp.route('/ready')
@health_production_bp.route('/readiness')
def readiness():
    """
    Readiness probe - can the application serve traffic?
    
    Returns 200 if all critical dependencies are available.
    Returns 503 if any critical dependency is unavailable.
    
    Kubernetes uses this to add/remove from load balancer.
    """
    checks = {}
    
    # Check database (critical)
    db_health = check_database_health()
    checks["database"] = db_health
    
    # Check Redis (non-critical - we have fallback)
    redis_health = check_redis_health()
    checks["redis"] = redis_health
    
    # Determine overall readiness
    # Database is critical, Redis is not (we have filesystem fallback)
    is_ready = db_health.get("healthy", False)
    
    status_code = 200 if is_ready else 503
    
    return jsonify({
        "status": "ready" if is_ready else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), status_code


@health_production_bp.route('/startup')
def startup():
    """
    Startup probe - has the application finished initializing?
    
    Returns 200 once all initialization is complete.
    Returns 503 during startup.
    
    Kubernetes uses this to know when to start liveness/readiness probes.
    """
    if _startup_complete:
        return jsonify({
            "status": "started",
            "uptime_seconds": round(get_uptime_seconds(), 2)
        }), 200
    else:
        return jsonify({
            "status": "starting",
            "uptime_seconds": round(get_uptime_seconds(), 2)
        }), 503


@health_production_bp.route('/detailed')
def detailed_health():
    """
    Detailed health check for monitoring dashboards.
    
    Returns comprehensive health information including:
    - All dependency statuses
    - System metrics
    - Feature status
    - Configuration summary
    
    This endpoint should be protected in production (internal only).
    """
    import psutil
    
    # Verify internal access or admin auth in production
    is_production = os.environ.get("REPLIT_DEPLOYMENT") or os.environ.get("FLASK_ENV") == "production"
    
    # Get system stats
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        system_stats = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": round(memory.available / (1024 * 1024), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2)
        }
    except Exception as e:
        system_stats = {"error": str(e)[:50]}
    
    # Check all dependencies
    dependencies = {
        "database": check_database_health(),
        "redis": check_redis_health(),
        "openai": check_openai_health()
    }
    
    # Calculate overall health
    critical_healthy = dependencies["database"].get("healthy", False)
    all_healthy = all(d.get("healthy", False) or d.get("status") == "not_configured" 
                      for d in dependencies.values())
    
    if critical_healthy and all_healthy:
        overall_status = "healthy"
    elif critical_healthy:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"
    
    # Environment info
    environment = {
        "env": os.environ.get("FLASK_ENV", "development"),
        "is_production": is_production,
        "replit_deployment": bool(os.environ.get("REPLIT_DEPLOYMENT")),
        "sentry_configured": bool(os.environ.get("SENTRY_DSN")),
        "redis_configured": bool(os.environ.get("REDIS_URL"))
    }
    
    response = {
        "status": overall_status,
        "startup_complete": _startup_complete,
        "uptime_seconds": round(get_uptime_seconds(), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": dependencies,
        "system": system_stats,
        "environment": environment
    }
    
    status_code = 200 if overall_status != "unhealthy" else 503
    return jsonify(response), status_code


@health_production_bp.route('/')
@health_production_bp.route('')
def health_index():
    """
    Default health endpoint - quick check for load balancers.
    
    Equivalent to readiness check but simpler response.
    """
    db_health = check_database_health()
    is_healthy = db_health.get("healthy", False)
    
    return jsonify({
        "status": "healthy" if is_healthy else "unhealthy",
        "uptime_seconds": round(get_uptime_seconds(), 2)
    }), 200 if is_healthy else 503
