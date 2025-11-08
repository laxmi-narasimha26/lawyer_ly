#!/usr/bin/env python3
"""
Supreme Court Judgments Ingestion Script
Processes downloaded Supreme Court judgments and creates embeddings for RAG
"""

import os
import sys
import json
import asyncio
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import re
import PyPDF2
from io import BytesIO

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

try:
    from config.local_settings import DATABASE_CONFIG, OPENAI_CONFIG, REDIS_CONFIG
    from services.local_openai_service import local_openai_service
    from utils.text_processing import TextProcessor
except ImportError:
    # Fallback configuration if imports fail
    DATABASE_CONFIG = {
        "url": os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/legal_ai_db")
    }
    OPENAI_CONFIG = {
        "api_key": os.getenv("OPENAI_API_KEY", "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"),
        "embedding_model": "text-embedding-ada-002"
    }

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import openai

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleTextProcessor:
    """Simple text processor if the main one is not available"""
    
    def chunk_text(self, text: str, chunk_size: int = 6000, overlap: int = 200, preserve_legal_structure: bool = True) -> List[str]:
        """Optimized text chunking based on Supreme Court data analysis"""
        if not text or len(text.strip()) < 50:
            return []
        
        # Clean text
        text = re.sub(r'\s+', ' ', text.strip())
        
        # If preserving legal structure, use hierarchical chunking
        if preserve_legal_structure:
            # Primary legal section markers (high priority based on analysis)
            primary_markers = [
                (r'\bJUDGMENT\b', 'JUDGMENT'),
                (r'\bORDER\b', 'ORDER'),
                (r'\bHELD\s*:', 'HELD'),
                (r'\bFACTS\s*:', 'FACTS'),
                (r'\bCONCLUSION\s*:', 'CONCLUSION'),
                (r'\bDISPOSAL\s*:', 'DISPOSAL')
            ]
            
            # Secondary markers for fine-grained chunking
            secondary_markers = [
                r'\d+\.\s+',  # Numbered sections (very common - 100% frequency)
                r'\([a-z]\)\s+',  # Lettered subsections (80% frequency)
                r'\([ivx]+\)\s+',  # Roman numeral subsections
            ]
            
            # Try hierarchical chunking
            chunks = self._hierarchical_legal_chunking(text, primary_markers, secondary_markers, chunk_size, overlap)
            if chunks:
                return chunks
        
        # Fallback to sentence-based chunking
        return self._chunk_by_sentences(text, chunk_size, overlap)
    
    def _hierarchical_legal_chunking(self, text: str, primary_markers: List, secondary_markers: List, 
                                   chunk_size: int, overlap: int) -> List[str]:
        """Hierarchical chunking based on legal document structure"""
        chunks = []
        
        # First, try to split on primary legal markers
        for pattern, marker_type in primary_markers:
            if re.search(pattern, text, re.IGNORECASE):
                sections = re.split(f'({pattern})', text, flags=re.IGNORECASE)
                
                if len(sections) > 2:  # Found meaningful splits
                    current_section = ""
                    
                    for i, section in enumerate(sections):
                        if re.match(pattern, section, re.IGNORECASE):
                            # This is a marker, start new section
                            if current_section.strip() and len(current_section) > 100:
                                # Process the previous section
                                section_chunks = self._process_section(current_section, secondary_markers, chunk_size, overlap)
                                chunks.extend(section_chunks)
                            current_section = section
                        else:
                            current_section += section
                    
                    # Process final section
                    if current_section.strip() and len(current_section) > 100:
                        section_chunks = self._process_section(current_section, secondary_markers, chunk_size, overlap)
                        chunks.extend(section_chunks)
                    
                    if chunks:
                        return chunks
        
        return []
    
    def _process_section(self, section: str, secondary_markers: List[str], chunk_size: int, overlap: int) -> List[str]:
        """Process a legal section with secondary markers"""
        # If section is small enough, return as single chunk
        if len(section) <= chunk_size:
            return [section.strip()] if section.strip() else []
        
        # Try to split on secondary markers
        for pattern in secondary_markers:
            if re.search(pattern, section):
                subsections = re.split(f'({pattern})', section)
                
                if len(subsections) > 2:
                    chunks = []
                    current_chunk = ""
                    
                    for subsection in subsections:
                        if re.match(pattern, subsection):
                            # This is a marker
                            if current_chunk and len(current_chunk) > chunk_size:
                                # Current chunk is too large, split it
                                chunk_parts = self._chunk_by_sentences(current_chunk, chunk_size, overlap)
                                chunks.extend(chunk_parts)
                                current_chunk = subsection
                            else:
                                current_chunk += subsection
                        else:
                            # Regular content
                            if len(current_chunk + subsection) > chunk_size and current_chunk:
                                chunks.append(current_chunk.strip())
                                # Start new chunk with overlap
                                if overlap > 0:
                                    words = current_chunk.split()
                                    overlap_words = words[-overlap//10:] if len(words) > overlap//10 else words
                                    current_chunk = " ".join(overlap_words) + " " + subsection
                                else:
                                    current_chunk = subsection
                            else:
                                current_chunk += subsection
                    
                    # Add final chunk
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    
                    return [chunk for chunk in chunks if len(chunk.strip()) > 50]
        
        # Fallback to sentence-based chunking
        return self._chunk_by_sentences(section, chunk_size, overlap)
    
    def _chunk_by_sentences(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Chunk text by sentences"""
        # Split into sentences
        sentences = re.split(r'[.!?]+\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                
                # Start new chunk with overlap
                if overlap > 0:
                    words = current_chunk.split()
                    overlap_words = words[-overlap:] if len(words) > overlap else words
                    current_chunk = " ".join(overlap_words) + " " + sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return [chunk for chunk in chunks if len(chunk.strip()) > 50]

class SupremeCourtIngestionPipeline:
    """
    Processes Supreme Court judgments and creates embeddings for RAG
    """
    
    def __init__(self, data_dir: str = "./data/supreme_court_judgments"):
        self.data_dir = Path(data_dir)
        self.openai_client = openai.OpenAI(api_key=OPENAI_CONFIG["api_key"])
        
        # Try to use the main text processor, fallback to simple one
        try:
            from utils.text_processing import TextProcessor
            self.text_processor = TextProcessor()
        except ImportError:
            self.text_processor = SimpleTextProcessor()
        
        # Database setup
        self.engine = create_engine(DATABASE_CONFIG["url"])
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Processing stats
        self.stats = {
            "total_judgments": 0,
            "processed_judgments": 0,
            "total_chunks": 0,
            "failed_judgments": 0,
            "years_processed": [],
            "processing_errors": []
        }
    
    def setup_database(self):
        """Set up database tables for Supreme Court judgments"""
        logger.info("Setting up database for Supreme Court judgments...")
        
        create_tables_sql = """
        -- Supreme Court judgments table
        CREATE TABLE IF NOT EXISTS sc_judgments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id VARCHAR(255) UNIQUE NOT NULL,
            title TEXT,
            petitioner TEXT,
            respondent TEXT,
            judge TEXT,
            author_judge TEXT,
            citation VARCHAR(255),
            decision_date DATE,
            disposal_nature VARCHAR(255),
            court VARCHAR(255) DEFAULT 'Supreme Court of India',
            year INTEGER,
            pdf_path VARCHAR(500),
            metadata JSONB DEFAULT '{}'::jsonb,
            full_text TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Supreme Court judgment chunks with embeddings
        CREATE TABLE IF NOT EXISTS sc_judgment_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            judgment_id UUID REFERENCES sc_judgments(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            embedding vector(1536),
            chunk_index INTEGER NOT NULL,
            chunk_type VARCHAR(50) DEFAULT 'content',
            token_count INTEGER,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_sc_judgments_year ON sc_judgments(year);
        CREATE INDEX IF NOT EXISTS idx_sc_judgments_date ON sc_judgments(decision_date);
        CREATE INDEX IF NOT EXISTS idx_sc_judgments_citation ON sc_judgments(citation);
        CREATE INDEX IF NOT EXISTS idx_sc_judgment_chunks_judgment_id ON sc_judgment_chunks(judgment_id);
        CREATE INDEX IF NOT EXISTS idx_sc_judgment_chunks_type ON sc_judgment_chunks(chunk_type);
        
        -- Vector similarity index
        CREATE INDEX IF NOT EXISTS sc_judgment_chunks_embedding_idx ON sc_judgment_chunks 
        USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100);
        """
        
        with self.engine.connect() as conn:
            conn.execute(text(create_tables_sql))
            conn.commit()
        
        logger.info("✅ Database setup complete")
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract text from PDF content"""
        try:
            pdf_file = BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                except Exception as e:
                    logger.warning(f"Error extracting text from page: {e}")
                    continue
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""
    
    def parse_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and clean metadata from Supreme Court judgment"""
        parsed = {
            "title": "",
            "petitioner": "",
            "respondent": "",
            "judge": "",
            "author_judge": "",
            "citation": "",
            "decision_date": None,
            "disposal_nature": "",
            "case_id": "",
            "cnr": "",
            "court": "Supreme Court of India"
        }
        
        try:
            # Extract from raw HTML if available
            raw_html = metadata.get("raw_html", "")
            
            if raw_html:
                # Extract title
                title_match = re.search(r'<strong[^>]*>(.*?)</strong>', raw_html, re.IGNORECASE | re.DOTALL)
                if title_match:
                    parsed["title"] = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                
                # Extract petitioner and respondent
                vs_match = re.search(r'(.*?)\s+[Vv][Ss]\.?\s+(.*?)(?:<br|$)', parsed["title"])
                if vs_match:
                    parsed["petitioner"] = vs_match.group(1).strip()
                    parsed["respondent"] = vs_match.group(2).strip()
                
                # Extract decision date
                date_match = re.search(r'Decision Date\s*:\s*<[^>]*>\s*(\d{2}-\d{2}-\d{4})', raw_html)
                if date_match:
                    try:
                        date_str = date_match.group(1)
                        parsed["decision_date"] = datetime.strptime(date_str, "%d-%m-%Y").date()
                    except ValueError:
                        pass
                
                # Extract judge information
                judge_match = re.search(r'Judge\(s\)\s*:\s*<[^>]*>(.*?)</font>', raw_html, re.IGNORECASE)
                if judge_match:
                    parsed["judge"] = re.sub(r'<[^>]+>', '', judge_match.group(1)).strip()
            
            # Use direct metadata fields if available
            for field in ["title", "petitioner", "respondent", "judge", "citation", "disposal_nature"]:
                if field in metadata and metadata[field]:
                    parsed[field] = str(metadata[field]).strip()
            
            # Extract case ID from path
            path = metadata.get("path", "")
            if path:
                parsed["case_id"] = path
            
            # Extract citation
            nc_display = metadata.get("nc_display", "")
            if nc_display:
                parsed["citation"] = nc_display
            
        except Exception as e:
            logger.error(f"Error parsing metadata: {e}")
        
        return parsed
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=OPENAI_CONFIG["embedding_model"],
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def insert_judgment(self, judgment_data: Dict[str, Any]) -> str:
        """Insert judgment into database and return ID"""
        insert_sql = """
        INSERT INTO sc_judgments (
            case_id, title, petitioner, respondent, judge, author_judge, 
            citation, decision_date, disposal_nature, court, year, 
            pdf_path, metadata, full_text
        ) VALUES (
            :case_id, :title, :petitioner, :respondent, :judge, :author_judge,
            :citation, :decision_date, :disposal_nature, :court, :year,
            :pdf_path, :metadata, :full_text
        ) 
        ON CONFLICT (case_id) DO UPDATE SET
            updated_at = NOW(),
            full_text = EXCLUDED.full_text
        RETURNING id
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(insert_sql), judgment_data)
            judgment_id = result.fetchone()[0]
            conn.commit()
            return str(judgment_id)
    
    def insert_chunk(self, judgment_id: str, chunk_data: Dict[str, Any]):
        """Insert chunk with embedding into database"""
        insert_sql = """
        INSERT INTO sc_judgment_chunks (
            judgment_id, content, embedding, chunk_index, chunk_type, 
            token_count, metadata
        ) VALUES (
            :judgment_id, :content, :embedding, :chunk_index, :chunk_type,
            :token_count, :metadata
        )
        """
        
        with self.engine.connect() as conn:
            conn.execute(text(insert_sql), chunk_data)
            conn.commit()
    
    async def process_judgment(self, pdf_content: bytes, metadata: Dict[str, Any], year: int) -> bool:
        """Process a single Supreme Court judgment"""
        try:
            # Extract text from PDF
            full_text = self.extract_text_from_pdf(pdf_content)
            if not full_text or len(full_text.strip()) < 100:
                logger.warning("Insufficient text extracted from PDF")
                return False
            
            # Parse metadata
            parsed_metadata = self.parse_metadata(metadata)
            
            # Prepare judgment data
            judgment_data = {
                "case_id": parsed_metadata["case_id"] or f"sc_{year}_{datetime.now().timestamp()}",
                "title": parsed_metadata["title"][:500] if parsed_metadata["title"] else "",
                "petitioner": parsed_metadata["petitioner"][:500] if parsed_metadata["petitioner"] else "",
                "respondent": parsed_metadata["respondent"][:500] if parsed_metadata["respondent"] else "",
                "judge": parsed_metadata["judge"][:500] if parsed_metadata["judge"] else "",
                "author_judge": parsed_metadata.get("author_judge", "")[:500],
                "citation": parsed_metadata["citation"][:255] if parsed_metadata["citation"] else "",
                "decision_date": parsed_metadata["decision_date"],
                "disposal_nature": parsed_metadata.get("disposal_nature", "")[:255],
                "court": "Supreme Court of India",
                "year": year,
                "pdf_path": metadata.get("path", ""),
                "metadata": json.dumps(metadata),
                "full_text": full_text
            }
            
            # Insert judgment
            judgment_id = self.insert_judgment(judgment_data)
            
            # Chunk the text using optimized parameters based on analysis
            chunks = self.text_processor.chunk_text(
                full_text,
                chunk_size=6000,  # Optimized based on avg text length analysis
                overlap=200,      # Increased overlap for better context retention
                preserve_legal_structure=True
            )
            
            logger.info(f"  Created {len(chunks)} chunks for judgment {judgment_data['case_id']}")
            
            # Process chunks and generate embeddings
            processed_chunks = 0
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 50:
                    continue
                
                # Generate embedding
                embedding = await self.generate_embedding(chunk)
                if embedding is None:
                    continue
                
                # Prepare chunk data
                chunk_data = {
                    "judgment_id": judgment_id,
                    "content": chunk,
                    "embedding": embedding,
                    "chunk_index": i,
                    "chunk_type": "content",
                    "token_count": len(chunk.split()) * 1.3,  # Rough estimate
                    "metadata": json.dumps({
                        "case_id": judgment_data["case_id"],
                        "year": year,
                        "citation": judgment_data["citation"],
                        "chunk_type": "judgment_content"
                    })
                }
                
                # Insert chunk
                self.insert_chunk(judgment_id, chunk_data)
                processed_chunks += 1
                
                if processed_chunks % 10 == 0:
                    logger.info(f"    Processed {processed_chunks} chunks...")
            
            self.stats["processed_judgments"] += 1
            self.stats["total_chunks"] += processed_chunks
            
            logger.info(f"✅ Processed judgment: {judgment_data['case_id']} ({processed_chunks} chunks)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing judgment: {e}")
            self.stats["failed_judgments"] += 1
            self.stats["processing_errors"].append(str(e))
            return False
    
    async def process_year_data(self, year: int, max_judgments: Optional[int] = None) -> bool:
        """Process all judgments for a specific year"""
        logger.info(f"📅 Processing Supreme Court judgments for year {year}")
        
        year_dir = self.data_dir / str(year)
        english_zip = year_dir / "english.zip"
        metadata_zip = year_dir / "metadata.zip"
        
        if not english_zip.exists() or not metadata_zip.exists():
            logger.error(f"Required files not found for year {year}")
            return False
        
        try:
            # Load metadata index
            metadata_files = {}
            with zipfile.ZipFile(metadata_zip, 'r') as meta_zip:
                for filename in meta_zip.namelist():
                    if filename.endswith('.json'):
                        with meta_zip.open(filename) as f:
                            metadata = json.load(f)
                            # Map PDF filename to metadata
                            base_name = filename.replace('.json', '')
                            pdf_filename = f"{base_name}_EN.pdf"
                            metadata_files[pdf_filename] = metadata
            
            logger.info(f"Found {len(metadata_files)} metadata files for year {year}")
            
            # Process PDF files
            processed_count = 0
            with zipfile.ZipFile(english_zip, 'r') as eng_zip:
                pdf_files = [f for f in eng_zip.namelist() if f.endswith('.pdf')]
                
                if max_judgments:
                    pdf_files = pdf_files[:max_judgments]
                
                self.stats["total_judgments"] += len(pdf_files)
                logger.info(f"Processing {len(pdf_files)} PDF files...")
                
                for pdf_file in pdf_files:
                    try:
                        # Get corresponding metadata
                        if pdf_file not in metadata_files:
                            logger.warning(f"No metadata found for {pdf_file}")
                            continue
                        
                        metadata = metadata_files[pdf_file]
                        
                        # Extract PDF content
                        with eng_zip.open(pdf_file) as f:
                            pdf_content = f.read()
                        
                        # Process the judgment
                        success = await self.process_judgment(pdf_content, metadata, year)
                        
                        if success:
                            processed_count += 1
                        
                        # Progress update
                        if processed_count % 10 == 0:
                            logger.info(f"  Progress: {processed_count}/{len(pdf_files)} judgments processed")
                        
                        # Rate limiting to avoid overwhelming OpenAI API
                        if processed_count % 5 == 0:
                            await asyncio.sleep(1)  # Brief pause every 5 judgments
                        
                    except Exception as e:
                        logger.error(f"Error processing {pdf_file}: {e}")
                        self.stats["failed_judgments"] += 1
                        continue
            
            self.stats["years_processed"].append(year)
            logger.info(f"✅ Completed year {year}: {processed_count} judgments processed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing year {year}: {e}")
            return False
    
    async def process_all_years(self, max_judgments_per_year: Optional[int] = None) -> bool:
        """Process all available years"""
        logger.info("🚀 Starting Supreme Court judgments ingestion")
        
        # Setup database
        self.setup_database()
        
        # Find available years
        available_years = []
        for year_dir in self.data_dir.iterdir():
            if year_dir.is_dir() and year_dir.name.isdigit():
                year = int(year_dir.name)
                if (year_dir / "english.zip").exists() and (year_dir / "metadata.zip").exists():
                    available_years.append(year)
        
        available_years.sort()
        logger.info(f"Found {len(available_years)} years with complete data: {available_years}")
        
        # Process each year
        success = True
        for i, year in enumerate(available_years, 1):
            logger.info(f"📅 Processing year {year} ({i}/{len(available_years)})")
            year_success = await self.process_year_data(year, max_judgments_per_year)
            success &= year_success
            
            # Progress update
            progress = (i / len(available_years)) * 100
            logger.info(f"📈 Overall progress: {progress:.1f}% ({i}/{len(available_years)} years)")
        
        return success
    
    def get_ingestion_summary(self) -> Dict[str, Any]:
        """Get summary of ingestion process"""
        return {
            "stats": self.stats,
            "data_directory": str(self.data_dir),
            "timestamp": datetime.now().isoformat(),
            "success_rate": (self.stats["processed_judgments"] / max(self.stats["total_judgments"], 1)) * 100
        }
    
    def save_ingestion_summary(self):
        """Save ingestion summary to file"""
        summary = self.get_ingestion_summary()
        summary_file = self.data_dir / "ingestion_summary.json"
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📄 Ingestion summary saved to: {summary_file}")

async def main():
    """Main function with command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest Supreme Court Judgments into RAG Database")
    parser.add_argument("--data-dir", default="./data/supreme_court_judgments",
                       help="Directory containing downloaded Supreme Court data")
    parser.add_argument("--year", type=int,
                       help="Process specific year only")
    parser.add_argument("--max-judgments", type=int,
                       help="Maximum judgments to process per year (for testing)")
    parser.add_argument("--setup-only", action="store_true",
                       help="Only setup database tables and exit")
    
    args = parser.parse_args()
    
    # Initialize ingestion pipeline
    pipeline = SupremeCourtIngestionPipeline(args.data_dir)
    
    try:
        if args.setup_only:
            pipeline.setup_database()
            logger.info("✅ Database setup complete")
            return
        
        if args.year:
            # Process specific year
            pipeline.setup_database()
            success = await pipeline.process_year_data(args.year, args.max_judgments)
        else:
            # Process all years
            success = await pipeline.process_all_years(args.max_judgments)
        
        # Save summary
        pipeline.save_ingestion_summary()
        
        if success:
            logger.info("🎉 Ingestion completed successfully!")
            summary = pipeline.get_ingestion_summary()
            logger.info(f"📊 Processed {summary['stats']['processed_judgments']} judgments")
            logger.info(f"📊 Created {summary['stats']['total_chunks']} chunks")
            logger.info(f"📊 Success rate: {summary['success_rate']:.1f}%")
        else:
            logger.error("❌ Ingestion completed with errors")
    
    except KeyboardInterrupt:
        logger.info("Ingestion interrupted by user")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())