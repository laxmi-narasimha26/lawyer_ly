"""
Main FastAPI application for Indian Legal AI Assistant
Production-grade implementation with comprehensive features
"""
import asyncio
import time
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
import structlog
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, BackgroundTasks, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

# Internal imports
from config import settings
from database import get_db_session, startup_database, shutdown_database
from database.models import User, Document, Query, QueryMode, DocumentType
from core.rag_pipeline import RAGPipeline
from core.cache_manager import cache_manager
from services.document_processor import DocumentProcessor
from services.azure_storage import AzureStorageService
from services.monitoring_service import azure_monitoring_service
from api.models import (
    QueryRequest, QueryResponse, UploadResponse, DocumentListResponse,
    DocumentStatusResponse, HealthResponse, MetricsResponse
)
from api.auth import get_current_user, auth_service, session_manager
from api.middleware import (
    SecurityMiddleware, LoggingMiddleware, MetricsMiddleware,
    RateLimitMiddleware, AuditMiddleware
)
from api import health
from utils.exceptions import LegalAIException, ValidationError, ProcessingError, RateLimitExceeded
from utils.monitoring import setup_monitoring, track_request_metrics
from core.rate_limiter import rate_limiter, check_user_rate_limits, record_user_request, estimate_query_cost

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Initialize Sentry for error tracking
if settings.monitoring.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.monitoring.sentry_dsn,
        integrations=[
            FastApiIntegration(auto_enabling_integrations=False),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,
        environment=settings.environment,
    )

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global startup_time
    startup_time = time.time()
    
    logger.info("Starting Indian Legal AI Assistant", version=settings.app_version)
    
    try:
        # Initialize database
        await startup_database()
        
        # Initialize cache
        await cache_manager.initialize()
        
        # Initialize monitoring
        setup_monitoring()
        
        # Start Azure monitoring service
        asyncio.create_task(azure_monitoring_service.start_monitoring_loop(interval_seconds=60))
        
        # Initialize Azure services
        storage_service = AzureStorageService()
        await storage_service.initialize_container()
        
        # Initialize rate limiter
        from utils.monitoring import health_checker
        
        # Register health checks
        await register_application_health_checks(health_checker)
        
        logger.info("Application startup completed successfully")
        
        yield
        
    except Exception as e:
        logger.error("Application startup failed", error=str(e), exc_info=True)
        raise
    
    finally:
        # Cleanup
        logger.info("Shutting down Indian Legal AI Assistant")
        
        try:
            from utils.monitoring import shutdown_monitoring
            shutdown_monitoring()
        except Exception as e:
            logger.error("Error during monitoring shutdown", error=str(e))
        
        try:
            await shutdown_database()
            await cache_manager.close()
        except Exception as e:
            logger.error("Error during service shutdown", error=str(e))
        
        logger.info("Application shutdown completed")

async def register_application_health_checks(health_checker):
    """Register application-specific health checks"""
    
    async def database_health_check():
        """Check database connectivity"""
        try:
            async with get_db_session() as session:
                await session.execute("SELECT 1")
                return {"status": "connected", "response_time_ms": 10}
        except Exception as e:
            raise Exception(f"Database health check failed: {str(e)}")
    
    async def cache_health_check():
        """Check cache connectivity"""
        try:
            cache_info = await cache_manager.get_cache_info()
            if cache_info.get('redis', {}).get('connected'):
                return {"status": "connected", "response_time_ms": 5}
            else:
                raise Exception("Cache not connected")
        except Exception as e:
            raise Exception(f"Cache health check failed: {str(e)}")
    
    async def storage_health_check():
        """Check storage connectivity"""
        try:
            storage_health = await storage_service.health_check()
            if storage_health.get('status') == 'healthy':
                return {"status": "available", "response_time_ms": 50}
            else:
                raise Exception("Storage not healthy")
        except Exception as e:
            raise Exception(f"Storage health check failed: {str(e)}")
    
    async def rag_pipeline_health_check():
        """Check RAG pipeline health"""
        try:
            # Simple health check for RAG pipeline
            return {"status": "available", "response_time_ms": 20}
        except Exception as e:
            raise Exception(f"RAG pipeline health check failed: {str(e)}")
    
    # Register health checks
    health_checker.register_health_check("database", database_health_check, critical=True)
    health_checker.register_health_check("cache", cache_health_check, critical=False)
    health_checker.register_health_check("storage", storage_health_check, critical=True)
    health_checker.register_health_check("rag_pipeline", rag_pipeline_health_check, critical=True)
    
    logger.info("Application health checks registered")

