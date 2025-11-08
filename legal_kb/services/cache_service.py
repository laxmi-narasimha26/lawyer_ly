"""
Caching service for Advanced Legal KB+RAG System
Implements intelligent caching strategies for performance optimization
"""
import json
import hashlib
import asyncio
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
import logging
from dataclasses import asdict

from ..database.connection import get_db_manager
from ..models.legal_models import SearchResult, SearchResults

logger = logging.getLogger(__name__)

class CacheService:
    """Intelligent caching service with LRU eviction and TTL"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.query_embedding_cache_size = 50000  # LRU cache for query embeddings
        self.result_cache_ttl = 3600  # 1 hour TTL for hot queries
        self.document_cache_ttl = 86400  # 24 hours for document cache
        
    async def initialize(self):
        """Initialize cache service"""
        db_manager = await get_db_manager()
        self.redis_client = db_manager.redis_client
        logger.info("Cache service initialized")
    
    def _generate_cache_key(self, prefix: str, data: Union[str, Dict, List]) -> str:
        """Generate consistent cache key"""
        if isinstance(data, str):
            content = data
        else:
            content = json.dumps(data, sort_keys=True)
        
        hash_obj = hashlib.sha256(content.encode())
        return f"{prefix}:{hash_obj.hexdigest()[:16]}"
    
    async def cache_query_embedding(self, query: str, embedding: List[float]) -> bool:
        """Cache query embedding with LRU eviction"""
        try:
            cache_key = self._generate_cache_key("query_emb", query)
            
            # Store embedding with metadata
            cache_data = {
                "embedding": embedding,
                "query": query,
                "cached_at": datetime.now().isoformat(),
                "access_count": 1
            }
            
            # Set with TTL and update LRU
            await self.redis_client.setex(
                cache_key, 
                self.result_cache_ttl, 
                json.dumps(cache_data)
            )
            
            # Maintain LRU list
            await self.redis_client.lpush("query_emb_lru", cache_key)
            await self.redis_client.ltrim("query_emb_lru", 0, self.query_embedding_cache_size - 1)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache query embedding: {e}")
            return False
    
    async def get_cached_query_embedding(self, query: str) -> Optional[List[float]]:
        """Retrieve cached query embedding"""
        try:
            cache_key = self._generate_cache_key("query_emb", query)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                
                # Update access count and LRU position
                data["access_count"] += 1
                data["last_accessed"] = datetime.now().isoformat()
                
                await self.redis_client.setex(
                    cache_key, 
                    self.result_cache_ttl, 
                    json.dumps(data)
                )
                
                # Move to front of LRU list
                await self.redis_client.lrem("query_emb_lru", 1, cache_key)
                await self.redis_client.lpush("query_emb_lru", cache_key)
                
                return data["embedding"]
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached query embedding: {e}")
            return None
    
    async def cache_search_results(self, query: str, results: SearchResults) -> bool:
        """Cache search results for hot queries"""
        try:
            cache_key = self._generate_cache_key("search_results", query)
            
            # Convert results to cacheable format
            cache_data = {
                "statutes": [asdict(result) for result in results.statutes],
                "cases": [asdict(result) for result in results.cases],
                "total_retrieved": results.total_retrieved,
                "processing_time": results.processing_time,
                "cached_at": datetime.now().isoformat()
            }
            
            await self.redis_client.setex(
                cache_key,
                self.result_cache_ttl,
                json.dumps(cache_data)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache search results: {e}")
            return False
    
    async def get_cached_search_results(self, query: str) -> Optional[SearchResults]:
        """Retrieve cached search results"""
        try:
            cache_key = self._generate_cache_key("search_results", query)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                
                # Reconstruct SearchResults object
                statutes = [SearchResult(**result) for result in data["statutes"]]
                cases = [SearchResult(**result) for result in data["cases"]]
                
                return SearchResults(
                    statutes=statutes,
                    cases=cases,
                    total_retrieved=data["total_retrieved"],
                    processing_time=data["processing_time"]
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached search results: {e}")
            return None
    
    async def cache_document_embeddings(self, document_id: str, embeddings: List[float]) -> bool:
        """Cache document embeddings for core legal documents"""
        try:
            cache_key = f"doc_emb:{document_id}"
            
            cache_data = {
                "embeddings": embeddings,
                "document_id": document_id,
                "cached_at": datetime.now().isoformat()
            }
            
            # Core documents get longer TTL
            ttl = self.document_cache_ttl * 7 if self._is_core_document(document_id) else self.document_cache_ttl
            
            await self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(cache_data)
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to cache document embeddings: {e}")
            return False

    async def cache_retrieval_payload(self, query: str, statute_k: int, case_k: int, payload: Dict[str, Any]) -> bool:
        try:
            key_data = {"query": query, "statute_k": statute_k, "case_k": case_k}
            cache_key = self._generate_cache_key("retrieval_payload", key_data)
            cache_data = {
                "payload": payload,
                "cached_at": datetime.now().isoformat()
            }
            await self.redis_client.setex(
                cache_key,
                self.result_cache_ttl,
                json.dumps(cache_data, ensure_ascii=False, default=str)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to cache retrieval payload: {e}")
            return False

    async def get_cached_retrieval_payload(self, query: str, statute_k: int, case_k: int) -> Optional[Dict[str, Any]]:
        try:
            key_data = {"query": query, "statute_k": statute_k, "case_k": case_k}
            cache_key = self._generate_cache_key("retrieval_payload", key_data)
            cached = await self.redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return data.get("payload")
            return None
        except Exception as e:
            logger.error(f"Failed to load cached retrieval payload: {e}")
            return None
    
    async def get_cached_document_embeddings(self, document_id: str) -> Optional[List[float]]:
        """Retrieve cached document embeddings"""
        try:
            cache_key = f"doc_emb:{document_id}"
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                return data["embeddings"]
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve cached document embeddings: {e}")
            return None
    
    def _is_core_document(self, document_id: str) -> bool:
        """Check if document is a core legal document for permanent caching"""
        core_prefixes = [
            "CONSTITUTION:",
            "BNS:2023:",
            "BNSS:2023:",
            "BSA:2023:"
        ]
        return any(document_id.startswith(prefix) for prefix in core_prefixes)
    
    async def invalidate_cache_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern"""
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries matching pattern: {pattern}")
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache pattern {pattern}: {e}")
            return 0
    
    async def invalidate_knowledge_base_cache(self):
        """Invalidate all knowledge base related cache when KB is updated"""
        patterns = [
            "search_results:*",
            "doc_emb:*",
            "query_emb:*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            deleted = await self.invalidate_cache_pattern(pattern)
            total_deleted += deleted
        
        logger.info(f"Knowledge base cache invalidation completed. Deleted {total_deleted} entries.")
        return total_deleted
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        try:
            info = await self.redis_client.info()
            
            # Count cache entries by type
            query_emb_count = await self.redis_client.eval(
                "return #redis.call('keys', 'query_emb:*')", 0
            )
            search_results_count = await self.redis_client.eval(
                "return #redis.call('keys', 'search_results:*')", 0
            )
            doc_emb_count = await self.redis_client.eval(
                "return #redis.call('keys', 'doc_emb:*')", 0
            )
            
            return {
                "redis_memory_used": info.get("used_memory_human", "N/A"),
                "redis_connected_clients": info.get("connected_clients", 0),
                "query_embedding_cache_count": query_emb_count,
                "search_results_cache_count": search_results_count,
                "document_embedding_cache_count": doc_emb_count,
                "total_keys": await self.redis_client.dbsize()
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e)}
    
    async def cleanup_expired_entries(self) -> int:
        """Clean up expired cache entries (called periodically)"""
        try:
            # Redis handles TTL automatically, but we can clean up LRU list
            lru_length = await self.redis_client.llen("query_emb_lru")
            
            if lru_length > self.query_embedding_cache_size:
                # Remove excess entries from LRU list
                excess = lru_length - self.query_embedding_cache_size
                removed_keys = await self.redis_client.lrange("query_emb_lru", -excess, -1)
                
                # Remove the actual cache entries
                if removed_keys:
                    await self.redis_client.delete(*removed_keys)
                
                # Trim the LRU list
                await self.redis_client.ltrim("query_emb_lru", 0, self.query_embedding_cache_size - 1)
                
                logger.info(f"Cleaned up {len(removed_keys)} expired cache entries")
                return len(removed_keys)
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired entries: {e}")
            return 0

# Global cache service instance
cache_service: Optional[CacheService] = None

async def get_cache_service() -> CacheService:
    """Get the global cache service instance"""
    global cache_service
    if cache_service is None:
        cache_service = CacheService()
        await cache_service.initialize()
    return cache_service
