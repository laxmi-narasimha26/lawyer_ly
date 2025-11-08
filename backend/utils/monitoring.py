"""
Monitoring and metrics collection utilities for the ingestion pipeline
"""
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import structlog
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import SystemMetrics, AuditLog
from database.connection import get_async_session

logger = structlog.get_logger(__name__)

@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    value: float
    dimensions: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.dimensions is None:
            self.dimensions = {}

@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric_name: str
    condition: str  # 'greater_than', 'less_than', 'equals'
    threshold: float
    duration_seconds: int = 300  # 5 minutes
    enabled: bool = True

class MetricsCollector:
    """
    Production-grade metrics collector for pipeline monitoring
    
    Features:
    - Real-time metric collection
    - Time-series data storage
    - Alert rule evaluation
    - Performance monitoring
    - Resource usage tracking
    """
    
    def __init__(self):
        self.metrics_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alert_rules: List[AlertRule] = []
        self.alert_states: Dict[str, Dict] = {}
        
        # Performance tracking
        self.operation_timers: Dict[str, float] = {}
        
        logger.info("Metrics collector initialized")
    
    def record_metric(
        self,
        name: str,
        value: float,
        dimensions: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Record a metric value
        
        Args:
            name: Metric name
            value: Metric value
            dimensions: Additional metric dimensions
            timestamp: Metric timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        metric_point = MetricPoint(
            timestamp=timestamp,
            value=value,
            dimensions=dimensions or {}
        )
        
        self.metrics_buffer[name].append(metric_point)
        
        # Evaluate alert rules
        asyncio.create_task(self._evaluate_alerts(name, metric_point))
    
    def start_timer(self, operation_name: str) -> str:
        """
        Start timing an operation
        
        Args:
            operation_name: Name of the operation
            
        Returns:
            Timer ID
        """
        timer_id = f"{operation_name}_{int(time.time() * 1000)}"
        self.operation_timers[timer_id] = time.time()
        return timer_id
    
    def end_timer(self, timer_id: str, dimensions: Optional[Dict[str, Any]] = None):
        """
        End timing an operation and record the duration
        
        Args:
            timer_id: Timer ID from start_timer
            dimensions: Additional dimensions for the metric
        """
        if timer_id in self.operation_timers:
            start_time = self.operation_timers.pop(timer_id)
            duration = time.time() - start_time
            
            # Extract operation name from timer ID
            operation_name = timer_id.rsplit('_', 1)[0]
            
            self.record_metric(
                f"{operation_name}_duration",
                duration,
                dimensions
            )
    
    def record_counter(
        self,
        name: str,
        increment: int = 1,
        dimensions: Optional[Dict[str, Any]] = None
    ):
        """
        Record a counter metric
        
        Args:
            name: Counter name
            increment: Increment value
            dimensions: Additional dimensions
        """
        # Get current value
        current_value = self.get_latest_metric_value(name, 0)
        new_value = current_value + increment
        
        self.record_metric(name, new_value, dimensions)
    
    def record_gauge(
        self,
        name: str,
        value: float,
        dimensions: Optional[Dict[str, Any]] = None
    ):
        """
        Record a gauge metric (current value)
        
        Args:
            name: Gauge name
            value: Current value
            dimensions: Additional dimensions
        """
        self.record_metric(name, value, dimensions)
    
    def get_latest_metric_value(self, name: str, default: float = 0.0) -> float:
        """
        Get the latest value for a metric
        
        Args:
            name: Metric name
            default: Default value if metric not found
            
        Returns:
            Latest metric value
        """
        if name in self.metrics_buffer and self.metrics_buffer[name]:
            return self.metrics_buffer[name][-1].value
        return default
    
    def get_metric_history(
        self,
        name: str,
        duration_minutes: int = 60
    ) -> List[MetricPoint]:
        """
        Get metric history for a specified duration
        
        Args:
            name: Metric name
            duration_minutes: Duration in minutes
            
        Returns:
            List of metric points
        """
        if name not in self.metrics_buffer:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=duration_minutes)
        
        return [
            point for point in self.metrics_buffer[name]
            if point.timestamp >= cutoff_time
        ]
    
    def get_metric_statistics(
        self,
        name: str,
        duration_minutes: int = 60
    ) -> Dict[str, float]:
        """
        Get statistical summary of a metric
        
        Args:
            name: Metric name
            duration_minutes: Duration in minutes
            
        Returns:
            Dictionary with statistics
        """
        history = self.get_metric_history(name, duration_minutes)
        
        if not history:
            return {}
        
        values = [point.value for point in history]
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'latest': values[-1] if values else 0
        }
    
    def add_alert_rule(self, rule: AlertRule):
        """
        Add an alert rule
        
        Args:
            rule: Alert rule configuration
        """
        self.alert_rules.append(rule)
        self.alert_states[rule.name] = {
            'triggered': False,
            'trigger_time': None,
            'last_evaluation': None
        }
        
        logger.info("Alert rule added", rule_name=rule.name, metric=rule.metric_name)
    
    async def _evaluate_alerts(self, metric_name: str, metric_point: MetricPoint):
        """
        Evaluate alert rules for a metric
        
        Args:
            metric_name: Name of the metric
            metric_point: Latest metric point
        """
        for rule in self.alert_rules:
            if rule.metric_name == metric_name and rule.enabled:
                await self._evaluate_single_alert(rule, metric_point)
    
    async def _evaluate_single_alert(self, rule: AlertRule, metric_point: MetricPoint):
        """
        Evaluate a single alert rule
        
        Args:
            rule: Alert rule
            metric_point: Latest metric point
        """
        try:
            # Check condition
            condition_met = False
            
            if rule.condition == 'greater_than':
                condition_met = metric_point.value > rule.threshold
            elif rule.condition == 'less_than':
                condition_met = metric_point.value < rule.threshold
            elif rule.condition == 'equals':
                condition_met = metric_point.value == rule.threshold
            
            alert_state = self.alert_states[rule.name]
            alert_state['last_evaluation'] = datetime.utcnow()
            
            if condition_met:
                if not alert_state['triggered']:
                    # Start tracking trigger time
                    alert_state['trigger_time'] = datetime.utcnow()
                else:
                    # Check if duration threshold is met
                    trigger_duration = (
                        datetime.utcnow() - alert_state['trigger_time']
                    ).total_seconds()
                    
                    if trigger_duration >= rule.duration_seconds:
                        await self._fire_alert(rule, metric_point, trigger_duration)
                
                alert_state['triggered'] = True
            else:
                # Reset alert state
                alert_state['triggered'] = False
                alert_state['trigger_time'] = None
                
        except Exception as e:
            logger.error(
                "Alert evaluation failed",
                rule_name=rule.name,
                error=str(e),
                exc_info=True
            )
    
    async def _fire_alert(
        self,
        rule: AlertRule,
        metric_point: MetricPoint,
        duration: float
    ):
        """
        Fire an alert
        
        Args:
            rule: Alert rule that triggered
            metric_point: Metric point that triggered the alert
            duration: Duration the condition has been met
        """
        alert_message = (
            f"Alert: {rule.name} - "
            f"Metric {rule.metric_name} is {rule.condition} {rule.threshold} "
            f"(current value: {metric_point.value}) "
            f"for {duration:.1f} seconds"
        )
        
        logger.warning(
            "Alert triggered",
            rule_name=rule.name,
            metric_name=rule.metric_name,
            current_value=metric_point.value,
            threshold=rule.threshold,
            duration=duration
        )
        
        # Log alert to audit log
        await self._log_alert(rule, metric_point, alert_message)
        
        # Here you could add integrations with external alerting systems
        # like email, Slack, PagerDuty, etc.
    
    async def _log_alert(
        self,
        rule: AlertRule,
        metric_point: MetricPoint,
        message: str
    ):
        """
        Log alert to audit log
        
        Args:
            rule: Alert rule
            metric_point: Metric point
            message: Alert message
        """
        try:
            session = await get_async_session()
            
            audit_log = AuditLog(
                event_type="alert_triggered",
                event_category="monitoring",
                event_description=message,
                metadata={
                    'rule_name': rule.name,
                    'metric_name': rule.metric_name,
                    'metric_value': metric_point.value,
                    'threshold': rule.threshold,
                    'condition': rule.condition,
                    'dimensions': metric_point.dimensions
                }
            )
            
            session.add(audit_log)
            await session.commit()
            await session.close()
            
        except Exception as e:
            logger.error("Failed to log alert", error=str(e))
    
    async def persist_metrics(self):
        """
        Persist buffered metrics to database
        """
        try:
            session = await get_async_session()
            
            metrics_to_persist = []
            
            # Collect all metrics from buffer
            for metric_name, points in self.metrics_buffer.items():
                for point in points:
                    metric_record = SystemMetrics(
                        metric_name=metric_name,
                        metric_value=point.value,
                        dimensions=point.dimensions,
                        timestamp=point.timestamp
                    )
                    metrics_to_persist.append(metric_record)
            
            # Batch insert
            if metrics_to_persist:
                session.add_all(metrics_to_persist)
                await session.commit()
                
                logger.info(f"Persisted {len(metrics_to_persist)} metrics to database")
                
                # Clear buffer after successful persistence
                self.metrics_buffer.clear()
            
            await session.close()
            
        except Exception as e:
            logger.error("Failed to persist metrics", error=str(e), exc_info=True)
    
    async def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health status
        
        Returns:
            Dictionary with health information
        """
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': {},
            'alerts': {
                'active_alerts': 0,
                'total_rules': len(self.alert_rules)
            }
        }
        
        # Check key metrics
        key_metrics = [
            'pipeline_jobs_processed',
            'pipeline_jobs_failed',
            'pipeline_processing_time',
            'document_processing_errors',
            'database_connection_errors'
        ]
        
        for metric_name in key_metrics:
            stats = self.get_metric_statistics(metric_name, 60)  # Last hour
            if stats:
                health_status['metrics'][metric_name] = stats
        
        # Count active alerts
        active_alerts = sum(
            1 for state in self.alert_states.values()
            if state['triggered']
        )
        health_status['alerts']['active_alerts'] = active_alerts
        
        # Determine overall health status
        if active_alerts > 0:
            health_status['status'] = 'warning'
        
        # Check for critical metrics
        error_rate = self.get_latest_metric_value('pipeline_error_rate', 0)
        if error_rate > 0.1:  # More than 10% error rate
            health_status['status'] = 'critical'
        
        return health_status
    
    def get_pipeline_dashboard_data(self) -> Dict[str, Any]:
        """
        Get data for pipeline monitoring dashboard
        
        Returns:
            Dictionary with dashboard data
        """
        dashboard_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'pipeline_status': {},
            'processing_metrics': {},
            'error_metrics': {},
            'performance_metrics': {},
            'recent_activity': []
        }
        
        # Pipeline status metrics
        pipeline_metrics = [
            'pipeline_jobs_queued',
            'pipeline_jobs_active',
            'pipeline_jobs_completed',
            'pipeline_jobs_failed'
        ]
        
        for metric in pipeline_metrics:
            dashboard_data['pipeline_status'][metric] = self.get_latest_metric_value(metric, 0)
        
        # Processing metrics
        processing_metrics = [
            'documents_processed_total',
            'chunks_created_total',
            'processing_throughput'
        ]
        
        for metric in processing_metrics:
            stats = self.get_metric_statistics(metric, 60)
            dashboard_data['processing_metrics'][metric] = stats
        
        # Error metrics
        error_metrics = [
            'document_processing_errors',
            'validation_errors',
            'database_errors'
        ]
        
        for metric in error_metrics:
            stats = self.get_metric_statistics(metric, 60)
            dashboard_data['error_metrics'][metric] = stats
        
        # Performance metrics
        performance_metrics = [
            'document_processing_duration',
            'chunk_generation_duration',
            'database_operation_duration'
        ]
        
        for metric in performance_metrics:
            stats = self.get_metric_statistics(metric, 60)
            dashboard_data['performance_metrics'][metric] = stats
        
        # Recent activity (last 10 metric points across all metrics)
        recent_points = []
        for metric_name, points in self.metrics_buffer.items():
            for point in list(points)[-5:]:  # Last 5 points per metric
                recent_points.append({
                    'metric': metric_name,
                    'value': point.value,
                    'timestamp': point.timestamp.isoformat(),
                    'dimensions': point.dimensions
                })
        
        # Sort by timestamp and take most recent
        recent_points.sort(key=lambda x: x['timestamp'], reverse=True)
        dashboard_data['recent_activity'] = recent_points[:20]
        
        return dashboard_data

# Global metrics collector instance
metrics_collector = MetricsCollector()

# Initialize default alert rules
default_alert_rules = [
    AlertRule(
        name="high_error_rate",
        metric_name="pipeline_error_rate",
        condition="greater_than",
        threshold=0.1,  # 10% error rate
        duration_seconds=300  # 5 minutes
    ),
    AlertRule(
        name="slow_processing",
        metric_name="document_processing_duration",
        condition="greater_than",
        threshold=60.0,  # 60 seconds
        duration_seconds=600  # 10 minutes
    ),
    AlertRule(
        name="queue_backup",
        metric_name="pipeline_jobs_queued",
        condition="greater_than",
        threshold=100,  # 100 jobs in queue
        duration_seconds=1800  # 30 minutes
    )
]

# Add default alert rules
for rule in default_alert_rules:
    metrics_collector.add_alert_rule(rule)


def setup_monitoring(app):
    """
    Setup monitoring for the FastAPI application

    Args:
        app: FastAPI application instance
    """
    logger.info("Monitoring setup initialized")
    # Monitoring is already configured via middleware and metrics_collector
    return metrics_collector


def track_request_metrics(request, response, duration: float):
    """
    Track request metrics

    Args:
        request: FastAPI request object
        response: FastAPI response object
        duration: Request duration in seconds
    """
    metrics_collector.record_metric(
        "request_duration",
        duration,
        dimensions={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code if hasattr(response, "status_code") else 200
        }
    )

    metrics_collector.record_counter(
        "total_requests",
        dimensions={
            "method": request.method,
            "path": request.url.path
        }
    )


async def log_api_call(
    service: str,
    model: str,
    tokens_used: int,
    processing_time: float,
    success: bool,
    error: str = None,
    metadata: dict = None
):
    """
    Log API call metrics

    Args:
        service: Service name (e.g., "openai_chat")
        model: Model name
        tokens_used: Number of tokens used
        processing_time: Processing time in seconds
        success: Whether the call was successful
        error: Error message if failed
        metadata: Additional metadata
    """
    metrics_collector.record_metric(
        f"{service}_processing_time",
        processing_time,
        dimensions={
            "model": model,
            "success": success
        }
    )

    if tokens_used > 0:
        metrics_collector.record_counter(
            f"{service}_tokens_used",
            increment=tokens_used,
            dimensions={
                "model": model
            }
        )

    if success:
        metrics_collector.record_counter(
            f"{service}_success",
            dimensions={"model": model}
        )
    else:
        metrics_collector.record_counter(
            f"{service}_error",
            dimensions={"model": model, "error": error}
        )

    logger.info(
        f"API call logged: {service}",
        service=service,
        model=model,
        tokens_used=tokens_used,
        processing_time=processing_time,
        success=success,
        error=error,
        metadata=metadata
    )


async def log_query_metrics(
    query: str,
    response: str,
    processing_time: float,
    user_id: str = None,
    conversation_id: str = None,
    mode: str = "qa",
    success: bool = True,
    error: str = None
):
    """
    Log query metrics

    Args:
        query: User query
        response: AI response
        processing_time: Processing time in seconds
        user_id: User ID
        conversation_id: Conversation ID
        mode: Query mode (qa, drafting, summarization)
        success: Whether the query was successful
        error: Error message if failed
    """
    metrics_collector.record_metric(
        "query_processing_time",
        processing_time,
        dimensions={
            "mode": mode,
            "success": success,
            "user_id": user_id
        }
    )

    metrics_collector.record_counter(
        "total_queries",
        dimensions={
            "mode": mode,
            "success": success
        }
    )

    if success:
        metrics_collector.record_metric(
            "query_response_length",
            len(response) if response else 0,
            dimensions={"mode": mode}
        )
    else:
        metrics_collector.record_counter(
            "query_errors",
            dimensions={"mode": mode, "error": error}
        )

    logger.info(
        "Query logged",
        query_length=len(query) if query else 0,
        response_length=len(response) if response else 0,
        processing_time=processing_time,
        user_id=user_id,
        conversation_id=conversation_id,
        mode=mode,
        success=success,
        error=error
    )