"""
Compliance and Security Management API endpoints
Provides access to compliance reports and security controls
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from config import settings
from database import get_db_session
from database.models import User
from api.auth import get_current_user, require_role
from services.compliance_service import compliance_service, ComplianceFramework
from services.audit_logging_service import audit_logger, AuditEventType, AuditEventCategory
from services.azure_key_vault_service import key_vault_service
from services.encryption_service import encryption_service
from utils.exceptions import ValidationError, AuthorizationError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/compliance", tags=["compliance"])

@router.get("/status")
async def get_compliance_status(
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, Any]:
    """
    Get overall compliance status
    
    Requires admin role
    """
    try:
        status_info = await compliance_service.get_compliance_status()
        
        # Log access to compliance information
        await audit_logger.log_event(
            event_type=AuditEventType.DATA_EXPORT,
            event_category=AuditEventCategory.COMPLIANCE,
            description="Compliance status accessed",
            user_id=str(current_user.id),
            resource_type="compliance_status",
            metadata={"accessed_by": current_user.email}
        )
        
        return status_info
        
    except Exception as e:
        logger.error("Failed to get compliance status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compliance status"
        )

@router.get("/reports/iso27001")
async def generate_iso27001_report(
    start_date: datetime = Query(..., description="Report start date"),
    end_date: datetime = Query(..., description="Report end date"),
    current_user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Generate ISO 27001 compliance report
    
    Requires admin role
    """
    try:
        # Validate date range
        if end_date <= start_date:
            raise ValidationError("End date must be after start date")
        
        if (end_date - start_date).days > 365:
            raise ValidationError("Report period cannot exceed 365 days")
        
        # Generate report
        report = await compliance_service.generate_iso27001_report(start_date, end_date)
        
        # Log report generation
        await audit_logger.log_event(
            event_type=AuditEventType.DATA_EXPORT,
            event_category=AuditEventCategory.COMPLIANCE,
            description="ISO 27001 compliance report generated",
            user_id=str(current_user.id),
            resource_type="compliance_report",
            metadata={
                "report_type": "iso27001",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "generated_by": current_user.email
            }
        )
        
        return report
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error("Failed to generate ISO 27001 report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance report"
        )

@router.get("/audit-logs")
async def get_audit_logs(
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    event_type: Optional[str] = Query(None, description="Event type filter"),
    user_id: Optional[str] = Query(None, description="User ID filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, Any]:
    """
    Retrieve audit logs with filtering
    
    Requires admin role
    """
    try:
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Convert event type string to enum if provided
        event_type_enum = None
        if event_type:
            try:
                event_type_enum = AuditEventType(event_type)
            except ValueError:
                raise ValidationError(f"Invalid event type: {event_type}")
        
        # Retrieve audit logs
        logs = await audit_logger.get_audit_logs(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            event_type=event_type_enum,
            limit=limit,
            offset=offset
        )
        
        # Log audit log access
        await audit_logger.log_event(
            event_type=AuditEventType.DATA_EXPORT,
            event_category=AuditEventCategory.COMPLIANCE,
            description="Audit logs accessed",
            user_id=str(current_user.id),
            resource_type="audit_logs",
            metadata={
                "filters": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "event_type": event_type,
                    "user_id": user_id,
                    "limit": limit,
                    "offset": offset
                },
                "accessed_by": current_user.email,
                "result_count": len(logs)
            }
        )
        
        return {
            "logs": logs,
            "total_count": len(logs),
            "filters": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "event_type": event_type,
                "user_id": user_id
            },
            "pagination": {
                "limit": limit,
                "offset": offset
            }
        }
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error("Failed to retrieve audit logs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs"
        )

@router.post("/data-residency/validate")
async def validate_data_residency(
    resource_location: str,
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, Any]:
    """
    Validate data residency compliance
    
    Requires admin role
    """
    try:
        is_compliant = await compliance_service.validate_data_residency(resource_location)
        
        result = {
            "resource_location": resource_location,
            "is_compliant": is_compliant,
            "allowed_regions": compliance_service.allowed_regions,
            "validation_timestamp": datetime.utcnow().isoformat()
        }
        
        # Log validation
        await audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_CONFIG_CHANGE,
            event_category=AuditEventCategory.COMPLIANCE,
            description="Data residency validation performed",
            user_id=str(current_user.id),
            resource_type="data_residency",
            resource_id=resource_location,
            metadata=result
        )
        
        return result
        
    except Exception as e:
        logger.error("Data residency validation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data residency validation failed"
        )

