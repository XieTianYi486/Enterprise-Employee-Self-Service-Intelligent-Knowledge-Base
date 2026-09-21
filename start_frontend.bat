@echo off
title EESS Frontend
cd /d "%~dp0frontend"

echo ============================================
echo   Enterprise Employee Self-Service - Frontend
echo ============================================
echo.

if not exist "node_modules" (
    echo [1/2] Installing Node.js dependencies...
    call npm install
) else (
    echo [1/2] Dependencies already installed
)

echo [2/2] Starting Vite dev server on port 5173...
echo.
echo   Frontend: http://localhost:5173
echo   Press Ctrl+C to stop
echo.

call npm run dev

pause
