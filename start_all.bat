@echo off
title EESS Launcher
cd /d "%~dp0"

echo ============================================
echo   Enterprise Employee Self-Service System
echo   Starting All Services
echo ============================================
echo.
echo   Backend:  http://localhost:8001
echo   Frontend: http://localhost:5173
echo   Account:  admin / password from backend\.env ADMIN_PASSWORD
echo.

echo Cleaning up old backend process on port 8001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001.*LISTENING" 2^>nul') do taskkill /PID %%a /F >nul 2>nul

echo Starting Backend...
start "EESS-Backend" cmd /k "cd /d %~dp0backend && set PYTHONIOENCODING=utf-8 && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"

timeout /t 4 /nobreak >nul

echo Starting Frontend...
start "EESS-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Both services started in separate windows.
echo Close the service windows to stop, or close this window.
echo.
pause
