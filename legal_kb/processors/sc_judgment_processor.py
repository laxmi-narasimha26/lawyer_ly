"""
Supreme Court Judgment Processor
Implements paragraph-level chunking for Supreme Court judgments per tasks.md requirements
- Extract text paragraph-by-paragraph using PyMuPDF
- Group consecutive paragraphs into windows until ~400-600 tokens
- Preserve paragraph/¶ numbers in text (key for citations)
- Create canonical IDs: SC:<YYYY>:<NeutralOrSCR>:<Slug>:Para:<number>
- Classify paragraphs into Facts/Issues/Analysis/Held/Order/Citations sections
"""
import re
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import date, datetime
import logging
import fitz  # PyMuPDF for better PDF extraction
from dataclasses import asdict

from legal_kb.models.legal_models import JudgmentChunk
from legal_kb.utils.text_processing import clean_legal_text, normalize_unicode

logger = logging.getLogger(__name__)

class SCJudgmentProcessor:
    """Processes Supreme Court judgments with paragraph-level chunking per tasks.md requirements"""
    
    def __init__(self):
        """Initialize SC judgment processor with legal-aware patterns"""
        
        # Paragraph detection patterns
        self.para_patterns = [
            re.compile(r'^(\d+)\.\s+(.+)', re.MULTILINE),  # "1. Text"
            re.compile(r'^\((\d+)\)\s+(.+)', re.MULTILINE),  # "(1) Text"
            re.compile(r'^¶\s*(\d+)\s+(.+)', re.MULTILINE),  # "¶ 1 Text"
            re.compile(r'^Para\s+(\d+)\s*[:.]\s*(.+)', re.MULTILINE | re.IGNORECASE)  # "Para 1: Text"
        ]
        
        # Case metadata patterns
        self.case_title_pattern = re.compile(r'^(.+?)\s+(?:v\.?|vs\.?|versus)\s+(.+?)(?:\s+and\s+.+)?$', re.IGNORECASE)
        self.citation_patterns = [
            re.compile(r'(\d{4})\s+SCC\s+OnLine\s+SC\s+(\d+)', re.IGNORECASE),
            re.compile(r'(\d{4})\s+(\d+)\s+SCC\s+(\d+)', re.IGNORECASE),
            re.compile(r'(\d{4})\s+SCR\s+\((\d+)\)\s+(\d+)', re.IGNORECASE),
            re.compile(r'AIR\s+(\d{4})\s+SC\s+(\d+)', re.IGNORECASE)
        ]
        
        # Bench composition pattern
        self.bench_pattern = re.compile(r'(?:Before|Coram):\s*(.+?)(?:\n|$)', re.IGNORECASE | re.MULTILINE)
        self.justice_pattern = re.compile(r'(?:Hon\'ble\s+)?(?:Mr\.\s+)?Justice\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', re.IGNORECASE)
        
        # Date patterns
        self.date_patterns = [
            re.compile(r'(?:Decided|Judgment\s+delivered)\s+on:?\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})', re.IGNORECASE),
            re.compile(r'Date\s+of\s+(?:Judgment|Decision):?\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})', re.IGNORECASE),
            re.compile(r'(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s+(\d{4})', re.IGNORECASE)
        ]
        
        # Section classification patterns
        self.section_keywords = {
            'Facts': ['facts', 'background', 'brief facts', 'factual matrix'],
            'Issue': ['issue', 'question', 'point for determination', 'questions framed'],
            'Analysis': ['analysis', 'discussion', 'reasoning', 'consideration', 'law'],
            'Held': ['held', 'conclusion', 'finding', 'decision'],
            'Order': ['order', 'direction', 'disposed', 'appeal allowed', 'appeal dismissed'],
            'Citations': ['citation', 'referred', 'relied upon', 'case law'],
            'Headnote': ['headnote', 'summary', 'synopsis']
        }
        
        # Statute reference patterns
        self.statute_patterns = [
            re.compile(r'Section\s+(\d+)\s+(?:of\s+)?(?:the\s+)?BNS', re.IGNORECASE),
            re.compile(r'Section\s+(\d+)\s+(?:of\s+)?(?:the\s+)?(?:Indian\s+Penal\s+Code|IPC)', re.IGNORECASE),
            re.compile(r'Section\s+(\d+)\s+(?:of\s+)?(?:the\s+)?(?:Code\s+of\s+Criminal\s+Procedure|CrPC)', re.IGNORECASE),
            re.compile(r'Article\s+(\d+)\s+(?:of\s+)?(?:the\s+)?Constitution', re.IGNORECASE)
        ]
    
    def process_judgment_text(self, text: str, source_file: str) -> Optional[Dict]:
        """
        Process Supreme Court judgment text with paragraph-level chunking per tasks.md
        Returns processed data ready for token-aware chunking
        """
        try:
            logger.info(f"Processing SC judgment: {source_file}")
            
            # Clean and normalize text - remove headers/footers, fix hyphenation
            cleaned_text = self._preprocess_text(text)
            
            # Extract metadata (case title, citations, bench, date)
            metadata = self._extract_judgment_metadata(cleaned_text, source_file)
            
            return {
                'content': cleaned_text,
                'title': metadata.get('case_title', 'Supreme Court Judgment'),
                'source_file': source_file,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process SC judgment {source_file}: {e}")
            return None
    
    def _extract_pdf_text_pymupdf(self, pdf_path: str) -> str:
        """Extract text from Supreme Court judgment PDF using PyMuPDF per tasks.md"""
        try:
            doc = fitz.open(pdf_path)
            text_content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text("text")
                
                # Remove page headers/footers while preserving paragraph numbers
                cleaned_page = self._remove_boilerplate(page_text, page_num)
                if cleaned_page.strip():
                    text_content.append(cleaned_page)
            
            doc.close()
            return '\n'.join(text_content)
                
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
            raise
    
    def _remove_boilerplate(self, page_text: str, page_num: int) -> str:
        """Remove page headers, footers, and boilerplate text per tasks.md requirements"""
        lines = page_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip common boilerplate patterns - remove "SUPREME COURT REPORTS" mastheads
            if any(pattern in line.lower() for pattern in [
                'supreme court reports',
                'supreme court cases', 
                'scc online',
                'page',
                'www.scconline.com',
                'printed for',
                'copyright',
                'supreme court of india'
            ]):
                continue
            
            # Skip page numbers but preserve paragraph numbers (¶ numbers are key for citations)
            if re.match(r'^\d+$', line) and len(line) < 4:  # Only standalone page numbers
                continue
                
            # Keep lines with paragraph markers like "1.", "(1)", "¶ 1"
            if len(line) >= 3:  # Keep meaningful content
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _preprocess_text(self, raw_text: str) -> str:
        """Clean and normalize extracted text per tasks.md requirements"""
        # Normalize Unicode and fix ligatures
        text = normalize_unicode(raw_text)
        
        # Collapse hyphenated line breaks ("con-\ntract" → "contract") per tasks.md
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        
        # Clean legal text
        text = clean_legal_text(text)
        
        # Fix common judgment formatting issues
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)  # Standalone page numbers
        
        return text
    
    def _extract_judgment_metadata(self, text: str, source_file: str) -> Dict:
        """Extract case metadata per tasks.md: bench, decision date, case title, citations"""
        metadata = {
            'case_title': None,
            'decision_date': None,
            'bench': [],
            'neutral_citation': None,
            'scr_citation': None,
            'court': 'Supreme Court of India',
            'source_file': source_file,
            'document_type': 'judgment'
        }
        
        # Extract case title (usually in first few lines)
        lines = text.split('\n')[:20]  # Check first 20 lines
        for line in lines:
            if ' v. ' in line or ' vs. ' in line or ' versus ' in line:
                title_match = self.case_title_pattern.match(line.strip())
                if title_match:
                    metadata['case_title'] = f"{title_match.group(1).strip()} v. {title_match.group(2).strip()}"
                    break
        
        # Extract citations
        for pattern in self.citation_patterns:
            matches = pattern.findall(text)
            if matches:
                match = matches[0]
                if 'SCC OnLine' in pattern.pattern:
                    metadata['neutral_citation'] = f"{match[0]} SCC OnLine SC {match[1]}"
                elif 'SCR' in pattern.pattern:
                    metadata['scr_citation'] = f"{match[0]} SCR ({match[1]}) {match[2]}"
                break
        
        # Extract bench composition
        bench_match = self.bench_pattern.search(text)
        if bench_match:
            bench_text = bench_match.group(1)
            justices = self.justice_pattern.findall(bench_text)
            metadata['bench'] = [f"Justice {justice}" for justice in justices]
        
        # Extract decision date
        for pattern in self.date_patterns:
            date_match = pattern.search(text)
            if date_match:
                try:
                    if len(date_match.groups()) == 3:
                        if date_match.group(2).isalpha():  # Month name format
                            month_names = {
                                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }
                            day = int(date_match.group(1))
                            month = month_names[date_match.group(2).lower()]
                            year = int(date_match.group(3))
                        else:  # Numeric format
                            day = int(date_match.group(1))
                            month = int(date_match.group(2))
                            year = int(date_match.group(3))
                        
                        metadata['decision_date'] = date(year, month, day)
                        break
                except (ValueError, KeyError):
                    continue
        
        return metadata
    
    async def _detect_paragraphs(self, text: str) -> List[Dict]:
        """Detect paragraph boundaries using numbering markers"""
        paragraphs = []
        lines = text.split('\n')
        current_para = None
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check for paragraph markers
            para_match = None
            for pattern in self.para_patterns:
                match = pattern.match(line)
                if match:
                    para_match = match
                    break
            
            if para_match:
                # Save previous paragraph
                if current_para:
                    paragraphs.append(current_para)
                
                # Start new paragraph
                current_para = {
                    'number': para_match.group(1),
                    'text': line,
                    'start_line': line_num,
                    'section_type': None
                }
            elif current_para:
                # Continue current paragraph
                current_para['text'] += '\n' + line
            else:
                # Text before first numbered paragraph
                if not paragraphs:
                    paragraphs.append({
                        'number': '0',
                        'text': line,
                        'start_line': line_num,
                        'section_type': 'Headnote'
                    })
        
        # Add final paragraph
        if current_para:
            paragraphs.append(current_para)
        
        # Classify paragraph sections
        for para in paragraphs:
            if para['section_type'] is None:
                para['section_type'] = await self._classify_paragraph_section(para['text'], para.get('number', '0'))
        
        return paragraphs
    
    async def _classify_paragraph_section(self, text: str, para_number: str) -> str:
        """Classify paragraph into judgment section type"""
        text_lower = text.lower()
        
        # Check for explicit section headers
        for section, keywords in self.section_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return section
        
        # Heuristic classification based on position and content
        try:
            para_num = int(para_number)
            
            # Early paragraphs often contain facts
            if para_num <= 5:
                if any(word in text_lower for word in ['fact', 'background', 'brief']):
                    return 'Facts'
            
            # Look for legal analysis indicators
            if any(phrase in text_lower for phrase in ['law is', 'legal principle', 'established', 'precedent']):
                return 'Analysis'
            
            # Look for conclusion indicators
            if any(phrase in text_lower for phrase in ['conclude', 'find', 'hold', 'decided']):
                return 'Held'
            
            # Look for order indicators
            if any(phrase in text_lower for phrase in ['order', 'direct', 'dispose', 'allow', 'dismiss']):
                return 'Order'
                
        except ValueError:
            pass
        
        # Default to analysis for numbered paragraphs
        return 'Analysis'
    
    async def _create_paragraph_chunk(self, paragraph: Dict, metadata: Dict, year: int, pdf_path: str) -> Optional[JudgmentChunk]:
        """Create judgment chunk from paragraph"""
        try:
            # Generate document ID
            case_slug = self._generate_case_slug(metadata.get('case_title', 'Unknown'))
            doc_id = f"SC:{year}:{case_slug}:Para:{paragraph['number']}"
            
            # Extract citations
            statute_refs = await self._extract_statute_references(paragraph['text'])
            case_refs = await self._extract_case_references(paragraph['text'])
            
            chunk = JudgmentChunk(
                id=doc_id,
                type="judgment_para",
                court=metadata['court'],
                decision_date=metadata.get('decision_date', date(year, 1, 1)),
                bench=metadata.get('bench', []),
                case_title=metadata.get('case_title', 'Unknown Case'),
                citation_neutral=metadata.get('neutral_citation'),
                scr_citation=metadata.get('scr_citation'),
                para_no=str(paragraph['number']),
                section=paragraph['section_type'],
                text=paragraph['text'],
                statute_refs=statute_refs,
                case_refs=case_refs,
                url=f"https://main.sci.gov.in/supremecourt/{year}/{pdf_path}",
                sha256=self._compute_hash(paragraph['text']),
                embedding=[],  # Will be populated by embedding service
                token_count=len(paragraph['text'].split())
            )
            
            return chunk
            
        except Exception as e:
            logger.error(f"Failed to create paragraph chunk: {e}")
            return None
    
    def _generate_case_slug(self, case_title: str) -> str:
        """Generate URL-friendly case slug"""
        if not case_title or case_title == 'Unknown Case':
            return 'UnknownCase'
        
        # Take first few words and clean them
        words = case_title.split()[:3]  # First 3 words
        slug_parts = []
        
        for word in words:
            # Remove special characters and keep only alphanumeric
            clean_word = re.sub(r'[^a-zA-Z0-9]', '', word)
            if clean_word:
                slug_parts.append(clean_word.capitalize())
        
        return ''.join(slug_parts) if slug_parts else 'UnknownCase'
    
    async def _extract_statute_references(self, text: str) -> List[str]:
        """Extract and normalize statute references"""
        references = []
        
        for pattern in self.statute_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if 'BNS' in pattern.pattern:
                    ref_id = f"BNS:2023:Sec:{match}"
                elif 'IPC' in pattern.pattern:
                    ref_id = f"IPC:1860:Sec:{match}"
                elif 'CrPC' in pattern.pattern:
                    ref_id = f"CrPC:1973:Sec:{match}"
                elif 'Constitution' in pattern.pattern:
                    ref_id = f"CONSTITUTION:1950:Art:{match}"
                else:
                    continue
                
                if ref_id not in references:
                    references.append(ref_id)
        
        return references
    
    async def _extract_case_references(self, text: str) -> List[str]:
        """Extract case citations and normalize them"""
        references = []
        
        # Simple citation detection
        citation_patterns = [
            re.compile(r'\d{4}\s+SCC\s+OnLine\s+\w+\s+\d+', re.IGNORECASE),
            re.compile(r'\d{4}\s+\d+\s+SCC\s+\d+', re.IGNORECASE),
            re.compile(r'AIR\s+\d{4}\s+SC\s+\d+', re.IGNORECASE)
        ]
        
        for pattern in citation_patterns:
            matches = pattern.findall(text)
            for match in matches:
                normalized = re.sub(r'\s+', ' ', match.strip())
                if normalized not in references:
                    references.append(normalized)
        
        return references
    
    def _compute_hash(self, text: str) -> str:
        """Compute SHA256 hash of text content"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    async def _process_and_store_chunks(self, chunks: List[JudgmentChunk]) -> List[JudgmentChunk]:
        """Generate embeddings and store chunks in database"""
        processed_chunks = []
        
        for chunk in chunks:
            try:
                # Generate embedding
                embedding = await self.embedding_service.get_embedding(chunk.text)
                chunk.embedding = embedding
                
                # Store in database
                await self._store_chunk_in_db(chunk)
                processed_chunks.append(chunk)
                
                logger.debug(f"Processed and stored chunk: {chunk.id}")
                
            except Exception as e:
                logger.error(f"Failed to process chunk {chunk.id}: {e}")
                continue
        
        return processed_chunks
    
    async def _store_chunk_in_db(self, chunk: JudgmentChunk):
        """Store judgment chunk in database"""
        async with self.db_manager.get_postgres_connection() as conn:
            import json
            await conn.execute("""
                INSERT INTO case_chunks (
                    id, type, court, decision_date, bench, case_title, citation_neutral,
                    scr_citation, para_no, para_no_int, section, text, statute_refs,
                    case_refs, url, sha256, embedding, token_count
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                ON CONFLICT (id) DO UPDATE SET
                    text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
            """, 
                chunk.id, chunk.type, chunk.court, chunk.decision_date, 
                json.dumps(chunk.bench),  # Convert list to JSON string
                chunk.case_title, chunk.citation_neutral, chunk.scr_citation,
                chunk.para_no, int(chunk.para_no) if chunk.para_no.isdigit() else 0,
                chunk.section, chunk.text, 
                json.dumps(chunk.statute_refs),  # Convert list to JSON string
                json.dumps(chunk.case_refs),     # Convert list to JSON string
                chunk.url, chunk.sha256, chunk.embedding, chunk.token_count
            )