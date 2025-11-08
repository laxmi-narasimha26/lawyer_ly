"""
Local Health Check Endpoints
Simplified health checks for local development without Azure dependencies
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import redis
from sqlalchemy import create_engine, text
import os

router = APIRouter(tags=["health"])

def check_database() -> Dict[str, str]:
    """Check PostgreSQL database connection"""
    try:
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:legal_kb_pass@localhost:5433/legal_kb")
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        return {"status": "connected", "type": "postgresql"}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}

def check_redis() -> Dict[str, str]:
    """Check Redis connection"""
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = redis.Redis.from_url(redis_url)
        redis_client.ping()
        
        return {"status": "connected", "type": "redis"}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}

def check_openai() -> Dict[str, str]:
    """Check OpenAI API key configuration"""
    try:
        api_key = os.getenv("OPENAI_API_KEY", "")
        
        if not api_key:
            return {"status": "not_configured", "error": "OPENAI_API_KEY not set"}
        
        if not api_key.startswith("sk-"):
            return {"status": "invalid", "error": "Invalid API key format"}
        
        return {"status": "configured", "key_prefix": api_key[:10] + "..."}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check for local development
    
    Returns:
        Health status of all system components
    """
    
    # Check all components
    database_status = check_database()
    redis_status = check_redis()
    openai_status = check_openai()
    
    # Determine overall status
    all_healthy = (
        database_status["status"] == "connected" and
        redis_status["status"] == "connected" and
        openai_status["status"] == "configured"
    )
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "service": "Indian Legal AI Assistant",
        "version": "1.0.0",
        "environment": "local",
        "components": {
            "database": database_status,
            "redis": redis_status,
            "openai": openai_status
        },
        "endpoints": {
            "api": "http://localhost:8000/api/v1",
            "docs": "http://localhost:8000/docs",
            "chat": "http://localhost:8000/api/v1/chat/query"
        }
    }

@router.get("/")
async def root_health() -> Dict[str, Any]:
    """
    Simple health check endpoint
    """
    return {
        "status": "online",
        "message": "Indian Legal AI Assistant is running",
        "timestamp": datetime.now().isoformat()
    }
