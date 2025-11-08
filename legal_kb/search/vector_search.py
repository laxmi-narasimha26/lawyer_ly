"""
Dense Vector Similarity Search Engine
Implements HNSW-based vector search for legal documents
"""
import asyncio
import time
from typing import List, Dict, Optional, Tuple, Any
import logging
from datetime import date

from ..database.connection import get_db_manager
from ..models.legal_models import SearchResult, SearchResults

logger = logging.getLogger(__name__)


def _to_pgvector(values: List[float]) -> str:
    """Convert a Python list of floats into pgvector textual representation."""
    return "[" + ",".join(f"{v:.10f}" for v in values) + "]"


def _normalize_embedding(value: Any) -> Optional[List[float]]:
    """Normalize various pgvector return types into a python list of floats."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return [float(v) for v in value]
    if isinstance(value, memoryview):
        return list(value.tolist())
    if isinstance(value, str):
        stripped = value.strip("[]")
        if not stripped:
            return []
        return [float(x) for x in stripped.split(",")]
    try:
        return list(value)
    except TypeError:
        return None

class VectorSearchEngine:
    """Dense vector similarity search using HNSW indexes"""
    
    def __init__(self):
        self.similarity_threshold = 0.0
        self.hnsw_params = {
            "M": 16,
            "ef_construction": 200,
            "ef_search": 196
        }
        self.default_statute_k = 50
        self.default_case_k = 200
    
    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _resolve_threshold(threshold: Optional[float]) -> float:
        """Return a similarity floor, defaulting to a permissive value when None."""
        if threshold is None:
            return -1.0
        return threshold
    
    async def search_similar_statutes(
        self, 
        query_embedding: List[float], 
        k: int = 20,
        similarity_threshold: float = None,
        act_filter: Optional[str] = None,
        effective_date: Optional[date] = None
    ) -> List[SearchResult]:
        """
        Search for similar statute chunks using vector similarity
        """
        try:
            base_threshold = similarity_threshold if similarity_threshold is not None else (
                self.similarity_threshold if self.similarity_threshold > 0 else None
            )
            threshold = self._resolve_threshold(base_threshold)
            effective_date = effective_date or date.today()
            
            db_manager = await get_db_manager()
            
            # Build query with filters
            query = """
            SELECT 
                id,
                doc_id,
                title,
                section_no,
                unit_type,
                SUBSTRING(text, 1, 400) AS text,
                act,
                tokens,
                effective_from,
                effective_to,
                source_path,
                1 - (embedding <=> $1::vector) as similarity_score
            FROM statute_chunks
            WHERE 
                embedding IS NOT NULL
                AND ($2::text IS NULL OR act = $2)
                AND ($3::date IS NULL OR effective_from IS NULL OR effective_from <= $3)
                AND ($3::date IS NULL OR effective_to IS NULL OR effective_to > $3)
            ORDER BY embedding <=> $1::vector
            LIMIT $4
            """
            embedding_param = _to_pgvector(query_embedding)
            
            results = await db_manager.execute_query(
                query, 
                embedding_param, 
                act_filter, 
                effective_date, 
                k
            )
            
            # Convert to SearchResult objects
            search_results = []
            for row in results:
                result = SearchResult(
                    id=row["id"],
                    similarity_score=float(row["similarity_score"]),
                    content=row["text"],
                    metadata={
                        "title": row["title"],
                        "doc_id": row["doc_id"],
                        "section_no": row["section_no"],
                        "unit_type": row["unit_type"],
                        "act": row["act"],
                        "canonical_id": f"{row['doc_id']}:Sec:{row['section_no']}",
                        "tokens": row["tokens"],
                        "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
                        "effective_to": row["effective_to"].isoformat() if row["effective_to"] else None,
                        "source_path": row["source_path"]
                    },
                    source_type="statute"
                )
                search_results.append(result)
            
            logger.debug(f"Vector search found {len(search_results)} statute results")
            return search_results
            
        except Exception as e:
            logger.error(f"Statute vector search failed: {e}")
            return []
    
    async def search_similar_cases(
        self,
        query_embedding: List[float],
        k: int = 50,
        similarity_threshold: float = None,
        court_filter: Optional[str] = None,
        date_filter: Optional[date] = None
    ) -> List[SearchResult]:
        """
        Search for similar case chunks using vector similarity
        """
        try:
            base_threshold = similarity_threshold if similarity_threshold is not None else (
                self.similarity_threshold if self.similarity_threshold > 0 else None
            )
            threshold = self._resolve_threshold(base_threshold)
            date_filter = date_filter or date.today()
            
            db_manager = await get_db_manager()
            try:
                await db_manager.execute_command("SET LOCAL hnsw.ef_search = 256;")
            except Exception:
                pass
            
            # Build query with filters
            query = """
            SELECT 
                id,
                doc_id,
                case_title,
                decision_date,
                bench,
                citation_strings,
                para_range,
                SUBSTRING(text, 1, 400) AS text,
                tokens,
                source_path,
                1 - (embedding <=> $1::vector) as similarity_score
            FROM judgment_chunks
            WHERE 
                embedding IS NOT NULL
                AND ($2::text IS NULL OR doc_id ILIKE $2 || '%%')
                AND ($3::date IS NULL OR (decision_date IS NOT NULL AND decision_date <= $3))
            ORDER BY embedding <=> $1::vector
            LIMIT $4
            """
            embedding_param = _to_pgvector(query_embedding)
            
            results = await db_manager.execute_query(
                query,
                embedding_param,
                court_filter,
                date_filter,
                k
            )
            
            # Convert to SearchResult objects
            search_results = []
            for row in results:
                result = SearchResult(
                    id=row["id"],
                    similarity_score=float(row["similarity_score"]),
                    content=row["text"],
                    metadata={
                        "doc_id": row["doc_id"],
                        "case_title": row["case_title"],
                        "decision_date": row["decision_date"].isoformat() if row["decision_date"] else None,
                        "bench": row["bench"],
                        "citation_strings": row["citation_strings"],
                        "para_range": row["para_range"],
                        "tokens": row["tokens"],
                        "source_path": row["source_path"]
                    },
                    source_type="case"
                )
                search_results.append(result)
            
            logger.debug(f"Vector search found {len(search_results)} case results")
            return search_results
            
        except Exception as e:
            logger.error(f"Case vector search failed: {e}")
            return []
    
    async def hybrid_vector_search(
        self,
        query_embedding: List[float],
        statute_k: int = 60,
        case_k: int = 120,
        filters: Optional[Dict[str, Any]] = None
    ) -> SearchResults:
        """
        Perform hybrid vector search across both statutes and cases
        """
        try:
            filters = filters or {}
            
            start = time.perf_counter()
            statute_task = self.search_similar_statutes(
                query_embedding,
                k=statute_k or self.default_statute_k,
                act_filter=filters.get("act"),
                effective_date=self._parse_date(filters.get("as_on_date"))
            )
            
            case_task = self.search_similar_cases(
                query_embedding,
                k=case_k or self.default_case_k,
                court_filter=filters.get("court_prefix"),
                date_filter=self._parse_date(filters.get("decision_date_to"))
            )
            
            statute_results, case_results = await asyncio.gather(statute_task, case_task)
            
            exclude_ids: List[str] = filters.get("exclude_ids") or []
            if exclude_ids:
                statute_results = [res for res in statute_results if res.id not in exclude_ids]
                case_results = [res for res in case_results if res.id not in exclude_ids]
            
            processing_time = time.perf_counter() - start
            total_retrieved = len(statute_results) + len(case_results)
            
            return SearchResults(
                statutes=statute_results,
                cases=case_results,
                total_retrieved=total_retrieved,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Hybrid vector search failed: {e}")
            return SearchResults(
                statutes=[],
                cases=[],
                total_retrieved=0,
                processing_time=0.0
            )
    
    async def find_similar_documents(
        self,
        document_id: str,
        k: int = 10
    ) -> List[SearchResult]:
        """
        Find documents similar to a given document
        """
        try:
            db_manager = await get_db_manager()
            
            # Get the embedding of the source document
            source_query = """
            SELECT embedding, 'statute' as source_type FROM statute_chunks WHERE id = $1
            UNION ALL
            SELECT embedding, 'case' as source_type FROM judgment_chunks WHERE id = $1
            """
            
            source_results = await db_manager.execute_query(source_query, document_id)
            
            if not source_results:
                logger.warning(f"Document {document_id} not found")
                return []
            
            source_embedding = _normalize_embedding(source_results[0]["embedding"])
            source_type = source_results[0]["source_type"]
            
            if not source_embedding:
                logger.warning(f"Document {document_id} has no embedding stored")
                return []
            
            # Search for similar documents
            if source_type == "statute":
                similar_results = await self.search_similar_statutes(
                    source_embedding, k=k
                )
            else:
                similar_results = await self.search_similar_cases(
                    source_embedding, k=k
                )
            
            # Filter out the source document itself
            filtered_results = [
                result for result in similar_results 
                if result.id != document_id
            ]
            
            return filtered_results[:k-1]  # Return k-1 since we excluded source
            
        except Exception as e:
            logger.error(f"Similar document search failed: {e}")
            return []
    
    async def get_search_statistics(self) -> Dict[str, Any]:
        """
        Get vector search performance statistics
        """
        try:
            db_manager = await get_db_manager()
            
            stats_query = """
            SELECT 
                (SELECT COUNT(*) FROM statute_chunks WHERE embedding IS NOT NULL) as indexed_statutes,
                (SELECT COUNT(*) FROM judgment_chunks WHERE embedding IS NOT NULL) as indexed_cases,
                (SELECT COUNT(*) FROM statute_chunks) as total_statutes,
                (SELECT COUNT(*) FROM judgment_chunks) as total_cases
            """
            
            result = await db_manager.execute_query(stats_query)
            
            if result:
                row = result[0]
                return {
                    "indexed_statutes": row["indexed_statutes"],
                    "indexed_cases": row["indexed_cases"],
                    "total_statutes": row["total_statutes"],
                    "total_cases": row["total_cases"],
                    "indexing_coverage": {
                        "statutes": row["indexed_statutes"] / max(1, row["total_statutes"]),
                        "cases": row["indexed_cases"] / max(1, row["total_cases"])
                    },
                    "embedding_dimension": 1536,
                    "hnsw_parameters": self.hnsw_params
                }
            
            return {"error": "No statistics available"}
            
        except Exception as e:
            logger.error(f"Failed to get search statistics: {e}")
            return {"error": str(e)}
    
    async def optimize_search_parameters(
        self,
        sample_queries: List[List[float]],
        ground_truth: List[List[str]]
    ) -> Dict[str, float]:
        """
        Optimize search parameters based on sample queries and ground truth
        """
        try:
            best_params = {
                "similarity_threshold": self.similarity_threshold,
                "ef_search": self.hnsw_params["ef_search"]
            }
            best_score = 0.0
            
            # Test different parameter combinations
            thresholds = [0.6, 0.65, 0.7, 0.75, 0.8]
            ef_values = [64, 96, 128, 160, 200]
            
            for threshold in thresholds:
                for ef_search in ef_values:
                    # Temporarily update parameters
                    old_threshold = self.similarity_threshold
                    old_ef = self.hnsw_params["ef_search"]
                    
                    self.similarity_threshold = threshold
                    self.hnsw_params["ef_search"] = ef_search
                    
                    # Evaluate on sample queries
                    total_score = 0.0
                    for query_emb, truth in zip(sample_queries, ground_truth):
                        results = await self.hybrid_vector_search(query_emb)
                        all_results = results.statutes + results.cases
                        retrieved_ids = [r.id for r in all_results[:10]]
                        
                        # Calculate precision@10
                        relevant_retrieved = len(set(retrieved_ids) & set(truth))
                        precision = relevant_retrieved / min(10, len(retrieved_ids)) if retrieved_ids else 0
                        total_score += precision
                    
                    avg_score = total_score / len(sample_queries)
                    
                    if avg_score > best_score:
                        best_score = avg_score
                        best_params = {
                            "similarity_threshold": threshold,
                            "ef_search": ef_search
                        }
                    
                    # Restore old parameters
                    self.similarity_threshold = old_threshold
                    self.hnsw_params["ef_search"] = old_ef
            
            # Apply best parameters
            self.similarity_threshold = best_params["similarity_threshold"]
            self.hnsw_params["ef_search"] = best_params["ef_search"]
            
            logger.info(f"Optimized search parameters: {best_params}, score: {best_score:.3f}")
            return {**best_params, "optimization_score": best_score}
            
        except Exception as e:
            logger.error(f"Parameter optimization failed: {e}")
            return {"error": str(e)}

# Global vector search engine instance
vector_search_engine: Optional[VectorSearchEngine] = None

async def get_vector_search_engine() -> VectorSearchEngine:
    """Get the global vector search engine instance"""
    global vector_search_engine
    if vector_search_engine is None:
        vector_search_engine = VectorSearchEngine()
    return vector_search_engine
