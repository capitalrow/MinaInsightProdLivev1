# services/cache.py
"""
Cache service with Redis backend (production) or no-op fallback (development).
Gracefully handles Redis connection failures.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None

class _NoopCache:
    """No-operation cache for when Redis is unavailable."""
    
    def delete_prefix(self, prefix: str) -> int:
        return 0
    
    def get(self, key: str) -> Optional[str]:
        return None
    
    def set(self, key: str, value: str, ex: int = None) -> bool:
        return True
    
    def delete(self, key: str) -> int:
        return 0

class _RedisCache:
    """Redis-backed cache for production use."""
    
    def __init__(self, client):
        self._r = client

    def delete_prefix(self, prefix: str) -> int:
        """Delete all keys with the given prefix using SCAN to avoid blocking."""
        count = 0
        cursor = 0
        pattern = f"{prefix}*"
        try:
            while True:
                cursor, keys = self._r.scan(cursor=cursor, match=pattern, count=500)
                if keys:
                    count += self._r.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"Redis delete_prefix failed: {e}")
        return count
    
    def get(self, key: str) -> Optional[str]:
        try:
            return self._r.get(key)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None
    
    def set(self, key: str, value: str, ex: int = None) -> bool:
        try:
            return self._r.set(key, value, ex=ex)
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
            return False
    
    def delete(self, key: str) -> int:
        try:
            return self._r.delete(key)
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")
            return 0

def _make_cache():
    """Create cache instance - Redis if available and configured, otherwise no-op."""
    url = os.getenv("REDIS_URL")
    
    if not url or not redis_lib:
        return _NoopCache()
    
    # Validate URL format before attempting connection
    valid_schemes = ('redis://', 'rediss://', 'unix://')
    if not any(url.startswith(scheme) for scheme in valid_schemes):
        logger.warning(f"Invalid REDIS_URL scheme - must start with redis://, rediss://, or unix://")
        return _NoopCache()
    
    try:
        client = redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=5)
        client.ping()  # Test connection
        logger.info("✅ Cache service connected to Redis")
        return _RedisCache(client)
    except Exception as e:
        logger.warning(f"Redis connection failed, using no-op cache: {e}")
        return _NoopCache()

cache = _make_cache()
