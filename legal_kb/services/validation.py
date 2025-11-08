"""
Validation firewall for lawyer-grade outputs:
- quote-span verification (every quote must appear verbatim in sources)
- statute "as-on" validity enforcement
- citation normalization helpers
- confidence scoring
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class QuoteSpan:
    quote: str
    source_id: str
    para_range: Optional[str]
    found: bool


def _iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def normalize_citation(meta: Dict) -> Dict:
    """Normalize case citation metadata into a canonical record.
    Expects metadata from SearchResult.metadata.
    """
    out = {
        "party": meta.get("case_title"),
        "court": "SC" if str(meta.get("doc_id", "")).startswith("SC:") else None,
        "decision_date": meta.get("decision_date"),
        "reporter": None,  # keep raw strings separate
        "citations": meta.get("citation_strings") or [],
        "para_range": meta.get("para_range"),
    }
    # Best-effort reporter hint
    for c in out["citations"]:
        if "SCC" in c or "SCR" in c or "AIR" in c:
            out["reporter"] = c
            break
    return out


def enforce_as_on(statute_meta: Dict, as_on: Optional[str]) -> bool:
    """Return True if statute chunk is valid on the given as_on date."""
    if not as_on:
        return True
    start = _iso_date(statute_meta.get("effective_from"))
    end = _iso_date(statute_meta.get("effective_to"))
    as_on_date = _iso_date(as_on)
    if as_on_date is None:
        return True
    if start and as_on_date < start:
        return False
    if end and as_on_date >= end:
        return False
    return True


def find_quote_in_text(quote: str, text: str) -> bool:
    q = (quote or "").strip()
    if not q or not text:
        return False
    # Normalize whitespace for robust matching
    q_norm = re.sub(r"\s+", " ", q)
    t_norm = re.sub(r"\s+", " ", text)
    return q_norm in t_norm


def verify_quotes(quotes: List[Tuple[str, str]], source_texts: Dict[str, str], source_meta: Dict[str, Dict]) -> List[QuoteSpan]:
    """Verify that each (quote, source_id) pair appears verbatim in that source's text.
    - quotes: list of (quote_text, source_id)
    - source_texts: id -> full text content
    - source_meta: id -> metadata dict (may include para_range)
    Returns list with found flags and para info for downstream rendering.
    """
    out: List[QuoteSpan] = []
    for quote, sid in quotes:
        text = source_texts.get(sid) or ""
        found = find_quote_in_text(quote, text)
        pr = (source_meta.get(sid) or {}).get("para_range")
        out.append(QuoteSpan(quote=quote, source_id=sid, para_range=pr, found=found))
    return out


def compute_confidence(coverage: float, quote_pass_rate: float, metadata_match: float) -> float:
    """Simple multiplicative confidence aggregator (0..1)."""
    coverage = max(0.0, min(1.0, coverage))
    quote_pass_rate = max(0.0, min(1.0, quote_pass_rate))
    metadata_match = max(0.0, min(1.0, metadata_match))
    return round(coverage * quote_pass_rate * metadata_match, 3)


def refusal_from_confidence(conf: float, min_conf: float = 0.45) -> Optional[str]:
    return None if conf >= min_conf else "Insufficient verified evidence to produce a filing-ready answer."

