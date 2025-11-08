"""
Monitoring and telemetry using Azure Application Insights
"""
import structlog
from typing import Dict, Any
import time

from config import settings

logger = structlog.get_logger()

# Metrics storage (in production, send to Azure Application Insights)
metrics_store = {
    "queries_total": 0,
    "queries_success": 0,
    "queries_failed": 0,
    "avg_response_time": 0.0,
    "total_response_time": 0.0
}

def setup_monitoring():
    """Initialize monitoring and telemetry"""
    try:
        if settings.AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING:
            # In production, initialize Azure Application Insights SDK
            logger.info("Monitoring initialized")
        else:
            logger.warning("Application Insights not configured, using local metrics")
    except Exception as e:
        logger.error("Monitoring setup failed", error=str(e))

def track_query_metrics(
    user_id: str,
    response_time: float,
    success: bool
):
    """Track query metrics"""
    try:
        metrics_store["queries_total"] += 1
        
        if success:
            metrics_store["queries_success"] += 1
        else:
            metrics_store["queries_failed"] += 1
        
        metrics_store["total_response_time"] += response_time
        metrics_store["avg_response_time"] = (
            metrics_store["total_response_time"] / metrics_store["queries_total"]
        )
        
        logger.info(
            "Query metrics tracked",
            user_id=user_id,
            response_time=response_time,
            success=success
        )
        
    except Exception as e:
        logger.error("Failed to track metrics", error=str(e))

def get_metrics() -> Dict[str, Any]:
    """Get current metrics"""
    return metrics_store.copy()
