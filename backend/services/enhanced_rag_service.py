"""
Enhanced RAG Service with Web Search Integration
Intelligently combines vector database search with Google web search
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from core.simple_rag import rag_pipeline
from services.google_search_service import google_search_service, SearchResult
from config.settings import settings

logger = structlog.get_logger(__name__)


class EnhancedRAGResponse:
    """Enhanced RAG response with web search results"""
    def __init__(
        self,
        answer: str,
        citations: List[Dict],
        confidence_score: float,
        token_usage: Dict[str, int],
        web_results: List[SearchResult] = None,
        used_web_search: bool = False,
        search_strategy: str = "vector_only"
    ):
        self.answer = answer
        self.citations = citations
        self.confidence_score = confidence_score
        self.token_usage = token_usage
        self.web_results = web_results or []
        self.used_web_search = used_web_search
        self.search_strategy = search_strategy


class EnhancedRAGService:
    """Enhanced RAG service combining vector search and web search"""

    def __init__(self):
        self.rag_pipeline = rag_pipeline
        self.google_search = google_search_service
        self.settings = settings
        logger.info(
            "Enhanced RAG service initialized",
            web_search_enabled=google_search_service.enabled
        )

    async def process_query(
        self,
        query: str,
        user_id: str,
        mode: str = "qa",
        conversation_context: List = None,
        force_web_search: bool = False
    ) -> EnhancedRAGResponse:
        """
        Process query with intelligent routing between vector DB and web search

        Args:
            query: User query
            user_id: User identifier
            mode: Query mode (qa, drafting, summarization)
            conversation_context: Previous conversation messages
            force_web_search: Force web search regardless of auto-detection

        Returns:
            Enhanced RAG response with combined results
        """
        start_time = datetime.utcnow()

        # Determine search strategy
        should_use_web = (
            force_web_search or
            (
                self.google_search.enabled and
                self.settings.enable_web_search and
                self.google_search.should_use_web_search(query, mode)
            )
        )

        search_strategy = "vector_only"
        web_results = []

        if should_use_web:
            # Try web search first for temporal queries
            logger.info("Using web search for query", query=query[:100])

            web_results = await self.google_search.search(
                query=query,
                num_results=self.settings.google_search.max_results,
                restrict_to_legal_sites=self.settings.google_search.restrict_to_legal_sites
            )

            if web_results:
                # Determine if we should combine with vector search
                if self.settings.google_search.combine_with_vector:
                    search_strategy = "hybrid"
                else:
                    search_strategy = "web_only"
            else:
                # Web search failed, fall back to vector
                search_strategy = "vector_fallback"
                logger.warning("Web search returned no results, using vector fallback")

        # Process with appropriate strategy
        if search_strategy in ["web_only", "hybrid"]:
            response = await self._process_with_web_search(
                query=query,
                user_id=user_id,
                mode=mode,
                conversation_context=conversation_context,
                web_results=web_results,
                use_vector=search_strategy == "hybrid"
            )
        else:
            # Vector-only search
            response = await self._process_vector_only(
                query=query,
                user_id=user_id,
                mode=mode,
                conversation_context=conversation_context
            )

        # Add web results metadata
        response.web_results = web_results
        response.used_web_search = bool(web_results)
        response.search_strategy = search_strategy

        processing_time = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            "Query processed",
            strategy=search_strategy,
            web_results_count=len(web_results),
            processing_time=processing_time
        )

        return response

    async def _process_vector_only(
        self,
        query: str,
        user_id: str,
        mode: str,
        conversation_context: List
    ) -> EnhancedRAGResponse:
        """Process query using only vector database"""
        rag_response = await self.rag_pipeline.process_query(
            query=query,
            user_id=user_id,
            mode=mode,
            conversation_context=conversation_context or []
        )

        return EnhancedRAGResponse(
            answer=rag_response.answer,
            citations=rag_response.citations,
            confidence_score=rag_response.confidence_score,
            token_usage=rag_response.token_usage,
            web_results=[],
            used_web_search=False,
            search_strategy="vector_only"
        )

    async def _process_with_web_search(
        self,
        query: str,
        user_id: str,
        mode: str,
        conversation_context: List,
        web_results: List[SearchResult],
        use_vector: bool = True
    ) -> EnhancedRAGResponse:
        """Process query with web search results"""

        # Get vector search results if hybrid mode
        vector_citations = []
        vector_context = ""

        if use_vector:
            rag_response = await self.rag_pipeline.process_query(
                query=query,
                user_id=user_id,
                mode=mode,
                conversation_context=conversation_context or []
            )
            vector_citations = rag_response.citations
            # Get the original RAG context (simplified)
            vector_context = f"**Knowledge Base Information:**\n{rag_response.answer[:500]}...\n\n"

        # Format web search results as context
        web_context = self.google_search.format_search_context(
            web_results,
            max_length=2000
        )

        # Combine contexts
        combined_context = vector_context + web_context

        # Generate answer with combined context
        # For now, use the RAG pipeline with enhanced context
        # In production, you'd pass this to OpenAI with a custom prompt
        from services.local_openai_service import openai_service

        prompt = self._build_web_enhanced_prompt(
            query=query,
            mode=mode,
            combined_context=combined_context,
            web_results=web_results
        )

        try:
            llm_response = await openai_service.generate_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4",
                temperature=0.3,
                max_tokens=2000
            )

            final_answer = llm_response.get("content", "")
            token_usage = llm_response.get("usage", {})

            # Create combined citations
            web_citations = [
                {
                    "title": result.title,
                    "source": result.source,
                    "link": result.link,
                    "snippet": result.snippet,
                    "type": "web_search"
                }
                for result in web_results
            ]

            combined_citations = vector_citations + web_citations

            return EnhancedRAGResponse(
                answer=final_answer,
                citations=combined_citations,
                confidence_score=0.85,  # Higher confidence with web results
                token_usage=token_usage,
                web_results=web_results,
                used_web_search=True,
                search_strategy="hybrid" if use_vector else "web_only"
            )

        except Exception as e:
            logger.error("Error generating web-enhanced response", error=str(e))
            # Fallback to vector-only
            return await self._process_vector_only(
                query=query,
                user_id=user_id,
                mode=mode,
                conversation_context=conversation_context
            )

    def _build_web_enhanced_prompt(
        self,
        query: str,
        mode: str,
        combined_context: str,
        web_results: List[SearchResult]
    ) -> str:
        """Build prompt with web search results"""

        mode_instructions = {
            "qa": "Provide a comprehensive answer based on both the knowledge base and latest web information.",
            "drafting": "Draft the requested legal document using both knowledge base templates and latest legal updates from the web.",
            "summarization": "Summarize the information from both the knowledge base and latest web sources."
        }

        prompt = f"""You are an expert Indian legal AI assistant with access to both a comprehensive legal knowledge base and real-time web search results.

**User Query:** {query}

**Mode:** {mode_instructions.get(mode, 'Answer the question accurately.')}

**Available Information:**
{combined_context}

**Instructions:**
1. Synthesize information from BOTH the knowledge base and web search results
2. Prioritize recent web results for temporal queries (latest, recent, current, etc.)
3. Use knowledge base for foundational legal principles and established case law
4. Cite your sources clearly:
   - For knowledge base: Cite as [KB: Case/Act name]
   - For web results: Cite as [Source: {web_results[0].source if web_results else 'Web'}]
5. If there's conflicting information, explain both perspectives
6. For legal queries, always maintain accuracy and cite authoritative sources
7. If information is uncertain, explicitly state this

**Answer:**"""

        return prompt


# Create singleton instance
enhanced_rag_service = EnhancedRAGService()
