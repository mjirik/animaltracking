#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs/pigtracking_dashboard"
WEB_PID_FILE="$LOG_DIR/web.pid"
WORKER_PID_FILE="$LOG_DIR/worker.pid"

stop_process() {
    local label="$1"
    local pid_file="$2"

    if [[ ! -f "$pid_file" ]]; then
        echo "$label is not running."
        return
    fi

    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid"
        echo "Stopped $label PID $pid"
    else
        echo "$label PID file existed, but process $pid was not running."
    fi
    rm -f "$pid_file"
}

stop_process "worker" "$WORKER_PID_FILE"
stop_process "web server" "$WEB_PID_FILE"