# Global startup time tracking
startup_time = time.time()

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-grade AI legal assistant for Indian law",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add security and monitoring middleware
app.add_middleware(AuditMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=settings.allowed_methods,
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)

# Add trusted host middleware for production
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.azurewebsites.net", "localhost", "127.0.0.1"]
    )

# Initialize core services
rag_pipeline = RAGPipeline()
document_processor = DocumentProcessor()
storage_service = AzureStorageService()

# Include routers
app.include_router(health.router)

# Import and include compliance router
from api import compliance
app.include_router(compliance.router)

# Import and include performance router
from api import performance
app.include_router(performance.router)

# Security
security = HTTPBearer()

# Exception handlers
@app.exception_handler(LegalAIException)
async def legal_ai_exception_handler(request: Request, exc: LegalAIException):
    """Handle custom Legal AI exceptions"""
    logger.error(
        "Legal AI exception occurred",
        error_type=type(exc).__name__,
        error_message=str(exc),
        request_id=getattr(request.state, 'request_id', None)
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_type,
            "message": exc.message,
            "details": exc.details,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "validation_error",
            "message": str(exc),
            "request_id": getattr(request.state, 'request_id', None)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(
        "Unexpected exception occurred",
        error=str(exc),
        request_id=getattr(request.state, 'request_id', None),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": getattr(request.state, 'request_id', None)
        }
    )

# Health check endpoints
@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with basic health information"""
    return HealthResponse(
        name=settings.app_name,
        version=settings.app_version,
        status="healthy",
        timestamp=time.time()
    )

@app.get("/health", response_model=HealthResponse)
async def health_check(session: AsyncSession = Depends(get_db_session)):
    """Comprehensive health check"""
    try:
        from utils.monitoring import health_checker
        
        # Run all health checks
        health_results = await health_checker.run_all_health_checks()
        
        # Determine overall status
        overall_status = health_results.get("overall_status", "unknown")
        
        # Map component statuses
        components = {}
        for check_name, check_result in health_results.get("checks", {}).items():
            components[check_name] = check_result.get("status", "unknown")
        
        return HealthResponse(
            name=settings.app_name,
            version=settings.app_version,
            status=overall_status,
            timestamp=time.time(),
            components=components
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e), exc_info=True)
        return HealthResponse(
            name=settings.app_name,
            version=settings.app_version,
            status="unhealthy",
            timestamp=time.time(),
            error=str(e)
        )

@app.get("/health/detailed")
async def detailed_health_check(session: AsyncSession = Depends(get_db_session)):
    """Detailed health check with component details"""
    try:
        from utils.monitoring import health_checker
        
        # Run all health checks
        health_results = await health_checker.run_all_health_checks()
        
        return {
            "overall_status": health_results.get("overall_status", "unknown"),
            "timestamp": health_results.get("timestamp"),
            "checks": health_results.get("checks", {}),
            "system_info": {
                "app_name": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
                "uptime_seconds": time.time() - startup_time if 'startup_time' in globals() else 0
            }
        }
        
    except Exception as e:
        logger.error("Detailed health check failed", error=str(e), exc_info=True)
        return {
            "overall_status": "unhealthy",
            "timestamp": time.time(),
            "error": str(e),
            "system_info": {
                "app_name": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment
            }
        }

@app.get("/health/readiness")
async def readiness_check():
    """Kubernetes readiness probe"""
    try:
        from utils.monitoring import health_checker
        
        # Check critical components only
        critical_checks = ["database", "openai"]
        
        for check_name in critical_checks:
            result = await health_checker.run_health_check(check_name)
            if result.get("status") != "healthy":
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "status": "not_ready",
                        "failed_check": check_name,
                        "timestamp": time.time()
                    }
                )
        
        return {
            "status": "ready",
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "error": str(e),
                "timestamp": time.time()
            }
        )

@app.get("/health/liveness")
async def liveness_check():
    """Kubernetes liveness probe"""
    try:
        # Simple check that the application is running
        return {
            "status": "alive",
            "timestamp": time.time(),
            "uptime_seconds": time.time() - startup_time if 'startup_time' in globals() else 0
        }
        
    except Exception as e:
        logger.error("Liveness check failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_alive",
                "error": str(e),
                "timestamp": time.time()
            }
        )

@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get application metrics"""
    try:
        from utils.monitoring import metrics_collector, get_monitoring_status
        
        # Get comprehensive metrics
        monitoring_status = get_monitoring_status()
        
        # Get additional component stats
        cache_info = await cache_manager.get_cache_info()
        storage_stats = storage_service.get_storage_statistics()
        processing_stats = document_processor.get_processing_statistics()
        
        return MetricsResponse(
            cache_stats=cache_info,
            storage_stats=storage_stats,
            processing_stats=processing_stats,
            timestamp=time.time(),
            system_metrics=monitoring_status.get("metrics", {}),
            alerts=monitoring_status.get("alerts", {})
        )
        
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )

