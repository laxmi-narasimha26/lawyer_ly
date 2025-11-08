"""
Query analysis utilities for legal-aware retrieval.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from ..models.legal_models import QueryAnalysis, TemporalContext
from .temporal_reasoning import TemporalReasoner


SECTION_PATTERN = re.compile(r"\b(?:section|sec\.?|§)\s*(\d+[a-z\-]*)", re.IGNORECASE)
CASE_DOC_PATTERN = re.compile(r"SC:\d{4}:[A-Z0-9_]+")

LEGAL_SYNONYMS: Dict[str, List[str]] = {
    "bail": [
        "anticipatory bail", "pre-arrest bail", "s 438", "sec 438", "section 438", "crpc 438",
        "regular bail", "interim bail", "default bail", "surety", "custody", "custodial interrogation"
    ],
    "arrest": ["custody", "detention", "apprehend"],
    "remand": ["custody", "judicial remand"],
    "fir": ["first information report", "crime report"],
    "habeas": ["habeas corpus", "illegal detention"],
    "writ": ["mandamus", "certiorari", "prohibition", "quo warranto"],
    "appeal": ["appellate", "challenge", "review"],
    "revision": ["criminal revision", "review petition"],
    "robbery": ["dacoity", "armed theft", "extortion", "snatching"],
    "murder": ["homicide", "culpable homicide"],
    "sexual": ["rape", "sexual assault", "outraging modesty"],
    "negligence": ["rash act", "breach of duty"],
    "cheating": ["fraud", "dishonestly"],
    "evidence": ["testimony", "proof", "material evidence"],
    "contract": ["agreement", "covenant"],
    "jurisdiction": ["competence", "authority"],
    "mens": ["intention", "mens rea"],
    "actus": ["act", "actus reus"],
    "sentence": ["punishment", "imprisonment", "fine"],
    "482": ["section 482", "482 crpc", "quash", "quash fir", "inherent powers"],
    "quash": ["482", "quash fir", "inherent powers"],
    "electronic": ["section 65b", "65-b certificate", "electronic record", "secondary evidence"],
    "article": ["article 14", "article 21", "fundamental rights", "arbitrary", "fair procedure"],
    "procedure": ["remand", "investigation", "cognizable", "non-cognizable", "compounding"],
    "precedent": ["binding precedent", "ratio decidendi", "article 141"],
}

OFFENSE_SECTION_GUESSES: Dict[str, Dict[str, str]] = {
    "robbery": {"canonical_id": "BNS:2023:Sec:147", "section_no": "147"},
    "dacoity": {"canonical_id": "BNS:2023:Sec:149", "section_no": "149"},
    "murder": {"canonical_id": "BNS:2023:Sec:101", "section_no": "101"},
    "homicide": {"canonical_id": "BNS:2023:Sec:103", "section_no": "103"},
    "culpable": {"canonical_id": "BNS:2023:Sec:103", "section_no": "103"},
    "theft": {"canonical_id": "BNS:2023:Sec:303", "section_no": "303"},
    "cheating": {"canonical_id": "BNS:2023:Sec:356", "section_no": "356"},
    "breach of trust": {"canonical_id": "BNS:2023:Sec:357", "section_no": "357"},
    "rape": {"canonical_id": "BNS:2023:Sec:63", "section_no": "63"},
    "sexual assault": {"canonical_id": "BNS:2023:Sec:63", "section_no": "63"},
    "wrongful restraint": {"canonical_id": "BNS:2023:Sec:351", "section_no": "351"},
    "criminal intimidation": {"canonical_id": "BNS:2023:Sec:351", "section_no": "351"},
    "kidnapping": {"canonical_id": "BNS:2023:Sec:133", "section_no": "133"},
    "dowry death": {"canonical_id": "BNS:2023:Sec:111", "section_no": "111"},
}

LEGAL_TERMINOLOGY: Tuple[str, ...] = (
    "fir",
    "charge sheet",
    "bail",
    "anticipatory",
    "non-bailable",
    "cognizable",
    "remand",
    "writ",
    "appeal",
    "revision",
    "jurisdiction",
    "mens rea",
    "actus reus",
    "per incuriam",
    "ratio",
    "obiter",
    "res judicata",
    "estoppel",
)

COMPARATIVE_MARKERS = {"difference", "distinguish", "compare", "versus", "vs", "distinction"}
PROCEDURAL_MARKERS = {"procedure", "process", "steps", "file", "lodge", "bail", "arrest", "fir"}


class QueryAnalysisService:
    """Detects legal signals in natural language user queries."""

    def __init__(self, temporal_reasoner: Optional[TemporalReasoner] = None):
        self.temporal_reasoner = temporal_reasoner or TemporalReasoner()

    def analyze(self, query: str) -> QueryAnalysis:
        temporal_context = self.temporal_reasoner.extract_context(query)
        normalized = query.lower()

        legal_terms = self._extract_terms(normalized)
        offense_keywords = self._extract_offense_terms(normalized)
        expanded_terms = self._expanded_terms(legal_terms | offense_keywords)
        section_guesses = self._guess_sections(offense_keywords)
        explicit_sections = self._extract_sections(query)
        case_mentions = self._extract_case_mentions(query)
        explicit_case_ids = self._extract_case_ids(query)
        query_type = self._classify_query(normalized, legal_terms, offense_keywords)

        return QueryAnalysis(
            original_query=query,
            temporal_context=temporal_context,
            expanded_terms=expanded_terms,
            section_guesses=section_guesses,
            query_type=query_type,
            legal_terms=sorted(legal_terms),
            offense_keywords=sorted(offense_keywords),
            explicit_sections=explicit_sections,
            case_mentions=case_mentions,
            explicit_case_ids=explicit_case_ids,
        )

    def _extract_terms(self, normalized: str) -> set[str]:
        terms: set[str] = set()
        for term in LEGAL_TERMINOLOGY:
            if term in normalized:
                terms.add(term.split()[0])
        for term in LEGAL_SYNONYMS.keys():
            if term in normalized:
                terms.add(term)
        return terms

    def _extract_offense_terms(self, normalized: str) -> set[str]:
        matches: set[str] = set()
        for offense in OFFENSE_SECTION_GUESSES.keys():
            if offense in normalized:
                matches.add(offense)
        return matches

    def _expanded_terms(self, terms: set[str]) -> Dict[str, List[str]]:
        return {term: LEGAL_SYNONYMS[term] for term in terms if term in LEGAL_SYNONYMS}

    def _guess_sections(self, offenses: set[str]) -> List[str]:
        guesses = []
        for offense in offenses:
            data = OFFENSE_SECTION_GUESSES.get(offense)
            if data and data["canonical_id"] not in guesses:
                guesses.append(data["canonical_id"])
        return guesses

    def _extract_sections(self, original_query: str) -> List[str]:
        matches = SECTION_PATTERN.findall(original_query)
        normalized = []
        for match in matches:
            value = match.strip().upper()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    def _extract_case_mentions(self, original_query: str) -> List[str]:
        upper = original_query.upper()
        pattern = re.compile(r"([A-Z][A-Z\s&.'-]+?)\s+V\.?\s+([A-Z][A-Z\s&.'-]+)")
        mentions: List[str] = []
        for match in pattern.finditer(upper):
            left = match.group(1).strip(" ?.,;:")
            right = match.group(2).strip(" ?.,;:")
            for stop in (" IN ", " ON ", " ABOUT ", " REGARDING ", " FOR ", " UNDER "):
                if stop in left:
                    left = left.split(stop)[-1].strip()
            left = " ".join(left.split()[-8:])
            right = " ".join(right.split()[:8])
            if not left or not right:
                continue
            mention = f"{left} v. {right}"
            if mention not in mentions:
                mentions.append(mention)
        return mentions

    def _extract_case_ids(self, original_query: str) -> List[str]:
        matches = CASE_DOC_PATTERN.findall(original_query.upper())
        seen = set()
        ordered: List[str] = []
        for match in matches:
            if match not in seen:
                seen.add(match)
                ordered.append(match)
        return ordered

    def _classify_query(
        self,
        normalized: str,
        legal_terms: set[str],
        offense_keywords: set[str],
    ) -> str:
        tokens = normalized.split()
        if any(marker in normalized for marker in COMPARATIVE_MARKERS):
            return "comparative"
        if any(marker in normalized for marker in PROCEDURAL_MARKERS) and not offense_keywords:
            return "procedural"
        if "difference" in normalized or normalized.startswith("how"):
            return "procedural"
        if offense_keywords or "punishment" in normalized or "sentence" in normalized:
            return "factual"
        if len(tokens) < 4 and not legal_terms:
            return "ambiguous"
        return "factual"

    def build_expanded_query(self, analysis: QueryAnalysis) -> str:
        additions: List[str] = []
        for synonyms in analysis.expanded_terms.values():
            additions.extend(synonyms)
        return " ".join([analysis.original_query, *additions]).strip()

    def generate_clarification(self, analysis: QueryAnalysis) -> Optional[str]:
        if analysis.query_type in {"procedural", "ambiguous"}:
            if not analysis.offense_keywords and not analysis.section_guesses:
                return (
                    "Could you specify the relevant offense or section so I can narrow down the legal provisions?"
                )
        if analysis.query_type == "comparative" and len(analysis.offense_keywords) < 2:
            return "Which two provisions or judgments should I compare?"
        return None

    def should_refuse(self, analysis: QueryAnalysis) -> Optional[str]:
        tokens = analysis.original_query.strip().split()
        if len(tokens) < 3 and not analysis.legal_terms and not analysis.offense_keywords:
            return "I’m not sure which legal issue to address. Please provide more context."
        return None
