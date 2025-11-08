#!/usr/bin/env python3
"""
Comprehensive system status check for Legal KB RAG System
"""
import asyncio
import os
import sys
from pathlib import Path

# Add legal_kb to path
sys.path.append('legal_kb')

async def check_system_status():
    """Check all system components and data status"""
    print("🔍 LEGAL KB RAG SYSTEM STATUS CHECK")
    print("=" * 60)
    
    # 1. Check Infrastructure
    print("\n📊 INFRASTRUCTURE STATUS:")
    
    # Database connection
    try:
        from legal_kb.database.connection import get_db_manager
        db_manager = await get_db_manager()
        connection_ok = await db_manager.test_connection()
        if connection_ok:
            print("✅ PostgreSQL + PGVector: Connected (Port 5433)")
        else:
            print("❌ PostgreSQL: Connection failed")
    except Exception as e:
        print(f"❌ PostgreSQL: Error - {e}")
    
    # Redis connection
    try:
        from legal_kb.services.cache_service import get_cache_service
        cache_service = get_cache_service()
        redis_ok = await cache_service.test_connection()
        if redis_ok:
            print("✅ Redis: Connected (Port 6380)")
        else:
            print("❌ Redis: Connection failed")
    except Exception as e:
        print(f"❌ Redis: Error - {e}")
    
    # OpenAI API
    try:
        from legal_kb.services.embedding_service import EmbeddingService
        embedding_service = EmbeddingService()
        api_ok = await embedding_service.test_api_connection()
        if api_ok:
            print("✅ OpenAI API: Connected")
        else:
            print("❌ OpenAI API: Connection failed")
    except Exception as e:
        print(f"❌ OpenAI API: Error - {e}")
    
    # 2. Check Data Status
    print("\n📚 DATA STATUS:")
    
    # BNS PDF
    bns_path = Path("data/BNS.pdf.pdf")
    if bns_path.exists():
        size_mb = bns_path.stat().st_size / (1024 * 1024)
        print(f"✅ BNS PDF: Available ({size_mb:.1f} MB)")
    else:
        print("❌ BNS PDF: Not found")
    
    # Supreme Court Judgments
    sc_dir = Path("data/supreme_court_judgments")
    if sc_dir.exists():
        pdf_files = list(sc_dir.glob("**/*.pdf"))
        total_size = sum(f.stat().st_size for f in pdf_files) / (1024 * 1024)
        print(f"✅ Supreme Court PDFs: {len(pdf_files)} files ({total_size:.1f} MB)")
    else:
        print("❌ Supreme Court PDFs: Directory not found")
    
    # 3. Check Database Schema
    print("\n🗄️ DATABASE SCHEMA STATUS:")
    
    try:
        db_manager = await get_db_manager()
        
        # Check if tables exist
        tables = await db_manager.get_table_list()
        required_tables = ['statute_chunks', 'case_chunks', 'cross_references']
        
        for table in required_tables:
            if table in tables:
                count = await db_manager.get_table_count(table)
                print(f"✅ Table {table}: Exists ({count} records)")
            else:
                print(f"❌ Table {table}: Not found")
                
    except Exception as e:
        print(f"❌ Database Schema: Error - {e}")
    
    # 4. Check Vectorization Status
    print("\n🔢 VECTORIZATION STATUS:")
    
    try:
        db_manager = await get_db_manager()
        
        # Check BNS vectorization
        bns_count = await db_manager.count_vectorized_documents("statute_chunks", "BNS")
        if bns_count > 0:
            print(f"✅ BNS Vectorization: {bns_count} sections processed")
        else:
            print("❌ BNS Vectorization: Not completed")
        
        # Check Supreme Court vectorization
        sc_count = await db_manager.count_vectorized_documents("case_chunks", "Supreme Court")
        if sc_count > 0:
            print(f"✅ Supreme Court Vectorization: {sc_count} paragraphs processed")
        else:
            print("❌ Supreme Court Vectorization: Not completed")
            
    except Exception as e:
        print(f"❌ Vectorization Check: Error - {e}")
    
    # 5. Overall Status
    print("\n🎯 OVERALL STATUS:")
    
    # Check if ready for RAG queries
    try:
        # Test a simple query
        from legal_kb.search.vector_search import VectorSearchEngine
        search_engine = VectorSearchEngine()
        test_results = await search_engine.test_search("robbery")
        
        if test_results and len(test_results) > 0:
            print("✅ RAG System: Ready for queries")
            print(f"   Test query 'robbery' returned {len(test_results)} results")
        else:
            print("❌ RAG System: Not ready - no search results")
            
    except Exception as e:
        print(f"❌ RAG System: Error - {e}")
    
    print("\n" + "=" * 60)
    print("Status check complete!")

if __name__ == "__main__":
    asyncio.run(check_system_status())