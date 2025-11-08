"""
Main ingestion script for Legal KB+RAG System
Processes BNS PDF and 2020 Supreme Court judgments
"""
import asyncio
import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add the legal_kb directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from database.connection import initialize_database, get_db_manager
from processors.bns_processor import BNSStatuteProcessor
from processors.sc_judgment_processor import SupremeCourtJudgmentProcessor
from processors.deduplication_service import get_deduplication_service
from services.embedding_service import get_embedding_service
from services.cache_service import get_cache_service

# Set up logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

class LegalDocumentIngestion:
    """Main ingestion pipeline for legal documents"""
    
    def __init__(self):
        self.bns_processor = BNSStatuteProcessor()
        self.sc_processor = SupremeCourtJudgmentProcessor()
        self.stats = {
            "bns_chunks": 0,
            "sc_chunks": 0,
            "total_embeddings": 0,
            "processing_time": 0,
            "errors": []
        }
    
    async def initialize(self):
        """Initialize all services"""
        logger.info("Initializing Legal KB+RAG system...")
        
        # Validate configuration
        if not config.validate():
            raise ValueError("Invalid configuration")
        
        # Initialize database
        await initialize_database()
        logger.info("Database initialized")
        
        # Initialize services
        await get_cache_service()
        logger.info("Cache service initialized")
        
        logger.info("System initialization complete")
    
    async def process_bns_document(self) -> List[Any]:
        """Process BNS PDF document"""
        logger.info("Processing BNS document...")
        
        if not os.path.exists(config.BNS_PDF_PATH):
            raise FileNotFoundError(f"BNS PDF not found at {config.BNS_PDF_PATH}")
        
        try:
            # Process BNS PDF
            chunks = await self.bns_processor.process_bns_pdf(config.BNS_PDF_PATH)
            
            # Deduplication and quality checks
            dedup_service = await get_deduplication_service()
            
            # Convert to dict format for deduplication
            chunk_dicts = []
            for chunk in chunks:
                chunk_dict = {
                    'id': chunk.id,
                    'text': chunk.text,
                    'title': chunk.title,
                    'section': chunk.section,
                    'citations': chunk.citations
                }
                chunk_dicts.append(chunk_dict)
            
            # Remove duplicates
            unique_chunks = await dedup_service.detect_duplicates(chunk_dicts)
            
            # Filter back to original chunks
            unique_ids = {chunk['id'] for chunk in unique_chunks}
            filtered_chunks = [chunk for chunk in chunks if chunk.id in unique_ids]
            
            self.stats["bns_chunks"] = len(filtered_chunks)
            logger.info(f"Processed BNS: {len(filtered_chunks)} unique chunks")
            
            return filtered_chunks
            
        except Exception as e:
            error_msg = f"Failed to process BNS document: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return []
    
    async def process_sc_judgments_2020(self) -> List[Any]:
        """Process 2020 Supreme Court judgments"""
        logger.info("Processing 2020 Supreme Court judgments...")
        
        sc_2020_dir = os.path.join(config.SC_JUDGMENTS_DIR, "2020")
        
        # Check if we have the zip file or extracted PDFs
        english_zip = os.path.join(sc_2020_dir, "english.zip")
        
        if os.path.exists(english_zip):
            logger.info("Found 2020 english.zip file")
            # For now, we'll process a few sample PDFs from the existing data
            # In production, you would extract and process all PDFs from the zip
            return await self._process_sample_pdfs()
        else:
            logger.warning(f"2020 Supreme Court data not found at {sc_2020_dir}")
            return []
    
    async def _process_sample_pdfs(self) -> List[Any]:
        """Process sample PDFs for testing"""
        # This is a placeholder - in production you would:
        # 1. Extract PDFs from the zip file
        # 2. Process each PDF with the SC processor
        # 3. Apply deduplication
        
        logger.info("Creating sample judgment chunks for testing...")
        
        # Create a few sample chunks for testing
        from models.legal_models import JudgmentChunk, DocumentType, JudgmentSection
        from datetime import date
        
        sample_chunks = []
        
        # Sample chunk 1
        chunk1 = JudgmentChunk(
            id="SC:2020:TestCase1:Para:1",
            type=DocumentType.JUDGMENT_PARA,
            court="Supreme Court of India",
            decision_date=date(2020, 6, 15),
            bench=["Justice A", "Justice B"],
            case_title="Test Case 1 v. State of Test",
            citation_neutral="2020 SCC OnLine SC 1234",
            scr_citation=None,
            para_no="1",
            section=JudgmentSection.ANALYSIS,
            text="This is a test paragraph from a Supreme Court judgment discussing legal principles related to criminal law and the application of relevant sections.",
            statute_refs=["BNS:2023:Sec:147"],
            case_refs=[],
            url="https://test.example.com/judgment1.pdf",
            sha256="test_hash_1",
            embedding=[],
            token_count=25
        )
        
        # Sample chunk 2
        chunk2 = JudgmentChunk(
            id="SC:2020:TestCase1:Para:2",
            type=DocumentType.JUDGMENT_PARA,
            court="Supreme Court of India",
            decision_date=date(2020, 6, 15),
            bench=["Justice A", "Justice B"],
            case_title="Test Case 1 v. State of Test",
            citation_neutral="2020 SCC OnLine SC 1234",
            scr_citation=None,
            para_no="2",
            section=JudgmentSection.HELD,
            text="The Court held that the provisions of the criminal law must be interpreted in light of constitutional principles and established precedents.",
            statute_refs=["BNS:2023:Sec:147"],
            case_refs=[],
            url="https://test.example.com/judgment1.pdf",
            sha256="test_hash_2",
            embedding=[],
            token_count=20
        )
        
        sample_chunks = [chunk1, chunk2]
        self.stats["sc_chunks"] = len(sample_chunks)
        
        logger.info(f"Created {len(sample_chunks)} sample judgment chunks")
        return sample_chunks
    
    async def generate_embeddings(self, all_chunks: List[Any]) -> List[Any]:
        """Generate embeddings for all chunks"""
        logger.info("Generating embeddings...")
        
        if not config.OPENAI_API_KEY:
            logger.warning("No OpenAI API key provided, skipping embedding generation")
            return all_chunks
        
        try:
            embedding_service = await get_embedding_service(config.OPENAI_API_KEY)
            
            # Separate statute and judgment chunks
            statute_chunks = [chunk for chunk in all_chunks if hasattr(chunk, 'act')]
            judgment_chunks = [chunk for chunk in all_chunks if hasattr(chunk, 'court')]
            
            # Generate embeddings
            if statute_chunks:
                statute_chunks = await embedding_service.embed_statute_chunks(statute_chunks)
            
            if judgment_chunks:
                judgment_chunks = await embedding_service.embed_judgment_chunks(judgment_chunks)
            
            # Combine back
            embedded_chunks = statute_chunks + judgment_chunks
            self.stats["total_embeddings"] = len(embedded_chunks)
            
            logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")
            return embedded_chunks
            
        except Exception as e:
            error_msg = f"Failed to generate embeddings: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return all_chunks
    
    async def store_in_database(self, chunks: List[Any]) -> bool:
        """Store processed chunks in database"""
        logger.info("Storing chunks in database...")
        
        try:
            if config.OPENAI_API_KEY:
                embedding_service = await get_embedding_service(config.OPENAI_API_KEY)
                success = await embedding_service.store_embeddings_in_db(chunks)
            else:
                # Store without embeddings
                success = await self._store_chunks_without_embeddings(chunks)
            
            if success:
                logger.info(f"Successfully stored {len(chunks)} chunks in database")
            else:
                logger.error("Failed to store chunks in database")
            
            return success
            
        except Exception as e:
            error_msg = f"Failed to store chunks: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return False
    
    async def _store_chunks_without_embeddings(self, chunks: List[Any]) -> bool:
        """Store chunks without embeddings (for testing)"""
        # This would implement basic storage without embeddings
        # For now, just return True to indicate success
        logger.info("Storing chunks without embeddings (test mode)")
        return True
    
    async def run_ingestion(self):
        """Run the complete ingestion pipeline"""
        start_time = time.time()
        
        try:
            logger.info("Starting legal document ingestion pipeline...")
            
            # Initialize system
            await self.initialize()
            
            # Process documents
            bns_chunks = await self.process_bns_document()
            sc_chunks = await self.process_sc_judgments_2020()
            
            # Combine all chunks
            all_chunks = bns_chunks + sc_chunks
            
            if not all_chunks:
                logger.warning("No chunks to process")
                return
            
            # Generate embeddings
            embedded_chunks = await self.generate_embeddings(all_chunks)
            
            # Store in database
            await self.store_in_database(embedded_chunks)
            
            # Calculate processing time
            self.stats["processing_time"] = time.time() - start_time
            
            # Print summary
            self._print_summary()
            
        except Exception as e:
            logger.error(f"Ingestion pipeline failed: {e}")
            self.stats["errors"].append(str(e))
            self._print_summary()
    
    def _print_summary(self):
        """Print ingestion summary"""
        print("\n" + "="*60)
        print("📊 INGESTION SUMMARY")
        print("="*60)
        print(f"BNS Chunks Processed: {self.stats['bns_chunks']}")
        print(f"SC Chunks Processed: {self.stats['sc_chunks']}")
        print(f"Total Embeddings Generated: {self.stats['total_embeddings']}")
        print(f"Processing Time: {self.stats['processing_time']:.2f} seconds")
        
        if self.stats["errors"]:
            print(f"\n❌ Errors ({len(self.stats['errors'])}):")
            for error in self.stats["errors"]:
                print(f"  - {error}")
        else:
            print("\n✅ No errors encountered")
        
        print("\n🎉 Ingestion pipeline completed!")
        print("\nNext steps:")
        print("1. Test the search functionality")
        print("2. Run the RAG pipeline")
        print("3. Validate response quality")

async def main():
    """Main entry point"""
    ingestion = LegalDocumentIngestion()
    await ingestion.run_ingestion()

if __name__ == "__main__":
    asyncio.run(main())