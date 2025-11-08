"""
Production-grade Retrieval-Augmented Generation (RAG) Pipeline
Implements state-of-the-art techniques for legal AI as specified in the PDF
"""
import asyncio
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
import tiktoken
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import DocumentChunk, Query, Citation, DocumentType, QueryMode
from .vector_search import VectorSearchEngine
from .prompt_engineering import PromptEngineer
from .citation_manager import CitationManager
from .hallucination_detector import HallucinationDetector
from .cache_manager import CacheManager
from services.azure_openai_service import azure_openai_service
from utils.text_processing import TextProcessor
from utils.metrics import MetricsCollector

logger = structlog.get_logger(__name__)

@dataclass
class RetrievalResult:
    """Result from document retrieval"""
    chunks: List[Dict[str, Any]]
    total_found: int
    retrieval_time_ms: int
    search_strategy: str

@dataclass
class RAGResponse:
    """Complete RAG pipeline response"""
    answer: str
    citations: List[Dict[str, Any]]
    confidence_score: float
    processing_time_ms: int
    token_usage: Dict[str, int]
    metadata: Dict[str, Any]

class SearchStrategy(Enum):
    """Search strategy enumeration"""
    VECTOR_ONLY = "vector_only"
    HYBRID = "hybrid"
    KEYWORD_BOOSTED = "keyword_boosted"
    SEMANTIC_RERANK = "semantic_rerank"

