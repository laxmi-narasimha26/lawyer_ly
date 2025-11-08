#!/usr/bin/env python3
"""
Start vectorization of BNS and Supreme Court documents
"""
import asyncio
import sys
import os
from pathlib import Path

# Add legal_kb to path
sys.path.append('legal_kb')

async def start_vectorization():
    """Start the document vectorization process"""
    print("🚀 STARTING LEGAL DOCUMENT VECTORIZATION")
    print("=" * 60)
    
    try:
        # Import services
        from legal_kb.processors.bns_processor import BNSProcessor
        from legal_kb.processors.sc_judgment_processor import SCJudgmentProcessor
        from legal_kb.services.embedding_service import EmbeddingService
        from legal_kb.database.connection import get_db_manager
        from legal_kb.config import config
        
        # Initialize services
        print("📋 Initializing services...")
        db_manager = await get_db_manager()
        embedding_service = EmbeddingService(config.OPENAI_API_KEY)
        
        # 1. Process BNS PDF
        print("\n📖 Processing BNS Act...")
        bns_processor = BNSProcessor(embedding_service, db_manager)
        
        bns_path = Path("data/BNS.pdf.pdf")
        if bns_path.exists():
            print(f"   Found BNS PDF: {bns_path} ({bns_path.stat().st_size / 1024 / 1024:.1f} MB)")
            
            # Process BNS (this will take a few minutes)
            bns_chunks = await bns_processor.process_bns_pdf(str(bns_path))
            print(f"✅ BNS Processing Complete: {len(bns_chunks)} sections processed")
        else:
            print("❌ BNS PDF not found!")
        
        # 2. Process Supreme Court Judgments (2020 only for testing)
        print("\n⚖️ Processing Supreme Court Judgments (2020)...")
        sc_processor = SCJudgmentProcessor(embedding_service, db_manager)
        
        sc_dir = Path("data/supreme_court_judgments")
        if sc_dir.exists():
            # Find 2020 PDFs
            pdf_files = list(sc_dir.glob("**/2020*.pdf"))[:10]  # Start with first 10 files
            
            if pdf_files:
                print(f"   Found {len(pdf_files)} 2020 Supreme Court PDFs (processing first 10)")
                
                processed_count = 0
                for pdf_file in pdf_files:
                    try:
                        print(f"   Processing: {pdf_file.name}")
                        chunks = await sc_processor.process_judgment_pdf(str(pdf_file), 2020)
                        processed_count += len(chunks)
                        print(f"     ✅ {len(chunks)} paragraphs processed")
                    except Exception as e:
                        print(f"     ❌ Error processing {pdf_file.name}: {e}")
                
                print(f"✅ Supreme Court Processing Complete: {processed_count} paragraphs processed")
            else:
                print("❌ No 2020 Supreme Court PDFs found!")
        else:
            print("❌ Supreme Court judgments directory not found!")
        
        # 3. Verify vectorization
        print("\n🔍 Verifying vectorization...")
        
        # Check statute count
        async with db_manager.get_postgres_connection() as conn:
            statute_count = await conn.fetchval("SELECT COUNT(*) FROM statute_chunks")
            case_count = await conn.fetchval("SELECT COUNT(*) FROM case_chunks")
            
            print(f"✅ Database Status:")
            print(f"   - Statute chunks: {statute_count}")
            print(f"   - Case chunks: {case_count}")
        
        # 4. Test search functionality
        print("\n🔍 Testing search functionality...")
        
        if statute_count > 0:
            # Test a simple search
            test_embedding = await embedding_service.get_embedding("robbery punishment")
            
            async with db_manager.get_postgres_connection() as conn:
                results = await conn.fetch("""
                    SELECT id, title, 1 - (embedding <=> $1) as similarity
                    FROM statute_chunks 
                    ORDER BY embedding <=> $1 
                    LIMIT 3
                """, test_embedding)
                
                print("✅ Search Test Results for 'robbery punishment':")
                for result in results:
                    print(f"   - {result['id']}: {result['title']} (similarity: {result['similarity']:.3f})")
        
        print("\n" + "=" * 60)
        print("🎉 VECTORIZATION COMPLETE!")
        print("The system is now ready for RAG queries.")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(start_vectorization())