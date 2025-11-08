"""
Database initialization and connection management
"""
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Integer, DateTime, Float, JSON, Text, LargeBinary
from datetime import datetime

from config import settings

logger = structlog.get_logger()

Base = declarative_base()

# Database models
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    blob_url = Column(String, nullable=False)
    status = Column(String, default="pending")
    processing_progress = Column(Integer, default=0)
    processing_message = Column(String, default="")
    page_count = Column(Integer, nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(String, primary_key=True)
    document_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    text = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=False)  # PGVector type
    source_name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    metadata = Column(JSON, default={})
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Initialize database tables"""
    try:
        async with engine.begin() as conn:
            # Create PGVector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # Create tables
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise

async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
