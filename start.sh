#!/bin/bash
# start.sh — Start the Pathwise backend + frontend in one command.
# Run from the project root: ./start.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# ---------------------------------------------------------------------------
# Cleanup: kill both servers when this script exits (Ctrl+C or error)
# ---------------------------------------------------------------------------
cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  echo "Done. Goodbye!"
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Clear ports
# ---------------------------------------------------------------------------
echo "Clearing ports 8000 and 5173..."
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :5173 | xargs kill -9 2>/dev/null || true
sleep 1

# ---------------------------------------------------------------------------
# Start backend
# ---------------------------------------------------------------------------
echo "Starting backend (FastAPI) on http://localhost:8000 ..."
cd "$PROJECT_ROOT"
uvicorn app.api:app --port 8000 &
BACKEND_PID=$!

# Wait until the backend is actually accepting connections
echo -n "Waiting for backend"
for i in $(seq 1 20); do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo " ready!"
    break
  fi
  echo -n "."
  sleep 0.5
done

# ---------------------------------------------------------------------------
# Start frontend
# ---------------------------------------------------------------------------
echo "Starting frontend (Vite) on http://localhost:5173 ..."
cd "$PROJECT_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

# ---------------------------------------------------------------------------
# Keep running until Ctrl+C
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo "  Pathwise is running!"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  Press Ctrl+C to stop both servers."
echo "============================================"
echo ""

wait