class RAGPipeline:
    """
    Production-grade RAG pipeline for Indian Legal AI Assistant
    
    Implements advanced techniques:
    - Hybrid search (dense + sparse)
    - Legal-specific keyword boosting
    - Multi-stage re-ranking
    - Hallucination detection
    - Citation verification
    - Conversation context management
    """
    
    def __init__(self):
        self.azure_openai = azure_openai_service
        self.vector_search = VectorSearchEngine()
        self.prompt_engineer = PromptEngineer()
        self.citation_manager = CitationManager()
        self.hallucination_detector = HallucinationDetector()
        self.cache_manager = CacheManager()
        self.text_processor = TextProcessor()
        self.metrics_collector = MetricsCollector()
        
        # Initialize tokenizer for token counting
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Legal keyword patterns for boosting
        self.legal_keywords = {
            'case_citations': r'\b\d{4}\s+\w+\s+\d+\b|\b\[\d{4}\]\s+\w+\s+\d+\b',
            'section_references': r'\bSection\s+\d+[A-Z]?\b|\bArt(?:icle)?\s+\d+[A-Z]?\b',
            'court_names': r'\bSupreme\s+Court\b|\bHigh\s+Court\b|\bDistrict\s+Court\b',
            'legal_acts': r'\bIndian\s+Penal\s+Code\b|\bConstitution\s+of\s+India\b|\bCrPC\b|\bCPC\b',
            'legal_terms': r'\bwrit\s+petition\b|\bbail\s+application\b|\bhabeas\s+corpus\b'
        }
        
        logger.info("RAG Pipeline initialized with advanced features")
    
    async def process_query(
        self,
        query: str,
        user_id: str,
        mode: QueryMode = QueryMode.QA,
        conversation_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        session: Optional[AsyncSession] = None
    ) -> RAGResponse:
        """
        Main RAG pipeline processing with comprehensive error handling
        """
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(query, mode, document_ids, user_id)
            
            # Check cache first
            cached_response = await self.cache_manager.get(cache_key)
            if cached_response and not settings.is_development:
                logger.info("Cache hit for query", cache_key=cache_key[:8])
                return cached_response
            
            # Step 1: Query preprocessing and analysis
            processed_query = await self._preprocess_query(query, mode)
            
            # Step 2: Retrieve relevant documents
            retrieval_result = await self._retrieve_documents(
                processed_query, user_id, document_ids, session
            )
            
            # Step 3: Re-rank and filter chunks
            ranked_chunks = await self._rerank_chunks(
                processed_query, retrieval_result.chunks
            )
            
            # Step 4: Build conversation context with continuity enhancement
            conversation_context = await self._build_conversation_context(
                conversation_id, session
            ) if conversation_id else []
            
            # Enhance context with continuity analysis
            if conversation_context:
                conversation_context = await self._enhance_conversation_continuity(
                    processed_query, conversation_context, ranked_chunks
                )
            
            # Step 5: Generate response
            llm_response = await self._generate_response(
                processed_query, ranked_chunks, mode, conversation_context
            )
            
            # Step 6: Extract and verify citations
            citations = await self._extract_and_verify_citations(
                llm_response['answer'], ranked_chunks
            )
            
            # Step 7: Detect hallucinations
            verified_answer = await self._verify_response(
                llm_response['answer'], citations, ranked_chunks
            )
            
            # Step 8: Calculate confidence score
            confidence_score = await self._calculate_confidence_score(
                verified_answer, citations, retrieval_result
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Build final response
            response = RAGResponse(
                answer=verified_answer,
                citations=citations,
                confidence_score=confidence_score,
                processing_time_ms=processing_time_ms,
                token_usage=llm_response['token_usage'],
                metadata={
                    'retrieval_strategy': retrieval_result.search_strategy,
                    'chunks_retrieved': len(retrieval_result.chunks),
                    'chunks_used': len(ranked_chunks),
                    'retrieval_time_ms': retrieval_result.retrieval_time_ms,
                    'llm_time_ms': llm_response['processing_time_ms'],
                    'mode': mode.value,
                    'has_conversation_context': bool(conversation_context)
                }
            )
            
            # Cache the response with intelligent TTL
            await self.cache_manager.cache_query_result(
                query=processed_query['original'],
                mode=mode.value,
                result=response,
                document_ids=document_ids,
                user_id=user_id,
                confidence_score=confidence_score
            )
            
            # Collect metrics
            await self._collect_metrics(response, retrieval_result)
            
            logger.info(
                "RAG pipeline completed successfully",
                processing_time_ms=processing_time_ms,
                confidence_score=confidence_score,
                citation_count=len(citations)
            )
            
            return response
            
        except Exception as e:
            logger.error(
                "RAG pipeline failed",
                error=str(e),
                query_length=len(query),
                mode=mode.value,
                exc_info=True
            )
            raise
    
    async def _preprocess_query(self, query: str, mode: QueryMode) -> Dict[str, Any]:
        """Preprocess and analyze the query"""
        return {
            'original': query,
            'cleaned': self.text_processor.clean_text(query),
            'keywords': self.text_processor.extract_legal_keywords(query),
            'intent': await self._analyze_query_intent(query, mode),
            'complexity': self._assess_query_complexity(query)
        }
    
    async def _retrieve_documents(
        self,
        processed_query: Dict[str, Any],
        user_id: str,
        document_ids: Optional[List[str]],
        session: AsyncSession
    ) -> RetrievalResult:
        """
        Retrieve relevant documents using hybrid search strategy
        """
        start_time = time.time()
        
        # Determine search strategy based on query characteristics
        strategy = self._select_search_strategy(processed_query)
        
        if strategy == SearchStrategy.HYBRID:
            chunks = await self._hybrid_search(
                processed_query, user_id, document_ids, session
            )
        elif strategy == SearchStrategy.KEYWORD_BOOSTED:
            chunks = await self._keyword_boosted_search(
                processed_query, user_id, document_ids, session
            )
        else:
            chunks = await self._vector_search(
                processed_query, user_id, document_ids, session
            )
        
        retrieval_time_ms = int((time.time() - start_time) * 1000)
        
        return RetrievalResult(
            chunks=chunks,
            total_found=len(chunks),
            retrieval_time_ms=retrieval_time_ms,
            search_strategy=strategy.value
        )
    
    async def _hybrid_search(
        self,
        processed_query: Dict[str, Any],
        user_id: str,
        document_ids: Optional[List[str]],
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining vector similarity and keyword matching
        """
        # Generate query embedding
        query_embedding = await self._generate_embedding(processed_query['cleaned'])
        
        # Build base query
        base_query = select(DocumentChunk).where(
            DocumentChunk.user_id == user_id
        )
        
        # Add document filter if specified
        if document_ids:
            base_query = base_query.where(
                DocumentChunk.document_id.in_(document_ids)
            )
        
        # Vector similarity search
        vector_query = base_query.order_by(
            DocumentChunk.embedding.cosine_distance(query_embedding)
        ).limit(settings.vector_db.max_chunks_per_query * 2)
        
        vector_results = await session.execute(vector_query)
        vector_chunks = vector_results.scalars().all()
        
        # Keyword boosting
        boosted_chunks = await self._apply_keyword_boosting(
            vector_chunks, processed_query
        )
        
        # Convert to dict format with scores
        chunks = []
        for i, chunk in enumerate(boosted_chunks[:settings.vector_db.max_chunks_per_query]):
            chunks.append({
                'id': str(chunk.id),
                'text': chunk.text,
                'source_name': chunk.source_name,
                'source_type': chunk.source_type.value,
                'metadata': chunk.metadata or {},
                'relevance_score': 1.0 - (i * 0.1),  # Decreasing relevance
                'section_number': chunk.section_number,
                'section_title': chunk.section_title,
                'page_range': f"{chunk.start_page}-{chunk.end_page}" if chunk.start_page else None
            })
        
        return chunks
    
    async def _keyword_boosted_search(
        self,
        processed_query: Dict[str, Any],
        user_id: str,
        document_ids: Optional[List[str]],
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Search with legal keyword boosting for exact matches
        """
        import re
        
        # Extract legal patterns from query
        legal_matches = {}
        for pattern_name, pattern in self.legal_keywords.items():
            matches = re.findall(pattern, processed_query['original'], re.IGNORECASE)
            if matches:
                legal_matches[pattern_name] = matches
        
        # Start with vector search
        chunks = await self._vector_search(processed_query, user_id, document_ids, session)
        
        # Boost chunks containing exact legal matches
        for chunk in chunks:
            boost_score = 0.0
            text_lower = chunk['text'].lower()
            
            for pattern_name, matches in legal_matches.items():
                for match in matches:
                    if match.lower() in text_lower:
                        if pattern_name == 'case_citations':
                            boost_score += 0.3
                        elif pattern_name == 'section_references':
                            boost_score += 0.25
                        elif pattern_name == 'court_names':
                            boost_score += 0.2
                        else:
                            boost_score += 0.1
            
            chunk['relevance_score'] = min(1.0, chunk['relevance_score'] + boost_score)
        
        # Re-sort by boosted scores
        chunks.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return chunks
    
    async def _vector_search(
        self,
        processed_query: Dict[str, Any],
        user_id: str,
        document_ids: Optional[List[str]],
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Pure vector similarity search"""
        return await self.vector_search.search(
            query=processed_query['cleaned'],
            user_id=user_id,
            document_ids=document_ids,
            limit=settings.vector_db.max_chunks_per_query,
            session=session
        )
    
    async def _rerank_chunks(
        self,
        processed_query: Dict[str, Any],
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Re-rank chunks using advanced scoring
        """
        scored_chunks = []
        
        for chunk in chunks:
            # Calculate comprehensive relevance score
            score = await self._calculate_chunk_relevance(chunk, processed_query)
            
            # Filter out low-quality chunks
            if score >= settings.vector_db.similarity_threshold:
                chunk['final_relevance_score'] = score
                scored_chunks.append(chunk)
        
        # Sort by final relevance score
        scored_chunks.sort(key=lambda x: x['final_relevance_score'], reverse=True)
        
        # Return top chunks
        return scored_chunks[:settings.vector_db.max_chunks_per_query]
    
    async def _calculate_chunk_relevance(
        self,
        chunk: Dict[str, Any],
        processed_query: Dict[str, Any]
    ) -> float:
        """Calculate comprehensive relevance score for a chunk"""
        base_score = chunk.get('relevance_score', 0.0)
        
        # Content quality factors
        text_length = len(chunk['text'])
        if text_length < 50:  # Too short
            return 0.0
        
        # Optimal length bonus
        length_score = 1.0
        if 200 <= text_length <= 800:
            length_score = 1.1
        elif text_length > 1500:  # Too long
            length_score = 0.9
        
        # Source type relevance
        source_type_score = 1.0
        if chunk['source_type'] in ['statute', 'case_law']:
            source_type_score = 1.2
        elif chunk['source_type'] == 'regulation':
            source_type_score = 1.1
        
        # Section/structure bonus
        structure_score = 1.0
        if chunk.get('section_number') or chunk.get('section_title'):
            structure_score = 1.15
        
        # Combine all factors
        final_score = base_score * length_score * source_type_score * structure_score
        
        return min(1.0, final_score)
    
    async def _build_conversation_context(
        self,
        conversation_id: str,
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Build intelligent conversation context with summarization and continuity"""
        if not settings.enable_conversation_history:
            return []
        
        # Get recent queries from conversation with more details
        query = select(Query).where(
            and_(
                Query.conversation_id == conversation_id,
                Query.status == "completed"
            )
        ).order_by(Query.created_at.desc()).limit(settings.conversation.max_history_queries)
        
        result = await session.execute(query)
        recent_queries = result.scalars().all()
        
        if not recent_queries:
            return []
        
        # Apply intelligent context window management
        context = await self._apply_intelligent_context_management(recent_queries)
        
        return context
    
    async def _apply_intelligent_context_management(
        self,
        queries: List[Query]
    ) -> List[Dict[str, Any]]:
        """Apply intelligent context window management with summarization"""
        
        context = []
        total_tokens = 0
        max_context_tokens = settings.conversation.max_context_tokens
        
        # Process queries in reverse chronological order (most recent first)
        for i, query in enumerate(queries):
            # Estimate token count for this query-response pair
            query_tokens = len(self.tokenizer.encode(query.query_text))
            response_tokens = len(self.tokenizer.encode(query.response_text or "")) if query.response_text else 0
            pair_tokens = query_tokens + response_tokens
            
            # Check if adding this pair would exceed token limit
            if total_tokens + pair_tokens > max_context_tokens:
                # If this is not the most recent query, try summarization
                if i > 0:
                    # Summarize older context
                    older_queries = queries[i:]
                    summary = await self._summarize_conversation_history(older_queries)
                    if summary:
                        summary_tokens = len(self.tokenizer.encode(summary))
                        if total_tokens + summary_tokens <= max_context_tokens:
                            context.append({
                                'role': 'system',
                                'content': f"Previous conversation summary: {summary}",
                                'is_summary': True
                            })
                break
            
            # Add the query-response pair to context
            context.insert(0, {
                'role': 'user',
                'content': query.query_text,
                'timestamp': query.created_at.isoformat(),
                'query_id': str(query.id)
            })
            
            if query.response_text:
                # Truncate very long responses to preserve context window
                response_content = query.response_text
                max_response_chars = settings.conversation.max_response_length_for_context
                if response_tokens > max_response_chars // 4:  # Rough token to char ratio
                    response_content = self._truncate_response_for_context(response_content)
                
                context.insert(1, {
                    'role': 'assistant',
                    'content': response_content,
                    'timestamp': query.created_at.isoformat(),
                    'confidence_score': query.confidence_score
                })
            
            total_tokens += pair_tokens
        
        # Add context continuity markers
        context = self._add_context_continuity_markers(context)
        
        return context
    
    async def _summarize_conversation_history(self, queries: List[Query]) -> Optional[str]:
        """Summarize older conversation history to preserve context window"""
        
        if not queries:
            return None
        
        # Build summary prompt
        conversation_text = []
        for query in reversed(queries):  # Chronological order for summary
            conversation_text.append(f"User: {query.query_text}")
            if query.response_text:
                # Use first 200 chars of response for summary
                response_snippet = query.response_text[:200] + "..." if len(query.response_text) > 200 else query.response_text
                conversation_text.append(f"Assistant: {response_snippet}")
        
        summary_prompt = f"""
        Summarize the following legal conversation history in 2-3 sentences, focusing on:
        1. Main legal topics discussed
        2. Key questions asked
        3. Important legal principles or cases mentioned
        
        Conversation:
        {chr(10).join(conversation_text)}
        
        Summary:"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.azure_openai.deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a legal assistant that creates concise summaries of legal conversations."
                    },
                    {
                        "role": "user",
                        "content": summary_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=settings.conversation.summary_max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.warning("Failed to summarize conversation history", error=str(e))
            return None
    
    def _truncate_response_for_context(self, response: str) -> str:
        """Truncate long responses while preserving key information"""
        
        # Try to preserve the first paragraph and any citations
        sentences = response.split('.')
        truncated = []
        char_count = 0
        max_chars = settings.conversation.max_response_length_for_context
        
        for sentence in sentences:
            if char_count + len(sentence) > max_chars:
                break
            truncated.append(sentence)
            char_count += len(sentence)
        
        truncated_text = '.'.join(truncated)
        
        # Ensure we preserve citations if they exist
        import re
        citations = re.findall(r'\[Doc\d+\]|\[\d+\]', response)
        if citations and not any(citation in truncated_text for citation in citations):
            # Add first few citations
            citation_text = ' '.join(citations[:3])
            truncated_text += f" ... {citation_text}"
        
        return truncated_text + " [Context truncated]"
    
    def _add_context_continuity_markers(self, context: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add markers to help maintain context continuity"""
        
        if not context:
            return context
        
        # Add topic continuity analysis
        topics = self._extract_conversation_topics(context)
        if topics:
            context.insert(0, {
                'role': 'system',
                'content': f"Conversation topics: {', '.join(topics)}",
                'is_topic_marker': True
            })
        
        # Add temporal markers for long conversations
        if len(context) > 6:  # More than 3 query-response pairs
            context.insert(-4, {
                'role': 'system',
                'content': "--- Earlier in conversation ---",
                'is_temporal_marker': True
            })
        
        return context
    
    def _extract_conversation_topics(self, context: List[Dict[str, Any]]) -> List[str]:
        """Extract main topics from conversation context"""
        
        topics = set()
        
        for message in context:
            if message['role'] == 'user':
                content = message['content'].lower()
                
                # Legal domain topics
                if any(term in content for term in ['contract', 'agreement', 'breach']):
                    topics.add('Contract Law')
                if any(term in content for term in ['criminal', 'ipc', 'crime', 'offense']):
                    topics.add('Criminal Law')
                if any(term in content for term in ['constitution', 'fundamental rights', 'article']):
                    topics.add('Constitutional Law')
                if any(term in content for term in ['property', 'ownership', 'title']):
                    topics.add('Property Law')
                if any(term in content for term in ['family', 'marriage', 'divorce']):
                    topics.add('Family Law')
                if any(term in content for term in ['company', 'corporate', 'business']):
                    topics.add('Corporate Law')
                if any(term in content for term in ['tax', 'income tax', 'gst']):
                    topics.add('Tax Law')
                if any(term in content for term in ['labor', 'employment', 'worker']):
                    topics.add('Labor Law')
        
        return list(topics)[:3]  # Limit to top 3 topics
    
    async def _enhance_conversation_continuity(
        self,
        processed_query: Dict[str, Any],
        conversation_context: List[Dict[str, Any]],
        current_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enhance conversation context with continuity analysis"""
        
        if not conversation_context or not settings.conversation.enable_topic_tracking:
            return conversation_context
        
        # Analyze query continuity patterns
        continuity_analysis = self._analyze_query_continuity(processed_query, conversation_context)
        
        # Add continuity markers if needed
        if continuity_analysis['is_follow_up']:
            context_marker = {
                'role': 'system',
                'content': f"This appears to be a follow-up question about: {continuity_analysis['topic']}",
                'is_continuity_marker': True
            }
            conversation_context.insert(0, context_marker)
        
        # Add reference resolution if pronouns or references are detected
        if continuity_analysis['has_references']:
            reference_context = self._resolve_contextual_references(
                processed_query['original'], conversation_context
            )
            if reference_context:
                conversation_context.insert(0, {
                    'role': 'system',
                    'content': f"Context for references: {reference_context}",
                    'is_reference_resolution': True
                })
        
        return conversation_context
    
    def _analyze_query_continuity(
        self,
        processed_query: Dict[str, Any],
        conversation_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze if current query is a continuation of previous conversation"""
        
        current_query = processed_query['original'].lower()
        
        # Check for follow-up indicators
        follow_up_indicators = [
            'also', 'additionally', 'furthermore', 'moreover', 'besides',
            'what about', 'how about', 'and what', 'can you also',
            'in addition', 'similarly', 'likewise'
        ]
        
        is_follow_up = any(indicator in current_query for indicator in follow_up_indicators)
        
        # Check for references to previous context
        reference_indicators = [
            'this', 'that', 'these', 'those', 'it', 'they', 'them',
            'the above', 'mentioned', 'said', 'same', 'such'
        ]
        
        has_references = any(indicator in current_query for indicator in reference_indicators)
        
        # Extract topic from recent context
        topic = 'previous discussion'
        if conversation_context:
            recent_user_messages = [
                msg['content'] for msg in conversation_context[-4:] 
                if msg['role'] == 'user'
            ]
            if recent_user_messages:
                # Simple topic extraction from most recent query
                last_query = recent_user_messages[-1].lower()
                if 'contract' in last_query:
                    topic = 'contract law'
                elif 'criminal' in last_query or 'ipc' in last_query:
                    topic = 'criminal law'
                elif 'property' in last_query:
                    topic = 'property law'
                elif 'family' in last_query or 'marriage' in last_query:
                    topic = 'family law'
        
        return {
            'is_follow_up': is_follow_up,
            'has_references': has_references,
            'topic': topic,
            'continuity_score': (int(is_follow_up) + int(has_references)) / 2
        }
    
    def _resolve_contextual_references(
        self,
        current_query: str,
        conversation_context: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Resolve pronouns and references in current query using conversation context"""
        
        if not conversation_context:
            return None
        
        # Get the most recent assistant response for context
        recent_responses = [
            msg['content'] for msg in conversation_context[-3:] 
            if msg['role'] == 'assistant'
        ]
        
        if not recent_responses:
            return None
        
        last_response = recent_responses[-1]
        
        # Simple reference resolution
        current_lower = current_query.lower()
        
        # If query contains "this" or "that", provide context from last response
        if any(ref in current_lower for ref in ['this', 'that', 'it']):
            # Extract key legal terms from last response for context
            import re
            legal_terms = re.findall(r'\b(?:section|article|act|case|court|law)\s+\w+\b', last_response.lower())
            if legal_terms:
                return f"Referring to: {', '.join(legal_terms[:3])}"
        
        # If query asks about "the above" or "mentioned", provide summary
        if any(ref in current_lower for ref in ['above', 'mentioned', 'said']):
            # Provide brief context from last response
            sentences = last_response.split('.')[:2]  # First two sentences
            return ' '.join(sentences).strip()
        
        return None
    
    async def _enhance_context_with_related_queries(
        self,
        current_query: str,
        conversation_context: List[Dict[str, Any]],
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Enhance context with related queries from user's history"""
        
        # This is an optional enhancement that could be implemented
        # to find semantically similar queries from user's history
        # For now, return the original context
        return conversation_context
    
    async def _generate_response(
        self,
        processed_query: Dict[str, Any],
        chunks: List[Dict[str, Any]],
        mode: QueryMode,
        conversation_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate response using Azure OpenAI"""
        start_time = time.time()
        
        # Build prompt
        prompt = await self.prompt_engineer.build_prompt(
            query=processed_query['original'],
            chunks=chunks,
            mode=mode,
            conversation_context=conversation_context
        )
        
        # Set temperature based on mode
        temperature = (
            settings.azure_openai.temperature_creative 
            if mode == QueryMode.DRAFTING 
            else settings.azure_openai.temperature_factual
        )
        
        # Generate response using Azure OpenAI service
        messages = [
            {
                "role": "system",
                "content": self.prompt_engineer.get_system_message()
            },
            {
                "role": "user", 
                "content": prompt
            }
        ]
        
        # Add conversation context if available
        if conversation_context:
            # Insert conversation context before the current query
            context_messages = []
            for ctx in conversation_context[-5:]:  # Last 5 exchanges
                if not ctx.get('is_summary') and not ctx.get('is_continuity_marker'):
                    context_messages.append({
                        "role": ctx['role'],
                        "content": ctx['content']
                    })
            
            # Combine system message, context, and current query
            messages = [messages[0]] + context_messages + [messages[1]]
        
        response = await self.azure_openai.generate_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=settings.azure_openai.max_tokens,
            user_id=processed_query.get('user_id'),
            request_context={
                'mode': mode.value,
                'chunks_count': len(chunks)
            }
        )
        
        return {
            'answer': response.content,
            'processing_time_ms': response.processing_time_ms,
            'token_usage': {
                'prompt_tokens': response.token_usage.prompt_tokens,
                'completion_tokens': response.token_usage.completion_tokens,
                'total_tokens': response.token_usage.total_tokens
            }
        }
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Azure OpenAI service"""
        embeddings = await self.azure_openai.generate_embeddings(
            texts=text,
            user_id=None  # System embeddings don't count against user limits
        )
        return embeddings[0] if embeddings else []
    
    async def _extract_and_verify_citations(
        self,
        answer: str,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract and verify citations from the response"""
        return await self.citation_manager.extract_citations(answer, chunks)
    
    async def _verify_response(
        self,
        answer: str,
        citations: List[Dict[str, Any]],
        chunks: List[Dict[str, Any]]
    ) -> str:
        """Verify response for hallucinations and add disclaimers if needed"""
        if not settings.enable_hallucination_detection:
            return answer
        
        return await self.hallucination_detector.verify_response(
            answer, citations, chunks
        )
    
    async def _calculate_confidence_score(
        self,
        answer: str,
        citations: List[Dict[str, Any]],
        retrieval_result: RetrievalResult
    ) -> float:
        """Calculate confidence score based on multiple factors"""
        # Base score from citations
        citation_score = min(1.0, len(citations) * 0.2)
        
        # Retrieval quality score
        retrieval_score = min(1.0, retrieval_result.total_found / 10.0)
        
        # Answer length and structure score
        answer_length = len(answer.split())
        length_score = 1.0 if 50 <= answer_length <= 500 else 0.8
        
        # Combine scores
        confidence = (citation_score * 0.4 + retrieval_score * 0.3 + length_score * 0.3)
        
        return round(confidence, 2)
    

    
    def _generate_cache_key(
        self,
        query: str,
        mode: QueryMode,
        document_ids: Optional[List[str]],
        user_id: str
    ) -> str:
        """Generate cache key for query"""
        key_parts = [query, mode.value, user_id]
        if document_ids:
            key_parts.extend(sorted(document_ids))
        
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _select_search_strategy(self, processed_query: Dict[str, Any]) -> SearchStrategy:
        """Select optimal search strategy based on query characteristics"""
        # Check for legal keywords
        if processed_query.get('keywords'):
            return SearchStrategy.KEYWORD_BOOSTED
        
        # Check query complexity
        if processed_query.get('complexity', 'simple') == 'complex':
            return SearchStrategy.HYBRID
        
        return SearchStrategy.VECTOR_ONLY
    
    async def _analyze_query_intent(self, query: str, mode: QueryMode) -> str:
        """Analyze query intent for better processing"""
        # Simple intent analysis - can be enhanced with ML models
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['what', 'define', 'explain']):
            return 'definition'
        elif any(word in query_lower for word in ['how', 'procedure', 'process']):
            return 'procedure'
        elif any(word in query_lower for word in ['case', 'judgment', 'ruling']):
            return 'case_law'
        elif any(word in query_lower for word in ['section', 'article', 'act']):
            return 'statute'
        elif mode == QueryMode.DRAFTING:
            return 'drafting'
        elif mode == QueryMode.SUMMARIZATION:
            return 'summarization'
        else:
            return 'general'
    
    def _assess_query_complexity(self, query: str) -> str:
        """Assess query complexity"""
        word_count = len(query.split())
        
        if word_count > 20:
            return 'complex'
        elif word_count > 10:
            return 'medium'
        else:
            return 'simple'
    
    async def _apply_keyword_boosting(
        self,
        chunks: List[DocumentChunk],
        processed_query: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Apply keyword boosting to chunks"""
        # This is a placeholder - the actual implementation would
        # modify the relevance scoring in the hybrid search
        return chunks
    
    async def _collect_metrics(
        self,
        response: RAGResponse,
        retrieval_result: RetrievalResult
    ):
        """Collect performance metrics"""
        await self.metrics_collector.record_query_metrics(
            processing_time_ms=response.processing_time_ms,
            confidence_score=response.confidence_score,
            citation_count=len(response.citations),
            chunks_retrieved=retrieval_result.total_found,
            search_strategy=retrieval_result.search_strategy
        )

        try:
            await self.metrics_collector.record_metric(
                "rag_processing_time",
                response.processing_time_ms,
                {"mode": response.metadata.get("mode", "unknown")}
            )
            
            await self.metrics_collector.record_metric(
                "rag_retrieval_time",
                retrieval_result.retrieval_time_ms,
                {"strategy": retrieval_result.search_strategy}
            )
            
            await self.metrics_collector.record_metric(
                "rag_token_usage",
                response.token_usage.get("total_tokens", 0),
                {"mode": response.metadata.get("mode", "unknown")}
            )
        except Exception as e:
            logger.warning("Failed to collect metrics", error=str(e))

# Global instance
rag_pipeline = RAGPipeline()
