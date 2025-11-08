"""
Advanced metadata extraction for Indian legal documents
Specialized for extracting structured information from legal texts
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import structlog

from database import DocumentType

logger = structlog.get_logger(__name__)

@dataclass
class LegalEntity:
    """Structured legal entity information"""
    name: str
    entity_type: str  # court, party, lawyer, etc.
    role: Optional[str] = None

class LegalMetadataExtractor:
    """
    Production-grade metadata extractor for Indian legal documents
    
    Features:
    - Document type classification
    - Party and court identification
    - Citation and reference extraction
    - Date and timeline extraction
    - Legal concept identification
    """
    
    def __init__(self):
        self.court_patterns = self._initialize_court_patterns()
        self.date_patterns = self._initialize_date_patterns()
        self.citation_patterns = self._initialize_citation_patterns()
        self.party_patterns = self._initialize_party_patterns()
        self.legal_concepts = self._initialize_legal_concepts()
        
        logger.info("Legal metadata extractor initialized")
    
    async def extract_metadata(
        self,
        text: str,
        filename: str
    ) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from legal document
        
        Args:
            text: Document text content
            filename: Original filename
            
        Returns:
            Dictionary containing extracted metadata
        """
        metadata = {
            'filename': filename,
            'extraction_timestamp': datetime.utcnow().isoformat(),
            'text_length': len(text),
            'word_count': len(text.split())
        }
        
        try:
            # Document classification
            doc_type = await self._classify_document_type(text, filename)
            metadata['document_type'] = doc_type
            
            # Extract based on document type
            if doc_type == DocumentType.CASE_LAW:
                case_metadata = await self._extract_case_metadata(text)
                metadata.update(case_metadata)
            
            elif doc_type == DocumentType.STATUTE:
                statute_metadata = await self._extract_statute_metadata(text)
                metadata.update(statute_metadata)
            
            elif doc_type == DocumentType.REGULATION:
                regulation_metadata = await self._extract_regulation_metadata(text)
                metadata.update(regulation_metadata)
            
            # Common extractions for all document types
            common_metadata = await self._extract_common_metadata(text)
            metadata.update(common_metadata)
            
            logger.info(
                "Metadata extracted successfully",
                document_type=doc_type.value if doc_type else 'unknown',
                metadata_fields=len(metadata)
            )
            
            return metadata
            
        except Exception as e:
            logger.error("Metadata extraction failed", error=str(e), exc_info=True)
            return metadata
    
    async def extract_case_metadata(
        self,
        text: str,
        case_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract metadata specifically for case law documents
        
        Args:
            text: Case judgment text
            case_info: Basic case information
            
        Returns:
            Dictionary containing case-specific metadata
        """
        metadata = {
            'document_type': 'case_law',
            'case_name': case_info.get('name', ''),
            'court': case_info.get('court', ''),
            'year': case_info.get('year'),
            'citation': case_info.get('citation', ''),
            'importance': case_info.get('importance', 'medium'),
            'legal_areas': case_info.get('legal_areas', []),
            'description': case_info.get('description', '')
        }
        
        try:
            # Extract additional metadata from text
            case_metadata = await self._extract_case_metadata(text)
            metadata.update(case_metadata)
            
            # Extract case-specific elements
            case_title = self._extract_case_title(text)
            if case_title:
                metadata['extracted_title'] = case_title
            
            # Extract parties
            parties = self._extract_parties(text)
            if parties:
                metadata['parties'] = parties
            
            # Extract judges
            judges = self._extract_judges(text)
            if judges:
                metadata['judges'] = judges
            
            # Extract legal issues
            legal_issues = self._extract_legal_issues(text)
            if legal_issues:
                metadata['legal_issues'] = legal_issues
            
            # Extract case dates
            dates = self._extract_case_dates(text)
            if dates:
                metadata.update(dates)
            
            # Extract citations mentioned in the case
            citations = self._extract_all_citations(text)
            if citations:
                metadata['cited_cases'] = citations
            
            # Extract legal concepts
            concepts = self._extract_mentioned_concepts(text)
            if concepts:
                metadata['legal_concepts'] = concepts
            
            logger.info(
                "Case metadata extracted successfully",
                case_name=case_info.get('name', 'Unknown'),
                metadata_fields=len(metadata)
            )
            
            return metadata
            
        except Exception as e:
            logger.error(
                "Case metadata extraction failed",
                case_name=case_info.get('name', 'Unknown'),
                error=str(e),
                exc_info=True
            )
            return metadata
    
    async def _classify_document_type(
        self,
        text: str,
        filename: str
    ) -> DocumentType:
        """
        Classify the type of legal document
        """
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        # Check filename patterns first
        if any(term in filename_lower for term in ['judgment', 'order', 'case', 'appeal']):
            return DocumentType.CASE_LAW
        
        if any(term in filename_lower for term in ['act', 'code', 'constitution']):
            return DocumentType.STATUTE
        
        if any(term in filename_lower for term in ['rule', 'regulation', 'notification']):
            return DocumentType.REGULATION
        
        if any(term in filename_lower for term in ['contract', 'agreement', 'deed']):
            return DocumentType.CONTRACT
        
        if any(term in filename_lower for term in ['petition', 'application', 'writ']):
            return DocumentType.PETITION
        
        # Check content patterns
        case_indicators = [
            'petitioner', 'respondent', 'appellant', 'appellee',
            'plaintiff', 'defendant', 'coram', 'bench',
            'civil appeal', 'criminal appeal', 'writ petition'
        ]
        
        statute_indicators = [
            'section', 'chapter', 'part', 'schedule',
            'whereas', 'be it enacted', 'parliament',
            'legislature', 'government of india'
        ]
        
        regulation_indicators = [
            'rule', 'regulation', 'notification',
            'ministry', 'department', 'authority',
            'prescribed', 'notified'
        ]
        
        # Count indicators
        case_score = sum(1 for indicator in case_indicators if indicator in text_lower)
        statute_score = sum(1 for indicator in statute_indicators if indicator in text_lower)
        regulation_score = sum(1 for indicator in regulation_indicators if indicator in text_lower)
        
        # Determine type based on highest score
        if case_score > statute_score and case_score > regulation_score:
            return DocumentType.CASE_LAW
        elif statute_score > regulation_score:
            return DocumentType.STATUTE
        elif regulation_score > 0:
            return DocumentType.REGULATION
        
        # Default to user document
        return DocumentType.USER_DOCUMENT
    
    async def _extract_case_metadata(self, text: str) -> Dict[str, Any]:
        """Extract metadata specific to case law documents"""
        metadata = {}
        
        # Extract case title
        case_title = self._extract_case_title(text)
        if case_title:
            metadata['case_title'] = case_title
            metadata['title'] = case_title
        
        # Extract parties
        parties = self._extract_parties(text)
        if parties:
            metadata['parties'] = parties
            if 'petitioner' in parties:
                metadata['petitioner'] = parties['petitioner']
            if 'respondent' in parties:
                metadata['respondent'] = parties['respondent']
        
        # Extract court information
        court_info = self._extract_court_info(text)
        if court_info:
            metadata.update(court_info)
        
        # Extract judges
        judges = self._extract_judges(text)
        if judges:
            metadata['judges'] = judges
        
        # Extract citation
        citation = self._extract_case_citation(text)
        if citation:
            metadata['citation'] = citation
        
        # Extract dates
        dates = self._extract_case_dates(text)
        if dates:
            metadata.update(dates)
        
        # Extract legal issues
        legal_issues = self._extract_legal_issues(text)
        if legal_issues:
            metadata['legal_issues'] = legal_issues
        
        return metadata
    
    async def _extract_statute_metadata(self, text: str) -> Dict[str, Any]:
        """Extract metadata specific to statute documents"""
        metadata = {}
        
        # Extract act name
        act_name = self._extract_act_name(text)
        if act_name:
            metadata['act_name'] = act_name
            metadata['title'] = act_name
        
        # Extract enactment year
        year = self._extract_enactment_year(text)
        if year:
            metadata['year'] = year
            metadata['enactment_year'] = year
        
        # Extract preamble
        preamble = self._extract_preamble(text)
        if preamble:
            metadata['preamble'] = preamble
        
        # Extract sections
        sections = self._extract_sections(text)
        if sections:
            metadata['sections'] = sections
            metadata['section_count'] = len(sections)
        
        # Extract chapters
        chapters = self._extract_chapters(text)
        if chapters:
            metadata['chapters'] = chapters
        
        return metadata
    
    async def _extract_regulation_metadata(self, text: str) -> Dict[str, Any]:
        """Extract metadata specific to regulation documents"""
        metadata = {}
        
        # Extract regulation title
        reg_title = self._extract_regulation_title(text)
        if reg_title:
            metadata['regulation_title'] = reg_title
            metadata['title'] = reg_title
        
        # Extract notification details
        notification_info = self._extract_notification_info(text)
        if notification_info:
            metadata.update(notification_info)
        
        # Extract issuing authority
        authority = self._extract_issuing_authority(text)
        if authority:
            metadata['issuing_authority'] = authority
        
        # Extract rules
        rules = self._extract_rules(text)
        if rules:
            metadata['rules'] = rules
        
        return metadata
    
    async def _extract_common_metadata(self, text: str) -> Dict[str, Any]:
        """Extract metadata common to all document types"""
        metadata = {}
        
        # Extract all dates
        dates = self._extract_all_dates(text)
        if dates:
            metadata['dates_mentioned'] = dates
            # Try to identify the most relevant date
            if dates:
                metadata['primary_date'] = dates[0]
        
        # Extract citations and references
        citations = self._extract_all_citations(text)
        if citations:
            metadata['citations'] = citations
            metadata['citation_count'] = len(citations)
        
        # Extract legal concepts
        concepts = self._extract_mentioned_concepts(text)
        if concepts:
            metadata['legal_concepts'] = concepts
        
        # Extract language
        language = self._detect_language(text)
        metadata['language'] = language
        
        # Extract jurisdiction indicators
        jurisdiction = self._extract_jurisdiction(text)
        if jurisdiction:
            metadata['jurisdiction'] = jurisdiction
        
        return metadata
    
    def _extract_case_title(self, text: str) -> Optional[str]:
        """Extract case title from case law document"""
        # Look for case title patterns
        patterns = [
            r'^([A-Z][^v\n]*?)\s+v\.?\s+([A-Z][^\n]*?)(?:\n|$)',
            r'IN THE MATTER OF:?\s*([^\n]+)',
            r'BETWEEN:?\s*([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                if 'v.' in pattern or 'vs.' in pattern:
                    return f"{match.group(1).strip()} v. {match.group(2).strip()}"
                else:
                    return match.group(1).strip()
        
        return None
    
    def _extract_parties(self, text: str) -> Dict[str, str]:
        """Extract party information from case"""
        parties = {}
        
        # Petitioner/Appellant patterns
        petitioner_patterns = [
            r'Petitioner[:\s]*([^\n]+)',
            r'Appellant[:\s]*([^\n]+)',
            r'Plaintiff[:\s]*([^\n]+)'
        ]
        
        for pattern in petitioner_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                parties['petitioner'] = match.group(1).strip()
                break
        
        # Respondent/Appellee patterns
        respondent_patterns = [
            r'Respondent[:\s]*([^\n]+)',
            r'Appellee[:\s]*([^\n]+)',
            r'Defendant[:\s]*([^\n]+)'
        ]
        
        for pattern in respondent_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                parties['respondent'] = match.group(1).strip()
                break
        
        return parties
    
    def _extract_court_info(self, text: str) -> Dict[str, Any]:
        """Extract court information"""
        court_info = {}
        
        # Extract court name
        for court_name, pattern in self.court_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                court_info['court'] = court_name
                break
        
        # Extract bench information
        bench_match = re.search(r'CORAM[:\s]*([^\n]+)', text, re.IGNORECASE)
        if bench_match:
            court_info['bench'] = bench_match.group(1).strip()
        
        return court_info
    
    def _extract_judges(self, text: str) -> List[str]:
        """Extract judge names from case"""
        judges = []
        
        # Look for judge patterns
        judge_patterns = [
            r'(?:Hon\'ble\s+)?(?:Mr\.|Ms\.|Justice)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'J\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        for pattern in judge_patterns:
            matches = re.findall(pattern, text)
            judges.extend(matches)
        
        return list(set(judges))  # Remove duplicates
    
    def _extract_case_citation(self, text: str) -> Optional[str]:
        """Extract case citation"""
        citation_patterns = [
            r'\b(\d{4})\s+(\w+)\s+(\d+)\b',
            r'AIR\s+(\d{4})\s+(\w+)\s+(\d+)',
            r'\[(\d{4})\]\s+(\w+)\s+(\d+)'
        ]
        
        for pattern in citation_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_case_dates(self, text: str) -> Dict[str, str]:
        """Extract important dates from case"""
        dates = {}
        
        # Look for judgment date
        judgment_patterns = [
            r'Judgment\s+(?:delivered\s+on\s+)?:?\s*([^\n]+)',
            r'Decided\s+on\s*:?\s*([^\n]+)',
            r'Date\s+of\s+Judgment\s*:?\s*([^\n]+)'
        ]
        
        for pattern in judgment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                dates['judgment_date'] = match.group(1).strip()
                break
        
        # Look for hearing date
        hearing_patterns = [
            r'Date\s+of\s+Hearing\s*:?\s*([^\n]+)',
            r'Heard\s+on\s*:?\s*([^\n]+)'
        ]
        
        for pattern in hearing_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                dates['hearing_date'] = match.group(1).strip()
                break
        
        return dates
    
    def _extract_legal_issues(self, text: str) -> List[str]:
        """Extract legal issues from case"""
        issues = []
        
        # Look for issues section
        issues_match = re.search(
            r'(?:ISSUES?|QUESTIONS?|POINTS?)\s*:?\s*\n(.*?)(?:\n\n|\nHELD|\nDECISION)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        
        if issues_match:
            issues_text = issues_match.group(1)
            # Split by numbered points
            issue_items = re.findall(r'\d+\.\s*([^\n]+)', issues_text)
            issues.extend(issue_items)
        
        return issues
    
    def _extract_act_name(self, text: str) -> Optional[str]:
        """Extract act name from statute"""
        # Look for act title patterns
        patterns = [
            r'THE\s+([^,\n]+?)\s+ACT,?\s+\d{4}',
            r'([^,\n]+?)\s+ACT,?\s+\d{4}',
            r'AN\s+ACT\s+([^.\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_enactment_year(self, text: str) -> Optional[int]:
        """Extract enactment year from statute"""
        # Look for year in act title
        year_match = re.search(r'ACT,?\s+(\d{4})', text, re.IGNORECASE)
        if year_match:
            return int(year_match.group(1))
        
        return None
    
    def _extract_preamble(self, text: str) -> Optional[str]:
        """Extract preamble from statute"""
        preamble_match = re.search(
            r'WHEREAS\s+(.*?)(?:\n\n|NOW\s+THEREFORE|BE\s+IT\s+ENACTED)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        
        if preamble_match:
            return preamble_match.group(1).strip()
        
        return None
    
    def _extract_sections(self, text: str) -> List[Dict[str, str]]:
        """Extract sections from statute"""
        sections = []
        
        # Find all section headers
        section_matches = re.finditer(
            r'(Section\s+(\d+[A-Z]?))\.\s*([^\n]+)',
            text,
            re.IGNORECASE
        )
        
        for match in section_matches:
            sections.append({
                'number': match.group(2),
                'title': match.group(3).strip(),
                'full_header': match.group(1)
            })
        
        return sections
    
    def _extract_chapters(self, text: str) -> List[Dict[str, str]]:
        """Extract chapters from statute"""
        chapters = []
        
        chapter_matches = re.finditer(
            r'CHAPTER\s+([IVX]+|\d+)\s*[:\-]?\s*([^\n]+)',
            text,
            re.IGNORECASE
        )
        
        for match in chapter_matches:
            chapters.append({
                'number': match.group(1),
                'title': match.group(2).strip()
            })
        
        return chapters
    
    def _extract_regulation_title(self, text: str) -> Optional[str]:
        """Extract regulation title"""
        patterns = [
            r'THE\s+([^,\n]+?)\s+RULES?,?\s+\d{4}',
            r'([^,\n]+?)\s+RULES?,?\s+\d{4}',
            r'NOTIFICATION\s*:?\s*([^\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_notification_info(self, text: str) -> Dict[str, str]:
        """Extract notification information"""
        info = {}
        
        # Extract notification number
        no_match = re.search(r'No\.?\s*([^\n,]+)', text, re.IGNORECASE)
        if no_match:
            info['notification_number'] = no_match.group(1).strip()
        
        # Extract date
        date_match = re.search(r'dated\s+([^\n,]+)', text, re.IGNORECASE)
        if date_match:
            info['notification_date'] = date_match.group(1).strip()
        
        return info
    
    def _extract_issuing_authority(self, text: str) -> Optional[str]:
        """Extract issuing authority"""
        authority_patterns = [
            r'MINISTRY\s+OF\s+([^\n]+)',
            r'DEPARTMENT\s+OF\s+([^\n]+)',
            r'GOVERNMENT\s+OF\s+([^\n]+)'
        ]
        
        for pattern in authority_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_rules(self, text: str) -> List[Dict[str, str]]:
        """Extract rules from regulation"""
        rules = []
        
        rule_matches = re.finditer(
            r'(Rule\s+(\d+[A-Z]?))\.\s*([^\n]+)',
            text,
            re.IGNORECASE
        )
        
        for match in rule_matches:
            rules.append({
                'number': match.group(2),
                'title': match.group(3).strip(),
                'full_header': match.group(1)
            })
        
        return rules
    
    def _extract_all_dates(self, text: str) -> List[str]:
        """Extract all dates mentioned in document"""
        dates = []
        
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)
        
        return list(set(dates))  # Remove duplicates
    
    def _extract_all_citations(self, text: str) -> List[Dict[str, str]]:
        """Extract all citations from document"""
        citations = []
        
        for citation_type, pattern in self.citation_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                citations.append({
                    'type': citation_type,
                    'text': match.group(0),
                    'position': match.start()
                })
        
        return citations
    
    def _extract_mentioned_concepts(self, text: str) -> List[str]:
        """Extract legal concepts mentioned in document"""
        concepts = []
        text_lower = text.lower()
        
        for concept in self.legal_concepts:
            if concept.lower() in text_lower:
                concepts.append(concept)
        
        return concepts
    
    def _detect_language(self, text: str) -> str:
        """Detect document language"""
        # Simple heuristic - can be enhanced with proper language detection
        hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
        total_chars = len(text)
        
        if hindi_chars > total_chars * 0.1:
            return 'hi'  # Hindi
        else:
            return 'en'  # English
    
    def _extract_jurisdiction(self, text: str) -> Optional[str]:
        """Extract jurisdiction information"""
        # Look for state/central jurisdiction indicators
        central_indicators = ['central government', 'union of india', 'parliament']
        state_indicators = ['state government', 'state legislature', 'high court']
        
        text_lower = text.lower()
        
        if any(indicator in text_lower for indicator in central_indicators):
            return 'central'
        elif any(indicator in text_lower for indicator in state_indicators):
            return 'state'
        
        return None
    
    def _initialize_court_patterns(self) -> Dict[str, str]:
        """Initialize court name patterns"""
        return {
            'Supreme Court': r'Supreme\s+Court\s+of\s+India|Supreme\s+Court',
            'Delhi High Court': r'Delhi\s+High\s+Court|High\s+Court\s+of\s+Delhi',
            'Bombay High Court': r'Bombay\s+High\s+Court|High\s+Court\s+of\s+Bombay',
            'Calcutta High Court': r'Calcutta\s+High\s+Court|High\s+Court\s+of\s+Calcutta',
            'Madras High Court': r'Madras\s+High\s+Court|High\s+Court\s+of\s+Madras',
            'Karnataka High Court': r'Karnataka\s+High\s+Court|High\s+Court\s+of\s+Karnataka',
            'Gujarat High Court': r'Gujarat\s+High\s+Court|High\s+Court\s+of\s+Gujarat',
        }
    
    def _initialize_date_patterns(self) -> List[str]:
        """Initialize date extraction patterns"""
        return [
            r'\b\d{1,2}(?:st|nd|rd|th)?\s+\w+,?\s+\d{4}\b',
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b',
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
            r'\b\w+\s+\d{1,2},?\s+\d{4}\b'
        ]
    
    def _initialize_citation_patterns(self) -> Dict[str, str]:
        """Initialize citation patterns"""
        return {
            'case_law': r'\b\d{4}\s+\w+\s+\d+\b|\bAIR\s+\d{4}\s+\w+\s+\d+\b',
            'statute': r'\bSection\s+\d+[A-Z]?\s+of\s+(?:the\s+)?[^,\n]+Act',
            'article': r'\bArticle\s+\d+[A-Z]?\s+of\s+(?:the\s+)?Constitution'
        }
    
    def _initialize_party_patterns(self) -> Dict[str, str]:
        """Initialize party identification patterns"""
        return {
            'petitioner': r'Petitioner[:\s]*([^\n]+)',
            'respondent': r'Respondent[:\s]*([^\n]+)',
            'appellant': r'Appellant[:\s]*([^\n]+)',
            'appellee': r'Appellee[:\s]*([^\n]+)'
        }
    
    def _initialize_legal_concepts(self) -> List[str]:
        """Initialize legal concepts list"""
        return [
            'fundamental rights', 'directive principles', 'judicial review',
            'natural justice', 'due process', 'rule of law', 'separation of powers',
            'federalism', 'secularism', 'democracy', 'republic',
            'habeas corpus', 'mandamus', 'certiorari', 'prohibition', 'quo warranto',
            'res judicata', 'sub judice', 'prima facie', 'bona fide', 'mala fide',
            'ultra vires', 'intra vires', 'locus standi', 'ratio decidendi', 'obiter dicta',
            'precedent', 'stare decisis', 'jurisdiction', 'venue', 'limitation',
            'appeal', 'revision', 'review', 'writ petition', 'public interest litigation'
        ]