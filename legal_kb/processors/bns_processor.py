"""
BNS (Bharatiya Nyaya Sanhita) Statute Processor
Implements legal-aware chunking for BNS Act 45 of 2023 per tasks.md requirements
- One legal unit per chunk: Section → Sub-section → Illustration → Explanation → Proviso
- Do not glue multiple sections together
- Generate canonical IDs: BNS:2023:Sec:<number>[:Sub:<clause>]
- Set effective_from as "2024-07-01" and effective_to as null
"""
import re
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import date
import logging
import fitz  # PyMuPDF for better PDF extraction

from legal_kb.models.legal_models import StatuteChunk, DocumentType, SubunitType
from legal_kb.utils.text_processing import clean_legal_text, normalize_unicode

logger = logging.getLogger(__name__)

class BNSProcessor:
    """Processes BNS PDF with legal-aware chunking per tasks.md requirements"""
    
    def __init__(self):
        """Initialize BNS processor with legal unit patterns"""
        
        # Regex patterns for legal structure detection
        self.section_pattern = re.compile(r'^(\d+)\.\s*(.+?)\.?\s*—\s*(.+)', re.MULTILINE)
        self.subsection_pattern = re.compile(r'^\((\d+)\)\s*(.+)', re.MULTILINE)
        self.illustration_pattern = re.compile(r'^Illustration[s]?\s*\.?\s*—?\s*(.+)', re.MULTILINE | re.IGNORECASE)
        self.explanation_pattern = re.compile(r'^Explanation[s]?\s*\.?\s*—?\s*(.+)', re.MULTILINE | re.IGNORECASE)
        self.proviso_pattern = re.compile(r'^Proviso\s*\.?\s*—?\s*(.+)', re.MULTILINE | re.IGNORECASE)
        self.cross_ref_pattern = re.compile(r'section\s+(\d+)', re.IGNORECASE)
        
    def process_bns_text(self, text: str, source_file: str) -> Optional[Dict]:
        """
        Process BNS text with legal-aware chunking per tasks.md
        Creates one chunk per legal unit (Section/Sub-section/Illustration/Explanation/Proviso)
        Returns processed data ready for token-aware chunking
        """
        try:
            logger.info(f"Processing BNS document: {source_file}")
            
            # Clean and normalize text
            cleaned_text = self._preprocess_text(text)
            
            # Extract metadata
            metadata = self._extract_metadata(cleaned_text, source_file)
            
            return {
                'content': cleaned_text,
                'title': metadata.get('title', 'Bharatiya Nyaya Sanhita'),
                'source_file': source_file,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process BNS text {source_file}: {e}")
            return None
    
    def _extract_pdf_text_pymupdf(self, pdf_path: str) -> str:
        """Extract text from BNS PDF file using PyMuPDF per tasks.md"""
        try:
            doc = fitz.open(pdf_path)
            text_content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text("text")
                
                # Remove page headers/footers
                cleaned_page = self._remove_boilerplate(page_text, page_num)
                if cleaned_page.strip():
                    text_content.append(cleaned_page)
            
            doc.close()
            return '\n'.join(text_content)
                
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
            raise
    
    def _remove_boilerplate(self, page_text: str, page_num: int) -> str:
        """Remove page headers, footers, and boilerplate text"""
        lines = page_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip common boilerplate patterns
            if any(pattern in line.lower() for pattern in [
                'bharatiya nyaya sanhita',
                'act no. 45 of 2023',
                'page',
                'gazette of india',
                'extraordinary',
                'part ii',
                'section 1'
            ]):
                continue
            
            # Skip page numbers
            if re.match(r'^\d+$', line):
                continue
            
            # Skip very short lines (likely artifacts)
            if len(line) < 3:
                continue
            
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
        
        # Fix common OCR errors in legal text
        text = re.sub(r'\bsection\s+(\d+)', r'section \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\bchapter\s+(\d+)', r'Chapter \1', text, flags=re.IGNORECASE)
        
        # Normalize section numbering
        text = re.sub(r'^(\d+)\s*\.\s*', r'\1. ', text, flags=re.MULTILINE)
        
        return text
    
    def _extract_metadata(self, text: str, source_file: str) -> Dict:
        """Extract metadata from BNS text per tasks.md requirements"""
        metadata = {
            'source_file': source_file,
            'document_type': 'statute',
            'act': 'BNS',
            'year': 2023,
            'effective_from': '2024-07-01',  # Per tasks.md requirements
            'effective_to': None  # Per tasks.md requirements
        }
        
        # Try to extract title
        lines = text.split('\n')[:10]
        for line in lines:
            if 'bharatiya nyaya sanhita' in line.lower() or 'bns' in line.lower():
                metadata['title'] = line.strip()[:200]
                break
        
        return metadata
    
    async def _parse_sections(self, text: str) -> List[Dict]:
        """Parse BNS text into structured sections"""
        sections = []
        current_section = None
        
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for section header
            section_match = self.section_pattern.match(line)
            if section_match:
                # Save previous section
                if current_section:
                    sections.append(current_section)
                
                # Start new section
                section_num = section_match.group(1)
                section_title = section_match.group(3).strip()
                
                current_section = {
                    'number': section_num,
                    'title': section_title,
                    'text': line,
                    'sub_units': []
                }
                
                i += 1
                continue
            
            # If we're in a section, collect content
            if current_section and line:
                # Check for sub-units
                if self._is_illustration(line):
                    sub_unit = await self._parse_illustration(lines, i)
                    current_section['sub_units'].append(sub_unit)
                    i += sub_unit.get('lines_consumed', 1)
                elif self._is_explanation(line):
                    sub_unit = await self._parse_explanation(lines, i)
                    current_section['sub_units'].append(sub_unit)
                    i += sub_unit.get('lines_consumed', 1)
                elif self._is_proviso(line):
                    sub_unit = await self._parse_proviso(lines, i)
                    current_section['sub_units'].append(sub_unit)
                    i += sub_unit.get('lines_consumed', 1)
                else:
                    # Add to main section text
                    current_section['text'] += '\n' + line
                    i += 1
            else:
                i += 1
        
        # Add final section
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def _is_illustration(self, line: str) -> bool:
        """Check if line starts an illustration"""
        return bool(self.illustration_pattern.match(line))
    
    def _is_explanation(self, line: str) -> bool:
        """Check if line starts an explanation"""
        return bool(self.explanation_pattern.match(line))
    
    def _is_proviso(self, line: str) -> bool:
        """Check if line starts a proviso"""
        return bool(self.proviso_pattern.match(line))
    
    async def _parse_illustration(self, lines: List[str], start_idx: int) -> Dict:
        """Parse illustration sub-unit"""
        text_lines = [lines[start_idx]]
        i = start_idx + 1
        
        # Collect illustration text until next section or sub-unit
        while i < len(lines):
            line = lines[i].strip()
            if (self._is_section_start(line) or 
                self._is_explanation(line) or 
                self._is_proviso(line)):
                break
            
            if line:
                text_lines.append(line)
            i += 1
        
        return {
            'type': 'Illustration',
            'text': '\n'.join(text_lines),
            'lines_consumed': i - start_idx
        }
    
    async def _parse_explanation(self, lines: List[str], start_idx: int) -> Dict:
        """Parse explanation sub-unit"""
        text_lines = [lines[start_idx]]
        i = start_idx + 1
        
        while i < len(lines):
            line = lines[i].strip()
            if (self._is_section_start(line) or 
                self._is_illustration(line) or 
                self._is_proviso(line)):
                break
            
            if line:
                text_lines.append(line)
            i += 1
        
        return {
            'type': 'Explanation',
            'text': '\n'.join(text_lines),
            'lines_consumed': i - start_idx
        }
    
    async def _parse_proviso(self, lines: List[str], start_idx: int) -> Dict:
        """Parse proviso sub-unit"""
        text_lines = [lines[start_idx]]
        i = start_idx + 1
        
        while i < len(lines):
            line = lines[i].strip()
            if (self._is_section_start(line) or 
                self._is_illustration(line) or 
                self._is_explanation(line)):
                break
            
            if line:
                text_lines.append(line)
            i += 1
        
        return {
            'type': 'Proviso',
            'text': '\n'.join(text_lines),
            'lines_consumed': i - start_idx
        }
    
    def _is_section_start(self, line: str) -> bool:
        """Check if line starts a new section"""
        return bool(self.section_pattern.match(line))
    
    async def _create_section_chunks(self, section: Dict) -> List[StatuteChunk]:
        """Create statute chunks for a section and its sub-units"""
        chunks = []
        
        # Create main section chunk
        section_chunk = StatuteChunk(
            id=f"BNS:2023:Sec:{section['number']}",
            type="statute_section",
            act="BNS",
            year=2023,
            title=section['title'],
            section=section['number'],
            subunit="Section",
            text=section['text'],
            effective_from=date(2024, 7, 1),  # BNS effective date
            effective_to=None,
            citations=await self._extract_cross_references(section['text']),
            url="https://indiacode.nic.in/handle/123456789/15436",
            sha256=self._compute_hash(section['text']),
            embedding=[],  # Will be populated by embedding service
            token_count=len(section['text'].split())
        )
        chunks.append(section_chunk)
        
        # Create sub-unit chunks
        for idx, sub_unit in enumerate(section['sub_units']):
            sub_chunk = StatuteChunk(
                id=f"BNS:2023:Sec:{section['number']}:{sub_unit['type']}:{idx+1}",
                type="statute_subsection",
                act="BNS",
                year=2023,
                title=f"{section['title']} - {sub_unit['type']}",
                section=section['number'],
                subunit=sub_unit['type'],
                text=sub_unit['text'],
                effective_from=date(2024, 7, 1),
                effective_to=None,
                citations=await self._extract_cross_references(sub_unit['text']),
                url="https://indiacode.nic.in/handle/123456789/15436",
                sha256=self._compute_hash(sub_unit['text']),
                embedding=[],
                token_count=len(sub_unit['text'].split())
            )
            chunks.append(sub_chunk)
        
        return chunks
    
    async def _extract_cross_references(self, text: str) -> List[str]:
        """Extract cross-references to other BNS sections"""
        references = []
        
        # Find section references
        matches = self.cross_ref_pattern.findall(text)
        for match in matches:
            ref_id = f"BNS:2023:Sec:{match}"
            if ref_id not in references:
                references.append(ref_id)
        
        return references
    
    def _compute_hash(self, text: str) -> str:
        """Compute SHA256 hash of text content"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    async def _process_and_store_chunks(self, chunks: List[StatuteChunk]) -> List[StatuteChunk]:
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
    
    async def _store_chunk_in_db(self, chunk: StatuteChunk):
        """Store statute chunk in database"""
        async with self.db_manager.get_postgres_connection() as conn:
            import json
            await conn.execute("""
                INSERT INTO statute_chunks (
                    id, type, act, year, title, section, section_no, subunit, text,
                    effective_from, effective_to, citations, url, sha256, embedding, token_count
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (id) DO UPDATE SET
                    text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
            """, 
                chunk.id, chunk.type, chunk.act, chunk.year, chunk.title, 
                chunk.section, int(chunk.section), chunk.subunit, chunk.text,
                chunk.effective_from, chunk.effective_to, json.dumps(chunk.citations), 
                chunk.url, chunk.sha256, chunk.embedding, chunk.token_count
            )