@echo off
REM ============================================================
REM OpenAI API Key Setup Helper
REM ============================================================

echo.
echo ============================================================
echo   OpenAI API Key Setup
echo ============================================================
echo.

if "%1"=="" (
    echo Usage: set_openai_key.bat YOUR_API_KEY
    echo.
    echo Example:
    echo   set_openai_key.bat sk-proj-abc123...
    echo.
    echo Get your API key from: https://platform.openai.com/api-keys
    echo.
    pause
    exit /b 1
)

set OPENAI_API_KEY=%1

echo ✓ OpenAI API Key has been set for this session
echo.
echo Key: %OPENAI_API_KEY:~0,10%...
echo.
echo This key will be available until you close this terminal.
echo.
echo To make it permanent, add it to your system environment variables:
echo   1. Search for "Environment Variables" in Windows
echo   2. Click "Environment Variables"
echo   3. Under "User variables", click "New"
echo   4. Variable name: OPENAI_API_KEY
echo   5. Variable value: %OPENAI_API_KEY%
echo   6. Click OK
echo.
echo Now you can run: start_local_system.bat
echo.
pause
