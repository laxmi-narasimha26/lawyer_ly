"""
Input Validation Service for security and data integrity
Implements comprehensive input validation and sanitization
"""
import re
import html
import json
import uuid
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
from urllib.parse import urlparse
import structlog
from pydantic import BaseModel, validator, ValidationError as PydanticValidationError
from sqlalchemy import text
import bleach

from config import settings
from utils.exceptions import ValidationError, SecurityViolation

logger = structlog.get_logger(__name__)

class InputValidationService:
    """
    Comprehensive input validation and sanitization service
    
    Features:
    - SQL injection prevention
    - XSS protection
    - Input sanitization
    - Data type validation
    - Business rule validation
    - File upload validation
    """
    
    def __init__(self):
        # SQL injection patterns
        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
            r"(\b(UNION|OR|AND)\s+\d+\s*=\s*\d+)",
            r"(--|#|/\*|\*/)",
            r"(\b(SCRIPT|JAVASCRIPT|VBSCRIPT|ONLOAD|ONERROR)\b)",
            r"(\b(CHAR|NCHAR|VARCHAR|NVARCHAR)\s*\(\s*\d+\s*\))",
            r"(\b(CAST|CONVERT|SUBSTRING|ASCII|CHAR_LENGTH)\s*\()",
            r"(\b(WAITFOR|DELAY|SLEEP)\s*\()",
            r"(\b(XP_|SP_)\w+)",
            r"(\b(INFORMATION_SCHEMA|SYSOBJECTS|SYSCOLUMNS)\b)"
        ]
        
        # XSS patterns
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"onmouseover\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<link[^>]*>",
            r"<meta[^>]*>"
        ]
        
        # Allowed HTML tags for rich text (if needed)
        self.allowed_html_tags = [
            'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote'
        ]
        
        # File type validation
        self.allowed_file_extensions = {
            'documents': ['.pdf', '.docx', '.doc', '.txt', '.rtf'],
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp'],
            'archives': ['.zip', '.rar', '.7z']
        }
        
        # Maximum sizes (in bytes)
        self.max_sizes = {
            'query_text': 10000,  # 10KB
            'document_title': 1000,
            'user_name': 255,
            'email': 320,
            'phone': 20,
            'file_size': 200 * 1024 * 1024,  # 200MB
            'json_payload': 1024 * 1024  # 1MB
        }
        
        logger.info("Input validation service initialized")
    
    def validate_query_text(self, query_text: str) -> str:
        """
        Validate and sanitize legal query text
        
        Args:
            query_text: User query text
            
        Returns:
            Sanitized query text
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Basic validation
            if not query_text or not query_text.strip():
                raise ValidationError("Query text cannot be empty")
            
            query_text = query_text.strip()
            
            # Length validation
            if len(query_text) > self.max_sizes['query_text']:
                raise ValidationError(f"Query text too long (max {self.max_sizes['query_text']} characters)")
            
            if len(query_text) < 5:
                raise ValidationError("Query text too short (minimum 5 characters)")
            
            # SQL injection check
            self._check_sql_injection(query_text)
            
            # XSS check
            self._check_xss(query_text)
            
            # Sanitize HTML entities
            sanitized_text = html.escape(query_text)
            
            logger.debug("Validated query text", length=len(sanitized_text))
            return sanitized_text
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Query validation failed", error=str(e))
            raise ValidationError(f"Query validation failed: {str(e)}")
    
    def validate_email(self, email: str) -> str:
        """
        Validate email address
        
        Args:
            email: Email address
            
        Returns:
            Normalized email address
            
        Raises:
            ValidationError: If email is invalid
        """
        try:
            if not email:
                raise ValidationError("Email address is required")
            
            email = email.strip().lower()
            
            # Length check
            if len(email) > self.max_sizes['email']:
                raise ValidationError("Email address too long")
            
            # Basic email regex
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                raise ValidationError("Invalid email address format")
            
            # Check for suspicious patterns
            self._check_sql_injection(email)
            self._check_xss(email)
            
            logger.debug("Validated email address")
            return email
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Email validation failed", error=str(e))
            raise ValidationError(f"Email validation failed: {str(e)}")
    
    def validate_user_name(self, name: str) -> str:
        """
        Validate user name
        
        Args:
            name: User name
            
        Returns:
            Sanitized name
            
        Raises:
            ValidationError: If name is invalid
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Name is required")
            
            name = name.strip()
            
            # Length check
            if len(name) > self.max_sizes['user_name']:
                raise ValidationError("Name too long")
            
            if len(name) < 2:
                raise ValidationError("Name too short")
            
            # Character validation (allow letters, spaces, hyphens, apostrophes)
            name_pattern = r"^[a-zA-Z\s\-'\.]+$"
            if not re.match(name_pattern, name):
                raise ValidationError("Name contains invalid characters")
            
            # Security checks
            self._check_sql_injection(name)
            self._check_xss(name)
            
            # Sanitize
            sanitized_name = html.escape(name)
            
            logger.debug("Validated user name")
            return sanitized_name
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Name validation failed", error=str(e))
            raise ValidationError(f"Name validation failed: {str(e)}")
    
    def validate_phone_number(self, phone: str) -> str:
        """
        Validate phone number
        
        Args:
            phone: Phone number
            
        Returns:
            Normalized phone number
            
        Raises:
            ValidationError: If phone is invalid
        """
        try:
            if not phone:
                return ""  # Phone is optional
            
            phone = phone.strip()
            
            # Length check
            if len(phone) > self.max_sizes['phone']:
                raise ValidationError("Phone number too long")
            
            # Remove common formatting characters
            cleaned_phone = re.sub(r'[\s\-\(\)\+]', '', phone)
            
            # Basic phone validation (digits only, 10-15 characters)
            if not re.match(r'^\d{10,15}$', cleaned_phone):
                raise ValidationError("Invalid phone number format")
            
            logger.debug("Validated phone number")
            return cleaned_phone
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Phone validation failed", error=str(e))
            raise ValidationError(f"Phone validation failed: {str(e)}")
    
    def validate_document_title(self, title: str) -> str:
        """
        Validate document title
        
        Args:
            title: Document title
            
        Returns:
            Sanitized title
            
        Raises:
            ValidationError: If title is invalid
        """
        try:
            if not title or not title.strip():
                raise ValidationError("Document title is required")
            
            title = title.strip()
            
            # Length check
            if len(title) > self.max_sizes['document_title']:
                raise ValidationError("Document title too long")
            
            # Security checks
            self._check_sql_injection(title)
            self._check_xss(title)
            
            # Sanitize
            sanitized_title = html.escape(title)
            
            logger.debug("Validated document title")
            return sanitized_title
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Document title validation failed", error=str(e))
            raise ValidationError(f"Document title validation failed: {str(e)}")
    
    def validate_file_upload(self, filename: str, file_size: int, content_type: str) -> Dict[str, Any]:
        """
        Validate file upload
        
        Args:
            filename: Original filename
            file_size: File size in bytes
            content_type: MIME content type
            
        Returns:
            Validation results
            
        Raises:
            ValidationError: If file is invalid
        """
        try:
            if not filename:
                raise ValidationError("Filename is required")
            
            # File size check
            if file_size > self.max_sizes['file_size']:
                max_mb = self.max_sizes['file_size'] / (1024 * 1024)
                raise ValidationError(f"File size exceeds {max_mb}MB limit")
            
            if file_size <= 0:
                raise ValidationError("File is empty")
            
            # File extension check
            file_extension = self._get_file_extension(filename)
            if not self._is_allowed_file_extension(file_extension):
                allowed_exts = []
                for exts in self.allowed_file_extensions.values():
                    allowed_exts.extend(exts)
                raise ValidationError(f"File type not allowed. Allowed types: {', '.join(allowed_exts)}")
            
            # Content type validation
            expected_content_types = self._get_expected_content_types(file_extension)
            if content_type not in expected_content_types:
                logger.warning("Content type mismatch", 
                             filename=filename, 
                             provided=content_type, 
                             expected=expected_content_types)
            
            # Filename security check
            safe_filename = self._sanitize_filename(filename)
            
            validation_result = {
                'is_valid': True,
                'safe_filename': safe_filename,
                'file_extension': file_extension,
                'file_size': file_size,
                'content_type': content_type,
                'file_category': self._get_file_category(file_extension)
            }
            
            logger.debug("Validated file upload", filename=safe_filename, size=file_size)
            return validation_result
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error("File validation failed", filename=filename, error=str(e))
            raise ValidationError(f"File validation failed: {str(e)}")
    
    def validate_uuid(self, uuid_string: str, field_name: str = "ID") -> str:
        """
        Validate UUID string
        
        Args:
            uuid_string: UUID string to validate
            field_name: Field name for error messages
            
        Returns:
            Validated UUID string
            
        Raises:
            ValidationError: If UUID is invalid
        """
        try:
            if not uuid_string:
                raise ValidationError(f"{field_name} is required")
            
            # Try to parse as UUID
            uuid_obj = uuid.UUID(uuid_string)
            
            logger.debug("Validated UUID", field_name=field_name)
            return str(uuid_obj)
            
        except ValueError:
            raise ValidationError(f"Invalid {field_name} format")
        except Exception as e:
            logger.error("UUID validation failed", field_name=field_name, error=str(e))
            raise ValidationError(f"{field_name} validation failed: {str(e)}")
    
    def validate_json_payload(self, json_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate JSON payload
        
        Args:
            json_data: JSON data (string or dict)
            
        Returns:
            Parsed and validated JSON data
            
        Raises:
            ValidationError: If JSON is invalid
        """
        try:
            # Parse if string
            if isinstance(json_data, str):
                if len(json_data) > self.max_sizes['json_payload']:
                    raise ValidationError("JSON payload too large")
                
                parsed_data = json.loads(json_data)
            else:
                parsed_data = json_data
            
            # Basic structure validation
            if not isinstance(parsed_data, dict):
                raise ValidationError("JSON payload must be an object")
            
            # Check for suspicious content in values
            self._validate_json_content(parsed_data)
            
            logger.debug("Validated JSON payload", keys=list(parsed_data.keys()))
            return parsed_data
            
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format: {str(e)}")
        except ValidationError:
            raise
        except Exception as e:
            logger.error("JSON validation failed", error=str(e))
            raise ValidationError(f"JSON validation failed: {str(e)}")
    
    def sanitize_html_content(self, html_content: str, allow_tags: bool = False) -> str:
        """
        Sanitize HTML content to prevent XSS
        
        Args:
            html_content: HTML content to sanitize
            allow_tags: Whether to allow safe HTML tags
            
        Returns:
            Sanitized HTML content
        """
        try:
            if not html_content:
                return ""
            
            if allow_tags:
                # Use bleach to allow only safe tags
                sanitized = bleach.clean(
                    html_content,
                    tags=self.allowed_html_tags,
                    attributes={},
                    strip=True
                )
            else:
                # Escape all HTML
                sanitized = html.escape(html_content)
            
            logger.debug("Sanitized HTML content", allow_tags=allow_tags)
            return sanitized
            
        except Exception as e:
            logger.error("HTML sanitization failed", error=str(e))
            return html.escape(html_content)  # Fallback to escaping
    
    def _check_sql_injection(self, input_text: str):
        """Check for SQL injection patterns"""
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, input_text, re.IGNORECASE):
                logger.warning("SQL injection attempt detected", pattern=pattern)
                raise SecurityViolation(f"Input contains potentially malicious content")
    
    def _check_xss(self, input_text: str):
        """Check for XSS patterns"""
        for pattern in self.xss_patterns:
            if re.search(pattern, input_text, re.IGNORECASE):
                logger.warning("XSS attempt detected", pattern=pattern)
                raise SecurityViolation(f"Input contains potentially malicious content")
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        return '.' + filename.split('.')[-1].lower() if '.' in filename else ''
    
    def _is_allowed_file_extension(self, extension: str) -> bool:
        """Check if file extension is allowed"""
        for allowed_exts in self.allowed_file_extensions.values():
            if extension in allowed_exts:
                return True
        return False
    
    def _get_file_category(self, extension: str) -> str:
        """Get file category based on extension"""
        for category, extensions in self.allowed_file_extensions.items():
            if extension in extensions:
                return category
        return 'unknown'
    
    def _get_expected_content_types(self, extension: str) -> List[str]:
        """Get expected MIME types for file extension"""
        content_type_map = {
            '.pdf': ['application/pdf'],
            '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            '.doc': ['application/msword'],
            '.txt': ['text/plain'],
            '.rtf': ['application/rtf', 'text/rtf'],
            '.jpg': ['image/jpeg'],
            '.jpeg': ['image/jpeg'],
            '.png': ['image/png'],
            '.gif': ['image/gif'],
            '.bmp': ['image/bmp'],
            '.zip': ['application/zip'],
            '.rar': ['application/x-rar-compressed'],
            '.7z': ['application/x-7z-compressed']
        }
        
        return content_type_map.get(extension, ['application/octet-stream'])
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove path separators and dangerous characters
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove leading/trailing dots and spaces
        safe_filename = safe_filename.strip('. ')
        
        # Limit length
        if len(safe_filename) > 255:
            name, ext = safe_filename.rsplit('.', 1) if '.' in safe_filename else (safe_filename, '')
            safe_filename = name[:250] + ('.' + ext if ext else '')
        
        return safe_filename
    
    def _validate_json_content(self, data: Dict[str, Any], max_depth: int = 10):
        """Recursively validate JSON content for security issues"""
        if max_depth <= 0:
            raise ValidationError("JSON structure too deeply nested")
        
        for key, value in data.items():
            # Validate key
            if not isinstance(key, str):
                raise ValidationError("JSON keys must be strings")
            
            self._check_sql_injection(key)
            self._check_xss(key)
            
            # Validate value based on type
            if isinstance(value, str):
                self._check_sql_injection(value)
                self._check_xss(value)
            elif isinstance(value, dict):
                self._validate_json_content(value, max_depth - 1)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, (str, dict)):
                        if isinstance(item, str):
                            self._check_sql_injection(item)
                            self._check_xss(item)
                        elif isinstance(item, dict):
                            self._validate_json_content(item, max_depth - 1)

# Global input validation service instance
input_validator = InputValidationService()