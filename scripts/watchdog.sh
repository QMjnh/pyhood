#!/bin/bash
# Watchdog for overnight autoresearch runner.
# Add to crontab: */30 * * * * /path/to/scripts/watchdog.sh
#
# Resume-safe: the runner auto-detects previous state from experiments.json
# so restarting is always safe.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PIDFILE="/tmp/autoresearch.pid"
LOGFILE="${PROJECT_DIR}/autoresearch_results/watchdog.log"
PYTHON="${PYTHON:-python3}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOGFILE"
}

mkdir -p "$(dirname "$LOGFILE")"

# Check if already running
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        log "Runner still alive (PID $PID). Nothing to do."
        exit 0
    else
        log "Stale pidfile found (PID $PID not running). Cleaning up."
        rm -f "$PIDFILE"
    fi
fi

# Start the runner
log "Starting overnight runner..."
cd "$PROJECT_DIR"
nohup "$PYTHON" scripts/run_overnight.py "$@" >> "${PROJECT_DIR}/autoresearch_results/runner_stdout.log" 2>&1 &
RUNNER_PID=$!
echo "$RUNNER_PID" > "$PIDFILE"
log "Runner started with PID $RUNNER_PID"
