"""
Database module initialization
Exports all models, enums, and database utilities
"""

from .models import (
    # Base
    Base,
    
    # Enums
    DocumentType,
    ProcessingStatus,
    QueryMode,
    UserRole,
    
    # Models
    User,
    Document,
    DocumentChunk,
    Conversation,
    Query,
    Citation,
    KnowledgeBase,
    AuditLog,
    SystemMetrics,
    
    # Utility functions
    create_vector_indexes
)

from .connection import (
    get_db_session,
    get_async_session,
    create_database_engine,
    init_database,
    startup_database,
    shutdown_database
)

__all__ = [
    # Base
    "Base",

    # Enums
    "DocumentType",
    "ProcessingStatus",
    "QueryMode",
    "UserRole",

    # Models
    "User",
    "Document",
    "DocumentChunk",
    "Conversation",
    "Query",
    "Citation",
    "KnowledgeBase",
    "AuditLog",
    "SystemMetrics",

    # Database functions
    "get_db_session",
    "get_async_session",
    "create_database_engine",
    "init_database",
    "startup_database",
    "shutdown_database",
    "create_vector_indexes"
]