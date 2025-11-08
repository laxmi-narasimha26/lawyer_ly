"""
Azure Key Vault Service for secure key management
Implements comprehensive encryption key management and secret storage
"""
import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import structlog
from azure.keyvault.secrets import SecretClient
from azure.keyvault.keys import KeyClient, KeyType, KeyCurveName
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
import base64

from config import settings
from utils.exceptions import ConfigurationError, ExternalServiceError

logger = structlog.get_logger(__name__)

class AzureKeyVaultService:
    """
    Azure Key Vault service for secure key and secret management
    
    Features:
    - Secret storage and retrieval
    - Encryption key management
    - Certificate management
    - Automatic key rotation
    - Audit logging
    """
    
    def __init__(self):
        self.vault_url = os.getenv("AZURE_KEY_VAULT_URL")
        self.tenant_id = os.getenv("AZURE_TENANT_ID")
        self.client_id = os.getenv("AZURE_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        
        self.key_vault_enabled = bool(self.vault_url)
        
        if self.key_vault_enabled:
            try:
                # Initialize credentials
                self.credential = self._get_credential()
                
                # Initialize clients
                self.secret_client = SecretClient(
                    vault_url=self.vault_url,
                    credential=self.credential
                )
                
                self.key_client = KeyClient(
                    vault_url=self.vault_url,
                    credential=self.credential
                )
                
                logger.info("Azure Key Vault service initialized", vault_url=self.vault_url)
            except Exception as e:
                logger.warning("Azure Key Vault initialization failed, using local keys", error=str(e))
                self.key_vault_enabled = False
        else:
            logger.info("Azure Key Vault not configured, using local encryption keys")
        
        # Local encryption for sensitive data
        self.local_key = self._get_or_create_local_key()
        self.fernet = Fernet(self.local_key)
    
    def _get_credential(self):
        """Get Azure credential based on available authentication methods"""
        try:
            if self.client_id and self.client_secret and self.tenant_id:
                # Use service principal authentication
                return ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
            else:
                # Use default credential (managed identity, Azure CLI, etc.)
                return DefaultAzureCredential()
        except Exception as e:
            logger.error("Failed to initialize Azure credentials", error=str(e))
            raise ConfigurationError(f"Azure credential initialization failed: {str(e)}")
    
    def _get_or_create_local_key(self) -> bytes:
        """Get or create local encryption key for sensitive data"""
        try:
            # Try to get key from Key Vault if enabled
            if self.key_vault_enabled:
                try:
                    secret = self.secret_client.get_secret("local-encryption-key")
                    return base64.b64decode(secret.value.encode())
                except ResourceNotFoundError:
                    # Create new key
                    key = Fernet.generate_key()
                    key_b64 = base64.b64encode(key).decode()
                    
                    # Store in Key Vault
                    self.secret_client.set_secret("local-encryption-key", key_b64)
                    logger.info("Created new local encryption key in Key Vault")
                    
                    return key
                except Exception as e:
                    logger.warning("Failed to get key from Key Vault, falling back to local", error=str(e))
            
            # Fallback to environment variable or generate key
            env_key = os.getenv("LOCAL_ENCRYPTION_KEY")
            if env_key:
                return base64.b64decode(env_key.encode())
            else:
                # Generate and store key locally for development
                key = Fernet.generate_key()
                logger.info("Generated new local encryption key for development")
                return key
                
        except Exception as e:
            logger.error("Failed to get local encryption key", error=str(e))
            # Generate temporary key as last resort
            logger.warning("Using temporary encryption key - data will not persist across restarts")
            return Fernet.generate_key()
    
    async def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Retrieve secret from Azure Key Vault
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret value or None if not found
        """
        if not self.key_vault_enabled:
            logger.debug("Key Vault not enabled, returning None for secret", secret_name=secret_name)
            return None
            
        try:
            secret = self.secret_client.get_secret(secret_name)
            logger.debug("Retrieved secret from Key Vault", secret_name=secret_name)
            return secret.value
        except ResourceNotFoundError:
            logger.warning("Secret not found in Key Vault", secret_name=secret_name)
            return None
        except Exception as e:
            logger.error("Failed to retrieve secret", secret_name=secret_name, error=str(e))
            return None  # Graceful fallback instead of raising exception
    
    async def set_secret(self, secret_name: str, secret_value: str, expires_on: Optional[datetime] = None) -> bool:
        """
        Store secret in Azure Key Vault
        
        Args:
            secret_name: Name of the secret
            secret_value: Secret value
            expires_on: Optional expiration date
            
        Returns:
            True if successful
        """
        try:
            self.secret_client.set_secret(
                name=secret_name,
                value=secret_value,
                expires_on=expires_on
            )
            logger.info("Stored secret in Key Vault", secret_name=secret_name)
            return True
        except Exception as e:
            logger.error("Failed to store secret", secret_name=secret_name, error=str(e))
            raise ExternalServiceError(f"Key Vault secret storage failed: {str(e)}", service="azure_key_vault")
    
    async def delete_secret(self, secret_name: str) -> bool:
        """
        Delete secret from Azure Key Vault
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            True if successful
        """
        try:
            self.secret_client.begin_delete_secret(secret_name)
            logger.info("Deleted secret from Key Vault", secret_name=secret_name)
            return True
        except ResourceNotFoundError:
            logger.warning("Secret not found for deletion", secret_name=secret_name)
            return True  # Already deleted
        except Exception as e:
            logger.error("Failed to delete secret", secret_name=secret_name, error=str(e))
            raise ExternalServiceError(f"Key Vault secret deletion failed: {str(e)}", service="azure_key_vault")
    
    async def list_secrets(self) -> List[str]:
        """
        List all secret names in the Key Vault
        
        Returns:
            List of secret names
        """
        try:
            secret_names = []
            for secret in self.secret_client.list_properties_of_secrets():
                secret_names.append(secret.name)
            
            logger.debug("Listed secrets from Key Vault", count=len(secret_names))
            return secret_names
        except Exception as e:
            logger.error("Failed to list secrets", error=str(e))
            raise ExternalServiceError(f"Key Vault secret listing failed: {str(e)}", service="azure_key_vault")
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """
        Encrypt sensitive data using local encryption key
        
        Args:
            data: Data to encrypt
            
        Returns:
            Base64 encoded encrypted data
        """
        try:
            encrypted_data = self.fernet.encrypt(data.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error("Failed to encrypt data", error=str(e))
            raise Exception(f"Data encryption failed: {str(e)}")
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data using local encryption key
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Decrypted data
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            logger.error("Failed to decrypt data", error=str(e))
            raise Exception(f"Data decryption failed: {str(e)}")
    
    async def create_encryption_key(self, key_name: str, key_type: str = "RSA") -> bool:
        """
        Create encryption key in Azure Key Vault
        
        Args:
            key_name: Name of the key
            key_type: Type of key (RSA, EC)
            
        Returns:
            True if successful
        """
        try:
            if key_type.upper() == "RSA":
                key = self.key_client.create_rsa_key(
                    name=key_name,
                    size=2048
                )
            elif key_type.upper() == "EC":
                key = self.key_client.create_ec_key(
                    name=key_name,
                    curve=KeyCurveName.p_256
                )
            else:
                raise ValueError(f"Unsupported key type: {key_type}")
            
            logger.info("Created encryption key", key_name=key_name, key_type=key_type)
            return True
        except Exception as e:
            logger.error("Failed to create encryption key", key_name=key_name, error=str(e))
            raise ExternalServiceError(f"Key creation failed: {str(e)}", service="azure_key_vault")
    
    async def rotate_key(self, key_name: str) -> bool:
        """
        Rotate encryption key in Azure Key Vault
        
        Args:
            key_name: Name of the key to rotate
            
        Returns:
            True if successful
        """
        try:
            # Create new version of the key
            key = self.key_client.create_rsa_key(
                name=key_name,
                size=2048
            )
            
            logger.info("Rotated encryption key", key_name=key_name, version=key.properties.version)
            return True
        except Exception as e:
            logger.error("Failed to rotate key", key_name=key_name, error=str(e))
            raise ExternalServiceError(f"Key rotation failed: {str(e)}", service="azure_key_vault")
    
    async def get_database_connection_string(self) -> str:
        """
        Get database connection string from Key Vault
        
        Returns:
            Database connection string
        """
        connection_string = await self.get_secret("database-connection-string")
        if not connection_string:
            # Fallback to environment variable
            connection_string = os.getenv("DATABASE_URL")
            if not connection_string:
                raise ConfigurationError("Database connection string not found")
        
        return connection_string
    
    async def get_openai_api_key(self) -> str:
        """
        Get OpenAI API key from Key Vault
        
        Returns:
            OpenAI API key
        """
        api_key = await self.get_secret("openai-api-key")
        if not api_key:
            # Fallback to environment variable
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            if not api_key:
                raise ConfigurationError("OpenAI API key not found")
        
        return api_key
    
    async def get_storage_connection_string(self) -> str:
        """
        Get Azure Storage connection string from Key Vault
        
        Returns:
            Storage connection string
        """
        connection_string = await self.get_secret("storage-connection-string")
        if not connection_string:
            # Fallback to environment variable
            connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            if not connection_string:
                raise ConfigurationError("Storage connection string not found")
        
        return connection_string
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Key Vault service
        
        Returns:
            Health check results
        """
        try:
            # Try to list secrets (minimal operation)
            secrets = await self.list_secrets()
            
            return {
                "status": "healthy",
                "vault_url": self.vault_url,
                "secret_count": len(secrets),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error("Key Vault health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "vault_url": self.vault_url,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def setup_initial_secrets(self):
        """
        Set up initial secrets in Key Vault if they don't exist
        """
        try:
            # Check and create essential secrets
            essential_secrets = {
                "jwt-secret-key": os.getenv("SECRET_KEY", "development-secret-key"),
                "database-connection-string": os.getenv("DATABASE_URL"),
                "openai-api-key": os.getenv("AZURE_OPENAI_API_KEY"),
                "storage-connection-string": os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            }
            
            for secret_name, secret_value in essential_secrets.items():
                if secret_value:
                    existing_secret = await self.get_secret(secret_name)
                    if not existing_secret:
                        await self.set_secret(secret_name, secret_value)
                        logger.info("Created initial secret", secret_name=secret_name)
            
            logger.info("Initial secrets setup completed")
        except Exception as e:
            logger.error("Failed to setup initial secrets", error=str(e))
            raise

# Global Key Vault service instance
key_vault_service = AzureKeyVaultService()