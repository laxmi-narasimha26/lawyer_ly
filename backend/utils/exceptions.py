"""
Custom exceptions for the Indian Legal AI Assistant
Production-grade error handling with comprehensive error types
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

class LegalAIException(Exception):
    """Base exception for Legal AI application"""
    
    def __init__(
        self,
        message: str,
        error_type: str = "legal_ai_error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class AuthenticationError(LegalAIException):
    """Authentication related errors"""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="authentication_error",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details
        )

class AuthorizationError(LegalAIException):
    """Authorization related errors"""
    
    def __init__(self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="authorization_error",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details
        )

class ValidationError(LegalAIException):
    """Input validation errors"""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if field:
            error_details["field"] = field
            
        super().__init__(
            message=message,
            error_type="validation_error",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=error_details
        )

class ProcessingError(LegalAIException):
    """Document or query processing errors"""
    
    def __init__(self, message: str, processing_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if processing_type:
            error_details["processing_type"] = processing_type
            
        super().__init__(
            message=message,
            error_type="processing_error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=error_details
        )

class RateLimitExceeded(LegalAIException):
    """Rate limiting errors"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        error_details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            error_type="rate_limit_exceeded",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=error_details
        )
        
        self.retry_after = retry_after

class SecurityViolation(LegalAIException):
    """Security related violations"""
    
    def __init__(self, message: str, violation_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if violation_type:
            error_details["violation_type"] = violation_type
            
        super().__init__(
            message=message,
            error_type="security_violation",
            status_code=status.HTTP_403_FORBIDDEN,
            details=error_details
        )

class DocumentError(LegalAIException):
    """Document related errors"""
    
    def __init__(self, message: str, document_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if document_id:
            error_details["document_id"] = document_id
            
        super().__init__(
            message=message,
            error_type="document_error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=error_details
        )

class VectorSearchError(LegalAIException):
    """Vector search related errors"""
    
    def __init__(self, message: str, query: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if query:
            error_details["query"] = query[:100]  # Truncate for logging
            
        super().__init__(
            message=message,
            error_type="vector_search_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=error_details
        )

class LLMError(LegalAIException):
    """Large Language Model related errors"""
    
    def __init__(self, message: str, model: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if model:
            error_details["model"] = model
            
        super().__init__(
            message=message,
            error_type="llm_error",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=error_details
        )

class CacheError(LegalAIException):
    """Cache related errors"""
    
    def __init__(self, message: str, cache_key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if cache_key:
            error_details["cache_key"] = cache_key
            
        super().__init__(
            message=message,
            error_type="cache_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=error_details
        )

class DatabaseError(LegalAIException):
    """Database related errors"""
    
    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
            
        super().__init__(
            message=message,
            error_type="database_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=error_details
        )

class ExternalServiceError(LegalAIException):
    """External service related errors"""
    
    def __init__(self, message: str, service: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if service:
            error_details["service"] = service
            
        super().__init__(
            message=message,
            error_type="external_service_error",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=error_details
        )

class ConfigurationError(LegalAIException):
    """Configuration related errors"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key
            
        super().__init__(
            message=message,
            error_type="configuration_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=error_details
        )

class QuotaExceededError(LegalAIException):
    """Quota or limit exceeded errors"""
    
    def __init__(self, message: str, quota_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if quota_type:
            error_details["quota_type"] = quota_type
            
        super().__init__(
            message=message,
            error_type="quota_exceeded",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=error_details
        )

class MaintenanceError(LegalAIException):
    """System maintenance related errors"""
    
    def __init__(self, message: str = "System is under maintenance", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="maintenance_error",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details
        )

# Utility functions for error handling
def create_http_exception(
    status_code: int,
    message: str,
    error_type: str = "error",
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """Create HTTPException with consistent format"""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": error_type,
            "message": message,
            "details": details or {}
        }
    )

def handle_database_error(error: Exception) -> DatabaseError:
    """Convert database errors to DatabaseError"""
    error_message = str(error)
    
    # Common database error patterns
    if "connection" in error_message.lower():
        return DatabaseError("Database connection failed", operation="connect")
    elif "timeout" in error_message.lower():
        return DatabaseError("Database operation timed out", operation="query")
    elif "constraint" in error_message.lower():
        return DatabaseError("Database constraint violation", operation="insert/update")
    else:
        return DatabaseError(f"Database error: {error_message}")

def handle_external_service_error(error: Exception, service: str) -> ExternalServiceError:
    """Convert external service errors to ExternalServiceError"""
    error_message = str(error)
    
    # Common service error patterns
    if "timeout" in error_message.lower():
        return ExternalServiceError(f"{service} service timeout", service=service)
    elif "connection" in error_message.lower():
        return ExternalServiceError(f"Failed to connect to {service}", service=service)
    elif "rate limit" in error_message.lower():
        return ExternalServiceError(f"{service} rate limit exceeded", service=service)
    else:
        return ExternalServiceError(f"{service} error: {error_message}", service=service)

def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable"""
    retryable_errors = [
        ExternalServiceError,
        DatabaseError,
        CacheError
    ]
    
    # Check if error type is retryable
    if any(isinstance(error, error_type) for error_type in retryable_errors):
        # Check specific error conditions
        error_message = str(error).lower()
        
        # Don't retry authentication or validation errors
        if any(keyword in error_message for keyword in ["auth", "permission", "validation", "constraint"]):
            return False
        
        # Retry timeouts and connection errors
        if any(keyword in error_message for keyword in ["timeout", "connection", "network"]):
            return True
    
    return False

def get_retry_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate exponential backoff delay"""
    delay = base_delay * (2 ** attempt)
    return min(delay, max_delay)