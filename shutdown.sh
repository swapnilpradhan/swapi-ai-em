#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need_cmd lsof

stop_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "- Stopping ${name} (pid $pid)"
      kill "$pid" >/dev/null 2>&1 || true
      sleep 1
      if kill -0 "$pid" >/dev/null 2>&1; then
        echo "  - Force killing ${name} (pid $pid)"
        kill -9 "$pid" >/dev/null 2>&1 || true
      fi
    else
      echo "- ${name}: pid file present but process not running"
    fi
    rm -f "$pid_file" >/dev/null 2>&1 || true
  fi
}

stop_port() {
  local name="$1"
  local port="$2"

  local pids
  pids="$(lsof -ti ":${port}" 2>/dev/null || true)"
  if [[ -n "${pids:-}" ]]; then
    echo "- Stopping ${name} (port :${port})"
    # shellcheck disable=SC2086
    kill ${pids} >/dev/null 2>&1 || true
    sleep 1
    local still
    still="$(lsof -ti ":${port}" 2>/dev/null || true)"
    if [[ -n "${still:-}" ]]; then
      echo "  - Force killing ${name} (port :${port})"
      # shellcheck disable=SC2086
      kill -9 ${still} >/dev/null 2>&1 || true
    fi
  else
    echo "- ${name}: not running on :${port}"
  fi
}

echo "==> SWAPI AI-EM shutdown"

# Stop app processes started by launch.sh
stop_pid_file "Backend" "$ROOT_DIR/logs/backend.pid"
stop_pid_file "Frontend" "$ROOT_DIR/logs/frontend.pid"

# Fallback: stop by port (covers cases where pid files were deleted)
stop_port "Backend" 8000
stop_port "Frontend" 4200

# Optional: stop services (only if Homebrew exists). Comment out if you prefer to keep them running.
if command -v brew >/dev/null 2>&1; then
  echo "- Stopping Redis (brew services stop redis)"
  brew services stop redis >/dev/null 2>&1 || true

  echo "- Stopping PostgreSQL (brew services stop postgresql@16)"
  brew services stop postgresql@16 >/dev/null 2>&1 || true
fi

echo "==> Done"
