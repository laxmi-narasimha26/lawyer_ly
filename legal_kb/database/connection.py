"""
Database connection and configuration for Advanced Legal KB+RAG System
"""
import os
import asyncio
import asyncpg
import redis.asyncio as redis
from typing import Optional, Dict, Any, List
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration settings"""
    
    def __init__(self):
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5433"))  # Using port 5433
        self.postgres_db = os.getenv("POSTGRES_DB", "legal_kb")
        self.postgres_user = os.getenv("POSTGRES_USER", "postgres")  # Default postgres user
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "legal_kb_pass")
        
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.redis_password = os.getenv("REDIS_PASSWORD")
        
        # Connection pool settings
        self.postgres_min_connections = int(os.getenv("POSTGRES_MIN_CONNECTIONS", "5"))
        self.postgres_max_connections = int(os.getenv("POSTGRES_MAX_CONNECTIONS", "20"))
        
    @property
    def postgres_dsn(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.postgres_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        
    async def initialize(self):
        """Initialize database connections"""
        try:
            # Initialize PostgreSQL connection pool
            self.postgres_pool = await asyncpg.create_pool(
                self.config.postgres_dsn,
                min_size=self.config.postgres_min_connections,
                max_size=self.config.postgres_max_connections,
                command_timeout=60
            )
            
            # Test PostgreSQL connection
            async with self.postgres_pool.acquire() as conn:
                await conn.execute("SELECT 1")
                logger.info("PostgreSQL connection established")
            
            # Initialize Redis connection
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=True
            )
            
            # Test Redis connection
            await self.redis_client.ping()
            logger.info("Redis connection established")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connections: {e}")
            raise
    
    async def close(self):
        """Close database connections"""
        if self.postgres_pool:
            await self.postgres_pool.close()
            logger.info("PostgreSQL connection pool closed")
        
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
    
    @asynccontextmanager
    async def get_postgres_connection(self):
        """Get PostgreSQL connection from pool"""
        if not self.postgres_pool:
            raise RuntimeError("PostgreSQL pool not initialized")
        
        async with self.postgres_pool.acquire() as conn:
            yield conn
    
    async def execute_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dicts"""
        async with self.get_postgres_connection() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def execute_command(self, command: str, *args) -> str:
        """Execute a command and return status"""
        async with self.get_postgres_connection() as conn:
            return await conn.execute(command, *args)

# Global database manager instance
db_manager: Optional[DatabaseManager] = None

async def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance"""
    global db_manager
    if db_manager is None:
        config = DatabaseConfig()
        db_manager = DatabaseManager(config)
        await db_manager.initialize()
    return db_manager

async def initialize_database():
    """Initialize the database with schema"""
    config = DatabaseConfig()
    manager = DatabaseManager(config)
    await manager.initialize()
    
    # Read and execute schema
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    async with manager.get_postgres_connection() as conn:
        await conn.execute(schema_sql)
        logger.info("Database schema initialized successfully")
    
    await manager.close()
    return True
