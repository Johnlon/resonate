#!/usr/bin/env bash
# Start the agent's vite dev server on port 4200.
# Runs all health checks (lint, unit, golden, DQ), then starts Vite dev.
# Use stop-http.sh 4200 to stop it.
set -euo pipefail
[ -z "${MSYSTEM:-}" ] && echo "ERROR: must run in Git Bash on Windows, not WSL or PowerShell" && exit 1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/start-http.sh" 4200
