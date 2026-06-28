#!/usr/bin/env bash
# Run the Knowledge Platform control panel locally:
# - compliance reasoning microservice (:5310)
# - backend API (FastAPI, :8010)
# - frontend dev server (Vite, :5200, which proxies /api to the backend).
# Prerequisites (one-time): python venv + deps, and frontend npm install.
#   python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
#   (cd frontend && npm install)
# Stop everything with Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")/.."

PIDS=()
cleanup() {
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT

PYTHONPATH=. KP_COMPLIANCE_AGENT_ENABLED="${KP_COMPLIANCE_AGENT_ENABLED:-1}" \
  KP_COMPLIANCE_LLM_MODEL="${KP_COMPLIANCE_LLM_MODEL:-deepseek-r1:32b}" \
  .venv/bin/python -m uvicorn services.compliance_reasoning.app:app --host 127.0.0.1 --port 5310 &
PIDS+=("$!")

KP_DATA_DIR=data KP_COMPLIANCE_REASONING_URL=http://127.0.0.1:5310 \
  KP_GOVERNANCE_LLM_MODEL="${KP_GOVERNANCE_LLM_MODEL:-deepseek-r1:32b}" \
  .venv/bin/python -m uvicorn assistant.api.app:app --app-dir src --port 8010 &
PIDS+=("$!")

cd frontend && npm start
