"""
Production-grade database models for Indian Legal AI Assistant
Comprehensive schema supporting all features from the PDF specification
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, Float, JSON, Text, 
    Boolean, ForeignKey, Index, UniqueConstraint, CheckConstraint,
    LargeBinary, Enum as SQLEnum, ARRAY
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
try:
    from pgvector.sqlalchemy import Vector as VECTOR
except ImportError:
    # Fallback for when pgvector is not available
    from sqlalchemy import Text as VECTOR
from datetime import datetime
import uuid
import enum
from typing import Optional, Dict, Any, List

Base = declarative_base()

class DocumentType(str, enum.Enum):
    """Document type enumeration"""
    STATUTE = "statute"
    CASE_LAW = "case_law"
    REGULATION = "regulation"
    USER_DOCUMENT = "user_document"
    LEGAL_NOTICE = "legal_notice"
    CONTRACT = "contract"
    PETITION = "petition"
    JUDGMENT = "judgment"

class ProcessingStatus(str, enum.Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class QueryMode(str, enum.Enum):
    """Query processing mode"""
    QA = "qa"
    DRAFTING = "drafting"
    SUMMARIZATION = "summarization"
    ANALYSIS = "analysis"

class UserRole(str, enum.Enum):
    """User role enumeration"""
    LAWYER = "lawyer"
    PARALEGAL = "paralegal"
    ADMIN = "admin"
    VIEWER = "viewer"

class User(Base):
    """User model with comprehensive authentication and profile management"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile information
    full_name = Column(String(255), nullable=False)
    bar_council_id = Column(String(50), nullable=True, unique=True)  # Indian Bar Council ID
    law_firm = Column(String(255), nullable=True)
    specialization = Column(ARRAY(String), nullable=True)  # Areas of legal practice
    phone_number = Column(String(20), nullable=True)
    
    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.LAWYER, nullable=False)
    
    # Security
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow)
    
    # Subscription and limits
    subscription_tier = Column(String(50), default="basic", nullable=False)
    monthly_query_limit = Column(Integer, default=1000, nullable=False)
    monthly_upload_limit = Column(Integer, default=100, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    queries = relationship("Query", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_user_email_active", "email", "is_active"),
        Index("idx_user_bar_council", "bar_council_id"),
    )

class Document(Base):
    """Document model supporting all legal document types"""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # File information
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash
    mime_type = Column(String(100), nullable=False)
    
    # Document metadata
    document_type = Column(SQLEnum(DocumentType), nullable=False, index=True)
    title = Column(String(1000), nullable=True)
    author = Column(String(255), nullable=True)
    court = Column(String(255), nullable=True)  # For case law
    jurisdiction = Column(String(100), nullable=True)  # State/Central
    year = Column(Integer, nullable=True, index=True)
    citation = Column(String(500), nullable=True, index=True)
    
    # Processing information
    status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False)
    processing_progress = Column(Integer, default=0, nullable=False)  # 0-100
    processing_message = Column(Text, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    
    # Content information
    page_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    language = Column(String(10), default="en", nullable=False)
    
    # Storage information
    blob_url = Column(String(1000), nullable=False)
    blob_container = Column(String(100), nullable=False)
    blob_path = Column(String(500), nullable=False)
    
    # Legal metadata (JSON field for flexible schema)
    legal_metadata = Column(JSON, nullable=True)  # Court details, case numbers, etc.
    
    # Access control
    is_public = Column(Boolean, default=False, nullable=False)
    access_level = Column(String(20), default="private", nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_document_user_type", "user_id", "document_type"),
        Index("idx_document_status", "status"),
        Index("idx_document_citation", "citation"),
        Index("idx_document_year_type", "year", "document_type"),
        CheckConstraint("processing_progress >= 0 AND processing_progress <= 100"),
        CheckConstraint("file_size_bytes > 0"),
    )

class DocumentChunk(Base):
    """Document chunks for vector search with comprehensive metadata"""
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Chunk content
    text = Column(Text, nullable=False)
    text_hash = Column(String(64), nullable=False, index=True)  # For deduplication
    
    # Vector embedding (1536 dimensions for OpenAI ada-002)
    embedding = Column(VECTOR(1536), nullable=False)
    
    # Chunk metadata
    chunk_index = Column(Integer, nullable=False)  # Position in document
    start_page = Column(Integer, nullable=True)
    end_page = Column(Integer, nullable=True)
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    
    # Legal structure metadata
    section_title = Column(String(500), nullable=True)  # For statutes
    section_number = Column(String(50), nullable=True)  # For statutes
    paragraph_number = Column(Integer, nullable=True)  # For case law
    
    # Content classification
    content_type = Column(String(50), nullable=True)  # "heading", "body", "citation", etc.
    importance_score = Column(Float, nullable=True)  # 0.0-1.0
    
    # Source information (inherited from document)
    source_name = Column(String(500), nullable=False)
    source_type = Column(SQLEnum(DocumentType), nullable=False)
    
    # Additional metadata (JSON for flexibility)
    chunk_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    user = relationship("User")
    
    __table_args__ = (
        Index("idx_chunk_document_index", "document_id", "chunk_index"),
        Index("idx_chunk_user_type", "user_id", "source_type"),
        Index("idx_chunk_text_hash", "text_hash"),
        Index("idx_chunk_section", "section_number"),
        # Vector similarity search index (created separately)
        Index("idx_chunk_embedding", "embedding", postgresql_using="hnsw"),
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
    )

class Conversation(Base):
    """Conversation sessions for maintaining context"""
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Conversation metadata
    title = Column(String(500), nullable=True)  # Auto-generated or user-provided
    mode = Column(SQLEnum(QueryMode), default=QueryMode.QA, nullable=False)
    
    # Session information
    is_active = Column(Boolean, default=True, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Context settings
    context_document_ids = Column(ARRAY(UUID), nullable=True)  # Pinned documents
    context_settings = Column(JSON, nullable=True)  # User preferences
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    queries = relationship("Query", back_populates="conversation", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_conversation_user_active", "user_id", "is_active"),
        Index("idx_conversation_last_activity", "last_activity"),
    )

class Query(Base):
    """Query model with comprehensive tracking and analytics"""
    __tablename__ = "queries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True)
    
    # Query content
    query_text = Column(Text, nullable=False)
    query_hash = Column(String(64), nullable=False, index=True)  # For caching
    mode = Column(SQLEnum(QueryMode), nullable=False)
    
    # Response content
    response_text = Column(Text, nullable=True)
    response_metadata = Column(JSON, nullable=True)  # Citations, sources, etc.
    
    # Processing metrics
    processing_time_ms = Column(Integer, nullable=True)
    retrieval_time_ms = Column(Integer, nullable=True)
    llm_time_ms = Column(Integer, nullable=True)
    
    # Token usage
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    # Quality metrics
    confidence_score = Column(Float, nullable=True)  # 0.0-1.0
    citation_count = Column(Integer, default=0, nullable=False)
    user_rating = Column(Integer, nullable=True)  # 1-5 stars
    user_feedback = Column(Text, nullable=True)
    
    # Retrieved context
    retrieved_chunk_ids = Column(ARRAY(UUID), nullable=True)
    context_document_ids = Column(ARRAY(UUID), nullable=True)
    
    # Status and error handling
    status = Column(String(20), default="completed", nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="queries")
    conversation = relationship("Conversation", back_populates="queries")
    
    __table_args__ = (
        Index("idx_query_user_created", "user_id", "created_at"),
        Index("idx_query_hash", "query_hash"),
        Index("idx_query_mode_status", "mode", "status"),
        Index("idx_query_conversation", "conversation_id", "created_at"),
        CheckConstraint("user_rating IS NULL OR (user_rating >= 1 AND user_rating <= 5)"),
    )

class Citation(Base):
    """Citation tracking for legal references"""
    __tablename__ = "citations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey("queries.id"), nullable=False, index=True)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=False, index=True)
    
    # Citation information
    citation_text = Column(String(1000), nullable=False)
    citation_type = Column(SQLEnum(DocumentType), nullable=False)
    relevance_score = Column(Float, nullable=False)  # 0.0-1.0
    
    # Position in response
    position_in_response = Column(Integer, nullable=False)
    
    # Verification status
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_method = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_citation_query", "query_id"),
        Index("idx_citation_chunk", "chunk_id"),
        Index("idx_citation_type_score", "citation_type", "relevance_score"),
    )

class KnowledgeBase(Base):
    """Knowledge base management and versioning"""
    __tablename__ = "knowledge_base"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Version information
    version = Column(String(20), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Statistics
    total_documents = Column(Integer, default=0, nullable=False)
    total_chunks = Column(Integer, default=0, nullable=False)
    
    # Content breakdown by type
    statute_count = Column(Integer, default=0, nullable=False)
    case_law_count = Column(Integer, default=0, nullable=False)
    regulation_count = Column(Integer, default=0, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=False, nullable=False)
    build_status = Column(String(20), default="building", nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    activated_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("idx_kb_version", "version"),
        Index("idx_kb_active", "is_active"),
    )

class AuditLog(Base):
    """Comprehensive audit logging for compliance"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # Event information
    event_type = Column(String(50), nullable=False, index=True)
    event_category = Column(String(30), nullable=False, index=True)  # "auth", "query", "upload", etc.
    event_description = Column(Text, nullable=False)
    
    # Request information
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True, index=True)
    
    # Resource information
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    
    # Additional context
    audit_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_audit_user_event", "user_id", "event_type"),
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_category_created", "event_category", "created_at"),
    )

class SystemMetrics(Base):
    """System performance and usage metrics"""
    __tablename__ = "system_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Metric information
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)
    
    # Dimensions
    dimensions = Column(JSON, nullable=True)  # Additional metric dimensions
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_metrics_name_timestamp", "metric_name", "timestamp"),
    )

# Create all indexes for vector similarity search
def create_vector_indexes(engine):
    """Create vector similarity search indexes"""
    with engine.connect() as conn:
        # Create HNSW index for fast similarity search
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunk_embedding_hnsw 
            ON document_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
        
        # Create IVF index as alternative
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunk_embedding_ivf
            ON document_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        
        conn.commit()