"""
Production-grade Azure Blob Storage service for Indian Legal AI Assistant
Handles secure document storage with enterprise-grade features
"""
import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO
from datetime import datetime, timedelta
import structlog
from azure.storage.blob.aio import BlobServiceClient, BlobClient
from azure.storage.blob import BlobSasPermissions, generate_blob_sas
from azure.core.exceptions import AzureError, ResourceNotFoundError

from config import settings

logger = structlog.get_logger(__name__)

class AzureStorageService:
    """
    Production-grade Azure Blob Storage service

    Features:
    - Secure document upload and retrieval
    - SAS token generation for secure access
    - Hierarchical storage organization
    - Metadata management
    - Lifecycle management
    - Access logging and monitoring
    - Local file storage fallback for development
    """

    def __init__(self):
        # Check if Azure connection string is configured
        self.use_azure = bool(settings.azure_storage.connection_string)

        if self.use_azure:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                settings.azure_storage.connection_string
            )
            self.container_name = settings.azure_storage.container_name
            logger.info("Azure Storage service initialized")
        else:
            # Use local file storage for development
            self.local_storage_path = Path("/app/local_storage/documents")
            self.local_storage_path.mkdir(parents=True, exist_ok=True)
            self.blob_service_client = None
            self.container_name = "local"
            logger.info("Azure Storage not configured, using local file storage", path=str(self.local_storage_path))

        # Storage statistics
        self.storage_stats = {
            'uploads': 0,
            'downloads': 0,
            'deletions': 0,
            'errors': 0,
            'total_bytes_uploaded': 0,
            'total_bytes_downloaded': 0
        }

    
    async def initialize_container(self):
        """Initialize storage container with proper configuration"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            # Create container if it doesn't exist
            try:
                await container_client.create_container()
                logger.info("Storage container created", container=self.container_name)
            except Exception as e:
                if "ContainerAlreadyExists" not in str(e):
                    raise
                logger.info("Storage container already exists", container=self.container_name)
            
            # Set container properties for legal document storage
            await container_client.set_container_metadata({
                'purpose': 'legal-documents',
                'created': datetime.utcnow().isoformat(),
                'compliance': 'indian-data-residency'
            })
            
        except Exception as e:
            logger.error("Container initialization failed", error=str(e))
            raise
    
    async def upload_document(
        self,
        document_id: str,
        filename: str,
        content: bytes,
        user_id: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload document to Azure Blob Storage with security and compliance
        
        Args:
            document_id: Unique document identifier
            filename: Original filename
            content: Document content as bytes
            user_id: User ID for access control
            metadata: Additional metadata
            
        Returns:
            Blob URL for the uploaded document
        """
        try:
            # Generate secure blob path
            blob_path = self._generate_blob_path(user_id, document_id, filename)
            
            # Prepare metadata
            blob_metadata = {
                'document_id': document_id,
                'user_id': user_id,
                'original_filename': filename,
                'upload_timestamp': datetime.utcnow().isoformat(),
                'content_length': str(len(content)),
                'compliance_region': 'india'
            }
            
            if metadata:
                blob_metadata.update(metadata)
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            # Upload with metadata and properties
            await blob_client.upload_blob(
                data=content,
                metadata=blob_metadata,
                overwrite=True,
                content_settings={
                    'content_type': self._detect_content_type(filename),
                    'content_encoding': 'utf-8' if filename.endswith('.txt') else None
                }
            )
            
            # Update statistics
            self.storage_stats['uploads'] += 1
            self.storage_stats['total_bytes_uploaded'] += len(content)
            
            blob_url = blob_client.url
            
            logger.info(
                "Document uploaded successfully",
                document_id=document_id,
                blob_path=blob_path,
                size_bytes=len(content)
            )
            
            return blob_url
            
        except Exception as e:
            self.storage_stats['errors'] += 1
            logger.error(
                "Document upload failed",
                document_id=document_id,
                filename=filename,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def download_document(
        self,
        document_id: str,
        user_id: str,
        filename: str
    ) -> Optional[bytes]:
        """
        Download document from Azure Blob Storage with access control
        
        Args:
            document_id: Document identifier
            user_id: User ID for access control
            filename: Original filename
            
        Returns:
            Document content as bytes or None if not found
        """
        try:
            blob_path = self._generate_blob_path(user_id, document_id, filename)
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            # Check if blob exists and user has access
            blob_properties = await blob_client.get_blob_properties()
            
            # Verify user access
            if blob_properties.metadata.get('user_id') != user_id:
                logger.warning(
                    "Unauthorized document access attempt",
                    document_id=document_id,
                    requesting_user=user_id,
                    owner_user=blob_properties.metadata.get('user_id')
                )
                return None
            
            # Download content
            download_stream = await blob_client.download_blob()
            content = await download_stream.readall()
            
            # Update statistics
            self.storage_stats['downloads'] += 1
            self.storage_stats['total_bytes_downloaded'] += len(content)
            
            logger.info(
                "Document downloaded successfully",
                document_id=document_id,
                size_bytes=len(content)
            )
            
            return content
            
        except ResourceNotFoundError:
            logger.warning("Document not found", document_id=document_id)
            return None
        except Exception as e:
            self.storage_stats['errors'] += 1
            logger.error(
                "Document download failed",
                document_id=document_id,
                error=str(e),
                exc_info=True
            )
            return None
    
    async def generate_secure_access_url(
        self,
        document_id: str,
        user_id: str,
        filename: str,
        expiry_hours: int = 1
    ) -> Optional[str]:
        """
        Generate secure SAS URL for temporary document access
        
        Args:
            document_id: Document identifier
            user_id: User ID for access control
            filename: Original filename
            expiry_hours: URL expiry time in hours
            
        Returns:
            Secure SAS URL or None if not authorized
        """
        try:
            blob_path = self._generate_blob_path(user_id, document_id, filename)
            
            # Verify user access first
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            blob_properties = await blob_client.get_blob_properties()
            if blob_properties.metadata.get('user_id') != user_id:
                return None
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=blob_client.account_name,
                container_name=self.container_name,
                blob_name=blob_path,
                account_key=self._get_account_key(),
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            secure_url = f"{blob_client.url}?{sas_token}"
            
            logger.info(
                "Secure access URL generated",
                document_id=document_id,
                expiry_hours=expiry_hours
            )
            
            return secure_url
            
        except Exception as e:
            logger.error(
                "Secure URL generation failed",
                document_id=document_id,
                error=str(e)
            )
            return None
    
    async def delete_document(
        self,
        document_id: str,
        user_id: str,
        filename: str
    ) -> bool:
        """
        Delete document from Azure Blob Storage with access control
        
        Args:
            document_id: Document identifier
            user_id: User ID for access control
            filename: Original filename
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            blob_path = self._generate_blob_path(user_id, document_id, filename)
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            # Verify user access before deletion
            blob_properties = await blob_client.get_blob_properties()
            if blob_properties.metadata.get('user_id') != user_id:
                logger.warning(
                    "Unauthorized document deletion attempt",
                    document_id=document_id,
                    requesting_user=user_id
                )
                return False
            
            # Delete blob
            await blob_client.delete_blob()
            
            # Update statistics
            self.storage_stats['deletions'] += 1
            
            logger.info("Document deleted successfully", document_id=document_id)
            return True
            
        except ResourceNotFoundError:
            logger.warning("Document not found for deletion", document_id=document_id)
            return False
        except Exception as e:
            self.storage_stats['errors'] += 1
            logger.error(
                "Document deletion failed",
                document_id=document_id,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def list_user_documents(
        self,
        user_id: str,
        prefix: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all documents for a specific user
        
        Args:
            user_id: User ID
            prefix: Optional prefix filter
            
        Returns:
            List of document metadata
        """
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            # Build name prefix for user's documents
            name_prefix = f"{user_id}/"
            if prefix:
                name_prefix += prefix
            
            documents = []
            
            async for blob in container_client.list_blobs(name_starts_with=name_prefix, include=['metadata']):
                # Verify this blob belongs to the user
                if blob.metadata and blob.metadata.get('user_id') == user_id:
                    documents.append({
                        'document_id': blob.metadata.get('document_id'),
                        'filename': blob.metadata.get('original_filename'),
                        'blob_name': blob.name,
                        'size_bytes': blob.size,
                        'last_modified': blob.last_modified,
                        'upload_timestamp': blob.metadata.get('upload_timestamp'),
                        'content_type': blob.content_settings.content_type if blob.content_settings else None
                    })
            
            logger.info("User documents listed", user_id=user_id, count=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to list user documents", user_id=user_id, error=str(e))
            return []
    
    async def get_document_metadata(
        self,
        document_id: str,
        user_id: str,
        filename: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get document metadata without downloading content
        
        Args:
            document_id: Document identifier
            user_id: User ID for access control
            filename: Original filename
            
        Returns:
            Document metadata or None if not found/unauthorized
        """
        try:
            blob_path = self._generate_blob_path(user_id, document_id, filename)
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            properties = await blob_client.get_blob_properties()
            
            # Verify user access
            if properties.metadata.get('user_id') != user_id:
                return None
            
            return {
                'document_id': document_id,
                'filename': properties.metadata.get('original_filename'),
                'size_bytes': properties.size,
                'content_type': properties.content_settings.content_type,
                'last_modified': properties.last_modified,
                'metadata': properties.metadata,
                'etag': properties.etag
            }
            
        except ResourceNotFoundError:
            return None
        except Exception as e:
            logger.error("Failed to get document metadata", document_id=document_id, error=str(e))
            return None
    
    async def update_document_metadata(
        self,
        document_id: str,
        user_id: str,
        filename: str,
        new_metadata: Dict[str, str]
    ) -> bool:
        """
        Update document metadata
        
        Args:
            document_id: Document identifier
            user_id: User ID for access control
            filename: Original filename
            new_metadata: New metadata to set
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            blob_path = self._generate_blob_path(user_id, document_id, filename)
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            # Get current properties to verify access
            properties = await blob_client.get_blob_properties()
            if properties.metadata.get('user_id') != user_id:
                return False
            
            # Merge with existing metadata
            updated_metadata = properties.metadata.copy()
            updated_metadata.update(new_metadata)
            updated_metadata['last_updated'] = datetime.utcnow().isoformat()
            
            # Update metadata
            await blob_client.set_blob_metadata(updated_metadata)
            
            logger.info("Document metadata updated", document_id=document_id)
            return True
            
        except Exception as e:
            logger.error("Failed to update document metadata", document_id=document_id, error=str(e))
            return False
    
    def _generate_blob_path(self, user_id: str, document_id: str, filename: str) -> str:
        """
        Generate hierarchical blob path for organized storage
        
        Format: {user_id}/{document_id}/{filename}
        """
        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)
        return f"{user_id}/{document_id}/{safe_filename}"
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        import re
        # Remove or replace unsafe characters
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Limit length
        if len(safe_filename) > 255:
            name, ext = safe_filename.rsplit('.', 1) if '.' in safe_filename else (safe_filename, '')
            safe_filename = name[:250] + ('.' + ext if ext else '')
        return safe_filename
    
    def _detect_content_type(self, filename: str) -> str:
        """Detect content type based on file extension"""
        import mimetypes
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or 'application/octet-stream'
    
    def _get_account_key(self) -> str:
        """Extract account key from connection string"""
        # Parse connection string to get account key
        conn_parts = dict(part.split('=', 1) for part in settings.azure_storage.connection_string.split(';') if '=' in part)
        return conn_parts.get('AccountKey', '')
    
    async def cleanup_expired_documents(self, days_old: int = 90):
        """
        Clean up documents older than specified days (for compliance)
        
        Args:
            days_old: Number of days after which to consider documents for cleanup
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            cleanup_count = 0
            
            async for blob in container_client.list_blobs(include=['metadata']):
                if blob.last_modified < cutoff_date:
                    # Check if document is marked for retention
                    if blob.metadata and blob.metadata.get('retain') != 'true':
                        try:
                            await container_client.delete_blob(blob.name)
                            cleanup_count += 1
                        except Exception as e:
                            logger.warning("Failed to cleanup blob", blob_name=blob.name, error=str(e))
            
            logger.info("Document cleanup completed", cleanup_count=cleanup_count, days_old=days_old)
            
        except Exception as e:
            logger.error("Document cleanup failed", error=str(e))
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get storage operation statistics"""
        return {
            **self.storage_stats,
            'container_name': self.container_name,
            'service_initialized': True
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on storage service"""
        try:
            # Test container access
            container_client = self.blob_service_client.get_container_client(self.container_name)
            properties = await container_client.get_container_properties()
            
            return {
                'status': 'healthy',
                'container_exists': True,
                'last_modified': properties.last_modified,
                'statistics': self.get_storage_statistics()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'container_exists': False
            }