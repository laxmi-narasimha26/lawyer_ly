#!/usr/bin/env python3
"""
Security Setup Script for Indian Legal AI Assistant
Initializes security services and validates configuration
"""
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import structlog
from config import settings
from services.azure_key_vault_service import key_vault_service
from services.encryption_service import encryption_service
from services.compliance_service import compliance_service
from services.audit_logging_service import audit_logger

logger = structlog.get_logger(__name__)

async def setup_azure_key_vault():
    """Set up Azure Key Vault with initial secrets"""
    try:
        logger.info("Setting up Azure Key Vault...")
        
        # Check Key Vault connectivity
        health_status = await key_vault_service.health_check()
        if health_status["status"] != "healthy":
            logger.error("Key Vault health check failed", status=health_status)
            return False
        
        # Set up initial secrets
        await key_vault_service.setup_initial_secrets()
        
        logger.info("Azure Key Vault setup completed successfully")
        return True
        
    except Exception as e:
        logger.error("Azure Key Vault setup failed", error=str(e))
        return False

async def setup_encryption_service():
    """Set up encryption service and validate keys"""
    try:
        logger.info("Setting up encryption service...")
        
        # Get encryption status
        status = encryption_service.get_encryption_status()
        logger.info("Encryption service status", status=status)
        
        # Test encryption/decryption
        test_data = "test_encryption_data"
        encrypted = encryption_service.encrypt_user_data(test_data)
        decrypted = encryption_service.decrypt_user_data(encrypted)
        
        if decrypted != test_data:
            logger.error("Encryption test failed")
            return False
        
        logger.info("Encryption service setup completed successfully")
        return True
        
    except Exception as e:
        logger.error("Encryption service setup failed", error=str(e))
        return False

async def setup_compliance_service():
    """Set up compliance service and validate configuration"""
    try:
        logger.info("Setting up compliance service...")
        
        # Get compliance status
        status = await compliance_service.get_compliance_status()
        logger.info("Compliance service status", status=status)
        
        # Validate data residency
        current_region = os.getenv("AZURE_REGION", "unknown")
        is_compliant = await compliance_service.validate_data_residency(current_region)
        
        if not is_compliant:
            logger.warning("Data residency compliance issue", region=current_region)
        
        logger.info("Compliance service setup completed successfully")
        return True
        
    except Exception as e:
        logger.error("Compliance service setup failed", error=str(e))
        return False

async def setup_audit_logging():
    """Set up audit logging service"""
    try:
        logger.info("Setting up audit logging service...")
        
        # Test audit logging
        await audit_logger.log_event(
            event_type=audit_logger.AuditEventType.SYSTEM_CONFIG_CHANGE,
            event_category=audit_logger.AuditEventCategory.SYSTEM_ADMINISTRATION,
            description="Security setup script executed",
            resource_type="security_setup",
            metadata={"setup_timestamp": "test"}
        )
        
        logger.info("Audit logging service setup completed successfully")
        return True
        
    except Exception as e:
        logger.error("Audit logging service setup failed", error=str(e))
        return False

async def validate_security_configuration():
    """Validate overall security configuration"""
    try:
        logger.info("Validating security configuration...")
        
        validation_results = {
            "https_enabled": settings.security.force_https,
            "encryption_enabled": settings.security.enable_data_encryption,
            "security_headers_enabled": settings.security.enable_security_headers,
            "key_vault_configured": bool(settings.security.azure_key_vault_url),
            "data_residency_enforced": compliance_service.data_residency_required,
            "audit_logging_enabled": True,
            "input_validation_enabled": True
        }
        
        # Check for missing configurations
        missing_configs = []
        
        if not settings.security.azure_key_vault_url:
            missing_configs.append("Azure Key Vault URL")
        
        if not os.getenv("MASTER_ENCRYPTION_KEY"):
            missing_configs.append("Master encryption key")
        
        if missing_configs:
            logger.warning("Missing security configurations", missing=missing_configs)
        
        # Security recommendations
        recommendations = []
        
        if not settings.security.force_https:
            recommendations.append("Enable HTTPS enforcement")
        
        if not settings.security.enable_security_headers:
            recommendations.append("Enable security headers")
        
        if settings.security.encryption_key_rotation_days > 90:
            recommendations.append("Consider shorter key rotation period")
        
        validation_summary = {
            "validation_results": validation_results,
            "missing_configurations": missing_configs,
            "recommendations": recommendations,
            "overall_status": "secure" if not missing_configs else "needs_attention"
        }
        
        logger.info("Security configuration validation completed", summary=validation_summary)
        return validation_summary
        
    except Exception as e:
        logger.error("Security configuration validation failed", error=str(e))
        return {"overall_status": "error", "error": str(e)}

async def main():
    """Main setup function"""
    logger.info("Starting security setup for Indian Legal AI Assistant")
    
    setup_results = {}
    
    # Set up services
    setup_results["key_vault"] = await setup_azure_key_vault()
    setup_results["encryption"] = await setup_encryption_service()
    setup_results["compliance"] = await setup_compliance_service()
    setup_results["audit_logging"] = await setup_audit_logging()
    
    # Validate configuration
    validation_results = await validate_security_configuration()
    setup_results["validation"] = validation_results
    
    # Summary
    successful_setups = sum(1 for result in setup_results.values() if result is True)
    total_setups = len([k for k in setup_results.keys() if k != "validation"])
    
    logger.info(
        "Security setup completed",
        successful_setups=successful_setups,
        total_setups=total_setups,
        validation_status=validation_results.get("overall_status", "unknown")
    )
    
    if successful_setups == total_setups and validation_results.get("overall_status") == "secure":
        logger.info("✅ Security setup completed successfully - System is secure")
        return 0
    else:
        logger.warning("⚠️  Security setup completed with issues - Review configuration")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())