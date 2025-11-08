"""
Pydantic models for API requests and responses
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class QueryMode(str, Enum):
    QA = "qa"
    DRAFTING = "drafting"
    SUMMARIZATION = "summarization"

class ConversationMessage(BaseModel):
    role: str
    content: str

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    mode: QueryMode = QueryMode.QA
    document_ids: Optional[List[str]] = None
    conversation_history: Optional[List[ConversationMessage]] = None

class Citation(BaseModel):
    id: str
    source_name: str
    source_type: str  # "case_law", "statute", "regulation", "user_document"
    reference: str  # Formatted citation
    text_snippet: str
    relevance_score: float

class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    mode: QueryMode
    processing_time: float
    metadata: Optional[Dict] = None

class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str  # "processing", "completed", "failed"
    message: str

class DocumentInfo(BaseModel):
    id: str
    filename: str
    upload_date: datetime
    status: str
    size_bytes: int
    page_count: Optional[int] = None
    document_type: str

class DocumentStatus(BaseModel):
    document_id: str
    status: str
    progress: int  # 0-100
    message: str
    error: Optional[str] = None
