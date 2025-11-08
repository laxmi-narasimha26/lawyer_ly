"""
Document chunking module
Splits documents into semantically coherent chunks
"""
import structlog
from typing import List, Dict
import re
import tiktoken

from config import settings

logger = structlog.get_logger()

class DocumentChunker:
    def __init__(self):
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP
    
    async def chunk_text(
        self,
        text: str,
        source_name: str,
        source_type: str,
        metadata: Dict
    ) -> List[Dict]:
        """
        Chunk text into semantically coherent segments
        """
        # Detect document type and use appropriate chunking strategy
        if source_type == "statute":
            chunks = await self._chunk_statute(text, source_name, metadata)
        elif source_type == "case_law":
            chunks = await self._chunk_case_law(text, source_name, metadata)
        else:
            chunks = await self._chunk_generic(text, source_name, metadata)
        
        logger.info(
            "Text chunked",
            source_name=source_name,
            chunk_count=len(chunks)
        )
        
        return chunks
    
    async def _chunk_statute(
        self,
        text: str,
        source_name: str,
        metadata: Dict
    ) -> List[Dict]:
        """
        Chunk statute preserving section boundaries
        """
        chunks = []
        
        # Split by section markers
        section_pattern = r'(Section\s+\d+[A-Z]?\.?\s*[:\-]?)'
        sections = re.split(section_pattern, text, flags=re.IGNORECASE)
        
        current_chunk = ""
        current_section = None
        
        for i, part in enumerate(sections):
            if re.match(section_pattern, part, re.IGNORECASE):
                # This is a section header
                if current_chunk and len(self.tokenizer.encode(current_chunk)) > 50:
                    chunks.append(self._create_chunk(
                        text=current_chunk,
                        source_name=source_name,
                        source_type="statute",
                        metadata={**metadata, "section": current_section}
                    ))
                current_section = part.strip()
                current_chunk = part
            else:
                current_chunk += part
                
                # If chunk is getting too large, split it
                if len(self.tokenizer.encode(current_chunk)) > self.chunk_size:
                    chunks.append(self._create_chunk(
                        text=current_chunk,
                        source_name=source_name,
                        source_type="statute",
                        metadata={**metadata, "section": current_section}
                    ))
                    current_chunk = ""
        
        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                text=current_chunk,
                source_name=source_name,
                source_type="statute",
                metadata={**metadata, "section": current_section}
            ))
        
        return chunks
    
    async def _chunk_case_law(
        self,
        text: str,
        source_name: str,
        metadata: Dict
    ) -> List[Dict]:
        """
        Chunk case law preserving paragraph boundaries
        """
        chunks = []
        
        # Split by paragraphs
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check if adding this paragraph would exceed chunk size
            test_chunk = current_chunk + "\n\n" + para if current_chunk else para
            token_count = len(self.tokenizer.encode(test_chunk))
            
            if token_count > self.chunk_size and current_chunk:
                # Save current chunk and start new one
                chunks.append(self._create_chunk(
                    text=current_chunk,
                    source_name=source_name,
                    source_type="case_law",
                    metadata=metadata
                ))
                current_chunk = para
            else:
                current_chunk = test_chunk
        
        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                text=current_chunk,
                source_name=source_name,
                source_type="case_law",
                metadata=metadata
            ))
        
        return chunks
    
    async def _chunk_generic(
        self,
        text: str,
        source_name: str,
        metadata: Dict
    ) -> List[Dict]:
        """
        Generic chunking with overlap
        """
        chunks = []
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_chunk = ""
        current_sentences = []
        
        for sentence in sentences:
            test_chunk = current_chunk + " " + sentence if current_chunk else sentence
            token_count = len(self.tokenizer.encode(test_chunk))
            
            if token_count > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(self._create_chunk(
                    text=current_chunk,
                    source_name=source_name,
                    source_type="user_document",
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
                source_type="user_document",
                metadata=metadata
            ))
        
        return chunks
    
    def _create_chunk(
        self,
        text: str,
        source_name: str,
        source_type: str,
        metadata: Dict
    ) -> Dict:
        """Create a chunk dictionary"""
        return {
            'text': text.strip(),
            'source_name': source_name,
            'source_type': source_type,
            'metadata': metadata
        }
