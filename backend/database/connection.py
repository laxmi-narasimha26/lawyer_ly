"""
Production-grade database connection management
Handles connection pooling, transactions, and error recovery
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, AsyncEngine, async_sessionmaker
)
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
from sqlalchemy import event, text
import structlog

from config import settings
from .models import Base, create_vector_indexes

logger = structlog.get_logger(__name__)

class DatabaseManager:
    """Production-grade database connection manager"""
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database connection and create tables"""
        if self._initialized:
            return
        
        try:
            # Create async engine with production settings
            engine_kwargs = {
                "echo": settings.database.echo,
                "poolclass": QueuePool if not settings.is_development else NullPool,
                "connect_args": {
                    "server_settings": {
                        "application_name": settings.app_name,
                        "jit": "off",  # Disable JIT for better performance with short queries
                    },
                    "command_timeout": 60,
                }
            }

            # Only add pool settings if not using NullPool
            if not settings.is_development:
                engine_kwargs.update({
                    "pool_size": settings.database.pool_size,
                    "max_overflow": settings.database.max_overflow,
                    "pool_timeout": settings.database.pool_timeout,
                    "pool_recycle": settings.database.pool_recycle,
                })

            self.engine = create_async_engine(
                settings.database.url,
                **engine_kwargs
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            # Set up event listeners
            self._setup_event_listeners()
            
            # Create database schema
            await self._create_schema()
            
            # Create vector indexes
            await self._create_vector_indexes()
            
            self._initialized = True
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e), exc_info=True)
            raise
    
    def _setup_event_listeners(self) -> None:
        """Set up SQLAlchemy event listeners for monitoring and optimization"""
        
        @event.listens_for(self.engine.sync_engine, "connect")
        def set_postgresql_settings(dbapi_connection, connection_record):
            """Optimize PostgreSQL connection settings for vector workloads"""
            with dbapi_connection.cursor() as cursor:
                # Enable vector extension
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Memory settings optimized for vector operations
                cursor.execute("SET work_mem = '512MB'")  # Increased for vector operations
                cursor.execute("SET maintenance_work_mem = '2GB'")  # Increased for index building
                cursor.execute("SET effective_cache_size = '8GB'")  # Increased cache assumption
                cursor.execute("SET shared_buffers = '2GB'")  # If we can control this
                
                # Cost settings optimized for SSD storage
                cursor.execute("SET random_page_cost = 1.1")
                cursor.execute("SET seq_page_cost = 1.0")
                cursor.execute("SET cpu_tuple_cost = 0.01")
                cursor.execute("SET cpu_index_tuple_cost = 0.005")
                cursor.execute("SET cpu_operator_cost = 0.0025")
                
                # Vector-specific optimizations
                cursor.execute("SET max_parallel_workers_per_gather = 4")
                cursor.execute("SET max_parallel_workers = 8")
                cursor.execute("SET parallel_tuple_cost = 0.1")
                cursor.execute("SET parallel_setup_cost = 1000.0")
                
                # Query planner settings
                cursor.execute("SET enable_seqscan = on")
                cursor.execute("SET enable_indexscan = on")
                cursor.execute("SET enable_bitmapscan = on")
                cursor.execute("SET enable_hashjoin = on")
                cursor.execute("SET enable_mergejoin = on")
                cursor.execute("SET enable_nestloop = on")
                
                # Logging for performance analysis (development only)
                if settings.is_development:
                    cursor.execute("SET log_statement = 'all'")
                    cursor.execute("SET log_duration = on")
                    cursor.execute("SET log_min_duration_statement = 1000")  # Log slow queries
        
        @event.listens_for(self.engine.sync_engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log connection checkout for monitoring"""
            logger.debug("Database connection checked out")
        
        @event.listens_for(self.engine.sync_engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Log connection checkin for monitoring"""
            logger.debug("Database connection checked in")
    
    async def _create_schema(self) -> None:
        """Create database schema if it doesn't exist"""
        try:
            async with self.engine.begin() as conn:
                # Create vector extension
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                
                # Create all tables
                await conn.run_sync(Base.metadata.create_all)
                
            logger.info("Database schema created successfully")
            
        except Exception as e:
            logger.error("Failed to create database schema", error=str(e))
            raise
    
    async def _create_vector_indexes(self) -> None:
        """Create optimized vector similarity search indexes"""
        try:
            async with self.engine.begin() as conn:
                # Check if indexes already exist
                result = await conn.execute(text("""
                    SELECT indexname, indexdef FROM pg_indexes 
                    WHERE tablename = 'document_chunks' 
                    AND indexname LIKE '%embedding%'
                """))
                
                existing_indexes = {row[0]: row[1] for row in result.fetchall()}
                
                # Create HNSW index for fast approximate similarity search
                if 'idx_chunk_embedding_hnsw' not in existing_indexes:
                    await conn.execute(text("""
                        CREATE INDEX CONCURRENTLY idx_chunk_embedding_hnsw 
                        ON document_chunks USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 32, ef_construction = 128)
                    """))
                    logger.info("HNSW vector index created with optimized parameters")
                
                # Create IVFFlat index as alternative for different query patterns
                if 'idx_chunk_embedding_ivfflat' not in existing_indexes:
                    await conn.execute(text("""
                        CREATE INDEX CONCURRENTLY idx_chunk_embedding_ivfflat
                        ON document_chunks USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 200)
                    """))
                    logger.info("IVFFlat vector index created")
                
                # Create composite indexes for filtered vector searches
                if 'idx_chunk_user_embedding' not in existing_indexes:
                    await conn.execute(text("""
                        CREATE INDEX CONCURRENTLY idx_chunk_user_embedding
                        ON document_chunks (user_id) INCLUDE (embedding)
                    """))
                    logger.info("User-filtered vector index created")
                
                if 'idx_chunk_type_embedding' not in existing_indexes:
                    await conn.execute(text("""
                        CREATE INDEX CONCURRENTLY idx_chunk_type_embedding
                        ON document_chunks (source_type) INCLUDE (embedding)
                    """))
                    logger.info("Source type filtered vector index created")
                
                # Create supporting indexes for hybrid search
                if 'idx_chunk_text_gin' not in existing_indexes:
                    await conn.execute(text("""
                        CREATE INDEX CONCURRENTLY idx_chunk_text_gin
                        ON document_chunks USING gin (to_tsvector('english', text))
                    """))
                    logger.info("Full-text search index created")
                
                # Create indexes for metadata queries
                if 'idx_chunk_metadata_gin' not in existing_indexes:
                    await conn.execute(text("""
                        CREATE INDEX CONCURRENTLY idx_chunk_metadata_gin
                        ON document_chunks USING gin (metadata)
                    """))
                    logger.info("Metadata search index created")
                
                # Create performance monitoring indexes
                if 'idx_chunk_importance' not in existing_indexes:
                    await conn.execute(text("""
                        CREATE INDEX CONCURRENTLY idx_chunk_importance
                        ON document_chunks (importance_score DESC NULLS LAST)
                        WHERE importance_score IS NOT NULL
                    """))
                    logger.info("Importance score index created")
                
                logger.info("All vector indexes created successfully")
                    
        except Exception as e:
            logger.warning("Failed to create some vector indexes", error=str(e))
            # Don't raise - indexes can be created manually if needed
    
    async def health_check(self) -> bool:
        """Check database health"""
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with proper error handling"""
        if not self._initialized:
            await self.initialize()
        
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error("Database session error", error=str(e), exc_info=True)
            raise
        except Exception as e:
            await session.rollback()
            logger.error("Unexpected session error", error=str(e), exc_info=True)
            raise
        finally:
            await session.close()
    
    async def optimize_connection_pool(self) -> Dict[str, Any]:
        """Optimize connection pool based on usage patterns"""
        try:
            async with self.get_session() as session:
                # Get current connection statistics
                result = await session.execute(text("""
                    SELECT 
                        count(*) as total_connections,
                        count(*) FILTER (WHERE state = 'active') as active_connections,
                        count(*) FILTER (WHERE state = 'idle') as idle_connections,
                        count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                        max(extract(epoch from (now() - query_start))) as longest_query_seconds
                    FROM pg_stat_activity 
                    WHERE datname = current_database()
                """))
                
                stats = dict(result.fetchone()._mapping)
                
                # Calculate pool utilization
                pool_size = settings.database.pool_size
                max_overflow = settings.database.max_overflow
                total_pool_capacity = pool_size + max_overflow
                
                utilization = stats['total_connections'] / total_pool_capacity
                
                recommendations = []
                
                # Generate optimization recommendations
                if utilization > 0.8:
                    recommendations.append("Consider increasing pool size or max_overflow")
                elif utilization < 0.3:
                    recommendations.append("Pool may be oversized - consider reducing pool size")
                
                if stats['idle_connections'] > stats['active_connections'] * 2:
                    recommendations.append("Many idle connections - consider reducing pool_timeout")
                
                if stats['idle_in_transaction'] > 0:
                    recommendations.append("Idle in transaction connections detected - check for uncommitted transactions")
                
                if stats['longest_query_seconds'] and stats['longest_query_seconds'] > 30:
                    recommendations.append("Long-running queries detected - consider query optimization")
                
                optimization_result = {
                    'connection_stats': stats,
                    'pool_configuration': {
                        'pool_size': pool_size,
                        'max_overflow': max_overflow,
                        'pool_timeout': settings.database.pool_timeout,
                        'pool_recycle': settings.database.pool_recycle
                    },
                    'utilization': utilization,
                    'recommendations': recommendations
                }
                
                logger.info("Connection pool optimization analysis completed", 
                           utilization=utilization, 
                           recommendations_count=len(recommendations))
                
                return optimization_result
                
        except Exception as e:
            logger.error("Connection pool optimization failed", error=str(e))
            return {'error': str(e)}
    
    async def analyze_query_performance(self, limit: int = 10) -> Dict[str, Any]:
        """Analyze query performance using pg_stat_statements"""
        try:
            async with self.get_session() as session:
                # Get slow queries
                result = await session.execute(text("""
                    SELECT 
                        query,
                        calls,
                        total_exec_time,
                        mean_exec_time,
                        max_exec_time,
                        rows,
                        100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
                    FROM pg_stat_statements 
                    WHERE query NOT LIKE '%pg_stat_statements%'
                    ORDER BY mean_exec_time DESC 
                    LIMIT :limit
                """), {'limit': limit})
                
                slow_queries = [dict(row._mapping) for row in result.fetchall()]
                
                # Get index usage statistics
                result = await session.execute(text("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname,
                        idx_scan,
                        idx_tup_read,
                        idx_tup_fetch,
                        pg_size_pretty(pg_relation_size(indexname::regclass)) as size
                    FROM pg_stat_user_indexes 
                    WHERE schemaname = 'public'
                    ORDER BY idx_scan DESC
                """))
                
                index_stats = [dict(row._mapping) for row in result.fetchall()]
                
                # Get table statistics
                result = await session.execute(text("""
                    SELECT 
                        schemaname,
                        tablename,
                        n_tup_ins + n_tup_upd + n_tup_del as total_writes,
                        seq_scan,
                        seq_tup_read,
                        idx_scan,
                        idx_tup_fetch,
                        pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size
                    FROM pg_stat_user_tables 
                    WHERE schemaname = 'public'
                    ORDER BY total_writes DESC
                """))
                
                table_stats = [dict(row._mapping) for row in result.fetchall()]
                
                return {
                    'slow_queries': slow_queries,
                    'index_statistics': index_stats,
                    'table_statistics': table_stats,
                    'analysis_timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Query performance analysis failed", error=str(e))
            return {'error': str(e)}
    
    async def optimize_vector_search_performance(self) -> Dict[str, Any]:
        """Optimize vector search performance specifically"""
        try:
            async with self.get_session() as session:
                # Analyze vector index usage
                result = await session.execute(text("""
                    SELECT 
                        indexname,
                        idx_scan,
                        idx_tup_read,
                        idx_tup_fetch,
                        pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
                    FROM pg_stat_user_indexes 
                    WHERE indexname LIKE '%embedding%'
                    ORDER BY idx_scan DESC
                """))
                
                vector_index_stats = [dict(row._mapping) for row in result.fetchall()]
                
                # Check vector search query patterns
                result = await session.execute(text("""
                    SELECT 
                        query,
                        calls,
                        mean_exec_time,
                        max_exec_time
                    FROM pg_stat_statements 
                    WHERE query LIKE '%embedding%' 
                       OR query LIKE '%vector%'
                       OR query LIKE '%cosine_distance%'
                    ORDER BY calls DESC
                    LIMIT 5
                """))
                
                vector_queries = [dict(row._mapping) for row in result.fetchall()]
                
                # Get vector table statistics
                result = await session.execute(text("""
                    SELECT 
                        count(*) as total_chunks,
                        count(DISTINCT user_id) as unique_users,
                        count(DISTINCT document_id) as unique_documents,
                        avg(array_length(embedding, 1)) as avg_embedding_dimension,
                        pg_size_pretty(pg_total_relation_size('document_chunks')) as table_size
                    FROM document_chunks
                """))
                
                chunk_stats = dict(result.fetchone()._mapping)
                
                # Generate optimization recommendations
                recommendations = []
                
                # Check index usage
                for idx_stat in vector_index_stats:
                    if idx_stat['idx_scan'] == 0:
                        recommendations.append(f"Index {idx_stat['indexname']} is unused - consider dropping")
                    elif idx_stat['idx_scan'] < 10:
                        recommendations.append(f"Index {idx_stat['indexname']} has low usage - monitor for removal")
                
                # Check query performance
                for query_stat in vector_queries:
                    if query_stat['mean_exec_time'] > 1000:  # > 1 second
                        recommendations.append("Vector queries are slow - consider index tuning or query optimization")
                
                # Check data distribution
                if chunk_stats['total_chunks'] > 1000000:  # > 1M chunks
                    recommendations.append("Large dataset detected - consider partitioning by user_id or date")
                
                return {
                    'vector_index_statistics': vector_index_stats,
                    'vector_query_patterns': vector_queries,
                    'chunk_statistics': chunk_stats,
                    'recommendations': recommendations,
                    'optimization_timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Vector search optimization analysis failed", error=str(e))
            return {'error': str(e)}
    
    async def create_database_partitions(self) -> bool:
        """Create table partitions for better performance with large datasets"""
        try:
            async with self.engine.begin() as conn:
                # Check if partitioning is already set up
                result = await conn.execute(text("""
                    SELECT tablename FROM pg_tables 
                    WHERE tablename LIKE 'document_chunks_%'
                    AND schemaname = 'public'
                """))
                
                existing_partitions = [row[0] for row in result.fetchall()]
                
                if existing_partitions:
                    logger.info("Database partitions already exist", partitions=existing_partitions)
                    return True
                
                # Create partitioned table structure (this would require schema migration)
                # For now, just create indexes that help with large datasets
                
                # Create partial indexes for active data
                await conn.execute(text("""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_recent_embedding
                    ON document_chunks USING hnsw (embedding vector_cosine_ops)
                    WHERE created_at > (CURRENT_DATE - INTERVAL '30 days')
                    WITH (m = 16, ef_construction = 64)
                """))
                
                # Create index for user-specific queries
                await conn.execute(text("""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_user_recent
                    ON document_chunks (user_id, created_at DESC)
                    WHERE created_at > (CURRENT_DATE - INTERVAL '90 days')
                """))
                
                logger.info("Performance optimization indexes created")
                return True
                
        except Exception as e:
            logger.error("Failed to create database partitions", error=str(e))
            return False
    
    async def close(self) -> None:
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")

# Global database manager instance
db_manager = DatabaseManager()

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with db_manager.get_session() as session:
        yield session

async def get_async_session() -> AsyncSession:
    """Get async session for background tasks"""
    if not db_manager._initialized:
        await db_manager.initialize()
    return db_manager.session_factory()

# Startup and shutdown handlers
async def startup_database():
    """Initialize database on startup"""
    await db_manager.initialize()

async def shutdown_database():
    """Close database connections on shutdown"""
    await db_manager.close()

# Additional utility functions for compatibility
async def create_database_engine() -> AsyncEngine:
    """Create and return database engine"""
    if not db_manager._initialized:
        await db_manager.initialize()
    return db_manager.engine

async def init_database():
    """Initialize database (alias for startup_database)"""
    await startup_database()

# Transaction management utilities
@asynccontextmanager
async def transaction():
    """Context manager for database transactions"""
    async with db_manager.get_session() as session:
        async with session.begin():
            yield session

class DatabaseError(Exception):
    """Custom database error"""
    pass

class ConnectionError(DatabaseError):
    """Database connection error"""
    pass

class TransactionError(DatabaseError):
    """Database transaction error"""
    pass

# Retry decorator for database operations
def retry_db_operation(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry database operations on failure"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (DisconnectionError, ConnectionError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            "Database operation failed, retrying",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            error=str(e)
                        )
                        await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error(
                            "Database operation failed after all retries",
                            attempts=max_retries,
                            error=str(e)
                        )
                        raise
                except Exception as e:
                    # Don't retry for other types of errors
                    logger.error("Database operation failed", error=str(e))
                    raise
            
            raise last_exception
        
        return wrapper
    return decorator