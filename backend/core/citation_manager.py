"""
Advanced citation management system for Indian Legal AI Assistant
Handles extraction, verification, and formatting of legal citations
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime

from database import DocumentType
from config import settings

logger = structlog.get_logger(__name__)

@dataclass
class LegalCitation:
    """Structured legal citation"""
    id: str
    text: str
    source_type: DocumentType
    source_name: str
    reference: str
    relevance_score: float
    position_in_response: int
    is_verified: bool = False
    verification_notes: Optional[str] = None

class CitationType(Enum):
    """Types of legal citations"""
    CASE_LAW = "case_law"
    STATUTE = "statute"
    REGULATION = "regulation"
    CONSTITUTIONAL = "constitutional"
    SECONDARY = "secondary"

class CitationManager:
    """
    Production-grade citation management system
    
    Features:
    - Pattern-based citation extraction
    - Indian legal citation format validation
    - Source verification against knowledge base
    - Citation formatting and standardization
    - Relevance scoring and ranking
    """
    
    def __init__(self):
        self.citation_patterns = self._initialize_citation_patterns()
        self.court_hierarchies = self._initialize_court_hierarchies()
        self.citation_formats = self._initialize_citation_formats()
        
        logger.info("Citation manager initialized with Indian legal patterns")
    
    async def extract_citations(
        self,
        response_text: str,
        source_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract and verify citations from AI response
        
        Args:
            response_text: Generated response text
            source_chunks: Source chunks used for generation
            
        Returns:
            List of verified citations with metadata
        """
        try:
            # Extract citation markers from response
            citation_markers = self._extract_citation_markers(response_text)
            
            # Map markers to source chunks
            mapped_citations = self._map_citations_to_sources(citation_markers, source_chunks)
            
            # Format citations according to Indian legal conventions
            formatted_citations = []
            for citation in mapped_citations:
                formatted_citation = await self._format_citation(citation)
                if formatted_citation:
                    formatted_citations.append(formatted_citation)
            
            # Verify citations against sources
            verified_citations = await self._verify_citations(formatted_citations, source_chunks)
            
            # Rank citations by relevance
            ranked_citations = self._rank_citations(verified_citations)
            
            logger.info(
                "Citations extracted and processed",
                total_citations=len(ranked_citations),
                verified_count=sum(1 for c in ranked_citations if c.get('is_verified', False))
            )
            
            return ranked_citations
            
        except Exception as e:
            logger.error("Citation extraction failed", error=str(e), exc_info=True)
            return []
    
    def _extract_citation_markers(self, text: str) -> List[Dict[str, Any]]:
        """Extract citation markers like [Doc1], [1], etc. from text"""
        markers = []
        
        # Pattern for [Doc1], [Doc2] format
        doc_pattern = r'\[Doc(\d+)\]'
        doc_matches = re.finditer(doc_pattern, text)
        
        for match in doc_matches:
            markers.append({
                'marker': match.group(0),
                'doc_number': int(match.group(1)),
                'start_pos': match.start(),
                'end_pos': match.end(),
                'type': 'doc_reference'
            })
        
        # Pattern for [1], [2] format
        num_pattern = r'\[(\d+)\]'
        num_matches = re.finditer(num_pattern, text)
        
        for match in num_matches:
            # Skip if already captured as doc reference
            if not any(m['start_pos'] <= match.start() <= m['end_pos'] for m in markers):
                markers.append({
                    'marker': match.group(0),
                    'doc_number': int(match.group(1)),
                    'start_pos': match.start(),
                    'end_pos': match.end(),
                    'type': 'numeric_reference'
                })
        
        # Sort by position in text
        markers.sort(key=lambda x: x['start_pos'])
        
        return markers
    
    def _map_citations_to_sources(
        self,
        citation_markers: List[Dict[str, Any]],
        source_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Map citation markers to actual source chunks"""
        mapped_citations = []
        
        for marker in citation_markers:
            doc_number = marker['doc_number']
            
            # Find corresponding source chunk (1-indexed)
            if 1 <= doc_number <= len(source_chunks):
                source_chunk = source_chunks[doc_number - 1]
                
                mapped_citations.append({
                    'marker': marker['marker'],
                    'position': marker['start_pos'],
                    'source_chunk': source_chunk,
                    'chunk_id': source_chunk.get('id'),
                    'source_name': source_chunk.get('source_name', 'Unknown'),
                    'source_type': source_chunk.get('source_type', 'unknown'),
                    'text_snippet': source_chunk.get('text', '')[:200] + "...",
                    'relevance_score': source_chunk.get('relevance_score', 0.0)
                })
        
        return mapped_citations
    
    async def _format_citation(self, citation_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Format citation according to Indian legal conventions"""
        source_type = citation_data.get('source_type', '').lower()
        source_chunk = citation_data.get('source_chunk', {})
        metadata = source_chunk.get('metadata', {})
        
        try:
            if source_type == 'case_law':
                formatted_ref = self._format_case_citation(source_chunk, metadata)
            elif source_type == 'statute':
                formatted_ref = self._format_statute_citation(source_chunk, metadata)
            elif source_type == 'regulation':
                formatted_ref = self._format_regulation_citation(source_chunk, metadata)
            else:
                formatted_ref = self._format_generic_citation(source_chunk, metadata)
            
            return {
                'id': citation_data.get('chunk_id', ''),
                'marker': citation_data.get('marker', ''),
                'source_name': citation_data.get('source_name', ''),
                'source_type': source_type,
                'formatted_reference': formatted_ref,
                'text_snippet': citation_data.get('text_snippet', ''),
                'relevance_score': citation_data.get('relevance_score', 0.0),
                'position_in_response': citation_data.get('position', 0),
                'is_verified': False,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.warning("Citation formatting failed", error=str(e), source_type=source_type)
            return None
    
    def _format_case_citation(self, source_chunk: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """Format case law citation in Indian legal format"""
        # Standard format: Case Name, Year Court Citation
        case_name = metadata.get('case_name') or source_chunk.get('source_name', 'Unknown Case')
        year = metadata.get('year', '')
        court = metadata.get('court', '')
        citation = metadata.get('citation', '')
        
        # Clean case name
        case_name = self._clean_case_name(case_name)
        
        # Format court name
        court = self._standardize_court_name(court)
        
        if year and court and citation:
            return f"{case_name}, {year} {court} {citation}"
        elif year and court:
            return f"{case_name}, {year} {court}"
        elif year:
            return f"{case_name} ({year})"
        else:
            return case_name
    
    def _format_statute_citation(self, source_chunk: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """Format statute citation in Indian legal format"""
        # Standard format: Act Name, Year, Section X
        act_name = metadata.get('act_name') or source_chunk.get('source_name', 'Unknown Act')
        year = metadata.get('year', '')
        section = metadata.get('section') or source_chunk.get('section_number', '')
        
        if section:
            if year:
                return f"{act_name}, {year}, Section {section}"
            else:
                return f"{act_name}, Section {section}"
        elif year:
            return f"{act_name}, {year}"
        else:
            return act_name
    
    def _format_regulation_citation(self, source_chunk: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """Format regulation citation"""
        regulation_name = metadata.get('regulation_name') or source_chunk.get('source_name', 'Unknown Regulation')
        notification_no = metadata.get('notification_number', '')
        date = metadata.get('date', '')
        
        if notification_no and date:
            return f"{regulation_name}, Notification No. {notification_no}, dated {date}"
        elif date:
            return f"{regulation_name}, dated {date}"
        else:
            return regulation_name
    
    def _format_generic_citation(self, source_chunk: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """Format generic document citation"""
        source_name = source_chunk.get('source_name', 'Unknown Document')
        date = metadata.get('date', '')
        
        if date:
            return f"{source_name} ({date})"
        else:
            return source_name
    
    def _clean_case_name(self, case_name: str) -> str:
        """Clean and standardize case names"""
        # Remove common prefixes/suffixes
        case_name = re.sub(r'^(In\s+re:?\s*|Re:?\s*)', '', case_name, flags=re.IGNORECASE)
        case_name = re.sub(r'\s*v\.?\s*', ' v. ', case_name)  # Standardize "versus"
        case_name = re.sub(r'\s+', ' ', case_name).strip()  # Clean whitespace
        
        return case_name
    
    def _standardize_court_name(self, court: str) -> str:
        """Standardize court names to common abbreviations"""
        court_mappings = {
            'supreme court of india': 'SC',
            'supreme court': 'SC',
            'delhi high court': 'Del HC',
            'bombay high court': 'Bom HC',
            'calcutta high court': 'Cal HC',
            'madras high court': 'Mad HC',
            'karnataka high court': 'Kar HC',
            'gujarat high court': 'Guj HC',
            'rajasthan high court': 'Raj HC',
            'punjab and haryana high court': 'P&H HC',
            'allahabad high court': 'All HC'
        }
        
        court_lower = court.lower()
        return court_mappings.get(court_lower, court)
    
    async def _verify_citations(
        self,
        citations: List[Dict[str, Any]],
        source_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Verify citations against source chunks"""
        verified_citations = []
        
        for citation in citations:
            if not citation:
                continue
                
            # Basic verification - check if citation matches source
            is_verified = self._verify_citation_against_source(citation, source_chunks)
            
            citation['is_verified'] = is_verified
            
            if not is_verified:
                citation['verification_notes'] = "Citation could not be verified against provided sources"
            
            verified_citations.append(citation)
        
        return verified_citations
    
    def _verify_citation_against_source(
        self,
        citation: Dict[str, Any],
        source_chunks: List[Dict[str, Any]]
    ) -> bool:
        """Verify individual citation against source chunks"""
        chunk_id = citation.get('id')
        
        # Find matching source chunk
        matching_chunk = None
        for chunk in source_chunks:
            if chunk.get('id') == chunk_id:
                matching_chunk = chunk
                break
        
        if not matching_chunk:
            return False
        
        # Verify source type matches
        if citation.get('source_type') != matching_chunk.get('source_type'):
            return False
        
        # Verify source name similarity
        citation_source = citation.get('source_name', '').lower()
        chunk_source = matching_chunk.get('source_name', '').lower()
        
        # Simple similarity check
        if citation_source in chunk_source or chunk_source in citation_source:
            return True
        
        return False
    
    def _rank_citations(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank citations by relevance and quality"""
        def citation_score(citation):
            score = citation.get('relevance_score', 0.0)
            
            # Boost verified citations
            if citation.get('is_verified', False):
                score += 0.2
            
            # Boost primary sources
            source_type = citation.get('source_type', '')
            if source_type in ['case_law', 'statute']:
                score += 0.1
            
            # Boost citations with complete metadata
            if citation.get('formatted_reference', ''):
                score += 0.05
            
            return score
        
        # Sort by score (descending)
        citations.sort(key=citation_score, reverse=True)
        
        return citations
    
    def _initialize_citation_patterns(self) -> Dict[str, str]:
        """Initialize regex patterns for citation recognition"""
        return {
            'case_citation': r'\b\d{4}\s+\w+\s+\d+\b|\b\[\d{4}\]\s+\w+\s+\d+\b',
            'section_reference': r'\bSection\s+\d+[A-Z]?\b|\bArt(?:icle)?\s+\d+[A-Z]?\b',
            'act_reference': r'\b\w+\s+Act,?\s+\d{4}\b',
            'court_name': r'\bSupreme\s+Court\b|\b\w+\s+High\s+Court\b',
            'year_pattern': r'\b(19|20)\d{2}\b'
        }
    
    def _initialize_court_hierarchies(self) -> Dict[str, int]:
        """Initialize court hierarchy for precedent value"""
        return {
            'Supreme Court': 1,
            'High Court': 2,
            'District Court': 3,
            'Tribunal': 4,
            'Commission': 5
        }
    
    def _initialize_citation_formats(self) -> Dict[str, str]:
        """Initialize standard citation formats"""
        return {
            'case_law': "{case_name}, {year} {court} {citation}",
            'statute': "{act_name}, {year}, Section {section}",
            'regulation': "{regulation_name}, Notification No. {notification_no}, dated {date}",
            'constitutional': "Constitution of India, Article {article}",
            'secondary': "{title} by {author} ({year})"
        }
    
    def get_citation_statistics(self, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about citations"""
        if not citations:
            return {
                'total_citations': 0,
                'verified_citations': 0,
                'verification_rate': 0.0,
                'citations_by_type': {}
            }
        
        verified_count = sum(1 for c in citations if c.get('is_verified', False))
        
        # Count by type
        type_counts = {}
        for citation in citations:
            source_type = citation.get('source_type', 'unknown')
            type_counts[source_type] = type_counts.get(source_type, 0) + 1
        
        return {
            'total_citations': len(citations),
            'verified_citations': verified_count,
            'verification_rate': verified_count / len(citations) if citations else 0.0,
            'citations_by_type': type_counts,
            'average_relevance': sum(c.get('relevance_score', 0) for c in citations) / len(citations)
        }