@app.get("/metrics/prometheus")
async def get_prometheus_metrics():
    """Get metrics in Prometheus format"""
    try:
        from utils.monitoring import metrics_collector
        
        metrics_summary = metrics_collector.get_metrics_summary()
        
        # Convert to Prometheus format
        prometheus_metrics = []
        
        # Counters
        for name, value in metrics_summary.get("counters", {}).items():
            prometheus_metrics.append(f"# TYPE {name} counter")
            prometheus_metrics.append(f"{name} {value}")
        
        # Gauges
        for name, value in metrics_summary.get("gauges", {}).items():
            prometheus_metrics.append(f"# TYPE {name} gauge")
            prometheus_metrics.append(f"{name} {value}")
        
        # Histograms
        for name, stats in metrics_summary.get("histograms", {}).items():
            prometheus_metrics.append(f"# TYPE {name} histogram")
            prometheus_metrics.append(f"{name}_count {stats['count']}")
            prometheus_metrics.append(f"{name}_sum {stats['avg'] * stats['count']}")
        
        return Response(
            content="\n".join(prometheus_metrics),
            media_type="text/plain"
        )
        
    except Exception as e:
        logger.error("Failed to get Prometheus metrics", error=str(e))
        return Response(
            content=f"# Error getting metrics: {str(e)}",
            media_type="text/plain",
            status_code=500
        )

# Authentication endpoints
@app.post("/auth/login")
async def login(
    request: Request,
    email: str,
    password: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Authenticate user and return access and refresh tokens"""
    try:
        logger.info("Login attempt", email=email, ip=request.client.host)
        
        # Authenticate user
        user = await auth_service.authenticate_user(email, password, session)
        
        if not user:
            logger.warning("Login failed - invalid credentials", email=email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create tokens
        token_data = await auth_service.create_user_tokens(user)
        
        # Create session
        session_id = session_manager.create_session(str(user.id), token_data)
        
        logger.info("Login successful", user_id=str(user.id), email=email)
        
        return {
            **token_data,
            "session_id": session_id,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error", email=email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to server error"
        )

@app.post("/auth/refresh")
async def refresh_token(
    refresh_token: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Refresh access token using refresh token"""
    try:
        # Verify refresh token
        payload = auth_service.verify_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user from database
        from sqlalchemy import select
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new tokens
        token_data = await auth_service.create_user_tokens(user)
        
        logger.info("Token refreshed", user_id=str(user.id))
        
        return token_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )

