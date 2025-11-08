"""
Advanced text processing utilities for Indian Legal AI Assistant
Specialized for legal document processing with Indian legal conventions
"""
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import structlog
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import tiktoken

from database import DocumentType
from config import settings

logger = structlog.get_logger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class TextType(Enum):
    """Types of text content"""
    HEADING = "heading"
    BODY = "body"
    CITATION = "citation"
    FOOTNOTE = "footnote"
    TABLE = "table"
    LIST_ITEM = "list_item"

@dataclass
class TextSegment:
    """Structured text segment"""
    text: str
    text_type: TextType
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any]

class TextProcessor:
    """
    Production-grade text processing for legal documents
    
    Features:
    - Legal text normalization and cleaning
    - Indian legal keyword extraction
    - Citation pattern recognition
    - Text structure analysis
    - Language detection and processing
    """
    
    def __init__(self):
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Indian legal patterns
        self.legal_patterns = self._initialize_legal_patterns()
        self.court_names = self._initialize_court_names()
        self.legal_terms = self._initialize_legal_terms()
        
        # Stop words (English + legal stop words)
        self.stop_words = set(stopwords.words('english'))
        self.stop_words.update(['said', 'aforesaid', 'whereas', 'whereof', 'thereof'])
        
        logger.info("Text processor initialized with Indian legal patterns")
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text for processing
        
        Args:
            text: Raw text content
            
        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR errors in legal documents
        text = self._fix_ocr_errors(text)
        
        # Normalize legal citations
        text = self._normalize_citations(text)
        
        # Fix paragraph breaks
        text = self._fix_paragraph_breaks(text)
        
        # Remove page headers/footers
        text = self._remove_headers_footers(text)
        
        return text.strip()
    
    def extract_legal_keywords(self, text: str) -> List[str]:
        """
        Extract legal keywords and phrases from text
        
        Args:
            text: Input text
            
        Returns:
            List of extracted legal keywords
        """
        keywords = []
        text_lower = text.lower()
        
        # Extract case names
        case_patterns = [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+v\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+vs\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        ]
        
        for pattern in case_patterns:
            matches = re.findall(pattern, text)
            keywords.extend(matches)
        
        # Extract statutory references
        statutory_patterns = [
            r'\bSection\s+\d+[A-Z]?\b',
            r'\bArticle\s+\d+[A-Z]?\b',
            r'\b\w+\s+Act,?\s+\d{4}\b',
            r'\bRule\s+\d+[A-Z]?\b'
        ]
        
        for pattern in statutory_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            keywords.extend(matches)
        
        # Extract court names
        for court_name in self.court_names:
            if court_name.lower() in text_lower:
                keywords.append(court_name)
        
        # Extract legal terms
        words = word_tokenize(text_lower)
        for term in self.legal_terms:
            if term.lower() in words:
                keywords.append(term)
        
        return list(set(keywords))  # Remove duplicates
    
    def analyze_text_structure(self, text: str) -> List[TextSegment]:
        """
        Analyze text structure and identify different types of content
        
        Args:
            text: Input text
            
        Returns:
            List of structured text segments
        """
        segments = []
        lines = text.split('\n')
        current_pos = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                current_pos += 1
                continue
            
            # Determine text type
            text_type = self._classify_text_type(line)
            
            # Extract metadata
            metadata = self._extract_line_metadata(line, text_type)
            
            segment = TextSegment(
                text=line,
                text_type=text_type,
                start_pos=current_pos,
                end_pos=current_pos + len(line),
                metadata=metadata
            )
            
            segments.append(segment)
            current_pos += len(line) + 1  # +1 for newline
        
        return segments
    
    def extract_citations(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract legal citations from text
        
        Args:
            text: Input text
            
        Returns:
            List of extracted citations with metadata
        """
        citations = []
        
        # Case law citations
        case_patterns = [
            r'\b(\d{4})\s+(\w+)\s+(\d+)\b',  # 2023 SC 123
            r'\b\[(\d{4})\]\s+(\w+)\s+(\d+)\b',  # [2023] SC 123
            r'\bAIR\s+(\d{4})\s+(\w+)\s+(\d+)\b'  # AIR 2023 SC 123
        ]
        
        for pattern in case_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                citations.append({
                    'type': 'case_law',
                    'text': match.group(0),
                    'year': match.group(1),
                    'court': match.group(2),
                    'number': match.group(3),
                    'position': match.start()
                })
        
        # Statutory citations
        statutory_patterns = [
            r'\bSection\s+(\d+[A-Z]?)\s+of\s+(?:the\s+)?([^,\n]+?)(?:,|\.|$)',
            r'\bArticle\s+(\d+[A-Z]?)\s+of\s+(?:the\s+)?([^,\n]+?)(?:,|\.|$)'
        ]
        
        for pattern in statutory_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                citations.append({
                    'type': 'statute',
                    'text': match.group(0),
                    'section': match.group(1),
                    'act': match.group(2).strip(),
                    'position': match.start()
                })
        
        return citations
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using OpenAI tokenizer"""
        return len(self.tokenizer.encode(text))
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences with legal document awareness
        
        Args:
            text: Input text
            
        Returns:
            List of sentences
        """
        # Use NLTK sentence tokenizer as base
        sentences = sent_tokenize(text)
        
        # Post-process for legal documents
        processed_sentences = []
        
        for sentence in sentences:
            # Handle legal abbreviations that shouldn't split sentences
            if self._is_legal_abbreviation_split(sentence, processed_sentences):
                # Merge with previous sentence
                if processed_sentences:
                    processed_sentences[-1] += " " + sentence
                else:
                    processed_sentences.append(sentence)
            else:
                processed_sentences.append(sentence)
        
        return processed_sentences
    
    def _initialize_legal_patterns(self) -> Dict[str, str]:
        """Initialize regex patterns for legal text"""
        return {
            'case_citation': r'\b\d{4}\s+\w+\s+\d+\b|\bAIR\s+\d{4}\s+\w+\s+\d+\b',
            'section_reference': r'\bSection\s+\d+[A-Z]?\b|\bArt(?:icle)?\s+\d+[A-Z]?\b',
            'act_reference': r'\b\w+(?:\s+\w+)*\s+Act,?\s+\d{4}\b',
            'court_name': r'\bSupreme\s+Court\b|\b\w+\s+High\s+Court\b',
            'legal_proceeding': r'\bWrit\s+Petition\b|\bCivil\s+Appeal\b|\bCriminal\s+Appeal\b',
            'date_pattern': r'\b\d{1,2}(?:st|nd|rd|th)?\s+\w+,?\s+\d{4}\b',
            'paragraph_number': r'^\s*\d+\.\s+',
            'sub_paragraph': r'^\s*\(\w+\)\s+',
        }
    
    def _initialize_court_names(self) -> Set[str]:
        """Initialize set of Indian court names"""
        return {
            'Supreme Court of India', 'Supreme Court',
            'Delhi High Court', 'Bombay High Court', 'Calcutta High Court',
            'Madras High Court', 'Karnataka High Court', 'Gujarat High Court',
            'Rajasthan High Court', 'Punjab and Haryana High Court',
            'Allahabad High Court', 'Patna High Court', 'Orissa High Court',
            'Madhya Pradesh High Court', 'Chhattisgarh High Court',
            'Jharkhand High Court', 'Gauhati High Court', 'Kerala High Court',
            'Andhra Pradesh High Court', 'Telangana High Court',
            'Himachal Pradesh High Court', 'Jammu and Kashmir High Court',
            'Uttarakhand High Court', 'Sikkim High Court', 'Tripura High Court',
            'Manipur High Court', 'Meghalaya High Court'
        }
    
    def _initialize_legal_terms(self) -> Set[str]:
        """Initialize set of important legal terms"""
        return {
            # Procedural terms
            'plaintiff', 'defendant', 'petitioner', 'respondent',
            'appellant', 'appellee', 'applicant', 'intervenor',
            
            # Court proceedings
            'judgment', 'order', 'decree', 'writ', 'mandamus',
            'certiorari', 'prohibition', 'habeas corpus', 'quo warranto',
            
            # Legal concepts
            'jurisdiction', 'precedent', 'ratio decidendi', 'obiter dicta',
            'res judicata', 'sub judice', 'prima facie', 'bona fide',
            
            # Indian legal terms
            'dharma', 'nyaya', 'rajya', 'lok adalat', 'gram nyayalaya',
            
            # Constitutional terms
            'fundamental rights', 'directive principles', 'emergency',
            'amendment', 'constituent assembly', 'preamble',
            
            # Criminal law
            'cognizable', 'non-cognizable', 'bailable', 'non-bailable',
            'charge sheet', 'challan', 'investigation', 'inquiry',
            
            # Civil law
            'suit', 'plaint', 'written statement', 'replication',
            'rejoinder', 'issues', 'evidence', 'cross-examination'
        }
    
    def _fix_ocr_errors(self, text: str) -> str:
        """Fix common OCR errors in legal documents"""
        # Common OCR substitutions
        ocr_fixes = {
            r'\bl\b': 'I',  # lowercase l to uppercase I
            r'\b0\b': 'O',  # zero to letter O in some contexts
            r'rn': 'm',     # rn to m
            r'vv': 'w',     # double v to w
            r'cl': 'd',     # cl to d in some contexts
        }
        
        for pattern, replacement in ocr_fixes.items():
            text = re.sub(pattern, replacement, text)
        
        return text
    
    def _normalize_citations(self, text: str) -> str:
        """Normalize legal citations to standard format"""
        # Standardize "v." and "vs."
        text = re.sub(r'\s+vs?\.\s+', ' v. ', text)
        text = re.sub(r'\s+versus\s+', ' v. ', text, flags=re.IGNORECASE)
        
        # Standardize court abbreviations
        court_abbreviations = {
            'Supreme Court of India': 'SC',
            'Supreme Court': 'SC',
            'High Court': 'HC'
        }
        
        for full_name, abbrev in court_abbreviations.items():
            text = re.sub(full_name, abbrev, text, flags=re.IGNORECASE)
        
        return text
    
    def _fix_paragraph_breaks(self, text: str) -> str:
        """Fix paragraph breaks in legal documents"""
        # Join lines that are likely continuation of previous line
        lines = text.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                fixed_lines.append('')
                continue
            
            # Check if this line should be joined with previous
            if (i > 0 and 
                fixed_lines and 
                not self._is_new_paragraph(line) and
                not fixed_lines[-1].endswith('.') and
                not fixed_lines[-1].endswith(':') and
                len(fixed_lines[-1]) > 0):
                
                # Join with previous line
                fixed_lines[-1] += ' ' + line
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _remove_headers_footers(self, text: str) -> str:
        """Remove page headers and footers"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip likely headers/footers
            if (len(line) < 5 or
                re.match(r'^\s*Page\s+\d+', line, re.IGNORECASE) or
                re.match(r'^\s*\d+\s*$', line) or  # Page numbers
                re.match(r'^\s*-\s*\d+\s*-\s*$', line)):  # Page numbers with dashes
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _classify_text_type(self, line: str) -> TextType:
        """Classify the type of text content"""
        line = line.strip()
        
        # Check for headings (all caps, numbered, etc.)
        if (line.isupper() and len(line) > 5) or re.match(r'^\d+\.\s+[A-Z]', line):
            return TextType.HEADING
        
        # Check for citations
        if re.search(self.legal_patterns['case_citation'], line):
            return TextType.CITATION
        
        # Check for footnotes
        if re.match(r'^\d+\s+', line) and len(line) < 200:
            return TextType.FOOTNOTE
        
        # Check for list items
        if re.match(r'^\s*[\(\[]?[a-z0-9]+[\)\]]\s+', line):
            return TextType.LIST_ITEM
        
        # Default to body text
        return TextType.BODY
    
    def _extract_line_metadata(self, line: str, text_type: TextType) -> Dict[str, Any]:
        """Extract metadata from a line of text"""
        metadata = {'type': text_type.value}
        
        if text_type == TextType.HEADING:
            # Extract heading level
            if re.match(r'^\d+\.\s+', line):
                metadata['level'] = 1
            elif re.match(r'^\d+\.\d+\s+', line):
                metadata['level'] = 2
            else:
                metadata['level'] = 1
        
        elif text_type == TextType.CITATION:
            # Extract citation details
            citations = self.extract_citations(line)
            if citations:
                metadata['citations'] = citations
        
        return metadata
    
    def _is_new_paragraph(self, line: str) -> bool:
        """Check if line starts a new paragraph"""
        # Paragraph indicators
        paragraph_indicators = [
            r'^\d+\.',  # Numbered paragraphs
            r'^\([a-z]\)',  # Lettered sub-paragraphs
            r'^[A-Z][A-Z\s]+:',  # All caps headings with colon
            r'^WHEREAS',  # Legal document clauses
            r'^NOW THEREFORE',
            r'^IN WITNESS WHEREOF'
        ]
        
        for pattern in paragraph_indicators:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        
        return False
    
    def _is_legal_abbreviation_split(self, sentence: str, previous_sentences: List[str]) -> bool:
        """Check if sentence was incorrectly split due to legal abbreviation"""
        if not previous_sentences:
            return False
        
        prev_sentence = previous_sentences[-1]
        
        # Common legal abbreviations that cause incorrect splits
        legal_abbrevs = ['v.', 'vs.', 'etc.', 'i.e.', 'e.g.', 'cf.', 'ibid.']
        
        for abbrev in legal_abbrevs:
            if prev_sentence.endswith(abbrev) and not sentence[0].isupper():
                return True
        
        return False

class LegalTextChunker:
    """
    Specialized text chunker for legal documents
    
    Features:
    - Legal structure-aware chunking
    - Semantic boundary preservation
    - Citation and reference handling
    - Optimal chunk sizing for embeddings
    """
    
    def __init__(self):
        self.text_processor = TextProcessor()
        self.chunk_size = settings.vector_db.chunk_size
        self.chunk_overlap = settings.vector_db.chunk_overlap
        
        logger.info("Legal text chunker initialized")
    
    async def chunk_document(
        self,
        text: str,
        document_type: DocumentType,
        source_name: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Chunk document based on its type and structure
        
        Args:
            text: Document text
            document_type: Type of legal document
            source_name: Source document name
            metadata: Document metadata
            
        Returns:
            List of chunks with metadata
        """
        # Clean and preprocess text
        cleaned_text = self.text_processor.clean_text(text)
        
        # Choose chunking strategy based on document type
        if document_type == DocumentType.STATUTE:
            chunks = await self._chunk_statute(cleaned_text, source_name, metadata)
        elif document_type == DocumentType.CASE_LAW:
            chunks = await self._chunk_case_law(cleaned_text, source_name, metadata)
        elif document_type == DocumentType.REGULATION:
            chunks = await self._chunk_regulation(cleaned_text, source_name, metadata)
        else:
            chunks = await self._chunk_generic_legal_document(cleaned_text, source_name, metadata)
        
        # Post-process chunks
        processed_chunks = []
        for i, chunk in enumerate(chunks):
            processed_chunk = await self._post_process_chunk(chunk, i, document_type)
            if processed_chunk:
                processed_chunks.append(processed_chunk)
        
        logger.info(
            "Document chunked successfully",
            source_name=source_name,
            document_type=document_type.value,
            chunk_count=len(processed_chunks)
        )
        
        return processed_chunks
    
    async def _chunk_statute(
        self,
        text: str,
        source_name: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Chunk statute preserving section boundaries"""
        chunks = []
        
        # Split by sections
        section_pattern = r'(Section\s+\d+[A-Z]?\.?\s*[:\-]?)'
        sections = re.split(section_pattern, text, flags=re.IGNORECASE)
        
        current_chunk = ""
        current_section = None
        
        for i, part in enumerate(sections):
            if re.match(section_pattern, part, re.IGNORECASE):
                # This is a section header
                if current_chunk and len(current_chunk.strip()) > 50:
                    chunks.append(self._create_chunk(
                        text=current_chunk,
                        source_name=source_name,
                        source_type=DocumentType.STATUTE,
                        metadata={**metadata, "section": current_section},
                        section_number=current_section
                    ))
                
                current_section = part.strip()
                current_chunk = part
            else:
                current_chunk += part
                
                # If chunk is getting too large, split it
                if self.text_processor.count_tokens(current_chunk) > self.chunk_size:
                    chunks.append(self._create_chunk(
                        text=current_chunk,
                        source_name=source_name,
                        source_type=DocumentType.STATUTE,
                        metadata={**metadata, "section": current_section},
                        section_number=current_section
                    ))
                    current_chunk = ""
        
        # Add final chunk
        if current_chunk and len(current_chunk.strip()) > 50:
            chunks.append(self._create_chunk(
                text=current_chunk,
                source_name=source_name,
                source_type=DocumentType.STATUTE,
                metadata={**metadata, "section": current_section},
                section_number=current_section
            ))
        
        return chunks
    
    async def _chunk_case_law(
        self,
        text: str,
        source_name: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Chunk case law preserving paragraph structure"""
        chunks = []
        
        # Split by paragraphs (double newlines)
        paragraphs = re.split(r'\n\s*\n', text)
        
        current_chunk = ""
        paragraph_count = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check if adding this paragraph would exceed chunk size
            test_chunk = current_chunk + "\n\n" + para if current_chunk else para
            token_count = self.text_processor.count_tokens(test_chunk)
            
            if token_count > self.chunk_size and current_chunk:
                # Save current chunk and start new one
                chunks.append(self._create_chunk(
                    text=current_chunk,
                    source_name=source_name,
                    source_type=DocumentType.CASE_LAW,
                    metadata={**metadata, "paragraph_range": f"1-{paragraph_count}"}
                ))
                
                # Start new chunk with overlap
                current_chunk = para
                paragraph_count = 1
            else:
                current_chunk = test_chunk
                paragraph_count += 1
        
        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                text=current_chunk,
                source_name=source_name,
                source_type=DocumentType.CASE_LAW,
                metadata={**metadata, "paragraph_range": f"1-{paragraph_count}"}
            ))
        
        return chunks
    
    async def _chunk_regulation(
        self,
        text: str,
        source_name: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Chunk regulation preserving rule structure"""
        # Similar to statute chunking but for rules/regulations
        chunks = []
        
        # Split by rules
        rule_pattern = r'(Rule\s+\d+[A-Z]?\.?\s*[:\-]?)'
        rules = re.split(rule_pattern, text, flags=re.IGNORECASE)
        
        current_chunk = ""
        current_rule = None
        
        for i, part in enumerate(rules):
            if re.match(rule_pattern, part, re.IGNORECASE):
                if current_chunk and len(current_chunk.strip()) > 50:
                    chunks.append(self._create_chunk(
                        text=current_chunk,
                        source_name=source_name,
                        source_type=DocumentType.REGULATION,
                        metadata={**metadata, "rule": current_rule}
                    ))
                
                current_rule = part.strip()
                current_chunk = part
            else:
                current_chunk += part
                
                if self.text_processor.count_tokens(current_chunk) > self.chunk_size:
                    chunks.append(self._create_chunk(
                        text=current_chunk,
                        source_name=source_name,
                        source_type=DocumentType.REGULATION,
                        metadata={**metadata, "rule": current_rule}
                    ))
                    current_chunk = ""
        
        if current_chunk and len(current_chunk.strip()) > 50:
            chunks.append(self._create_chunk(
                text=current_chunk,
                source_name=source_name,
                source_type=DocumentType.REGULATION,
                metadata={**metadata, "rule": current_rule}
            ))
        
        return chunks
    
    async def _chunk_generic_legal_document(
        self,
        text: str,
        source_name: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generic chunking with overlap for user documents"""
        chunks = []
        
        # Split into sentences
        sentences = self.text_processor.split_into_sentences(text)
        
        current_chunk = ""
        current_sentences = []
        
        for sentence in sentences:
            test_chunk = current_chunk + " " + sentence if current_chunk else sentence
            token_count = self.text_processor.count_tokens(test_chunk)
            
            if token_count > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(self._create_chunk(
                    text=current_chunk,
                    source_name=source_name,
                    source_type=DocumentType.USER_DOCUMENT,
                    metadata=metadata
                ))
                
                # Start new chunk with overlap
                overlap_sentences = current_sentences[-2:] if len(current_sentences) >= 2 else current_sentences
                current_chunk = " ".join(overlap_sentences) + " " + sentence
                current_sentences = overlap_sentences + [sentence]
            else:
                current_chunk = test_chunk
                current_sentences.append(sentence)
        
        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                text=current_chunk,
                source_name=source_name,
                source_type=DocumentType.USER_DOCUMENT,
                metadata=metadata
            ))
        
        return chunks
    
    async def chunk_case_law(
        self,
        text: str,
        case_name: str,
        court: str,
        year: int,
        citation: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Specialized chunking for case law that preserves judicial reasoning
        
        Args:
            text: Case judgment text
            case_name: Name of the case
            court: Court name
            year: Year of judgment
            citation: Legal citation
            metadata: Additional metadata
            
        Returns:
            List of chunks with case-specific metadata
        """
        chunks = []
        
        # Enhanced metadata for case law
        case_metadata = {
            **metadata,
            'case_name': case_name,
            'court': court,
            'year': year,
            'citation': citation,
            'document_type': 'case_law'
        }
        
        # Split by major sections (JUDGMENT, FACTS, RATIO, etc.)
        section_patterns = [
            r'(JUDGMENT|JUDGEMENT)',
            r'(FACTS?)',
            r'(ISSUES?)',
            r'(RATIO\s+DECIDENDI|RATIO)',
            r'(OBITER\s+DICTA|OBITER)',
            r'(CONCLUSION|HELD)',
            r'(ORDER)',
            r'(DISSENTING\s+OPINION|DISSENT)'
        ]
        
        # Try to identify major sections
        sections = self._identify_case_sections(text, section_patterns)
        
        if sections:
            # Process each section separately
            for section_name, section_text in sections.items():
                section_chunks = await self._chunk_case_section(
                    section_text, 
                    case_name, 
                    section_name,
                    case_metadata
                )
                chunks.extend(section_chunks)
        else:
            # Fall back to paragraph-based chunking
            chunks = await self._chunk_case_law(text, case_name, case_metadata)
        
        return chunks
    
    def _identify_case_sections(
        self, 
        text: str, 
        section_patterns: List[str]
    ) -> Dict[str, str]:
        """Identify major sections in a case judgment"""
        sections = {}
        current_section = "INTRODUCTION"
        current_text = ""
        
        lines = text.split('\n')
        
        for line in lines:
            line_upper = line.strip().upper()
            
            # Check if this line matches any section pattern
            section_found = None
            for pattern in section_patterns:
                if re.match(pattern, line_upper):
                    section_found = line_upper
                    break
            
            if section_found:
                # Save previous section
                if current_text.strip():
                    sections[current_section] = current_text.strip()
                
                # Start new section
                current_section = section_found
                current_text = line + '\n'
            else:
                current_text += line + '\n'
        
        # Save final section
        if current_text.strip():
            sections[current_section] = current_text.strip()
        
        return sections
    
    async def _chunk_case_section(
        self,
        section_text: str,
        case_name: str,
        section_name: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Chunk a specific section of a case judgment"""
        chunks = []
        
        # Split by paragraphs
        paragraphs = re.split(r'\n\s*\n', section_text)
        
        current_chunk = ""
        paragraph_count = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check if adding this paragraph would exceed chunk size
            test_chunk = current_chunk + "\n\n" + para if current_chunk else para
            token_count = self.text_processor.count_tokens(test_chunk)
            
            if token_count > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_metadata = {
                    **metadata,
                    'section': section_name,
                    'paragraph_range': f"1-{paragraph_count}"
                }
                
                chunks.append(self._create_chunk(
                    text=current_chunk,
                    source_name=case_name,
                    source_type=DocumentType.CASE_LAW,
                    metadata=chunk_metadata
                ))
                
                # Start new chunk with some overlap for context
                current_chunk = para
                paragraph_count = 1
            else:
                current_chunk = test_chunk
                paragraph_count += 1
        
        # Add final chunk
        if current_chunk:
            chunk_metadata = {
                **metadata,
                'section': section_name,
                'paragraph_range': f"1-{paragraph_count}"
            }
            
            chunks.append(self._create_chunk(
                text=current_chunk,
                source_name=case_name,
                source_type=DocumentType.CASE_LAW,
                metadata=chunk_metadata
            ))
        
        return chunks
    
    def _create_chunk(
        self,
        text: str,
        source_name: str,
        source_type: DocumentType,
        metadata: Dict[str, Any],
        section_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a chunk dictionary with all required fields"""
        return {
            'text': text.strip(),
            'source_name': source_name,
            'source_type': source_type,
            'metadata': metadata,
            'section_number': section_number,
            'section_title': metadata.get('section_title'),
            'content_type': 'body',
            'importance_score': self._calculate_importance_score(text)
        }
    
    def _calculate_importance_score(self, text: str) -> float:
        """Calculate importance score for chunk (0.0-1.0)"""
        score = 0.5  # Base score
        
        # Boost for legal keywords
        legal_keywords = self.text_processor.extract_legal_keywords(text)
        score += min(0.3, len(legal_keywords) * 0.05)
        
        # Boost for citations
        citations = self.text_processor.extract_citations(text)
        score += min(0.2, len(citations) * 0.1)
        
        # Penalty for very short or very long chunks
        word_count = len(text.split())
        if word_count < 20:
            score -= 0.2
        elif word_count > 300:
            score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    async def _post_process_chunk(
        self,
        chunk: Dict[str, Any],
        index: int,
        document_type: DocumentType
    ) -> Optional[Dict[str, Any]]:
        """Post-process chunk for quality and consistency"""
        text = chunk['text']
        
        # Filter out very short chunks
        if len(text.strip()) < 30:
            return None
        
        # Filter out chunks that are mostly whitespace or special characters
        if len(re.sub(r'[^\w\s]', '', text)) < 20:
            return None
        
        # Add chunk index
        chunk['chunk_index'] = index
        
        # Extract additional metadata
        chunk['word_count'] = len(text.split())
        chunk['token_count'] = self.text_processor.count_tokens(text)
        
        return chunk