#!/usr/bin/env bash
# Start the dev server — runs all quality checks first, then serves on port 4000.
# This is the ONE script AI and developers should use. Never run npm run dev directly.
set -euo pipefail

PASS=0
FAIL=0
ERRORS=()

run() {
  local label="$1"; shift
  echo ""
  echo "── $label ──────────────────────────────────"
  if "$@"; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    ERRORS+=("$label")
  fi
}

echo "========================================"
echo "  Health checks — $(date '+%H:%M:%S')"
echo "========================================"

run "ESLint"       npm run lint
run "Unit tests"   node --test packages/engine/test/*.test.mjs packages/ui/test/config.test.mjs
run "Golden tests" node packages/engine/test/golden.test.mjs
run "DQ check"     python scripts/dq_check.py

echo ""
echo "========================================"
if [ "$FAIL" -gt 0 ]; then
  echo "  $FAIL check(s) FAILED — server not started:"
  for e in "${ERRORS[@]}"; do echo "    - $e"; done
  echo "========================================"
  exit 1
fi
echo "  All $PASS checks passed — starting server"
echo "========================================"

# Kill project port range then start dev server on 4000
for port in $(seq 4000 4005); do
  pids=$(netstat -ano | awk "/:${port}[[:space:]].*LISTENING/{print \$5}" | sort -u)
  for pid in $pids; do
    cmd /c "taskkill /PID $pid /F" > /dev/null 2>&1 && echo "killed PID $pid on port $port" || true
  done
done

sleep 2
echo ""
npm run dev -- --port 4000 --strictPort
