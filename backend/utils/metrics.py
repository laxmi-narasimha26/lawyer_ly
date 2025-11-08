"""
Metrics collection and monitoring utilities
Production-grade metrics for performance monitoring and analytics
"""
import time
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import structlog
from collections import defaultdict, deque
import threading

logger = structlog.get_logger(__name__)

@dataclass
class QueryMetrics:
    """Metrics for a single query"""
    query_id: str
    user_id: str
    processing_time_ms: int
    confidence_score: float
    citation_count: int
    chunks_retrieved: int
    search_strategy: str
    mode: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    token_usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None

@dataclass
class SystemMetrics:
    """System-wide metrics"""
    timestamp: datetime
    active_users: int
    queries_per_minute: float
    avg_response_time_ms: float
    error_rate: float
    cache_hit_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float

class MetricsCollector:
    """
    Production-grade metrics collector with thread-safe operations
    Collects, aggregates, and exports metrics for monitoring
    """
    
    def __init__(self, max_history_size: int = 10000):
        self.max_history_size = max_history_size
        self._lock = threading.RLock()
        
        # Query metrics storage
        self.query_metrics: deque = deque(maxlen=max_history_size)
        self.query_metrics_by_user: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # System metrics
        self.system_metrics: deque = deque(maxlen=1000)
        
        # Real-time counters
        self.counters = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'active_sessions': 0
        }
        
        # Performance tracking
        self.response_times: deque = deque(maxlen=1000)
        self.error_counts: Dict[str, int] = defaultdict(int)
        
        # Start background metrics collection
        self._start_background_collection()
        
        logger.info("Metrics collector initialized")
    
    async def record_query_metrics(
        self,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,
        processing_time_ms: int = 0,
        confidence_score: float = 0.0,
        citation_count: int = 0,
        chunks_retrieved: int = 0,
        search_strategy: str = "unknown",
        mode: str = "qa",
        token_usage: Optional[Dict[str, int]] = None,
        error: Optional[str] = None
    ):
        """Record metrics for a query"""
        try:
            metrics = QueryMetrics(
                query_id=query_id or f"query_{int(time.time() * 1000)}",
                user_id=user_id or "anonymous",
                processing_time_ms=processing_time_ms,
                confidence_score=confidence_score,
                citation_count=citation_count,
                chunks_retrieved=chunks_retrieved,
                search_strategy=search_strategy,
                mode=mode,
                token_usage=token_usage,
                error=error
            )
            
            with self._lock:
                self.query_metrics.append(metrics)
                if user_id:
                    self.query_metrics_by_user[user_id].append(metrics)
                
                # Update counters
                self.counters['total_queries'] += 1
                if error:
                    self.counters['failed_queries'] += 1
                    self.error_counts[error] += 1
                else:
                    self.counters['successful_queries'] += 1
                
                # Track response times
                self.response_times.append(processing_time_ms)
            
            logger.debug("Query metrics recorded", query_id=query_id, processing_time_ms=processing_time_ms)
            
        except Exception as e:
            logger.error("Failed to record query metrics", error=str(e))
    
    def record_cache_hit(self):
        """Record cache hit"""
        with self._lock:
            self.counters['cache_hits'] += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        with self._lock:
            self.counters['cache_misses'] += 1
    
    def increment_active_sessions(self):
        """Increment active session count"""
        with self._lock:
            self.counters['active_sessions'] += 1
    
    def decrement_active_sessions(self):
        """Decrement active session count"""
        with self._lock:
            self.counters['active_sessions'] = max(0, self.counters['active_sessions'] - 1)
    
    def get_query_statistics(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get query statistics for the specified time window"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            
            with self._lock:
                # Filter metrics by time window
                recent_metrics = [
                    m for m in self.query_metrics 
                    if m.timestamp >= cutoff_time
                ]
                
                if not recent_metrics:
                    return {
                        'total_queries': 0,
                        'avg_response_time_ms': 0,
                        'success_rate': 0,
                        'avg_confidence_score': 0,
                        'queries_per_minute': 0
                    }
                
                # Calculate statistics
                total_queries = len(recent_metrics)
                successful_queries = len([m for m in recent_metrics if not m.error])
                
                response_times = [m.processing_time_ms for m in recent_metrics if not m.error]
                avg_response_time = sum(response_times) / len(response_times) if response_times else 0
                
                confidence_scores = [m.confidence_score for m in recent_metrics if not m.error]
                avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
                
                success_rate = successful_queries / total_queries if total_queries > 0 else 0
                queries_per_minute = total_queries / time_window_minutes
                
                # Mode distribution
                mode_counts = defaultdict(int)
                for m in recent_metrics:
                    mode_counts[m.mode] += 1
                
                # Search strategy distribution
                strategy_counts = defaultdict(int)
                for m in recent_metrics:
                    strategy_counts[m.search_strategy] += 1
                
                return {
                    'time_window_minutes': time_window_minutes,
                    'total_queries': total_queries,
                    'successful_queries': successful_queries,
                    'failed_queries': total_queries - successful_queries,
                    'success_rate': round(success_rate, 3),
                    'avg_response_time_ms': round(avg_response_time, 2),
                    'avg_confidence_score': round(avg_confidence, 3),
                    'queries_per_minute': round(queries_per_minute, 2),
                    'mode_distribution': dict(mode_counts),
                    'strategy_distribution': dict(strategy_counts),
                    'p95_response_time_ms': self._calculate_percentile(response_times, 95),
                    'p99_response_time_ms': self._calculate_percentile(response_times, 99)
                }
                
        except Exception as e:
            logger.error("Failed to get query statistics", error=str(e))
            return {}
    
    def get_user_statistics(self, user_id: str, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get statistics for a specific user"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            
            with self._lock:
                user_metrics = self.query_metrics_by_user.get(user_id, deque())
                recent_metrics = [
                    m for m in user_metrics 
                    if m.timestamp >= cutoff_time
                ]
                
                if not recent_metrics:
                    return {
                        'user_id': user_id,
                        'total_queries': 0,
                        'avg_response_time_ms': 0,
                        'avg_confidence_score': 0
                    }
                
                total_queries = len(recent_metrics)
                response_times = [m.processing_time_ms for m in recent_metrics if not m.error]
                confidence_scores = [m.confidence_score for m in recent_metrics if not m.error]
                
                return {
                    'user_id': user_id,
                    'time_window_minutes': time_window_minutes,
                    'total_queries': total_queries,
                    'successful_queries': len([m for m in recent_metrics if not m.error]),
                    'avg_response_time_ms': round(sum(response_times) / len(response_times), 2) if response_times else 0,
                    'avg_confidence_score': round(sum(confidence_scores) / len(confidence_scores), 3) if confidence_scores else 0,
                    'queries_per_minute': round(total_queries / time_window_minutes, 2)
                }
                
        except Exception as e:
            logger.error("Failed to get user statistics", user_id=user_id, error=str(e))
            return {'user_id': user_id, 'error': str(e)}
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health metrics"""
        try:
            with self._lock:
                total_queries = self.counters['total_queries']
                successful_queries = self.counters['successful_queries']
                failed_queries = self.counters['failed_queries']
                cache_hits = self.counters['cache_hits']
                cache_misses = self.counters['cache_misses']
                
                success_rate = successful_queries / total_queries if total_queries > 0 else 1.0
                error_rate = failed_queries / total_queries if total_queries > 0 else 0.0
                cache_hit_rate = cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0.0
                
                # Recent response time statistics
                recent_response_times = list(self.response_times)[-100:]  # Last 100 queries
                avg_response_time = sum(recent_response_times) / len(recent_response_times) if recent_response_times else 0
                
                return {
                    'status': 'healthy' if success_rate > 0.95 and avg_response_time < 5000 else 'degraded',
                    'total_queries': total_queries,
                    'success_rate': round(success_rate, 3),
                    'error_rate': round(error_rate, 3),
                    'cache_hit_rate': round(cache_hit_rate, 3),
                    'avg_response_time_ms': round(avg_response_time, 2),
                    'active_sessions': self.counters['active_sessions'],
                    'top_errors': dict(sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Failed to get system health", error=str(e))
            return {'status': 'error', 'error': str(e)}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics"""
        try:
            with self._lock:
                response_times = list(self.response_times)
                
                if not response_times:
                    return {'error': 'No performance data available'}
                
                return {
                    'response_time_stats': {
                        'min_ms': min(response_times),
                        'max_ms': max(response_times),
                        'avg_ms': round(sum(response_times) / len(response_times), 2),
                        'median_ms': self._calculate_percentile(response_times, 50),
                        'p95_ms': self._calculate_percentile(response_times, 95),
                        'p99_ms': self._calculate_percentile(response_times, 99)
                    },
                    'query_volume': {
                        'total_queries': self.counters['total_queries'],
                        'successful_queries': self.counters['successful_queries'],
                        'failed_queries': self.counters['failed_queries']
                    },
                    'cache_performance': {
                        'cache_hits': self.counters['cache_hits'],
                        'cache_misses': self.counters['cache_misses'],
                        'hit_rate': round(
                            self.counters['cache_hits'] / (self.counters['cache_hits'] + self.counters['cache_misses']),
                            3
                        ) if (self.counters['cache_hits'] + self.counters['cache_misses']) > 0 else 0.0
                    },
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Failed to get performance metrics", error=str(e))
            return {'error': str(e)}
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100.0) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
    
    def _start_background_collection(self):
        """Start background metrics collection"""
        def collect_system_metrics():
            """Collect system-wide metrics periodically"""
            try:
                import psutil
                import os
                
                while True:
                    try:
                        # Get system metrics
                        process = psutil.Process(os.getpid())
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        cpu_percent = process.cpu_percent()
                        
                        # Calculate recent query rate
                        recent_queries = len([
                            m for m in self.query_metrics 
                            if m.timestamp >= datetime.utcnow() - timedelta(minutes=1)
                        ])
                        
                        # Calculate error rate
                        recent_errors = len([
                            m for m in self.query_metrics 
                            if m.timestamp >= datetime.utcnow() - timedelta(minutes=5) and m.error
                        ])
                        recent_total = len([
                            m for m in self.query_metrics 
                            if m.timestamp >= datetime.utcnow() - timedelta(minutes=5)
                        ])
                        error_rate = recent_errors / recent_total if recent_total > 0 else 0.0
                        
                        # Calculate cache hit rate
                        cache_total = self.counters['cache_hits'] + self.counters['cache_misses']
                        cache_hit_rate = self.counters['cache_hits'] / cache_total if cache_total > 0 else 0.0
                        
                        # Calculate average response time
                        recent_response_times = [
                            m.processing_time_ms for m in self.query_metrics 
                            if m.timestamp >= datetime.utcnow() - timedelta(minutes=5) and not m.error
                        ]
                        avg_response_time = sum(recent_response_times) / len(recent_response_times) if recent_response_times else 0
                        
                        system_metrics = SystemMetrics(
                            timestamp=datetime.utcnow(),
                            active_users=len(self.query_metrics_by_user),
                            queries_per_minute=recent_queries,
                            avg_response_time_ms=avg_response_time,
                            error_rate=error_rate,
                            cache_hit_rate=cache_hit_rate,
                            memory_usage_mb=memory_mb,
                            cpu_usage_percent=cpu_percent
                        )
                        
                        with self._lock:
                            self.system_metrics.append(system_metrics)
                        
                        time.sleep(60)  # Collect every minute
                        
                    except Exception as e:
                        logger.error("Error collecting system metrics", error=str(e))
                        time.sleep(60)
                        
            except ImportError:
                logger.warning("psutil not available, system metrics collection disabled")
            except Exception as e:
                logger.error("Failed to start system metrics collection", error=str(e))
        
        # Start background thread
        import threading
        metrics_thread = threading.Thread(target=collect_system_metrics, daemon=True)
        metrics_thread.start()
    
    def export_metrics_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        try:
            with self._lock:
                metrics_lines = []
                
                # Query metrics
                metrics_lines.append(f"# HELP legal_ai_queries_total Total number of queries processed")
                metrics_lines.append(f"# TYPE legal_ai_queries_total counter")
                metrics_lines.append(f"legal_ai_queries_total {self.counters['total_queries']}")
                
                metrics_lines.append(f"# HELP legal_ai_queries_successful_total Total number of successful queries")
                metrics_lines.append(f"# TYPE legal_ai_queries_successful_total counter")
                metrics_lines.append(f"legal_ai_queries_successful_total {self.counters['successful_queries']}")
                
                metrics_lines.append(f"# HELP legal_ai_queries_failed_total Total number of failed queries")
                metrics_lines.append(f"# TYPE legal_ai_queries_failed_total counter")
                metrics_lines.append(f"legal_ai_queries_failed_total {self.counters['failed_queries']}")
                
                # Cache metrics
                metrics_lines.append(f"# HELP legal_ai_cache_hits_total Total number of cache hits")
                metrics_lines.append(f"# TYPE legal_ai_cache_hits_total counter")
                metrics_lines.append(f"legal_ai_cache_hits_total {self.counters['cache_hits']}")
                
                metrics_lines.append(f"# HELP legal_ai_cache_misses_total Total number of cache misses")
                metrics_lines.append(f"# TYPE legal_ai_cache_misses_total counter")
                metrics_lines.append(f"legal_ai_cache_misses_total {self.counters['cache_misses']}")
                
                # Active sessions
                metrics_lines.append(f"# HELP legal_ai_active_sessions Current number of active sessions")
                metrics_lines.append(f"# TYPE legal_ai_active_sessions gauge")
                metrics_lines.append(f"legal_ai_active_sessions {self.counters['active_sessions']}")
                
                # Response time metrics
                if self.response_times:
                    response_times = list(self.response_times)
                    avg_response_time = sum(response_times) / len(response_times)
                    p95_response_time = self._calculate_percentile(response_times, 95)
                    
                    metrics_lines.append(f"# HELP legal_ai_response_time_ms_avg Average response time in milliseconds")
                    metrics_lines.append(f"# TYPE legal_ai_response_time_ms_avg gauge")
                    metrics_lines.append(f"legal_ai_response_time_ms_avg {avg_response_time:.2f}")
                    
                    metrics_lines.append(f"# HELP legal_ai_response_time_ms_p95 95th percentile response time in milliseconds")
                    metrics_lines.append(f"# TYPE legal_ai_response_time_ms_p95 gauge")
                    metrics_lines.append(f"legal_ai_response_time_ms_p95 {p95_response_time:.2f}")
                
                return "\n".join(metrics_lines)
                
        except Exception as e:
            logger.error("Failed to export Prometheus metrics", error=str(e))
            return f"# Error exporting metrics: {str(e)}"
    
    def reset_counters(self):
        """Reset all counters (for testing)"""
        with self._lock:
            self.counters = {
                'total_queries': 0,
                'successful_queries': 0,
                'failed_queries': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'active_sessions': 0
            }
            self.query_metrics.clear()
            self.query_metrics_by_user.clear()
            self.system_metrics.clear()
            self.response_times.clear()
            self.error_counts.clear()

# Global metrics collector instance
metrics_collector = MetricsCollector()

# Convenience functions
async def record_query_metrics(**kwargs):
    """Record query metrics (convenience function)"""
    await metrics_collector.record_query_metrics(**kwargs)

def record_cache_hit():
    """Record cache hit (convenience function)"""
    metrics_collector.record_cache_hit()

def record_cache_miss():
    """Record cache miss (convenience function)"""
    metrics_collector.record_cache_miss()

def get_system_health():
    """Get system health (convenience function)"""
    return metrics_collector.get_system_health()