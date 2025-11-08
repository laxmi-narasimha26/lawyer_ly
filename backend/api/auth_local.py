"""
Local Authentication Router - Demo Mode
Simplified authentication for local development
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

@router.post("/login")
async def login(request: LoginRequest = None):
    """
    Demo mode login - always succeeds and returns guest user
    """
    # Generate a session ID for demo user
    session_id = str(uuid.uuid4())

    return LoginResponse(
        access_token=session_id,
        token_type="bearer",
        user={
            "id": "demo_user",
            "username": "Guest User",
            "email": "guest@demo.local",
            "role": "user"
        }
    )

@router.post("/logout")
async def logout():
    """
    Demo mode logout
    """
    return {"message": "Logged out successfully"}

@router.get("/me")
async def get_current_user():
    """
    Get current user info - returns demo user
    """
    return {
        "id": "demo_user",
        "username": "Guest User",
        "email": "guest@demo.local",
        "role": "user"
    }

@router.get("/profile")
async def get_profile():
    """
    Get user profile - returns demo user profile
    """
    return {
        "id": "demo_user",
        "username": "Guest User",
        "email": "guest@demo.local",
        "role": "user",
        "created_at": "2025-01-01T00:00:00Z",
        "preferences": {
            "theme": "light",
            "language": "en"
        }
    }
