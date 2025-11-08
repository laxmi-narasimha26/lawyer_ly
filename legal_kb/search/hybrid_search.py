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
from typing import Any, Dict, List, Optional, Tuple

from .vector_search import get_vector_search_engine, VectorSearchEngine
from .keyword_search import get_keyword_search_engine, KeywordSearchEngine
from ..models.legal_models import SearchResult, SearchResults
from ..database.connection import get_db_manager
from ..services.query_analysis_service import LEGAL_SYNONYMS

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
        self.max_case_results = 320
        self.vector_engine: Optional[VectorSearchEngine] = None
        self.keyword_engine: Optional[KeywordSearchEngine] = None
        # Enable lightweight cross-encoder reranker for cases (top-50) by default
        self.use_case_ce_reranker = True
        self._case_ce_model = None
        self._case_ce_failed = False
        self._case_ce_active = False
        self._ce_cache: dict[tuple[str, str], float] = {}
        self._last_ce_pairs: int = 0
        self._last_ce_cache_hits: int = 0

    async def initialize(self) -> None:
        if self.vector_engine is None:
            self.vector_engine = await get_vector_search_engine()
        if self.keyword_engine is None:
            self.keyword_engine = await get_keyword_search_engine()

    async def fetch_statute_ann(self, query_embedding: List[float], filters: Dict[str, Any]) -> List[SearchResult]:
        await self.initialize()
        return await self.vector_engine.search_similar_statutes(
            query_embedding,
            k=self.max_statute_results,
            act_filter=filters.get("act"),
            effective_date=filters.get("as_on_date"),
        )

    async def fetch_statute_bm25(self, query: str, filters: Dict[str, Any]) -> List[SearchResult]:
        await self.initialize()
        return await self.keyword_engine.search_statutes(
            query,
            k=self.max_statute_results,
            act_filter=filters.get("act"),
            effective_date=filters.get("as_on_date"),
        )

    async def fetch_case_ann(self, query_embedding: List[float], filters: Dict[str, Any], k: Optional[int] = None) -> List[SearchResult]:
        await self.initialize()
        return await self.vector_engine.search_similar_cases(
            query_embedding,
            k=k or self.max_case_results,
            court_filter=filters.get("court_prefix"),
            date_filter=filters.get("decision_date_to"),
        )

    async def fetch_case_bm25(self, query: str, filters: Dict[str, Any], k: int = 100) -> List[SearchResult]:
        await self.initialize()
        return await self.keyword_engine.search_cases(
            query,
            k=k,
            doc_prefix=filters.get("court_prefix"),
            decision_date_to=filters.get("decision_date_to"),
        )

    async def hydrate_full_text(self, statutes: List[SearchResult], cases: List[SearchResult]) -> None:
        if not statutes and not cases:
            return
        db_manager = await get_db_manager()
        if statutes:
            statute_ids = [res.id for res in statutes]
            rows = await db_manager.execute_query(
                "SELECT id, text FROM statute_chunks WHERE id = ANY($1::text[])",
                statute_ids,
            )
            text_map = {row["id"]: row["text"] for row in rows}
            for res in statutes:
                if res.id in text_map:
                    res.content = text_map[res.id]
        if cases:
            case_ids = [res.id for res in cases]
            rows = await db_manager.execute_query(
                "SELECT id, text FROM judgment_chunks WHERE id = ANY($1::text[])",
                case_ids,
            )
            text_map = {row["id"]: row["text"] for row in rows}
            for res in cases:
                if res.id in text_map:
                    res.content = text_map[res.id]

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

    @staticmethod
    def _sanitize_case_query(query: str, doc_id: str) -> str:
        doc_bits = re.sub(r"[^A-Za-z0-9 ]+", " ", doc_id or "")
        raw = f"{query} {doc_bits}"
        cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", raw)
        return re.sub(r"\s+", " ", cleaned).strip()

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
                id, doc_id, title, section_no, unit_type, text, tokens, act,
                effective_from, effective_to, source_path, "order"
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
        """Party resolver using trigram LIKE on lower(case_title).
        Injects AND hits (both parties) and OR hits (either party) with different bonuses later.
        """
        if not mentions:
            return []
        try:
            db_manager = await get_db_manager()
        except Exception as exc:
            logger.error("Case title resolver failed: %s", exc)
            return []
        results: List[SearchResult] = []
        seen_ids: set[str] = set()

        STOP_PHRASES = [
            "state of", "union of india", "and anr", "and ors", "and others", "anr.", "ors.", "the"
        ]

        def _clean_party(s: str) -> str:
            s = re.sub(r"[^A-Za-z0-9 ]+", " ", s or "").lower()
            for p in STOP_PHRASES:
                s = s.replace(p, " ")
            return " ".join(s.split())

        for mention in mentions[:6]:
            m = re.search(r"\b(.+?)\s+v(?:\.|s\.)\s+(.+?)\b", mention or "", re.IGNORECASE)
            if not m:
                continue
            left = _clean_party(m.group(1).strip())
            right = _clean_party(m.group(2).strip())
            if not left or not right:
                continue
            left_like = f"%{' '.join(left.split())}%"
            right_like = f"%{' '.join(right.split())}%"
            sql_and = (
                "SELECT id, doc_id, case_title, decision_date, para_range, "
                "SUBSTRING(text,1,400) AS text, tokens, source_path, \"order\" "
                "FROM judgment_chunks "
                "WHERE (lower(case_title) LIKE $1 AND lower(case_title) LIKE $2) "
                "   OR (lower(case_title) LIKE $2 AND lower(case_title) LIKE $1) "
                "ORDER BY doc_id, \"order\" LIMIT $3"
            )
            try:
                rows = await db_manager.execute_query(sql_and, left_like, right_like, min(limit, 40))
            except Exception as exc:
                logger.warning("Party resolver query failed: %s", exc)
                continue
            for row in rows:
                rid = row["id"]
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                meta = {
                    "doc_id": row["doc_id"],
                    "case_title": row["case_title"],
                    "decision_date": row["decision_date"].isoformat() if row["decision_date"] else None,
                    "para_range": row["para_range"],
                    "tokens": row["tokens"],
                    "source_path": row["source_path"],
                    "party_resolver": True,  # AND match (both parties)
                }
                results.append(
                    SearchResult(
                        id=row["id"],
                        similarity_score=1.0,
                        content=row["text"],
                        metadata=meta,
                        source_type="case",
                    )
                )

            # OR-only path: either party; lower-weight; exclude already seen
            sql_or = (
                "SELECT id, doc_id, case_title, decision_date, para_range, "
                "SUBSTRING(text,1,400) AS text, tokens, source_path, \"order\" "
                "FROM judgment_chunks "
                "WHERE (lower(case_title) LIKE $1 OR lower(case_title) LIKE $2) "
                "ORDER BY doc_id, \"order\" LIMIT $3"
            )
            try:
                rows_or = await db_manager.execute_query(sql_or, left_like, right_like, min(limit, 40))
            except Exception:
                rows_or = []
            for row in rows_or:
                rid = row["id"]
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                results.append(
                    SearchResult(
                        id=row["id"],
                        similarity_score=1.0,
                        content=row["text"],
                        metadata={
                            "doc_id": row["doc_id"],
                            "case_title": row["case_title"],
                            "decision_date": row["decision_date"].isoformat() if row["decision_date"] else None,
                            "para_range": row["para_range"],
                            "tokens": row["tokens"],
                            "source_path": row["source_path"],
                            "party_resolver_or": True,
                        },
                        source_type="case",
                    )
                )
        return results

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
                SELECT id, doc_id, case_title, decision_date, bench, citation_strings,
                       para_range, text, tokens, source_path, "order"
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
                highest_order = max(scored_rows, key=lambda item: item[1]["order"], default=None)
                if highest_order and highest_order[1]["id"] not in {row["id"] for _, row in selected}:
                    selected.append(highest_order)
                selected = selected[:limit_per_doc]
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
        query_text: Optional[str] = None,
    ) -> List[SearchResult]:
        if source_type == "case":
            vec_sorted = sorted(vector_results, key=lambda x: x.similarity_score, reverse=True)
            kw_sorted = sorted(keyword_results, key=lambda x: x.similarity_score, reverse=True)
            vec_ranks = {r.id: i + 1 for i, r in enumerate(vec_sorted)}
            kw_ranks = {r.id: i + 1 for i, r in enumerate(kw_sorted)}
            vec_sims = {r.id: r.similarity_score for r in vector_results}
            max_vec = max(vec_sims.values()) if vec_sims else 0.0
            ids = set(vec_ranks) | set(kw_ranks)
            tokens: set[str] = set()
            for r in keyword_results:
                tsq = (r.metadata or {}).get("tsquery") or ""
                for t in re.findall(r"[a-z0-9]+", tsq.lower()):
                    tokens.add(t)
                    for s in LEGAL_SYNONYMS.get(t, []):
                        if s:
                            tokens.add(s.lower())
            # extract statute/section markers from query for bridging
            markers = self._extract_statute_markers(query_text or "")
            fused: List[SearchResult] = []
            K = 60
            for _id in ids:
                base = next((r for r in vector_results if r.id == _id), None) or next(
                    (r for r in keyword_results if r.id == _id), None
                )
                rrf = (1.0 / (K + vec_ranks.get(_id, 10**6))) + (
                    1.0 / (K + kw_ranks.get(_id, 10**6))
                )
                vec_norm = (vec_sims.get(_id, 0.0) / max_vec) if max_vec > 0 else 0.0
                doc_id = (base.metadata or {}).get("doc_id") or ""
                is_sc = doc_id.startswith("SC:")
                authority_boost = 0.15 if is_sc else 0.0
                rec_boost = 0.0
                try:
                    dd = (base.metadata or {}).get("decision_date")
                    if dd:
                        y = date.fromisoformat(dd).year
                        if date.today().year - y <= 10:
                            rec_boost = 0.05
                except Exception:
                    rec_boost = 0.0
                text_lower = (base.content or "").lower()
                topical_hits = sum(1 for t in tokens if t and t in text_lower)
                topical_boost = 0.10 if topical_hits >= 1 else 0.0
                if topical_hits >= 2:
                    topical_boost += 0.05  # small additive boost for >=2 topical tokens
                # statute-to-case bridge: if query has section markers and candidate mentions them
                bridge_bonus = 0.0
                if markers and any(m in text_lower for m in markers):
                    bridge_bonus = 0.20
                resolver_bonus = 0.0
                md = base.metadata or {}
                if md.get("party_resolver"):
                    resolver_bonus = 0.25
                elif md.get("party_resolver_or"):
                    resolver_bonus = 0.10
                elif md.get("fallback_match") or md.get("fallback_doc_match") or md.get("citation_resolver"):
                    resolver_bonus = 0.20
                final = rrf + 0.20 * vec_norm + authority_boost + rec_boost + topical_boost + bridge_bonus + resolver_bonus
                fused.append(replace(base, similarity_score=final))
            fused = sorted(fused, key=lambda r: r.similarity_score, reverse=True)
            fused = self._apply_case_ce(query_text, fused)
            ranked = fused
            ranked = self._apply_mmr(ranked[:max(4*top_k, top_k)], top_k)
            per_doc: Dict[str, int] = {}
            out: List[SearchResult] = []
            for r in ranked:
                did = (r.metadata or {}).get("doc_id")
                c = per_doc.get(did, 0)
                if c >= 3:
                    continue
                per_doc[did] = c + 1
                out.append(r)
                if len(out) >= top_k:
                    break
            return out
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
        guessed_sections = guessed_sections or []
        combined: List[SearchResult] = []
        for entry in candidates.values():
            base_result: SearchResult = entry["result"]
            vector_norm = entry["vector_score"] / max_vector if max_vector > 0 else 0.0
            keyword_norm = entry["keyword_score"] / max_keyword if max_keyword > 0 else 0.0
            recency = self._compute_recency(base_result.metadata, "statute")
            authority = self._compute_authority(base_result.metadata, "statute")
            final_score = (
                self.vector_weight * vector_norm
                + self.keyword_weight * keyword_norm
                + self.recency_weight * recency
                + self.authority_weight * (authority - 1.0)
            )
            boost = 0.0
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

    def _apply_case_ce(self, query_text: Optional[str], candidates: List[SearchResult], top_n: int = 50) -> List[SearchResult]:
        if not self.use_case_ce_reranker or not query_text or not candidates:
            return candidates
        if self._case_ce_failed:
            return candidates
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
        except Exception as exc:  # pragma: no cover
            self._case_ce_failed = True
            logger.warning("Case CE reranker unavailable: %s", exc)
            return candidates

        if self._case_ce_model is None and not self._case_ce_failed:
            try:
                self._case_ce_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            except Exception as exc:  # pragma: no cover
                self._case_ce_failed = True
                logger.warning("Case CE reranker load failed: %s", exc)
                return candidates

        if self._case_ce_model is None:
            return candidates

        head_count = min(top_n, len(candidates))
        if head_count == 0:
            return candidates

        head = candidates[:head_count]
        # Truncate content for CE to reduce cost
        def _short(s: str) -> str:
            s = s or ""
            return s[:400]
        qshort = (query_text or "")[:400]
        # naive in-process cache keyed by (qshort,res.id)
        cache_hits = 0
        to_score: list[tuple[str, str]] = []
        score_indices: list[int] = []
        ce_scores_out: list[float] = [0.0] * head_count
        for idx, res in enumerate(head):
            key = (qshort, res.id)
            if key in self._ce_cache:
                cache_hits += 1
                ce_scores_out[idx] = self._ce_cache[key]
            else:
                to_score.append((qshort, _short(res.content or "")))
                score_indices.append(idx)
        try:
            ce_scores = []
            if to_score:
                ce_scores = list(self._case_ce_model.predict(to_score, batch_size=16))
        except Exception as exc:  # pragma: no cover
            self._case_ce_failed = True
            logger.warning("Case CE reranker inference failed: %s", exc)
            return candidates

        # fill outputs
        for i, s in zip(score_indices, ce_scores):
            ce_scores_out[i] = float(s)
        updated_head: List[SearchResult] = []
        for res, ce_score in zip(head, ce_scores_out):
            combined = 0.65 * res.similarity_score + 0.35 * ce_score
            updated_head.append(
                replace(
                    res,
                    similarity_score=combined,
                    metadata={**(res.metadata or {}), "ce_score": ce_score},
                )
            )

        # update cache
        for res, ce_score in zip(head, ce_scores_out):
            self._ce_cache[(qshort, res.id)] = ce_score
        self._last_ce_pairs = len(to_score)
        self._last_ce_cache_hits = cache_hits
        tail = candidates[head_count:]
        combined_list = updated_head + tail
        self._case_ce_active = True
        return sorted(combined_list, key=lambda r: r.similarity_score, reverse=True)

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

        filters_sc = {**filters, "court_prefix": filters.get("court_prefix") or "SC:"}

        vector_statutes, keyword_statutes, case_ann_sc, case_bm25_sc = await asyncio.gather(
            self.fetch_statute_ann(query_embedding, filters),
            self.fetch_statute_bm25(query, filters),
            self.fetch_case_ann(query_embedding, filters_sc, 360),
            self.fetch_case_bm25(query, filters_sc, 160),
        )

        lexical_statutes = await self._fetch_statute_sections(filters.get("explicit_sections") or [])
        lexical_cases = await self._fetch_cases_by_title(
            filters.get("case_mentions") or [],
            limit=min(self.max_case_results, 48),
        )
        # citation resolver (very light): find citation-like tokens in query and include hits
        citation_hints = self._extract_citation_hints(query)
        citation_cases: List[SearchResult] = []
        if citation_hints:
            try:
                db_manager = await get_db_manager()
                rows = []
                for hint in citation_hints[:4]:
                    sql = (
                        "SELECT id, doc_id, case_title, decision_date, para_range, SUBSTRING(text,1,400) AS text, tokens, source_path, \"order\" "
                        "FROM judgment_chunks WHERE lower(citation_strings::text) LIKE $1 ORDER BY doc_id, \"order\" LIMIT 8"
                    )
                    rows += await db_manager.execute_query(sql, f"%{hint.lower()}%")
                seen = set()
                for row in rows:
                    if row["id"] in seen:
                        continue
                    seen.add(row["id"])
                    citation_cases.append(
                        SearchResult(
                            id=row["id"],
                            similarity_score=1.0,
                            content=row["text"],
                            metadata={
                                "doc_id": row["doc_id"],
                                "case_title": row["case_title"],
                                "decision_date": row["decision_date"].isoformat() if row["decision_date"] else None,
                                "para_range": row["para_range"],
                                "tokens": row["tokens"],
                                "source_path": row["source_path"],
                                "citation_resolver": True,
                            },
                            source_type="case",
                        )
                    )
            except Exception:
                citation_cases = []
        doc_case_matches = await self._fetch_cases_by_ids(
            query,
            filters.get("explicit_case_ids") or [],
            limit_per_doc=max(case_k, 6),
            decision_date_to=filters.get("decision_date_to"),
        )

        vector_statutes_all = vector_statutes + lexical_statutes
        guessed_sections = filters.get("section_guesses") or []
        final_statutes = self._combine_candidates(
            vector_statutes_all,
            keyword_statutes,
            source_type="statute",
            top_k=statute_k,
            guessed_sections=guessed_sections,
        )

        vector_cases_all = case_ann_sc + lexical_cases + citation_cases + doc_case_matches
        final_cases = self._combine_candidates(
            vector_cases_all,
            case_bm25_sc,
            source_type="case",
            top_k=case_k,
            query_text=query,
        )

        if len(final_cases) < case_k:
            fallback_filters = {**filters, "court_prefix": None}
            case_ann_all, case_bm25_all = await asyncio.gather(
                self.fetch_case_ann(query_embedding, fallback_filters, 360),
                self.fetch_case_bm25(query, fallback_filters, 160),
            )
            vector_cases_union = case_ann_all + lexical_cases + doc_case_matches
            keyword_cases_union = case_bm25_sc + case_bm25_all
            final_cases = self._combine_candidates(
                vector_cases_union,
                keyword_cases_union,
                source_type="case",
                top_k=case_k,
                query_text=query,
            )

        await self.hydrate_full_text(final_statutes, final_cases)
        if self._case_ce_active:
            logger.info(
                "CE_applied=%d CE_cache_hits=%d",
                getattr(self, "_last_ce_pairs", 0),
                getattr(self, "_last_ce_cache_hits", 0),
            )
        
        return SearchResults(
            statutes=final_statutes,
            cases=final_cases,
            total_retrieved=len(final_statutes) + len(final_cases),
            processing_time=0.0,
        )

    @staticmethod
    def _extract_citation_hints(query: str) -> List[str]:
        txt = (query or "").lower()
        hints: List[str] = []
        # broader patterns: SCC, SCC Online, AIR, SCALE, CrLJ, year tokens
        patterns = [
            r"\b\d{4}\s*scc\b",
            r"\b\d{4}\s*scc\s*online\b",
            r"\bair\s*\d{4}\b",
            r"\bscale\b",
            r"\bcrlj\b",
        ]
        for pat in patterns:
            hints.extend(re.findall(pat, txt))
        # also capture loose year tokens
        years = re.findall(r"\b\d{4}\b", txt)
        hints.extend(years[:2])
        # dedupe
        seen = set(); out = []
        for h in hints:
            if h and h not in seen:
                out.append(h)
                seen.add(h)
        return out

    @staticmethod
    def _extract_statute_markers(query: str) -> List[str]:
        txt = (query or "").lower()
        markers: List[str] = []
        # Common Indian markers: section numbers, 482, 65b, articles
        for pat in [
            r"section\s*\d+[a-z]?",
            r"\b482\b",
            r"\b65b\b",
            r"article\s*\d+",
        ]:
            markers.extend(re.findall(pat, txt))
        # normalize spaces
        return [" ".join(m.split()) for m in markers if m]


hybrid_search_engine: Optional[HybridSearchEngine] = None


async def get_hybrid_search_engine() -> HybridSearchEngine:
    global hybrid_search_engine
    if hybrid_search_engine is None:
        hybrid_search_engine = HybridSearchEngine()
    return hybrid_search_engine


