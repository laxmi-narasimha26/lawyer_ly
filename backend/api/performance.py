"""
Performance monitoring and optimization API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
import structlog

from services.performance_optimization_service import performance_optimization_service
from api.auth import get_current_admin_user
from database.models import User

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/performance", tags=["performance"])

@router.get("/analysis")
async def get_performance_analysis(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get comprehensive performance analysis
    Requires admin privileges
    """
    try:
        analysis = await performance_optimization_service.run_comprehensive_analysis()
        return {
            "status": "success",
            "data": analysis
        }
    except Exception as e:
        logger.error("Performance analysis failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Performance analysis failed")

@router.post("/optimize")
async def apply_optimizations(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Apply automatic performance optimizations
    Requires admin privileges
    """
    try:
        # Run optimizations in background
        background_tasks.add_task(performance_optimization_service.apply_automatic_optimizations)
        
        return {
            "status": "success",
            "message": "Performance optimizations started in background"
        }
    except Exception as e:
        logger.error("Performance optimization failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Performance optimization failed")

@router.get("/report")
async def get_performance_report(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get comprehensive performance report with trends
    Requires admin privileges
    """
    try:
        report = await performance_optimization_service.generate_performance_report()
        return {
            "status": "success",
            "data": report
        }
    except Exception as e:
        logger.error("Performance report generation failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Performance report generation failed")

@router.get("/history")
async def get_optimization_history(
    limit: int = 10,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get performance optimization history
    Requires admin privileges
    """
    try:
        history = performance_optimization_service.get_optimization_history(limit=limit)
        return {
            "status": "success",
            "data": {
                "history": history,
                "count": len(history)
            }
        }
    except Exception as e:
        logger.error("Failed to get optimization history", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get optimization history")

@router.get("/cache/stats")
async def get_cache_statistics(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get detailed cache performance statistics
    Requires admin privileges
    """
    try:
        from core.cache_manager import cache_manager
        from services.azure_redis_service import azure_redis_service
        
        # Get cache manager stats
        cache_stats = await cache_manager.get_cache_performance_metrics()
        
        # Get Redis stats
        redis_stats = await azure_redis_service.get_cache_info()
        
        return {
            "status": "success",
            "data": {
                "cache_manager": cache_stats,
                "redis": redis_stats
            }
        }
    except Exception as e:
        logger.error("Failed to get cache statistics", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get cache statistics")

@router.post("/cache/optimize")
async def optimize_cache_performance(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Optimize cache performance
    Requires admin privileges
    """
    try:
        from core.cache_manager import cache_manager
        
        # Run cache optimization in background
        background_tasks.add_task(cache_manager.optimize_cache_performance)
        
        return {
            "status": "success",
            "message": "Cache optimization started in background"
        }
    except Exception as e:
        logger.error("Cache optimization failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Cache optimization failed")

@router.post("/cache/invalidate")
async def invalidate_cache(
    pattern: Optional[str] = None,
    domain: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Invalidate cache entries by pattern or domain
    Requires admin privileges
    """
    try:
        from core.cache_manager import cache_manager
        
        if domain:
            cleared_count = await cache_manager.invalidate_by_knowledge_base_update(domain)
            message = f"Invalidated {cleared_count} cache entries for domain: {domain}"
        elif pattern:
            cleared_count = await cache_manager.clear_pattern(pattern)
            message = f"Invalidated {cleared_count} cache entries matching pattern: {pattern}"
        else:
            raise HTTPException(status_code=400, detail="Either pattern or domain must be specified")
        
        return {
            "status": "success",
            "message": message,
            "cleared_count": cleared_count
        }
    except Exception as e:
        logger.error("Cache invalidation failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Cache invalidation failed")

@router.get("/database/stats")
async def get_database_statistics(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get detailed database performance statistics
    Requires admin privileges
    """
    try:
        from services.azure_database_service import azure_database_service
        from database.connection import db_manager
        
        # Get database statistics
        db_stats = await azure_database_service.get_database_statistics()
        
        # Get connection pool analysis
        pool_analysis = await db_manager.optimize_connection_pool()
        
        # Get query performance analysis
        query_analysis = await db_manager.analyze_query_performance()
        
        return {
            "status": "success",
            "data": {
                "database_statistics": db_stats,
                "connection_pool": pool_analysis,
                "query_performance": query_analysis
            }
        }
    except Exception as e:
        logger.error("Failed to get database statistics", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get database statistics")

@router.post("/database/optimize")
async def optimize_database_performance(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Optimize database performance
    Requires admin privileges
    """
    try:
        from services.azure_database_service import azure_database_service
        
        # Run database optimization in background
        background_tasks.add_task(azure_database_service.optimize_vector_indexes)
        
        return {
            "status": "success",
            "message": "Database optimization started in background"
        }
    except Exception as e:
        logger.error("Database optimization failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Database optimization failed")

@router.get("/vector-search/analysis")
async def get_vector_search_analysis(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get vector search performance analysis
    Requires admin privileges
    """
    try:
        from services.azure_database_service import azure_database_service
        
        # Get vector search optimization analysis
        optimization_analysis = await azure_database_service.optimize_vector_search_performance()
        
        # Get parameter tuning analysis
        tuning_analysis = await azure_database_service.tune_vector_search_parameters()
        
        return {
            "status": "success",
            "data": {
                "optimization_analysis": optimization_analysis,
                "tuning_analysis": tuning_analysis
            }
        }
    except Exception as e:
        logger.error("Vector search analysis failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Vector search analysis failed")

@router.post("/monitoring/start")
async def start_performance_monitoring(
    background_tasks: BackgroundTasks,
    interval_minutes: int = 60,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Start scheduled performance monitoring
    Requires admin privileges
    """
    try:
        # Start monitoring in background
        background_tasks.add_task(
            performance_optimization_service.schedule_performance_monitoring,
            interval_minutes
        )
        
        return {
            "status": "success",
            "message": f"Performance monitoring started with {interval_minutes} minute intervals"
        }
    except Exception as e:
        logger.error("Failed to start performance monitoring", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start performance monitoring")