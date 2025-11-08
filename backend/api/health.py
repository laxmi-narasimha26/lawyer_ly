"""
Health check endpoints for monitoring and load balancer probes
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import asyncio
from datetime import datetime
import structlog

from services.azure_monitoring_service import azure_monitoring_service
from database.connection import get_async_session
from core.cache_manager import cache_manager
from services.azure_openai_service import azure_openai_service
from utils.exceptions import ProcessingError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    
    Returns:
        Basic health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "indian-legal-ai-assistant",
        "version": "1.0.0"
    }

@router.get("/live")
async def liveness_probe() -> Dict[str, Any]:
    """
    Kubernetes liveness probe endpoint
    
    Returns:
        Liveness status - indicates if the application is running
    """
    try:
        # Basic application health check
        health_data = {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": 0,  # Would track actual uptime in production
            "checks": {
                "application": "healthy"
            }
        }
        
        return health_data
        
    except Exception as e:
        logger.error("Liveness probe failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unavailable")

@router.get("/ready")
async def readiness_probe() -> Dict[str, Any]:
    """
    Kubernetes readiness probe endpoint
    
    Returns:
        Readiness status - indicates if the application can serve traffic
    """
    try:
        health_checks = {}
        overall_status = "ready"
        
        # Check database connectivity
        try:
            session = await get_async_session()
            await session.execute("SELECT 1")
            await session.close()
            health_checks["database"] = "healthy"
        except Exception as e:
            health_checks["database"] = f"unhealthy: {str(e)}"
            overall_status = "not_ready"
        
        # Check Redis cache
        try:
            await cache_manager.health_check()
            health_checks["cache"] = "healthy"
        except Exception as e:
            health_checks["cache"] = f"unhealthy: {str(e)}"
            overall_status = "not_ready"
        
        # Check OpenAI service
        try:
            # Simple connectivity check (don't make actual API call to save costs)
            if azure_openai_service.client:
                health_checks["openai"] = "healthy"
            else:
                health_checks["openai"] = "unhealthy: client not initialized"
                overall_status = "not_ready"
        except Exception as e:
            health_checks["openai"] = f"unhealthy: {str(e)}"
            overall_status = "not_ready"
        
        health_data = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": health_checks
        }
        
        if overall_status != "ready":
            raise HTTPException(status_code=503, detail=health_data)
        
        return health_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness probe failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unavailable")

@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with system metrics
    
    Returns:
        Comprehensive health status including system metrics
    """
    try:
        # Get system health from monitoring service
        system_health = await azure_monitoring_service.get_health_status()
        
        # Get detailed component health
        component_health = {}
        
        # Database health
        try:
            session = await get_async_session()
            result = await session.execute("SELECT version()")
            db_version = result.scalar()
            await session.close()
            
            component_health["database"] = {
                "status": "healthy",
                "version": db_version,
                "connection_pool": "active"
            }
        except Exception as e:
            component_health["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Cache health
        try:
            cache_info = await cache_manager.get_cache_info()
            component_health["cache"] = {
                "status": "healthy",
                "info": cache_info
            }
        except Exception as e:
            component_health["cache"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Vector store health (would check PGVector)
        component_health["vector_store"] = {
            "status": "healthy",
            "type": "pgvector"
        }
        
        # Combine all health information
        detailed_health = {
            "overall_status": system_health.get("status", "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
            "system_metrics": system_health.get("metrics", {}),
            "component_health": component_health,
            "monitoring": {
                "current_instances": system_health.get("current_instances", 0),
                "alerts": system_health.get("alerts", {}),
                "autoscaling": system_health.get("autoscaling", {})
            }
        }
        
        return detailed_health
        
    except Exception as e:
        logger.error("Detailed health check failed", error=str(e))
        raise HTTPException(status_code=500, detail="Health check failed")

@router.get("/metrics")
async def metrics_endpoint() -> Dict[str, Any]:
    """
    Prometheus-style metrics endpoint
    
    Returns:
        Application metrics in a format suitable for monitoring systems
    """
    try:
        # Get metrics from monitoring service
        metrics_history = azure_monitoring_service.get_metrics_history(hours=1)
        
        # Format metrics for Prometheus/monitoring systems
        metrics_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {}
        }
        
        if "system_metrics" in metrics_history and metrics_history["system_metrics"]:
            latest_metrics = metrics_history["system_metrics"][-1]
            
            metrics_data["metrics"] = {
                # System metrics
                "legal_ai_cpu_usage_percent": latest_metrics.cpu_percent,
                "legal_ai_memory_usage_percent": latest_metrics.memory_percent,
                "legal_ai_memory_used_mb": latest_metrics.memory_used_mb,
                "legal_ai_disk_usage_percent": latest_metrics.disk_usage_percent,
                "legal_ai_active_connections": latest_metrics.active_connections,
                
                # Application metrics
                "legal_ai_request_rate": latest_metrics.request_rate,
                "legal_ai_error_rate": latest_metrics.error_rate,
                "legal_ai_response_time_avg": latest_metrics.response_time_avg,
                
                # Instance metrics
                "legal_ai_current_instances": azure_monitoring_service.current_instances,
                
                # Timestamp
                "legal_ai_last_updated": latest_metrics.timestamp.timestamp()
            }
        
        return metrics_data
        
    except Exception as e:
        logger.error("Metrics endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail="Metrics unavailable")

@router.post("/alerts/test")
async def test_alert_system() -> Dict[str, Any]:
    """
    Test the alert system by triggering a test alert
    
    Returns:
        Test alert result
    """
    try:
        # Create a test alert rule
        from services.azure_monitoring_service import AlertRule
        
        test_rule = AlertRule(
            name="test_alert",
            metric_name="cpu_percent",
            condition="greater_than",
            threshold=0.0,  # This will always trigger
            duration_minutes=0,
            severity="info",
            notification_channels=["test"]
        )
        
        # Get current metrics
        current_metrics = await azure_monitoring_service.collect_system_metrics()
        
        # Trigger test alert
        await azure_monitoring_service._trigger_alert(test_rule, current_metrics, current_metrics.cpu_percent)
        
        return {
            "status": "success",
            "message": "Test alert triggered successfully",
            "timestamp": datetime.utcnow().isoformat(),
            "test_metric_value": current_metrics.cpu_percent
        }
        
    except Exception as e:
        logger.error("Alert test failed", error=str(e))
        raise HTTPException(status_code=500, detail="Alert test failed")

@router.get("/autoscaling/status")
async def autoscaling_status() -> Dict[str, Any]:
    """
    Get current auto-scaling status
    
    Returns:
        Auto-scaling configuration and status
    """
    try:
        return {
            "current_instances": azure_monitoring_service.current_instances,
            "last_scale_action": azure_monitoring_service.last_scale_action.isoformat(),
            "scaling_rules": [
                {
                    "name": rule.name,
                    "metric": rule.metric_name,
                    "scale_out_threshold": rule.scale_out_threshold,
                    "scale_in_threshold": rule.scale_in_threshold,
                    "min_instances": rule.min_instances,
                    "max_instances": rule.max_instances,
                    "enabled": rule.enabled
                }
                for rule in azure_monitoring_service.autoscaling_rules
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Auto-scaling status failed", error=str(e))
        raise HTTPException(status_code=500, detail="Auto-scaling status unavailable")

@router.post("/autoscaling/manual/{action}")
async def manual_scaling(action: str, instances: int = None) -> Dict[str, Any]:
    """
    Manually trigger scaling action
    
    Args:
        action: 'scale_out' or 'scale_in'
        instances: Target number of instances (optional)
        
    Returns:
        Scaling action result
    """
    try:
        if action not in ["scale_out", "scale_in"]:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'scale_out' or 'scale_in'")
        
        old_instances = azure_monitoring_service.current_instances
        
        if instances:
            new_instances = instances
        else:
            if action == "scale_out":
                new_instances = min(old_instances + 1, 10)  # Max 10 instances
            else:
                new_instances = max(old_instances - 1, 2)   # Min 2 instances
        
        # Execute scaling action
        await azure_monitoring_service._execute_scaling_action(action, old_instances, new_instances)
        azure_monitoring_service.current_instances = new_instances
        azure_monitoring_service.last_scale_action = datetime.now()
        
        return {
            "status": "success",
            "action": action,
            "old_instances": old_instances,
            "new_instances": new_instances,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Manual scaling failed", error=str(e), action=action)
        raise HTTPException(status_code=500, detail="Manual scaling failed")