"""
Azure Cache for Redis service for Indian Legal AI Assistant
Production-grade Redis caching with comprehensive features
"""
import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import structlog
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import pickle
import hashlib
from dataclasses import dataclass, asdict

from config.settings import settings
from utils.monitoring import metrics_collector
from utils.exceptions import ProcessingError

logger = structlog.get_logger(__name__)

@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    data: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

class AzureRedisService:
    """
    Production-grade Azure Cache for Redis service
    
    Features:
    - Connection pooling and failover
    - Intelligent caching strategies
    - Cache invalidation patterns
    - Performance monitoring
    - Memory optimization
    - Distributed locking
    - Pub/Sub messaging
    """
    
    def __init__(self):
        self.redis_client = None
        self.connection_pool = None
        
        # Cache statistics
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0,
            'total_operations': 0
        }
        
        # Cache configuration
        self.default_ttl = settings.cache.default_ttl
        self.query_cache_ttl = settings.cache.query_cache_ttl
        self.embedding_cache_ttl = settings.cache.embedding_cache_ttl
        
        # Key prefixes for organization
        self.key_prefixes = {
            'query': 'query:',
            'embedding': 'embedding:',
            'document': 'document:',
            'user': 'user:',
            'session': 'session:',
            'rate_limit': 'rate_limit:',
            'lock': 'lock:',
            'metrics': 'metrics:'
        }
        
        logger.info("Azure Redis service initialized")
    
    async def initialize(self):
        """Initialize Redis connection with Azure optimizations"""
        try:
            # Parse Redis URL
            redis_url = settings.cache.redis_url
            
            # Create connection pool with optimizations
            self.connection_pool = ConnectionPool.from_url(
                redis_url,
                max_connections=settings.cache.max_connections,
                retry_on_timeout=True,
                retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                health_check_interval=30,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,  # TCP_KEEPIDLE
                    2: 3,  # TCP_KEEPINTVL
                    3: 5,  # TCP_KEEPCNT
                },
                decode_responses=False  # We handle encoding ourselves
            )
            
            # Create Redis client
            self.redis_client = redis.Redis(
                connection_pool=self.connection_pool,
                socket_timeout=5.0,
                socket_connect_timeout=5.0
            )
            
            # Test connection
            await self._test_connection()
            
            # Setup monitoring
            await self._setup_monitoring()
            
            logger.info(
                "Azure Redis initialized successfully",
                max_connections=settings.cache.max_connections,
                default_ttl=self.default_ttl
            )
            
        except Exception as e:
            logger.error("Failed to initialize Azure Redis", error=str(e), exc_info=True)
            raise ProcessingError(
                message="Redis initialization failed",
                details={"error": str(e)}
            )
    
    async def _test_connection(self):
        """Test Redis connection and basic operations"""
        try:
            # Test basic operations
            await self.redis_client.ping()
            
            # Test set/get
            test_key = "test:connection"
            await self.redis_client.set(test_key, "test_value", ex=10)
            value = await self.redis_client.get(test_key)
            
            if value != b"test_value":
                raise Exception("Redis set/get test failed")
            
            await self.redis_client.delete(test_key)
            
            logger.info("Redis connection test successful")
            
        except Exception as e:
            logger.error("Redis connection test failed", error=str(e))
            raise
    
    async def _setup_monitoring(self):
        """Setup Redis monitoring and statistics collection"""
        try:
            # Get Redis info
            info = await self.redis_client.info()
            
            logger.info(
                "Redis server info",
                version=info.get('redis_version'),
                memory_used=info.get('used_memory_human'),
                connected_clients=info.get('connected_clients'),
                total_commands_processed=info.get('total_commands_processed')
            )
            
        except Exception as e:
            logger.warning("Failed to setup Redis monitoring", error=str(e))
    
    async def get(
        self,
        key: str,
        default: Any = None,
        deserialize: bool = True
    ) -> Any:
        """
        Get value from cache with comprehensive error handling
        
        Args:
            key: Cache key
            default: Default value if key not found
            deserialize: Whether to deserialize the value
            
        Returns:
            Cached value or default
        """
        start_time = time.time()
        
        try:
            # Get value from Redis
            value = await self.redis_client.get(key)
            
            if value is None:
                self.cache_stats['misses'] += 1
                self.cache_stats['total_operations'] += 1
                
                metrics_collector.record_counter(
                    "cache_operations",
                    1,
                    {"operation": "get", "result": "miss"}
                )
                
                return default
            
            # Deserialize if requested
            if deserialize:
                try:
                    # Try JSON first (for simple types)
                    if value.startswith(b'{') or value.startswith(b'['):
                        result = json.loads(value.decode('utf-8'))
                    else:
                        # Use pickle for complex objects
                        result = pickle.loads(value)
                except (json.JSONDecodeError, pickle.UnpicklingError):
                    # Fallback to string
                    result = value.decode('utf-8')
            else:
                result = value
            
            # Update statistics
            self.cache_stats['hits'] += 1
            self.cache_stats['total_operations'] += 1
            
            # Record metrics
            duration_ms = int((time.time() - start_time) * 1000)
            metrics_collector.record_metric(
                "cache_operation_duration",
                duration_ms,
                {"operation": "get", "result": "hit"}
            )
            
            metrics_collector.record_counter(
                "cache_operations",
                1,
                {"operation": "get", "result": "hit"}
            )
            
            return result
            
        except Exception as e:
            self.cache_stats['errors'] += 1
            self.cache_stats['total_operations'] += 1
            
            logger.error(
                "Cache get operation failed",
                key=key,
                error=str(e),
                exc_info=True
            )
            
            metrics_collector.record_counter(
                "cache_operations",
                1,
                {"operation": "get", "result": "error"}
            )
            
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serialize: bool = True,
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        Set value in cache with optional TTL and tags
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            serialize: Whether to serialize the value
            tags: Tags for cache invalidation
            
        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        
        try:
            # Serialize value if requested
            if serialize:
                if isinstance(value, (dict, list)):
                    serialized_value = json.dumps(value, default=str).encode('utf-8')
                else:
                    serialized_value = pickle.dumps(value)
            else:
                serialized_value = value if isinstance(value, bytes) else str(value).encode('utf-8')
            
            # Use default TTL if not specified
            effective_ttl = ttl or self.default_ttl
            
            # Set value in Redis
            result = await self.redis_client.set(key, serialized_value, ex=effective_ttl)
            
            # Handle tags for invalidation
            if tags:
                await self._add_tags_to_key(key, tags)
            
            # Update statistics
            self.cache_stats['sets'] += 1
            self.cache_stats['total_operations'] += 1
            
            # Record metrics
            duration_ms = int((time.time() - start_time) * 1000)
            metrics_collector.record_metric(
                "cache_operation_duration",
                duration_ms,
                {"operation": "set", "ttl": effective_ttl}
            )
            
            metrics_collector.record_counter(
                "cache_operations",
                1,
                {"operation": "set", "result": "success"}
            )
            
            return bool(result)
            
        except Exception as e:
            self.cache_stats['errors'] += 1
            self.cache_stats['total_operations'] += 1
            
            logger.error(
                "Cache set operation failed",
                key=key,
                error=str(e),
                exc_info=True
            )
            
            metrics_collector.record_counter(
                "cache_operations",
                1,
                {"operation": "set", "result": "error"}
            )
            
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            result = await self.redis_client.delete(key)
            
            self.cache_stats['deletes'] += 1
            self.cache_stats['total_operations'] += 1
            
            metrics_collector.record_counter(
                "cache_operations",
                1,
                {"operation": "delete", "result": "success"}
            )
            
            return bool(result)
            
        except Exception as e:
            self.cache_stats['errors'] += 1
            
            logger.error("Cache delete operation failed", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            result = await self.redis_client.exists(key)
            return bool(result)
        except Exception as e:
            logger.error("Cache exists check failed", key=key, error=str(e))
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for key"""
        try:
            result = await self.redis_client.expire(key, ttl)
            return bool(result)
        except Exception as e:
            logger.error("Cache expire operation failed", key=key, error=str(e))
            return False
    
    async def get_ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        try:
            ttl = await self.redis_client.ttl(key)
            return ttl
        except Exception as e:
            logger.error("Cache TTL check failed", key=key, error=str(e))
            return -1
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment counter with optional TTL"""
        try:
            # Use pipeline for atomic operation
            async with self.redis_client.pipeline() as pipe:
                await pipe.incr(key, amount)
                if ttl:
                    await pipe.expire(key, ttl)
                results = await pipe.execute()
                
            return results[0]
            
        except Exception as e:
            logger.error("Cache increment failed", key=key, error=str(e))
            return 0
    
    async def get_multiple(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple keys at once"""
        try:
            if not keys:
                return {}
            
            values = await self.redis_client.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        # Try to deserialize
                        if value.startswith(b'{') or value.startswith(b'['):
                            result[key] = json.loads(value.decode('utf-8'))
                        else:
                            result[key] = pickle.loads(value)
                    except (json.JSONDecodeError, pickle.UnpicklingError):
                        result[key] = value.decode('utf-8')
            
            return result
            
        except Exception as e:
            logger.error("Cache mget operation failed", keys=keys, error=str(e))
            return {}
    
    async def set_multiple(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple key-value pairs at once"""
        try:
            if not mapping:
                return True
            
            # Serialize all values
            serialized_mapping = {}
            for key, value in mapping.items():
                if isinstance(value, (dict, list)):
                    serialized_mapping[key] = json.dumps(value, default=str).encode('utf-8')
                else:
                    serialized_mapping[key] = pickle.dumps(value)
            
            # Use pipeline for atomic operation
            async with self.redis_client.pipeline() as pipe:
                await pipe.mset(serialized_mapping)
                
                if ttl:
                    for key in mapping.keys():
                        await pipe.expire(key, ttl)
                
                await pipe.execute()
            
            return True
            
        except Exception as e:
            logger.error("Cache mset operation failed", error=str(e))
            return False
    
    async def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate keys matching pattern"""
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} keys matching pattern", pattern=pattern)
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error("Cache pattern invalidation failed", pattern=pattern, error=str(e))
            return 0
    
    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate keys by tags"""
        try:
            deleted_count = 0
            
            for tag in tags:
                tag_key = f"tag:{tag}"
                
                # Get all keys with this tag
                keys = await self.redis_client.smembers(tag_key)
                
                if keys:
                    # Delete the keys
                    deleted = await self.redis_client.delete(*keys)
                    deleted_count += deleted
                    
                    # Remove the tag set
                    await self.redis_client.delete(tag_key)
            
            logger.info(f"Invalidated {deleted_count} keys by tags", tags=tags)
            return deleted_count
            
        except Exception as e:
            logger.error("Cache tag invalidation failed", tags=tags, error=str(e))
            return 0
    
    async def _add_tags_to_key(self, key: str, tags: List[str]):
        """Add tags to key for invalidation purposes"""
        try:
            async with self.redis_client.pipeline() as pipe:
                for tag in tags:
                    tag_key = f"tag:{tag}"
                    await pipe.sadd(tag_key, key)
                await pipe.execute()
                
        except Exception as e:
            logger.error("Failed to add tags to key", key=key, tags=tags, error=str(e))
    
    async def acquire_lock(
        self,
        lock_name: str,
        timeout: int = 10,
        blocking_timeout: int = 5
    ) -> Optional[str]:
        """
        Acquire distributed lock
        
        Args:
            lock_name: Name of the lock
            timeout: Lock timeout in seconds
            blocking_timeout: How long to wait for lock
            
        Returns:
            Lock identifier if acquired, None otherwise
        """
        try:
            lock_key = f"{self.key_prefixes['lock']}{lock_name}"
            lock_value = f"{datetime.utcnow().timestamp()}:{id(self)}"
            
            # Try to acquire lock with timeout
            start_time = time.time()
            
            while time.time() - start_time < blocking_timeout:
                # Try to set lock with NX (only if not exists) and EX (expiration)
                result = await self.redis_client.set(
                    lock_key, lock_value, nx=True, ex=timeout
                )
                
                if result:
                    logger.debug("Lock acquired", lock_name=lock_name, lock_value=lock_value)
                    return lock_value
                
                # Wait a bit before retrying
                await asyncio.sleep(0.1)
            
            logger.warning("Failed to acquire lock within timeout", lock_name=lock_name)
            return None
            
        except Exception as e:
            logger.error("Lock acquisition failed", lock_name=lock_name, error=str(e))
            return None
    
    async def release_lock(self, lock_name: str, lock_value: str) -> bool:
        """
        Release distributed lock
        
        Args:
            lock_name: Name of the lock
            lock_value: Lock identifier from acquire_lock
            
        Returns:
            True if released, False otherwise
        """
        try:
            lock_key = f"{self.key_prefixes['lock']}{lock_name}"
            
            # Use Lua script for atomic check-and-delete
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            
            result = await self.redis_client.eval(lua_script, 1, lock_key, lock_value)
            
            if result:
                logger.debug("Lock released", lock_name=lock_name)
                return True
            else:
                logger.warning("Lock release failed - value mismatch", lock_name=lock_name)
                return False
                
        except Exception as e:
            logger.error("Lock release failed", lock_name=lock_name, error=str(e))
            return False
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get comprehensive cache information"""
        try:
            # Get Redis info
            redis_info = await self.redis_client.info()
            
            # Calculate hit rate
            total_ops = self.cache_stats['hits'] + self.cache_stats['misses']
            hit_rate = (self.cache_stats['hits'] / total_ops * 100) if total_ops > 0 else 0
            
            return {
                'redis': {
                    'connected': True,
                    'version': redis_info.get('redis_version'),
                    'memory_used': redis_info.get('used_memory_human'),
                    'memory_peak': redis_info.get('used_memory_peak_human'),
                    'connected_clients': redis_info.get('connected_clients'),
                    'total_commands_processed': redis_info.get('total_commands_processed'),
                    'keyspace_hits': redis_info.get('keyspace_hits', 0),
                    'keyspace_misses': redis_info.get('keyspace_misses', 0)
                },
                'service_stats': {
                    **self.cache_stats,
                    'hit_rate_percent': round(hit_rate, 2)
                },
                'configuration': {
                    'default_ttl': self.default_ttl,
                    'query_cache_ttl': self.query_cache_ttl,
                    'embedding_cache_ttl': self.embedding_cache_ttl,
                    'max_connections': settings.cache.max_connections
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'redis': {'connected': False, 'error': str(e)},
                'service_stats': self.cache_stats,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Redis service"""
        health_start = time.time()
        
        try:
            # Test basic operations
            await self.redis_client.ping()
            
            # Test set/get/delete
            test_key = "health:check"
            test_value = f"test_{int(time.time())}"
            
            await self.redis_client.set(test_key, test_value, ex=10)
            retrieved_value = await self.redis_client.get(test_key)
            await self.redis_client.delete(test_key)
            
            if retrieved_value.decode('utf-8') != test_value:
                raise Exception("Health check set/get/delete test failed")
            
            health_duration_ms = int((time.time() - health_start) * 1000)
            
            return {
                'status': 'healthy',
                'response_time_ms': health_duration_ms,
                'operations_tested': ['ping', 'set', 'get', 'delete'],
                'statistics': self.cache_stats
            }
            
        except Exception as e:
            health_duration_ms = int((time.time() - health_start) * 1000)
            
            return {
                'status': 'unhealthy',
                'response_time_ms': health_duration_ms,
                'error': str(e),
                'statistics': self.cache_stats
            }
    
    async def cleanup_expired_keys(self):
        """Clean up expired keys and optimize memory usage"""
        try:
            # Get memory info before cleanup
            info_before = await self.redis_client.info('memory')
            memory_before = info_before.get('used_memory', 0)
            
            # Force expire check on sample of keys
            sample_size = 1000
            expired_count = 0
            
            async for key in self.redis_client.scan_iter(count=sample_size):
                ttl = await self.redis_client.ttl(key)
                if ttl == -2:  # Key expired
                    expired_count += 1
            
            # Get memory info after
            info_after = await self.redis_client.info('memory')
            memory_after = info_after.get('used_memory', 0)
            
            memory_freed = memory_before - memory_after
            
            logger.info(
                "Cache cleanup completed",
                expired_keys=expired_count,
                memory_freed_bytes=memory_freed,
                memory_before=memory_before,
                memory_after=memory_after
            )
            
        except Exception as e:
            logger.error("Cache cleanup failed", error=str(e))
    
    async def close(self):
        """Close Redis connections"""
        try:
            if self.redis_client:
                await self.redis_client.close()
            
            if self.connection_pool:
                await self.connection_pool.disconnect()
            
            logger.info("Redis connections closed")
            
        except Exception as e:
            logger.error("Error closing Redis connections", error=str(e))

# Global service instance
azure_redis_service = AzureRedisService()