"""
Data models for Advanced Legal KB+RAG System
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date
from enum import Enum

class DocumentType(Enum):
    STATUTE_UNIT = "statute_unit"
    JUDGMENT_WINDOW = "judgment_window"

class SubunitType(Enum):
    SECTION = "Section"
    SUB = "Sub"
    ILLUSTRATION = "Illustration"
    EXPLANATION = "Explanation"
    PROVISO = "Proviso"

class JudgmentSection(Enum):
    ANALYSIS = "Analysis"
    FACTS = "Facts"
    ISSUE = "Issue"
    HELD = "Held"
    ORDER = "Order"
    CITATIONS = "Citations"
    HEADNOTE = "Headnote"

class RelationType(Enum):
    STATUTE_TO_STATUTE = "statute_to_statute"
    JUDGMENT_TO_STATUTE = "judgment_to_statute"
    JUDGMENT_TO_JUDGMENT = "judgment_to_judgment"

@dataclass
class StatuteChunk:
    """Model for statute section chunks"""
    id: str                   # BNS:2023:chunk:0001
    doc_id: str               # BNS:2023
    year: int                 # 2023
    section_no: str           # 147
    text: str                 # Verbatim legal text
    sha256: str               # Content hash
    type: DocumentType = DocumentType.STATUTE_UNIT
    order: float = 0.0
    act: str = "BNS"
    unit_type: SubunitType = SubunitType.SECTION
    title: Optional[str] = None
    tokens: int = 0
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    source_path: Optional[str] = None
    embedding: Optional[List[float]] = None  # 1536-dim vector
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class JudgmentChunk:
    """Model for judgment paragraph chunks"""
    id: str                 # SC:2020:2020_1_xxx:chunk:0001
    doc_id: str
    text: str
    sha256: str
    case_title: str
    type: DocumentType = DocumentType.JUDGMENT_WINDOW
    order: int = 0
    tokens: int = 0
    overlap_tokens: int = 0
    decision_date: Optional[date] = None
    bench: List[str] = field(default_factory=list)
    citation_strings: List[str] = field(default_factory=list)
    para_range: Optional[str] = None
    source_path: Optional[str] = None
    embedding: Optional[List[float]] = None  # 1536-dim vector
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class CrossReference:
    """Model for cross-reference relationships"""
    src_id: str  # Source document ID
    dst_id: str  # Target document ID
    rel_type: RelationType
    weight: float  # Relationship strength (0.0-1.0)
    context: Optional[str]  # Surrounding text context
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class LegalSynonym:
    """Model for legal terminology synonyms"""
    term: str
    synonyms: List[str]
    category: str  # procedural, judicial, criminal
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class LegacyMapping:
    """Model for BNS to legacy IPC/CrPC mappings"""
    bns_section: str
    legacy_act: str  # IPC, CrPC, Evidence
    legacy_section: str
    mapping_type: str  # equivalent, partial, related
    notes: Optional[str]
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class QueryAnalysis:
    """Model for analyzed user query"""
    original_query: str
    temporal_context: Optional['TemporalContext']
    expanded_terms: Dict[str, List[str]]
    section_guesses: List[str]
    query_type: str  # factual, comparative, procedural
    legal_terms: List[str]
    offense_keywords: List[str]
    explicit_sections: List[str] = field(default_factory=list)
    case_mentions: List[str] = field(default_factory=list)
    explicit_case_ids: List[str] = field(default_factory=list)

@dataclass
class TemporalContext:
    """Model for temporal query context"""
    as_on_date: date
    date_source: str  # explicit, inferred, default
    confidence: float  # 0.0-1.0

@dataclass
class SearchResult:
    """Model for search result"""
    id: str
    similarity_score: float
    content: str
    metadata: Dict[str, Any]
    source_type: str  # statute, case
    authority_weight: float = 1.0

@dataclass
class SearchResults:
    """Model for combined search results"""
    statutes: List[SearchResult]
    cases: List[SearchResult]
    total_retrieved: int
    processing_time: float

@dataclass
class AssembledContext:
    """Model for assembled LLM context"""
    statute_block: str
    case_block: str
    combined_context: str
    source_ids: List[str]
    token_count: int

@dataclass
class Citation:
    """Model for citation in response"""
    id: str  # Source document ID
    quote_text: str  # Verbatim quote (≤300 chars)
    source_name: str  # Human-readable source name
    confidence_score: float
    citation_type: str  # statute, case

@dataclass
class ClaimVerification:
    """Model for claim verification result"""
    claim: str
    is_supported: bool
    supporting_sources: List[str]
    confidence: float

@dataclass
class CitationVerification:
    """Model for citation verification result"""
    citation_id: str
    exists: bool
    accessible: bool
    quote_match: bool

@dataclass
class VerificationResult:
    """Model for response verification result"""
    claim_verifications: List[ClaimVerification]
    citation_verifications: List[CitationVerification]
    quote_verifications: List['QuoteVerification']
    overall_confidence: float

@dataclass
class QuoteVerification:
    """Model for quote verification result"""
    quote_text: str
    source_id: str
    exact_match: bool
    normalized_match: bool

@dataclass
class RAGResponse:
    """Model for RAG system response"""
    answer: str
    citations: List[Citation]
    query_id: str
    processing_time: float
    token_usage: Dict[str, int]
    verification_result: Optional[VerificationResult]
    as_on_date: date
    confidence_score: float

@dataclass
class ProcessingResult:
    """Model for document processing result"""
    document_id: str
    chunks_created: int
    embeddings_generated: int
    cross_references_found: int
    processing_time: float
    success: bool
    error_message: Optional[str] = None
