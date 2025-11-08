"""
Production-grade cache management system for Indian Legal AI Assistant
Implements sophisticated caching strategies with Azure Redis backend
"""
import json
import hashlib
import pickle
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
import structlog

from config.settings import settings
from services.azure_redis_service import azure_redis_service

logger = structlog.get_logger(__name__)

class CacheManager:
    """
    Production-grade cache management system
    
    Features:
    - Multi-level caching (memory + Redis)
    - Intelligent cache key generation
    - TTL management and expiration
    - Cache warming and preloading
    - Performance monitoring
    - Automatic cache invalidation
    """
    
    def __init__(self):
        self.redis_service = azure_redis_service
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'memory_size': 0,
            'redis_operations': 0
        }
        
        # Cache configuration
        self.max_memory_items = 1000
        self.default_ttl = settings.cache.default_ttl
        self.query_cache_ttl = settings.cache.query_cache_ttl
        self.embedding_cache_ttl = settings.cache.embedding_cache_ttl
        
        logger.info("Cache manager initialized")
    
    async def initialize(self):
        """Initialize Azure Redis connection"""
        try:
            await self.redis_service.initialize()
            logger.info("Cache manager with Azure Redis initialized successfully")
            
        except Exception as e:
            logger.warning("Azure Redis connection failed, using memory cache only", error=str(e))
            self.redis_service = None
    
    async def get(self, key: str, use_memory: bool = True) -> Optional[Any]:
        """
        Get value from cache with multi-level lookup
        
        Args:
            key: Cache key
            use_memory: Whether to check memory cache first
            
        Returns:
            Cached value or None if not found
        """
        try:
            # Check memory cache first
            if use_memory and key in self.memory_cache:
                cache_entry = self.memory_cache[key]
                
                # Check if expired
                if self._is_expired(cache_entry):
                    del self.memory_cache[key]
                else:
                    self.cache_stats['hits'] += 1
                    logger.debug("Memory cache hit", key=key[:16])
                    return cache_entry['value']
            
            # Check Azure Redis cache
            if self.redis_service:
                try:
                    value = await self.redis_service.get(key, deserialize=True)
                    if value is not None:
                        # Store in memory cache for faster access
                        if use_memory:
                            self._set_memory_cache(key, value, self.default_ttl)
                        
                        self.cache_stats['hits'] += 1
                        self.cache_stats['redis_operations'] += 1
                        logger.debug("Azure Redis cache hit", key=key[:16])
                        return value
                        
                except Exception as e:
                    logger.warning("Azure Redis get operation failed", key=key[:16], error=str(e))
            
            self.cache_stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error("Cache get operation failed", key=key[:16], error=str(e))
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        use_memory: bool = True
    ) -> bool:
        """
        Set value in cache with multi-level storage
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            use_memory: Whether to store in memory cache
            
        Returns:
            True if successful, False otherwise
        """
        try:
            ttl = ttl or self.default_ttl
            
            # Store in memory cache
            if use_memory:
                self._set_memory_cache(key, value, ttl)
            
            # Store in Azure Redis cache
            if self.redis_service:
                try:
                    success = await self.redis_service.set(key, value, ttl=ttl, serialize=True)
                    if success:
                        self.cache_stats['redis_operations'] += 1
                    else:
                        logger.warning("Azure Redis set operation failed", key=key[:16])
                        return False
                    
                except Exception as e:
                    logger.warning("Azure Redis set operation failed", key=key[:16], error=str(e))
                    return False
            
            self.cache_stats['sets'] += 1
            logger.debug("Cache set successful", key=key[:16], ttl=ttl)
            return True
            
        except Exception as e:
            logger.error("Cache set operation failed", key=key[:16], error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from all cache levels"""
        try:
            # Delete from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            # Delete from Azure Redis cache
            if self.redis_service:
                try:
                    success = await self.redis_service.delete(key)
                    if success:
                        self.cache_stats['redis_operations'] += 1
                except Exception as e:
                    logger.warning("Azure Redis delete operation failed", key=key[:16], error=str(e))
            
            self.cache_stats['deletes'] += 1
            return True
            
        except Exception as e:
            logger.error("Cache delete operation failed", key=key[:16], error=str(e))
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        cleared_count = 0
        
        try:
            # Clear from memory cache
            keys_to_delete = [key for key in self.memory_cache.keys() if self._matches_pattern(key, pattern)]
            for key in keys_to_delete:
                del self.memory_cache[key]
                cleared_count += 1
            
            # Clear from Azure Redis cache
            if self.redis_service:
                try:
                    redis_cleared = await self.redis_service.invalidate_by_pattern(pattern)
                    cleared_count += redis_cleared
                    self.cache_stats['redis_operations'] += 1
                        
                except Exception as e:
                    logger.warning("Azure Redis pattern clear failed", pattern=pattern, error=str(e))
            
            logger.info("Cache pattern cleared", pattern=pattern, cleared_count=cleared_count)
            return cleared_count
            
        except Exception as e:
            logger.error("Cache pattern clear failed", pattern=pattern, error=str(e))
            return 0
    
    def generate_query_cache_key(
        self,
        query: str,
        mode: str,
        document_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> str:
        """Generate cache key for query results"""
        key_parts = ['query', query, mode]
        
        if document_ids:
            key_parts.extend(sorted(document_ids))
        
        if user_id:
            key_parts.append(user_id)
        
        key_string = '|'.join(key_parts)
        return f"query:{hashlib.sha256(key_string.encode()).hexdigest()[:16]}"
    
    def generate_embedding_cache_key(self, text: str) -> str:
        """Generate cache key for embeddings"""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"embedding:{text_hash}"
    
    def generate_document_cache_key(self, document_id: str, user_id: str) -> str:
        """Generate cache key for document metadata"""
        return f"document:{user_id}:{document_id}"
    
    async def cache_query_result(
        self,
        query: str,
        mode: str,
        result: Any,
        document_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        confidence_score: Optional[float] = None
    ) -> bool:
        """Cache query result with intelligent TTL based on confidence and complexity"""
        cache_key = self.generate_query_cache_key(query, mode, document_ids, user_id)
        
        # Intelligent TTL based on result quality and query characteristics
        ttl = self._calculate_intelligent_ttl(query, mode, confidence_score)
        
        # Add cache tags for invalidation
        tags = self._generate_cache_tags(query, mode, document_ids, user_id)
        
        return await self.set(cache_key, result, ttl=ttl, use_memory=True)
    
    async def get_cached_query_result(
        self,
        query: str,
        mode: str,
        document_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> Optional[Any]:
        """Get cached query result"""
        cache_key = self.generate_query_cache_key(query, mode, document_ids, user_id)
        return await self.get(cache_key)
    
    async def cache_embedding(self, text: str, embedding: List[float], is_frequent: bool = False) -> bool:
        """Cache text embedding with intelligent TTL and frequency-based optimization"""
        cache_key = self.generate_embedding_cache_key(text)
        
        # Longer TTL for frequently accessed embeddings
        ttl = self.embedding_cache_ttl * 2 if is_frequent else self.embedding_cache_ttl
        
        # Always cache embeddings in memory for fast access
        return await self.set(cache_key, embedding, ttl=ttl, use_memory=True)
    
    async def get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Get cached embedding"""
        cache_key = self.generate_embedding_cache_key(text)
        return await self.get(cache_key)
    
    async def warm_cache(self, warm_data: Dict[str, Any]):
        """Warm cache with frequently accessed data"""
        try:
            for key, data in warm_data.items():
                await self.set(key, data['value'], ttl=data.get('ttl', self.default_ttl))
            
            logger.info("Cache warming completed", items_count=len(warm_data))
            
        except Exception as e:
            logger.error("Cache warming failed", error=str(e))
    
    def _set_memory_cache(self, key: str, value: Any, ttl: int):
        """Set value in memory cache with TTL"""
        # Implement LRU eviction if cache is full
        if len(self.memory_cache) >= self.max_memory_items:
            self._evict_lru_items()
        
        expiry_time = datetime.utcnow() + timedelta(seconds=ttl)
        self.memory_cache[key] = {
            'value': value,
            'expiry': expiry_time,
            'access_time': datetime.utcnow()
        }
        
        self.cache_stats['memory_size'] = len(self.memory_cache)
    
    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is expired"""
        return datetime.utcnow() > cache_entry['expiry']
    
    def _evict_lru_items(self, count: int = 100):
        """Evict least recently used items from memory cache"""
        if len(self.memory_cache) <= count:
            return
        
        # Sort by access time and remove oldest
        sorted_items = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1]['access_time']
        )
        
        for i in range(count):
            key = sorted_items[i][0]
            del self.memory_cache[key]
        
        self.cache_stats['memory_size'] = len(self.memory_cache)
        logger.debug("LRU eviction completed", evicted_count=count)
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for Redis storage"""
        try:
            # Try JSON first for simple types
            if isinstance(value, (dict, list, str, int, float, bool, type(None))):
                return json.dumps(value, default=str).encode('utf-8')
            else:
                # Use pickle for complex objects
                return pickle.dumps(value)
        except Exception:
            # Fallback to pickle
            return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from Redis storage"""
        try:
            # Try JSON first
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fallback to pickle
            return pickle.loads(data)
    
    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern (simple glob-style)"""
        import fnmatch
        return fnmatch.fnmatch(key, pattern)
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get comprehensive cache information"""
        info = {
            'memory_cache': {
                'size': len(self.memory_cache),
                'max_size': self.max_memory_items,
                'utilization': len(self.memory_cache) / self.max_memory_items
            },
            'statistics': self.cache_stats.copy(),
            'configuration': {
                'default_ttl': self.default_ttl,
                'query_cache_ttl': self.query_cache_ttl,
                'embedding_cache_ttl': self.embedding_cache_ttl
            }
        }
        
        # Add Azure Redis info if available
        if self.redis_service:
            try:
                redis_info = await self.redis_service.get_cache_info()
                info['redis'] = redis_info.get('redis', {'connected': False})
                info['service_stats'] = redis_info.get('service_stats', {})
            except Exception as e:
                info['redis'] = {'connected': False, 'error': str(e)}
        else:
            info['redis'] = {'connected': False, 'error': 'Not initialized'}
        
        return info
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        if total_requests == 0:
            return 0.0
        return self.cache_stats['hits'] / total_requests
    
    def _calculate_intelligent_ttl(
        self,
        query: str,
        mode: str,
        confidence_score: Optional[float] = None
    ) -> int:
        """Calculate intelligent TTL based on query characteristics and result quality"""
        base_ttl = self.query_cache_ttl
        
        # Adjust TTL based on confidence score
        if confidence_score:
            if confidence_score >= 0.9:
                base_ttl = int(base_ttl * 1.5)  # High confidence - cache longer
            elif confidence_score <= 0.6:
                base_ttl = int(base_ttl * 0.5)  # Low confidence - cache shorter
        
        # Adjust TTL based on query complexity
        query_length = len(query.split())
        if query_length > 20:  # Complex queries
            base_ttl = int(base_ttl * 1.3)
        elif query_length < 5:  # Simple queries
            base_ttl = int(base_ttl * 0.8)
        
        # Adjust TTL based on mode
        if mode == 'drafting':
            base_ttl = int(base_ttl * 0.7)  # Drafting results may be less reusable
        elif mode == 'qa':
            base_ttl = int(base_ttl * 1.2)  # Q&A results are more reusable
        
        return max(300, min(7200, base_ttl))  # Clamp between 5 minutes and 2 hours
    
    def _generate_cache_tags(
        self,
        query: str,
        mode: str,
        document_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> List[str]:
        """Generate cache tags for intelligent invalidation"""
        tags = [f"mode:{mode}"]
        
        if user_id:
            tags.append(f"user:{user_id}")
        
        if document_ids:
            for doc_id in document_ids:
                tags.append(f"doc:{doc_id}")
        
        # Add legal domain tags based on query content
        query_lower = query.lower()
        if any(term in query_lower for term in ['contract', 'agreement', 'breach']):
            tags.append("domain:contract")
        if any(term in query_lower for term in ['criminal', 'ipc', 'crime']):
            tags.append("domain:criminal")
        if any(term in query_lower for term in ['constitution', 'fundamental', 'article']):
            tags.append("domain:constitutional")
        
        return tags
    
    async def invalidate_by_document_update(self, document_id: str, user_id: str) -> int:
        """Invalidate cache entries when a document is updated"""
        patterns = [
            f"*doc:{document_id}*",
            f"*user:{user_id}*"
        ]
        
        total_cleared = 0
        for pattern in patterns:
            cleared = await self.clear_pattern(pattern)
            total_cleared += cleared
        
        logger.info("Cache invalidated for document update", 
                   document_id=document_id, cleared_count=total_cleared)
        return total_cleared
    
    async def invalidate_by_knowledge_base_update(self, domain: Optional[str] = None) -> int:
        """Invalidate cache entries when knowledge base is updated"""
        if domain:
            pattern = f"*domain:{domain}*"
            cleared = await self.clear_pattern(pattern)
        else:
            # Clear all query caches but keep embeddings
            cleared = await self.clear_pattern("query:*")
        
        logger.info("Cache invalidated for knowledge base update", 
                   domain=domain, cleared_count=cleared)
        return cleared
    
    async def preload_frequent_queries(self, frequent_queries: List[Dict[str, Any]]):
        """Preload cache with frequently asked queries"""
        try:
            preload_count = 0
            for query_data in frequent_queries:
                cache_key = self.generate_query_cache_key(
                    query_data['query'],
                    query_data['mode'],
                    query_data.get('document_ids'),
                    query_data.get('user_id')
                )
                
                # Check if already cached
                if not await self.get(cache_key, use_memory=False):
                    # Cache with longer TTL for frequent queries
                    await self.set(
                        cache_key,
                        query_data['result'],
                        ttl=self.query_cache_ttl * 2,
                        use_memory=True
                    )
                    preload_count += 1
            
            logger.info("Frequent queries preloaded", count=preload_count)
            
        except Exception as e:
            logger.error("Failed to preload frequent queries", error=str(e))
    
    async def get_cache_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed cache performance metrics"""
        hit_rate = self.get_hit_rate()
        
        # Calculate memory efficiency
        memory_efficiency = (
            self.cache_stats['hits'] / max(1, len(self.memory_cache))
        )
        
        # Get Redis metrics if available
        redis_metrics = {}
        if self.redis_service:
            try:
                redis_info = await self.redis_service.get_cache_info()
                redis_metrics = redis_info.get('service_stats', {})
            except Exception:
                pass
        
        return {
            'hit_rate': hit_rate,
            'memory_efficiency': memory_efficiency,
            'memory_cache_size': len(self.memory_cache),
            'memory_cache_utilization': len(self.memory_cache) / self.max_memory_items,
            'operations': self.cache_stats,
            'redis_metrics': redis_metrics,
            'recommendations': self._generate_performance_recommendations(hit_rate, memory_efficiency)
        }
    
    def _generate_performance_recommendations(
        self,
        hit_rate: float,
        memory_efficiency: float
    ) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        if hit_rate < 0.3:
            recommendations.append("Consider increasing cache TTL or preloading frequent queries")
        
        if memory_efficiency < 0.5:
            recommendations.append("Memory cache may be oversized - consider reducing max_memory_items")
        
        if len(self.memory_cache) / self.max_memory_items > 0.9:
            recommendations.append("Memory cache is near capacity - consider increasing max_memory_items")
        
        if self.cache_stats['redis_operations'] > self.cache_stats['hits'] * 2:
            recommendations.append("High Redis operation count - optimize memory cache usage")
        
        return recommendations
    
    async def optimize_cache_performance(self):
        """Perform cache performance optimization"""
        try:
            # Clean up expired entries
            await self.cleanup_expired_entries()
            
            # Optimize memory cache size based on usage patterns
            if len(self.memory_cache) < self.max_memory_items * 0.5:
                # Cache is underutilized - could reduce size
                logger.info("Memory cache is underutilized", 
                           current_size=len(self.memory_cache),
                           max_size=self.max_memory_items)
            
            # Clear least recently used items if cache is full
            if len(self.memory_cache) >= self.max_memory_items * 0.9:
                self._evict_lru_items(int(self.max_memory_items * 0.1))
            
            # Optimize Redis cache if available
            if self.redis_service:
                await self.redis_service.cleanup_expired_keys()
            
            logger.info("Cache performance optimization completed")
            
        except Exception as e:
            logger.error("Cache optimization failed", error=str(e))
    
    async def cleanup_expired_entries(self):
        """Clean up expired entries from memory cache"""
        expired_keys = []
        current_time = datetime.utcnow()
        
        for key, entry in self.memory_cache.items():
            if current_time > entry['expiry']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        if expired_keys:
            self.cache_stats['memory_size'] = len(self.memory_cache)
            logger.debug("Expired entries cleaned", count=len(expired_keys))
    
    async def close(self):
        """Close cache connections"""
        if self.redis_service:
            await self.redis_service.close()
            logger.info("Cache connections closed")

# Global cache manager instance
cache_manager = CacheManager()