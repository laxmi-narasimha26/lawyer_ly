from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

import asyncio
import logging
import time

from .temporal_reasoning import TemporalReasoner
from .query_analysis_service import QueryAnalysisService
from ..search.hybrid_search import get_hybrid_search_engine, HybridSearchEngine
from ..models.legal_models import TemporalContext, QueryAnalysis


logger = logging.getLogger(__name__)


class RetrievalService:
    """High-level orchestration for query analysis and hybrid retrieval."""

    def __init__(self, temporal_reasoner: Optional[TemporalReasoner] = None):
        self.temporal_reasoner = temporal_reasoner or TemporalReasoner()
        self.query_analysis_service = QueryAnalysisService(self.temporal_reasoner)
        self._hybrid_engine: Optional[HybridSearchEngine] = None

    async def _get_hybrid_engine(self) -> HybridSearchEngine:
        if self._hybrid_engine is None:
            self._hybrid_engine = await get_hybrid_search_engine()
        return self._hybrid_engine

    async def search(
        self,
        query: str,
        query_embedding: list[float],
        statute_k: int = 8,
        case_k: int = 8,
    ) -> Dict[str, Any]:
        from legal_kb.database.connection import get_db_manager
        await get_db_manager()

        analysis: QueryAnalysis = self.query_analysis_service.analyze(query)
        refusal_reason = self.query_analysis_service.should_refuse(analysis)
        clarification = self.query_analysis_service.generate_clarification(analysis)
        temporal_context: TemporalContext = analysis.temporal_context or self.temporal_reasoner.extract_context(query)

        if refusal_reason:
            return {
                "temporal_context": asdict(temporal_context),
                "query_analysis": asdict(analysis),
                "clarifying_question": clarification,
                "refusal_reason": refusal_reason,
                "statutes": [],
                "cases": [],
                "total_retrieved": 0,
            }

        filters = {
            "as_on_date": temporal_context.as_on_date,
            "decision_date_to": temporal_context.as_on_date,
            "section_guesses": analysis.section_guesses,
            "explicit_sections": analysis.explicit_sections,
            "case_mentions": analysis.case_mentions,
            "explicit_case_ids": analysis.explicit_case_ids,
        }

        expanded_query = self.query_analysis_service.build_expanded_query(analysis)

        engine = await self._get_hybrid_engine()

        filters_sc = {**filters, "court_prefix": filters.get("court_prefix") or "SC:"}

        async def timed(label: str, coro):
            start = time.perf_counter()
            result = await coro
            elapsed = (time.perf_counter() - start) * 1000
            return label, result, elapsed

        gather_results = await asyncio.gather(
            timed("statute_ann", engine.fetch_statute_ann(query_embedding, filters)),
            timed("statute_bm25", engine.fetch_statute_bm25(expanded_query, filters)),
            timed("case_ann", engine.fetch_case_ann(query_embedding, filters_sc, 320)),
            timed("case_bm25", engine.fetch_case_bm25(expanded_query, filters_sc, 140)),
        )

        metrics: Dict[str, Dict[str, Any]] = {}
        for label, result, elapsed in gather_results:
            metrics[label] = {"results": result, "elapsed": elapsed}

        logger.debug(
            "retrieval timers ms: statute_ann=%.1f statute_bm25=%.1f case_ann=%.1f case_bm25=%.1f",
            metrics["statute_ann"]["elapsed"],
            metrics["statute_bm25"]["elapsed"],
            metrics["case_ann"]["elapsed"],
            metrics["case_bm25"]["elapsed"],
        )

        vector_statutes = metrics["statute_ann"]["results"]
        keyword_statutes = metrics["statute_bm25"]["results"]
        vector_cases_primary = metrics["case_ann"]["results"]
        keyword_cases_primary = metrics["case_bm25"]["results"]

        lexical_statutes = await engine._fetch_statute_sections(filters.get("explicit_sections") or [])
        lexical_cases = await engine._fetch_cases_by_title(
            filters.get("case_mentions") or [],
            limit=min(engine.max_case_results, 48),
        )
        doc_case_matches = await engine._fetch_cases_by_ids(
            query,
            filters.get("explicit_case_ids") or [],
            limit_per_doc=max(case_k, 6),
            decision_date_to=filters.get("decision_date_to"),
        )

        vector_statutes_all = vector_statutes + lexical_statutes
        guessed_sections = filters.get("section_guesses") or []
        final_statutes = engine._combine_candidates(
            vector_statutes_all,
            keyword_statutes,
            source_type="statute",
            top_k=statute_k,
            guessed_sections=guessed_sections,
        )

        vector_cases_all = vector_cases_primary + lexical_cases + doc_case_matches
        final_cases = engine._combine_candidates(
            vector_cases_all,
            keyword_cases_primary,
            source_type="case",
            top_k=case_k,
            query_text=expanded_query,
        )

        fallback_filters = {**filters, "court_prefix": None}
        fallback_ann, fallback_kw = await asyncio.gather(
            engine.fetch_case_ann(query_embedding, fallback_filters, 320),
            engine.fetch_case_bm25(expanded_query, fallback_filters, 140),
        )
        vector_cases_union = fallback_ann + vector_cases_all
        keyword_cases_union = fallback_kw + keyword_cases_primary
        final_cases = engine._combine_candidates(
            vector_cases_union,
            keyword_cases_union,
            source_type="case",
            top_k=case_k,
            query_text=expanded_query,
        )
        logger.debug("case fallback union applied; final count=%d", len(final_cases))

        await engine.hydrate_full_text(final_statutes, final_cases)

        statutes = self.temporal_reasoner.enforce_temporal_validity(final_statutes, temporal_context.as_on_date)
        cases = self.temporal_reasoner.enforce_temporal_validity(final_cases, temporal_context.as_on_date)

        for result in statutes:
            legacy = self.temporal_reasoner.map_to_legacy(result.metadata)
            if legacy:
                result.metadata = {**(result.metadata or {}), "legacy_mappings": legacy}

        return {
            "temporal_context": asdict(temporal_context),
            "query_analysis": asdict(analysis),
            "clarifying_question": clarification,
            "statutes": [asdict(result) for result in statutes],
            "cases": [asdict(result) for result in cases],
            "total_retrieved": len(statutes) + len(cases),
        }
