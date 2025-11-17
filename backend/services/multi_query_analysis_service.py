"""
Multi-Query Analysis Mode Service
Breaks down complex queries into sub-queries and provides comprehensive analysis
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from datetime import datetime
import asyncio


class SubQuery(BaseModel):
    """Individual sub-query generated from main query"""
    sub_query_id: int
    query_text: str
    category: str  # e.g., "statutory", "procedural", "precedent", "practical"
    priority: int  # 1 (highest) to 5 (lowest)
    answer: Optional[str] = None
    sources: List[Dict[str, Any]] = []
    confidence: float = 0.0


class MultiQueryAnalysisResult(BaseModel):
    """Complete multi-query analysis result"""
    original_query: str
    sub_queries: List[SubQuery]
    integrated_answer: str
    total_sources: int
    analysis_duration_ms: int
    overall_confidence: float


class MultiQueryAnalysisService:
    """
    Multi-Query Analysis Mode - Decomposes complex queries into sub-queries

    Process:
    1. Query Decomposition - Break complex query into simpler sub-queries
    2. Parallel Research - Research each sub-query independently
    3. Integration - Combine answers into comprehensive response
    4. Validation - Ensure consistency across sub-answers
    """

    def __init__(
        self,
        rag_pipeline,
        llm_service,
        citation_manager
    ):
        self.rag_pipeline = rag_pipeline
        self.llm = llm_service
        self.citation_manager = citation_manager

    async def analyze_multi_query(
        self,
        query: str,
        user_id: str,
        max_sub_queries: int = 8
    ) -> MultiQueryAnalysisResult:
        """
        Perform multi-query analysis

        Args:
            query: Complex legal query to analyze
            user_id: User performing the analysis
            max_sub_queries: Maximum number of sub-queries to generate
        """
        start_time = datetime.utcnow()

        # Step 1: Decompose query into sub-queries
        sub_queries = await self._decompose_query(query, max_sub_queries)

        # Step 2: Research each sub-query in parallel
        research_tasks = [
            self._research_sub_query(sq, user_id)
            for sq in sub_queries
        ]
        researched_sub_queries = await asyncio.gather(*research_tasks)

        # Step 3: Integrate answers
        integrated_answer = await self._integrate_answers(
            query,
            researched_sub_queries
        )

        # Step 4: Calculate metrics
        total_sources = sum(len(sq.sources) for sq in researched_sub_queries)
        overall_confidence = sum(sq.confidence for sq in researched_sub_queries) / len(researched_sub_queries) if researched_sub_queries else 0.0

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return MultiQueryAnalysisResult(
            original_query=query,
            sub_queries=researched_sub_queries,
            integrated_answer=integrated_answer,
            total_sources=total_sources,
            analysis_duration_ms=duration,
            overall_confidence=overall_confidence
        )

    async def _decompose_query(
        self,
        query: str,
        max_sub_queries: int
    ) -> List[SubQuery]:
        """Decompose complex query into simpler sub-queries"""

        decomposition_prompt = f"""You are a legal research expert. Break down this complex legal query into {max_sub_queries} simpler, focused sub-queries.

**Complex Query:** {query}

**Instructions:**
1. Identify different aspects of the query (statutory, procedural, precedent-based, practical)
2. Create focused sub-queries for each aspect
3. Prioritize sub-queries (1 = most important, 5 = least important)
4. Ensure sub-queries cover the full scope of the original question

**Format your response as a JSON array:**
```json
[
  {{
    "sub_query_id": 1,
    "query_text": "...",
    "category": "statutory|procedural|precedent|practical|conceptual",
    "priority": 1-5
  }}
]
```

