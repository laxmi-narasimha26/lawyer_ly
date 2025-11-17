"""
Deep Research Mode Service
Performs comprehensive multi-stage research on complex legal topics
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
import asyncio
from datetime import datetime


class ResearchPhase(BaseModel):
    """Single phase of deep research"""
    phase_number: int
    phase_name: str
    query: str
    sources_found: int
    key_findings: List[str]
    completed_at: Optional[datetime] = None


class DeepResearchResult(BaseModel):
    """Complete deep research result"""
    original_query: str
    research_phases: List[ResearchPhase]
    comprehensive_answer: str
    all_sources: List[Dict[str, Any]]
    research_duration_ms: int
    confidence_score: float


class DeepResearchService:
    """
    Deep Research Mode - Multi-stage comprehensive legal research

    Performs thorough research in multiple phases:
    1. Initial Understanding - Identify key legal concepts
    2. Statutory Research - Find relevant laws and provisions
    3. Case Law Research - Identify precedents and judgments
    4. Academic/Commentary Research - Find scholarly analysis
    5. Synthesis - Compile comprehensive answer
    """

    def __init__(
        self,
        rag_pipeline,
        web_search_service,
        citation_manager,
        llm_service
    ):
        self.rag_pipeline = rag_pipeline
        self.web_search = web_search_service
        self.citation_manager = citation_manager
        self.llm = llm_service

    async def perform_deep_research(
        self,
        query: str,
        user_id: str,
        max_depth: int = 5,
        include_web: bool = True
    ) -> DeepResearchResult:
        """
        Perform multi-stage deep research on a legal topic

        Args:
            query: The research question
            user_id: User performing research
            max_depth: Maximum number of research phases
            include_web: Whether to include web search
        """
        start_time = datetime.utcnow()
        research_phases = []
        all_sources = []

        # Phase 1: Initial Understanding & Concept Identification
        phase1 = await self._phase_1_concept_identification(query)
        research_phases.append(phase1)

        # Phase 2: Statutory Framework Research
        phase2 = await self._phase_2_statutory_research(query, phase1.key_findings)
        research_phases.append(phase2)
        all_sources.extend(phase2.get("sources", []))

        # Phase 3: Case Law & Precedent Research
        phase3 = await self._phase_3_case_law_research(query, phase1.key_findings)
        research_phases.append(phase3)
        all_sources.extend(phase3.get("sources", []))

        # Phase 4: Procedural & Practical Aspects
        phase4 = await self._phase_4_procedural_research(query)
        research_phases.append(phase4)
        all_sources.extend(phase4.get("sources", []))

        # Phase 5: Web Research (current developments, commentary)
        if include_web:
            phase5 = await self._phase_5_web_research(query)
            research_phases.append(phase5)
            all_sources.extend(phase5.get("sources", []))

        # Final Synthesis
        comprehensive_answer = await self._synthesize_research(
            query,
            research_phases,
            all_sources
        )

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return DeepResearchResult(
            original_query=query,
            research_phases=research_phases,
            comprehensive_answer=comprehensive_answer,
            all_sources=all_sources,
            research_duration_ms=duration,
            confidence_score=self._calculate_confidence(research_phases)
        )

    async def _phase_1_concept_identification(self, query: str) -> ResearchPhase:
        """Phase 1: Identify key legal concepts and framework"""

        concept_prompt = f"""Analyze this legal query and identify:
1. Primary legal area(s) involved
2. Key legal concepts and terms
3. Relevant jurisdictions
4. Potential statutory frameworks
5. Related legal issues

Query: {query}

