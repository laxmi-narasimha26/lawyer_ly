"""
Caching manager using Redis
"""
import structlog
import json
import hashlib
from typing import Optional, Any, List
import redis.asyncio as redis

from config import settings

logger = structlog.get_logger()

class CacheManager:
    def __init__(self):
        self.redis_client = None
        self.default_ttl = settings.CACHE_TTL_SECONDS
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False
            )
            logger.info("Redis cache initialized")
        except Exception as e:
            logger.warning("Redis initialization failed, caching disabled", error=str(e))
            self.redis_client = None
    
    def generate_cache_key(
        self,
        query: str,
        mode: str,
        document_ids: Optional[List[str]]
    ) -> str:
        """Generate cache key from query parameters"""
        key_parts = [query, mode]
        if document_ids:
            key_parts.extend(sorted(document_ids))
        
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning("Cache get failed", key=key[:8], error=str(e))
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        if not self.redis_client:
            return
        
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value, default=str)
            await self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            logger.warning("Cache set failed", key=key[:8], error=str(e))
    
    async def delete(self, key: str):
        """Delete value from cache"""
        if not self.redis_client:
            return
        
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.warning("Cache delete failed", key=key[:8], error=str(e))
    
    async def clear_pattern(self, pattern: str):
        """Clear all keys matching pattern"""
        if not self.redis_client:
            return
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning("Cache clear pattern failed", pattern=pattern, error=str(e))
