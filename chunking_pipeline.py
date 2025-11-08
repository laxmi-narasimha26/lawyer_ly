#!/usr/bin/env python3
"""
Chunking & Pre-Embedding Pipeline
Implements exact specifications for processing Supreme Court judgments (2020) and BNS bare act
Outputs JSONL files ready for embedding (no API calls)
"""

import os
import sys
import json
import hashlib
import unicodedata
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import logging

# Required libraries
import fitz  # PyMuPDF
import tiktoken

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global constants (hard rules)
TARGET_CHUNK_LENGTH_MIN = 400
TARGET_CHUNK_LENGTH_MAX = 600
HARD_MAXIMUM_TOKENS = 800
OVERLAP_TOKENS = 80
MINIMUM_TOKENS = 80
TEXT_DENSITY_THRESHOLD = 0.6

# Initialize tokenizer
tokenizer = tiktoken.get_encoding("cl100k_base")

@dataclass
class JudgmentChunk:
    """Judgment chunk model following exact specification"""
    id: str
    type: str  # judgment_window
    doc_id: str
    order: int
    text: str
    tokens: int
    overlap_tokens: int
    case_title: Optional[str]
    decision_date: Optional[str]  # YYYY-MM-DD
    bench: List[str]
    citation_strings: List[str]
    para_range: Optional[str]
    source_path: str
    sha256: str

@dataclass
class StatuteChunk:
    """Statute chunk model following exact specification"""
    id: str
    type: str  # statute_unit
    doc_id: str
    order: int
    act: str
    year: int
    section_no: str
    unit_type: str  # Section|Sub-section|Illustration|Explanation|Proviso
    title: Optional[str]
    text: str
    tokens: int
    effective_from: str  # 2024-07-01
    effective_to: Optional[str]  # null
    source_path: str
    sha256: str

@dataclass
class ChunkingSummary:
    """Summary report model"""
    processed_docs: int
    total_chunks_emitted: int
    p50_tokens: int
    p95_tokens: int
    max_tokens: int
    min_tokens: int
    dropped_too_small: int
    dropped_too_large: int
    ocr_pages: int
    errors: List[str]

