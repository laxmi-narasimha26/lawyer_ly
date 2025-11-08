"""
Pydantic models for API requests and responses
Production-grade models with comprehensive validation
"""
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator
import re

from database.models import QueryMode, DocumentType, ProcessingStatus

class QueryRequest(BaseModel):
    """Request model for legal query processing"""
    query: str = Field(
        ...,
        min_length=5,
        max_length=5000,
        description="Legal question or request"
    )
    mode: QueryMode = Field(
        default=QueryMode.QA,
        description="Query processing mode"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Conversation ID for context continuity"
    )
    document_ids: Optional[List[str]] = Field(
        None,
        description="Specific document IDs to search within"
    )
    context_settings: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional context settings"
    )
    
    @validator('query')
    def validate_query(cls, v):
        """Validate query content"""
        if not v.strip():
            raise ValueError("Query cannot be empty or only whitespace")
        
        # Check for potentially harmful content
        harmful_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        for pattern in harmful_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Query contains potentially harmful content")
        
        return v.strip()
    
    @validator('document_ids')
    def validate_document_ids(cls, v):
        """Validate document IDs format"""
        if v is not None:
            if len(v) > 10:
                raise ValueError("Maximum 10 document IDs allowed per query")
            
            for doc_id in v:
                if not re.match(r'^[a-f0-9-]{36}$', doc_id):
                    raise ValueError(f"Invalid document ID format: {doc_id}")
        
        return v

class Citation(BaseModel):
    """Citation model with comprehensive metadata"""
    id: str = Field(..., description="Unique citation identifier")
    source_name: str = Field(..., description="Name of the source document")
    source_type: str = Field(..., description="Type of legal source")
    reference: str = Field(..., description="Formatted legal citation")
    text_snippet: str = Field(..., description="Relevant text excerpt")
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0-1.0)"
    )
    page_reference: Optional[str] = Field(
        None,
        description="Page or section reference"
    )
    is_verified: bool = Field(
        default=False,
        description="Whether citation has been verified"
    )
    verification_notes: Optional[str] = Field(
        None,
        description="Notes about citation verification"
    )

class QueryResponse(BaseModel):
    """Response model for legal query processing"""
    answer: str = Field(..., description="AI-generated legal response")
    citations: List[Citation] = Field(
        default_factory=list,
        description="Supporting citations and references"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the response"
    )
    processing_time_ms: int = Field(
        ...,
        ge=0,
        description="Processing time in milliseconds"
    )
    mode: QueryMode = Field(..., description="Query processing mode used")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional response metadata"
    )
    warnings: Optional[List[str]] = Field(
        None,
        description="Any warnings about the response"
    )
    disclaimer: Optional[str] = Field(
        None,
        description="Legal disclaimer if applicable"
    )

class UploadResponse(BaseModel):
    """Response model for document upload"""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")
    estimated_processing_time: Optional[int] = Field(
        None,
        description="Estimated processing time in seconds"
    )

class DocumentInfo(BaseModel):
    """Document information model"""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    upload_date: datetime = Field(..., description="Upload timestamp")
    status: ProcessingStatus = Field(..., description="Processing status")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    page_count: Optional[int] = Field(None, description="Number of pages")
    document_type: DocumentType = Field(..., description="Classified document type")
    processing_progress: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Processing progress percentage"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Extracted document metadata"
    )

class DocumentListResponse(BaseModel):
    """Response model for document listing"""
    documents: List[DocumentInfo] = Field(
        default_factory=list,
        description="List of user documents"
    )
    total_count: int = Field(..., ge=0, description="Total number of documents")
    pagination: Optional[Dict[str, Any]] = Field(
        None,
        description="Pagination information"
    )

class DocumentStatusResponse(BaseModel):
    """Response model for document processing status"""
    document_id: str = Field(..., description="Document identifier")
    status: ProcessingStatus = Field(..., description="Current processing status")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    message: str = Field(..., description="Status message")
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    error_details: Optional[str] = Field(None, description="Error details if failed")
    estimated_completion: Optional[datetime] = Field(
        None,
        description="Estimated completion time"
    )

class HealthResponse(BaseModel):
    """Health check response model"""
    name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    status: str = Field(..., description="Overall health status")
    timestamp: float = Field(..., description="Response timestamp")
    components: Optional[Dict[str, str]] = Field(
        None,
        description="Component health status"
    )
    error: Optional[str] = Field(None, description="Error message if unhealthy")

class MetricsResponse(BaseModel):
    """Metrics response model"""
    cache_stats: Dict[str, Any] = Field(..., description="Cache statistics")
    storage_stats: Dict[str, Any] = Field(..., description="Storage statistics")
    processing_stats: Dict[str, Any] = Field(..., description="Processing statistics")
    timestamp: float = Field(..., description="Metrics timestamp")

class ConversationMessage(BaseModel):
    """Conversation message model"""
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Message metadata")
    
    @validator('role')
    def validate_role(cls, v):
        """Validate message role"""
        allowed_roles = ['user', 'assistant', 'system']
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {allowed_roles}")
        return v

