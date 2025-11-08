"""
Temporal reasoning and legacy mapping helpers for legal retrieval.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ..models.legal_models import TemporalContext, LegacyMapping

DATE_PATTERNS: Sequence[re.Pattern] = (
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b"),
    re.compile(r"\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
               r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
               r"Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(\d{4})\b"),
)

MONTH_LOOKUP: Dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


class TemporalReasoner:
    """Extracts temporal context from queries and enforces validity."""

    def __init__(self, mapping_path: Optional[Path] = None):
        self.mapping_path = mapping_path or (
            Path(__file__).resolve().parents[2] / "data" / "bns_legacy_mapping.json"
        )
        self._legacy_index: Dict[str, List[LegacyMapping]] = {}
        self._load_legacy_mappings()

    def _load_legacy_mappings(self) -> None:
        if not self.mapping_path.exists():
            return
        with self.mapping_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        index: Dict[str, List[LegacyMapping]] = {}
        for entry in data:
            mapping = LegacyMapping(
                bns_section=entry["bns_section"],
                legacy_act=entry["legacy_act"],
                legacy_section=entry["legacy_section"],
                mapping_type=entry["mapping_type"],
                notes=entry.get("notes"),
            )
            index.setdefault(mapping.bns_section, []).append(mapping)
        self._legacy_index = index

    def extract_context(self, query: str) -> TemporalContext:
        """Derive an as-on date from the natural language query."""
        normalized = query.strip()
        for pattern in DATE_PATTERNS:
            match = pattern.search(normalized)
            if not match:
                continue
            if len(match.groups()) == 3 and pattern is DATE_PATTERNS[0]:
                day, month, year = match.groups()
                return TemporalContext(
                    as_on_date=self._build_date(int(day), int(month), int(year)),
                    date_source="explicit",
                    confidence=0.9,
                )
            if len(match.groups()) == 3 and pattern is DATE_PATTERNS[1]:
                day, month_name, year = match.groups()
                month = MONTH_LOOKUP.get(month_name.lower(), 1)
                return TemporalContext(
                    as_on_date=self._build_date(int(day), month, int(year)),
                    date_source="explicit",
                    confidence=0.9,
                )
            if len(match.groups()) == 1 and pattern is DATE_PATTERNS[2]:
                year = int(match.group(1))
                if 1800 <= year <= 2500:
                    lowered = normalized.lower()
                    if year == 2023 and ("bharatiya nyaya sanhita" in lowered or "bns" in lowered):
                        return TemporalContext(
                            as_on_date=date(2024, 7, 1),
                            date_source="acts_inference",
                            confidence=0.7,
                        )
                    return TemporalContext(
                        as_on_date=date(year, 12, 31),
                        date_source="inferred_year",
                        confidence=0.5,
                    )
        return TemporalContext(
            as_on_date=date.today(),
            date_source="default",
            confidence=0.2,
        )

    @staticmethod
    def _build_date(day: int, month: int, year: int) -> date:
        if year < 100:
            year += 2000 if year < 70 else 1900
        try:
            return date(year, month, day)
        except ValueError:
            return date(year, month, min(day, 28))

    def enforce_temporal_validity(
        self,
        results: List[SearchResult],
        as_on: date,
    ) -> List[SearchResult]:
        """Filter retrieval results by temporal validity."""
        filtered: List[SearchResult] = []
        for result in results:
            metadata = result.metadata or {}
            if result.source_type == "statute":
                effective_from = metadata.get("effective_from")
                effective_to = metadata.get("effective_to")
                if not self._is_statute_active(as_on, effective_from, effective_to):
                    continue
            if result.source_type == "case":
                decision_date = metadata.get("decision_date")
                if decision_date and not self._is_case_applicable(as_on, decision_date):
                    continue
            filtered.append(result)
        return filtered

    @staticmethod
    def _is_statute_active(
        as_on: date,
        effective_from: Optional[str],
        effective_to: Optional[str],
    ) -> bool:
        try:
            if effective_from:
                start = date.fromisoformat(effective_from)
                if start > as_on:
                    return False
        except ValueError:
            pass
        try:
            if effective_to:
                end = date.fromisoformat(effective_to)
                if end <= as_on:
                    return False
        except ValueError:
            pass
        return True

    @staticmethod
    def _is_case_applicable(as_on: date, decision_date: str) -> bool:
        try:
            decided = date.fromisoformat(decision_date)
            return decided <= as_on
        except ValueError:
            return True

    def map_to_legacy(self, statute_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        section_no = statute_metadata.get("section_no")
        if not section_no:
            return []
        mappings = self._legacy_index.get(str(section_no), [])
        return [asdict(mapping) for mapping in mappings]
