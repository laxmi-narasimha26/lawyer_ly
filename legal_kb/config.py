"""
Configuration settings for Advanced Legal KB+RAG System
"""
import os
from typing import Optional

class Config:
    """Main configuration class"""
    
    # Database settings
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5433"))  # Using port 5433
    POSTGRES_DB = os.getenv("POSTGRES_DB", "legal_kb")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")  # Default postgres user
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "legal_kb_pass")
    
    # Redis settings
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))  # Local Redis default
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
    
    # OpenAI settings - Using working API key from test
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
    EMBEDDING_MODEL = "text-embedding-3-large"
    GENERATION_MODEL = "gpt-5"  # Using GPT-5 (released August 2025)
    FALLBACK_MODEL = "gpt-4.1"  # GPT-4.1 as fallback
    
    # RAG settings
    VECTOR_DIMENSION = 3072  # text-embedding-3-large actual dimensions
    SIMILARITY_THRESHOLD = 0.7
    MAX_CONTEXT_TOKENS = 12000  # Increased for GPT-4o
    RESPONSE_RESERVE_RATIO = 0.25  # Reserve 25% for response
    
    # Search settings
    STATUTE_RETRIEVAL_K = 20
    CASE_RETRIEVAL_K = 50
    FINAL_CONTEXT_SIZE = 8  # Max 4 statutes + 4 cases
    MMR_LAMBDA = 0.7
    
    # Re-ranking weights
    RELEVANCE_WEIGHT = 0.6
    STATUTE_EDGE_WEIGHT = 0.25
    RECENCY_WEIGHT = 0.15
    
    # Performance settings
    EMBEDDING_BATCH_SIZE = 100
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    
    # Cache settings
    QUERY_CACHE_SIZE = 50000
    RESULT_CACHE_TTL = 3600  # 1 hour
    DOCUMENT_CACHE_TTL = 86400  # 24 hours
    
    # File paths
    DATA_DIR = os.getenv("DATA_DIR", "data")
    BNS_PDF_PATH = os.path.join(DATA_DIR, "BNS.pdf.pdf")  # Actual file name
    SC_JUDGMENTS_DIR = os.path.join(DATA_DIR, "supreme_court_judgments")
    SC_2020_ONLY = True  # Process only 2020 data for testing
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration"""
        required_settings = [
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            ("POSTGRES_PASSWORD", cls.POSTGRES_PASSWORD),
        ]
        
        missing = []
        for name, value in required_settings:
            if not value:
                missing.append(name)
        
        if missing:
            print(f"Missing required configuration: {', '.join(missing)}")
            return False
        
        return True

# Global config instance
config = Config()
