"""
Document processing module for parsing and chunking documents
"""
import structlog
from typing import List, Dict, Optional
import uuid
import fitz  # PyMuPDF
from docx import Document as DocxDocument
import io
from fastapi import UploadFile, BackgroundTasks
from datetime import datetime

from config import settings
from vector_store import VectorStore
from azure_storage import AzureStorageClient
from chunking import DocumentChunker
from models import DocumentInfo, DocumentStatus

logger = structlog.get_logger()

class DocumentProcessor:
    def __init__(self):
        self.vector_store = VectorStore()
        self.storage_client = AzureStorageClient()
        self.chunker = DocumentChunker()
    
    async def process_upload(
        self,
        file: UploadFile,
        user_id: str,
        db,
        background_tasks: BackgroundTasks
    ) -> str:
        """
        Process uploaded document
        """
        document_id = str(uuid.uuid4())
        
        try:
            # Read file content
            content = await file.read()
            
            # Upload to Azure Blob Storage
            blob_url = await self.storage_client.upload_blob(
                container=settings.AZURE_STORAGE_CONTAINER_NAME,
                blob_name=f"{user_id}/{document_id}/{file.filename}",
                data=content
            )
            
            # Create document record
            await self._create_document_record(
                document_id=document_id,
                user_id=user_id,
                filename=file.filename,
                size_bytes=len(content),
                blob_url=blob_url,
                db=db
            )
            
            # Schedule background processing
            background_tasks.add_task(
                self._process_document_async,
                document_id=document_id,
                user_id=user_id,
                filename=file.filename,
                content=content,
                db=db
            )
            
            return document_id
            
        except Exception as e:
            logger.error(
                "Document upload failed",
                document_id=document_id,
                error=str(e)
            )
            raise
    
    async def _process_document_async(
        self,
        document_id: str,
        user_id: str,
        filename: str,
        content: bytes,
        db
    ):
        """
        Background task to process document
        """
        try:
            # Update status to processing
            await self._update_document_status(
                document_id=document_id,
                status="processing",
                progress=10,
                db=db
            )
            
            # Extract text based on file type
            if filename.lower().endswith('.pdf'):
                text, page_count = await self._extract_pdf_text(content)
            elif filename.lower().endswith('.docx'):
                text, page_count = await self._extract_docx_text(content)
            elif filename.lower().endswith('.txt'):
                text = content.decode('utf-8')
                page_count = None
            else:
                raise ValueError(f"Unsupported file type: {filename}")
            
            await self._update_document_status(
                document_id=document_id,
                status="processing",
                progress=40,
                db=db
            )
            
            # Chunk the text
            chunks = await self.chunker.chunk_text(
                text=text,
                source_name=filename,
                source_type="user_document",
                metadata={"filename": filename, "page_count": page_count}
            )
            
            await self._update_document_status(
                document_id=document_id,
                status="processing",
                progress=60,
                db=db
            )
            
            # Generate embeddings and store
            await self._embed_and_store_chunks(
                chunks=chunks,
                document_id=document_id,
                user_id=user_id,
                db=db
            )
            
            # Update document with page count
            await self._update_document_metadata(
                document_id=document_id,
                page_count=page_count,
                db=db
            )
            
            # Mark as completed
            await self._update_document_status(
                document_id=document_id,
                status="completed",
                progress=100,
                message="Document processed successfully",
                db=db
            )
            
            logger.info(
                "Document processed successfully",
                document_id=document_id,
                chunk_count=len(chunks)
            )
            
        except Exception as e:
            logger.error(
                "Document processing failed",
                document_id=document_id,
                error=str(e),
                exc_info=True
            )
            await self._update_document_status(
                document_id=document_id,
                status="failed",
                progress=0,
                message=f"Processing failed: {str(e)}",
                db=db
            )
    
    async def _extract_pdf_text(self, content: bytes) -> tuple[str, int]:
        """Extract text from PDF"""
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            text_parts = []
            
            for page in doc:
                text_parts.append(page.get_text())
            
            page_count = len(doc)
            doc.close()
            
            return "\n\n".join(text_parts), page_count
            
        except Exception as e:
            logger.error("PDF extraction failed", error=str(e))
            raise
    
    async def _extract_docx_text(self, content: bytes) -> tuple[str, Optional[int]]:
        """Extract text from DOCX"""
        try:
            doc = DocxDocument(io.BytesIO(content))
            text_parts = []
            
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)
            
            return "\n\n".join(text_parts), None
            
        except Exception as e:
            logger.error("DOCX extraction failed", error=str(e))
            raise
    
    async def _embed_and_store_chunks(
        self,
        chunks: List[Dict],
        document_id: str,
        user_id: str,
        db
    ):
        """
        Generate embeddings for chunks and store in vector database
        """
        from openai import AsyncAzureOpenAI
        
        client = AsyncAzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )
        
        # Generate embeddings in batches
        batch_size = 20
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [chunk['text'] for chunk in batch]
            
            response = await client.embeddings.create(
                input=texts,
                model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
            )
            
            for j, embedding_data in enumerate(response.data):
                batch[j]['embedding'] = embedding_data.embedding
                batch[j]['id'] = str(uuid.uuid4())
        
        # Store in vector database
        await self.vector_store.insert_chunks(
            chunks=chunks,
            document_id=document_id,
            user_id=user_id,
            db=db
        )
    
    async def _create_document_record(
        self,
        document_id: str,
        user_id: str,
        filename: str,
        size_bytes: int,
        blob_url: str,
        db
    ):
        """Create document record in database"""
        query = """
            INSERT INTO documents 
            (id, user_id, filename, size_bytes, blob_url, status, upload_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        await db.execute(
            query,
            document_id,
            user_id,
            filename,
            size_bytes,
            blob_url,
            "pending",
            datetime.utcnow()
        )
    
    async def _update_document_status(
        self,
        document_id: str,
        status: str,
        progress: int,
        message: str = "",
        db = None
    ):
        """Update document processing status"""
        # Implementation would update database
        pass
    
    async def _update_document_metadata(
        self,
        document_id: str,
        page_count: Optional[int],
        db
    ):
        """Update document metadata"""
        if page_count:
            query = """
                UPDATE documents
                SET page_count = $1
                WHERE id = $2
            """
            await db.execute(query, page_count, document_id)
    
    async def list_user_documents(
        self,
        user_id: str,
        db
    ) -> List[DocumentInfo]:
        """List all documents for a user"""
        query = """
            SELECT id, filename, upload_date, status, size_bytes, page_count
            FROM documents
            WHERE user_id = $1
            ORDER BY upload_date DESC
        """
        rows = await db.fetch(query, user_id)
        
        documents = []
        for row in rows:
            documents.append(DocumentInfo(
                id=row['id'],
                filename=row['filename'],
                upload_date=row['upload_date'],
                status=row['status'],
                size_bytes=row['size_bytes'],
                page_count=row['page_count'],
                document_type="user_document"
            ))
        
        return documents
    
    async def get_document_status(
        self,
        document_id: str,
        user_id: str,
        db
    ) -> DocumentStatus:
        """Get document processing status"""
        query = """
            SELECT status, processing_progress, processing_message
            FROM documents
            WHERE id = $1 AND user_id = $2
        """
        row = await db.fetchrow(query, document_id, user_id)
        
        if not row:
            raise ValueError("Document not found")
        
        return DocumentStatus(
            document_id=document_id,
            status=row['status'],
            progress=row['processing_progress'] or 0,
            message=row['processing_message'] or ""
        )
