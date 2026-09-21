@echo off
title EESS Backend
cd /d "%~dp0backend"

echo ============================================
echo   Enterprise Employee Self-Service - Backend
echo ============================================
echo.

if not exist ".env" (
    echo [WARN] .env not found, copying from .env.example...
    copy .env.example .env >nul
    echo [INFO] Please edit backend\.env with your Bailian API Key
    pause
    exit /b 1
)

if not exist "data" mkdir data
if not exist "uploads" mkdir uploads

echo [1/2] Installing Python dependencies...
pip install -r requirements.txt -q 2>nul

echo [2/2] Starting FastAPI on port 8001...
echo.
echo   API Docs: http://localhost:8001/docs
echo   Account:  admin / password from backend\.env ADMIN_PASSWORD
echo   Press Ctrl+C to stop
echo.

set PYTHONIOENCODING=utf-8
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

pause
