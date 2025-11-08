"""
Embedding Generation Service for Advanced Legal KB+RAG System
Uses OpenAI text-embedding-3-small with token-aware chunking for reliable embeddings
"""
import asyncio
import logging
import time
from typing import Any, List, Optional, Tuple, Dict

import hashlib
import json

import numpy as np
import openai
import tiktoken

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None

from legal_kb.utils.token_aware_chunking import TokenAwareChunker, ChunkMetadata

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating and managing document embeddings with token awareness"""

    def __init__(self, api_key: str):
        from legal_kb.config import Config

        self.config = Config()
        # Best-effort Redis client (sync); safe to call from async for our eval harness scale
        self.redis = None
        if redis is not None:
            try:
                self.redis = redis.Redis(
                    host=self.config.REDIS_HOST,
                    port=self.config.REDIS_PORT,
                    db=self.config.REDIS_DB,
                    password=self.config.REDIS_PASSWORD,
                )
                self.redis.ping()
                logger.info("Redis cache connected")
            except Exception as e:  # pragma: no cover
                self.redis = None
                logger.warning(f"Redis unavailable: {e}")

        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_bypass = 0
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = "text-embedding-3-small"  # 1536 dimensions, cheaper, reliable
        self.batch_size = 128  # Smaller batches for reliability
        self.max_retries = 3
        self.retry_delay = 1.0  # Base delay for exponential backoff
        
        # Token-aware chunking
        self.chunker = TokenAwareChunker(self.model)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Request size limits
        self.max_request_size = 1024 * 1024  # 1MB JSON payload limit
        
    async def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text with token validation + Redis cache."""
        try:
            # Cache lookup
            key = None
            redis_available = self.redis is not None
            cached = None
            if redis_available:
                norm = (text or "").strip().lower()
                key = "emb:v1:" + hashlib.sha256(norm.encode("utf-8")).hexdigest()
                try:
                    cached = self.redis.get(key)
                except Exception:  # pragma: no cover
                    redis_available = False
                    cached = None
                    self.cache_bypass += 1
            else:
                self.cache_bypass += 1

            if cached:
                try:
                    if isinstance(cached, (bytes, bytearray)):
                        vec = np.frombuffer(cached, dtype=np.float32)
                    else:
                        arr = json.loads(cached)
                        vec = np.array(arr, dtype=np.float32)
                    self.cache_hits += 1
                    return self._normalize_embedding(vec.tolist())
                except Exception:
                    # fall through to fresh call
                    pass
            elif redis_available:
                self.cache_misses += 1

            # Validate token count before sending
            token_count = self.chunker.count_tokens(text)
            if token_count > 8192:
                logger.error(f"Text has {token_count} tokens, exceeds limit of 8192")
                raise ValueError(f"Text too long: {token_count} tokens > 8192 limit")
            
            if token_count > 1800:
                logger.warning(f"Text has {token_count} tokens, consider chunking")
            
            # Generate embedding (fresh)
            response = await self._call_openai_with_retry(text)
            embedding = response.data[0].embedding

            # Normalize embedding (L2 normalization)
            normalized_embedding = self._normalize_embedding(embedding)

            # Store in cache (24h) as float32 bytes
            if redis_available and self.redis is not None and key is not None:
                try:
                    arr = np.array(normalized_embedding, dtype=np.float32)
                    self.redis.set(key, arr.tobytes(), ex=86400)
                except Exception:  # pragma: no cover
                    pass

            return normalized_embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding for text ({len(text)} chars): {e}")
            raise
    
    async def get_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in token-aware batches"""
        all_embeddings = []
        
        # Validate all texts first
        validated_texts = []
        for i, text in enumerate(texts):
            token_count = self.chunker.count_tokens(text)
            if token_count > 8192:
                logger.error(f"Text {i} has {token_count} tokens, skipping")
                validated_texts.append("")  # Empty text for failed validation
            else:
                validated_texts.append(text)
        
        # Process in token-aware batches
        current_batch = []
        current_batch_tokens = 0
        
        for i, text in enumerate(validated_texts):
            if not text:  # Skip empty/failed texts
                all_embeddings.append([0.0] * 1536)  # Zero vector for text-embedding-3-small
                continue
            
            text_tokens = self.chunker.count_tokens(text)
            
            # Check if adding this text would exceed batch limits
            if (len(current_batch) >= self.batch_size or 
                current_batch_tokens + text_tokens > 100000 or  # Conservative token limit per batch
                self._estimate_request_size(current_batch + [text]) > self.max_request_size):
                
                # Process current batch
                if current_batch:
                    try:
                        batch_embeddings = await self._process_batch(current_batch)
                        all_embeddings.extend(batch_embeddings)
                        await asyncio.sleep(0.1)  # Rate limiting
                    except Exception as e:
                        logger.error(f"Batch processing failed, falling back to individual: {e}")
                        # Fallback to individual processing
                        for batch_text in current_batch:
                            try:
                                embedding = await self.get_embedding(batch_text)
                                all_embeddings.append(embedding)
                            except Exception:
                                all_embeddings.append([0.0] * 1536)
                
                # Start new batch
                current_batch = [text]
                current_batch_tokens = text_tokens
            else:
                current_batch.append(text)
                current_batch_tokens += text_tokens
        
        # Process final batch
        if current_batch:
            try:
                batch_embeddings = await self._process_batch(current_batch)
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Final batch processing failed: {e}")
                for batch_text in current_batch:
                    try:
                        embedding = await self.get_embedding(batch_text)
                        all_embeddings.append(embedding)
                    except Exception:
                        all_embeddings.append([0.0] * 1536)
        
        return all_embeddings
    
    async def _process_batch(self, texts: List[str]) -> List[List[float]]:
        """Process a batch of texts"""
        try:
            response = await self._call_openai_batch_with_retry(texts)
            
            embeddings = []
            for embedding_data in response.data:
                embedding = embedding_data.embedding
                normalized_embedding = self._normalize_embedding(embedding)
                embeddings.append(normalized_embedding)
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise
    
    async def _call_openai_with_retry(self, text: str) -> Any:
        """Call OpenAI API with proper retry logic (no retry on 400 errors)"""
        for attempt in range(self.max_retries):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=text,
                    encoding_format="float"
                )
                return response
                
            except openai.BadRequestError as e:
                # 400 errors are caller errors - don't retry
                logger.error(f"Bad request (400) - not retrying: {e}")
                token_count = self.chunker.count_tokens(text)
                logger.error(f"Text token count: {token_count}, char count: {len(text)}")
                raise
                
            except openai.RateLimitError as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt) + (attempt * 0.5)  # Add jitter
                    logger.warning(f"Rate limit (429), retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Rate limit exceeded after {self.max_retries} attempts")
                    raise
                    
            except (openai.APIError, openai.InternalServerError) as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt) + (attempt * 0.5)
                    logger.warning(f"API/Server error (5xx), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"API error after {self.max_retries} attempts: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error in OpenAI call: {e}")
                raise
    
    async def _call_openai_batch_with_retry(self, texts: List[str]) -> Any:
        """Call OpenAI API for batch processing with proper retry logic"""
        for attempt in range(self.max_retries):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                    encoding_format="float"
                )
                return response
                
            except openai.BadRequestError as e:
                # 400 errors are caller errors - don't retry
                logger.error(f"Bad request (400) on batch - not retrying: {e}")
                total_tokens = sum(self.chunker.count_tokens(text) for text in texts)
                logger.error(f"Batch size: {len(texts)}, total tokens: {total_tokens}")
                for i, text in enumerate(texts):
                    token_count = self.chunker.count_tokens(text)
                    if token_count > 8192:
                        logger.error(f"Text {i} has {token_count} tokens (exceeds limit)")
                raise
                
            except openai.RateLimitError as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt) + (attempt * 0.5)
                    logger.warning(f"Rate limit (429) on batch, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Rate limit exceeded on batch after {self.max_retries} attempts")
                    raise
                    
            except (openai.APIError, openai.InternalServerError) as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt) + (attempt * 0.5)
                    logger.warning(f"API/Server error (5xx) on batch, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"API error on batch after {self.max_retries} attempts: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error in batch OpenAI call: {e}")
                raise
    
    def _normalize_embedding(self, embedding: List[float]) -> List[float]:
        """Normalize embedding using L2 normalization"""
        embedding_array = np.array(embedding)
        
        # text-embedding-3-small returns 1536 dimensions
        if len(embedding_array) != 1536:
            logger.warning(f"Unexpected embedding dimension: {len(embedding_array)}")
        
        norm = np.linalg.norm(embedding_array)
        
        if norm == 0:
            return embedding_array.tolist()  # Return original if norm is zero
        
        normalized = embedding_array / norm
        return normalized.tolist()
    
    def _estimate_request_size(self, texts: List[str]) -> int:
        """Estimate JSON request size in bytes"""
        # Rough estimate: JSON overhead + text content
        total_chars = sum(len(text) for text in texts)
        json_overhead = len(texts) * 50  # Rough JSON structure overhead per text
        return total_chars + json_overhead
    
    async def embed_legal_chunks(self, chunks: List[Tuple[str, ChunkMetadata]]) -> List[Tuple[List[float], ChunkMetadata]]:
        """Embed legal document chunks with metadata preservation"""
        logger.info(f"Embedding {len(chunks)} legal chunks")
        
        # Extract texts and validate
        texts = []
        metadatas = []
        for text, metadata in chunks:
            if self.chunker.validate_chunk_size(text):
                texts.append(text)
                metadatas.append(metadata)
            else:
                logger.error(f"Chunk {metadata.chunk_id} exceeds token limit, skipping")
        
        # Generate embeddings
        embeddings = await self.get_batch_embeddings(texts)
        
        # Combine with metadata
        result = []
        for embedding, metadata in zip(embeddings, metadatas):
            result.append((embedding, metadata))
        
        logger.info(f"Successfully embedded {len(result)} chunks")
        return result
    
    async def test_api_connection(self) -> bool:
        """Test OpenAI API connection"""
        try:
            test_embedding = await self.get_embedding("test")
            return len(test_embedding) == 1536  # text-embedding-3-small dimensions
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False

    def close(self) -> None:
        if self.redis is not None:
            try:
                self.redis.close()
            except Exception:  # pragma: no cover
                pass

