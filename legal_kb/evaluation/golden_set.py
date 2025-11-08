"""
Golden set builder for evaluation harness.

This script scans the real chunk outputs for the Bharatiya Nyaya Sanhita (BNS)
and the 2020 Supreme Court judgments to assemble an evaluation dataset made of
authentic statute and case IDs.  Run it whenever the chunk corpus is refreshed
to regenerate `golden_set.json`.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BNS_CHUNKS_PATH = PROJECT_ROOT / "out" / "chunks" / "BNS" / "BNS_2023.jsonl"
CASE_CHUNKS_DIR = PROJECT_ROOT / "out" / "chunks" / "2020"
OUTPUT_PATH = Path(__file__).resolve().parent / "golden_set.json"

# We ensure broad doctrinal coverage with statute-heavy queries for offences and
# procedure, plus targeted case questions for bail, Article 14/21, electronic
# evidence, and other live issues.
CASE_KEYWORDS: List[Tuple[str, str]] = [
    ("anticipatory bail", "anticipatory bail safeguards"),
    ("regular bail", "regular bail principles"),
    ("interim bail", "interim bail conditions"),
    ("default bail", "default bail rights under the Code"),
    ("electronic evidence", "admissibility of electronic evidence"),
    ("digital evidence", "treatment of digital evidence"),
    ("cyber crime", "investigation of cyber offences"),
    ("money laundering", "PMLA compliance obligations"),
    ("Article 14", "Article 14 equality guarantee"),
    ("Article 21", "Article 21 protection of life and personal liberty"),
    ("Article 19", "Article 19 freedoms"),
    ("Article 32", "Article 32 writ jurisdiction"),
    ("Article 136", "Article 136 special leave jurisdiction"),
    ("Article 141", "Article 141 binding precedent"),
    ("Article 142", "Article 142 complete justice power"),
    ("Article 226", "Article 226 high court writ power"),
    ("Article 300A", "Article 300A property rights"),
    ("natural justice", "principles of natural justice"),
    ("domestic violence", "domestic violence safeguards"),
    ("dowry harassment", "dowry harassment prosecution"),
    ("sexual harassment", "sexual harassment at workplace"),
    ("rape", "rape sentencing principles"),
    ("outraging modesty", "outraging modesty standard"),
    ("acid attack", "acid attack compensation"),
    ("organised crime", "organised crime legislation"),
    ("economic offences", "economic offence bail considerations"),
    ("juvenile justice", "juvenile justice interpretation"),
    ("juvenile in conflict with law", "juvenile in conflict jurisprudence"),
    ("habeas corpus", "habeas corpus remedy"),
    ("custodial violence", "custodial violence safeguards"),
    ("whistleblower", "whistleblower protections"),
    ("electoral disqualification", "electoral disqualification rules"),
    ("environmental clearance", "environmental clearance review"),
    ("forest conservation", "forest conservation compliance"),
    ("tax evasion", "tax evasion penalties"),
    ("gst", "GST liability dispute"),
    ("transfer pricing", "transfer pricing adjustments"),
    ("insolvency", "IBC resolution principles"),
    ("arbitration", "arbitration enforcement"),
    ("specific performance", "specific performance relief"),
    ("maintenance", "maintenance rights under criminal law"),
    ("guardianship", "child custody and guardianship"),
    ("medical negligence", "medical negligence standard"),
    ("insurance claim", "insurance claim repudiation"),
    ("motor accident", "motor accident compensation"),
    ("contempt of court", "contempt jurisdiction"),
    ("court fees", "court fee computation"),
    ("limitation", "limitation period computation"),
    ("res judicata", "res judicata application"),
    ("stare decisis", "stare decisis doctrine"),
    ("per incuriam", "per incuriam ruling"),
    ("locus standi", "locus standi requirements"),
]


@dataclass
class GoldenEntry:
    question: str
    expected_statutes: List[str]
    expected_cases: List[str]


def natural_key(value: str) -> List[object]:
    """Return a list usable for natural sorting of alphanumeric section numbers."""
    return [
        int(chunk) if chunk.isdigit() else chunk.lower()
        for chunk in re.split(r"(\d+)", value)
        if chunk
    ]


def extract_topic(raw: str) -> str:
    """Reduce a section title or text snippet to a short topic phrase."""
    cleaned = (
        raw.replace("\n", " ")
        .replace("—", " ")
        .replace("�", " ")
        .replace("–", " ")
    )
    cleaned = re.sub(r"[“”\"'`’]", "", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "its subject matter"
    # Remove leading numbering like "(1)" or "Section 101."
    cleaned = re.sub(r"^(section\s+\d+[A-Z]?\s*[:\-]?\s*)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\(?\d+\)?\s*", "", cleaned)
    words = cleaned.split()
    topic_words = words[:14] if len(words) >= 14 else words
    topic = " ".join(topic_words).strip().lower()
    return topic or "its subject matter"


def load_bns_sections(path: Path) -> Dict[str, Dict[str, object]]:
    sections: Dict[str, Dict[str, object]] = defaultdict(lambda: {"title": "", "ids": [], "text": ""})
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            entry = json.loads(line)
            if entry.get("type") != "statute_unit":
                continue
            if entry.get("unit_type") != "Section":
                continue
            sec_no = str(entry.get("section_no")).strip()
            if not sec_no:
                continue
            sections[sec_no]["ids"].append(entry["id"])
            if not sections[sec_no]["title"] and entry.get("title"):
                sections[sec_no]["title"] = entry["title"]
            if not sections[sec_no]["text"]:
                sections[sec_no]["text"] = entry.get("text", "")
    return sections


def build_statute_entries(sections: Dict[str, Dict[str, object]], limit: Optional[int] = None) -> List[GoldenEntry]:
    entries: List[GoldenEntry] = []
    for sec_no, info in sorted(sections.items(), key=lambda item: natural_key(item[0])):
        title_or_text = info["title"] or info["text"]
        if not title_or_text:
            continue
        topic = extract_topic(title_or_text)
        question = (
            f"What does Section {sec_no} of the Bharatiya Nyaya Sanhita, 2023 provide about {topic}?"
        )
        unique_ids = sorted(set(info["ids"]))
        if not unique_ids:
            continue
        entries.append(GoldenEntry(question=question, expected_statutes=unique_ids, expected_cases=[]))
        if limit and len(entries) >= limit:
            break
    return entries


def iter_case_chunks() -> Iterable[Tuple[str, Dict[str, object]]]:
    for path in sorted(CASE_CHUNKS_DIR.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                entry = json.loads(line)
                if entry.get("type") != "judgment_window":
                    continue
                yield path.name, entry


def find_case_chunk(keyword: str, used_ids: set[str]) -> Optional[Dict[str, object]]:
    kw = keyword.lower()
    for _, entry in iter_case_chunks():
        if entry["id"] in used_ids:
            continue
        text = entry.get("text", "").lower()
        if kw in text:
            return entry
    return None


def sanitise_case_title(title: str) -> str:
    lines = [segment.strip() for segment in title.replace("\r", "").split("\n") if segment.strip()]
    filtered = [line for line in lines if len(line) > 1]
    clean = re.sub(r"\s+", " ", " ".join(filtered)).strip()
    return clean if clean else "the referenced case"


def build_case_entries(keywords: List[Tuple[str, str]]) -> List[GoldenEntry]:
    entries: List[GoldenEntry] = []
    used_ids: set[str] = set()
    for keyword, topic in keywords:
        match = find_case_chunk(keyword, used_ids)
        if not match:
            continue
        case_title = match.get("case_title") or match.get("doc_id", "")
        clean_title = sanitise_case_title(case_title)
        question = f"What did the Supreme Court hold on {topic} in {clean_title}?"
        entries.append(GoldenEntry(question=question, expected_statutes=[], expected_cases=[match["id"]]))
        used_ids.add(match["id"])
    return entries


def ensure_keyword_coverage(entries: Iterable[GoldenEntry], keywords: Iterable[str]) -> Dict[str, int]:
    coverage_counts: Dict[str, int] = {kw: 0 for kw in keywords}
    for entry in entries:
        text = entry.question.lower()
        for keyword in keywords:
            if keyword in text:
                coverage_counts[keyword] += 1
    return coverage_counts


def main() -> None:
    if not BNS_CHUNKS_PATH.exists():
        raise FileNotFoundError(f"BNS chunk file not found at {BNS_CHUNKS_PATH}")
    if not CASE_CHUNKS_DIR.exists():
        raise FileNotFoundError(f"Case chunk directory not found at {CASE_CHUNKS_DIR}")

    sections = load_bns_sections(BNS_CHUNKS_PATH)
    statute_entries = build_statute_entries(sections, limit=200)
    case_entries = build_case_entries(CASE_KEYWORDS)

    total_entries = statute_entries + case_entries
    if len(total_entries) < 150:
        raise RuntimeError(f"Golden set too small: only {len(total_entries)} entries generated.")

    # Persist dataset.
    payload = [
        {
            "question": entry.question,
            "expected_statutes": entry.expected_statutes,
            "expected_cases": entry.expected_cases,
        }
        for entry in total_entries
    ]
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    statute_keywords = ["punishment", "offence", "bail", "electronic", "cyber"]
    coverage = ensure_keyword_coverage(total_entries, statute_keywords)

    print(f"Golden set written to {OUTPUT_PATH}")
    print(f"Statute entries: {len(statute_entries)} | Case entries: {len(case_entries)} | Total: {len(total_entries)}")
    print("Keyword coverage (statute questions):")
    for keyword, count in coverage.items():
        print(f"  - {keyword}: {count}")


if __name__ == "__main__":
    main()