**Sub-Queries:**
"""

        response = await self.llm.generate_completion(
            messages=[{"role": "user", "content": decomposition_prompt}],
            temperature=0.5
        )

        # Parse response and create SubQuery objects
        sub_queries = []
        try:
            import json
            import re

            # Extract JSON from response
            content = response.get("content", "")
            json_match = re.search(r'\[.*\]', content, re.DOTALL)

            if json_match:
                sq_data = json.loads(json_match.group())

                for item in sq_data[:max_sub_queries]:
                    sub_queries.append(SubQuery(
                        sub_query_id=item.get("sub_query_id", len(sub_queries) + 1),
                        query_text=item.get("query_text", ""),
                        category=item.get("category", "general"),
                        priority=item.get("priority", 3)
                    ))
        except Exception as e:
            # Fallback: create basic sub-queries
            sub_queries = [
                SubQuery(
                    sub_query_id=1,
                    query_text=f"What is the statutory framework for: {query}?",
                    category="statutory",
                    priority=1
                ),
                SubQuery(
                    sub_query_id=2,
                    query_text=f"What are the relevant precedents for: {query}?",
                    category="precedent",
                    priority=2
                ),
                SubQuery(
                    sub_query_id=3,
                    query_text=f"What is the procedure for: {query}?",
                    category="procedural",
                    priority=2
                ),
            ]

        return sub_queries

    async def _research_sub_query(
        self,
        sub_query: SubQuery,
        user_id: str
    ) -> SubQuery:
        """Research a single sub-query"""

        # Determine search strategy based on category
        search_strategy_map = {
            "statutory": "KEYWORD_BOOSTED",
            "procedural": "KEYWORD_BOOSTED",
            "precedent": "HYBRID",
            "practical": "SEMANTIC_RERANK",
            "conceptual": "VECTOR_ONLY"
        }

        strategy = search_strategy_map.get(sub_query.category, "HYBRID")

        # Retrieve context
        try:
            context_result = await self.rag_pipeline.retrieve_context(
                query=sub_query.query_text,
                user_id=user_id,
                search_strategy=strategy,
                max_chunks=8
            )

            chunks = context_result.get("chunks", [])

            # Store sources
            sub_query.sources = [
                {
                    "source_name": chunk.get("source_name", "Unknown"),
                    "content": chunk.get("text", ""),
                    "relevance": chunk.get("similarity_score", 0.0)
                }
                for chunk in chunks
            ]

            # Generate answer for this sub-query
            context_text = "\n\n".join([
                f"[Source: {chunk.get('source_name', 'Unknown')}]\n{chunk.get('text', '')}"
                for chunk in chunks[:5]
            ])

            answer_prompt = f"""Answer this specific legal sub-query based on the provided sources.

**Sub-Query:** {sub_query.query_text}

**Category:** {sub_query.category}

**Sources:**
{context_text}

**Instructions:**
- Provide a focused, direct answer to this sub-query
- Cite sources properly
- Keep it concise (2-4 paragraphs)
- Focus only on this specific aspect

**Answer:**
"""

            answer_response = await self.llm.generate_completion(
                messages=[{"role": "user", "content": answer_prompt}],
                temperature=0.3,
                max_tokens=800
            )

            sub_query.answer = answer_response.get("content", "No answer generated.")

            # Calculate confidence based on source relevance
            if chunks:
                avg_relevance = sum(c.get("similarity_score", 0) for c in chunks) / len(chunks)
                sub_query.confidence = avg_relevance
            else:
                sub_query.confidence = 0.2

        except Exception as e:
            sub_query.answer = f"Error researching this aspect: {str(e)}"
            sub_query.confidence = 0.0

        return sub_query

    async def _integrate_answers(
        self,
        original_query: str,
        sub_queries: List[SubQuery]
    ) -> str:
        """Integrate all sub-query answers into comprehensive response"""

        # Sort by priority
        sorted_queries = sorted(sub_queries, key=lambda x: x.priority)

        # Build integration context
        integration_context = ""
        for sq in sorted_queries:
            integration_context += f"""
**Aspect: {sq.category.upper()}**
Sub-Question: {sq.query_text}

Answer:
{sq.answer}

Sources: {len(sq.sources)} found (confidence: {sq.confidence:.2f})

---
"""

        integration_prompt = f"""You are a senior legal expert integrating multi-faceted research.

**Original Complex Query:** {original_query}

**Research Conducted on Multiple Aspects:**
{integration_context}

**Integration Instructions:**
1. Synthesize ALL aspects into ONE comprehensive, well-structured answer
2. Start with a clear executive summary
3. Organize by logical flow (not by sub-queries)
4. Ensure consistency across all aspects
5. Highlight any conflicts or uncertainties
6. Include all important citations
7. Provide practical guidance
8. End with key takeaways

**Integrated Comprehensive Answer:**
"""

        response = await self.llm.generate_completion(
            messages=[{"role": "user", "content": integration_prompt}],
            temperature=0.4,
            max_tokens=2500
        )

        integrated_answer = response.get("content", "Unable to integrate answers.")

        # Add metadata
        metadata = f"\n\n---\n**Analysis Breakdown:**\n"
        metadata += f"- Original query decomposed into {len(sub_queries)} focused sub-queries\n"
        metadata += f"- Total sources consulted: {sum(len(sq.sources) for sq in sub_queries)}\n"
        metadata += f"- Aspects covered: {', '.join(set(sq.category for sq in sub_queries))}\n"

        return integrated_answer + metadata

    def _validate_consistency(
        self,
        sub_queries: List[SubQuery]
    ) -> Dict[str, Any]:
        """Validate consistency across sub-query answers"""

        # Check for contradictions or inconsistencies
        # This is a simplified version - can be enhanced with LLM-based validation

        issues = []

        # Check if answers reference different jurisdictions
        # Check if statutory and precedent answers align
        # Flag if low confidence answers

        low_confidence_queries = [
            sq for sq in sub_queries if sq.confidence < 0.3
        ]

        if low_confidence_queries:
            issues.append({
                "type": "low_confidence",
                "message": f"{len(low_confidence_queries)} sub-queries have low confidence",
                "queries": [sq.query_text for sq in low_confidence_queries]
            })

        return {
            "consistent": len(issues) == 0,
            "issues": issues
        }
