@echo off
setlocal
title Growth Engine POC - AI Sales Intelligence
color 0A
cd /d "%~dp0"

echo.
echo  ================================================================
echo    GROWTH ENGINE POC - Contact Centre AI
echo    AI-Driven Sales Lead Identification
echo  ================================================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python is not installed or not on PATH.
    echo          Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo  [1/3] Installing dependencies...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo  [ERROR] Dependency installation failed. See messages above.
    pause
    exit /b 1
)
echo        Done.
echo.

echo  [2/3] Checking configuration...
if defined ANTHROPIC_API_KEY (
    echo        Claude AI: ENABLED - live analysis layered on the demo.
) else (
    echo        Claude AI: OFF - running the scripted demo.
    echo        To enable:  set ANTHROPIC_API_KEY=sk-ant-your-key-here
)
if /i "%CUSTOMER_PLATFORM%"=="unomi" (
    echo        Customer platform: Apache Unomi - start it from the platform folder first.
) else (
    echo        Customer platform: built-in store.
    echo        To use Apache Unomi:  set CUSTOMER_PLATFORM=unomi
)
echo        Assets: vendored locally, no internet required.
echo.

echo  [3/3] Starting server at http://localhost:8000
start "" http://localhost:8000
echo  ----------------------------------------------------------------
echo   Press Ctrl+C to stop.
echo.

python backend\main.py

echo.
echo  Server stopped.
pause
