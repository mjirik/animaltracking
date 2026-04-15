#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs/pigtracking_dashboard"
WEB_LOG="$LOG_DIR/web.log"
WORKER_LOG="$LOG_DIR/worker.log"
WEB_PID_FILE="$LOG_DIR/web.pid"
WORKER_PID_FILE="$LOG_DIR/worker.pid"

PORT="${ANTRA_PORT:-8000}"
HOST="${ANTRA_BIND_HOST:-0.0.0.0}"
DEVICE="${RFDETR_DEVICE:-cuda:0}"
THRESHOLD="${PEN_WORKER_THRESHOLD:-0.25}"
WEB_PATTERN="src/animaltracking/manage.py runserver ${HOST}:${PORT}"
WORKER_PATTERN="src/animaltracking/manage.py run_pen_worker"
PYTHON_BIN="${PIGTRACKING_PYTHON:-$HOME/miniconda3/envs/pigtracking/bin/python}"

mkdir -p "$LOG_DIR"
mkdir -p "$ROOT_DIR/src/animaltracking/media"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python executable for env pigtracking not found: $PYTHON_BIN" >&2
    echo "Set PIGTRACKING_PYTHON explicitly or create the conda env first." >&2
    exit 1
fi

timestamp() {
    date '+%Y-%m-%d %H:%M:%S %Z'
}

append_log_header() {
    local log_file="$1"
    local label="$2"
    {
        echo
        echo "==== ${label} start: $(timestamp) ===="
    } >>"$log_file"
}

is_running() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid="$(cat "$pid_file")"
        if kill -0 "$pid" >/dev/null 2>&1; then
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

find_existing_pid() {
    local pattern="$1"
    pgrep -f "$pattern" | head -n 1 || true
}

wait_for_pattern_to_clear() {
    local pattern="$1"
    local label="$2"
    local attempts=10
    local existing_pid=""

    while (( attempts > 0 )); do
        existing_pid="$(find_existing_pid "$pattern")"
        if [[ -z "$existing_pid" ]]; then
            return 0
        fi
        sleep 1
        ((attempts--))
    done

    echo "$label is still shutting down or already running with PID $existing_pid" >&2
    return 1
}

start_web() {
    if is_running "$WEB_PID_FILE"; then
        echo "Web server already running with PID $(cat "$WEB_PID_FILE")"
        return
    fi
    local existing_pid
    existing_pid="$(find_existing_pid "$WEB_PATTERN")"
    if [[ -n "$existing_pid" ]]; then
        if wait_for_pattern_to_clear "$WEB_PATTERN" "Web server"; then
            existing_pid=""
        else
            echo "$existing_pid" >"$WEB_PID_FILE"
            echo "Web server already running with PID $existing_pid"
            return
        fi
    fi

    append_log_header "$WEB_LOG" "web"

    (
        cd "$ROOT_DIR"
        PYTHONUNBUFFERED=1 "$PYTHON_BIN" -u src/animaltracking/manage.py migrate >>"$WEB_LOG" 2>&1
        exec env PYTHONUNBUFFERED=1 "$PYTHON_BIN" -u src/animaltracking/manage.py runserver "${HOST}:${PORT}"
    ) >>"$WEB_LOG" 2>&1 &
    echo $! >"$WEB_PID_FILE"
    echo "Started web server on ${HOST}:${PORT} with PID $(cat "$WEB_PID_FILE")"
}

start_worker() {
    if is_running "$WORKER_PID_FILE"; then
        echo "Worker already running with PID $(cat "$WORKER_PID_FILE")"
        return
    fi
    local existing_pid
    existing_pid="$(find_existing_pid "$WORKER_PATTERN")"
    if [[ -n "$existing_pid" ]]; then
        if wait_for_pattern_to_clear "$WORKER_PATTERN" "Worker"; then
            existing_pid=""
        else
            echo "$existing_pid" >"$WORKER_PID_FILE"
            echo "Worker already running with PID $existing_pid"
            return
        fi
    fi

    append_log_header "$WORKER_LOG" "worker"

    (
        cd "$ROOT_DIR"
        exec env PYTHONUNBUFFERED=1 "$PYTHON_BIN" -u src/animaltracking/manage.py run_pen_worker --device "$DEVICE" --threshold "$THRESHOLD"
    ) >>"$WORKER_LOG" 2>&1 &
    echo $! >"$WORKER_PID_FILE"
    echo "Started worker with PID $(cat "$WORKER_PID_FILE")"
}

start_web
start_worker

echo "Logs:"
echo "  $WEB_LOG"
echo "  $WORKER_LOG"
