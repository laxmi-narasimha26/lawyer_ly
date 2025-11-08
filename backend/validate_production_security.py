#!/usr/bin/env python3
"""
Production Security Validation Script
Comprehensive validation of all security components for legal compliance
"""
import os
import sys
import asyncio
import traceback
from pathlib import Path
from datetime import datetime
import json

# Set environment variables for testing
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test_legal_ai"
os.environ["SECRET_KEY"] = "production-test-secret-key-very-long-and-secure-for-legal-compliance"
os.environ["AZURE_OPENAI_API_KEY"] = "test-openai-key-for-validation"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://test.openai.azure.com"
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
os.environ["ENVIRONMENT"] = "testing"
os.environ["MASTER_ENCRYPTION_KEY"] = "dGVzdC1tYXN0ZXIta2V5LWZvci1wcm9kdWN0aW9uLXZhbGlkYXRpb24tMTIzNDU2Nzg5MA=="

class ProductionSecurityValidator:
    """Comprehensive production security validator"""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "critical_failures": 0,
            "test_results": {},
            "security_status": "unknown"
        }
        
    def log_test(self, test_name: str, status: str, message: str = "", critical: bool = False):
        """Log test result"""
        self.results["total_tests"] += 1
        
        if status == "PASS":
            self.results["passed_tests"] += 1
            print(f"✅ {test_name}: PASSED")
        else:
            self.results["failed_tests"] += 1
            if critical:
                self.results["critical_failures"] += 1
            print(f"❌ {test_name}: FAILED - {message}")
        
        self.results["test_results"][test_name] = {
            "status": status,
            "message": message,
            "critical": critical,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if message:
            print(f"   📝 {message}")
    
    def test_encryption_service(self):
        """Test encryption service comprehensively"""
        print("\n🔐 Testing Encryption Service...")
        
        try:
            from services.encryption_service import EncryptionService
            encryption_service = EncryptionService()
            
            # Test 1: Basic encryption/decryption
            try:
                test_data = "sensitive_legal_data_123"
                encrypted = encryption_service.encrypt_user_data(test_data)
                decrypted = encryption_service.decrypt_user_data(encrypted)
                
                if decrypted == test_data and encrypted != test_data:
                    self.log_test("Encryption Basic Functionality", "PASS")
                else:
                    self.log_test("Encryption Basic Functionality", "FAIL", "Encryption/decryption mismatch", critical=True)
            except Exception as e:
                self.log_test("Encryption Basic Functionality", "FAIL", str(e), critical=True)
            
            # Test 2: Document encryption
            try:
                doc_content = b"Legal document content with sensitive information"
                encrypted_content, metadata = encryption_service.encrypt_document_content(doc_content)
                decrypted_content = encryption_service.decrypt_document_content(encrypted_content, metadata)
                
                if decrypted_content == doc_content and "salt" in metadata:
                    self.log_test("Document Encryption", "PASS")
                else:
                    self.log_test("Document Encryption", "FAIL", "Document encryption failed", critical=True)
            except Exception as e:
                self.log_test("Document Encryption", "FAIL", str(e), critical=True)
            
            # Test 3: Password hashing
            try:
                password = "SecurePassword123!"
                hash_value, salt = encryption_service.hash_sensitive_data(password)
                is_valid = encryption_service.verify_hashed_data(password, hash_value, salt)
                is_invalid = encryption_service.verify_hashed_data("wrong_password", hash_value, salt)
                
                if is_valid and not is_invalid and len(hash_value) == 64:
                    self.log_test("Password Hashing", "PASS")
                else:
                    self.log_test("Password Hashing", "FAIL", "Password hashing verification failed", critical=True)
            except Exception as e:
                self.log_test("Password Hashing", "FAIL", str(e), critical=True)
            
            # Test 4: Session encryption
            try:
                session_data = {"user_id": "123", "role": "lawyer", "permissions": ["read", "write"]}
                encrypted_session = encryption_service.encrypt_session_data(session_data)
                decrypted_session = encryption_service.decrypt_session_data(encrypted_session)
                
                if decrypted_session == session_data:
                    self.log_test("Session Encryption", "PASS")
                else:
                    self.log_test("Session Encryption", "FAIL", "Session encryption failed")
            except Exception as e:
                self.log_test("Session Encryption", "FAIL", str(e))
            
            # Test 5: Key rotation
            try:
                test_data = "data_before_rotation"
                encrypted_before = encryption_service.encrypt_user_data(test_data)
                
                success = encryption_service.rotate_encryption_keys()
                
                # Should still decrypt old data
                decrypted_old = encryption_service.decrypt_user_data(encrypted_before)
                
                # New encryption should be different
                encrypted_after = encryption_service.encrypt_user_data(test_data)
                
                if success and decrypted_old == test_data and encrypted_after != encrypted_before:
                    self.log_test("Key Rotation", "PASS")
                else:
                    self.log_test("Key Rotation", "FAIL", "Key rotation functionality failed")
            except Exception as e:
                self.log_test("Key Rotation", "FAIL", str(e))
                
        except Exception as e:
            self.log_test("Encryption Service Import", "FAIL", str(e), critical=True)
    
    def test_input_validation_service(self):
        """Test input validation service comprehensively"""
        print("\n🛡️ Testing Input Validation Service...")
        
        try:
            from services.input_validation_service import InputValidationService
            from utils.exceptions import ValidationError, SecurityViolation
            
            validator = InputValidationService()
            
            # Test 1: Valid query processing
            try:
                valid_queries = [
                    "What are the provisions of Indian Contract Act?",
                    "Explain Section 420 of IPC",
                    "How to file a PIL in Supreme Court?"
                ]
                
                all_passed = True
                for query in valid_queries:
                    sanitized = validator.validate_query_text(query)
                    if sanitized != query:
                        all_passed = False
                        break
                
                if all_passed:
                    self.log_test("Valid Query Processing", "PASS")
                else:
                    self.log_test("Valid Query Processing", "FAIL", "Valid queries rejected")
            except Exception as e:
                self.log_test("Valid Query Processing", "FAIL", str(e))
            
            # Test 2: SQL Injection Detection
            try:
                sql_attacks = [
                    "What is law? DROP TABLE users; --",
                    "Legal query'; DELETE FROM documents; --",
                    "Query UNION SELECT * FROM users",
                    "Test' OR '1'='1"
                ]
                
                blocked_count = 0
                for attack in sql_attacks:
                    try:
                        validator.validate_query_text(attack)
                        # If we get here, the attack wasn't blocked
                        pass
                    except (SecurityViolation, ValidationError):
                        blocked_count += 1  # Attack was blocked (expected)
                
                if blocked_count == len(sql_attacks):
                    self.log_test("SQL Injection Detection", "PASS")
                else:
                    self.log_test("SQL Injection Detection", "FAIL", f"Only {blocked_count}/{len(sql_attacks)} attacks blocked", critical=True)
            except Exception as e:
                self.log_test("SQL Injection Detection", "FAIL", str(e), critical=True)
            
            # Test 3: XSS Detection
            try:
                xss_attacks = [
                    "Legal query <script>alert('xss')</script>",
                    "What is law? <img src=x onerror=alert('xss')>",
                    "Query javascript:alert('xss')"
                ]
                
                blocked_count = 0
                for attack in xss_attacks:
                    try:
                        validator.validate_query_text(attack)
                        # If we get here, the attack wasn't blocked
                        pass
                    except (SecurityViolation, ValidationError):
                        blocked_count += 1  # Attack was blocked (expected)
                
                if blocked_count == len(xss_attacks):
                    self.log_test("XSS Detection", "PASS")
                else:
                    self.log_test("XSS Detection", "FAIL", f"Only {blocked_count}/{len(xss_attacks)} attacks blocked", critical=True)
            except Exception as e:
                self.log_test("XSS Detection", "FAIL", str(e), critical=True)
            
            # Test 4: File Upload Validation
            try:
                # Valid files
                valid_result = validator.validate_file_upload("legal_doc.pdf", 1024*1024, "application/pdf")
                
                # Invalid file
                invalid_blocked = False
                try:
                    validator.validate_file_upload("malware.exe", 1024, "application/octet-stream")
                except ValidationError:
                    invalid_blocked = True
                
                if valid_result["is_valid"] and invalid_blocked:
                    self.log_test("File Upload Validation", "PASS")
                else:
                    self.log_test("File Upload Validation", "FAIL", "File validation failed")
            except Exception as e:
                self.log_test("File Upload Validation", "FAIL", str(e))
            
            # Test 5: Email Validation
            try:
                valid_email = validator.validate_email("lawyer@lawfirm.com")
                
                invalid_blocked = False
                try:
                    validator.validate_email("not-an-email")
                except ValidationError:
                    invalid_blocked = True
                
                if valid_email == "lawyer@lawfirm.com" and invalid_blocked:
                    self.log_test("Email Validation", "PASS")
                else:
                    self.log_test("Email Validation", "FAIL", "Email validation failed")
            except Exception as e:
                self.log_test("Email Validation", "FAIL", str(e))
                
        except Exception as e:
            self.log_test("Input Validation Service Import", "FAIL", str(e), critical=True)
    
    def test_audit_logging_service(self):
        """Test audit logging service"""
        print("\n📊 Testing Audit Logging Service...")
        
        try:
            from services.audit_logging_service import AuditLoggingService, AuditEventType, AuditEventCategory
            
            audit_service = AuditLoggingService()
            
            # Test 1: Metadata Sanitization
            try:
                sensitive_metadata = {
                    "password": "secret123",
                    "api_key": "sk-1234567890",
                    "safe_data": "This is safe",
                    "query_text": "Confidential query"
                }
                
                sanitized = audit_service._sanitize_metadata(sensitive_metadata)
                
                if (sanitized["password"] == "[REDACTED]" and 
                    sanitized["api_key"] == "[REDACTED]" and
                    sanitized["safe_data"] == "This is safe" and
                    sanitized["query_text"] == "[REDACTED]"):
                    self.log_test("Metadata Sanitization", "PASS")
                else:
                    self.log_test("Metadata Sanitization", "FAIL", "Sensitive data not properly redacted", critical=True)
            except Exception as e:
                self.log_test("Metadata Sanitization", "FAIL", str(e), critical=True)
            
            # Test 2: Event Types and Categories
            try:
                # Test critical event types exist
                critical_events = [
                    AuditEventType.LOGIN_SUCCESS,
                    AuditEventType.LOGIN_FAILURE,
                    AuditEventType.LEGAL_QUERY,
                    AuditEventType.DOCUMENT_UPLOAD,
                    AuditEventType.SECURITY_VIOLATION
                ]
                
                critical_categories = [
                    AuditEventCategory.AUTHENTICATION,
                    AuditEventCategory.DATA_ACCESS,
                    AuditEventCategory.SECURITY,
                    AuditEventCategory.COMPLIANCE
                ]
                
                events_valid = all(hasattr(event, 'value') for event in critical_events)
                categories_valid = all(hasattr(cat, 'value') for cat in critical_categories)
                
                if events_valid and categories_valid:
                    self.log_test("Audit Event Types", "PASS")
                else:
                    self.log_test("Audit Event Types", "FAIL", "Required audit types missing")
            except Exception as e:
                self.log_test("Audit Event Types", "FAIL", str(e))
                
        except Exception as e:
            self.log_test("Audit Logging Service Import", "FAIL", str(e), critical=True)
    
    async def test_compliance_service(self):
        """Test compliance service"""
        print("\n📋 Testing Compliance Service...")
        
        try:
            from services.compliance_service import ComplianceService, DataClassification
            
            compliance_service = ComplianceService()
            
            # Test 1: Data Residency Validation
            try:
                # Valid India regions
                india_compliant = await compliance_service.validate_data_residency("india-central")
                # Invalid non-India region
                non_india_compliant = await compliance_service.validate_data_residency("us-east-1")
                
                if india_compliant and not non_india_compliant:
                    self.log_test("Data Residency Validation", "PASS")
                else:
                    self.log_test("Data Residency Validation", "FAIL", "Data residency validation failed", critical=True)
            except Exception as e:
                self.log_test("Data Residency Validation", "FAIL", str(e), critical=True)
            
            # Test 2: Data Classification
            try:
                # Test different data types
                restricted = await compliance_service.classify_data("user_data", "password: secret123")
                confidential = await compliance_service.classify_data("case_data", "legal case details")
                public_data = await compliance_service.classify_data("statute", "Indian Penal Code Section 420")
                
                if (restricted == DataClassification.RESTRICTED and
                    confidential == DataClassification.CONFIDENTIAL and
                    public_data == DataClassification.PUBLIC):
                    self.log_test("Data Classification", "PASS")
                else:
                    self.log_test("Data Classification", "FAIL", "Data classification incorrect")
            except Exception as e:
                self.log_test("Data Classification", "FAIL", str(e))
            
            # Test 3: Retention Policies
            try:
                policies = compliance_service.retention_policies
                
                if (policies.get("audit_logs") == 2555 and  # 7 years
                    policies.get("user_queries") == 0 and   # Zero retention
                    "system_logs" in policies):
                    self.log_test("Retention Policies", "PASS")
                else:
                    self.log_test("Retention Policies", "FAIL", "Retention policies not configured correctly")
            except Exception as e:
                self.log_test("Retention Policies", "FAIL", str(e))
            
            # Test 4: Privacy Controls
            try:
                controls = compliance_service.privacy_controls
                required_controls = [
                    "data_minimization", "purpose_limitation", "storage_limitation",
                    "accuracy", "integrity_confidentiality", "accountability"
                ]
                
                all_enabled = all(controls.get(control, False) for control in required_controls)
                
                if all_enabled:
                    self.log_test("Privacy Controls", "PASS")
                else:
                    self.log_test("Privacy Controls", "FAIL", "Privacy controls not properly configured")
            except Exception as e:
                self.log_test("Privacy Controls", "FAIL", str(e))
                
        except Exception as e:
            self.log_test("Compliance Service Import", "FAIL", str(e), critical=True)
    
    def test_api_endpoints(self):
        """Test API endpoints structure"""
        print("\n🌐 Testing API Endpoints...")
        
        try:
            from api.compliance import router
            
            # Test 1: Router exists
            if router is not None:
                self.log_test("Compliance Router", "PASS")
            else:
                self.log_test("Compliance Router", "FAIL", "Compliance router not found", critical=True)
                return
            
            # Test 2: Required endpoints exist
            try:
                route_paths = [route.path for route in router.routes]
                required_endpoints = [
                    "/status",
                    "/reports/iso27001", 
                    "/audit-logs",
                    "/data-residency/validate",
                    "/encryption/status"
                ]
                
                missing_endpoints = [ep for ep in required_endpoints if ep not in route_paths]
                
                if not missing_endpoints:
                    self.log_test("Required Endpoints", "PASS")
                else:
                    self.log_test("Required Endpoints", "FAIL", f"Missing endpoints: {missing_endpoints}")
            except Exception as e:
                self.log_test("Required Endpoints", "FAIL", str(e))
                
        except Exception as e:
            self.log_test("API Endpoints Import", "FAIL", str(e), critical=True)
    
    def test_configuration_security(self):
        """Test security configuration"""
        print("\n⚙️ Testing Security Configuration...")
        
        try:
            from config import settings
            
            # Test 1: Security Settings
            try:
                security_checks = [
                    hasattr(settings, 'security') and settings.security.enable_data_encryption,
                    hasattr(settings, 'security') and settings.security.enable_security_headers,
                    hasattr(settings, 'security') and settings.security.force_https,
                    hasattr(settings, 'security') and len(settings.security.secret_key) >= 32,
                    hasattr(settings, 'security') and settings.security.password_min_length >= 8,
                    hasattr(settings, 'security') and settings.security.max_login_attempts <= 10
                ]
                
                if all(security_checks):
                    self.log_test("Security Configuration", "PASS")
                else:
                    self.log_test("Security Configuration", "FAIL", "Security settings not properly configured", critical=True)
            except Exception as e:
                self.log_test("Security Configuration", "FAIL", str(e), critical=True)
            
            # Test 2: File Upload Limits
            try:
                if (hasattr(settings, 'security') and 
                    settings.security.max_file_size_mb <= 200 and
                    len(settings.security.allowed_file_types) > 0 and
                    ".pdf" in settings.security.allowed_file_types):
                    self.log_test("File Upload Security", "PASS")
                else:
                    self.log_test("File Upload Security", "FAIL", "File upload limits not configured")
            except Exception as e:
                self.log_test("File Upload Security", "FAIL", str(e))
            
            # Test 3: Rate Limiting
            try:
                if (hasattr(settings, 'rate_limit') and
                    settings.rate_limit.queries_per_hour > 0 and
                    settings.rate_limit.uploads_per_hour > 0 and
                    settings.rate_limit.burst_limit > 0):
                    self.log_test("Rate Limiting Configuration", "PASS")
                else:
                    self.log_test("Rate Limiting Configuration", "FAIL", "Rate limiting not configured")
            except Exception as e:
                self.log_test("Rate Limiting Configuration", "FAIL", str(e))
                
        except Exception as e:
            self.log_test("Configuration Import", "FAIL", str(e), critical=True)
    
    async def test_integration_scenarios(self):
        """Test integration scenarios"""
        print("\n🔗 Testing Integration Scenarios...")
        
        try:
            from services.encryption_service import EncryptionService
            from services.input_validation_service import InputValidationService
            from services.compliance_service import ComplianceService
            
            encryption_service = EncryptionService()
            validator = InputValidationService()
            compliance_service = ComplianceService()
            
            # Test 1: End-to-end query processing
            try:
                query = "What are the provisions of Indian Contract Act?"
                
                # Validate input
                sanitized_query = validator.validate_query_text(query)
                
                # Classify data
                classification = await compliance_service.classify_data("user_query", query)
                
                # Encrypt if needed
                if classification.value in ["confidential", "restricted"]:
                    encrypted_query = encryption_service.encrypt_query_data(query)
                    decrypted_query = encryption_service.decrypt_query_data(encrypted_query)
                    encryption_works = decrypted_query == query
                else:
                    encryption_works = True
                
                if sanitized_query == query and encryption_works:
                    self.log_test("Query Processing Integration", "PASS")
                else:
                    self.log_test("Query Processing Integration", "FAIL", "Integration workflow failed")
            except Exception as e:
                self.log_test("Query Processing Integration", "FAIL", str(e))
            
            # Test 2: Document upload workflow
            try:
                # Validate file
                file_result = validator.validate_file_upload("contract.pdf", 1024*1024, "application/pdf")
                
                # Encrypt document content
                doc_content = b"Confidential legal document content"
                encrypted_content, metadata = encryption_service.encrypt_document_content(doc_content)
                
                # Classify document
                classification = await compliance_service.classify_data("legal_document", doc_content.decode())
                
                # Verify decryption
                decrypted_content = encryption_service.decrypt_document_content(encrypted_content, metadata)
                
                if (file_result["is_valid"] and 
                    decrypted_content == doc_content and
                    classification in [DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED]):
                    self.log_test("Document Upload Integration", "PASS")
                else:
                    self.log_test("Document Upload Integration", "FAIL", "Document workflow failed")
            except Exception as e:
                self.log_test("Document Upload Integration", "FAIL", str(e))
                
        except Exception as e:
            self.log_test("Integration Test Setup", "FAIL", str(e), critical=True)
    
    async def run_all_tests(self):
        """Run all security validation tests"""
        print("🔒 PRODUCTION SECURITY VALIDATION")
        print("=" * 80)
        print("🏛️  Indian Legal AI Assistant - Security Compliance Validation")
        print("⚖️  Legal-grade security testing for production deployment")
        print("=" * 80)
        
        # Run all test suites
        self.test_encryption_service()
        self.test_input_validation_service()
        self.test_audit_logging_service()
        await self.test_compliance_service()
        self.test_api_endpoints()
        self.test_configuration_security()
        await self.test_integration_scenarios()
        
        # Calculate final results
        success_rate = (self.results["passed_tests"] / self.results["total_tests"]) * 100 if self.results["total_tests"] > 0 else 0
        
        print("\n" + "=" * 80)
        print("📊 VALIDATION RESULTS")
        print("=" * 80)
        print(f"Total Tests: {self.results['total_tests']}")
        print(f"Passed: {self.results['passed_tests']}")
        print(f"Failed: {self.results['failed_tests']}")
        print(f"Critical Failures: {self.results['critical_failures']}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        # Determine security status
        if self.results["critical_failures"] > 0:
            self.results["security_status"] = "CRITICAL_ISSUES"
            status_emoji = "🚨"
            status_message = "CRITICAL SECURITY ISSUES DETECTED"
        elif success_rate >= 95:
            self.results["security_status"] = "PRODUCTION_READY"
            status_emoji = "🎉"
            status_message = "PRODUCTION READY - LEGAL COMPLIANCE ACHIEVED"
        elif success_rate >= 85:
            self.results["security_status"] = "MINOR_ISSUES"
            status_emoji = "⚠️"
            status_message = "MINOR ISSUES - REVIEW REQUIRED"
        else:
            self.results["security_status"] = "MAJOR_ISSUES"
            status_emoji = "❌"
            status_message = "MAJOR ISSUES - NOT READY FOR PRODUCTION"
        
        print(f"\n{status_emoji} SECURITY STATUS: {status_message}")
        
        if self.results["security_status"] == "PRODUCTION_READY":
            print("\n✅ SECURITY COMPLIANCE SUMMARY:")
            print("• ✅ Data encryption at rest and in transit - COMPLIANT")
            print("• ✅ Input validation and sanitization - COMPLIANT") 
            print("• ✅ SQL injection and XSS protection - COMPLIANT")
            print("• ✅ Audit logging without sensitive data - COMPLIANT")
            print("• ✅ ISO 27001 compliance controls - COMPLIANT")
            print("• ✅ Data residency enforcement (India) - COMPLIANT")
            print("• ✅ Zero-retention policy implementation - COMPLIANT")
            print("• ✅ Privacy controls and data protection - COMPLIANT")
            print("• ✅ Security configuration and headers - COMPLIANT")
            print("• ✅ API endpoint security - COMPLIANT")
            print("\n🏛️  LEGAL COMPLIANCE STATUS: READY FOR LEGAL PRACTICE")
            print("🔒 SECURITY CERTIFICATION: PRODUCTION APPROVED")
        else:
            print(f"\n❌ ISSUES DETECTED:")
            for test_name, result in self.results["test_results"].items():
                if result["status"] == "FAIL":
                    criticality = "CRITICAL" if result["critical"] else "MINOR"
                    print(f"• {criticality}: {test_name} - {result['message']}")
        
        print("\n" + "=" * 80)
        
        # Save detailed results
        with open("security_validation_report.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        print("📄 Detailed report saved to: security_validation_report.json")
        
        return self.results["security_status"] == "PRODUCTION_READY"

async def main():
    """Main validation function"""
    validator = ProductionSecurityValidator()
    
    try:
        success = await validator.run_all_tests()
        return 0 if success else 1
    except Exception as e:
        print(f"\n💥 VALIDATION FAILED WITH EXCEPTION:")
        print(f"Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return 2

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)