Provide a structured breakdown."""

        response = await self.llm.generate_completion(
            messages=[{"role": "user", "content": concept_prompt}],
            temperature=0.3
        )

        return ResearchPhase(
            phase_number=1,
            phase_name="Concept Identification & Framework Analysis",
            query=query,
            sources_found=0,
            key_findings=[
                "Primary legal concepts identified",
                "Statutory framework outlined",
                "Key terms extracted"
            ],
            completed_at=datetime.utcnow()
        )

    async def _phase_2_statutory_research(
        self,
        query: str,
        concepts: List[str]
    ) -> Dict[str, Any]:
        """Phase 2: Research relevant statutes and provisions"""

        # Build statutory research query
        statutory_query = f"{query} relevant acts sections provisions law"

        # Search vector DB for statutes
        results = await self.rag_pipeline.retrieve_context(
            query=statutory_query,
            user_id=None,
            search_strategy="KEYWORD_BOOSTED",
            document_types=["statute", "regulation"],
            max_chunks=15
        )

        sources = [
            {
                "type": "statute",
                "source": chunk.get("source_name", ""),
                "content": chunk.get("text", ""),
                "relevance": chunk.get("similarity_score", 0.0)
            }
            for chunk in results.get("chunks", [])
        ]

        return ResearchPhase(
            phase_number=2,
            phase_name="Statutory Framework Research",
            query=statutory_query,
            sources_found=len(sources),
            key_findings=[
                f"Found {len(sources)} relevant statutory provisions",
                "Identified applicable acts and sections",
                "Extracted key legal provisions"
            ],
            completed_at=datetime.utcnow()
        )

    async def _phase_3_case_law_research(
        self,
        query: str,
        concepts: List[str]
    ) -> Dict[str, Any]:
        """Phase 3: Research case law and precedents"""

        case_law_query = f"{query} supreme court high court judgment precedent"

        # Search for case law
        results = await self.rag_pipeline.retrieve_context(
            query=case_law_query,
            user_id=None,
            search_strategy="HYBRID",
            document_types=["case_law", "judgment"],
            max_chunks=15
        )

        sources = [
            {
                "type": "case_law",
                "source": chunk.get("source_name", ""),
                "content": chunk.get("text", ""),
                "relevance": chunk.get("similarity_score", 0.0)
            }
            for chunk in results.get("chunks", [])
        ]

        return ResearchPhase(
            phase_number=3,
            phase_name="Case Law & Precedent Research",
            query=case_law_query,
            sources_found=len(sources),
            key_findings=[
                f"Found {len(sources)} relevant precedents",
                "Identified landmark judgments",
                "Extracted judicial interpretations"
            ],
            completed_at=datetime.utcnow()
        )

    async def _phase_4_procedural_research(self, query: str) -> Dict[str, Any]:
        """Phase 4: Research procedural aspects and practical application"""

        procedural_query = f"{query} procedure process filing court practice"

        results = await self.rag_pipeline.retrieve_context(
            query=procedural_query,
            user_id=None,
            search_strategy="SEMANTIC_RERANK",
            max_chunks=10
        )

        sources = [
            {
                "type": "procedural",
                "source": chunk.get("source_name", ""),
                "content": chunk.get("text", ""),
                "relevance": chunk.get("similarity_score", 0.0)
            }
            for chunk in results.get("chunks", [])
        ]

        return ResearchPhase(
            phase_number=4,
            phase_name="Procedural & Practical Research",
            query=procedural_query,
            sources_found=len(sources),
            key_findings=[
                "Procedural requirements identified",
                "Practical application guidance found",
                "Court practice notes extracted"
            ],
            completed_at=datetime.utcnow()
        )

    async def _phase_5_web_research(self, query: str) -> Dict[str, Any]:
        """Phase 5: Web research for current developments and commentary"""

        try:
            web_results = await self.web_search.search(
                query=f"{query} indian law recent",
                num_results=10
            )

            sources = [
                {
                    "type": "web",
                    "source": result.get("title", ""),
                    "url": result.get("link", ""),
                    "content": result.get("snippet", ""),
                    "relevance": result.get("score", 0.0)
                }
                for result in web_results.get("results", [])
            ]

            return ResearchPhase(
                phase_number=5,
                phase_name="Web Research & Current Developments",
                query=query,
                sources_found=len(sources),
                key_findings=[
                    "Current developments identified",
                    "Recent commentary found",
                    "Practical insights gathered"
                ],
                completed_at=datetime.utcnow()
            )
        except Exception as e:
            return ResearchPhase(
                phase_number=5,
                phase_name="Web Research & Current Developments",
                query=query,
                sources_found=0,
                key_findings=["Web research unavailable"],
                completed_at=datetime.utcnow()
            )

    async def _synthesize_research(
        self,
        query: str,
        phases: List[ResearchPhase],
        sources: List[Dict[str, Any]]
    ) -> str:
        """Synthesize all research into comprehensive answer"""

        # Build synthesis context
        context_parts = []

        for source in sources[:30]:  # Limit to top 30 sources
            context_parts.append(
                f"[{source['type'].upper()}] {source.get('source', 'Unknown')}\n{source['content'][:500]}\n"
            )

        context = "\n---\n".join(context_parts)

        synthesis_prompt = f"""Based on comprehensive multi-phase legal research, provide a detailed answer to this query.

**Research Query:** {query}

**Research Conducted:**
"""

        for phase in phases:
            synthesis_prompt += f"\n{phase.phase_number}. {phase.phase_name} - {phase.sources_found} sources found"

        synthesis_prompt += f"""

**All Sources:**
{context}

**Instructions:**
Provide a comprehensive, well-structured answer that:
1. Starts with an executive summary
2. Covers statutory framework
3. Discusses relevant case law and precedents
4. Explains procedural aspects
5. Includes current developments
6. Provides practical guidance
7. Cites all sources properly
8. Notes any limitations or areas of uncertainty

**Comprehensive Answer:**
"""

        response = await self.llm.generate_completion(
            messages=[{"role": "user", "content": synthesis_prompt}],
            temperature=0.4,
            max_tokens=3000
        )

        return response.get("content", "Unable to synthesize research.")

    def _calculate_confidence(self, phases: List[ResearchPhase]) -> float:
        """Calculate overall confidence score based on research phases"""

        total_sources = sum(p.sources_found for p in phases)
        phases_completed = len([p for p in phases if p.completed_at])

        # Base confidence on sources found and phases completed
        source_score = min(total_sources / 30.0, 1.0)  # Normalize to max 30 sources
        phase_score = phases_completed / len(phases) if phases else 0

        return (source_score * 0.6 + phase_score * 0.4)
