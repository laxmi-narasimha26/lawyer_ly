@echo off
REM ============================================================
REM Setup Verification Script
REM ============================================================

echo.
echo ============================================================
echo   Indian Legal AI Assistant - Setup Verification
echo ============================================================
echo.

REM Check Python
echo [1/7] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Python is not installed or not in PATH
    echo   Download from: https://www.python.org/downloads/
    set PYTHON_OK=0
) else (
    python --version
    echo ✓ Python is installed
    set PYTHON_OK=1
)
echo.

REM Check Node.js
echo [2/7] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Node.js is not installed or not in PATH
    echo   Download from: https://nodejs.org/
    set NODE_OK=0
) else (
    node --version
    echo ✓ Node.js is installed
    set NODE_OK=1
)
echo.

REM Check Docker
echo [3/7] Checking Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Docker is not installed or not in PATH
    echo   Download from: https://www.docker.com/products/docker-desktop
    set DOCKER_OK=0
) else (
    docker --version
    echo ✓ Docker is installed
    set DOCKER_OK=1
)
echo.

REM Check Docker running
echo [4/7] Checking if Docker is running...
docker ps >nul 2>&1
if errorlevel 1 (
    echo ✗ Docker is not running
    echo   Please start Docker Desktop
    set DOCKER_RUNNING=0
) else (
    echo ✓ Docker is running
    set DOCKER_RUNNING=1
)
echo.

REM Check OpenAI API Key
echo [5/7] Checking OpenAI API Key...
if "%OPENAI_API_KEY%"=="" (
    echo ✗ OPENAI_API_KEY environment variable is not set
    echo   Set it with: set OPENAI_API_KEY=sk-your-key-here
    set OPENAI_OK=0
) else (
    echo ✓ OPENAI_API_KEY is set
    set OPENAI_OK=1
)
echo.

REM Check if containers exist
echo [6/7] Checking Docker containers...
docker ps -a | findstr "legal-ai-postgres-local" >nul 2>&1
if errorlevel 1 (
    echo ℹ PostgreSQL container not found (will be created on first run)
    set POSTGRES_EXISTS=0
) else (
    echo ✓ PostgreSQL container exists
    set POSTGRES_EXISTS=1
)

docker ps -a | findstr "legal-ai-redis-local" >nul 2>&1
if errorlevel 1 (
    echo ℹ Redis container not found (will be created on first run)
    set REDIS_EXISTS=0
) else (
    echo ✓ Redis container exists
    set REDIS_EXISTS=1
)
echo.

REM Check if backend dependencies are installed
echo [7/7] Checking backend dependencies...
if exist "backend\.venv" (
    echo ✓ Backend virtual environment exists
    set BACKEND_VENV=1
) else (
    echo ℹ Backend virtual environment not found (will be created on first run)
    set BACKEND_VENV=0
)

if exist "frontend\node_modules" (
    echo ✓ Frontend dependencies installed
    set FRONTEND_DEPS=1
) else (
    echo ℹ Frontend dependencies not installed (will be installed on first run)
    set FRONTEND_DEPS=0
)
echo.

REM Summary
echo ============================================================
echo   Verification Summary
echo ============================================================
echo.

if %PYTHON_OK%==1 if %NODE_OK%==1 if %DOCKER_OK%==1 if %DOCKER_RUNNING%==1 if %OPENAI_OK%==1 (
    echo ✓ All prerequisites are met!
    echo.
    echo You are ready to start the system.
    echo.
    echo Run: start_local_system.bat
    echo.
) else (
    echo ⚠ Some prerequisites are missing:
    echo.
    if %PYTHON_OK%==0 echo   - Install Python 3.9+
    if %NODE_OK%==0 echo   - Install Node.js 18+
    if %DOCKER_OK%==0 echo   - Install Docker Desktop
    if %DOCKER_RUNNING%==0 echo   - Start Docker Desktop
    if %OPENAI_OK%==0 echo   - Set OPENAI_API_KEY environment variable
    echo.
    echo Please install missing prerequisites and run this script again.
    echo.
)

echo ============================================================
pause
