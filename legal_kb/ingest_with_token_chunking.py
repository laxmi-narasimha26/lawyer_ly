#!/usr/bin/env python3
"""
Token-aware legal document ingestion with proper chunking
Fixes the embedding context limit issues by using smart chunking
"""
import asyncio
import os
import sys
import logging
import json
import fitz  # PyMuPDF for better PDF extraction
from pathlib import Path
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import redis

# Add the legal_kb directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from services.embedding_service import EmbeddingService
from utils.token_aware_chunking import TokenAwareChunker, ChunkMetadata
from processors.simple_processors import SupremeCourtJudgmentProcessor, BNSProcessor
# from database.connection import DatabaseConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('token_aware_ingestion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TokenAwareLegalIngestion:
    """Token-aware legal document ingestion pipeline"""
    
    def __init__(self):
        self.config = Config()
        self.db = None
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
            'oversized_chunks_fixed': 0
        }
    
    async def initialize(self):
        """Initialize all services"""
        logger.info("Initializing token-aware ingestion pipeline...")
        
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
            
            # Embedding service
            self.embedding_service = EmbeddingService(self.config.OPENAI_API_KEY)
            api_test = await self.embedding_service.test_api_connection()
            if not api_test:
                raise Exception("OpenAI API connection failed")
            logger.info("OpenAI API connected")
            
            # Token-aware chunker
            self.chunker = TokenAwareChunker()
            logger.info("Token-aware chunker initialized")
            
            # Document processors
            self.sc_processor = SupremeCourtJudgmentProcessor()
            self.bns_processor = BNSProcessor()
            logger.info("Document processors initialized")
            
            logger.info("All services initialized successfully")
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise
    
    async def ingest_supreme_court_judgments(self, data_dir: str = "indian-supreme-court-judgments"):
        """Ingest Supreme Court judgments with token-aware chunking"""
        logger.info(f"Starting Supreme Court judgment ingestion from {data_dir}")
        
        data_path = Path(data_dir)
        if not data_path.exists():
            logger.error(f"Data directory not found: {data_path}")
            return
        
        # Find all PDF files
        pdf_files = list(data_path.rglob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files")
        
        # Process files in batches
        batch_size = 10
        for i in range(0, len(pdf_files), batch_size):
            batch = pdf_files[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(pdf_files) + batch_size - 1)//batch_size}")
            
            for pdf_file in batch:
                try:
                    await self._process_judgment_pdf(pdf_file)
                except Exception as e:
                    logger.error(f"Failed to process {pdf_file}: {e}")
                    self.stats['errors'] += 1
            
            # Small delay between batches
            await asyncio.sleep(1)
        
        logger.info("Supreme Court judgment ingestion completed")
        self._log_stats()
    
    async def ingest_bns_documents(self, data_dir: str = "bns-data"):
        """Ingest BNS documents with token-aware chunking"""
        logger.info(f"Starting BNS document ingestion from {data_dir}")
        
        data_path = Path(data_dir)
        if not data_path.exists():
            logger.error(f"BNS data directory not found: {data_path}")
            return
        
        # Find all text/PDF files
        files = list(data_path.rglob("*.txt")) + list(data_path.rglob("*.pdf"))
        logger.info(f"Found {len(files)} BNS files")
        
        for file_path in files:
            try:
                await self._process_bns_file(file_path)
            except Exception as e:
                logger.error(f"Failed to process BNS file {file_path}: {e}")
                self.stats['errors'] += 1
        
        logger.info("BNS document ingestion completed")
        self._log_stats()
    
    async def _process_judgment_pdf(self, pdf_path: Path):
        """Process a single Supreme Court judgment PDF"""
        logger.info(f"Processing judgment: {pdf_path.name}")
        
        try:
            # Extract text using PyMuPDF (better than PyPDF2)
            text = self._extract_pdf_text_pymupdf(pdf_path)
            if not text or len(text.strip()) < 100:
                logger.warning(f"No meaningful text extracted from {pdf_path.name}")
                return
            
            # Process with SC processor
            processed_data = self.sc_processor.process_judgment_text(text, str(pdf_path))
            if not processed_data:
                logger.warning(f"No processed data from {pdf_path.name}")
                return
            
            # Create document ID
            document_id = f"sc_judgment_{pdf_path.stem}"
            
            # Token-aware chunking
            chunks = self.chunker.chunk_judgment_text(processed_data['content'], document_id)
            if not chunks:
                logger.warning(f"No chunks created for {pdf_path.name}")
                return
            
            # Log chunk statistics
            chunk_stats = self.chunker.get_chunk_stats(chunks)
            logger.info(f"Created {chunk_stats['total_chunks']} chunks, "
                       f"avg tokens: {chunk_stats['avg_tokens']:.1f}, "
                       f"max tokens: {chunk_stats['max_tokens']}")
            
            if chunk_stats['oversized_chunks'] > 0:
                logger.warning(f"Found {chunk_stats['oversized_chunks']} oversized chunks")
                self.stats['oversized_chunks_fixed'] += chunk_stats['oversized_chunks']
            
            # Generate embeddings
            embedded_chunks = await self.embedding_service.embed_legal_chunks(chunks)
            
            # Store in database
            await self._store_judgment_chunks(document_id, processed_data, embedded_chunks, chunks)
            
            # Update statistics
            self.stats['documents_processed'] += 1
            self.stats['chunks_created'] += len(chunks)
            self.stats['chunks_embedded'] += len(embedded_chunks)
            self.stats['chunks_stored'] += len(embedded_chunks)
            
            logger.info(f"Successfully processed {pdf_path.name}: {len(embedded_chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            raise
    
    async def _process_bns_file(self, file_path: Path):
        """Process a single BNS file"""
        logger.info(f"Processing BNS file: {file_path.name}")
        
        try:
            # Extract text
            if file_path.suffix.lower() == '.pdf':
                text = self._extract_pdf_text_pymupdf(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            
            if not text or len(text.strip()) < 100:
                logger.warning(f"No meaningful text extracted from {file_path.name}")
                return
            
            # Process with BNS processor
            processed_data = self.bns_processor.process_bns_text(text, str(file_path))
            if not processed_data:
                logger.warning(f"No processed data from {file_path.name}")
                return
            
            # Create document ID
            document_id = f"bns_{file_path.stem}"
            
            # Token-aware chunking
            chunks = self.chunker.chunk_bns_text(processed_data['content'], document_id)
            if not chunks:
                logger.warning(f"No chunks created for {file_path.name}")
                return
            
            # Log chunk statistics
            chunk_stats = self.chunker.get_chunk_stats(chunks)
            logger.info(f"Created {chunk_stats['total_chunks']} chunks, "
                       f"avg tokens: {chunk_stats['avg_tokens']:.1f}")
            
            # Generate embeddings
            embedded_chunks = await self.embedding_service.embed_legal_chunks(chunks)
            
            # Store in database
            await self._store_bns_chunks(document_id, processed_data, embedded_chunks, chunks)
            
            # Update statistics
            self.stats['documents_processed'] += 1
            self.stats['chunks_created'] += len(chunks)
            self.stats['chunks_embedded'] += len(embedded_chunks)
            self.stats['chunks_stored'] += len(embedded_chunks)
            
            logger.info(f"Successfully processed {file_path.name}: {len(embedded_chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            raise
    
    def _extract_pdf_text_pymupdf(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyMuPDF (better quality than PyPDF2)"""
        try:
            doc = fitz.open(pdf_path)
            text_parts = []
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                
                # Clean up the text
                text = self._clean_extracted_text(text)
                if text.strip():
                    text_parts.append(text)
            
            doc.close()
            return "\n\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""
    
    def _clean_extracted_text(self, text: str) -> str:
        """Clean extracted PDF text"""
        # Remove common PDF artifacts
        text = text.replace('\x0c', '')  # Form feed
        text = text.replace('\uf0b7', '•')  # Bullet point
        
        # Fix hyphenated line breaks
        import re
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text.strip()
    
    async def _store_judgment_chunks(self, document_id: str, processed_data: Dict, 
                                   embedded_chunks: List, original_chunks: List):
        """Store judgment chunks in database"""
        try:
            # Use regular psycopg2 connection since asyncpg isn't set up
            conn = psycopg2.connect(
                host=self.config.POSTGRES_HOST,
                port=self.config.POSTGRES_PORT,
                database=self.config.POSTGRES_DB,
                user=self.config.POSTGRES_USER,
                password=self.config.POSTGRES_PASSWORD
            )
            cursor = conn.cursor()
            
            # Store document metadata
            cursor.execute("""
                INSERT INTO legal_documents (id, title, document_type, source_file, metadata)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """, (document_id, processed_data.get('title', 'Unknown'), 'judgment', 
                  processed_data.get('source_file', ''), json.dumps(processed_data.get('metadata', {}))))
            
            # Store chunks with their original text
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
                
                cursor.execute("""
                    INSERT INTO document_chunks (id, document_id, content, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                """, (metadata.chunk_id, document_id, original_text, embedding, json.dumps(chunk_data)))
                
                # Store citations if any
                for citation in metadata.legal_citations:
                    cursor.execute("""
                        INSERT INTO legal_citations (chunk_id, citation_text, citation_type)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (metadata.chunk_id, citation, 'case'))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Stored {len(embedded_chunks)} chunks for document {document_id}")
            
        except Exception as e:
            logger.error(f"Failed to store chunks for {document_id}: {e}")
            raise
    
    async def _store_bns_chunks(self, document_id: str, processed_data: Dict, 
                               embedded_chunks: List, original_chunks: List):
        """Store BNS chunks in database"""
        # Similar to judgment storage but for BNS documents
        await self._store_judgment_chunks(document_id, processed_data, embedded_chunks, original_chunks)
    
    def _log_stats(self):
        """Log ingestion statistics"""
        logger.info("=== INGESTION STATISTICS ===")
        logger.info(f"Documents processed: {self.stats['documents_processed']}")
        logger.info(f"Chunks created: {self.stats['chunks_created']}")
        logger.info(f"Chunks embedded: {self.stats['chunks_embedded']}")
        logger.info(f"Chunks stored: {self.stats['chunks_stored']}")
        logger.info(f"Oversized chunks fixed: {self.stats['oversized_chunks_fixed']}")
        logger.info(f"Errors: {self.stats['errors']}")
        
        if self.stats['documents_processed'] > 0:
            avg_chunks = self.stats['chunks_created'] / self.stats['documents_processed']
            logger.info(f"Average chunks per document: {avg_chunks:.1f}")
    
    async def cleanup(self):
        """Clean up resources"""
        if self.redis_client:
            self.redis_client.close()
        logger.info("Resources cleaned up")

async def main():
    """Main ingestion function"""
    ingestion = TokenAwareLegalIngestion()
    
    try:
        await ingestion.initialize()
        
        # Ingest Supreme Court judgments
        await ingestion.ingest_supreme_court_judgments()
        
        # Ingest BNS documents (if available)
        # await ingestion.ingest_bns_documents()
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return 1
    finally:
        await ingestion.cleanup()
    
    logger.info("Token-aware ingestion completed successfully!")
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
    
    # Run the ingestion
    exit_code = asyncio.run(main())
    sys.exit(exit_code)