"""
Azure Blob Storage client
"""
import structlog
from azure.storage.blob.aio import BlobServiceClient
from azure.core.exceptions import AzureError

from config import settings

logger = structlog.get_logger()

class AzureStorageClient:
    def __init__(self):
        self.blob_service_client = BlobServiceClient.from_connection_string(
            settings.AZURE_STORAGE_CONNECTION_STRING
        )
    
    async def upload_blob(
        self,
        container: str,
        blob_name: str,
        data: bytes
    ) -> str:
        """
        Upload blob to Azure Storage
        Returns the blob URL
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container,
                blob=blob_name
            )
            
            await blob_client.upload_blob(data, overwrite=True)
            
            blob_url = blob_client.url
            logger.info("Blob uploaded", blob_name=blob_name)
            
            return blob_url
            
        except AzureError as e:
            logger.error("Blob upload failed", blob_name=blob_name, error=str(e))
            raise
    
    async def download_blob(
        self,
        container: str,
        blob_name: str
    ) -> bytes:
        """Download blob from Azure Storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container,
                blob=blob_name
            )
            
            downloader = await blob_client.download_blob()
            data = await downloader.readall()
            
            return data
            
        except AzureError as e:
            logger.error("Blob download failed", blob_name=blob_name, error=str(e))
            raise
    
    async def delete_blob(
        self,
        container: str,
        blob_name: str
    ):
        """Delete blob from Azure Storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container,
                blob=blob_name
            )
            
            await blob_client.delete_blob()
            logger.info("Blob deleted", blob_name=blob_name)
            
        except AzureError as e:
            logger.error("Blob deletion failed", blob_name=blob_name, error=str(e))
            raise
