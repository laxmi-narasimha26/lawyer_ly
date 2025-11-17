"""
Vercel Serverless Function Entry Point for FastAPI Backend
"""
import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from backend.main import app

# Export the FastAPI app for Vercel
handler = app
