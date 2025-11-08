"""
Performance Optimization Service for Indian Legal AI Assistant
Provides comprehensive performance monitoring and optimization capabilities
"""
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.connection import db_manager
from services.azure_database_service import azure_database_service
from services.azure_redis_service import azure_redis_service
from core.cache_manager import cache_manager
from utils.monitoring import metrics_collector

logger = structlog.get_logger(__name__)

class PerformanceOptimizationService:
    """
    Comprehensive performance optimization service
    
    Features:
    - Database performance monitoring and tuning
    - Cache optimization and analysis
    - Query performance analysis
    - Resource utilization monitoring
    - Automated optimization recommendations
    """
    
    def __init__(self):
        self.optimization_history = []
        self.performance_thresholds = {
            'query_time_ms': 2000,
            'cache_hit_rate': 0.7,
            'db_connection_utilization': 0.8,
            'memory_usage_percent': 85
        }
        
        logger.info("Performance optimization service initialized")
    
    async def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run comprehensive performance analysis across all components"""
        analysis_start = time.time()
        
        try:
            # Parallel analysis of different components
            tasks = [
                self._analyze_database_performance(),
                self._analyze_cache_performance(),
                self._analyze_vector_search_performance(),
                self._analyze_system_resources()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results
            analysis_result = {
                'database_analysis': results[0] if not isinstance(results[0], Exception) else {'error': str(results[0])},
                'cache_analysis': results[1] if not isinstance(results[1], Exception) else {'error': str(results[1])},
                'vector_search_analysis': results[2] if not isinstance(results[2], Exception) else {'error': str(results[2])},
                'system_analysis': results[3] if not isinstance(results[3], Exception) else {'error': str(results[3])},
                'analysis_duration_ms': int((time.time() - analysis_start) * 1000),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Generate overall recommendations
            analysis_result['overall_recommendations'] = self._generate_overall_recommendations(analysis_result)
            
            # Store analysis history
            self.optimization_history.append(analysis_result)
            
            # Keep only last 10 analyses
            if len(self.optimization_history) > 10:
                self.optimization_history = self.optimization_history[-10:]
            
            logger.info("Comprehensive performance analysis completed", 
                       duration_ms=analysis_result['analysis_duration_ms'])
            
            return analysis_result
            
        except Exception as e:
            logger.error("Comprehensive performance analysis failed", error=str(e), exc_info=True)
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _analyze_database_performance(self) -> Dict[str, Any]:
        """Analyze database performance metrics"""
        try:
            # Get database statistics
            db_stats = await azure_database_service.get_database_statistics()
            
            # Analyze connection pool
            pool_analysis = await db_manager.optimize_connection_pool()
            
            # Analyze query performance
            query_analysis = await db_manager.analyze_query_performance()
            
            # Vector search specific analysis
            vector_analysis = await azure_database_service.optimize_vector_indexes()
            
            # Calculate performance scores
            performance_score = self._calculate_database_performance_score(
                db_stats, pool_analysis, query_analysis
            )
            
            return {
                'database_statistics': db_stats,
                'connection_pool_analysis': pool_analysis,
                'query_performance': query_analysis,
                'vector_optimization': vector_analysis,
                'performance_score': performance_score,
                'status': 'healthy' if performance_score > 0.7 else 'needs_attention'
            }
            
        except Exception as e:
            logger.error("Database performance analysis failed", error=str(e))
            return {'error': str(e)}
    
    async def _analyze_cache_performance(self) -> Dict[str, Any]:
        """Analyze cache performance and efficiency"""
        try:
            # Get cache manager metrics
            cache_metrics = await cache_manager.get_cache_performance_metrics()
            
            # Get Redis service metrics
            redis_health = await azure_redis_service.health_check()
            redis_info = await azure_redis_service.get_cache_info()
            
            # Calculate cache efficiency score
            hit_rate = cache_metrics.get('hit_rate', 0)
            memory_efficiency = cache_metrics.get('memory_efficiency', 0)
            
            efficiency_score = (hit_rate * 0.6 + memory_efficiency * 0.4)
            
            # Generate cache optimization recommendations
            cache_recommendations = []
            
            if hit_rate < self.performance_thresholds['cache_hit_rate']:
                cache_recommendations.append("Low cache hit rate - consider increasing TTL or preloading frequent queries")
            
            if redis_health['status'] != 'healthy':
                cache_recommendations.append("Redis health issues detected - check connection and configuration")
            
            memory_utilization = cache_metrics.get('memory_cache_utilization', 0)
            if memory_utilization > 0.9:
                cache_recommendations.append("Memory cache near capacity - consider increasing max_memory_items")
            
            return {
                'cache_manager_metrics': cache_metrics,
                'redis_health': redis_health,
                'redis_info': redis_info,
                'efficiency_score': efficiency_score,
                'recommendations': cache_recommendations,
                'status': 'healthy' if efficiency_score > 0.7 else 'needs_optimization'
            }
            
        except Exception as e:
            logger.error("Cache performance analysis failed", error=str(e))
            return {'error': str(e)}
    
    async def _analyze_vector_search_performance(self) -> Dict[str, Any]:
        """Analyze vector search performance specifically"""
        try:
            # Get vector search optimization analysis
            vector_optimization = await azure_database_service.optimize_vector_search_performance()
            
            # Get vector search tuning recommendations
            tuning_analysis = await azure_database_service.tune_vector_search_parameters()
            
            # Analyze embedding cache performance
            embedding_cache_stats = {}
            try:
                from core.vector_search import VectorSearchEngine
                vector_engine = VectorSearchEngine()
                embedding_cache_stats = vector_engine.get_cache_stats()
            except Exception as e:
                logger.warning("Failed to get embedding cache stats", error=str(e))
            
            # Calculate vector search performance score
            vector_queries = vector_optimization.get('vector_query_patterns', [])
            avg_query_time = sum(q.get('mean_exec_time', 0) for q in vector_queries) / max(len(vector_queries), 1)
            
            performance_score = 1.0
            if avg_query_time > 2000:  # > 2 seconds
                performance_score = 0.3
            elif avg_query_time > 1000:  # > 1 second
                performance_score = 0.6
            elif avg_query_time > 500:  # > 0.5 seconds
                performance_score = 0.8
            
            return {
                'vector_optimization_analysis': vector_optimization,
                'parameter_tuning_analysis': tuning_analysis,
                'embedding_cache_stats': embedding_cache_stats,
                'average_query_time_ms': avg_query_time,
                'performance_score': performance_score,
                'status': 'optimal' if performance_score > 0.8 else 'needs_tuning'
            }
            
        except Exception as e:
            logger.error("Vector search performance analysis failed", error=str(e))
            return {'error': str(e)}
    
    async def _analyze_system_resources(self) -> Dict[str, Any]:
        """Analyze system resource utilization"""
        try:
            # This would typically integrate with system monitoring tools
            # For now, we'll provide a basic analysis structure
            
            resource_analysis = {
                'cpu_utilization': 'Not available - integrate with Azure Monitor',
                'memory_utilization': 'Not available - integrate with Azure Monitor',
                'disk_io': 'Not available - integrate with Azure Monitor',
                'network_io': 'Not available - integrate with Azure Monitor',
                'recommendations': [
                    "Integrate with Azure Monitor for detailed resource metrics",
                    "Set up Application Insights for application-level monitoring",
                    "Configure alerts for resource threshold breaches"
                ]
            }
            
            return resource_analysis
            
        except Exception as e:
            logger.error("System resource analysis failed", error=str(e))
            return {'error': str(e)}
    
    def _calculate_database_performance_score(
        self,
        db_stats: Dict[str, Any],
        pool_analysis: Dict[str, Any],
        query_analysis: Dict[str, Any]
    ) -> float:
        """Calculate overall database performance score"""
        score = 1.0
        
        # Check connection pool utilization
        utilization = pool_analysis.get('utilization', 0)
        if utilization > 0.9:
            score -= 0.2
        elif utilization > 0.8:
            score -= 0.1
        
        # Check for slow queries
        slow_queries = query_analysis.get('slow_queries', [])
        if slow_queries:
            avg_slow_time = sum(q.get('mean_exec_time', 0) for q in slow_queries) / len(slow_queries)
            if avg_slow_time > 5000:  # > 5 seconds
                score -= 0.3
            elif avg_slow_time > 2000:  # > 2 seconds
                score -= 0.2
        
        # Check index usage
        index_stats = query_analysis.get('index_statistics', [])
        unused_indexes = [idx for idx in index_stats if idx.get('idx_scan', 0) == 0]
        if len(unused_indexes) > 3:
            score -= 0.1
        
        return max(0.0, score)
    
    def _generate_overall_recommendations(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Generate overall optimization recommendations"""
        recommendations = []
        
        # Database recommendations
        db_analysis = analysis_result.get('database_analysis', {})
        if db_analysis.get('performance_score', 1.0) < 0.7:
            recommendations.append("Database performance needs attention - review slow queries and connection pool")
        
        # Cache recommendations
        cache_analysis = analysis_result.get('cache_analysis', {})
        if cache_analysis.get('efficiency_score', 1.0) < 0.7:
            recommendations.append("Cache efficiency is low - optimize hit rates and memory usage")
        
        # Vector search recommendations
        vector_analysis = analysis_result.get('vector_search_analysis', {})
        if vector_analysis.get('performance_score', 1.0) < 0.7:
            recommendations.append("Vector search performance needs optimization - tune index parameters")
        
        # System recommendations
        recommendations.append("Set up comprehensive monitoring with Azure Monitor and Application Insights")
        recommendations.append("Implement automated performance alerts and notifications")
        
        return recommendations
    
    async def apply_automatic_optimizations(self) -> Dict[str, Any]:
        """Apply safe automatic optimizations"""
        optimization_start = time.time()
        applied_optimizations = []
        
        try:
            # Cache optimizations
            await cache_manager.optimize_cache_performance()
            applied_optimizations.append("Cache performance optimization")
            
            # Database statistics update
            async with db_manager.get_session() as session:
                await session.execute(text("ANALYZE"))
            applied_optimizations.append("Database statistics updated")
            
            # Vector index optimization
            vector_optimizations = await azure_database_service.optimize_vector_indexes()
            if vector_optimizations:
                applied_optimizations.extend(vector_optimizations)
            
            # Redis cleanup
            await azure_redis_service.cleanup_expired_keys()
            applied_optimizations.append("Redis expired keys cleanup")
            
            optimization_duration = int((time.time() - optimization_start) * 1000)
            
            result = {
                'applied_optimizations': applied_optimizations,
                'optimization_count': len(applied_optimizations),
                'duration_ms': optimization_duration,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'completed'
            }
            
            logger.info("Automatic optimizations applied", 
                       count=len(applied_optimizations),
                       duration_ms=optimization_duration)
            
            return result
            
        except Exception as e:
            logger.error("Automatic optimization failed", error=str(e), exc_info=True)
            return {
                'error': str(e),
                'applied_optimizations': applied_optimizations,
                'status': 'partial_failure',
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def schedule_performance_monitoring(self, interval_minutes: int = 60):
        """Schedule regular performance monitoring"""
        logger.info("Starting scheduled performance monitoring", interval_minutes=interval_minutes)
        
        while True:
            try:
                # Run analysis
                analysis = await self.run_comprehensive_analysis()
                
                # Check if any critical issues need immediate attention
                critical_issues = self._identify_critical_issues(analysis)
                
                if critical_issues:
                    logger.warning("Critical performance issues detected", issues=critical_issues)
                    # In production, this would trigger alerts
                
                # Apply automatic optimizations if needed
                if self._should_apply_auto_optimizations(analysis):
                    await self.apply_automatic_optimizations()
                
                # Wait for next interval
                await asyncio.sleep(interval_minutes * 60)
                
            except Exception as e:
                logger.error("Scheduled performance monitoring failed", error=str(e))
                await asyncio.sleep(300)  # Wait 5 minutes before retry
    
    def _identify_critical_issues(self, analysis: Dict[str, Any]) -> List[str]:
        """Identify critical performance issues that need immediate attention"""
        critical_issues = []
        
        # Check database performance
        db_analysis = analysis.get('database_analysis', {})
        if db_analysis.get('performance_score', 1.0) < 0.5:
            critical_issues.append("Critical database performance degradation")
        
        # Check cache performance
        cache_analysis = analysis.get('cache_analysis', {})
        if cache_analysis.get('status') != 'healthy':
            critical_issues.append("Cache system health issues")
        
        # Check vector search performance
        vector_analysis = analysis.get('vector_search_analysis', {})
        avg_query_time = vector_analysis.get('average_query_time_ms', 0)
        if avg_query_time > 5000:  # > 5 seconds
            critical_issues.append("Vector search queries extremely slow")
        
        return critical_issues
    
    def _should_apply_auto_optimizations(self, analysis: Dict[str, Any]) -> bool:
        """Determine if automatic optimizations should be applied"""
        # Apply optimizations if any component has low performance score
        db_score = analysis.get('database_analysis', {}).get('performance_score', 1.0)
        cache_score = analysis.get('cache_analysis', {}).get('efficiency_score', 1.0)
        vector_score = analysis.get('vector_search_analysis', {}).get('performance_score', 1.0)
        
        return any(score < 0.8 for score in [db_score, cache_score, vector_score])
    
    def get_optimization_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent optimization history"""
        return self.optimization_history[-limit:] if self.optimization_history else []
    
    async def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        try:
            # Run fresh analysis
            current_analysis = await self.run_comprehensive_analysis()
            
            # Get historical data
            history = self.get_optimization_history()
            
            # Calculate trends if we have historical data
            trends = {}
            if len(history) >= 2:
                trends = self._calculate_performance_trends(history)
            
            report = {
                'current_analysis': current_analysis,
                'historical_data': history,
                'performance_trends': trends,
                'summary': {
                    'overall_health': self._calculate_overall_health(current_analysis),
                    'critical_issues_count': len(self._identify_critical_issues(current_analysis)),
                    'recommendations_count': len(current_analysis.get('overall_recommendations', [])),
                    'last_optimization': history[-1]['timestamp'] if history else None
                },
                'report_generated': datetime.utcnow().isoformat()
            }
            
            return report
            
        except Exception as e:
            logger.error("Performance report generation failed", error=str(e))
            return {
                'error': str(e),
                'report_generated': datetime.utcnow().isoformat()
            }
    
    def _calculate_performance_trends(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate performance trends from historical data"""
        if len(history) < 2:
            return {}
        
        # Compare latest with previous
        latest = history[-1]
        previous = history[-2]
        
        trends = {}
        
        # Database performance trend
        latest_db_score = latest.get('database_analysis', {}).get('performance_score', 0)
        previous_db_score = previous.get('database_analysis', {}).get('performance_score', 0)
        trends['database_performance'] = 'improving' if latest_db_score > previous_db_score else 'declining'
        
        # Cache efficiency trend
        latest_cache_score = latest.get('cache_analysis', {}).get('efficiency_score', 0)
        previous_cache_score = previous.get('cache_analysis', {}).get('efficiency_score', 0)
        trends['cache_efficiency'] = 'improving' if latest_cache_score > previous_cache_score else 'declining'
        
        # Vector search performance trend
        latest_vector_score = latest.get('vector_search_analysis', {}).get('performance_score', 0)
        previous_vector_score = previous.get('vector_search_analysis', {}).get('performance_score', 0)
        trends['vector_search_performance'] = 'improving' if latest_vector_score > previous_vector_score else 'declining'
        
        return trends
    
    def _calculate_overall_health(self, analysis: Dict[str, Any]) -> str:
        """Calculate overall system health status"""
        db_score = analysis.get('database_analysis', {}).get('performance_score', 0)
        cache_score = analysis.get('cache_analysis', {}).get('efficiency_score', 0)
        vector_score = analysis.get('vector_search_analysis', {}).get('performance_score', 0)
        
        overall_score = (db_score + cache_score + vector_score) / 3
        
        if overall_score >= 0.9:
            return 'excellent'
        elif overall_score >= 0.8:
            return 'good'
        elif overall_score >= 0.6:
            return 'fair'
        else:
            return 'poor'

# Global service instance
performance_optimization_service = PerformanceOptimizationService()