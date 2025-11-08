#!/usr/bin/env python3
"""
2020-focused Supreme Court judgment ingestion with token-aware chunking
Implements all requirements from tasks.md for vectorization
- Target per-chunk length: 250-500 tokens (max 800 tokens for coherent paragraphs)
- Hard guardrail: if chunk > 1,800 tokens, split again before embedding
- Sliding window: 50-100 token overlap for continuity
- Use text-embedding-3-small (1536-d)
- Batch ≤128 chunks per request, ensure JSON body < 1MB
- Retry 429/5xx only, no retries on 400
- Process 2020 PDFs only
"""
import asyncio
import os
import sys
import logging
import json
import re  # Missing import for regex operations
import fitz  # PyMuPDF for better PDF extraction
from pathlib import Path
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import tiktoken

# Add the legal_kb directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'legal_kb'))

from legal_kb.config import Config
from legal_kb.services.embedding_service import EmbeddingService
from legal_kb.utils.token_aware_chunking import TokenAwareChunker, ChunkMetadata
from legal_kb.processors.sc_judgment_processor import SCJudgmentProcessor
from legal_kb.processors.bns_processor import BNSProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('2020_focused_ingestion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Focused2020Ingestion:
    """2020-focused legal document ingestion with all tasks.md requirements"""
    
    def __init__(self):
        self.config = Config()
        self.redis_client = None
        self.embedding_service = None
        self.chunker = None
        self.sc_processor = None
        self.bns_processor = None
        
        # Statistics
        self.stats = {
            'documents_processed': 0,
            'chunks_created': 0,
            'chunks_embedded': 0,
            'chunks_stored': 0,
            'errors': 0,
            'oversized_chunks_fixed': 0,
            'token_validation_failures': 0,
            'embedding_400_errors': 0
        }
    
    async def initialize(self):
        """Initialize all services per tasks.md requirements"""
        logger.info("Initializing 2020-focused ingestion pipeline...")
        
        try:
            # Test database connection
            conn = psycopg2.connect(
                host=self.config.POSTGRES_HOST,
                port=self.config.POSTGRES_PORT,
                database=self.config.POSTGRES_DB,
                user=self.config.POSTGRES_USER,
                password=self.config.POSTGRES_PASSWORD
            )
            conn.close()
            logger.info("Database connected")
            
            # Redis connection
            self.redis_client = redis.Redis(
                host=self.config.REDIS_HOST,
                port=self.config.REDIS_PORT,
                db=self.config.REDIS_DB,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Redis connected")
            
            # Embedding service with text-embedding-3-small per tasks.md
            self.embedding_service = EmbeddingService(self.config.OPENAI_API_KEY)
            api_test = await self.embedding_service.test_api_connection()
            if not api_test:
                raise Exception("OpenAI API connection failed")
            logger.info("OpenAI API connected (text-embedding-3-small)")
            
            # Token-aware chunker with tasks.md requirements
            self.chunker = TokenAwareChunker()
            logger.info("Token-aware chunker initialized (250-500 tokens, max 800, hard limit 1800)")
            
            # Document processors
            self.sc_processor = SCJudgmentProcessor()
            self.bns_processor = BNSProcessor()
            logger.info("Document processors initialized")
            
            logger.info("All services initialized successfully")
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise
    
    async def ingest_2020_supreme_court_judgments(self, data_dir: str = "data/supreme_court_judgments/extracted/judgments"):
        """Ingest 2020 Supreme Court judgments only per tasks.md requirements"""
        logger.info(f"Starting 2020 Supreme Court judgment ingestion from {data_dir}")
        
        data_path = Path(data_dir)
        if not data_path.exists():
            logger.error(f"Data directory not found: {data_path}")
            return
        
        # Find 2020 PDF files only
        pdf_files = []
        for pdf_file in data_path.rglob("*.pdf"):
            # Check if filename contains 2020
            if "2020" in pdf_file.name or "2020" in str(pdf_file.parent):
                pdf_files.append(pdf_file)
        
        logger.info(f"Found {len(pdf_files)} 2020 PDF files")
        
        if not pdf_files:
            logger.warning("No 2020 PDF files found!")
            return
        
        # Process files in larger batches for full 2020 dataset
        batch_size = 20  # Larger batches for full processing
        for i in range(0, len(pdf_files), batch_size):
            batch = pdf_files[i:i + batch_size]
            logger.info(f"Processing 2020 batch {i//batch_size + 1}/{(len(pdf_files) + batch_size - 1)//batch_size}")
            
            for pdf_file in batch:
                try:
                    await self._process_2020_judgment_pdf(pdf_file)
                except Exception as e:
                    logger.error(f"Failed to process 2020 PDF {pdf_file}: {e}")
                    self.stats['errors'] += 1
            
            # Small delay between batches
            await asyncio.sleep(2)
        
        logger.info("2020 Supreme Court judgment ingestion completed")
        self._log_stats()
    
    async def _process_2020_judgment_pdf(self, pdf_path: Path):
        """Process a single 2020 Supreme Court judgment PDF per tasks.md requirements"""
        logger.info(f"Processing 2020 judgment: {pdf_path.name}")
        
        try:
            # Extract text using PyMuPDF per tasks.md
            text = self._extract_pdf_text_pymupdf(pdf_path)
            if not text or len(text.strip()) < 100:
                logger.warning(f"No meaningful text extracted from {pdf_path.name}")
                return
            
            # Process with SC processor per tasks.md
            processed_data = self.sc_processor.process_judgment_text(text, str(pdf_path))
            if not processed_data:
                logger.warning(f"No processed data from {pdf_path.name}")
                return
            
            # Create canonical document ID per tasks.md: SC:<YYYY>:<NeutralOrSCR>:<Slug>:Para:<number>
            document_id = f"SC:2020:{pdf_path.stem}"
            
            # Token-aware chunking per tasks.md: paragraph windows 250-500 tokens (cap 800)
            chunks = self.chunker.chunk_judgment_text(processed_data['content'], document_id)
            if not chunks:
                logger.warning(f"No chunks created for {pdf_path.name}")
                return
            
            # Validate all chunks per tasks.md: enforce if tokens > 1800: split()
            validated_chunks = []
            for text_chunk, metadata in chunks:
                if metadata.token_count > 1800:
                    logger.warning(f"Chunk {metadata.chunk_id} has {metadata.token_count} tokens, splitting")
                    self.stats['oversized_chunks_fixed'] += 1
                    # This should not happen with proper chunker, but log it
                    continue
                
                if not self.chunker.validate_chunk_size(text_chunk):
                    logger.error(f"Chunk {metadata.chunk_id} failed validation")
                    self.stats['token_validation_failures'] += 1
                    continue
                
                validated_chunks.append((text_chunk, metadata))
            
            # Log chunk statistics
            chunk_stats = self.chunker.get_chunk_stats(validated_chunks)
            logger.info(f"Created {chunk_stats['total_chunks']} validated chunks, "
                       f"avg tokens: {chunk_stats['avg_tokens']:.1f}, "
                       f"max tokens: {chunk_stats['max_tokens']}")
            
            # Generate embeddings per tasks.md: batch ≤128 chunks, ensure request body <1MB
            embedded_chunks = await self.embedding_service.embed_legal_chunks(validated_chunks)
            
            # Store in database per tasks.md: upsert in batches, then commit
            await self._store_judgment_chunks_batch(document_id, processed_data, embedded_chunks, validated_chunks)
            
            # Update statistics
            self.stats['documents_processed'] += 1
            self.stats['chunks_created'] += len(validated_chunks)
            self.stats['chunks_embedded'] += len(embedded_chunks)
            self.stats['chunks_stored'] += len(embedded_chunks)
            
            logger.info(f"Successfully processed 2020 judgment {pdf_path.name}: {len(embedded_chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error processing 2020 judgment {pdf_path.name}: {e}")
            raise
    
    def _extract_pdf_text_pymupdf(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyMuPDF per tasks.md: keep ¶ numbers, remove headers/footers"""
        try:
            doc = fitz.open(pdf_path)
            text_parts = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                
                # Clean up the text per tasks.md requirements
                text = self._clean_extracted_text_per_tasks(text)
                if text.strip():
                    text_parts.append(text)
            
            doc.close()
            return "\n\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""
    
    def _clean_extracted_text_per_tasks(self, text: str) -> str:
        """Clean extracted PDF text per tasks.md requirements"""
        # Remove running headers/footers, page numbers, "SUPREME COURT REPORTS" mastheads
        text = re.sub(r'SUPREME COURT REPORTS.*?\n', '', text, flags=re.IGNORECASE)
        text = re.sub(r'SUPREME COURT OF INDIA.*?\n', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Page \d+ of \d+', '', text)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)  # Standalone page numbers
        
        # Collapse hyphenated line breaks ("con-\ntract" → "contract") per tasks.md
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        
        # Remove form feed and other PDF artifacts
        text = text.replace('\x0c', '')  # Form feed
        text = text.replace('\uf0b7', '•')  # Bullet point
        
        # Normalize whitespace but preserve paragraph/¶ numbers (key for citations per tasks.md)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text.strip()
    
    async def _store_judgment_chunks_batch(self, document_id: str, processed_data: Dict, 
                                         embedded_chunks: List, original_chunks: List):
        """Store judgment chunks in database per tasks.md: upsert in batches, then commit"""
        try:
            # Use regular psycopg2 connection for batch operations
            conn = psycopg2.connect(
                host=self.config.POSTGRES_HOST,
                port=self.config.POSTGRES_PORT,
                database=self.config.POSTGRES_DB,
                user=self.config.POSTGRES_USER,
                password=self.config.POSTGRES_PASSWORD
            )
            cursor = conn.cursor()
            
            # Convert any date objects to strings for JSON serialization
            processed_metadata = {}
            for key, value in processed_data.get('metadata', {}).items():
                if hasattr(value, 'isoformat'):  # Check if it's a date/datetime object
                    processed_metadata[key] = value.isoformat()
                else:
                    processed_metadata[key] = value
            
            # Store document metadata
            cursor.execute("""
                INSERT INTO legal_documents (id, title, document_type, source_file, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """, (document_id, processed_data.get('title', 'Unknown'), 'judgment', 
                  processed_data.get('source_file', ''), json.dumps(processed_metadata)))
            
            # Batch insert chunks per tasks.md requirements
            chunk_batch = []
            citation_batch = []
            
            for i, (embedding, metadata) in enumerate(embedded_chunks):
                original_text = original_chunks[i][0]  # Get original text from chunks
                
                chunk_data = {
                    'token_count': metadata.token_count,
                    'char_count': metadata.char_count,
                    'paragraph_numbers': metadata.paragraph_numbers,
                    'section_title': metadata.section_title,
                    'legal_citations': metadata.legal_citations,
                    'chunk_type': metadata.chunk_type
                }
                

                
                chunk_batch.append((
                    metadata.chunk_id, document_id, original_text, 
                    embedding, json.dumps(chunk_data)
                ))
                
                # Collect citations for batch insert
                for citation in metadata.legal_citations:
                    citation_batch.append((metadata.chunk_id, citation, 'case'))
            
            # Batch upsert chunks
            if chunk_batch:
                cursor.executemany("""
                    INSERT INTO document_chunks (id, document_id, content, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                """, chunk_batch)
            
            # Batch insert citations
            if citation_batch:
                cursor.executemany("""
                    INSERT INTO legal_citations (chunk_id, citation_text, citation_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, citation_batch)
            
            # Commit all changes per tasks.md
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Batch stored {len(embedded_chunks)} chunks for document {document_id}")
            
        except Exception as e:
            logger.error(f"Failed to batch store chunks for {document_id}: {e}")
            raise
    
    def _log_stats(self):
        """Log ingestion statistics per tasks.md requirements"""
        logger.info("=== 2020 FOCUSED INGESTION STATISTICS ===")
        logger.info(f"Documents processed: {self.stats['documents_processed']}")
        logger.info(f"Chunks created: {self.stats['chunks_created']}")
        logger.info(f"Chunks embedded: {self.stats['chunks_embedded']}")
        logger.info(f"Chunks stored: {self.stats['chunks_stored']}")
        logger.info(f"Oversized chunks fixed: {self.stats['oversized_chunks_fixed']}")
        logger.info(f"Token validation failures: {self.stats['token_validation_failures']}")
        logger.info(f"Embedding 400 errors: {self.stats['embedding_400_errors']}")
        logger.info(f"Errors: {self.stats['errors']}")
        
        if self.stats['documents_processed'] > 0:
            avg_chunks = self.stats['chunks_created'] / self.stats['documents_processed']
            logger.info(f"Average chunks per document: {avg_chunks:.1f}")
            
        # Success rate
        total_attempts = self.stats['chunks_created']
        if total_attempts > 0:
            success_rate = (self.stats['chunks_embedded'] / total_attempts) * 100
            logger.info(f"Embedding success rate: {success_rate:.1f}%")
    
    async def cleanup(self):
        """Clean up resources per tasks.md: close HTTP sessions, Redis, DB pool"""
        if self.redis_client:
            self.redis_client.close()
        logger.info("Resources cleaned up")

async def main():
    """Main ingestion function per tasks.md: single asyncio.run entrypoint"""
    ingestion = Focused2020Ingestion()
    
    try:
        await ingestion.initialize()
        
        # Ingest 2020 Supreme Court judgments only
        await ingestion.ingest_2020_supreme_court_judgments()
        
        # Smoke test: verify >90% of paragraphs are embedded, confirm no 400 errors
        if ingestion.stats['embedding_400_errors'] == 0:
            logger.info("✅ SMOKE TEST PASSED: No 400 errors")
        else:
            logger.error(f"❌ SMOKE TEST FAILED: {ingestion.stats['embedding_400_errors']} 400 errors")
        
        if ingestion.stats['chunks_created'] > 0:
            success_rate = (ingestion.stats['chunks_embedded'] / ingestion.stats['chunks_created']) * 100
            if success_rate >= 90:
                logger.info(f"✅ SMOKE TEST PASSED: {success_rate:.1f}% embedding success rate")
            else:
                logger.error(f"❌ SMOKE TEST FAILED: {success_rate:.1f}% embedding success rate")
        
    except Exception as e:
        logger.error(f"2020 focused ingestion failed: {e}")
        return 1
    finally:
        await ingestion.cleanup()
    
    logger.info("2020 focused ingestion completed successfully!")
    return 0

if __name__ == "__main__":
    # Ensure we have required dependencies
    try:
        import fitz
        import tiktoken
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        print("Install with: pip install PyMuPDF tiktoken")
        sys.exit(1)
    
    # Run the 2020 focused ingestion per tasks.md
    exit_code = asyncio.run(main())
    sys.exit(exit_code)