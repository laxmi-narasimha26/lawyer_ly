#!/usr/bin/env python3
"""
Local Document Ingestion Script
Processes local knowledge base documents and creates embeddings
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
import openai
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import redis
import hashlib
from datetime import datetime

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

try:
    from config.local_settings import DATABASE_CONFIG, OPENAI_CONFIG, REDIS_CONFIG
    from utils.text_processing import TextProcessor
except ImportError:
    # Fallback configuration if imports fail
    DATABASE_CONFIG = {
        "url": os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/legal_ai_db")
    }
    OPENAI_CONFIG = {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "embedding_model": "text-embedding-ada-002"
    }
    REDIS_CONFIG = {
        "url": os.getenv("REDIS_URL", "redis://localhost:6379")
    }

class SimpleTextProcessor:
    """Simple text processor if the main one is not available"""
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50, preserve_legal_structure: bool = True) -> List[str]:
        """Simple text chunking"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk = ' '.join(chunk_words)
            if len(chunk.strip()) > 50:  # Only add substantial chunks
                chunks.append(chunk)
        
        return chunks

class LocalDocumentIngestion:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=OPENAI_CONFIG["api_key"])
        
        # Try to use the main text processor, fallback to simple one
        try:
            from utils.text_processing import TextProcessor
            self.text_processor = TextProcessor()
        except ImportError:
            self.text_processor = SimpleTextProcessor()
        
        try:
            self.redis_client = redis.Redis.from_url(REDIS_CONFIG["url"])
        except:
            self.redis_client = None
        
        # Database setup
        self.engine = create_engine(DATABASE_CONFIG["url"])
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        self.kb_path = Path("./data/knowledge_base")
        
    async def setup_database(self):
        """Set up database tables and extensions"""
        print("Setting up database...")
        
        # Enable pgvector extension
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        
        # Create tables
        create_tables_sql = """
        -- Documents table
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            filename VARCHAR(255) NOT NULL,
            title VARCHAR(255),
            content TEXT NOT NULL,
            document_type VARCHAR(50),
            file_size INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Chunks table with embeddings
        CREATE TABLE IF NOT EXISTS chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            embedding vector(1536),
            chunk_index INTEGER NOT NULL,
            token_count INTEGER,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Create vector similarity index
        CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks 
        USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100);
        
        -- Create other indexes
        CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
        CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
        """
        
        with self.engine.connect() as conn:
            conn.execute(text(create_tables_sql))
            conn.commit()
        
        print("✓ Database setup complete")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=OPENAI_CONFIG["embedding_model"],
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None
    
    async def process_document(self, file_path: Path) -> Dict[str, Any]:
        """Process a single document"""
        print(f"Processing {file_path.name}...")
        
        # Read document content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Insert document record
        doc_id = self._insert_document(file_path, content)
        
        # Chunk the document
        chunks = self.text_processor.chunk_text(
            content, 
            chunk_size=500, 
            overlap=50,
            preserve_legal_structure=True
        )
        
        print(f"  Created {len(chunks)} chunks")
        
        # Process chunks and generate embeddings
        processed_chunks = 0
        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 50:  # Skip very short chunks
                continue
                
            # Generate embedding
            embedding = await self.generate_embedding(chunk)
            if embedding is None:
                continue
            
            # Insert chunk with embedding
            self._insert_chunk(doc_id, chunk, embedding, i)
            processed_chunks += 1
            
            if processed_chunks % 5 == 0:
                print(f"  Processed {processed_chunks} chunks...")
        
        print(f"✓ Completed {file_path.name} - {processed_chunks} chunks indexed")
        return {
            "document_id": doc_id,
            "filename": file_path.name,
            "chunks_processed": processed_chunks,
            "total_chunks": len(chunks)
        }
    
    def _insert_document(self, file_path: Path, content: str) -> str:
        """Insert document into database"""
        doc_type = self._determine_document_type(file_path.name)
        title = file_path.stem.replace('_', ' ').title()
        
        insert_sql = """
        INSERT INTO documents (filename, title, content, document_type, file_size)
        VALUES (:filename, :title, :content, :doc_type, :file_size)
        RETURNING id
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(insert_sql), {
                "filename": file_path.name,
                "title": title,
                "content": content,
                "doc_type": doc_type,
                "file_size": len(content)
            })
            doc_id = result.fetchone()[0]
            conn.commit()
            return str(doc_id)
    
    def _insert_chunk(self, document_id: str, content: str, embedding: List[float], index: int):
        """Insert chunk with embedding into database"""
        insert_sql = """
        INSERT INTO chunks (document_id, content, embedding, chunk_index, token_count, metadata)
        VALUES (:doc_id, :content, :embedding, :index, :token_count, :metadata)
        """
        
        # Estimate token count (rough approximation)
        token_count = len(content.split()) * 1.3
        
        metadata = {
            "source_file": document_id,
            "chunk_type": "text",
            "processed_at": datetime.now().isoformat()
        }
        
        with self.engine.connect() as conn:
            conn.execute(text(insert_sql), {
                "doc_id": document_id,
                "content": content,
                "embedding": embedding,
                "index": index,
                "token_count": int(token_count),
                "metadata": json.dumps(metadata)
            })
            conn.commit()
    
    def _determine_document_type(self, filename: str) -> str:
        """Determine document type from filename"""
        filename_lower = filename.lower()
        if 'constitution' in filename_lower:
            return 'constitutional_law'
        elif 'contract' in filename_lower:
            return 'contract_law'
        elif 'ipc' in filename_lower or 'penal' in filename_lower:
            return 'criminal_law'
        elif 'case' in filename_lower:
            return 'case_law'
        elif 'procedure' in filename_lower or 'limitation' in filename_lower:
            return 'procedural_law'
        else:
            return 'general'
    
    async def ingest_all_documents(self):
        """Ingest all documents in the knowledge base"""
        print("Starting local document ingestion...")
        print("=" * 50)
        
        # Setup database
        await self.setup_database()
        
        # Find all text files
        text_files = list(self.kb_path.glob("*.txt"))
        if not text_files:
            print("❌ No text files found in knowledge base directory")
            return
        
        print(f"Found {len(text_files)} documents to process")
        
        # Process each document
        results = []
        for file_path in text_files:
            try:
                result = await self.process_document(file_path)
                results.append(result)
            except Exception as e:
                print(f"❌ Error processing {file_path.name}: {e}")
        
        # Summary
        print("=" * 50)
        print("📊 Ingestion Summary:")
        total_chunks = sum(r["chunks_processed"] for r in results)
        print(f"✅ Documents processed: {len(results)}")
        print(f"✅ Total chunks indexed: {total_chunks}")
        print(f"✅ Average chunks per document: {total_chunks / len(results):.1f}")
        
        # Update metadata
        self._update_metadata(results)
        
        print("\n🎉 Local knowledge base ingestion complete!")
        print("You can now start the backend and test queries.")
    
    def _update_metadata(self, results: List[Dict]):
        """Update metadata file with ingestion results"""
        metadata_path = self.kb_path / "metadata.json"
        
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {"documents": []}
        
        # Update document status
        for result in results:
            for doc in metadata["documents"]:
                if doc["filename"] == result["filename"]:
                    doc["indexed"] = True
                    doc["chunks_count"] = result["chunks_processed"]
                    doc["indexed_at"] = datetime.now().isoformat()
        
        metadata["last_ingestion"] = datetime.now().isoformat()
        metadata["total_indexed_chunks"] = sum(r["chunks_processed"] for r in results)
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

async def main():
    """Main ingestion function"""
    ingestion = LocalDocumentIngestion()
    await ingestion.ingest_all_documents()

if __name__ == "__main__":
    asyncio.run(main())