class UserProfile(BaseModel):
    """User profile model"""
    id: str = Field(..., description="User identifier")
    email: str = Field(..., description="User email")
    full_name: Optional[str] = Field(None, description="Full name")
    bar_council_id: Optional[str] = Field(None, description="Bar Council ID")
    law_firm: Optional[str] = Field(None, description="Law firm name")
    specialization: Optional[List[str]] = Field(None, description="Legal specializations")
    subscription_tier: str = Field(default="basic", description="Subscription tier")
    created_at: datetime = Field(..., description="Account creation date")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

class TokenResponse(BaseModel):
    """Authentication token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiry in seconds")
    refresh_token: Optional[str] = Field(None, description="Refresh token")

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    request_id: Optional[str] = Field(None, description="Request identifier")
    timestamp: float = Field(..., description="Error timestamp")

class ValidationErrorDetail(BaseModel):
    """Validation error detail"""
    field: str = Field(..., description="Field name")
    message: str = Field(..., description="Validation error message")
    value: Optional[Any] = Field(None, description="Invalid value")

class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    error: str = Field(default="validation_error", description="Error type")
    message: str = Field(..., description="General error message")
    details: List[ValidationErrorDetail] = Field(..., description="Validation details")
    request_id: Optional[str] = Field(None, description="Request identifier")

class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    document_types: Optional[List[DocumentType]] = Field(
        None,
        description="Filter by document types"
    )
    date_range: Optional[Dict[str, str]] = Field(
        None,
        description="Date range filter"
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Result offset")

class SearchResult(BaseModel):
    """Search result model"""
    document_id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    snippet: str = Field(..., description="Relevant text snippet")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    document_type: DocumentType = Field(..., description="Document type")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Document metadata")

class SearchResponse(BaseModel):
    """Search response model"""
    results: List[SearchResult] = Field(..., description="Search results")
    total_count: int = Field(..., ge=0, description="Total matching documents")
    query_time_ms: int = Field(..., ge=0, description="Query processing time")
    suggestions: Optional[List[str]] = Field(None, description="Query suggestions")

class FeedbackRequest(BaseModel):
    """User feedback request model"""
    query_id: Optional[str] = Field(None, description="Related query ID")
    rating: int = Field(..., ge=1, le=5, description="Rating (1-5 stars)")
    feedback_text: Optional[str] = Field(
        None,
        max_length=1000,
        description="Detailed feedback"
    )
    category: Optional[str] = Field(None, description="Feedback category")
    
    @validator('feedback_text')
    def validate_feedback_text(cls, v):
        """Validate feedback text"""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v

class SystemStatus(BaseModel):
    """System status model"""
    overall_status: str = Field(..., description="Overall system status")
    components: Dict[str, Dict[str, Any]] = Field(..., description="Component statuses")
    last_updated: datetime = Field(..., description="Last status update")
    maintenance_mode: bool = Field(default=False, description="Maintenance mode flag")

class RateLimitInfo(BaseModel):
    """Rate limit information"""
    limit: int = Field(..., description="Rate limit")
    remaining: int = Field(..., description="Remaining requests")
    reset_time: datetime = Field(..., description="Rate limit reset time")
    retry_after: Optional[int] = Field(None, description="Retry after seconds")

# Request/Response wrapper models
class APIRequest(BaseModel):
    """Base API request wrapper"""
    request_id: Optional[str] = Field(None, description="Request identifier")
    timestamp: Optional[datetime] = Field(None, description="Request timestamp")
    client_version: Optional[str] = Field(None, description="Client version")

class APIResponse(BaseModel):
    """Base API response wrapper"""
    success: bool = Field(default=True, description="Request success status")
    request_id: Optional[str] = Field(None, description="Request identifier")
    timestamp: float = Field(..., description="Response timestamp")
    rate_limit: Optional[RateLimitInfo] = Field(None, description="Rate limit info")

# Specialized request models
class BulkQueryRequest(BaseModel):
    """Bulk query processing request"""
    queries: List[QueryRequest] = Field(
        ...,
        min_items=1,
        max_items=10,
        description="List of queries to process"
    )
    batch_id: Optional[str] = Field(None, description="Batch identifier")

class BulkQueryResponse(BaseModel):
    """Bulk query processing response"""
    results: List[QueryResponse] = Field(..., description="Query results")
    batch_id: Optional[str] = Field(None, description="Batch identifier")
    total_processing_time_ms: int = Field(..., description="Total processing time")
    success_count: int = Field(..., description="Successful queries")
    error_count: int = Field(..., description="Failed queries")

# Configuration models
class UserPreferences(BaseModel):
    """User preferences model"""
    language: str = Field(default="en", description="Preferred language")
    citation_format: str = Field(default="indian", description="Citation format preference")
    response_length: str = Field(default="medium", description="Preferred response length")
    enable_notifications: bool = Field(default=True, description="Enable notifications")
    theme: str = Field(default="light", description="UI theme preference")
    
    @validator('language')
    def validate_language(cls, v):
        """Validate language code"""
        allowed_languages = ['en', 'hi']
        if v not in allowed_languages:
            raise ValueError(f"Language must be one of: {allowed_languages}")
        return v
    
    @validator('response_length')
    def validate_response_length(cls, v):
        """Validate response length preference"""
        allowed_lengths = ['short', 'medium', 'long']
        if v not in allowed_lengths:
            raise ValueError(f"Response length must be one of: {allowed_lengths}")
        return v