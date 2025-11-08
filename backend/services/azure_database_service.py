"""
Azure Database for PostgreSQL service with PGVector extension
Production-grade database service with comprehensive monitoring and optimization
"""
import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text, select, func
from sqlalchemy.exc import SQLAlchemyError
import psycopg2
from contextlib import asynccontextmanager

from config import settings
from database.models import Base, DocumentChunk, SystemMetrics
from utils.monitoring import metrics_collector
from utils.exceptions import ProcessingError

logger = structlog.get_logger(__name__)

class AzureDatabaseService:
    """
    Production-grade Azure Database for PostgreSQL service
    
    Features:
    - PGVector extension management
    - Connection pooling optimization
    - Performance monitoring
    - Backup and disaster recovery
    - Index optimization for vector search
    - Query performance analysis
    """
    
    def __init__(self):
        self.engine = None
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'query_count': 0,
            'slow_queries': 0,
            'vector_searches': 0
        }
        
        # Performance thresholds
        self.slow_query_threshold_ms = 1000
        self.connection_timeout_seconds = 30
        
        logger.info("Azure Database service initialized")
    
    async def initialize(self):
        """Initialize Azure PostgreSQL connection with optimizations"""
        try:
            # Create optimized engine for Azure PostgreSQL
            self.engine = create_async_engine(
                settings.database.url,
                echo=settings.database.echo,
                pool_size=settings.database.pool_size,
                max_overflow=settings.database.max_overflow,
                pool_timeout=settings.database.pool_timeout,
                pool_recycle=settings.database.pool_recycle,
                connect_args={
                    "server_settings": {
                        "application_name": f"{settings.app_name}-{settings.environment}",
                        "jit": "off",  # Disable JIT for consistent performance
                        "shared_preload_libraries": "vector",
                        "work_mem": "256MB",
                        "maintenance_work_mem": "1GB",
                        "effective_cache_size": "4GB",
                        "random_page_cost": "1.1",
                        "seq_page_cost": "1.0",
                        "max_parallel_workers_per_gather": "2"
                    },
                    "command_timeout": self.connection_timeout_seconds,
                    "options": "-c timezone=UTC"
                }
            )
            
            # Test connection and setup
            await self._setup_database()
            
            logger.info(
                "Azure Database initialized successfully",
                pool_size=settings.database.pool_size,
                max_overflow=settings.database.max_overflow
            )
            
        except Exception as e:
            logger.error("Failed to initialize Azure Database", error=str(e), exc_info=True)
            raise ProcessingError(
                message="Database initialization failed",
                details={"error": str(e)}
            )
    
    async def _setup_database(self):
        """Setup database with required extensions and optimizations"""
        async with self.engine.begin() as conn:
            # Enable required extensions
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            
            # Create schema if needed
            await conn.run_sync(Base.metadata.create_all)
            
            # Setup vector indexes
            await self._create_vector_indexes(conn)
            
            # Setup performance monitoring
            await self._setup_performance_monitoring(conn)
            
        logger.info("Database setup completed successfully")
    
    async def _create_vector_indexes(self, conn):
        """Create optimized vector indexes for similarity search"""
        try:
            # Check if indexes already exist
            result = await conn.execute(text("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'document_chunks' 
                AND indexname LIKE '%embedding%'
            """))
            
            existing_indexes = [row[0] for row in result.fetchall()]
            
            if 'idx_chunk_embedding_hnsw' not in existing_indexes:
                # Create HNSW index for fast approximate search
                await conn.execute(text("""
                    CREATE INDEX CONCURRENTLY idx_chunk_embedding_hnsw 
                    ON document_chunks USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64)
                """))
                logger.info("HNSW vector index created")
            
            if 'idx_chunk_embedding_ivfflat' not in existing_indexes:
                # Create IVFFlat index as alternative
                await conn.execute(text("""
                    CREATE INDEX CONCURRENTLY idx_chunk_embedding_ivfflat
                    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """))
                logger.info("IVFFlat vector index created")
            
            # Create supporting indexes for hybrid search
            if 'idx_chunk_text_search' not in existing_indexes:
                await conn.execute(text("""
                    CREATE INDEX CONCURRENTLY idx_chunk_text_search
                    ON document_chunks USING gin (to_tsvector('english', text))
                """))
                logger.info("Full-text search index created")
            
        except Exception as e:
            logger.warning("Failed to create some vector indexes", error=str(e))
            # Don't raise - indexes can be created manually if needed
    
    async def _setup_performance_monitoring(self, conn):
        """Setup performance monitoring and statistics collection"""
        try:
            # Enable query statistics collection
            await conn.execute(text("SELECT pg_stat_statements_reset()"))
            
            # Create custom monitoring views
            await conn.execute(text("""
                CREATE OR REPLACE VIEW vector_search_stats AS
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes 
                WHERE indexname LIKE '%embedding%'
            """))
            
            logger.info("Performance monitoring setup completed")
            
        except Exception as e:
            logger.warning("Failed to setup performance monitoring", error=str(e))
    
    @asynccontextmanager
    async def get_session(self):
        """Get database session with monitoring"""
        if not self.engine:
            await self.initialize()
        
        session_start = time.time()
        session = None
        
        try:
            from sqlalchemy.ext.asyncio import AsyncSession
            session = AsyncSession(self.engine)
            
            self.connection_stats['active_connections'] += 1
            self.connection_stats['total_connections'] += 1
            
            yield session
            
            await session.commit()
            
        except SQLAlchemyError as e:
            if session:
                await session.rollback()
            
            self.connection_stats['failed_connections'] += 1
            
            logger.error(
                "Database session error",
                error=str(e),
                session_duration_ms=int((time.time() - session_start) * 1000),
                exc_info=True
            )
            raise
            
        finally:
            if session:
                await session.close()
                self.connection_stats['active_connections'] -= 1
            
            session_duration_ms = int((time.time() - session_start) * 1000)
            
            # Record session metrics
            metrics_collector.record_metric(
                "database_session_duration",
                session_duration_ms,
                {"status": "success" if not session else "error"}
            )
    
    async def execute_vector_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        similarity_threshold: float = 0.7,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute optimized vector similarity search
        
        Args:
            query_embedding: Query vector embedding
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            user_id: Filter by user ID
            document_ids: Filter by document IDs
            
        Returns:
            List of similar chunks with metadata
        """
        search_start = time.time()
        
        try:
            async with self.get_session() as session:
                # Build base query
                query = select(DocumentChunk).where(
                    DocumentChunk.embedding.cosine_distance(query_embedding) < (1 - similarity_threshold)
                )
                
                # Add filters
                if user_id:
                    query = query.where(DocumentChunk.user_id == user_id)
                
                if document_ids:
                    query = query.where(DocumentChunk.document_id.in_(document_ids))
                
                # Order by similarity and limit
                query = query.order_by(
                    DocumentChunk.embedding.cosine_distance(query_embedding)
                ).limit(limit)
                
                # Execute query
                result = await session.execute(query)
                chunks = result.scalars().all()
                
                # Convert to dict format with similarity scores
                results = []
                for chunk in chunks:
                    similarity_score = 1 - chunk.embedding.cosine_distance(query_embedding)
                    
                    results.append({
                        'id': str(chunk.id),
                        'text': chunk.text,
                        'similarity_score': float(similarity_score),
                        'source_name': chunk.source_name,
                        'source_type': chunk.source_type.value,
                        'section_number': chunk.section_number,
                        'section_title': chunk.section_title,
                        'page_range': f"{chunk.start_page}-{chunk.end_page}" if chunk.start_page else None,
                        'metadata': chunk.metadata or {}
                    })
                
                search_duration_ms = int((time.time() - search_start) * 1000)
                
                # Record metrics
                self.connection_stats['vector_searches'] += 1
                self.connection_stats['query_count'] += 1
                
                if search_duration_ms > self.slow_query_threshold_ms:
                    self.connection_stats['slow_queries'] += 1
                
                metrics_collector.record_metric(
                    "vector_search_duration",
                    search_duration_ms,
                    {
                        "result_count": len(results),
                        "similarity_threshold": similarity_threshold,
                        "has_filters": bool(user_id or document_ids)
                    }
                )
                
                logger.info(
                    "Vector search completed",
                    duration_ms=search_duration_ms,
                    result_count=len(results),
                    similarity_threshold=similarity_threshold
                )
                
                return results
                
        except Exception as e:
            search_duration_ms = int((time.time() - search_start) * 1000)
            
            logger.error(
                "Vector search failed",
                error=str(e),
                duration_ms=search_duration_ms,
                exc_info=True
            )
            
            metrics_collector.record_metric(
                "vector_search_errors",
                1,
                {"error_type": type(e).__name__}
            )
            
            raise ProcessingError(
                message="Vector search failed",
                details={"error": str(e)}
            )
    
    async def execute_hybrid_search(
        self,
        query_embedding: List[float],
        query_text: str,
        limit: int = 10,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute hybrid search combining vector similarity and text search
        
        Args:
            query_embedding: Query vector embedding
            query_text: Query text for full-text search
            limit: Maximum number of results
            vector_weight: Weight for vector similarity score
            text_weight: Weight for text search score
            user_id: Filter by user ID
            
        Returns:
            List of results with combined scores
        """
        search_start = time.time()
        
        try:
            async with self.get_session() as session:
                # Execute hybrid search query
                hybrid_query = text("""
                    WITH vector_search AS (
                        SELECT 
                            id,
                            text,
                            source_name,
                            source_type,
                            section_number,
                            section_title,
                            start_page,
                            end_page,
                            metadata,
                            1 - (embedding <=> :query_embedding) as vector_score
                        FROM document_chunks
                        WHERE (:user_id IS NULL OR user_id = :user_id)
                        ORDER BY embedding <=> :query_embedding
                        LIMIT :vector_limit
                    ),
                    text_search AS (
                        SELECT 
                            id,
                            text,
                            source_name,
                            source_type,
                            section_number,
                            section_title,
                            start_page,
                            end_page,
                            metadata,
                            ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', :query_text)) as text_score
                        FROM document_chunks
                        WHERE (:user_id IS NULL OR user_id = :user_id)
                        AND to_tsvector('english', text) @@ plainto_tsquery('english', :query_text)
                        ORDER BY ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', :query_text)) DESC
                        LIMIT :text_limit
                    )
                    SELECT DISTINCT
                        COALESCE(v.id, t.id) as id,
                        COALESCE(v.text, t.text) as text,
                        COALESCE(v.source_name, t.source_name) as source_name,
                        COALESCE(v.source_type, t.source_type) as source_type,
                        COALESCE(v.section_number, t.section_number) as section_number,
                        COALESCE(v.section_title, t.section_title) as section_title,
                        COALESCE(v.start_page, t.start_page) as start_page,
                        COALESCE(v.end_page, t.end_page) as end_page,
                        COALESCE(v.metadata, t.metadata) as metadata,
                        COALESCE(v.vector_score, 0) * :vector_weight + COALESCE(t.text_score, 0) * :text_weight as combined_score
                    FROM vector_search v
                    FULL OUTER JOIN text_search t ON v.id = t.id
                    ORDER BY combined_score DESC
                    LIMIT :final_limit
                """)
                
                result = await session.execute(hybrid_query, {
                    'query_embedding': query_embedding,
                    'query_text': query_text,
                    'user_id': user_id,
                    'vector_limit': limit * 2,  # Get more candidates
                    'text_limit': limit * 2,
                    'vector_weight': vector_weight,
                    'text_weight': text_weight,
                    'final_limit': limit
                })
                
                rows = result.fetchall()
                
                # Convert to dict format
                results = []
                for row in rows:
                    results.append({
                        'id': str(row.id),
                        'text': row.text,
                        'combined_score': float(row.combined_score),
                        'source_name': row.source_name,
                        'source_type': row.source_type,
                        'section_number': row.section_number,
                        'section_title': row.section_title,
                        'page_range': f"{row.start_page}-{row.end_page}" if row.start_page else None,
                        'metadata': row.metadata or {}
                    })
                
                search_duration_ms = int((time.time() - search_start) * 1000)
                
                # Record metrics
                metrics_collector.record_metric(
                    "hybrid_search_duration",
                    search_duration_ms,
                    {
                        "result_count": len(results),
                        "vector_weight": vector_weight,
                        "text_weight": text_weight
                    }
                )
                
                logger.info(
                    "Hybrid search completed",
                    duration_ms=search_duration_ms,
                    result_count=len(results)
                )
                
                return results
                
        except Exception as e:
            logger.error("Hybrid search failed", error=str(e), exc_info=True)
            raise ProcessingError(
                message="Hybrid search failed",
                details={"error": str(e)}
            )
    
    async def optimize_vector_indexes(self):
        """Optimize vector indexes for better performance with advanced analysis"""
        try:
            async with self.get_session() as session:
                # Comprehensive vector index analysis
                stats_query = text("""
                    SELECT 
                        i.schemaname,
                        i.tablename,
                        i.indexname,
                        i.idx_scan,
                        i.idx_tup_read,
                        i.idx_tup_fetch,
                        pg_size_pretty(pg_relation_size(i.indexname::regclass)) as index_size,
                        pg_stat_get_blocks_fetched(c.oid) - pg_stat_get_blocks_hit(c.oid) as disk_reads,
                        pg_stat_get_blocks_hit(c.oid) as buffer_hits,
                        CASE 
                            WHEN pg_stat_get_blocks_fetched(c.oid) > 0 
                            THEN round(100.0 * pg_stat_get_blocks_hit(c.oid) / pg_stat_get_blocks_fetched(c.oid), 2)
                            ELSE 0 
                        END as hit_ratio
                    FROM pg_stat_user_indexes i
                    JOIN pg_class c ON c.oid = i.indexrelid
                    WHERE i.indexname LIKE '%embedding%'
                    ORDER BY i.idx_scan DESC
                """)
                
                result = await session.execute(stats_query)
                index_stats = result.fetchall()
                
                optimization_actions = []
                
                # Analyze each index
                for stat in index_stats:
                    logger.info(
                        "Vector index detailed statistics",
                        index_name=stat.indexname,
                        scans=stat.idx_scan,
                        tuples_read=stat.idx_tup_read,
                        tuples_fetched=stat.idx_tup_fetch,
                        size=stat.index_size,
                        hit_ratio=stat.hit_ratio
                    )
                    
                    # Determine optimization actions
                    if stat.idx_scan == 0:
                        optimization_actions.append(f"Consider dropping unused index: {stat.indexname}")
                    elif stat.hit_ratio < 90:
                        optimization_actions.append(f"Low hit ratio for {stat.indexname}: {stat.hit_ratio}%")
                    elif stat.idx_scan > 1000 and stat.idx_tup_read / max(stat.idx_scan, 1) > 1000:
                        # High usage with poor selectivity - consider reindexing
                        logger.info("Reindexing vector index due to poor selectivity", 
                                   index_name=stat.indexname)
                        await session.execute(text(f"REINDEX INDEX CONCURRENTLY {stat.indexname}"))
                        optimization_actions.append(f"Reindexed {stat.indexname} due to poor selectivity")
                
                # Check for missing indexes based on query patterns
                missing_indexes = await self._analyze_missing_vector_indexes(session)
                optimization_actions.extend(missing_indexes)
                
                # Update index statistics
                await session.execute(text("ANALYZE document_chunks"))
                optimization_actions.append("Updated table statistics")
                
                logger.info("Vector index optimization completed", 
                           actions_taken=len(optimization_actions))
                
                return optimization_actions
                
        except Exception as e:
            logger.error("Failed to optimize vector indexes", error=str(e))
            return [f"Optimization failed: {str(e)}"]
    
    async def _analyze_missing_vector_indexes(self, session: AsyncSession) -> List[str]:
        """Analyze query patterns to identify missing indexes"""
        try:
            # Check for common query patterns that might benefit from additional indexes
            query_patterns = text("""
                SELECT 
                    query,
                    calls,
                    mean_exec_time,
                    total_exec_time
                FROM pg_stat_statements 
                WHERE query LIKE '%document_chunks%' 
                  AND query LIKE '%embedding%'
                  AND calls > 10
                ORDER BY mean_exec_time DESC
                LIMIT 10
            """)
            
            result = await session.execute(query_patterns)
            slow_queries = result.fetchall()
            
            suggestions = []
            
            for query_stat in slow_queries:
                query = query_stat.query.lower()
                
                # Check for user_id filtering without proper index
                if 'user_id' in query and 'embedding' in query and query_stat.mean_exec_time > 500:
                    suggestions.append("Consider composite index on (user_id, embedding) for user-filtered vector searches")
                
                # Check for source_type filtering
                if 'source_type' in query and 'embedding' in query and query_stat.mean_exec_time > 500:
                    suggestions.append("Consider composite index on (source_type, embedding) for type-filtered searches")
                
                # Check for date range filtering
                if 'created_at' in query and 'embedding' in query and query_stat.mean_exec_time > 500:
                    suggestions.append("Consider partial index on recent embeddings for time-filtered searches")
            
            return list(set(suggestions))  # Remove duplicates
            
        except Exception as e:
            logger.warning("Failed to analyze missing indexes", error=str(e))
            return []
    
    async def tune_vector_search_parameters(self) -> Dict[str, Any]:
        """Tune vector search parameters for optimal performance"""
        try:
            async with self.get_session() as session:
                # Get current vector index parameters
                index_info_query = text("""
                    SELECT 
                        indexname,
                        indexdef
                    FROM pg_indexes 
                    WHERE indexname LIKE '%embedding%'
                    AND tablename = 'document_chunks'
                """)
                
                result = await session.execute(index_info_query)
                current_indexes = {row.indexname: row.indexdef for row in result.fetchall()}
                
                # Analyze query performance with current parameters
                perf_query = text("""
                    SELECT 
                        avg(mean_exec_time) as avg_query_time,
                        max(max_exec_time) as max_query_time,
                        sum(calls) as total_calls
                    FROM pg_stat_statements 
                    WHERE query LIKE '%cosine_distance%'
                    OR query LIKE '%<=>%'
                """)
                
                result = await session.execute(perf_query)
                perf_stats = dict(result.fetchone()._mapping) if result.rowcount > 0 else {}
                
                # Get data distribution statistics
                data_stats_query = text("""
                    SELECT 
                        count(*) as total_vectors,
                        count(DISTINCT user_id) as unique_users,
                        avg(array_length(embedding, 1)) as avg_dimension
                    FROM document_chunks
                    WHERE embedding IS NOT NULL
                """)
                
                result = await session.execute(data_stats_query)
                data_stats = dict(result.fetchone()._mapping)
                
                # Generate tuning recommendations
                recommendations = []
                
                if data_stats.get('total_vectors', 0) > 100000:
                    recommendations.append("Large dataset detected - consider HNSW with higher m parameter")
                
                if perf_stats.get('avg_query_time', 0) > 1000:  # > 1 second
                    recommendations.append("Slow queries detected - consider increasing ef_construction parameter")
                
                if data_stats.get('unique_users', 0) > 100:
                    recommendations.append("Multi-tenant usage - consider user-specific index partitioning")
                
                tuning_result = {
                    'current_indexes': current_indexes,
                    'performance_stats': perf_stats,
                    'data_statistics': data_stats,
                    'recommendations': recommendations,
                    'optimal_parameters': self._calculate_optimal_parameters(data_stats, perf_stats)
                }
                
                return tuning_result
                
        except Exception as e:
            logger.error("Vector search parameter tuning failed", error=str(e))
            return {'error': str(e)}
    
    def _calculate_optimal_parameters(
        self, 
        data_stats: Dict[str, Any], 
        perf_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate optimal parameters based on data characteristics"""
        total_vectors = data_stats.get('total_vectors', 0)
        avg_query_time = perf_stats.get('avg_query_time', 0)
        
        # HNSW parameters
        if total_vectors < 10000:
            m = 16
            ef_construction = 64
        elif total_vectors < 100000:
            m = 24
            ef_construction = 128
        else:
            m = 32
            ef_construction = 256
        
        # IVFFlat parameters
        lists = max(100, min(1000, int(total_vectors / 1000)))
        
        # Adjust based on performance
        if avg_query_time > 2000:  # Very slow
            ef_construction *= 2
            lists = int(lists * 1.5)
        
        return {
            'hnsw': {
                'm': m,
                'ef_construction': ef_construction
            },
            'ivfflat': {
                'lists': lists
            },
            'reasoning': f"Optimized for {total_vectors} vectors with {avg_query_time:.1f}ms avg query time"
        }
    
    async def get_database_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics"""
        try:
            async with self.get_session() as session:
                # Get table statistics
                table_stats_query = text("""
                    SELECT 
                        schemaname,
                        tablename,
                        n_tup_ins as inserts,
                        n_tup_upd as updates,
                        n_tup_del as deletes,
                        n_live_tup as live_tuples,
                        n_dead_tup as dead_tuples,
                        last_vacuum,
                        last_autovacuum,
                        last_analyze,
                        last_autoanalyze
                    FROM pg_stat_user_tables
                    WHERE tablename IN ('document_chunks', 'documents', 'queries', 'users')
                """)
                
                result = await session.execute(table_stats_query)
                table_stats = [dict(row._mapping) for row in result.fetchall()]
                
                # Get index statistics
                index_stats_query = text("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname,
                        idx_scan,
                        idx_tup_read,
                        idx_tup_fetch
                    FROM pg_stat_user_indexes
                    WHERE tablename IN ('document_chunks', 'documents', 'queries', 'users')
                    ORDER BY idx_scan DESC
                """)
                
                result = await session.execute(index_stats_query)
                index_stats = [dict(row._mapping) for row in result.fetchall()]
                
                # Get database size information
                size_query = text("""
                    SELECT 
                        pg_size_pretty(pg_database_size(current_database())) as database_size,
                        pg_size_pretty(pg_total_relation_size('document_chunks')) as chunks_table_size,
                        pg_size_pretty(pg_total_relation_size('documents')) as documents_table_size
                """)
                
                result = await session.execute(size_query)
                size_info = dict(result.fetchone()._mapping)
                
                # Get connection statistics
                connection_query = text("""
                    SELECT 
                        count(*) as total_connections,
                        count(*) FILTER (WHERE state = 'active') as active_connections,
                        count(*) FILTER (WHERE state = 'idle') as idle_connections
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """)
                
                result = await session.execute(connection_query)
                connection_info = dict(result.fetchone()._mapping)
                
                return {
                    'table_statistics': table_stats,
                    'index_statistics': index_stats,
                    'size_information': size_info,
                    'connection_information': connection_info,
                    'service_statistics': self.connection_stats,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Failed to get database statistics", error=str(e))
            return {
                'error': str(e),
                'service_statistics': self.connection_stats,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive database health check"""
        health_start = time.time()
        
        try:
            async with self.get_session() as session:
                # Test basic connectivity
                await session.execute(text("SELECT 1"))
                
                # Test vector extension
                await session.execute(text("SELECT vector_dims(ARRAY[1,2,3]::vector)"))
                
                # Check index health
                index_health_query = text("""
                    SELECT 
                        indexname,
                        idx_scan > 0 as is_used,
                        pg_size_pretty(pg_relation_size(indexname::regclass)) as size
                    FROM pg_stat_user_indexes 
                    WHERE indexname LIKE '%embedding%'
                """)
                
                result = await session.execute(index_health_query)
                index_health = [dict(row._mapping) for row in result.fetchall()]
                
                health_duration_ms = int((time.time() - health_start) * 1000)
                
                return {
                    'status': 'healthy',
                    'response_time_ms': health_duration_ms,
                    'vector_extension': 'available',
                    'index_health': index_health,
                    'connection_pool': {
                        'size': settings.database.pool_size,
                        'overflow': settings.database.max_overflow,
                        'active': self.connection_stats['active_connections']
                    },
                    'statistics': self.connection_stats
                }
                
        except Exception as e:
            health_duration_ms = int((time.time() - health_start) * 1000)
            
            return {
                'status': 'unhealthy',
                'response_time_ms': health_duration_ms,
                'error': str(e),
                'statistics': self.connection_stats
            }
    
    async def setup_backup_configuration(self):
        """Setup automated backup configuration for Azure PostgreSQL"""
        try:
            async with self.get_session() as session:
                # Create backup monitoring view
                await session.execute(text("""
                    CREATE OR REPLACE VIEW backup_status AS
                    SELECT 
                        now() as check_time,
                        pg_is_in_recovery() as is_replica,
                        pg_last_wal_receive_lsn() as last_wal_received,
                        pg_last_wal_replay_lsn() as last_wal_replayed,
                        EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) as replication_lag_seconds
                """))
                
                logger.info("Backup monitoring configuration completed")
                
        except Exception as e:
            logger.error("Failed to setup backup configuration", error=str(e))
    
    async def cleanup_old_metrics(self, days_to_keep: int = 30):
        """Clean up old system metrics to manage database size"""
        try:
            async with self.get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                delete_query = text("""
                    DELETE FROM system_metrics 
                    WHERE timestamp < :cutoff_date
                """)
                
                result = await session.execute(delete_query, {'cutoff_date': cutoff_date})
                deleted_count = result.rowcount
                
                logger.info(
                    "Old metrics cleaned up",
                    deleted_count=deleted_count,
                    cutoff_date=cutoff_date.isoformat()
                )
                
        except Exception as e:
            logger.error("Failed to cleanup old metrics", error=str(e))

# Global service instance
azure_database_service = AzureDatabaseService()