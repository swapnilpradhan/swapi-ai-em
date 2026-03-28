#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Helper: check command exists
need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need_cmd lsof
need_cmd python3
need_cmd npm

echo "==> SWAPI AI-EM launch"

mkdir -p "$ROOT_DIR/logs"

if [[ ! -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  echo "Missing venv activate script: $ROOT_DIR/.venv/bin/activate" >&2
  echo "Create the venv and install deps first (e.g., 'uv sync' or your existing setup steps)." >&2
  exit 1
fi

# 1) Ensure PostgreSQL is running (Homebrew service)
if command -v brew >/dev/null 2>&1; then
  if brew services list 2>/dev/null | grep -q "postgresql@16.*started"; then
    echo "- PostgreSQL: already running"
  else
    echo "- Starting PostgreSQL (brew services start postgresql@16)"
    brew services start postgresql@16 >/dev/null || true
  fi
else
  echo "- brew not found; skipping PostgreSQL auto-start"
fi

# 2) Ensure Redis is running (optional)
if command -v brew >/dev/null 2>&1; then
  if brew services list 2>/dev/null | grep -q "redis.*started"; then
    echo "- Redis: already running"
  else
    echo "- Starting Redis (brew services start redis)"
    brew services start redis >/dev/null || true
  fi
else
  echo "- brew not found; skipping Redis auto-start"
fi

# 3) Start FastAPI backend (port 8000)
if lsof -ti :8000 >/dev/null 2>&1; then
  echo "- Backend: already running on :8000"
else
  echo "- Starting backend (uvicorn) on :8000"
  (
    cd "$ROOT_DIR/backend"
    source "$ROOT_DIR/.venv/bin/activate"
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > "$ROOT_DIR/logs/backend.log" 2>&1 &
    echo $! > "$ROOT_DIR/logs/backend.pid"
  )
fi

# 4) Start Angular dev server (port 4200)
if lsof -ti :4200 >/dev/null 2>&1; then
  echo "- Frontend: already running on :4200"
else
  echo "- Starting frontend (ng serve) on :4200"
  (
    cd "$ROOT_DIR/frontend"
    nohup npm run start -- --host 0.0.0.0 --port 4200 > "$ROOT_DIR/logs/frontend.log" 2>&1 &
    echo $! > "$ROOT_DIR/logs/frontend.pid"
  )
fi

echo ""
echo "==> Running services"
echo "- Backend:   http://localhost:8000 (docs: /docs)"
echo "- Frontend:  http://localhost:4200"
echo "- Admin API: http://localhost:8000/api/admin/metrics"
echo ""
echo "Logs:"
echo "- $ROOT_DIR/logs/backend.log"
echo "- $ROOT_DIR/logs/frontend.log"
