#!/usr/bin/env python3
"""
Script to ingest Supreme Court and High Court cases into the knowledge base
"""
import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.knowledge_base_ingestion import KnowledgeBaseIngestionService
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

async def main():
    """Main ingestion function"""
    try:
        logger.info("Starting case law ingestion process")
        
        # Initialize ingestion service
        ingestion_service = KnowledgeBaseIngestionService()
        
        # Ingest case law
        results = await ingestion_service.ingest_case_law()
        
        # Print results
        print("\n" + "="*60)
        print("CASE LAW INGESTION RESULTS")
        print("="*60)
        print(f"Total cases: {results['total_cases']}")
        print(f"Successfully processed: {len(results['processed_cases'])}")
        print(f"Failed: {len(results['failed_cases'])}")
        
        if results['processed_cases']:
            print("\nSuccessfully processed cases:")
            for case in results['processed_cases']:
                print(f"  ✓ {case['name']} - {case['status']}")
                if case['status'] == 'success':
                    print(f"    Document ID: {case['document_id']}")
                    print(f"    Chunks created: {case['chunks_created']}")
        
        if results['failed_cases']:
            print("\nFailed cases:")
            for case in results['failed_cases']:
                print(f"  ✗ {case['name']} - {case.get('error', 'Unknown error')}")
        
        print(f"\nStatistics:")
        for key, value in results['statistics'].items():
            print(f"  {key}: {value}")
        
        logger.info("Case law ingestion completed successfully")
        
    except Exception as e:
        logger.error("Case law ingestion failed", error=str(e), exc_info=True)
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())