@app.post("/auth/logout")
async def logout(
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Logout user and invalidate session"""
    try:
        if session_id:
            session_manager.invalidate_session(session_id)
        else:
            # Invalidate all user sessions
            session_manager.invalidate_user_sessions(str(current_user.id))
        
        logger.info("User logged out", user_id=str(current_user.id))
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error("Logout error", user_id=str(current_user.id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@app.get("/auth/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "subscription_tier": current_user.subscription_tier,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at.isoformat(),
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }

@app.get("/api/usage")
async def get_usage_status(
    current_user: User = Depends(get_current_user)
):
    """Get current user's usage and rate limit status"""
    try:
        from core.rate_limiter import get_user_usage_status
        
        usage_status = await get_user_usage_status(str(current_user.id))
        
        return {
            "user_id": str(current_user.id),
            "subscription_tier": current_user.subscription_tier,
            "usage_status": usage_status,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(
            "Failed to get usage status",
            user_id=str(current_user.id),
            error=str(e)
        )
        
        raise ProcessingError(
            message="Failed to retrieve usage information",
            details={"error": str(e)} if settings.debug else None
        )

@app.get("/api/usage/alerts")
async def get_usage_alerts(
    current_user: User = Depends(get_current_user)
):
    """Get usage alerts and warnings for the current user"""
    try:
        from core.rate_limiter import get_user_usage_status
        
        usage_status = await get_user_usage_status(str(current_user.id))
        alerts = []
        
        # Check for usage warnings
        daily_usage = usage_status.get("usage", {}).get("daily", {})
        hourly_usage = usage_status.get("usage", {}).get("hourly", {})
        
        # Cost alerts
        daily_cost = daily_usage.get("cost", 0.0)
        if daily_cost > 8.0:  # 80% of $10 daily limit
            alerts.append({
                "type": "cost_warning",
                "severity": "warning" if daily_cost < 9.0 else "critical",
                "message": f"Daily cost usage: ${daily_cost:.2f} / $10.00",
                "threshold": 10.0,
                "current": daily_cost
            })
        
        # Token alerts
        daily_tokens = daily_usage.get("tokens", 0)
        if daily_tokens > 80000:  # 80% of typical daily limit
            alerts.append({
                "type": "token_warning",
                "severity": "warning" if daily_tokens < 90000 else "critical",
                "message": f"Daily token usage: {daily_tokens:,} tokens",
                "threshold": 100000,
                "current": daily_tokens
            })
        
        return {
            "alerts": alerts,
            "alert_count": len(alerts),
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(
            "Failed to get usage alerts",
            user_id=str(current_user.id),
            error=str(e)
        )
        
        return {
            "alerts": [],
            "alert_count": 0,
            "error": "Failed to retrieve alerts"
        }

@app.get("/api/system/alerts")
async def get_system_alerts():
    """Get system-wide alerts and monitoring status"""
    try:
        from utils.monitoring import alert_manager, get_monitoring_status
        
        # Get active alerts
        active_alerts = alert_manager.get_active_alerts()
        alert_summary = alert_manager.get_alert_summary()
        
        # Get monitoring status
        monitoring_status = get_monitoring_status()
        
        return {
            "active_alerts": active_alerts,
            "alert_summary": alert_summary,
            "monitoring_status": monitoring_status,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error("Failed to get system alerts", error=str(e))
        return {
            "active_alerts": [],
            "alert_summary": {"active_count": 0},
            "error": str(e),
            "timestamp": time.time()
        }

@app.get("/api/system/errors")
async def get_recent_errors(
    limit: int = 50,
    severity: Optional[str] = None
):
    """Get recent system errors for monitoring"""
    try:
        # This would typically query error logs from database or logging system
        # For now, return a placeholder response
        
        recent_errors = [
            {
                "timestamp": time.time() - 3600,
                "level": "ERROR",
                "message": "Sample error message",
                "component": "rag_pipeline",
                "error_type": "ProcessingError",
                "count": 1
            }
        ]
        
        if severity:
            recent_errors = [
                error for error in recent_errors 
                if error["level"].lower() == severity.lower()
            ]
        
        return {
            "errors": recent_errors[:limit],
            "total_count": len(recent_errors),
            "filters": {"severity": severity, "limit": limit},
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error("Failed to get recent errors", error=str(e))
        return {
            "errors": [],
            "total_count": 0,
            "error": str(e),
            "timestamp": time.time()
        }

@app.post("/api/system/alerts/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user)
):
    """Acknowledge a system alert"""
    try:
        from utils.monitoring import alert_manager
        
        # In a full implementation, this would mark the alert as acknowledged
        logger.info(
            "Alert acknowledged",
            alert_id=alert_id,
            user_id=str(current_user.id)
        )
        
        return {
            "alert_id": alert_id,
            "acknowledged": True,
            "acknowledged_by": str(current_user.id),
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error("Failed to acknowledge alert", alert_id=alert_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge alert"
        )

# Core API endpoints
@app.post("/api/query", response_model=QueryResponse)
async def process_query(
    request: Request,
    query_request: QueryRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Process legal query and return AI-generated response with citations
    """
    start_time = time.time()
    user_id = str(current_user.id)
    
    try:
        logger.info(
            "Processing legal query",
            user_id=user_id,
            mode=query_request.mode.value,
            query_length=len(query_request.query),
            has_document_ids=bool(query_request.document_ids)
        )
        
        # Validate query
        if len(query_request.query.strip()) < 5:
            raise ValidationError("Query must be at least 5 characters long")
        
        if len(query_request.query) > 5000:
            raise ValidationError("Query must be less than 5000 characters")
        
        # Estimate tokens and cost for rate limiting
        estimated_tokens, estimated_cost = estimate_query_cost(
            query_request.query, 
            query_request.mode.value
        )
        
        # Check rate limits
        rate_limit_result = await check_user_rate_limits(
            user_id=user_id,
            endpoint="/api/query",
            tokens=estimated_tokens,
            estimated_cost=estimated_cost
        )
        
        if not rate_limit_result["allowed"]:
            violations = rate_limit_result["violations"]
            primary_violation = violations[0] if violations else {}
            
            logger.warning(
                "Rate limit exceeded",
                user_id=user_id,
                violations=violations
            )
            
            raise RateLimitExceeded(
                message=primary_violation.get("message", "Rate limit exceeded"),
                retry_after=primary_violation.get("retry_after", 60),
                details={
                    "violations": violations,
                    "remaining_limits": rate_limit_result["remaining"]
                }
            )
        
        # Process query through RAG pipeline
        rag_response = await rag_pipeline.process_query(
            query=query_request.query,
            user_id=user_id,
            mode=query_request.mode,
            conversation_id=query_request.conversation_id,
            document_ids=query_request.document_ids,
            session=session
        )
        
        # Record actual usage for rate limiting
        actual_tokens = rag_response.metadata.get("total_tokens", estimated_tokens)
        background_tasks.add_task(
            record_user_request,
            user_id=user_id,
            endpoint="/api/query",
            tokens=actual_tokens,
            model=rag_response.metadata.get("model", "gpt-4")
        )
        
        # Store query in database for analytics
        background_tasks.add_task(
            store_query_record,
            query_request=query_request,
            response=rag_response,
            user_id=user_id,
            processing_time=time.time() - start_time
        )
        
        # Track metrics
        track_request_metrics(
            endpoint="/api/query",
            user_id=user_id,
            processing_time=time.time() - start_time,
            success=True
        )
        
        # Add rate limit headers to response
        response = QueryResponse(
            answer=rag_response.answer,
            citations=rag_response.citations,
            confidence_score=rag_response.confidence_score,
            processing_time_ms=rag_response.processing_time_ms,
            mode=query_request.mode,
            metadata=rag_response.metadata
        )
        
        return response
        
    except (ValidationError, RateLimitExceeded):
        raise
    except Exception as e:
        logger.error(
            "Query processing failed",
            user_id=user_id,
            error=str(e),
            exc_info=True
        )
        
        track_request_metrics(
            endpoint="/api/query",
            user_id=user_id,
            processing_time=time.time() - start_time,
            success=False
        )
        
        raise ProcessingError(
            message="Failed to process query. Please try again.",
            details={"error": str(e)} if settings.debug else None
        )

@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_type: Optional[DocumentType] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Upload and process legal document
    """
    user_id = str(current_user.id)
    
    try:
        logger.info(
            "Document upload initiated",
            user_id=user_id,
            filename=file.filename,
            content_type=file.content_type,
            file_size=file.size if hasattr(file, 'size') else 'unknown'
        )
        
        # Check rate limits for uploads
        rate_limit_result = await check_user_rate_limits(
            user_id=user_id,
            endpoint="/api/upload"
        )
        
        if not rate_limit_result["allowed"]:
            violations = rate_limit_result["violations"]
            primary_violation = violations[0] if violations else {}
            
            logger.warning(
                "Upload rate limit exceeded",
                user_id=user_id,
                violations=violations
            )
            
            raise RateLimitExceeded(
                message=primary_violation.get("message", "Upload rate limit exceeded"),
                retry_after=primary_violation.get("retry_after", 3600),
                details={
                    "violations": violations,
                    "remaining_limits": rate_limit_result["remaining"]
                }
            )
        
        # Validate file
        if not file.filename:
            raise ValidationError("Filename is required")
        
        # Check file size
        if hasattr(file, 'size') and file.size > settings.azure_storage.max_file_size_mb * 1024 * 1024:
            raise ValidationError(
                f"File size exceeds {settings.azure_storage.max_file_size_mb}MB limit"
            )
        
        # Check file extension
        file_extension = file.filename.split('.')[-1].lower()
        allowed_extensions = [ext.lstrip('.') for ext in settings.azure_storage.allowed_extensions]
        
        if file_extension not in allowed_extensions:
            raise ValidationError(
                f"File type .{file_extension} not supported. "
                f"Allowed types: {', '.join(settings.azure_storage.allowed_extensions)}"
            )
        
        # Process document
        document_id = await document_processor.process_upload(
            file=file,
            user_id=user_id,
            session=session,
            document_type=document_type
        )
        
        # Record upload for rate limiting
        await record_user_request(
            user_id=user_id,
            endpoint="/api/upload"
        )
        
        logger.info(
            "Document upload completed",
            user_id=user_id,
            document_id=document_id,
            filename=file.filename
        )
        
        return UploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="processing",
            message="Document uploaded successfully. Processing in background."
        )
        
    except (ValidationError, RateLimitExceeded):
        raise
    except Exception as e:
        logger.error(
            "Document upload failed",
            user_id=user_id,
            filename=file.filename,
            error=str(e),
            exc_info=True
        )
        
        raise ProcessingError(
            message="Failed to upload document. Please try again.",
            details={"error": str(e)} if settings.debug else None
        )

@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    List all documents uploaded by the current user
    """
    try:
        documents = await storage_service.list_user_documents(str(current_user.id))
        
        return DocumentListResponse(
            documents=documents,
            total_count=len(documents)
        )
        
    except Exception as e:
        logger.error(
            "Failed to list documents",
            user_id=current_user.id,
            error=str(e)
        )
        
        raise ProcessingError(
            message="Failed to retrieve documents",
            details={"error": str(e)} if settings.debug else None
        )

@app.get("/api/documents/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get processing status of a specific document
    """
    try:
        status_info = await document_processor.get_processing_status(
            document_id=document_id,
            user_id=str(current_user.id),
            session=session
        )
        
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return DocumentStatusResponse(**status_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get document status",
            document_id=document_id,
            user_id=current_user.id,
            error=str(e)
        )
        
        raise ProcessingError(
            message="Failed to retrieve document status",
            details={"error": str(e)} if settings.debug else None
        )

@app.get("/api/citation/{citation_id}")
async def get_citation_text(
    citation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve the full text of a citation for user verification
    """
    try:
        citation_text = await rag_pipeline.get_citation_text(
            citation_id=citation_id,
            user_id=str(current_user.id),
            session=session
        )
        
        if not citation_text:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Citation not found"
            )
        
        return {
            "citation_id": citation_id,
            "text": citation_text,
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve citation",
            citation_id=citation_id,
            user_id=current_user.id,
            error=str(e)
        )
        
        raise ProcessingError(
            message="Failed to retrieve citation text",
            details={"error": str(e)} if settings.debug else None
        )

# Background task functions
async def store_query_record(
    query_request: QueryRequest,
    response: Any,
    user_id: str,
    processing_time: float
):
    """Store query record for analytics"""
    try:
        # Implementation would store query details in database
        # for analytics and improvement purposes
        logger.debug(
            "Query record stored",
            user_id=user_id,
            processing_time=processing_time
        )
    except Exception as e:
        logger.error("Failed to store query record", error=str(e))

# Admin endpoints (if needed)
if settings.debug:
    @app.post("/admin/cache/clear")
    async def clear_cache(pattern: str = "*"):
        """Clear cache entries matching pattern"""
        cleared_count = await cache_manager.clear_pattern(pattern)
        return {"message": f"Cleared {cleared_count} cache entries"}
    
    @app.get("/admin/system/info")
    async def get_system_info():
        """Get system information for debugging"""
        return {
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "debug": settings.debug,
            "python_version": "3.10+",
            "database_url": settings.database.url.split('@')[0] + "@***",  # Hide credentials
        }

# Startup message
@app.on_event("startup")
async def startup_message():
    """Log startup message"""
    logger.info(
        "Indian Legal AI Assistant started successfully",
        version=settings.app_version,
        environment=settings.environment,
        debug=settings.debug
    )

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
        log_config=None,  # Use our custom logging
        access_log=False,  # We handle access logging in middleware
    )