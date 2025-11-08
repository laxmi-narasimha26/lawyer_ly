"""
Production-grade configuration management for Indian Legal AI Assistant
Supports multiple environments with proper secret management
"""
import os
from typing import List, Optional, Dict, Any
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field, validator
except ImportError:
    from pydantic import BaseSettings, Field, validator
from functools import lru_cache
import logging

class DatabaseSettings(BaseSettings):
    """Database configuration"""
    url: str = Field(default="postgresql://localhost/legal_ai", env="DATABASE_URL")
    pool_size: int = Field(20, env="DB_POOL_SIZE")
    max_overflow: int = Field(30, env="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(30, env="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(3600, env="DB_POOL_RECYCLE")
    echo: bool = Field(False, env="DB_ECHO")

class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI configuration"""
    api_key: str = Field(default="", env="AZURE_OPENAI_API_KEY")
    endpoint: str = Field(default="", env="AZURE_OPENAI_ENDPOINT")
    api_version: str = Field("2024-02-01", env="AZURE_OPENAI_API_VERSION")
    deployment_name: str = Field("gpt-4", env="AZURE_OPENAI_DEPLOYMENT_NAME")
    embedding_deployment: str = Field("text-embedding-ada-002", env="AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    max_tokens: int = Field(4000, env="AZURE_OPENAI_MAX_TOKENS")
    max_context_tokens: int = Field(4000, env="AZURE_OPENAI_MAX_CONTEXT_TOKENS")
    temperature_factual: float = Field(0.2, env="TEMPERATURE_FACTUAL")
    temperature_creative: float = Field(0.7, env="TEMPERATURE_CREATIVE")
    request_timeout: int = Field(60, env="OPENAI_REQUEST_TIMEOUT")
    max_retries: int = Field(3, env="OPENAI_MAX_RETRIES")

class AzureStorageSettings(BaseSettings):
    """Azure Storage configuration"""
    connection_string: str = Field(default="", env="AZURE_STORAGE_CONNECTION_STRING")
    container_name: str = Field("legal-documents", env="AZURE_STORAGE_CONTAINER_NAME")
    max_file_size_mb: int = Field(200, env="MAX_FILE_SIZE_MB")
    allowed_extensions: List[str] = Field(
        default=[".pdf", ".docx", ".doc", ".txt"],
        env="ALLOWED_FILE_EXTENSIONS"
    )

class VectorDatabaseSettings(BaseSettings):
    """Vector database configuration"""
    dimensions: int = Field(1536, env="VECTOR_DIMENSIONS")
    similarity_threshold: float = Field(0.7, env="SIMILARITY_THRESHOLD")
    max_chunks_per_query: int = Field(10, env="MAX_CHUNKS_PER_QUERY")
    chunk_size: int = Field(500, env="CHUNK_SIZE")
    chunk_overlap: int = Field(50, env="CHUNK_OVERLAP")
    index_type: str = Field("hnsw", env="VECTOR_INDEX_TYPE")

class SecuritySettings(BaseSettings):
    """Security and authentication configuration"""
    secret_key: str = Field(default="dev-secret-key-change-in-production", env="SECRET_KEY")
    algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(60, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    password_min_length: int = Field(8, env="PASSWORD_MIN_LENGTH")
    max_login_attempts: int = Field(5, env="MAX_LOGIN_ATTEMPTS")
    lockout_duration_minutes: int = Field(30, env="LOCKOUT_DURATION_MINUTES")
    
    # Encryption settings
    enable_data_encryption: bool = Field(True, env="ENABLE_DATA_ENCRYPTION")
    encryption_key_rotation_days: int = Field(90, env="ENCRYPTION_KEY_ROTATION_DAYS")
    
    # HTTPS and TLS settings
    force_https: bool = Field(True, env="FORCE_HTTPS")
    tls_min_version: str = Field("1.2", env="TLS_MIN_VERSION")
    
    # Azure Key Vault settings
    azure_key_vault_url: Optional[str] = Field(None, env="AZURE_KEY_VAULT_URL")
    azure_tenant_id: Optional[str] = Field(None, env="AZURE_TENANT_ID")
    azure_client_id: Optional[str] = Field(None, env="AZURE_CLIENT_ID")
    azure_client_secret: Optional[str] = Field(None, env="AZURE_CLIENT_SECRET")
    
    # Input validation settings
    max_query_length: int = Field(10000, env="MAX_QUERY_LENGTH")
    max_file_size_mb: int = Field(200, env="MAX_FILE_SIZE_MB")
    allowed_file_types: List[str] = Field(
        default=[".pdf", ".docx", ".doc", ".txt"],
        env="ALLOWED_FILE_TYPES"
    )
    
    # Security headers
    enable_security_headers: bool = Field(True, env="ENABLE_SECURITY_HEADERS")
    content_security_policy: str = Field(
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        env="CONTENT_SECURITY_POLICY"
    )

class CacheSettings(BaseSettings):
    """Redis cache configuration"""
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    default_ttl: int = Field(3600, env="CACHE_DEFAULT_TTL")
    query_cache_ttl: int = Field(1800, env="QUERY_CACHE_TTL")
    embedding_cache_ttl: int = Field(86400, env="EMBEDDING_CACHE_TTL")
    max_connections: int = Field(20, env="REDIS_MAX_CONNECTIONS")

class RateLimitSettings(BaseSettings):
    """Rate limiting configuration"""
    queries_per_hour: int = Field(100, env="RATE_LIMIT_QUERIES_PER_HOUR")
    uploads_per_hour: int = Field(20, env="RATE_LIMIT_UPLOADS_PER_HOUR")
    max_concurrent_requests: int = Field(10, env="MAX_CONCURRENT_REQUESTS")
    burst_limit: int = Field(20, env="RATE_LIMIT_BURST")

class MonitoringSettings(BaseSettings):
    """Monitoring and logging configuration"""
    application_insights_connection_string: Optional[str] = Field(
        None, env="AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING"
    )
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    enable_metrics: bool = Field(True, env="ENABLE_METRICS")
    metrics_port: int = Field(8001, env="METRICS_PORT")

class ConversationSettings(BaseSettings):
    """Conversation context management configuration"""
    max_history_queries: int = Field(10, env="MAX_HISTORY_QUERIES")
    max_context_tokens: int = Field(4000, env="MAX_CONTEXT_TOKENS")
    enable_summarization: bool = Field(True, env="ENABLE_CONTEXT_SUMMARIZATION")
    summary_max_tokens: int = Field(150, env="CONTEXT_SUMMARY_MAX_TOKENS")
    context_relevance_threshold: float = Field(0.6, env="CONTEXT_RELEVANCE_THRESHOLD")
    enable_topic_tracking: bool = Field(True, env="ENABLE_TOPIC_TRACKING")
    max_response_length_for_context: int = Field(400, env="MAX_RESPONSE_LENGTH_FOR_CONTEXT")

class LegalKnowledgeSettings(BaseSettings):
    """Legal knowledge base configuration"""
    initial_corpus_size: int = Field(5000, env="INITIAL_CORPUS_SIZE")
    auto_update_enabled: bool = Field(True, env="AUTO_UPDATE_ENABLED")
    update_check_interval_hours: int = Field(24, env="UPDATE_CHECK_INTERVAL_HOURS")
    supported_languages: List[str] = Field(["en", "hi"], env="SUPPORTED_LANGUAGES")
    citation_formats: Dict[str, str] = Field(
        default={
            "case_law": "{case_name}, {year} {court} {citation}",
            "statute": "{act_name}, {year}, Section {section}",
            "regulation": "{regulation_name}, {date}"
        }
    )

class GoogleSearchSettings(BaseSettings):
    """Google Custom Search Engine configuration"""
    enabled: bool = Field(False, env="GOOGLE_SEARCH_ENABLED")
    api_key: Optional[str] = Field(None, env="GOOGLE_SEARCH_API_KEY")
    search_engine_id: Optional[str] = Field(None, env="GOOGLE_SEARCH_ENGINE_ID")
    max_results: int = Field(5, env="GOOGLE_SEARCH_MAX_RESULTS")
    restrict_to_legal_sites: bool = Field(True, env="GOOGLE_SEARCH_RESTRICT_LEGAL")
    auto_detect_temporal_queries: bool = Field(True, env="GOOGLE_SEARCH_AUTO_DETECT")
    cache_results: bool = Field(True, env="GOOGLE_SEARCH_CACHE_RESULTS")
    cache_ttl: int = Field(3600, env="GOOGLE_SEARCH_CACHE_TTL")

    # Fallback settings
    use_web_fallback: bool = Field(True, env="GOOGLE_SEARCH_USE_FALLBACK")
    vector_confidence_threshold: float = Field(0.6, env="GOOGLE_SEARCH_VECTOR_THRESHOLD")
    combine_with_vector: bool = Field(True, env="GOOGLE_SEARCH_COMBINE_VECTOR")

class Settings(BaseSettings):
    """Main application settings"""
    
    # Application metadata
    app_name: str = Field("Indian Legal AI Assistant", env="APP_NAME")
    app_version: str = Field("1.0.0", env="APP_VERSION")
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    
    # Server configuration
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    workers: int = Field(1, env="WORKERS")
    
    # CORS settings
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="ALLOWED_ORIGINS"
    )
    allowed_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        env="ALLOWED_METHODS"
    )
    
    # Component settings
    database: DatabaseSettings = DatabaseSettings()
    azure_openai: AzureOpenAISettings = AzureOpenAISettings()
    azure_storage: AzureStorageSettings = AzureStorageSettings()
    vector_db: VectorDatabaseSettings = VectorDatabaseSettings()
    security: SecuritySettings = SecuritySettings()
    cache: CacheSettings = CacheSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    conversation: ConversationSettings = ConversationSettings()
    legal_knowledge: LegalKnowledgeSettings = LegalKnowledgeSettings()
    google_search: GoogleSearchSettings = GoogleSearchSettings()
    
    # Feature flags
    enable_document_upload: bool = Field(True, env="ENABLE_DOCUMENT_UPLOAD")
    enable_drafting_mode: bool = Field(True, env="ENABLE_DRAFTING_MODE")
    enable_summarization: bool = Field(True, env="ENABLE_SUMMARIZATION")
    enable_conversation_history: bool = Field(True, env="ENABLE_CONVERSATION_HISTORY")
    enable_citation_verification: bool = Field(True, env="ENABLE_CITATION_VERIFICATION")
    enable_hallucination_detection: bool = Field(True, env="ENABLE_HALLUCINATION_DETECTION")
    enable_web_search: bool = Field(False, env="ENABLE_WEB_SEARCH")
    
    def validate_environment(cls, v):
        allowed_envs = ["development", "staging", "production"]
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of {allowed_envs}")
        return v
    
    def validate_log_level(cls, v):
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of {allowed_levels}")
        return v.upper()
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # Support nested environment variables
        env_nested_delimiter = "__"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Global settings instance
settings = get_settings()

# Configure logging based on settings
def configure_logging():
    """Configure application logging"""
    logging.basicConfig(
        level=getattr(logging, settings.monitoring.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Suppress noisy loggers in production
    if settings.is_production:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

# Initialize logging
configure_logging()