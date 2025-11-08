#!/usr/bin/env python3
"""
Fix API key issue and start vectorization with proper error handling
"""
import asyncio
import os
import sys
from pathlib import Path

# Set the working API key directly in environment
WORKING_API_KEY = "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"

# Force set environment variable
os.environ["OPENAI_API_KEY"] = WORKING_API_KEY

# Add legal_kb to path
sys.path.append('legal_kb')

async def fix_and_vectorize():
    """Fix API key and start vectorization"""
    print("🔧 FIXING API KEY AND STARTING VECTORIZATION")
    print("=" * 60)
    
    try:
        # Import after setting environment
        from legal_kb.processors.bns_processor import BNSProcessor
        from legal_kb.processors.sc_judgment_processor import SCJudgmentProcessor
        from legal_kb.services.embedding_service import EmbeddingService
        from legal_kb.database.connection import get_db_manager
        
        # Initialize services with explicit API key
        print("📋 Initializing services with working API key...")
        db_manager = await get_db_manager()
        embedding_service = EmbeddingService(WORKING_API_KEY)
        
        # Test API connection first
        print("🧪 Testing API connection...")
        test_result = await embedding_service.test_api_connection()
        if not test_result:
            print("❌ API connection test failed!")
            return
        print("✅ API connection working!")
        
        # 1. Process BNS PDF
        print("\n📖 Processing BNS Act...")
        bns_processor = BNSProcessor(embedding_service, db_manager)
        
        bns_path = Path("data/BNS.pdf.pdf")
        if bns_path.exists():
            print(f"   Found BNS PDF: {bns_path} ({bns_path.stat().st_size / 1024 / 1024:.1f} MB)")
            
            try:
                bns_chunks = await bns_processor.process_bns_pdf(str(bns_path))
                print(f"✅ BNS Processing Complete: {len(bns_chunks)} sections processed")
            except Exception as e:
                print(f"❌ BNS Processing Failed: {e}")
        else:
            print("❌ BNS PDF not found!")
        
        # 2. Process Supreme Court Judgments (2020 only, limited to 5 files for testing)
        print("\n⚖️ Processing Supreme Court Judgments (2020 - Limited Test)...")
        sc_processor = SCJudgmentProcessor(embedding_service, db_manager)
        
        sc_dir = Path("data/supreme_court_judgments")
        if sc_dir.exists():
            # Find 2020 PDFs - limit to 5 for testing
            pdf_files = list(sc_dir.glob("**/2020*.pdf"))[:5]
            
            if pdf_files:
                print(f"   Found {len(pdf_files)} 2020 Supreme Court PDFs (processing first 5)")
                
                processed_count = 0
                for i, pdf_file in enumerate(pdf_files, 1):
                    try:
                        print(f"   [{i}/5] Processing: {pdf_file.name}")
                        chunks = await sc_processor.process_judgment_pdf(str(pdf_file), 2020)
                        processed_count += len(chunks)
                        print(f"     ✅ {len(chunks)} paragraphs processed")
                    except Exception as e:
                        print(f"     ❌ Error processing {pdf_file.name}: {e}")
                        continue
                
                print(f"✅ Supreme Court Processing Complete: {processed_count} paragraphs processed")
            else:
                print("❌ No 2020 Supreme Court PDFs found!")
        else:
            print("❌ Supreme Court judgments directory not found!")
        
        # 3. Verify vectorization
        print("\n🔍 Verifying vectorization...")
        
        # Check database counts
        async with db_manager.get_postgres_connection() as conn:
            try:
                statute_count = await conn.fetchval("SELECT COUNT(*) FROM statute_chunks")
                case_count = await conn.fetchval("SELECT COUNT(*) FROM case_chunks")
                
                print(f"✅ Database Status:")
                print(f"   - Statute chunks: {statute_count}")
                print(f"   - Case chunks: {case_count}")
                
                if statute_count > 0 or case_count > 0:
                    print("🎉 VECTORIZATION SUCCESSFUL!")
                    print("The system now has vectorized legal documents ready for RAG queries.")
                else:
                    print("⚠️ No documents were vectorized. Check the processing logs above.")
                    
            except Exception as e:
                print(f"❌ Database verification failed: {e}")
        
        print("\n" + "=" * 60)
        print("🏁 VECTORIZATION PROCESS COMPLETE!")
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_and_vectorize())