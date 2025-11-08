"""
Local FastAPI Application Entry Point
Configured for local development with conversation management
"""

import os
import sys
from pathlib import Path
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment variables for local development
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("DEBUG", "true")

# Import after setting environment
from config.local_settings import LOGGING_CONFIG, DEMO_CONFIG
from api.chat import router as chat_router
from api.health_local import router as health_router
from api.auth_local import router as auth_router
from services.conversation_manager import conversation_manager
from services.local_openai_service import local_openai_service

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG["level"]),
    format=LOGGING_CONFIG["format"],
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGGING_CONFIG["file"]) if Path(LOGGING_CONFIG["file"]).parent.exists() else logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Indian Legal AI Assistant",
    description="AI-powered legal assistant for Indian law with conversation management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("🚀 Starting Indian Legal AI Assistant (Local Mode)")
    
    try:
        # Test OpenAI connection
        connection_test = await local_openai_service.test_connection()
        if connection_test["status"] == "connected":
            logger.info("✅ OpenAI API connection successful")
        else:
            logger.error(f"❌ OpenAI API connection failed: {connection_test.get('error')}")
    
    except Exception as e:
        logger.error(f"❌ Error testing OpenAI connection: {e}")
    
    logger.info("🎯 Local MVP ready for demonstration")
    logger.info("📍 API Documentation: http://localhost:8000/docs")
    logger.info("🧪 Health Check: http://localhost:8000/health")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down Indian Legal AI Assistant")

@app.get("/")
async def root():
    """Root endpoint with system information"""
    return {
        "message": "Indian Legal AI Assistant - Local MVP",
        "version": "1.0.0",
        "environment": "local",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "Legal Q&A with citations",
            "Document upload and analysis", 
            "Conversation history management",
            "Multiple modes (Q&A, Drafting, Summarization)",
            "Real-time context retention"
        ],
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "chat": "/chat",
            "conversations": "/chat/conversations"
        }
    }

@app.get("/demo")
async def demo_info():
    """Demo information and sample queries"""
    if not DEMO_CONFIG["enabled"]:
        raise HTTPException(status_code=404, detail="Demo mode not enabled")
    
    return {
        "demo_mode": True,
        "sample_queries": DEMO_CONFIG["sample_queries"],
        "sample_documents": DEMO_CONFIG["sample_documents"],
        "instructions": [
            "1. Use the sample queries to test the system",
            "2. Try uploading legal documents for analysis",
            "3. Explore different modes (Q&A, Drafting, Summarization)",
            "4. Check conversation history and context retention"
        ],
        "api_examples": {
            "send_message": {
                "url": "/chat/message",
                "method": "POST",
                "body": {
                    "message": "What are the essential elements of a valid contract?",
                    "mode": "qa",
                    "user_id": "demo_user"
                }
            },
            "get_conversations": {
                "url": "/chat/conversations?user_id=demo_user",
                "method": "GET"
            }
        }
    }

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again.",
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    print("🚀 Starting Indian Legal AI Assistant - Local MVP")
    print("=" * 60)
    print("📍 Backend will be available at: http://localhost:8000")
    print("📖 API Documentation: http://localhost:8000/docs")
    print("🧪 Demo Information: http://localhost:8000/demo")
    print("❌ Press Ctrl+C to stop")
    print("=" * 60)
    
    uvicorn.run(
        "main_local:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )
