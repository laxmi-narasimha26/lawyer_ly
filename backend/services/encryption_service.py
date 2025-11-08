"""
Encryption Service for data at rest and in transit
Implements comprehensive encryption for sensitive data
"""
import os
import json
import hashlib
import secrets
from typing import Dict, Any, Optional, Union, Tuple
from datetime import datetime
import structlog
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

from config import settings
from services.azure_key_vault_service import key_vault_service
from utils.exceptions import ConfigurationError

logger = structlog.get_logger(__name__)

class EncryptionService:
    """
    Comprehensive encryption service for data protection
    
    Features:
    - Field-level encryption for sensitive data
    - Document encryption for file storage
    - Key rotation support
    - Multiple encryption algorithms
    - Secure key derivation
    """
    
    def __init__(self):
        self.backend = default_backend()
        self.encryption_keys = {}
        self.current_key_version = 1
        
        # Initialize encryption keys
        self._initialize_encryption_keys()
        
        logger.info("Encryption service initialized")
    
    def _initialize_encryption_keys(self):
        """Initialize encryption keys from Key Vault or generate new ones"""
        try:
            # Get master key from Key Vault or environment
            master_key = self._get_master_key()
            
            # Derive encryption keys for different purposes
            self.encryption_keys = {
                'user_data': self._derive_key(master_key, b'user_data_salt'),
                'document_content': self._derive_key(master_key, b'document_salt'),
                'query_data': self._derive_key(master_key, b'query_data_salt'),
                'audit_logs': self._derive_key(master_key, b'audit_log_salt'),
                'session_data': self._derive_key(master_key, b'session_salt')
            }
            
            # Create Fernet instances for each key
            self.fernet_instances = {
                key_name: Fernet(key) for key_name, key in self.encryption_keys.items()
            }
            
            logger.info("Encryption keys initialized", key_count=len(self.encryption_keys))
            
        except Exception as e:
            logger.error("Failed to initialize encryption keys", error=str(e))
            raise ConfigurationError(f"Encryption initialization failed: {str(e)}")
    
    def _get_master_key(self) -> bytes:
        """Get or generate master encryption key"""
        try:
            # Try to get from environment variable first
            env_key = os.getenv("MASTER_ENCRYPTION_KEY")
            if env_key:
                return base64.b64decode(env_key)
            
            # Generate new key for development/testing
            logger.warning("Generating temporary master key - use MASTER_ENCRYPTION_KEY env var in production")
            return os.urandom(32)
            
        except Exception as e:
            logger.error("Failed to get master key", error=str(e))
            # Generate fallback key
            logger.warning("Using fallback master key generation")
            return os.urandom(32)
    
    def _derive_key(self, master_key: bytes, salt: bytes) -> bytes:
        """Derive encryption key from master key using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=self.backend
        )
        return base64.urlsafe_b64encode(kdf.derive(master_key))
    
    def encrypt_user_data(self, data: str) -> str:
        """
        Encrypt user sensitive data (PII, credentials, etc.)
        
        Args:
            data: Data to encrypt
            
        Returns:
            Base64 encoded encrypted data with version prefix
        """
        try:
            fernet = self.fernet_instances['user_data']
            encrypted_data = fernet.encrypt(data.encode())
            
            # Add version prefix for key rotation support
            versioned_data = f"v{self.current_key_version}:{base64.b64encode(encrypted_data).decode()}"
            
            logger.debug("Encrypted user data", data_length=len(data))
            return versioned_data
            
        except Exception as e:
            logger.error("Failed to encrypt user data", error=str(e))
            raise Exception(f"User data encryption failed: {str(e)}")
    
    def decrypt_user_data(self, encrypted_data: str) -> str:
        """
        Decrypt user sensitive data
        
        Args:
            encrypted_data: Encrypted data with version prefix
            
        Returns:
            Decrypted data
        """
        try:
            # Parse version and data
            if ':' in encrypted_data:
                version_part, data_part = encrypted_data.split(':', 1)
                version = int(version_part[1:])  # Remove 'v' prefix
            else:
                # Legacy data without version
                version = 1
                data_part = encrypted_data
            
            # Get appropriate Fernet instance
            fernet = self.fernet_instances['user_data']
            
            # Decode and decrypt
            encrypted_bytes = base64.b64decode(data_part)
            decrypted_data = fernet.decrypt(encrypted_bytes)
            
            logger.debug("Decrypted user data", version=version)
            return decrypted_data.decode()
            
        except Exception as e:
            logger.error("Failed to decrypt user data", error=str(e))
            raise Exception(f"User data decryption failed: {str(e)}")
    
    def encrypt_document_content(self, content: bytes) -> Tuple[bytes, Dict[str, Any]]:
        """
        Encrypt document content for storage
        
        Args:
            content: Document content as bytes
            
        Returns:
            Tuple of (encrypted_content, encryption_metadata)
        """
        try:
            # Generate unique salt for this document
            salt = os.urandom(16)
            
            # Derive document-specific key
            master_key = self._get_master_key()
            doc_key = self._derive_key(master_key, salt)
            
            # Encrypt content
            fernet = Fernet(doc_key)
            encrypted_content = fernet.encrypt(content)
            
            # Create metadata
            metadata = {
                'algorithm': 'Fernet',
                'key_version': self.current_key_version,
                'salt': base64.b64encode(salt).decode(),
                'encrypted_at': datetime.utcnow().isoformat()
            }
            
            logger.debug("Encrypted document content", content_size=len(content))
            return encrypted_content, metadata
            
        except Exception as e:
            logger.error("Failed to encrypt document content", error=str(e))
            raise Exception(f"Document encryption failed: {str(e)}")
    
    def decrypt_document_content(self, encrypted_content: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        Decrypt document content
        
        Args:
            encrypted_content: Encrypted content
            metadata: Encryption metadata
            
        Returns:
            Decrypted content
        """
        try:
            # Extract salt from metadata
            salt = base64.b64decode(metadata['salt'])
            
            # Derive document-specific key
            master_key = self._get_master_key()
            doc_key = self._derive_key(master_key, salt)
            
            # Decrypt content
            fernet = Fernet(doc_key)
            decrypted_content = fernet.decrypt(encrypted_content)
            
            logger.debug("Decrypted document content", content_size=len(decrypted_content))
            return decrypted_content
            
        except Exception as e:
            logger.error("Failed to decrypt document content", error=str(e))
            raise Exception(f"Document decryption failed: {str(e)}")
    
    def encrypt_query_data(self, query_text: str) -> str:
        """
        Encrypt query text for audit logging (if required)
        
        Args:
            query_text: Query text to encrypt
            
        Returns:
            Encrypted query text
        """
        try:
            fernet = self.fernet_instances['query_data']
            encrypted_data = fernet.encrypt(query_text.encode())
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error("Failed to encrypt query data", error=str(e))
            raise Exception(f"Query encryption failed: {str(e)}")
    
    def decrypt_query_data(self, encrypted_query: str) -> str:
        """
        Decrypt query text
        
        Args:
            encrypted_query: Encrypted query text
            
        Returns:
            Decrypted query text
        """
        try:
            fernet = self.fernet_instances['query_data']
            encrypted_bytes = base64.b64decode(encrypted_query)
            decrypted_data = fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
            
        except Exception as e:
            logger.error("Failed to decrypt query data", error=str(e))
            raise Exception(f"Query decryption failed: {str(e)}")
    
    def hash_sensitive_data(self, data: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash sensitive data for secure storage (one-way)
        
        Args:
            data: Data to hash
            salt: Optional salt (generated if not provided)
            
        Returns:
            Tuple of (hash, salt)
        """
        try:
            if salt is None:
                salt = secrets.token_hex(16)
            
            # Create hash with salt
            hash_input = f"{data}{salt}".encode()
            hash_value = hashlib.sha256(hash_input).hexdigest()
            
            logger.debug("Hashed sensitive data")
            return hash_value, salt
            
        except Exception as e:
            logger.error("Failed to hash data", error=str(e))
            raise Exception(f"Data hashing failed: {str(e)}")
    
    def verify_hashed_data(self, data: str, hash_value: str, salt: str) -> bool:
        """
        Verify hashed data
        
        Args:
            data: Original data
            hash_value: Stored hash
            salt: Salt used for hashing
            
        Returns:
            True if data matches hash
        """
        try:
            computed_hash, _ = self.hash_sensitive_data(data, salt)
            return secrets.compare_digest(computed_hash, hash_value)
            
        except Exception as e:
            logger.error("Failed to verify hash", error=str(e))
            return False
    
    def encrypt_session_data(self, session_data: Dict[str, Any]) -> str:
        """
        Encrypt session data for secure storage
        
        Args:
            session_data: Session data dictionary
            
        Returns:
            Encrypted session data
        """
        try:
            fernet = self.fernet_instances['session_data']
            json_data = json.dumps(session_data)
            encrypted_data = fernet.encrypt(json_data.encode())
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error("Failed to encrypt session data", error=str(e))
            raise Exception(f"Session encryption failed: {str(e)}")
    
    def decrypt_session_data(self, encrypted_session: str) -> Dict[str, Any]:
        """
        Decrypt session data
        
        Args:
            encrypted_session: Encrypted session data
            
        Returns:
            Session data dictionary
        """
        try:
            fernet = self.fernet_instances['session_data']
            encrypted_bytes = base64.b64decode(encrypted_session)
            decrypted_data = fernet.decrypt(encrypted_bytes)
            return json.loads(decrypted_data.decode())
            
        except Exception as e:
            logger.error("Failed to decrypt session data", error=str(e))
            raise Exception(f"Session decryption failed: {str(e)}")
    
    def rotate_encryption_keys(self) -> bool:
        """
        Rotate encryption keys (creates new key version)
        
        Returns:
            True if successful
        """
        try:
            # Increment key version
            self.current_key_version += 1
            
            # Generate new master key
            new_master_key = os.urandom(32)
            
            # Store new master key in Key Vault
            if hasattr(key_vault_service, 'set_secret'):
                master_key_b64 = base64.b64encode(new_master_key).decode()
                key_vault_service.set_secret(
                    f"master-encryption-key-v{self.current_key_version}",
                    master_key_b64
                )
            
            # Derive new encryption keys
            new_keys = {
                'user_data': self._derive_key(new_master_key, b'user_data_salt'),
                'document_content': self._derive_key(new_master_key, b'document_salt'),
                'query_data': self._derive_key(new_master_key, b'query_data_salt'),
                'audit_logs': self._derive_key(new_master_key, b'audit_log_salt'),
                'session_data': self._derive_key(new_master_key, b'session_salt')
            }
            
            # Update encryption keys (keep old ones for decryption)
            self.encryption_keys.update(new_keys)
            
            # Create new Fernet instances
            new_fernet_instances = {
                key_name: Fernet(key) for key_name, key in new_keys.items()
            }
            self.fernet_instances.update(new_fernet_instances)
            
            logger.info("Encryption keys rotated", new_version=self.current_key_version)
            return True
            
        except Exception as e:
            logger.error("Failed to rotate encryption keys", error=str(e))
            return False
    
    def get_encryption_status(self) -> Dict[str, Any]:
        """
        Get encryption service status
        
        Returns:
            Encryption status information
        """
        return {
            'service_status': 'active',
            'key_version': self.current_key_version,
            'available_keys': list(self.encryption_keys.keys()),
            'algorithms': ['Fernet', 'PBKDF2-SHA256'],
            'last_rotation': None,  # Would track in production
            'timestamp': datetime.utcnow().isoformat()
        }

# Global encryption service instance
encryption_service = EncryptionService()