class TextExtractor:
    """PDF text extraction with PyMuPDF and OCR fallback"""
    
    def extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text using PyMuPDF with per-page density gate.
        OCR is optional and disabled by default via OCR_MODE env.
        When OCR is disabled or unavailable, non-textful pages are skipped (ignored).
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = doc.page_count
            page_texts: List[str] = []
            skipped_indices: List[int] = []

            # First pass: compute per-page text metrics
            textful_flags: List[bool] = []
            for i in range(total_pages):
                page = doc[i]
                rd = page.get_text("rawdict")
                # collect all spans
                spans = []
                for blk in rd.get("blocks", []):
                    if blk.get("type") == 0:  # text block
                        for ln in blk.get("lines", []):
                            for sp in ln.get("spans", []):
                                spans.append(sp)
                # Per approval: char_count from page.get_text() length
                char_count = len(page.get_text() or "")
                def _area(bb):
                    try:
                        x0, y0, x1, y1 = bb
                        return max(0.0, (x1 - x0)) * max(0.0, (y1 - y0))
                    except Exception:
                        return 0.0
                text_area = sum(_area(sp.get("bbox", (0, 0, 0, 0))) for sp in spans)
                rect = page.rect
                page_area = max(1.0, (rect.x1 - rect.x0) * (rect.y1 - rect.y0))
                page_text_coverage = (text_area / page_area)
                is_textful = (char_count >= 500) and (page_text_coverage >= 0.12)
                textful_flags.append(is_textful)

            textful_ratio = (sum(1 for f in textful_flags if f) / float(total_pages)) if total_pages else 0.0

            # Determine OCR policy
            ocr_mode = os.environ.get('OCR_MODE', 'disabled').lower()
            skip_ocr = True if ocr_mode == 'disabled' else False

            # Second pass: extract text with OCR on non-textful pages
            for i in range(total_pages):
                page = doc[i]
                if not textful_flags[i]:
                    if skip_ocr:
                        # ignore non-textful pages when OCR disabled
                        skipped_indices.append(i)
                        page_texts.append("")
                    else:
                        # Placeholder for OCR if ever enabled; currently not used
                        page_texts.append("")
                        skipped_indices.append(i)
                else:
                    txt = page.get_text() or ""
                    page_texts.append(txt)

            doc.close()
            raw_text = "\n\n".join([t for t in page_texts if t.strip()])

            cleaned_text = self._clean_text(raw_text)

            # Record run metrics for logs/summary consumers
            self.last_ocr_pages = 0  # OCR disabled
            self.last_ocr_indices = []
            self.last_skipped_pages = len(skipped_indices)
            self.last_skipped_indices = skipped_indices
            self.last_textful_ratio = textful_ratio

            logger.info(
                f"Extracted text from {pdf_path}: chars={len(cleaned_text)}, textful_ratio={textful_ratio:.2f}, "
                f"pages_skipped={len(skipped_indices)}, skipped_indices={skipped_indices}, OCR_MODE={ocr_mode}"
            )
            if skipped_indices:
                logger.info(f"IGNORED_PAGES: {skipped_indices}  (no OCR; OCR_MODE={ocr_mode})")
            return cleaned_text
        
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""
    
    def _calculate_text_density(self, page, text: str) -> float:
        """Calculate text density to determine if OCR is needed"""
        if not text.strip():
            return 0.0
        
        # Simple heuristic: characters per unit area
        page_area = page.rect.width * page.rect.height
        char_count = len(text.strip())
        
        if page_area == 0:
            return 0.0
        
        density = char_count / page_area * 10000  # Scale factor
        return min(density, 1.0)
    
    # OCR is disabled in this configuration (PyMuPDF-only extraction)
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted PDF text according to specifications"""
        # Remove running headers/footers, page numbers, mastheads
        text = re.sub(r'SUPREME COURT REPORTS.*?\n', '', text, flags=re.IGNORECASE)
        text = re.sub(r'SUPREME COURT OF INDIA.*?\n', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Page \d+ of \d+', '', text)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Collapse hyphenated line breaks (con-\ntract â†’ contract)
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        
        # Remove form feed and other PDF artifacts
        text = text.replace('\x0c', '')
        text = text.replace('\uf0b7', 'â€¢')
        
        # Normalize encoding to NFC and strip non-printable characters
        text = unicodedata.normalize('NFC', text)
        text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\t ')
        
        # Normalize whitespace but preserve paragraph numbers
        text = re.sub(r'[ \t]+', ' ', text)  # Collapse spaces/tabs
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Collapse multiple newlines
        
        return text.strip()

class JudgmentProcessor:
    """Supreme Court judgment processor with paragraph windows"""
    
    def __init__(self, text_extractor: TextExtractor):
        self.text_extractor = text_extractor
        self.current_metadata: Optional[Dict[str, Any]] = None
        self._order_counter: Dict[str, int] = {}
    
    def process_judgment_pdf(self, pdf_path: str) -> List[JudgmentChunk]:
        """Process judgment PDF with paragraph-level chunking"""
        try:
            # Extract text
            raw_text = self.text_extractor.extract_pdf_text(pdf_path)
            if not raw_text or len(raw_text.strip()) < 100:
                logger.warning(f"Insufficient text extracted from {pdf_path}")
                return []
            
            # Extract metadata
            metadata = self._extract_metadata(raw_text)
            
            # Extract paragraphs
            paragraphs = self._extract_paragraphs(raw_text)
            
            # Build windows with overlap
            self.current_metadata = dict(metadata)
            self.current_metadata['source_path'] = pdf_path
            try:
                chunks = self._build_paragraph_windows(paragraphs, pdf_path, metadata)
            finally:
                self.current_metadata = None
            
            # Validate chunks
            validated_chunks = self._validate_chunks(chunks)
            
            logger.info(f"Processed {pdf_path}: {len(validated_chunks)} chunks")
            return validated_chunks
            
        except Exception as e:
            logger.error(f"Failed to process judgment {pdf_path}: {e}")
            return []
    
    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """Extract judgment metadata"""
        metadata = {
            'case_title': None,
            'decision_date': None,
            'bench': [],
            'citation_strings': []
        }
        
        # Extract case title (look for "v." pattern or centered capitalized lines)
        case_title_match = re.search(r'([A-Z][A-Za-z\s&]+)\s+v\.?\s+([A-Z][A-Za-z\s&]+)', text[:2000])
        if case_title_match:
            metadata['case_title'] = f"{case_title_match.group(1).strip()} v. {case_title_match.group(2).strip()}"
        
        # Extract decision date (YYYY-MM-DD format)
        date_patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',
            r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})'
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, text[:2000], re.IGNORECASE)
            if date_match:
                try:
                    if len(date_match.groups()) == 3:
                        if date_match.group(2).isalpha():  # Month name format
                            day, month_name, year = date_match.groups()
                            month_map = {
                                'january': '01', 'february': '02', 'march': '03', 'april': '04',
                                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                                'september': '09', 'october': '10', 'november': '11', 'december': '12'
                            }
                            month = month_map.get(month_name.lower(), '01')
                            metadata['decision_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        else:
                            # Numeric format - assume first match is correct format
                            parts = date_match.groups()
                            if len(parts[0]) == 4:  # YYYY-MM-DD
                                metadata['decision_date'] = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                            else:  # DD-MM-YYYY
                                metadata['decision_date'] = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                        break
                except:
                    continue
        
        # Extract bench (Justice names)
        justice_pattern = r'Justice\s+([A-Z][a-zA-Z\s\.]+?)(?=\s*(?:Justice|,|\n|$))'
        justice_matches = re.findall(justice_pattern, text[:3000])
        metadata['bench'] = [f"Justice {name.strip()}" for name in justice_matches[:5]]  # Limit to 5
        
        # Extract citation strings
        citation_patterns = [
            r'\(\d{4}\)\s+\d+\s+SCC\s+\d+',
            r'\d{4}\s+SCC\s+OnLine\s+SC\s+\d+',
            r'\(\d{4}\)\s+\d+\s+SCR\s+\d+',
            r'\d{4}\s+AIR\s+SC\s+\d+'
        ]
        
        for pattern in citation_patterns:
            citations = re.findall(pattern, text[:5000])
            metadata['citation_strings'].extend(citations)
        
        return metadata
    
    def _extract_paragraphs(self, text: str) -> List[Dict[str, Any]]:
        """Extract paragraphs with numbering detection"""
        paragraphs = []
        
        # Split by visual paragraph (blank lines / vertical gaps)
        para_blocks = re.split(r'\n\s*\n', text)
        
        para_number = 1
        for block in para_blocks:
            block = block.strip()
            if not block or len(block) < 20:  # Skip very short blocks
                continue
            
            # Detect paragraph numbering
            para_range = None
            number_match = re.match(r'^(\d+)\.?\s+', block)
            if number_match:
                para_range = f"Â¶ {number_match.group(1)}"
                para_number = int(number_match.group(1))
            else:
                # Look for other numbering patterns
                other_patterns = [
                    r'^Â¶\s*(\d+)',
                    r'^\((\d+)\)',
                    r'^(\d+)\)'
                ]
                for pattern in other_patterns:
                    match = re.match(pattern, block)
                    if match:
                        para_range = f"Â¶ {match.group(1)}"
                        para_number = int(match.group(1))
                        break
            
            paragraphs.append({
                'number': para_number,
                'text': block,
                'para_range': para_range
            })
            para_number += 1
        
        return paragraphs
    
    def _build_paragraph_windows(self, paragraphs: List[Dict], pdf_path: str, metadata: Dict) -> List[JudgmentChunk]:
        """Wrapper: delegate to strict v2 loop."""
        filename_stem = Path(pdf_path).stem
        year = self._extract_year_from_filename(filename_stem)
        doc_id = f"SC:{year}:{filename_stem}"
        return self._build_paragraph_windows_v2(doc_id, paragraphs)

    def _build_paragraph_windows_v2(self, doc_id: str, paragraphs: List[Dict]) -> List[JudgmentChunk]:
        windows: List[JudgmentChunk] = []
        current_parts: List[str] = []
        current_tokens = 0
        if not hasattr(self, "_order_counter"):
            self._order_counter = {}
        self._order_counter[doc_id] = 1

        i = 0
        while i < len(paragraphs):
            para = paragraphs[i] or {}
            para_text = para.get("text", "").strip()
            joined = ("\n\n".join(current_parts + [para_text])).strip()
            current_tokens = len(tokenizer.encode(joined))

            if current_tokens > HARD_MAXIMUM_TOKENS:
                if current_parts:
                    chunk = self._make_chunk(doc_id, current_parts)
                    self._accept_or_merge_small(chunk, windows, doc_id, stats=getattr(self, "stats_ref", None))
                    current_parts, current_tokens = [], 0
                self._split_large_paragraph(doc_id, para_text, windows, para_range_hint=para.get("para_no"))
                i += 1
                continue

            current_parts.append(para_text)

            next_para = paragraphs[i + 1] if (i + 1) < len(paragraphs) else None
            next_text = (next_para or {}).get("text", "").strip() if next_para is not None else None
            next_tokens = len(tokenizer.encode(("\n\n".join(current_parts + [next_text])).strip())) if next_text else None

            should_close = False
            if current_tokens >= 500:
                should_close = True
            elif next_tokens is not None and next_tokens > 600:
                should_close = True
            if should_close and current_tokens < 400 and next_tokens is not None and next_tokens <= HARD_MAXIMUM_TOKENS:
                should_close = False

            if should_close:
                chunk = self._make_chunk(doc_id, current_parts)
                self._accept_or_merge_small(chunk, windows, doc_id, stats=getattr(self, "stats_ref", None))
                if windows:
                    target_chunk = windows[-1]
                    overlap_text = self._start_overlap_for_next_window(target_chunk.text, next_text)
                    overlap_used = len(tokenizer.encode(overlap_text)) if overlap_text else 0
                    target_chunk.overlap_tokens = overlap_used
                else:
                    overlap_text = ""
                current_parts = [overlap_text] if overlap_text else []
                current_tokens = len(tokenizer.encode("\n\n".join(current_parts))) if current_parts else 0

            i += 1

        if current_parts:
            chunk = self._make_chunk(doc_id, current_parts)
            self._accept_or_merge_small(chunk, windows, doc_id, stats=getattr(self, "stats_ref", None))
            if windows:
                windows[-1].overlap_tokens = 0

        if windows:
            assert all(80 <= c.tokens <= HARD_MAXIMUM_TOKENS for c in windows), f"Token gate breach in {doc_id}"
        return windows

    def _start_overlap_for_next_window(self, prev_text: str, next_para_text: Optional[str]) -> str:
        next_tokens = len(tokenizer.encode(next_para_text)) if next_para_text else 0
        desired = 520 - next_tokens
        overlap_n = max(0, min(OVERLAP_TOKENS, desired))
        if overlap_n <= 0:
            return ""
        return self._take_tail_tokens(prev_text, overlap_n)

    def _take_tail_tokens(self, text: str, n_tokens: int) -> str:
        toks = tokenizer.encode(text)
        if not toks:
            return ""
        return tokenizer.decode(toks[-n_tokens:])

    def _next_order_for(self, doc_id: str) -> int:
        if not hasattr(self, "_order_counter"):
            self._order_counter = {}
        order = self._order_counter.get(doc_id, 1)
        self._order_counter[doc_id] = order + 1
        return order

    def _derive_para_range(self, parts: List[str], hint: Optional[str] = None) -> Optional[str]:
        if not parts:
            return hint
        f = re.search(r"(\d+)", parts[0])
        l = re.search(r"(\d+)", parts[-1])
        if f and l:
            para_symbol = "\u00B6"
            if f.group(1) == l.group(1):
                return f"{para_symbol} {f.group(1)}"
            return f"{para_symbol}{para_symbol} {f.group(1)}–{l.group(1)}"
        return hint

    def _make_chunk(self, doc_id: str, parts: List[str], para_range_hint: Optional[str] = None, part: Optional[str] = None) -> JudgmentChunk:
        text = "\n\n".join(parts).strip()
        order = self._next_order_for(doc_id)
        chunk_id = f"{doc_id}:chunk:{order:04d}"
        pr = self._derive_para_range(parts, para_range_hint)
        if part:
            pr = f"{pr} {part}" if pr else part
        meta = getattr(self, 'current_metadata', {}) or {}
        case_title = meta.get('case_title')
        decision_date = meta.get('decision_date')
        bench = list(meta.get('bench', []))
        citations = list(meta.get('citation_strings', []))
        source_path = meta.get('source_path', "")
        return JudgmentChunk(
            id=chunk_id,
            type="judgment_window",
            doc_id=doc_id,
            order=order,
            text=text,
            tokens=len(tokenizer.encode(text)),
            overlap_tokens=0,
            case_title=case_title,
            decision_date=decision_date,
            bench=bench,
            citation_strings=citations,
            para_range=pr,
            source_path=source_path,
            sha256=hashlib.sha256(text.encode('utf-8')).hexdigest()
        )

    def _accept_or_merge_small(self, new_chunk: Optional[JudgmentChunk], chunks: List[JudgmentChunk], doc_id: str, stats: Optional[Dict] = None):
        text = (new_chunk.text if new_chunk else '') if new_chunk else ''
        if not new_chunk or not text.strip() or len(text.strip()) < 20:
            if stats is not None:
                stats['dropped_too_small'] = stats.get('dropped_too_small', 0) + 1
                stats['dropped_too_small_events'].append({
                    'doc_id': doc_id,
                    'chunk_id': getattr(new_chunk, 'id', 'NA'),
                    'tokens': len(tokenizer.encode(text)) if text else 0,
                    'reason': 'empty_or_whitespace',
                    'excerpt': text.strip()[:200] if text else ''
                })
            logger.info(f"DROPPED_TAIL: doc={doc_id} tail={getattr(new_chunk, 'id', 'NA')} tokens=0")
            return
        new_chunk.tokens = len(tokenizer.encode(text))
        if new_chunk.tokens > HARD_MAXIMUM_TOKENS:
            logger.warning("Oversized chunk detected: %s tokens=%s; attempting resplit", new_chunk.id, new_chunk.tokens)
            if hasattr(self, "_order_counter"):
                self._order_counter[doc_id] = new_chunk.order
            self._split_large_paragraph(
                doc_id,
                new_chunk.text,
                chunks,
                para_range_hint=new_chunk.para_range,
            )
            return
        if new_chunk.tokens >= MINIMUM_TOKENS:
            chunks.append(new_chunk)
            return
        if chunks and (chunks[-1].tokens + new_chunk.tokens) <= HARD_MAXIMUM_TOKENS:
            prev = chunks[-1]
            merged_text = (prev.text + "\n\n" + text).strip()
            prev.text = merged_text
            prev.tokens = len(tokenizer.encode(merged_text))
            prev.sha256 = hashlib.sha256(merged_text.encode('utf-8')).hexdigest()
            logger.info(f"MERGED_TAIL: doc={doc_id} prev={prev.id} tail={new_chunk.id} new_tokens={prev.tokens}")
        else:
            if stats is not None:
                stats['dropped_too_small'] = stats.get('dropped_too_small', 0) + 1
                stats['dropped_too_small_events'].append({
                    'doc_id': doc_id,
                    'chunk_id': new_chunk.id,
                    'tokens': new_chunk.tokens,
                    'reason': 'too_small_unmergeable',
                    'excerpt': text.strip()[:200]
                })
            logger.info(f"DROPPED_TAIL: doc={doc_id} tail={new_chunk.id} tokens={new_chunk.tokens}")

    def _sentence_split(self, text: str) -> List[str]:
        parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+', text) if p and p.strip()]
        return parts or [text.strip()]

    def _hard_token_split(self, text: str, limit: int) -> List[str]:
        toks = tokenizer.encode(text)
        parts = []
        for i in range(0, len(toks), limit):
            decoded = tokenizer.decode(toks[i:i+limit]).strip()
            if decoded:
                parts.append(decoded)
        return parts or [text.strip()]

    def _split_large_paragraph(self, doc_id: str, para_text: str, out_windows: List[JudgmentChunk], para_range_hint: Optional[str] = None):
        sentences = self._sentence_split(para_text)
        buf: List[str] = []
        part_idx = 1
        for sent in sentences:
            prospective = ("\n\n".join(buf + [sent])).strip()
            prospective_tokens = len(tokenizer.encode(prospective))
            if prospective_tokens <= HARD_MAXIMUM_TOKENS:
                buf.append(sent)
                continue
            if buf:
                chunk = self._make_chunk(doc_id, buf, para_range_hint=para_range_hint, part=f"(part {part_idx})")
                self._accept_or_merge_small(chunk, out_windows, doc_id, stats=getattr(self, 'stats_ref', None))
                part_idx += 1
                buf = [sent]
            else:
                for piece in self._hard_token_split(sent, HARD_MAXIMUM_TOKENS):
                    chunk = self._make_chunk(doc_id, [piece], para_range_hint=para_range_hint, part=f"(part {part_idx})")
                    self._accept_or_merge_small(chunk, out_windows, doc_id, stats=getattr(self, 'stats_ref', None))
                    part_idx += 1
                buf = []
        if buf:
            chunk = self._make_chunk(doc_id, buf, para_range_hint=para_range_hint, part=f"(part {part_idx})")
            self._accept_or_merge_small(chunk, out_windows, doc_id, stats=getattr(self, 'stats_ref', None))
    def _extract_year_from_filename(self, filename: str) -> str:
        """Extract year from filename"""
        year_match = re.search(r'(20\d{2})', filename)
        return year_match.group(1) if year_match else "2020"
    
    def _validate_chunks(self, chunks: List[JudgmentChunk]) -> List[JudgmentChunk]:
        """Validate chunks according to rules"""
        validated = []
        
        for chunk in chunks:
            # Token validation
            if chunk.tokens < MINIMUM_TOKENS or chunk.tokens > HARD_MAXIMUM_TOKENS:
                continue
            
            # Text validation
            if not chunk.text or not chunk.id:
                continue
            
            validated.append(chunk)
        
        return validated

class BNSProcessor:
    """BNS statute processor with legal unit chunking"""
    
    def __init__(self, text_extractor: TextExtractor):
        self.text_extractor = text_extractor
    
    def process_bns_pdf(self, pdf_path: str) -> List[StatuteChunk]:
        """Process BNS PDF with legal unit chunking"""
        try:
            # Extract text
            raw_text = self.text_extractor.extract_pdf_text(pdf_path)
            if not raw_text or len(raw_text.strip()) < 100:
                logger.warning(f"Insufficient text extracted from {pdf_path}")
                return []
            
            # Detect legal units
            legal_units = self._detect_legal_units(raw_text)
            
            # Create chunks
            chunks = self._create_statute_chunks(legal_units, pdf_path)
            
            # Validate chunks
            validated_chunks = self._validate_chunks(chunks)
            
            logger.info(f"Processed BNS PDF: {len(validated_chunks)} chunks")
            return validated_chunks
            
        except Exception as e:
            logger.error(f"Failed to process BNS PDF {pdf_path}: {e}")
            return []
    
    def _detect_legal_units(self, text: str) -> List[Dict[str, Any]]:
        """Detect legal units in order: Section, Sub-section, Illustration, Explanation, Proviso"""
        units = []
        
        # Split text into potential sections
        section_pattern = r'(?:^|\n)\s*(\d+)\.\s*([^\n]+?)(?=\n|$)'
        sections = re.finditer(section_pattern, text, re.MULTILINE)
        
        for section_match in sections:
            section_num = section_match.group(1)
            section_title = section_match.group(2).strip()
            
            # Find section end (next section or end of text)
            next_section = re.search(r'(?:^|\n)\s*(\d+)\.\s*', text[section_match.end():], re.MULTILINE)
            if next_section:
                section_end = section_match.end() + next_section.start()
            else:
                section_end = len(text)
            
            section_text = text[section_match.end():section_end].strip()
            
            # Create main section unit
            units.append({
                'type': 'Section',
                'section_no': section_num,
                'title': section_title,
                'text': section_text,
                'order': int(section_num)
            })
            
            # Look for sub-units within this section
            sub_units = self._extract_sub_units(section_text, section_num)
            units.extend(sub_units)
        
        return sorted(units, key=lambda x: (x['order'], x['type']))
    
    def _extract_sub_units(self, section_text: str, section_num: str) -> List[Dict[str, Any]]:
        """Extract sub-units from section text"""
        sub_units = []
        
        # Patterns for different sub-unit types
        patterns = {
            'Illustration': r'(?:^|\n)\s*Illustration[s]?\s*[:\-]?\s*(.*?)(?=\n\s*(?:Explanation|Proviso|Illustration|\d+\.|$))',
            'Explanation': r'(?:^|\n)\s*Explanation[s]?\s*[:\-]?\s*(.*?)(?=\n\s*(?:Illustration|Proviso|Explanation|\d+\.|$))',
            'Proviso': r'(?:^|\n)\s*Proviso\s*[:\-]?\s*(.*?)(?=\n\s*(?:Illustration|Explanation|Proviso|\d+\.|$))'
        }
        
        for unit_type, pattern in patterns.items():
            matches = re.finditer(pattern, section_text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
            for i, match in enumerate(matches, 1):
                unit_text = match.group(1).strip()
                if unit_text and len(unit_text) > 20:  # Minimum length check
                    sub_units.append({
                        'type': unit_type,
                        'section_no': section_num,
                        'title': None,
                        'text': unit_text,
                        'order': int(section_num) + (i * 0.1)  # Sub-ordering
                    })
        
        return sub_units
    
    def _create_statute_chunks(self, legal_units: List[Dict], pdf_path: str) -> List[StatuteChunk]:
        """Create statute chunks from legal units"""
        chunks = []
        
        for i, unit in enumerate(legal_units, 1):
            # Check if unit exceeds token limit
            unit_tokens = len(tokenizer.encode(unit['text']))
            
            if unit_tokens <= HARD_MAXIMUM_TOKENS:
                # Single chunk
                chunk = self._create_single_statute_chunk(unit, i, pdf_path)
                if chunk:
                    chunks.append(chunk)
            else:
                # Split into parts
                part_chunks = self._split_statute_unit(unit, i, pdf_path)
                chunks.extend(part_chunks)
        
        return chunks
    
    def _create_single_statute_chunk(self, unit: Dict, order: int, pdf_path: str) -> Optional[StatuteChunk]:
        """Create single statute chunk"""
        text = unit['text']
        tokens = len(tokenizer.encode(text))
        
        # Skip if too small (unless it's a title)
        if tokens < MINIMUM_TOKENS and unit['type'] != 'Section':
            return None
        
        chunk_id = f"BNS:2023:chunk:{unit['section_no'].zfill(4)}"
        if unit['type'] != 'Section':
            chunk_id += f":{unit['type']}"
        
        return StatuteChunk(
            id=chunk_id,
            type="statute_unit",
            doc_id="BNS:2023",
            order=order,
            act="BNS",
            year=2023,
            section_no=unit['section_no'],
            unit_type=unit['type'],
            title=unit.get('title'),
            text=text,
            tokens=tokens,
            effective_from="2024-07-01",
            effective_to=None,
            source_path=pdf_path,
            sha256=hashlib.sha256(text.encode('utf-8')).hexdigest()
        )
    
    def _split_statute_unit(self, unit: Dict, base_order: int, pdf_path: str) -> List[StatuteChunk]:
        """Split large statute unit into parts"""
        text = unit['text']
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_part = []
        current_tokens = 0
        part_num = 1
        
        for sentence in sentences:
            sentence_tokens = len(tokenizer.encode(sentence))
            
            if current_tokens + sentence_tokens > HARD_MAXIMUM_TOKENS and current_part:
                # Create part chunk
                part_text = ' '.join(current_part)
                chunk_id = f"BNS:2023:chunk:{unit['section_no'].zfill(4)}:part:{part_num}"
                
                chunk = StatuteChunk(
                    id=chunk_id,
                    type="statute_unit",
                    doc_id="BNS:2023",
                    order=base_order + (part_num * 0.01),
                    act="BNS",
                    year=2023,
                    section_no=unit['section_no'],
                    unit_type=unit['type'],
                    title=unit.get('title'),
                    text=part_text,
                    tokens=len(tokenizer.encode(part_text)),
                    effective_from="2024-07-01",
                    effective_to=None,
                    source_path=pdf_path,
                    sha256=hashlib.sha256(part_text.encode('utf-8')).hexdigest()
                )
                chunks.append(chunk)
                
                part_num += 1
                current_part = []
                current_tokens = 0
            
            current_part.append(sentence)
            current_tokens += sentence_tokens
        
        # Handle remaining part
        if current_part:
            part_text = ' '.join(current_part)
            if len(tokenizer.encode(part_text)) >= MINIMUM_TOKENS:
                chunk_id = f"BNS:2023:chunk:{unit['section_no'].zfill(4)}:part:{part_num}"
                
                chunk = StatuteChunk(
                    id=chunk_id,
                    type="statute_unit",
                    doc_id="BNS:2023",
                    order=base_order + (part_num * 0.01),
                    act="BNS",
                    year=2023,
                    section_no=unit['section_no'],
                    unit_type=unit['type'],
                    title=unit.get('title'),
                    text=part_text,
                    tokens=len(tokenizer.encode(part_text)),
                    effective_from="2024-07-01",
                    effective_to=None,
                    source_path=pdf_path,
                    sha256=hashlib.sha256(part_text.encode('utf-8')).hexdigest()
                )
                chunks.append(chunk)
        
        return chunks
    
    def _validate_chunks(self, chunks: List[StatuteChunk]) -> List[StatuteChunk]:
        """Validate statute chunks"""
        validated = []
        
        for chunk in chunks:
            # Token validation
            if chunk.tokens > HARD_MAXIMUM_TOKENS:
                continue
            
            # Skip too small unless it's a section title
            if chunk.tokens < MINIMUM_TOKENS and not chunk.title:
                continue
            
            # Text and ID validation
            if not chunk.text or not chunk.id:
                continue
            
            # Section number required for Sections/Sub-sections
            if chunk.unit_type in ['Section', 'Sub-section'] and not chunk.section_no:
                continue
            
            validated.append(chunk)
        
        return validated

class DeduplicationService:
    """Deduplication and noise control"""
    
    def __init__(self):
        self.seen_hashes = set()
        self.seen_texts = {}
    
    def deduplicate_chunks(self, chunks: List) -> List:
        """Remove exact and near duplicates"""
        deduplicated = []
        
        for chunk in chunks:
            # Exact duplicate check by SHA256
            if chunk.sha256 in self.seen_hashes:
                continue
            
            # Near duplicate check by Jaccard similarity
            if self._is_near_duplicate(chunk.text, chunk.doc_id):
                continue
            
            # Add to seen sets
            self.seen_hashes.add(chunk.sha256)
            self._add_to_text_index(chunk.text, chunk.doc_id)
            
            deduplicated.append(chunk)
        
        return deduplicated
    
    def _is_near_duplicate(self, text: str, doc_id: str) -> bool:
        """Check for near duplicates using Jaccard similarity"""
        text_words = set(text.lower().split())
        
        for existing_text, existing_doc_id in self.seen_texts.items():
            if existing_doc_id == doc_id:  # Only check within same document
                existing_words = set(existing_text.lower().split())
                
                if len(text_words) == 0 or len(existing_words) == 0:
                    continue
                
                intersection = len(text_words.intersection(existing_words))
                union = len(text_words.union(existing_words))
                
                jaccard_similarity = intersection / union if union > 0 else 0
                
                if jaccard_similarity >= 0.95:
                    return True
        
        return False
    
    def _add_to_text_index(self, text: str, doc_id: str):
        """Add text to index for similarity checking"""
        # Limit index size to prevent memory issues
        if len(self.seen_texts) > 10000:
            # Remove oldest entries (simple FIFO)
            oldest_key = next(iter(self.seen_texts))
            del self.seen_texts[oldest_key]
        
        self.seen_texts[text] = doc_id

class ChunkingPipeline:
    """Main chunking pipeline orchestrator"""
    
    def __init__(self):
        self.text_extractor = TextExtractor()
        self.judgment_processor = JudgmentProcessor(self.text_extractor)
        self.bns_processor = BNSProcessor(self.text_extractor)
        self.deduplication_service = DeduplicationService()
        
        # Statistics
        self.stats = {
            'processed_docs': 0,
            'total_chunks_emitted': 0,
            'token_counts': [],
            'dropped_too_small': 0,
            'dropped_too_large': 0,
            'dropped_too_small_events': [],
            'dropped_too_large_events': [],
            'ocr_pages': 0,
            'errors': []
        }
    
    def process_all_documents(self) -> bool:
        """Process all documents according to specifications"""
        try:
            # Wire stats into judgment processor for truthful counters
            try:
                self.judgment_processor.stats_ref = self.stats
            except Exception:
                pass
            # Create output directories
            self._create_output_directories()
            
            # Process Supreme Court judgments (2020 only)
            judgment_success = self._process_supreme_court_judgments()
            
            # Process BNS statute
            bns_success = self._process_bns_statute()
            
            # Generate summary report
            self._generate_summary_report()
            
            return judgment_success and bns_success
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.stats['errors'].append(str(e))
            return False
    
    def _create_output_directories(self):
        """Create output directory structure"""
        output_dirs = [
            'out/chunks/2020',
            'out/chunks/BNS',
            'out/reports'
        ]
        
        for dir_path in output_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def _process_supreme_court_judgments(self) -> bool:
        """Process Supreme Court judgments from 2020"""
        try:
            judgment_dir = Path('data/supreme_court_judgments/extracted/judgments')
            
            if not judgment_dir.exists():
                logger.error(f"Judgment directory not found: {judgment_dir}")
                return False
            
            # Find 2020 PDFs
            pdf_files = []
            for pdf_file in judgment_dir.rglob('*.pdf'):
                if '2020' in pdf_file.name or '2020' in str(pdf_file.parent):
                    pdf_files.append(pdf_file)
            
            logger.info(f"Found {len(pdf_files)} 2020 judgment PDFs")
            
            for pdf_file in pdf_files:
                try:
                    # Process judgment
                    chunks = self.judgment_processor.process_judgment_pdf(str(pdf_file))
                    
                    if chunks:
                        # Deduplicate
                        deduplicated_chunks = self.deduplication_service.deduplicate_chunks(chunks)
                        
                        # Token gate validation
                        validated_chunks = self._token_gate_validation(deduplicated_chunks)
                        # Per-file token stats log
                        if validated_chunks:
                            tok_list = [c.tokens for c in validated_chunks]
                            tok_list_sorted = sorted(tok_list)
                            def _pct(vs, p):
                                if not vs:
                                    return 0
                                k = (len(vs) - 1) * (p/100.0)
                                f = int(k)
                                c = min(f+1, len(vs)-1)
                                if f == c:
                                    return vs[f]
                                return round(vs[f]*(c-k) + vs[c]*(k-f))
                            p50 = _pct(tok_list_sorted, 50)
                            p95 = _pct(tok_list_sorted, 95)
                            logger.info(f"Doc token stats: p50={p50}, p95={p95}, max={max(tok_list)}, min={min(tok_list)}")
                        
                        # Write JSONL
                        output_file = f"out/chunks/2020/{pdf_file.stem}.jsonl"
                        self._write_jsonl(validated_chunks, output_file)
                        # Update statistics
                        self.stats['processed_docs'] += 1
                        self.stats['total_chunks_emitted'] += len(validated_chunks)
                        self.stats['token_counts'].extend([chunk.tokens for chunk in validated_chunks])
                        # accumulate skipped non-textful pages (reported in ocr_pages field per schema)
                        if hasattr(self.text_extractor, 'last_skipped_pages'):
                            self.stats['ocr_pages'] += int(self.text_extractor.last_skipped_pages)
                    
                except Exception as e:
                    logger.error(f"Failed to process {pdf_file}: {e}")
                    self.stats['errors'].append(f"{pdf_file}: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process Supreme Court judgments: {e}")
            self.stats['errors'].append(f"Supreme Court processing: {str(e)}")
            return False
    
    def _process_bns_statute(self) -> bool:
        """Process BNS statute"""
        try:
            # BNS PDF path as provided by user
            bns_path = Path('data/BNS.pdf.pdf')
            
            if not bns_path.exists():
                logger.error(f"BNS PDF not found: {bns_path}")
                return False
            
            # Process BNS
            chunks = self.bns_processor.process_bns_pdf(str(bns_path))
            
            if chunks:
                # Deduplicate
                deduplicated_chunks = self.deduplication_service.deduplicate_chunks(chunks)
                
                # Token gate validation
                validated_chunks = self._token_gate_validation(deduplicated_chunks)
                
                # Write JSONL
                output_file = "out/chunks/BNS/BNS_2023.jsonl"
                self._write_jsonl(validated_chunks, output_file)
                
                # Update statistics
                self.stats['processed_docs'] += 1
                self.stats['total_chunks_emitted'] += len(validated_chunks)
                # accumulate OCR page count
                if hasattr(self.text_extractor, 'last_ocr_pages'):
                    self.stats['ocr_pages'] += int(self.text_extractor.last_ocr_pages)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process BNS statute: {e}")
            self.stats['errors'].append(f"BNS processing: {str(e)}")
            return False
    
    def _token_gate_validation(self, chunks: List) -> List:
        """Final token gate validation"""
        validated = []
        
        for chunk in chunks:
            # Re-tokenize to ensure accuracy
            actual_tokens = len(tokenizer.encode(chunk.text))
            chunk.tokens = actual_tokens
            
            # Enforce hard limits
            if actual_tokens > HARD_MAXIMUM_TOKENS:
                logger.warning(
                    "DROPPED_TOO_LARGE: doc=%s chunk=%s tokens=%s",
                    getattr(chunk, 'doc_id', 'unknown'),
                    getattr(chunk, 'id', 'unknown'),
                    actual_tokens,
                )
                self.stats['dropped_too_large'] += 1
                self.stats['dropped_too_large_events'].append({
                    'doc_id': getattr(chunk, 'doc_id', 'unknown'),
                    'chunk_id': getattr(chunk, 'id', 'unknown'),
                    'tokens': actual_tokens,
                    'reason': 'token_gate_too_large'
                })
                continue
            
            if actual_tokens < MINIMUM_TOKENS:
                # Exception for statute titles
                if hasattr(chunk, 'unit_type') and chunk.unit_type == 'Section' and chunk.title:
                    pass  # Allow statute titles
                else:
                    logger.warning(
                        "DROPPED_TOO_SMALL: doc=%s chunk=%s tokens=%s",
                        getattr(chunk, 'doc_id', 'unknown'),
                        getattr(chunk, 'id', 'unknown'),
                        actual_tokens,
                    )
                    self.stats['dropped_too_small'] += 1
                    self.stats['dropped_too_small_events'].append({
                        'doc_id': getattr(chunk, 'doc_id', 'unknown'),
                        'chunk_id': getattr(chunk, 'id', 'unknown'),
                        'tokens': actual_tokens,
                        'reason': 'token_gate_too_small',
                        'excerpt': chunk.text.strip()[:200]
                    })
                    continue
            
            validated.append(chunk)
        
        return validated
    
    def _write_jsonl(self, chunks: List, output_file: str):
        """Write chunks to JSONL file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                json_line = json.dumps(asdict(chunk), ensure_ascii=False)
                f.write(json_line + '\n')
        
        logger.info(f"Wrote {len(chunks)} chunks to {output_file}")
    
    def _generate_summary_report(self):
        """Generate chunking summary report"""
        def _percentile(values, pct):
            if not values:
                return 0
            vals = sorted(values)
            k = (len(vals) - 1) * (pct / 100.0)
            f = int(k)
            c = min(f + 1, len(vals) - 1)
            if f == c:
                return vals[f]
            d0 = vals[f] * (c - k)
            d1 = vals[c] * (k - f)
            return d0 + d1

        if self.stats['token_counts']:
            p50_tokens = int(round(_percentile(self.stats['token_counts'], 50)))
            p95_tokens = int(round(_percentile(self.stats['token_counts'], 95)))
            max_tokens = max(self.stats['token_counts'])
            min_tokens = min(self.stats['token_counts'])
        else:
            p50_tokens = p95_tokens = max_tokens = min_tokens = 0
        
        summary = ChunkingSummary(
            processed_docs=self.stats['processed_docs'],
            total_chunks_emitted=self.stats['total_chunks_emitted'],
            p50_tokens=p50_tokens,
            p95_tokens=p95_tokens,
            max_tokens=max_tokens,
            min_tokens=min_tokens,
            dropped_too_small=self.stats['dropped_too_small'],
            dropped_too_large=self.stats['dropped_too_large'],
            ocr_pages=self.stats['ocr_pages'],
            errors=self.stats['errors']
        )
        
        # Write summary report
        with open('out/reports/chunking_summary.json', 'w', encoding='utf-8') as f:
            json.dump(asdict(summary), f, indent=2, ensure_ascii=False)
        
        # Persist drop event diagnostics for auditability
        drop_events_path = 'out/reports/drop_events.json'
        with open(drop_events_path, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    'dropped_too_large': self.stats.get('dropped_too_large_events', []),
                    'dropped_too_small': self.stats.get('dropped_too_small_events', []),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        logger.info("Wrote drop event audit log to %s", drop_events_path)
        
        logger.info("Generated chunking summary report")
        logger.info(f"Summary: {self.stats['processed_docs']} docs, {self.stats['total_chunks_emitted']} chunks")
        logger.info(f"Token stats: p50={p50_tokens}, p95={p95_tokens}, max={max_tokens}, min={min_tokens}")

def main():
    """Main execution function"""
    logger.info("Starting Chunking & Pre-Embedding Pipeline")
    
    # Initialize pipeline
    pipeline = ChunkingPipeline()
    
    # Process all documents
    success = pipeline.process_all_documents()
    
    if success:
        logger.info("âœ… Chunking pipeline completed successfully")
        return 0
    else:
        logger.error("âŒ Chunking pipeline failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())





