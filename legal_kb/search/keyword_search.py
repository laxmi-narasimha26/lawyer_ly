"""
Sparse keyword/BM25 search for legal documents.
"""
import re
import logging
from typing import List, Optional
from datetime import date

from ..database.connection import get_db_manager
from ..models.legal_models import SearchResult
from ..services.query_analysis_service import LEGAL_SYNONYMS

logger = logging.getLogger(__name__)

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _normalize_phrase(term: str) -> str:
    if " " not in term:
        return term
    parts = [TOKEN_PATTERN.sub("", token) or token for token in term.split()]
    parts = [p for p in parts if p]
    return "<->".join(parts) if parts else term


class KeywordSearchEngine:
    def __init__(self):
        self.default_statute_k = 20
        self.default_case_k = 40

    def _extract_tokens(self, query: str) -> List[str]:
        tokens = [m.group(0) for m in TOKEN_PATTERN.finditer((query or "").lower())]
        seen = set(); out = []
        for token in tokens:
            if token and token not in seen:
                out.append(token)
                seen.add(token)
        return out

    def _build_tsquery(self, query: str, include_synonyms: bool = True) -> Optional[str]:
        tokens = self._extract_tokens(query)
        if not tokens:
            return None
        parts: List[str] = []
        for token in tokens:
            variants = [token]
            if include_synonyms:
                variants.extend(LEGAL_SYNONYMS.get(token, []))
            seen = set()
            exprs: List[str] = []
            for term in variants:
                cleaned = term.replace("'", " ").replace("-", " ").strip()
                if not cleaned:
                    continue
                normalized = _normalize_phrase(cleaned)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    if "<->" in normalized:
                        exprs.append(f"({normalized})")
                    else:
                        exprs.append(f"{normalized}:*")
            if exprs:
                parts.append("(" + " | ".join(exprs) + ")")
        return " | ".join(parts) if parts else None

    def _extract_case_hints(self, query: str) -> List[str]:
        hints: List[str] = []
        m = re.search(r"\b(.+?)\s+v(?:\.|s\.)\s+(.+?)\b", query or "", re.IGNORECASE)
        if m:
            for group in (1, 2):
                p = re.sub(r"[^A-Za-z0-9 ]+", " ", m.group(group)).strip()
                if p:
                    hints.append(p)
        if re.search(r"\(\d{4}\)\s+\d+\s+SCC", query or "", re.IGNORECASE):
            hints.append("SCC")
        if re.search(r"AIR\s+\d{4}\s+\w+\s+\d+", query or "", re.IGNORECASE):
            hints.append("AIR")
        seen = set(); out = []
        for hint in hints:
            if hint not in seen:
                out.append(hint)
                seen.add(hint)
        return out

    async def search_statutes(
        self,
        query: str,
        k: Optional[int] = None,
        act_filter: Optional[str] = None,
        effective_date: Optional[date] = None,
    ) -> List[SearchResult]:
        qtext = (query or "").strip()
        if not qtext:
            return []
        effective_date = effective_date or date.today()
        limit = k or self.default_statute_k
        sql = """
        WITH q AS (
          SELECT plainto_tsquery('english_unaccent', $1) AS tsq
        )
        SELECT
          id, doc_id, title, section_no, unit_type,
          SUBSTRING(text, 1, 400) AS text,
          tokens, act, source_path,
          ts_rank(tsv, (SELECT tsq FROM q)) AS rank
        FROM statute_chunks
        WHERE tsv @@ (SELECT tsq FROM q)
          AND ($2::text IS NULL OR act = $2)
          AND ($3::date IS NULL OR effective_from IS NULL OR effective_from <= $3)
          AND ($3::date IS NULL OR effective_to IS NULL OR effective_to > $3)
        ORDER BY rank DESC
        LIMIT $4
        """
        try:
            db = await get_db_manager()
            rows = await db.execute_query(sql, qtext, act_filter, effective_date, limit)
            results: List[SearchResult] = []
            for row in rows:
                results.append(
                    SearchResult(
                        id=row['id'],
                        similarity_score=float(row['rank']),
                        content=row['text'],
                        metadata={
                            'doc_id': row['doc_id'],
                            'title': row['title'],
                            'section_no': row['section_no'],
                            'unit_type': row['unit_type'],
                            'tokens': row['tokens'],
                            'act': row['act'],
                            'canonical_id': f"{row['doc_id']}:Sec:{row['section_no']}",
                            'source_path': row['source_path'],
                            'tsquery': qtext,
                        },
                        source_type='statute',
                    )
                )
            return results
        except Exception as exc:
            logger.error("Keyword statute search failed: %s", exc)
            return []

    async def search_cases(
        self,
        query: str,
        k: Optional[int] = None,
        doc_prefix: Optional[str] = None,
        decision_date_to: Optional[date] = None,
    ) -> List[SearchResult]:
        qtext = (query or "").strip()
        if not qtext:
            return []
        hints = self._extract_case_hints(qtext)
        party1 = f"%{hints[0]}%" if len(hints) > 0 else None
        party2 = f"%{hints[1]}%" if len(hints) > 1 else None
        cit_hint = "%SCC%" if any("scc" in h.lower() for h in hints) else None
        decision_date_to = decision_date_to or date.today()
        limit_total = k or 100
        per_query_limit = min(80, limit_total)
        sql_strict = """
        WITH q AS (
          SELECT plainto_tsquery('english_unaccent', $1) AS tsq
        )
        SELECT id, doc_id, case_title, decision_date, para_range,
               SUBSTRING(text, 1, 400) AS text, tokens, source_path,
               ts_rank(tsv, (SELECT tsq FROM q))
                 + (CASE WHEN $5::text IS NOT NULL AND lower(case_title) LIKE $5 THEN 0.05 ELSE 0 END)
                 + (CASE WHEN $6::text IS NOT NULL AND lower(case_title) LIKE $6 THEN 0.05 ELSE 0 END)
                 + (CASE WHEN $7::text IS NOT NULL AND lower(citation_strings::text) LIKE $7 THEN 0.05 ELSE 0 END)
                 AS rank
        FROM judgment_chunks
        WHERE tsv @@ (SELECT tsq FROM q)
          AND ($2::text IS NULL OR doc_id ILIKE $2 || '%')
          AND ($3::date IS NULL OR decision_date IS NULL OR decision_date <= $3)
        ORDER BY rank DESC
        LIMIT $4
        """
        sql_broad = """
        WITH q AS (
          SELECT plainto_tsquery('english_unaccent', $1) AS tsq
        )
        SELECT id, doc_id, case_title, decision_date, para_range,
               SUBSTRING(text, 1, 400) AS text, tokens, source_path,
               ts_rank(tsv, (SELECT tsq FROM q)) AS rank
        FROM judgment_chunks
        WHERE tsv @@ (SELECT tsq FROM q)
          AND ($2::text IS NULL OR doc_id ILIKE $2 || '%')
          AND ($3::date IS NULL OR decision_date IS NULL OR decision_date <= $3)
        ORDER BY rank DESC
        LIMIT $4
        """
        try:
            db = await get_db_manager()
            rows_strict = await db.execute_query(
                sql_strict,
                qtext,
                doc_prefix,
                decision_date_to,
                per_query_limit,
                (party1 or '').lower() if party1 else None,
                (party2 or '').lower() if party2 else None,
                (cit_hint or '').lower() if cit_hint else None,
            )
            rows_broad = await db.execute_query(
                sql_broad, qtext, doc_prefix, decision_date_to, per_query_limit
            )
            # Issue-terms variant using LEGAL_SYNONYMS present in query
            rows_issue = []
            try:
                qlower = qtext.lower()
                issue_terms: List[str] = []
                for term, syns in LEGAL_SYNONYMS.items():
                    if term in qlower:
                        issue_terms.extend(syns)
                issue_terms = list({t for t in issue_terms if t})
                if issue_terms:
                    issue_q = " ".join(issue_terms[:40])
                    rows_issue = await db.execute_query(
                        sql_broad, issue_q, doc_prefix, decision_date_to, 40
                    )
            except Exception:
                rows_issue = []

            seen = set(); rows = []
            for row in rows_strict + rows_broad + rows_issue:
                if row['id'] in seen:
                    continue
                seen.add(row['id'])
                rows.append(row)
            rows = rows[: (k or 160)]
            results: List[SearchResult] = []
            for row in rows:
                results.append(
                    SearchResult(
                        id=row['id'],
                        similarity_score=float(row['rank']),
                        content=row['text'],
                        metadata={
                            'doc_id': row['doc_id'],
                            'case_title': row['case_title'],
                            'decision_date': row['decision_date'].isoformat() if row['decision_date'] else None,
                            'para_range': row['para_range'],
                            'tokens': row['tokens'],
                            'source_path': row['source_path'],
                            'tsquery': qtext,
                        },
                        source_type='case',
                    )
                )
            return results
        except Exception as exc:
            logger.error('Keyword judgment search failed: %s', exc)
            return []


keyword_search_engine: Optional[KeywordSearchEngine] = None


async def get_keyword_search_engine() -> KeywordSearchEngine:
    global keyword_search_engine
    if keyword_search_engine is None:
        keyword_search_engine = KeywordSearchEngine()
    return keyword_search_engine
