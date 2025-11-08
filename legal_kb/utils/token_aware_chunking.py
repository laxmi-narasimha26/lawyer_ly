"""
Token-aware chunking service for legal documents
Ensures chunks never exceed embedding model token limits
"""
import re
import tiktoken
from typing import List, Dict, Optional, Tuple
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ChunkMetadata:
    """Metadata for a text chunk"""
    chunk_id: str
    token_count: int
    char_count: int
    paragraph_numbers: List[str]
    section_title: Optional[str]
    legal_citations: List[str]
    chunk_type: str  # 'judgment', 'statute', 'bns'

class TokenAwareChunker:
    """Token-aware chunking service that respects embedding model limits"""
    
    def __init__(self, model_name: str = "text-embedding-3-small"):
        # Use cl100k_base tokenizer (GPT-4/text-embedding-3 compatible)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.model_name = model_name
        
        # Token limits with safety margins
        self.max_tokens = 8192  # OpenAI embedding model limit
        self.target_tokens = 400  # Target chunk size (250-500 range)
        self.max_target_tokens = 800  # Max for coherent paragraphs
        self.hard_limit_tokens = 1800  # Hard limit before forced split
        self.overlap_tokens = 75  # Overlap for continuity (50-100 range)
        
        # Legal document patterns
        self.paragraph_pattern = re.compile(r'^\s*\(?\d+\)?\s*\.?\s*', re.MULTILINE)
        self.section_pattern = re.compile(r'^\s*(?:Section\s+)?(\d+)\.?\s*(.+?)(?:—|\.—)\s*(.+)', re.MULTILINE)
        self.citation_patterns = [
            re.compile(r'\b\d{4}\s+SCC\s+\d+\b'),
            re.compile(r'\(\d{4}\)\s+\d+\s+SCC\s+\d+\b'),
            re.compile(r'\bAIR\s+\d{4}\s+SC\s+\d+\b'),
            re.compile(r'\b\d{4}\s+SCR\s+\(\d+\)\s+\d+\b')
        ]
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the tokenizer"""
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed, using character estimate: {e}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4
    
    def chunk_judgment_text(self, text: str, document_id: str) -> List[Tuple[str, ChunkMetadata]]:
        """Chunk Supreme Court judgment text with legal awareness"""
        chunks = []
        
        # Clean and normalize text first
        text = self._clean_judgment_text(text)
        
        # Split into paragraphs
        paragraphs = self._split_into_paragraphs(text)
        
        current_chunk = ""
        current_tokens = 0
        current_para_numbers = []
        chunk_counter = 0
        
        for i, paragraph in enumerate(paragraphs):
            para_tokens = self.count_tokens(paragraph)
            para_number = self._extract_paragraph_number(paragraph)
            
            # If single paragraph exceeds hard limit, force split
            if para_tokens > self.hard_limit_tokens:
                # Save current chunk if exists
                if current_chunk:
                    chunk_metadata = self._create_chunk_metadata(
                        f"{document_id}_chunk_{chunk_counter}",
                        current_tokens,
                        len(current_chunk),
                        current_para_numbers,
                        None,
                        self._extract_citations(current_chunk),
                        "judgment"
                    )
                    chunks.append((current_chunk.strip(), chunk_metadata))
                    chunk_counter += 1
                    current_chunk = ""
                    current_tokens = 0
                    current_para_numbers = []
                
                # Split the oversized paragraph
                sub_chunks = self._force_split_paragraph(paragraph, para_number)
                for sub_chunk in sub_chunks:
                    sub_tokens = self.count_tokens(sub_chunk)
                    chunk_metadata = self._create_chunk_metadata(
                        f"{document_id}_chunk_{chunk_counter}",
                        sub_tokens,
                        len(sub_chunk),
                        [para_number] if para_number else [],
                        None,
                        self._extract_citations(sub_chunk),
                        "judgment"
                    )
                    chunks.append((sub_chunk.strip(), chunk_metadata))
                    chunk_counter += 1
                continue
            
            # Check if adding this paragraph would exceed target
            if current_tokens + para_tokens > self.max_target_tokens:
                # Save current chunk
                if current_chunk:
                    chunk_metadata = self._create_chunk_metadata(
                        f"{document_id}_chunk_{chunk_counter}",
                        current_tokens,
                        len(current_chunk),
                        current_para_numbers,
                        None,
                        self._extract_citations(current_chunk),
                        "judgment"
                    )
                    chunks.append((current_chunk.strip(), chunk_metadata))
                    chunk_counter += 1
                
                # Start new chunk with overlap if possible
                current_chunk = self._create_overlap(current_chunk, paragraph)
                current_tokens = self.count_tokens(current_chunk)
                current_para_numbers = [para_number] if para_number else []
            else:
                # Add paragraph to current chunk
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph
                current_tokens += para_tokens
                if para_number:
                    current_para_numbers.append(para_number)
        
        # Add final chunk
        if current_chunk:
            chunk_metadata = self._create_chunk_metadata(
                f"{document_id}_chunk_{chunk_counter}",
                current_tokens,
                len(current_chunk),
                current_para_numbers,
                None,
                self._extract_citations(current_chunk),
                "judgment"
            )
            chunks.append((current_chunk.strip(), chunk_metadata))
        
        logger.info(f"Created {len(chunks)} chunks for judgment {document_id}")
        return chunks
    
    def chunk_bns_text(self, text: str, document_id: str) -> List[Tuple[str, ChunkMetadata]]:
        """Chunk BNS text by legal units (sections, sub-sections, etc.)"""
        chunks = []
        
        # Clean text
        text = self._clean_statute_text(text)
        
        # Split by sections
        sections = self._split_bns_sections(text)
        
        chunk_counter = 0
        for section in sections:
            section_tokens = self.count_tokens(section)
            section_title = self._extract_section_title(section)
            section_number = self._extract_section_number(section)
            
            # If section is within limits, use as single chunk
            if section_tokens <= self.max_target_tokens:
                chunk_metadata = self._create_chunk_metadata(
                    f"{document_id}_section_{section_number or chunk_counter}",
                    section_tokens,
                    len(section),
                    [section_number] if section_number else [],
                    section_title,
                    self._extract_citations(section),
                    "bns"
                )
                chunks.append((section.strip(), chunk_metadata))
                chunk_counter += 1
            else:
                # Split large section into sub-chunks
                sub_chunks = self._split_large_section(section, section_number, section_title)
                for i, sub_chunk in enumerate(sub_chunks):
                    sub_tokens = self.count_tokens(sub_chunk)
                    chunk_metadata = self._create_chunk_metadata(
                        f"{document_id}_section_{section_number or chunk_counter}_{i}",
                        sub_tokens,
                        len(sub_chunk),
                        [section_number] if section_number else [],
                        section_title,
                        self._extract_citations(sub_chunk),
                        "bns"
                    )
                    chunks.append((sub_chunk.strip(), chunk_metadata))
                chunk_counter += 1
        
        logger.info(f"Created {len(chunks)} chunks for BNS document {document_id}")
        return chunks
    
    def _clean_judgment_text(self, text: str) -> str:
        """Clean judgment text by removing headers, footers, and noise"""
        # Remove common headers/footers
        text = re.sub(r'SUPREME COURT REPORTS.*?\n', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Page \d+ of \d+', '', text)
        text = re.sub(r'\[.*?\]', '', text)  # Remove bracketed metadata
        
        # Fix hyphenated line breaks
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text.strip()
    
    def _clean_statute_text(self, text: str) -> str:
        """Clean statute text"""
        # Remove page numbers and headers
        text = re.sub(r'Page \d+.*?\n', '', text)
        text = re.sub(r'THE GAZETTE OF INDIA.*?\n', '', text, flags=re.IGNORECASE)
        
        # Fix formatting
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs"""
        # Split on double newlines or paragraph markers
        paragraphs = re.split(r'\n\s*\n|\n\s*\(\d+\)\s*', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _split_bns_sections(self, text: str) -> List[str]:
        """Split BNS text into sections"""
        # Split on section markers
        sections = re.split(r'\n\s*(?=\d+\.)', text)
        return [s.strip() for s in sections if s.strip()]
    
    def _extract_paragraph_number(self, paragraph: str) -> Optional[str]:
        """Extract paragraph number from text"""
        match = re.match(r'^\s*\(?(\d+)\)?\s*\.?\s*', paragraph)
        return match.group(1) if match else None
    
    def _extract_section_number(self, section: str) -> Optional[str]:
        """Extract section number from BNS section"""
        match = re.match(r'^\s*(\d+)\.', section)
        return match.group(1) if match else None
    
    def _extract_section_title(self, section: str) -> Optional[str]:
        """Extract section title from BNS section"""
        match = re.match(r'^\s*\d+\.\s*(.+?)\.?\s*—\s*(.+)', section)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_citations(self, text: str) -> List[str]:
        """Extract legal citations from text"""
        citations = []
        for pattern in self.citation_patterns:
            citations.extend(pattern.findall(text))
        return list(set(citations))
    
    def _force_split_paragraph(self, paragraph: str, para_number: Optional[str]) -> List[str]:
        """Force split an oversized paragraph"""
        # Split by sentences first
        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            if current_tokens + sentence_tokens > self.hard_limit_tokens:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                    current_tokens = sentence_tokens
                else:
                    # Single sentence too long, split by words
                    word_chunks = self._split_by_words(sentence)
                    chunks.extend(word_chunks)
            else:
                current_chunk += " " + sentence if current_chunk else sentence
                current_tokens += sentence_tokens
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_by_words(self, text: str) -> List[str]:
        """Split text by words when sentences are too long"""
        words = text.split()
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for word in words:
            word_tokens = self.count_tokens(word)
            
            if current_tokens + word_tokens > self.hard_limit_tokens:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = word
                    current_tokens = word_tokens
                else:
                    # Single word too long, just add it
                    chunks.append(word)
            else:
                current_chunk += " " + word if current_chunk else word
                current_tokens += word_tokens
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _create_overlap(self, previous_chunk: str, next_paragraph: str) -> str:
        """Create overlap between chunks for continuity"""
        if not previous_chunk:
            return next_paragraph
        
        # Take last few sentences from previous chunk
        sentences = re.split(r'(?<=[.!?])\s+', previous_chunk)
        overlap_text = ""
        overlap_tokens = 0
        
        # Add sentences from the end until we reach overlap limit
        for sentence in reversed(sentences[-3:]):  # Max 3 sentences
            sentence_tokens = self.count_tokens(sentence)
            if overlap_tokens + sentence_tokens <= self.overlap_tokens:
                overlap_text = sentence + " " + overlap_text if overlap_text else sentence
                overlap_tokens += sentence_tokens
            else:
                break
        
        return overlap_text + "\n\n" + next_paragraph if overlap_text else next_paragraph
    
    def _split_large_section(self, section: str, section_number: Optional[str], section_title: Optional[str]) -> List[str]:
        """Split a large section into smaller chunks"""
        # Try to split by sub-sections, illustrations, explanations
        parts = re.split(r'\n\s*(?=(?:Illustration|Explanation|Proviso))', section)
        
        if len(parts) == 1:
            # No natural splits, force split by paragraphs
            return self._force_split_paragraph(section, section_number)
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for part in parts:
            part_tokens = self.count_tokens(part)
            
            if current_tokens + part_tokens > self.max_target_tokens:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = part
                current_tokens = part_tokens
            else:
                current_chunk += "\n\n" + part if current_chunk else part
                current_tokens += part_tokens
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _create_chunk_metadata(self, chunk_id: str, token_count: int, char_count: int,
                             paragraph_numbers: List[str], section_title: Optional[str],
                             citations: List[str], chunk_type: str) -> ChunkMetadata:
        """Create metadata for a chunk"""
        return ChunkMetadata(
            chunk_id=chunk_id,
            token_count=token_count,
            char_count=char_count,
            paragraph_numbers=paragraph_numbers,
            section_title=section_title,
            legal_citations=citations,
            chunk_type=chunk_type
        )
    
    def validate_chunk_size(self, text: str) -> bool:
        """Validate that a chunk is within token limits"""
        token_count = self.count_tokens(text)
        return token_count <= self.max_tokens
    
    def get_chunk_stats(self, chunks: List[Tuple[str, ChunkMetadata]]) -> Dict:
        """Get statistics about chunks"""
        if not chunks:
            return {}
        
        token_counts = [metadata.token_count for _, metadata in chunks]
        char_counts = [metadata.char_count for _, metadata in chunks]
        
        return {
            'total_chunks': len(chunks),
            'avg_tokens': sum(token_counts) / len(token_counts),
            'max_tokens': max(token_counts),
            'min_tokens': min(token_counts),
            'avg_chars': sum(char_counts) / len(char_counts),
            'oversized_chunks': sum(1 for t in token_counts if t > self.max_tokens),
            'chunk_types': {metadata.chunk_type for _, metadata in chunks}
        }