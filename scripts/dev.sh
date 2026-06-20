#!/usr/bin/env bash
# Run the Knowledge Platform control panel locally: backend (FastAPI, :8010)
# plus the frontend dev server (Vite, :5200, which proxies /api to the backend).
# Prerequisites (one-time): python venv + deps, and frontend npm install.
#   python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
#   (cd frontend && npm install)
# Stop everything with Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")/.."

KP_DATA_DIR=data .venv/bin/python -m uvicorn assistant.api.app:app --app-dir src --port 8010 &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

cd frontend && npm start
