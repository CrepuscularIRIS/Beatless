#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
    echo "Stopping..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend (port 3721)..."
cd "$DIR/backend"
uv run uvicorn server:app --host "${DASHBOARD_HOST:-127.0.0.1}" --port "${DASHBOARD_API_PORT:-3721}" &
BACKEND_PID=$!

echo "Starting frontend (port 3720)..."
cd "$DIR/frontend"
npm run dev -- --host "${DASHBOARD_FRONTEND_HOST:-127.0.0.1}" --port "${DASHBOARD_FRONTEND_PORT:-3720}" &
FRONTEND_PID=$!

echo ""
echo "  Dashboard: http://${DASHBOARD_FRONTEND_HOST:-127.0.0.1}:${DASHBOARD_FRONTEND_PORT:-3720}"
echo "  API:       http://${DASHBOARD_HOST:-127.0.0.1}:${DASHBOARD_API_PORT:-3721}/api/status"
echo ""

wait
