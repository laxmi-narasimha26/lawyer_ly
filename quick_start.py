#!/usr/bin/env python3
"""
Quick Start Script for Local MVP
One-command setup and startup
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    print("🚀 Indian Legal AI Assistant - Local MVP Quick Start")
    print("=" * 60)
    
    # Check if OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Please set your OpenAI API key first:")
        print("   Windows: set OPENAI_API_KEY=your_api_key_here")
        print("   macOS/Linux: export OPENAI_API_KEY=your_api_key_here")
        print("   Then run this script again.")
        sys.exit(1)
    
    print("✅ OpenAI API key is set")
    print("\n🔧 Starting automated setup...")
    
    # Create directories
    print("📁 Creating directories...")
    directories = ["data/documents", "data/knowledge_base", "logs"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    print("✅ Directories created")
    
    # Setup knowledge base
    print("\n📚 Setting up knowledge base...")
    try:
        subprocess.run([sys.executable, "scripts/setup_local_knowledge_base.py"], check=True)
        print("✅ Knowledge base setup complete")
    except subprocess.CalledProcessError:
        print("❌ Knowledge base setup failed")
        sys.exit(1)
    
    # Start Docker services
    print("\n🐳 Starting Docker services...")
    try:
        subprocess.run(["docker-compose", "-f", "docker-compose.local.yml", "up", "-d"], check=True)
        print("✅ Docker services started")
    except subprocess.CalledProcessError:
        print("❌ Failed to start Docker services")
        print("   Make sure Docker Desktop is running")
        sys.exit(1)
    
    # Wait for services
    print("⏳ Waiting for services to initialize...")
    import time
    time.sleep(15)
    
    # Install Python dependencies
    print("\n📦 Installing Python dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt"], check=True)
        print("✅ Python dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install Python dependencies")
        sys.exit(1)
    
    # Ingest documents
    print("\n📄 Ingesting documents...")
    try:
        subprocess.run([sys.executable, "scripts/ingest_local_documents.py"], check=True)
        print("✅ Document ingestion complete")
    except subprocess.CalledProcessError:
        print("❌ Document ingestion failed")
        sys.exit(1)
    
    # Create startup files
    print("\n🚀 Creating startup files...")
    
    # Backend startup script
    backend_start = """
import os
import sys
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment variables
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("DEBUG", "true")

# Import and run the main application
try:
    from main import app
    import uvicorn
    
    if __name__ == "__main__":
        print("🚀 Starting Indian Legal AI Assistant Backend...")
        print("📍 Backend will be available at: http://localhost:8000")
        print("📖 API Documentation: http://localhost:8000/docs")
        print("❌ Press Ctrl+C to stop")
        
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're in the backend directory and dependencies are installed")
except Exception as e:
    print(f"❌ Error starting backend: {e}")
"""
    
    with open("backend/start_local.py", "w") as f:
        f.write(backend_start)
    
    # Frontend environment
    frontend_env = """REACT_APP_API_URL=http://localhost:8000
REACT_APP_DEMO_MODE=true
REACT_APP_AUTH_ENABLED=false
"""
    
    with open("frontend/.env.local", "w") as f:
        f.write(frontend_env)
    
    # Install frontend dependencies
    print("\n📦 Installing frontend dependencies...")
    try:
        subprocess.run(["npm", "install"], cwd="frontend", check=True)
        print("✅ Frontend dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install frontend dependencies")
        print("   You can install them manually: cd frontend && npm install")
    
    # Create final instructions
    instructions = """
🎉 LOCAL MVP SETUP COMPLETE!

To start the application:

1. Backend (Terminal 1):
   cd backend
   python start_local.py

2. Frontend (Terminal 2):
   cd frontend
   npm run dev

3. Open your browser:
   http://localhost:3000

🧪 Test Queries:
- "What are the essential elements of a valid contract?"
- "What is Article 21 of the Constitution?"
- "What is the difference between murder and culpable homicide?"

📊 Services:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

🔧 Troubleshooting:
- Check services: docker-compose -f docker-compose.local.yml ps
- View logs: docker-compose -f docker-compose.local.yml logs
- Restart: docker-compose -f docker-compose.local.yml restart

✅ Setup complete! Follow the instructions above to start the application.
"""
    
    print(instructions)
    
    with open("LOCAL_STARTUP_INSTRUCTIONS.txt", "w") as f:
        f.write(instructions)

if __name__ == "__main__":
    main()