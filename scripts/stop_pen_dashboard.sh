#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs/pigtracking_dashboard"
WEB_PID_FILE="$LOG_DIR/web.pid"
WORKER_PID_FILE="$LOG_DIR/worker.pid"
WEB_PATTERN="src/animaltracking/manage.py runserver"
WORKER_PATTERN="src/animaltracking/manage.py run_pen_worker"

stop_pid() {
    local label="$1"
    local pid="$2"
    if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" 2>/dev/null || true
        echo "Stopped $label PID $pid"
    fi
}

stop_by_pattern() {
    local label="$1"
    local pattern="$2"
    local pids

    pids="$(pgrep -f "$pattern" || true)"
    if [[ -z "$pids" ]]; then
        echo "$label is not running."
        return
    fi

    while read -r pid; do
        [[ -n "$pid" ]] || continue
        stop_pid "$label" "$pid"
    done <<<"$pids"
}

stop_process() {
    local label="$1"
    local pid_file="$2"
    local pattern="$3"

    if [[ -f "$pid_file" ]]; then
        local pid
        pid="$(cat "$pid_file")"
        stop_pid "$label" "$pid"
        rm -f "$pid_file"
    fi

    stop_by_pattern "$label" "$pattern"
}

stop_process "worker" "$WORKER_PID_FILE" "$WORKER_PATTERN"
stop_process "web server" "$WEB_PID_FILE" "$WEB_PATTERN"
