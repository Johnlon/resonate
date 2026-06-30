#!/usr/bin/env bash
# THE primary script for starting the dev/preview server.
# Runs all health checks first, then starts vite preview on port 4000.
# AI must use this script — never start the server via ad-hoc commands.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "$SCRIPT_DIR/health-check.sh"
bash "$SCRIPT_DIR/preview-4000.sh"
