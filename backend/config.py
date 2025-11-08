"""
Configuration settings for the application
"""
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Indian Legal AI Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Azure OpenAI
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4"
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-ada-002"
    
    # Database
    DATABASE_URL: str
    VECTOR_DIMENSIONS: int = 1536
    
    # Azure Storage
    AZURE_STORAGE_CONNECTION_STRING: str
    AZURE_STORAGE_CONTAINER_NAME: str = "legal-documents"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Rate Limiting
    RATE_LIMIT_PER_HOUR: int = 100
    MAX_UPLOAD_SIZE_MB: int = 50
    MAX_DOCUMENT_PAGES: int = 200
    
    # RAG Configuration
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K_RETRIEVAL: int = 5
    TEMPERATURE_FACTUAL: float = 0.3
    TEMPERATURE_CREATIVE: float = 0.7
    
    # Caching
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 900
    
    # Monitoring
    AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
