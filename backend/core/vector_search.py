"""
Production-grade vector search engine for semantic similarity
Optimized for legal document retrieval with PostgreSQL + PGVector
"""
import time
from typing import List, Dict, Any, Optional
import structlog
from sqlalchemy import select, and_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncAzureOpenAI

from config.settings import settings
from database import DocumentChunk, DocumentType

logger = structlog.get_logger(__name__)

class VectorSearchEngine:
    """
    High-performance vector search engine for legal documents
    
    Features:
    - Cosine similarity search with PGVector
    - Optimized indexing (HNSW/IVF)
    - Batch embedding generation
    - Query optimization
    - Performance monitoring
    """
    
    def __init__(self):
        self.openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai.api_key,
            api_version=settings.azure_openai.api_version,
            azure_endpoint=settings.azure_openai.endpoint
        )
        
        # Cache for embeddings to reduce API calls
        self._embedding_cache = {}
        
        logger.info("Vector search engine initialized")
    
    async def search(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        document_types: Optional[List[DocumentType]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        session: Optional[AsyncSession] = None,
        enable_legal_boosting: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Perform enhanced semantic similarity search with legal-specific optimizations
        
        Args:
            query: Search query text
            user_id: User ID for access control
            document_ids: Optional list of specific document IDs to search
            document_types: Optional list of document types to filter
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            session: Database session
            enable_legal_boosting: Enable legal term keyword boosting
            
        Returns:
            List of matching chunks with metadata and enhanced relevance scores
        """
        start_time = time.time()
        
        try:
            # Generate query embedding
            query_embedding = await self._get_embedding(query)
            
            # Extract legal terms for keyword boosting
            legal_terms = self._extract_legal_terms(query) if enable_legal_boosting else []
            case_citations = self._extract_case_citations(query) if enable_legal_boosting else []
            
            # Build search query with enhanced limit for re-ranking
            search_query = self._build_search_query(
                query_embedding=query_embedding,
                user_id=user_id,
                document_ids=document_ids,
                document_types=document_types,
                limit=limit * 3,  # Get more results for re-ranking
                similarity_threshold=max(0.5, similarity_threshold - 0.1)  # Lower threshold for initial search
            )
            
            # Execute search
            result = await session.execute(search_query)
            chunks = result.fetchall()
            
            # Apply legal-specific boosting and re-ranking
            enhanced_results = []
            for chunk, similarity_score in chunks:
                boosted_score = await self._apply_legal_boosting(
                    chunk, float(similarity_score), query, legal_terms, case_citations
                )
                
                # Apply relevance threshold filtering after boosting
                if boosted_score >= similarity_threshold:
                    enhanced_results.append({
                        'id': str(chunk.id),
                        'text': chunk.text,
                        'source_name': chunk.source_name,
                        'source_type': chunk.source_type.value,
                        'document_id': str(chunk.document_id),
                        'relevance_score': boosted_score,
                        'original_similarity': float(similarity_score),
                        'metadata': chunk.metadata or {},
                        'section_number': chunk.section_number,
                        'section_title': chunk.section_title,
                        'page_range': self._format_page_range(chunk),
                        'content_type': chunk.content_type,
                        'importance_score': chunk.importance_score,
                        'boost_factors': self._get_boost_factors(chunk, legal_terms, case_citations)
                    })
            
            # Sort by enhanced relevance score and limit results
            enhanced_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            final_results = enhanced_results[:limit]
            
            search_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(
                "Enhanced vector search completed",
                query_length=len(query),
                results_count=len(final_results),
                search_time_ms=search_time_ms,
                legal_terms_found=len(legal_terms),
                case_citations_found=len(case_citations),
                avg_similarity=sum(r['relevance_score'] for r in final_results) / len(final_results) if final_results else 0
            )
            
            return final_results
            
        except Exception as e:
            logger.error(
                "Enhanced vector search failed",
                error=str(e),
                query_length=len(query),
                exc_info=True
            )
            raise
    
    async def batch_search(
        self,
        queries: List[str],
        user_id: str,
        **kwargs
    ) -> List[List[Dict[str, Any]]]:
        """
        Perform batch search for multiple queries
        Optimized for better throughput
        """
        # Generate embeddings in batch
        embeddings = await self._get_embeddings_batch(queries)
        
        results = []
        for query, embedding in zip(queries, embeddings):
            # Use cached embedding
            self._embedding_cache[query] = embedding
            result = await self.search(query, user_id, **kwargs)
            results.append(result)
        
        return results
    
    async def similarity_search_by_embedding(
        self,
        embedding: List[float],
        user_id: str,
        session: AsyncSession,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search using pre-computed embedding
        Useful for avoiding duplicate embedding generation
        """
        search_query = self._build_search_query(
            query_embedding=embedding,
            user_id=user_id,
            **kwargs
        )
        
        result = await session.execute(search_query)
        chunks = result.fetchall()
        
        formatted_results = []
        for chunk, similarity_score in chunks:
            formatted_results.append({
                'id': str(chunk.id),
                'text': chunk.text,
                'source_name': chunk.source_name,
                'source_type': chunk.source_type.value,
                'relevance_score': float(similarity_score),
                'metadata': chunk.metadata or {}
            })
        
        return formatted_results
    
    async def find_similar_chunks(
        self,
        chunk_id: str,
        user_id: str,
        session: AsyncSession,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find chunks similar to a given chunk
        Useful for expanding search results
        """
        # Get the reference chunk
        ref_query = select(DocumentChunk).where(
            and_(
                DocumentChunk.id == chunk_id,
                DocumentChunk.user_id == user_id
            )
        )
        
        result = await session.execute(ref_query)
        ref_chunk = result.scalar_one_or_none()
        
        if not ref_chunk:
            return []
        
        # Search for similar chunks
        return await self.similarity_search_by_embedding(
            embedding=ref_chunk.embedding,
            user_id=user_id,
            session=session,
            limit=limit
        )
    
    def _build_search_query(
        self,
        query_embedding: List[float],
        user_id: str,
        document_ids: Optional[List[str]] = None,
        document_types: Optional[List[DocumentType]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ):
        """
        Build optimized SQL query for vector search with legal-specific enhancements
        """
        # Calculate similarity score (1 - cosine_distance)
        similarity_expr = (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label('similarity_score')
        
        # Base query
        query = select(DocumentChunk, similarity_expr).where(
            DocumentChunk.user_id == user_id
        )
        
        # Add document ID filter
        if document_ids:
            query = query.where(DocumentChunk.document_id.in_(document_ids))
        
        # Add document type filter with legal priority
        if document_types:
            query = query.where(DocumentChunk.source_type.in_(document_types))
        else:
            # Prioritize legal sources over user documents
            legal_types = [DocumentType.STATUTE, DocumentType.CASE_LAW, DocumentType.REGULATION]
            query = query.where(
                or_(
                    DocumentChunk.source_type.in_(legal_types),
                    and_(
                        DocumentChunk.source_type == DocumentType.USER_DOCUMENT,
                        similarity_expr >= similarity_threshold + 0.1  # Higher threshold for user docs
                    )
                )
            )
        
        # Add similarity threshold with legal content boost
        base_threshold = similarity_threshold
        legal_boost_expr = func.case(
            (DocumentChunk.source_type.in_([DocumentType.STATUTE, DocumentType.CASE_LAW]), base_threshold - 0.05),
            (DocumentChunk.source_type == DocumentType.REGULATION, base_threshold - 0.03),
            else_=base_threshold
        )
        
        query = query.where(similarity_expr >= legal_boost_expr)
        
        # Enhanced ordering with importance score and content type
        order_expr = func.case(
            # Boost statutes and case law
            (DocumentChunk.source_type.in_([DocumentType.STATUTE, DocumentType.CASE_LAW]), 
             similarity_expr + 0.1 + func.coalesce(DocumentChunk.importance_score, 0.0) * 0.05),
            # Boost structured content (sections, headings)
            (DocumentChunk.content_type.in_(['section', 'heading', 'principle']),
             similarity_expr + 0.05),
            else_=similarity_expr
        ).desc()
        
        query = query.order_by(order_expr).limit(limit * 2)  # Get more results for re-ranking
        
        return query
    
    async def _get_embedding(self, text: str, is_frequent: bool = False) -> List[float]:
        """
        Get embedding for text with enhanced caching
        """
        # Check local cache first
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        
        # Check distributed cache if available
        from .cache_manager import cache_manager
        cached_embedding = await cache_manager.get_cached_embedding(text)
        if cached_embedding:
            # Store in local cache for faster access
            self._embedding_cache[text] = cached_embedding
            return cached_embedding
        
        # Generate embedding
        response = await self.openai_client.embeddings.create(
            input=text,
            model=settings.azure_openai.embedding_deployment
        )
        
        embedding = response.data[0].embedding
        
        # Cache the result in both local and distributed cache
        self._embedding_cache[text] = embedding
        await cache_manager.cache_embedding(text, embedding, is_frequent=is_frequent)
        
        return embedding
    
    async def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch with enhanced caching
        """
        from .cache_manager import cache_manager
        
        # Check both local and distributed cache
        uncached_texts = []
        embeddings_map = {}
        
        for text in texts:
            if text in self._embedding_cache:
                embeddings_map[text] = self._embedding_cache[text]
            else:
                # Check distributed cache
                cached_embedding = await cache_manager.get_cached_embedding(text)
                if cached_embedding:
                    embeddings_map[text] = cached_embedding
                    self._embedding_cache[text] = cached_embedding
                else:
                    uncached_texts.append(text)
        
        if uncached_texts:
            # Generate embeddings for uncached texts
            response = await self.openai_client.embeddings.create(
                input=uncached_texts,
                model=settings.azure_openai.embedding_deployment
            )
            
            # Cache the results in both local and distributed cache
            for text, embedding_data in zip(uncached_texts, response.data):
                embedding = embedding_data.embedding
                embeddings_map[text] = embedding
                self._embedding_cache[text] = embedding
                await cache_manager.cache_embedding(text, embedding)
        
        # Return all embeddings in original order
        return [embeddings_map[text] for text in texts]
    
    def _format_page_range(self, chunk: DocumentChunk) -> Optional[str]:
        """Format page range for display"""
        if chunk.start_page and chunk.end_page:
            if chunk.start_page == chunk.end_page:
                return f"Page {chunk.start_page}"
            else:
                return f"Pages {chunk.start_page}-{chunk.end_page}"
        return None
    
    async def get_search_statistics(
        self,
        user_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get search statistics for monitoring and optimization
        """
        # Total chunks available
        total_chunks_query = select(func.count(DocumentChunk.id)).where(
            DocumentChunk.user_id == user_id
        )
        total_chunks = await session.scalar(total_chunks_query)
        
        # Chunks by document type
        type_stats_query = select(
            DocumentChunk.source_type,
            func.count(DocumentChunk.id)
        ).where(
            DocumentChunk.user_id == user_id
        ).group_by(DocumentChunk.source_type)
        
        type_stats_result = await session.execute(type_stats_query)
        type_stats = {row[0].value: row[1] for row in type_stats_result.fetchall()}
        
        return {
            'total_chunks': total_chunks,
            'chunks_by_type': type_stats,
            'embedding_cache_size': len(self._embedding_cache)
        }
    
    async def optimize_search_performance(self, session: AsyncSession):
        """
        Optimize search performance by updating statistics and indexes
        """
        try:
            # Update table statistics
            await session.execute(text("ANALYZE document_chunks"))
            
            # Vacuum if needed (in production, this should be scheduled)
            if settings.is_development:
                await session.execute(text("VACUUM ANALYZE document_chunks"))
            
            logger.info("Search performance optimization completed")
            
        except Exception as e:
            logger.warning("Search optimization failed", error=str(e))
    
    def clear_embedding_cache(self):
        """Clear the embedding cache"""
        self._embedding_cache.clear()
        logger.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get embedding cache statistics"""
        return {
            'cache_size': len(self._embedding_cache),
            'cache_keys': list(self._embedding_cache.keys())[:10]  # First 10 keys for debugging
        }
    
    def _extract_legal_terms(self, query: str) -> List[str]:
        """Extract legal terms from query for keyword boosting"""
        import re
        
        legal_terms = []
        query_lower = query.lower()
        
        # Legal acts and statutes
        act_patterns = [
            r'\bindian\s+penal\s+code\b',
            r'\bipc\b',
            r'\bcode\s+of\s+criminal\s+procedure\b',
            r'\bcrpc\b',
            r'\bindian\s+contract\s+act\b',
            r'\bconstitution\s+of\s+india\b',
            r'\bindian\s+evidence\s+act\b',
            r'\bcpc\b',
            r'\blimitation\s+act\b'
        ]
        
        for pattern in act_patterns:
            matches = re.findall(pattern, query_lower)
            legal_terms.extend(matches)
        
        # Section references
        section_patterns = [
            r'\bsection\s+\d+[a-z]?\b',
            r'\barticle\s+\d+[a-z]?\b',
            r'\bsec\.\s*\d+[a-z]?\b',
            r'\bart\.\s*\d+[a-z]?\b'
        ]
        
        for pattern in section_patterns:
            matches = re.findall(pattern, query_lower)
            legal_terms.extend(matches)
        
        # Court names
        court_patterns = [
            r'\bsupreme\s+court\b',
            r'\bhigh\s+court\b',
            r'\bdistrict\s+court\b',
            r'\btribunal\b'
        ]
        
        for pattern in court_patterns:
            matches = re.findall(pattern, query_lower)
            legal_terms.extend(matches)
        
        # Legal procedures
        procedure_terms = [
            'writ petition', 'habeas corpus', 'mandamus', 'certiorari',
            'bail', 'anticipatory bail', 'interim order', 'stay order',
            'injunction', 'appeal', 'revision', 'review'
        ]
        
        for term in procedure_terms:
            if term in query_lower:
                legal_terms.append(term)
        
        return list(set(legal_terms))  # Remove duplicates
    
    def _extract_case_citations(self, query: str) -> List[str]:
        """Extract case citations from query for exact matching"""
        import re
        
        case_citations = []
        
        # Standard case citation patterns
        citation_patterns = [
            r'\b\d{4}\s+\w+\s+\d+\b',  # 2020 SC 123
            r'\b\[\d{4}\]\s+\w+\s+\d+\b',  # [2020] SC 123
            r'\bAIR\s+\d{4}\s+\w+\s+\d+\b',  # AIR 2020 SC 123
            r'\b\d{4}\s+\(\d+\)\s+\w+\s+\d+\b'  # 2020 (1) SC 123
        ]
        
        for pattern in citation_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            case_citations.extend(matches)
        
        # Case name patterns (Party v. Party)
        case_name_patterns = [
            r'\b[A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+\b',
            r'\b[A-Z][a-z]+\s+vs\.?\s+[A-Z][a-z]+\b'
        ]
        
        for pattern in case_name_patterns:
            matches = re.findall(pattern, query)
            case_citations.extend(matches)
        
        return list(set(case_citations))  # Remove duplicates
    
    async def _apply_legal_boosting(
        self,
        chunk: DocumentChunk,
        similarity_score: float,
        query: str,
        legal_terms: List[str],
        case_citations: List[str]
    ) -> float:
        """Apply legal-specific boosting to similarity scores"""
        
        boosted_score = similarity_score
        chunk_text_lower = chunk.text.lower()
        
        # Boost for exact legal term matches
        for term in legal_terms:
            if term.lower() in chunk_text_lower:
                if 'section' in term or 'article' in term:
                    boosted_score += 0.15  # High boost for section references
                elif any(act in term for act in ['ipc', 'crpc', 'constitution']):
                    boosted_score += 0.12  # High boost for major acts
                else:
                    boosted_score += 0.08  # Standard legal term boost
        
        # Boost for exact case citation matches
        for citation in case_citations:
            if citation.lower() in chunk_text_lower:
                boosted_score += 0.20  # Very high boost for exact citation matches
        
        # Boost based on source type and content structure
        if chunk.source_type == DocumentType.STATUTE:
            boosted_score += 0.05
            # Extra boost for structured content in statutes
            if chunk.section_number or chunk.section_title:
                boosted_score += 0.03
        elif chunk.source_type == DocumentType.CASE_LAW:
            boosted_score += 0.04
            # Boost for important parts of judgments
            if chunk.content_type in ['principle', 'ratio', 'holding']:
                boosted_score += 0.05
        
        # Boost for high importance content
        if chunk.importance_score and chunk.importance_score > 0.7:
            boosted_score += chunk.importance_score * 0.05
        
        # Apply relevance threshold filtering
        return min(1.0, boosted_score)  # Cap at 1.0
    
    def _get_boost_factors(
        self,
        chunk: DocumentChunk,
        legal_terms: List[str],
        case_citations: List[str]
    ) -> Dict[str, Any]:
        """Get boost factors applied to a chunk for debugging/transparency"""
        
        factors = {
            'legal_term_matches': [],
            'case_citation_matches': [],
            'source_type_boost': chunk.source_type.value,
            'structure_boost': bool(chunk.section_number or chunk.section_title),
            'importance_boost': chunk.importance_score or 0.0
        }
        
        chunk_text_lower = chunk.text.lower()
        
        # Track which legal terms matched
        for term in legal_terms:
            if term.lower() in chunk_text_lower:
                factors['legal_term_matches'].append(term)
        
        # Track which case citations matched
        for citation in case_citations:
            if citation.lower() in chunk_text_lower:
                factors['case_citation_matches'].append(citation)
        
        return factors
    
    async def hybrid_search_with_reranking(
        self,
        query: str,
        user_id: str,
        session: AsyncSession,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search with semantic reranking
        Combines dense vector search with keyword matching and legal boosting
        """
        
        # Step 1: Dense vector search with legal boosting
        dense_results = await self.search(
            query=query,
            user_id=user_id,
            session=session,
            enable_legal_boosting=True,
            **kwargs
        )
        
        # Step 2: Apply semantic reranking based on query intent
        query_intent = self._analyze_query_intent(query)
        reranked_results = self._apply_semantic_reranking(dense_results, query, query_intent)
        
        return reranked_results
    
    def _analyze_query_intent(self, query: str) -> str:
        """Analyze query intent for better reranking"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['what', 'define', 'meaning', 'explain']):
            return 'definition'
        elif any(word in query_lower for word in ['how', 'procedure', 'process', 'steps']):
            return 'procedure'
        elif any(word in query_lower for word in ['case', 'judgment', 'ruling', 'held']):
            return 'case_law'
        elif any(word in query_lower for word in ['section', 'article', 'act', 'law']):
            return 'statute'
        elif any(word in query_lower for word in ['penalty', 'punishment', 'fine', 'imprisonment']):
            return 'penalty'
        else:
            return 'general'
    
    def _apply_semantic_reranking(
        self,
        results: List[Dict[str, Any]],
        query: str,
        query_intent: str
    ) -> List[Dict[str, Any]]:
        """Apply semantic reranking based on query intent"""
        
        for result in results:
            intent_boost = 0.0
            
            # Apply intent-specific boosting
            if query_intent == 'definition' and result['content_type'] in ['definition', 'explanation']:
                intent_boost = 0.1
            elif query_intent == 'procedure' and result['content_type'] in ['procedure', 'process']:
                intent_boost = 0.1
            elif query_intent == 'case_law' and result['source_type'] == 'case_law':
                intent_boost = 0.08
            elif query_intent == 'statute' and result['source_type'] == 'statute':
                intent_boost = 0.08
            elif query_intent == 'penalty' and 'penalty' in result['text'].lower():
                intent_boost = 0.12
            
            # Apply the boost
            result['relevance_score'] = min(1.0, result['relevance_score'] + intent_boost)
            result['intent_boost'] = intent_boost
        
        # Re-sort by updated relevance scores
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return results