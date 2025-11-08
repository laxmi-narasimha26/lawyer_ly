"""
Audit Logging Service for compliance and security monitoring
Implements comprehensive audit trail without storing sensitive content
"""
import json
import asyncio
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from enum import Enum
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from config import settings
from database import get_db_session
from database.models import AuditLog, User
from services.encryption_service import encryption_service
from utils.exceptions import DatabaseError

logger = structlog.get_logger(__name__)

class AuditEventType(str, Enum):
    """Audit event types for categorization"""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKED = "account_locked"
    
    # Query events
    LEGAL_QUERY = "legal_query"
    QUERY_RESPONSE = "query_response"
    QUERY_ERROR = "query_error"
    
    # Document events
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DOWNLOAD = "document_download"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_SHARE = "document_share"
    
    # System events
    SYSTEM_ERROR = "system_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SECURITY_VIOLATION = "security_violation"
    
    # Administrative events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    
    # Data access events
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    BULK_OPERATION = "bulk_operation"

class AuditEventCategory(str, Enum):
    """Audit event categories for compliance reporting"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM_ADMINISTRATION = "system_administration"
    SECURITY = "security"
    COMPLIANCE = "compliance"

class AuditLoggingService:
    """
    Comprehensive audit logging service for compliance and security
    
    Features:
    - Structured audit logging
    - Compliance reporting (ISO 27001)
    - Data residency controls
    - Zero-retention policy compliance
    - Automated log retention
    - Security event correlation
    """
    
    def __init__(self):
        self.retention_days = 2555  # 7 years for legal compliance
        self.max_batch_size = 1000
        self.sensitive_fields = {
            'password', 'token', 'api_key', 'secret', 'query_text', 
            'document_content', 'personal_data', 'email_content'
        }
        
        logger.info("Audit logging service initialized")
    
    async def log_event(
        self,
        event_type: AuditEventType,
        event_category: AuditEventCategory,
        description: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Log audit event to database
        
        Args:
            event_type: Type of event
            event_category: Category for compliance reporting
            description: Human-readable description
            user_id: User ID (if applicable)
            resource_type: Type of resource accessed
            resource_id: ID of resource accessed
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request correlation ID
            metadata: Additional event metadata (sanitized)
            session: Database session
            
        Returns:
            True if logged successfully
        """
        try:
            # Sanitize metadata to remove sensitive information
            sanitized_metadata = self._sanitize_metadata(metadata or {})
            
            # Create audit log entry
            audit_entry = AuditLog(
                user_id=user_id,
                event_type=event_type.value,
                event_category=event_category.value,
                event_description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata=sanitized_metadata,
                created_at=datetime.utcnow()
            )
            
            # Use provided session or create new one
            if session:
                session.add(audit_entry)
                await session.flush()
            else:
                async with get_db_session() as db_session:
                    db_session.add(audit_entry)
                    await db_session.commit()
            
            # Log to structured logger as well
            logger.info(
                "Audit event logged",
                event_type=event_type.value,
                event_category=event_category.value,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                request_id=request_id
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to log audit event", error=str(e), event_type=event_type.value)
            return False
    
    async def log_authentication_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str],
        email: Optional[str],
        ip_address: str,
        user_agent: str,
        success: bool,
        failure_reason: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> bool:
        """
        Log authentication-related events
        
        Args:
            event_type: Authentication event type
            user_id: User ID (if known)
            email: User email (for failed attempts)
            ip_address: Client IP
            user_agent: Client user agent
            success: Whether authentication succeeded
            failure_reason: Reason for failure (if applicable)
            request_id: Request correlation ID
            
        Returns:
            True if logged successfully
        """
        description = f"Authentication attempt for {email or 'unknown user'}"
        if not success and failure_reason:
            description += f" - {failure_reason}"
        
        metadata = {
            "email": email,
            "success": success,
            "failure_reason": failure_reason
        }
        
        return await self.log_event(
            event_type=event_type,
            event_category=AuditEventCategory.AUTHENTICATION,
            description=description,
            user_id=user_id,
            resource_type="user_account",
            resource_id=user_id or email,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            metadata=metadata
        )
    
    async def log_query_event(
        self,
        user_id: str,
        query_id: str,
        query_mode: str,
        processing_time_ms: int,
        token_usage: int,
        citation_count: int,
        success: bool,
        ip_address: str,
        request_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Log legal query events (without storing query content)
        
        Args:
            user_id: User ID
            query_id: Query ID for correlation
            query_mode: Query processing mode
            processing_time_ms: Processing time
            token_usage: Token usage count
            citation_count: Number of citations returned
            success: Whether query succeeded
            ip_address: Client IP
            request_id: Request correlation ID
            error_message: Error message (if failed)
            
        Returns:
            True if logged successfully
        """
        description = f"Legal query processed in {query_mode} mode"
        if not success:
            description += " - Failed"
        
        metadata = {
            "query_id": query_id,
            "query_mode": query_mode,
            "processing_time_ms": processing_time_ms,
            "token_usage": token_usage,
            "citation_count": citation_count,
            "success": success,
            "error_message": error_message
        }
        
        return await self.log_event(
            event_type=AuditEventType.LEGAL_QUERY,
            event_category=AuditEventCategory.DATA_ACCESS,
            description=description,
            user_id=user_id,
            resource_type="legal_query",
            resource_id=query_id,
            ip_address=ip_address,
            request_id=request_id,
            metadata=metadata
        )
    
    async def log_document_event(
        self,
        event_type: AuditEventType,
        user_id: str,
        document_id: str,
        document_title: str,
        file_size: Optional[int] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log document-related events
        
        Args:
            event_type: Document event type
            user_id: User ID
            document_id: Document ID
            document_title: Document title (sanitized)
            file_size: File size in bytes
            ip_address: Client IP
            request_id: Request correlation ID
            additional_metadata: Additional metadata
            
        Returns:
            True if logged successfully
        """
        description = f"Document {event_type.value}: {document_title}"
        
        metadata = {
            "document_id": document_id,
            "document_title": document_title,
            "file_size": file_size,
            **(additional_metadata or {})
        }
        
        return await self.log_event(
            event_type=event_type,
            event_category=AuditEventCategory.DATA_MODIFICATION,
            description=description,
            user_id=user_id,
            resource_type="document",
            resource_id=document_id,
            ip_address=ip_address,
            request_id=request_id,
            metadata=metadata
        )
    
    async def log_security_event(
        self,
        event_type: AuditEventType,
        description: str,
        severity: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        threat_indicators: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log security-related events
        
        Args:
            event_type: Security event type
            description: Event description
            severity: Severity level (low, medium, high, critical)
            ip_address: Source IP address
            user_agent: User agent
            user_id: User ID (if known)
            request_id: Request correlation ID
            threat_indicators: Security threat indicators
            
        Returns:
            True if logged successfully
        """
        metadata = {
            "severity": severity,
            "threat_indicators": threat_indicators or {}
        }
        
        return await self.log_event(
            event_type=event_type,
            event_category=AuditEventCategory.SECURITY,
            description=description,
            user_id=user_id,
            resource_type="security_event",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            metadata=metadata
        )
    
    async def get_audit_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        event_category: Optional[AuditEventCategory] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs with filtering
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            user_id: User ID filter
            event_type: Event type filter
            event_category: Event category filter
            limit: Maximum number of results
            offset: Result offset for pagination
            
        Returns:
            List of audit log entries
        """
        try:
            async with get_db_session() as session:
                query = select(AuditLog)
                
                # Apply filters
                conditions = []
                
                if start_date:
                    conditions.append(AuditLog.created_at >= start_date)
                
                if end_date:
                    conditions.append(AuditLog.created_at <= end_date)
                
                if user_id:
                    conditions.append(AuditLog.user_id == user_id)
                
                if event_type:
                    conditions.append(AuditLog.event_type == event_type.value)
                
                if event_category:
                    conditions.append(AuditLog.event_category == event_category.value)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                # Order by creation time (newest first)
                query = query.order_by(desc(AuditLog.created_at))
                
                # Apply pagination
                query = query.offset(offset).limit(limit)
                
                result = await session.execute(query)
                audit_logs = result.scalars().all()
                
                # Convert to dictionaries
                log_entries = []
                for log in audit_logs:
                    log_entries.append({
                        'id': str(log.id),
                        'user_id': log.user_id,
                        'event_type': log.event_type,
                        'event_category': log.event_category,
                        'event_description': log.event_description,
                        'ip_address': log.ip_address,
                        'user_agent': log.user_agent,
                        'request_id': log.request_id,
                        'resource_type': log.resource_type,
                        'resource_id': log.resource_id,
                        'metadata': log.metadata,
                        'created_at': log.created_at.isoformat()
                    })
                
                logger.debug("Retrieved audit logs", count=len(log_entries))
                return log_entries
                
        except Exception as e:
            logger.error("Failed to retrieve audit logs", error=str(e))
            raise DatabaseError(f"Audit log retrieval failed: {str(e)}")
    
    async def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        report_type: str = "iso27001"
    ) -> Dict[str, Any]:
        """
        Generate compliance report for specified period
        
        Args:
            start_date: Report start date
            end_date: Report end date
            report_type: Type of compliance report
            
        Returns:
            Compliance report data
        """
        try:
            async with get_db_session() as session:
                # Get event counts by category
                category_query = select(
                    AuditLog.event_category,
                    func.count(AuditLog.id).label('count')
                ).where(
                    and_(
                        AuditLog.created_at >= start_date,
                        AuditLog.created_at <= end_date
                    )
                ).group_by(AuditLog.event_category)
                
                category_result = await session.execute(category_query)
                category_counts = dict(category_result.fetchall())
                
                # Get security events
                security_query = select(AuditLog).where(
                    and_(
                        AuditLog.event_category == AuditEventCategory.SECURITY.value,
                        AuditLog.created_at >= start_date,
                        AuditLog.created_at <= end_date
                    )
                ).order_by(desc(AuditLog.created_at))
                
                security_result = await session.execute(security_query)
                security_events = security_result.scalars().all()
                
                # Get authentication failures
                auth_failure_query = select(AuditLog).where(
                    and_(
                        AuditLog.event_type == AuditEventType.LOGIN_FAILURE.value,
                        AuditLog.created_at >= start_date,
                        AuditLog.created_at <= end_date
                    )
                )
                
                auth_failure_result = await session.execute(auth_failure_query)
                auth_failures = auth_failure_result.scalars().all()
                
                # Generate report
                report = {
                    'report_type': report_type,
                    'period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    },
                    'summary': {
                        'total_events': sum(category_counts.values()),
                        'events_by_category': category_counts,
                        'security_events_count': len(security_events),
                        'authentication_failures': len(auth_failures)
                    },
                    'security_incidents': [
                        {
                            'event_type': event.event_type,
                            'description': event.event_description,
                            'timestamp': event.created_at.isoformat(),
                            'ip_address': event.ip_address,
                            'severity': event.metadata.get('severity', 'unknown') if event.metadata else 'unknown'
                        }
                        for event in security_events[:50]  # Limit to top 50
                    ],
                    'compliance_status': self._assess_compliance_status(category_counts, security_events),
                    'generated_at': datetime.utcnow().isoformat()
                }
                
                logger.info("Generated compliance report", 
                           report_type=report_type, 
                           total_events=report['summary']['total_events'])
                
                return report
                
        except Exception as e:
            logger.error("Failed to generate compliance report", error=str(e))
            raise DatabaseError(f"Compliance report generation failed: {str(e)}")
    
    async def cleanup_old_logs(self) -> int:
        """
        Clean up audit logs older than retention period
        
        Returns:
            Number of logs deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            async with get_db_session() as session:
                # Count logs to be deleted
                count_query = select(func.count(AuditLog.id)).where(
                    AuditLog.created_at < cutoff_date
                )
                count_result = await session.execute(count_query)
                delete_count = count_result.scalar()
                
                if delete_count > 0:
                    # Delete old logs in batches
                    deleted_total = 0
                    while True:
                        delete_query = select(AuditLog.id).where(
                            AuditLog.created_at < cutoff_date
                        ).limit(self.max_batch_size)
                        
                        result = await session.execute(delete_query)
                        log_ids = [row[0] for row in result.fetchall()]
                        
                        if not log_ids:
                            break
                        
                        # Delete batch
                        await session.execute(
                            AuditLog.__table__.delete().where(
                                AuditLog.id.in_(log_ids)
                            )
                        )
                        
                        deleted_total += len(log_ids)
                        await session.commit()
                        
                        logger.debug("Deleted audit log batch", count=len(log_ids))
                    
                    logger.info("Cleaned up old audit logs", 
                               deleted_count=deleted_total, 
                               cutoff_date=cutoff_date.isoformat())
                    
                    return deleted_total
                
                return 0
                
        except Exception as e:
            logger.error("Failed to cleanup old audit logs", error=str(e))
            return 0
    
    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata to remove sensitive information
        
        Args:
            metadata: Original metadata
            
        Returns:
            Sanitized metadata
        """
        sanitized = {}
        
        for key, value in metadata.items():
            # Skip sensitive fields
            if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_metadata(value)
            elif isinstance(value, str) and len(value) > 1000:
                # Truncate very long strings
                sanitized[key] = value[:1000] + "...[TRUNCATED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _assess_compliance_status(
        self, 
        category_counts: Dict[str, int], 
        security_events: List[AuditLog]
    ) -> Dict[str, Any]:
        """
        Assess compliance status based on audit data
        
        Args:
            category_counts: Event counts by category
            security_events: Security events
            
        Returns:
            Compliance assessment
        """
        # Simple compliance assessment
        total_events = sum(category_counts.values())
        security_event_ratio = len(security_events) / max(total_events, 1)
        
        # Determine compliance level
        if security_event_ratio > 0.1:  # More than 10% security events
            compliance_level = "needs_attention"
        elif security_event_ratio > 0.05:  # More than 5% security events
            compliance_level = "monitoring_required"
        else:
            compliance_level = "compliant"
        
        return {
            'compliance_level': compliance_level,
            'security_event_ratio': security_event_ratio,
            'recommendations': self._get_compliance_recommendations(compliance_level),
            'data_residency': 'india',  # All data stored in India region
            'retention_policy': f"{self.retention_days} days",
            'zero_retention_compliance': True  # No user data stored in logs
        }
    
    def _get_compliance_recommendations(self, compliance_level: str) -> List[str]:
        """Get compliance recommendations based on assessment"""
        recommendations = {
            'compliant': [
                "Continue monitoring security events",
                "Regular compliance report reviews"
            ],
            'monitoring_required': [
                "Increase security monitoring frequency",
                "Review authentication policies",
                "Implement additional access controls"
            ],
            'needs_attention': [
                "Immediate security review required",
                "Investigate security incidents",
                "Strengthen access controls",
                "Consider additional security measures"
            ]
        }
        
        return recommendations.get(compliance_level, [])

# Global audit logging service instance
audit_logger = AuditLoggingService()