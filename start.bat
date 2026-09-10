@echo off
title AI Order Supervisor - One-Click Start
color 0A

echo.
echo  ============================================
echo   AI Order Supervisor - starting everything
echo  ============================================
echo.

REM Step 1: infrastructure (Temporal + PostgreSQL + dashboard)
echo [1/4] Starting Temporal and PostgreSQL in Docker...
docker compose up -d
if errorlevel 1 (
    color 0C
    echo Docker failed to start. Is Docker Desktop running?
    pause
    exit /b 1
)

REM Step 2: worker in its own window
echo [2/4] Starting the worker (new window)...
start "2 - Worker" cmd /k "cd /d %~dp0worker && uv sync && uv run python supervisor_worker.py"

REM Step 3: backend in its own window
echo [3/4] Starting the backend API (new window)...
start "3 - Backend API" cmd /k "cd /d %~dp0backend && uv sync && uv run uvicorn main:app --port 8000"

REM Step 4: console in its own window
echo [4/4] Starting the website console (new window)...
start "4 - Console" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"

REM Open the console in the browser once it has a moment to boot
timeout /t 12 /nobreak >nul
start http://localhost:3000

echo.
echo  ============================================
echo   Everything is starting in 4 windows.
echo   The website opens at localhost:3000
echo   Close a window to stop that service.
echo  ============================================
echo.
pause
