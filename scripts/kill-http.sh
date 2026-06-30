#!/usr/bin/env bash
# Kill all processes on the project's reserved port range (4000-4005).
# Escalation chain per port:
#   1. taskkill /PID /F /T  (Windows tree-kill)
#   2. kill -9 $pid         (bash signal)
#   3. wmic terminate       (WMI API path)
#   4. taskkill /IM node.exe /F /T  (image-name nuke)
# Loops until netstat confirms port is free or 10 attempts exhausted.
# Pass explicit ports to override: scripts/kill-http.sh 4000 4001
set -euo pipefail
[ -z "${MSYSTEM:-}" ] && echo "ERROR: must run in Git Bash on Windows, not WSL or PowerShell" && exit 1

PORT_MIN=4000
PORT_MAX=4005

if [ $# -gt 0 ]; then
  ports=("$@")
else
  ports=()
  for p in $(seq "$PORT_MIN" "$PORT_MAX"); do ports+=("$p"); done
fi

_pids_on_port() {
  netstat -ano 2>/dev/null \
    | awk "/:$1[[:space:]].*LISTENING/{print \$5}" \
    | sort -u
}

_kill_pid() {
  local pid="$1" port="$2" attempt="$3"

  # Step 1: Windows taskkill tree-kill
  if [ "$attempt" -le 2 ]; then
    cmd /c "taskkill /PID $pid /F /T" > /dev/null 2>&1 \
      && echo "  [attempt $attempt] taskkill /T killed PID $pid" \
      || true
  fi

  # Step 2: bash kill -9
  if [ "$attempt" -eq 3 ]; then
    kill -9 "$pid" 2>/dev/null \
      && echo "  [attempt $attempt] kill -9 sent to PID $pid" \
      || echo "  [attempt $attempt] kill -9 failed for PID $pid"
  fi

  # Step 3: wmic terminate
  if [ "$attempt" -eq 4 ]; then
    cmd /c "wmic process where \"ProcessId=$pid\" call terminate" > /dev/null 2>&1 \
      && echo "  [attempt $attempt] wmic terminate PID $pid" \
      || echo "  [attempt $attempt] wmic terminate failed for PID $pid"
  fi

  # Step 4+: nuke all node.exe
  if [ "$attempt" -ge 5 ]; then
    echo "  [attempt $attempt] escalating — taskkill /IM node.exe /F /T"
    cmd /c "taskkill /IM node.exe /F /T" > /dev/null 2>&1 || true
  fi
}

_diagnose_port() {
  local port="$1"
  local pid
  pid=$(_pids_on_port "$port")
  echo "  DIAGNOSTIC — port $port still occupied:"
  echo "    netstat PID: $pid"
  cmd /c "tasklist /FI \"PID eq $pid\" /FO LIST" 2>/dev/null || true
  cmd /c "wmic process where \"ProcessId=$pid\" get Name,CommandLine /FORMAT:LIST" 2>/dev/null || true
}

for port in "${ports[@]}"; do
  pids=$(_pids_on_port "$port")
  [ -z "$pids" ] && continue

  echo "port $port: found PID(s) $pids — killing..."
  for attempt in $(seq 1 10); do
    pids=$(_pids_on_port "$port")
    [ -z "$pids" ] && echo "port $port: free after $((attempt - 1)) attempt(s)" && break

    for pid in $pids; do
      _kill_pid "$pid" "$port" "$attempt"
    done
    sleep 2

    if [ "$attempt" = "10" ]; then
      _diagnose_port "$port"
      echo "port $port: WARNING — still occupied, proceeding anyway"
    fi
  done
done

echo "done"