@router.post("/privacy/validate/{user_id}")
async def validate_privacy_controls(
    user_id: str,
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, Any]:
    """
    Validate privacy controls for a specific user
    
    Requires admin role
    """
    try:
        validation_results = await compliance_service.validate_privacy_controls(user_id)
        
        # Log privacy validation
        await audit_logger.log_event(
            event_type=AuditEventType.DATA_EXPORT,
            event_category=AuditEventCategory.COMPLIANCE,
            description="Privacy controls validated",
            user_id=str(current_user.id),
            resource_type="privacy_controls",
            resource_id=user_id,
            metadata={
                "target_user_id": user_id,
                "validation_status": validation_results.get("overall_status"),
                "validated_by": current_user.email
            }
        )
        
        return validation_results
        
    except Exception as e:
        logger.error("Privacy control validation failed", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Privacy control validation failed"
        )

@router.post("/zero-retention/enforce/{user_id}")
async def enforce_zero_retention(
    user_id: str,
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, Any]:
    """
    Enforce zero-retention policy for a user
    
    Requires admin role
    """
    try:
        enforcement_results = await compliance_service.enforce_zero_retention_policy(user_id)
        
        # Log enforcement
        await audit_logger.log_event(
            event_type=AuditEventType.DATA_EXPORT,
            event_category=AuditEventCategory.COMPLIANCE,
            description="Zero-retention policy enforced",
            user_id=str(current_user.id),
            resource_type="zero_retention",
            resource_id=user_id,
            metadata={
                "target_user_id": user_id,
                "enforcement_results": enforcement_results,
                "enforced_by": current_user.email
            }
        )
        
        return enforcement_results
        
    except Exception as e:
        logger.error("Zero-retention enforcement failed", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Zero-retention enforcement failed"
        )

@router.get("/encryption/status")
async def get_encryption_status(
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, Any]:
    """
    Get encryption service status
    
    Requires admin role
    """
    try:
        encryption_status = encryption_service.get_encryption_status()
        
        # Add Key Vault status
        key_vault_status = await key_vault_service.health_check()
        
        status_info = {
            "encryption_service": encryption_status,
            "key_vault_service": key_vault_status,
            "data_encryption": {
                "at_rest": True,
                "in_transit": True,
                "key_rotation_enabled": True
            }
        }
        
        # Log status access
        await audit_logger.log_event(
            event_type=AuditEventType.DATA_EXPORT,
            event_category=AuditEventCategory.SECURITY,
            description="Encryption status accessed",
            user_id=str(current_user.id),
            resource_type="encryption_status",
            metadata={"accessed_by": current_user.email}
        )
        
        return status_info
        
    except Exception as e:
        logger.error("Failed to get encryption status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve encryption status"
        )

@router.post("/encryption/rotate-keys")
async def rotate_encryption_keys(
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, Any]:
    """
    Rotate encryption keys
    
    Requires admin role
    """
    try:
        success = encryption_service.rotate_encryption_keys()
        
        result = {
            "success": success,
            "rotation_timestamp": datetime.utcnow().isoformat(),
            "rotated_by": current_user.email
        }
        
        # Log key rotation
        await audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_CONFIG_CHANGE,
            event_category=AuditEventCategory.SECURITY,
            description="Encryption keys rotated",
            user_id=str(current_user.id),
            resource_type="encryption_keys",
            metadata=result
        )
        
        return result
        
    except Exception as e:
        logger.error("Key rotation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Key rotation failed"
        )

@router.post("/audit/cleanup")
async def cleanup_old_audit_logs(
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, Any]:
    """
    Clean up old audit logs according to retention policy
    
    Requires admin role
    """
    try:
        deleted_count = await audit_logger.cleanup_old_logs()
        
        result = {
            "deleted_count": deleted_count,
            "cleanup_timestamp": datetime.utcnow().isoformat(),
            "performed_by": current_user.email
        }
        
        # Log cleanup operation
        await audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_ADMINISTRATION,
            event_category=AuditEventCategory.SYSTEM_ADMINISTRATION,
            description="Audit log cleanup performed",
            user_id=str(current_user.id),
            resource_type="audit_logs",
            metadata=result
        )
        
        return result
        
    except Exception as e:
        logger.error("Audit log cleanup failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audit log cleanup failed"
        )

@router.get("/frameworks")
async def get_supported_frameworks(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get supported compliance frameworks
    """
    return {
        "supported_frameworks": [
            {
                "name": "ISO 27001:2013",
                "code": "iso27001",
                "description": "Information Security Management System"
            },
            {
                "name": "India Data Protection",
                "code": "india_data_protection", 
                "description": "Indian data protection and privacy requirements"
            }
        ],
        "data_residency": {
            "required": compliance_service.data_residency_required,
            "allowed_regions": compliance_service.allowed_regions
        },
        "retention_policies": compliance_service.retention_policies
    }