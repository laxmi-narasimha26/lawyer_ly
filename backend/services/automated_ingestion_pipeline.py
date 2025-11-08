"""
Automated ETL Pipeline for Legal Document Ingestion
Handles batch processing, validation, monitoring, and error recovery
"""
import asyncio
import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
import aiofiles
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import settings
from database.models import Document, DocumentChunk, DocumentType, ProcessingStatus, KnowledgeBase, AuditLog
from database.connection import get_async_session
from services.knowledge_base_ingestion import KnowledgeBaseIngestionService
from services.document_processor import DocumentProcessor
from utils.text_processing import LegalTextChunker
from utils.metadata_extractor import LegalMetadataExtractor
from utils.monitoring import MetricsCollector

logger = structlog.get_logger(__name__)

class PipelineStatus(str, Enum):
    """Pipeline execution status"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"

class DocumentSource(str, Enum):
    """Document source types"""
    LOCAL_FILE = "local_file"
    URL_DOWNLOAD = "url_download"
    API_FETCH = "api_fetch"
    BATCH_UPLOAD = "batch_upload"

@dataclass
class IngestionJob:
    """Ingestion job configuration"""
    job_id: str
    source_type: DocumentSource
    source_path: str
    document_type: DocumentType
    priority: int = 1
    metadata: Dict[str, Any] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ValidationRule:
    """Document validation rule"""
    name: str
    rule_type: str  # file_size, content_length, format, etc.
    parameters: Dict[str, Any]
    error_message: str

@dataclass
class PipelineMetrics:
    """Pipeline execution metrics"""
    jobs_processed: int = 0
    jobs_successful: int = 0
    jobs_failed: int = 0
    documents_created: int = 0
    chunks_created: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    start_time: datetime = None
    end_time: datetime = None

class AutomatedIngestionPipeline:
    """
    Production-grade automated ingestion pipeline for legal documents
    
    Features:
    - Batch processing with configurable parallelism
    - Document validation and quality checks
    - Error handling and retry logic
    - Progress monitoring and metrics collection
    - Automated scheduling and queue management
    - Comprehensive logging and audit trails
    """
    
    def __init__(self):
        self.status = PipelineStatus.IDLE
        self.job_queue: List[IngestionJob] = []
        self.active_jobs: Dict[str, IngestionJob] = {}
        self.completed_jobs: List[IngestionJob] = []
        self.failed_jobs: List[IngestionJob] = []
        
        # Pipeline configuration
        self.config = self._load_pipeline_config()
        
        # Initialize services
        self.kb_ingestion = KnowledgeBaseIngestionService()
        self.document_processor = DocumentProcessor()
        self.chunker = LegalTextChunker()
        self.metadata_extractor = LegalMetadataExtractor()
        self.metrics_collector = MetricsCollector()
        
        # Validation rules
        self.validation_rules = self._initialize_validation_rules()
        
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(
            max_workers=self.config['max_parallel_workers']
        )
        
        # Pipeline metrics
        self.metrics = PipelineMetrics()
        
        logger.info("Automated ingestion pipeline initialized", config=self.config)
    
    async def start_pipeline(self) -> Dict[str, Any]:
        """
        Start the automated ingestion pipeline
        
        Returns:
            Dictionary with pipeline status and initial metrics
        """
        if self.status == PipelineStatus.RUNNING:
            return {'status': 'already_running', 'message': 'Pipeline is already running'}
        
        try:
            logger.info("Starting automated ingestion pipeline")
            
            self.status = PipelineStatus.RUNNING
            self.metrics.start_time = datetime.utcnow()
            
            # Create necessary directories
            await self._create_pipeline_directories()
            
            # Load pending jobs from queue
            await self._load_job_queue()
            
            # Start processing jobs
            results = await self._process_job_queue()
            
            # Update final metrics
            self.metrics.end_time = datetime.utcnow()
            if self.metrics.start_time:
                self.metrics.total_processing_time = (
                    self.metrics.end_time - self.metrics.start_time
                ).total_seconds()
            
            if self.metrics.jobs_processed > 0:
                self.metrics.average_processing_time = (
                    self.metrics.total_processing_time / self.metrics.jobs_processed
                )
            
            self.status = PipelineStatus.COMPLETED
            
            # Log completion
            await self._log_pipeline_completion()
            
            logger.info(
                "Pipeline execution completed",
                jobs_processed=self.metrics.jobs_processed,
                successful=self.metrics.jobs_successful,
                failed=self.metrics.jobs_failed
            )
            
            return {
                'status': 'completed',
                'metrics': asdict(self.metrics),
                'results': results
            }
            
        except Exception as e:
            self.status = PipelineStatus.FAILED
            logger.error("Pipeline execution failed", error=str(e), exc_info=True)
            await self._log_pipeline_error(str(e))
            raise
    
    async def add_job(self, job: IngestionJob) -> str:
        """
        Add a new ingestion job to the queue
        
        Args:
            job: Ingestion job configuration
            
        Returns:
            Job ID
        """
        # Validate job
        validation_result = await self._validate_job(job)
        if not validation_result['valid']:
            raise ValueError(f"Invalid job: {validation_result['errors']}")
        
        # Add to queue
        self.job_queue.append(job)
        
        # Persist job to disk
        await self._persist_job(job)
        
        logger.info("Job added to queue", job_id=job.job_id, source=job.source_path)
        
        return job.job_id
    
    async def add_batch_jobs(self, jobs: List[IngestionJob]) -> List[str]:
        """
        Add multiple jobs to the queue
        
        Args:
            jobs: List of ingestion jobs
            
        Returns:
            List of job IDs
        """
        job_ids = []
        
        for job in jobs:
            try:
                job_id = await self.add_job(job)
                job_ids.append(job_id)
            except Exception as e:
                logger.error(
                    "Failed to add job to queue",
                    job_id=job.job_id,
                    error=str(e)
                )
        
        logger.info(f"Added {len(job_ids)} jobs to queue")
        return job_ids
    
    async def create_jobs_from_directory(
        self,
        directory_path: str,
        document_type: DocumentType,
        recursive: bool = True
    ) -> List[str]:
        """
        Create ingestion jobs from files in a directory
        
        Args:
            directory_path: Path to directory containing documents
            document_type: Type of documents in directory
            recursive: Whether to scan subdirectories
            
        Returns:
            List of created job IDs
        """
        jobs = []
        directory = Path(directory_path)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Supported file extensions
        supported_extensions = {'.pdf', '.docx', '.txt', '.html', '.xml'}
        
        # Scan directory
        pattern = "**/*" if recursive else "*"
        for file_path in directory.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                job = IngestionJob(
                    job_id=f"dir_{hashlib.md5(str(file_path).encode()).hexdigest()[:8]}",
                    source_type=DocumentSource.LOCAL_FILE,
                    source_path=str(file_path),
                    document_type=document_type,
                    metadata={
                        'source_directory': directory_path,
                        'filename': file_path.name,
                        'file_extension': file_path.suffix
                    }
                )
                jobs.append(job)
        
        # Add jobs to queue
        job_ids = await self.add_batch_jobs(jobs)
        
        logger.info(
            "Created jobs from directory",
            directory=directory_path,
            job_count=len(job_ids)
        )
        
        return job_ids
    
    async def get_pipeline_status(self) -> Dict[str, Any]:
        """Get current pipeline status and metrics"""
        return {
            'status': self.status.value,
            'queue_size': len(self.job_queue),
            'active_jobs': len(self.active_jobs),
            'completed_jobs': len(self.completed_jobs),
            'failed_jobs': len(self.failed_jobs),
            'metrics': asdict(self.metrics),
            'config': self.config
        }
    
    async def pause_pipeline(self) -> Dict[str, str]:
        """Pause the pipeline execution"""
        if self.status == PipelineStatus.RUNNING:
            self.status = PipelineStatus.PAUSED
            logger.info("Pipeline paused")
            return {'status': 'paused', 'message': 'Pipeline execution paused'}
        else:
            return {'status': 'not_running', 'message': 'Pipeline is not running'}
    
    async def resume_pipeline(self) -> Dict[str, str]:
        """Resume the pipeline execution"""
        if self.status == PipelineStatus.PAUSED:
            self.status = PipelineStatus.RUNNING
            logger.info("Pipeline resumed")
            return {'status': 'resumed', 'message': 'Pipeline execution resumed'}
        else:
            return {'status': 'not_paused', 'message': 'Pipeline is not paused'}
    
    async def _process_job_queue(self) -> Dict[str, Any]:
        """Process all jobs in the queue"""
        results = {
            'processed_jobs': [],
            'failed_jobs': [],
            'skipped_jobs': []
        }
        
        # Process jobs in batches
        batch_size = self.config['batch_size']
        
        while self.job_queue and self.status == PipelineStatus.RUNNING:
            # Get next batch
            batch = self.job_queue[:batch_size]
            self.job_queue = self.job_queue[batch_size:]
            
            # Process batch
            batch_results = await self._process_job_batch(batch)
            
            # Update results
            results['processed_jobs'].extend(batch_results['successful'])
            results['failed_jobs'].extend(batch_results['failed'])
            
            # Update metrics
            self.metrics.jobs_processed += len(batch)
            self.metrics.jobs_successful += len(batch_results['successful'])
            self.metrics.jobs_failed += len(batch_results['failed'])
            
            # Check if pipeline should pause
            if self.status == PipelineStatus.PAUSED:
                logger.info("Pipeline paused, stopping job processing")
                break
        
        return results
    
    async def _process_job_batch(self, batch: List[IngestionJob]) -> Dict[str, List]:
        """Process a batch of jobs in parallel"""
        results = {'successful': [], 'failed': []}
        
        # Create tasks for parallel processing
        tasks = []
        for job in batch:
            task = asyncio.create_task(self._process_single_job(job))
            tasks.append(task)
        
        # Wait for all tasks to complete
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(completed_tasks):
            job = batch[i]
            
            if isinstance(result, Exception):
                logger.error(
                    "Job processing failed",
                    job_id=job.job_id,
                    error=str(result)
                )
                results['failed'].append({
                    'job_id': job.job_id,
                    'error': str(result)
                })
                self.failed_jobs.append(job)
            else:
                logger.info("Job processed successfully", job_id=job.job_id)
                results['successful'].append(result)
                self.completed_jobs.append(job)
        
        return results
    
    async def _process_single_job(self, job: IngestionJob) -> Dict[str, Any]:
        """Process a single ingestion job"""
        try:
            logger.info("Processing job", job_id=job.job_id, source=job.source_path)
            
            # Add to active jobs
            self.active_jobs[job.job_id] = job
            
            # Validate job before processing
            validation_result = await self._validate_job_execution(job)
            if not validation_result['valid']:
                raise ValueError(f"Job validation failed: {validation_result['errors']}")
            
            # Load document content
            content = await self._load_document_content(job)
            
            # Validate document content
            content_validation = await self._validate_document_content(content, job)
            if not content_validation['valid']:
                raise ValueError(f"Content validation failed: {content_validation['errors']}")
            
            # Process document
            result = await self._process_document(job, content)
            
            # Remove from active jobs
            del self.active_jobs[job.job_id]
            
            # Update metrics
            if result.get('success'):
                self.metrics.documents_created += 1
                self.metrics.chunks_created += result.get('chunks_created', 0)
            
            # Log success
            await self._log_job_completion(job, result)
            
            return result
            
        except Exception as e:
            # Handle job failure
            job.retry_count += 1
            
            # Remove from active jobs
            if job.job_id in self.active_jobs:
                del self.active_jobs[job.job_id]
            
            # Check if should retry
            if job.retry_count < job.max_retries:
                logger.warning(
                    "Job failed, will retry",
                    job_id=job.job_id,
                    retry_count=job.retry_count,
                    max_retries=job.max_retries,
                    error=str(e)
                )
                # Add back to queue for retry
                self.job_queue.append(job)
            else:
                logger.error(
                    "Job failed permanently",
                    job_id=job.job_id,
                    retry_count=job.retry_count,
                    error=str(e)
                )
                await self._log_job_failure(job, str(e))
            
            raise
    
    async def _load_document_content(self, job: IngestionJob) -> str:
        """Load document content based on source type"""
        if job.source_type == DocumentSource.LOCAL_FILE:
            return await self._load_local_file(job.source_path)
        elif job.source_type == DocumentSource.URL_DOWNLOAD:
            return await self._download_from_url(job.source_path)
        elif job.source_type == DocumentSource.API_FETCH:
            return await self._fetch_from_api(job.source_path, job.metadata)
        else:
            raise ValueError(f"Unsupported source type: {job.source_type}")
    
    async def _load_local_file(self, file_path: str) -> str:
        """Load content from local file"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if path.suffix.lower() == '.txt':
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                return await f.read()
        else:
            # Use document processor for other formats
            return await self.document_processor.extract_text_from_file(file_path)
    
    async def _download_from_url(self, url: str) -> str:
        """Download and extract content from URL"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    return content
                else:
                    raise Exception(f"Failed to download from URL: {response.status}")
    
    async def _fetch_from_api(self, api_endpoint: str, metadata: Dict[str, Any]) -> str:
        """Fetch content from API endpoint"""
        # Implementation depends on specific API
        # This is a placeholder for API integration
        raise NotImplementedError("API fetching not implemented yet")
    
    async def _process_document(self, job: IngestionJob, content: str) -> Dict[str, Any]:
        """Process document content and create database records"""
        try:
            session = await get_async_session()
            
            # Extract metadata
            metadata = await self.metadata_extractor.extract_metadata(
                content, Path(job.source_path).name
            )
            metadata.update(job.metadata)
            
            # Create document record
            document = await self._create_document_record(job, content, metadata, session)
            
            # Chunk document
            chunks = await self.chunker.chunk_document(
                text=content,
                document_type=job.document_type,
                source_name=Path(job.source_path).name,
                metadata=metadata
            )
            
            # Process and store chunks
            await self._process_and_store_chunks(
                chunks, str(document.id), document.user_id, session
            )
            
            # Update document status
            await self._update_document_status(
                str(document.id), ProcessingStatus.COMPLETED, session
            )
            
            await session.close()
            
            return {
                'success': True,
                'job_id': job.job_id,
                'document_id': str(document.id),
                'chunks_created': len(chunks),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(
                "Document processing failed",
                job_id=job.job_id,
                error=str(e),
                exc_info=True
            )
            return {
                'success': False,
                'job_id': job.job_id,
                'error': str(e)
            }
    
    async def _validate_job(self, job: IngestionJob) -> Dict[str, Any]:
        """Validate job configuration"""
        errors = []
        
        # Check required fields
        if not job.job_id:
            errors.append("Job ID is required")
        
        if not job.source_path:
            errors.append("Source path is required")
        
        if not job.document_type:
            errors.append("Document type is required")
        
        # Check source path exists (for local files)
        if job.source_type == DocumentSource.LOCAL_FILE:
            if not Path(job.source_path).exists():
                errors.append(f"Source file does not exist: {job.source_path}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    async def _validate_job_execution(self, job: IngestionJob) -> Dict[str, Any]:
        """Validate job before execution"""
        errors = []
        
        # Check if document already exists
        session = await get_async_session()
        try:
            existing_doc = await session.execute(
                select(Document).where(
                    Document.filename == Path(job.source_path).name
                )
            )
            if existing_doc.scalar_one_or_none():
                errors.append("Document already exists in database")
        finally:
            await session.close()
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    async def _validate_document_content(
        self, 
        content: str, 
        job: IngestionJob
    ) -> Dict[str, Any]:
        """Validate document content against rules"""
        errors = []
        
        for rule in self.validation_rules:
            if not await self._apply_validation_rule(rule, content, job):
                errors.append(rule.error_message)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    async def _apply_validation_rule(
        self, 
        rule: ValidationRule, 
        content: str, 
        job: IngestionJob
    ) -> bool:
        """Apply a single validation rule"""
        if rule.rule_type == "content_length":
            min_length = rule.parameters.get('min_length', 0)
            max_length = rule.parameters.get('max_length', float('inf'))
            return min_length <= len(content) <= max_length
        
        elif rule.rule_type == "file_size":
            if job.source_type == DocumentSource.LOCAL_FILE:
                file_size = Path(job.source_path).stat().st_size
                max_size = rule.parameters.get('max_size_mb', 50) * 1024 * 1024
                return file_size <= max_size
        
        elif rule.rule_type == "legal_keywords":
            min_keywords = rule.parameters.get('min_keywords', 5)
            # Simple keyword check - can be enhanced
            legal_keywords = ['section', 'act', 'court', 'judgment', 'law', 'legal']
            content_lower = content.lower()
            keyword_count = sum(1 for keyword in legal_keywords if keyword in content_lower)
            return keyword_count >= min_keywords
        
        return True
    
    def _load_pipeline_config(self) -> Dict[str, Any]:
        """Load pipeline configuration"""
        return {
            'batch_size': getattr(settings, 'PIPELINE_BATCH_SIZE', 10),
            'max_parallel_workers': getattr(settings, 'PIPELINE_MAX_WORKERS', 5),
            'retry_attempts': getattr(settings, 'PIPELINE_RETRY_ATTEMPTS', 3),
            'validation_enabled': getattr(settings, 'PIPELINE_VALIDATION_ENABLED', True),
            'monitoring_enabled': getattr(settings, 'PIPELINE_MONITORING_ENABLED', True),
            'queue_persistence': getattr(settings, 'PIPELINE_QUEUE_PERSISTENCE', True)
        }
    
    def _initialize_validation_rules(self) -> List[ValidationRule]:
        """Initialize document validation rules"""
        return [
            ValidationRule(
                name="content_length",
                rule_type="content_length",
                parameters={'min_length': 100, 'max_length': 1000000},
                error_message="Document content length is outside acceptable range"
            ),
            ValidationRule(
                name="file_size",
                rule_type="file_size",
                parameters={'max_size_mb': 50},
                error_message="File size exceeds maximum limit of 50MB"
            ),
            ValidationRule(
                name="legal_keywords",
                rule_type="legal_keywords",
                parameters={'min_keywords': 3},
                error_message="Document does not contain sufficient legal keywords"
            )
        ]
    
    async def _create_pipeline_directories(self):
        """Create necessary directories for pipeline operation"""
        directories = [
            "data/pipeline/queue",
            "data/pipeline/processing",
            "data/pipeline/completed",
            "data/pipeline/failed",
            "logs/pipeline"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    async def _load_job_queue(self):
        """Load pending jobs from persistent storage"""
        queue_file = Path("data/pipeline/queue/pending_jobs.json")
        
        if queue_file.exists():
            try:
                async with aiofiles.open(queue_file, 'r') as f:
                    content = await f.read()
                    job_data = json.loads(content)
                    
                    for job_dict in job_data:
                        job = IngestionJob(**job_dict)
                        self.job_queue.append(job)
                
                logger.info(f"Loaded {len(self.job_queue)} jobs from queue")
            except Exception as e:
                logger.error("Failed to load job queue", error=str(e))
    
    async def _persist_job(self, job: IngestionJob):
        """Persist job to storage"""
        if not self.config['queue_persistence']:
            return
        
        queue_file = Path("data/pipeline/queue/pending_jobs.json")
        
        try:
            # Load existing jobs
            existing_jobs = []
            if queue_file.exists():
                async with aiofiles.open(queue_file, 'r') as f:
                    content = await f.read()
                    existing_jobs = json.loads(content)
            
            # Add new job
            job_dict = asdict(job)
            job_dict['created_at'] = job.created_at.isoformat()
            existing_jobs.append(job_dict)
            
            # Save back to file
            async with aiofiles.open(queue_file, 'w') as f:
                await f.write(json.dumps(existing_jobs, indent=2))
                
        except Exception as e:
            logger.error("Failed to persist job", job_id=job.job_id, error=str(e))
    
    async def _log_pipeline_completion(self):
        """Log pipeline completion to audit log"""
        session = await get_async_session()
        try:
            audit_log = AuditLog(
                event_type="pipeline_completed",
                event_category="ingestion",
                event_description=f"Pipeline completed processing {self.metrics.jobs_processed} jobs",
                metadata={
                    'metrics': asdict(self.metrics),
                    'successful_jobs': self.metrics.jobs_successful,
                    'failed_jobs': self.metrics.jobs_failed
                }
            )
            session.add(audit_log)
            await session.commit()
        finally:
            await session.close()
    
    async def _log_pipeline_error(self, error: str):
        """Log pipeline error to audit log"""
        session = await get_async_session()
        try:
            audit_log = AuditLog(
                event_type="pipeline_failed",
                event_category="ingestion",
                event_description=f"Pipeline execution failed: {error}",
                metadata={'error': error, 'metrics': asdict(self.metrics)}
            )
            session.add(audit_log)
            await session.commit()
        finally:
            await session.close()
    
    async def _log_job_completion(self, job: IngestionJob, result: Dict[str, Any]):
        """Log job completion"""
        session = await get_async_session()
        try:
            audit_log = AuditLog(
                event_type="job_completed",
                event_category="ingestion",
                event_description=f"Job {job.job_id} completed successfully",
                metadata={
                    'job_id': job.job_id,
                    'source_path': job.source_path,
                    'document_type': job.document_type.value,
                    'result': result
                }
            )
            session.add(audit_log)
            await session.commit()
        finally:
            await session.close()
    
    async def _log_job_failure(self, job: IngestionJob, error: str):
        """Log job failure"""
        session = await get_async_session()
        try:
            audit_log = AuditLog(
                event_type="job_failed",
                event_category="ingestion",
                event_description=f"Job {job.job_id} failed: {error}",
                metadata={
                    'job_id': job.job_id,
                    'source_path': job.source_path,
                    'document_type': job.document_type.value,
                    'error': error,
                    'retry_count': job.retry_count
                }
            )
            session.add(audit_log)
            await session.commit()
        finally:
            await session.close()
    
    # Helper methods from knowledge base ingestion service
    async def _create_document_record(self, job, content, metadata, session):
        """Create document record in database"""
        # Implementation similar to knowledge base ingestion service
        pass
    
    async def _process_and_store_chunks(self, chunks, document_id, user_id, session):
        """Process and store document chunks"""
        # Implementation similar to knowledge base ingestion service
        pass
    
    async def _update_document_status(self, document_id, status, session):
        """Update document processing status"""
        # Implementation similar to knowledge base ingestion service
        pass