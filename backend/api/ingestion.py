"""
API endpoints for automated document ingestion pipeline
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, UploadFile, File
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from pathlib import Path

from services.automated_ingestion_pipeline import (
    AutomatedIngestionPipeline,
    IngestionJob,
    DocumentSource,
    PipelineStatus
)
from database.models import DocumentType
from utils.monitoring import metrics_collector
from api.auth import get_current_user
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])

# Pydantic models for API
class JobRequest(BaseModel):
    """Request model for creating an ingestion job"""
    source_path: str = Field(..., description="Path to source document")
    document_type: DocumentType = Field(..., description="Type of document")
    source_type: DocumentSource = Field(default=DocumentSource.LOCAL_FILE, description="Source type")
    priority: int = Field(default=1, description="Job priority (1-10)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

class BatchJobRequest(BaseModel):
    """Request model for creating batch jobs"""
    jobs: List[JobRequest] = Field(..., description="List of jobs to create")

class DirectoryJobRequest(BaseModel):
    """Request model for creating jobs from directory"""
    directory_path: str = Field(..., description="Directory path")
    document_type: DocumentType = Field(..., description="Document type")
    recursive: bool = Field(default=True, description="Scan subdirectories")

class JobResponse(BaseModel):
    """Response model for job operations"""
    job_id: str
    status: str
    message: Optional[str] = None

class PipelineStatusResponse(BaseModel):
    """Response model for pipeline status"""
    status: str
    queue_size: int
    active_jobs: int
    completed_jobs: int
    failed_jobs: int
    metrics: Dict[str, Any]

class IngestionResultResponse(BaseModel):
    """Response model for ingestion results"""
    status: str
    jobs_processed: int
    jobs_successful: int
    jobs_failed: int
    documents_created: int
    chunks_created: int
    processing_time: float

# Global pipeline instance
pipeline = AutomatedIngestionPipeline()

@router.post("/jobs", response_model=JobResponse)
async def create_job(
    job_request: JobRequest,
    current_user = Depends(get_current_user)
):
    """
    Create a new ingestion job
    """
    try:
        # Create job
        job = IngestionJob(
            job_id=f"job_{uuid.uuid4().hex[:8]}",
            source_type=job_request.source_type,
            source_path=job_request.source_path,
            document_type=job_request.document_type,
            priority=job_request.priority,
            metadata=job_request.metadata or {}
        )
        
        # Add user information to metadata
        job.metadata.update({
            'created_by': str(current_user.id),
            'created_by_email': current_user.email
        })
        
        # Add job to pipeline
        job_id = await pipeline.add_job(job)
        
        # Record metrics
        metrics_collector.record_counter("ingestion_jobs_created")
        
        logger.info(
            "Ingestion job created",
            job_id=job_id,
            user_id=str(current_user.id),
            document_type=job_request.document_type.value
        )
        
        return JobResponse(
            job_id=job_id,
            status="queued",
            message="Job created and added to queue"
        )
        
    except Exception as e:
        logger.error("Failed to create ingestion job", error=str(e), exc_info=True)
        metrics_collector.record_counter("ingestion_job_creation_errors")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jobs/batch", response_model=List[JobResponse])
async def create_batch_jobs(
    batch_request: BatchJobRequest,
    current_user = Depends(get_current_user)
):
    """
    Create multiple ingestion jobs
    """
    try:
        jobs = []
        responses = []
        
        for job_request in batch_request.jobs:
            job = IngestionJob(
                job_id=f"batch_{uuid.uuid4().hex[:8]}",
                source_type=job_request.source_type,
                source_path=job_request.source_path,
                document_type=job_request.document_type,
                priority=job_request.priority,
                metadata=job_request.metadata or {}
            )
            
            # Add user information
            job.metadata.update({
                'created_by': str(current_user.id),
                'created_by_email': current_user.email,
                'batch_operation': True
            })
            
            jobs.append(job)
        
        # Add jobs to pipeline
        job_ids = await pipeline.add_batch_jobs(jobs)
        
        # Create responses
        for job_id in job_ids:
            responses.append(JobResponse(
                job_id=job_id,
                status="queued",
                message="Job created and added to queue"
            ))
        
        # Record metrics
        metrics_collector.record_counter("ingestion_batch_jobs_created", len(job_ids))
        
        logger.info(
            "Batch ingestion jobs created",
            job_count=len(job_ids),
            user_id=str(current_user.id)
        )
        
        return responses
        
    except Exception as e:
        logger.error("Failed to create batch jobs", error=str(e), exc_info=True)
        metrics_collector.record_counter("ingestion_batch_creation_errors")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jobs/directory", response_model=List[JobResponse])
async def create_directory_jobs(
    dir_request: DirectoryJobRequest,
    current_user = Depends(get_current_user)
):
    """
    Create ingestion jobs from files in a directory
    """
    try:
        # Create jobs from directory
        job_ids = await pipeline.create_jobs_from_directory(
            dir_request.directory_path,
            dir_request.document_type,
            dir_request.recursive
        )
        
        # Create responses
        responses = []
        for job_id in job_ids:
            responses.append(JobResponse(
                job_id=job_id,
                status="queued",
                message="Job created from directory scan"
            ))
        
        # Record metrics
        metrics_collector.record_counter("ingestion_directory_jobs_created", len(job_ids))
        
        logger.info(
            "Directory ingestion jobs created",
            directory=dir_request.directory_path,
            job_count=len(job_ids),
            user_id=str(current_user.id)
        )
        
        return responses
        
    except Exception as e:
        logger.error("Failed to create directory jobs", error=str(e), exc_info=True)
        metrics_collector.record_counter("ingestion_directory_creation_errors")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/upload", response_model=JobResponse)
async def upload_and_ingest(
    file: UploadFile = File(...),
    document_type: DocumentType = DocumentType.USER_DOCUMENT,
    current_user = Depends(get_current_user)
):
    """
    Upload a file and create an ingestion job
    """
    try:
        # Create upload directory
        upload_dir = Path("data/uploads") / str(current_user.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded file
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Create ingestion job
        job = IngestionJob(
            job_id=f"upload_{uuid.uuid4().hex[:8]}",
            source_type=DocumentSource.LOCAL_FILE,
            source_path=str(file_path),
            document_type=document_type,
            metadata={
                'uploaded_by': str(current_user.id),
                'uploaded_by_email': current_user.email,
                'original_filename': file.filename,
                'file_size': len(content),
                'upload_timestamp': datetime.utcnow().isoformat()
            }
        )
        
        # Add job to pipeline
        job_id = await pipeline.add_job(job)
        
        # Record metrics
        metrics_collector.record_counter("ingestion_file_uploads")
        metrics_collector.record_gauge("ingestion_upload_file_size", len(content))
        
        logger.info(
            "File uploaded and ingestion job created",
            job_id=job_id,
            filename=file.filename,
            file_size=len(content),
            user_id=str(current_user.id)
        )
        
        return JobResponse(
            job_id=job_id,
            status="queued",
            message=f"File '{file.filename}' uploaded and queued for processing"
        )
        
    except Exception as e:
        logger.error("Failed to upload and create job", error=str(e), exc_info=True)
        metrics_collector.record_counter("ingestion_upload_errors")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/pipeline/start", response_model=IngestionResultResponse)
async def start_pipeline(
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """
    Start the ingestion pipeline
    """
    try:
        # Check if user has admin privileges
        if current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only administrators can start the pipeline"
            )
        
        # Start pipeline in background
        result = await pipeline.start_pipeline()
        
        # Record metrics
        metrics_collector.record_counter("ingestion_pipeline_starts")
        
        logger.info(
            "Ingestion pipeline started",
            user_id=str(current_user.id),
            result_status=result['status']
        )
        
        return IngestionResultResponse(
            status=result['status'],
            jobs_processed=result['metrics']['jobs_processed'],
            jobs_successful=result['metrics']['jobs_successful'],
            jobs_failed=result['metrics']['jobs_failed'],
            documents_created=result['metrics']['documents_created'],
            chunks_created=result['metrics']['chunks_created'],
            processing_time=result['metrics']['total_processing_time']
        )
        
    except Exception as e:
        logger.error("Failed to start pipeline", error=str(e), exc_info=True)
        metrics_collector.record_counter("ingestion_pipeline_start_errors")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pipeline/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    current_user = Depends(get_current_user)
):
    """
    Get current pipeline status
    """
    try:
        status = await pipeline.get_pipeline_status()
        
        return PipelineStatusResponse(
            status=status['status'],
            queue_size=status['queue_size'],
            active_jobs=status['active_jobs'],
            completed_jobs=status['completed_jobs'],
            failed_jobs=status['failed_jobs'],
            metrics=status['metrics']
        )
        
    except Exception as e:
        logger.error("Failed to get pipeline status", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pipeline/pause")
async def pause_pipeline(
    current_user = Depends(get_current_user)
):
    """
    Pause the ingestion pipeline
    """
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only administrators can pause the pipeline"
            )
        
        result = await pipeline.pause_pipeline()
        
        logger.info(
            "Pipeline pause requested",
            user_id=str(current_user.id),
            result=result
        )
        
        return result
        
    except Exception as e:
        logger.error("Failed to pause pipeline", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pipeline/resume")
async def resume_pipeline(
    current_user = Depends(get_current_user)
):
    """
    Resume the ingestion pipeline
    """
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only administrators can resume the pipeline"
            )
        
        result = await pipeline.resume_pipeline()
        
        logger.info(
            "Pipeline resume requested",
            user_id=str(current_user.id),
            result=result
        )
        
        return result
        
    except Exception as e:
        logger.error("Failed to resume pipeline", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/dashboard")
async def get_dashboard_metrics(
    current_user = Depends(get_current_user)
):
    """
    Get metrics for monitoring dashboard
    """
    try:
        dashboard_data = metrics_collector.get_pipeline_dashboard_data()
        
        return dashboard_data
        
    except Exception as e:
        logger.error("Failed to get dashboard metrics", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def get_system_health():
    """
    Get system health status
    """
    try:
        health_status = await metrics_collector.get_system_health()
        
        return health_status
        
    except Exception as e:
        logger.error("Failed to get system health", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))