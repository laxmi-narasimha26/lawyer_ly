"""
Production-grade middleware for security, logging, and rate limiting
Implements comprehensive request processing pipeline
"""
import time
import uuid
import json
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import structlog
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db_session
from database.models import User, AuditLog
from services.input_validation_service import input_validator
from services.audit_logging_service import audit_logger, AuditEventType, AuditEventCategory
from utils.exceptions import RateLimitExceeded, SecurityViolation

logger = structlog.get_logger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware implementing comprehensive security controls
    
    Features:
    - Request ID generation
    - Security headers
    - IP-based blocking
    - Request size limits
    - Content type validation
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.blocked_ips = set()
        self.suspicious_ips = defaultdict(int)
        self.max_request_size = 50 * 1024 * 1024  # 50MB
        
        logger.info("Security middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security pipeline"""
        start_time = time.time()
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        try:
            # Security checks
            await self._check_ip_security(request)
            await self._check_request_size(request)
            await self._check_content_type(request)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            self._add_security_headers(response)
            
            # Add request ID to response
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{(time.time() - start_time) * 1000:.2f}ms"
            
            return response
            
        except SecurityViolation as e:
            logger.warning(
                "Security violation detected",
                request_id=request_id,
                ip=request.client.host,
                violation=str(e),
                path=request.url.path
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "security_violation",
                    "message": "Request blocked for security reasons",
                    "request_id": request_id
                }
            )
            
        except Exception as e:
            logger.error(
                "Security middleware error",
                request_id=request_id,
                error=str(e),
                exc_info=True
            )
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "internal_error",
                    "message": "Internal server error",
                    "request_id": request_id
                }
            )
    
    async def _check_ip_security(self, request: Request):
        """Check IP-based security rules"""
        client_ip = request.client.host
        
        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            raise SecurityViolation(f"IP {client_ip} is blocked")
        
        # Check for suspicious activity
        if self.suspicious_ips[client_ip] > 100:  # Threshold for suspicious activity
            self.blocked_ips.add(client_ip)
            raise SecurityViolation(f"IP {client_ip} blocked due to suspicious activity")
    
    async def _check_request_size(self, request: Request):
        """Check request size limits"""
        content_length = request.headers.get("content-length")
        
        if content_length:
            size = int(content_length)
            if size > self.max_request_size:
                raise SecurityViolation(f"Request size {size} exceeds limit {self.max_request_size}")
    
    async def _check_content_type(self, request: Request):
        """Validate content type for POST/PUT requests"""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            
            # Allow common content types
            allowed_types = [
                "application/json",
                "multipart/form-data",
                "application/x-www-form-urlencoded",
                "text/plain"
            ]
            
            if not any(allowed_type in content_type for allowed_type in allowed_types):
                raise SecurityViolation(f"Invalid content type: {content_type}")
    
    def _add_security_headers(self, response: Response):
        """Add security headers to response"""
        if not settings.security.enable_security_headers:
            return
            
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": settings.security.content_security_policy,
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "X-Permitted-Cross-Domain-Policies": "none",
        }
        
        # Add HTTPS enforcement in production
        if settings.is_production and settings.security.force_https:
            security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        for header, value in security_headers.items():
            response.headers[header] = value

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Advanced rate limiting middleware with multiple strategies
    
    Features:
    - Per-user rate limiting
    - Per-IP rate limiting
    - Endpoint-specific limits
    - Token bucket algorithm
    - Sliding window counters
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
        # Rate limit storage
        self.user_limits = defaultdict(lambda: defaultdict(deque))
        self.ip_limits = defaultdict(lambda: defaultdict(deque))
        self.token_buckets = defaultdict(lambda: {
            'tokens': settings.rate_limit.burst_limit,
            'last_refill': time.time()
        })
        
        # Endpoint-specific limits
        self.endpoint_limits = {
            "/api/query": {
                "requests_per_hour": settings.rate_limit.queries_per_hour,
                "burst_limit": 10
            },
            "/api/upload": {
                "requests_per_hour": settings.rate_limit.uploads_per_hour,
                "burst_limit": 5
            },
            "/auth/token": {
                "requests_per_hour": 20,
                "burst_limit": 5
            }
        }
        
        logger.info("Rate limit middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting to request"""
        try:
            # Extract user and IP information
            user_id = await self._get_user_id(request)
            client_ip = request.client.host
            endpoint = request.url.path
            
            # Apply rate limits
            await self._check_rate_limits(user_id, client_ip, endpoint)
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            self._add_rate_limit_headers(response, user_id, client_ip, endpoint)
            
            return response
            
        except RateLimitExceeded as e:
            logger.warning(
                "Rate limit exceeded",
                user_id=user_id if 'user_id' in locals() else None,
                ip=client_ip if 'client_ip' in locals() else None,
                endpoint=endpoint if 'endpoint' in locals() else None,
                limit_type=str(e)
            )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": str(e),
                    "retry_after": e.retry_after if hasattr(e, 'retry_after') else 60
                },
                headers={
                    "Retry-After": str(e.retry_after if hasattr(e, 'retry_after') else 60)
                }
            )
    
    async def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request"""
        try:
            # Try to get user from authorization header
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # This would normally decode the JWT token
                # For now, return a placeholder
                return "authenticated_user"
            return None
        except Exception:
            return None
    
    async def _check_rate_limits(self, user_id: Optional[str], client_ip: str, endpoint: str):
        """Check all applicable rate limits"""
        current_time = time.time()
        
        # Check endpoint-specific limits
        if endpoint in self.endpoint_limits:
            limit_config = self.endpoint_limits[endpoint]
            
            # Check user-based limits
            if user_id:
                await self._check_sliding_window_limit(
                    self.user_limits[user_id][endpoint],
                    limit_config["requests_per_hour"],
                    3600,  # 1 hour window
                    current_time,
                    f"User rate limit exceeded for {endpoint}"
                )
            
            # Check IP-based limits (more restrictive for unauthenticated users)
            ip_limit = limit_config["requests_per_hour"] // 2 if not user_id else limit_config["requests_per_hour"]
            await self._check_sliding_window_limit(
                self.ip_limits[client_ip][endpoint],
                ip_limit,
                3600,
                current_time,
                f"IP rate limit exceeded for {endpoint}"
            )
            
            # Check burst limits using token bucket
            bucket_key = f"{user_id or client_ip}:{endpoint}"
            await self._check_token_bucket_limit(
                bucket_key,
                limit_config["burst_limit"],
                current_time
            )
    
    async def _check_sliding_window_limit(
        self,
        request_times: deque,
        limit: int,
        window_seconds: int,
        current_time: float,
        error_message: str
    ):
        """Check sliding window rate limit"""
        # Remove old requests outside the window
        cutoff_time = current_time - window_seconds
        while request_times and request_times[0] < cutoff_time:
            request_times.popleft()
        
        # Check if limit is exceeded
        if len(request_times) >= limit:
            retry_after = int(request_times[0] + window_seconds - current_time) + 1
            raise RateLimitExceeded(error_message, retry_after=retry_after)
        
        # Add current request
        request_times.append(current_time)
    
    async def _check_token_bucket_limit(self, bucket_key: str, burst_limit: int, current_time: float):
        """Check token bucket rate limit for burst protection"""
        bucket = self.token_buckets[bucket_key]
        
        # Refill tokens based on time elapsed
        time_elapsed = current_time - bucket['last_refill']
        tokens_to_add = time_elapsed * (burst_limit / 60)  # Refill rate per second
        bucket['tokens'] = min(burst_limit, bucket['tokens'] + tokens_to_add)
        bucket['last_refill'] = current_time
        
        # Check if tokens available
        if bucket['tokens'] < 1:
            raise RateLimitExceeded("Burst limit exceeded", retry_after=60)
        
        # Consume token
        bucket['tokens'] -= 1
    
    def _add_rate_limit_headers(self, response: Response, user_id: Optional[str], client_ip: str, endpoint: str):
        """Add rate limit information to response headers"""
        if endpoint in self.endpoint_limits:
            limit_config = self.endpoint_limits[endpoint]
            
            # Calculate remaining requests
            current_time = time.time()
            cutoff_time = current_time - 3600  # 1 hour window
            
            if user_id:
                request_times = self.user_limits[user_id][endpoint]
                # Remove old requests
                while request_times and request_times[0] < cutoff_time:
                    request_times.popleft()
                
                remaining = max(0, limit_config["requests_per_hour"] - len(request_times))
                response.headers["X-RateLimit-Limit"] = str(limit_config["requests_per_hour"])
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                
                if request_times:
                    reset_time = int(request_times[0] + 3600)
                    response.headers["X-RateLimit-Reset"] = str(reset_time)

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive logging middleware for audit and monitoring
    
    Features:
    - Request/response logging
    - Performance metrics
    - Error tracking
    - Audit trail
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.sensitive_headers = {
            "authorization", "cookie", "x-api-key", "x-auth-token"
        }
        self.sensitive_paths = {
            "/auth/token", "/auth/login", "/auth/register"
        }
        
        logger.info("Logging middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details"""
        start_time = time.time()
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        # Log request
        await self._log_request(request, request_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log response
            await self._log_response(request, response, request_id, processing_time)
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            # Log error
            await self._log_error(request, e, request_id, processing_time)
            
            raise
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request details"""
        # Sanitize headers
        headers = dict(request.headers)
        for sensitive_header in self.sensitive_headers:
            if sensitive_header in headers:
                headers[sensitive_header] = "***REDACTED***"
        
        # Determine if path is sensitive
        is_sensitive_path = request.url.path in self.sensitive_paths
        
        log_data = {
            "event_type": "request_received",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params) if not is_sensitive_path else "***REDACTED***",
            "headers": headers,
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "content_length": request.headers.get("content-length"),
            "content_type": request.headers.get("content-type"),
        }
        
        logger.info("HTTP request received", **log_data)
    
    async def _log_response(self, request: Request, response: Response, request_id: str, processing_time: float):
        """Log response details"""
        log_data = {
            "event_type": "request_completed",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "processing_time_ms": round(processing_time * 1000, 2),
            "response_size": response.headers.get("content-length"),
        }
        
        # Log level based on status code
        if response.status_code >= 500:
            logger.error("HTTP request failed", **log_data)
        elif response.status_code >= 400:
            logger.warning("HTTP request error", **log_data)
        else:
            logger.info("HTTP request completed", **log_data)
    
    async def _log_error(self, request: Request, error: Exception, request_id: str, processing_time: float):
        """Log request error"""
        log_data = {
            "event_type": "request_error",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "processing_time_ms": round(processing_time * 1000, 2),
        }
        
        logger.error("HTTP request error", **log_data, exc_info=True)

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Metrics collection middleware for monitoring and analytics
    
    Features:
    - Request counting
    - Response time tracking
    - Error rate monitoring
    - Endpoint usage statistics
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
        # Metrics storage
        self.request_counts = defaultdict(int)
        self.response_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.status_codes = defaultdict(int)
        
        # Metrics collection interval
        self.last_metrics_flush = time.time()
        self.metrics_flush_interval = 60  # 1 minute
        
        logger.info("Metrics middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collect metrics for request"""
        start_time = time.time()
        endpoint = request.url.path
        method = request.method
        
        try:
            # Process request
            response = await call_next(request)
            
            # Collect metrics
            processing_time = time.time() - start_time
            await self._collect_metrics(endpoint, method, response.status_code, processing_time)
            
            return response
            
        except Exception as e:
            # Collect error metrics
            processing_time = time.time() - start_time
            await self._collect_error_metrics(endpoint, method, e, processing_time)
            
            raise
    
    async def _collect_metrics(self, endpoint: str, method: str, status_code: int, processing_time: float):
        """Collect successful request metrics"""
        metric_key = f"{method}:{endpoint}"
        
        # Increment request count
        self.request_counts[metric_key] += 1
        
        # Track response time
        self.response_times[metric_key].append(processing_time)
        
        # Track status codes
        self.status_codes[f"{metric_key}:{status_code}"] += 1
        
        # Flush metrics if interval elapsed
        await self._maybe_flush_metrics()
    
    async def _collect_error_metrics(self, endpoint: str, method: str, error: Exception, processing_time: float):
        """Collect error metrics"""
        metric_key = f"{method}:{endpoint}"
        error_key = f"{metric_key}:error:{type(error).__name__}"
        
        # Increment error count
        self.error_counts[error_key] += 1
        
        # Track response time for errors too
        self.response_times[metric_key].append(processing_time)
        
        # Flush metrics if interval elapsed
        await self._maybe_flush_metrics()
    
    async def _maybe_flush_metrics(self):
        """Flush metrics to storage if interval elapsed"""
        current_time = time.time()
        
        if current_time - self.last_metrics_flush >= self.metrics_flush_interval:
            await self._flush_metrics()
            self.last_metrics_flush = current_time
    
    async def _flush_metrics(self):
        """Flush collected metrics to persistent storage"""
        try:
            # In production, this would write to a metrics database
            # For now, just log the metrics
            
            metrics_summary = {
                "timestamp": datetime.utcnow().isoformat(),
                "request_counts": dict(self.request_counts),
                "error_counts": dict(self.error_counts),
                "status_codes": dict(self.status_codes),
                "avg_response_times": {
                    key: sum(times) / len(times) if times else 0
                    for key, times in self.response_times.items()
                }
            }
            
            logger.info("Metrics flushed", metrics=metrics_summary)
            
            # Clear metrics after flushing
            self.request_counts.clear()
            self.response_times.clear()
            self.error_counts.clear()
            self.status_codes.clear()
            
        except Exception as e:
            logger.error("Failed to flush metrics", error=str(e))

class AuditMiddleware(BaseHTTPMiddleware):
    """
    Audit logging middleware for compliance and security
    
    Features:
    - Comprehensive audit trail
    - User action tracking
    - Data access logging
    - Compliance reporting
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
        # Audit configuration
        self.audit_endpoints = {
            "/api/query": "legal_query",
            "/api/upload": "document_upload",
            "/auth/token": "authentication",
            "/api/documents": "document_access"
        }
        
        logger.info("Audit middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Create audit trail for request"""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        # Check if endpoint requires auditing
        if not self._should_audit(request):
            return await call_next(request)
        
        # Extract user information
        user_id = await self._extract_user_id(request)
        
        # Create audit log entry
        audit_data = await self._create_audit_entry(request, user_id, request_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Update audit entry with response
            audit_data.update({
                "status_code": response.status_code,
                "success": response.status_code < 400
            })
            
            # Store audit log
            await self._store_audit_log(audit_data)
            
            return response
            
        except Exception as e:
            # Update audit entry with error
            audit_data.update({
                "status_code": 500,
                "success": False,
                "error": str(e)
            })
            
            # Store audit log
            await self._store_audit_log(audit_data)
            
            raise
    
    def _should_audit(self, request: Request) -> bool:
        """Determine if request should be audited"""
        return request.url.path in self.audit_endpoints
    
    async def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request for audit purposes"""
        try:
            # This would normally decode the JWT token
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                return "authenticated_user"  # Placeholder
            return None
        except Exception:
            return None
    
    async def _create_audit_entry(self, request: Request, user_id: Optional[str], request_id: str) -> Dict[str, Any]:
        """Create audit log entry"""
        return {
            "request_id": request_id,
            "user_id": user_id,
            "event_type": self.audit_endpoints.get(request.url.path, "unknown"),
            "event_category": "api_access",
            "event_description": f"{request.method} {request.url.path}",
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "timestamp": datetime.utcnow(),
            "resource_type": "api_endpoint",
            "resource_id": request.url.path,
            "metadata": {
                "method": request.method,
                "query_params": dict(request.query_params),
                "content_type": request.headers.get("content-type")
            }
        }
    
    async def _store_audit_log(self, audit_data: Dict[str, Any]):
        """Store audit log entry in database"""
        try:
            # Map event types
            event_type_mapping = {
                "api_access": AuditEventType.LEGAL_QUERY,
                "document_upload": AuditEventType.DOCUMENT_UPLOAD,
                "authentication": AuditEventType.LOGIN_SUCCESS
            }
            
            event_type = event_type_mapping.get(
                audit_data.get("event_type"), 
                AuditEventType.LEGAL_QUERY
            )
            
            # Use audit logging service
            await audit_logger.log_event(
                event_type=event_type,
                event_category=AuditEventCategory.DATA_ACCESS,
                description=audit_data.get("event_description", "API access"),
                user_id=audit_data.get("user_id"),
                resource_type=audit_data.get("resource_type"),
                resource_id=audit_data.get("resource_id"),
                ip_address=audit_data.get("ip_address"),
                user_agent=audit_data.get("user_agent"),
                request_id=audit_data.get("request_id"),
                metadata=audit_data.get("metadata", {})
            )
            
        except Exception as e:
            logger.error("Failed to store audit log", error=str(e), audit_data=audit_data)

# Middleware factory functions
def create_security_middleware() -> SecurityMiddleware:
    """Create configured security middleware"""
    return SecurityMiddleware

def create_rate_limit_middleware() -> RateLimitMiddleware:
    """Create configured rate limit middleware"""
    return RateLimitMiddleware

def create_logging_middleware() -> LoggingMiddleware:
    """Create configured logging middleware"""
    return LoggingMiddleware

def create_metrics_middleware() -> MetricsMiddleware:
    """Create configured metrics middleware"""
    return MetricsMiddleware

def create_audit_middleware() -> AuditMiddleware:
    """Create configured audit middleware"""
    return AuditMiddleware