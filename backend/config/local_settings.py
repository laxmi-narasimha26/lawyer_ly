import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database Configuration
DATABASE_CONFIG = {
    "url": os.getenv("DATABASE_URL", "postgresql://postgres:legal_kb_pass@localhost:5433/legal_kb"),
    "echo": os.getenv("DEBUG", "false").lower() == "true",
    "pool_size": 5,
    "max_overflow": 10,
    "pool_timeout": 30,
    "pool_recycle": 3600,
}

# Redis Configuration
REDIS_CONFIG = {
    "url": os.getenv("REDIS_URL", "redis://localhost:6379"),
    "decode_responses": True,
    "socket_timeout": 5,
    "socket_connect_timeout": 5,
    "retry_on_timeout": True,
}

# OpenAI Configuration
OPENAI_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY", ""),  # set via environment; do not hardcode secrets
    "model": os.getenv("OPENAI_MODEL", "gpt-4"),
    "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
    "max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", "2000")),
    "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
    "timeout": 30,
}

# Local Storage Configuration
STORAGE_CONFIG = {
    "upload_folder": Path(os.getenv("UPLOAD_FOLDER", "./data/documents")),
    "knowledge_base_folder": Path(os.getenv("KNOWLEDGE_BASE_FOLDER", "./data/knowledge_base")),
    "max_file_size": os.getenv("MAX_FILE_SIZE", "50MB"),
    "allowed_extensions": [".pdf", ".docx", ".txt"],
}

# Vector Search Configuration
VECTOR_CONFIG = {
    "embedding_dimension": 1536,  # OpenAI ada-002
    "similarity_threshold": 0.7,
    "max_results": int(os.getenv("VECTOR_SEARCH_LIMIT", "5")),
    "index_type": "ivfflat",
    "index_lists": 100,
}

# RAG Configuration
RAG_CONFIG = {
    "chunk_size": 500,
    "chunk_overlap": 50,
    "max_context_length": 4000,
    "citation_format": "indian_legal",
    "hallucination_detection": True,
}

# Security Configuration (Simplified for local)
SECURITY_CONFIG = {
    "jwt_secret": os.getenv("JWT_SECRET_KEY", "local-dev-secret"),
    "jwt_algorithm": "HS256",
    "jwt_expiration": 3600,  # 1 hour
    "encryption_key": os.getenv("ENCRYPTION_KEY", "local-dev-encryption-key"),
    "auth_enabled": os.getenv("AUTH_ENABLED", "false").lower() == "true",
}

# Performance Configuration
PERFORMANCE_CONFIG = {
    "max_concurrent_requests": int(os.getenv("MAX_CONCURRENT_REQUESTS", "10")),
    "cache_ttl": int(os.getenv("CACHE_TTL", "3600")),
    "request_timeout": 30,
    "worker_processes": 1,  # Single process for local
}

# Logging Configuration
LOGGING_CONFIG = {
    "level": os.getenv("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "logs/app.log",
    "max_size": "10MB",
    "backup_count": 5,
}

# Demo Configuration
DEMO_CONFIG = {
    "enabled": os.getenv("DEMO_MODE", "true").lower() == "true",
    "sample_queries": [
        "What are the essential elements of a valid contract under Indian law?",
        "Explain the doctrine of promissory estoppel",
        "What is the limitation period for filing a civil suit?",
        "What are the grounds for divorce under Hindu Marriage Act?",
    ],
    "sample_documents": [
        "Constitution of India - Fundamental Rights",
        "Indian Contract Act, 1872",
        "Indian Penal Code, 1860",
    ],
}
