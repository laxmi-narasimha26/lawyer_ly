#!/usr/bin/env python3
"""
Pipeline management script for automated document ingestion
"""
import asyncio
import sys
import argparse
from pathlib import Path
from typing import List

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.automated_ingestion_pipeline import (
    AutomatedIngestionPipeline, 
    IngestionJob, 
    DocumentSource
)
from database.models import DocumentType
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

async def start_pipeline():
    """Start the ingestion pipeline"""
    pipeline = AutomatedIngestionPipeline()
    
    print("Starting automated ingestion pipeline...")
    result = await pipeline.start_pipeline()
    
    print("\nPipeline Results:")
    print(f"Status: {result['status']}")
    print(f"Jobs processed: {result['metrics']['jobs_processed']}")
    print(f"Successful: {result['metrics']['jobs_successful']}")
    print(f"Failed: {result['metrics']['jobs_failed']}")
    print(f"Documents created: {result['metrics']['documents_created']}")
    print(f"Chunks created: {result['metrics']['chunks_created']}")
    print(f"Total processing time: {result['metrics']['total_processing_time']:.2f}s")

async def add_directory_jobs(directory: str, doc_type: str, recursive: bool = True):
    """Add jobs from a directory"""
    pipeline = AutomatedIngestionPipeline()
    
    # Convert string to DocumentType enum
    document_type = DocumentType(doc_type.lower())
    
    print(f"Creating jobs from directory: {directory}")
    print(f"Document type: {document_type.value}")
    print(f"Recursive: {recursive}")
    
    job_ids = await pipeline.create_jobs_from_directory(
        directory, document_type, recursive
    )
    
    print(f"\nCreated {len(job_ids)} jobs:")
    for job_id in job_ids:
        print(f"  - {job_id}")

async def add_single_job(file_path: str, doc_type: str):
    """Add a single file job"""
    pipeline = AutomatedIngestionPipeline()
    
    document_type = DocumentType(doc_type.lower())
    
    job = IngestionJob(
        job_id=f"single_{Path(file_path).stem}",
        source_type=DocumentSource.LOCAL_FILE,
        source_path=file_path,
        document_type=document_type,
        metadata={
            'source': 'manual_addition',
            'filename': Path(file_path).name
        }
    )
    
    job_id = await pipeline.add_job(job)
    print(f"Added job: {job_id}")

async def get_status():
    """Get pipeline status"""
    pipeline = AutomatedIngestionPipeline()
    status = await pipeline.get_pipeline_status()
    
    print("Pipeline Status:")
    print(f"  Status: {status['status']}")
    print(f"  Queue size: {status['queue_size']}")
    print(f"  Active jobs: {status['active_jobs']}")
    print(f"  Completed jobs: {status['completed_jobs']}")
    print(f"  Failed jobs: {status['failed_jobs']}")
    
    print("\nMetrics:")
    metrics = status['metrics']
    for key, value in metrics.items():
        if key not in ['start_time', 'end_time']:
            print(f"  {key}: {value}")

async def create_sample_jobs():
    """Create sample jobs for testing"""
    pipeline = AutomatedIngestionPipeline()
    
    # Create sample data directory
    sample_dir = Path("data/sample_documents")
    sample_dir.mkdir(parents=True, exist_ok=True)
    
    # Create sample documents
    sample_docs = [
        {
            'filename': 'sample_constitution.txt',
            'content': '''
CONSTITUTION OF INDIA

PREAMBLE

WE, THE PEOPLE OF INDIA, having solemnly resolved to constitute India into a 
SOVEREIGN SOCIALIST SECULAR DEMOCRATIC REPUBLIC and to secure to all its citizens:

JUSTICE, social, economic and political;
LIBERTY of thought, expression, belief, faith and worship;
EQUALITY of status and of opportunity;

Article 14. Equality before law
The State shall not deny to any person equality before the law or the equal 
protection of the laws within the territory of India.

Article 19. Protection of certain rights regarding freedom of speech, etc.
All citizens shall have the right to freedom of speech and expression.

Article 21. Protection of life and personal liberty
No person shall be deprived of his life or personal liberty except according 
to procedure established by law.
            ''',
            'doc_type': DocumentType.STATUTE
        },
        {
            'filename': 'sample_case.txt',
            'content': '''
MANEKA GANDHI v. UNION OF INDIA
(1978) 1 SCC 248

JUDGMENT

BHAGWATI, J.

This case arises from the impounding of the passport of Smt. Maneka Gandhi 
under Section 10(3)(c) of the Passports Act, 1967.

ARTICLE 21 - RIGHT TO LIFE AND PERSONAL LIBERTY

The fundamental question in this case is the scope and ambit of Article 21 
of the Constitution, which guarantees that "No person shall be deprived of 
his life or personal liberty except according to procedure established by law."

HELD:
Article 21 does not merely require compliance with some semblance of procedure, 
but demands that the procedure must be fair, just and reasonable.
            ''',
            'doc_type': DocumentType.CASE_LAW
        }
    ]
    
    # Write sample documents
    for doc in sample_docs:
        file_path = sample_dir / doc['filename']
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(doc['content'])
    
    # Create jobs
    jobs = []
    for doc in sample_docs:
        file_path = sample_dir / doc['filename']
        job = IngestionJob(
            job_id=f"sample_{doc['filename'].split('.')[0]}",
            source_type=DocumentSource.LOCAL_FILE,
            source_path=str(file_path),
            document_type=doc['doc_type'],
            metadata={
                'source': 'sample_data',
                'filename': doc['filename']
            }
        )
        jobs.append(job)
    
    job_ids = await pipeline.add_batch_jobs(jobs)
    
    print(f"Created {len(job_ids)} sample jobs:")
    for job_id in job_ids:
        print(f"  - {job_id}")

def main():
    parser = argparse.ArgumentParser(description='Manage automated ingestion pipeline')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Start pipeline command
    subparsers.add_parser('start', help='Start the ingestion pipeline')
    
    # Add directory command
    dir_parser = subparsers.add_parser('add-dir', help='Add jobs from directory')
    dir_parser.add_argument('directory', help='Directory path')
    dir_parser.add_argument('--type', required=True, 
                           choices=['statute', 'case_law', 'regulation', 'user_document'],
                           help='Document type')
    dir_parser.add_argument('--no-recursive', action='store_true',
                           help='Do not scan subdirectories')
    
    # Add single file command
    file_parser = subparsers.add_parser('add-file', help='Add single file job')
    file_parser.add_argument('file_path', help='File path')
    file_parser.add_argument('--type', required=True,
                            choices=['statute', 'case_law', 'regulation', 'user_document'],
                            help='Document type')
    
    # Status command
    subparsers.add_parser('status', help='Get pipeline status')
    
    # Create samples command
    subparsers.add_parser('create-samples', help='Create sample jobs for testing')
    
    args = parser.parse_args()
    
    if args.command == 'start':
        asyncio.run(start_pipeline())
    elif args.command == 'add-dir':
        asyncio.run(add_directory_jobs(
            args.directory, 
            args.type, 
            not args.no_recursive
        ))
    elif args.command == 'add-file':
        asyncio.run(add_single_job(args.file_path, args.type))
    elif args.command == 'status':
        asyncio.run(get_status())
    elif args.command == 'create-samples':
        asyncio.run(create_sample_jobs())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()