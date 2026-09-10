#!/usr/bin/env bash
# AI Order Supervisor - one-command start for Mac and Linux.
# Usage:  bash start.sh

set -e
cd "$(dirname "$0")"

echo ""
echo "============================================"
echo " AI Order Supervisor - starting everything"
echo "============================================"
echo ""

echo "[1/4] Starting Temporal and PostgreSQL in Docker..."
docker compose up -d

echo "[2/4] Starting the worker in the background..."
(cd worker && uv sync && uv run python supervisor_worker.py > worker.log 2>&1) &
WORKER_PID=$!

echo "[3/4] Starting the backend API in the background..."
(cd backend && uv sync && uv run uvicorn main:app --port 8000 > backend.log 2>&1) &
BACKEND_PID=$!

echo "[4/4] Starting the console in the background..."
(cd frontend && npm install && npm run dev > console.log 2>&1) &
CONSOLE_PID=$!

sleep 12

echo ""
echo "============================================"
echo " Everything is running."
echo "   Console:      http://localhost:3000"
echo "   Temporal UI:  http://localhost:8080"
echo "   Logs:         worker.log, backend.log, console.log"
echo "   Stop with:    Ctrl+C (stops all services)"
echo "============================================"
echo ""

wait $WORKER_PID $BACKEND_PID $CONSOLE_PID
