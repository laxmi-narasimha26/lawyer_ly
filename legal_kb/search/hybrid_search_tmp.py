"""
Hybrid retrieval engine combining dense and sparse search with re-ranking.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from dataclasses import replace
from datetime import date
from typing import Any, Dict, List, Optional

from .vector_search import get_vector_search_engine, VectorSearchEngine
from .keyword_search import get_keyword_search_engine, KeywordSearchEngine
from ..models.legal_models import SearchResult, SearchResults
from ..database.connection import get_db_manager

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """Combines dense vector search with keyword/BM25 and adaptive re-ranking."""

    def __init__(self) -> None:
        self.vector_weight = 0.6
        self.keyword_weight = 0.25
        self.recency_weight = 0.1
        self.authority_weight = 0.05
        self.mmr_lambda = 0.7
        self.max_statute_results = 60
        self.max_case_results = 120
        self.vector_engine: Optional[VectorSearchEngine] = None
        self.keyword_engine: Optional[KeywordSearchEngine] = None

    async def initialize(self) -> None:
        if self.vector_engine is None:
            self.vector_engine = await get_vector_search_engine()
        if self.keyword_engine is None:
            self.keyword_engine = await get_keyword_search_engine()

    @staticmethod
    def _merge_metadata(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(primary or {})
        for key, value in (secondary or {}).items():
            if value is None:
                continue
            if key not in merged or merged[key] in (None, "", []):
                merged[key] = value
        return merged

    @staticmethod
    def _compute_recency(metadata: Dict[str, Any], source_type: str) -> float:
        if source_type == "case":
            decision_date = metadata.get("decision_date")
            if decision_date:
                try:
                    decided = date.fromisoformat(decision_date)
                    delta_years = max((date.today() - decided).days / 365.0, 0.0)
                    return 1.0 / (1.0 + delta_years)
                except ValueError:
                    return 0.0
        if source_type == "statute":
            effective_from = metadata.get("effective_from")
            if effective_from:
                try:
                    started = date.fromisoformat(effective_from)
                    delta_years = max((date.today() - started).days / 365.0, 0.0)
                    return max(0.2, 1.0 / (1.0 + delta_years))
                except ValueError:
                    return 0.3
        return 0.0

    @staticmethod
    def _compute_authority(metadata: Dict[str, Any], source_type: str) -> float:
        if source_type == "case":
            bench = metadata.get("bench") or []
            try:
                bench_size = len(bench)
            except TypeError:
                bench_size = 0
            return 1.0 + 0.05 * min(bench_size, 5)
        if source_type == "statute":
            unit_type = metadata.get("unit_type")
            return 1.1 if unit_type == "Section" else 1.0
        return 1.0

    async def _fetch_statute_sections(self, sections: List[str]) -> List[SearchResult]:
        if not sections:
            return []
        normalized = sorted({section.upper() for section in sections})
        try:
            db_manager = await get_db_manager()
        except Exception as exc:
            logger.error("Statute fallback lookup failed: %s", exc)
            return []

        rows = await db_manager.execute_query(
            """
            SELECT
                id,
                doc_id,
                title,
                section_no,
                unit_type,
                text,
                tokens,
                act,
                effective_from,
                effective_to,
                source_path
            FROM statute_chunks
            WHERE section_no = ANY($1::text[])
            ORDER BY section_no, "order"
            """,
            normalized,
        )

        results: List[SearchResult] = []
        for row in rows:
            metadata = {
                "doc_id": row["doc_id"],
                "title": row["title"],
                "section_no": row["section_no"],
                "unit_type": row["unit_type"],
                "tokens": row["tokens"],
                "act": row["act"],
                "canonical_id": f"{row['doc_id']}:Sec:{row['section_no']}",
                "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
                "effective_to": row["effective_to"].isoformat() if row["effective_to"] else None,
                "source_path": row["source_path"],
                "fallback_match": True,
            }
            results.append(
                SearchResult(
                    id=row["id"],
                    similarity_score=1.0,
                    content=row["text"],
                    metadata=metadata,
                    source_type="statute",
                )
            )
        return results

    async def _fetch_cases_by_title(self, mentions: List[str], limit: int = 24) -> List[SearchResult]:
        if not mentions:
            return []
        try:
            db_manager = await get_db_manager()
        except Exception as exc:
            logger.error("Case title fallback failed: %s", exc)
            return []

        results: List[SearchResult] = []
        seen_ids: set[str] = set()
        query = """
        SELECT
            id,
            doc_id,
            case_title,
            decision_date,
            bench,
            citation_strings,
            para_range,
            text,
            tokens,
            source_path
        FROM judgment_chunks
        WHERE REGEXP_REPLACE(UPPER(case_title), '[^A-Z0-9]', '', 'g') LIKE $1
        ORDER BY doc_id, "order"
        LIMIT $2
        """

        for mention in mentions:
            normalized = re.sub(r"[^A-Z0-9]", "", mention.upper())
            if not normalized:
                continue
            pattern = f"%{normalized}%"
            try:
                rows = await db_manager.execute_query(query, pattern, limit)
            except Exception as exc:
                logger.error("Title fallback query failed for %s: %s", pattern, exc)
                continue
            for row in rows:
                if row["id"] in seen_ids:
                    continue
                metadata = {
                    "doc_id": row["doc_id"],
                    "case_title": row["case_title"],
                    "decision_date": row["decision_date"].isoformat() if row["decision_date"] else None,
                    "bench": row["bench"],
                    "citation_strings": row["citation_strings"],
                    "para_range": row["para_range"],
                    "tokens": row["tokens"],
                    "source_path": row["source_path"],
                    "fallback_match": True,
                }
                results.append(
                    SearchResult(
                        id=row["id"],
                        similarity_score=1.0 + 0.05 * score + 0.0001 * row["order"],
                        content=row["text"],
                        metadata=metadata,
                        source_type="case",
                    )
                )
                seen_ids.add(row["id"])
        return results

    @staticmethod
    def _sanitize_case_query(raw_query: str, case_id: str) -> str:
        sanitized = re.sub(re.escape(case_id), " ", raw_query, flags=re.IGNORECASE)
        sanitized = re.sub(r"SC:\d{4}:[A-Z0-9_]+", " ", sanitized, flags=re.IGNORECASE)
        tokens = [
            token
            for token in sanitized.split()
            if token.isalpha() and len(token) > 2
        ]
        if tokens:
            return " ".join(tokens)
        tail = case_id.split(":")[-1]
        return tail.replace("_", " ")

    async def _fetch_cases_by_ids(
        self,
        query: str,
        case_ids: List[str],
        limit_per_doc: int = 6,
        decision_date_to: Optional[date] = None,
    ) -> List[SearchResult]:
        if not case_ids:
            return []
        await self.initialize()
        try:
            db_manager = await get_db_manager()
        except Exception as exc:
            logger.error("Doc-specific case lookup failed: %s", exc)
            return []

        results: List[SearchResult] = []
        seen_ids: set[str] = set()

        for case_id in case_ids:
            keywords = [
                token.lower()
                for token in self._sanitize_case_query(query, case_id).split()
                if len(token) > 2
            ]
            rows = await db_manager.execute_query(
                """
                SELECT
                    id,
                    doc_id,
                    case_title,
                    decision_date,
                    bench,
                    citation_strings,
                    para_range,
                    text,
                    tokens,
                    source_path,
                    "order"
                FROM judgment_chunks
                WHERE doc_id = $1
                ORDER BY "order"
                """,
                case_id,
            )
            scored_rows: List[Tuple[int, Dict[str, Any]]] = []
            for row in rows:
                text_lower = row["text"].lower()
                score = sum(1 for token in keywords if token in text_lower)
                scored_rows.append((score, row))

            if keywords:
                scored_rows.sort(key=lambda item: (-item[0], item[1]["order"]))
                selected = [item for item in scored_rows if item[0] > 0][:limit_per_doc]
            else:
                scored_rows.sort(key=lambda item: item[1]["order"])
                selected = scored_rows[:limit_per_doc]

            if not selected:
                selected = scored_rows[:limit_per_doc]
            else:
                highest_order = max(scored_rows, key=lambda item: item[1]["order"])
                if highest_order[1]["id"] not in {row["id"] for _, row in selected}:
                    selected.append(highest_order)
                selected = selected[:limit_per_doc]

            logger.debug("Doc-specific fallback for %s yielded %d matches", case_id, len(selected))

            for score, row in selected:
                if row["id"] in seen_ids:
                    continue
                seen_ids.add(row["id"])
                metadata = {
                    "doc_id": row["doc_id"],
                    "case_title": row["case_title"],
                    "decision_date": row["decision_date"].isoformat() if row["decision_date"] else None,
                    "bench": row["bench"],
                    "citation_strings": row["citation_strings"],
                    "para_range": row["para_range"],
                    "tokens": row["tokens"],
                    "source_path": row["source_path"],
                    "fallback_match": True,
                    "fallback_doc_match": True,
                    "keyword_hits": score,
                }
                results.append(
                    SearchResult(
                        id=row["id"],
                        similarity_score=1.0,
                        content=row["text"],
                        metadata=metadata,
                        source_type="case",
                    )
                )
        return results

    def _combine_candidates(
        self,
        vector_results: List[SearchResult],
        keyword_results: List[SearchResult],
        source_type: str,
        top_k: int,
        guessed_sections: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        candidates: Dict[str, Dict[str, Any]] = {}
        max_vector = max((res.similarity_score for res in vector_results), default=0.0)
        max_keyword = max((res.similarity_score for res in keyword_results), default=0.0)

        for res in vector_results:
            candidates[res.id] = {
                "result": res,
                "vector_score": res.similarity_score,
                "keyword_score": 0.0,
            }

        for res in keyword_results:
            entry = candidates.get(res.id)
            if entry:
                entry["keyword_score"] = res.similarity_score
                entry["result"] = replace(
                    entry["result"],
                    metadata=self._merge_metadata(entry["result"].metadata, res.metadata),
                    content=entry["result"].content or res.content,
                )
            else:
                candidates[res.id] = {
                    "result": res,
                    "vector_score": 0.0,
                    "keyword_score": res.similarity_score,
                }

        logger.debug(
            "Candidate pool size for %s: vector=%d keyword=%d",
            source_type,
            len(vector_results),
            len(keyword_results),
        )

        guessed_sections = guessed_sections or []
        combined: List[SearchResult] = []
        for entry in candidates.values():
            base_result: SearchResult = entry["result"]
            vector_norm = entry["vector_score"] / max_vector if max_vector > 0 else 0.0
            keyword_norm = entry["keyword_score"] / max_keyword if max_keyword > 0 else 0.0
            recency = self._compute_recency(base_result.metadata, source_type)
            authority = self._compute_authority(base_result.metadata, source_type)

            final_score = (
                self.vector_weight * vector_norm
                + self.keyword_weight * keyword_norm
                + self.recency_weight * recency
                + self.authority_weight * (authority - 1.0)
            )

            boost = 0.0
            if source_type == "statute":
                section_no = base_result.metadata.get("section_no")
                canonical_id = base_result.metadata.get("canonical_id") or base_result.metadata.get("doc_id")
                if section_no and any(section_no in guess for guess in guessed_sections):
                    boost += 0.15
                if canonical_id and canonical_id in guessed_sections:
                    boost += 0.25

            combined.append(
                replace(
                    base_result,
                    similarity_score=final_score + boost,
                    authority_weight=authority,
                    metadata={
                        **(base_result.metadata or {}),
                        "vector_score": entry["vector_score"],
                        "keyword_score": entry["keyword_score"],
                        "recency_score": recency,
                        "final_score": final_score,
                    },
                )
            )

        ranked = self._apply_mmr(combined, top_k)
        logger.debug(
            "Final ranked %s ids: %s",
            source_type,
            [result.id for result in ranked[:top_k]],
        )
        return ranked[:top_k]

    def _apply_mmr(self, candidates: List[SearchResult], top_k: int) -> List[SearchResult]:
        if not candidates:
            return []
        candidates = sorted(candidates, key=lambda r: r.similarity_score, reverse=True)
        selected: List[SearchResult] = []
        remaining = candidates.copy()

        def _similarity(a: SearchResult, b: SearchResult) -> float:
            if a.metadata.get("fallback_match") or b.metadata.get("fallback_match"):
                return 0.0
            return 1.0 if a.metadata.get("doc_id") == b.metadata.get("doc_id") else 0.0

        while remaining and len(selected) < top_k:
            best_candidate = None
            best_score = -math.inf
            for candidate in remaining:
                relevance = candidate.similarity_score
                diversity = max((_similarity(candidate, chosen) for chosen in selected), default=0.0)
                mmr_score = self.mmr_lambda * relevance - (1 - self.mmr_lambda) * diversity
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_candidate = candidate
            selected.append(best_candidate)
            remaining.remove(best_candidate)
        return selected

    async def search(
        self,
        query: str,
        query_embedding: List[float],
        statute_k: int = 8,
        case_k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SearchResults:
        filters = filters or {}
        await self.initialize()

        vector_results = await self.vector_engine.hybrid_vector_search(
            query_embedding,
            statute_k=self.max_statute_results,
            case_k=self.max_case_results,
            filters=filters,
        )

        keyword_statutes, keyword_cases = await asyncio.gather(
            self.keyword_engine.search_statutes(
                query,
                k=self.max_statute_results,
                act_filter=filters.get("act"),
                effective_date=filters.get("as_on_date"),
            ),
            self.keyword_engine.search_cases(
                query,
                k=self.max_case_results,
                doc_prefix=filters.get("court_prefix"),
                decision_date_to=filters.get("decision_date_to"),
            ),
        )

        explicit_sections = filters.get("explicit_sections") or []
        explicit_case_mentions = filters.get("case_mentions") or []
        explicit_case_ids = filters.get("explicit_case_ids") or []

        lexical_statutes = await self._fetch_statute_sections(explicit_sections)
        lexical_cases = await self._fetch_cases_by_title(explicit_case_mentions, limit=min(self.max_case_results, 48))
        doc_case_matches = await self._fetch_cases_by_ids(
            query,
            explicit_case_ids,
            limit_per_doc=max(case_k, 6),
            decision_date_to=filters.get("decision_date_to"),
        )

        vector_statutes = vector_results.statutes + lexical_statutes
        vector_cases = vector_results.cases + lexical_cases + doc_case_matches

        guessed_sections = filters.get("section_guesses")

        start = time.perf_counter()
        final_statutes = self._combine_candidates(
            vector_statutes,
            keyword_statutes,
            source_type="statute",
            top_k=statute_k,
            guessed_sections=guessed_sections,
        )
        final_cases = self._combine_candidates(
            vector_cases,
            keyword_cases,
            source_type="case",
            top_k=case_k,
        )
        processing_time = time.perf_counter() - start

        return SearchResults(
            statutes=final_statutes,
            cases=final_cases,
            total_retrieved=len(final_statutes) + len(final_cases),
            processing_time=processing_time,
        )


hybrid_search_engine: Optional[HybridSearchEngine] = None


async def get_hybrid_search_engine() -> HybridSearchEngine:
    global hybrid_search_engine
    if hybrid_search_engine is None:
        hybrid_search_engine = HybridSearchEngine()
    return hybrid_search_engine
