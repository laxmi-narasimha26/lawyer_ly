#!/usr/bin/env python3
"""
Setup script for Advanced Legal KB+RAG System
Sets environment variables and runs the system
"""
import os
import sys
import subprocess
import asyncio
from pathlib import Path

# Set environment variables
os.environ["OPENAI_API_KEY"] = "sk-proj-7yXjRXp9-dIjgnZG4GvYlJr-u_424mAt-l12JYaTRm0Ms0B2pdyWaGuQex6tcx6nfNwJteccwcT3BlbkFJFIrJRD84R4JhCzatEu3qXwhquTA4GyTj3py7Vasu2uFcA3JM1dfLXYXrhQ4zROTP09U37CNYQAth"

# Database settings (using SQLite for simplicity in testing)
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_DB"] = "legal_kb_test"
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "password"

# Redis settings
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"

# Data paths
os.environ["DATA_DIR"] = "data"
os.environ["BNS_PDF_PATH"] = "data/BNS.pdf.pdf"  # Note the double .pdf extension

def install_requirements():
    """Install required packages"""
    print("📦 Installing required packages...")
    
    packages = [
        "asyncio",
        "asyncpg",
        "redis",
        "openai>=1.0.0",
        "PyPDF2",
        "numpy",
        "python-dotenv",
        "psycopg2-binary",
        "aiofiles"
    ]
    
    for package in packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ Installed {package}")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Failed to install {package}: {e}")

def check_data_files():
    """Check if required data files exist"""
    print("\n📁 Checking data files...")
    
    bns_path = Path("data/BNS.pdf.pdf")
    sc_2020_path = Path("data/supreme_court_judgments/2020/english.zip")
    
    if bns_path.exists():
        print(f"✅ BNS PDF found: {bns_path}")
    else:
        print(f"❌ BNS PDF not found at {bns_path}")
        return False
    
    if sc_2020_path.exists():
        print(f"✅ SC 2020 data found: {sc_2020_path}")
    else:
        print(f"❌ SC 2020 data not found at {sc_2020_path}")
        return False
    
    return True

async def run_system_test():
    """Run the legal KB system test"""
    print("\n🚀 Running Legal KB+RAG System...")
    
    # Add legal_kb to Python path
    sys.path.insert(0, str(Path("legal_kb").absolute()))
    
    try:
        # Import and run the test
        from legal_kb.test_setup import main as test_main
        await test_main()
        
        print("\n✅ System test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ System test failed: {e}")
        return False

async def run_document_ingestion():
    """Run document ingestion pipeline"""
    print("\n📥 Running document ingestion...")
    
    # Add legal_kb to Python path
    sys.path.insert(0, str(Path("legal_kb").absolute()))
    
    try:
        # Import and run the ingestion
        from legal_kb.ingest_legal_documents import main as ingest_main
        await ingest_main()
        
        print("\n✅ Document ingestion completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Document ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main setup and execution"""
    print("🏗️  Advanced Legal KB+RAG System Setup")
    print("=" * 50)
    
    # Install requirements
    install_requirements()
    
    # Check data files
    if not check_data_files():
        print("\n❌ Required data files not found. Please ensure:")
        print("1. BNS PDF is at data/BNS.pdf.pdf")
        print("2. SC 2020 data is at data/supreme_court_judgments/2020/english.zip")
        return
    
    # Run system test
    test_success = await run_system_test()
    
    if test_success:
        # Run document ingestion
        ingest_success = await run_document_ingestion()
        
        if ingest_success:
            print("\n🎉 SETUP COMPLETE!")
            print("The Legal KB+RAG system is ready for use.")
            print("\nNext steps:")
            print("1. The system has processed BNS and SC 2020 documents")
            print("2. Embeddings have been generated and stored")
            print("3. You can now build the hybrid search and RAG pipeline")
        else:
            print("\n⚠️  Setup partially complete. System test passed but ingestion failed.")
    else:
        print("\n❌ Setup failed. Please check the error messages above.")

if __name__ == "__main__":
    asyncio.run(main())