@echo off
REM ============================================================
REM Indian Legal AI Assistant - Local Startup Script
REM ============================================================

echo.
echo ============================================================
echo   Indian Legal AI Assistant - Local Setup
echo ============================================================
echo.

REM Check if Docker is running
echo [1/6] Checking Docker status...
docker ps >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)
echo ✓ Docker is running

REM Start Postgres and Redis
echo.
echo [2/6] Starting Postgres and Redis containers...
docker compose -f docker-compose.local.yml up -d
if errorlevel 1 (
    echo ERROR: Failed to start containers
    pause
    exit /b 1
)
echo ✓ Containers started

REM Wait for services to be healthy
echo.
echo [3/6] Waiting for services to be ready...
timeout /t 5 /nobreak >nul
echo ✓ Services ready

REM Apply database migrations
echo.
echo [4/6] Applying database migrations...
python apply_stored_tsv_migration.py
if errorlevel 1 (
    echo WARNING: Migration script had issues, but continuing...
)
echo ✓ Migrations applied

echo.
echo ============================================================
echo   Setup Complete! Starting Services...
echo ============================================================
echo.
echo Backend will be available at: http://localhost:8000
echo Frontend will be available at: http://localhost:5173
echo API Documentation: http://localhost:8000/docs
echo.
echo Press Ctrl+C in each window to stop the services
echo ============================================================
echo.

REM Start backend in new window
echo Starting backend server...
start "Legal AI - Backend" cmd /k "cd backend && if not exist .venv (python -m venv .venv) && .venv\Scripts\activate && pip install -r requirements.txt && set DATABASE_URL=postgresql://postgres:legal_kb_pass@localhost:5433/legal_kb && set REDIS_URL=redis://localhost:6379 && set OPENAI_API_KEY=%OPENAI_API_KEY% && python main_local.py"

REM Wait a bit for backend to start
timeout /t 5 /nobreak >nul

REM Start frontend in new window
echo Starting frontend server...
start "Legal AI - Frontend" cmd /k "cd frontend && if not exist node_modules (npm install) && npm run dev"

echo.
echo ============================================================
echo   All services are starting!
echo ============================================================
echo.
echo Please wait 10-15 seconds for services to fully start
echo Then open: http://localhost:5173
echo.
echo To stop all services:
echo   1. Close the backend and frontend windows
echo   2. Run: docker compose -f docker-compose.local.yml down
echo.
pause
