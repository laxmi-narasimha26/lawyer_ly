"""
Vector Store implementation using PostgreSQL with PGVector
"""
import structlog
from typing import List, Optional, Dict
import asyncpg
from pgvector.asyncpg import register_vector

from config import settings

logger = structlog.get_logger()

class VectorStore:
    def __init__(self):
        self.pool = None
    
    async def initialize(self):
        """Initialize database connection pool"""
        self.pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=5,
            max_size=20
        )
        async with self.pool.acquire() as conn:
            await register_vector(conn)
    
    async def similarity_search(
        self,
        embedding: List[float],
        top_k: int,
        document_ids: Optional[List[str]],
        user_id: str,
        db
    ) -> List[Dict]:
        """
        Perform vector similarity search
        """
        try:
            query = """
                SELECT 
                    id,
                    document_id,
                    text,
                    source_name,
                    source_type,
                    metadata,
                    1 - (embedding <=> $1::vector) as relevance_score
                FROM document_chunks
                WHERE user_id = $2
            """
            
            params = [embedding, user_id]
            
            # Filter by document_ids if provided
            if document_ids:
                query += " AND document_id = ANY($3)"
                params.append(document_ids)
            
            query += """
                ORDER BY embedding <=> $1::vector
                LIMIT ${}
            """.format(len(params) + 1)
            params.append(top_k)
            
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
            
            results = []
            for row in rows:
                results.append({
                    'id': row['id'],
                    'document_id': row['document_id'],
                    'text': row['text'],
                    'source_name': row['source_name'],
                    'source_type': row['source_type'],
                    'metadata': row['metadata'],
                    'relevance_score': float(row['relevance_score'])
                })
            
            return results
            
        except Exception as e:
            logger.error("Similarity search failed", error=str(e))
            raise
    
    async def insert_chunks(
        self,
        chunks: List[Dict],
        document_id: str,
        user_id: str,
        db
    ):
        """
        Insert document chunks with embeddings
        """
        try:
            query = """
                INSERT INTO document_chunks 
                (id, document_id, user_id, text, embedding, source_name, source_type, metadata, chunk_index)
                VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $8, $9)
            """
            
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for i, chunk in enumerate(chunks):
                        await conn.execute(
                            query,
                            chunk['id'],
                            document_id,
                            user_id,
                            chunk['text'],
                            chunk['embedding'],
                            chunk['source_name'],
                            chunk['source_type'],
                            chunk['metadata'],
                            i
                        )
            
            logger.info(
                "Chunks inserted",
                document_id=document_id,
                chunk_count=len(chunks)
            )
            
        except Exception as e:
            logger.error("Failed to insert chunks", error=str(e))
            raise
    
    async def get_chunk_by_id(
        self,
        chunk_id: str,
        user_id: str,
        db
    ) -> str:
        """
        Retrieve chunk text by ID
        """
        try:
            query = """
                SELECT text
                FROM document_chunks
                WHERE id = $1 AND user_id = $2
            """
            
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, chunk_id, user_id)
            
            if row:
                return row['text']
            else:
                raise ValueError(f"Chunk {chunk_id} not found")
                
        except Exception as e:
            logger.error("Failed to retrieve chunk", error=str(e))
            raise
    
    async def delete_document_chunks(
        self,
        document_id: str,
        user_id: str,
        db
    ):
        """
        Delete all chunks for a document
        """
        try:
            query = """
                DELETE FROM document_chunks
                WHERE document_id = $1 AND user_id = $2
            """
            
            async with self.pool.acquire() as conn:
                await conn.execute(query, document_id, user_id)
            
            logger.info("Document chunks deleted", document_id=document_id)
            
        except Exception as e:
            logger.error("Failed to delete chunks", error=str(e))
            raise

# Initialize vector store
vector_store = VectorStore()
