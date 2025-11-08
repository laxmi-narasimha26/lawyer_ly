#!/usr/bin/env python3
"""
Run token-aware ingestion on available Supreme Court PDFs
"""
import asyncio
import sys
import os
from pathlib import Path

# Add legal_kb to path
sys.path.insert(0, str(Path(__file__).parent / "legal_kb"))

from ingest_with_token_chunking import TokenAwareLegalIngestion

async def main():
    """Run token-aware ingestion on available data"""
    ingestion = TokenAwareLegalIngestion()
    
    try:
        await ingestion.initialize()
        
        # Ingest from the data directory where we have PDFs
        await ingestion.ingest_supreme_court_judgments("data/supreme_court_judgments/extracted/judgments")
        
    except Exception as e:
        print(f"Ingestion failed: {e}")
        return 1
    finally:
        await ingestion.cleanup()
    
    print("Token-aware ingestion completed successfully!")
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)