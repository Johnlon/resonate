#!/usr/bin/env bash
# Stop the dev server — kills by PID file first, then falls back to kill-http.sh.
set -euo pipefail
[ -z "${MSYSTEM:-}" ] && echo "ERROR: must run in Git Bash on Windows, not WSL or PowerShell" && exit 1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$(dirname "$SCRIPT_DIR")/.server.pid"

if [ -f "$PID_FILE" ]; then
  pid=$(cat "$PID_FILE")
  echo "Killing server PID $pid (from .server.pid)..."
  cmd /c "taskkill /PID $pid /F /T" > /dev/null 2>&1 && echo "killed PID $pid" || echo "PID $pid already gone"
  rm -f "$PID_FILE"
fi

bash "$SCRIPT_DIR/kill-http.sh"
