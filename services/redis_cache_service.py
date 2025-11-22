"""
🚀 REDIS CACHE SERVICE: High-performance caching and session management with circuit breaker protection
Provides distributed caching, session persistence, and performance optimization
"""

import os
import time
import logging
import threading
import json
import pickle
import hashlib
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import traceback

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

try:
    from services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False
    CircuitBreakerOpenError = Exception

logger = logging.getLogger(__name__)

@dataclass
class CacheConfig:
    """Redis cache configuration"""
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    decode_responses: bool = False
    socket_timeout: float = 5.0
    connection_pool_max_connections: int = 50
    
    # Cache TTL settings (in seconds)
    default_ttl: int = 3600  # 1 hour
    session_ttl: int = 86400  # 24 hours
    transcription_ttl: int = 7200  # 2 hours
    analytics_ttl: int = 1800  # 30 minutes
    temp_cache_ttl: int = 300  # 5 minutes

@dataclass
class CacheStats:
    """Cache performance statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0
    last_reset: float = 0.0

class RedisCacheService:
    """
    High-performance Redis caching service for Mina transcription platform
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.client = None
        self.connection_pool = None
        self.is_connected = False
        self.stats = CacheStats(last_reset=time.time())
        self.stats_lock = threading.RLock()
        
        # Initialize circuit breaker for Redis operations
        if CIRCUIT_BREAKER_AVAILABLE:
            cb_config = CircuitBreakerConfig(
                failure_threshold=5,    # Open circuit after 5 failures
                recovery_timeout=30,    # Try recovery after 30 seconds
                success_threshold=3,    # Close after 3 successes
                request_timeout=5       # 5 second timeout for Redis operations
            )
            self.circuit_breaker = CircuitBreaker("redis_cache", cb_config)
        else:
            self.circuit_breaker = None
        
        # Key prefixes for different data types
        self.key_prefixes = {
            'session': 'mina:session:',
            'transcription': 'mina:transcription:',
            'speaker': 'mina:speaker:',
            'sentiment': 'mina:sentiment:',
            'insights': 'mina:insights:',
            'analytics': 'mina:analytics:',
            'audio_cache': 'mina:audio:',
            'temp': 'mina:temp:',
            'health': 'mina:health:',
            'circuit_breaker': 'mina:cb:'
        }
        
        self._initialize_redis()
        
        logger.info("🚀 Redis Cache Service initialized with circuit breaker protection")
    
    def _initialize_redis(self):
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            logger.warning("⚠️ Redis not available, cache service disabled")
            return
        
        try:
            # Create connection pool
            self.connection_pool = redis.ConnectionPool(  # type: ignore
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                db=self.config.db,
                decode_responses=self.config.decode_responses,
                socket_timeout=self.config.socket_timeout,
                max_connections=self.config.connection_pool_max_connections
            )
            
            # Create Redis client
            self.client = redis.Redis(connection_pool=self.connection_pool)  # type: ignore
            
            # Test connection
            self.client.ping()
            self.is_connected = True
            
            logger.info("✅ Redis connection established")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.is_connected = False
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Redis cache is available"""
        return REDIS_AVAILABLE and self.is_connected and self.client is not None
    
    def get(self, key: str, prefix: str = 'temp') -> Optional[Any]:
        """Get value from cache with circuit breaker protection"""
        if not self.is_available():
            return None
        
        try:
            full_key = self._build_key(key, prefix)
            
            # Execute with circuit breaker protection if available
            def _get_from_cache():
                raw_value = self.client.get(full_key)  # type: ignore
                return raw_value
            
            if self.circuit_breaker:
                try:
                    raw_value = self.circuit_breaker.call(_get_from_cache)
                except CircuitBreakerOpenError:
                    logger.warning(f"🔴 Redis circuit breaker OPEN - cache unavailable for key {key}")
                    with self.stats_lock:
                        self.stats.errors += 1
                    return None
            else:
                raw_value = _get_from_cache()
            
            with self.stats_lock:
                self.stats.total_requests += 1
                
                if raw_value is not None:
                    self.stats.hits += 1
                    value = self._deserialize_value(raw_value)
                    logger.debug(f"🎯 Cache HIT: {full_key}")
                    return value
                else:
                    self.stats.misses += 1
                    logger.debug(f"💨 Cache MISS: {full_key}")
                    return None
            
        except Exception as e:
            logger.error(f"❌ Cache get error for {key}: {e}")
            with self.stats_lock:
                self.stats.errors += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, prefix: str = 'temp') -> bool:
        """Set value in cache with circuit breaker protection"""
        if not self.is_available():
            return False
        
        try:
            full_key = self._build_key(key, prefix)
            serialized_value = self._serialize_value(value)
            
            # Use appropriate TTL
            cache_ttl = ttl or self._get_default_ttl(prefix)
            
            # Execute with circuit breaker protection if available
            def _set_in_cache():
                return self.client.setex(full_key, cache_ttl, serialized_value)  # type: ignore
            
            if self.circuit_breaker:
                try:
                    result = self.circuit_breaker.call(_set_in_cache)
                except CircuitBreakerOpenError:
                    logger.warning(f"🔴 Redis circuit breaker OPEN - cache unavailable for key {key}")
                    with self.stats_lock:
                        self.stats.errors += 1
                    return False
            else:
                result = _set_in_cache()
            
            with self.stats_lock:
                self.stats.sets += 1
            
            logger.debug(f"💾 Cache SET: {full_key} (TTL: {cache_ttl}s)")
            return bool(result)
            
        except Exception as e:
            logger.error(f"❌ Cache set error for {key}: {e}")
            with self.stats_lock:
                self.stats.errors += 1
            return False
    
    def delete(self, key: str, prefix: str = 'temp') -> bool:
        """Delete key from cache"""
        if not self.is_available():
            return False
        
        try:
            full_key = self._build_key(key, prefix)
            result = self.client.delete(full_key)  # type: ignore
            
            with self.stats_lock:
                self.stats.deletes += 1
            
            logger.debug(f"🗑️ Cache DELETE: {full_key}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"❌ Cache delete error for {key}: {e}")
            with self.stats_lock:
                self.stats.errors += 1
            return False
    
    def exists(self, key: str, prefix: str = 'temp') -> bool:
        """Check if key exists in cache"""
        if not self.is_available():
            return False
        
        try:
            full_key = self._build_key(key, prefix)
            return bool(self.client.exists(full_key))  # type: ignore
            
        except Exception as e:
            logger.error(f"❌ Cache exists error for {key}: {e}")
            return False
    
    def get_ttl(self, key: str, prefix: str = 'temp') -> int:
        """Get TTL for a key"""
        if not self.is_available():
            return -1
        
        try:
            full_key = self._build_key(key, prefix)
            return self.client.ttl(full_key)  # type: ignore
            
        except Exception as e:
            logger.error(f"❌ Cache TTL error for {key}: {e}")
            return -1
    
    def increment(self, key: str, amount: int = 1, prefix: str = 'temp', ttl: Optional[int] = None) -> int:
        """Increment a counter"""
        if not self.is_available():
            return 0
        
        try:
            full_key = self._build_key(key, prefix)
            
            # Use pipeline for atomic operation
            pipe = self.client.pipeline()  # type: ignore
            pipe.incr(full_key, amount)
            
            if ttl:
                pipe.expire(full_key, ttl)
            
            results = pipe.execute()
            return results[0]
            
        except Exception as e:
            logger.error(f"❌ Cache increment error for {key}: {e}")
            return 0
    
    def get_keys_by_pattern(self, pattern: str, prefix: str = 'temp') -> List[str]:
        """Get keys matching a pattern"""
        if not self.is_available():
            return []
        
        try:
            full_pattern = self._build_key(pattern, prefix)
            keys = self.client.keys(full_pattern)  # type: ignore
            
            # Remove prefix from keys
            prefix_len = len(self.key_prefixes[prefix])
            result_keys = []
            for key in keys:
                if isinstance(key, bytes):
                    key_str = key.decode('utf-8')
                else:
                    key_str = str(key)
                result_keys.append(key_str[prefix_len:])
            return result_keys
            
        except Exception as e:
            logger.error(f"❌ Cache keys error for pattern {pattern}: {e}")
            return []
    
    def expire(self, key: str, ttl: int, prefix: str = 'temp') -> bool:
        """Set expiration for a key"""
        if not self.is_available():
            return False
        
        try:
            full_key = self._build_key(key, prefix)
            return bool(self.client.expire(full_key, ttl))  # type: ignore
            
        except Exception as e:
            logger.error(f"❌ Cache expire error for {key}: {e}")
            return False
    
    def clear_prefix(self, prefix: str) -> int:
        """Clear all keys with given prefix"""
        if not self.is_available():
            return 0
        
        try:
            pattern = f"{self.key_prefixes[prefix]}*"
            keys = self.client.keys(pattern)  # type: ignore
            
            if keys:
                deleted = self.client.delete(*keys)  # type: ignore
                logger.info(f"🗑️ Cleared {deleted} keys with prefix {prefix}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"❌ Cache clear prefix error for {prefix}: {e}")
            return 0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get Redis memory usage information"""
        if not self.is_available():
            return {}
        
        try:
            info = self.client.info('memory')  # type: ignore
            return {
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'used_memory_peak': info.get('used_memory_peak', 0),
                'used_memory_peak_human': info.get('used_memory_peak_human', '0B'),
                'maxmemory': info.get('maxmemory', 0),
                'maxmemory_human': info.get('maxmemory_human', 'unlimited')
            }
            
        except Exception as e:
            logger.error(f"❌ Cache memory usage error: {e}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on Redis"""
        health_status = {
            'status': 'unhealthy',
            'available': False,
            'latency_ms': 0.0,
            'memory_usage': {},
            'connection_pool': {},
            'stats': {}
        }
        
        if not self.is_available():
            health_status['error'] = 'Redis not available'
            return health_status
        
        try:
            # Ping test with latency measurement
            start_time = time.time()
            self.client.ping()  # type: ignore
            latency = (time.time() - start_time) * 1000
            
            health_status.update({
                'status': 'healthy',
                'available': True,
                'latency_ms': round(latency, 2)
            })
            
            # Memory usage
            health_status['memory_usage'] = self.get_memory_usage()
            
            # Connection pool info
            if self.connection_pool:
                health_status['connection_pool'] = {
                    'created_connections': self.connection_pool.created_connections,
                    'available_connections': len(self.connection_pool._available_connections),
                    'in_use_connections': len(self.connection_pool._in_use_connections)
                }
            
            # Cache statistics
            health_status['stats'] = self.get_cache_stats()
            
        except Exception as e:
            health_status.update({
                'status': 'unhealthy',
                'error': str(e)
            })
            logger.error(f"❌ Redis health check failed: {e}")
        
        return health_status
    
    # Session management methods
    def save_session_state(self, session_id: str, state: Dict[str, Any]) -> bool:
        """Save session state to cache"""
        return self.set(session_id, state, prefix='session', ttl=self.config.session_ttl)
    
    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session state from cache"""
        return self.get(session_id, prefix='session')
    
    def delete_session_state(self, session_id: str) -> bool:
        """Delete session state from cache"""
        return self.delete(session_id, prefix='session')
    
    def extend_session_ttl(self, session_id: str) -> bool:
        """Extend session TTL"""
        return self.expire(session_id, self.config.session_ttl, prefix='session')
    
    # Transcription caching methods
    def cache_transcription_result(self, audio_hash: str, result: Dict[str, Any]) -> bool:
        """Cache transcription result"""
        return self.set(audio_hash, result, prefix='transcription', ttl=self.config.transcription_ttl)
    
    def get_cached_transcription(self, audio_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached transcription result"""
        return self.get(audio_hash, prefix='transcription')
    
    # Speaker data caching methods
    def cache_speaker_profile(self, session_id: str, speaker_id: str, profile: Dict[str, Any]) -> bool:
        """Cache speaker profile"""
        key = f"{session_id}:{speaker_id}"
        return self.set(key, profile, prefix='speaker', ttl=self.config.session_ttl)
    
    def get_cached_speaker_profile(self, session_id: str, speaker_id: str) -> Optional[Dict[str, Any]]:
        """Get cached speaker profile"""
        key = f"{session_id}:{speaker_id}"
        return self.get(key, prefix='speaker')
    
    # Sentiment caching methods
    def cache_sentiment_analysis(self, session_id: str, sentiment_data: Dict[str, Any]) -> bool:
        """Cache sentiment analysis"""
        return self.set(session_id, sentiment_data, prefix='sentiment', ttl=self.config.session_ttl)
    
    def get_cached_sentiment_analysis(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached sentiment analysis"""
        return self.get(session_id, prefix='sentiment')
    
    # Analytics caching methods
    def cache_analytics_data(self, key: str, data: Dict[str, Any]) -> bool:
        """Cache analytics data"""
        return self.set(key, data, prefix='analytics', ttl=self.config.analytics_ttl)
    
    def get_cached_analytics_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached analytics data"""
        return self.get(key, prefix='analytics')
    
    # Circuit breaker state management
    def get_circuit_breaker_state(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get circuit breaker state"""
        return self.get(service_name, prefix='circuit_breaker')
    
    def save_circuit_breaker_state(self, service_name: str, state: Dict[str, Any]) -> bool:
        """Save circuit breaker state"""
        return self.set(service_name, state, prefix='circuit_breaker', ttl=self.config.default_ttl)
    
    # Utility methods
    def _build_key(self, key: str, prefix: str) -> str:
        """Build full Redis key with prefix"""
        return f"{self.key_prefixes[prefix]}{key}"
    
    def _get_default_ttl(self, prefix: str) -> int:
        """Get default TTL for prefix"""
        ttl_mapping = {
            'session': self.config.session_ttl,
            'transcription': self.config.transcription_ttl,
            'speaker': self.config.session_ttl,
            'sentiment': self.config.session_ttl,
            'insights': self.config.session_ttl,
            'analytics': self.config.analytics_ttl,
            'audio_cache': self.config.transcription_ttl,
            'health': self.config.analytics_ttl,
            'circuit_breaker': self.config.default_ttl,
            'temp': self.config.temp_cache_ttl
        }
        return ttl_mapping.get(prefix, self.config.default_ttl)
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for Redis storage"""
        try:
            # Use JSON for simple types, pickle for complex ones
            if isinstance(value, (str, int, float, bool, list, dict)):
                return json.dumps(value, default=str).encode('utf-8')
            else:
                return pickle.dumps(value)
        except Exception as e:
            logger.error(f"❌ Serialization error: {e}")
            raise
    
    def _deserialize_value(self, raw_value: bytes) -> Any:
        """Deserialize value from Redis storage"""
        try:
            # Try JSON first (most common)
            try:
                return json.loads(raw_value.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fall back to pickle
                return pickle.loads(raw_value)
        except Exception as e:
            logger.error(f"❌ Deserialization error: {e}")
            raise
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        with self.stats_lock:
            # Calculate hit rate
            if self.stats.total_requests > 0:
                self.stats.hit_rate = self.stats.hits / self.stats.total_requests
            else:
                self.stats.hit_rate = 0.0
            
            return {
                'hits': self.stats.hits,
                'misses': self.stats.misses,
                'sets': self.stats.sets,
                'deletes': self.stats.deletes,
                'errors': self.stats.errors,
                'total_requests': self.stats.total_requests,
                'hit_rate': round(self.stats.hit_rate * 100, 2),
                'uptime_seconds': time.time() - self.stats.last_reset
            }
    
    def reset_stats(self):
        """Reset cache statistics"""
        with self.stats_lock:
            self.stats = CacheStats(last_reset=time.time())
            logger.info("📊 Cache statistics reset")
    
    def generate_audio_hash(self, audio_data: bytes, additional_context: str = "") -> str:
        """Generate hash for audio data caching"""
        try:
            # Create hash from audio data + context
            hasher = hashlib.sha256()
            hasher.update(audio_data)
            if additional_context:
                hasher.update(additional_context.encode('utf-8'))
            
            return hasher.hexdigest()[:16]  # Use first 16 characters
            
        except Exception as e:
            logger.error(f"❌ Audio hash generation error: {e}")
            return ""
    
    def cleanup_expired_keys(self):
        """Cleanup expired keys (Redis does this automatically, but can be called manually)"""
        if not self.is_available():
            return
        
        try:
            # This is mainly for logging purposes as Redis handles expiration automatically
            info = self.client.info('keyspace')  # type: ignore
            logger.debug(f"📊 Redis keyspace info: {info}")
            
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
    
    def close(self):
        """Close Redis connection"""
        try:
            if self.client:
                self.client.close()
            if self.connection_pool:
                self.connection_pool.disconnect()
            
            self.is_connected = False
            logger.info("🔌 Redis connection closed")
            
        except Exception as e:
            logger.error(f"❌ Error closing Redis connection: {e}")

# Global cache service instance
_global_cache_service = None
_cache_lock = threading.Lock()

def get_cache_service() -> RedisCacheService:
    """Get global Redis cache service"""
    global _global_cache_service
    
    if _global_cache_service is None:
        with _cache_lock:
            if _global_cache_service is None:
                _global_cache_service = RedisCacheService()
    
    return _global_cache_service

# Convenience functions for common caching patterns
def cache_with_fallback(cache_key: str, fallback_func, 
                       ttl: int = 3600, prefix: str = 'temp') -> Any:
    """Cache pattern: get from cache or compute and cache"""
    cache_service = get_cache_service()
    
    # Try to get from cache
    cached_result = cache_service.get(cache_key, prefix=prefix)
    if cached_result is not None:
        return cached_result
    
    # Compute result
    try:
        result = fallback_func()
        
        # Cache the result
        cache_service.set(cache_key, result, ttl=ttl, prefix=prefix)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Cache fallback error for {cache_key}: {e}")
        raise

def invalidate_session_cache(session_id: str):
    """Invalidate all cache entries for a session"""
    cache_service = get_cache_service()
    
    # Clear session-specific caches
    cache_service.delete_session_state(session_id)
    cache_service.delete(session_id, prefix='sentiment')
    cache_service.delete(session_id, prefix='insights')
    
    # Clear speaker profiles for this session
    speaker_keys = cache_service.get_keys_by_pattern(f"{session_id}:*", prefix='speaker')
    for speaker_key in speaker_keys:
        cache_service.delete(speaker_key, prefix='speaker')
    
    logger.info(f"🗑️ Invalidated cache for session {session_id}")

logger.info("🚀 Redis Cache Service initialized")